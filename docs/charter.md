# Software Factory Charter

| | |
|---|---|
| Status | Draft v0.9 |
| Date | 2026-09-04 |
| Owner | Abhishek Thakur |
| Review cadence | After each research pass and after each pilot ticket |

## How to use this document

This charter is the citation root for everything built after it. A requirement, rubric, or pipeline stage enters the system only if it cites at least one principle (P-n) and at least one failure mode (FM-n) from this document. Constraints (C-n) may be cited in addition, never instead. If a requirement cannot cite a principle and a failure mode, it is either generic or unjustified, and it stays out.

The failure-mode catalogue is the living part. Every production incident, every wasted review, and every abandoned ticket that involves the factory becomes a new entry or a frequency update on an existing one.

Architecture and tool selection do not belong here. They belong to later documents that cite this one.

## 1. Problem statement

We want LLM agents to make changes to production services that customers depend on. Those services are brownfield: years of history, edge-case handling that nobody fully remembers, implicit conventions, and cross-service dependencies. A change that looks correct in a diff can take a service down.

The bottleneck is not the agent's ability to write code. It is the human's ability to steer it: to answer the right questions, to catch bad judgment in a plan, and to review output without reconstructing the agent's reasoning from scratch. Today that steering costs so much attention that engineers avoid the agent's questions, answer them half-heartedly, or cannot hold more than one ticket at a time.

The factory therefore has two jobs, and both are required:

1. Make each change safe for a high-stakes system.
2. Make the human's part of that process cheap enough that people keep using it.

### Scope

The factory's responsibility ends at pull-request merge. It opens the PR, tracks the GitHub Actions runs the PR triggers, and assembles the review packet. Rollout, flag ramps, and production verification happen after merge, by the engineer, outside the factory (D25). The plan still states how the change should be rolled out, because the reviewer needs to judge it, but the factory does not execute it.

### What this is

A collaborator. The human is a participant in every stage, not an approver waiting at the end. Every artefact a stage produces is written to be read and acted on by the human, and the factory's own reasoning is always on the record. Automation grows one step at a time, under P10, by adding a cheaper check for that step, never by removing the human from a stage wholesale (P11).

### What this is not

- Not a greenfield code generator.
- Not an MVP or proof-of-concept factory.
- Not a ticket-in, PR-out pipeline. Those exist, are easy to build, and are the thing we are explicitly not building.
- Not a dark factory. Every published account of removing the human from review ends in comprehension debt or an unverifiable claim.

## 2. Design principles

**P1. Human attention is the scarce resource.** Every stage is judged by how much attention it consumes and what that attention buys. A stage that spends attention without changing the outcome is a defect.

**P2. Rubrics are the product.** The pipeline is a delivery mechanism for explicit rubrics that encode engineering and product judgment. Where a rubric is missing, the agent will guess, and it will guess silently.

**P3. Front-load the effort.** Context gathering, requirements clarification, and spec creation receive the majority of agent time and the majority of human attention. Implementation is the cheap part.

**P4. The agent states what it does not know.** Every plan carries explicit assumptions, explicit unknowns, and explicit non-goals. An unstated assumption is a defect.

**P5. Not touching is the default.** Existing code, style, structure, and utilities are presumed correct until shown otherwise. Code that looks wrong is presumed load-bearing until its history says otherwise.

**P6. Nothing that fakes confidence.** No tests whose purpose is to raise a number. No comments that restate the code. No "handled" that means "swallowed."

**P7. Blind spots are declared.** Where the agent cannot see, it says so and hands that verification to a named human step. It never implies coverage it does not have.

**P8. Every requirement traces to a failure.** See "How to use this document." This is the mechanism that keeps the system specific to us.

**P9. Reviewable reasoning over reviewable diffs.** The unit of human review is the plan, the decisions, and the risk map. The diff is evidence, not the artifact.

