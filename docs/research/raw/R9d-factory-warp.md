# R9d Factory implementations: Warp

| | |
|---|---|
| Packet | R9d |
| Sources | Warp blog and docs.warp.dev (vendor) |
| Date | 2026-09-03 |
| Fetch status | Blog post: fetched OK. `/factories`: fetched OK. `/factories/how-factories-work/`: fetched OK. `/factories/factory-agents/`: fetched OK. `/factories/factory-as-code/`: fetched OK. `/factories/factory-api-and-mcp/`: 404, not found at that path (recovered partial content via search snippet, cited as such below). `/factories/dashboard-and-measurement/`: 404, not found at that path, no substitute found within budget. |

All content below is vendor documentation or a vendor blog post. Every quote is Warp's own description of its product; no figure below is independently verified. Warp's own dashboard example ("$57.55 cost per PR, 93% code quality, and 96% efficiency") is a vendor-supplied illustrative sample, not a disclosed customer measurement, and is flagged as such wherever cited.

---

### RQ-F-1. Definition and scope.

**Answer.** Warp defines a "software factory" as a hosted, coordinated fleet of cloud agents that takes in requests from existing tools (Slack, Linear, Jira, GitHub) and turns them into a stream of mergeable pull requests, explicitly framed as the next layer of automation after CI/CD. The unit of work is a tracked request (bug report, feature spec, support escalation, ticket) that a "foreman" agent routes through whichever stages apply and hands back to a human as a pull request. Triage, spec drafting, implementation, and code review are automated by named agents; scope decisions, spec approval, and merge remain human.

**Patterns found.**
- "A cloud software factory is... an automation loop around the SDLC, where cloud agents triage, spec, implement, review, verify and monitor work" — "Introducing Warp Factories," warp.dev/blog, vendor blog.
- "A software factory takes in requests (bug reports, feature specs, support escalations), and a coordinated fleet of agents works them into a stream of mergeable pull requests" — docs.warp.dev/factories, vendor documentation.
- Foreman agent "decides which agent a work item goes to next" and "keeps the requester informed" — docs.warp.dev/factories/factory-agents/, vendor documentation.

