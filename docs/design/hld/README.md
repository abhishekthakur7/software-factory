# Soft-factory high-level design: layered diagrams

| | |
|---|---|
| Status | Draft v0.3 |
| Date | 2026-09-07 |
| Owner | Abhishek Thakur |
| Derived from | `docs/prd/prd.md` v0.18 and its parts; `docs/design/milestones.md` v0.6 (the 25 blocks, the 11 crossings, Appendix A row map, Appendix B crossings); `docs/charter.md` v0.14 |
| Layers | Layer 1: one bird's-eye view and one ticket walk. Layer 2: one file per domain. Layer 3 does not exist yet; it is written per block just before that block is coded, as `milestones.md` section 0 says |

## 1. How to read

The factory is drawn in two layers so that no single picture has to hold everything. Layer 1 shows six domains, the components inside each, and the eleven crossings between domains; a second Layer 1 file walks one ticket across the domains as a sequence. Layer 2 has one file per domain, showing each component's parts, the edges inside the domain, and the crossings at its border. Every node in a Layer 2 file is a component or part of the register in section 4; every edge across a domain border is one of the eleven crossings in section 5. A reviewer checks a picture row by row through the derivation table at the end of each file, which maps components and parts to `milestones.md` blocks, requirement rows and the step at which they first exist.

**Marks.** Everything unmarked exists at Milestone A, the walking skeleton on synthetic fixtures. `(AB)` marks what `milestones.md` section 3 builds between Milestone A and Milestone B: the OS policy, the copy-on-write copies, the loopback proxy, the escape suite, the real outside reads and writes and their credentials, the pilot repository and its configuration, the frozen baseline. `(B)` marks what section 3 places at Milestone B: the manual outcome record, the graduation gate, the first real-ticket fixture. `(Later)` marks what the PRD defers: a dashed node inside the component that would grow, joined to the part it grows from by one dotted edge, never a box on the main path. A dotted edge marks a crossing or part that first exists at the step in its label. A thick edge marks the main ticket path and nothing else. Shaded red is untrusted: the sandbox interior and the content of outside systems. Shaded blue is versioned content under `factory/`, read-only at run time. Shaded grey is the record, state on disk that the runner alone writes.

**Trust.** Three rules from the charter apply everywhere and are not repeated on the pictures: the person is trusted, the runner process is trusted, and anything inside a sandbox is not. Ticket and repository text is untrusted instruction wherever it crosses; it never selects a tool, recipe, mount, model, endpoint or credential. Every content-bearing crossing passes the guard (C5) and leaves one `guard_decision` row; the guard's seats are drawn once, in `L2-control-plane.md`, and every other file states the rule instead of redrawing it. Every command and invocation passes the stage interface (C1).

## 2. The domain rule

A component sits in the domain where its code runs or its file lives, and under whose trust it acts. Domain 1 is the exception the rule names: it is the person's view, and the code that renders it is C1.

| # | Domain | What it holds | Trust |
|---|---|---|---|
| 1 | Human surface | What the person sees and does: the person and roles, the list view as shown with its queue items, questions as read and answered, approvals, waivers and the governance view as decided. No runner code; C1 renders it | Trusted (the person) |
| 2 | Control plane | The runner: one Python process per `factory` command, no daemon; the command, the state machine and the fence, run orchestration, binding and freshness, the guard, the stage drivers, the checks and gates, external access, git-tree operations | Trusted |
| 3 | Execution boundary | The trusted code whose only job is to build and police the wall around every agent or build run (adapter and envelope; launcher, recipe runner, OS policy, loopback proxy) and the untrusted interior (agent, codegraph, recipe execution, copies) | Wall trusted; interior untrusted, stated per component |
| 4 | Record | State on disk that the runner alone writes: the SQLite ledger, artefact files and per-run directories under `runs/`, git trees (the pinned source checkout at the path `project.yaml` names, the per-ticket clone and worktree under `runs/`), measure views and the baseline | Trusted, single writer |
| 5 | Factory as code | Versioned content under `factory/`, read-only at run time, every file hashed by the manifest: manifest, agents and skills, rubrics and checklists, context index, policies and configuration, scripts, fixtures and evals | Read-only content |
| 6 | External systems | Everything outside the machine plus the two host facilities the runner trusts: Atlassian (Jira, Confluence), GitHub, Slack, the hosted model, the credential store and scheduler, registries and vulnerability feeds | Content untrusted (shaded red); the credential store and scheduler are trusted host facilities and are not shaded |