**P10. Autonomy is bounded by verification.** The agent may do without a human only what can be checked cheaply and reliably without a human. No increase in what the agent does on its own is adopted unless a cheaper check for that step exists first. This principle governs every future change to D4.

**P11. Collaborator, not black box.** The factory works with the engineer, not instead of them. Every stage's output is written for the human to read and act on, the reasoning behind it is on the record, and the human can intervene at any stage, not only at the gates. A step becomes autonomous only under P10, one step at a time. A factory that takes a ticket and returns a pull request is the problem statement, not the goal.

## 3. Anti-goals

- **No autonomous merge or deploy.** A human approves every change into a production branch and every flag ramp.
- **No replacing human review.** The goal is to make review cheaper and better targeted, not to remove it. The human gates at S3 and S6 are structural. They are not configuration and cannot be switched off per ticket.
- **No throughput optimization.** Tickets per period, cost per ticket, and touchpoints per ticket are tracked as context and are never success measures or improvement objectives (C8). Neither is the share of pull requests attributed to agents.
- **No self-grading judge.** No LLM pass grades output produced in its own context. An advisory pass runs in a fresh context with no access to the authoring transcript.
- **No measure feeds performance review.** Every number in section 8 describes the factory, not a person. None of them is used to evaluate an individual.
- **No greenfield mode.** A problem that only matters for empty repositories is out of scope.
- **No generic product.** This is built for this environment, this team, and these failure modes.
- **No black box.** No stage runs whose output the human cannot read, whose reasoning is not on the record, or whose result cannot be replayed from the ticket record.

## 4. Failure-mode catalogue

Cost and frequency are computed, not estimated. Every revision after plan approval, every incident, every override of an agent judgment, and every abandoned ticket is tagged at the source with a failure-mode ID, and the two columns are filled from those tags (D21). FM-01 to FM-14, FM-20, and FM-21 come from our own experience with agents. FM-15 to FM-19 and FM-22 were added from the research record (section 9) and are hypothesised until the pilot observes them.

