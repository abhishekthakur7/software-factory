# Software Factory Charter

| | |
|---|---|
| Status | Draft v0.11 |
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

The factory's eventual responsibility ends at pull-request merge. It opens the PR, tracks the GitHub Actions runs the PR triggers, and assembles the review packet. Rollout, flag ramps, and production verification happen after merge, by the engineer, outside the factory (D25). The plan still states how the change should be rolled out, because the reviewer needs to judge it, but the factory does not execute it.

The initial pilot is production-capable, not production-autonomous. Its factory phase ends when the locally reviewed branch is opened as a draft pull request. That event is not the ticket outcome and is not permission to merge: the ordinary team checks, an independent human review where this charter requires one, and the human merge decision still follow. Until S7 automates observation, the engineer records the eventual `merged` or `abandoned` outcome and any intervening revision in the ticket record. Pilot measures use that outcome, not draft-PR creation, as ticket completion (D33).

### What this is

A collaborator. The human is a participant in every stage, not an approver waiting at the end. Every artefact a stage produces is written to be read and acted on by the human, and the factory's own reasoning is always on the record. Automation grows one step at a time, under P10, by adding a cheaper check for that step, never by removing the human from a stage wholesale (P11).

The collaboration happens at stable, visible boundaries. The engineer can always see the current stage, task, bound inputs, budget, and last durable output, and can cancel a running stage without losing the record so far. A stage never crosses a pending human gate in the background. Continuous steering is not required and is not a substitute for a reviewable boundary (D39).

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
- **No black box.** No stage runs whose output the human cannot read, whose decision-relevant reasoning is not on the record, or whose inputs and actions cannot be reconstructed from the ticket record. The factory does not promise bit-for-bit replay of a hosted, nondeterministic model (C12).
- **No unisolated implementation.** Agent-authored code and repository build logic are untrusted execution. They do not run with the engineer's ambient filesystem, network, keychain, cloud credentials, or Git push authority (C10).
- **No unapproved data boundary.** Source, ticket, document, prompt, tool-result, and run-record data cross only the provider and retention boundaries recorded in the trust profile. A privacy toggle alone is not approval (C9).
- **No stale approval.** An approval applies only to the exact source, configuration, artefacts, diff, and evidence the human reviewed. A material change invalidates it; approvals do not float forward (C11).

## 4. Failure-mode catalogue

Cost and frequency are computed, not estimated. Every revision after plan approval, every incident, every override of an agent judgment, and every abandoned ticket is tagged at the source with a failure-mode ID, and the two columns are filled from those tags (D21). FM-01 to FM-14, FM-20, and FM-21 come from our own experience with agents. FM-15 to FM-19 and FM-22 were added from the research record (section 9). FM-23 to FM-25 were added by the requirements-boundary audit that produced v0.10. Research-derived and audit-derived entries are hypothesised until the pilot observes them.

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
| FM-23 | Implementation, Checks | Untrusted execution escapes its intended boundary: an agent or repository build reads host data, reaches an undeclared network service, uses ambient credentials, changes another checkout, or pushes without approval | Source or credential disclosure; host or repository damage; an unaudited external action | TBD |
| FM-24 | Cross-cutting | Data crosses an unapproved trust boundary, or is retained, exposed, or reused beyond the recorded policy | Confidentiality or compliance breach; the factory cannot show what a provider or operator was allowed to see | TBD |
| FM-25 | Planning, Review | An approval remains in force after its base source, factory configuration, approved artefact, branch diff, required reviewer set, or check evidence changes | The human appears to have approved a state they never reviewed; stale judgment reaches a pull request or merge | TBD |

## 5. Stage map

For each stage: what the factory produces, what the human decides, and the exit criterion. Rubric contents and tooling are deliberately absent; they come later and cite this table.

Each stage attempt is a separate recorded run with its own tool allowlist (C1). An agent-bearing attempt is one fresh agent invocation; a script-only attempt records no agent or model. No run carries state between attempts except through the ticket record (C3).

