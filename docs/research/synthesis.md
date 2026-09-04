# Research Synthesis

| | |
|---|---|
| Status | v0.1 |
| Date | 2026-09-03 |
| Inputs | `docs/research/questions.md` v0.1 (52 questions); `docs/research/raw/R1` to `R8` |
| Cites | `docs/charter.md` v0.2 |
| Extended by | `docs/research/synthesis-factories.md` v0.1, packet R9 (four whole-factory accounts: Uber, Ona, Osmani, Warp); adds amendments A to H to section 4 below |

## Coverage

52 questions across eight packets. 45 answered fully, 5 partially, 2 are genuine gaps in the published record (RQ-S4-5 deviation logging for agents, RQ-S5-4 scope checking as a named practice). Roughly 190 sources consulted; each raw packet lists its own with source type. Four primary posts were blocked on fetch (Netflix, Etsy, Gusto, Pinterest returned 403) and one packet, R3, exhausted the shared search budget for its last two questions. Both are flagged inline in the raw files and listed in section 6.

Evidence grades used throughout:

- **A** — peer-reviewed or company-published with measured figures and denominators.
- **B** — primary practice documentation or practitioner canon, qualitative.
- **C** — secondary, single-source, snippet-only, or analogy from another domain.

Every rubric line below is a proposal derived from evidence, not a decision. The charter (section 10) is where decisions are recorded.

---

## 1. What changes the charter

Ten findings the charter should absorb. Each names the evidence, the grade, and the packet.

**1. The attention constraint is externally confirmed.** Cognition, building Devin, writes that scaling agent parallelism bottlenecks "the management, planning, and reviewing." Anthropic's multi-agent research system is recommended for breadth-first independent strands and explicitly not for "tightly interdependent tasks such as coding" (R8, A-). P1 stands. The corollary is architectural: never present N agent outputs to a human as N review events. A synthesis layer merges, deduplicates, and risk-ranks first.

**2. Human review catches few defects, and agent-only review is measurably worse.** At Microsoft, 14% of 570 manually classified review comments found defects; at Google, 2 of 44 engineers said their most recent review found a bug (R6, A). In 2026 mining studies, pull requests reviewed only by AI agents merged at 45.20% against 68.37% for human-only review, and 60.2% of closed agent-only PRs had actionable-signal ratios of 0 to 30% (R6, A). Consequence for the stage map: S6 certifies judgment and intent. Defect-freedom is the job of S4 and S5. The S5 agent pass is evidence submitted to the human, never a substitute for the human.

**3. Change size is the strongest measured lever in the corpus.** Cisco/SmartBear: defect density collapses above 200 to 400 lines and no review over 250 lines exceeded 37 defects per kLOC. Google: median change is 24 lines; latency under one hour for small changes and about five hours for very large ones, across 9 million changes. Microsoft: comment usefulness falls as file count rises, across 1.5 million comments (R3, A). This is the basis for a hard size gate before S6.

**4. Question triage has a research base and a convergent rule.** Five independent preprints document the recognition-action gap: models recognise ambiguity when asked to judge it but default to answering. Ranking candidate questions by expected value of information beats fixed thresholds. Kiro operationalises this by measuring semantic entropy across independent formalisations of each requirement, and every question it asks is two-option with a suggested default (R2, A-). Separately, three unrelated domains converge on the same escalation rule: Shape Up, Amazon's PR/FAQ, and Apache lazy consensus all escalate only when a decision is consequential and hard to reverse, and otherwise decide locally and disclose (R2, A-). This is the principled replacement for the withdrawn question cap.

**5. Completeness can be checked mechanically, by exactly one known mechanism.** EARS clause syntax plus formalisation into SMT-lib with a solver and a semantic-entropy check is the only machine-checkable completeness test found (R2, A-). INVEST and Given/When/Then remain human discipline. Every spec-driven tool's users report the same failure: "a vague spec with the appearance of rigor is worse than no spec at all" (R2, B). The S2 to S3 gate needs a formalisation pass so that form cannot pass for substance.