| ID | Stage | Symptom | Cost when it happens | Frequency |
|---|---|---|---|---|
| FM-01 | Planning | Abstraction introduced without justification, or a needed one skipped | Harder maintenance or duplication; rework in review | TBD |
| FM-02 | Planning | Load-bearing hack modified or removed because it looked wrong | Edge-case regression; production risk | TBD |
| FM-03 | Planning | Existing style, utilities, and patterns ignored; new patterns introduced alongside old | Inconsistency; review churn | TBD |
| FM-04 | Planning | Tech debt silently fixed inside a feature change, or never surfaced at all | Mixed-concern diffs that are hard to review, or debt accumulates | TBD |
| FM-05 | Planning | Scope creep; the agent extends the change beyond the ticket | Larger diff, longer review, larger blast radius | TBD |
| FM-06 | Requirements | Agent jumps from a large product requirement straight to implementation without checking completeness | Multiple revision cycles; the wrong thing built correctly | TBD |
| FM-07 | Requirements | Meaningful questions mixed with useless ones | Humans stop reading questions; the ones that would have simplified the spec go unanswered | TBD |
| FM-08 | Requirements | Product scenarios not surfaced: error paths, migration, backward compatibility, concurrency | Late discovery; rework | TBD |
| FM-09 | Cross-cutting | A human cannot hold parallel tickets because every switch back demands re-immersion; switches imposed from outside, into cognitively distant work, are the expensive kind | Resumption cost on every switch; the second ticket gets half-hearted answers | TBD |
| FM-10 | Review | Diff arrives without narrative; the reviewer reconstructs intent line by line | Review is slow and shallow; humans avoid it | TBD |
| FM-11 | Implementation | Filler tests that pass but do not exercise behaviour | False sense of safety | TBD |
| FM-12 | Implementation | Filler comments that restate the code | Noise; masks the absence of needed comments | TBD |
| FM-13 | Implementation | Missing comments where the code is not self-explanatory | The next reader, human or agent, misreads intent | TBD |
| FM-14 | Context gathering | Impacted services unknown at the start of the change | Change lands with an unknown blast radius; downstream breakage | TBD |
| FM-15 | Implementation | Contract drift: an input, output, or error contract of touched code changes without being declared | Later agents and humans build on the wrong assumption; the next change to the same code fails | TBD |
| FM-16 | Requirements, Planning | False rigor: a spec, plan, or question set that is structurally complete but semantically vague passes on appearance | The wrong thing built correctly, with a paper trail that says otherwise | TBD |
| FM-17 | Cross-cutting | Memory rot: a rubric line, instruction, or context index entry stops being true with no signal; or the owning engineer's understanding of a changed subsystem decays while tests stay green | Agent behaviour degrades and the model is blamed; the subsystem becomes illegible to its owner | TBD |
| FM-18 | Review | Agent-only review: an agent pass is treated as satisfying human review, or the human gate is implemented as a configurable default and switched off | Merge quality drops measurably; nobody holds the judgment | TBD |
| FM-19 | Implementation | Slow failure: an ungrounded or blocked agent keeps working, expanding context and cost, instead of failing early and escalating | Wasted budget; a late escalation with a long history to read | TBD |
| FM-20 | Implementation | Hallucinated dependency: the agent uses a package, API, function, or version that does not exist or does not behave as assumed | Build or runtime failure at best; a subtly wrong behaviour that passes review at worst | TBD |
| FM-21 | Cross-cutting | State loss: over a long task the agent forgets what it has done, repeats or skips steps, or contradicts its own earlier decision | Wasted budget; inconsistent change; deviations the self-report does not mention | TBD |
| FM-22 | Cross-cutting | Loop drift: the improvement loop, pointed at a cost, throughput, or touchpoint number, proposes locally reasonable changes that remove context, questions, or gates; each is merged on its own merits and the factory drifts back to a pipeline | FM-06, FM-07, FM-14, and FM-18 return with a paper trail that says every step was justified | TBD |

## 5. Stage map

For each stage: what the agent produces, what the human decides, and the exit criterion. Rubric contents and tooling are deliberately absent; they come later and cite this table.

Each stage is a separate agent invocation with its own tool allowlist (C1). A stage holds no state between invocations except what is written to the ticket record (C3).

| Stage | Agent produces | Human decides | Exit criterion |
|---|---|---|---|
| S0 Intake | Provisional complexity tier from the service tier and ticket type (D11); the type of scrutiny the ticket requests | Whether the ticket is eligible for the factory; tier override | Ticket assigned to the factory with a provisional tier |
| S1 Context gathering | Context brief: ticket, epic, linked docs, repo history of the touched area, impacted services, flags found in code, SLIs and live flag state as declared blind spots (C2); the index entries used and any found stale; the final tier from files and services touched and the unknown count | Nothing, unless the brief flags a blocker | Brief complete, unknowns explicitly listed, tier final |
| S2 Requirements clarification | Completeness assessment of acceptance criteria; ranked question set in the format of section 6 | Answers, or accepts defaults | Acceptance criteria pass the completeness rubric, including structural completeness on the universal core; every blocking question resolved |
| S3 Spec and plan | Approach, alternatives considered, non-goals, code to touch and code deliberately not touched with reasons, abstraction decisions, tech debt proposals as separate items, declared contracts of touched code, an ordered task list with dependencies, validation criteria for the change, test strategy, flag and rollout strategy for the engineer to execute after merge, risk map | Approve or redirect | Plan passes the planning rubric, including the size gate, and is approved |
| S4 Implementation | The change, within bounds (D14): three verification attempts per task, then escalation carrying the full failure history; a token and wall-clock budget per tier. A self-report of conformance to the plan, any deviations, and any contract change | Nothing, unless escalated to | Conformance check passes within budget |
| S5 Cleanup pass | Two tiers. Blocking: deterministic checks run first, tests, lint, types, contract diff against the plan, size gate. Advisory: an independent agent pass against the slop rubrics, tests, comments, style, scope, in a fresh context (C4), never run on a red build | Nothing | Blocking tier green; advisory findings attached to the ticket record as evidence |
| S6 Human review | Review packet (see section 6); diff as appendix | Approve or request changes | Approval of judgment, intent, and residual risk, with defect evidence supplied by S5 |
| S7 PR checks and merge | Status of every GitHub Actions run the PR triggered, read through the GitHub MCP server; a summary of any failure with the likely cause; the PR left open for the human | Merge, or send back | PR merged by the human with all required checks green. Rollout after merge is outside the factory (D25) |