| Stage | Factory produces | Human decides | Exit criterion |
|---|---|---|---|
| S0 Intake | Provisional complexity tier from the service tier and ticket type (D11); the type of scrutiny the ticket requests; the trust profile and required human roles for the ticket | Whether the ticket is eligible for the factory; tier override; whether every required independent approver is available | Ticket assigned to the factory with a provisional tier and named roles; a sensitive-path ticket without its independent approver is ineligible |
| S1 Context gathering | Context brief: ticket, epic, linked docs, repo history of the touched area, evidence-backed impact findings, flags found in code, SLIs and live flag state as declared blind spots (C2); the method and coverage limit of every impact claim; the index entries used and any found stale; the final tier from files and services touched and the unknown count | Nothing, unless the brief flags a blocker | Brief complete, unknowns explicitly listed, every method-labelled blind spot resolved or handed to the S3 reviewer, tier final |
| S2 Requirements clarification | Completeness assessment of acceptance criteria; ranked question set in the format of section 6 | Answers, or accepts defaults | Acceptance criteria pass the structural completeness rubric; every blocking question is resolved |
| S3 Spec and plan | Approach, alternatives considered, non-goals, code to touch and code deliberately not touched with reasons, abstraction decisions, tech debt proposals as separate items, declared contracts of touched code, an ordered task list with dependencies, validation criteria for the change, test strategy, flag and rollout strategy for the engineer to execute after merge, risk map; the exact source, configuration, and artefact identities the plan binds | Approve or redirect; during bootstrap, verify every uncalibrated semantic line from S1 through S3 | Plan passes the planning rubric, including the size gate; every semantic line is human-verified or checked by a calibrated grader; the criteria-and-plan bundle is approved against the bound state |
| S4 Implementation | The change, inside the C10 execution boundary and within D14 bounds: three verification attempts per task, then escalation carrying the full failure history; a token and wall-clock budget per tier. A self-report of conformance to the plan, any deviations, and any contract change | Nothing, unless cancelled or escalated to | Conformance check passes within budget against the approved bound state |
| S5 Cleanup pass | A trusted preflight verifies plan approval, target-base, head, diff, deviation, sandbox, and toolchain identities and derives the actual and effective reviewer sets from the final diff. On success, deterministic checks run in order: the project's lint, compile/type and tests; mandatory secret, static-analysis, dependency-vulnerability and licence-policy recipes; dependency resolution; size; scope; source-declaration and behavioural-evidence checks; final reviewer-set and approval-binding checks. Advisory: an independent agent pass against the slop rubrics in a fresh context (C4), never on a red build | Resolve or send back a failure; waive a declared epistemic blind spot only where policy permits; no silent waiver | Every blocking result is recorded against one fresh review binding; none is `fail`, and each is either `pass` or a policy-waivable `blind_spot` with a valid waiver reported separately from green evidence; reviewer requirements are unchanged; advisory findings are attached as evidence |
| S6 Human review | A race guard confirms the S5 identities and reviewer set are unchanged; then the review packet in section 6, with the diff as appendix and exact hashes of the source, manifest, plan, head, checks, packet, and PR narrative | Approve or request changes; a sensitive-path owner approves independently | Every required role approves judgment, intent, and residual risk for the same exact state, with defect evidence supplied by S5 |
| S7 PR checks and merge | Status of every GitHub Actions run the PR triggered, read through the GitHub MCP server; a summary of any failure with the likely cause; the PR left open for the human | Merge, or send back | PR merged by the human with all required checks green. Rollout after merge is outside the factory (D25) |

The improvement pass is a stage over the factory repository, not over a ticket. It is specified in the PRD and bounded by C8.

## 6. Human interaction contract

This section is the human-friendly guarantee. Violations are defects in the factory, not in the human.

**Questions.** A question reaches a human only if both hold: the agent could not answer it from the available sources and says what it tried, and the answer changes the spec or the plan. Each question carries what it affects, the agent's reasoning, and between two and four options, as many as the question genuinely has. "None of these, tell me" is always available.

**Defaults.** Consequence and reversibility are separate properties and both are recorded. For a routine question, including a consequential but cheaply reversible one, the agent marks a default, and accepting it takes one word. Only when a question is both consequential and hard to reverse does the agent present the options without pre-selecting one; those are the questions the human is there to decide. Every accepted default is recorded as a named assumption in the plan.

**Batching and ranking.** Questions are batched per ticket and ranked by how much the answer changes the spec. There is no fixed cap. The count scales with the ticket: a simple change may raise none and a complex feature may raise many. What is fixed is the gate above, and every question has to pass it.

**Delivery.** Questions arrive through a queue, never as an interrupt and never inside an editor session. A ticket waiting on an answer shows a visible blocked state, and the agent continues any work that does not depend on the answer. A digest of open questions goes to Slack on a cadence the engineer sets. Answering is its own mode of work, so a person can hold several tickets and answer in one sitting. Work may continue beside a non-blocking question, but no plan is approved while the question is open: the answer is either recorded, or a human explicitly accepts the stated assumption. An answer that changes an accepted assumption invalidates every dependent downstream artefact and approval (C11).

**Rounds.** Complex tickets produce follow-up questions. They arrive in rounds: the first round holds what blocks the spec, later rounds hold what the answers raised. Each follow-up names the answer that raised it and passes the same gate.

**Scrutiny.** Every ticket states, from S0, the type of scrutiny it requests: what the reviewer should look hardest at and what they may take on the evidence. The review packet repeats it.

**Roles.** Every ticket names an operator, a plan approver, and a final reviewer. One engineer may fill those roles for an ordinary pilot ticket, but a change whose candidate or actual diff touches a sensitive path also names that path's owner, and that owner approves independently at S3 and S6. Each required role records its own decision; a gate closes only when all required roles approve the same exact subject. If the owner is unavailable, the ticket is not eligible for the pilot. The factory owner maintains the process and may not stand in for a missing service or path owner merely by owning the factory. The trust profile separately names security and legal/data-governance approvers and whether one identity may fill both roles.

**Assumption log.** Append-only. Replacing or withdrawing an assumption appends a new entry that names the prior entry and states the replacement or withdrawal; prior rows never change. The current assumption set is derived from the latest unsuperseded entries.

**Review packet.** In this order: the checks that ran and their results; intent in two sentences; the scrutiny requested; decisions made and why; what was deliberately not touched and why; risk map naming the three places worth a reviewer's eyes; deviations from the plan, including any contract change; the assumption log; test summary stating what each test proves; blind spots handed to the human; diff.

