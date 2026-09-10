# Mastra Comparison: what the factory can port

| | |
|---|---|
| Status | v0.1; owner answered section 6 on 2026-09-10 (all defaults; question 4 answered yes, escalations post at once, amending R-H-3); applied as PRD v0.21 and inputs v0.9 |
| Date | 2026-09-10 |
| Owner | Abhishek Thakur |
| Source | `/Users/abhishekthakur/Developer/mastra` at commit `64c1190de3` (2026-09-10) |
| Compared against | `docs/prd/prd.md` v0.20, `docs/design/milestones.md` v0.7, `docs/design/hld/` v0.5, `runner/` at `7bc61ee` |
| Raw reports | `docs/research/raw/mastra/` — seven packet reports (A1, A2, B, C, D, E, F) written by Sonnet 5 study agents from the brief in `00-brief.md`; every mechanism cited there carries a Mastra file path |

## 1. What Mastra is, and why it matters to us

Mastra is a TypeScript framework for agents and workflows, and it ships a product called **Mastra Software Factory** under `mastracode/`: a board-driven pipeline that takes GitHub issues and pull requests through triage, planning, execution and review with coding agents in sandboxes. That product is the closest thing to our factory we have read. The framework beneath it holds most of the building blocks our milestones name: a durable workflow engine with suspend and resume, agent adapters for Claude Code and Cursor, skills, evals and scorers, tracing, memory, sandboxes, Slack and GitHub integrations, and a studio.

The study asked one question per area: what does Mastra do, what do we already have, and what is worth carrying into the PRD as a granular requirement for a future milestone. The constraints were the owner's: prototype first, no third-party runtime dependency, no niche tools, Python runner on one Mac, and a factory that is a collaborator rather than a black box.

## 2. The headline

**Most of Mastra's surface is either already covered by our design or the deliberate opposite of it.** In seven places our version is stricter, and the study confirms those choices rather than questioning them (section 3). Eleven mechanisms would make the factory better and are small enough to specify now (section 4). Around twenty-five more are real but belong to Later milestones and are listed with their landing rows so they are not lost (section 5). A do-not-port list (section 7) records what looked tempting and why it stays out.

Nothing in the study argues for adopting Mastra itself. Its state model is a generic version of our fixed state table; its approval and outbox are weaker than ours; its "one fresh invocation per attempt" opposite, the durable agent with mid-turn checkpoints, would require reversing R-I-2.

## 3. Where our design is already stricter

These are places a reviewer might be tempted to "upgrade" toward Mastra. Each would be a regression.

| Ours | Mastra's | Why ours stays |
|---|---|---|
| Content-hashed canonical subjects and expiring quorum (`evidence_tuple`, `approval_record`, R-T-10) | Integer `expectedRevision` on the work item, `isHumanTransition` boolean | A hash commits to every field a decision depends on; a counter does not. (A1) |
| Failure taxonomy: `infrastructure_failure`, `sandbox_violation`, `refused`, `aborted_budget`, `aborted_human`, each with its own retry and resume rule (R-S4-5, R-S4-6, 2.3) | `failed` plus a `nonRetryable` flag; a flat `{attempts, delay}` retry | Cause routes the resume; a boolean cannot. (B, C) |
| Two-tier implementation bound: three verification attempts per plan item inside two fix rounds per ticket, token and wall-clock budgets, escalation on exhaustion (R-S4-5, R-S4-9, D14) | The shipped `goal` loop: one flat `maxRuns` (50), no wall clock, no human escalation branch | Mastra's own explorations concede LLM-judged completion "can hallucinate". (C) |
| Fresh invocation per attempt, envelope reconstructable from the record (R-I-2, R-I-15) | Snapshot plus `resumePath`, durable agents checkpointing every tool call | Ours trades mid-invocation resume for auditability; the durable agent requires idempotent tools Mastra itself warns it cannot guarantee. (B, C) |
| Transactional outbox with content-hash idempotency keys, compare-and-set push, crash-injection tests (R-T-11) | Webhook dedupe "best effort", in-memory Slack approval gate that does not survive a restart | Our two external writes are safety-relevant. (A2, F) |
| Tool results written as governed files, bounded excerpt in context (R-I-17) | Nothing equivalent for tool results; only a token limiter on model output | Ours never drops data and never floods context. (C) |
| Per-run sandbox, destroyed on exit (R-I-14) | Session-long sandbox with a terminal-cleanup coordinator and stop-versus-destroy races to guard | The problem their coordinator solves does not arise. (A2) |

