# Layer 2: Record

| Field | Value |
|---|---|
| Status | Draft v0.3 |
| Date | 2026-09-07 |
| Owner | Abhishek Thakur |
| Derived from | docs/prd/prd.md v0.18; docs/design/milestones.md v0.6; docs/charter.md v0.14 |
| Layer | Layer 2 — domain 4, Record |
| Domain rule | A component sits in the domain where its code runs or its file lives, and under whose trust it acts. **Record**: state on disk under `runs/` that the runner alone writes: the SQLite ledger, artefact files and per-run directories under `runs/`, git trees (the pinned source checkout at the path `project.yaml` names, the per-ticket clone and worktree under `runs/`), measure views and the baseline. A data block of `milestones.md` (queue item and decision, question and assumption log, approval and quorum, binding, tag) is one or more tables in the ledger, listed once there — R1 below; its contract is drawn where its rows are decided: the person's decisions in domain 1, runner-computed rows in domain 2 at the component that computes them. |

## How to read this

Three diagrams. The first shows R1, R2, R3 and R5 — the SQLite ledger's table groups (including `utility_run` and the merged `tag`/`incident_observation` group), the artefact directory, git trees, and the measure views and baseline — plus the three border stubs where another domain touches the record: a single "trusted runner" stub (C1 to C9) for every write and read-back over X2, the launcher's mounts (G2) over X7, and the one governed export that becomes a fixture (F8) over X10. The record answers only the runner; it never hands content straight to the human surface — queue items, the report and governed artefact content reach the person through C1 over X1, drawn in `L2-human-surface.md`. The second diagram shows the relationships that carry the design's integrity across tables, independent of domain layout. The third walks the artefact kinds in production order, marking which stage writes and reads each, whether the content is agent-written or runner/script-written, and naming where two or more PRD kinds fold into one node. Every crossing edge into or out of this domain passes the guard (C5) and leaves one `guard_decision` row in R1; the guard's seats are drawn once, in `L2-control-plane.md`, and are not redrawn here. Unmarked parts exist at Milestone A; `(AB)` and `(B)` mark what is built or first populated at those steps; a dotted edge or node border marks something that holds only from AB, B, or Later; grey fill marks the record (this whole file); blue fill marks the one Factory-as-code stub (F8) a crossing reaches. Left out deliberately: the full internals of C1 to C9, G2 and F8 (their own Layer 2 files), and the stage-by-stage sequence (the Layer 1 ticket-walk file).

## Diagram 1: R1, R2, R3 and R5, and the border

The SQLite ledger's table groups, the artefact directory's parts, git trees' data, and the record's measure views and baseline, with the crossings that touch another domain at this border.

