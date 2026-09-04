# Research Questions

| | |
|---|---|
| Status | v0.4 |
| Date | 2026-09-04 |
| Cites | docs/charter.md v0.8 (stages S0 to S7, failure modes FM-01 to FM-22, principles P1 to P11, constraints C1 to C8); docs/prd/prd.md v0.4 and docs/prd/inputs.md v0.6 for packets R10 and R10b |

## Purpose

These are the questions the research pass has to answer, organised by pipeline stage. Researchers answer named questions. They do not browse topics. Each question states which failure modes it serves, what a good answer must contain, and the primary sources to start from.

## Rules for answering

1. **Primary sources first.** Company engineering blogs and practice docs, books by practitioners, peer-reviewed or industry papers, official lab and tool documentation. Secondary commentary is used only to locate primaries. Vendor marketing does not count as evidence.
2. **Every claim carries a URL and a source type** (company practice doc, paper, book, lab doc, practitioner report, secondary).
3. **Every answer ends with a transfer note.** Can an agent apply this pattern, and what would the rubric line or pipeline rule be? If it does not transfer, say why.
4. **Say "no published evidence found" when that is the case.** Do not fill a gap with a plausible generality.
5. **Prefer measured over anecdotal.** Where a source gives numbers (keep rates, review times, defect rates), record them with their denominator.

ID format is `RQ-<stage>-<n>`. Cross-cutting questions are `RQ-X-<n>`.

---

## S0 Intake

**RQ-S0-1.** How do organisations running critical services tier changes by risk before work starts, and what signals feed the tier?
- Serves: FM-14, S0 eligibility decision.
- Good answer: the tiering scheme; the signals used (service tier, modules touched, schema or data change, historical incident density); who assigns the tier; what changes in process per tier.
- Start: Google SRE Book and Workbook chapters on change management; Meta publications on risk-aware deployment; Uber engineering blog; ITIL standard versus normal change classification.

**RQ-S0-2.** What "definition of ready" criteria do mature teams require before a ticket may start, and which of those are machine-checkable?
- Serves: FM-06.
- Good answer: the criteria lists; the artefacts they require (linked design, acceptance criteria present, owner named); the split between checkable and judgment-based.
- Start: Scrum.org and Atlassian definition-of-ready material; INVEST; Google design doc prerequisites.

**RQ-S0-3.** What kinds of change do organisations explicitly exclude from automated or AI-assisted flows, and why?
- Serves: anti-goals, S0.
- Good answer: named exclusions (security-sensitive paths, data migrations, payment code, infrastructure); the reasoning; whether the exclusion is enforced by policy or by tooling.
- Start: Anthropic and OpenAI internal usage reports; GitHub and Google published guardrails for AI coding; financial-services engineering blogs.

## S1 Context gathering

**RQ-S1-1.** How do large organisations determine which services a change impacts before it ships, and which of those methods work outside a monorepo?
- Serves: FM-14.
- Good answer: build-graph methods (Bazel query, Buck); service catalogues (Backstage); trace-derived dependency graphs; API contract registries; accuracy and cost of each; what polyrepo teams do instead.
- Start: Google monorepo papers; Uber engineering blog on monorepo and dependency management; Spotify Backstage docs; Meta on Buck and dependency analysis; Netflix on service graphs from traces.

**RQ-S1-2.** How do teams reconstruct why a piece of code exists when its purpose is not obvious, and what do they do when the record is missing?
- Serves: FM-02.
- Good answer: ADRs; commit message and linked-ticket conventions; code ownership; blame-driven archaeology; characterization tests; any explicit policy on touching code of unknown purpose.
- Start: Nygard on Architecture Decision Records; Feathers, Working Effectively with Legacy Code; Google engineering practices on CL descriptions; Chesterton's fence in engineering blogs.

**RQ-S1-3.** What does the context section of a strong design document contain, and what do design reviewers refuse to review without?
- Serves: S1 exit criterion, FM-14.
- Good answer: template fields (background, current state, constraints, related work); any published reviewer expectations.
- Start: Google design doc practice (Malte Ubl); Uber RFC template; Stripe and Shopify RFC posts; Squarespace and Pinterest design doc templates.