**6. Rubrics have operating requirements, and the field has none to lend.** No company publishes a scored design-review rubric; only role and venue structure exist (R3, B). Anthropic's guidance: single-dimension judges rather than one omnibus judge, calibration against human graders, an explicit "insufficient information" output. Protocol choice alone shifts reported human-judge agreement from 0.551 to 0.899 on identical verdicts, so a calibration claim without a disclosed protocol means nothing (R8, A). The authoring model must not grade its own output, and authority framing swings judge accuracy by more than 60 points independent of correctness (R5, A). Atomic, well-designed rubric items reach Cohen's κ of 0.98 across reruns, so the ceiling is high when the design is right.

**7. Contract drift, not complexity, predicts downstream agent failure.** Cyclomatic and cognitive complexity were not significant predictors of whether a later agent could extend agent-written code. Undeclared divergence in input or error contracts was, with an odds ratio of 1.83. Resolve rates drop by up to 13.1 points when agents extend agent code rather than human code (R5, A). S3 must declare the contracts of touched code, and S5 must diff contracts against the plan. Complexity metrics are not a maintainability proxy.

**8. FM-09 needs a wording correction.** The popular "23 minutes to refocus" figure has no peer-reviewed source. What is measured: only 10% of interrupted programmers resume coding within a minute and about 30% take longer than 30 minutes, across 9,899 IDE sessions; interrupted work finishes faster at a measured cost in stress, frustration, and effort; externally imposed switches to cognitively distant tasks are the expensive kind (R8, A). Resumption cost should be tracked separately from question count.

**9. Formal approval buys no stability.** DORA's multi-year research finds external or board approval negatively correlated with lead time, deployment frequency, and time to restore, with no correlation to change failure rate (R7, A-). D4 stands, but reframed: one named human decision per change, not a scheduling gate through a standing body. Multi-party review is reserved for changes flagged high-tier at S0.

**10. The factory must measure what nobody has.** No published evidence exists that plan review reduces rework, that decision records or alternatives sections are reused, that deviation logs work for agents, or that scope checks are practised. Anthropic, Cursor, and Kiro all gate implementation behind a plan and all justify it qualitatively (R3, R5). Section 8 of the charter is therefore not optional instrumentation. It is the only evidence that will exist.

---

## 2. Findings by stage

Each stage lists the evidence with grades, the rubric lines that transfer, and what was not found.

### S0 Intake

**Evidence.** ITIL change categories gate process weight; service criticality tiers gate rollout pace (Google per-service risk tolerance; Uber tiers 0 to 5). Uber: 1.4% of 500,000 monorepo commits touch more than 100 services, 0.3% more than 1,000 (R1, B). Definition of Ready splits cleanly into presence checks and judgment; Atlassian's own DoR app checks exactly epic link, story points, and acceptance criteria non-empty (R1, B). The only primary exclusion policy found is GitHub's for its cloud agent: hard block on pushing to default branches or merging, CODEOWNERS on agent config files, secrets kept out of the repo (R1, C).

**Rubric lines.**
- Mechanical gate, no LLM: acceptance criteria field non-empty, named owner, linked parent.
- Look up the target service's criticality tier and the change type (schema or data, new integration, config-only) from the service catalogue. Above the threshold tier, a human signs off on eligibility before the factory starts. The same tier drives S7 ramp pace and kill sensitivity.
- Tool-level block on merge and deploy regardless of agent judgment. Owner-equivalent sign-off required on auth, payments, secrets, migration, and infrastructure paths, sourced from the catalogue rather than inferred per ticket.

**Not found.** A named organisation's intake risk score combining schema-change and incident history. Any financial-services engineering blog disclosing an AI-coding exclusion policy.

### S1 Context gathering

**Evidence.** Four impact-analysis methods with different preconditions and no published accuracy figures: build-graph reverse dependencies (precise, monorepo only), service catalogue (works in polyrepo, accuracy equals upkeep), trace-derived dependency graph (observes runtime, sampling gaps, no endpoint context) (R1, B). Google's CL-description guidance names Chesterton's fence as the reason "why" must be written: "reading source code may reveal what the software is doing but it may not reveal why it exists" (R1, B). Instruction files: four vendors independently converge on include only what the agent cannot infer from code; bloat measurably degrades instruction following; one five-run benchmark shows 9 to 27% improvement from a twelve-line file and no effect from a rule that never triggered (R1, A-). Error budget as a pre-agreed release gate: budget exceeded over four weeks halts everything except P0 and security; an incident consuming over 20% of budget mandates a postmortem (R1, B). Feature flags decided at design time because they change the design, not just the deployment (R1, B).