**Approval identity.** A plan approval binds the exact ticket source, brief, criteria, plan, base commit, factory configuration, trust approvals, execution policy, planned reviewer set, and human semantic-verdict set the reviewer saw. The planned S4 change does not invalidate that approval merely by producing a new branch head. Final review separately binds the approved plan plus the exact branch head, diff, deviations, blocking checks, waivers, effective reviewer set, packet, PR narrative, and publication destination. Each required role writes an immutable approval against one canonical subject; records for different subjects never combine to satisfy quorum. A change to bound evidence or role-authority policy creates a new subject; expiry invalidates the satisfying set and requires fresh full quorum against the same subject. A base commit is never silently re-pinned: refresh is a recorded transition through the affected context, plan, check, and review stages (C11).

**Evidence language.** An impact method, contract check, or other check says only what it observed. A dependency scan is not called a service-call graph without an explicit, versioned mapping. A source-declaration comparison is not called behavioural or binary contract verification. `blind_spot` is not green: it either sends the ticket back or advances under an immutable policy-permitted waiver naming its actor, role, reason, exact scope, expiry, and compensating evidence. Secret or classification failure, missing trust approval, sandbox-integrity failure, stale evidence, reviewer-quorum failure, and Initial-scope exclusion are not waivable. The actual diff is matched against sensitive paths during S5 and again as a race guard before review; a new match invalidates the plan approval and required-reviewer set.

**Visible boundaries and cancellation.** The queue and ticket view always show the current stage or S4 task, its bound input versions, elapsed budget, last durable output, and next human boundary. The human can cancel a running invocation. Cancellation preserves its outputs and failure history, performs no rollback hidden from the record, and returns through the queue. There is no continuous mid-run steering and no autonomous chaining across a pending human decision.

**Attention and latency.** Active attention and queue latency are different measures. At S3 and S6 the engineer records a coarse time bucket for the effort spent reading and deciding, including `unknown`; the factory does not infer it from focus, keystrokes, or editor activity. Queue latency is the union of the intervals from an item entering the queue to its resolution; it measures availability and flow, not attention. Both are compared only with tickets of the same tier. Neither is used to evaluate a person. The signal under P1 is active attention that did not change or strengthen the outcome, not the time a ticket happened to wait.

**Reconstruction is a defect.** If a human has to reconstruct the agent's reasoning to make a decision, the packet failed.

## 7. Environment and constraints

| System | Role | Agent access |
|---|---|---|
| GitHub | Source of truth for services; PRs; Actions runs on the PR | MCP server |
| Confluence, team space | Architecture, runbooks, team process | MCP server |
| Confluence, user space | Personal notes and context | MCP server |
| Jira | Epics, tickets, feature tracking | MCP server |
| AWS | Runtime after merge; a possible later host for the factory | None for the pilot. No agent access until a cited stage requirement establishes a use inside C2 and C9 |
| LaunchDarkly | Feature flags; the rollout mechanism, used by the engineer after merge | None for now. Out of scope (D25) |
| Slack | Cross-team communication; home of the question digest | MCP server |
| Grafana | SLIs, SLOs, traces of the brownfield services | None for now. Not an agent tool and not a destination for factory traces (C5) |
| OpenSearch | Logs of the brownfield services | None. Out of scope with the rest of production verification (D25) |

Agent runtimes available: Cursor SDK, Cursor CLI, Claude CLI. These are treated as interchangeable execution engines. Choosing one is a late decision and must not shape the design.

The pipeline runs on the engineer's machine for the initial version and may move to an EC2 host later.

### Constraints