**RQ-S1-4.** What have practitioners learned about which repository context belongs in standing agent instruction files versus what the agent should discover per task?
- Serves: FM-03, FM-02.
- Good answer: guidance from Anthropic (CLAUDE.md), OpenAI (AGENTS.md), Cursor rules, Kiro steering files; evidence on what rots, what is ignored, and what measurably changes agent behaviour.
- Start: Anthropic Claude Code best practices; agents.md specification; Kiro docs; practitioner write-ups with measured results.

**RQ-S1-5.** How do organisations use production signals such as SLO status, error budget, and existing feature flags as inputs to planning a change, rather than only to verify it afterwards?
- Serves: FM-14, S7.
- Good answer: error-budget policies that gate feature work; flag inventories consulted at design time; production readiness review inputs.
- Start: Google SRE Workbook on error budget policy; LaunchDarkly practice guides; Netflix and Meta reliability posts.

## S2 Requirements clarification

**RQ-S2-1.** Which requirements frameworks include an explicit completeness test for acceptance criteria, and what does that test check?
- Serves: FM-06, FM-08.
- Good answer: EARS syntax and its clause classes; Given/When/Then structure; INVEST; specification by example; for each, the checkable properties and any published defect data.
- Start: Mavin et al on EARS; Adzic, Specification by Example; Cucumber and BDD documentation; Kiro's use of EARS.

**RQ-S2-2.** What scenario categories do mature requirements or design practices force out of a requirement, and are there published checklists?
- Serves: FM-08.
- Good answer: categories such as error paths, concurrency, migration, backward compatibility, permissions, observability, rollback, data retention; the checklist sources; how they are applied in review.
- Start: Google design doc cross-cutting concerns; production readiness review checklists (Google SRE, Uber, Stripe); AWS Well-Architected review questions.

**RQ-S2-3.** How do product and engineering practices decide which open questions must go to the product owner and which should be decided by a default assumption?
- Serves: FM-07.
- Good answer: Shape Up shaping and rabbit holes; Amazon PR/FAQ discipline; assumption logs; decide-and-disclose or lazy-consensus norms; the criteria actually used.
- Start: Shape Up (Singer); Working Backwards (Bryar and Carr); Apache lazy consensus; business-analysis assumption-log practice.

**RQ-S2-4.** What is known about clarifying-question quality for LLM agents: when to ask versus assume, how to rank questions, and how to avoid low-value questions?
- Serves: FM-07.
- Good answer: research on ambiguity detection and clarification (information gain, uncertainty thresholds); lab guidance on asking (Anthropic, OpenAI, Kiro); any measured user response to question volume.
- Start: arXiv on clarifying questions and ambiguity in LLM agents; Anthropic Claude Code and Agent SDK docs; OpenAI Codex guidance; Kiro requirements phase docs.

**RQ-S2-5.** How do spec-driven development tools structure requirements, design, and tasks, and what failure modes do their users report?
- Serves: FM-06, FM-07.
- Good answer: the artefact chain in Kiro, GitHub spec-kit, OpenSpec, Tessl; reported problems such as over-specification, spec drift, rubber-stamping, question fatigue.
- Start: Kiro docs and blog; spec-kit README and issue tracker; OpenSpec; practitioner reports.

**RQ-S2-6.** How do teams split large product requirements, and how do they detect that a ticket is too large to specify safely?
- Serves: FM-05, FM-06.
- Good answer: story splitting patterns; vertical slicing; Shape Up appetite; size signals (files, services, unknowns); evidence linking size to rework.
- Start: Lawrence story-splitting patterns; Shape Up; Google small CL evidence.

**RQ-S2-7.** How do organisations record which requirement questions were asked, answered, or defaulted, so that the record survives to review and rollout?
- Serves: P4, FM-07.
- Good answer: FAQ sections in PR/FAQ; decision logs; open-questions sections in design docs; assumption registers.
- Start: Amazon PR/FAQ; Google design doc template; ADR practice.

## S3 Spec and plan

This stage carries the most weight (P3). It is split into two packets: 3A on document and review practice, 3B on engineering judgment.

### 3A. Document and review practice

