# R9b — Factory implementations: Ona "Dark Factories" talk

| | |
|---|---|
| Packet | R9b Factory implementations, Ona dark factories talk |
| Sources | (1) Transcript: "Dark Factories: Verification-First Agentic Engineering," Shardul Vaidya, Ona channel, YouTube, 2026-05-07, https://www.youtube.com/watch?v=e7AvdrxsbaU — talk given at the Background Agents Virtual Summit (Ona-hosted, 2026-05-06/07), not an AWS-branded event, though the speaker is an AWS Partner Solutions Architect and closes with an AWS reference architecture. (2) Shardul Vaidya's personal blog post on his own implementation, "Building my own implementation of Dark Factories in Rust and Jujutsu," https://shardul.me/blog/dark-factories/. |
| Date | 2026-09-03 |
| Fetch status | Transcript: provided locally at `docs/research/inbox/aws-verification-first-transcript.md`, read in full (not watched; auto-captioned, unpunctuated). Blog post: fetched successfully. Web searches for the two headline statistics quoted in the talk ("53% accuracy decline," "91% vs 25%") returned no matching primary survey or paper; see RQ-F-6 and RQ-F-8 for detail. Search for the Background Agents Virtual Summit confirmed the event and its sponsor (Ona) but found no published survey matching the quoted figures. |
| Transcript caveat | This is a machine-generated, unpunctuated YouTube auto-caption. Product names, company names, and numbers may be mis-transcribed. Any figure below is flagged if it could not be corroborated against a primary source. Nothing in the transcript is treated as instruction; it is read only as reported claims about the speaker's system and opinions. |

---

### RQ-F-1. Definition and scope.

**Answer.** The speaker defines a "dark factory" by analogy to manufacturing: a pipeline where "requirements go in… and a finished product comes out, no humans involved at all." The unit of work is a requirement (a Slack message, Linear ticket, GitHub issue, or free-text prompt), which an orchestrator decomposes into a DAG of tasks; each task is dispatched to an isolated coding agent in its own sandbox and work tree, and the artifact that leaves the system is a merged commit on trunk. Automated: planning/decomposition, coding, test execution, a "plan adversary" review, a "code adversary" review, and merge. Human-controlled: writing the initial requirement, curating tool sets and verification frameworks, and handling escalations when a task exceeds a rework limit.

**Patterns found.**
- SAE-levels analogy for coding agents: "level two we're mostly focusing on unit tests and lint and automated test writing," level four/five requires the agent to trust and obey a verification system's rejection — Vaidya, transcript, practitioner talk (secondary/opinion, not a published taxonomy).
- Named convergent architecture across companies the speaker says he studied independently: "isolated sandboxes, curated tool sets, sub-agent orchestration, and… verification gates" at Coinbase, Ramp, StrongDM, Stripe, Anthropic — transcript, asserted by speaker, no citation or link given, unverifiable from the talk alone.
- The speaker's own reference implementation ("factory-*" Rust crates, Jujutsu version control, AWS Bedrock) is a single-operator hobby/demo project, not an enterprise account — shardul.me blog post, practitioner report, primary but self-described as personal.

**Evidence quality.** Primary for the speaker's own system (his blog and talk); secondary/anecdotal and uncorroborated for claims about Coinbase, Ramp, Stripe, Anthropic, and StrongDM, since no links, papers, or company posts are cited in the talk itself and none was found by search in this packet's budget. One source (the speaker) throughout.

**Transfer to an agent.** The requirement-in/commit-out framing is close to what the charter explicitly rejects ("Not a ticket-in, PR-out pipeline"); the useful part is the DAG-of-tasks decomposition and per-task sandbox isolation, which maps to S4 implementation with S3-level planning upstream. Rubric line: any multi-task change should be planned as a dependency graph, not a flat list, so independent subtasks can run in parallel and blocked ones wait.

**Gaps.** No named primary sources for the Coinbase/Ramp/StrongDM/Stripe/Anthropic convergence claim; not verifiable from the talk or from search within budget.

---

### RQ-F-2. Stage structure and gates.

**Answer.** The speaker names six phases: requirement → plan (with a "plan adversary" review gate) → queue → schedule → code (in an isolated sandbox, with a deterministic test-executor gate and a "code adversary" review gate) → merge (with a Jujutsu-based conflict-detection gate and, on failure, an LLM merge-rework step). Mapped onto the charter's S0–S7:

