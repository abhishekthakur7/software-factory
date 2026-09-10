# Packet D: Evals, scorers, datasets, observability/tracing, the LLM recorder

Mastra: `/Users/abhishekthakur/Developer/mastra`, commit 2026-09-10. Ours:
`/Users/abhishekthakur/Developer/soft-factory`, `7bc61ee`.

## 1. What Mastra does here

### 1.1 The scorer pipeline — `createScorer`

`packages/core/src/evals/base.ts` (2164 lines; types in `evals/types.ts`).
A scorer chains up to four steps, each a function or a "prompt object"
(`{description, outputSchema, judge?, createPrompt}`) run by an internal
judge agent:

```
createScorer({ id, description, judge?: { model, instructions, tools? }, type? })
  .preprocess(stepDef)     // optional
  .analyze(stepDef)        // optional
  .generateScore(stepDef)  // required, returns a number
  .generateReason(stepDef) // optional, returns text
```

Each step compiles to one workflow step (`toMastraWorkflow()`, line 1192);
`.run(input: ScorerRun)` (line 952) creates a `SCORER_RUN` span and one
`SCORER_STEP` child span per step, and for judge-backed steps accumulates a
`ScorerJudgeExecution`: `prompt`, `judgeModelId`, `attemptCount`,
`modelCallCount`, `durationMs`, `usage` (input/output/reasoning/cached
tokens), `cost {amount, unit, source}` on success, or `error`+`rawOutput`
on failure (lines 325-347). On completion it emits a `score` event
correlated to a target trace/span if storage is wired (lines 1119-1155).

`ScorerRun` (lines 174-238) carries `requestContextKeys` — an explicit
allow-list (omitted/`[]` = nothing persisted, `['*']` = everything,
specific keys = only those) so a run can be made reproducible without
leaking secrets by default — plus `scoreSource` (`'live'|'trace'|
'experiment'`), `targetScope` (`'span'|'trajectory'`), and
`targetTraceId`/`targetSpanId` to anchor the score.

### 1.2 The score row shape

`evals/types.ts:169-244` (`ScoreRowData`, `SaveScorePayload`). Beyond
`id`/`scorerId`/`entityId`/`score`:

- **Every step's prompt and result, separately**: `preprocessPrompt`/
  `preprocessStepResult`, `analyzePrompt`/`analyzeStepResult`,
  `generateScorePrompt`, `generateReasonPrompt`, `reason` — the audit
  trail a bare number can't reconstruct.
- **`scorer` as a denormalized snapshot** (id/name/description/type/
  hasJudge at grading time), not just a foreign key, so a later scorer
  edit doesn't retroactively change what an old row appears to be.
- **`source`** (`LIVE`/`TEST`) vs **`scoreSource`** (`live`/`trace`/
  `experiment`) — two axes: prod-vs-test, and which pipeline produced it.
- **`entityType`** — an open enum: `AGENT`, `WORKFLOW`, `TRAJECTORY`,
  `STEP`, `EXTERNAL` (caller-supplied), plus every `SpanType`.
- **`datasetId`/`datasetItemId`** — links a score to the dataset item it
  scored without re-running the target.
- **`batchId`** — groups every score one batch-scoring call produced,
  distinct from per-execution `runId`.
- **`id` is caller-settable** in `SaveScorePayload` specifically so a
  caller-driven experiment loop can derive a deterministic id from
  `(experiment, item, attempt, scorer)` and retry-converge on one row.

No "sampling rate" field on the row — sampling (`ScoringSamplingConfig =
{type:'none'}|{type:'ratio', rate}`, `evals/types.ts:14`) is a runtime
decision about whether a row gets written, not a value on it. No "prompt
version" field either — Mastra's answer is storing the exact prompt text
per step, not a version pointer.

### 1.3 `runEvals` — gates, scorers, thresholds, verdicts

`evals/run/index.ts` (1642 lines). Runs a target (`Agent`/`Workflow`) over
data items; per item, **gates** (must score 1.0; a throwing gate scores 0,
logged not fatal, line 554) run first, then **scorers** (bare, `{scorer,
threshold}`, or structured `AgentScorerConfig{agent?, trajectory?}` /
`WorkflowScorerConfig{workflow?, steps?, trajectory?}`). Result carries an
`EvalVerdict`: `'passed'` (all gates + thresholds pass), `'scored'` (gates
pass, a threshold misses), `'failed'` (a gate fails) — cost/throughput
never enter this computation, matching our `R-O-12` almost verbatim.

