# Packet C — Agents, the coding-agent harness, subagents, skills, tool loop, agent SDK adapters

Scope: `packages/core/src/{agent,tool-loop-agent,loop,tools,tool-provider,processors,harness,coding-agent,skills,agent-controller}/`,
`agent-sdks/{claude,cursor,openai,acp}/`, `mastracode/{sdk,tui}/`, the harness/subagents/skills docs, and the
ralph-wiggum-loop explorations. Compared against `docs/prd/03-stage-interface.md`, `04-S3-spec-and-plan.md`,
`04-S4-implementation.md`, `07-factory-as-code.md`, `08-configuration.md`, `docs/design/hld/L2-execution-boundary.md`,
`L2-factory-as-code.md`, `runner/adapters/`, `runner/recipes.py`, `runner/definitions.py`, `runner/binding.py`,
`runner/budgets.py`, `runner/tool_results.py`, `runner/envelope.py`, `factory/agents/`, `factory/skills/`.

No file in either repository was modified while producing this report.

## 1. What Mastra does here

### 1.1 The `SubAgent` interface — the actual cross-runtime adapter contract

"The agent SDK adapters" is not four independent wrappers; it is one interface, `SubAgent<TId, TRequestContext>`
(`packages/core/src/agent/subagent.ts:44-100`): `id`, `name?`, `getDescription()`, `getModel()`, `hasOwnMemory()`,
`__setMemory()`, `getMemory()`, `getInstructions()`, `generate()`, `stream()`, `resumeGenerate()`, `resumeStream()`.
`ClaudeSDKAgent` (`agent-sdks/claude/src/index.ts`), `CursorSDKAgent` (`agent-sdks/cursor/src/index.ts`), the
OpenAI Agents SDK wrapper (`agent-sdks/openai/src/index.ts`), `AcpAgent` (`agent-sdks/acp/src/agent.ts`), and
`Agent` itself all implement it (`isAgentCompatible()` duck-types it at runtime). None of the three vendor wrappers
is a real `MastraLanguageModel` — each constructs its `Agent` base with a `createNoopModel()` placeholder and
overrides `generate`/`stream` directly, because the "model" is really an opaque external agent process whose own
tool loop is invisible to Mastra's `loop/`. This maps almost one-to-one onto our R-I-13 adapter contract, except
ours has one implementation (Cursor SDK) where Mastra has four.

**Resume, per runtime** (all under `resumeGenerate`/`resumeStream`, no normalized shape): Claude
(`agent-sdks/claude/src/index.ts:79-107`) takes `{message, sessionId, forkSession?, resumeSessionAt?}` or
`{message, continue: true}`; Cursor (`:57-70`) takes `{message, agentId?, sdkOptions?}`; OpenAI (`:46-63`) takes
`{message, previousResponseId?, conversationId?, session?}` — three different continuation mechanisms the vendor
SDK itself exposes; ACP (`agent-sdks/acp/src/agent.ts:118-124`) **refuses outright** — both methods `throw`, since
its session lives only inside the spawned subprocess and is lost if that process exits. No two runtimes normalize
to the same resume shape, and ACP opts out entirely — informative for §3.1: our own doctrine (R-I-2) never resumes
mid-invocation, so this whole axis is unused by design, but an adapter still has to know the runtime's own
primitive well enough to deliberately not call it.