```mermaid
flowchart TB
  C_STUB["Control plane C1–C9<br/>(trusted runner)"]
  LAUNCHER_STUB["Launcher G2<br/>(execution boundary wall)"]
  F8_STUB["Fixtures and evals F8<br/>(factory as code)"]

  subgraph R1["R1 SQLite ledger"]
    R1_ticket["ticket"]
    R1_run["stage_run (parent_run_id<br/>for children), utility_run,<br/>tool_call"]
    R1_artefact["artefact: kind, version,<br/>hash, supersession, class,<br/>redaction state; untrusted-<br/>instruction mark on ticket/<br/>repo text, imported prose<br/>(R-T-9, R-T-4)"]
    R1_queue["queue_item, question,<br/>answer, assumption"]
    R1_approval["reviewer_set,<br/>approval_record, waiver"]
    R1_evidence["evidence_tuple"]
    R1_guard["guard_decision"]
    R1_check["check_result, human_verdict"]
    R1_deviation["deviation, generated_test"]
    R1_tag["tag: human (send_back, abandon,<br/>override, revision_after_approval,<br/>packet_defect); mechanical<br/>(stale_index, escalation cause,<br/>control_defect); policy_exception<br/>(on a valid waiver, grants nothing);<br/>resolution chains (resolves_tag_id)<br/><br/>incident_observation: event root,<br/>disposition, coverage<br/>(not_deployed A; rest B)"]
    R1_outbox["external_write<br/>(outbox intent, receipt)"]
    R1_index["index_use"]
    R1_baseline["baseline_measure (AB)"]
    R1_later["Later: score, human_signal,<br/>proposal, benchmark,<br/>fixture_candidate, each<br/>created with the row that<br/>first writes it"]
    R1_note["append-only outside R-T-3<br/>exceptions: ticket lifecycle,<br/>question.state, run/outbox/queue fields"]
  end

  subgraph R2["R2 Artefact files and per-run directories"]
    R2_dir["runs/tickets/&lt;id&gt;/<br/>per-ticket directory"]
    R2_kinds["14 kinds: ticket source →<br/>… → packet, PR body → export<br/>(full order in diagram 3)"]
    R2_dirs["per-run directory:<br/>out/ (stage writes,<br/>runner registers, hand-back);<br/>results/ (runner-only,<br/>unwritable inside from AB)"]
  end

  subgraph R3["R3 Git trees (data)"]
    R3_checkout["pinned source checkout:<br/>fixture project (A);<br/>pilot, scratch repos (AB)"]
    R3_worktree["per-ticket clone<br/>and worktree"]
    R3_copies["base/head checkouts (A);<br/>copy-on-write copies (AB)"]
    R3_shas["base_sha, target_base_sha,<br/>head_sha"]
  end

  subgraph R5["R5 Measure views and baseline"]
    R5_views["views: charter §8 primary<br/>and secondary measures;<br/>separate context block<br/>(forbidden-view list,<br/>context label; R-O-5, R-O-12);<br/>reliability-view exclusions;<br/>unavailable-measure display"]
    R5_baseline["frozen baseline<br/>cohort (AB)"]
  end

  C_STUB -->|"X2 write: every ticket, run,<br/>artefact, queue, approval,<br/>evidence, guard, check, tag,<br/>outbox, index, baseline row"| R1
  R1 -->|"X2 read: ticket state,<br/>queue items, approvals,<br/>waivers, view rows for report"| C_STUB

  C_STUB -->|"X2 write: registers<br/>governed artefact files"| R2
  R2 -->|"X2 read: registered<br/>artefact content"| C_STUB

  C_STUB -->|"X2 write: clone, worktree,<br/>copies, SHAs the runner<br/>prepares"| R3
  R3 -->|"X2 read: current SHAs,<br/>worktree state"| C_STUB

  R1 -->|"views over the ledger;<br/>baseline rows (AB)"| R5
  R5 -->|"X2 read: measures<br/>for the report"| C_STUB

  R1_note -.-> R1_ticket
  R1_note -.-> R1_evidence

  R1 ~~~ R2
  R2 ~~~ R3
  R3 ~~~ R5

  R2_dirs -->|"X7 mounts; back: out/ files"| LAUNCHER_STUB
  R3_worktree -->|"X7 mounts: worktree,<br/>base/head copies"| LAUNCHER_STUB

  R2_kinds -.->|"X10 (B) governed export →<br/>fixture, by the engineer's<br/>reviewed pull request"| F8_STUB

  classDef untrusted fill:#fde8e8,stroke:#b91c1c
  classDef later stroke-dasharray:5 5,color:#666
  classDef content fill:#eef6ff
  classDef store fill:#f3f4f6

  class R1_ticket,R1_run,R1_artefact,R1_queue,R1_approval,R1_evidence,R1_guard,R1_check,R1_deviation,R1_tag,R1_outbox,R1_index,R1_baseline,R1_note store
  class R1_later later
  class R2_dir,R2_kinds,R2_dirs store
  class R3_checkout,R3_worktree,R3_copies,R3_shas store
  class R5_views,R5_baseline store
  class F8_STUB content
```