**RQ-S3-1.** What sections do the strongest design document and RFC templates require, and which sections do reviewers say carry the decision?
- Serves: FM-01, FM-04, FM-05.
- Good answer: template comparison across Google, Uber, Stripe, Shopify, Squarespace, Pinterest; explicit statements on goals, non-goals, alternatives considered, risks, rollout.

**RQ-S3-2.** How are design documents evaluated? Are there published review rubrics or checklists, and what causes a design to be sent back?
- Serves: P2, FM-01, FM-05.
- Good answer: rubric or checklist text; reviewer roles; recorded rejection reasons.
- Start: Google design review practice; Uber RFC review; Squarespace RFC process; Rust RFC and Python PEP acceptance criteria.

**RQ-S3-3.** How do Shape Up appetite and no-gos, design doc non-goals, and PR size norms contain scope, and what measured evidence links change size to review time or defect rate?
- Serves: FM-05.
- Good answer: the mechanisms; the quantitative studies (Google, Microsoft, Cisco and SmartBear review size studies) with their numbers.

**RQ-S3-4.** What do design and planning practices require a plan to say about testing and about rollout before it is approved?
- Serves: FM-11, S7.
- Good answer: test strategy expectations (Google test sizes, test pyramid); rollout sections (flags, migration, rollback, monitoring); production readiness gates.

**RQ-S3-5.** What do AI labs and agent tool vendors say about the plan artefact: its content, its review, and whether reviewing plans reduces rework?
- Serves: P3, FM-05.
- Good answer: Anthropic plan mode and explore-plan-code guidance; OpenAI Codex; Cursor plan mode; Kiro design phase; any evidence on plan review outcomes.

**RQ-S3-6.** How do organisations record alternatives considered and rejected, and is there evidence that the record helps later readers?
- Serves: FM-01, P4.
- Good answer: design doc alternatives sections; ADR considered-options format; any evidence of reuse.

### 3B. Engineering judgment

**RQ-S3-7.** What heuristics do respected practitioners publish for when to introduce an abstraction, and has anyone operationalised them as a checklist or lint?
- Serves: FM-01.
- Good answer: rule of three; Metz on the wrong abstraction; YAGNI; Ousterhout on deep modules; Google style guidance; any codified form.

**RQ-S3-8.** How do teams decide whether legacy or hacky code is load-bearing before changing it, and what written policy exists?
- Serves: FM-02.
- Good answer: characterization tests; blame plus linked ticket; owner consultation; do-not-touch annotations; any documented decision procedure.

**RQ-S3-9.** How do organisations keep refactoring separate from feature changes, and when do they require a refactor to be split into its own change?
- Serves: FM-04.
- Good answer: Fowler on preparatory refactoring; "make the change easy, then make the easy change"; Google CL guidance on separating refactors; Meta and Uber large-scale migration practice.

**RQ-S3-10.** How do organisations enforce "use existing patterns and utilities" beyond linters, and what is transferable to a rubric?
- Serves: FM-03.
- Good answer: readability programs; golden paths and paved roads; style guides with rationale; code owners; internal library discovery.
- Start: Google readability; Spotify golden path; Netflix paved road.

**RQ-S3-11.** How do teams identify the highest-risk parts of a change in advance, so review attention can be pointed at them?
- Serves: FM-10, P9.
- Good answer: hot spot analysis (churn times complexity, Tornhill); change-risk models (Google, Meta, Microsoft); ownership signals.

## S4 Implementation

**RQ-S4-1.** What do labs and tool vendors say about keeping an agent's implementation conformant to an approved plan, and what evidence of drift exists?
- Serves: FM-05, P4.
- Good answer: task decomposition; checkpointing; plan re-reading; deviation logging; reports of drift and its causes.

**RQ-S4-2.** What do major style guides say about when a comment is required and when it is forbidden, and is any of it mechanically checkable?
- Serves: FM-12, FM-13.
- Good answer: Google style guides; Ousterhout on comments; why-not-what norms; lints for redundant comments.

**RQ-S4-3.** How do organisations judge test quality beyond coverage, and what criteria did Meta use to accept or reject generated tests?
- Serves: FM-11.
- Good answer: mutation testing; assertion quality; flakiness policy; test smells; Meta TestGen-LLM acceptance filters and keep rates; Google test certification levels.