**Rubric lines.**
- The impacted-services list cites its method (build graph, catalogue, trace). If no method is available, "impacted services unknown" is a named blocker, not a footnote.
- Two-step archaeology on any non-obvious code to be touched: blame plus linked-ticket chain; if empty or contradictory, a characterization test pins current behaviour and the plan declares an unknown needing human confirmation.
- The brief states the target service's current error-budget consumption and inventories flags in the touched path. Exhausted budget means a reliability-only change or a named P0 or security exception.
- Context section is fact-only and lets an unfamiliar reviewer orient in under a minute. Padded or missing context fails S3 on its own.
- Factory instruction files pass the test "would removing this line cause a mistake?" Cap near 200 to 500 lines. Scoped files for path-specific guidance. An agent asking a question the file already answers is a bloat signal, not a signal to add text.

**Not found.** Any company other than Google publishing what its context section must contain. Netflix's primary posts were blocked.

### S2 Requirements clarification

**Evidence.** Headlines 4 and 5 above. Forced scenario categories exist only as pre-launch checklists: Google's launch checklist (ten categories including rollback, canary, external-dependency degradation) and AWS Well-Architected OPS1 to OPS11; nothing requirements-stage-native exists anywhere (R2, B). Splitting: Lawrence's nine patterns; a story that fails INVEST's Valuable test cannot be split; Google calls about 100 lines reasonable and about 1,000 too large; an industrial study confirms review time rises with patch size (R2, A-). Durable record: Amazon's Internal FAQ and ADR status plus alternatives are purpose-built to survive; Google's published design-doc template has no open-questions section at all (R2, B).

**Rubric lines.**
- Every acceptance criterion is expressible in EARS form (precondition, trigger, system, response) and passes an automated formalisation check. High variance across independent formalisations, a contradiction, or an input region with no specified behaviour fails S2.
- At least one concrete Given/When/Then example per criterion before S3.
- A versioned checklist of forced categories (error paths, concurrency, migration, backward compatibility, permissions, observability, rollback, data retention) is run against the criteria. An empty category becomes a ranked question, never a silent gap.
- A question reaches a human only if the answer is consequence-bearing and not cheaply reversible after a default is accepted. Otherwise the agent states the default and logs it. Rank by expected value of information: impact on spec times probability the default is wrong. Each question is two-option where possible, names the affected criterion, and carries a suggested default.
- If the requirement is not one vertical slice with observable value, or its estimated diff exceeds about 100 lines or 10 files, the agent proposes a split using the named patterns before criteria are marked complete.
- A per-ticket assumption log (question, default, answer or acceptance, who, when) ships with the spec and carries unmodified into S3 and S6. Append-only; supersede with links.

**Not found.** Any measurement of human response to question volume in a coding-agent setting. Acceptance or override rates for agent-proposed defaults at the plan level, from any lab.

### S3 Spec and plan

**Evidence.** Universal core across every located template: goals and non-goals, design, alternatives considered, risk or cross-cutting concerns; Uber's internal template adds testing and rollout plus metrics and monitoring; Stripe, Shopify, and Pinterest publish no template (R3, B). No scored design-review rubric exists; open-source governance supplies the only explicit rejection grounds: duplication of effort, technical unsoundness, insufficient motivation or missing backward-compatibility analysis, inconsistency with stated principles (R3, B). Anthropic, Cursor, and Kiro gate implementation behind a plan and none measures rework reduction (R3, B). Abstraction: rule of three, Metz's wrong abstraction, Ousterhout's deep modules; no lint measures abstraction quality (R4, B). Refactor separation is written Google policy, with tests required on pure refactors (R4, A/B). Pattern conformance: Google's readability certification has no agent analogue; catalogue discoverability does (R4, B). Risk location has the best evidence in the stage: relative churn discriminates fault-prone binaries at 89.0% accuracy; low ownership concentration and many minor contributors predict failures; Meta's Diff Risk Score routes reviewer attention in production, and flagging 10% of diffs catches 60% of incident-causing ones (R4, A). Test strategy: Google test sizes with a target mix near 80/15/5; rollout: the SRE launch checklist requires named steps, owners, and contingencies (R3, B). Design-before-diff friction at Google is unresolved company-wide and argues for S3 as a separate gate (R6, B).