## Diagram 2: the relationships that carry integrity

Only the bindings the requirement rows fix, independent of which physical table stores which side; each edge names the row that requires it. `reviewer_set`, `human_verdict` and `assumption` are drawn as nodes here for the first time, to carry the evidence tuple's inbound bindings; the dashed note carries the tuple's fields that come from outside this domain (manifest, trust-profile, recipe-set, sandbox and toolchain hashes), so the picture does not claim a table this domain does not hold.

```mermaid
flowchart LR
  NT_ticket["ticket"]
  NT_stage_run["stage_run"]
  NT_tool_call["tool_call"]
  NT_artefact["artefact"]
  NT_queue_item["queue_item"]
  NT_answer["answer"]
  NT_assumption["assumption"]
  NT_approval_record["approval_record"]
  NT_reviewer_set["reviewer_set"]
  NT_human_verdict["human_verdict"]
  NT_waiver["waiver"]
  NT_tag["tag"]
  NT_evidence_tuple["evidence_tuple"]
  NT_check_result["check_result"]
  NT_external_write["external_write<br/>(outbox intent)"]
  NT_guard_decision["guard_decision"]
  NT_incident_observation["incident_observation<br/>(incl. coverage)"]
  NT_note_external["manifest, project-config,<br/>trust-profile, recipe-set,<br/>sandbox, toolchain hashes<br/>(F2/F6/G1/G2 fields, not<br/>tables of this domain)"]

  NT_ticket -->|"R-T-12"| NT_stage_run
  NT_stage_run -->|"one row per call"| NT_tool_call
  NT_stage_run -->|"R-T-2 produces"| NT_artefact
  NT_artefact -->|"R-T-3 supersedes"| NT_artefact
  NT_queue_item -->|"R-H-1, R-H-4"| NT_answer
  NT_answer -->|"R-S2-11 accepted default"| NT_assumption
  NT_queue_item -->|"R-H-4, R-H-12"| NT_approval_record
  NT_queue_item -->|"R-H-4 waiver"| NT_waiver
  NT_queue_item -->|"R-T-6 human transition"| NT_tag
  NT_ticket -->|"R-H-11, R-O-13"| NT_incident_observation

  NT_deviation["deviation (rows written<br/>at the S4 hand-back)"]
  NT_deviation -->|"R-T-10 binds: deviation-<br/>set hash (review tuple)"| NT_evidence_tuple
  NT_artefact -->|"R-T-10 binds: ticket-source,<br/>brief, criteria, plan hashes"| NT_evidence_tuple
  NT_assumption -->|"R-T-10 binds: current<br/>assumption-set hash"| NT_evidence_tuple
  NT_answer -->|"R-T-10 binds: question-<br/>resolution-set hash"| NT_evidence_tuple
  NT_human_verdict -->|"R-T-10 binds: human-<br/>verdict-set hash"| NT_evidence_tuple
  NT_reviewer_set -->|"R-T-10 binds: planned,<br/>actual, effective<br/>reviewer-set hash"| NT_evidence_tuple
  NT_waiver -->|"R-T-10 binds: plan/review-<br/>waiver-set hash"| NT_evidence_tuple
  NT_ticket -->|"R-T-10 binds: base_sha,<br/>target_base_sha, head_sha"| NT_evidence_tuple
  NT_note_external -.->|"R-T-10 binds<br/>(not this domain's table)"| NT_evidence_tuple

  NT_evidence_tuple -->|"R-T-10 subject"| NT_approval_record
  NT_evidence_tuple -->|"R-T-10 binds"| NT_check_result
  NT_evidence_tuple -->|"R-T-11 subject"| NT_external_write

  NT_guard_decision -->|"guard_decision_id"| NT_tool_call
  NT_guard_decision -->|"guard_decision_id"| NT_artefact

  classDef store fill:#f3f4f6
  classDef note stroke-dasharray:3 3,fill:#fff7e6,stroke:#d97706,color:#666
  class NT_ticket,NT_stage_run,NT_tool_call,NT_artefact,NT_queue_item,NT_answer,NT_assumption,NT_approval_record,NT_reviewer_set,NT_human_verdict,NT_waiver,NT_tag,NT_evidence_tuple,NT_check_result,NT_external_write,NT_guard_decision,NT_incident_observation store
  class NT_note_external note
```