**RQ-S4-4.** What published data exists on the quality of AI-authored code: defect rates, churn, duplication, and where agents fail most?
- Serves: FM-01, FM-03, FM-11.
- Good answer: GitClear reports; DORA AI reports; Google and Microsoft internal figures; academic studies; what each measured and how.

**RQ-S4-5.** How do organisations prevent silent decisions during implementation, such as unlogged deviations or invented behaviour?
- Serves: P4.
- Good answer: deviation logs; ADR updates; PR templates that require "what changed from the plan".

## S5 Cleanup pass

**RQ-S5-1.** What automated or LLM-based gates exist for detecting low-value tests, redundant comments, dead code, and style drift, and what is known about their precision?
- Serves: FM-11, FM-12, FM-03.

**RQ-S5-2.** What presubmit and pre-merge checks do organisations with critical systems run, and how do they split cheap checks from expensive ones?
- Serves: S5 exit criterion.
- Start: Google TAP and presubmit; Meta Sandcastle; Uber SubmitQueue; Netflix.

**RQ-S5-3.** What is known about using an LLM as a reviewer or judge of code and plans against a rubric: calibration to human judgment, self-preference bias, independence from the authoring model?
- Serves: P2, FM-10.
- Good answer: LLM-as-judge literature; lab guidance on rubric grading; code-review-specific evaluations.

**RQ-S5-4.** How can a change be checked for staying within its declared scope, meaning the files, modules, and services named in the plan?
- Serves: FM-05.

## S6 Human review

**RQ-S6-1.** What do Google's code review guidelines say a reviewer should look at and in what order, and what evidence supports small changes?
- Serves: FM-10.

**RQ-S6-2.** What have organisations published about reviewing AI-generated code specifically: review time, rubber-stamping, reviewer fatigue, defect escape?
- Serves: FM-10.
- Start: Google ML-assisted review comment resolution; Meta AI review; Uber uReview; GitHub Copilot code review data; academic studies.

**RQ-S6-3.** What evidence links structured change descriptions (intent, risk, testing) to faster or better review?
- Serves: FM-10, P9.

**RQ-S6-4.** How do organisations focus reviewer attention: risk-based review, mandatory second reviewer for sensitive areas, review of the design before the diff, stacked diffs?
- Serves: FM-10, P1.

**RQ-S6-5.** What do empirical studies say reviewers actually catch and miss, and what does that imply for what a review packet should foreground?
- Serves: FM-10.
- Start: Bacchelli and Bird (Microsoft); Sadowski et al (Google); Rigby and Bird.

## S7 Rollout and verification

**RQ-S7-1.** How do organisations size a canary or flag-ramp verification window and define automatic kill conditions from SLOs?
- Serves: S7.
- Start: Google SRE Workbook on canarying; LaunchDarkly; Netflix Kayenta; Meta continuous deployment.

**RQ-S7-2.** What is published practice for automated rollback, and for deciding between rollback and fix-forward?
- Serves: S7.

**RQ-S7-3.** How do organisations manage feature flag lifecycle and debt, and how is flag cleanup planned at design time?
- Serves: S7, FM-04.
- Start: LaunchDarkly; Uber flag management (Piranha); Google.

**RQ-S7-4.** When logs are the primary verification signal and automation cannot read them, how do teams structure human verification steps and checklists after deploy?
- Serves: P7.

**RQ-S7-5.** How do organisations with critical systems balance change control formality (change windows, approvals) against deployment frequency?
- Serves: S7, anti-goals.
- Start: DORA research; Google SRE; ITIL 4 and DevOps reconciliation.

## Cross-cutting

**RQ-X-1.** What is known about the cost of context switching and interruption for engineers, and about batching decisions to reduce it?
- Serves: FM-09.
- Start: Parnin and Rugaber; Mark et al on interruptions; Graham, maker's schedule; Microsoft developer productivity research.

**RQ-X-2.** How do organisations run asynchronous decision processes: written narratives, comment periods, lazy consensus, decision-by-default with objection windows?
- Serves: FM-09, FM-07.
- Start: Amazon narratives; Apache lazy consensus; Rust RFC final comment period; Shopify and GitLab async practice.

