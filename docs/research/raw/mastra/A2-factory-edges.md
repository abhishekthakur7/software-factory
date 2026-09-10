# A2 — Factory edges: integrations, sandboxes, web host, factory UI

Packet: Mastra Software Factory edges — integrations, sandboxes/workspaces, the web host, and the factory UI, compared against our S0–S7 factory. Mastra paths are under `/Users/abhishekthakur/Developer/mastra/`; ours under `/Users/abhishekthakur/Developer/soft-factory/`.

---

## 1. What Mastra does here

### 1.1 The shared integration contract

`mastracode/factory/src/integrations/base.ts:180-268` defines one interface every external system plugs into, `FactoryIntegration`: `id`, optional `intake` (issue-oriented capability) and `versionControl` (repo/PR capability), `initialize()`, `routes(ctx)`, `agentTools()`/`sessionTools()`, `postToolObserver()`, `workers(ctx)` (background pollers), `channels(ctx)` (chat platforms), `feedPublisher(ctx)`, `diagnostics()`, `audit()`. An integration is a self-contained class constructed once at boot with explicit credentials; no other module reads its env vars. An absent integration means its routes never mount and the server still boots — the same "capability, not configuration" shape the sandbox abstraction uses (base.ts:1-18).

Two narrower capability contracts most integrations implement:
- **`Intake`** (`factory/src/capabilities/intake.ts:134-153`): `listSources/listItems/listIssues/getIssue/createComment/updateIssue/resolveIntakeDispatch`. `updateIssue` must not throw for a policy miss (unsupported target state) — only for infrastructure errors — so the caller can read `null` as "nothing to do" vs. an exception as "retry." Every write carries an optional `actingUserId?` for per-user attribution, honored only by the Platform proxy (§1.5).
- **`VersionControl`** (`capabilities/version-control.ts:236-273`): full PR/review/comment/reviewer CRUD, implemented only by GitHub.

Everything lives inside a board lifecycle (`factory/README.md`): a work item moves through installed `defineBoard()` phases, each declared `resting` (parked, a human move arms autonomy), `working` (an agent seat, `role` required), or `terminal` (releases the sandbox). Rules are never global — each integration owns its own per-event handler map (`rules: {issueOpened, issueClosed, ...}`), each handler a pure function returning one typed `Decision` (`transition`, `upsertLinkedWorkItem`, `invokeSkill`, `sendMessage`, `notify`) or `undefined`; a `null` entry disables a default handler, an `undefined` key keeps it.

### 1.2 GitHub — the richest integration (`integrations/github/`, ~19,600 lines incl. tests)

**Entry.** A webhook, HMAC-SHA256-verified over the raw body with `timingSafeEqual` (`webhook.ts:129-138`), keyed by `x-hub-signature-256`, dated by `x-github-delivery`. `SUPPORTED_GITHUB_WEBHOOK_EVENTS` = `issues, issue_comment, pull_request, pull_request_review, pull_request_review_comment, push` (push accepted but never classified — used only to trigger base-checkpoint rebuilds). `classifyGithubWebhook` maps `(event, action)` to `{priority, kind, terminal}` for notification routing. Two more entry paths run beside the webhook: a **reconciliation worker** (`GithubReconcileWorker`, default 1 hour, sweeps once on boot "since a restart is exactly when webhooks were most likely missed," no stored cursor — every tick re-lists every bound item fresh) and **poll-on-view** (opening the issues/PR list in the UI replays each item through the same rule ingress with a synthetic delivery id).

**What it writes back, and on what event.** The critical finding: the webhook→rule-engine path (`default-rules.ts`) **never calls the GitHub API**. Every lifecycle handler (issue opened/closed, PR opened/merged, review submitted) only emits internal board decisions; GitHub state flows in, board state changes, nothing writes back as a *consequence* of an inbound event. The only GitHub-side writes Factory itself initiates are: (a) a triage-comment upsert with a marker string (`upsertFactoryTriageComment`, find-by-marker-and-bot-author then create-or-update); (b) clearing a `needs approval` label when a human accepts a triaged card on the board (`acceptance-labels.ts`, best-effort, 404-tolerant, warns rather than blocks); (c) observing (never authoring) a PR the agent opened itself by running `gh pr create` inside its own sandbox, then recording **provenance** — parsing the PR URL out of the tool result, verifying it via a live `GET` against GitHub before trusting it, and linking it back to the originating work item (`provenance.ts:52-168`, dedupe key `factory-pr-provenance:{repoId}:{prNumber}` scoped per project). Factory never opens/merges/approves a PR on its own initiative; the agent's own `gh`/git commands, run inside the sandbox under the installation's own token, do that.