- **C1. Tools attach per stage.** Every connected tool's schema costs context before the ticket is read. Each stage attempt resolves its own stage-and-tier allowlist rather than inheriting every tool at once. An agent-bearing attempt is one fresh invocation with that allowlist; a script-only attempt remains a separately recorded run without an agent invocation.
- **C2. Production is out of view.** Logs, metrics, and flags of the brownfield services are not reachable by agents and the factory does not act on them. The factory's view ends at PR merge. Where a plan depends on a production fact, the agent declares it as a blind spot (P7) and the packet names it for the human.
- **C3. Memory is split.** Versioned files hold rubrics, agent instructions, skills, the catalogue, and decisions. A SQLite database holds run state: tickets, runs, questions, answers, metrics. A finding from run state enters the versioned files only through a change the engineer reviews. Every context index entry carries a last-verified date and a staleness rule.
- **C4. Judges are separated.** An advisory pass runs in a fresh context with no access to the authoring transcript, on a different model where the runtime offers one, and the ticket record says which. Before the observer pass and calibrated graders exist, every Initial semantic rubric line that cannot be checked deterministically is verified by a named human at the next stable boundary and the verdict is recorded. A stage does not call such a line passed merely because its grader is Later. Smoke and conformance evals verify the bootstrap machinery and seeded cases; they do not stand in for human judgment on a live ticket.
- **C5. All factory work is recorded at its true grain.** Every ticket-stage execution writes to the ticket record: ticket, stage, tier, inputs, tool calls, a reasoning summary where an agent ran, outputs, tokens, cost provenance, wall-clock, and outcome. This is the factory's own tracing of its work, not brownfield-service tracing, and it is the only source for section 8, escalation, and catalogue tags. Nothing is measured that is not recorded. No ticket-directed agent or stage script runs without a ticket and stage. A post-approval outbox worker is not a second stage attempt: its intent, guard decision, delivery attempts, and receipt are recorded against the originating stage and excluded from stage reliability. Setup, digest, re-index, retention, and other non-ticket maintenance run only as named maintenance jobs in their own job ledger; they never masquerade as a ticket stage. A text report is Initial; a graphical dashboard is Later.
- **C6. Factory as code.** Skills, agent definitions, rubrics, deterministic scripts, lint configurations, and their evals are versioned files (C3). Every referenced skill and agent definition has a smoke and conformance eval before the first production-capable pilot ticket. The bootstrap fixtures come from the factory's own build tickets and exercise structure, allowlists, state transitions, and seeded rubric cases; an empty directory is not an eval. After the first factory scaffold commit, every change to an agent, skill, rubric, checklist, script, or configuration lands as a reviewed pull request and passes the applicable smoke and conformance suite. Recorded-ticket replay, calibrated graders, benchmarks, and the richer adoption gate grow later, but they strengthen this bootstrap gate rather than replacing an unevaluated period. No LLM grader runs on output from its own authoring context or model.
- **C7. Stages are replaceable.** A stage communicates with the rest of the factory only through the ticket record, behind one interface: run a named stage for a ticket and return the record. The initial state table and the orchestration around it can be replaced by a durable workflow engine or a DAG orchestrator without changing a stage.
- **C8. Improvement is objective-bound and human-merged.** Scorers, the improvement pass, and benchmarks take the section 8 primary measures and the rubric lines as their objective. Cost, throughput, and touchpoints are visible to them only as context. Their output is a proposed change to the versioned files, landed only through a change the engineer reviews. The state table that enforces the gates is outside the manifest and outside their reach. A scorer contributes to a benchmark or a proposal only after its agreement with the engineer's grading has been recorded.
- **C9. Data has an explicit, enforced trust boundary.** A versioned, content-addressed trust profile defines admitted repositories, ticket projects, document spaces, data classes and their dominance/join rules, source-to-destination purposes and fields, providers and models, MCP servers and endpoints, processing and storage locations, logging and training/reuse terms, subprocessors, residency, readers, exports, retention and deletion, and the classifier, redaction, secret-detection, and sanitizer policy. Each permitted downgrade route names the sanitizer implementation/rule hash and allowed source and target classes. Every profile requires current immutable security and legal/data-governance approvals bound to the exact profile and authority-policy hashes, with actor, role, evidence, scope, decision time, and expiry. Before activation, a governance-only path may display the proposed profile and authority metadata to those approvers and write their metadata-only decisions to a trusted audit sink; it cannot read, persist, or dispatch production content. After activation, one runner-owned, non-bypassable guard enforces the profile for every content-bearing ingress, persistence, display, model/MCP/tool dispatch, outbox write, and export. Its metadata-only audit sink records the exact route, approvals, post-redaction content digest, policy and decision without recursively guarding its own row. Unknown classification, failure to derive a valid class join, an absent route, an unavailable guard, a secret hit, or a missing or expired approval denies the operation. Derived content takes the profile-defined join of its inputs unless the exact route-authorised sanitizer records its permitted downgrade. Rejected secret material is never written to an artefact, log, ledger, or digest.
- **C10. Agent and build execution is OS-isolated.** S4 and every command that executes repository-controlled build logic in S5 run in an ephemeral container or equivalently restricted operating-system identity from the first production-capable pilot. S4 alone may write the ticket worktree. S5 sees that worktree as a read-only lower layer and may write only disposable recipe-declared build-output, scratch, and cache layers; none is copied back. Declared inputs are read-only, no ambient keychain, cloud, Slack, Jira, Confluence, or GitHub credential is supplied, and network access is denied except endpoints explicitly named for a deterministic dependency or build step. Git push authority exists only in the post-approval PR-publication worker outside that boundary. Enforcement is tested from inside the boundary, including attempted host-file, sibling-checkout, credential, network, source-write, and push access.
- **C11. Approvals bind immutable evidence.** Plan approval records the exact ticket-source, brief, criteria, plan, base-commit, factory configuration, trust approvals, execution policy, planned reviewer set, and semantic-verdict and plan-waiver sets it covers. Final review records that approved plan binding plus the exact branch head, diff, deviations, blocking-check evidence, review waivers, effective reviewer set, packet, PR narrative, and publication destination. Each required role produces its own immutable approval against one canonical subject; a gate passes only when the exact subject satisfies every required slot and identity-separation rule, and records for different subjects never combine. Expected implementation changes create the review binding without invalidating the plan binding. Changing bound evidence or reviewer-authority policy creates a new subject; expiry invalidates the satisfying approval set and requires fresh full quorum against the same subject. The current target-branch head is checked immediately before implementation and again before PR publication. It is never silently re-pinned; accepting a new base is a recorded decision followed by rerunning every stage whose evidence it can change. A newly touched sensitive path invalidates approval even when it was inside a discretion glob.
- **C12. The audit is reconstructable, not deterministically replayable.** The record must let another engineer reconstruct what information and configuration a stage saw, what tools and versions it used, what decisions it made, and what it produced. It therefore pins runtime, model identifier, SDK and tool versions, environment fingerprint, source commits, manifest and artefact hashes, and approved redacted snapshots or immutable locators for decision-relevant external responses. A digest alone is not a replay input. When policy forbids retaining a payload, the record names the omitted source, immutable version if one exists, and resulting blind spot. Hosted-model nondeterminism means the factory does not promise identical output from a rerun.
- **C13. Evidence cannot claim beyond its method.** Every impact and contract statement names the method, coverage, and blind spots that support it. Package dependencies become service-impact claims only through a versioned package-to-service mapping. Source-level public-declaration comparison is called API-shape checking and does not claim behavioural, inherited-member, or binary compatibility. A `blind_spot` does not satisfy a blocking tier without an immutable, policy-permitted waiver naming the policy version, authorised actor and role, reason, exact scope, expiry, and supporting or compensating evidence. The non-waivable conditions are those named in the human contract. Sensitive-path ownership is recomputed from the actual diff during S5 and before final review.