**Rubric lines.**
- Structural completeness: goals and non-goals, approach, alternatives considered, a named risk section, test strategy by test size and target mix, rollout section with steps, owners, and contingencies. Missing any one fails on structure alone.
- Every rejected alternative gets one line: what it was and why it was rejected, so "not considered" and "considered and rejected" are distinguishable.
- A new shared abstraction cites at least three existing near-duplicates it replaces, or names pre-abstraction as a risk. Adding both a parameter and a conditional to a shared function that serves two or more unrelated callers must state why inlining was not chosen.
- Before modifying non-self-evident code: blame and ticket; characterization test if none exists; a change that alters captured behaviour is a named risk; the human decides load-bearing versus accidental.
- A diff whose entire justification is "no behaviour change" lands as its own change with behaviour-preserving tests. Bundling requires a named exception.
- Before proposing a new utility or pattern, query the component catalogue or repo index and record why any existing candidate was rejected.
- Risk map: for each touched file, compute change frequency over a fixed window and ownership concentration. Top-decile churn times complexity, or no clear owner, becomes a named entry stating the reviewer attention it warrants.
- Declare the input, output, and error contracts of touched code. Altering one is a named decision.
- Send-back grounds are recorded, not silently revised: duplicates existing work, technically unsound, missing backward-compatibility or migration analysis, contradicts a stated non-goal.
- The plan is dense and self-contained enough to judge in one sitting.

**Not found.** Any measured link from plan review to rework reduction. Any evidence that alternatives sections or decision records are consulted later. A scored design rubric to adapt, so the factory's plan rubric is original work.

### S4 Implementation

**Evidence.** Vendors describe checkpointing and plan gates; none publishes a conformance rate. Agent PR acceptance varies from 55% to 86% by tool, and "oversized" and "experimentation-only" appear as agent-specific rejection reasons (R5, A). Comments: Google style guides and Ousterhout converge: required where "tricky, non-obvious, interesting, or important," forbidden where the comment sits at the same abstraction level as the code; only TODO-owner format is lint-checkable (R5, B). Tests: Meta's TestGen-LLM filter chain (build, pass reliably, raise coverage, human accept) yielded a surviving test in 25% of 86 classes, and engineers accepted 73% of what survived to them (R5, A). AI code quality data is divergent by who measures; the actionable signal is contract drift (headline 7).

**Rubric lines.**
- S4 is not complete until the agent emits a deviation list, possibly empty, in a fixed schema: file or decision, what the plan said, what the agent did, why, judgment call or error. S5 and S6 consume it.
- A comment fails if it can be regenerated by paraphrasing the adjacent code. A comment is required where the plan marked a decision non-obvious or where behaviour deviates from what the name or signature implies. TODO owner is lint-enforced.
- A generated test fails unless it builds, passes without flakiness across N reruns, and raises coverage or kills a mutant the existing suite missed. Baseline expectations: about a quarter of candidates survive filters; about three quarters of survivors are accepted.

**Not found.** First-party production defect figures for AI-authored code from Google or Microsoft. Any software-engineering precedent for agent deviation logging; the nearest analogues are clinical and project-management deviation logs.

### S5 Cleanup pass

**Evidence.** Slop detectors have recall problems (LLM smell detection) or precision problems (one dead-code tool produced 260 false positives on Flask); no redundant-comment or style-drift detector has published precision; the literature recommends hybrid static plus LLM (R5, B/C). Presubmit tiering: Google's TAP runs only fast hermetic tests pre-merge and passing correlates with 95%+ likelihood of passing the full suite; Uber's SubmitQueue validates pending changes speculatively in parallel (R5, A/B). Judge requirements: headline 6. Scope checking has no published practice but is a literal set difference (R5, C).