The improvement pass is a stage over the factory repository, not over a ticket. It is specified in the PRD and bounded by C8.

## 6. Human interaction contract

This section is the human-friendly guarantee. Violations are defects in the factory, not in the human.

**Questions.** A question reaches a human only if both hold: the agent could not answer it from the available sources and says what it tried, and the answer changes the spec or the plan. Each question carries what it affects, the agent's reasoning, and between two and four options, as many as the question genuinely has. "None of these, tell me" is always available.

**Defaults.** For a routine question the agent marks a default, and accepting it takes one word. For a question that is both consequential and hard to reverse, the agent presents the options and does not pre-select one; those are the questions the human is there to decide. Every accepted default is recorded as a named assumption in the plan.

**Batching and ranking.** Questions are batched per ticket and ranked by how much the answer changes the spec. There is no fixed cap. The count scales with the ticket: a simple change may raise none and a complex feature may raise many. What is fixed is the gate above, and every question has to pass it.

**Delivery.** Questions arrive through a queue, never as an interrupt and never inside an editor session. A ticket waiting on an answer shows a visible blocked state, and the agent continues any work that does not depend on the answer. A digest of open questions goes to Slack on a cadence the engineer sets. Answering is its own mode of work, so a person can hold several tickets and answer in one sitting.

**Rounds.** Complex tickets produce follow-up questions. They arrive in rounds: the first round holds what blocks the spec, later rounds hold what the answers raised. Each follow-up names the answer that raised it and passes the same gate.

**Scrutiny.** Every ticket states, from S0, the type of scrutiny it requests: what the reviewer should look hardest at and what they may take on the evidence. The review packet repeats it.

**Assumption log.** Append-only. An assumption that stops holding is superseded by a new entry naming the old one. Nothing is edited in place.

**Review packet.** In this order: the checks that ran and their results; intent in two sentences; the scrutiny requested; decisions made and why; what was deliberately not touched and why; risk map naming the three places worth a reviewer's eyes; deviations from the plan, including any contract change; the assumption log; test summary stating what each test proves; blind spots handed to the human; diff.

**Attention budget.** Time a ticket waits on a human at S2, S3, and S6 is measured from the moment a question or packet enters the queue to the answer, and compared against tickets of the same tier, not against a fixed target. The signal we look for is attention that was spent without changing the outcome (P1).

**Reconstruction is a defect.** If a human has to reconstruct the agent's reasoning to make a decision, the packet failed.

## 7. Environment and constraints

| System | Role | Agent access |
|---|---|---|
| GitHub | Source of truth for services; PRs; Actions runs on the PR | MCP server |
| Confluence, team space | Architecture, runbooks, team process | MCP server |
| Confluence, user space | Personal notes and context | MCP server |
| Jira | Epics, tickets, feature tracking | MCP server |
| AWS | Runtime | MCP server |
| LaunchDarkly | Feature flags; the rollout mechanism, used by the engineer after merge | None for now. Out of scope (D25) |
| Slack | Cross-team communication; home of the question digest | MCP server |
| Grafana | SLIs, SLOs, traces of the brownfield services | None for now. Not an agent tool and not a destination for factory traces (C5) |
| OpenSearch | Logs of the brownfield services | None. Out of scope with the rest of production verification (D25) |