**Telemetry normalization.** Every adapter converts its runtime's own event shape into one `{toolCallId, toolName,
input, output, isError}` pair (`agent-sdks/*/src/utils.ts`) and one usage shape (`{total, noCache, cacheRead,
cacheWrite}` via `toV3Usage()`). Claude reports usage twice (per-`assistant`-message and again in the terminal
`result` message, which wins when present) and reads tool calls out of message content blocks
(`type:'tool_use'`/`'tool_result'` — no separate event stream); Cursor gets both usage and tool events through one
`onDelta` callback on `agent.send()`, distinguishing an MCP-routed call (`toolCall.type==='mcp'`, renamed
`mcp__<provider>__<tool>`) from a native one. Only Claude's wrapper produces a cost figure at all
(`total_cost_usd`, explicitly tagged `costMetadata.source:'sdk_estimate'` — a client-side estimate, not
provider-settled); Cursor's wrapper reports tokens only, matching what `docs/prd/inputs.md` row 1 already told us
about both runtimes' telemetry ceilings. Structured output is Claude-only — Cursor's wrapper throws
(*"the Cursor TypeScript SDK does not expose a schema-constrained output API"*) rather than degrading silently.

**Stopping conditions and step budgets.** `maxSteps` is sugar for the AI-SDK stop condition `stepCountIs(maxSteps)`
(`llm/model/model.loop.ts:150-160`); a custom `stopWhen` is **composed as OR** with it, and if neither is set the
loop defaults to `stepCountIs(5)` — five steps out of the box. The composed set is checked every iteration inside
the workflow's do-while predicate, but only when the model's own `finish_reason` would otherwise continue — a stop
condition never overrides a model-decided hard stop. Layered on top: `isTaskComplete` (a per-call, non-persisted
LLM-judge gate — the ephemeral sibling of the durable `goal` mechanism, §1.8), `onIterationComplete` (force-stop or
inject feedback and continue), and an orthogonal wall-clock budget (`modelSettings.timeout.{stepMs,totalMs,
firstChunkMs}`, `loop/timeout.ts`) raised as a typed `MastraTimeoutError`, distinguishable from a plain cancellation.

**Sub-agent delegation** (the base `Agent` class's own primitive, distinct from `AgentController`'s convenience
wrapper in §1.3): any `config.agents` entry becomes an auto-generated tool. The child gets a filtered
`RequestContext` (parent's entries copied, memory/thread-identity keys excluded), the full parent conversation
forwarded as reasoning context but never persisted to the child's own memory (only the delegation prompt+response
are, on a fresh child thread), and a step budget that can only be *shrunk*, never expanded, by the parent's call
arguments. `DelegationConfig` hooks: `onDelegationStart` (reject outright, or rewrite prompt/instructions/step
cap), `onDelegationComplete` (rewrite the result, or `bail()` the *parent's* whole loop), `messageFilter`. The
child returns `{text, finishReason, subAgentThreadId, subAgentResourceId, subAgentToolResults[], usage}`, but by
default only `text` reaches the parent model's own context. This is materially richer than `AgentController`'s
`subagent` tool (§1.3), which has no hook points and always returns bare prose.

### 1.2 ACP — a fourth, protocol-level adapter, not a fifth vendor SDK

`agent-sdks/acp/` wraps the **Agent Client Protocol** (`@agentclientprotocol/sdk`), JSON-RPC over stdio
(`agent-sdks/acp/src/connection.ts`). `AcpAgent` spawns an arbitrary executable that itself speaks ACP, then drives
a fixed lifecycle: `initialize()` → optional `authenticate()` → `newSession({cwd, mcpServers})` →
`prompt({sessionId, prompt})`, streaming `session/update` notifications back. The permission callback is a
**first-class RPC method the client must implement**, not an SDK option:

```ts
async requestPermission(request): Promise<RequestPermissionResponse> {
  if (this.onPermissionRequest) return this.onPermissionRequest(request);
  const option = request.options[0];
  return option ? { outcome: selectedPermissionOutcome(option) } : { outcome: { outcome: 'cancelled' } };
}
```

`request.options` is a list of `{optionId, name}` choices the *agent* proposes ("allow once", "allow always",
"deny"); Mastra's default, absent a supplied callback, is to auto-select the agent's first option — auto-approve
by default. `createACPTool()` also exposes ACP as an ordinary Mastra tool with a matching `suspendSchema`/
`resumeSchema` pair, so a permission pause can flow through Mastra's own suspend/resume primitive (§1.6) instead of
the raw ACP callback. The client also proxies file I/O (`readTextFile`/`writeTextFile` are requests *from* the
agent *to* the client, not direct filesystem access by the spawned process). ACP is Mastra's answer to "one client
surface for many vendor coding-agent CLIs": spawn a process, negotiate a session, stream text + tool-call updates,
answer permission requests, proxy file I/O.

### 1.3 The AgentController (formerly "Harness") — modes, sessions, subagents, permission gate

`packages/core/src/harness/index.ts` is now a pure backwards-compatibility shim (`export const Harness =
AgentController`, ~13 deprecated aliases). "Harness" is a conceptual umbrella (durable agents, background tasks,
goals, schedules, signals, `AgentController`) — not one class. `AgentController` adds **modes**, **subagents**,
**sessions**, and a **tool-approval gate** on top of one or more `Agent` instances.

**Modes** (`agent-controller/types.ts:80-135`): `id`, `name`, `instructions`, `defaultModelId`, `transitionsTo?`
(named successor mode), `availableTools?: string[]` (positive allowlist — `undefined` unrestricted, `[]` nothing,
enforced at LLM-call time via `activeTools`), `metadata.default===true` (the one reserved key, picks the default
mode). `mastracode` defines **`plan`** (read-only, `transitionsTo:'build'`, a `beforeToolCall` hook
(`guardPlanModePlanFileWrites`) that inspects live session state and refuses any write outside the session's plan
directory) and **`build`** (full read/write/execute, no restriction). The plan→build handoff is driven by
`submit_plan`'s approval outcome (§1.6); a `PlanRejectionAbortProcessor` inspects the just-persisted turn for a
rejected `submit_plan` result and calls `abort(...)` on the very next `processInputStep` — a rejected plan ends the
turn immediately rather than paying for one more wasted LLM call.

**Subagents** (`agent-controller/types.ts:145-203`, spawning tool `createSubagentTool`): a controller declares
definitions (`id`, `instructions`, `tools?`, `allowedControllerTools?`, `defaultModelId?`, `maxSteps?`, `stopWhen?`,
`allowedWorkspaceTools?`, `forked?`) and auto-builds one `subagent` tool called with `{agentType, task, modelId?,
forked?}`. **Non-forked (default)**: a fresh `Agent` with **no visibility into the parent conversation at all** —
*"write a clear, self-contained task description."* `mastracode`'s `explore`/`plan`/`execute` subagents are all
this shape. **Forked**: the parent thread is cloned and the subagent reuses the *parent agent instance itself*
(its own instructions/tools/model, ignoring the definition's), explicitly to preserve prompt-cache prefix; nested
`subagent` calls inside a fork are blocked by a hard-coded refusal notice rather than by removing the tool (keeps
the cache prefix byte-identical). Either way, the **return to the parent model is unstructured**:
`{content: resultText, isError}` — the child's own final free-text answer, no typed schema for "what happened."
Structured events (`subagent_start`/`_text_delta`/`_tool_start`/`_tool_end`/`_end`) give the *host* visibility for
rendering; the parent *model* only ever receives prose.

**Sessions** (`agent-controller/session.ts`) hold live, mostly in-memory, per-thread state: granted tool
permissions (reset on restart), running usage, active mode/model, a single in-flight approval gate, parked
suspensions, a follow-up queue, app state. **Only two things persist through a restart**, written into thread
*metadata*: the selected mode/per-mode model, and a small fixed allowlist of state keys (`['thinkingLevel',
'notifications']`). `loadMetadata()` restores those, in order, when a session re-binds to a thread; grants, the
in-flight approval, and parked suspensions are all gone. A run's own suspend snapshot (§1.6) survives
independently, recovered via `agent.listSuspendedRuns()`, not through `Session`.

**The tool-approval gate**: per-call policy resolution (`session.resolveToolApproval`) checks, in order: explicit
per-tool `deny` → session-wide `yolo` → explicit per-tool policy → a session-scoped grant → the tool's category
policy → default `ask`. `PermissionPolicy = 'allow'|'ask'|'deny'` over `ToolCategory = 'read'|'edit'|'execute'|
'mcp'|'other'`. An `ask` resolution arms a bare `Promise` (`SessionApproval`) that a later
`respondToToolApproval({decision:'approve'|'decline'|'always_allow_category', ...})` resolves; an aborted run
auto-declines any parked gate. `mastracode`'s TUI renders a four-choice dialog (`approve`/`decline`/
`always_allow_category`/`yolo`) and a `/permissions` command showing resolved policies, overrides, and grants.
This entire mechanism decides per *tool call*, live, inside one running turn — something our design deliberately
never does (§2, §3.4).

### 1.4 Skills — the Anthropic Agent Skills spec, discovery, two injection strategies, versioning

Mastra's skill shape directly implements the public Agent Skills spec (`workspace/skills/types.ts`, citing
`github.com/anthropics/skills`): `SkillMetadata{name (1-64 chars), path, description (1-1024 chars), license?,
compatibility?, 'user-invocable'? (default true), metadata?}`, extended by `Skill{instructions (SKILL.md body),
source: {type:'external'|'local'|'managed', ...Path}, references: string[], scripts: string[], assets: string[]}`
(the last three: sibling subdirectories of the same name).

**Discovery** tries each configured path (static array, or `(context)=>string[]` resolved per-request — e.g. a
premium/basic skill split by tier) as a direct skill (`<path>/SKILL.md`), else a one-level container directory
(not recursive), else a glob (`maxDepth: 4`); each file is parsed with `gray-matter`. Name collisions:
`SOURCE_PRIORITY = {local:0, managed:1, external:2}` after de-duplicating by realpath — same-source collisions
**throw**, cross-source collisions **warn and pick higher priority**. Agent-level skills merge with
workspace-level, agent-level winning conflicts.

**Two injection strategies**: `SkillsProcessor` (eager) injects the **full catalog's metadata only** as a system
message every turn (*"Skills are NOT tools... activate immediately without asking permission"*) and defers actual
instructions to a `skill` tool call whose result — not a system message — carries the instructions plus
reference/script/asset listings. `SkillSearchProcessor` (lazy/RAG) instead exposes `search_skills`
(BM25/vector/hybrid) and `load_skill` (TTL-cached, default 1 hour) as meta-tools, deferring even the catalog
listing — the mechanism for "many skills, don't always pay the context cost."

Inline skills (`createSkill(input)`, no filesystem) are served through a virtual `InlineSkillSource` so downstream
code never forks on inline-vs-file. **Versioning** exists one layer up, in the storage/publish path
(`SkillVersionTree`, content-addressed by SHA-256 blob hash per file — structurally a git-tree analog), with
per-agent pin-to-version or track-latest semantics.

### 1.5 Tools, tool-provider, code-mode

A Mastra tool (`tools/tool.ts`) is `{id, description, inputSchema, execute, suspendSchema?, resumeSchema?}`, with a
per-tool `requireApproval`/`NeedsApprovalFn` predicate and a matching global `requireToolApproval` on the run —
the primitive §1.6 and §1.3's gate both build on. There is **no** built-in "keep large tool results out of context,
write the full result to disk, hand back a bounded excerpt" contract analogous to our R-I-17; the closest thing,
`TokenLimiterProcessor`, truncates or aborts an over-budget model *output* stream, not a tool result, and
code-mode's own result shape (`{success, result?, logs?, error?}`) has no size handling at all.

**Code mode** (`tools/code-mode/`) lets the model write one TypeScript program (`execute_typescript` tool) that
orchestrates a fixed tool allow-list as `external_<id>()` functions inside a sandbox, each call RPC'd back to the
host's real tool — reducing round-trips for tool-call-heavy turns. Different axis from our per-task,
one-invocation-per-attempt model, which already makes comparatively few tool calls per invocation.

**Tool providers** (`tool-provider/base.ts`) abstract large third-party SaaS-integration catalogs (Composio-style):
a subclass implements `listAllToolkits`/`listAllTools`/`resolveToolsVNext`/OAuth; `BaseToolProvider` layers admin
allowlisting on top — `allowedToolkits: string[]` and `allowedTools: Record<toolkit, pattern[]>`, matched by exact
slug or `prefix*` wildcard.

### 1.6 The suspend/resume primitive, and `ask_user`/`submit_plan` as its reference implementation

Calling `context.agent.suspend(payload)` inside a tool's `execute` (validated against `suspendSchema`) emits a
`tool-call-suspended` stream chunk and **persists a resume snapshot** — "minimal resume artifacts... deleted once
the run finishes," distinct from tracing and memory. Resume is `agent.resumeStream(resumeData, {runId})`, which
re-invokes the *same* tool call with `context.agent.resumeData` populated (validated against `resumeSchema`); the
tool re-runs from the top and branches on whether `resumeData` is set. This differs from *pre-execution* approval
(§1.3/§1.5), which pauses before `execute` even starts. `autoResumeSuspendedTools: true` lets the agent
auto-extract `resumeData` from the user's *next chat message* rather than needing an explicit resume call.
`agent.listSuspendedRuns()` rediscovers pending runs from storage after a restart.

`ask_user` (`tools/builtin/ask-user.ts`): `inputSchema {question, options?: {label, description?}[],
selectionMode?: 'single_select'|'multi_select'}`, `resumeSchema: z.union([z.string(), z.array(z.string())])` —
free-text/single-select resume with a string, multi-select with an array. `submit_plan`
(`tools/builtin/submit-plan.ts`) takes a plan-file **path**, never the body (*"do not paste the plan contents
here"*); `resumeSchema: {action:'approved'|'rejected', feedback?, path?, title?, plan?}`. Both tools are explicitly
host-agnostic — mode switching on approval is layered on by the controller, not the tool — and both fall back to
plain readable text when invoked with no `agent.suspend` available.

### 1.7 Guardrail / moderation processors

`moderation.ts`/`pii-detector.ts`/`prompt-injection-detector.ts` share one shape: a confidence `threshold`
(0.5–0.7 by processor), evaluated by an **internal Mastra agent acting as classifier** (never the authoring
model), and a `strategy` enum — moderation `'block'|'warn'|'filter'`; prompt-injection adds `'rewrite'`; PII adds
`'redact'` (with `redactionMethod: 'mask'|'hash'|'remove'|'placeholder'`). `TokenLimiterProcessor`: a flat
`maxTokens`/`{limit, strategy:'truncate'|'abort'}`, enforced as the stream is emitted. `TokenCostControl` queries
observability storage for cumulative cost per thread/window before each call and blocks over ceiling — with an
explicit accuracy caveat ("fast-running agents may briefly exceed the limit"), i.e. non-atomic by design, unlike
our R-I-6 pre-invocation check against settled figures only.

Every `'block'`-strategy processor shares one abort primitive: `TripWire` (`agent/trip-wire.ts`), an `Error`
thrown with `(reason, {retry?, metadata?}, processorId?)`, converted into a synthetic model output whose stream
emits one `{type:'tripwire', payload:{reason, retry, metadata, processorId}}` chunk and closes. `retry: true` folds
the reason into message history as feedback and retries the turn instead of hard-failing — a softer alternative to
surfacing an error to the caller.

### 1.8 Durable/evented agents, and the shipped `goal` (ralph-wiggum) loop

`createDurableAgent()`/`createEventedAgent()` run an `Agent`'s loop inside a workflow, streamed through PubSub with
a replay cache so a disconnected client can reconnect via `observe(runId)`; `resume(runId, {approved:true})`
continues a suspended run. What crosses the process boundary is narrower than "the run": a fully JSON-serializable
`DurableAgenticWorkflowInput` (messages, tool *metadata* only — never `execute` closures, model config, `maxSteps`,
a boolean-collapsed approval policy). Every closure-based piece — `stopWhen` predicates, `onIterationComplete`,
`isTaskComplete`'s scorer instances, the full `goal` config, function-form `requireToolApproval` — lives only in an
in-process `RunRegistry`, and each has a documented, deliberate degrade path on cross-process resume: `stopWhen`
"falls back to `maxSteps` only" (fail-open on budget), a function-form `requireToolApproval` "degrades safely to
require approval for every tool call" (fail-closed on permission) — the same mechanism degrades in opposite
directions depending on what's at stake. A crashed run left `running` gets **no automatic retry** unless
`recovery.durableAgents:'auto'`, which re-drives every orphan **from its last snapshot** with an explicit warning:
*"re-issues LLM calls... re-executes tool calls. Make sure your tools are idempotent."* `recover()` takes a
short-lived, single-process recovery lease first, but Mastra's own docs admit there is still no cross-replica lock.

The **ralph-wiggum loop** explorations (`explorations/ralph-wiggum-loop-{integration.md,prototype.ts}`,
`agent-network-vs-ralph-wiggum.md`) describe and prototype a flat, single-tier retry loop — *"let the agent fail
repeatedly until it succeeds"* — with exactly one hard cap (`maxIterations`), an optional cumulative `maxTokens`,
and externally/programmatically checked completion (`testsPassing()`, `buildSucceeds()`), explicitly contrasted
against a competing "agent network" pattern whose LLM-self-assessed completion *"can hallucinate."* The two
converge, and ship, as the **`goal`** mechanism (`agent/goal/`): a durable, thread-scoped objective graded each
iteration by an LLM-judge scorer against a **tri-state score** — `1` complete, `0` continue, and sentinel
`GOAL_SCORE_WAITING = 0.5` that halts the auto-loop *without* marking it done, so a human gets a turn.
`DEFAULT_GOAL_MAX_RUNS = 50` is the one flat budget. **None** of the prototype, the shipped mechanism, or either
document has a two-tier verification/fix-round split, a wall-clock budget, or **any human-escalation branch on
exhaustion** — the prototype just returns `{success:false, ...}` and stops. Direct evidence for §3.4/§5.

## 2. What we already have

Our equivalent of "the agent SDK adapter contract" is `runner/adapters/cursor_sdk.py`'s `invoke()`
(`runner/adapters/cursor_sdk.py:297-467`) plus `runner/envelope.py`'s `Envelope`/`build`/`reconstruct` — R-I-13,
R-I-15. Where Mastra's `SubAgent` interface is a shared TypeScript contract with four concrete implementations, we
have exactly one implementation (Cursor SDK) and a Claude Code adapter named only as `G1_later` in
`docs/design/hld/L2-execution-boundary.md` diagram 1 and `08-configuration.md`'s "Initial-version tooling" table
("Cursor SDK... primary; Claude Code CLI and Agent SDK secondary"). R-I-13 already states the *shape* every
adapter must fill (requested/resolved model, exact runtime/adapter versions, every available usage/cost/
duration/outcome field, reasoning summary, one `tool_call` row per call) but, unlike Mastra, we have never written
a second adapter against that shape to prove it actually generalizes — this is the single largest gap this packet
surfaces (§3.1).

Where Mastra's contract explicitly includes `resumeGenerate`/`resumeStream` (because its agents are long-lived,
multi-turn, human-steerable sessions), our R-I-2 makes the opposite choice on purpose: *"Each agent attempt is a
fresh invocation... A rerun after a blocking question, failed S4 verification, or escalation learns the round and
full recorded history from registered artefacts alone"* — never a literal resumed session. Our adapter contract
therefore has no resume-token field at all, by design, not by oversight; §3 below treats every Mastra resume
mechanism as something to understand, not to port.

Mastra's per-tool-call approval gate (`PermissionPolicy`/`SessionApproval`, §1.3) and its runtime `suspend`/`resume`
primitive (§1.6) both operate *inside* one live agent turn — a live human is in the loop of a single conversation.
Our R-I-3/R-I-14 tool/capability surface is resolved once, before the invocation starts, from the manifest and
trust profile (`08-configuration.md`'s tool-attachment table), and never asked about mid-run; R-I-8 states this
explicitly — *"neither action injects steering text into a live model context."* Our analog of `ask_user` is the
S2 blocking-question mechanism (`question`/`answer` rows, `docs/prd/02-2-entities.md:85-104`): 2–4 labeled options
with a one-sentence consequence each, a `default_option`, single selection (`chosen_option`, or `free_text` under
"none of these") — no multi-select. Our analog of `submit_plan` is the S3 human plan-verdict/review gate
(R-S3-20's bootstrap checklist, `human_verdict` rows) plus S6's full approval quorum — but structurally split
across two different stages (plan approval at S3, code review at S6) rather than one reusable tool. Neither
mechanism is a *tool the agent calls mid-turn*; both are stage-boundary artefacts the trusted runner gates before
starting the next stage run.

Our skills story (`07-factory-as-code.md`'s `skills/` directory, `factory/skills/{clarification,context_gathering,
implementation,planning}.md` plus `skills/shared/codegraph-lookup.md`) is flat Markdown with a small YAML front
matter (`name`, `kind`, `stage` — `runner/definitions.py`'s `REQUIRED_KEYS`), attached to exactly one stage each by
a manifest entry (R-F-7's line cap keeps each one short), always-loaded (no search/lookup tool, no RAG layer, no
`references/`/`scripts/`/`assets/` subdirectory split, no versioning beyond the manifest's own content hash). At
four skill files this is proportionate; Mastra's two-strategy (eager-catalog vs. search-and-load) design exists to
solve a scaling problem — "too many skills to always load" — that we do not have yet.

Our tool-result handling (`runner/tool_results.py`'s `shape()`, R-I-17) is *stricter* than anything in this
packet: every tool/recipe result is written by the trusted runner to the per-run directory's `results/` subpath,
the agent's context receives only path/size/exit-status plus a bounded head-and-tail excerpt (200 lines / 8 KB,
first 40 / last 20 lines per `08-configuration.md`), and a non-text result is represented by digest/media-type/size
only — never truncated silently, never handed back whole by default. Nothing in Mastra's tool/processor layer does
this for *tool results themselves* (only `TokenLimiterProcessor` truncates model *output*); this is a place our
design is already ahead, worth keeping rather than "porting" anything toward.

Our own crash/orphan-run recovery (`docs/prd/02-3-ticket-states.md:26`, `02-2-entities.md:51`'s
`lease_expires_at`/`heartbeat_at`) already exists and is *more conservative* than Mastra's durable-agent recovery:
*"the runner expires only a run whose lease and process identity are both dead, records `infrastructure_failure`
with `failure_kind = expired_lease`, preserves registered outputs and the worktree, and reconciles pending
external writes before any state advance."* We never blindly re-drive a crashed invocation from a snapshot the way
`recoverAllDurableAgents()` does — an expired-lease run is classified as an infrastructure failure and re-enters
our ordinary single-retry path (R-I-6/02-3), not a silent replay. Mastra's own explicit non-idempotency warning
(§1.8) is external validation that our stricter choice is the right one, not a gap to close.

## 3. Portable ideas

### 3.1 Write a second runtime adapter against the R-I-13 contract before treating it as proven

One-line: prove R-I-13's adapter shape actually generalizes by building the Claude Code adapter now, shaped after
how Mastra's `ClaudeSDKAgent`/`CursorSDKAgent` both converge on one usage/tool-call normalization even though the
underlying event streams (Claude's message-content-block tool calls vs. Cursor's `onDelta` update stream) are
completely different.

- **Why it matters**: R-I-13 already claims "the record schema and stage behavior do not depend on the adapter" —
  untested with only one adapter in existence. Mastra's `SubAgent` interface would have looked plausible with one
  implementation too; its proof came from writing four. FM-19/FM-21 both depend on the contract holding across
  runtimes, not just for Cursor.
- **Rating**: `must-have for dry run` — `08-configuration.md` already commits to Claude Code as secondary runtime;
  S4 is the highest-risk stage to first prove a second adapter against.
- **Where it lands**: `runner/adapters/claude_code.py` (new file, `cursor_sdk.py`'s shape); no PRD change — R-I-13
  already specifies the contract. HLD `L2-execution-boundary.md` component G1 (`G1_adapter`), promoted from dashed
  `G1_later` to solid; no new component or seam.
- **Acceptance criteria** (draft, PRD style):
  - Returns requested/resolved model, exact adapter/runtime version, every available usage field (unavailable
    ones `null`, never estimated), one `tool_call` row per call, a `replayability` verdict — same shape as
    `cursor_sdk.py`'s `InvocationResult`.
  - A `stage_run` row from this adapter is shape-indistinguishable from one produced by the Cursor SDK adapter.
  - `must-reject:` a resolved-model mismatch records `infrastructure_failure` with no output registered, adapter-
    agnostically, matching the existing Cursor behavior; `must-reject:` any silent fallback to a default model,
    tool, or image when the requested one is unavailable.
  - Verification: one adapter-contract fixture set (settled/estimate/null/silent-fallback) run against *both*
    adapters — the shared test is the proof the contract is adapter-agnostic.
- **Size**: L (> 3 days). **Copy literally**: the `InvocationResult`/`Envelope` shape (already R-I-13/R-I-15-
  specified). **Re-derive**: the Claude Code Agent SDK event-parsing logic in Python — Mastra's
  `observeClaudeMessages`/`getClaudeToolCalls` is a reference for which SDK fields carry what, not code to port.

### 3.2 Normalize cache-read/cache-write token fields into usage capture

One-line: extend our usage capture to distinguish cache-read and cache-write tokens from ordinary input tokens,
the way every Mastra adapter's `toV3Usage()` does (`{total, noCache, cacheRead, cacheWrite}`).

- **Why it matters**: prompt caching materially changes both cost and the meaning of "tokens used" for budget
  enforcement (R-I-6, D14) — a run that hits budget through cache writes is a different failure than one that hits
  it through fresh generation, and `pricing.yaml`'s cost-provenance rule has no place to record that today.
- **Rating**: `next milestone` — cheap, but only worth doing once a second adapter exists to populate it.
- **Where it lands**: extends R-I-13 and the `stage_run` schema's usage columns; HLD component G1, same seam.
- **Acceptance criteria**: `stage_run` gains nullable `tokens_cache_read`/`tokens_cache_write` columns, populated
  only when reported, else `null` (R-I-13's existing null rule); `tokens_in`/`tokens_out` semantics unchanged;
  `must-reject:` a price-table cost computation that silently drops a reported cache-token field from the total.
  Verification: schema migration test; adapter fixture with cache-bearing and cache-absent payloads.
- **Size**: S. **Copy literally**: the four-field shape (`total`/`noCache`/`cacheRead`/`cacheWrite`) — small,
  clean, already proven across two runtimes. **Re-derive**: nothing else.

### 3.3 Multi-select and richer resume shapes for the S2 question schema

One-line: extend the `question`/`answer` schema (`docs/prd/02-2-entities.md:85-104`) to optionally support
`selectionMode: multi_select` the way `ask_user`'s `resumeSchema: z.union([z.string(), z.array(z.string())])` does.

- **Why it matters**: R-S2 questions force every multi-part decision into one option or a free-text escape hatch
  today; a genuinely two-independent-decisions clarification needs two separate rows. `new` — a usability gap, not
  tied to a named failure mode.
- **Rating**: `later` — the pilot's low question ceilings (Light 2, Standard 6) make it plausible no real pilot
  question needs this yet; revisit once real tickets show the pattern.
- **Where it lands**: extends `02-2-entities.md`'s `question` row (new optional `selection_mode` field) and R-S2;
  no new HLD component or seam.
- **Acceptance criteria**: a question row may carry `selection_mode: single | multi`, defaulting to `single`
  (backward compatible); a `multi` answer's `chosen_option` becomes a list; `must-reject:` a `multi` question with
  fewer than 2 options, or selections not a subset of the declared options. Verification: schema test over both
  modes; a fixture ticket exercising a multi-select round.
- **Size**: S. **Copy literally**: the single/multi split and "string vs. string array" resume shape. **Re-derive**:
  everything about *how* the answer is collected — ours is a Slack digest + CLI, not a live chat turn, so there is
  no "auto-resume from the next chat message" analog to port (§5).

### 3.4 Keep the two-tier verification/fix-round budget — do not flatten it toward Mastra's model

One-line: the ralph-wiggum research (§1.9) found that **neither** Mastra's shipped `goal` mechanism nor its
prototype separates "verification attempts" from "fix rounds," uses a wall-clock budget, or escalates to a human
on exhaustion — all three gaps sit exactly where our R-S4-5/R-S4-6/R-S4-9 design is already stricter.

- **Why it matters**: this is external validation, not a gap. R-S4-5's three-verification-attempt-per-plan-item
  budget, nested inside R-S4-9's two-fix-round-per-ticket budget (`08-configuration.md`: "Fix rounds. 2 per
  ticket"), both wall-clock- and token-bounded (D14), escalating on exhaustion (R-S4-6) rather than returning a
  bare failure object, is a *more conservative* design than anything in the Mastra corpus reviewed for this
  packet. FM-19 (silent failure/no escalation) is exactly the failure mode Mastra's prototype exhibits
  unmitigated.
- **Rating**: `do not port` — there is nothing to port; this entry exists to record that the comparison was done
  and came back confirming the existing design, not to propose a change.
- **Where it lands**: no change. Cites R-S4-5, R-S4-6, R-S4-9 (`04-S4-implementation.md`) as already correct.
- **Draft acceptance criteria**: none — no new behavior proposed.
- **Size**: — (no work).
- **What to copy/re-derive**: neither; this is a documentation-only finding for the report's own record.

### 3.5 A lightweight, trusted-side lifecycle-hook facility (observational only)

One-line: `mastracode`'s hook system (`mastracode/sdk/src/hooks/types.ts`) fires a user-configured shell command at
named lifecycle events (`PreToolUse`, `PostToolUse`, `Stop`, `SessionStart/End`, `PermissionRequest/Result`,
`SubagentStart/End`, `AgentStart/End`, `Notification`) with a typed JSON payload on stdin per event
(`HookStdinToolEvent`, `HookStdinStop`, `HookStdinSession`, ...), split into `BlockingHookEvent` (`PreToolUse`,
`Stop`, `UserPromptSubmit` — can veto) vs. `LifecycleHookEvent` (the rest — observe only, cannot change outcome).

- **Why it matters**: the engineer has no lightweight way today to wire "run a script when a `red_check` fires" or
  "notify me when a ticket escalates" other than reading the digest or the record directly. `new` — ergonomics,
  not a named failure mode.
- **Rating**: `next milestone` — not required for the dry run (digest and queue already surface every such event),
  and scoped narrowly: a *blocking* veto hook would need to run trusted-side and would duplicate/weaken R-I-3's
  static tool allowlist, so only the observational half is in scope; a veto hook is out of scope entirely, not
  deferred.
- **Where it lands**: new `07-factory-as-code.md` row under `scripts/` (`scripts/hooks/`, content-hashed into the
  manifest like any other script); HLD `L2-factory-as-code.md` component F7, no new component or seam.
- **Acceptance criteria**: a hook is a typed recipe (R-I-16 shape) triggered by a named runner-lifecycle event,
  never by anything the agent sandbox can invoke; hook output is captured as governed evidence and never re-enters
  a running invocation's context; `must-reject:` a hook definition whose event name implies veto power over a
  runner decision. Verification: script test that a hook never runs inside the agent/build sandbox; manifest test
  that it is content-hashed like any other script.
- **Size**: M. **Copy literally**: the event-name set (adapted — drop `PreToolUse`/`UserPromptSubmit`, we have no
  per-call or per-message boundary to hook) and the typed-JSON-stdin-per-event pattern. **Re-derive**: the
  dispatcher itself, as a typed recipe, not a raw shell-command registry (a bare shell string would violate R-I-16).

### 3.6 Skill directory shape: `references/`, `scripts/`, `assets/` subdirectories

One-line: when `factory/skills/` grows past a handful of files, adopt the Agent Skills spec's three-subdirectory
convention (`references/` for supporting docs, `scripts/` for helper code, `assets/` for other bundled files)
rather than inventing our own.

- **Why it matters**: `skills/shared/` already exists for cross-stage procedures; as shared skills grow, some will
  need bundled reference material or helper scripts that don't belong inline in the Markdown body. `new` — pure
  structure, no failure mode.
- **Rating**: `later` — four skill files plus one shared skill today; R-F-7's line cap has kept this pressure from
  building up.
- **Where it lands**: extends `07-factory-as-code.md`'s `skills/` line; HLD component F3, no new component.
- **Acceptance criteria**: a skill directory may contain `references/`, `scripts/`, `assets/` subdirectories,
  hashed by the manifest the same way as the skill's own file (R-F-1 already covers this — naming convention
  only); `must-reject:` a bundled script invoked by anything other than a typed recipe. Verification: manifest
  test that bundled files hash the same way as the skill body.
- **Size**: S. **Copy literally**: the three-subdirectory names/meanings. **Re-derive**: no search/versioning
  layer — our manifest hash already plays that role at this scale.

### 3.7 A question worth raising, not yet a portable mechanism: session-scoped tool grants for interactive `factory` CLI use

One-line: Mastra's category×policy permission model with session-scoped "always allow this category" grants
(§1.3) and a YOLO override is a real answer to "how should an engineer interactively re-run a stage without being
asked the same thing every time" — a use case our fully-automated, pre-declared-manifest model does not currently
name at all outside the human queue.

- **Why it matters**: `08-configuration.md`'s day-one decision list already gives the engineer direct CLI
  commands (`factory run <stage> <ticket>`, `factory show`) that are, in effect, interactive single-stage
  invocations — but every capability decision for that run still comes from the same static manifest as a fully
  automated run. There is no engineer-facing notion of "for this one interactive session, let me approve a
  broader tool set" the way Mastra's session grants do.
- **Rating**: `do not port` for the closed automated loop itself (R-I-3's static, pre-resolved allowlist is
  exactly the FM-05/FM-20/FM-23 protection a live per-call "ask" gate would weaken — an in-process approval
  prompt is bypassable and unauditable compared to an OS-enforced sandbox boundary resolved before the process
  starts). Flagged here only because it surfaces a real open question (§4), not because the mechanism itself
  should be adopted.
- **Where it lands**: n/a — no work proposed.
- **Acceptance criteria**: n/a.
- **Size**: —.
- **Copy/re-derive**: neither.

## 4. Questions for the owner

Plain words, no ids, with a stated default for each.

1. **Should we commit to building a second runtime adapter (Claude Code) before the pilot ticket, or after the
   first pilot ticket completes on Cursor SDK alone?** Building it first proves the adapter contract generalizes
   before we depend on it; building it after means the pilot ticket is the first real test of whether our "the
   record schema doesn't depend on the adapter" claim actually holds, but keeps the pilot timeline shorter.
   Default: build it after the first pilot ticket, since the configuration table already calls Cursor SDK primary
   and the pilot's whole point is proving the walking skeleton works at all before widening it.

2. **Do we want any engineer-facing way to run a single stage interactively with a broader, session-scoped tool
   allowance (like Mastra's "approve this category for the rest of the session"), or should every `factory run`
   invocation always use the exact same static manifest allowlist a fully automated run would use?** A broader
   interactive mode is convenient for debugging a stuck ticket but is also exactly the kind of live per-call
   decision our design currently refuses to make. Default: no — every invocation, interactive or automated, uses
   the same pre-resolved manifest allowlist; an engineer who needs broader access edits the manifest through the
   ordinary reviewed-change path instead.

3. **Should the engineer be able to register simple observational scripts that fire on runner lifecycle events
   (a ticket escalates, a fix round starts, a check goes red) without waiting for the next digest cycle, or is the
   twice-daily digest plus the queue view sufficient for the pilot?** A hook facility is cheap to build small and
   easy to build unsafely large. Default: the digest and queue are sufficient for the pilot; revisit once real
   pilot tickets show a concrete need for faster-than-digest notification.

## 5. Do-not-port list

- **Runtime `suspend()`/`resumeGenerate()` mid-invocation resume, in any form (session id, conversation id,
  response id, or agent id).** Our R-I-2 makes the opposite choice deliberately: every attempt is a fresh
  invocation with no transcript inheritance from any earlier one, including its own earlier attempt. Adopting any
  form of Mastra's resume contract for the core stage loop would directly contradict a decision already made and
  cited (C1, C3, C4, P4, P7, FM-19, FM-21).
- **Forked subagents that reuse the parent's live conversation/thread for prompt-cache efficiency.** Same reason
  as above — this is architecturally the same move as session resume, just applied to a subagent instead of the
  top-level run. Our S2 restatement children and any future subagent-shaped invocation should stay on Mastra's
  *non-forked* path (self-contained task description, isolated context) — which, notably, is already what we do.
- **Free-text subagent-to-parent result contract (`{content: string, isError: boolean}`).** Mastra's subagent tool
  hands the parent *another LLM turn* a prose summary because the consumer is itself a model that reads text. Our
  stage hand-backs (R-S4-1's handoff, R-S4-2's deviation set) are consumed by the trusted runner, not by another
  model — a typed, schema-validated hand-back is strictly better for us and downgrading to prose would be a
  regression, not a simplification.
- **Per-tool-call live approval gate (`PermissionPolicy: allow/ask/deny` resolved per call, `SessionApproval`'s
  in-process promise-based pause).** This entire mechanism exists because Mastra's target use case includes a
  live human watching one conversational turn. Our automated stages have no live human present during execution
  (R-I-3, R-I-8); the equivalent decision point in our design is the manifest resolved once before the sandbox
  starts, which is stronger (OS-enforced, pre-committed, auditable as a single resolved-set write) than any
  in-process "ask" callback could be.
- **`recoverAllDurableAgents()`-style blind re-drive of a crashed run from its last snapshot.** Already covered in
  §2 — our lease-based expiry already exists, is more conservative (classifies as `infrastructure_failure` and
  re-enters the ordinary single-retry path rather than replaying), and Mastra's own documentation warns this
  requires idempotent tools, a guarantee we do not have and should not assume.
- **ACP as a protocol dependency.** Interesting as a design reference (§1.2) for what a minimal cross-runtime
  contract looks like, but adopting it would mean depending on a third-party protocol SDK
  (`@agentclientprotocol/sdk`) beyond the enterprise rule's named exceptions (GitHub, Atlassian, Slack, codegraph);
  it also solves a problem — integrating with *many* different vendor coding-agent CLIs through one client
  surface — that we do not have, since we have deliberately scoped to exactly two named runtimes.
- **Code mode (model-authored batch-orchestration scripts).** Solves a context-window/round-trip efficiency
  problem for tool-call-heavy turns; our per-plan-task invocations already make comparatively few tool calls each
  (one task, one fix round), so the problem this solves does not show up at our grain of work.
- **Tool-provider catalog allowlisting (`allowedToolkits`/`allowedTools` wildcard patterns over a large
  third-party SaaS-integration catalog).** There is no catalog to filter — the enterprise rule already caps our
  external tool surface to four named exceptions; a wildcard-pattern allowlist mechanism has nothing to operate
  over.
