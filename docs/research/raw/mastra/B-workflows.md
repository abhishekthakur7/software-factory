# Workflow engine and durable execution — steps, suspend/resume, snapshots, retries, schedules, background tasks, batching

Packet owner reading: Mastra `packages/core/src/workflows/`, `packages/core/src/storage/domains/workflows/`,
`packages/core/src/background-tasks/`, `packages/core/src/schedules/`, `packages/core/src/workflows/scheduler/`,
`packages/core/src/run/`, `packages/core/src/events/`, `workflows/inngest/src/`, `workflows/temporal/src/`,
`explorations/durable-agent.md`, `explorations/batching-spec.md`, `docs/src/content/en/docs/workflows/`.
Our side: `docs/prd/02-3-ticket-states.md`, `docs/prd/03-stage-interface.md`, `docs/prd/04-S4-implementation.md`,
`docs/prd/08-configuration.md`, `docs/design/hld/L2-control-plane.md`, `runner/state_table.py`, `runner/transitions.py`,
`runner/run_ledger.py`, `runner/launcher.py`, `runner/budgets.py`, `runner/stage_interface.py`, `runner/control.py`,
`runner/envelope.py`, `runner/digest.py`, `runner/operations.py`, `runner/queue.py`.

---

## 1. What Mastra does here

### 1.1 The step/graph model