Multi-turn (`EvalTurn{input, gates?, scorers?}`) scores **each turn
against only that turn's own output** (`scoreTurn`, line 566), aggregated
by turn index across items (line 640) — a broken turn fails that turn
rather than averaging away.

Trajectory scorers receive a `Trajectory` (ordered `TrajectoryStep[]`,
`evals/types.ts:291-460`) instead of raw output.
`extractTrajectoryFromTrace` (line 958) rebuilds the span parent/child
tree from a trace's flat `SpanRecord[]`, skips noise span types
(`SCORER_RUN`, `MODEL_STEP`, `MODEL_CHUNK`, etc. — promoting a skipped
span's children so the subtree survives), and converts survivors to typed
steps (`tool_call`, `model_generation`, `workflow_step`, …) — **derived
from the trace**, never hand-assembled. `TrajectoryExpectation` (lines
587-631) then declares `ordering` (`strict`/`relaxed`/`unordered`),
`allowRepeatedSteps`, `maxSteps`/`maxTotalTokens`/`maxTotalDurationMs`,
`blacklistedTools`/`blacklistedSequences`, `maxRetriesPerTool`.

### 1.4 `scoreTraces` — batch scoring after the fact

`evals/scoreTraces/scoreTraces.ts`: `scoreTraces({scorerId, targets:
[{traceId, spanId?}]})` fires an internal workflow that re-reads recorded
traces and scores them, tagging every result with one shared `batchId`.
Scoring does not have to happen inline with execution — the mechanism an
"observer pass" over already-recorded runs would use.

### 1.5 Built-in scorers

`packages/evals/src/scorers/`: `llm/` (LLM-judge — faithfulness,
hallucination, answer-relevancy/similarity, bias, toxicity,
context-precision/recall/relevance, noise-sensitivity, summarization,
prompt-alignment, tool-call-accuracy, trajectory, multi-turn-judge,
rubric) and `code/` (deterministic — checks, completeness,
content-similarity, keyword-coverage, textual-difference, tone,
tool-call-accuracy, trajectory). Read in full:
`scorers/llm/faithfulness/index.ts` (99 lines) — extract claims → judge
each claim's support against context → score = supported/total, plus a
reasoning step reading the verdicts back; prompts live in a separate
`prompts.ts`. The `code/` scorers use the identical `createScorer` shape
for pure-function, non-LLM grading — the pipeline shape isn't LLM-specific.

### 1.6 Datasets and experiments

`packages/core/src/datasets/dataset.ts` (1139 lines),
`experiment/executor.ts`, `experiment/analytics/{aggregate,compare}.ts`.
A `Dataset` is versioned (`DatasetItem` full SCD-2 history via
`getItemHistory`, line 350; every experiment pins a `version`). An
`Experiment` runs a target over one dataset version, three modes:

1. **Mastra-owned loop** (`startExperiment`/`Async`) — iterate items,
   `executeTarget` (agent/workflow/scorer, `executor.ts:113`), run
   scorers (precedence experiment→item→dataset, `dataset.ts:848-850`),
   persist one `ExperimentResult` per `(experimentId, itemId, attempt)`.
2. **Caller-driven, target present** (`createExperiment` +
   `runExperimentItem`) — an external orchestrator fans out one call per
   item; Mastra still executes/scores, orchestrator owns retries.
   Idempotent on the natural key.
3. **Caller-driven, no target** (`createExperiment` +
   `submitExperimentResult`) — pure ingestion: caller executed/scored
   everything itself, upserts flat `{scorerId, score, reason, metadata}`
   rows (`dataset.ts:931-1041`) into the same score-row shape.

`executeTarget` for an agent (`executor.ts:225-383`) injects a fresh,
experiment-isolated memory thread per item (so concurrent items can't leak
context) and supports **item-level tool mocks** (`tool-mocks.ts`) that
fail an item deterministically the instant an undeclared/mismatched tool
call happens — a dataset-level golden-trajectory mechanism, not an
HTTP-level recorder (contrast §1.8).

**Comparing two runs** — `compareExperiments(mastra, {experimentIdA,
experimentIdB, thresholds?})` (`analytics/compare.ts`): loads both runs'
results+scores; warns (not fails) on dataset-version mismatch; per scorer
computes `ScorerStats` (`analytics/aggregate.ts:37-83`): `errorRate`/
`errorCount` (null scores — a scorer that threw, distinct from a real 0),
`passRate`/`passCount` (over a threshold, default 0.5), `avgScore` (mean
of non-null scores only), `totalItems`; computes `delta =
statsB.avgScore - statsA.avgScore` and flags regression via
`isRegression(delta, threshold, direction)` (lines 101-115) —
`'higher-is-better'`: regression when `delta < -threshold`;
`'lower-is-better'`: when `delta > threshold` — one function serves both
accuracy and latency scorers. Also returns a per-item table
(`ItemComparison{itemId, inBothExperiments, scoresA, scoresB}`).

### 1.7 Observability / tracing / metrics

`packages/core/src/observability/`, `observability/mastra/src/`.
`SpanType` enum (`observability/types/tracing.ts:35-123`): `AGENT_RUN`,
`WORKFLOW_RUN/STEP/CONDITIONAL/PARALLEL/LOOP/SLEEP/WAIT_EVENT`,
`MODEL_GENERATION/STEP/INFERENCE/CHUNK` (inference separated from
generation specifically to isolate pure model-provider latency from
processor/tool overhead), `TOOL_CALL/MCP_TOOL_CALL/CLIENT_TOOL_CALL/
PROVIDER_TOOL_CALL`, `SCORER_RUN/STEP`, `MEMORY_OPERATION`,
`WORKSPACE_ACTION`, RAG/`GRAPH_ACTION`/`MAPPING`/`SKILL_ACTION`/
`AGENT_SIGNAL`/`GENERIC`. Each has a typed attributes interface.

**Stored span shape** (`storage/domains/observability/tracing.ts:113-144`,
`SpanRecord`): `traceId`/`spanId`/`parentSpanId`, `name`, `spanType`,
`isEvent`, `startedAt`/`endedAt` (status is *derived* — no `endedAt` =
running, `error` present = error, else success; no separate status
column), `attributes`, `input`/`output`/`error`, `metadata`/`tags`,
`experimentId` (nullable, links a span to the experiment/eval run that
produced it).

**Token/cost on `MODEL_GENERATION`**: `usage: UsageStats` with a detailed
breakdown (`InputTokenDetails`: text/cacheRead/cacheWrite/
cacheWrite5m/1h/audio/image; `OutputTokenDetails`: text/reasoning/audio/
image), `costContext` (a provider-reported cost, used verbatim when
present), `responseModel`/`responseId` (the model that actually answered,
which can differ from requested).

**Auto-derived metrics** — `observability/mastra/src/metrics/
auto-extract.ts`: `emitDurationMetrics` reads span start/end, emits one
duration metric per span type tagged `status: error|ok`.
`emitTokenMetrics` reads a `MODEL_GENERATION` span's `usage` and, via a
provider+model pricing table (`metrics/pricing-model.ts`,
`pricing-data.jsonl`), emits one metric per token-usage dimension each
carrying an attached cost — total spend, spend by cache-hit vs
cache-write, spend by reasoning tokens are all **queries over spans**,
never hand-summed by the caller. Provider-reported cost is preferred over
the price-table estimate when present (lines 131-150) — the same
settled-vs-estimated distinction our `cost_basis` enum makes, at a finer
grain.

**Exporters** — `console`/`test`/`mastra-storage`/`mastra-platform`/
`cloud` plus separate packages per third-party backend (arize, arthur,
braintrust, datadog, deepeval, laminar, langfuse, langsmith, posthog,
sentry) and a generic `otel-exporter`/`otel-bridge`. Not relevant to port
literally (§5); the reusable idea is one internal event shape
(`ObservabilityEvent = TracingEvent|LogEvent|MetricEvent|ScoreEvent|
FeedbackEvent`, `observability/types/core.ts:161`), many pluggable sinks,
through one event bus with a uniform drop/retry contract.

**Score as one more observability signal** — `ExportedScore`
(`observability/types/scores.ts:60-124`): `scoreId`, `timestamp`,
optional `traceId`/`spanId` anchor (a score can exist with none),
`scoreTraceId` (the *scoring run's own* trace, separate from the target's
trace — for debugging the grader itself), `correlationContext`
(flattened entity/parent/root/session/experiment id bundle).

### 1.8 The LLM recorder — deterministic replay without the real API

`packages/_llm-recorder/src/llm-recorder.ts` (1352 lines),
`llm-contract.ts` (388 lines). `useLLMRecording(name)` wraps Vitest hooks
around `setupLLMRecording`, which uses MSW to intercept outbound `POST`s
to a fixed LLM-host list. Five modes resolved by explicit priority (lines
106-124): `--update-recordings`/`UPDATE_RECORDINGS=true` → force
re-record; `LLM_TEST_MODE=live` → real API, no recording; `=replay` →
strict, fails if no recording; default `auto` → replay if a file exists,
record if not (Vitest snapshot semantics).

**Matching is content-based, not order-based**: `hashRequest(url, body)`
is an MD5 of the URL plus deep-sorted, date-canonicalized body (lines
385-400), so tests run in any order/parallel and identical requests hit
the same recording. On a miss, `findRecording` (lines 622-725) falls back
to string-similarity fuzzy matching (threshold 0.6), preferring a
same-URL candidate, warning (or throwing under `exactMatch`) with a JSON
diff of what changed. `transformRequest` normalizes volatile fields
(timestamps, UUIDs) before both hashing and matching.

**Streaming is captured as ordered chunks with timing** (lines 533-603):
every SSE chunk plus inter-chunk delay recorded; replay can reproduce
timing (capped, default 10ms) — real streaming behavior, not one canned
response chunked artificially.

**Storage**: one human-readable JSON file per named set (`{meta:
{name, testFile, provider, model, createdAt}, recordings: []}`), binary
payloads as content-hash-named sidecar files (keeps JSON diffable).
Sensitive headers stripped before write (lines 344-354).

**Contract validation** (`llm-contract.ts`): `extractSchema(value)` turns
a JSON value into a structural `SchemaNode` (types/nesting, not values);
`validateLLMContract(actual, expected)` diffs two schemas ignoring known-
volatile paths (`id`, `usage.*`, `x-request-id`, …), reporting
missing/extra field or type-mismatch — for a periodic "does the live API
still match what we recorded" job, independent of any test's pass/fail.

### 1.9 `packages/core/src/relevance/`

Three small files: `RelevanceScoreProvider` scores memory-recall
candidate relevance, with an LLM-agent-backed implementation. Narrow scope
(memory recall, not general eval scoring); noted for completeness, weak
port candidate.

## 2. What we already have

| Mastra mechanism | Our equivalent | Difference |
|---|---|---|
| `createScorer` pipeline, judge model separation | Rubric lines (`runner/rubrics.py`) split `script`/`grader` halves; the grader half is stood in for by a human today via the bootstrap checklist (`runner/checklist.py`, `human_verdict` table) until R-F-8 calibration exists. The manifest already separates grader model from authoring model per stage/tier (`docs/design/hld/L2-factory-as-code.md` diagram 2) — we have the *contract*, not yet the pipeline. | R-F-3/R-O-10/R-O-11/R-F-8 (all Later) are where a `createScorer`-shaped harness lands. |
| `score` table | Defined in `docs/prd/02-2-entities.md:157-166` but one of five `LATER_TABLES` `runner/schema.py:925-927` withholds until R-O-10. | Narrower: one `grade`/`evidence` pair, no per-step prompt trail. `context` already mirrors `scoreSource`; `human_grade`/`graded_by` already mirrors Mastra's calibration pattern almost exactly (independent convergence, §3.11). |
| `runEvals` gates/scorers/thresholds | `runner/evals.py` (238 lines) is a **completeness walk over eval directories**: `expected_eval_dirs` derives the required `factory/evals/<kind>/<name>` set from what's on disk; `check`/`walk` assert `eval.yaml`, owner, cases, a real fixture, redaction review. Closer to R-F-2's fixture-completeness gate than to scoring. | No semantic scoring exists yet — R-O-10/R-F-8 are Later. `runEvals`'s verdict computation is a ready-made implementation of `R-O-12`'s objective rule (see §3.2). |
| `compareExperiments` | `runner/graduation.py`'s `baseline_revisions` clause (lines 352-401): factory mean vs. baseline mean revisions, pass iff factory ≤ baseline and ≥10 observed baseline rows. `runner/baseline.py` freezes the cohort with the same observed/approximate/unavailable status discipline. | We compare one cohort vs. one frozen baseline on one measure (R-O-13 scope), not Mastra's general two-experiment, all-scorer, per-item table. `R-F-12` (benchmark, Later) is where that generality would matter. |
| Dataset SCD-2 versioning | `baseline_measure` is one row per (baseline ticket, measure), frozen at import; `factory/evals/` fixtures version implicitly through the manifest hash (R-F-1/R-F-4). `runner/export.py` materializes a ticket as a directory (`EXPORT_TABLES`). | Ours is frozen-at-creation + hash-pinned/PR-reviewed, stricter on mutability by design (R-F-5: nothing writes `factory/` at runtime) — most of Mastra's dataset-mutation API has no analogue and shouldn't get one (§5). |
| Span model, auto-derived cost/duration metrics | `stage_run`/`tool_call` (`docs/prd/02-2-entities.md:36-61`) carry `tokens_in`/`tokens_out`/`cost`/`cost_basis`/`duration_ms` per run/call; `runner/run_ledger.py` is the single write path. Measures are hand-specified SQL in `runner/schema.py`'s `VIEWS`. | Coarser grain: one `stage_run` sums an entire agent run's model calls into one `tokens_in`/`cost`, not per-model-call rows with a token-type breakdown or pricing table. `tool_call.tokens` exists but isn't broken down; no per-model-call row at all (§3.7). |
| The LLM recorder | `factory/evals/adapters/cursor_sdk/fixtures/*.json` are hand-authored JSON matching the worker's one-document stdout contract (`runner/adapters/cursor_sdk_worker.py`), patched in at a fixture runtime (`cursor_sdk.py:322`). A `replayability` field already exists on the adapter's result (`best_effort`/blind-spot) but means "can this invocation be retried," not "was it recorded for replay." | Fixtures approximate the worker's final envelope; no real model text, tool-call sequence, or streaming is ever exercised — a stage test proves only "the adapter parses a JSON shape," not "the agent behaves as expected on real output" (§3.6, the focus question). |
| `extractTrajectoryFromTrace`/`TrajectoryExpectation` | Nothing. `deviation` rows (plan-vs-actual at S4 hand-back) are adjacent but human/runner-written prose, not a derived typed step sequence. | New ground, relevant once an S4 trajectory grader exists (§3.4). |
| One event shape, many exporters | `runner/schema.py`'s `VIEWS`, read only by the report generator (R-O-5); no exporter concept — SQLite read in-process, never streamed out. | By design (R-O-5 "text report on demand"; no third-party MCP/tool rule). Not a gap (§5). |

## 3. Portable ideas

**1. Persist every scoring step's prompt/result on the future `score` row.**
Instead of one `evidence` field, carry a prompt+result pair per pipeline
step plus a final `reason` (§1.2). Serves FM-16 (false rigor) and P11
(collaborator not black box); serves R-F-8 directly — agreement analysis
is far more useful when the exact extraction/scoring/reasoning text is
visible, not just the final grade.
Rating: **later** (`score` itself is Later); worth deciding now so a
future migration from a 1-field `evidence` to a 4-5-field shape doesn't
happen twice. Lands in: `docs/prd/02-2-entities.md`'s `score` block
(extends it, no new row); HLD: extends the `R1_later` placeholder in
`docs/design/hld/L2-record.md`.
AC: a multi-step grader's row carries a distinct prompt+result per step it
ran; single-step graders leave the rest null; `evidence` keeps its current
meaning (final-step support, never repurposed); must-reject: a `score`
insert missing a declared step's fields for a multi-step grader is
rejected by schema validation. Verified by: schema test; manifest test
that grader step-count matches eval fixtures.
Size: **S**. Copy: the field list. Re-derive: the workflow-step machinery
— our grader path is Inspect, whose `Score`/`TaskState` output maps into
this row shape at the result-recording boundary, not a reimplementation.

**2. Gate/scorer/threshold split with a three-valued verdict, cost
structurally excluded.** `runEvals`'s `passed`/`scored`/`failed` (§1.3) is
close to a ready-made implementation of R-O-12 ("cost … available as
context columns only," never overriding a verdict) — today that's prose
with no enforcing code.
Rating: **later** (grader authority to block is R-F-8-gated). Lands in:
`docs/prd/06-observability.md` R-O-12 / `docs/prd/07-factory-as-code.md`
R-F-8 grader-authority extension point — implementation note, no new row.
AC: all-gates-pass + all-thresholds-met → `passed`; gates pass but a
threshold misses → `scored`, non-blocking; must-reject: any gate scoring
below 1.0 yields `failed` regardless of every other input, including cost
or throughput. Verified by: unit tests per verdict; a fuzzed test that
cost/throughput never move the verdict for fixed grader scores.
Size: **S**. Copy: the three-state names and gates-then-thresholds
precedence. Re-derive: how a "gate" is declared — ours are rubric lines
with a `checklist` flag, not standalone scorer objects.

**3. Regression comparison as a reusable two-cohort function.**
`computeScorerStats` + `isRegression(delta, threshold, direction)` (§1.6)
— errors reported separately from a real 0, one function serving both
higher-is-better and lower-is-better measures via a direction flag.
Rating: **next milestone** for extracting what `baseline_revisions`
already does inline into a shared helper; **later** for wiring it into
R-F-12's benchmark harness. Lands in: `runner/graduation.py` refactor into
a new `runner/compare.py` (no PRD change — implementation detail R-F-12
should cite later); HLD: no new component, computation over existing
Record-domain views.
AC: given two value lists (with explicit nulls for unavailable), reports
count/error-count/mean of non-null values and, given threshold+direction,
whether the delta is a regression; `baseline_revisions`'s existing
pass/fail is unchanged after refactor; must-reject: a comparison with
fewer than the configured minimum comparable values on either side is
refused, not computed on a tiny sample. Verified by: unit tests on the
helper; existing graduation clause tests pass unchanged post-refactor.
Size: **S**. Copy: errors-excluded-from-mean-but-reported, the
direction-flag trick. Re-derive: where the two cohorts come from — ours
are view rows, not `Experiment` objects.

**4. Trajectory as a typed, derived-from-the-record step sequence with
declarative expectations.** `Trajectory`/`TrajectoryExpectation` (§1.3),
derived from the trace tree, not hand-assembled. New ground for us —
serves FM-02 (load-bearing hack) and FM-05 (scope creep) at S4: a grader
asserting "no `git push` before `git commit`" or "no forbidden tool
sequence" needs exactly this, derived from `tool_call` rows, never
agent-self-reported (which R-T-9/guard discipline would reject as
unverifiable).
Rating: **later** (no consumer before the R-F-3/grader-authority
extension point exists). Lands in: R-S4-7's Later rubric grader-authority
extension point — not a new row; HLD: a small derivation function inside
whichever component runs S4 graders, reading `stage_run`+`tool_call`.
AC: given a ticket's S4 `stage_run`/`tool_call` rows, produces an ordered
step list (tool name, args digest, result digest — digest-only, matching
`tool_call`'s existing discipline); a forbidden-sequence expectation flags
any matching contiguous run, ordered or unordered; must-reject: an
incomplete underlying `tool_call` record (a guard-denied or unrecorded
call) fails the check as a blind spot, never passes silently. Verified
by: script test per ordering mode; must-reject test on an incomplete
record.
Size: **M**. Copy: the discriminated-union step shape, ordering-mode
vocabulary. Re-derive: the source tree — ours comes from `tool_call` rows,
not an observability span store (we have none).

**5. Score as a first-class signal with an optional target anchor,
distinct from the scoring run's own trace.** `ExportedScore`'s `traceId`/
`spanId` optionality plus a separate `scoreTraceId` for the *grading
call's own* trace (§1.7). Serves R-O-10/R-O-11 — a score needs to point
at the graded `stage_run` and, separately, record the grading call's own
cost/duration.
Rating: **later** — folds into idea 1 (same table, same milestone); a
distinct design point (anchor optionality) worth deciding together.
Size: **S** (folds into 1's schema decision).

**6. A recorded, replayable Cursor SDK session for deterministic stage
tests — the focus question.** Capture the real worker stdout transcript
(and any sub-process HTTP calls) once against the live SDK, store it
content-hash-keyed and human-readable, replay deterministically — the
mechanism §1.8 implements for Mastra's own suite. Today's fixtures
(`factory/evals/adapters/cursor_sdk/fixtures/*.json`) are hand-authored
approximations of the worker's *final* document — no real prompt
assembly, model text, or tool-call sequence is ever exercised, so a stage
test proves only "the adapter parses a JSON shape," never "the agent
behaves as expected on real output" or "the SDK's output shape hasn't
drifted." Serves C4/C6 (eval harness runs on recorded, not live, calls)
and FM-16 (a test that always passes because its fixture was hand-picked
is exactly what real-traffic replay prevents).
Rating: **must-have for dry run**, narrowly scoped — record/replay at the
worker-process boundary we already have, not a port of MSW/HTTP
interception. The dry run's one real pilot ticket exercises every stage
live at least once; every subsequent regression test for that stage
should replay that transcript instead of a hand-picked fake result — this
is cheaper CI, not slower, and directly protects the one real run the dry
run exists to validate.
Lands in: `docs/prd/07-factory-as-code.md`'s `evals/` block (extends the
existing `factory/evals/adapters/cursor_sdk/` directory — R-F-2 already
requires a fixture; this improves how one is produced, no new row); HLD:
extends `F8_evals` in `docs/design/hld/L2-factory-as-code.md`, no new
component.
AC: recording writes one content-hash-keyed JSON file under
`factory/evals/adapters/cursor_sdk/recordings/` with the worker's full
stdout document and any underlying model-provider exchanges, credentials
stripped; replaying the same envelope hash with no mode override makes no
real network call and reproduces the same `stage_run` outcome
byte-for-byte; a prompt-assembly change that alters the envelope hash
misses the existing recording and is reported as "real call required,"
never silently matched; must-reject: replay of a recording whose stored
content fails an integrity check (hash mismatch, missing binary sidecar)
is refused, never served as a match. Verified by: script test recording
then replaying a synthetic invocation and asserting byte-identical output;
must-reject test on a corrupted/missing recording.
Size: **M** (worker-transcript capture + envelope-hash-keyed lookup/replay
in `runner/adapters/cursor_sdk.py`; simpler than HTTP interception since
the worker's entire output is already one stdout JSON document,
`cursor_sdk_worker.py`'s explicit contract).
Copy literally: the mode vocabulary and priority order (auto/update/
replay/live); content-hash lookup (keyed off the existing envelope hash,
not a new scheme); human-readable JSON + binary sidecars; credential
stripping before write. Re-derive: capture mechanics — Mastra intercepts
HTTP inside one Node process; our worker is a sandboxed child process
whose only channel out is one stdout document, so capture means recording
that document, not intercepting HTTP from the trusted parent.

**7. Per-model-call token/cost breakdown, derivable rather than
hand-summed.** Token usage by type (cache read/write, reasoning, audio,
image) at the model-call grain, cost from a provider+model pricing table
when not reported directly (§1.7). Our `Context: cost per ticket` measure
already has the right provenance model (`provider_settled`/
`runtime_estimate`/`price_table_estimate`/`unavailable`); missing is
grain — one `stage_run` sums an entire agent turn's calls, hiding e.g. "the
model burned tokens retrying a failed tool call" inside one total.
Rating: **later** — depends on unverified Cursor SDK per-call reporting;
the PRD's existing "estimates never fill missing … per-tool-call usage"
clause (`docs/prd/02-2-entities.md:49`) already refuses to synthesize what
isn't reported. Lands in: would extend `stage_run` or a new child table
(new row, new grain) — AC deferred pending capability verification; see
question 3.
Size: **L**. Copy: the token-type taxonomy, if the runtime exposes it.
Re-derive: everything else, pending SDK verification.

**8. Contract validation for the Cursor SDK's output shape.**
`validateLLMContract`'s structural (not value) schema diff (§1.8), run
periodically to catch upstream drift. The worker's "print null rather
than guess" discipline already shows awareness of this risk per-run; no
systematic check exists that the output *shape* hasn't silently changed
between SDK versions.
Rating: **next milestone** — small, independent of idea 6 though most
useful paired with it. Lands in: a new script under
`factory/scripts/tools/` (e.g. `adapter_contract_check`) — falls under
the existing adapter eval-directory requirement, no new row.
AC: given a recorded and a fresh output document for the same envelope,
reports any field present in one but not the other and any type change,
ignoring known-volatile fields (request id, duration, cost, timestamps);
must-reject: a fresh output missing a field the parent adapter reads
unconditionally (`status`, `tool_calls`) is reported as breaking drift,
never ignored. Verified by: script test with synthetic changed/unchanged
fixture pairs.
Size: **S**. Copy: structural diff + default-ignore-list approach.
Re-derive: the schema source — the worker's one documented JSON contract,
not an arbitrary provider API.

**9. Batch scoring over already-recorded runs.** `scoreTraces` decouples
scoring from execution (§1.4) — matches R-O-10's own description ("scored
against that stage's rubric lines," sample rate/cadence as config,
implying a batch job over the ledger).
Rating: **later** (R-O-10 itself is Later); confirms the Later design's
batch shape is already right — no change needed. Folds a `batch_id`
column into idea 1's table shape.
Size: **S**.

**10. Caller-driven, target-less experiment ingestion.** Mode 3 of §1.6 —
a pattern where the framework never executes anything, only stores
externally-computed scores idempotently. Matches our architecture closely:
`graduation.py`'s `evaluate()` already reads the record and writes one
summary artefact + `utility_run`; `baseline.py`'s `import_baseline` is our
own target-less ingestion path (baseline measures come from external
Jira/PR history, never an agent run).
Rating: **duplicates ours** — listed to answer the "how do they compare
two runs" focus question directly: we already have the ingestion half of
this pattern and don't need the execution-orchestration half.

**11. `human_grade`/`graded_by` calibration fields.** `docs/prd/
02-2-entities.md:165` already specifies these on `score`, matching
Mastra's pattern (§1.2) field-for-field.
Rating: **duplicates ours** — stated explicitly as validation: our
independently-designed calibration shape already matches this state of
the art; nothing to import.

## 4. Questions for the owner

1. **Should we record a replayable transcript of the Cursor SDK the first
   time each stage runs it for real, so later regression tests replay
   that transcript instead of calling the real service again or relying
   on a hand-written fake result?** The main recommendation of this
   packet (idea 6). Default: yes, scoped to the worker's own stdout
   document keyed off the existing envelope hash — no new interception
   layer, no change to how the sandboxed worker talks to the outside
   world.

2. **When the grading pipeline exists later, should a grade record show
   its full working — the exact text it extracted, the exact question it
   asked the judge model, and the reasoning it got back — rather than
   just a pass/fail and one evidence note?** Changes the future `score`
   table's shape (idea 1), cheaper to decide now than to migrate later.
   Default: yes, one field per grading step, length-capped the same way
   `reasoning_summary` already is.

3. **Do we want to break down a stage's token usage and cost by
   individual model call, or is one summed total per stage run enough for
   the pilot?** Depends on what the Cursor SDK actually reports per call,
   which nobody has verified. Default: keep the current one-total-per-run
   shape for the dry run; revisit only if a real measure needs finer
   grain and the SDK can supply it.

4. **Should the graduation report's baseline comparison also show how
   many values on each side were errors or unavailable, next to the
   pass/fail mean it already computes?** Small, cheap, makes an
   "unavailable baseline" refusal easier to read at a glance. Default:
   yes, add it the next time `graduation.py` is touched — report field
   only, no schema change.

## 5. Do-not-port list

- **The MSW/HTTP-interception mechanism as code.** Python, not Node; the
  shape (content-hash matching, mode vocabulary, human-readable storage)
  is portable (idea 6), the library and its interception approach are not.
- **The full dataset CRUD/versioning API** (re-editable datasets with
  per-item SCD-2 history). Our fixtures and cohorts are deliberately
  frozen/hash-pinned by design (R-F-5; `baseline.py`'s freeze-on-import) —
  a general mutable-dataset API works against that constraint.
- **Multi-tenant scoping** (`organizationId`/`projectId` everywhere).
  Single-tenant pilot; hosting-only generality outside the prototype-first
  constraint.
- **The third-party exporter ecosystem** (arize, arthur, braintrust,
  datadog, deepeval, laminar, langfuse, langsmith, posthog, sentry, the
  generic OTel exporter/bridge). Violates the enterprise rule directly:
  no niche third-party tools, no third-party MCP servers. Our
  in-process report generator reading SQL views (R-O-5) is the right
  shape; we have no exporter destination.
- **Mastra's own anonymous product-usage telemetry** (posthog-backed
  `telemetry/usage-telemetry.ts`). Not applicable — measures Mastra's own
  product adoption, unrelated to measuring factory output.
- **The benchmark manifest-configuration matrix as built.** We already
  have an equivalent row planned (R-F-12, Later) with the same shape —
  nothing to import, confirms the design like ideas 10/11.
- **`relevance-score-provider`.** Narrow, memory-recall-specific scope
  with no current analogue; not worth tracking unless a context-index
  relevance grader is actually proposed.
