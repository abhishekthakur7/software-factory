# Platform plumbing and the human surface: what soft-factory can port from Mastra

Packet: storage abstraction; pubsub/events/signals; channels (Slack/Telegram); notifications; auth/roles;
guardrail processors; studio/playground; agent-builder/editor; CLI.

Mastra commit read: `/Users/abhishekthakur/Developer/mastra`, 2026-09-10. Soft-factory read at the same
commit as `git log` shows in this session (`7bc61ee` at HEAD).

## 1. What Mastra does here

### 1.1 Storage: per-domain interfaces, not one schema

Mastra's storage is not one table set behind one interface. `packages/core/src/storage/base.ts` defines
`MastraCompositeStore` (the class every backend extends) as a bag of ~24 optional per-domain interfaces
(`StorageDomains` type), each with its own `base.ts` contract: `agents`, `promptBlocks`, `scorerDefinitions`,
`mcpClients`, `mcpServers`, `workspaces`, `skills`, `favorites`, `toolProviderConnections` (the "editor"
domains); `memory`, `workflows`, `workflowDefinitions`, `observability`, `scores`, `channels`,
`notifications`, `datasets`, `experiments`, `schedules`, `backgroundTasks`, `harness`, `threadState`,
`knowledge`, `blobs`, `operations`. A `getStore<K>(name)` call resolves one domain; a caller never reaches
into a table directly. `DOMAIN_KEYS` plus a compile-time exhaustiveness check forces every new domain to
register in two places at once, so a domain can never exist in the type but not the runtime registry.

The reason to split, from the same file's docstrings: different domains can be sourced from *different*
backends in the same running app — `new MastraCompositeStore({ default: pgStore, editor: filesystemStore,
domains: { memory: libsqlStore.stores.memory } })`. The "editor" domains (agent/prompt/tool config) commonly
live on a filesystem or a git-backed provider while everything else (traces, messages, run snapshots) stays
on a real database, because the two have different lifecycles: one is small, human-edited, and wants review;
the other is high-volume and machine-written.

**Versioning is a shared generic, not per-domain code.** `domains/versioned.ts` defines
`VersionedStorageDomain<TEntity, TSnapshot, TResolved, TVersion, ...>`, used by `agents`, `promptBlocks`,
`scorerDefinitions`, `mcpClients`, `mcpServers`, `skills`, `workspaces`. Shape: a thin entity row
(`{id, status: 'draft'|'published'|'archived', activeVersionId?, ...}`) plus separate immutable version rows
(`{id, versionNumber, changedFields?, changeMessage?, createdAt}`), `versionNumber` a strictly increasing
integer per entity. Resolution (`getByIdResolved`) takes `{status:'draft'}` (latest version), `{status:
'published'}` (the `activeVersionId` version, the default), or `{versionId}` (an exact pin). "Publish" is
"move `activeVersionId`"; "rollback" is "move `activeVersionId` to an older version" — there is no dedicated
rollback endpoint, and no diff/compare API in the base class. The one diff-shaped thing is
`changedFields: string[]`, computed by `packages/editor/src/namespaces/versioned-update.ts` by a plain
deep-equal against the latest version before deciding whether a new version is even worth writing.

