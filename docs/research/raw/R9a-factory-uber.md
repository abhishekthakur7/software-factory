# R9a — Factory implementations: Uber

| | |
|---|---|
| Packet | R9a Factory implementations, Uber |
| Sources | Primary: Uber Engineering Blog, "Efficient software factory" (fetched at `https://www.uber.com/en-US/blog/efficient-software-factory/`); Secondary: Port newsletter, "How Uber built a software factory" (`https://newsletter.port.io/p/how-uber-built-a-software-factory`) |
| Date | 2026-09-03 |
| Fetch status | Primary: succeeded via `https://www.uber.com/en-US/blog/efficient-software-factory/` (the `/in/en/` URL specified in the task prompt was not attempted directly; `en-US` returned full content on first try, so the region-blocked fallback path was not exercised). Secondary: succeeded, `https://newsletter.port.io/p/how-uber-built-a-software-factory` fetched directly. No additional Uber source (talk, paper) was fetched beyond the one YouTube conference talk the primary blog itself references ("AI Engineer 2026" talk, linked but not fetched — video, out of scope for a text research pass). |

Note on method: content was extracted by an intermediate summarising model (the WebFetch tool), not read verbatim by the researcher. Numbers below are as returned by that extraction; where the two sources disagree on a figure that should be identical (skills count, context-graph size), this is flagged rather than resolved, and the primary is preferred per the packet rules.

---

### RQ-F-1. Definition and scope.