Two independent convergences worth noting: our `score.human_grade`/`graded_by` calibration fields match Mastra's design field for field, and our digest `slot_id` is the same deterministic idempotency key their cron scheduler derives.

## 4. Candidates for the PRD now

Each row is one requirement the study rates as worth specifying before or during the next milestone. The raw report holds the full draft acceptance criteria, the must-reject clause, and what to copy versus re-derive. None needs a new HLD component; each extends a component that exists. "Dry run" means the agent rated it must-have before the pilot ticket; the owner decides in section 6.

| # | Idea | Rating | Lands in PRD | HLD | Size | Report |
|---|---|---|---|---|---|---|
| 1 | **Recorded, replayable Cursor SDK transcript.** Record the worker's real stdout document once per stage, keyed by envelope hash; replay it in stage tests with modes auto, update, replay, live. Today's adapter fixtures are hand-written approximations that never exercise real model output. | dry run | §7 `evals/` block, extends R-F-2 | F8 evals | M | D-6 |
| 2 | **Secret-shaped text redaction before any free-text write.** One regex-and-truncate pass on `reasoning_summary`, `tag.note`, `queue_item.note`, `check_result.summary`, applied in the record writer, not at display time. | dry run | §2.2 entities, near R-T-9 | R1 record | S | A1-2 |
| 3 | **Second runtime adapter (Claude Code) against R-I-13.** Proves the adapter contract generalises; Mastra's proof came from writing four. Shared fixture set run against both adapters. | dry run (agent) / after pilot (its own default) | none new; R-I-13 already specifies it | G1 from dashed to solid | L | C-3.1 |
| 4 | **Deterministic "what is stuck" health report.** Pure function over the record: expired leases, items past an age threshold, missing seats; named finding kinds with a suggested repair; thresholds in config. | next milestone | §6 observability, sibling of R-O-1 | C1 command | S | A1-1 |
| 5 | **Immediate post for an urgent queue-item class.** An `escalation` (and non-waivable `red_check`) creates an outbox digest intent at open time instead of waiting for the next slot; additive to the scheduled digest; same minimised fields. | next milestone | §5 extends R-H-3; §8 digest cadence | C7 outbox | S–M | B-4, F-1 |
| 6 | **Read-before-write guard on the implementation worktree.** Refuse a write to a file the current attempt has not read, or that changed on disk since; per attempt, cleared on each fresh invocation. | next milestone | §3, new row beside R-I-3/R-I-11 | G3 interior | S | E-2 |
| 7 | **Typed payload schema per queue action, and compare-and-set resolution.** Declare the argument shape for every `(kind, action)` pair and validate before any side effect; resolve an item with one `UPDATE … WHERE resolved_at IS NULL` and refuse on zero rows. | next milestone | §3 extends R-I-1 (act on the queue) | H2, C1 | M + S | B-2, B-3 |
| 8 | **Name the executor seam.** A `StageDispatcher` protocol with exactly the methods `advance` calls (`due_stage`, `dispatch`, `evaluate_gate`); the fence stays outside it; import-graph test. No behaviour change; turns the HLD's dashed "a workflow engine may replace the state table" box into a real boundary. | next milestone | §3 extends R-I-1 | C2 fence, C2_orch | S | B-1 |
| 9 | **Cache-read and cache-write token fields on `stage_run`.** Null when not reported, never estimated; price-table cost must not drop a reported cache field. | next milestone | §3 extends R-I-13; §2.2 `stage_run` | G1 | S | C-3.2 |
| 10 | **Seatbelt profile knowledge for the OS policy.** Copy the two gotchas (`-p` inline profile, blanket read allow before subpath allows) and the Mach-service allowlist into R-I-14's profile author's checklist and escape suite. | next milestone (AB, when the policy is built) | §3 R-I-14, no new row | G2 wall | S | E-1 |
| 11 | **Run-detail expansion and single-run export.** Expand any `tool_call` to its full recorded input and output on request; `factory show --run <id> --export` writes one self-contained JSON with every tool call, check result and artefact reference resolved. | next milestone | §6 extends R-O-4/R-O-5 | H2 view | M | F-6 a, b |