**RQ-X-3.** What have labs and vendors published about humans supervising multiple concurrent agents, and what did they learn about review load and the interaction surface?
- Serves: FM-09.
- Start: Anthropic multi-agent research system; OpenAI Codex asynchronous agents; Cursor background agents; Devin; Google Jules.

**RQ-X-4.** What is known about propose-a-default, human-approves interaction patterns and their acceptance rates?
- Serves: FM-07, P1.
- Start: Google ML-suggested review comment resolution; Copilot autofix acceptance; Meta auto-generated diffs.

**RQ-X-5.** How do labs design rubrics for grading subjective engineering artefacts such as plans, specs, and reviews, and how do they calibrate against humans?
- Serves: P2.
- Start: Anthropic and OpenAI evaluation guidance; rubric-based grading literature; SWE-bench and related benchmarks.

**RQ-X-6.** What engineering productivity metrics have organisations found misleading, and which survived?
- Serves: success measures.
- Start: DORA; SPACE; Google engineering productivity research; Goodhart's law discussions.

**RQ-X-7.** What do organisations and AI-coding teams say about keeping decisions and agent memory traceable and fresh: ADRs, decision logs, instruction files; what rots and what stays useful?
- Serves: P4, D7.

---

## Factory implementations (whole-factory sources)

Packet R9 reads named accounts of software factories rather than searching for stage-level practice. The unit of analysis is the factory as a whole: how work enters, where humans decide, what is verified mechanically, and what evidence the authors offer. Each question is answered per source, then once across the sources in the packet.

- **RQ-F-1. Definition and scope.** What does the author mean by "software factory"? What is the unit of work, what enters, what leaves, and which activities are automated versus human. Serves: P1, P2, anti-goals.
- **RQ-F-2. Stage structure and gates.** Which stages exist, which gates sit between them, and where a human decision is required. Map each onto S0 to S7 and name what has no equivalent. Serves: stage map.
- **RQ-F-3. Human interaction model.** How questions, approvals, and reviews reach humans; whether they are batched, queued, or interrupt-driven; whether defaults are proposed; how attention is budgeted. Serves: FM-07, FM-09, section 6 of the charter.
- **RQ-F-4. Verification and judgment.** What is checked mechanically (tests, evals, policies, rubrics), who authored the checks, when they run, and what happens on failure. Whether any judgment rubric exists for abstraction, scope, style, or debt. Serves: FM-01 to FM-05, FM-11 to FM-13.
- **RQ-F-5. Context and memory.** How the factory gathers codebase and organisational context, and what persists across units of work. Serves: FM-14, D7.
- **RQ-F-6. Evidence.** Every metric reported, with denominator and measurement method. State which are measured, which are self-reported, and which are vendor claims. Serves: section 8 of the charter.
- **RQ-F-7. Named failure modes.** Failures the authors name and their mitigations. Map to FM-01 to FM-14 and to the proposed FM-15 to FM-18 in `synthesis.md` section 4; list failures with no catalogue entry. Serves: failure-mode catalogue.
- **RQ-F-8. Delta against the synthesis.** For each of the ten headline findings in `synthesis.md` section 1: confirmed, contradicted, or untouched by this source, with the quote or figure that decides it. Serves: synthesis v0.2.
- **RQ-F-9. Transfer.** What is directly reusable for a single-engineer, brownfield, MCP-connected factory running on one machine, and what depends on scale, proprietary infrastructure, or greenfield assumptions. Serves: D7, D8, D9.

## Tooling (PRD inputs, packet R10)

Packet R10 serves `docs/prd/inputs.md` section 3, not a stage. Each question names the inputs row it decides and the PRD entities or requirements it touches. Rules 1 to 5 apply, with three additions:

- For every tool named, record licence, date of last release or last commit, and whether the evidence of use comes from anyone other than the author. Stars are not evidence. A tool with no release or commit in the last twelve months is reported as unmaintained.
- Official tool documentation is a primary source for what a tool exposes and for nothing else. Claims of benefit need a measurement or a first-hand practitioner report.
- In the answer format, the **Transfer to an agent** field becomes **Fit to the inputs row**: whether the candidate satisfies the row's need as written, which constraint or failure mode its adoption would cite (D24), and what the row's note gets wrong. Nothing is selected in this packet; selection is a PRD decision.