**Rubric lines.**
- Two tiers. Blocking: lint, unit tests, slop rubric, scope diff, contract diff, all before the review packet is generated. Advisory: integration, mutation testing, LLM judge, run in parallel and surfaced into the packet without blocking it.
- S5 flags; it never auto-removes. A flagged item needs second-pass confirmation, or is surfaced as a declared blind spot when a known false-positive mode applies.
- Scope: any file or service not in the plan's scope section fails, unless the plan reserved discretion for that path. No LLM involved.
- Contract: any altered input or error contract not named in the plan fails.
- Judge independence: the model that wrote the code or plan may not grade it. Cross-family judging. Calibration κ reported before a judge may block.
- The gate blocks only on regressions to code health, not stylistic disagreement with a working solution.

**Not found.** Precision figures for any of the four slop-gate categories. Scope checking as a named, measured practice.

### S6 Human review

**Evidence.** Headlines 2 and 3. Google's reviewer look-order: design, functionality, complexity, tests, naming, comments, style, documentation; approve on net improvement, not perfection (R6, B). Stating the type of feedback wanted raises merge odds (odds ratio 1.72) yet appears in only 16.2% of 80,000 PRs; most other description elements have negligible effect once confounded (R6, A). Familiarity, not effort, determines comment depth; unfamiliar reviewers default to style comments (R6, A). Google routes attention through directory ownership, readability certification, and static-analysis pre-filtering; Meta through stacked single-thesis diffs; GitHub's required-reviewer rule mandates specific approvers for sensitive paths (R6, B).

**Rubric lines.**
- Packet order is fixed and not reorderable per ticket: intent and design, risk map, what was deliberately not touched and why, tests and what each proves, blind spots handed to the human, diff.
- The intent section names what the reviewer is being asked to verify, not only what changed.
- The risk map is mandatory and non-generic per ticket, because unfamiliar reviewers do not find those places unaided.
- Packet length is not a quality proxy. Measure completeness only of the risk map and the feedback request.
- Nothing reaches S6 while its S3 approval is open. S6 reviews conformance to an approved design, not the design.
- Independently mergeable plan tasks go to S6 as an ordered stack of single-purpose diffs mapping one-to-one to plan decisions.
- Touching a directory outside the assigned scope requires that directory's named owner, regardless of diff size.
- An automated reviewer comment must name a breaking, security, architecture, or performance concern, or be suppressed by default.
- S6 approval certifies judgment and intent, not defect-freedom.

**Not found.** Any company engineering account of reviewing AI-generated code specifically. Any measured effect of stacked diffs on review time or defects.

### S7 Rollout and verification

**Evidence.** Verification window sized to release cadence and traffic, judged against no more than a dozen SLI-derived metrics; Kayenta fails the whole canary when any metric marked critical breaches; LaunchDarkly guarded rollouts stage at 1, 10, 50, 100 percent with sequential statistical testing and automatic pause when a stage is undersized (R7, A-). Google's doctrine: roll back, fix, roll forward; schema changes sequenced as v, v+1 compatible no-op, v+2 feature so rollback is never blocked; rollback drills between incidents (R7, B). Flag debt: open the cleanup PR alongside the feature PR; every flag has owner, purpose, last-reviewed date, temporary or permanent; Uber's Piranha treats eight weeks unmodified as stale and removed about 2,000 flags, with 65% of generated diffs landing unchanged (R7, A-). No organisation publishes a human log-verification checklist; GitHub's ChatOps named-query pattern is the transferable analogy (R7, C). DORA on approval formality: headline 9.

**Rubric lines.**
- The rollout plan states one ramp schedule sized to expected traffic and release cadence, plus no more than twelve guardrail metrics, each expressed as a Grafana query with an explicit critical-fail threshold.
- The default response to any kill trigger is rollback. Fix-forward requires a named reason rollback is unsafe plus human sign-off.
- Any new flag states its expected life, owner, removal condition, and a placeholder cleanup diff. Staleness is checked 8 to 12 weeks after full rollout.
- The human log-verification step names the exact query (index, time window, filters) and the exact pass or fail pattern. A query used more than once becomes a saved, named check.
- Approval is one named human per change. Multi-party review is reserved for high-tier changes identified at S0.

**Not found.** A recommended minimum window duration from any source. A second organisation's rollback-versus-fix-forward doctrine. Any published post-deploy human log checklist.

### Cross-cutting