Smaller items rated next milestone that need no PRD row, only a code or text change: a per-failure-kind retry policy lookup in one module (A1-8), the sentence "a confirmed finding may never be resolved by recording an assumption" in the planning and review skills (A1-5), a two-cohort comparison helper extracted from the graduation clause with error counts reported beside the mean (D-3), an adapter output-shape drift check script (D-8), a lightweight observational hook facility as typed recipes on runner lifecycle events (C-3.5, M), and a declarative predicate grammar for the tiering and split rules (E-6, M, the owner's laxness rule favours waiting for a third rule).

## 5. Later: real, but not now

Listed with the PRD row each would extend so a future milestone can pick them up with the reasoning intact.

| Idea | Lands in | Report |
|---|---|---|
| Score row carries every grading step's prompt and result, a batch id, and an optional anchor to the graded run separate from the grader's own trace | §2.2 `score` (decide the shape before R-O-10 creates the table) | D-1, D-5, D-9 |
| Gate/scorer/threshold verdict `passed`/`scored`/`failed`, cost structurally excluded | R-O-12, R-F-8 | D-2 |
| Trajectory derived from `tool_call` rows with declarative expectations (forbidden sequences, ordering) | R-S4-7 grader extension point | D-4 |
| Per-model-call token breakdown | needs Cursor SDK capability check first | D-7 |
| Multi-select questions | §2.2 `question`, R-S2 | C-3.3 |
| Skill directory convention `references/`, `scripts/`, `assets/` | §7 `skills/` | C-3.6 |
| Self-recognising bot identity, reconciliation sweep, decision idempotency-key convention | R-S7 rows | A2-1, A2-3, A2-4 |
| OS isolation backend as a named enum with fail-closed refusal | R-I-14 | A2-5 |
| Live push status for a running ticket, bounded progress events | R-O-8, R-I-1 status | A2-6, B-6 |
| Prior-rejection feedback inline on the next approval | presentation, when a UI exists | A2-7 |
| Backpressure vocabulary `queue`/`reject`/`fallback-sync` for the parallel-ticket limit | §8 D28 note for R-O-13 | B-5 |
| Untrusted-checkout guard (skip repo instruction files from an unreviewed branch) | R-I-14, when an agent ever reads an external PR | A1-6 |
| Per-ticket "hands-off once accepted" autonomy flag | `ticket` table, new R-H row; owner question first | A1-7 |
| Explicit three-way state kind (waiting on human / agent working / closed) in the state table | `state_table.py` only | A1-3 |
| BM25 lexical search over prose the code graph does not index | R-S1-4 or R-S1-7 | E-3 |
| Escalating-compression retry for a size-capped agent output | R-S1-2 | E-4 |
| LLM relevance ranking of archaeology candidates without a vector store | R-S1-4 | E-5 |
| Factory-wide, multi-window cost aggregation | R-I-10, once parallel tickets exceed one | E-7 |
| Header-aware chunking for long-document excerpts | R-I-17 | E-8 |
| File-history command over `factory/` via git log | §7 F1 | F-2 |
| Age-based pruning of growth tables with an explicit allowlist | `limits.yaml`, R1; gated by R-O-13 | F-3 |
| Coalesced count for same-kind items in the digest | R-H-3 | F-5 |
| Full-text log search and latency percentiles on the report | R-O-8 | F-6 c, d |

## 6. Questions for the owner

Plain words, one default each. The answers decide which of section 4 enters the PRD and at what version.

1. **Record and replay the real Cursor SDK transcript for stage tests?** Every stage test today runs against a hand-written fake result. Default: yes, scoped to the worker's own stdout document keyed by the envelope hash, no new interception layer.
2. **Add the secret-shaped text redaction pass before the pilot?** Default: yes, it is small and closes the gap between "the one credential never enters the sandbox" and "nothing that looks like a credential is ever written".
3. **Build the Claude Code adapter before the pilot ticket, or after it?** Default: after, the configuration already names Cursor primary and the pilot exists to prove the skeleton first.
4. **Should an escalation or non-waivable red check reach Slack at once instead of the next 10:00 or 15:00 slot?** Default: keep the uniform cadence for the dry run; add the immediate class in the next milestone.
5. **A "what is stuck" health report before the dry run, or is `factory show` enough?** Default: next milestone; it is cheap but new surface.
6. **Read-before-write guard on the implementation worktree: implementation stage only, or any future stage with write access?** Default: implementation only; it is the sole writing stage.
7. **Typed action payloads and compare-and-set resolution on the queue: before or after the first real send-back exercises `factory act`?** Default: after, so the real ticket informs the schema.
8. **Decide the future score row's shape now (one prompt-and-result pair per grading step) so the table is created once?** Default: yes, written as text in the entities section, table still created with R-O-10.
9. **How should Later ideas enter the PRD?** Every requirement must cite a principle and a failure mode; several ideas above are "new" with no failure mode to cite. Options: add them as Later rows with the nearest citation, or hold them in `docs/prd/inputs.md` as candidates until a milestone adopts them. Default: hold in inputs, add a row only when a milestone takes it.
10. **Any of the "do not port" items you want reconsidered?** Section 7 lists them with the constraint each would break. Default: none.

## 7. Do not port

Each entry names the constraint or decision it would break.

- **Board definitions, custom boards, transition-policy hooks, a generic decision dispatcher.** We have one fixed pipeline behind the fence (R-F-11); a board framework is the flexibility the fence exists to foreclose. (A1)
- **Mid-invocation approval, steering, or resume in any form.** Per-tool-call approval gates, `suspend`/`resume` inside a running turn, forked subagents sharing the parent thread, session-scoped tool grants. R-I-2 and R-I-8 make the opposite choice on purpose. (C, F)
- **Durable agents with mid-turn checkpoints and blind crash re-drive.** Would reverse R-I-2; Mastra's own docs require idempotent tools. Our lease expiry classifies the run as an infrastructure failure and re-enters the single retry. (B, C)
- **Chat with the agent, in-channel Slack approval buttons, GitHub comment slash commands.** The list view is the only decision surface (D17, R-H-4); the human surface HLD draws these as "never" nodes. (A2, F)
- **General pub/sub event bus, lease provider, batching machinery.** One ticket, one process, no daemon (D28, §8). The outbox already covers the one place at-least-once delivery matters. (B, F)
- **RBAC for a web UI, multi-tenant hosting, Platform proxy, product telemetry.** No UI to protect; telemetry conflicts with R-H-12. (A2, F)
- **Observational Memory, semantic recall, vector stores, LSP client, code mode.** No conversational thread exists to compress; vector stores and a second code index are outside the tooling constraint; model-written code contradicts R-I-16 and R-I-18. (E)
- **LLM-judge guardrails as a blocking gate today.** R-F-8 forbids an uncalibrated grader from blocking. Right time is R-O-10. (F)
- **Token-tiered model selection.** R-I-4 forbids silent substitution. (E)
- **ACP as a protocol dependency, tool-provider catalogues, the Temporal adapter as a reference.** Third-party dependency beyond the named exceptions; nothing to filter; Temporal's adapter does not implement resume. (B, C)
- **Mastra's retry taxonomy or integer revisions.** Both weaker than ours (section 3).

## 8. Method

Seven Sonnet 5 study agents, one per packet, each reading Mastra source and docs in depth and our PRD, HLD, milestones and runner for the same ground, writing to a fixed report format: mechanisms with file paths, what we have, portable ideas with rating, landing row, draft acceptance criteria including a must-reject clause, size, copy-versus-re-derive, owner questions, and a do-not-port list. One packet (workflow engine) was rerun after the first agent delegated to helpers and never compiled; the rerun did its own reading. No file in either repository was modified by the agents. This document is the synthesis; the raw reports are the evidence.