| Ona-talk stage/gate | Charter stage | Notes |
|---|---|---|
| Requirement submission (Slack/Linear/GitHub/web UI, "hit plan") | S0 Intake | No eligibility or tiering decision described; any requirement is accepted. |
| Planner researches codebase, decomposes into tasks/DAG | S1 Context gathering + S3 Spec and plan (merged) | The talk does not separate context-gathering from planning; the planner "has access and ability to research the codebase" as part of producing the plan. No S2 requirements-clarification stage is named — no clarifying-question step is described at all. |
| Plan adversary reviews the plan and DAG "to make sure it will work fine within the context of the code base" | S3 exit gate | This is the closest analogue to human plan approval in the charter, but here the reviewer is an agent, not a human (see RQ-F-3, RQ-F-8). |
| Queue → schedule → coder in isolated sandbox | S4 Implementation | One agent per task, own work tree/sandbox/container. |
| Test executor (deterministic) | Part of S4/S5 blocking gate | "if the tests fail, we never get to the code reviewer" — a hard block before any LLM judgment, similar to the charter's S5 "blocking" tier idea. |
| Code adversary ("code reviewer" agent) | S5 Cleanup pass (agent pass) — explicitly conflated with S6 in the talk | The speaker calls this "how a maintainer would refuse to look at a PR," i.e., positions an agent as doing what the charter reserves for a human at S6. No separate human review stage is described in the pipeline diagram. |
| Merge (Jujutsu conflict detection, deterministic; merge-rework agent on failure) | Between S5/S6 and deploy | No S7 rollout/verification stage is described at all — the talk stops at merge, with a passing aside that a "finished product comes out" and, near the end, "gets deployed," but no ramp, kill condition, or verification window is discussed. |
| Human escalation on "exceeded max rework count" | Only human decision point named in the pipeline | Functions as a residual S6-like gate, but only for failures, not for every change (see RQ-F-3). |

**Patterns found.**
- Six-phase pipeline with a rework loop feeding failure context back to the same or next agent attempt (bounded at some retry count; the blog post says up to 5 attempts before an item is "dropped with logged reasons") — transcript; shardul.me blog, practitioner primary.
- No named S0 risk-tiering, no named S2 clarification stage, no named S7 rollout/verification stage.