**Evidence.** Headlines 1, 6, and 8. Async decision shape: written proposal, objection window, default-proceed if silent (Apache about 72 hours; Rust ten-day final comment period; GitLab escalates to synchronous after roughly three failed async round-trips; Amazon's six-pager read silently before discussion) (R8, A-). Propose-a-default acceptance: Google's ML-suggested review edits resolve 7.5% of all reviewer comments company-wide, with 40 to 50% of previewed suggestions applied, and a more prominent button doubled the preview rate; Meta's SapFix has about half of proposed fixes accepted (R8, A). Metrics: lines of code rejected; any productivity metric used for individual review gets gamed; Google's GSM and the SPACE framework both insist on multi-dimensional panels (R8, B). Memory rot: instruction files rot silently and the model gets blamed; ADRs are superseded, never edited (R8, B).

**Rubric lines.**
- Questions and review requests never interrupt an active session. They queue, and the human chooses when. Resumption cost is tracked separately from question count.
- Accepted defaults follow propose, publish, proceed after a window, log any objection.
- Track surfacing rate and accept-given-shown rate separately. A mature accept-given-shown rate near 40 to 50% is the calibration anchor.
- Success measures are reported as an unranked panel, never a composite, and never feed individual performance evaluation.
- Memory: behaviour-change litmus test on every stored rubric or instruction line; decision log append-only with supersession links; a freshness pass every N tickets.
- Parallelism for independent subtasks such as S1 context gathering across services. A single agent with a clear plan for S4.

**Not found.** A software-engineering-specific study of batching interruptions. Any "agents per reviewer" figure. Plan-level propose-a-default acceptance data.

---

## 3. Findings by failure mode

| FM | Strongest evidence | Grade | Rubric line, short form | Packet |
|---|---|---|---|---|
| FM-01 Abstraction | Metz, Fowler, Ousterhout heuristics; no lint measures abstraction quality | B | Cite three or more duplicates or name pre-abstraction as a risk; parameter plus conditional growth must justify not inlining | R4 |
| FM-02 Load-bearing hack | Google CL-descriptions names Chesterton's fence; Feathers characterization tests; agent-specific practitioner source | B | Blame and ticket, then characterization test, then named risk; human decides | R1, R4 |
| FM-03 Style and pattern | Google readability; Spotify golden path; instruction-file bloat degrades behaviour | B / A- | Catalogue query before any new utility; instruction-file litmus test | R4, R1 |
| FM-04 Tech debt mixing | Google written policy: separate CLs, tests on pure refactors; Piranha flag cleanup | A / B | No-behaviour-change diff lands alone with tests; flag cleanup PR at creation | R4, R7 |
| FM-05 Scope creep | Cisco, Google, Microsoft size studies; agent "oversized PR" rejections; Shape Up appetite | A | Over 300 to 400 lines or 10 files triggers split-or-justify; scope diff fails on undeclared files | R3, R5, R2 |
| FM-06 Jumps to implementation | EARS plus SMT is the only mechanical completeness test; false-rigor failure mode | A- | Formalisation gate at S2 to S3; one example per criterion | R2 |
| FM-07 Question noise | Recognition-action gap; EVPI ranking; consequential-and-irreversible rule; default per question | A- | Value-of-information threshold; two-option with default; assumption log | R2, R8 |
| FM-08 Missing scenarios | Google launch checklist, AWS OPS questions; nothing requirements-native | B | Versioned forced-category checklist; empty category becomes a ranked question | R2 |
| FM-09 Parallel fatigue | Parnin and Rugaber 10% and 30%; Mark et al stress cost; Cognition and Anthropic bottleneck; async decision windows | A | Queue, never interrupt; resumption-cost metric; synthesis layer before the human | R8 |
| FM-10 Unreviewable diff | 14% of comments find defects; familiarity effect; feedback-type odds ratio 1.72; agent-only review 45% vs 68% merge | A | Fixed packet order; named ask; mandatory risk map; S5 is not S6 | R6 |
| FM-11 Filler tests | TestGen-LLM 25% survive, 73% accepted; mutation testing; LLM smell detectors low recall | A | Build, stable, coverage-or-mutant; flag, never auto-remove | R5 |
| FM-12 Filler comments | Google and Ousterhout same-abstraction-level rule; no detector with published precision | B | Paraphrase-regenerable comment fails | R5 |
| FM-13 Missing comments | Google "tricky, non-obvious, interesting, important" | B | Required where the plan marked non-obvious or behaviour differs from signature | R5 |
| FM-14 Unknown impact | Bazel rdeps, Backstage, Netflix traces; Uber 1.4% over 100 services; error-budget gate | B | List cites its method or declares a blocker; error budget in the brief | R1 |

---

## 4. Proposed charter amendments for v0.3

Decisions are recorded in the charter, not here. These are the changes the evidence supports.

1. **FM-09 wording.** Replace the "fresh deep-attention session" framing with the measured facts and remove any implied fixed refocus time. Add resumption cost to the success measures.

2. **New catalogue entries.**
   - **FM-15 Contract drift.** The agent alters an input, output, or error contract of touched code without declaring it, and later agents or humans build on the wrong assumption. Evidence: CodeThread odds ratio 1.83.
   - **FM-16 False rigor.** A spec or plan that is structurally complete but semantically vague passes review on appearance. Evidence: spec-driven tool practitioners; absence of any scored design rubric.
   - **FM-17 Silent memory rot.** A rubric or instruction line stops being true with no signal; agent behaviour degrades and the model is blamed. Evidence: Anthropic guidance plus independent practitioner convergence.
   - **FM-18 Agent-only review.** An agent review pass is treated as satisfying human review. Evidence: 45.20% vs 68.37% merge; 60.2% low-signal.

3. **Section 6 additions.** Fixed packet order. "Type of scrutiny requested" as a mandatory element of intent. Questions never delivered as interrupts. Two-option questions with defaults. Assumption log append-only with supersession.

4. **Section 8 changes.** Split "share resolved by accepting the default" into surfacing rate and accept-given-shown. Add revisions after plan approval as the plan-review evidence the field lacks. Report as an unranked panel. Never used for individual evaluation.

5. **Q3 complexity classification.** Starting signals: files touched, services touched, unresolved unknowns, estimated diff size against Google's bands (about 100 lines fine, about 1,000 too large), plus the S0 service tier.

6. **Stage map.** S5 becomes explicitly two-tier, blocking and advisory. S6's exit criterion reads "approval of judgment and intent." S3's exit adds structural completeness on the universal core.

7. **Anti-goals.** Add "no LLM judge grades its own author's output" and "no success measure feeds individual performance review."

---

## 5. What the field has not measured, and the factory must

- Whether plan review reduces rework. No vendor or lab has published it.
- Whether decision records, alternatives sections, or assumption logs are reused by later readers.
- Deviation logging and scope enforcement for agents as named practices.
- Human response to question volume in coding-agent settings, and acceptance or override of agent-proposed defaults at the plan level.
- Precision of redundant-comment and style-drift detection.
- Post-deploy human log verification as a checklist.
- Misclassification rates for load-bearing judgments.
- How many agents one reviewer can supervise before quality drops.

These map onto the charter's section 8 and the pilot in D10. Instrument from the first ticket.

---

## 6. Follow-up research, targeted and small

- Fetch blocked primaries by other means: Netflix Service Topology and Kayenta posts, Etsy's Quantum of Deployment, Gusto's False Fences, Pinterest's experiment review.
- Direct reads of PDFs: DORA 2019 and 2024 reports (the 2.6x and the +3.4% / -7.2% figures), Rigby and Bird FSE 2013, Piranha ICSE 2020 SEIP, the PRM derailment paper's figures.
- Academic literature on ADR usage and reuse, as distinct from adoption.
- Meta's Buck-based dependency analysis. OpenAI Codex plan-mode re-check. Any financial-services AI-coding exclusion policy.
- Resolve the TestGen-LLM discrepancy between 11.5% in the abstract and 9.9% in the table.

---

## 7. Method notes

- Eight Sonnet researchers, one packet each, under a primary-source rule and a fixed answer format defined in `questions.md`. Each raw packet states its own evidence quality per question; grades here were assigned by the orchestrator from those statements.
- Vendor marketing was excluded as evidence throughout. GitClear and Qodo material is labelled as coming from interested parties.
- R3 exhausted the shared web-search budget before RQ-S3-5 and RQ-S3-6 and completed them by direct URL fetch; both are marked in the raw file.