The pilot service's language is not fixed (charter Q9). Language questions are answered as a matrix over Python, TypeScript and JavaScript, Java and Kotlin, and Go.

**RQ-T-1.** Which OpenTelemetry GenAI semantic conventions are stable enough to borrow as the ledger schema, and which of Claude Code (CLI and Agent SDK), Cursor CLI, and Cursor SDK expose per-invocation tool-call, token, and cost data locally without an exporter?
- Serves: inputs row 1; C5, D5, D23; PRD `stage_run` and `tool_call` fields (section 2.2).
- Good answer: the stability status of each GenAI semantic-convention group (spans, metrics, events) and of the individual attributes, as of the current specification release, with the date; the attributes that map onto `stage_run` (`runtime`, `model`, `tokens_in`, `tokens_out`, `cost`, `wall_clock_seconds`) and onto `tool_call` (`tool`, `args_digest`, `result_digest`, `duration_ms`, `tokens`), and the ledger fields with no counterpart; for each runtime, whether tokens, cost, per-tool-call duration, and per-tool-call tokens are available from a hook, a local log file, a JSON or stream output mode, or an SDK message type, with the field names and the documentation page; which of those fields are absent, so that the PRD's "null, never estimated" rule applies.
- Start: OpenTelemetry semantic conventions for generative AI and their stability annotations; Claude Code documentation on hooks, JSON output, monitoring and OpenTelemetry, and the Agent SDK message types; Cursor CLI documentation, output formats, and any SDK reference; the OpenLLMetry and OpenInference conventions as comparison.

**RQ-T-2.** Which open-source code graph or symbol index tools are maintained, expose an MCP server, cover the mainstream service languages, and can be rebuilt or invalidated on merge?
- Serves: inputs row 3; FM-14, FM-03, FM-02, FM-17; C1.
- Good answer: a matrix of tools by language coverage, MCP transport, index build model (on demand, watched, on commit), rebuild or invalidation mechanism, and maintenance signal; for each, whether it is an LSP wrapper, a tree-sitter or SCIP graph, or a summary such as a repo map; the schema cost of attaching it (number of tools exposed, since C1 pays for every tool schema); any measured evidence that structural navigation reduces agent tool calls, tokens, or wrong edits against grep, with the benchmark and denominator.
- Start: Serena and other LSP-backed MCP servers; SCIP and its indexers (scip-python, scip-typescript, scip-java, scip-go) and Sourcegraph's documentation; tree-sitter based repository graphs; Aider's repo-map write-up and its measurements; the MCP servers registry; language-server MCP bridges.

**RQ-T-3.** What does a minimal durable workflow engine cost to run on one machine, and at what concurrency is a SQLite state table known to fail as a job queue?
- Serves: inputs rows 5 and 6; C7, D24, D27, FM-21, FM-09; PRD R-I-7 and the parallel-ticket limit in section 8 (1, then 2, then 3).
- Good answer: for Temporal (dev server and self-hosted with SQLite or Postgres), Prefect, and Dagster: processes, memory footprint, storage backends, per-step overhead, and how retries and timeouts are expressed as configuration, so D14 bounds can be mapped; for SQLite: the documented write-concurrency model (single writer, WAL, busy timeout) and the published figures or first-hand reports for a job queue or state table on SQLite, with write rate, number of workers, and where it broke; whether any published agent pipeline runs its state on SQLite at one to ten concurrent units of work and what its authors report; a statement of whether the PRD's limit of three parallel tickets is anywhere near a known failure point.
- Start: Temporal self-hosting and dev-server documentation; Prefect and Dagster deployment documentation; SQLite documentation on WAL, locking, and appropriate uses; write-ups of SQLite as a job queue (Rails Solid Queue on SQLite, litequeue, and similar) that carry numbers; the Ona and Warp orchestration accounts in `docs/research/synthesis-factories.md`.

