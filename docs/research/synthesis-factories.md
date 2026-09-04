# Research Synthesis, Factory Implementations

| | |
|---|---|
| Status | v0.1 |
| Date | 2026-09-03 |
| Inputs | `docs/research/questions.md` v0.2, packet R9 (RQ-F-1 to RQ-F-9); `docs/research/raw/R9a` to `R9d` |
| Extends | `docs/research/synthesis.md` v0.1. Read that first. This file records only what the four factory accounts confirm, contradict, or add. |
| Cites | `docs/charter.md` v0.2 |

## Coverage

Four sources supplied by the user, read as whole-factory accounts rather than stage-level practice. Nine questions per source, 36 answers, all complete. Every URL was reached except two Warp documentation pages that returned 404 (Factory API and MCP; Dashboard and Measurement). The talk was read from a machine transcript pulled by `yt-dlp`, not watched. Two primaries referenced by the sources were not fetched: Dex Horthy's own account of the four-month automated run, and Uber's AI Engineer 2026 talk.

Two corrections to the labels the sources arrived with:

- The "AWS verification-first" video is a talk by Shardul Vaidya, an AWS Partner Solutions Architect, given at Ona's Background Agents Virtual Summit in May 2026. It is not an AWS publication and the architecture shown is his personal Rust and Jujutsu implementation.
- Addy Osmani's final role at Google was Director, Google Cloud AI, leading Gemini developer experience. He left Google in 2026. The essay is a personal one and carries no company endorsement.

Grades:

| Source | Type | Grade |
|---|---|---|
| Uber, "Efficient software factory" (plus Port newsletter as secondary) | Company engineering blog | B for architecture, C for every number: self-reported, undated, and the secondary disagrees with the primary on skill count and graph size |
| Ona summit talk, "Dark Factories" | Practitioner talk, single speaker, hobby implementation | C. Both headline statistics are unsourced and no primary could be found |
| Osmani, "Software Factories, Light and Dark" | Personal essay synthesising others | C. Rests on one unpublished case study reached through secondary coverage |
| Warp Factories, blog and docs | Vendor documentation | C. Descriptive, unmeasured; dashboard figures are labelled sample data |

No figure in this packet has a denominator larger than one. The packet therefore moves no evidence grade in the main synthesis. What it changes is structural: it shows what the factories being built today have in common, what they all leave out, and where the charter is already ahead of them.

---

## 1. What the factory accounts change

**1. All four converge on one skeleton, and none of them has S0, S2, or S7.** Intake from a ticket or chat tool, a plan or spec, implementation in an isolated environment, an agent review, a pull request. Warp names seven states, Ona six phases, Uber four layers of specialisation, Osmani "many harnessed loops... drained through a review gate." Not one has a risk-tiering decision at intake. Not one has a requirements clarification stage with a described question mechanism; Warp's "the foreman asks instead of guessing" is the only mention and it comes with no threshold, ranking, batching, or default. Not one documents a rollout ramp, kill condition, or post-deploy verification window; Warp's stage list says "monitor" once and its docs never elaborate. The charter's stage map is not a superset of theirs for completeness' sake. S0, S2, and S7 are where the charter differs, and P3 (front-load the effort) has no counterpart anywhere in this literature.

**2. Agent-only review is the industry default, not a hypothetical.** Uber's own list of automated capabilities reads "code review" alongside "self-healing CI failures" and "triaging on-call alerts," with human "draft PR review" positioned downstream. The Ona talk's stated ideal is "zero humans write code, zero humans review code," and it claims without citation that Coinbase, Ramp, Stripe, Anthropic, and StrongDM have converged on the same. Osmani's essay is built around the failure of exactly that design: a four-month fully automated run that produced "comprehension debt" the agent could not diagnose. Warp is the only account whose review agent is explicitly "advisory" with merge as "your team's call," and Warp then adds that both of its human gates "are workflow policy, written into the foreman's instructions; edit them to change when the factory checks in." Proposed FM-18 should be adopted, and its wording needs a second clause: the human gate is not merely skipped, it is demoted to a configurable default and edited away.