**Where a data block is drawn.** A data block of `milestones.md` (queue item and decision, question and assumption log, approval and quorum, binding, tag) is one or more tables in the ledger (R1), listed once there. Its contract is drawn where its rows are decided: the person's decisions (queue item, answer, accepted default, approval, waiver, governance approval, human tag) in domain 1; runner-computed rows (binding, subject hash, tuple, mechanical tag, escalation cause) in domain 2 at the component that computes them.

## 3. The files

| File | Layer | Shows |
|---|---|---|
| [L1-bird-view.md](L1-bird-view.md) | 1 | Six domains, 34 components, eleven crossings; a second diagram with the six domains alone |
| [L1-ticket-walk.md](L1-ticket-walk.md) | 1 | One ticket from `intake` to the recorded outcome across the domains as a sequence; the blocking-question loop and the two S5 red-exit loops |
| [L2-human-surface.md](L2-human-surface.md) | 2 | H1 to H4; the touchpoints along the state path |
| [L2-control-plane.md](L2-control-plane.md) | 2 | C1 to C9; the ticket state machine of PRD 2.3, drawn once; the S5 gate order |
| [L2-execution-boundary.md](L2-execution-boundary.md) | 2 | G1 to G3; the wall by stage; one invocation's lifecycle |
| [L2-record.md](L2-record.md) | 2 | R1 to R3 and R5; the relationships that carry integrity; the artefact chain |
| [L2-factory-as-code.md](L2-factory-as-code.md) | 2 | F1 to F8 over the `factory/` layout; run-time resolution; a change landing |
| [L2-external-systems.md](L2-external-systems.md) | 2 | E1 to E6; credential roles and routes |

## 4. The component register

The ids are the Mermaid node ids in every file. Blocks are `milestones.md` section 1. R4 and G4 of v0.1 are folded (section 6) and their ids are not reused.

| Id | Component | Domain | Blocks |
|---|---|---|---|
| H1 | Person and roles | 1 | charter section 6; R-F-13 |
| H2 | List view and queue items | 1 | Queue item and decision |
| H3 | Questions and assumption log | 1 | Question and assumption log |
| H4 | Approvals, waivers and governance view | 1 | Approval and quorum |
| C1 | `factory` command (stage interface) | 2 | Stage interface |
| C2 | Ticket state machine and the fence | 2 | Ticket and its state; Factory tree and change control (R-F-11) |
| C3 | Run orchestration | 2 | Run |
| C4 | Binding and freshness guard | 2 | Binding |
| C5 | Guard | 2 | Guard; Trust profile (enforced) |
| C6 | Stage drivers | 2 | Run (how a stage runs); Artefact (runner-written kinds); Rubric (script lines) |
| C7 | External access | 2 | External access |
| C8 | Git-tree operations | 2 | Git trees (operations) |
| C9 | Checks and gates | 2 | Check |
| G1 | Runtime adapter and invocation envelope | 3 | Invocation and runtime adapter |
| G2 | The wall: launcher, recipe runner, OS policy, loopback proxy | 3 | Sandbox; Recipe (validator and execution by id) |
| G3 | Sandbox interior | 3 | Sandbox (inside); Context index (codegraph) |
| R1 | SQLite ledger | 4 | Record; every data block's table |
| R2 | Artefact files and per-run directories | 4 | Artefact |
| R3 | Git trees | 4 | Git trees (data) |
| R5 | Measure views and baseline | 4 | Record (measures) |
| F1 | Tree and change control | 5 | Factory tree and change control |
| F2 | Manifest | 5 | Manifest |
| F3 | Agent definitions and skills | 5 | Agent definition; Skill |
| F4 | Rubrics and checklists | 5 | Rubric |
| F5 | Context index | 5 | Context index |
| F6 | Policies, configuration and catalogue | 5 | Trust profile; Recipe (catalogue file); PRD section 8 files; catalogue |
| F7 | Scripts | 5 | versioned here, executed by C6, C9, C7 and C1 |
| F8 | Fixtures and evals | 5 | Fixtures and evals |
| E1 | Atlassian server: Jira and Confluence | 6 | |
| E2 | GitHub | 6 | |
| E3 | Slack | 6 | |
| E4 | Hosted model endpoint | 6 | |
| E5 | Host credential store and scheduler | 6 | |
| E6 | Package registries and vulnerability feeds | 6 | |