**RQ-T-4.** Which git-backed or local issue trackers built for agents exist, and does any have evidence of use beyond its author?
- Serves: inputs row 8; C3, D9, D17, FM-09, FM-07; PRD `ticket`, `question`, `answer`, and `assumption` tables.
- Good answer: a list of trackers with storage model (git objects, files in the repository, SQLite), the schema they carry (tasks, dependencies, questions, decisions), whether they expose a CLI or MCP server for agents, and for each the evidence of external use: contributors other than the author, named adopters, issues filed by third parties, a first-hand account of running it; a comparison stating what, if anything, a plain SQLite schema per PRD section 2 loses against the best of them, and whether any supports the move off one machine that D9 keeps open.
- Start: Beads (Yegge); git-bug; Backlog.md; claude-task-master and similar agent task managers; GitHub topic searches for agent task tracker; practitioner reports of running agents against a git-backed tracker.

**RQ-T-5.** How do existing factories record agent cost per unit of work, and does any publish its schema?
- Serves: inputs row 1; C5, charter section 8; PRD `stage_run.cost`, `benchmark.cost`, and the cost-per-ticket context measure.
- Good answer: for each factory account already read (Uber, Ona, Osmani and the HumanLayer run, Warp; raw files R9a to R9d) and any further published account: the unit of work (ticket, PR, task, run), the cost components captured (tokens by model, tool time, wall-clock, human minutes), where the record lives, and whether a schema, table, or export format is published; as the fallback comparison, the data models of Langfuse, Arize Phoenix with OpenInference, and OpenLLMetry, mapped field by field onto `stage_run` and `tool_call`, with what each would add and what it cannot hold (tier, manifest hash, catalogue tags).
- Start: `docs/research/raw/R9a-factory-uber.md` to `R9d-factory-warp.md`; Warp's dashboard and measurement page (URL moved; see `synthesis-factories.md` section 6); Uber engineering blog; Langfuse data model documentation; OpenInference specification; OpenLLMetry.

**RQ-T-6.** Which open-source eval harnesses support single-dimension graders, fixtures from recorded runs, and a model-separation rule, and how do teams version evals next to prompts and skills?
- Serves: inputs row 12; C6, C4, D26, FM-16, FM-17, FM-18; PRD R-F-2, R-F-3, R-F-8, and the `factory/evals/` layout in section 7.
- Good answer: for promptfoo, Inspect (UK AI Security Institute), DeepEval, OpenAI Evals, and any harness the labs document: whether a grader can be constrained to one dimension with an explicit "insufficient information" output; whether a fixture can be an exported directory of artefacts and a transcript rather than a prompt and response pair; whether the grader model is configured per grader and can be asserted different from the authoring model; whether the harness runs as a check on a pull request; the published practice on versioning evals beside prompts and skills (directory layouts, thresholds in files, CI gates) from company engineering posts, with what rotted.
- Start: promptfoo documentation on assertions, model-graded metrics, and CI; Inspect documentation on tasks, scorers, and logs; DeepEval; OpenAI Evals repository; Anthropic documentation on evaluations and on Claude Code skill and plugin evaluation; practitioner writing on LLM evals (Husain, Yan) for the versioning practice.

**RQ-T-7.** What does the GitHub MCP server expose for workflow runs, check runs, and job logs, and what does it not?
- Serves: inputs row 13; S7, D25, D4, P7, C1; PRD `pr_checks_summary` artefact and the five-minute runner poll in section 8.
- Good answer: the Actions and Checks tools of the official GitHub MCP server, remote and local, with the read-only subset (list workflow runs for a ref or PR, get run, list jobs, get job logs, check runs and check suites) and the write subset the factory must never attach (rerun, cancel, approve, merge); log retrieval limits and truncation; authentication options (PAT scopes, GitHub App, OAuth) and the rate limits a five-minute poll would meet; toolset configuration so only the read-only Actions tools attach and their schema count; what is missing, so the runner would call the REST API directly or declare a blind spot.
- Start: github/github-mcp-server README, toolsets documentation, and tool reference; GitHub REST API documentation for Actions and Checks; GitHub documentation on the remote MCP server and rate limits.