**Identity.** Writes authenticate as the GitHub App installation (`getInstallationOctokit`), never as the triggering human — every write appears as `<slug>[bot]`. A **self-recognizing bot identity**, `GithubAppIdentity` (`app-identity.ts:23-61`), tracks its own login two ways in order of trust: *observed* (captured live from the author GitHub reports on Factory's own writes — free, no config) then *configured* (`${slug}[bot]`) — `matches()` fails closed when unknown, and this is what stops the rule engine waking itself on its own comment. A trust gate (`trustedGithubActor`) checks live collaborator permission (`{admin,maintain,write}`) with a 5s timeout that fails closed, plus an allowlisted set of third-party review bots (`coderabbitai[bot]`, `devin-ai-integration[bot]`).

**Auth.** GitHub App installation tokens for almost every write (minted fresh per call, no local cache — Octokit handles TTL); an optional org PAT (`pat.ts`) for endpoints installation tokens 403 on, with a separate optional `reviewer` PAT identity; refresh is reactive (agent calls a `github_refresh_token` tool after an auth failure), not scheduled.

**Idempotency (two layers, storage-backed, not header-only).** (1) A durable `factory_rule_ingress` table, unique on `(org_id, factory_project_id, identity)`; `identity` is deterministic per real-world fact — the real webhook uses `installationId:deliveryId`, the reconcile sweep synthesizes a **timestamp-free** string (`reconcile:{repoId}:pull-request:{n}:{merged|closed}`) so repeat sweeps that still find the same state replay harmlessly, poll-on-view embeds a timestamp because it represents a one-time "opened" fact. (2) A decision-level `idempotencyKey` (`${ingress.id}:<suffix>`, e.g. `:issue-intake`, `:pull-request-merged`) unique per `(evaluation_id, key)`, so two effects inside one ingress evaluation can't double-fire. On top: check-before-write everywhere (skip if state already matches), metadata-diff-and-skip in every reconciler, and a lease-based cross-replica mutual exclusion for every periodic worker that falls back to *no* cross-replica guard when the pubsub backend lacks leases (correctness then rests entirely on the ingress table).

**Sandbox seam.** `github/sandbox.ts` owns git/GitHub operations *inside* an already-running sandbox, never sandbox lifecycle itself: a repo is never cloned onto the host, only inside the sandbox; every credential crossing the boundary is injected into `origin` for one git operation and immediately scrubbed (`withInstallToken`/`scrubRemote`).

### 1.3 Linear — polling only, narrower writeback (`integrations/linear/`)

No webhook file exists at all. Entry is UI-driven (viewing the issue list replays results through the rule ingress) plus a background sweep (5-minute default) using the **same generic, provider-agnostic reconciler** GitHub's issue half and incident.io share (`integrations/issue-reconciler.ts:84-162`). Writes back only on explicit agent tool call — `linearIssueObserved`/`linearIssueClosed` never call `updateIssue`/`createComment` themselves, only emit internal board decisions. `updateIssue` is a GraphQL mutation with a no-op check before writing (`if (targetState.name === issue.state) return`); `createComment` is a genuine write, exposed as an agent tool. There is **no bot-identity/self-loop guard at all** for Linear — a single org-owned OAuth token authors every write, and `actingUserId` is defined by the shared contract but never read by this adapter; the agent-tool docstring compensates by instructing the agent to self-identify in the comment text.

### 1.4 incident.io — a different intake shape, minimal writeback (`integrations/incidentio/`)

`routes(): []` — zero HTTP endpoints, so no inbound receiver of any kind; the only ingestion is the same generic reconciler, and it only **refreshes items already imported**, never auto-creates a task from an opening incident. `IncidentioApiClient`'s only mutating verb in the whole client is `PUT /v3/follow_ups/{id}` — incidents and comments are entirely read-only; `createComment` is a permanent stub returning `null`. Incidents and follow-ups are exposed as two separate Intake sources sharing one `IntakeIssue` shape, disambiguated by prefixed external ids (`incidentio:incident:`, `incidentio:follow-up:`). Auth is one static API key for the whole deploy — no per-user attribution possible.

### 1.5 Platform variants — hosted-proxy mode, not a second protocol

`integrations/platform/{github,linear,incidentio}/integration.ts` never hold direct provider credentials; they hold a bearer token to Mastra's own hosted Integrations proxy (`platform/api-client.ts`, region-resolved `https://integrations.{us,eu}.mastra.ai`). On the Platform path GitHub's webhook is terminated **once, centrally** by Mastra's hosted service, and each deployment instead long-polls a cursor-based per-repository event log (`PlatformGithubEventWorker`, `GET /v1/server/github-app/repositories/{id}/events`, 20s default poll, 500-event pages) and hands each fetched event to the **same** dispatch function the direct webhook path uses — no duplicated logic. incident.io's Platform variant has no bespoke worker at all, reusing the plain generic reconciler. The one capability the Platform proxy adds that no direct integration has: `PlatformApiClient.request()` accepts `actingUserId`, sent as `x-acting-user-id`, letting the centralized proxy resolve a human's *own* linked OAuth connection so issues/PRs are authored as that person instead of a shared bot.

### 1.6 Slack and WorkOS (briefly)

Slack is not a ticket source: it is a notification/feed channel (`SlackFeedPublisher` mirrors a work-item comment into the item's Slack thread, formatted `**Author**: body` since "the bot cannot post as the commenter") plus a DM-based account-linking flow that binds a Slack identity to a Mastra tenant. WorkOS here is audit-log export only (`audit(event)` forwards to WorkOS Audit Logs, swallowing failures so an outage never blocks Factory's own trail) plus an admin-portal deep link — SSO lives in a separate package.

### 1.7 Sandbox/workspace abstraction (`packages/core/src/workspace/`, `mastracode/factory/src/sandbox/`)

**Core types** (`workspace/types.ts`, `lifecycle.ts`): `WorkspaceStatus = pending|initializing|ready|paused|error|destroying|destroyed`. Lifecycle is deliberately split by provider kind: `FilesystemLifecycle` (two-phase, `init()`/`destroy()`) vs. `SandboxLifecycle` (three-phase, `start()`/`stop()`/`destroy()`), both built on a common `Lifecycle<TInfo>` carrying `status`/`error`/`getInfo()`. `ProviderStatus` adds `starting|running|stopping|stopped` to the workspace enum. `SandboxStartResult { outcome: 'created'|'connected' }` is the explicit id-keyed getOrCreate contract every provider must resolve.

**Filesystem** (`workspace/filesystem/filesystem.ts`) — `WorkspaceFilesystem extends FilesystemLifecycle`: `readFile/writeFile/appendFile/deleteFile/copyFile/moveFile/mkdir/rmdir/readdir/exists/stat`, `WriteOptions.expectedMtime?` for optimistic-concurrency writes, an optional `WorkspaceFilesystemAudit` (`getHistory/count`) for providers like AgentFS. Entirely separate interface hierarchy from the sandbox.

**Sandbox / process** (`workspace/sandbox/sandbox.ts`, `types.ts`) — `WorkspaceSandbox extends SandboxLifecycle`: identity (`id/name/provider`), `executeCommand?`, `writeFiles?`, `processes?: SandboxProcessManager`, `mounts?: MountManager`, `mount?/unmount?`, and two optional capability bundles gated by runtime type-guards (`supportsNetworking`, `supportsComputer`) since providers differ wildly (Docker has neither; E2B has FUSE mounts + public ports; some providers expose a GUI desktop). `ExecutionResult`/`CommandResult` carry `stdout/stderr/exitCode/timedOut/killed` plus streaming (`onStdout/onStderr`) and a **retention cap** (`maxRetainedBytes`, default 1 MiB for spawned processes, oldest-dropped/newest-kept — callbacks still see every byte). `SandboxError` hierarchy: `SandboxExecutionError`, `SandboxTimeoutError(timeoutMs, operation)`, `SandboxNotReadyError`, `IsolationUnavailableError(backend, reason)`, `MountError`/`MountNotSupportedError`/`FilesystemNotMountableError`.

**Agent-safety layer above the interface, not part of it**: `file-read-tracker.ts` enforces read-before-write (compares mtime, flags a write on an unread or externally-modified path with a human-readable reason) and `file-write-lock.ts` is a per-file promise queue serializing concurrent writes (30s timeout) — both wired in at the tools layer, not inside `LocalFilesystem`/`CompositeFilesystem`.

**`MastraSandbox` base class** — the provisioning engine every real provider extends: `_start()` is idempotent/coalesced (concurrent calls join one in-flight promise; a `'destroyed'` sandbox refuses to start); three acquisition "rungs" a provider can implement — override the `find()/connect()/create()` primitives (E2B), return a `SandboxStartResult` directly, or return `void` and let the base infer nothing (Docker, which does its own container lookup/create dance). `onStart` fires once per boot (fresh or reconnect), errors fatal; `ensureRunning()` is the lazy-boot entry every tool call goes through.

**Providers read in depth:**
- **Docker** (`workspaces/docker/src/`) — looks up an existing container by label `mastra.sandbox.id=<id>`, else pulls the image and creates a long-lived container (`sleep infinity`; commands run via `docker exec`, never `docker run`). Hardening options map straight to `HostConfig` (`capDrop/capAdd/securityOpt/readonlyRootfs/pidsLimit`), with an explicit warning system that *logs but doesn't fail* when `privileged:true` would defeat the hardening options, or when a reconnected container's actual config doesn't match the requested one. Stdout/stderr streaming is hand-rolled: Docker's 8-byte-header multiplexed exec stream is demultiplexed by hand, and command timeout is a manual `setTimeout` → process-group kill inside the container. No `mount()`/`networking` — bind mounts are set once at container creation via `HostConfig.Binds`, not the FUSE mechanism.
- **E2B** (`workspaces/e2b/src/`) — the find/connect/create ladder, with a multi-rung **template fallback** (try the primary template → a declared fallback → the default mountable template → force-rebuild), gated only on the failure actually being "template unusable," never on auth/quota/network errors ("an ambiguous timeout must not create a duplicate VM"). `stop()` **pauses** (freezes filesystem/memory, stops billing, unmounts FUSE mounts first since they don't survive pause) vs. `destroy()` kills outright. FUSE mounting (S3/GCS/Azure) validates the mount path against a fixed regex, refuses to shadow a non-empty directory, and writes a marker file so a reconnect can tell "already mounted, matching config" from "config changed, remount." Streaming/timeout for commands are handled server-side by the E2B SDK itself, not hand-rolled.
- **Platform-workspace** (`workspaces/platform-workspace/src/`) — Mastra's own hosted sandbox, a thin REST/WebSocket client to a proxy service (`workspaces.{us,eu}.mastra.ai`) that itself wraps Railway or E2B (`SANDBOX_PROVIDER` env). Notable: a **dual transport** — the normal control-plane lease/WebSocket path, plus a private-network direct call to an in-VM sidecar when the create/get response exposes an `instanceUrl`, cached in a process-local registry and evicted on any transport failure so the next call falls back cleanly.
- The remaining ~15 providers (`agentfs, apple-container, archil, azure, blaxel, cloudflare-sandbox, files-sdk, gcs, google-drive, mesa, modal, railway, s3, vercel`, `e2b-desktop`) were only listed, not read in depth, per the packet's scope.

**Factory-level orchestration** (`mastracode/factory/src/sandbox/session-sandbox.ts`): trigger is **first access to a session's workspace**, not a webhook — `sandboxStart: 'lazy'|'eager'` (default lazy: boots on the agent's first command). Provider selection is a caller-supplied callback (`sandbox: ctx => new E2BSandbox({id: ctx.sessionId})`), never an env var the factory itself reads — omitting it disables sandboxes entirely. **Sandbox identity is the session id**, by explicit contract ("the provider must honor id-keyed getOrCreate on `start()`"); construction must be side-effect-free, VMs provision only on `start()`. Release: `releaseSessionSandbox({sessionId, destroy?})` — `stop()` (work item closes, may reopen — VM stays pausable) vs. `destroy()` (repository unlinked or session permanently deleted), decided one layer up by a `SessionRetirementCoordinator` with **per-session serialized locks** (a competing retire request chains onto the in-flight one). A repo's `teardownCommand` runs inside the sandbox before release, but only if this process actually resolved the session's workdir — an unresolved workdir means nothing to undo. Setup-command idempotency is a marker file keyed by a digest of the command, explicitly "a skip cache, not a correctness mechanism — the setup command is assumed idempotent." Idempotency against collisions stacks: `MastraSandbox._start()`'s per-instance coalescing, plus a factory-level `sessionSandboxes: Map<sessionId, entry>` that only coalesces **within one process** — cross-replica double-create is an accepted gap, left to "the provider's own idle lifecycle (pause/idle GC)." No "settle vs. abort → commit vs. discard" decision point was found tied to teardown; `settle-or-abort.ts` turns out to be an unrelated generic `settleOrAbort(promise, signal, fallback)` utility.

**Agent-controller tie-in**: `AgentController` accepts a `workspace` (static or per-request resolver), hands it into `Session`; `workspace_status_changed`/`workspace_ready`/`workspace_error` events tell a client when it's live. Tool binding: `createWorkspaceTools(workspace, ...)` (core, not factory) builds the actual `mastra_workspace_*` tool set (`read_file`, `write_file`, `execute_command`, …) for one run; factory code never talks to `WorkspaceSandbox`/`WorkspaceFilesystem` directly inside the run loop.

### 1.8 Web host (`mastracode/web/`)

Pure backend/deploy wiring — `web/src/mastra/index.ts` is the only application file; there is no React here at all (`web/README.md`: "React code belongs in factory-ui"). It reads every deployment env var exactly once and maps it onto `MastraFactory` config (storage, auth, sandbox provider, integrations). `factory-ui`'s built SPA is served same-origin in production ("integrated mode") or by a separate Vite dev server proxying to the API ("split UI mode").

**GitHub App onboarding**: `connectGithub`/`manageGithubConnection`/`connectUserGithub` browser-side triggers a full-page OAuth+App-install redirect; the callback lands back on the SPA with query params handled entirely client-side (`GitHubAppCallbackHandler.tsx`), invalidating caches and toasting a result. Status is polled via `GET /web/github/status` → `GithubStatusReason = missing_config|auth_required|organization_required|not_connected|ready`. Explicit design statement: "the browser never sees installation tokens — those live only inside the server and the cloud sandbox."

**Env** (`.env.schema`, 16.6 KB, Varlock-validated, every section a no-op when unset): `MASTRACODE_PUBLIC_URL` (single source of truth for every OAuth callback), `GITHUB_APP_ID/PRIVATE_KEY/CLIENT_ID/CLIENT_SECRET/SLUG/WEBHOOK_SECRET`, `SLACK_APP_SIGNING_SECRET` (the Slack on/off switch) plus a `cloudflared` tunnel workflow for local webhook development, `FACTORY_CREDENTIAL_ENCRYPTION_KEY` with rotation via `_KEY_ID`/`_PREVIOUS_KEYS`, `MASTRA_PLATFORM_ACCESS_TOKEN`/`MASTRA_PROJECT_ID`/`SANDBOX_PROVIDER`.

### 1.9 Factory UI (`mastracode/factory-ui/src/`)

**Routes**: `/onboarding` (first-run wizard) → `/factories/:id/{work,review,boards/:boardId}` (kanban boards), `/overview` (stage funnel, running/stalled sessions, activity, commit rail, supervisor health), `/attention` (day-grouped inbox of failed decisions, retry gated by policy), `/activity` (combined board+audit feed), `/rules` (automation rules status), `/audit` (append-only log viewer), `/knowledge` (force-directed knowledge graph), `/supervisor` (dedicated chat to a supervisor agent), `/workspaces/:sessionId` or `/user/threads/:id` (the run/session detail view), `/settings/*` (account, connections, repositories, intake routing, models, memory, skills, behavior).

**Board**: merges persisted cards with *live* GitHub/Linear candidates in the Intake column; drag/menu moves only file/move a card, never start a run directly.

**Approval/permission-prompt screen** — rendered **inline in the chat transcript**, not a separate screen, driven by two SDK event shapes: `ApprovalPrompt` (from `tool_approval_required`, generic "Approve `<toolName>`?" with raw-args preview and Approve/Decline) and `SuspensionPrompt` (from `tool_suspended`, dispatched by tool name — `submit_plan` → a `SubmitPlanCard` with plan text fetched from the workspace file, prior-rejection feedback shown inline, Approve & Build / Reject; `request_access` → "Grant access to `<path>`?" Allow/Deny; anything else → free-text or multiple-choice `AskUserCard`).

**Diff/workspace viewer** — a live git-status + unified-diff panel over the session's sandbox (file tree with per-file status badges, +/− counts, drill into a diff); explicitly **read-only**, no inline hunk accept/reject — an observability surface, not an editable review tool.

**Real-time mechanism**: Server-Sent Events (`session.subscribe`), deduped across mounted consumers via a `WeakMap`, with a 1-second polling fallback that drives reconnect after a drop (explicit warning in the source against tearing down a still-connecting stream on every poll tick — that would livelock). Hidden tabs tear down their subscription entirely (browsers cap 6 connections per host).

**e2e test names** (representative, from both the MSW jsdom suite and a separate real-SSE scenario suite): `surfaces an approval prompt and executes the tool once approved`, `surfaces a submit_plan prompt and resumes on approval`, `steers the conversation to a new direction` / `aborts an in-flight run`, `resumes event delivery after disconnect and reconnect`, `re-queues a failed rule effect from the card`, `reconstructs a resolved submit_plan card from persisted message history after reload`, `does not fetch paths outside the workspace artifacts root`, `identifies Slack-created work items as Slack instead of Manual`, `shows event density, custom rows, expandable details, and automatically fetches the next page` (audit).

### 1.10 SDK — the coding-agent runtime (`packages/core/src/agent-controller/`, wrapped by `mastracode/sdk`)

A `Session` is a composition of narrow sub-managers (`SessionPermissions`, `SessionApproval`, `SessionSuspensions`, `SessionFollowUps`, `SessionStream`, `SessionDisplayState`, …) — **sessions are in-memory only**, reconstructed per process; only a fixed allowlist of keys plus mode/model selection persist to thread metadata.

**Tool-call streaming**: `AgentControllerEvent` is a ~45-member discriminated union including `tool_start`, `tool_approval_required`, `tool_suspended`, `tool_update` (partial result), `tool_end` (with a `denied` flag distinct from `isError` — a tool that resolved only because the user declined its gate).

**Permission-prompt surfacing and controller API**:
```ts
async approveToolCall({toolCallId?, requestContext?}): Promise<void>
async declineToolCall({toolCallId?, requestContext?, declineContext?}): Promise<void>
respondToToolApproval({decision: 'approve'|'decline'|'always_allow_category', toolCallId?, ...}): void
async respondToToolSuspension({resumeData, toolCallId?}): Promise<void>   // ask_user / request_access / submit_plan
```
Approval-policy precedence: explicit per-tool deny > session-wide yolo > explicit per-tool policy > session-scoped grant > tool-category grant/policy > ask.

**Interruption/abort**: `session.abort()` special-cases a run parked on an approval gate — the agent-side run is still alive waiting for a decision, so the gated call must be *declined through it* first (persisting an `output-denied` tool result); tearing the stream down first would make that decline fail. Both stream abort and the abort signal are deferred to the run engine, fired only once the synthetic decline has landed (`requestAbort({deferSignal: true})` / `completeDeferredAbort()`).

**Wiring**: the same package backs both the web/factory server (multi-tenant, SSE-fronted) and the standalone TUI (103 files import it) — confirmed by `grep -rl "@mastra/code-sdk"` on both trees. `factory-ui` (the browser bundle) never imports the SDK itself; it talks over `@mastra/client-js`'s SSE/REST client.

**`packages/core/src/browser/`** is not used by the production web product or `factory-ui` — confirmed by empty greps on those trees. It appears only in the TUI, an SDK onboarding-settings file, and the SSE test harness (Stagehand browser-tool support).

---

## 2. What we already have

| Mastra mechanism | Our coverage | How it differs |
|---|---|---|
| `FactoryIntegration` contract, webhook ingress, board rule dispatch | `runner/readers/{github,atlassian}.py` (read, injectable transport), `runner/deliverers/{github,slack,stub}.py` (write, trusted), `factory/config/trust-profile.yaml` (per-route field/class governance) | We have **no webhook ingestion at all**, by explicit design (charter D25, PRD "Explicitly not there": "no polling GitHub, fetching Actions logs, detecting new commits, or detecting merge" — R-S7 is entirely Later). Every external read is trusted-side, injectable-transport, single-purpose (`AtlassianReader.read_issue`, `GitHubReader.read_pull_request_history`), not a general capability interface with routes/tools/workers |
| GitHub write (comment/label/PR) on lifecycle events | Only `pr_create`/`pr_update` (R-T-11, R-S6-3), through `runner/outbox.py` + `runner/deliverers/github.py` | We write far less (one draft PR create/update, never a comment or label) but govern it far more: content-hash-bound idempotency key (`IntentRefused` on a payload change under the same key), an explicit `external_write` state machine (`pending→sending→reconciled/failed/superseded`), crash-injection tests at three points, compare-and-set/force-with-lease git push, and a post-create verification that the remote PR's head/body hash actually match before trusting the receipt — Mastra's provenance-verification (`provenance.ts` GET-and-compare) is the closest analogue and is narrower (checked once, not gated on a canonical content hash) |
| Identity mapping (bot self-recognition, acting-user attribution) | `factory/config/owners.yaml` (single pilot operator holds every role), `credential_role` per trust-profile route, fetched just-in-time, never in an agent sandbox | We have no self-loop problem to guard against (no webhook re-entry) and no per-human-write-attribution mechanism (all writes are attributed to the runner's own scoped key); instead every *decision* is attributed to a named human actor and role in the record (`approval_record.actor_identity`, RACI) — a different mechanism for the same underlying goal (know who is responsible), audit-first rather than API-identity-first |
| Polling reconciliation (issue-reconciler pattern) | None — explicitly excluded from Initial | Directly maps to R-S7-1/R-S7-2 (Later): "each poll records PR state... summarised," "fetches the job log and writes a summary" |
| Sandbox: provisioning / file access / command execution / cleanup | `runner/sandbox/{copies,os_policy,proxy}.py`, the S4 worktree mount, `runner/adapters/cursor_sdk.py` + `runner/launcher.py` | Mastra separates these four concerns via distinct **type-level interfaces** (`SandboxLifecycle`, `WorkspaceFilesystem`, `WorkspaceSandbox.executeCommand`, `destroy()`) across 10+ pluggable providers; we separate them via distinct **modules** for one fixed local macOS host: `os_policy.wrap()` is provisioning+exec (Seatbelt), `copies.py` is provisioning+cleanup for S5's base/head views (`cp -c -R` APFS clone, disposed in a `finally` via `provisioned()`), the worktree mount is S4's sole file-write surface, `proxy.py` is the network path (CONNECT-tunnel loopback proxy, route allowlist). No pluggable "provider" concept — Docker/containers are explicitly Later (HLD `G2_later`) |
| Command output governance | `sandbox/types.ts` `maxRetainedBytes` (live, in-memory ring buffer) | R-I-17: every tool/recipe result is written as a full governed artefact by the trusted runner outside the sandbox; the agent's context gets only a bounded head/tail excerpt (200 lines / 8 KB) plus a path. Ours never drops data (full artefact always kept); Mastra's cap is a live-memory bound for a still-running stream, a different problem (long-lived interactive session vs. one-shot recipe capture) |
| OS isolation backend | `runner/sandbox/os_policy.py` — macOS Seatbelt only (`sandbox-exec`), single `ROLES = (agent, build)` | Mastra's `native-sandbox` names an explicit `IsolationBackend = none\|seatbelt\|bwrap` enum so the same abstraction runs on macOS or Linux; ours hardcodes one OS |
| Web host / dashboard | None — D17: "Queue only, visible blocked state, Slack digest... no modal interrupts"; R-O-8 dashboard is Later | We have a local CLI (`factory queue`/`act`/`show`) and the Observatory mockup (`docs/design/claude-mockups/02-observatory/`, 8 screens: Queue, Tickets, Ticket detail, Runs, Run detail, Report, Factory, Governance) as a design reference, not a built product |
| Live run visibility (SSE transcript, tool-call streaming) | None | Our stage status is inspected on demand (`factory show`), never pushed; R-H-13 gives boundary-level visibility (stage/attempt/elapsed/budget/registered outputs) but nothing mid-invocation |
| Mid-run tool-call approval (`approveToolCall`/`respondToToolApproval`) | None, by design | R-I-8: "Stop is the only mid-invocation intervention and neither action injects steering text into a live model context." This is a **direct architectural opposite**, not a gap — see §5 |
| Plan/packet approval as a gated action | `plan_review` state (R-S3-15/20), `review` state (R-S6-1/6/7/10) — batch, at fixed stage boundaries, bound to a canonical content-hash subject | Mastra's `SubmitPlanCard` is the closest analogue: an in-transcript plan-approval prompt with prior-rejection feedback rendered inline. Ours is heavier and slower (one immutable `approval_record` per required role per canonical subject, quorum-checked, expiry-invalidated) but happens only twice per ticket, never mid-run |

---

## 3. Portable ideas

None of these are must-have for the single-ticket dry run: the dry run exercises one local ticket with no webhook ingestion, one operator, and a single macOS sandbox — the whole surface this packet studies (multi-provider sandboxes, live dashboards, webhook-driven writeback, multi-tenant onboarding) sits on Later PRD rows (R-S7, R-O-8) or beyond D20's Initial scope by design. The list below is honest about that: most ratings are `later`, a few are `next milestone` where a small, cheap piece would harden AB/B without adding scope, and several are explicitly `do not port`.

**1. Self-recognizing write identity (observed-then-configured bot login).**
What it is: before ever writing to an external system, learn your own posted-identity from what you get back, falling back to a configured value, and treat "unknown" as distinct from "not me" (`GithubAppIdentity`, `app-identity.ts:23-61`).
Why it matters: prevents a self-loop the day we ever read GitHub state back (FM-19 "slow failure," ungrounded/blocked agent keeps working; also protects against a wasted re-triage cycle).
Rating: **later** — only needed once we read GitHub comments/labels back (R-S7-6, Later); nothing writes-then-rereads in Initial.
Where it lands: PRD §4 `04-S7-pr-checks-and-merge.md`, extends R-S7-6 (new sub-clause) or a new row; HLD component: External access (C7), domain 2, seam X5.
Draft acceptance criteria: the reconciler records the account/login its own PR-comment or label write reports as author, and treats a live event whose author matches that login as self-authored, never queuing a repeat action; `must-reject:` an event whose author is unknown (never observed, no configured value) is never treated as self-authored merely by absence of a mismatch.
Verification: script test with an observed-login fixture and an unknown-identity fixture.
Size: S.
Copy literally: the "observed overrides configured, unknown is a third state" shape. Re-derive: everything else (no OAuth-bot concept in our model).

**2. Provenance-verify before trusting a tool-reported write.**
What it is: after a tool call claims it created something externally, fetch it back live and check it actually matches (repo id, number, URL) before recording it as true (`provenance.ts:120-125`).
Why it matters: FM-20 (hallucinated dependency/result) generalized to hallucinated external state — an agent's self-report of "I opened the PR" could be wrong or stale.
Rating: **do not port as new work** — we already have an equivalent, stricter check: `GitHubDeliverer.pr_create`/`pr_update` compare the returned PR's `head_sha`/`body_hash` against the exact approved payload before finalizing the receipt (`runner/deliverers/github.py:245-246,265-266`), and this runs on our own trusted-side write, not on an agent's self-report. No action needed; noted here so the comparison isn't missed.

**3. Generic, provider-agnostic reconciliation sweep (diff-then-patch-only-if-changed, replay-close-through-the-same-rule-path).**
What it is: one small reusable function (`createIssueReconciler`, `integrations/issue-reconciler.ts:84-162`) that any polling integration wraps: list bound items, resolve each against the live source, if closed replay a close decision through the ordinary rule path (not a special code path), else patch only the fields that actually changed.
Why it matters: this is close to the shape R-S7-1/R-S7-2 already specify ("each poll records PR state... summarised") — copying the *shape* now would save re-deriving it when S7 is built. Also serves FM-17 (memory rot) by keeping our mirrored state from silently drifting from GitHub's.
Rating: **later** — R-S7 is explicitly Later; no work now.
Where it lands: PRD `04-S7-pr-checks-and-merge.md`, new row alongside R-S7-1; HLD External access (C7), domain 2, seam X5.
Draft acceptance criteria: a poll that finds no drift writes nothing to the record; a poll that finds the PR closed queues the same `pr_outcome`/failure-mode classification path R-H-11 already uses, not a separate code path; `must-reject:` a poll must never write a field the ticket record didn't actually change (no touch, no timestamp bump).
Verification: script test with an unchanged-state fixture (zero writes) and a closed-state fixture (routes through the existing R-H-11 path).
Size: M.
Copy literally: the "diff first, write only the delta" discipline and "replay through the same decision path as a live event, never a shadow path." Re-derive: the whole polling/lease/cursor machinery — ours would be a single-ticket, single-operator poll, not a multi-tenant lease-guarded worker.

**4. Board-level typed decision union with per-event idempotency key convention (`${ingress.id}:<suffix>`).**
What it is: every inbound-event handler is a pure function returning one of a small closed set of typed decisions (`transition`, `upsertLinkedWorkItem`, `sendMessage`, `notify`), each carrying a deterministic idempotency key derived from the triggering event id plus a fixed suffix naming the effect.
Why it matters: a clean, auditable shape for "one external fact in, one internal effect out" — directly useful once we ever ingest an event (S7 polling, or the maintenance scanner of R-S0-9).
Rating: **later** — tied to R-S7/R-S0-9, both Later.
Where it lands: PRD `07-factory-as-code.md` (a new convention note) or `04-S7-pr-checks-and-merge.md`; HLD External access (C7).
Draft acceptance criteria: every generated effect names a stable key derived only from the triggering fact's own identity plus a literal suffix (never a timestamp, never randomness); two evaluations of the same fact produce the same key; `must-reject:` a handler that derives a key from anything mutable (current time, a retry counter) is rejected in review/lint.
Verification: script test asserting key determinism across two runs of the same fixture.
Size: S.
Copy literally: the `<factId>:<suffix>` key shape. Re-derive: the decision-type union itself (ours would be far smaller — likely just "open a red_check/queue item" and "advance a ticket state").

**5. OS isolation backend as a named enum (`none | seatbelt | bwrap`), not a hardcoded macOS path.**
What it is: `workspace/sandbox/native-sandbox` names the local isolation mechanism explicitly and picks per-host; a generated Seatbelt/bwrap profile carries a marker so it's safe to regenerate, while a user-authored profile (no marker) is used as-is.
Why it matters: nothing today — the pilot host is fixed macOS (C10, "from the first production-capable pilot" pins to the pilot host) — but CI or a second engineer's Linux machine would need this the moment either exists.
Rating: **later** — Docker/containers are already named Later (`G2_later`); this is the same bucket (a second host OS).
Where it lands: PRD `03-stage-interface.md`, extends R-I-14 (new sub-clause naming the backend as configuration, not code); HLD Sandbox block (G2), domain 3.
Draft acceptance criteria: `sandbox.yaml`'s OS policy names its backend explicitly; an unsupported backend on the current host fails closed with a named reason, never silently runs unsandboxed; `must-reject:` a host with no available backend for the configured policy must refuse to start a stage run, not fall back to unsandboxed execution.
Verification: script test faking an unavailable backend and asserting fail-closed.
Size: S (the enum and fail-closed check) but M once a second backend is actually implemented.
Copy literally: the "generated-profile marker comment, so a re-run regenerates but a hand-authored profile is left alone" convention — directly reusable in `os_policy.py` if a `bwrap` profile is ever added. Re-derive: everything else (our OS policy is already narrower and stricter than Mastra's agent profile, which the codebase's own TODO admits is unconfined on `process-exec` for the prototype).

**6. Live push status for a running ticket (SSE with a polling reconnect fallback, hidden-tab teardown).**
What it is: `session.subscribe()` streams tool-call/thread events to a client over SSE; a 1-second poll drives reconnect after a drop; a hidden browser tab tears its subscription down entirely (explicit rationale: HTTP/1.1's 6-connections-per-host cap starves other requests).
Why it matters: this is the mechanism a future Observatory dashboard would need for the Run detail screen to show a live event log instead of a static snapshot (matches R-O-8's intent, "dashboards over the record's views").
Rating: **later** — R-O-8 is Later, and D17 is explicit that Initial has no dashboard.
Where it lands: PRD `06-observability.md`, extends R-O-8 (new sub-clause on the transport) or a new row; HLD Record (domain 4) / Human surface (domain 1), a new seam once a dashboard exists.
Draft acceptance criteria: a dashboard client receives run events without polling the whole record; a dropped connection reconnects without duplicating already-shown events; `must-reject:` a hidden/backgrounded client tab must not hold a live connection open indefinitely.
Verification: manifest/script test once R-O-8 is scheduled; inspection until then.
Size: L (a whole new surface).
Copy literally: the reconnect-livelock warning (don't tear down a still-connecting stream on every poll tick) and the hidden-tab teardown rule. Re-derive: the whole transport — ours would stream from the SQLite ledger, not an in-process event bus.

**7. Prior-rejection feedback rendered inline on the next approval prompt.**
What it is: `SubmitPlanCard` shows the previous reviewer's rejection note alongside the new plan when a card is resubmitted after "request changes."
Why it matters: P9 (reviewable reasoning), FM-10 (diff without narrative) — a reviewer re-approving after a redirect should never have to go hunting for what they said last time.
Rating: **later** — tied to any built dashboard/packet UI; the underlying data already exists (`revision_after_approval` tag plus the reviewer's note, R-S6-7) and is already carried into the next S4 handoff by requirement text — this is a presentation idea for whenever a UI exists, not a data-model gap.
Where it lands: N/A (presentation only) — when the Observatory mockup's Ticket detail / Run detail screens are implemented, not a PRD row.
Draft acceptance criteria: N/A (design guidance, not a requirement).
Size: S (once there's a UI to add it to).
Copy literally: nothing code-level; re-derive the rendering entirely against our own packet shape.

**8. Command-execution retention cap for a long-running streamed process (`maxRetainedBytes`, oldest-dropped/newest-kept).**
What it is: a live in-memory bound on how much of a still-running command's stdout/stderr a sandbox keeps buffered, independent of what streaming callbacks already saw.
Why it matters: protects the trusted runner's own memory if a recipe or agent command produces unexpectedly large live output before task validation captures it to a file.
Rating: **later** — no observed problem yet (our recipes run to completion and are captured as files, R-I-16/R-I-17); worth a look only if a long-lived streamed command is ever added.
Where it lands: PRD `03-stage-interface.md`, would extend R-I-16 (recipe execution) if ever needed; HLD Sandbox interior (G3), domain 3.
Size: S if ever needed.
Copy literally: the drop-oldest-keep-newest policy with callbacks unaffected. Re-derive: nothing else — our result-governance model (R-I-17, full artefact + bounded excerpt) already solves the "don't blow the context window" problem differently and doesn't need this for the finished-result case.

**9. Explicit stop-vs-destroy sandbox teardown distinction with a dedicated, per-key-serialized retirement decision.**
What it is: releasing a session's sandbox is either `stop()` (pausable, VM state kept, used when the work item might reopen) or `destroy()` (torn down for good, used when the repository is unlinked or the session is permanently deleted) — decided one layer above the sandbox itself, with retirement requests for the same key serialized so a competing stop and destroy can't race.
Why it matters: FM-19/FM-21 (state loss, wasted budget) — tearing down a resumable environment because two teardown paths raced would be a wasted re-provision.
Rating: **do not port** — doesn't fit our model. Our sandbox is per-stage-run and ephemeral by construction (R-I-2: fresh invocation, nothing carried from an earlier one); there is no "might reopen" state to pause, and our own `provisioned()` context manager already disposes deterministically on every exit path including an exception, with no race to guard against because nothing else can be operating on the same run's copies concurrently.

**10. Diff/workspace viewer as a read-only observability panel, never an editable review tool.**
What it is: `WorkspaceChangesPanel` shows file-level git status and a unified diff with no inline accept/reject of individual hunks.
Why it matters: confirms rather than changes anything — it is exactly our own stance (S6's packet plus GitHub's native diff view, "the diff is evidence, not the artifact," P9).
Rating: **do not port as new work** — already achieved via our own artefact/packet model; noted for completeness only.

---

## 4. Questions for the owner

Only questions whose answer changes what gets written into the PRD:

1. **Once the factory ever reads GitHub comments or labels back (the Later PR-checks stage), should it recognise and ignore its own past writes, or is every read treated as new information regardless of who wrote it?** Default: recognise its own writes (idea 1 above), so a re-run of the poll never re-queues an action the factory already took.

2. **Should a command typed into a GitHub pull-request comment (like "review" or "re-review") ever be able to start or restart a stage, or does every trigger stay inside the local list view?** Default: never — every trigger stays inside the local list view, matching the existing rule that a person never approves on GitHub instead of the queue.

3. **When a future polling stage (S7) finds that a small, non-blocking write-back (like a label) failed, should that failure hold the ticket, or just get logged and the ticket moves on?** Default: log it and move on — a label is not evidence the record depends on, so it should never block on the same terms as a check result.

4. **Should the sandbox ever need to run on more than one kind of machine (for example, a Linux CI runner) before the pilot is done, or does it stay fixed to the one macOS host it already targets?** Default: stay fixed to the one host until a real need for a second one appears, matching the existing "prototype first" rule.

---

## 5. Do-not-port list

- **Mid-run interactive tool-call approval and steering** (`approveToolCall`/`respondToToolApproval`, live suspensions resumed with arbitrary data). This is not merely out of scope — it is the **architectural opposite** of R-I-8/P11: "Stop is the only mid-invocation intervention and neither action injects steering text into a live model context." A fresh invocation with a resolved tool allowlist (R-I-2/R-I-3) has no notion of a live approval gate to answer.
- **GitHub PR-comment slash commands** (`@bot review`/`re-review`) that start or restart a review from inside GitHub. Violates the charter's explicit human-surface exclusivity: the Human surface HLD file draws exactly this as a "never" node ("NEVER approve on GitHub instead of list view") and every command must cross through the `factory` command / list view (X1 person acts).
- **Full multi-tenant web host and GitHub-App-marketplace onboarding** (org-scoped OAuth wizard, resumable multi-step onboarding state, Platform proxy with per-user `x-acting-user-id` writes). Hosting-only, multi-tenant scope; our pilot is one operator with one fixed owners.yaml identity, and the enterprise rule already excludes standing up new hosted infrastructure.
- **Product/usage telemetry** (`factory_web_activity` in PostHog: page views, interaction counts, per-account activity). Directly conflicts with R-H-12's "the factory collects no keystrokes, focus events, editor telemetry, or inferred individual-attention score" and the charter's "No measure feeds performance review" anti-goal.
- **A general-purpose, reusable board/workflow engine** (`defineBoard()`, arbitrary custom boards and phases, transition-policy hooks). We already have a purpose-built, stricter state machine (`docs/prd/02-3-ticket-states.md`, C7: "stages are replaceable... behind one interface"); building a generic workflow framework on top would be exactly the charter's "No generic product" anti-goal ("built for this environment, this team, and these failure modes").
- **Computer-use / GUI desktop sandbox capability** (`SandboxComputer`: screenshot, click, drag, type). Nothing in S0–S7 needs a GUI-driven tool; adding it would only grow the sandbox's attack surface for no cited requirement.
- **Bidirectional Slack (DM account-linking, chat-driven agent runs).** Our Slack use is fixed one-way (R-H-3: "the digest... is the only Slack write"; D17: "no modal interrupts"). A conversational Slack surface that can trigger or steer runs would violate "the factory never interrupts" and add a second control-plane entry point outside the list view.

---

## Files read (this repo)

`docs/prd/prd.md`, `03-stage-interface.md`, `04-S0-intake.md`, `04-S6-human-review.md`, `04-S7-pr-checks-and-merge.md`, `05-human-interaction.md`, `02-1-ticket-record.md` (R-T-9/10/11), `02-2-entities.md` (ticket, stage_run, external_write, queue_item), `02-3-ticket-states.md`; `docs/charter.md` (principles, anti-goals, failure-mode catalogue, human-interaction contract, constraints C1–C13, decisions D4/D16/D17/D20–D22/D25/D28); `docs/design/hld/README.md`, `L1-bird-view.md`, `L2-external-systems.md`, `L2-execution-boundary.md`, `L2-human-surface.md`; `docs/design/milestones.md` (crossings, blocks); `docs/design/claude-mockups/README.md`, `02-observatory/README.md`; `docs/build/findings.md` (G-11, G-20, G-21, G-28); `factory/config/trust-profile.yaml`, `owners.yaml`; `runner/outbox.py`, `publication.py`, `readers/{github,atlassian}.py`, `deliverers/{github,slack}.py`, `sandbox/{copies,os_policy,proxy}.py`, `adapters/cursor_sdk.py`.

## Files read (Mastra repo, direct — beyond the three research passes)

`mastracode/README.md`, `factory/README.md`, `web/README.md`, `sdk/README.md`, `factory-ui/README.md`, `AGENTS.md`, `factory-ui/AGENTS.md`; `factory/src/integrations/base.ts`, `github/{webhook,app-identity,provenance,acceptance-labels,default-rules}.ts`, `issue-reconciler.ts`, `reconciliation-config.ts`, `incidentio/integration.ts`, `linear/integration.ts` (partial), `linear/default-rules.ts`, `platform/api-client.ts`; `packages/core/src/workspace/{types,filesystem/filesystem,sandbox/{index,errors,types,sandbox}}.ts`. The three background research passes (integrations; sandbox/workspace; web/factory-ui/sdk) each read 15–75 files in full and are the primary source for §1.2–1.6, §1.7 (providers), and §1.8–1.10.