Codegraph is third-party software but runs inside the sandbox, so it is a part of G3, not an external system.

**Block homes.** Each of the 25 blocks has one home of record, the component whose Layer 3 section it will attach to; a second component may draw the block's use.

| Block | Home | Also drawn in |
|---|---|---|
| Agent definition, Skill | F3 | G3 (as loaded) |
| Rubric | F4 | C6 (script lines run), H4 (verdicts recorded) |
| Manifest | F2 | C1 (resolved), G1 (envelope) |
| Context index | F5 | G3 (codegraph) |
| Trust profile | F6 | C5 (enforced), H4 (governance approval) |
| Fixtures and evals | F8 | |
| Factory tree and change control | F1 | C2 (the fence) |
| Ticket and its state | C2 | R1 (table) |
| Run | C3 | C6 (drivers), R1 (table) |
| Artefact | R2 | R1 (registry table), C6 (assembly) |
| Queue item and decision | H2 | C1 (rendered), R1 (table) |
| Question and assumption log | H3 | C6 (S2 driver), R1 (tables) |
| Approval and quorum | H4 | C9 (reviewer set), R1 (tables) |
| Binding | C4 | R1 (tuples) |
| Tag | R1 | H2 (human tags), C2 and C3 (mechanical tags) |
| Record | R1 | R5 (views), C1 (export, import, purge, report) |
| Stage interface | C1 | |
| Invocation and runtime adapter | G1 | |
| Sandbox | G2 | G3 (interior), R2 (per-run directories) |
| Recipe | G2 | F6 (catalogue file), G3 (execution) |
| Check | C9 | F7 (scripts) |
| Guard | C5 | |
| External access | C7 | |
| Git trees | R3 | C8 (operations) |

## 5. The crossings

From `milestones.md` section 2 and Appendix B, which state in full what crosses and what never crosses each edge.

| Id | Crossing | From | To | Holds from |
|---|---|---|---|---|
| X1 | The person acts | H2 (and the governance view of H4) | C1; back from C1 to H2 | A |
| X2 | The runner writes and reads its record | C1 to C9 | R1, R2, R3 | A |
| X3 | The runner dispatches a run | C6, C3 | G1 | A |
| X4 | The factory tree is read at run time | F2 (and every file it references) | C1, which resolves the manifest; C9 reads the policy files the manifest hashes (waiver policy, security checks) | A |
| X5 | The runner reads from and writes to outside systems | C7 | E1, E2, E3; E5 to C7 (credentials by role) and E5 to C1 (the scheduler invokes `factory digest`, never a stage) | Runtime key and stubs at A; real reads and writes and the other credentials AB |
| X6 | The agent reaches the hosted model and attached servers | G3 directly at A; G2 (proxy) from AB | E4; E1 at S1 (AB); E6 (AB) | A for the model; AB for the proxy, Atlassian and registry legs |
| X7 | Mounts into a run | R2, R3 | G2 | A; copies and the unwritable results subpath of the per-run directory AB |
| X8 | The person sees outside systems | E2, E3 | H1 | AB |
| X9 | The factory changes | H1, via a GitHub pull request | F1 | A |
| X10 | Run findings return to the tree | R2 (the governed export), by the engineer's reviewed pull request | F8 | B once; the rest Later |
| X11 | The sandbox wall | G2 (launcher) | G3 | A; OS policy and proxy AB |