**RQ-T-8.** Does Cursor publish an SDK, distinct from the CLI's non-interactive mode, and what does it expose per invocation?
- Serves: inputs row 1 and the runtime choice; C5, D5, D9; PRD `stage_run` fields and R-I-4 manifest entries (runtime, model).
- Good answer: whether a documented programmatic interface exists (a package, an HTTP API, or the Cloud Agents API), with the URL; whether it runs on the engineer's machine or only in Cursor's cloud (D9); per invocation, whether it reports input and output tokens, cost, tool calls with duration, and the model used, with field names; whether the model can be chosen per invocation; whether hooks or rules files are honoured in that mode; the terms that govern programmatic use. If none of this is documented, say "no SDK documented" and name the pages checked.
- Start: cursor.com/docs index, in particular any SDK, API, Cloud Agents, or headless pages; Cursor changelog; Cursor forum announcements from staff only.

**RQ-T-9.** Which projects called CodeGraph expose an MCP server for code navigation, and which of them could serve a Java service?
- Serves: inputs row 3; FM-14, FM-03, FM-17, C1.
- Good answer: every maintained project named CodeGraph or codegraph with an MCP server, with repository URL, licence, last release or commit date, languages supported with Java stated explicitly, how the index is stored, whether it updates incrementally or must be rebuilt after a change, the number of MCP tools it exposes, and evidence of use beyond the author; a statement of which one the token-reduction claim cited in RQ-T-2 ("62% fewer tokens across seven repos") belongs to; and, for the strongest candidate, what it would take to invalidate its index on every merge.
- Start: GitHub search for codegraph MCP; the MCP servers registry; the comparison pages cited in RQ-T-2; each candidate's own README.

## Research packets

Each packet is one researcher. Output goes to `docs/research/raw/<packet>.md`.

| Packet | Questions | Output file |
|---|---|---|
| R1 Intake and context | RQ-S0-1 to RQ-S0-3, RQ-S1-1 to RQ-S1-5 | `R1-intake-context.md` |
| R2 Requirements | RQ-S2-1 to RQ-S2-7 | `R2-requirements.md` |
| R3 Spec, document and review practice | RQ-S3-1 to RQ-S3-6 | `R3-spec-documents.md` |
| R4 Spec, engineering judgment | RQ-S3-7 to RQ-S3-11 | `R4-spec-judgment.md` |
| R5 Implementation and cleanup | RQ-S4-1 to RQ-S4-5, RQ-S5-1 to RQ-S5-4 | `R5-implementation-cleanup.md` |
| R6 Human review | RQ-S6-1 to RQ-S6-5 | `R6-human-review.md` |
| R7 Rollout | RQ-S7-1 to RQ-S7-5 | `R7-rollout.md` |
| R8 Cross-cutting | RQ-X-1 to RQ-X-7 | `R8-cross-cutting.md` |
| R9a Factory implementations, Uber | RQ-F-1 to RQ-F-9 | `R9a-factory-uber.md` |
| R9b Factory implementations, Ona dark factories talk | RQ-F-1 to RQ-F-9 | `R9b-factory-ona.md` |
| R9c Factory implementations, Osmani | RQ-F-1 to RQ-F-9 | `R9c-factory-osmani.md` |
| R9d Factory implementations, Warp | RQ-F-1 to RQ-F-9 | `R9d-factory-warp.md` |
| R10 Tooling | RQ-T-1 to RQ-T-7 | `R10-tooling.md` |
| R10b Tooling, selection check | RQ-T-8, RQ-T-9 | `R10b-selection-check.md` |

## Required answer format

For each question, in order:

```
### RQ-<id>. <question restated>

**Answer.** Two to five sentences. Lead with the pattern, not the source.

**Patterns found.**
- <pattern> — <source title>, <URL>, <source type>. <measured figure if any, with denominator>.

**Evidence quality.** Primary or secondary; measured or anecdotal; how many independent sources agree.

**Transfer to an agent.** Whether the pattern applies to an agent-driven pipeline, and the proposed rubric line or pipeline rule in one sentence each.

**Gaps.** What was searched for and not found.
```

End each packet with a `## Sources consulted` list and a `## Cross-references` list naming any question in another packet whose answer this packet touched.