**3. Spec approval and merge are the convergent minimum human gates.** Warp defaults to exactly those two. Uber names prototype approval and draft-PR review. Osmani's "lit factory" keeps design decisions human and calls review "the single expensive gate." Ona has neither. This supports S3 and S6 as the charter's two hard gates. No source has any gate at S2. The charter's third gate, on requirements completeness, has no external precedent and no external evidence either way. It rests entirely on the Kiro formalisation finding in the main synthesis and on the user's own revision-cycle experience.

**4. Rubric-as-code now exists as an artefact class, still without calibration.** Warp's `scorers/` directory holds user-authored, versioned, LLM-evaluated rubric files kept separate from agent prompts. Repeated scorer failures are grouped by a "self-improvement" step into proposed follow-up runs, including proposed edits to the factory's own definition, which a human accepts or rejects. Ona's "plan adversary" and "code adversary" have no disclosed rubric at all. Osmani names "review agents coupled with a real rubric" as a requirement and never shows one. Uber has an internal benchmark of real PRs with known bugs for choosing models, and no judgment rubric for abstraction, scope, style, or debt. Headline finding 6 stands. What is new is a design pattern the charter should adopt for D7: rubrics live as versioned files owned by humans, apart from agent instructions, and the only path from a run's failures into a rubric is a human-reviewed change.

**5. Deterministic gates run before any LLM judgment.** The Ona talk states the rule plainly: "if the tests fail, we never get to the code reviewer... this is essentially how a maintainer would refuse to look at a PR if the tests are red." Uber runs five small safety and policy models in under 100 ms in front of its LLM gateway. Osmani's split is cheap mechanical checks, then one expensive human gate. Three unrelated accounts, one ordering. The main synthesis proposed a two-tier S5; this fixes the order: the blocking tier is deterministic and runs first, and the advisory LLM tier never runs on a red build.

**6. A persistent context index beats per-ticket rediscovery, on the only figure in the packet with a denominator.** Uber's context graph, at 24 million nodes over more than 30 internal systems, answered one example task in 38 seconds against 20 minutes 9 seconds without it. That is one task, self-reported. Against it: Ona's agents are deliberately stateless with no memory across tasks, Warp versions configuration but keeps "work items, runs, and metrics" in its web app and leaves "memories" undocumented, and Osmani's comprehension debt is the cost of having no such index at all. D7 is confirmed in direction. Two additions follow. The index needs a staleness policy, which no source has, and which is the proposed FM-17 in operational form. And D7 needs an explicit split between versioned configuration and run state, described under amendment C below.

**7. Back-pressure is the one principle every source states and the charter only implies.** Osmani: "you can only hand a loop as much autonomy as you can cheaply and reliably verify," and "Generation is a wide mouth; verification is the narrow neck. Speeding up the mouth just deepens the pile at the neck." The Ona implementation bounds rework at five attempts and then escalates with the full failure context. Uber nudges on spend at 50, 80, and 100 percent of the expected budget. The charter has P1 and the verification-capacity idea inside headline finding 1, but no principle that says autonomy is bounded by verification. Proposed as P10 below.

**8. Every metric these factories publish is the charter's anti-goal.** Uber reports that more than 70 percent of PRs are agent-attributed, 30,000 skill executions a day, cost per session down 52 percent. Warp's sample dashboard reads "$57.55 cost per PR, 93% code quality, and 96% efficiency" with no formula for either percentage. The Ona talk quotes "53% accuracy decline" and "91% versus 25%" and neither number could be traced to a survey. Osmani reports nothing. Uber names revert rate and MTTR as tracked and gives no values. Not one source reports revisions after approval, reviewer minutes, defect rate, or escalation frequency. Headline finding 10 is reinforced by four more data points. One thing is worth borrowing from Uber: growth figures are reported with a time window, while point-in-time counts are not, and that is why the primary and secondary cannot be reconciled.