**Filesystem storage derives version history from git, not from a table.**
`packages/core/src/storage/filesystem.ts` implements the 7 editor domains as one JSON file per domain
(`agents.json`, `prompt-blocks.json`, …) under `.mastra-storage/`, written atomically
(`writeFileSync(tmp)` + `renameSync`). `filesystem-versioned.ts` (774 lines) is the standout mechanism: when
the storage directory sits inside a git repo, "committed versions of the JSON file are automatically loaded
as read-only version history. Each git commit that touched the file becomes a version record" (its own
docstring). `git-history.ts`'s `GitHistory` class shells to the real `git` CLI (`git log --follow`, `git show
<hash>:<path>`), never writes, and caches by commit hash. Version numbers are reassigned so the live on-disk
state sits above the git-derived history count; JSON keys are alphabetically sorted before every write
(`stableSortKeys()`) purely so git diffs stay clean. `source-control.ts` generalises the same idea to a
*remote* git host through a `SourceControlProvider` interface (`readFile/writeFile/listFileHistory/
openChangeRequest?`), concretely implemented by `providers/github.ts` for the Editor's "repository files"
mode (below).

**Schema evolution on the SQLite-compatible reference store (`stores/libsql/src/storage/`) has no migrations
table and no schema-version column.** DDL is generated once from a single declarative source
(`TABLE_SCHEMAS: Record<TABLE_NAMES, Record<string, StorageColumn>>` in `packages/core/src/storage/
constants.ts`, shared across every backend — Postgres, LibSQL, MySQL, …), so `CREATE TABLE IF NOT EXISTS` is
generated per dialect from the same column specs. On every boot, `db/index.ts`'s `alterTable()` runs `PRAGMA
table_info("table")`, diffs it against the declared columns, and issues `ALTER TABLE ... ADD COLUMN "col"
TYPE DEFAULT <value>` for anything missing — additive-only, idempotent, no down-migration. Reads/writes are
additionally defended at the row level: `filterRecordToKnownColumns()` silently drops unknown columns rather
than erroring, so an old binary reading a newer table (or vice versa) degrades instead of crashing (the
"resilient columns" pattern, `db/resilient-columns.test.ts`). One special case breaks the additive-only rule:
`migrateSpansTable()` needs a `UNIQUE("spanId","traceId")` index and, if it finds pre-existing duplicate
rows, `createTable()` throws and tells the operator to run `npx mastra migrate` — the one CLI-driven data
migration that exists, and it is a one-off dedup (`migrateSpans()`, a `ROW_NUMBER() OVER (PARTITION BY
spanId, traceId ...)` delete), not a general schema-migration runner. Table names carry a `mastra_` prefix
(`mastra_threads`, `mastra_messages`, `mastra_workflow_snapshot`, `mastra_ai_spans`, `mastra_agent_versions`,
`mastra_prompt_block_versions`, …); representative indexes: `idx_messages_thread_created_at ON
mastra_messages(thread_id,"createdAt")`, `mastra_ai_spans_spanid_traceid_idx UNIQUE ON
mastra_ai_spans("spanId","traceId")`, `idx_prompt_block_versions_block_version UNIQUE ON
mastra_prompt_block_versions("blockId","versionNumber")`. `write-lock.ts` serialises writes per client
instance (`WeakMap<SqliteClient, Promise>` chain) to avoid `SQLITE_BUSY` under `@libsql/client`'s pooled
connections, while reads are left ungated (WAL readers never see partial writes).

**Retention is separate from schema versioning.** `retention.ts` is a pure age-based prune, not a
migration: `TableRetentionPolicy{maxAge: Duration, batchSize?}`, configured per table
(`new MastraCompositeStore({retention:{memory:{messages:{maxAge:'30d'}}, observability:{spans:{maxAge:
'7d'}}}})`), run by calling `storage.prune()`, deleting in bounded batches with `AbortSignal`/`maxBatches`
support, returning `{domain, table, deleted, done}` so a caller re-invokes until `done`. Only *growth*
tables are eligible (declared per-domain via a static `retentionTables` descriptor) — "user-authored config
... grows with user intent" and is explicitly excluded. The docstring is blunt: `prune()` only deletes rows;
"freed pages are reused by future writes so the file stops growing. Handing disk back to the OS (VACUUM) is
left to the operator" — no auto-VACUUM.

### 1.2 Events, pub/sub, and signals — three distinct things under one word

**PubSub** (`packages/core/src/events/pubsub.ts`) is an abstract `PubSub` class:
`publish(topic, event, {localOnly?})`, `subscribe(topic, cb, options?)`, `unsubscribe`, `flush()`
(best-effort drain), `clearTopic()` (delete a run's retained state on terminal transition). A `PubSubDeliveryMode`
is `'pull'` (broker-side XREADGROUP/streamingPull; Mastra runs a long-lived `OrchestrationWorker` subscription
loop) or `'push'` (in-process `EventEmitter`, or a broker POSTing to `POST /api/workers/events`). An
`Event` (`events/types.ts`) is `{type, id, data, runId, createdAt, index?, deliveryAttempt?}` —
`deliveryAttempt` starts at 1 and increments on nack/redelivery, giving **at-least-once delivery with an
explicit attempt counter** rather than a hidden retry. `SubscribeOptions.group` turns fan-out into
competing-consumer semantics (each event to exactly one subscriber in the group) when set, fan-out to every
subscriber when not. `SubscribeBatchOptions` adds opt-in batching (`maxSize`, `maxWaitMs`, `minIntervalMs`,
a `coalesce()` hook that must return a *subset by reference* of its input or the whole batch is discarded as
a contract violation, `overflow: 'drop-oldest'|'drop-newest'|'coalesce-or-drop-oldest'`). The concrete
in-process transport, `events/unix-socket-pubsub.ts`, pins `MAX_LOCAL_REDELIVERIES = 6` with a code comment
that this constant "MUST be >= the consumer-side retry budget
(`WorkflowEventProcessor.MAX_DELIVERY_ATTEMPTS`) — otherwise the transport gives up before the consumer can
exhaust its budget ... which would leave the run silently hung," and an invariant test
(`unix-socket-pubsub-redelivery-budget.test.ts`) pins the two constants together so they cannot drift apart.
Real distributed backends exist as separate packages: `pubsub/redis-streams`, `pubsub/valkey-streams`,
`pubsub/google-cloud-pubsub` — durable, replayable brokers, not just the default in-process bus. Event names
observed in the evented workflow engine (`packages/core/src/workflows/evented/execution-engine.ts`,
`workflow.ts`): `workflow.start`, `workflow.end`, `workflow.fail`, `workflow.suspend`, `workflow.resume`,
`workflow.cancel` — one topic family per workflow run (`RUN_LOCAL_TOPIC_PREFIXES = ['workflow.events.v2.']`
in `events/topics.ts`), i.e. the event bus *is* the workflow engine's own execution log, not a separate
audit trail bolted on afterward.

**"Signal" is a different concept from "event."** `packages/core/src/agent/signals.ts` defines a signal as
an out-of-band item injected into a *live agent thread/stream*, not a bus message: `AgentSignalCategory =
'user' | 'state' | 'reactive' | 'notification'`, delivered via `sendSignal`/`sendStateSignal` on the
processor context (`processors/index.ts`'s `ProcessorContext`). A signal can carry text or file parts, has a
`mode: 'snapshot'|'delta'` for state signals, and is what a processor uses to push something into the
conversation without it being a normal user turn. `packages/core/src/signals/signal-provider.ts`'s abstract
`SignalProvider` is a third, related idea: an external-world monitor (poll or webhook) that "pushes
notification signals into agent threads" and tracks `SignalSubscription{id, providerId, threadId,
resourceId, externalResourceId, subscribedAt, metadata}` — concretely implemented by `signals/github` (a
GitHub webhook signal provider) and `signals/task-signal-provider.ts`/`webhook-signal-provider.ts` in core.
`notifications/signals.ts` is the glue: it turns a `NotificationRecord` into a `notification`-category
`AgentSignalContents` signal (`notificationSignalAttributes`, `notificationSignalMetadata`). So the three
words map to three layers: **event** = durable execution/audit fact on the pub/sub bus (drives the workflow
engine, at-least-once, replayable on the streaming backends); **notification** = a stored, prioritised,
delivery-policy-governed record (below); **signal** = the live-injection mechanism that gets a notification,
a state update, or an external webhook fact into a running agent's context.

**Notifications** (`packages/core/src/notifications/types.ts`) are their own storage domain with a real
lifecycle: `NotificationRecord{id, threadId, source, kind, priority: 'low'|'medium'|'high'|'urgent', status:
'pending'|'delivered'|'seen'|'dismissed'|'archived'|'discarded'|'failed', summary, payload?, dedupeKey?,
coalesceKey?, coalescedCount?, deliverAt?, summaryAt?, deliveryAttempts?, lastDeliveryError?, ...}`.
`delivery-policy.ts`'s `defaultNotificationDeliveryDecision` is a small, explicit table: `urgent` always
delivers immediately; `high` on an idle thread delivers immediately, on an active thread gets a same-instant
summary then a full deliver; `medium`/`low` on an active thread batch into a summary, on idle they still
deliver (medium) or summarize (low). A summary record separately aggregates: `NotificationSummarySignalMetadata
{pending, groups:[{source,count}], byPriority, notificationIds}`. Delivery is capped and terminal:
`MAX_NOTIFICATION_DELIVERY_ATTEMPTS = 5`, then `status: 'failed'` so a permanently-broken delivery path
(missing model, rejected context) stops being retried forever. This whole apparatus is priority- and
thread-state-aware batching, not a fixed cadence.

### 1.3 Channels: Slack/Telegram as one adapter model, approval buttons, and honest limits

`packages/core/src/channels/` is the generic layer (`AgentChannels`, extended by `AgentControllerChannels`
for stateful multi-turn sessions) built on top of the third-party **Chat SDK** (`chat-sdk.dev`), which
supplies the per-platform `Adapter` (Slack, Discord, Telegram, …). Docs (`docs/src/content/en/docs/
channels.mdx`) describe Slack, Microsoft Teams, Discord, Telegram, WhatsApp, GitHub, and Linear as
"channels," all through the same `channels: { adapters: { slack: createSlackAdapter() } } }` shape on an
`Agent`. Mastra registers one webhook route per adapter: `/api/agents/<AGENT_ID>/channels/<PLATFORM>/webhook`.
`PostableMessage = string | CardElement | {markdown: string}` (`channels/types.ts`) is the outbound message
shape; `ToolDisplay` (`'cards'|'text'|'timeline'|'grouped'|'hidden'|fn`) controls how a tool call renders.

**Tool approval is a first-class channel feature.** A tool with `requireApproval: true` renders as an
interactive card with Approve/Deny buttons (`docs/.../channels.mdx` "Tool approval" section, and
`packages/core/src/tools/hitl.md`). The actual wiring, read in `channels/agent-channels.ts`: an approval
button's `actionId` is `"tool_approve:<toolCallId>"` / `"tool_deny:<toolCallId>"` (line ~516) — **the
`toolCallId` is the sole correlation key** between the button click and the paused run. On click, the handler
first checks an in-memory `pendingApprovalCards` map keyed by `toolCallId` (survives parallel same-tool
calls); if that's empty (process restarted since the card was posted) it falls back to a persisted
`pendingToolApprovals` metadata blob on the message itself, read back through the memory store — explicitly
noted as "lossy for parallel same-tool calls since core keys those by toolName — only the latest survives."
If neither resolves a `runId`, the click is silently dropped with a log line. If the click *does* resolve but
the run has already consumed that snapshot (`err.message.includes('No snapshot found')`), it's caught and
logged as `Ignoring stale tool approval action (runId already consumed)` — i.e. a duplicate or late click is
made a no-op by catching a specific error string, not by a durable idempotency table. The controller-session
variant (`agent-controller-channels.ts`) is explicit about the limit: **"V1 targets long-lived servers:
controller sessions are in-memory objects and do not survive process restarts"** (class docstring, line
~150), and ships an `onStaleToolApproval` hook specifically so "a durable host can settle that exact attempt
(mark it interrupted, retryable, expired) instead of silently dropping the user's click" — Mastra's own code
acknowledges the in-memory approval gate is not durable by default and hands the durability problem to the
integrator. Adapters whose platform can't render approval buttons auto-approve instead of parking forever
(`autoApproveResourceIds`, `requireToolApproval: false` fallback) — silent auto-approval as the safety valve
for an unsupported surface, not a queued item.

**Idempotency for inbound webhook delivery is explicitly "best effort."** From `channels.mdx`, "Error
handling and delivery": a webhook acknowledges the platform with `200` before the agent finishes ("received,"
not "answered"); after that `200` "the platform never retries and Mastra owns errors." "Platform retries
sometimes deliver an event more than once. Adapters use channel state for deduplication, which storage can
preserve across restarts. **Because this protection is best effort, custom-handler side effects should be
idempotent** so duplicate delivery can't repeat work." Thread continuity across turns uses platform-native
threading: on first mention in a thread Mastra fetches the last N platform messages as context, then
subscribes to the thread and uses Mastra memory for everything after — `threadContext: {maxMessages: 0}`
disables the fetch. The concrete Slack package (`channels/slack/src/provider.ts`, `SlackProvider implements
ChannelProvider`) layers OAuth app-manifest install (`manifest.ts`, `client.ts`), request verification and
token encryption (`crypto.ts`) on top of the Chat SDK adapter — this is the *installation* half (who can
connect a workspace), separate from the *messaging* half described above. `channels/telegram` is structurally
the same shape (`telegram-provider.ts`, `telegram-client.ts`) plus its own `install-store.ts` and
`commands.ts` for Telegram's bot-command model, which has no true threads the way Slack does.

### 1.4 Auth, roles, and guardrail processors

**Auth and authorization are three independently-pluggable layers, not one system.** `packages/core/src/
auth/` is a thin re-export shim over `packages/_internals/auth/src/`; eleven provider packages exist under
top-level `auth/` (`auth0`, `better-auth`, `clerk`, `cloud`, `firebase`, `google`, `neon`, `okta`, `studio`,
`supabase`, `workos`). **Authentication** (`IMastraAuthProvider<TUser>`: `authenticateToken(token, request)`,
`authorizeUser(user, request)`, optional `mapUserToResourceId`) is deliberately a *structural*, not nominal,
interface so provider packages can each bundle their own copy of the base class. `CompositeAuth` chains
several providers (`authenticateToken` tries each in order, `authorizeUser` is OR'd across all of them);
`SimpleAuth<TUser>` (dev/test) checks a token map against `Authorization`/cookie headers, `password` doubling
as the token in its `signIn`. Three separate **authorization** layers sit on top, independently pluggable
into `Mastra({server: {auth, rbac, fga}})`: (1) coarse **RBAC** (`IRBACProvider`: `getRoles`, `hasPermission`,
`hasAnyPermission`) — `DEFAULT_ROLES` (`packages/_internals/auth/src/ee/defaults/roles.ts`): `owner` (`['*']`),
`admin` (`['*:read','*:write','*:execute','*:publish','*:share']` — notably *not* delete), `member`
(`['*:read','*:execute']`), `viewer` (`['*:read']`); permission strings are `resource:action[:resourceId]`
with wildcard matching (`*`, `resource:*`, `*:action`) plus a resource-alias expansion table so `stored:*`
also matches `stored-agents:*` etc.; `StaticRBACProvider` runs either Mastra's own role list or a
`roleMapping` translating an external IdP's group names straight into these permission strings; (2) **ACL**
(`IACLProvider.canAccess(user, {type,id}, action)`, grant/revoke over named resources); (3) **FGA**
(fine-grained authorization, `packages/_internals/auth/src/ee/interfaces/fga.ts`,
`IFGAProvider.check`/`require`/`filterAccessible`) — this is the layer that actually gates individual actions
including tool calls, with resource-id helpers per kind (`getAgentToolFGAResourceId(agentId, toolName)`,
and notably `getMCPToolFGAResourceId(serverName, toolName)`, a *different* id shape for MCP-sourced tools).
FGA's most interesting feature for a factory-shaped system: `requireActor(actor: ActorSignal, params)`
authorizes a **non-human, trusted actor** — `{actorKind: 'system', agentId?, permissions?, scope?}` — as a
first-class principal distinct from a signed-in user, so an autonomous agent or workflow can be authorized
by scope rather than impersonating a person. Studio hides UI actions a viewer's role can't take; none of
this hashes the policy in force at decision time or has a quorum concept — it answers "can this call happen"
once, not "did enough of the right people agree," which is what our own approval model does instead (§2).

**Guardrail processors** implement a single, much wider `Processor` interface
(`packages/core/src/processors/index.ts`) than a name like "guardrail" suggests: `processInput` (once,
before the model call), `processInputStep` (every step), `processLLMRequest` (after prompt conversion, per
model call, transient), `processLLMResponse` (after a step completes), `processOutputStream` (per stream
chunk), `processOutputStep` (after each step, before tool execution), `processToolResult` (after a tool
succeeds, before its result is appended), `processOutputResult` (once, generation done), `processAPIError`
(on a non-retryable API rejection) — a guardrail typically implements only one or two of these. Every hook's
context carries `abort(reason?, {retry?, metadata?}) => never`, which throws a typed
`TripWire<TMetadata>` (`agent/trip-wire.ts`) the agent loop catches to stop generation, optionally retry with
the reason as feedback, and carry structured metadata about what fired; `sendSignal`/`sendStateSignal` are
on the same context, so a guardrail can push a notification-category signal into the thread the moment it
fires (ties directly to 1.2/1.3). The three content-safety guardrails
(`packages/core/src/processors/processors/{pii-detector,moderation,prompt-injection-detector}.ts`) all run
an internal `Agent` sub-call (a separate LLM judge, Zod-schema structured output) against selected messages,
score named categories, and compare to a `threshold` (default 0.5): `PIIDetector` (categories email/phone/
credit-card/ssn/api-key/ip-address/name/address/date-of-birth/url/uuid/crypto-wallet/iban;
`strategy: 'block'|'warn'|'filter'|'redact'` — default `'redact'`, with a `redactionMethod:
'mask'|'hash'|'remove'|'placeholder'`); `ModerationInputProcessor` (OpenAI-style categories,
`strategy: 'block'|'warn'|'filter'`); `PromptInjectionDetector` (`strategy` adds a fourth option, `'rewrite'`
— transform the flagged content instead of blocking/dropping it). A separate, purely deterministic sibling,
`regex-filter.ts`, does the same three-way `block/redact/warn` dispatch with hand-written `RegExp` rules or
named presets (`'pii'|'secrets'|'urls'`) and no LLM call at all — the two are meant to compose, not compete
(regex catches the cheap, certain cases; the LLM judge catches the rest). A named `CostGuardProcessor`
(`token-cost-control.ts`) is a cost-based tripwire scoped per run or per resource over a window — a
guardrail on spend, not content.

**Tool-level `requireApproval` and human-in-the-loop.** Full mechanism spans `packages/core/src/tools/hitl.md`
(overview), `tools/tool.ts`/`tools/types.ts` (the config surface), and
`packages/core/src/loop/workflows/agentic-execution/tool-call-step.ts` (runtime enforcement, ~1460 lines —
the workflow step every tool call passes through). `requireApproval` on a tool is `boolean |
((input, ctx?: {requestContext?, workspace?}) => boolean | Promise<boolean>)` — a per-call predicate, not
just a static flag. There is also a *run-level* policy, `requireToolApproval` (same boolean-or-function
shape), passed to `generateVNext`/`streamVNext` and gating every tool call in that run unless a tool's own
predicate overrides it. **Precedence and failure mode, read directly from `tool-call-step.ts`**: the
run-level policy OR the tool's own boolean seeds whether approval is required; a per-tool `needsApprovalFn`
(synthesized whenever `requireApproval` is a function, or by the MCP client — below) then overrides that
seed, and **a policy function that throws defaults to requiring approval** ("fail-safe: on error, default to
requiring approval, to be safe" — the code comment's own words). Approval is implemented *on top of* generic
tool suspension, not beside it: when gated, the step emits a `tool-call-approval` stream chunk, persists
`pendingToolApprovals` metadata on the assistant message, and calls the same `suspend()` primitive a tool's
own `execute` can call directly for a data-gathering pause (`suspendSchema`/`resumeSchema`) — approval is
"should this run at all," suspend is "this tool needs more input to finish," and both close the agent's
stream the same way. On resume, a **declined** call never runs `execute()` at all — the step returns
`{approval: {approved: false, reason}, ...inputData}` directly (persisted as `state: 'output-denied'`);
resumption happens through `agent.approveToolCall({runId, toolCallId?})` /
`.declineToolCall({runId, toolCallId?})` (`agent/agent.ts`, thin wrappers over the generic resume path;
`DEFAULT_TOOL_DECLINE_REASON` and the reason-shape normalizer live in the small dedicated
`agent/tool-approval.ts`). A nested case — a sub-agent or workflow tool itself calling a gated tool — routes
the *outer* run's resume into the *inner* suspended run via `suspendedToolRunId` tracking, so approving the
inner call doesn't re-trigger the outer gate. This whole mechanism is a generic stream-chunk/persisted-
metadata protocol with no channel-specific code in `packages/core`; the Slack/Telegram approval card
described in 1.3 and the Studio UI are both *consumers* of the same protocol, not separate subsystems.

**MCP** (`packages/core/src/mcp/`) holds only the server-side shape (`MCPServerBase`, `MCPServerConfig`) —
the client lives in a separate `packages/mcp`. `MCPServerConfig.fga?: MCPServerFGAConfig` lets one MCP
server override the global FGA resource/permission mapping for its own `tools/list`/`tools/call` checks,
confirming MCP tools sit on a distinct (if parallel) authorization path from regular agent tools. The
client-side approval gate: `@mastra/mcp`'s client config takes a **server-level**
`requireToolApproval: boolean | ((ctx) => boolean | Promise<boolean>)`, with an explicit warning in its own
docs that server-advertised tool annotations (`readOnlyHint`, `destructiveHint`, …) are untrusted hints, not
a security boundary — "gate dangerous behaviour with `requireToolApproval: true` ... for any server you do
not control." When set, every tool discovered from that server gets `requireApproval: true` plus a
synthesized `needsApprovalFn` wrapping the server-level function, so it flows through the exact same
`packages/core` runtime gate described above — there is no separate MCP execution path, only a convenient
way to pre-populate the per-tool fields at discovery time.

### 1.5 Studio (the playground) — what a developer sees per agent/workflow run

"Studio" is the current name for what used to be "Playground" (`packages/playground`, `packages/
playground-ui`; no separate `packages/studio` — the docs' "Studio" is this same app, `mastra dev` starts it
at `localhost:4111`). Per `docs/src/content/en/docs/studio/overview.mdx` and `.../observability.mdx`, its
primitives:

- **Agents** — chat directly with the agent, switch models/temperature/top-p live, watch reasoning and tool
  calls stream in, attach scorers to score responses over time, send a follow-up mid-stream (other Studio
  tabs open on the same thread see the same live stream).
- **Workflows** — visualise the run as a graph, execute step by step with custom input, watch the active
  step and path taken update live; trace panel shows tool calls and raw JSON per step.
- **Processors** — the agent detail panel lists every input/output processor by name and type, so guardrails,
  token limiters, and custom processors are visibly wired before testing (this is a first-class Studio tab,
  not something you infer from logs).
- **MCP servers** — lists attached servers and their available tools.
- **Tools** — run a tool in isolation with no agent involved, to debug before wiring it in.
- **Workspaces** — a built-in file browser over the agent's workspace filesystem (multiple mounts,
  read-only vs writable labelled), plus a Skills tab listing every discovered skill with instructions,
  references and metadata, installable from a community registry (skills.sh).
- **Request context** — edit runtime dependency-injection variables as JSON or via a schema-driven form when
  the agent declares a `requestContextSchema`; persists across test chats.
- **Evaluation** — **Scorers** (live results as messages pass through, compare across test cases), **Datasets**
  (CSV/JSON import, input/ground-truth schemas, pinned versions for reproducible experiments), **Experiments**
  (run every dataset item against an agent/workflow/scorer, per-item input/output/status/score breakdown,
  side-by-side comparison of two experiment runs).
- **Observability** (`studio/observability.mdx`) — **Metrics** dashboard (configurable 24h–30d window: total
  runs, cost, tokens, average scorer score up top; model cost/usage, token-usage-over-time-with-estimated-cost,
  trace volume with error counts, p50/p95 latency, scorer trends below — explicitly requires a separate OLAP
  store, "relational databases ... aren't supported for metrics"); **Traces** (hierarchical spans per model
  call/tool call/workflow step, a configurable Columns picker including estimated cost, a **"Download trace
  JSON"** export of the full trace with every span's input/output/metadata — used for bug reports or building
  an offline eval dataset); **Logs** (full-text search across message and entity name including trace IDs,
  multi-select level/entity filters, a log correlated with a trace jumps straight to that trace's span
  timeline).
- **Settings** — instance URL, API prefix, custom headers, theme; auth (`studio/auth.mdx`) adds a login
  screen and RBAC-driven hiding of actions the signed-in user can't perform.

### 1.6 Agent-builder/editor — three different things share the name

This packet found **three unrelated "agent builder" concepts**, which is itself worth flagging precisely so
the wrong one isn't ported:

1. **`packages/agent-builder`** (`AgentBuilder`) is a *code-generation* agent: it extends Mastra's own
   `Agent`, clones a git template repository, discovers "units" (agents/tools/workflows/mcp-servers),
   topologically merges them into a target project, and writes TypeScript files to disk (`README.md`: "turns
   natural-language requirements into Mastra applications, agents, tools, and workflows"). It never touches
   the storage domains below. It requires a Mastra Enterprise license for production use.
2. **`packages/core/src/agent-builder/ee/`** is pure policy plumbing for the *separate*
   `agent-builder.mastra.ai` hosted product — model allowlists, per-deployment feature toggles, admin-pinned
   defaults. No agent-editing UI code lives in this repo for that product.
3. **`packages/editor`** (`@mastra/editor`, docs at `docs/src/content/en/docs/studio/editor.mdx`) is the one
   that matches the packet's actual question — **agent-as-data editing with versioning** — and it is a
   headless data/provider layer, not a UI itself: "Editor works like a CMS for Mastra agents. Collaborators
   can change an agent's instructions and tools in Studio without accessing the codebase." `MastraEditor` is
   attached to a `Mastra` instance (`editor: new MastraEditor()`) and consumed by Studio's Agents → Editor tab.

**What Editor actually versions and how.** An agent's code-defined fields (`id`, `name`, `model`) stay
code-owned; instructions and tools can be overridden. The `editor` field on `new Agent({...})` controls
exactly what's editable, from full (omitted) to nothing (`false`) to just-descriptions
(`{tools:{description:true}}}`) — a real per-field permission grid, not an all-or-nothing toggle. Saving
creates a **draft**; the live agent keeps using the **published** version until a human explicitly publishes;
restoring an older version creates a new draft to test before publishing again — the
draft/published/versionId selection described in 1.1 is exactly this mechanism surfaced to a person. An
application can pick a version per request (`mastra.getAgentById('support-agent', {status:'published'|
'draft'} | {versionId})`), which the docs call out for A/B testing, staged rollout to a group, staging-vs-prod
split, and per-customer pinning — and the same selection composes through sub-agent calls, so a supervisor
can test one draft sub-agent without touching the rest of the system. **Prompt blocks** are the reuse unit:
a named, independently-versioned instruction fragment (e.g. a shared refund policy) that multiple agents
reference by id; publishing a block updates every agent referencing its published version, while an agent
previewing a draft block sees the draft without affecting anyone else. Storage for Editor changes is a
choice: the default database path (draft/published rows as in 1.1), or **"Repository files"** mode
(`source: 'code', codePath: './mastra/editor'`) that writes one JSON override file per agent
(`mastra/editor/agents/support-agent.json`, containing only the Editor-managed fields) so "developers can
review the files in pull requests and deploy them with the application" — with a source-control integration,
Studio can open a pull request directly instead of writing locally. Everything Editor can do is also reachable
programmatically via `mastra.getEditor()`, the REST API, or the client SDK, including scripting bulk updates
or "power[ing] automation that tunes agents based on evaluation results" — i.e. Editor is explicitly designed
as the write target for an automated improvement loop, not only a human-facing UI.

### 1.7 CLI and scaffold

`packages/cli` verbs (`packages/cli/src/commands/*`): `create` (scaffold), `init` (add Mastra into an
existing project — `--components agents,workflows,tools,scorers`, `--llm`, `--mcp <editor>`,
`--observability`), `lint` (`--preflight` bundle check), `dev` (dev server = Studio), `build` (`--studio`
bundles the Studio UI into the build), `start` (run the built `.mastra/output`), `deploy` (unified deploy),
`studio` (run Studio locally, plus `studio deploy`/`deploy list|status|logs|suggestions`, `studio projects
[create]` for the hosted product), `migrate` (the span-dedup one-off from 1.1, via `npx mastra migrate`),
`scorers add|list`, `auth login|logout|whoami|orgs|tokens`, `env`/`db` (env var and DB management), `server
deploy|pause|restart|env ...` (managed deployment lifecycle), `experiment build`, `worker build|start|dev`,
`api` (OpenAPI schema/client generation). `packages/create-mastra` is a thin re-exec wrapper with no local
templates of its own — it re-runs `mastra create`, which has three scaffold modes: `template`/`managed`
**clone a remote git repository** (`DEFAULT_TEMPLATE` points at
`github.com/mastra-ai/template-agent-harness`) via `cloneTemplate()`, while the plain `empty` scaffold (and
`mastra init`) generates files inline (`cli/src/commands/init/utils.ts`): `agents/`, `tools/`, `workflows/`,
`scorers/` directories, a sample weather agent/tool/workflow/scorer, an `index.ts` wiring
`Mastra({agents, workflows, scorers, storage: new MastraCompositeStore({...}), observability: new
Observability({...})})`, plus `AGENTS.md`/`CLAUDE.md` generators. So Mastra's "starter kit" is either a git
clone of a maintained template repo, or a small in-code generator — never a static template directory
shipped in the npm package.

## 2. What we already have

| Mastra mechanism | Our equivalent | How ours differs |
|---|---|---|
| `StorageDomains` composite, per-domain interfaces, mixed backends | One SQLite file, `runner/schema.py`'s `TABLES` list, `factory/manifest.yaml` hashes the `factory/` tree (not the DB schema) | Deliberately not split: R-T-1/R-T-3 (`docs/design/hld/L2-record.md`, R1) want one ledger a trusted runner alone writes, not a pluggable multi-backend surface. `factory/` (agents, skills, rubrics, config) *is* our "editor domain," and it is genuinely code-reviewed, not live-edited (07-factory-as-code.md, R-F-4, R-F-5) |
| `VersionedStorageDomain` (draft/published/versionId, `activeVersionId`) | `factory/manifest.yaml`'s content hash pinned per ticket at S0/S1, `migrate_manifest` transition (`runner/manifest.py`) | We have exactly one "published" state at a time (the committed tree) and no "draft" a ticket can preview — R-F-5: "Nothing at runtime writes to `factory/`." A running ticket keeps its pinned hash until an engineer explicitly migrates it (docs/design/hld/L2-factory-as-code.md, diagram 2), which is closer to Mastra's per-request version *pin* than to its draft/publish flow |
| `FilesystemVersionedHelpers` deriving version history from `git log` | `factory/manifest_hash` recomputed from the committed tree by `scripts/tools/manifest_hash`; ordinary `git log`/`git show` on `factory/` | Same underlying idea (git is the version store) but we have no query surface over it — no `factory show --history <path>` equivalent; an engineer reads `git log` directly |
| LibSQL `PRAGMA table_info` boot-time `ALTER TABLE ADD COLUMN` reconciliation | None — `runner/schema.py`'s `ddl()` emits `CREATE TABLE IF NOT EXISTS` once; a new column is a code change, not a runtime migration | Fine for a single fresh dry-run database (`docs/prd/prd.md` "what runs": one ticket at a time, on one engineer's machine); becomes a real question only once a production `factory.sqlite` persists across schema changes, i.e. post-Milestone-B |
| `retention.ts` age-based pruning of growth tables | Nothing — `runner/cli.py`'s `purge` verb deletes a whole governed ticket export, not individual old rows; `08-configuration.md`'s tool-result inline limit (R-I-17) caps *what's stored per call*, not *how long it's kept* | No table in `runner/schema.py` is ever pruned by age in Initial; `tool_call`/`artefact` rows accumulate for the life of the record by design (the record is the audit trail, `06-observability.md`) |
| `PubSub` (`Event{type,id,data,runId,deliveryAttempt}`, consumer groups, redelivery budget) | `runner/outbox.py`'s `external_write` table: `state` (`pending`→`sending`→`reconciled`/`failed`/`superseded`), `idempotency_key` (canonical hash over each operation's own key columns, e.g. `pr_create`'s `(review_approval_subject_hash, repository, target_ref, head_ref, desired_remote_head_sha, pr_body_hash)`), `attempt_count`, `reconcile_pending()` resolving `sending` rows before any `pending` one dispatches | Ours is a **work queue for external side-effects**, not a general internal event bus: there is no publish/subscribe fan-out inside the runner, no topics, no replay. D28 pins the whole factory to one ticket at a time in Initial, so there is no concurrent-consumer problem yet for a bus to solve. Our idempotency is a deterministic content hash over the exact fields that define "the same write," checked before insert (`create_intent`), not a best-effort dedupe window |
| `notifications` domain (priority, status lifecycle, `dedupeKey`/`coalesceKey`, delivery-policy decider) | `queue_item` (`kind`, `queued_at`/`resolved_at`, `active_attention_bucket`) plus `runner/digest.py`'s fixed twice-daily Slack batch | Every `queue_item` is equally "batched to the next digest slot" today — there is no `urgent` fast-path and no per-source coalescing; R-H-3 explicitly wants this simplicity ("The factory never interrupts... sends nothing for an empty queue") and the digest already dedupes deterministically by `(digest_channel, schedule_slot, payload_digest)`, not by a best-effort window |
| Channel approval buttons (`tool_approve:<toolCallId>`, in-memory + persisted fallback, stale-click swallowed) | **No approval button anywhere.** `L2-human-surface.md`'s second diagram marks "NEVER: approve on GitHub instead of list view" as a red `untrusted`-styled node; R-H-4 makes the local list view (`factory act`) the only place a decision is recorded; the Slack digest is documented as "the only Slack write" (R-H-3) | This is a deliberate divergence, not a gap: D17 (one queue, one channel to the human) and the charter's anti-goals rule out chat-based approval entirely. Where Mastra's in-memory gate is explicitly non-durable across restarts (`agent-controller-channels.ts`), our `approval_record`/`queue_item` rows are durable SQLite rows from the first write |
| Webhook idempotency as "best effort... custom-handler side effects should be idempotent" | `runner/outbox.py`'s exact idempotency key + `reconcile_pending()`'s crash-safe resolution order, tested with three injected crash points (`before_send`, `after_remote_success`, `before_local_commit`) | We hold ourselves to a stronger bar because our one outbound Slack write (the digest) and our one outbound GitHub write (`pr_create`/`pr_update`) are both safety-relevant, not developer-experience conveniences |
| `SimpleAuth`/three-layer RBAC+ACL+FGA (`{resource}:{action}`, roles `owner/admin/member/viewer`, FGA `requireActor` for non-human principals) | `owners.yaml` (`REQUIRED_ROLES`: `factory_owner`, `security_approver`, `legal_data_governance_approver`, `service_owner`, `sensitive_path_owner`, `ticket_engineer`, `plan_reviewer`, `packet_reviewer`, `outcome_recorder`, `incident_reviewer`), `authority_policy_hash` binding a decision to the exact policy bytes in force, `approvals.evaluate()` quorum with per-slot `min_count`/`distinct_from` separation; `runner/trust_profile.py`'s scoped runtime key + route allowlist stands in for "authorize a non-human caller" | Ours answers a different question: not "can this signed-in user click this button" but "does this exact decision have enough of the right, separated people behind it, provably, forever" (`runner/approvals.py`, `runner/owners.py`). There is no Studio-equivalent app to secure yet, so RBAC/ACL-as-UI-gating has no target in Initial; FGA's `requireActor` (authorizing an agent as a first-class principal by scope) is the one piece with a real echo in our design — R-I-14's scoped runtime key and the trust profile's per-route field allowlist already do, by a different mechanism, what `requireActor` is for: let an automated caller act without impersonating a person |
| PII/Moderation/PromptInjection processors (LLM-judge, `strategy: block/warn/filter/redact/rewrite`, `TripWire`) | `trust-profile.yaml`'s deterministic `SecretRule`/`ClassTaxonomy`/`Sanitizer` (`runner/trust_profile.py`), enforced at every route crossing by `guard.decide()`/`guard.pass_through()` (`runner/outbox.py`'s `_guard_outbox`), raising `guard.GuardRefused` | We do the "cheap, deterministic, first" half of what Mastra's guardrails do (regex secret rules, a fixed class-join taxonomy with default-deny) and none of the "LLM judge scores content" half — consistent with R-F-8: no grader may block anything until its agreement with the engineer's own grading is calibrated over 20 sampled items, which is explicitly Later |
| Tool `requireApproval` (per-call predicate, `suspend()`/`resume()`, closes the model stream) | Manifest `tool_allowlist` per `(stage, tier)` (static allow/deny, `08-configuration.md`'s "Tool attachment per stage" table); human approval only at stage gates (`plan_approval`, `packet_approval`, `red_check` waiver) | Ours is coarser by design: a stage either has a tool or it doesn't, decided before the run starts, not per call mid-run. There is no synchronous "pause this one tool call for a human" primitive — P1 ("the factory never interrupts") and R-H-13 (pause takes effect only "at the next boundary") rule out a mid-invocation stop for anything short of budget/lease expiry |
| MCP `requireToolApproval` at the server level | codegraph attached with "the single default tool," the owner's sole enterprise exception (`08-configuration.md`) | Not comparable in scope — we attach exactly one read-only MCP tool by policy; there is no MCP tool surface large enough to need a server-level approval gate |
| Studio (chat with the agent live, Workflows graph, Processors/MCP/Tools/Workspaces tabs, Datasets/Experiments, Metrics/Traces/Logs with trace-JSON export) | The Observatory mockup's eight screens (`docs/design/claude-mockups/`): Queue, Tickets, Ticket detail, Runs, Run detail, Report, Factory, Governance | See §3 item 9 below for the detailed screen-by-screen gap; the headline difference is that Studio is built around *talking to a running agent* and Observatory is built around *reviewing what already happened and deciding what happens next* — there is no chat surface in our design at all, by charter (no synchronous interruption, no agent addressed directly by a human mid-run) |
| Editor (draft/published agent instructions and tools, prompt blocks, per-field edit permissions, PR-backed file mode) | `factory/agents/`, `factory/skills/`, `factory/rubrics/` as plain files, changed only by a reviewed pull request through the adoption gate (R-F-1, R-F-4, R-F-14) | Structurally similar to Editor's "repository files" mode (one file per entity, PR review, git as history) but with no live "draft" a person can preview against a real run before merging — the closest thing is the smoke/conformance fixture suite (R-F-14) proving mechanics, and the Later quality harness (R-F-3) proving output quality, both pre-merge, not post-merge-as-draft |
| `mastra` CLI (dev/build/start/deploy/studio/migrate/scorers/auth/server/experiment/worker/api/…) | `factory` CLI (`runner/cli.py`: `advance/run/show/pause/resume/stop/queue/act/abandon/refresh-base/ migrate-manifest/tag/report/graduate/digest/export/import/purge`) | Different domains entirely: Mastra's CLI runs and deploys a general agent app; ours drives one ticket through a fixed state machine. The one true overlap is `migrate` — Mastra's is a one-off span-dedup fixup; ours, `migrate-manifest`, is "return every open ticket to `context` because the pinned factory tree changed" (`runner/manifest.py`) — same word, different job |
| `create-mastra`/`mastra create` (git-clone a template repo, or generate inline files) | `runner/setup.py` (installs the launchd/cron digest entry, seeds `factory/config/` from the pilot service) | We don't scaffold a *new* factory instance from a template; there is exactly one factory (this repository) and `setup.py` provisions its local environment, not a copy of itself |

## 3. Portable ideas

1. **Priority-aware, thread-state-aware notification delivery (Mastra `notifications/delivery-policy.ts`)**
   — a small decision table (`urgent`→deliver now, `high`/`medium`/`low`→deliver or batch depending on
   whether "the thread" is active) instead of one fixed cadence for every queue item.
   Why it matters: R-H-3's fixed twice-daily digest treats a `red_check` from a non-waivable sandbox-integrity
   failure the same as a routine `question` — both wait for the next 10:00/15:00 slot (P1, FM-07 "silent
   factory," FM-09 "no visible progress"). Rating: **later** — the dry run is one ticket at a time with an
   engineer already watching it closely; a priority fast-path matters once several tickets and a less
   attentive engineer are in the picture (ties to R-O-13's step from one ticket to more than one).
   Lands: `05-human-interaction.md`, extends R-H-3 (not a new row; add an `urgency` derivation and an
   immediate-send path alongside the scheduled one); HLD `L2-human-surface.md` H2 (list view and queue items),
   crossing into the control plane's outbox (`L2-control-plane.md`, not read in this packet but implied by
   `runner/digest.py`/`runner/outbox.py`).
   Draft acceptance criteria: a `queue_item` whose kind is `red_check` with a non-waivable check or an
   `escalation` after the fix-round cap triggers an out-of-cadence digest send within one polling interval,
   not the next scheduled slot; every other kind still waits for the scheduled slot; an out-of-cadence send
   still respects the empty-queue-sends-nothing rule and the exact-content rule of R-H-3 (ticket id, tier,
   kind, age, command only); **must-reject:** a second urgent item for the same ticket within one polling
   interval does not trigger a second send (still governed by the existing idempotency key). Verification:
   script test seeding an urgent and a routine item in the same window and asserting one immediate send and
   one scheduled send.
   Size: S. Copy literally: the five-branch priority table's *shape* (urgent/high/medium/low ×
   active/idle) as a starting menu of urgency levels; re-derive: which of our existing `queue_item.kind`
   values actually deserve "urgent" (almost certainly just the non-waivable `red_check` and
   escalation-after-cap; not `question`, which R-S2-12's blocking flag already governs on its own terms).

2. **A read-only "show me every version of this file" command backed by `git log`/`git show`
   (Mastra's `FilesystemVersionedHelpers`/`GitHistory`)** — turn the git history the `factory/` tree already
   has into a queryable list instead of leaving it to `git log` alone.
   Why it matters: R-F-1/R-F-4 already make git the authority for every change to `factory/`; this doesn't
   add a mechanism, it exposes one that exists. Helps the specific failure mode of a reviewer trying to
   understand *why* a rubric line reads the way it does at S3/S6 review time (P9, self-containedness) without
   leaving the tool. New idea, no single failure mode compels it.
   Rating: **later** — a nice-to-have around the adoption-gate PR review, not needed for one pilot ticket's
   dry run; an engineer can run `git log -- factory/rubrics/S3.md` today.
   Lands: `07-factory-as-code.md`, new row under Tree and change control (F1); HLD
   `L2-factory-as-code.md`, F1/F7 (a new `scripts/tools/` entry, not a new component).
   Draft acceptance criteria: `factory show --history <path under factory/>` lists every commit that touched
   the file (hash, author, date, subject) newest first; each entry's content is retrievable by hash without
   a working-tree checkout; the command refuses a path outside `factory/`; **must-reject:** a path that has
   never been committed under `factory/` returns an explicit "no history" result, not an empty list
   indistinguishable from "not implemented yet." Verification: script test against a scratch git repo fixture.
   Size: S. Copy literally: nothing (this is a two-line `git log --follow`/`git show` wrapper, not worth
   importing Mastra's 774-line helper, which also does JSON-diff-per-entity reconstruction we don't need
   since our files aren't a shared JSON map).

3. **Age-based retention/pruning of growth tables, separate from full-ticket purge (Mastra `retention.ts`)**
   — bounded, resumable, batch-deleted pruning of specifically the tables that grow without bound
   (`tool_call`, large `artefact` blobs), explicitly never touching decision/config rows.
   Why it matters: our own docstring in `runner/schema.py` calls the record append-only by design, and
   `06-observability.md` treats the full ledger as the audit trail — so this is not "add deletion," it's "add
   deletion only once the database is genuinely large," which is explicitly out of scope now (FM-25's audit
   reconstruction requirement is a hard constraint until R-O-13 widens scope).
   Rating: **later**, tied to R-O-13 (any capacity increase needs its own gate) — a single pilot ticket will
   never make `factory.sqlite` large enough to matter.
   Lands: `07-factory-as-code.md`/`08-configuration.md` (new config keys, `limits.yaml`), new row; HLD
   `L2-record.md`, R1 (a new prune operation over `tool_call`/`artefact`, never over `queue_item`,
   `approval_record`, `tag`, or any other decision-bearing table).
   Draft acceptance criteria: a prune operation only ever deletes from an explicit table allowlist that
   excludes every decision-bearing table; deletion is age-bounded and batched with a resumable cursor;
   **must-reject:** a prune request naming a table outside the allowlist (e.g. `approval_record`) is refused
   before any row is touched. Verification: manifest/schema test asserting the allowlist excludes every
   append-only decision table by name.
   Size: M. Copy literally: the "declare prunable tables as an explicit descriptor, not by convention" idea,
   and the "done: false means call again" resumable-batch contract. Re-derive: our own allowlist (Mastra's
   is generic across arbitrary domains; ours only ever needs `tool_call` and oversized `artefact` content).

4. **Per-field agent/skill edit permissions as a design reference for a future editor, not a UI to build now
   (Mastra's `editor` field: `false | {instructions: true} | {tools: {description: true}}`, etc.)** — a
   ready-made small vocabulary for "who may change what" on a factory-tree file, should we ever build
   anything beyond plain PR review.
   Why it matters: nothing in our charter calls for live editing; this is purely a vocabulary to borrow *if*
   R-F-10's improvement pass ever grows an interactive review surface beyond "diff on a pull request."
   New idea, no failure mode compels it now.
   Rating: **do not port** — we have no editor to attach it to, and R-F-5 ("nothing at runtime writes to
   `factory/`") plus R-F-4 (every change is a reviewed pull request) make a live-editable-field system a
   structural mismatch, not just a missing feature. If a UI is ever built, git-diff review already gives
   field-level visibility for free.

5. **Notification `dedupeKey`/`coalesceKey` with a `coalescedCount` (Mastra `NotificationRecord`)** — collapse
   N occurrences of "the same kind of thing" into one record with a count, rather than N separate rows.
   Why it matters: our digest already collapses by ticket (`open_items()` groups by `qi.ticket_id, qi.id`) but
   doesn't collapse *within* a ticket — three stale-index questions on one ticket show as three lines, not
   "3 stale-index questions." Minor readability improvement, cites FM-09 (visible progress without noise) as
   the closest fit.
   Rating: **later** — purely a digest-formatting nicety; irrelevant at one-ticket-at-a-time scale where a
   ticket rarely has three of the same open item at once.
   Lands: `05-human-interaction.md`, extends R-H-3 (no new row); no HLD change (H2's `H2_view` rendering
   detail only).
   Draft acceptance criteria: when a ticket has more than one open item of the same `kind`, the digest line
   shows one row with a count instead of one row per item; **must-reject:** items of different kinds are
   never collapsed together even if they share a ticket. Verification: script test on a seeded multi-item
   ticket.
   Size: S. Copy literally: the `coalescedCount` field name/idea only.

6. **Studio's per-run traceability surface — specifically the "download the full trace as JSON" export and
   the trace-to-log correlation** — the single most concrete gap this packet found in the Observatory mockup.
   What Studio shows that Observatory's screen list (`docs/design/claude-mockups/BRIEF-v2.md` §3) doesn't:
   (a) a full hierarchical span tree per run with a configurable column picker (input, entity, duration,
   tokens in/out, estimated cost, custom metadata) — our Run detail screen (`#run`) shows a flat "event log
   as one monospace block of at most ten lines," not a navigable span tree; (b) a one-click export of the
   complete trace (every span, full input/output/metadata) as a portable JSON file for a bug report or an
   offline eval dataset — nothing in our design writes out a single-file, self-contained trace bundle for one
   run (our closest equivalent, `factory export`, exports a whole *ticket*, not one run's trace in isolation);
   (c) full-text log search across message content and entity name with a jump-to-the-correlated-trace action
   — we have no free-text search across `tool_call`/`stage_run` content at all, only structured queries the
   report generator's views define; (d) a metrics dashboard with token/cost trends *over time* and latency
   percentiles (p50/p95) — our Report screen shows point-in-time KPIs and a cost line, not latency
   percentiles. Cites P9 (self-contained artefacts) for (a)/(b): a run-detail screen a reviewer can't fully
   inspect without reconstructing context from elsewhere is exactly the FM-10 failure mode our packet
   approval process is built to catch at S3/S6, just applied to the *observability* surface instead of the
   approval surface.
   Rating: **next milestone** for (a) and (b) — a navigable span/tool-call tree and a single-run export both
   sit naturally inside the existing Run detail screen and the existing `artefact`/`tool_call` tables, no new
   entity needed; **later** for (c) (full-text search) and (d) (percentile latency, needs the observer pass's
   volume to be worth building); none of these are must-have for a one-ticket dry run where the engineer is
   already watching every run directly.
   Lands: `06-observability.md`, extends R-O-4/R-O-5 (the view layer) — no new requirement row for (a)/(b)
   since the data already exists in `tool_call`/`stage_run`/`artefact`, this is a rendering and one export
   script; HLD: no change to `L2-record.md`'s data model, a rendering change only inside the human surface's
   `H2_view` (`L2-human-surface.md`).
   Draft acceptance criteria: the run-detail view can expand any `tool_call` row into its full recorded
   input/output rather than only the truncated inline excerpt (R-I-17 already governs what's stored; this is
   about what's *shown* on request); a `factory show --run <id> --export` writes one self-contained JSON file
   with every `tool_call`/`check_result`/`artefact` reference for that run resolved to content; **must-reject:**
   the exported file never inlines a tool result that exceeded the inline limit without noting it was
   truncated at capture time (R-I-17's own rule, carried through, not bypassed by the export). Verification:
   script test on a seeded multi-tool-call run.
   Size: M. Copy literally: nothing structural (our data model already has everything needed); re-derive
   everything, since Mastra's version is backed by an OpenTelemetry span model we don't have and don't need.

7. **Do not port: chat-with-the-agent as a Studio primitive.** Explicitly excluded, not merely low-priority.
    Reason: violates the charter directly — P1/R-H-13 rule out a human addressing a running agent
    synchronously mid-invocation ("NEVER: steer a running invocation," `L2-human-surface.md`'s red `never1`
    node), and our entire human-interaction model (R-H-1, D17) is "one queue, asynchronous decisions," the
    structural opposite of a live chat pane.

8. **Do not port: in-channel approval buttons (Slack/Telegram Approve/Deny cards).** Explicitly excluded.
    Reason: violates D17 (one queue is the only channel to the human) and the charter's own anti-goal, drawn
    as the second red node in `L2-human-surface.md` ("NEVER: approve on GitHub instead of list view" — the
    same reasoning extends to Slack). Also weaker than what we already have: Mastra's own approval gate is
    explicitly non-durable across a process restart in v1; our `approval_record`/`queue_item` rows are durable
    from the first write.

9. **Do not port: general internal pub/sub event bus for run orchestration.** Reason: hosting-only /
    premature for our scale. D28 fixes one ticket at a time in Initial; there is exactly one consumer
    (the trusted runner) of every event that matters, so a competing-consumer/broker abstraction solves a
    concurrency problem we don't have yet. `runner/outbox.py`'s existing work-queue-with-idempotency-key
    already covers the one place we do need at-least-once delivery (external writes). Revisit only if/when
    R-O-13 raises the parallel-ticket count above one.

10. **Do not port: RBAC-as-UI-permission-gating (`{resource}:{action}`, default roles).** Reason: no target
    surface exists yet — there is no Studio/Playground-equivalent web app to secure in Initial (the read-only
    MCP server and dashboards are both named Later in `08-configuration.md`/`06-observability.md`). Our
    `owners.yaml` + `approval_record` quorum already answers the harder question ("does this exact decision
    have enough of the right people, provably") that Mastra's RBAC does not attempt to answer at all.

11. **Do not port: LLM-judge PII/moderation/prompt-injection processors as a blocking gate today.** Reason:
    directly conflicts with R-F-8 (no grader may block, or contribute to a benchmark or proposal, until its
    agreement with the engineer's own grading is recorded over the section-8 minimum sample) and with
    "prototype first, no hardening now." The *idea* is not wrong — it is explicitly what R-O-10's Later
    observer pass and R-F-8's calibration are for — it is simply not sequenced to land before those.

## 4. Questions for the owner

- Should a genuinely urgent queue item (for example, a non-waivable sandbox-integrity failure) get sent to
  Slack right away instead of waiting for the next scheduled digest, or is twice a day always soon enough for
  the dry run? Default: keep every item on the fixed twice-daily schedule for the dry run; revisit once more
  than one ticket runs at a time.
- Do we want a small command that lists every past version of one factory file (an agent, a skill, a rubric)
  by reading its git history, or is running `git log` on the file directly good enough for now? Default:
  skip the command; the engineer already has git.
- Should a single run's full evidence (every tool call, check result, and artefact reference) be exportable
  as one self-contained file for sharing outside the tool, separate from exporting a whole ticket? Default:
  not yet; `factory export` at the ticket level already covers what a reviewer needs during the dry run.
- Should the record ever delete old rows to keep the database from growing without bound, or is keeping
  everything forever part of the design on purpose? Default: keep everything; this only becomes worth solving
  once real database size becomes a practical problem, well past the first pilot ticket.

## 5. Do-not-port list

- **Chat with the agent live**, Mastra Studio's central primitive. Structurally opposite to our
  "never interrupt a running invocation" rule (P1, R-H-13) and our fully asynchronous human-interaction model
  (D17, R-H-1). Nothing about it is salvageable in spirit for this factory.
- **In-channel (Slack/Telegram) approval buttons.** Directly forbidden by the charter's own drawn anti-goal
  ("NEVER approve on GitHub instead of list view," and the same logic for Slack); also, on inspection, a
  weaker mechanism than what we already have — Mastra's own approval gate is explicitly non-durable across a
  restart in v1, ours is durable from the first row.
  Restated from §3 item 8 because it is the single most tempting-looking mechanism in the whole packet (it
  looks like exactly what our digest should grow into) and is exactly the one the charter rules out by name.
- **A general internal pub/sub event bus** (Redis Streams / GCP Pub/Sub-style, with consumer groups and
  replay) for run orchestration. Solves a many-concurrent-consumer problem D28 says we don't have in Initial;
  our outbox's idempotency-key work queue already covers the one place at-least-once delivery actually
  matters (external writes).
  Restated from §3 item 9 because "add an event bus" is the kind of infrastructure upgrade that's easy to
  justify in the abstract ("it's more scalable") and wrong for a single-ticket, single-engineer dry run.
- **RBAC permission strings for a web UI.** No web UI exists to protect; would be pure unused surface area
  until a dashboard or read-only MCP server (both Later) exists to gate.
- **LLM-judge guardrail processors as a blocking gate today.** Would let an uncalibrated grader block a run,
  directly contradicting R-F-8. The right time is exactly when R-O-10/R-F-8 land, not before.