**Evidence quality.** Primary (vendor's own documentation and announcement blog). Not measured; descriptive/product-spec only. Single source (one vendor); internally consistent across the three pages that define scope.

**Transfer to an agent.** The "foreman routes to agents, humans approve at named gates, PR is the final artefact" shape matches the charter's stage map at a coarse level; it does not itself supply a rubric. Proposed pipeline rule: keep a single coordinating role responsible for stage routing and for surfacing questions, so a human always has one entry point rather than N agent channels.

**Gaps.** No definition of what counts as "unit of work" size or complexity; no criteria for what enters versus is excluded (no S0-equivalent risk tiering disclosed).

---

### RQ-F-2. Stage structure and gates — mapped to S0 to S7.

**Answer.** Warp's default loop is Intake, Triage, Planning (Spec), Building (Implement), Reviewing, Human handoff, Complete/Cancelled — a linear seven-state flow with two hard human gates (spec approval, merge) and one soft gate (clarification questions). Mapped onto the charter's S0–S7: Intake ≈ S0 (no eligibility criteria disclosed); Triage ≈ S1 (partial, skippable); Planning ≈ S2+S3 merged (no separate requirements-completeness gate); Building ≈ S4 (includes some verification); Reviewing ≈ S5+S6 blended (an agent review, advisory only, with a separate human merge decision serving as S6); there is no explicit S7 (rollout/verification stage) — Warp's flow ends at PR merge, with "monitor" mentioned only once in the blog's stage list and not detailed in docs.

**Stage-by-stage mapping.**
- Intake → **S0 Intake.** "Work enters from integrations, automations, or direct runs" (docs.warp.dev/factories/how-factories-work/, vendor doc). No eligibility/risk-tiering criteria published; gate is presence-only, not risk-based. **Optional** human step (none required to start).
- Triage → **S1 Context gathering.** Agent "researches and defines scope... reports context, scope, complexity, and open questions"; "The foreman skips this stage when the request already explains the problem" (same source). No human decision named here; unknowns are surfaced to the foreman, not directly to a human. **No required human gate.**
- Planning → **S2+S3 combined (Requirements clarification + Spec/plan).** Spec agent "writes product and technical specifications in a draft pull request with criteria for validating the change" (factory-agents/). **Required human gate**: "the Building stage waits until a person signs off on the plan" (how-factories-work/). This is the single clearest mandatory approval point and functions as both the S2 completeness check and the S3 plan approval, undifferentiated.
- Building → **S4 Implementation.** Implement agent "continues the spec's branch and draft pull request" and "adds tests and validation... It never merges" (factory-agents/). No human decision required at this stage; verification (see RQ-F-4) happens here, blending S4 and part of S5.
- Reviewing → **S5 Cleanup pass / partial S6.** Review agent "independently examines the change," gives a verdict that is explicitly "advisory," and can trigger a revision loop back to Building ("Revision needed?" loop). This is agent-only, not a human gate — closer to S5 (independent agent pass) than S6.
- Human handoff → **S6 Human review.** "Factory opens the PR but whether and when it merges is your team's call" (factory-agents/, how-factories-work/). **Required human gate**: merge decision.
- Complete/Cancelled → terminal state; **no S7 equivalent found.** No rollout ramp, kill condition, or post-deploy verification stage is documented; "monitor" appears once in the blog's stage list ("triage, spec, implement, review, verify and monitor") but is not elaborated anywhere in the docs pages fetched.

**Where gates are required versus optional:** Required — spec approval before Building starts (default; policy-editable), and the merge decision (always, "your team's call"). Optional/conditional — clarification questions ("When requirements are unclear or a review finding is ambiguous, the foreman asks instead of guessing," how-factories-work/), and Triage/Planning stages themselves are skippable by the foreman when it judges the request already sufficiently defined. Notably: "The first two [gates] are workflow policy, written into the foreman's instructions; edit them to change when the factory checks in" — meaning even the mandatory-sounding spec-approval gate is a configurable default, not a structural guarantee.

**Patterns found.**
- Seven-stage linear flow with foreman-driven skip logic — docs.warp.dev/factories/how-factories-work/, vendor doc.
- Spec-approval gate is policy, not hard-coded — same source, direct quote above.
- No S7-equivalent rollout/verification stage documented — absence noted across all five fetched pages.

**Evidence quality.** Primary, vendor documentation. Descriptive, not measured. Single source.

**Transfer to an agent.** The Warp model confirms that "spec approval" and "merge approval" are the two gates vendors converge on treating as non-negotiable defaults, which supports keeping S3 and S6 as the charter's two hard gates. The absence of a rollout/verification stage is a gap the charter's S7 already fills that Warp does not — worth noting as a differentiator, not something to copy.

**Gaps.** No disclosed criteria for skipping Triage or Planning ("when the request already explains the problem" is not defined); no rollout, flag-ramp, or kill-condition mechanism found in any fetched page.

---

### RQ-F-3. Human interaction model.

**Answer.** Warp routes questions and approvals through the foreman agent, which is described as talking "to the requester directly" and asking only "when requirements are unclear or a review finding is ambiguous... instead of guessing" — implying a threshold-based, not always-ask, policy, though no explicit ranking, batching, or queuing mechanism is documented. Spec approval and merge approval are named as decision points delivered presumably through the requester's own channel (Slack, Linear, Jira are listed as intake integrations) and through GitHub PRs respectively, but the docs never describe a dedicated question queue, batching rule, or attention-budgeting mechanism comparable to the charter's section 6.

**Patterns found.**
- "When requirements are unclear or a review finding is ambiguous, the foreman asks instead of guessing" — docs.warp.dev/factories/how-factories-work/, vendor doc. No stated threshold for "unclear," no ranking of multiple questions, no default-proposal mechanism disclosed.
- Foreman "keeps the requester informed" and "handles human questions by routing them back to relevant agents" — docs.warp.dev/factories/factory-agents/, vendor doc.
- Intake integrations (Slack, GitHub, GitLab, Linear, Jira, webhooks) are the plausible delivery channels but no page states which channel carries which interaction type, nor whether questions are batched per work item or delivered as they arise.

**Evidence quality.** Primary, vendor documentation, but thin: no page dedicated to the question/approval UX was found or fetchable (the `/factory-api-and-mcp/` and `/dashboard-and-measurement/` pages 404'd). Descriptive only, not measured. Single source, and incomplete even within that source.

**Transfer to an agent.** The "ask instead of guessing, but only when ambiguous" framing is directionally consistent with the charter's question gate (P4, section 6), but Warp discloses no batching, ranking, or default-proposal mechanism to borrow. Proposed rule: do not adopt Warp's model as evidence for a specific queuing design; the charter's more detailed batching-and-rounds rule (already synthesized from other sources) remains the stronger design.

**Gaps.** No description found of question batching, ranking, delivery cadence, or whether the agent proposes a default alongside a question — a materially thinner account than the charter's own section 6. `/factories/factory-api-and-mcp/` and `/factories/dashboard-and-measurement/` both returned 404 and could not be checked for interaction-surface detail.

---

### RQ-F-4. Verification and judgment.

**Answer.** Verification is split between an implementation-time check (the Implement agent adds "tests and validation" and, per the blog, uses "computer use to click through a dropdown it built to verify the change works end-to-end," with a video saved to the PR description) and a post-implementation Review agent whose verdict is explicitly "advisory" and can send the change back to Building via a "Revision needed?" loop. Quality judgment beyond pass/fail tests is handled by "scorers" — user-authored, LLM-based evaluation rubrics defined as code (`scorers/` directory) that "grade completed runs against criteria you write," feeding a "Self-improvement" mechanism that "turns repeated failures into follow-up work the factory proposes for review," including proposed edits to the factory's own definition files. Failure at the Review stage loops back to Building for revision; failure detected by scorers becomes a follow-up work item, not a blocking gate.

**Patterns found.**
- "It employs computer use to click through a dropdown it built to verify the change works end-to-end" and videos "saved to PR descriptions for human review" — warp.dev/blog, vendor blog. No figure on how often this verification method is used or its accuracy.
- Review agent "independently examines the change" and gives a verdict that "is advisory," feeding a revision loop back to Building — docs.warp.dev/factories/how-factories-work/, vendor doc.
- "Scorers: LLM-based evaluation rubrics for quality measurement," authored by the user, stored as code — docs.warp.dev/factories/factory-as-code/, vendor doc.
- "Scorers grade completed runs against criteria you write, and Self-improvement groups the failures they flag into follow-up runs that propose fixes — to the application code or to the factory's own definition" — search-snippet recovery from a 404'd docs page (docs.warp.dev/factories/factory-api-and-mcp/ or an adjacent scorers page), attributed as vendor documentation but not independently re-fetched; treat with lower confidence than the directly fetched pages.

**Evidence quality.** Primary, vendor documentation and blog. Descriptive, not measured — no pass/fail rate, no precision/recall for the review agent or scorers, no figure on how often the revision loop triggers. One claim (scorers quote) recovered only via search snippet, not direct fetch, and is flagged as such per the rules for answering.

**Transfer to an agent.** "Scorers as versioned, user-authored code, separate from the agent prompts" is a transferable pattern: it operationalises P2 (rubrics are the product) as an artefact class distinct from agent instructions. Proposed rubric line: store judgment rubrics (test-quality, scope, style) as their own versioned files, authored and owned by humans, not embedded in agent prompts — mirrors Warp's `scorers/` directory. No evidence, however, on how Warp calibrates these scorers to human judgment or prevents the authoring model from grading its own output (the charter's headline 6 concern) — not addressed anywhere in the fetched pages.

**Gaps.** No precision, false-positive, or keep-rate figures for scorers or the review agent. No description of scorer calibration or judge independence (self-grading risk unaddressed). Dashboard/measurement page (which likely holds relevant figures) 404'd and could not be substituted within budget.

---

### RQ-F-5. Context and memory.

**Answer.** Warp gathers codebase context primarily through the Triage agent, which "researches and defines scope" per work item, and through per-agent "skills, MCPs, and memories" configured in the factory-as-code definition; "memories" are named as a persisted resource agents draw on, but the factory-as-code page states explicitly that only configuration (agents, automations, runners, scorers, skills, webhooks) is versioned as code, while "work items, runs, and metrics live in the web app and are never written to the files" — meaning there is no disclosed mechanism by which something learned in one run automatically updates the versioned agent definitions for the next run, aside from the Self-improvement feature proposing (not automatically applying) edits to the factory's own definition.

**Patterns found.**
- "Every factory is defined by files: a `factory.yaml` plus directories of agents, automations, runners, scorers, skills, and webhooks, versioned in a Git repository. The files are the source of truth" — docs.warp.dev/factories/factory-as-code/, vendor doc.
- "Definition files describe how the factory is configured, not what it is doing: work items, runs, and metrics live in the web app and are never written to the files" — same source. This is the key fact for RQ-F-5: run-level learning is not automatically persisted into the versioned definition.
- "Self-improvement... turns repeated failures into follow-up work the factory proposes for review" (recovered via search snippet, lower confidence) — implies a human-mediated path from run failures back into factory config, i.e. memory update requires a human to accept a proposed change, not an automatic loop.
- "Custom agents receive specific skills, MCPs, and memories tailored for their roles" — warp.dev/blog, vendor blog. No further detail on what "memories" contain, how they are scoped, or how they age.

**Evidence quality.** Primary, vendor documentation, but the memory mechanism itself is thinly documented — one sentence in the blog, no dedicated page found. Descriptive, not measured. Single source; internally the "as code" doc and the blog are in tension (blog implies agents "access" memories fluidly; docs say only configuration files are versioned, with runs/metrics external and ephemeral in the code sense).

**Transfer to an agent.** The clean separation of "static configuration as versioned code" from "run/work-item state in a database" maps directly onto the charter's D7 (SQLite plus markdown, factory memory as decisions/rubrics/catalogue/per-ticket state). Proposed rule: keep rubrics, agent instructions, and skills as versioned files (as Warp does), and keep per-ticket run state in a database, with any promotion from run learning to versioned rubric requiring an explicit human-reviewed change — matches Warp's Self-improvement-proposes-not-applies pattern and is directly reusable regardless of runtime.

**Gaps.** No detail on what "memories" store, their format, scope (per-agent, per-repo, per-factory), or freshness/rot handling — a direct hole relative to the charter's D7 and the synthesis's proposed FM-17 (silent memory rot). No description found of how Triage-stage context findings are reused by later stages within the same run, let alone across runs.

---

### RQ-F-6. Evidence.

**Answer.** Warp discloses very few concrete figures, and every one found is either an unattributed vendor claim or an illustrative sample. The clearest: "we're automating about 30% of our tasks through our factories" (warp.dev/blog) — a self-reported, undated, undenominated internal usage figure with no methodology. A sample dashboard screenshot in the blog shows "$57.55 cost per PR, 93% code quality, and 96% efficiency" — explicitly labelled here as illustrative/sample data, not a disclosed measurement from a real deployment, since no source repo, ticket count, or measurement definition accompanies it.

**Patterns found.**
- "automating about 30% of our tasks through our factories" — warp.dev/blog, vendor blog, self-reported, no denominator (tasks of what kind, over what period, measured how) disclosed.
- "$57.55 cost per PR, 93% code quality, and 96% efficiency" — warp.dev/blog, vendor blog, presented as a sample metrics dashboard image; treat as a vendor illustration, not a customer or production measurement. "Code quality" and "efficiency" are undefined percentages with no stated formula.
- The Dashboard & Measurement docs page, which likely defines these metrics precisely, returned 404 and could not be substituted within the search budget — a material gap for this question.

**Evidence quality.** Primary source (vendor's own blog) but the figures themselves are vendor claims with no independent verification, no denominator disclosed for the 30% figure, and explicit sample-data framing for the cost/quality/efficiency numbers. Not measured in any externally checkable sense. Single source.

**Transfer to an agent.** None of these figures are usable as calibration targets for the charter's success measures (section 8); they are marketing-adjacent illustrations, not methodology-disclosed measurements, and should not be cited as evidence of factory effectiveness. Proposed rule: the charter's own instrumentation (section 8) must define cost-per-ticket, defect, and revision metrics with explicit denominators, since vendor examples like Warp's do not supply a reusable measurement definition.

**Gaps.** No methodology for "30% of tasks automated" (denominator, task definition, time window). No formula for "code quality" or "efficiency" percentages. Dashboard/measurement docs page, the most likely source of a real definition, was not fetchable (404) within budget.

---

### RQ-F-7. Named failure modes.

**Answer.** Warp names two problems with the pre-factory status quo (uncoordinated interactive coding agents), not failure modes of the factory itself: unclear ROI, and a "governance nightmare" from unmanaged, per-user agent installs. Within the factory design, the only named failure-handling mechanism is the Review-stage "revision needed" loop (agent-detected issues sent back to Building) and Self-improvement (repeated scorer failures become proposed follow-up work). No catalogue of specific failure symptoms (e.g., scope creep, filler tests, missing comments, contract drift) is published.

**Patterns found and FM mapping.**
- "ROI measurement uncertainty: it's unclear if they are worth the cost" of interactive agents — warp.dev/blog. Not a factory-stage failure; a pre-factory market problem. No FM match; closest is the charter's section 8 "no throughput optimization" concern but this is about ROI of ad hoc agent use, not a pipeline failure — **no catalogue entry**.
- "Governance nightmare: every user installs a bespoke coding agent that runs on their laptop... security holes when agents go off the rails" — warp.dev/blog. This is closest to an infrastructure/access-control concern, not covered by FM-01 to FM-18 (which are pipeline-judgment failures, not fleet-governance failures) — **no catalogue entry**; arguably adjacent to D8/D9 (MCP access, run-on-engineer-machine) rather than a failure mode.
- Review agent's "revision needed" loop implies undetected implementation defects are the expected failure to correct, but no named symptom (filler tests, missing scenarios, style drift) is disclosed — cannot be mapped to FM-01, FM-03, FM-11, FM-12, or FM-13 specifically; Warp does not name which defect categories the review agent checks for.
- Self-improvement "turns repeated failures into follow-up work" — implies recurring failures exist but does not name them, so no specific FM mapping is possible.

**Failures with no catalogue entry:** ROI uncertainty of ungoverned agent use, and the "governance nightmare" of per-user unmanaged agent installs and associated security exposure — both organizational/fleet-management concerns outside FM-01 to FM-18's scope (which is about judgment and process failures within a single change), and also outside the proposed FM-15–FM-18. This suggests a possible gap in the catalogue for multi-agent fleet governance/security, though it is arguably out of scope for a single-engineer factory per D9.

**Evidence quality.** Primary, vendor blog. Descriptive, not measured — no frequency, cost, or incident data behind either named problem. Single source.

**Transfer to an agent.** The two named problems (ROI opacity, ungoverned fleet installs) are largely inapplicable to a single-engineer, single-machine factory (D9), since there is no fleet to govern. Not proposed for the catalogue. The revision-loop pattern (agent review sends work back to implementation) is already implicit in the charter's S5→S4 relationship and needs no new entry.

**Gaps.** No specific defect taxonomy disclosed for what the Review agent or scorers actually check; cannot confirm or deny coverage of FM-01 through FM-13 at the mechanism level.

---

### RQ-F-8. Delta against the synthesis — ten headline findings.

1. **Attention constraint (P1).** **Untouched.** Warp's "governance nightmare" quote gestures at attention/oversight cost of many ungoverned agents but does not discuss review load, synthesis layers, or parallel-agent attention economics as the synthesis's headline 1 does.
2. **Human review catches few defects / agent-only review worse.** **Untouched.** Warp's Review agent verdict is explicitly "advisory" and merge is always a human call, which is consistent with not letting agent review substitute for human review, but Warp presents no data on defect-catch rates or merge-rate comparisons; no confirmation or contradiction, just silence.
3. **Change size is the strongest lever.** **Untouched.** No mention of diff size, LOC thresholds, or size-linked review time anywhere in the fetched pages.
4. **Question triage has a research base / convergent escalation rule.** **Partially touched, weakly.** "The foreman asks instead of guessing" when "requirements are unclear or a review finding is ambiguous" is directionally consistent with escalate-only-when-consequential, but Warp discloses no expected-value-of-information ranking, no two-option-with-default format, and no measured acceptance rate — too thin to count as confirming; call it **untouched at the evidentiary level**, consistent only in framing.
5. **Completeness can be checked mechanically (EARS+SMT).** **Untouched.** No mention of EARS, formalisation, or any completeness-check mechanism for specs; the Spec agent's output is "criteria for validating the change" with no disclosed completeness test.
6. **Rubrics have operating requirements; field has none to lend.** **Partially confirmed, new data point.** Warp's "scorers" are exactly the kind of rubric artefact the synthesis says the field lacks — user-authored, versioned, LLM-based. This is a new instance of a vendor building the rubric-as-code pattern the synthesis calls for, but Warp discloses no calibration methodology, no κ figures, and no self-grading safeguard — so it neither confirms nor contradicts headline 6's claim that no scored rubric exists in the wild; it is a previously undocumented existence proof of the pattern without the calibration evidence the synthesis says is missing.
7. **Contract drift predicts failure.** **Untouched.** No mention of contracts, interface drift, or agent-extending-agent-code anywhere in the fetched pages.
8. **FM-09 wording / interruption cost.** **Untouched.** No discussion of interruption, refocus time, or resumption cost.
9. **Formal approval buys no stability (DORA).** **Partially touched, ambiguous.** Warp's default design keeps exactly "one named human decision" at spec and at merge (matching the synthesis's reframing of D4), and explicitly makes even the spec gate a configurable policy rather than a standing board — consistent with, not contradicting, headline 9. No quantitative DORA-style data offered, so this is directional agreement, not confirmation by new evidence.
10. **The factory must measure what nobody has.** **Confirmed by omission.** Warp's own dashboard/measurement claims (30% automation, sample "$57.55/PR, 93% quality, 96% efficiency") are exactly the kind of unmeasured, undenominated, self-reported figures the synthesis warns the field offers instead of real instrumentation — reinforcing headline 10's point that published figures in this space lack methodology, rather than contradicting it.

**Evidence quality.** Primary, vendor documentation and blog, evaluated against the synthesis's own grading. All comparisons above are the researcher's judgment applied to vendor text, not new independent measurement.

**Transfer to an agent.** None of the ten headlines are contradicted by Warp; several are simply not addressed. The one genuinely new data point is the existence of "scorers" as a rubric-as-code artefact, which strengthens the case for the charter's P2/D7 design (store rubrics as versioned files) without adding calibration evidence.

**Gaps.** No data behind headlines 2, 3, 5, 7, 8. Headlines 4 and 9 only touched at the framing level, not the evidentiary level.

---

### RQ-F-9. Transfer.

**Answer.** Warp Factories is a fully hosted, cloud-run product with its own orchestration ("foreman"), its own agent runtime, its own YAML/skills/scorers definition format, and its own PR/dashboard surface — it is not a drop-in candidate for the charter's D5 (interchangeable local runtimes: Cursor SDK, Cursor CLI, Claude CLI) because those are execution engines, while Warp is a full competing factory platform that would replace the entire pipeline, not slot into one stage of it. Adopting Warp would mean lock-in to its hosted control plane, its `factory.yaml`/agents/automations/runners/scorers/skills file format, its own state store (work items, runs, metrics living in Warp's web app, explicitly not in the versioned files), and its own MCP/API surface for external analysis — directly duplicating the charter's D7 (local SQLite plus markdown factory memory), D8 (agent-to-external-system access via MCP, which Warp also does but through its own Factory MCP layer), and D9 (runs on the engineer's machine; Warp instead runs in Warp's cloud, with self-hosting only on Enterprise plans, per the docs overview page).

