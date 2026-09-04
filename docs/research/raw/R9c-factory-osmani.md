# R9c — Factory implementations: Addy Osmani, "Software Factories, Light and Dark"

| | |
|---|---|
| Packet | R9c Factory implementations, Osmani |
| Sources | Addy Osmani, "Software Factories, Light and Dark," https://addyosmani.com/blog/software-factories/ (primary, essay). Cross-checked: addyosmani.com/about (fetched, no role info found there); web search results confirming author bio/departure; Dex Horthy / HumanLayer material cited inside the post as the source of the "dark factory" case study. |
| Date | 2026-09-03 |
| Fetch status | Post itself: fetched successfully via WebFetch (full extraction returned). About page: fetched, contained no role statement (site nav/credits only). Author role confirmed instead via web search of Osmani's bio page and press coverage (LeadDev, O'Reilly event listing, X/Twitter departure announcement), not a direct blog-post self-statement of title. Dex Horthy primary source not independently fetched (used only via search snippets); flagged as a gap. |
| Author role as stated | Not "Gemini tech lead" in those exact words. Per his own bio page and independent coverage (O'Reilly event listing, LeadDev profile, and a widely circulated departure post), Osmani spent 14 years at Google, most recently as **Director at Google Cloud AI**, where he led **Gemini's developer experience** and agentic-engineering work (coding agents, harnesses, evals, code quality) before departing Google in 2026. He held tech-lead and tech-lead-manager roles at various points across those 14 years, but his final title was Director, not tech lead. This packet treats the piece as an **individual practitioner essay from a well-placed but non-company-authorized source**, not a company practice document — it does not carry Google's institutional endorsement and Osmani had already left or was leaving Google around the time of publication. |

## Source-type grading

This is a personal blog essay (practitioner report / secondary synthesis), not a company engineering blog post or peer-reviewed paper. It synthesizes and names other primary sources (notably Dex Horthy of HumanLayer, whose four-month "dark factory" experiment is the concrete case study underlying the post's central failure narrative) rather than reporting the author's own measured data. Graded **C** (secondary/synthesis, single essay) for its own claims; where it reports Horthy's case study, that underlying material is graded **B/C** (practitioner report, unpublished formal measurement, single account) because it was only reached via search snippets, not the primary post/talk itself.

---

### RQ-F-1. Definition and scope.

**Answer.** Osmani defines a "software factory" as "many harnessed loops running at once, fed by a queue of work and drained through a review gate into production, with humans owning the whole thing from above." The unit of work is the **loop**: gather context, take an action, check the result, repeat until a condition is met. Work enters as intent from engineering leadership, engineer requests, or production signals (incidents, user reports); automated checks (CI, tests, static analysis, security scanning) run at near-zero marginal cost; the single expensive gate before production is human review. What leaves is an approved, deployed change, with monitoring data feeding back into the queue.

**Patterns found.**
- Factory = many loops + queue + review gate + human ownership — "Software Factories, Light and Dark," https://addyosmani.com/blog/software-factories/, practitioner essay (secondary/synthesis).
- Automated versus human split: type systems, tests, static analysis, security scanning, and "review agents coupled with a real rubric" are mechanical; humans own "deciding whether solutions address problems correctly, verifying diagnoses/implementations, approving changes, and accepting consequences" — same source.

**Evidence quality.** Single-source practitioner essay; no measured figures attached to this definition itself, and no other independent post repeats this exact "harnessed loops" framing. It is the author's own synthesis of practice observed across the industry (Google, HumanLayer/Horthy, and unnamed others), not a description of one named organisation's built system.

**Transfer to an agent.** The loop-as-unit-of-work framing and the "cheap mechanical gate, one expensive human gate" split match the charter's stage map and P1 directly. Proposed rubric line: define the factory's own unit of work as the ticket-to-approved-plan-to-approved-diff sequence, and require every automated check to run before the single named human gates (S2, S3, S6), never in place of them.

**Gaps.** No named organisation's factory is described end-to-end in this post beyond the Horthy case study; the "many loops at once" claim is not grounded in a cited multi-agent deployment at scale.

---

### RQ-F-2. Stage structure and gates.

**Answer.** The post's structure is informal and does not name discrete stages the way S0–S7 do; it describes a queue-in, loop-execution, review-gate-out flow with a design/architecture decision point kept human ("lit factory") versus fully automated ("dark factory"). Mapping is necessarily approximate because the post operates one level of abstraction above the charter's stage map.

**Patterns found.**
- Queue of work (intent, engineer requests, production signals) → maps to **S0 Intake** (no explicit eligibility/tiering criteria given).
- No explicit context-gathering stage named; "gather context" is one leg of the generic loop, so it maps loosely to **S1 Context gathering**, but with no artefact (no brief, no impacted-services list) described.
- No requirements-clarification stage or question-asking mechanism is named at all — **no equivalent to S2** in the post.
- "Design/architecture" decisions are the point the "lit factory" keeps human — maps to **S3 Spec and plan**, but described only as a principle ("keep the lights on wherever a wrong call is expensive"), not as an artefact or gate with defined exit criteria.
- The loop's "take an action, check the result" cycle maps to **S4 Implementation**, bounded by the post's "short loops (3–10 steps)" recommendation because agents "lose coherence beyond 20 steps."
- Automated checks (CI, tests, static analysis, scanning) map to **S5 Cleanup pass**, but the post does not distinguish a separate independent-agent cleanup pass from S4's own checks; they are treated as one blocking gate.
- "Human review before deployment" maps to **S6 Human review**, named as "the single expensive gate."
- Deployment plus "monitoring data cycles back into the signal loop" maps to **S7 Rollout and verification**, but no canary sizing, kill condition, or flag-ramp detail is given.
- **No equivalent** for: definition-of-ready checks, requirement-completeness testing, a distinct plan-approval step separate from general "design," or a distinct S5 second-pass agent review separate from S4's own checks.

**Evidence quality.** Author's own synthesis; C grade. No organisation's actual stage gates (names, exit criteria, tooling) are documented — the post argues in principles, not in described pipeline architecture.

**Transfer to an agent.** The post gives no stage-level detail to lift directly. What transfers is the general principle that automated checks should be cheap and the single expensive gate should be human review — already present in the charter (S5/S6 split, P1). No new stage-level rubric line is supported by this source alone.

**Gaps.** No description of a requirements-clarification stage, a discrete plan-approval artefact, canary/rollout mechanics, or definition-of-ready criteria — all absent from the post.

---

### RQ-F-3. Human interaction model.

**Answer.** The post argues humans should move from writing code to "owning the outer loop": deciding correctness of the approach, verifying diagnosis and implementation, approving changes, and accepting consequences — but it does not describe a concrete interaction mechanism (queue versus interrupt, batching, defaults, or attention budgeting). It draws a binary: "lit" factories keep humans engaged at the design stage before agents execute; "dark" factories remove human review entirely and, per the cited Horthy case study, accumulate "comprehension debt."

**Patterns found.**
- "Lit factory" keeps humans at design/architecture review before code generation, versus "dark factory" (no review at all) — https://addyosmani.com/blog/software-factories/, practitioner essay.
- No description of how questions are batched, queued, ranked, or defaulted; no mention of a question-answer interaction pattern at all.

**Evidence quality.** Single-source, qualitative, no interaction-design detail. Directly compares to the charter's section 6 contract (batching, defaults, queue delivery) but the post simply does not address that layer of detail — it stays at the "should a human review or not" level.

**Transfer to an agent.** Nothing new transfers on the mechanics of question delivery. The one usable principle — humans should own outer-loop judgment, not inner-loop execution — reinforces P9 (reviewable reasoning over reviewable diffs) but adds no new rubric line beyond what synthesis.md finding 1 and 2 already establish.

**Gaps.** No treatment of question batching, ranking, defaults, or attention budgeting — the entire FM-07/FM-09/section-6 territory is untouched by this source.

---

### RQ-F-4. Verification and judgment.

**Answer.** Mechanical verification named: type systems, tests, static analysis, security scanning, and "review agents coupled with a real rubric" (the rubric's content is not specified). The post's central judgment claim is a capacity limit — "back pressure": "you can only hand a loop as much autonomy as you can cheaply and reliably verify" — and a stated empirical-feeling threshold that agents "lose coherence beyond 20 steps," recommending loops of 3 to 10 steps to stay verifiable. No rubric content for abstraction, scope, style, or debt judgment is given; "review agents coupled with a real rubric" is named as a category, not shown.

**Patterns found.**
- Back-pressure principle: autonomy bounded by verification capacity — https://addyosmani.com/blog/software-factories/, practitioner essay, no citation given for the mechanism itself.
- Loop-length claim: agents "lose coherence beyond 20 steps," 3–10-step loops "remain verifiable" — same source; presented as an observed pattern, no denominator, no study cited, appears to be the author's own operational heuristic rather than a measured figure from a named benchmark.
- Architecture as an external safety net: "good types, test seams, clear boundaries, dependency injection, legible call stacks" substitute for judgment the model does not supply — same source.

**Evidence quality.** C grade throughout. The "20 steps" figure in particular has no denominator, no source citation, and no benchmark named — it reads as the author's synthesised operating rule, not a measured result. Treat as a claim, not a figure.

**Transfer to an agent.** The back-pressure principle is directly usable as a design constraint: cap agent loop length to what the S5 gate can verify cheaply, and treat "review agent plus real rubric" as a requirement — a review agent without a rubric is not verification. Proposed rubric line: any autonomous loop step-count above a set ceiling (the post's anecdotal 10–20-step range) requires a named human checkpoint before continuing, rather than running to completion unsupervised.

**Gaps.** No rubric content is given for abstraction, scope, style, or tech-debt judgment specifically — the post asserts such rubrics should exist ("review agents coupled with a real rubric") but does not show one, and no source for the 20-step figure was locatable in the fetch.

---

### RQ-F-5. Context and memory.

**Answer.** The post treats "gather context" as one leg of every loop but does not describe a persistence mechanism, a context brief artefact, or an instruction-file practice. Its main memory-related claim is negative: dark factories accumulate "comprehension debt," defined as "the widening gap between how much code exists and how much any human still understands," and this debt is not paid down by passing tests — it compounds silently while tests stay green.

**Patterns found.**
- Comprehension debt concept: "A dark factory doesn't pay it down; it takes it on as fast as it can, with the tests green the whole way" — https://addyosmani.com/blog/software-factories/, attributed to Dex Horthy's (HumanLayer) four-month fully-automated experiment (per search-snippet corroboration of "Software Factories, Light and Dark," and secondary coverage such as the BigGo Finance summary of Horthy's account).
- No described mechanism for what persists across tickets (no instruction file, no ADR, no decision log named in the post).

**Evidence quality.** C grade; the comprehension-debt narrative rests on one unpublished, self-reported case (Horthy's), reached here only through search snippets, not the primary talk/post. It could not be independently verified against a primary Horthy source within this packet's budget.

**Transfer to an agent.** The comprehension-debt concept is directly relevant to FM-14 and to D7 (factory memory in SQLite/markdown): a factory with no human review accumulates undocumented state faster than any memory file can capture it. Proposed rubric line: treat "time for a human to re-orient in a subsystem" as a tracked cost, and require it to stay bounded, not just test pass rate.

**Gaps.** No description of what a context brief should contain, no instruction-file guidance, and no primary Horthy source was fetched to confirm the "three weeks to re-onboard" and "days to find the root cause" figures reported in secondary coverage.

---

### RQ-F-6. Evidence.

**Answer.** The post reports almost no first-party measured figures of its own. The one concrete anecdotal figure — the length of Horthy's fully-automated run — is reported inconsistently across sources reached here (the post's own framing versus secondary coverage), and the "20 steps" coherence-loss claim carries no denominator or citation.

**Patterns found.**
- "Four months" (per the post/its search-derived summary) versus "July to November 2025" (roughly four months, per a WebSearch-derived secondary account) versus a separate secondary summary reading "wouldn't even take four months to develop" now — https://addyosmani.com/blog/software-factories/ and secondary coverage (BigGo Finance, https://finance.biggo.com/news/15099f5634f5ab9a). **Self-reported by Dex Horthy**, a claim, not an independently measured figure; denominator is "one organisation's one internal system over one time window," not disclosed further (team size, codebase size, or ticket count not given).
- "Agents lose coherence beyond 20 steps" — https://addyosmani.com/blog/software-factories/. **Claim**, author's own stated heuristic; no denominator, no cited study, no benchmark name.
- "3 to 10 steps" as the verifiable loop length — same source. **Claim**, author's own operational recommendation, not measured.
- No percentage, defect rate, review time, or acceptance-rate figures anywhere in the extracted post content.

**Evidence quality.** Every number in this post is either an anecdotal claim from a single unpublished experiment (Horthy, self-reported, not independently audited) or the author's own unsourced heuristic. None reach measured status (no denominator, no methodology, no replication). This is the weakest evidence tier among the R9 packet's sources.

**Transfer to an agent.** No figure here is strong enough to set a numeric rubric threshold on its own. Proposed rubric line: treat "20 steps" and "3–10 steps" only as a starting hypothesis for a loop-length ceiling to be validated against the factory's own pilot data (per charter D10 and synthesis section 5), not as an adopted constant.

**Gaps.** No measured figures with disclosed denominators exist anywhere in this source. Searched for a primary Horthy publication (talk transcript or written postmortem) to verify the four-month/three-week/days-to-diagnose figures directly; not fetched within budget — flagged rather than treated as confirmed.

---

### RQ-F-7. Named failure modes.

**Answer.** The post names two failure modes directly and one implicitly: the **funnel problem** (generation outpaces verification), **comprehension debt** (undocumented accumulated state from unreviewed code), and implicitly, **loss of coherence in long agent loops**. It also implies a review-shirking failure by contrast (the "dark factory" itself as a failure mode, i.e., removing the human review gate).

**Patterns found.**
- Funnel problem: "Generation is a wide mouth; verification is the narrow neck. Speeding up the mouth just deepens the pile at the neck." Mitigation: back-pressure (bound autonomy to what can be cheaply verified). — https://addyosmani.com/blog/software-factories/.
- Comprehension debt: unreviewed code accumulates faster than human understanding; mitigation is keeping humans "lit" (engaged) at the design stage. — same source, sourced to Horthy's case study.
- Coherence loss beyond ~20 steps; mitigation is short loops (3–10 steps) plus architectural safety nets (types, test seams, DI, legible call stacks). — same source.
- Dark factory itself (full automation, no human review) as the umbrella failure mode the essay is structured around; mitigation is the "lit factory" pattern.

**Mapping to the charter catalogue:**
- Funnel problem → closest to **FM-18 (proposed, Agent-only review)**: both describe verification capacity being overwhelmed when generation outpaces the human/mechanical check that certifies it. Also touches **FM-09** (attention as the bottleneck) since "verification" ultimately routes through human review capacity.
- Comprehension debt → closest to **FM-14 (Unknown impact/context gathering)** and **FM-17 (proposed, Silent memory rot)**: undocumented state that nobody currently understands is a superset of both — no impacted-services knowledge (FM-14) and no fresh, checked memory of why code is the way it is (FM-17). Comprehension debt is broader than either existing entry and has **no exact catalogue match**; it names a systemic outcome (whole-codebase illegibility) that FM-14 and FM-17 only partially cover.
- Coherence loss beyond N steps → **no catalogue entry**. This is an agent-capability limit (context window / attention degradation within a single execution), distinct from any FM-01 to FM-18 entry, all of which describe human-facing or judgment failures, not raw agent execution degradation.
- Dark factory (removing human review) → directly **FM-18 (proposed, Agent-only review)**: "An agent review pass is treated as satisfying human review" is exactly what a dark factory institutionalises.

**Failures named in the post with no catalogue entry:** the funnel/verification-capacity-overwhelm framing as a general systemic dynamic (partially but not fully captured by FM-09/FM-18); the specific agent-coherence-degrades-with-loop-length failure (no FM entry at all — this is closer to a tooling/architecture constraint than a process failure mode, so it may belong in a future "agent execution limits" category rather than the human-process catalogue).

**Evidence quality.** Qualitative, single-source; the mapping above is this packet's own analysis, not something the post itself performs (the post does not reference the charter's FM numbering, obviously, since it predates or is independent of this project).

**Transfer to an agent.** Loop-length ceiling and back-pressure are transferable design constraints, not rubric lines per se: cap unsupervised execution length and require every increase in autonomy to be matched by a cheaper, faster verification method, not just faith in the model. Comprehension debt argues for tracking a "human legibility" metric (time to re-orient) as its own success measure, distinct from tests-passing.

**Gaps.** No coverage at all of FM-01 (abstraction), FM-02 (load-bearing hack), FM-03 (style/pattern conformance), FM-04 (tech debt mixing), FM-05 (scope creep), FM-06 (requirement completeness), FM-07 (question noise), FM-08 (missing scenarios), FM-10 (unreviewable diff format), FM-11 (filler tests), FM-12/FM-13 (comments), or FM-15/FM-16 (contract drift, false rigor) — the post operates at a much higher level of abstraction and does not discuss any of these.

---

### RQ-F-8. Delta against the synthesis.

Going through synthesis.md section 1's ten headline findings:

1. **Attention constraint (P1, Cognition/Anthropic).** **Confirmed, independently.** The post's back-pressure principle — "you can only hand a loop as much autonomy as you can cheaply and reliably verify" — and its framing of humans "owning the outer loop" both restate the same constraint from a different source, without citing Cognition or Anthropic. Independent convergence, not a citation chain.

2. **Human review catches few defects / agent-only review measurably worse.** **Untouched directly, but thematically confirmed.** The post never cites the Microsoft 14%/Google 2-of-44 figures or the 45.20%/68.37% merge-rate study, but its entire "dark factory" narrative is a qualitative version of the same claim: removing human review (agent-only verification) produced comprehension debt and a production failure the agent itself could not diagnose. Same direction, no shared figures.

3. **Change size is the strongest measured lever.** **Untouched.** No mention of diff size, review latency, or defect density by size.

4. **Question triage / EVPI ranking.** **Untouched.** No mention of questions, ranking, or defaults reaching a human at all.

5. **Completeness checked mechanically (EARS/SMT).** **Untouched.** No requirements-stage content in the post.

6. **Rubrics have no operating standard; the field has none to lend.** **Partially confirmed.** The post names "review agents coupled with a real rubric" as necessary but, consistent with synthesis finding 6, does not show or cite one — it treats the rubric as an assumed input, reinforcing the synthesis's point that no scored rubric exists to borrow.

7. **Contract drift predicts downstream failure.** **Untouched directly**, but the comprehension-debt narrative is a broader, unmeasured cousin of the same idea: undeclared changes to a codebase that later work (human or agent) cannot safely build on. No mention of contracts specifically.

8. **FM-09 wording / "23 minutes" correction.** **Untouched.** No interruption-cost figures cited.

9. **Formal approval buys no stability (DORA).** **Untouched.** No mention of approval formality, DORA, or change-failure-rate correlation.

10. **The factory must measure what nobody has.** **Confirmed by omission.** The post itself supplies almost no measured figures (RQ-F-6), which is itself evidence for synthesis finding 10 — even a well-placed practitioner writing specifically about software factories in 2026 could not cite instrumented figures for loop-length limits, review-gate effectiveness, or comprehension-debt cost. It offers only one unpublished, single-organisation case study (Horthy's) as its evidentiary base.

**Evidence quality.** Author's own synthesis compared point-by-point against synthesis.md; no new primary figures introduced by this source that would revise the synthesis's grades.

**Transfer to an agent.** No changes to the synthesis's rubric lines are supported by this source; it adds independent qualitative corroboration for findings 1, 2 (by analogy), 6, and 10, but no new measured evidence.

**Gaps.** Findings 3, 4, 5, 8, and 9 are entirely untouched by this source.

---

### RQ-F-9. Transfer.

**Answer.** Two principles transfer cleanly to a single-engineer, brownfield, MCP-connected, one-machine factory: back-pressure (bound autonomy to what can be cheaply verified) and the lit-versus-dark framing (never let full automation substitute for the one human review gate). The loop-length figures (3–10, up to 20 steps) are anecdotal and should be treated as a hypothesis to validate locally, not adopted as a constant. The "many harnessed loops running at once" framing itself assumes a scale (multiple parallel agents, a team-wide queue, an engineering-leadership intent stream) that does not describe a single-engineer factory and should not be imported as an architectural target.

**Patterns found.**
- Back-pressure and lit-vs-dark — directly applicable design constraints, scale-independent.
- Comprehension debt as a named risk of any unreviewed automation, regardless of team size — applicable even at one-engineer scale, arguably more dangerous there since there is no second engineer to catch drift.
- "Many loops running at once," queue fed by "engineering leadership" — assumes team/organisational scale; not applicable as described to a solo factory.

**Evidence quality.** C grade; this is the packet's own transfer judgment applied to a single-source essay.

**Transfer to an agent.** Adopt back-pressure and lit-factory framing as stated design principles (already implicit in the charter's P1/P9/anti-goals). Do not adopt the specific step-count numbers without local validation; do not adopt the multi-loop/queue architecture as a target, since the charter's factory is explicitly single-engineer and single-machine (D9).

**Gaps.** No guidance in the post on how a single-engineer factory should scale down the "many loops" model — this is an explicit gap the charter's design work, not this source, will have to resolve.

---

## Sources consulted

- Addy Osmani, "Software Factories, Light and Dark," https://addyosmani.com/blog/software-factories/. Primary essay (practitioner report/secondary synthesis), fetched successfully.
- addyosmani.com/about — fetched; contained no role/title information (site credits and disclaimer only).
- WebSearch: "Dex Horthy 'software factory' comprehension debt four-month experiment" — used to corroborate the post's central case study via secondary coverage (BigGo Finance, https://finance.biggo.com/news/15099f5634f5ab9a; Substack recap https://hungrymindsdev.substack.com/p/software-factories-harnessing-loops; the post itself). Dex Horthy's own primary talk/post was not independently fetched within budget.
- WebSearch: "Addy Osmani 'tech lead' Gemini Google role 2025 2026" — used to confirm author's stated role via his own bio page (addyosmani.com/bio, referenced in search results but not separately fetched), an O'Reilly event listing describing him as "Google Cloud AI Director," and a widely circulated departure summary (X/Twitter, https://x.com/CodeByPoonam/status/2068317985039896880) stating he was "most recently ... a Director at Google Cloud AI leading Gemini's developer experience."

## Cross-references

- **R9b (Ona dark factories talk)**: Dex Horthy's four-month "dark factory" experiment appears to be the same underlying case study likely covered directly in R9b; the two packets should be reconciled for consistency on the comprehension-debt figures (four months, three weeks re-onboarding, days-to-diagnose), since this packet reached them only via secondary coverage.
- **synthesis.md finding 1** (attention constraint, Cognition/Anthropic) — independently corroborated by this source's back-pressure principle.
- **synthesis.md finding 2** (human review catches few defects; agent-only review worse) — thematically but not numerically corroborated by the dark-factory narrative.
- **synthesis.md finding 6** (no scored rubric exists in the field) — corroborated by the post's unfilled "review agents coupled with a real rubric" claim.
- **synthesis.md finding 10** (the factory must measure what nobody has) — corroborated by this source's near-total absence of measured figures.
- **Charter FM-14, FM-17 (proposed), FM-18 (proposed)** — see RQ-F-7 mapping; comprehension debt spans FM-14/FM-17 without an exact match, and the dark-factory pattern is a clean instance of FM-18.
- **Charter D9** (single-machine, single-engineer factory) — see RQ-F-9; the post's "many loops at once" framing does not transfer directly and should be flagged if a later document cites this source for architecture.