**Answer.** Uber does not define "software factory" in the engineering blog itself in a single sentence; the term is used descriptively as an operating model where AI agents are "embedded in every phase of software development." The secondary source supplies the explicit definition the primary implies: "an operating model where your software development lifecycle runs as a production line, with agents doing the work at each stage and engineers designing and running the line." The unit of work is the pull request and, underneath it, the "agent skill execution" (a discrete automated task run through Uber's skill registry); sessions are the interactive unit for human-initiated agent work. Inputs are code changes, PRs, CI failures, bugs, and on-call alerts, contextualised through an internal knowledge graph; outputs are merged PRs, completed reviews, triaged alerts, and completed maintenance tasks. Automated activities span code review, self-healing CI, PR completion with visual validation, on-call triage, debugging, and maintenance; human activities are reviews/escalations, manager sign-off on cost-tier upgrades, and per-engineer judgment on whether a task is worth automating (task ROI).

**Patterns found.**
- Software factory as production-line metaphor with agents at each stage and engineers "designing and running the line" — Port newsletter, `https://newsletter.port.io/p/how-uber-built-a-software-factory`, secondary. No measured figure; definitional claim.
- >70% of PRs "attributed to local or cloud agents" — Uber blog, primary, self-reported, denominator = total Uber pull requests (period unstated).
- Skill registry as the unit of automated work: "3,600 agent skills across the software development life cycle, and executed more than 30K agent skill executions per day" (primary) versus "2,500 curated skills in registry" and "20,000 skill runs daily" (secondary). The two disagree by roughly 30–50%; primary preferred, but neither states a measurement date, so the difference may simply reflect different snapshots in a fast-growing rollout rather than an error.

**Evidence quality.** Primary is a company engineering blog (grade B/A- style, self-reported numbers, no external audit). Secondary is single-source commentary on the same primary, adds an explicit definitional sentence not found verbatim in the primary extraction, and disagrees with the primary on two headline counts. Only one independent account exists; nothing corroborates either set of numbers.

**Transfer to an agent.** The "production line with agents at each stage, engineers running the line" framing is directly usable as the charter's own factory definition and is already close to how S0–S7 is structured. Rubric line: define the factory's unit of work explicitly (ticket, not PR — Uber's PR-centric framing is downstream of a different intake shape) and require every stage to declare what enters and leaves it, mirroring section 5 of the charter.

**Gaps.** No single canonical definition sentence was found inside the primary blog itself as fetched; it had to be inferred from usage. Could not verify by reading the raw HTML directly (fetch was via summarising tool).

---

### RQ-F-2. Stage structure and gates.

**Answer.** The primary blog does not describe strict sequential stages; it describes four "layers" of specialisation (most specialised domain tasks, moderate general-SDLC workflows, and most general interactive developer interfaces) plus a scattering of point capabilities (context graph, tool/MCP gateway, model routing, cost monitoring). The secondary source imposes a cleaner five-stage pipeline that the primary content does not explicitly present in that form: Planning → Coding → Inner-loop validation → CI/CD → Maintenance. Where they overlap, the secondary's phase language is a reasonable read of primary capabilities (spec-to-prototype, warm coding environments, self-healing CI, DevOps maintenance skills) but should be treated as the secondary author's structuring, not Uber's own stated pipeline.

**Mapping to S0–S7** (secondary's five-stage read, since the primary does not name stages):
- Planning (spec-to-prototype, prototype approval) → maps loosely across **S1 (context gathering)** and **S2/S3 (requirements/spec)**; no split between requirements clarification and plan the way the charter separates S2 from S3.
- Coding (agent writes in warm environments) → **S4 Implementation**.
- Inner-loop validation (static analysis, visual checks, integration tests) → **S5 Cleanup pass**, partially; also overlaps **S4** self-check.
- CI/CD (self-healing pipeline, code review) → **S5/S6**: self-healing CI is closer to S5 (mechanical gate before humans see it); "code review" in Uber's account is itself agent-performed, which the charter's S6 explicitly reserves for a human decision — this is a divergence, not a mapping (see RQ-F-7 and RQ-F-8, headline 2).
- Maintenance (DevOps automation for recurring tasks) → has **no equivalent** in S0–S7; the charter's stage map is ticket-scoped and does not model standing post-rollout automated maintenance loops as a stage.
- **No equivalent to S0 intake tiering** is described in either source: nothing in either account describes risk-tiering a change before work starts.
- **No equivalent to S7 rollout/verification with named kill conditions** is described; "self-healing CI" and "draft PR review" are the closest analogues but do not describe canary/flag-ramp mechanics.

**Human decision points named:** prototype approval before handoff to the coding agent; draft PR review by a human reviewer (with "pre-flight checks displayed"); a product-level "should we build this" decision, described as newly foregrounded now that "can we" is cheap; explicit team enrolment into maintenance automation; manager sign-off for spend-tier upgrades.

**Patterns found.**
- Four-layer specialisation model (not a stage pipeline) — Uber blog, primary, self-reported, no figures attached to the layer boundaries themselves.
- Five-stage "production line" reading — Port newsletter, secondary, its own synthesis of primary material.
- "Pre-flight checks displayed" ahead of human PR review — Port newsletter, secondary; no primary confirmation found in the extraction.

**Evidence quality.** Weak on stage structure specifically: the primary source is organised by capability/layer, not by pipeline stage, so the secondary's five-stage frame is an interpretive overlay, not something Uber itself asserts in those words. Single-source for the pipeline framing.

**Transfer to an agent.** Uber's "layers of specialisation" is a useful orthogonal cut (which agent handles how domain-specific a task is) that the charter's stage map does not currently have; it could sit alongside S0–S7 rather than replace it. The clean transferable rule: name explicitly which stages have no equivalent in a source before assuming parity — done above for S0 tiering, S7 kill-condition rollout, and standing maintenance.

**Gaps.** No description in either source of a risk-tiering gate at intake analogous to S0, and no description of automatic rollback/kill conditions analogous to S7. Searched within the fetched content only; did not run additional searches for a separate Uber post specifically on CI/CD gating (out of the packet's search budget for this URL-specific packet).

---

### RQ-F-3. Human interaction model.

**Answer.** Uber's account describes attention management almost entirely through passive visibility rather than an explicit queue: a live "status line" showing spend per harness, Slack nudges at 50/80/100% of expected spend, and a "session analysis dashboard" that flags 16 anti-patterns after the fact. Neither source describes batching of questions, ranking by information value, or a formal interrupt-versus-queue design comparable to the charter's section 6 contract. The one explicit approval flow named is manager sign-off for spend-tier upgrades, described as fast ("quick propagation"), and human review/escalation of automated work, with no detail on how those reach a person (interrupt, queue, or dashboard pull).

**Patterns found.**
- Real-time cost visibility (status line, threshold-triggered Slack nudges at 50/80/100%) as the attention mechanism, rather than question batching — Uber blog, primary, self-reported, no denominator for effectiveness.
- Post-hoc session dashboard flagging "16 distinct anti-patterns" — Uber blog, primary, self-reported; no precision/recall figure given for the flagging.
- "Draft PR review" with "pre-flight checks displayed" to the human reviewer — Port newsletter, secondary; the closest either source comes to a structured review packet, but no detail on its contents or ordering.

**Evidence quality.** Primary and secondary agree that the human-facing surface is dashboards/notifications rather than a structured question queue; neither publishes acceptance rates, resolution rates, or resumption cost. Single-source per claim; weak — this is the least-detailed part of both accounts relative to what the charter's section 6 specifies.

**Transfer to an agent.** Only weakly transferable: Uber's model optimises for cost/spend visibility, not for question quality or defaults, which is the opposite emphasis from the charter's P1/section 6. Rubric line: do not adopt Uber's dashboard-only pattern as the primary interaction surface; retain the charter's gate-plus-rounds question design, since Uber publishes no evidence that dashboard-only surfacing avoids FM-07 or FM-09.

**Gaps.** No description in either source of question ranking, default proposals, or a queue with rounds. No published acceptance/override rate for any agent-proposed default. Not found: any statement of how many concurrent tickets/PRs one engineer supervises at Uber (relevant to FM-09).

---

### RQ-F-4. Verification and judgment.

**Answer.** Mechanical checks named are code review (performed by agents, evaluated against an internal "Uber SWE Benchmark" built from real PRs "with known bugs" graded easy/medium/hard), self-healing CI that "repairs common failures autonomously," static analysis and visual validation (screenshot-based) in the inner loop, and a small-model safety/policy layer ("5 smaller models handle safety and policy" in under 100ms) sitting in front of the LLM gateway. Checks are authored internally (Uber's own benchmark, own anti-pattern taxonomy) and run continuously (real-time anti-pattern monitoring) plus on a weekly/monthly metrics cadence. On failure, the described behaviour is model-switching / re-routing and, for CI, autonomous repair; deeper failures escalate to "human reviews/escalations," without detail on the trigger. Neither source describes a rubric for abstraction, scope, style, or debt; RQ-F-4's second half — a judgment rubric — returned nothing in either account.

**Patterns found.**
- Internal "Uber SWE Benchmark" from real PRs graded by difficulty, used to evaluate/select models — Uber blog, primary, self-reported, no published precision/recall numbers, no public dataset.
- Self-healing CI repairing "common failures autonomously" — Uber blog, primary, self-reported, no failure-rate or repair-success figure given.
- 5-model safety/policy layer at <100ms — Uber blog, primary, self-reported, measured latency figure but no accuracy/false-positive rate.
- No abstraction/scope/style/debt rubric found in either source — absence noted, not found.

**Evidence quality.** Primary only; single-sourced for every mechanism. All figures are self-reported with no external validation, no denominators for accuracy claims (only latency and count figures are given a denominator).

**Transfer to an agent.** The benchmark-driven model selection and the layered safety-check pattern (cheap models gate before expensive ones act) transfer well as a pipeline rule: run a fast, cheap policy check before invoking a large model, and maintain an internal benchmark of real graded examples rather than relying on public benchmarks. What does not transfer: nothing here substitutes for the charter's planned S3/S5 judgment rubrics (abstraction, scope, style, debt), since Uber publishes none.

**Gaps.** No published rubric for abstraction, scope, style, or tech debt judgment. No precision/recall for the SWE benchmark or the anti-pattern detector. No description of what happens when self-healing CI fails to heal.

---

### RQ-F-5. Context and memory.

**Answer.** Uber's central context mechanism is the "AI Context Graph," described in the primary as containing 24 million nodes and 80 million edges across 86 node types and 117 edge types, integrating over 30 internal systems (services, teams, incident logs, PRs, design docs, deployments, datasets, table-usage queries). The secondary reports a different, larger snapshot — 40 million context-graph entries across 150 node/edge types — which, given no date is attached to either figure, most plausibly reflects graph growth over time rather than a contradiction, but this cannot be confirmed from the material fetched. Persistence across units of work is handled by the graph itself (durable, queried per session) plus prompt caching with stated TTLs of 5 minutes for subagents and 1 hour for the main thread; a graph query is reported to complete in 38 seconds versus 20 minutes 9 seconds without the graph for an unspecified example task.

**Patterns found.**
- AI Context Graph, 24M nodes / 80M edges, 86 node types / 117 edge types, 30+ integrated systems — Uber blog, primary, self-reported.
- AI Context Graph, "40 million" entries, 150 node/edge types — Port newsletter, secondary; conflicts with the primary's count, no timestamp on either to reconcile.
- Prompt caching: 5-minute TTL for subagents, 1-hour TTL for main thread — Uber blog, primary, self-reported.
- Graph-assisted query time 38 seconds vs 20m09s without the graph — Uber blog, primary, self-reported, single example, no denominator (n=1 stated case, not a distribution).

**Evidence quality.** Primary and secondary disagree on the graph's size by roughly 1.7x with no way to reconcile from the fetched content; this is flagged rather than resolved, primary preferred per rule 1 (rules for answering say prefer primary on disagreement). Both are self-reported, single-organisation, no external audit.

**Transfer to an agent.** The core transferable idea — a queryable graph over org systems that persists across tickets and is cheaper to query than ad hoc discovery (38s vs 20m in the one reported case) — directly supports the charter's D7 (local SQLite/markdown memory) and RQ-S1-4/RQ-X-7 concerns about what should be standing versus discovered per task. Rubric line: maintain a persistent, queryable index of org context (services, incidents, docs) rather than re-discovering it per ticket, but scale the implementation down; Uber's graph is enterprise infrastructure, not something a single-engineer factory can replicate at that scale (see RQ-F-9).

**Gaps.** No description of how the context graph is kept fresh (staleness policy), a gap directly relevant to the charter's FM-17 (proposed) silent memory rot. No node/edge-type breakdown beyond raw counts. No accuracy figure for what the graph returns.

---

### RQ-F-6. Evidence.

**Answer.** Below, every number found, source, denominator, and classification (measured / self-reported / claim). All figures below are self-reported by Uber (or by the secondary summarising Uber) with no independent audit found; none are third-party measured. "Measured" here means Uber states it as an internally instrumented figure rather than a marketing round number; none rise to independently verified.

| Metric | Value | Denominator / period | Source | Classification |
|---|---|---|---|---|
| PRs attributed to agents | >70% | total Uber pull requests, period unstated | Primary | Self-reported |
| Agent skills in registry | 3,600 | across the SDLC, snapshot date unstated | Primary | Self-reported |
| Agent skill executions | >30,000/day | daily count, date unstated | Primary | Self-reported |
| Weekly active users growth | 7x | Feb–Aug 2026 | Primary | Self-reported |
| Weekly agentic requests growth | 9.4x | Feb–Aug 2026 | Primary | Self-reported |
| Cost per 1,000 requests | −34% | reduction, "peak to Aug" (2026) | Primary | Self-reported |
| Cost per session | −52% | reduction, June–Aug 2026 | Primary | Self-reported |
| Code-mode token savings, simple query | 55% | vs standard tool-use tokens, one example ("SELECT 1") | Primary | Self-reported, n=1 example |
| Code-mode token savings, wide table | ~100% | vs standard tool-use tokens, one example | Primary | Self-reported, n=1 example |
| Prompt cache hit rate | 95% | one example user session | Primary | Self-reported, n=1 example |
| Context graph query time | 38 seconds vs 20m09s | one example task, with vs without graph | Primary | Self-reported, n=1 example |
| Context graph size | 24M nodes / 80M edges, 86 node types / 117 edge types | integrating 30+ systems | Primary | Self-reported |
| Context graph size (secondary figure) | 40M entries, 150 node/edge types | — | Secondary | Self-reported, conflicts with primary |
| MCP tools accessible | 1,000+ | gateway-routed tools | Primary / Secondary (agree) | Self-reported |
| Curated skills in registry (secondary figure) | 2,500 | — | Secondary | Self-reported, conflicts with primary's 3,600 |
| Skill runs daily (secondary figure) | 20,000 | — | Secondary | Self-reported, conflicts with primary's 30K |
| Lines of code per engineer, YoY | 2x | year-over-year, period unstated | Secondary | Self-reported |
| Model requests through LLM gateway | 100 million/day | daily | Secondary | Self-reported |
| Token usage reduction | 40% | unstated denominator/period | Secondary | Self-reported |
| Team-specific assistant versions | 300 | count | Secondary | Self-reported |
| Safety/policy check latency | <100ms | per check, via 5 smaller models | Primary | Self-reported |

**Patterns found.** No figure in either source carries an external audit, a confidence interval, or a comparison group (e.g., no control period, no A/B). Growth figures (7x, 9.4x, cost reductions) are given time windows, which is better denominator discipline than the point-in-time counts (skills, graph size), which carry no date at all — this is why the primary/secondary disagreements on skill count and graph size cannot be resolved as either a genuine discrepancy or simple time drift.

**Evidence quality.** All self-reported, single-organisation, no third-party corroboration found. This is weaker evidence than most packets in the corpus (contrast synthesis.md's grade-A findings from Google/Microsoft mining studies with denominators of 570 comments or 9 million changes); Uber's factory account should be graded C for its numeric claims specifically, B for its qualitative architecture description.

**Transfer to an agent.** None of these figures are directly reusable as targets for a single-engineer factory; they describe fleet-scale economics (token cost, gateway throughput) that do not apply at one-engineer, one-machine scale. Rubric line: do not adopt Uber's percentages as benchmarks; instead adopt its measurement *discipline* pattern — report growth with a stated time window — for the charter's own section 8 instrumentation.

**Gaps.** No defect rate, no revert rate despite "revert rates" being named as a tracked category in the primary extraction (value not given), no MTTR figure despite MTTR being named as tracked, no reviewer-time figure, no production-incident count.

---

### RQ-F-7. Named failure modes.

**Answer.** Both sources name several failure modes, mapped below to the charter catalogue or the proposed FM-15–FM-18. None are named using the charter's language, so mapping is by symptom.

| Uber-named failure | Mapping | Notes |
|---|---|---|
| "Ungrounded agent fails slowly rather than cheaply, repeatedly sending an expanding context window" | No direct FM match; closest is **FM-17 (proposed, silent memory rot)** in spirit — an agent operating without grounded context degrades silently — but Uber's failure is about missing grounding causing runaway cost/loops, not stale instructions specifically. Also touches **FM-14** (context/impact unknown) at the input side. | Partial mapping only |
| Context bloat from preloading 50K–70K tokens of MCP schemas | No catalogue entry. Closest analogue in spirit to instruction-file bloat findings cited in synthesis.md (RQ-S1-4, FM-03/FM-02 adjacent) but the charter catalogue has no "tool/schema bloat" entry. | **No catalogue entry — a gap** |
| Cache expiration forcing "full-price prefix rebuilds" | No catalogue entry; a cost/performance failure, not a judgment or review failure the FM catalogue covers. | **No catalogue entry** |
| Suboptimal model routing (expensive model for simple task) | No catalogue entry; cost-governance failure, outside FM-01–FM-14's scope (which is about judgment/quality, not spend). | **No catalogue entry** |
| Token exhaustion from tool sprawl (secondary) | Same as MCP schema bloat above — **no catalogue entry**. | |
| Agents pushing broken code to CI prematurely (secondary) | Closest to **FM-05** (scope/quality not held to a gate before reaching a checkpoint) or a precursor to **FM-11** (filler tests / false confidence) if CI is gamed to pass; mapping is approximate since Uber's own account doesn't describe *why* the code was broken. | Approximate mapping |
| Uncontrolled autonomous maintenance loops (secondary) | No direct FM match. Closest in spirit to **FM-09** (parallel/attention fatigue) if the loops consume human escalation attention, but the charter's FM-09 is about human parallel-ticket load, not autonomous-loop runaway. | **No catalogue entry**, adjacent to FM-09 |
| Loss of governance across decentralized agent deployments (secondary) | No catalogue entry; this is an organisational-scale failure (many teams, inconsistent policy) that the charter's single-factory catalogue does not model. | **No catalogue entry** |
| Context fragmentation across 20–30 organisational systems (secondary) | Direct match to **FM-14** (impacted context/services unknown at start) in spirit — fragmented context is exactly what FM-14 names as a risk, and the AI Context Graph is presented as its mitigation. | **FM-14** |

**Failures with no catalogue entry:** the majority of Uber's named failures are cost/infrastructure failures (tool sprawl, cache expiration, model routing, ungoverned decentralised deployment) that fall outside the charter's FM-01–FM-14 and the proposed FM-15–FM-18, all of which are judgment/quality/attention failures. This is a genuine gap the charter's catalogue does not currently cover, because the charter's environment (section 7) commits to a much smaller, single-machine footprint where fleet-scale cost governance may not arise the same way.

**Patterns found.**
- Fleet-scale operational failures (cost, cache, routing, governance) dominate Uber's account, versus the charter's judgment-quality failures — Uber blog and Port newsletter, both self-reported, no measured frequency for any named failure (no "X% of sessions hit this").

**Evidence quality.** Both sources name failures qualitatively with zero frequency or cost data attached (contrast the charter's own catalogue, which flags "TBD" for cost/frequency and expects real incident data) — Uber's account is at the same maturity level, naming failure categories without rates.

**Transfer to an agent.** Not directly transferable to the FM catalogue as written, because Uber's failures are almost entirely about infrastructure economics at a scale the single-engineer factory won't reach. The one clean transfer is context fragmentation → FM-14, reinforcing the existing charter emphasis on declaring impacted-context blockers explicitly.

**Gaps.** No frequency, cost, or example-incident data for any named failure in either source.

---

### RQ-F-8. Delta against the synthesis.

Going through the ten headline findings of `docs/research/synthesis.md` section 1:

1. **Attention constraint externally confirmed.** *Untouched.* Uber's account does not discuss synthesis layers merging multi-agent output for human review, nor does it discuss N-agent-outputs-to-one-human framing. Its human-attention mechanism is dashboards/nudges, not a synthesis layer (see RQ-F-3).

2. **Human review catches few defects; agent-only review measurably worse.** *Touched, ambiguously — leans contradicted in framing, not evidence.* Uber's account states code review is itself performed by agents ("code review" listed under automated activities in the primary; "self-healing pipeline, code review" in the secondary's CI/CD stage), with only "draft PR review" by a human downstream. Neither source reports a defect-catch rate or a merge-rate comparison, so there is no figure to confirm or contradict the 45.20% vs 68.37% merge-rate finding. But the *practice* Uber describes — agent-performed review as a standing pipeline stage, with human review positioned after it as a secondary check — is exactly the pattern synthesis finding 2 warns against (S5 agent pass "never a substitute" for human review), and Uber's account does not caveat this the way the synthesis does. Deciding quote: primary blog, "code review" listed as an automated capability alongside "self-healing CI failures... triaging on-call alerts."

3. **Change size is the strongest measured lever.** *Untouched.* No size/latency/defect-density figures relating to change size appear in either source.

4. **Question triage has a research base and a convergent rule.** *Untouched.* Neither source describes a question-ranking or expected-value-of-information mechanism; the closest is spend-threshold Slack nudges, which are not question triage.

5. **Completeness can be checked mechanically by exactly one known mechanism (EARS+SMT).** *Untouched.* No mention of requirement formalisation or completeness checking in either source; Uber's "planning" stage per the secondary covers spec-to-prototype but no completeness test is described.

6. **Rubrics have operating requirements, and the field has none to lend.** *Confirmed by absence.* Consistent with synthesis finding 6, Uber's account, searched specifically for RQ-F-4, yields no scored rubric for abstraction, scope, style, or debt — reinforcing that no company publishes one.

7. **Contract drift, not complexity, predicts downstream agent failure.** *Untouched.* Neither source discusses contract drift or complexity as a predictor.

8. **FM-09 needs a wording correction (resumption cost, not 23-minute myth).** *Untouched.* No interruption-cost or resumption-time data in either source.

9. **Formal approval buys no stability.** *Loosely touched, consistent.* Uber's described approval points (manager sign-off for spend-tier upgrades "with quick propagation," single draft-PR human review) are lightweight, single-named-approver patterns rather than standing-committee approval, consistent with the synthesis's finding that formal multi-party approval correlates negatively with delivery speed. No DORA-style correlation data appears, though, so this is consistency of practice, not confirming evidence.

10. **The factory must measure what nobody has (plan-review-reduces-rework, decision-record reuse, deviation logs, scope checks).** *Confirmed by absence.* Uber's metrics (RQ-F-6) are entirely about cost, throughput, and adoption — none address whether plans reduce rework, whether decisions get reused, or whether scope is checked. This matches synthesis finding 10's claim that no one measures these.

**Patterns found.** Two headline findings (6 and 10) are reinforced by absence of counter-evidence in a tenth data point; one (2) is in tension with the synthesis's caution about agent-only review, since Uber positions agent review as a standing production-line stage without publishing the defect/merge-rate caveats the synthesis's Microsoft/Google/2026-mining evidence attaches to that practice.

**Evidence quality.** Uber blog and Port newsletter, both self-reported, single organisation; this is one data point against a synthesis built from ~190 sources, so it should not move any of the ten findings, only flag where Uber's stated practice runs ahead of the caution the synthesis draws from stronger evidence.

**Transfer to an agent.** Rubric line: if the factory adopts agent-performed pre-review (as Uber does), keep the charter's existing anti-goal "no replacing human review" explicit and do not let an agent review pass count as the S6 gate — this is exactly the FM-18 (proposed) risk the synthesis already names, and Uber's own account is a live example of the pattern FM-18 warns about, not a counter-example.

**Gaps.** No figures in either source to confirm or contradict findings 1, 3, 4, 5, 7, 8 quantitatively.

---

### RQ-F-9. Transfer.

**Answer.** Very little of Uber's account transfers directly to a single-engineer, brownfield, MCP-connected, one-machine factory; nearly everything described operates at fleet scale (24–40 million node context graph, 100 million daily gateway requests, 3,600+ skills, 300 team-specific assistant configurations) and depends on proprietary infrastructure (an internal context graph integrating 30+ systems, an internal SWE benchmark, an internal MCP gateway routing 1,000+ tools). What transfers is pattern-level, not artefact-level: (1) a persistent, queryable index over org context that beats per-task rediscovery on cost (the 38s-vs-20m figure, if taken as representative, argues strongly for the charter's own D7 local-memory approach rather than re-deriving context each ticket); (2) cheap-check-before-expensive-model layering (the 5-small-model safety/policy gate ahead of the LLM gateway) as a pipeline-design pattern usable even at one-machine scale; (3) benchmark-driven model selection using real graded examples from the org's own history rather than public leaderboards, which a single-engineer factory could do at small scale with its own past tickets.

What does not transfer: the scale-dependent numbers in RQ-F-6 (none are targets a one-engineer setup should aim for or compare itself to); the fleet-governance failures in RQ-F-7 (tool sprawl, decentralised governance loss) that assume many teams and many agents, not one; and the "software factory as production line with agents at every stage including review" framing in RQ-F-2/RQ-F-8, which conflicts with the charter's explicit anti-goal against agent-only review and against treating throughput (PRs, skill executions) as a success measure — Uber's headline metrics are almost entirely throughput and cost metrics, the opposite of the charter's stated "no throughput optimization" anti-goal.

**Patterns found.**
- Persistent context index beating per-task discovery on cost — Uber blog, primary, self-reported, n=1 example (38s vs 20m09s).
- Cheap-model-gates-before-expensive-model as a layering pattern — Uber blog, primary, self-reported, latency figure only (<100ms), no accuracy data.
- Internal benchmark from real graded examples for model selection — Uber blog, primary, self-reported, no published accuracy.

**Evidence quality.** Primary, self-reported, single organisation; the transfer judgment above is the researcher's inference from architecture description, not a claim Uber itself makes about small-scale applicability — Uber's account is written for and about a large fleet.

**Transfer to an agent.** Rubric line: adopt the persistent-context-index and cheap-check-before-expensive-model patterns at whatever scale is appropriate (a local SQLite/markdown index and a fast rules-based or small-model pre-check before invoking a large agent), but explicitly reject Uber's throughput/cost-centric metrics and its agent-performed-review-as-pipeline-stage pattern as inconsistent with the charter's anti-goals.

**Gaps.** No description in either source of how a small team or single engineer might replicate the context graph without the 30+ integrated systems Uber has; no cost figure for building or maintaining such infrastructure at small scale.

---

## Sources consulted

- Uber Engineering Blog, "Efficient software factory," `https://www.uber.com/en-US/blog/efficient-software-factory/` — primary, company engineering blog, fetched successfully.
- Port newsletter, "How Uber built a software factory," `https://newsletter.port.io/p/how-uber-built-a-software-factory` — secondary, single-source commentary on the same primary, fetched successfully.
- (Referenced but not fetched) Uber "AI Engineer 2026" conference talk, linked from the primary blog as `https://youtu.be/17-YSUHo6Lk?si=EbqFAc2UwHX_3wSc` — video, out of scope for a text-based research pass; not fetched.

## Cross-references

- **R1 (Intake and context), RQ-S1-1, RQ-S1-4.** Uber's AI Context Graph is a scaled-up version of the impact-analysis and standing-context-file questions R1 covers; contrast the 38s-vs-20m query-time figure here with R1's build-graph/service-catalogue/trace-derived methods (no accuracy figures found there either).
- **R6 (Human review), RQ-S6-2.** Uber's agent-performed code review, positioned ahead of a human "draft PR review," directly bears on R6's question about reviewing AI-generated code and the synthesis's FM-18 (agent-only review) concern; no defect/merge-rate figures found here to add to R6's evidence base.
- **synthesis.md section 1, findings 2, 6, and 10**, and **section 4, proposed FM-15 to FM-18** — see RQ-F-7 and RQ-F-8 above for the direct mapping; this packet finds FM-18 (agent-only review) is the best-fitting proposed catalogue entry for Uber's own described practice, not merely a hypothetical risk.
- **R8 (Cross-cutting), RQ-X-3.** Uber's human-interaction model (dashboards, spend nudges) is a data point for R8's question on humans supervising multiple concurrent agents, though it addresses cost visibility rather than review-load or question-quality, which is the gap R8 already flags.