**Patterns found.**
- Warp explicitly separates versioned configuration from runtime state, with state living in "the web app," not in files a user controls — docs.warp.dev/factories/factory-as-code/, vendor doc. This is the opposite locus of control from D7 (local SQLite/markdown, engineer-owned).
- "Self-hosting available for Enterprise plans" (from docs.warp.dev/factories overview fetch) — confirms default hosting is Warp's cloud, contradicting D9's engineer-machine-first design unless the Enterprise self-host tier is used, about which no further detail was fetched.
- "The Warp Agent CLI runs the Warp Agent in any terminal and exchanges work with a factory through the Factory MCP" (search-snippet recovery, lower confidence) — suggests Warp's own agent, not Cursor/Claude CLI, is the intended runtime; no evidence Warp supports plugging in Cursor SDK, Cursor CLI, or Claude CLI as alternative execution engines for its agent roles.

**Evidence quality.** Primary, vendor documentation, for the architecture claims; one lower-confidence search-snippet claim for the CLI/MCP relationship, flagged above. Descriptive, not measured.

**Transfer to an agent.** Not a candidate runtime for D5: Warp is a competing whole-factory product, not an interchangeable execution engine to sit under the charter's own orchestration. If adopted, it would replace the charter's entire planned architecture (orchestration, memory store, stage gates, dashboard) rather than filling the D5 slot, and would introduce lock-in to Warp's cloud control plane, file format, and state store — directly conflicting with D7 (local memory) and D9 (engineer-machine execution) as currently decided. The one component worth reusing conceptually, not adopting wholesale, is the "scorers as versioned files separate from agent instructions" pattern (RQ-F-4, RQ-F-5), which is compatible with a local SQLite-plus-markdown design if implemented independently.