## Diagram 3: the artefact chain

The Initial artefact kinds in the order stages produce and consume them, each labelled with the writing and reading stage and whether the content is agent-written or runner/script-written; `pr_checks_summary` is Later and not shown. Two folds keep the fourteen PRD kinds to twelve nodes: `criteria and question set` (K3) merges the criteria file and its per-round question sets; `tool inputs and results` (K9) merges `tool_input` and `tool_result`. `packet` and `pr_body` are drawn as two nodes (K11, K12), not folded, because R-S6-1 gives them different readers and a different diff rule; both share one evidence table, fed by deviation rows written at the S4 hand-back, the check evidence, the readiness table and the tool record. Deviation rows are `deviation` table rows, not a file, so no artefact-kind node carries them here; `R1_deviation` in diagram 1 is where they live. Every edge below is a plain arrow: the production order runs left to right along the chain, and thick and dotted marks are left to the meanings `README.md` gives them (the main ticket path and the AB/B/Later steps), neither of which applies to this diagram.

```mermaid
flowchart LR
  K1["ticket source<br/>writes S0 · reads S1, S2<br/>runner-written<br/>untrusted instruction (R-T-9)"]
  K2["brief<br/>writes S1 · reads S2, S3<br/>agent-written"]
  K3["criteria and question set<br/>writes S2 · reads S3<br/>agent-written"]
  K4["risk map<br/>writes before S3 · reads S3<br/>runner script (risk_map)"]
  K5["plan (readiness table)<br/>writes S3 · reads S4, H4<br/>agent + runner script"]
  K6["handoff<br/>writes after S3 · reads S4<br/>runner script (handoff_ready)"]
  K8["failure history<br/>writes S4 escalation<br/>reads: escalation item (human)<br/>runner-compiled"]
  K9["tool inputs and results<br/>writes every agent stage<br/>reads: S5, S6 audit; runner-written"]
  K10["check evidence<br/>writes S5 · reads S6<br/>runner-written"]
  K11["packet<br/>writes S6 · reads H4 (reviewer)<br/>exact branch diff appended<br/>runner script assembled"]
  K12["pr_body<br/>writes S6 · reads outbox (C7)<br/>no literal diff, relies on<br/>GitHub's native diff view<br/>runner script assembled"]
  K13["export<br/>writes on demand · reads import, F8<br/>runner-written"]

  K1 --> K2 --> K3 --> K4 --> K5 --> K6
  K6 -->|"S4 escalation"| K8
  K6 --> K10
  K6 -->|"deviation rows,<br/>written at S4 hand-back"| K11
  K6 -->|"deviation rows,<br/>written at S4 hand-back"| K12
  K10 --> K11
  K10 --> K12
  K5 -->|"readiness table (R-S3-21),<br/>shared evidence table (R-S6-1)"| K11
  K5 -->|"readiness table (R-S3-21),<br/>shared evidence table (R-S6-1)"| K12
  K9 -->|"feeds"| K10
  K9 -->|"feeds"| K11
  K9 -->|"feeds"| K12
  K11 --> K13

  classDef store fill:#f3f4f6
  class K1,K2,K3,K4,K5,K6,K8,K9,K10,K11,K12,K13 store
```

## Derivation table