## 8. Success measures

Before the first factory ticket, a baseline cohort from the current agent-assisted workflow is frozen by a documented deterministic rule. Every value records its measure-definition hash, cohort dimensions, source kind and immutable locator, observed-through time, recorder, and status: `observed`, `approximate`, or `unavailable`. A value is comparable only when its endpoint definition and cohort dimensions match the factory measure. Approximate values are context only. When evidence cannot meet the rule, `unavailable` is recorded with a null value and reason; it is never omitted, treated as zero, or reconstructed favourably. A graduation condition that depends on an unavailable comparator has not passed. Factory measures use only the governed record. During the manual PR-outcome shell, the engineer records merge, abandonment, revisions, production exposure and incident coverage, and the optional close answer in that record.

Primary:

- Revisions per ticket after plan approval, tagged by failure mode.
- Questions surfaced per ticket, by tier; the share shown with a default; the share where the default was accepted when shown.
- Active human-attention buckets at S3 and S6, by tier, measured as in the interaction contract; queue latency is reported separately as context.
- Share of generated tests kept after human review.
- Share of plans approved without redirect.
- Production incidents attributable to factory changes, by severity, attribution, and reviewed disposition. Severe means severity 1 or 2 under the versioned incident policy. A no-incident attestation names deployment or exposure start, its source, and the observed-through time. A merged but not demonstrably exposed ticket remains unknown. Zero is reported only from explicit attestations covering every exposed merged ticket through the report cutoff; absence of an incident tag or coverage attestation is unknown, not zero.
- Share of stage runs that pass on the first attempt, by stage and tier. This is the reliability measure the initial version is judged on (D28).
- Share of S3 and S6 decisions that carried an FM-10 reconstruction-defect tag, and the active-attention buckets recorded on those decisions.

Secondary:

- Share of "deliberately not touched" items that turn out to be correct calls.
- Escalations per ticket from S4 after bounded attempts (FM-19).
- Index entries found stale per ticket (FM-17).
- Optional at ticket close, one question: tickets held in parallel and whether returning to this one cost effort (FM-09).

Context, tracked from the initial version, never a success measure (D28, D29):

- Ticket outcomes recorded per window, split into `merged` and `abandoned`; draft-PR creation is reported separately as factory-phase completion.
- Cost per ticket, by stage and tier.
- Non-structural touchpoints per ticket, by tier: questions, red checks, escalations. The S3 and S6 gates are excluded from the count.
- Queue latency at S2, S3, and S6, by tier, reported as flow time and never labelled human attention.

Reporting rules:

- Every growth figure carries its time window. A count with no window is not reported.
- Measures are presented as an unranked panel, never as a single score.
- Context measures are reported in their own block, never in the primary panel, never ranked, and never as an improvement objective (C8).
- Excluded from every report: share of pull requests attributed to agents, estimated savings over human work, and invented numeric values for measures that cannot be computed from the record. An `unavailable` status and its reason remain visible wherever the measure was requested.
- Every measure can be sliced by factory version, the manifest hash in force when the run happened, so a change to the factory is compared before and after.
- No measure feeds an individual's evaluation.

### Pilot graduation

Draft-PR creation proves that the factory phase completed; it does not graduate the pilot. The owner may raise parallelism or widen the eligible service, ticket-type, data-class, or sensitive-path set only after all of the following hold and the evidence is recorded in one decision:

- At least ten pilot tickets have a final `merged` or `abandoned` outcome, not merely an opened pull request.
- Every merged ticket in the window has recorded production exposure and an explicit incident-coverage attestation from that exposure through the decision cutoff. There has been no severity-1 or severity-2 production incident attributable to a factory change. A severe incident starts a new candidate window only after its catalogue and rubric remediations land. Every reported incident, including lesser incidents, has reviewed attribution and disposition; an unknown attribution, open disposition, or merged-but-unexposed ticket blocks graduation.
- Every Initial stage has at least ten eligible top-level first attempts and a first-attempt pass share above 90 percent. `blocked`, `refused`, cancelled (`aborted_human`), child, and maintenance runs are excluded from that denominator but reported separately; all other eligible non-passing first attempts remain failures.
- Mean revisions after plan approval are no worse than the comparable pre-factory baseline, and every revision and abandonment in the window has a reviewed failure-mode tag. An unavailable or non-comparable baseline does not satisfy this condition.
- No unresolved defect remains in the data boundary, execution boundary, approval binding, required-reviewer enforcement, or audit reconstruction. Every blocking-tier blind spot in the window was either resolved or explicitly waived by an authorised human.
- The engineer and every independent reviewer required for the tickets in the window agree that the packet supported their decision without transcript reconstruction; any exception is recorded as FM-10 against the exact decision and carries immutable resolution evidence before graduation.