Agent runtimes available: Cursor SDK, Cursor CLI, Claude CLI. These are treated as interchangeable execution engines. Choosing one is a late decision and must not shape the design.

The pipeline runs on the engineer's machine for the initial version and may move to an EC2 host later.

### Constraints

- **C1. Tools attach per stage.** Every connected tool's schema costs context before the ticket is read. MCP servers are attached per stage and per tier, not all at once, which requires each stage to be its own invocation with its own allowlist.
- **C2. Production is out of view.** Logs, metrics, and flags of the brownfield services are not reachable by agents and the factory does not act on them. The factory's view ends at PR merge. Where a plan depends on a production fact, the agent declares it as a blind spot (P7) and the packet names it for the human.
- **C3. Memory is split.** Versioned files hold rubrics, agent instructions, skills, the catalogue, and decisions. A SQLite database holds run state: tickets, runs, questions, answers, metrics. A finding from run state enters the versioned files only through a change the engineer reviews. Every context index entry carries a last-verified date and a staleness rule.
- **C4. Judges are separated.** An advisory pass runs in a fresh context with no access to the authoring transcript, on a different model where the runtime offers one, and the ticket record says which.
- **C5. Everything an agent does is recorded.** Every invocation writes to the ticket record: ticket, stage, tier, inputs, tool calls, a reasoning summary, outputs, tokens, cost, wall-clock, and outcome. This record is the factory's own tracing of its agents. It lives in the factory's run state, it is not exported to Grafana or any external system, and it is not tracing of the brownfield services. It is the only source for section 8, for every escalation, and for every catalogue tag. Nothing is measured that is not recorded, and nothing runs without a ticket and a stage. Dashboards over this record are a requirement and are built by the factory.
- **C6. Factory as code.** Skills, agent definitions, rubrics, deterministic scripts, lint configurations, and their evals are versioned files (C3). Every skill and every agent definition ships with an eval. A change to either is adopted only when its eval passes, and the eval never runs on the model that authored the change. The initial version starts this once the first rubrics exist; the structure is fixed from the start so nothing has to move later. The versioned files are a git repository. Changes land as reviewed pull requests, and the adoption gate runs as a check on them.
- **C7. Stages are replaceable.** A stage communicates with the rest of the factory only through the ticket record, behind one interface: run a named stage for a ticket and return the record. The initial state table and the orchestration around it can be replaced by a durable workflow engine or a DAG orchestrator without changing a stage.
- **C8. Improvement is objective-bound and human-merged.** Scorers, the improvement pass, and benchmarks take the section 8 primary measures and the rubric lines as their objective. Cost, throughput, and touchpoints are visible to them only as context. Their output is a proposed change to the versioned files, landed only through a change the engineer reviews. The state table that enforces the gates is outside the manifest and outside their reach. A scorer contributes to a benchmark or a proposal only after its agreement with the engineer's grading has been recorded.


## 8. Success measures

Baseline is measured first, against the current way of working with agents, so every number below has a before. The initial version measures only what the factory can compute from its own records. Self-reported measures are one optional question at ticket close.

Primary:

- Revisions per ticket after plan approval, tagged by failure mode.
- Questions surfaced per ticket, by tier; the share shown with a default; the share where the default was accepted when shown.
- Minutes a ticket waited on the human at S2, S3, and S6, by tier.
- Share of generated tests kept after human review.
- Share of plans approved without redirect.
- Production incidents attributable to factory changes. Target is zero; every incident becomes a catalogue entry.
- Share of stage runs that pass on the first attempt, by stage and tier. This is the reliability measure the initial version is judged on (D28).

Secondary:

- Share of "deliberately not touched" items that turn out to be correct calls.
- Escalations per ticket from S4 after bounded attempts (FM-19).
- Index entries found stale per ticket (FM-17).
- Optional at ticket close, one question: tickets held in parallel and whether returning to this one cost effort (FM-09).

Context, tracked from the initial version, never a success measure (D28, D29):

- Tickets closed per window.
- Cost per ticket, by stage and tier.
- Non-structural touchpoints per ticket, by tier: questions, red checks, escalations. The S3 and S6 gates are excluded from the count.

Reporting rules:

- Every growth figure carries its time window. A count with no window is not reported.
- Measures are presented as an unranked panel, never as a single score.
- Context measures are reported in their own block, never in the primary panel, never ranked, and never as an improvement objective (C8).
- Excluded from every report: share of pull requests attributed to agents, estimated savings over human work, and any measure that cannot be computed from the record.
- Every measure can be sliced by factory version, the manifest hash in force when the run happened, so a change to the factory is compared before and after.
- No measure feeds an individual's evaluation.

## 9. Research record

Source-first, not topic-first. Each source was read against the catalogue and yielded three things: the pattern, the failure modes it addresses, and whether it transfers to an agent.

| Pass | Scope | Output | What it changed |
|---|---|---|---|
| 1 | 52 questions, 8 packets, roughly 190 sources, stage by stage | `docs/research/synthesis.md` | FM-09 wording; FM-15 to FM-18; S5 two tiers; S6 exit; question format; review packet order; success measure split |
| 2 | Four whole-factory accounts: Uber, Ona, Osmani, Warp | `docs/research/synthesis-factories.md` | P10; FM-19; C1, C3, C4; S4 bounds; reporting exclusions; D20 |
| 2a | One vendor article, read directly: Warp, "Closing the loop with self-improving cloud software factories" (Lloyd, 2026-08-27). Grade C, vendor documentation | `docs/research/inbox/warp-article-self-improving-factories.md` | P11 and the black-box anti-goal; FM-22; C8; C6 git path; section 8 context block and version slicing; D5 amended; D28 to D31; PRD v0.2 factory API, observer scoring, improvement pass, benchmarks. The cloud requirement was set aside (D9) |

Findings with measured evidence and denominators: change size against defect-finding; human review defect yield; agent-only review merge rates; contract drift as a predictor; interruption resumption. Everything else is practice documentation or single-source, and is marked as such in the synthesis files. Follow-up items are listed in section 6 of each synthesis file and are not blockers.

## 10. Decisions and open questions

### Decided