**Evidence quality.** Primary (the speaker's own architecture), single source.

**Transfer to an agent.** The deterministic-gate-before-LLM-gate ordering ("if the tests fail, we never get to the code reviewer") is directly reusable: cheap mechanical checks should block before any LLM judgment runs, matching the charter's S5 blocking/advisory split. What does not transfer is collapsing S2 (clarification), S6 (human review), and S7 (rollout) into "merge," which conflicts with D4 and P1 (see RQ-F-8).

**Gaps.** No description of an S0 eligibility filter, an S2 clarifying-question mechanism, or an S7 rollout/verification stage in this source.

---

### RQ-F-3. Human interaction model.

**Answer.** The stated design goal is "zero humans write code, zero humans review code": the plan adversary and code adversary are both agents, not people. The only described human touchpoint in the pipeline itself is exception handling — when a task "exceeded max rework count," the system escalates to the human operator with the message "you should probably look at this yourself... because you're responsible for the code that it generates." Outside the pipeline, the human's job is redefined as authoring requirements, curating tool sets, and architecting the verification framework, not reviewing diffs or answering in-flow questions.

**Patterns found.**
- Explicit zero-human-review target: "Coinbase, Ramp, Stripe, Anthropic, and StrongDM" and "zero humans write code, zero humans review code" — transcript, unsourced claim about other companies.
- Escalation-only human interaction, triggered by rework-count exhaustion, not batched or queued per the charter's section 6 model — transcript.
- Reframed human role: "you're composing the factory that writes the code for you... you architect verification frameworks and fundamentally ensure correctness" — transcript.

**Evidence quality.** Primary (speaker's own account and opinion), anecdotal, single source; no measured data on how often escalation triggers, how much human time it costs, or how attention is budgeted.

**Transfer to an agent — and explicit conflict with the charter.** This is the sharpest divergence from the charter in this packet. The charter's D4 ("No autonomous merge or deploy. A human approves every change into a production branch and every flag ramp") and P1 ("Human attention is the scarce resource... every stage is judged by how much attention it consumes") both require a human decision on every change. The talk's target architecture merges without a human approval step for the common case — the only human touchpoint is a failure escalation, not a per-change gate. What the speaker actually proposes humans do is upstream and configurational: write requirements, curate tools, design the verification gates themselves, and handle rework-exhausted exceptions — not approve each merge. This is not compatible with D4 as written; it substitutes review of the verification *system* for review of each *change*. The transferable piece is the escalation-on-repeated-failure pattern as a supplement to, not a replacement for, per-change human approval.

**Gaps.** No data on escalation frequency, resolution time, or what fraction of tasks reach a human at all.

---

### RQ-F-4. Verification and judgment.

**Answer.** Verification is split into three layers described as running in parallel: (1) traditional checks — unit tests, property tests, mutation tests, lint, all deterministic and blocking; (2) "AI-native" checks — an LLM code-reviewer ("code adversary") judging diffs for "too much entropy" or incomplete features, plus LLM-driven scenario/end-to-end testing describable as a user journey; (3) a named-aspirational layer — formal system invariants stated mathematically, which the speaker says is "mostly unexplored" and "aspirational for me too." No rubric content, scoring scheme, or calibration method is given for the code-adversary or plan-adversary judgments; they are described only functionally ("points out if there was too much entropy... or some feature isn't complete").

**Patterns found.**
- Ordering rule: deterministic tests run first and block the LLM reviewer entirely on failure ("if the tests fail, we never get to the code reviewer... this is essentially how a maintainer would refuse to look at a PR if the tests are red") — transcript, B-grade practitioner claim, no rubric published.
- Plan adversary and code adversary are the only two named "back pressure" mechanisms beyond deterministic tests; no rubric text, weighting, or acceptance threshold is disclosed.
- Formal invariants layer named as aspirational and unimplemented, not evidence of a working practice.

**Evidence quality.** Primary, anecdotal, single source; no precision, recall, or calibration figures for either adversary; no statement on whether the adversary models are the same family as the authoring model (a live risk against synthesis finding 6/headline on judge independence).

**Transfer to an agent.** The deterministic-before-LLM-judgment order is directly reusable as a pipeline rule: block on tests/lint before invoking any LLM reviewer. The "adversary" concept without a published rubric is not directly transferable — it is exactly the gap the charter's P2 ("rubrics are the product") and synthesis headline 6 warn about: an unscored, unrubricked LLM judge.

**Gaps.** No rubric content, no calibration or judge-independence statement, no precision/recall figures for the code or plan adversary, no detail on the scenario-testing implementation.

---

### RQ-F-5. Context and memory.

**Answer.** Context gathering is folded into the planning step: "the planner has access and ability to research the codebase," and this research substitutes for a distinct S1 stage. Agents are explicitly stateless and share nothing: "There [is] no shared state between agents running at any given time... they can crash, we can reboot them, and they will just keep running." Cross-task memory is provided structurally by the version-control substrate (Jujutsu workspaces/stable change IDs) and by the rework loop, which the speaker distinguishes from a bare retry: "the full context of why it failed is fed forward into the next attempt. That's not a retry, that's essentially just a full rework." No standing instruction file, decision log, or ADR-equivalent is mentioned.

**Patterns found.**
- Statelessness-by-design across agents, contrasted with persistence at the orchestration/VCS layer (Jujutsu stable change IDs) — transcript.
- Rework-loop context carry-forward as the only named cross-attempt memory mechanism — transcript.
- No instruction-file, CLAUDE.md/AGENTS.md-equivalent, or organisational-memory artifact named anywhere in the talk or blog post.

**Evidence quality.** Primary, single source, anecdotal; no measurement of what the planner's "research" actually retrieves or how completeness is checked.

**Transfer to an agent.** The failure-context-forward-not-bare-retry pattern is directly useful and aligns with the charter's P4 (agent states what it does not know) if extended to log *why* a rework happened. What is missing relative to the charter's D7 (SQLite/markdown factory memory, rubrics, decisions) is any standing memory across tickets — this factory appears to have per-task memory only, not organisational memory.

**Gaps.** No description of how the planner's codebase research works, what sources it draws on, or how it avoids re-discovering the same context on every ticket.

---

### RQ-F-6. Evidence.

**Answer.** The talk contains two headline statistics presented without citation, and the packet found no matching primary source for either after search.

**Patterns found.**
- "53% accuracy decline" when engineers use trust-all-tools/YOLO/non-interactive mode, attributed to lack of a feedback loop — transcript. Status: **claim, self-reported by the speaker, not sourced in the talk; unverifiable from the transcript; no matching published figure found by search in this packet's budget.** Possibly a garbled or rounded recollection of a different study; flagged, not repeated as fact.
- "91% versus 25%": "91% of engineering leaders claim that AI has improved velocity, but only 25% have the data to prove it" — transcript. Status: **claim, no source named in the talk.** Search found adjacent but non-matching figures from unrelated 2026 reports (e.g., Jellyfish's State of Engineering Management 2026 reports 91% AI-coding-assistant adoption and 64% reporting ≥25% velocity increase; DX/getdx.com reports AI adoption up 65% with PR throughput up only 8% at the median, and only 20% of teams using metrics to measure AI impact). None of these reproduces the speaker's exact "91% claim vs. 25% data" framing, so the two numbers cannot be confirmed as quoting a specific named survey correctly; they may be a paraphrase or conflation of several sources.
- "over 300 commits," "23 tasks," "27 additions, 30 deletions" — these are demo-walkthrough figures from the speaker's own dashboard, self-reported, denominator is his own single hobby project, not a benchmark.
- "up to 5 attempts before being dropped" (rework bound) — from the blog post, self-reported, denominator is the speaker's own implementation, not measured against a broader sample.

**Evidence quality.** All figures in this source are self-reported by one speaker about his own system or asserted without citation about the industry; none is independently measured or corroborated within this packet's search budget. Grade C throughout (secondary/uncorroborated or single-source anecdote).

**Transfer to an agent.** None of these figures should be cited as evidence in the factory's rubric or success-measure design; they fail the charter's "measured, not estimated" bar in section 4 and section 8. If the factory wants a comparable statistic (e.g., accuracy decline in non-interactive/auto-approve mode, or leaders'-claims-vs-data gap), it needs the primary survey, not this talk.

**Gaps.** Primary source for "53% accuracy decline" not found. Primary source for "91% vs 25%" not found; closest located reports (Jellyfish 2026, DX/getdx.com longitudinal analysis) do not reproduce the same framing and are noted only as candidates, not confirmations.

---

### RQ-F-7. Named failure modes.

**Answer.** The talk names failure modes mostly implicitly, through what its architecture guards against, rather than as a list.

**Patterns found and FM mapping.**
- **Ungoverned autonomous/"YOLO" mode causing accuracy loss** ("no feedback loop... no way to know it's gone wrong") — closest to **FM-11** (false sense of safety from unverified output) and to the charter's general concern about unmonitored autonomy; also touches proposed **FM-18 (agent-only review)** since the talk's own target state is agent-only review, which the synthesis flags as measurably worse.
- **Merge conflicts from bad decomposition** ("Bad decomposition can produce merge conflicts because more than one agent will try to do the same thing") — closest to **FM-05** (scope creep / overlapping change boundaries) though framed as a parallelism problem rather than scope; no exact catalogue match, note as partial fit.
- **Agent going "haywire," blast-radius containment via sandboxing** — no direct FM match; closest is a runtime/operational risk not covered by FM-01 to FM-18. **No catalogue entry.**
- **Task fails, full rework with fed-forward context (as opposed to bare retry)** — mitigation for repeated/silent failure but does not map cleanly to a named FM; closest is **FM-17 (silent memory rot)** in reverse (the mitigation, not the failure) since it explicitly avoids losing failure context between attempts.
- **Zero-human-review target and reliance on the code adversary as reviewer** — directly instantiates proposed **FM-18 (agent-only review)**: the talk's own stated ideal (zero humans review code) is the exact pattern synthesis headline 2 and FM-18 warn against (45.20% vs 68.37% merge rate, low actionable-signal ratio for agent-only review).
- **No rubric disclosed for the code/plan adversary** — instantiates proposed **FM-16 (false rigor)**: a structurally plausible-sounding gate ("code adversary... points out if there was too much entropy") with no disclosed scoring criteria risks passing on appearance.
- **No S2 clarification stage, no forced-scenario checklist** — touches **FM-06** (jumps to implementation without a completeness check) and **FM-08** (missing scenarios), since the pipeline goes straight from requirement to plan-DAG with no described clarifying-question step.
- **Statelessness / no organisational memory** — touches **FM-02** (load-bearing code judged without history) and **FM-17 (silent memory rot)** by omission: there is no described mechanism preserving why past decisions were made across tickets.

**Failures with no catalogue entry.** Blast-radius containment via sandbox/container isolation for a misbehaving agent process (an infrastructure/operational risk, not a judgment or attention risk) has no FM-01–FM-18 equivalent; it is closer to conventional systems-reliability practice than to the factory's judgment-and-attention catalogue.

**Evidence quality.** Primary, single source, all inferred rather than explicitly labeled as "failure modes" by the speaker; no frequency or cost data for any of them.

**Transfer to an agent.** The clearest transferable lesson is negative: this architecture's own headline design goal (zero human review) is the pattern the charter's D4 and the synthesis's FM-18 evidence say fails on measured merge-quality grounds. The deterministic-gate-before-agent-judgment ordering is the one positive, transferable mitigation pattern.

**Gaps.** No cost or frequency data for any named failure; no discussion of FM-01, FM-03, FM-04, FM-09, FM-10, FM-12, FM-13, FM-14, or FM-15 in this source.

---

### RQ-F-8. Delta against the synthesis.

Going through all ten headline findings from `synthesis.md` section 1:

1. **Attention constraint externally confirmed (P1).** **Untouched/contradicted in intent.** The talk does not address human attention budgeting explicitly; its target state removes the human from the loop almost entirely rather than managing attention as a scarce resource, which is a different framing than "spend attention only where it changes the outcome." No synthesis layer for merging N agent outputs before a human is described.
2. **Human review catches few defects; agent-only review is measurably worse.** **Directly touched, and the talk's design ideal runs counter to it.** The talk's target state — "zero humans write code, zero humans review code," judged instead by an LLM "code adversary" — is precisely the agent-only-review pattern the synthesis (45.20% vs 68.37% merge rate, 60.2% low actionable-signal) finds measurably worse. The talk offers no counter-evidence; it asserts the pattern is used by named companies without citation.
3. **Change size is the strongest measured lever.** **Weakly touched, not contradicted.** The demo shows very small diffs ("three additions, six deletions... net reduction in entropy") as a stated goal ("we can force the factory to behave that way"), consistent with the synthesis's size-discipline finding, but with no quantitative size-vs-defect data of its own.
4. **Question triage has a research base and convergent rule.** **Untouched.** No clarifying-question mechanism, escalation rule, or default-and-disclose pattern is described in the pipeline; the only human-facing signal is failure escalation, not question triage.
5. **Completeness can be checked mechanically by exactly one mechanism (EARS/SMT).** **Untouched.** No requirements-completeness check of any kind is described.
6. **Rubrics have operating requirements and the field has none to lend.** **Confirmed by omission.** The plan adversary and code adversary are named but their rubric content is never disclosed, consistent with the synthesis's finding that no scored design/code rubric exists in the wild.
7. **Contract drift predicts downstream agent failure.** **Untouched.** No discussion of input/output/error contracts.
8. **FM-09 wording correction (interruption cost).** **Untouched.** No discussion of interruption or resumption cost; the talk's model largely removes the human from per-task interaction, sidestepping the question rather than answering it.
9. **Formal approval buys no stability (DORA).** **Weakly touched, consistent in spirit.** The talk replaces standing committees ("AI center of excellence... committees that meet every month") with automated verification gates, which is directionally consistent with DORA's finding that external/board approval correlates negatively with delivery metrics — though the talk offers no comparable measurement of its own.
10. **The factory must measure what nobody has.** **Confirmed by omission.** The talk reports no rework-reduction data, no plan-review-effectiveness data, and no reuse data for its own decision or rework logs — it is another example of a system that gates on artifacts (plans, adversary reviews) without publishing whether those gates work.

**Evidence quality.** Primary but single-source and largely anecdotal; the deltas above are the packet's own mapping of the talk's claims onto the synthesis, not independently measured contradictions or confirmations from the talk itself.

**Transfer to an agent.** The most actionable delta is #2: this talk is a real-world example of the exact "agent-only review" pattern that FM-18 and synthesis headline 2 warn against, presented as an aspirational best practice by a credible practitioner audience (AWS Partner SA, an industry summit). It is useful evidence that the pattern is being actively promoted and should be explicitly guarded against in the charter's D4 language.

---

### RQ-F-9. Transfer.

**Answer.** Several structural elements transfer to a single-engineer, brownfield, MCP-connected, one-machine factory; the "zero human" framing and most of the scale-dependent infrastructure do not.

**Patterns found — transferable.**
- Deterministic tests block before any LLM review is invoked — cheap, machine-checkable, no infrastructure dependency.
- DAG-based task decomposition for independent subtasks, letting unrelated work proceed in parallel — feasible on one machine using MCP-connected tools and multiple agent sessions.
- Rework loop that forwards *why* a task failed into the next attempt rather than bare-retrying — directly implementable regardless of scale.
- Escalate to a human only after a bounded number of failed attempts, as a supplement to (not replacement for) per-change human approval.

**Patterns found — not directly transferable.**
- "Zero humans write code, zero humans review code" — conflicts with the charter's D4 and with the measured evidence the synthesis already collected (finding 2); not adoptable as stated.
- Container/micro-VM/EC2-per-agent isolation, DynamoDB state, Bedrock AgentCore, EventBridge/Step Functions orchestration — all scale- and AWS-infrastructure-dependent; the charter's environment (section 7) runs on the engineer's machine with MCP servers, not a fleet of isolated cloud sandboxes.
- Unrubricked "adversary" agents as the sole judgment layer — depends on having a mature, calibrated rubric first (P2), which this source does not supply.
- Claims about Coinbase/Ramp/Stripe/Anthropic/StrongDM convergence — unverifiable and not something to build design decisions on.

**Evidence quality.** Primary, single source, anecdotal; the transfer assessment above is this packet's own judgment applied against the charter, not a claim made by the source itself.

**Transfer to an agent.** Adopt: deterministic-before-LLM gate ordering; DAG decomposition for independent subtasks; failure-context-forward rework. Reject as-is: zero-human review; unrubricked adversary judges; cloud-fleet isolation model. Rubric line: "every merge gate must have a named human approval step; an LLM 'adversary' pass is evidence submitted to that human, never a substitute for it" (restates D4 against this source's explicit counter-example).

**Gaps.** No data from this source on cost, latency, or failure rate of running the described architecture at any scale beyond one demo project; no comparison to a single-engineer setting anywhere in the talk.

---

## Sources consulted

- Transcript: "Dark Factories: Verification-First Agentic Engineering," Shardul Vaidya, Ona channel, YouTube, 2026-05-07, https://www.youtube.com/watch?v=e7AvdrxsbaU — primary (talk transcript, auto-captioned), read via local file `docs/research/inbox/aws-verification-first-transcript.md`.
- Shardul Vaidya, "Building my own implementation of Dark Factories in Rust and Jujutsu," https://shardul.me/blog/dark-factories/ — primary, practitioner blog, fetched.
- Ona, "Background Agents Virtual Summit," https://ona.com/events/background-agents-virtual-summit — primary, event page, used only to confirm venue/date via search snippet (not directly fetched).
- Jellyfish, "The State of Engineering Management in 2026," https://jellyfish.co/blog/the-state-of-engineering-management-in-2026/ — secondary/company survey, used only as a candidate (non-matching) source for the "91%/25%" figure; not a confirmed match.
- getdx.com, "AI and engineering velocity: A longitudinal analysis" and related DX newsletter posts — secondary/company survey, used only as candidate (non-matching) sources for velocity-claim-vs-data figures.
- Search snippets only, no fetch: LinkedIn profile confirming Shardul Vaidya's role as AWS Partner Solutions Architect; softwaredarkfactory.com (marketing page, not used as evidence).

No primary source was found for the transcript's "53% accuracy decline" figure or its exact "91% vs 25%" framing; both are recorded as unverified claims in RQ-F-6, not as facts.

## Cross-references

- RQ-F-8 point 2 and RQ-F-7's FM-18 mapping touch **synthesis.md headline 2** and the proposed **FM-18** directly; also relevant to **R9a, R9c, R9d** (other factory packets) for cross-source comparison of how many name a zero-human-review target.
- RQ-F-4's rubric-absence finding parallels **R3 (RQ-S3-2)** on the absence of a published scored design-review rubric, and **R5/R6** on judge independence (synthesis headline 6).
- RQ-F-2's stage mapping (no S2, no S7 equivalent) is relevant to **R2** (requirements clarification) and **R7** (rollout) as a negative example — a named factory that skips both stages entirely.
- RQ-F-6's unverifiable statistics are relevant to **R8 (RQ-X-6)** on misleading productivity metrics — this talk repeats headline claims of exactly the kind R8 warns are ungrounded.
- RQ-F-9's isolation/DAG pattern is relevant to **R8 (RQ-X-3)** on humans supervising multiple concurrent agents.