Meeting the numbers does not widen scope automatically. It makes a recorded human decision eligible. Cost, throughput, default acceptance, plan-approval rate, and touchpoint count cannot satisfy or override this gate (C8).

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
- **D12. Catalogue extended.** FM-15 to FM-19 and FM-22 to FM-25 adopted as hypothesised entries. Tool-schema context cost is a constraint (C1), not a failure mode.
- **D13. Back-pressure adopted** as P10.
- **D14. Implementation bounds.** Three implementation-or-verification failures per approved plan-task version, then escalation carrying the full failure history. One verification attempt is one fresh task invocation that reaches the runner's approved validation commands; a failed validation starts a new recorded attempt, not a hidden repair loop. Infrastructure failures are recorded separately, follow the ordinary stage retry policy, and do not consume the three verification attempts. The third failed verification remains a failed run while escalation is the resulting ticket state. Continuing after that bound requires a superseding plan-task version and new plan approval. Sandbox-integrity failure escalates immediately under FM-23. A token and wall-clock budget per tier is the runaway stop. No step counts.
- **D15. Question format.** Reasoning, two to four options, a marked default unless the question is both consequential and hard to reverse, and "none of these" always available. `consequential` and `hard_to_reverse` are separate recorded judgments, each overridable by the human. Questions are ranked by impact and decision uncertainty; a question with no displayed default is not ranked against an imaginary default.
- **D16. Stage map.** S5 is two-tier with the deterministic tier first and the advisory tier never run on a red build. S6 approves judgment, intent, and residual risk. The plan is an ordered task list with declared dependencies, and validation criteria are written at S3.
- **D17. Delivery.** Queue only, visible blocked state, Slack digest on a cadence the engineer sets, no modal interrupts. The current stage, task, bindings, budget, and durable output are visible; cancellation is always available and returns through the queue with the partial record intact. No stage crosses a pending human boundary in the background.
- **D18. Measures** are computed from factory records only, with the reporting rules in section 8. Active attention and queue latency are separate measures; neither is inferred from the other.
- **D19. Memory split and judge separation** as in C3 and C4.
- **D20. Initial version scope.** Amended 2026-09-04 and tightened in v0.11. S0 to S4, with S4 automated through the primary runtime under the D14 bounds and C10 isolation; the S5 trusted preflight and deterministic blocking tier on immutable base/head views (the project's lint, types, and tests; secret, static-analysis, dependency-vulnerability and licence-policy controls; dependency resolution; size and scope; API-shape and behavioural-evidence checks; reviewer/quorum, waiver, freshness, and approval-binding controls); an S6 race guard and local review packet with the diff appended, reviewed before anything is pushed; and, on first approval, one draft pull request created by a trusted outbox worker with a separately hashed PR narrative, without a duplicated literal diff, as its description and GitHub's native diff as the diff surface. A later human-recorded revision follows the same checks and review before that worker updates the same draft PR under remote-head comparison. First creation completes the initial factory phase; it does not close the ticket outcome. Until automated S7 exists, a human records CI/review revisions, production exposure and incident coverage, and the eventual merge or abandonment in the same record. The LLM advisory pass at S5 and automated S7 wait until the planning rubrics have survived real tickets. The smoke/conformance bootstrap, trust profile and approvals, OS boundary, manual outcome shell, transactional outbox, and exact approval bindings are Initial safety controls, not Later machinery.
- **D21. Evidence process.** Revisions, production incidents, control defects, overrides, and abandoned tickets are tagged with a failure-mode ID at the exact source event or decision. Catalogue cost and frequency are computed from immutable tags; later disposition or resolution never erases an occurrence.
- **D22. Confluence sync.** One-way, human-facing artefacts only: brief, plan, decisions, review packet. Deferred past the initial version.
- **D23. Observability is a core requirement** from the initial version, as C5. The ledger and text report are Initial; a graphical dashboard may follow.
- **D24. Tooling candidates live in the PRD inputs**, `docs/prd/inputs.md`, not here. Code graphs, DAG orchestrators, durable workflow engines, sandbox implementations, and local trackers are adopted only when the adoption cites a constraint or a failure mode. C10 makes an OS-enforced sandbox mandatory for the production-capable pilot without prescribing its implementation.
- **D25. Scope ends at merge.** The eventual factory opens the PR, tracks its GitHub Actions runs through the GitHub MCP server, and stops when the human records or the factory observes merge or abandonment. Opening a draft PR completes the initial factory phase but not the ticket outcome (D33). Rollout, flag ramps, and production verification are the engineer's, outside the factory, for now. LaunchDarkly, Grafana, OpenSearch, and AWS are not agent tools until a cited stage requirement establishes a use inside this boundary.
- **D26. Factory as code with evals**, as C6. Skills, agents, rubrics, scripts, lints, and evals are versioned together. Smoke and conformance evals gate the first production-capable pilot and every reviewed factory pull request after the scaffold commit; recorded-ticket replay, calibrated graders, benchmarks, and the richer adoption gate arrive as evidence accumulates.
- **D27. Extensible by design**, as C7. The state table is the first orchestrator, not the last; durable workflow engines and DAG orchestrators are the expected direction, adopted when the state table demonstrably fails (D24).
- **D28. Context measures and initial success.** Ticket outcomes per window, cost per ticket, non-structural touchpoints, and queue latency are tracked from the initial version as context, never as success measures or improvement objectives. Reliability of the pipeline is the initial success criterion. The factory runs one ticket at a time until the full pilot-graduation gate in section 8 is met; only then may the owner raise the limit to two and later three. The parallel limit is configuration in the PRD, but changing it remains a recorded human decision.
- **D29. Touchpoints defined.** What the factory literature calls automation percent is recorded as non-structural touchpoints per ticket by tier, with the S3 and S6 gates excluded from the count. It is not optimised in the initial version; more human involvement is the intent while skills, agents, rubrics, and feedback loops are built. Its direction flips later, per step, under P10.
- **D30. Closed-loop improvement adopted**, bounded by C8: scored runs, an improvement pass over the factory repository, and benchmarks, with proposals landing only through reviewed changes. FM-22 names the drift C8 bounds. Cloud hosting, which the source treats as essential, is not adopted (D9).
- **D31. Routing in the manifest.** Runtime and model are named per stage and tier in the manifest and chosen from benchmark data, so multi-model operation is code, not convention.
- **D32. Pilot eligibility.** One T2 service, written in Java, one approved data class, and `small_feature` tickets only, accepted at S0. A candidate or actual sensitive-path change is rejected until the named independent owner can approve at S3 and S6 and the required-reviewer control has passed its conformance test. Widening the service, type, data-class, sensitive-path, or concurrency set is the owner's recorded decision only after section 8's pilot-graduation gate. Closes Q9.
- **D33. Factory phase is not ticket outcome.** In the initial pilot, creating the first approved draft pull request records factory-phase completion; approved revisions update that same PR without creating another factory completion. `merged` or `abandoned` records the actual ticket outcome and is entered manually until S7 observes it. External truth is recorded even when it reveals a stale-approval control defect. Completion, baseline comparison, and graduation use the outcome; operational latency may also show factory-phase duration.
- **D34. Trust is configured before execution.** The C9 trust profile and its immutable security and legal/data-governance approvals are setup gates and remain valid only for the exact profile hash and unexpired authority. Privacy Mode and a spend limit are necessary runtime settings, not sufficient data-governance evidence. An unset source scope, destination route, data class, provider term, retention rule, residency constraint, reader population, or approval blocks the operation rather than becoming an agent assumption.
- **D35. Isolation is Initial.** The production-capable pilot does not run an agent or repository-controlled build with the engineer's ambient authority. C10 is satisfied before S4 is enabled. A logical tool allowlist without an OS-enforced boundary is not sufficient.
- **D36. Approval is content-addressed.** C11's separate plan and final-review bindings are recorded with each approval. Expected S4 commits do not invalidate the plan approval they implement. Base-branch movement, a changed plan-bound input, a post-review commit, a changed check result, a changed packet, PR narrative, publication destination, or required-reviewer set creates a new affected subject. Approval expiry instead requires fresh quorum against the unchanged subject. Re-pinning is explicit and reruns affected stages.
- **D37. Roles and sensitive approval.** The operator may be the ordinary-ticket approver in the single-engineer pilot. A sensitive-path owner is a distinct human role and approves independently; absent that person and an enforceable record of their decision, the ticket is outside pilot scope. The final diff, not ticket wording, decides whether the role is required.
- **D38. Claims follow evidence.** Impact scans and API-shape checks use the names and limitations in C13. A blind spot is visible unresolved evidence, not a passing check. An authorised waiver is an explicit human judgment bound to the reviewed state and is reported separately from green evidence.
- **D39. Human control uses stable boundaries.** Current state and durable progress are visible, cancellation is always available, and no hidden autonomous work crosses a queue item. The factory does not require a person to watch or steer a running agent. Active attention is measured only at decision surfaces and is never equated with queue latency.
- **D40. Auditability, not deterministic replay.** C12 is the guarantee. Another engineer can reconstruct the stage's approved inputs, environment, actions, decisions, and outputs; no claim is made that a hosted model will reproduce identical output. A digest without a retained or immutable decision-relevant source is declared incomplete evidence.
- **D41. Eval bootstrap and graduation.** Smoke and conformance evals exist before the first production-capable draft PR, and the section 8 graduation gate controls expansion. Later graders and benchmarks may improve selection, but neither an empty eval scaffold nor ten PR openings satisfies this decision.
- **D42. Pilot configuration defaults.** Q10 to Q12 are closed. The pilot uses the configurable size gates and provisional token and wall-clock budgets in the PRD; the Standard size gate starts at 300 changed lines, and budgets are recalibrated from the first three pilot tickets rather than treated as permanent targets. Service tiers come from a hand-maintained versioned list, populated first for the pilot service. The question digest runs twice each working day by default; its times, weekdays, and channel remain engineer-owned configuration.

### Open

None.

Closed in v0.10: Q10 to Q12 became D42. Closed in v0.3: Q2 became D21, Q3 became D11, Q8 became D22. Closed in v0.2: Q1, Q5, Q6, and Q7 became D7 to D10. Q4, a fixed question cap per stage, was withdrawn because question count has to scale with ticket complexity.

## Revision history

- **v0.11, 2026-09-04.** Closed the implementation-contract ambiguities found in the final consistency audit. Trust governance now has a metadata-only bootstrap and audit path, explicit class joins, and approval authority binding without recursive guard logging. Approval expiry requires fresh quorum against the same immutable subject; publication destination is part of final approval. Stage wording now distinguishes runs from agent invocations and valid waived blind spots from green evidence. Baseline unavailability remains visible, production-incident coverage requires recorded exposure, and D20/D32 reflect the complete Initial controls and data-class gate.
- **v0.10, 2026-09-04.** Requirements-boundary audit incorporated without renumbering existing principles or failure modes. The pilot now opens a production-capable draft PR while keeping ticket outcome open to merge or abandonment through a manual PR-outcome shell. Added FM-23 unsafe execution, FM-24 data-boundary breach, and FM-25 stale approval; C9 to C13 define the trust profile, OS isolation, content-addressed approvals and base refresh, reconstructable audit, and honest evidence limits. C4 assigns uncalibrated semantic rubric lines to a named human instead of allowing a silent pass. C5 separates ticket stage runs from maintenance jobs. C6 requires smoke and conformance evals before the pilot and reviewed, eval-gated factory changes after the scaffold commit. The human contract now names operating roles, independent sensitive-path approval, stable visible and cancellable boundaries, non-blocking-question resolution, exact approval identity, and active attention separately from queue latency. S4 and repository builds are isolated from ambient authority; blind spots are not green; API-shape and service-impact claims are narrowed to their evidence. D14 and D15 clarify attempt and default semantics. D20, D25, D28, and D32 distinguish factory-phase completion from outcome and bind scope expansion to the new pilot-graduation gate. D42 closes Q10 to Q12 on the recommended configurable pilot defaults.
- **v0.9, 2026-09-04.** Consistency fixes from the PRD review. Stage map S1 no longer lists live SLIs and flags as products, matching C2. Section 6 review packet gains the assumption log after deviations. D11 names everything the tier drives in the initial version. D20 lists all seven blocking-tier scripts. No change to principles, catalogue, or constraints.
- **v0.8, 2026-09-04.** D20 amended on the owner's decision: S4 is automated from the initial version, the review precedes the pull request, and the initial version ends when the pull request is opened; S7 moves to Later. Stage map and D25 unchanged as the eventual scope.
- **v0.7, 2026-09-04.** Owner named. Q9 closed into D32 from the owner's answers after research packet R10. No change to principles, catalogue, stages, or constraints.
- **v0.6, 2026-09-04.** Absorbed the Warp closed-loop article. Added P11 collaborator, not black box, with a matching anti-goal and a "What this is" statement in section 1. Added FM-22 loop drift. Added C8 objective-bound, human-merged improvement; C6 now names the git repository and PR path. Section 8 gained a first-attempt reliability measure, a context block for tickets per window, cost per ticket, and non-structural touchpoints, and factory-version slicing; the exclusion list was rewritten. D5 amended; D28 to D31 added. The metrics disagreement is recorded as a decision: Warp's three are context, never objectives.
- **v0.5, 2026-09-04.** Scope fixed at PR merge with Actions tracking (S7 rewritten, D25). Grafana, LaunchDarkly, and OpenSearch removed from agent access. C2 generalised to production out of view. C5 made factory-internal. Added C6 factory as code with evals and C7 replaceable stages, with D26 and D27. D20 names the deterministic S5 scripts as MVP.
- **v0.4, 2026-09-04.** Added FM-20 hallucinated dependency and FM-21 state loss from own experience. Added C5 observability, D23, and D24. Opened `docs/prd/inputs.md` for tooling candidates.
- **v0.3, 2026-09-03.** Absorbed both research passes. Added P10, two anti-goals, FM-15 to FM-19, constraints C1 to C4, and D11 to D22. Reworded FM-09 from the measured interruption evidence. Rewrote the stage map for tiers, bounds, the two-tier S5, and the S6 exit. Rewrote the question format, delivery, and review packet order in section 6. Restricted section 8 to computed measures with reporting rules. Replaced the research agenda with a research record. Closed Q2, Q3, Q8. Opened Q9 to Q12. Note: the entry proposed as FM-20 in `synthesis-factories.md` enters here as FM-19, and the proposed FM-19 became C1.
- **v0.2, 2026-09-03.** Closed Q1, Q5, Q6, Q7 into D7 to D10. Withdrew Q4. Replaced the fixed question cap with the gate-plus-rounds rule and made the attention budget relative to ticket complexity. Environment access set to MCP servers.
- **v0.1, 2026-09-03.** First draft.