**9. The failure modes factory operators name are fleet-economics failures, and three of them reach a single machine.** Uber: MCP schema preloading costing 50,000 to 70,000 tokens, cache expiry forcing full-price prefix rebuilds, wrong model routing, tool sprawl, "uncontrolled autonomous maintenance loops," and an ungrounded agent that "fails slowly rather than cheaply, repeatedly sending an expanding context window." Warp: the "governance nightmare" of per-laptop bespoke agents. Ona: blast-radius containment through sandboxes. Osmani: coherence loss beyond about 20 steps, and comprehension debt. Most of these assume a fleet and belong outside the catalogue. Three do not. Tool-schema bloat follows directly from D8, since every MCP server the factory connects pays in context before the first token of the ticket. The slow-failing loop follows from any autonomous S4. Comprehension debt is a single-engineer risk, arguably worse there because no second engineer notices the drift. Coherence loss with loop length is not a catalogue entry; it is a design constraint on S4.

**10. Nothing here is a runtime, and D5 stands.** Warp is a competing whole-factory platform: its own orchestration, agent runtime, file format, and hosted state store, with self-hosting on Enterprise plans only. Adopting it would replace D7 and D9, not fill D5. Uber's stack is proprietary and fleet-scale. The Ona implementation is an AWS fleet with EC2-per-agent isolation, DynamoDB state, and Step Functions. The interchangeable-runtime assumption survives. Read the other way, this is the "no generic product" anti-goal confirmed: no off-the-shelf factory does what the charter describes, because none of them puts the effort where P3 puts it.

---

## 2. Findings by stage

Only stages the factory accounts touch. Rubric lines are proposals.

**S0 Intake.** No source tiers risk at intake; all accept any request. Warp's foreman skips Triage "when the request already explains the problem," undefined. Rubric line: S0 assigns a tier before any agent time is spent, and the tier is a field on the ticket record, not a foreman judgment.

**S1 Context gathering.** Uber's graph spans services, teams, incident logs, PRs, design docs, deployments, and datasets, which is a reasonable node-type list for the local index even at small scale. Warp's Triage agent "reports context, scope, complexity, and open questions" to the foreman, not to a human. Rubric line: the S1 brief lists the index entries it used and the ones it found stale, so that FM-17 has a signal.

**S2 Requirements clarification.** Nothing. This is the stage with the least external precedent in the whole corpus. Rubric line unchanged from the main synthesis.

**S3 Spec and plan.** Warp's spec agent writes "product and technical specifications in a draft pull request with criteria for validating the change," and building "waits until a person signs off on the plan." Ona's planner emits a task DAG with declared dependencies so independent tasks run in parallel. Rubric line: the plan is a dependency graph, not a list, and the validation criteria are written at S3, not discovered at S5.

**S4 Implementation.** Ona: one agent per task in its own worktree, stateless, and rework carries "the full context of why it failed" into the next attempt, "not a retry." Osmani: loops of 3 to 10 steps stay verifiable; coherence is lost past about 20. Rubric lines: unsupervised loop length has a ceiling, value set from pilot data, hypothesis 10 to 20 steps; after N failed attempts the task escalates to a human with the accumulated failure context, never a bare retry; the implementing agent "never merges."

**S5 Cleanup pass.** Ordering fixed by finding 5. Warp's implement agent records a computer-use walkthrough video in the PR as verification evidence for the human, which is a cheap way to make S5 evidence legible at S6. Rubric line: S5 output is evidence attached to the ticket record for the S6 reviewer, and the deterministic tier's result is shown first.

**S6 Human review.** Uber shows "pre-flight checks displayed" to the draft-PR reviewer; Warp attaches the review agent's advisory verdict. Rubric line: the review packet opens with the checks that ran and their result, then the plan and deviations, then the diff, matching the main synthesis's fixed packet order.

**S7 Rollout.** Nothing beyond Osmani's "monitoring data cycles back into the signal loop." The main synthesis's S7 findings stand unchanged.

---

## 3. Failure-mode table, delta only

| ID | Status after R9 | Evidence from R9 |
|---|---|---|
| FM-14 | Confirmed, mitigation named | Uber's graph exists because context is "fragmented across 20 to 30 systems" |
| FM-16 (proposed) | Two live instances | Ona's adversaries and Warp's scorers are gates with no disclosed criteria |
| FM-17 (proposed) | Confirmed by omission, scope widened | No source has a staleness policy; comprehension debt is the human-side form |
| FM-18 (proposed) | Confirmed as default practice | Uber, Ona; Warp's gates are editable policy |
| FM-19 (new) | Proposed | Uber: tool-schema preloading at 50 to 70 thousand tokens; Warp: "governance nightmare" of tool sprawl |
| FM-20 (new) | Proposed | Uber: agent "fails slowly rather than cheaply"; Ona: rework bound as mitigation |