**Gaps.** No detail found on what the Enterprise self-hosting option actually relocates (compute only, or also the state store); the two 404'd pages (`factory-api-and-mcp/`, `dashboard-and-measurement/`) most likely would have clarified the MCP integration surface and hosting/pricing model in more depth and could not be fetched within budget.

---

## Sources consulted

- "Introducing Warp Factories - open, flexible infrastructure for building your software factory," https://www.warp.dev/blog/open-infrastructure-for-building-a-software-factory — vendor blog, fetched.
- "Warp Factories overview," https://docs.warp.dev/factories — vendor documentation, fetched.
- "How Warp Factories work," https://docs.warp.dev/factories/how-factories-work/ — vendor documentation, fetched.
- "Factory Agents & Skills," https://docs.warp.dev/factories/factory-agents/ — vendor documentation, fetched.
- "Factory as Code," https://docs.warp.dev/factories/factory-as-code/ — vendor documentation, fetched.
- "Factory API & MCP," https://docs.warp.dev/factories/factory-api-and-mcp/ — vendor documentation, attempted fetch returned 404; partial content recovered via web search snippet only, lower confidence, flagged inline.
- "Dashboard & Measurement Tools," https://docs.warp.dev/factories/dashboard-and-measurement/ — vendor documentation, attempted fetch returned 404; no substitute found within budget.
- Web search: "docs.warp.dev factories MCP API scorers" — used only to recover snippet content after two 404s, per the rules for answering.

## Cross-references

- RQ-F-2, RQ-F-3 touch **R8 (RQ-X-3, RQ-X-4)** on multi-agent supervision and propose-a-default patterns; Warp adds a thin, unmeasured data point (foreman "asks instead of guessing") that does not strengthen R8's evidence base.
- RQ-F-4, RQ-F-5 touch **R3/R5 (RQ-S3-2, RQ-S5-1, RQ-S5-3)** on rubrics and LLM-as-judge; Warp's "scorers" is a new existence-proof artefact for synthesis headline 6 but adds no calibration evidence.
- RQ-F-5 touches **R8 (RQ-X-7)** on memory freshness/rot (D7); Warp's memory mechanism is undocumented in enough depth to inform FM-17.
- RQ-F-6 touches **synthesis section 5** ("what the field has not measured"); Warp's undenominated 30%-automation and sample dashboard figures are a further instance of the measurement gap the synthesis identifies, not a resolution of it.
- RQ-F-9 touches **charter D5, D7, D8, D9** directly, and should be read alongside **R9a (Uber)**, **R9b (Ona)**, and **R9c (Osmani)** for a comparative read on how much of each vendor/practitioner account is architecture-agnostic versus platform-locked.