| Component or part | `milestones.md` block | Requirement rows | First step |
|---|---|---|---|
| R1 SQLite ledger (the file) | Record (#17) | R-T-1, R-T-3, R-T-4, R-O-4, R-O-5, R-O-12 | A |
| R1 — ticket | Ticket and its state (#9) | R-T-5, R-S0-5, R-S2-12, R-H-11 | A (manual outcome fields B) |
| R1 — stage_run, utility_run, tool_call | Run (#10) | R-T-12, R-O-1, R-I-6, R-S2-3, R-S4-5, R-H-13 | A |
| R1 — artefact | Artefact (#11) | R-I-12, R-S3-14, R-S3-19, R-S3-21, R-S4-1, R-S4-2, R-S6-1, R-S6-2; R-T-2 | A (unregistered-file isolation test AB) |
| R1 — queue_item, question, answer, assumption | Queue item and decision (#12); Question and assumption log (#13) | R-H-1, R-H-12, R-S2-5 to R-S2-14 | A (full action set B via R-H-4) |
| R1 — reviewer_set, approval_record, waiver | Approval and quorum (#14) | R-S0-5, R-S5-13, R-S6-6, R-S6-7, R-H-8, R-H-12, R-F-13 | A (graduation gate B via R-O-13, R-I-10) |
| R1 — evidence_tuple | Binding (#15) | R-T-10, R-S3-15, R-S3-20, R-S6-10 | A |
| R1 — guard_decision | Guard (#23) | secondary of R-T-4, R-T-9 (0 primary rows) | A |
| R1 — check_result, human_verdict | Check (#22); Rubric (#3, human_verdict via R-S3-20) | R-S5-4, R-S5-5, R-S5-10, R-S3-20 | A |
| R1 — deviation, generated_test | folded into Artefact (ms:73 fold note, no dedicated Appendix A row); Record (generated_test, via R-T-3) | R-S4-2, R-T-3 | A (kept-share filter R-S4-7 Later) |
| R1 — tag, incident_observation | Tag (#16); incident_observation rides Ticket-and-its-state (R-S4-6, secondary tag; R-H-11, primary), Approval-and-quorum (R-H-8), Record (R-O-13, secondary) — no dedicated block | R-T-6, R-S4-6, R-H-11, R-O-13 | A (tag); A/B split (incident_observation) |
| R1 — external_write (outbox) | External access (#24) | R-T-11 | A (stub); AB (real push, R-S6-3) |
| R1 — index_use | Context index (#5) | R-S1-7, R-F-6 | A |
| R1 — baseline_measure | Record (#17), secondary External access | R-O-6 | AB |
| R1 — Later tables (score, human_signal, proposal, benchmark, fixture_candidate) | Fixtures and evals (#7); External access (#24, human_signal via R-S7-6) | R-O-10, R-F-10, R-F-12, R-S7-6, R-F-15 | Later (each created with the row that first writes it, R-T-1) |
| R1 — append-only note | Record (#17) | R-T-3 | A |
| R2 Artefact files and per-run directories | Artefact (#11) | R-T-2, R-S6-1 | A (row at AB in Appendix A: the isolation or per-run-directory enforcement it names arrives with the OS policy) |
| R2 — per-ticket directory | Artefact (#11) | R-T-2 | A (row at AB in Appendix A: the isolation or per-run-directory enforcement it names arrives with the OS policy) |
| R2 — kinds (as a group) | Artefact (#11); secondary Record (export directory, via R-T-4) | R-S3-14, R-S3-21, R-S4-1, R-S4-2, R-S6-1, R-S6-2, R-T-4 | A |
| R2 — per-run directory (out/, results/) | Sandbox (#20) | R-I-14, R-I-17 | A (results/ subpath unwritable inside AB) |
| R3 Git trees (data) | Git trees (#25) | secondary R-S4-10, R-S5-12 | A |
| R3 — pinned source checkout | Git trees (#25) | R-S5-12 | A (pilot, scratch repos AB) |
| R3 — per-ticket clone and worktree | Git trees (#25) | R-S4-10 | A |
| R3 — base/head checkouts and copies | Git trees (#25) | R-S5-12 | A (copy-on-write AB) |
| R3 — SHAs (base, target-base, head) | Git trees (#25) | R-S5-12 | A |
| R5 Measure views and baseline | Record (#17) | R-O-4, R-O-5, R-O-12 | A (baseline AB) |
| R5 — views (primary, secondary, context block) | Record (#17) | R-O-4, R-O-5, R-O-12 | A |
| R5 — frozen baseline cohort | Record (#17), secondary External access | R-O-6 | AB |
| K1 ticket source | Artefact (#11) | R-T-2 | A (row at AB in Appendix A: the isolation or per-run-directory enforcement it names arrives with the OS policy) |
| K2 brief | Artefact (#11) | R-T-2 | A (row at AB in Appendix A: the isolation or per-run-directory enforcement it names arrives with the OS policy) |
| K3 criteria and question set | Artefact (#11) | R-S3-19 | A |
| K4 risk map | Artefact (#11) | R-S3-11 | A |
| K5 plan (readiness table) | Artefact (#11) | R-S3-14, R-S3-18, R-S3-19, R-S3-21 | A |
| K6 handoff | Artefact (#11) | R-S4-1 | A |
| K8 failure history | Artefact (#11); secondary Ticket-and-its-state (R-S4-6), Approval-and-quorum (R-H-8) | R-S4-6, R-H-8 | A |
| K9 tool inputs and results | Invocation and runtime adapter (#19), secondary Artefact | R-I-17 | A (row at AB in Appendix A: the isolation or per-run-directory enforcement it names arrives with the OS policy) |
| K10 check evidence | Artefact (#11), secondary Check | R-S5-4, R-S5-5, R-S5-10 | A |
| K11 packet | Artefact (#11) | R-S6-1, R-S6-2 | A |
| K12 pr_body | Artefact (#11) | R-S6-1 | A |
| K13 export | Record (#17) | R-T-4 | A |
| C_STUB (border stub, C1–C9) | Stage interface (#18) and others; full derivation in L2-control-plane.md | X2 (Appendix B) | A |
| LAUNCHER_STUB (border stub, G2) | Sandbox (#20); full derivation in L2-execution-boundary.md | X7 (Appendix B) | A (copies and the unwritable results subpath of the per-run directory AB) |
| F8_STUB (border stub) | Fixtures and evals (#7); full derivation in L2-factory-as-code.md | X10 (Appendix B) | B |

## Not drawn

- Dashboards over the views (Later; Record #17, R-O-8) — owned by R5, the measure-views component in this domain.
- The observer pass, calibration and improvement-pass machinery that would write `score`, `human_signal`, `proposal`, `benchmark`, `fixture_candidate` (Later; Fixtures and evals #7, R-O-10, R-O-11, R-F-10, R-F-12, owned by F8; External access #24, R-S7-6, owned by C7 — both in other domains, see `L2-factory-as-code.md` and `L2-control-plane.md`) — only a placeholder (`R1_later`) is drawn, one per table, created with the row that first writes it.
- A read-only MCP server reading the record (Later; Stage interface #18, C1's register note) — owned by C1, see `L2-control-plane.md`.
- Stacked pull requests, each with its own packet (Later; Git trees #25, secondary Artefact, R-S6-8) — owned by R3, this domain's git-trees component.
- Never drawn per the brief's exclusion list, as it touches this domain: a push before quorum (no edge leaves R1_outbox before full quorum); the sandbox or its interior writing the record or the tree (no edge enters R1, R2, R3 or R5 from LAUNCHER_STUB or any execution-boundary node except the established X7 mount/hand-back leg); an approval carried past a change (R1_approval's superseded records confer no authority, per R-T-10, and no edge shows otherwise); an in-place edit of an append-only row (R1_note names the R-T-3 exceptions exhaustively; nothing else is drawn as mutable); a maintenance job recorded as a ticket-stage attempt (R1_run keeps `utility_run` as a table separate from `stage_run`, excluded from the reliability view per R-T-12).