A Mastra workflow is a typed, imperative graph built with `createWorkflow(...).then(step).branch([...]).parallel([...]).dowhile(step, cond).dountil(step, cond).foreach(step, {concurrency}).map(...).sleep(ms).sleepUntil(date).waitForEvent(...).commit()`
(`packages/core/src/workflows/workflow.ts:1888` `then`, `:2128` `waitForEvent`, `:2314` `parallel`, `:2374` `branch`,
`:2438` `dowhile`, `:2491` `dountil`, `:2544` `foreach`, `:2032` `sleep`, `:2082` `sleepUntil`, `:2143` `map`, `:2620` `commit`).
Every builder call appends a `StepFlowEntry` to a graph that is *also* serialized to a JSON-safe `SerializedStepFlowEntry`
(`packages/core/src/workflows/types.ts:660-901`) so the same graph can be persisted, diffed, and rehydrated (`workflows/dynamic/rehydrate.ts`).
The entry union covers a live step, a declarative `agent`/`tool`/`mapping` entry, `sleep`/`sleepUntil`, `parallel`, `conditional`
(the `branch` primitive), `loop` (`dowhile`/`dountil`, carrying `loopType` and an optional declarative `Predicate` so it can
round-trip through storage), and `foreach` (carrying a `ForeachOptions.concurrency`, which may be a per-run `ForeachConcurrencyResolver`
function rather than a static number — `types.ts:734-754`). A `Step` (`workflows/step.ts:150-177`) is `{id, inputSchema, outputSchema,
resumeSchema?, suspendSchema?, stateSchema?, requestContextSchema?, execute, scorers?, retries?, metadata?}`; the `execute` closure
receives `ExecuteFunctionParams` — `inputData`, `state`/`setState`, `resumeData`, `suspendData`, `retryCount`, `getInitData()`,
`getStepResult()`, `suspend()`, `bail()`, `abort()`, a `resume`/`restart`/`timeTravel` descriptor, an `abortSignal`, a `writer`
stream, and `engine` (the platform-specific context object, e.g. Inngest's `step` primitive — `step.ts:24-72`).

### 1.2 Run lifecycle and status enums

Two parallel enums. Run-level `WorkflowRunStatus` (`types.ts:282-293`): `running | success | failed | tripwire | suspended |
waiting | pending | canceled | bailed | paused | skipped`. Step-level `StepResult` is a discriminated union over `status`:
`success | failed | suspended | running | waiting | paused | skipped` (`types.ts:73-173`), each variant carrying `payload`,
`resumePayload?`, `suspendPayload?`, `suspendOutput?`, `startedAt/endedAt/suspendedAt/resumedAt`, and `metadata?`. `paused` is
distinct from `suspended`: it is what `perStep` execution (single-step-at-a-time driving, used by Studio and some hosts) returns
between steps, with no `suspendPayload` — a control-plane pause, not a business-logic suspend. `bailed` (produced by `bail()`) is
folded back into `success` by `DefaultExecutionEngine.execute` before it is returned (`workflows/default.ts:952-954`) — `bail()`
is "exit early with a successful result," not a distinct terminal status.

### 1.3 Suspend/resume contract

A step calls `await suspend(suspendPayload?, { resumeLabel? })` (`workflows/handlers/step.ts:373-404`). This: (a) validates
`suspendPayload` against the step's `suspendSchema` if one exists; (b) records `executionContext.suspendedPaths[step.id] =
executionContext.executionPath` — the exact graph coordinate to resume from; (c) if `resumeLabel` is given (one or many strings),
writes `executionContext.resumeLabels[label] = {stepId, foreachIndex}` — a *name* for this suspend point, independent of step id,
so a foreach that suspends N parallel iterations under the same step id can still be addressed individually
(`WorkflowResumeLabel = {stepId, foreachIndex?}`, `types.ts:295-298`); (d) returns a branded `InnerOutput` sentinel type so
TypeScript can statically distinguish "this function suspended" from "this function returned a real value." `Run.resume()`
(`workflows/workflow.ts:4317-4343`, implementation at `:4498-4804`) accepts `{resumeData, step | step[] | label, forEachIndex?}`;
if no `step` is given it auto-detects the sole suspended step from `snapshot.suspendedPaths`, refusing with an explicit "multiple
suspended steps found, specify which" error if there is more than one open suspend point on the run. `resumeData` is validated
against the target step's `resumeSchema` before the run resumes (`_validateResumeData`, called at `:4622`). Nested-workflow
suspension threads a `__workflow_meta: {runId, path, foreachIndex, foreachOutput}` object through the parent's `suspendPayload`
(`workflows/default.ts:654-663`, and the Inngest nested-workflow handler at `workflows/inngest/src/execution-engine.ts:672-734`)
so a suspend three levels deep in nested workflows still resumes with one `resume({step: [outer, middle, inner]})` call.

### 1.4 The snapshot: `WorkflowRunState`

`WorkflowRunState` (`types.ts:383-408`) is the exact JSON blob persisted on every suspend/pause/terminal transition:
`{runId, status, result?, error?, requestContext?, value: state, context: {input, ...SerializedStepResult per step id},
serializedStepGraph, activePaths, activeStepsPath, suspendedPaths, resumeLabels, waitingPaths, timestamp, tripwire?,
stepExecutionPath?, tracingContext?}`. `context` doubles as both "step results so far" and the workflow's own input (`context.input`).
`docs/src/content/en/docs/workflows/snapshots.mdx:39-86` gives the canonical worked example: an `approval-step` suspended
with `{message, requestedBy, approvers}` and resumed with `{confirm: true, approver: "manager"}`, showing `startedAt`,
`suspendedAt`, `resumedAt`, `endedAt` all on one step-result row. This is *more than a status flag* — it is the entire live
execution context (which parallel branches are active, which loop iteration is running, what the accumulated `state` object
holds, the RequestContext) frozen so a resumed run can pick up exactly where it left off, including inside nested control flow.

### 1.5 Storage contract

`WorkflowsStorage` (`packages/core/src/storage/domains/workflows/base.ts:5-61`) is the abstract interface every storage
backend implements: `updateWorkflowResults`, `updateWorkflowState`, `persistWorkflowSnapshot`, `loadWorkflowSnapshot`,
`listWorkflowRuns`, `getWorkflowRunById`, `deleteWorkflowRunById`, plus `supportsConcurrentUpdates(): boolean`. The table is
`mastra_workflow_snapshot` (`storage/constants.ts:5,742-759`): columns `workflow_name, run_id, resourceId, snapshot (jsonb),
createdAt, updatedAt`. `updateWorkflowState`'s options (`storage/types.ts:2232-2263`) carry an optional
`expectedStatus?: WorkflowRunStatus | WorkflowRunStatus[]` — a **compare-and-set guard**: the write applies only if the
persisted status currently matches, otherwise it is a no-op and the call resolves `undefined`. `matchesExpectedWorkflowStatus`
(`storage/types.ts:2268-2276`) is the shared predicate stores call inside their own critical section. This CAS is what backs
`Workflow.#claimResume` (`workflows/workflow.ts:4414-4496`): before entering the execution engine, `resume()` atomically flips
`suspended → running` via `updateWorkflowState({status: 'running', expectedStatus: 'suspended'})`; a losing concurrent caller
gets `WORKFLOW_RESUME_ALREADY_CLAIMED` and never enters the engine at all (so downstream steps and their side effects cannot
double-fire — this exists specifically because of a filed bug, #20443, cited in the source comment at `:4695-4704`). If the
engine never actually starts the resumed step (crash between claim and first persist), `releaseClaimIfUnused`
(`:4707-4753`) rolls the claim back to `suspended` by re-checking that every path/step-id set is byte-identical to what was
claimed — a strictly conservative check that would rather leave a run stuck `running` than silently re-arm a suspension whose
downstream steps already fired.

### 1.6 Retry, timeout, error propagation

Step-level `retries?: number` overrides workflow-level `retryConfig: {attempts, delay}` (`docs/.../error-handling.mdx:187-233`).
`DefaultExecutionEngine.executeStepWithRetry` (`workflows/default.ts:451-537`) is a plain `for` loop: `params.retries + 1`
attempts, a flat `delay` between them, catching each failure and returning `{ok:false, error:{status:'failed', error, endedAt,
nonRetryable?, tripwire?}}` once retries are exhausted or the error is a `MastraNonRetryableError` — which short-circuits the
loop immediately regardless of remaining attempts (`:485-487`). `TripWire` (`../agent/trip-wire`, imported at `default.ts:1`) is
a distinct error class an *agent output processor* throws to reject a run; it is captured as `StepTripwireInfo {reason, retry?,
metadata?, processorId?}` and surfaces as run status `'tripwire'`, not `'failed'` — a separate terminal state precisely so a
caller can tell "the model produced something a safety/quality gate rejected" apart from "the step threw." `bail(result)` lets a
step exit the *whole workflow* early with a successful result — no further steps run, and the workflow's result is `result`
(`docs/.../error-handling.mdx:296-316`). Every retry attempt is a plain in-place retry of the *same* invocation, not a fresh
process — the Default engine's loop runs in the same Node process, and only the Inngest engine changes this (below).

### 1.7 The `ExecutionEngine` abstraction and its override seam

`ExecutionEngine` (`workflows/execution-engine.ts:73-251`) is an abstract base class: one abstract method, `execute(...)`, plus
concrete lifecycle-callback plumbing (`invokeStartCallback`, `invokeLifecycleCallbacks` for `onStart`/`onFinish`/`onError`) and
a `runPersistenceOverrides` map for per-run snapshot-policy overrides. `DefaultExecutionEngine` (`workflows/default.ts:72-1258`)
implements the whole graph-walking loop (`execute`, `:743-1155`) as a synchronous in-process `for` loop over `graph.steps`, and
exposes roughly a dozen **override hooks** other engines specialize instead of reimplementing the loop:
`isNestedWorkflowStep`, `executeSleepDuration`/`executeSleepUntilDate`, `wrapDurableOperation<T>(operationId, fn)` (the single
seam every "make this durable" concern threads through), `getEngineContext()`, `evaluateCondition`, `onStepExecutionStart`,
`executeWorkflowStep` (nested-workflow dispatch), `createStepSpan`/`endStepSpan`/`errorStepSpan` and their `*ChildSpan`
equivalents (durable tracing), `executeStepWithRetry`, `requiresDurableContextSerialization()`, and
`buildMutableContext`/`applyMutableContext` (`:720-735`, the fields a step's execution can actually mutate: `state`,
`suspendedPaths`, `resumeLabels`). This is a genuine plugin seam: a new durable executor subclasses `DefaultExecutionEngine`
and overrides only the hooks whose semantics it wants to change, inheriting the graph-walking and suspend/resume/retry
*policy* unchanged.

### 1.8 Two concrete executors: Inngest (mature) and Temporal (experimental)

`InngestExecutionEngine extends DefaultExecutionEngine` (`workflows/inngest/src/execution-engine.ts:60-832`). It overrides:
`wrapDurableOperation` to wrap every unit of work in `inngestStep.run(operationId, fn)` (Inngest's own step-memoization
primitive — on replay after a crash, a `step.run` call whose id was already recorded returns the memoized result instead of
re-executing, `:218-240`); `executeSleepDuration`/`executeSleepUntilDate` to use `inngestStep.sleep`/`sleepUntil` (durable
timers, not `setTimeout`, `:195-204`); `executeStepWithRetry` to do the *same* retry-count loop as the base class but push each
attempt through `retryCountStorage` (an `AsyncLocalStorage`) so `getOrGenerateRetryCount` reads it back deterministically across
replays (`:75-77, 121-190`); `requiresDurableContextSerialization()` returns `true` — because a replayed `step.run` does not
re-execute the original closure, any `RequestContext` mutation must be captured into the memoized result and restored on replay,
not read live off the closure (`:112-114`); and `executeWorkflowStep` to invoke a nested `InngestWorkflow` via
`inngestStep.invoke()` outside of `step.run()` (an Inngest platform constraint), handling resume, time-travel and fresh-start as
three separate `invoke` shapes (`:471-831`). A dedicated `isNonRetryableStepFailure` walks `error.cause` chains and
`NonRetriableError`/`MastraNonRetryableError`/`.nonRetryable` markers recursively (`:25-56`) because Inngest's own error
serialization can nest the classification. `TemporalRun extends Run` (`workflows/temporal/src/run.ts:14-116`) overrides only
`start`, `startAsync`, and `cancel` — dispatching to `client.workflow.start(...)`/`getHandle(...).cancel()` — and defines
**no** `resume`/`restart` override at all, so it silently inherits the base `Run.resume()`, which reads from Mastra's own
`workflowsStore.loadWorkflowSnapshot`, a storage path the Temporal adapter never writes to. The package's own README
(`workflows/temporal/README.md:5`) states: *"Experimental: `@mastra/temporal` is under active development and is not ready for
production use yet."* Suspend/resume on Temporal is, in the code as it stands, not a supported path — a useful negative data
point: two implementations of the same `ExecutionEngine` seam can diverge sharply in how much of the suspend/resume contract
they actually honor.

### 1.9 The `evented` engine: pubsub-driven, single-step-at-a-time

`EventedExecutionEngine extends ExecutionEngine` directly (not `DefaultExecutionEngine`) (`workflows/evented/execution-engine.ts:19-376`).
Instead of a synchronous loop, `execute()` publishes a start event onto `this.mastra.pubsub` and returns a promise that resolves
when a `finishCb` subscriber sees the matching `runId` terminate (`:96-110`). The actual step-by-step driving happens in
`WorkflowEventProcessor` (`workflows/evented/workflow-event-processor/index.ts`, 3205 lines) — each step's completion publishes
the *next* event rather than the engine calling the next step directly, which is what lets the workflow's execution be
distributed across process boundaries or resumed by any consumer that picks up the topic. It tracks redelivery via a
`deliveryAttempts: Map<string, number>` with a `TERMINAL_SENTINEL` value and a bounded `DELIVERY_ATTEMPTS_MAX_ENTRIES` eviction
policy (`:132-144, 2955-3029`) — its own retry-budget concern, separate from step-level `retries`.

### 1.10 Scheduling: cron-driven workflow triggers

A workflow can declare `schedule: {cron, timezone?, inputData?, initialState?, requestContext?}` (single or array,
`workflows/scheduler/types.ts:16-63`) — "only supported on the evented engine." The `Scheduler` class
(`workflows/scheduler/scheduler.ts:29-511`) runs a `setInterval` tick loop (default 10s, `DEFAULT_TICK_INTERVAL_MS`) that on
each tick: loads `listDueSchedules(now, batchSize)`; for each due row, computes `newNextFireAt` from the cron expression;
derives a **deterministic runId**, `sched_${schedule.id}_${schedule.nextFireAt}` (`:362`), so concurrent ticks across processes
converge on the same id; atomically claims the fire via `updateScheduleNextFire(id, expectedOldFireAt, newFireAt, actualFireAt,
runId)` — a CAS on `nextFireAt` itself (`:366-372`), returning `false` (skip, someone else won) if the expected value no longer
matches; and only then publishes `workflow.start`. Two fencing predicates guard against stale-build races in multi-instance
deployments: `isTargetReady` (is the workflow even registered locally? with a `missesBeforeDelete` grace window for
deploy-ordering races) and `isTargetCurrent` (does the *local build's* serialized step graph hash match the row's recorded
`definitionHash`, via `computeScheduleDefinitionHash` in `workflows/scheduler/definition-hash.ts`? — an instance running a
stale deploy must not claim and silently execute an outdated graph, escalating from warning to error after
`staleSkipsBeforeEscalation` consecutive stale-skips). Separately, `workflows/schedules/` implements agent-level cron
schedules (not workflow schedules) with their own `prepare`/`onFinish`/`onError`/`onAbort` lifecycle hooks
(`schedules/types.ts:272-279`) and an `ifActive`/`ifIdle` behavior split for whether a fire should interrupt a live thread or
queue behind it.

### 1.11 Background tasks: async tool execution with its own suspend/resume/retry

`packages/core/src/background-tasks/` gives an agent tool call its own out-of-band lifecycle, independent of the workflow
engine. `BackgroundTask` (`background-tasks/types.ts:20-62`): `{id, status, toolName, toolCallId, args, agentId, threadId?,
resourceId?, runId, result?, error?, createdAt, startedAt?, suspendedAt?, completedAt?, retryCount, maxRetries, timeoutMs,
suspendPayload?}`, `status: pending | running | suspended | completed | failed | cancelled | timed_out`. A tool executor
receives `suspend?: (data?) => Promise<void>` and `resumeData?: unknown` (`:304-331`) — the same suspend/resume shape as a
workflow step, applied to one background tool call rather than a graph node. `BackgroundTaskManagerConfig` (`:149-203`) is a
rich policy object: `mode: 'full' | 'producer' | 'worker'` (which pubsub subscriptions this instance owns, so an API tier can
dispatch without competing with a dedicated worker); `globalConcurrency`/`perAgentConcurrency` (default 10 / 5);
`backpressure: 'queue' | 'reject' | 'fallback-sync'` (`fallback-sync` signals the caller to run the tool synchronously in the
loop instead of dispatching); `defaultTimeoutMs` (300_000); `defaultRetries: RetryConfig {maxRetries, retryDelayMs,
backoffMultiplier, maxRetryDelayMs, retryableErrors}` — an exponential-backoff-with-cap policy, richer than the workflow
engine's flat `{attempts, delay}`; and `cleanup: CleanupConfig` for pruning old task records. On boot,
`BackgroundTaskManager.recoverStaleTasks` (`manager.ts:1420-1456`) resets every task still `running` from a previous process:
`maxRetries > 0` → back to `pending`; `maxRetries === 0` → `failed`.

### 1.12 PubSub, leasing, and batching

`PubSub` (`events/pubsub.ts:19-143`) is the abstract transport: `publish`/`subscribe`/`unsubscribe`/`flush`, an optional
`clearTopic` (delete retained per-topic state on run completion), a `supportedModes: ('pull'|'push')[]` flag,
`supportsNativeBatching`/`supportsOffsets`, and `subscribeWithReplay`/`subscribeFromOffset` for resumable client streams.
`LeaseProvider` (`pubsub.ts:160-219`) is a *separate* abstraction — distributed mutual exclusion, not delivery — used to
elect one process as the owner of a resource: `acquireLease(key, owner, ttlMs)`, `getLeaseOwner`, `releaseLease`,
`renewLease`, and a **gap-free** `transferLease(key, from, to, ttlMs)` explicitly designed to avoid a release-then-acquire
window a third process could steal. `NoopLeaseProvider` (`:246-264`) is the always-win single-process fallback. Batching
(`explorations/batching-spec.md`, shipped) adds opt-in per-subscription batching to `PubSub.subscribe(topic, cb, {batch:
{...}})`: `SubscribeBatchOptions {maxSize?, maxWaitMs?, minIntervalMs?, isImmediate?, coalesce?, maxBufferSize?, overflow?}`.
`BatchPolicy` (`events/event-emitter/batch-policy.ts:41-247`) is the decision engine: `onEnqueue(event)` returns
`'flush-now' | 'wait'` from size/deadline/interval-floor/immediate-escape-hatch logic; `prepareBatch(events)` applies
`coalesce` then `overflow` (`drop-oldest | drop-newest | coalesce-or-drop-oldest`) with a hard reference-identity contract on
`coalesce` (manufactured events break ack/nack routing and are treated as a contract violation). It is wired into exactly one
adapter, in-process `EventEmitterPubSub`; distributed (cache-backed) batching was designed and explicitly cut
(`batching-spec.md §4.2, §7`) because `BatchPolicy`'s timer/counter state is process-local and two replicas would race.

### 1.13 The durable-agent three-tier model

`explorations/durable-agent.md` documents three increasingly durable ways to run an agent loop: `createDurableAgent`
(resumable *streams* only — reconnect via `CachingPubSub` replay, execution stays in the HTTP request);
`createEventedAgent` (+ fire-and-forget execution via the evented workflow engine); `createInngestAgent` (+
Inngest-checkpointed execution across process crashes). The loop itself is a `dowhile(shouldContinue)` workflow:
`durableLLMExecutionStep` (deserialize messages, call the model, emit chunks via PubSub) → `foreach(toolCalls) →
durableToolCallStep` (resolve tool, check approval, suspend if needed, execute with a per-call `suspend` callback, emit
result) → an optional `scorerExecutionStep`. `RunRegistry`/`globalRunRegistry` (a `TTLCache`, 10 min TTL, 1000-entry cap)
holds the non-serializable state (tool `execute` closures) that cannot travel through the snapshot — only tool metadata
`{id, name, schema}` is serialized into workflow input, and the real object is resolved back out at execution time. Messages
are flushed to memory *before* any suspension point, so a crash between suspend and resume never loses conversation state.

---

## 2. What we already have

Our closed-loop factory has no workflow *engine* in Mastra's sense at all — `docs/design/milestones.md:85` names this
directly as a Later "Extension point": *"Orchestrator | The state table first; a workflow engine may replace it behind the
stage interface | Ticket and its state, stage interface."* Charter **D27** states the same intent from the other side:
*"The state table is the first orchestrator, not the last; durable workflow engines and DAG orchestrators are the expected
direction, adopted when the state table demonstrably fails (D24)."* **D24** keeps "durable workflow engines" explicitly in
`docs/prd/inputs.md` as a tooling candidate, adopted "only when the adoption cites a constraint or a failure mode" — so this
whole packet exists to answer exactly that question for a future milestone, not to justify adopting Mastra now.

**The graph.** Mastra's `StepFlowEntry` union (branch/parallel/loop/foreach/map/sleep) has no counterpart in our system: a
"stage" is not a graph of composable steps, it is one fixed driver function (`runner/stages/S<n>.py`, dispatched by
`HLD L2-control-plane.md` C6) that either runs the recipe/agent work for that stage or does not run at all. Our only graph
is the **ticket state machine**, `runner/state_table.py:101-177`, a flat `dict[(from_state, event), to_state]` — data, not
code, deliberately kept "outside `factory/`... so no proposal path can ever reach the gates it enforces" (`state_table.py:1-8`).
The state machine dispatches at most one stage driver per `advance()` call (`docs/prd/02-3-ticket-states.md`'s state table is
its own documentation of this graph, 13 open states + `pr_checks`); there is no `parallel`/`foreach` primitive because the
whole factory processes one ticket end-to-end per attempt (D28 caps parallel tickets at 1 in Initial). The one loop
construct we have is R-S4-9's fix round — `docs/prd/04-S4-implementation.md:R-S4-9` — a bounded `checks → implementing →
checks` cycle capped at `limits.yaml`'s `fix_rounds` (2, `08-configuration.md:39`), tracked by `stage_run.run_kind =
'fix_round'` rather than a `LoopConditionFunction`'s `iterationCount` — philosophically Mastra's `dowhile`, expressed instead
as one hardcoded state-table edge (`("checks", "checks_fix_round"): "implementing"`) plus a config-carried round cap.

**Status enums.** `runner/schema.py:82-91` `OUTCOMES = (pass, fail, infrastructure_failure, sandbox_violation, blocked,
aborted_budget, aborted_human, refused)` is our `stage_run.outcome`, the rough analog of Mastra's `StepResult.status`. Ours
is *stricter and more causally specific*: where Mastra collapses every non-retryable failure into `nonRetryable: true` on a
generic `failed` status, we split by *cause* — `infrastructure_failure` (retry, doesn't consume verification quota),
`sandbox_violation`/`refused` (control defect, escalates immediately, never retried), `aborted_budget`/`aborted_human`
(operator-terminated, quota preserved) — each cause routing to a different resume path (`docs/prd/02-3-ticket-states.md`
"Failed and blocked runs" paragraph; R-S4-5, R-S4-6). `ticket.state` (14 values, `state_table.py:29-44`) is our run-level
status; there is no `waiting`/`paused`/`bailed`/`skipped`/`canceled` equivalent because a ticket is never mid-step — it is
always sitting *between* stage invocations.

**Suspend points and resume payload.** Our suspend mechanism is `queue_item` + `ticket.blocked_on`: `queue.open_item`
(`runner/queue.py:91-117`) inserts a typed `queue_item` row and, unless its `kind` is `pr_outcome` (non-blocking by design),
sets `ticket.blocked_on = item_id`. `ACTIONS: dict[str, frozenset[str]]` (`queue.py:48-58`) is our closest analog to a
per-step `resumeSchema` — but it types the *verb space* per `queue_item.kind` (e.g. `plan_approval` accepts `approve, redirect,
send_back, abandon, verdict, verdicts, waiver`), not a JSON schema for the resume *payload*. `act()`
(`queue.py:761-...`, ~470 lines) validates the actor's role, mandatory-bucket and mandatory-`self_contained` rules
per-action, then dispatches to the same functions any other caller uses (`transitions.apply`, `approvals.record_approval`,
`outbox.intent_for_review_quorum`) and settles the item's once-only resolution columns. There is exactly one blocking item
per ticket at a time (`blocked_on` is a single foreign key) — so Mastra's `WorkflowResumeLabel`/multi-suspended-step
disambiguation problem does not arise for us by construction, not by a mechanism we would need to port. `_resume`
(`queue.py:654-694`) is the escalation-specific resume router: it reads `stage_run.failure_kind` off the run the item's `ref`
names and picks the resume event by *cause* — `verification` exhaustion refuses plain resume entirely (only
`send_back --to planning` with a new plan-item version); `sandbox_integrity`/`recipe_binding` requires a `remediated`
disposition and a fresh passing gate run first; everything else (infra failure, human stop) resumes the interrupted stage
with quota preserved. This is the same idea as Mastra reading `resumeLabels`/`suspendPayload` to route a resume, applied to
our own richer failure taxonomy.

**Snapshot.** We have none, deliberately. **R-I-2** (`docs/prd/03-stage-interface.md`) states the opposite design choice:
*"Each agent attempt is a fresh invocation. It receives the governed ticket artefacts named in the manifest for that stage,
their hashes, the rubric file, and nothing from an earlier invocation's transcript... Reconstructable means the input and
execution envelope can be rebuilt; it does not mean a hosted model must return identical output."* `runner/envelope.py`
implements this literally: `build()` (`:249-...`) assembles the `Envelope` (`ticket_id, stage, inputs (ordered artefact
refs), agent_hash, skill_hash, rubric_hash, manifest_hash, trust_profile_hash, ..., base_sha, head_sha, tool_allowlist,
approval_subject_hash`) a *fresh* invocation receives, and `reconstruct()` (`:331-398`) rebuilds the *same shape after the
fact* purely from the `stage_run` row's own immutable columns, the ticket, and the artefact rows its `inputs` column names —
"never the manifest file or the recipe catalogue again, since a later edit to either must not silently change what an
already-run invocation is said to have received" (`envelope.py:334-343`). There is no mid-step resumption at all: `advance()`
(`runner/operations.py:74-131`) never resumes a *stage run*, only the *ticket's position in the state machine* — the "resume"
after a human answers a question or approves a plan is always a brand-new `open_stage_run` with `attempt + 1`
(`run_ledger.py:112-155`), never a continuation of the interrupted process. Where Mastra's snapshot answers "what was this
step doing when it stopped, so we can pick the thread back up," our record answers "what would a brand-new invocation need
to reach the same decision" — a stronger auditability property (R-I-15's reconstructable envelope) traded for zero
mid-invocation resumability.

**Retries, timeouts, budgets.** Mastra's flat `{attempts, delay}` per step/workflow (`workflows/default.ts:800,
executeStepWithRetry`) versus our two-tier bound: **ordinary stage retries** are "one fresh rerun after `fail` or
`infrastructure_failure`, then escalation" (`08-configuration.md:37`) — a hardcoded single retry, not a configurable count,
per the owner's "prefer rules to hard-coded numbers... lax initially" stance (feedback memory
`feedback-lax-initially-no-hardcoded-numbers`) applied to keep the *policy* simple even though the *budget numbers* live in
config. **S4 (implementation)** uses D14's separate three-verification bound (R-S4-5/R-S4-6): three failed *verification*
attempts (recipe validation after a completed invocation) before escalation, where infrastructure failures get "the ordinary
single retry without consuming that quota" and a control defect (sandbox violation, invalid recipe binding) "escalates
immediately without consuming verification quota" — a three-way split Mastra's binary retryable/`MastraNonRetryableError`
distinction does not make. Budgets are two-dimensional and enforced two ways: `runner/budgets.py:check_before_invocation`
sums settled `tokens`/`wall_clock_seconds` across a run's whole ancestor family (`_descendant_ids`/`_root_id`, mirroring
Mastra's parent/child run relationship but walked explicitly rather than inherited context) against `tiers.yaml`'s
per-stage-and-tier budget (`run_ledger.budget`, `run_ledger.py:281-291`), *plus* a second cumulative check unique to S4:
every `implementation` `stage_run` the ticket has ever opened against a **per-ticket** budget
(`implementation_per_ticket_budget`, `run_ledger.py:294-296`) — because S4's budget spans the whole multi-task
implementation effort, not one invocation's descendants. Wall clock is enforced *live* by `launcher.launch`'s
`subprocess.communicate(timeout=wall_clock_seconds)` (`runner/launcher.py:338-344`) — a hard process kill, not a cooperative
`AbortController.signal` Mastra steps must check (`step.ts:59` `abortSignal`). `budgets.abort` (`budgets.py:114-143`) finishes
the run `aborted_budget`, escalates the ticket, and opens one `escalation` item — never a hidden retry.

**Resumed-run determinism.** Answered directly above: Mastra achieves it by replaying a frozen snapshot plus a `resumePath`
array that re-enters the exact graph coordinate the run suspended at (`execute()`'s `resume.resumePath`, consumed one
element at a time as the loop descends into nested `parallel`/`loop`/`foreach` entries, `workflows/default.ts:818-828`); we
achieve it by never needing to resume *inside* an invocation — R-I-2's fresh-invocation rule means "resume" only ever means
"start a brand-new attempt whose envelope is reconstructable from governed rows," so there is no analog to `resumePath` to
port, and no snapshot format to design.

**Minimum executor interface.** Today there is none — `state_table.TABLE`, `transitions.apply`
(`runner/transitions.py:22-45`, "the sole writer of `ticket.state`"), and `operations.advance` are one hardcoded path with
no abstraction boundary between "decide the next event" and "apply it." Mastra's answer to the equivalent question is
`ExecutionEngine`'s dozen override hooks (§1.7) sitting on top of a shared graph-walking loop the base class owns outright.
Section 3.1 below proposes naming (not yet implementing) the same seam for us.

**Schedules and the digest.** `runner/digest.py`'s `Schedule` (`:48-121`) is close kin to Mastra's `Scheduler`, converged
independently: `Schedule.occurrence(now)` computes "the most recent scheduled occurrence at or before now" from `{times,
weekdays, zone}` read out of `project.yaml`'s `digest` key (`08-configuration.md:51`, "Digest cadence... twice per working day...
from a launchd entry"), and `Schedule.slot_id(occurrence)` (`:113-121`) is a **deterministic idempotency key** —
`occurrence.strftime("%Y-%m-%dT%H:%M")` — functionally identical to Mastra's `sched_${schedule.id}_${schedule.nextFireAt}`
runId, arrived at for the same reason: "a retry within it [is] idempotent." The architectural difference is total: Mastra's
`Scheduler` is a live `setInterval` loop inside a long-running server process claiming fires via CAS across possibly many
concurrent instances; ours is invoked fresh by launchd/cron as `factory digest`, a new process every time, with *no* CAS
needed because "there is no daemon in Initial; outbox reconciliation runs before each command that may advance state"
(`08-configuration.md:110`) — a single-writer assumption Mastra's design explicitly does not get to make.

**Background tasks / durable agents.** No analog. Every agent invocation is one synchronous
`subprocess.Popen(...).communicate(timeout=...)` call (`runner/launcher.py:332-344`) — opaque until it exits, no
mid-invocation checkpoint, no suspend-from-inside-a-tool-call. By design, not omission: R-I-2's fresh-invocation rule and
D14's "no hidden repair loop" language rule out exactly what `createDurableAgent`/`createEventedAgent`/`createInngestAgent`
exist to provide (mid-turn checkpointing). Our "attempts" (D14, R-S4-5) are a whole fresh invocation; Mastra's durable agent
checkpoints at every tool call inside one turn.

**Batching / outbox.** `runner/digest.py:run()` is itself a batching operation — it gathers every currently-open
`queue_item` into one message per scheduled occurrence (`open_items`, `:139-155`), the coarsest possible form of Mastra's
`BatchPolicy` (one giant window, no `maxSize`/`coalesce`/`isImmediate`). `runner/outbox.py` (referenced from
`digest.py:209-220`, `operations.py:101`) provides idempotency-keyed, compare-and-set delivery for Slack/GitHub writes — the
same shape as Mastra's batching/ack-nack contract, for outbound writes rather than inbound event delivery.

---

## 3. Portable ideas

### 1. Name the executor seam behind `operations.advance` now, even with one implementation
**What it is.** A minimal Python `Protocol`/ABC that `transitions.apply` + `operations.advance` are typed against, mirroring
`ExecutionEngine`'s split between "the graph-walking policy" (ours: `_due_stage`, gate evaluation, transition lookup) and
platform-specific hooks a future durable executor would override (ours: how a stage run is dispatched, how its lease/timeout
is enforced, how a suspend point is opened).
**Why it matters.** D27 already commits to "a workflow engine may replace [the state table] behind the stage interface"
(also `milestones.md:85`) but names no seam today; `operations.advance` and `runner/stages/DRIVERS` are imported and called
directly by several modules, so the boundary is implicit, not enforced. Serves D27 and R-F-11 (the fence: "the transition
table + anti-goals in runner code, outside `factory/`, beyond any proposal") — naming the interface now makes the fence's own
shape an artifact reviewers can inspect, rather than something only discoverable by reading `operations.py` end to end.
**Rating.** `next milestone` — zero runtime behavior change, so it does not conflict with "prototype first, no hardening
now" (owner feedback), but it is not needed to get one ticket through the pilot dry run either.
**Where it lands.** PRD: new row under `docs/prd/03-stage-interface.md` (stage interface section), extending R-I-1's "the
runner imports the stage interface and nothing inside a stage" language to name the dispatch boundary explicitly. HLD:
extends `C2sg` (Ticket state machine and the fence) in `docs/design/hld/L2-control-plane.md`, specifically the already-drawn
`C2_orch` dashed node ("Later: a workflow engine may replace the state table behind the stage interface") — this would turn
that box from a label into a real component reference once written.
**Draft acceptance criteria.**
- A `StageDispatcher` protocol/ABC exists with exactly the methods `operations.advance` currently calls inline
  (`due_stage`, `dispatch(ticket, stage)`, `evaluate_gate(ticket)`), and `state_table.TABLE`/`transitions.apply` do not
  import it — the fence (R-F-11) stays outside any pluggable surface.
- `operations.advance` calls only through the protocol; a test asserts (via `ast` or an import-graph check, matching
  R-I-1's existing "runner import-graph tests") that no other module reaches `runner.stages.DRIVERS` directly except the
  one concrete implementation.
- must-reject: a second concrete implementation registered without satisfying every protocol method fails at
  construction/import time, not silently at first dispatch.
- Verification: script test (import-graph / protocol-conformance check), no new manifest or agent surface touched.
**Size.** S (< 1 day) — it is a refactor of an existing call path into a named interface, not new behavior.
**What to copy.** The *shape* of the split (policy loop owns "what event fires," hooks own "how a run is actually
dispatched/bounded") — not Mastra's dozen span/tracing hooks, which we have no use for; not `wrapDurableOperation`, which
exists only because Mastra has in-place step retry we deliberately do not have (R-I-2).

### 2. Typed resume-payload schema per `queue_item.kind` + action
**What it is.** A declared schema (could be as light as a per-`(kind, action)` dataclass/TypedDict, not necessarily
zod-equivalent) that `queue.act()`'s loosely-typed kwargs (`verdict`, `note`, `evidence`, `waiver`, `fields: dict`) are
validated against before dispatch, replacing the current per-action ad hoc checks scattered through `queue.py`'s ~470-line
`act()` function — the same role Mastra's `resumeSchema` plays for a step's `resume()` call.
**Why it matters.** FM-25 (stale approval reaching a decision the human never actually reviewed) and the general "prefer
rules to hard-coded numbers" owner stance both favor making the *shape* of a valid resume declarative and testable, rather
than embedded in `act()`'s control flow. New concern otherwise, no existing FM row cites it directly.
**Rating.** `next milestone` — `act()` already works and is exercised by fixtures; this is a maintainability/auditability
improvement, not something the one-ticket dry run needs.
**Where it lands.** PRD: extends `docs/prd/03-stage-interface.md` R-I-1 ("act on the queue" as an Initial operation) with a
new row on the *shape* of an action's arguments. HLD: extends `H2` (list view & queue) and `C1sg` in
`docs/design/hld/L2-control-plane.md` diagram 1a — no new component, a stricter contract on the existing `factory act` op.
**Draft acceptance criteria.**
- Every entry in `queue.ACTIONS` (`queue.py:48-58`) has a declared argument schema; `act()` validates against it before any
  side-effecting call (`transitions.apply`, `approvals.record_approval`, etc.).
- must-reject: calling `act()` with an action valid for the item's kind but missing a field that action's schema requires
  (e.g. `waiver` with no `policy_id`) is refused with a schema-named error, not an attribute error deep in a helper.
- A schema mismatch is refused before any row is written — the once-only resolution columns (`resolved_at` etc.) are never
  partially settled.
- Verification: script test enumerating every `(kind, action)` pair against its schema with valid/invalid fixtures.
**Size.** M (1–3 days) — touches every action branch in `queue.py`, but no new state.
**What to copy.** The *separation* of "which actions this kind accepts" (already ours, `ACTIONS`) from "what shape this
action's payload must have" (Mastra's `resumeSchema`, ours currently implicit). Do not copy zod itself or a runtime schema
library — a small Python-native validator matching AGENTS.md's "no niche tools" constraint is enough.

### 3. Explicit compare-and-set on `queue_item` resolution, not read-then-write
**What it is.** Change `_resolve`'s write (`queue.py:703-719`) to an `UPDATE queue_item SET resolved_at=... WHERE id=? AND
resolved_at IS NULL` with a rowcount check, rather than reading the row, deciding it is unresolved, and writing — mirroring
`updateWorkflowState`'s `expectedStatus` guard and `#claimResume`'s atomic `suspended → running` flip.
**Why it matters.** New concern, not yet an observed failure — but the failure mode it forecloses (two `factory act` calls
against the same open item resolving it twice, e.g. from two terminal sessions) is exactly what motivated Mastra's own fix
(issue #20443, cited in `workflow.ts:4701`). Serves P11 ("the human can intervene... not only at the gates") by making
double-intervention safe rather than merely unlikely.
**Rating.** `next milestone` — SQLite's single-writer WAL mode already serializes writes, so this is a defense against a
narrower race (two reads racing before either writes) than Mastra's distributed-worker scenario; not urgent for a
single-operator pilot dry run.
**Where it lands.** PRD: tightens R-I-1's "act on the queue" operation (`docs/prd/03-stage-interface.md`) with a
must-reject clause. No new HLD component — this is inside the existing `C1sg`/queue write path.
**Draft acceptance criteria.**
- `act()`'s resolution write is a single `UPDATE ... WHERE resolved_at IS NULL`; a `rowcount == 0` result raises
  `ActionRefused` naming the item as already resolved, without having performed any of the action's side effects first.
- must-reject: two concurrent `act()` calls against the same `item_id` (simulated with two connections in a test) result in
  exactly one write to `transitions.apply`/`approvals.record_approval`, never both.
- Verification: script test using two SQLite connections against the same WAL database.
**Size.** S (< 1 day).
**What to copy.** The CAS *pattern* (guard the write on the expected prior value, in the same statement that performs it),
not Mastra's generic `expectedStatus: T | T[]` union machinery — our items resolve exactly once, so a boolean `resolved_at
IS NULL` guard is sufficient.

### 4. An "immediate" class of queue-item kinds that bypasses the digest cadence
**What it is.** Borrowing `SubscribeBatchOptions.isImmediate` (`events/types.ts`, `BatchPolicy.onEnqueue`,
`batch-policy.ts:79-86`): let a small named set of `queue_item.kind`s (candidate: `escalation`) trigger an out-of-band Slack
post through the existing outbox immediately, rather than waiting for the next twice-daily `Schedule.occurrence`.
**Why it matters.** Directly serves FM-19 ("slow failure... a late escalation with a long history to read") — an escalation
is exactly the item kind where a 5-hour wait until the next digest slot compounds the failure mode the digest was designed
to reduce in the first place.
**Rating.** `next milestone` — during the pilot dry run a human is actively watching the one running ticket, so the twice
daily cadence is already adequate; worth having once the factory runs unattended between digest windows.
**Where it lands.** PRD: extends `docs/prd/08-configuration.md`'s "Digest cadence" paragraph with an immediate-kinds list,
and `docs/prd/02-3-ticket-states.md`'s escalated-state row implicitly (the escalation item already exists; only its
delivery timing changes). HLD: extends `C7sg`'s `C7_outbox` node in `docs/design/hld/L2-control-plane.md` diagram 1a —
"digest (AB): only ticket id, tier, item kind, age..." gains an immediate-dispatch path alongside the scheduled one; same
guard seat (`C5_seat`), same data-minimization rule.
**Draft acceptance criteria.**
- An `escalation` queue item's `open_item` call (`queue.open_item`, `queue.py:91-117`) triggers an outbox `digest` intent
  immediately, through the same `outbox.create_intent`/idempotency-key path `digest.run` already uses, carrying the same
  minimized field set the scheduled digest carries (no ticket text, code, or artefact content).
- The immediate post does not suppress or duplicate that item's appearance in the next scheduled digest occurrence — it is
  additive notice, not a replacement.
- must-reject: an immediate post for a kind not on the configured immediate-list is refused (fails a test asserting the
  digest module's own allowlist, not silently sent).
- Verification: script test on `queue.open_item` for an `escalation` kind asserting an outbox intent is created
  synchronously; manifest/config test on the immediate-kinds list living in `project.yaml`'s `digest` key.
**Size.** S–M (1–2 days).
**What to copy.** The `isImmediate` *concept* — a per-item-kind predicate that bypasses batching's own size/deadline gate.
Do not copy `BatchPolicy`'s general machinery (timers, buffer overflow, coalesce) — we are not building a live pubsub
subscriber, this is one extra `outbox.create_intent` call at the point an escalation item is opened.

### 5. Backpressure vocabulary for the parallel-ticket limit, named now for the Milestone-B raise
**What it is.** Adopt `queue | reject | fallback-sync`-shaped naming (`BackgroundTaskManagerConfig.backpressure`,
`background-tasks/types.ts:174-180`) for what happens when a ticket arrives at capacity, ahead of R-O-13 raising the
parallel-ticket limit past 1. R-I-10 already implements `queue` today (a ticket beyond the limit "waits at `intake`... as
capacity wait... not as a human wait"); naming the alternatives now gives R-O-13's graduation decision existing vocabulary.
**Why it matters.** New concern — D28 keeps the limit at 1 through Initial specifically so this question doesn't arise yet.
**Rating.** `later` — blocked on R-O-13's graduation gate; no dry-run or Milestone-AB value.
**Where it lands.** PRD: a note on `docs/prd/08-configuration.md`'s "Parallel tickets (D28)" paragraph for the future
R-O-13 row, not a new row now. HLD: `C3sg` (Run orchestration) in `L2-control-plane.md`, no new component.
**Draft acceptance criteria.** Deferred — sketch only: the three named modes documented against `capacity.wait`'s existing
`queue` behavior as the only Initial choice.
**Size.** S, once taken up. **What to copy.** The three-way naming only.

### 6. Live per-run progress, modeled on `WorkflowStreamEvent`/`watch`
**What it is.** A `factory show`-adjacent live channel (e.g. a tailable log the launcher writes progress lines to,
structured like Mastra's `workflow-step-progress`/`workflow-step-output` chunk shapes, `stream/types.ts:1016-1045`) so an
operator watching a long S4 invocation sees intermediate progress rather than only the final hand-back.
**Why it matters.** Supports FM-19 (catching "ungrounded agent keeps working" earlier) and P11 — but R-I-14's sandbox
boundary and R-I-17's tool-result-out-of-context rule mean this must be a governed, bounded projection, not a raw stream.
**Rating.** `later` — an observability investment "prototype first" defers; `control.status` (`control.py:137-188`)'s
elapsed-time/budget-remaining view is adequate for a single watched pilot ticket.
**Where it lands.** PRD: extends R-I-1's "get record/status" op (`docs/prd/03-stage-interface.md`). HLD: extends `C1sg`'s
`C1_ops` node.
**Draft acceptance criteria.** Sketch only: a progress line written under the run's `out/`/`results/` split (R-I-14), never
raw agent stdout, bounded like an R-I-17 tool-result excerpt.
**Size.** M, if taken up. **What to copy.** The *shape* of a bounded, typed progress event
(`{id, completedCount, totalCount, currentIndex, status}`) — not the pubsub transport, which would need its own governed
proxy under R-I-14 to avoid a new egress path out of the sandbox.

---

## 4. Questions for the owner

1. **Should an escalation item post to Slack immediately, ahead of the next scheduled digest?** Today every queue item,
   including an escalation, waits for the next twice-daily digest slot. Idea 3.4 above would make escalations an exception.
   Default if unanswered: keep the current uniform cadence — escalations wait like everything else, since only one ticket
   runs at a time during the dry run and an operator is already watching it.

2. **Is a second concurrent `factory act` call against the same open item a real risk during the dry run, or only a
   distributed-deployment concern we do not have yet?** This determines whether idea 3.3 (the compare-and-set resolution
   write) is worth doing before or after the dry run. Default if unanswered: after — treat it as a next-milestone hardening
   item, since the dry run has one operator and SQLite's WAL mode already serializes the underlying writes.

3. **Should the resume-payload-per-action work (idea 3.2) happen before or after the dry run's first send-back or
   escalation resolution actually exercises `queue.act()` on real data?** Writing the schema from the existing code's
   ad hoc checks now risks encoding an assumption the real ticket then contradicts. Default if unanswered: after — let the
   first real ticket's actual `act()` calls inform what the schema should require.

---

## 5. Do-not-port list

- **The full durable-agent three-tier model** (`createDurableAgent`/`createEventedAgent`/`createInngestAgent`,
  `explorations/durable-agent.md`). This exists to checkpoint a long agent *loop* mid-turn so it survives a process crash.
  R-I-2's fresh-invocation rule is the opposite design choice, made deliberately: every attempt starts clean from the
  governed record, so there is no mid-turn state to checkpoint and nothing to resume into. Porting this would require
  reversing R-I-2, not extending it. **Reason: violates constraint** (contradicts a settled requirement, not a gap).

- **`LeaseProvider`'s generic acquire/renew/transfer abstraction** (`events/pubsub.ts:160-219`). We already have a working
  lease mechanism (`run_ledger.py`'s `open_stage_run`/`heartbeat`/`expire_dead_runs`, tied to `process_identity` — host,
  pid, and process start time together, so a recycled pid is never mistaken for the original holder). Mastra's version
  solves multi-process, multi-host lease contention across a distributed deployment; D28 keeps us at one ticket, one
  process, one host through Initial. **Reason: hosting-only, duplicates ours** for the case we actually have.

- **`BatchPolicy`/`SubscribeBatchOptions`'s general machinery** (`events/event-emitter/batch-policy.ts`) as a reusable
  library. The one useful nugget (`isImmediate`) is idea 3.4 above, applied narrowly to the digest's escalation case. The
  rest — maxBufferSize/overflow-drop policy, timer-based deadline scheduling, the coalesce reference-identity contract —
  solves a live-pubsub-subscriber problem ("a file watcher fires 3–4 events/second") that a twice-daily cron digest with no
  daemon (`08-configuration.md:110`) does not have. **Reason: violates constraint** (no daemon) and would be
  hosting/scale-only work.

- **The Temporal adapter as a model to follow.** It is explicitly experimental and does not implement resume at all
  (§1.8) despite inheriting a `resume()` method that looks like it should work — a cautionary example of an incomplete
  `ExecutionEngine` implementation, not a pattern to copy. If a durable executor is ever evaluated per D27's bar
  ("adopted when the state table demonstrably fails"), Inngest's engine (§1.8) is the far more complete reference; Temporal
  is not. **Reason: does not solve our problem** (this packet found no evidence it is production-usable in Mastra itself).

- **Nested-workflow `__workflow_meta` propagation** (`{runId, path, foreachIndex, foreachOutput}` threaded through suspend
  payloads, `workflows/default.ts:654-663`). This solves addressing a specific suspended leaf inside nested parallel/foreach
  workflows. We have no nested-workflow or parallel-iteration concept — S4's task loop and fix rounds already use
  `parent_run_id` for the one kind of run-nesting we have (children counting against a parent's budget, `budgets.py:31-52`),
  and `ticket.blocked_on` is a single foreign key by construction. **Reason: duplicates ours** for the nesting we actually
  have, and solves nesting we don't.

- **Mastra's binary `MastraNonRetryableError`/`retryableErrors` predicate** as a replacement for our failure-kind
  taxonomy. Our `stage_run.outcome` + `failure_kind` split (infrastructure vs. verification vs. sandbox/control-defect,
  each with its own quota and resume rule — R-S4-5, R-S4-6) is already a finer classification than Mastra's own; adopting
  Mastra's shape would be a regression in causal precision, not an improvement. **Reason: duplicates ours, and ours is
  stricter.**