- **D1.** Human attention is the design constraint.
- **D2.** Rubrics before pipeline.
- **D3.** This charter is the citation root for all requirements.
- **D4.** No autonomous merge or deploy. Changes to this decision are governed by P10.
- **D5.** Agent runtime choice is deferred and must not shape the design. No bound in this document is expressed in runtime-specific units such as steps or turns. Runtime and model are manifest content per stage and tier (D31), and the choice for each stage is made from benchmark data once scorers are calibrated (C8).
- **D6.** Research is source-first, planning phase first.
- **D7.** Factory memory lives locally, split as in C3, with optional one-way sync of human-facing artefacts to the Confluence user space (D22).
- **D8.** Agents reach every external system through MCP servers, attached per stage and per tier (C1).
- **D9.** The pipeline runs on the engineer's machine first. EC2 hosting is a later option.
- **D10.** Sequence is charter, research, PRD, initial factory version, then pilot. Pilot selection waits for the initial version.
- **D11. Complexity tiers.** Three tiers: Light, Standard, Heavy. Provisional at S0 from the service tier and ticket type; final at S1 from files and services touched and the unknown count. The engineer can override at either point. In the initial version the tier drives the size gate threshold, the budgets, the tool allowlists, the length ceilings, and metric segmentation.
- **D12. Catalogue extended.** FM-15 to FM-19 adopted as hypothesised entries. Tool-schema context cost is a constraint (C1), not a failure mode.
- **D13. Back-pressure adopted** as P10.
- **D14. Implementation bounds.** Three verification attempts per task, then escalation carrying the full failure history. A token and wall-clock budget per tier is the runaway stop. No step counts.
- **D15. Question format.** Reasoning, two to four options, a marked default for routine questions, no pre-selected default for consequential and hard-to-reverse questions, "none of these" always available.
- **D16. Stage map.** S5 is two-tier with the deterministic tier first and the advisory tier never run on a red build. S6 approves judgment, intent, and residual risk. The plan is an ordered task list with declared dependencies, and validation criteria are written at S3.
- **D17. Delivery.** Queue only, visible blocked state, Slack digest on a cadence the engineer sets, no modal interrupts.
- **D18. Measures** are computed from factory records only, with the reporting rules in section 8.
- **D19. Memory split and judge separation** as in C3 and C4.
- **D20. Initial version scope.** Amended 2026-09-04. S0 to S4, with S4 automated through the primary runtime under the D14 bounds; the deterministic scripts of the S5 blocking tier on the branch diff (the project's own lint, types, and tests; dependency resolution; size gate; scope diff; contract diff); the S6 review packet with the diff appended, reviewed before anything is pushed; and, on approval, the pull request opened by script with the packet as its description. The initial version ends there. S7, the LLM advisory pass at S5, and everything after the pull request wait until the planning rubrics have survived real tickets.
- **D21. Evidence process.** Revisions, incidents, overrides, and abandoned tickets are tagged with a failure-mode ID at the source. Catalogue cost and frequency are computed from the tags.
- **D22. Confluence sync.** One-way, human-facing artefacts only: brief, plan, decisions, review packet. Deferred past the initial version.
- **D23. Observability is a core requirement** from the initial version, as C5. The record comes first; dashboards may follow.
- **D24. Tooling candidates live in the PRD inputs**, `docs/prd/inputs.md`, not here. Code graphs, DAG orchestrators, durable workflow engines, containers, and local trackers are adopted only when the adoption cites a constraint or a failure mode, and the initial version uses the simplest thing that satisfies C3 and C5.
- **D25. Scope ends at merge.** The factory opens the PR, tracks its GitHub Actions runs through the GitHub MCP server, and stops at merge. Rollout, flag ramps, and production verification are the engineer's, outside the factory, for now. LaunchDarkly, Grafana, and OpenSearch are not agent tools in this version.
- **D26. Factory as code with evals**, as C6. Skills, agents, rubrics, scripts, lints, and evals are versioned together, and no skill or agent changes without its eval.
- **D27. Extensible by design**, as C7. The state table is the first orchestrator, not the last; durable workflow engines and DAG orchestrators are the expected direction, adopted when the state table demonstrably fails (D24).
- **D28. Context measures and initial success.** Tickets closed per window, cost per ticket, and non-structural touchpoints per ticket are tracked from the initial version as context, never as success measures or improvement objectives. Reliability of the pipeline is the initial success criterion: one ticket at a time, then two or three in parallel once every stage passes on the first attempt often enough. The parallel limit is configuration in the PRD.
- **D29. Touchpoints defined.** What the factory literature calls automation percent is recorded as non-structural touchpoints per ticket by tier, with the S3 and S6 gates excluded from the count. It is not optimised in the initial version; more human involvement is the intent while skills, agents, rubrics, and feedback loops are built. Its direction flips later, per step, under P10.
- **D30. Closed-loop improvement adopted**, bounded by C8: scored runs, an improvement pass over the factory repository, and benchmarks, with proposals landing only through reviewed changes. FM-22 names the drift C8 bounds. Cloud hosting, which the source treats as essential, is not adopted (D9).
- **D31. Routing in the manifest.** Runtime and model are named per stage and tier in the manifest and chosen from benchmark data, so multi-model operation is code, not convention.
- **D32. Pilot eligibility.** One T2 service, written in Java, and `small_feature` tickets only, accepted at S0. Widening the list is the owner's decision after the first tickets. Closes Q9.

### Open

- **Q10. Budgets per tier.** The token and wall-clock budgets in D14 and the size gate threshold per tier. Recommendation: start the Standard size gate at 300 changed lines, from the Cisco and Google bands, and set budgets from the first three pilot tickets. Both are configuration in the PRD, not charter text.
- **Q11. Source of the service tier.** A hand-maintained list in the versioned files for pilot services, or an existing catalogue. Recommendation: hand-maintained for the pilot.
- **Q12. Digest cadence default.** Recommendation: twice a working day until the pilot says otherwise.

Closed in v0.3: Q2 became D21, Q3 became D11, Q8 became D22. Closed in v0.2: Q1, Q5, Q6, and Q7 became D7 to D10. Q4, a fixed question cap per stage, was withdrawn because question count has to scale with ticket complexity.

## Revision history

- **v0.9, 2026-09-04.** Consistency fixes from the PRD review. Stage map S1 no longer lists live SLIs and flags as products, matching C2. Section 6 review packet gains the assumption log after deviations. D11 names everything the tier drives in the initial version. D20 lists all seven blocking-tier scripts. No change to principles, catalogue, or constraints.
- **v0.8, 2026-09-04.** D20 amended on the owner's decision: S4 is automated from the initial version, the review precedes the pull request, and the initial version ends when the pull request is opened; S7 moves to Later. Stage map and D25 unchanged as the eventual scope.
- **v0.7, 2026-09-04.** Owner named. Q9 closed into D32 from the owner's answers after research packet R10. No change to principles, catalogue, stages, or constraints.
- **v0.6, 2026-09-04.** Absorbed the Warp closed-loop article. Added P11 collaborator, not black box, with a matching anti-goal and a "What this is" statement in section 1. Added FM-22 loop drift. Added C8 objective-bound, human-merged improvement; C6 now names the git repository and PR path. Section 8 gained a first-attempt reliability measure, a context block for tickets per window, cost per ticket, and non-structural touchpoints, and factory-version slicing; the exclusion list was rewritten. D5 amended; D28 to D31 added. The metrics disagreement is recorded as a decision: Warp's three are context, never objectives.
- **v0.5, 2026-09-04.** Scope fixed at PR merge with Actions tracking (S7 rewritten, D25). Grafana, LaunchDarkly, and OpenSearch removed from agent access. C2 generalised to production out of view. C5 made factory-internal. Added C6 factory as code with evals and C7 replaceable stages, with D26 and D27. D20 names the deterministic S5 scripts as MVP.
- **v0.4, 2026-09-04.** Added FM-20 hallucinated dependency and FM-21 state loss from own experience. Added C5 observability, D23, and D24. Opened `docs/prd/inputs.md` for tooling candidates.
- **v0.3, 2026-09-03.** Absorbed both research passes. Added P10, two anti-goals, FM-15 to FM-19, constraints C1 to C4, and D11 to D22. Reworded FM-09 from the measured interruption evidence. Rewrote the stage map for tiers, bounds, the two-tier S5, and the S6 exit. Rewrote the question format, delivery, and review packet order in section 6. Restricted section 8 to computed measures with reporting rules. Replaced the research agenda with a research record. Closed Q2, Q3, Q8. Opened Q9 to Q12. Note: the entry proposed as FM-20 in `synthesis-factories.md` enters here as FM-19, and the proposed FM-19 became C1.
- **v0.2, 2026-09-03.** Closed Q1, Q5, Q6, Q7 into D7 to D10. Withdrew Q4. Replaced the fixed question cap with the gate-plus-rounds rule and made the attention budget relative to ticket complexity. Environment access set to MCP servers.
- **v0.1, 2026-09-03.** First draft.