No frequency or cost data for any entry from any source. The TBD columns stay TBD.

---

## 4. Proposed charter amendments, additional to synthesis section 4

Decisions are recorded in the charter. These add to, and in one case modify, the list already awaiting review.

- **A. FM-18 wording.** "An agent review pass is treated as satisfying human review, or the human gate is implemented as a configurable default and switched off." Evidence: Uber's stage list; Ona's stated ideal; Warp's "edit them to change when the factory checks in."

- **B. Two new entries.**
  - **FM-19 Tool-schema context bloat.** Connected tool schemas consume the context budget before the ticket is read; the agent's effective context for the task shrinks silently. Evidence: Uber, 50 to 70 thousand tokens; Warp tool sprawl. Follows from D8.
  - **FM-20 Slow failure.** An ungrounded or blocked agent keeps working, expanding context and cost, instead of failing early and escalating. Evidence: Uber's description; Ona's five-attempt bound as mitigation.

- **C. D7 split.** Factory memory has two halves with different rules. Versioned configuration: rubrics, agent instructions, skills, the failure-mode catalogue, decisions. Run state in SQLite: tickets, runs, questions, answers, metrics. A finding from run state enters versioned configuration only through a human-reviewed change. The context index carries a last-verified date per entry and a staleness rule. Evidence: Warp's factory-as-code split and its propose-then-accept loop; Uber's absent staleness policy.

- **D. New principle P10, back-pressure.** "Autonomy is bounded by verification. Every increase in what the agent may do without a human is paired with a cheaper, faster check, or it does not happen." Evidence: Osmani, Ona, Uber, three independent statements; consistent with headline finding 1.

- **E. Stage map.** S5's blocking tier is deterministic and runs first; the advisory tier never runs on a red build. S4 gains a loop-length ceiling with a checkpoint and a bounded rework count with escalation carrying failure context. S3's plan is a dependency graph.

- **F. FM-17 scope.** Widen from "a rubric or instruction line stops being true" to include the human side: the owning engineer's understanding of a changed subsystem decays while tests stay green. Add a success measure: time for the owning engineer to re-orient in a subsystem the factory changed.

- **G. Section 8.** Adopt time-windowed reporting for every growth figure. Explicitly exclude PRs per period, agent-attributed share of PRs, and cost per PR from the primary measures, naming them as the metrics the factory literature publishes instead of the ones that matter.

- **H. Section 7 and D8.** Record the MCP schema cost as a design constraint: servers are attached per stage and per ticket tier, not all at once.

---

## 5. What the field has not measured, additions

- Escalation frequency and resolution time when a bounded loop hands a task to a human.
- Whether a versioned rubric edited through a propose-and-accept loop improves the next run. Warp offers the mechanism and no data.
- Cost of comprehension debt in re-orientation time. One self-reported case, secondary coverage says about three weeks to re-onboard.
- Context consumed by tool schemas per ticket, and its effect on task success.

---

## 6. Follow-up research, targeted

- Dex Horthy's primary account of the four-month run (HumanLayer talk or post), to verify the figures Osmani relies on.
- Uber's AI Engineer 2026 talk, linked from the blog; transcript via `yt-dlp` as done for the Ona talk.
- Warp's Dashboard and Measurement page, which likely defines "code quality" and "efficiency"; the URL has moved.
- The origin of the Ona talk's "53% accuracy decline" and "91% versus 25%" figures, or confirmation that none exists.

---

## 7. Method notes

- Four Sonnet researchers on the registered `web-researcher` agent definition at medium effort, one source group each, under the same rules and answer format as R1 to R8.
- The talk was converted from YouTube auto-captions to a 3,038-word transcript. Auto-captions are unpunctuated and can garble names and numbers; the researcher flagged rather than repeated anything it could not corroborate.
- Uber's post was read through a summarising fetch, not verbatim, which is why the primary and secondary disagreements are flagged and not resolved.
- Vendor and self-reported figures are labelled as such throughout. Nothing in this file is graded above B.