## 6. What changed in v0.2

Seven fresh-context adversarial reviews of v0.1 (completeness in two halves, grouping, edges and arrangement, simplicity and qualities, consistency, charter conformance; about 205 findings, 27 blocking) were applied. Structural changes: domain 1 restated as the person's view with its code in C1; the reviewer-set derivation and the question gate moved to the control plane; G4 Recipes folded into G2 and F6; R4 Tags and incidents folded into R1; R5 narrowed to measure views and the baseline; C9 Checks and gates split out of the stage drivers, which no longer chain to each other; the guard given its seats on every crossing; nothing in the execution boundary writes the record; the runtime key's path fixed as X5, X3, X11; the transition table drawn once and completed; one convention for milestone marks; the crossing ids restored after a rename had spilled into the crossings table. The validation findings that the reviews raised against the requirements themselves are in [findings.md](findings.md) for the owner's decision.

## 7. What changed in v0.3

The owner's decisions of 2026-09-07 on the high-level design findings ([findings.md](findings.md)) were applied. The runner-taken disjoint base advance moves to Later (charter D43): Initial keeps only the human `refresh_base` of R-S5-12, and R-S5-14's loop and edges are withdrawn from the pictures that carried it. No agent runs at S0: the scrutiny paragraph is filled by a script from a template, and the manifest's S0 agent, skill and model entries are null. Deviation rows replace the `deviation_list` artefact kind: the runner writes them from the S4 hand-back into the `deviation` table, the one shape. The output and results directories fold into one per-run directory under `runs/tickets/<id>/`, with a writable `out/` subpath and a read-only `results/` subpath. Inbound callers become context index entries of kind `caller`; `service-callers.yaml` is withdrawn. The `factory/` layout changes: `rubrics/` gains a `checklists/` subdirectory, `scripts/` splits into `scripts/checks/` and `scripts/tools/`, and `service-callers.yaml`, `digest.yaml` and `budgets.yaml` fold into the context index, the `digest` key of `project.yaml`, and `tiers.yaml`. X2 (the runner writes and reads its record) now names git trees among its targets, and holds the pinned source checkout at the path `project.yaml` names, outside this repository. None of this changes the register: 34 components, as in v0.2.

## 8. What these diagrams are not

Not an implementation: no module names, no schemas beyond table names, no command syntax beyond the `factory` verbs the PRD fixes. Not a replacement for `milestones.md`: block shapes per step and the row map live there. Not Layer 3: the pieces that carry risk (the state machine, the S5 gate, the wall, the outbox and its intent states) get their own two-deep diagrams per block just before that block is coded.

## Revision history

- **v0.3, 2026-09-07.** The owner's decisions of 2026-09-07 on the high-level design findings (`findings.md`) applied to the diagrams; section 7 lists the changes. Cites charter v0.14, PRD v0.18, milestones v0.6. 34 components, unchanged.
- **v0.2, 2026-09-07.** After seven adversarial reviews (about 205 findings, 27 blocking); section 6 lists the changes. Two fresh confirmation reviews then checked every blocking and major finding (127 of 146 closed, the rest either requirement items in findings.md or residuals), and a residual pass applied the 39 residuals: the guard's persistence seat drawn, the structure check invoked at every stage, the digest's field rule and the governance path restored to the control plane, the scheduler's invocation and the policy-file reads admitted to X5 and X4, one mark convention and exact register names throughout. 34 components.
- **v0.1, 2026-09-07.** First version. Nine readers extracted components, data, flows, crossings and simplification candidates from the PRD parts, the charter and `milestones.md`; the register and domain rule were fixed from the extracts; eight authors drew the files. 35 components.
