# L2 — Control plane (domain 2)

| Field | Value |
|---|---|
| Status | Draft v0.3 |
| Date | 2026-09-07 |
| Owner | Abhishek Thakur |
| Derived from | `docs/prd/prd.md` v0.18; `docs/design/milestones.md` v0.6; `docs/charter.md` v0.14 |
| Layer | Layer 2 — domain 2, Control plane |
| Domain rule | A component sits in the domain where its code runs or its file lives, and under whose trust it acts. **Control plane**: the trusted runner, one Python process per `factory` command, no daemon. Everything drawn here is trusted-side code that reads and writes the record directly; nothing here is invoked by an agent and nothing here runs inside the execution boundary. |

## How to read

The control plane owns nine components, `C1` to `C9` (`C9`, Checks and gates, is new in this revision: the exclusion gate, the S3 size gate, the R-I-12 structure and R-S3-19 traceability check, `risk_map` and `handoff_ready`, the S5 preflight and its ordered check list, `base_test_diff`, the fix-round routing rule, the S6 race-guard call, and the waiver check against `waiver-policy.yaml`; `C6` keeps only the seven stage drivers, S0 to S6, dispatched one at a time by `C2` and communicating with each other only through the record — no driver-to-driver chain). Diagram 1 splits at 31 and 18 nodes into **1a** (`C1`–`C5`: command, state machine, run orchestration, binding and the guard) and **1b** (`C6`, `C9`, `C7`, `C8`: stage drivers, checks and gates, external access, git-tree operations), because the combined picture passed the 35-node guideline. Each half draws its own border stubs; `C2` and `C4` reappear in 1b as small reference stubs pointing back at 1a, since `C9`'s S5 preflight calls `C4` for the review-tuple boundary, and every stage driver in `C6` dispatches from and returns an outcome to `C2`.

The control plane's own border crossings are five: `X1` (the person acts, `H2`↔`C1`; a second, metadata-only leg from `H4`'s governance view into `C1`'s audit sink, which cannot reach production content), `X2` (the runner writes and reads its record, `C1`–`C9`→`R1`–`R3`, every write and every mount-bound read passing `C5`'s seat), `X3` (the runner dispatches a run, `C3`/`C6`→`G1`; `C9`'s recipes are dispatched by the S4 and S5 drivers that call it, not by `C9` directly), `X4` (the factory tree is read at run time, `F2`→`C1`), and `X5` (the runner reads from and writes to outside systems, `C7`↔`E1`/`E2`/`E3`/`E5`; `E5` also invokes `factory digest` on `C1`, never a stage), drawn to twelve border stub nodes across the two halves (`H2`, `H4`, `R1`, `R2`, `R3`, `F2`, `G1`, `G2`, `E1`, `E2`, `E3`, `E5`) — those stubs are not detailed here; each lives in its own domain's Layer 2 file. The guard (`C5`) also seats on `X7` (mounts, `R2`/`R3`→`G2`) even though `X7` itself is not one of the five crossings whose endpoint is a control-plane component: the guard's policy evaluation runs in domain 2, so its seat on that crossing is drawn here per the rule below, not redrawn in `L2-record.md` or `L2-execution-boundary.md`.

**The guard is drawn once, with a seat on every carrier.** `C5` seats on `X1`'s display route (`C1`→`H2`), `X2` persistence (every write from `C2`, `C3`, `C6`, `C8` and `C9` fans in to `C5_seat`, which alone writes `R1`, `R2` and `R3`, each edge labelled `X2`; the two record legs read back into the seat for mounting, `R2`/`R3`→`C5_seat`, are labelled `X2 read`), `X3` dispatch (→`G1`), `X5` ingress (→`E1`), `X5` outbox payloads and the digest (→`E2`, `E3`), `X7` mounts (`C5_seat`→`G2`, labelled "mounts"), the `C1` export operation (→`R2`, labelled `X2 export`), and logs (R-T-9 names logs among the seated carriers; no distinct component exists to draw a twelfth edge to at this layer, so the seat is stated in prose only — see "Not drawn"); each drawn seat is one labelled edge from `C5_seat` to its carrier, and no content-bearing edge in this file bypasses it. Every other Layer 2 file states this rule once in its own "How to read" and does not redraw the guard. The credential fetch (`E5`→`C7`) is not a guard seat — it is not content, it is a secret the runner holds outside every sandbox — and is drawn as a direct, solid edge labelled "runtime key A; other roles AB" (decision 8/10): the launcher receives it inside the dispatch (`X3`) and supplies it to agent sandboxes only across `X11`; no edge runs from `E5` into domain 3.

Diagram 2 is the ticket state machine of PRD 2.3, `stateDiagram-v2`, drawn once and complete — this is its only drawing; `L2-human-surface.md` diagram 2 is a touchpoint strip with no transition edges of its own. Transition families, each covering several individual edges below: **advance on success** along the thick thirteen-state backbone; **send-back** to `context`, `clarifying` or `planning` from any open item (`plan_review`, `implementing`, `checks`, `review`, `escalated`); **abandon** from any open item, or directly from `context`, `clarifying`, `planning` or `pr_opened`; **escalation**, either stage-specific (budget, sandbox, verification, non-retryable control failure, stop) or a second consecutive failure outside S4 (`context`, `clarifying`, `planning`, `checks`, `review`); **resume from `escalated`** to the same stage after an infrastructure or human-stop cause, or to `planning` (or earlier, for a superseding plan version) after verification exhaustion; **`refresh_base`** to `context`; the **validation-only rerun** after a fix round (R-S4-9), recorded as an S4 run with no state change, so not drawn as an edge; the fix round itself is the drawn `checks → implementing` edge; and **manifest migration** (R-I-4), a human-approved change that returns any state to `context`, shown once as a note rather than thirteen edges. `pr_checks` and its transitions are Later, shown with a dashed node border and `(Later)` on every edge, since `stateDiagram-v2` has no dotted-edge syntax.

Diagram 3 is the S5 blocking-tier gate as a flow: preflight (creating the review tuple via `C4`), the ordered check list as one solid Milestone-A chain through every check that exists at A — marked once on the subgraph as "A in plain checkouts; AB in the copies" — with the security recipes and dependency verification as the only AB-only insertions, a recipe that cannot run becoming a waivable `blind_spot`, preflight failures fanned out by cause exactly as 2.3's `checks` row states them, the final reviewer-set and approval-binding checks named separately, and the `red_check` item's three exits: waiver to the S6 assembly run, send-back with a tag, or abandon, with sandbox-integrity failure routed to `escalated` on its own edge rather than folded into the non-waivable list.

Unmarked parts are Milestone A; `(AB)` and `(B)` in a label mark parts that first exist at that step; `(Later)` marks a dashed node joined by one dotted edge to the part it grows from. A thick edge (`==>`) marks the main ticket-advancing path only. `classDef store` (grey) marks Record-domain stubs, `classDef content` (blue) marks the Factory-as-code stub; `classDef untrusted` (red) marks external-systems stubs and is not applied to `G1`/`G2` (trusted wall code, per the charter's trust rule, even though they sit in the execution boundary domain) or to `E5` (`classDef hostFacility`, tan: the credential store and scheduler are a trusted host facility per README section 2, not untrusted content). The diagrams deliberately leave out: the internal machinery of every border stub, every Later item as an active box (advisory tier, S7 polling, the read-only MCP server, the host and orchestrator seams, the second adapter — see "Not drawn"), and the full 131-row requirement text (the derivation table below carries the row ids).

### Diagram 1a — command, state machine, run orchestration, binding, guard (31 nodes: 19 interior, 12 border stubs)

```mermaid
flowchart LR
  H2["H2 List view & queue<br/>(Human surface)"]

  subgraph C1sg["C1: `factory` command<br/>(stage interface)"]
    C1_ops["ops: advance, run, queue, act,<br/>pause/resume/stop, refresh-base,<br/>migrate-manifest, tag, abandon,<br/>export/import/purge, show, report,<br/>digest, incident/control-event<br/>+ disposition (R-I-1);<br/>+ outcome/exposure/graduation (B)"]
    C1_gov_audit["governance-only path<br/>-> audit sink (metadata only);<br/>cannot reach production content"]
    C1_mcp["Later: read-only MCP server<br/>(get record, list queue,<br/>get measures, export) — R-I-9"]
    C1_host["Later: EC2 host behind<br/>the same command line<br/>(Host seam)"]
    C1_ops -.-> C1_mcp
    C1_ops -.-> C1_host
  end

  subgraph C2sg["C2: Ticket state machine<br/>and the fence"]
    C2_states["state machine (PRD 2.3):<br/>13 states + pr_checks (Later);<br/>tiers; holds incl. parallel-limit<br/>at intake (R-I-10); close reasons;<br/>escalation causes; mechanical<br/>tags: escalation, control_defect"]
    C2_fence["the fence: transition table +<br/>anti-goals in runner code, outside<br/>factory/, beyond any proposal (R-F-11)"]
    C2_orch["Later: a workflow engine<br/>may replace the state table<br/>behind the stage interface"]
    C2_fence --> C2_states
    C2_states -.-> C2_orch
  end

  subgraph C3sg["C3: Run orchestration"]
    C3_runs["run tables: stage_run<br/>(parent_run_id for children),<br/>utility_run — separate ledger,<br/>excluded from reliability (R-T-12)"]
    C3_kinds["stage_run.run_kind: task,<br/>fix_round, validation_only;<br/>3-verification quota per<br/>plan item (R-S4-5)"]
    C3_lease["lease/heartbeat/restart;<br/>tiers.yaml budgets: tokens+wall-clock;<br/>abort → escalated (tag: escalation)"]
    C3_fanout["Later: S1 fan-out children<br/>merged to one brief (R-S1-10)"]
    C3_runs --> C3_kinds --> C3_lease
    C3_runs -.-> C3_fanout
  end

  subgraph C4sg["C4: Binding and<br/>freshness guard"]
    C4_subject["canonical serialization,<br/>SHA-256 subject hashes;<br/>plan tuple; review tuple (R-T-10)"]
    C4_fresh["freshness check, 3 boundaries:<br/>1 before each S4 invocation and<br/>at the plan-approval commit;<br/>2 S5 preflight, creates review<br/>tuple (via C9); 3 S6 race guard +<br/>pre-dispatch recheck (via C9)"]
    C4_subject --> C4_fresh
  end

  subgraph C5sg["C5: Guard"]
    C5_seat["one seat on every content-<br/>bearing crossing — display,<br/>persistence, dispatch, ingress,<br/>outbox, mounts, export, logs:<br/>allow/redact/deny + guard_decision<br/>row (R-T-9). Denies: unknown<br/>class; absent route; unavailable<br/>guard; missing/expired approval;<br/>attempted downgrade; secret hit"]
  end

  subgraph C7sg["C7: External access"]
    C7_cred["credentials by role,<br/>held outside every sandbox"]
    C7_ingress["ingress: Jira/Confluence reads<br/>at S0 (AB real, stub A); the<br/>target-branch fetch and<br/>CODEOWNERS read C8 requests<br/>through this route; baseline<br/>read (AB)"]
    C7_outbox["outbox: pr_create, pr_update,<br/>digest, jira_feedback intents,<br/>idempotency key + receipt.<br/>digest (R-H-3, AB): only ticket<br/>id, tier, item kind, age and<br/>local command/link — no ticket<br/>text, code, question options,<br/>artefact content or secret.<br/>pr_update: expected prior remote<br/>head, compare-and-set/force-<br/>with-lease, never overwrites an<br/>unexpected commit, one<br/>publication_target. Worker: sole<br/>push authority; co-commits with<br/>the quorum-completing approval"]
    C7_later["Later: read-only GitHub<br/>reads (S7 checks);<br/>Confluence sync (R-H-10)"]
    C7_cred --> C7_ingress
    C7_cred --> C7_outbox
    C7_outbox -.-> C7_later
  end

  subgraph C8sg["C8: Git-tree operations"]
    C8_ops["clone + worktree per ticket;<br/>base_sha at eligibility (network<br/>read via C7); 3 freshness<br/>boundaries; refresh_base<br/>(human route); no push URL"]
  end

  H4["H4 Approvals, waivers<br/>and governance view<br/>(Human surface)"]
  R1["R1 SQLite ledger (Record)"]
  R2["R2 Artefact files (Record)"]
  R3["R3 Git trees (Record)"]
  F2["F2 Manifest (Factory as code)"]
  G1["G1 Runtime adapter<br/>(Execution boundary)"]
  G2["G2 The wall: launcher<br/>(Execution boundary)"]
  E1["E1 Atlassian server"]
  E2["E2 GitHub"]
  E3["E3 Slack"]
  E5["E5 Cred store & scheduler"]

  H2 ==>|"X1 commands"| C1_ops
  C1_ops ==> C2_states
  C2_states ==> C3_kinds
  C3_kinds ==>|"X3"| C5_seat
  C5_seat ==>|"X3 dispatch"| G1

  F2 -->|"X4"| C1_ops
  C1_ops --> C5_seat
  C5_seat -->|"X1 display route"| H2
  C5_seat -->|"X2 export"| R2
  C1_ops -->|"reconcile at start"| C7_outbox
  H4 -->|"X1 governance view,<br/>metadata-only"| C1_gov_audit

  C2_states -->|"X2"| C5_seat
  C2_states -->|"boundary 1: plan-approval<br/>commit"| C4_fresh
  C3_kinds -->|"X2"| C5_seat
  C3_lease -->|"X2"| C5_seat
  C3_lease -->|"abort"| C2_states
  C5_seat -->|"X2"| R1
  C5_seat -->|"X2"| R3

  C4_fresh --> C8_ops

  C7_ingress --> C5_seat
  C5_seat -.->|"X5 ingress (AB)"| E1
  C7_outbox --> C5_seat
  C5_seat -.->|"X5 (AB)"| E2
  C5_seat -.->|"X5 digest (AB)"| E3
  R2 -->|"X2 read"| C5_seat
  R3 -->|"X2 read"| C5_seat
  C5_seat -->|"X7 mounts"| G2

  E5 -->|"X5 runtime key A;<br/>other roles AB"| C7_cred
  E5 -.->|"X5 invokes digest<br/>only — AB; never<br/>starts a stage"| C1_ops
  C8_ops --> C7_ingress

  C8_ops -->|"X2 SHAs, ticket<br/>fields, tree state"| C5_seat

  classDef store fill:#f3f4f6
  classDef content fill:#eef6ff
  classDef untrusted fill:#fde8e8,stroke:#b91c1c
  classDef hostFacility fill:#fff7ed,stroke:#9a3412
  classDef later stroke-dasharray:5 5,color:#666
  class R1,R2,R3 store
  class F2 content
  class E1,E2,E3 untrusted
  class E5 hostFacility
  class C1_mcp,C1_host,C2_orch,C3_fanout,C7_later later
```

### Diagram 1b — stage drivers, checks and gates, external access reference, git-tree reference (18 nodes: 12 interior, 6 border/reference stubs)

`C2_stub`, `C4_stub` and `C5_stub` are the same components as diagram 1a's `C2`, `C4` and `C5`, repeated here only as dispatch/return and persistence-seat targets so this half reads on its own; every `X3` dispatch edge below passes `C5`'s seat (drawn fully in diagram 1a), and every `X2` write from `C6` or `C9` passes through `C5_stub` before it reaches `R1`/`R2` — no driver writes the record directly.

```mermaid
flowchart LR
  C2_stub["C2 state machine<br/>(diagram 1a)"]
  C4_stub["C4 binding & freshness<br/>(diagram 1a)"]
  C5_stub["C5 guard seat<br/>(diagram 1a)"]
  R1["R1 SQLite ledger (Record)"]
  R2["R2 Artefact files (Record)"]
  G1["G1 Runtime adapter<br/>(Execution boundary)"]

  subgraph C6sg["C6: Stage drivers (no chain; each dispatched by C2, returns an outcome to C2)"]
    C6_s0["S0 driver: field gate, tier/type<br/>lookup, sensitive-path match,<br/>template scrutiny paragraph"]
    C6_s1["S1 driver: archaeology (agent<br/>work; archaeology script is its<br/>tool), index_staleness script,<br/>final tier computation"]
    C6_s2["S2 driver: restatement child<br/>runs, forced categories, question<br/>gate, ranker, format/wording<br/>validators, split rule"]
    C6_s3["S3 driver: plan authoring<br/>(rubric lines R-S3-2–14);<br/>calls C9 for risk_map, size<br/>gate, structure/traceability<br/>check, handoff_ready"]
    C6_s4["S4 driver: task loop, one fresh<br/>invocation per task (R-S4-1/2);<br/>calls C9 for validation recipes,<br/>base_test_diff, fix rounds"]
    C6_s5["S5 driver: calls C9 for preflight<br/>and the ordered check list<br/>(diagram 3)"]
    C6_s6["S6 driver: packet_assemble,<br/>pr_body_assemble (R-S6-1/2),<br/>after C9's race guard call"]
  end

  subgraph C9sg["C9: Checks and gates"]
    C9_excl["exclusion gate, one part:<br/>invoked at S0, S1, S3, S5<br/>(R-S0-8)"]
    C9_struct["size gate (R-S3-12, at S3);<br/>R-I-12 structure + R-S3-19<br/>traceability check on brief/<br/>criteria/plan/packet; risk_map<br/>(before S3, impact_scan script);<br/>handoff_ready (after S3, R-S3-21)"]
    C9_preflight["S5 preflight: reviewer set from<br/>CODEOWNERS + owners.yaml<br/>(R-S6-6); review tuple via C4;<br/>sandbox integrity; ordered check<br/>list + exits (diagram 3);<br/>base_test_diff (R-S4-10)"]
    C9_fixround["fix-round rule: red confined to<br/>lint/compile/unit/integration,<br/>green at base, red at head; test-<br/>only diff refused (R-S4-9).<br/>S6 race guard call<br/>(R-S6-6). Waiver check against<br/>waiver-policy.yaml (F6, R-S5-13)"]
    C9_later["Later: graders + the advisory<br/>tier (R-S5-8, owned by domain 5,<br/>see L2-factory-as-code.md);<br/>compiled compatibility<br/>(contract checker)"]
    C9_fixround -.-> C9_later
  end

  C2_stub --> C6_s0 --> C2_stub
  C2_stub --> C6_s1 --> C2_stub
  C2_stub --> C6_s2 --> C2_stub
  C2_stub --> C6_s3 --> C2_stub
  C2_stub --> C6_s4 --> C2_stub
  C2_stub --> C6_s5 --> C2_stub
  C2_stub --> C6_s6 --> C2_stub

  C6_s0 --> C9_excl
  C6_s1 --> C9_excl
  C6_s1 --> C9_struct
  C6_s2 --> C9_struct
  C6_s3 --> C9_excl
  C6_s3 --> C9_struct
  C6_s4 --> C9_fixround
  C6_s5 --> C9_excl
  C6_s5 --> C9_preflight
  C6_s6 --> C9_fixround
  C6_s6 --> C9_struct

  C6_s4 -->|"X3"| G1
  C6_s5 -->|"X3"| G1

  C9_preflight -->|"boundary 2"| C4_stub
  C9_fixround -->|"boundary 3"| C4_stub

  C6sg -->|"X2"| C5_stub
  C6_s6 -->|"X2"| C5_stub
  C9sg -->|"X2"| C5_stub
  C5_stub -->|"X2"| R1
  C5_stub -->|"X2"| R2

  classDef store fill:#f3f4f6
  classDef later stroke-dasharray:5 5,color:#666
  class R1,R2 store
  class C9_later later
```

### Diagram 2 — the ticket state machine, PRD 2.3, drawn once and complete

```mermaid
stateDiagram-v2
  direction LR
  [*] --> intake
  note right of intake : parallel-limit hold (R-I-10)

  intake --> context : S0 pass, eligibility granted
  intake --> rejected : S0 fail / decline
  intake --> abandoned : abandon

  context --> clarifying : S1 pass
  context --> rejected : Initial exclusion (S1)
  context --> escalated : second failure / stop
  context --> abandoned : abandon

  clarifying --> planning : S2 exit, no open question
  clarifying --> escalated : second failure / stop
  clarifying --> abandoned : abandon

  planning --> plan_review : S3 produces plan
  planning --> rejected : Initial exclusion (S3)
  planning --> escalated : second failure / stop
  planning --> abandoned : abandon

  plan_review --> implementing : full quorum + fresh base
  plan_review --> context : refresh_base / send-back
  plan_review --> planning : send-back
  plan_review --> clarifying : send-back
  plan_review --> abandoned : abandon

  implementing --> checks : hand-back
  implementing --> context : refresh_base / send-back
  implementing --> planning : send-back
  implementing --> clarifying : send-back
  implementing --> escalated : verify/budget/sandbox/<br/>control/stop
  implementing --> abandoned : abandon

  checks --> implementing : hand-back invalid /<br/>S4 removal / fix round
  checks --> context : refresh_base / send-back
  checks --> planning : reviewer requirement /<br/>send-back
  checks --> clarifying : send-back
  checks --> rejected : plan-required<br/>sensitive path
  checks --> escalated : sandbox-integrity /<br/>second failure / stop
  checks --> review : S5 + S6 assembly pass
  checks --> abandoned : abandon

  review --> pr_opened : full quorum / closed-<br/>merged remote PR
  review --> checks : pre-dispatch mismatch
  review --> planning : pre-dispatch mismatch /<br/>send-back
  review --> context : pre-dispatch mismatch /<br/>send-back
  review --> clarifying : send-back
  review --> implementing : request changes
  review --> escalated : control failure /<br/>second failure / stop
  review --> abandoned : abandon

  pr_opened --> merged : human records merge
  pr_opened --> abandoned : human records<br/>abandonment
  pr_opened --> planning : requested revision,<br/>through the selected<br/>earlier stage
  pr_opened --> pr_checks : S7 polling (Later)

  note right of planning : requested revision (pr_opened) returns through the stage the human selects, planning drawn as the representative target — context, clarifying and implementing are the other targets, one shared note, not drawn per target

  pr_checks --> merged : observed merge (Later)
  pr_checks --> abandoned : closed-unmerged (Later)
  pr_checks --> context : target-base movement (Later)
  pr_checks --> implementing : sync_pr_head (Later)
  pr_checks --> planning : send-back (Later)

  escalated --> planning : verification exhaustion
  escalated --> clarifying : verification exhaustion<br/>(earlier)
  escalated --> context : verification exhaustion<br/>(earlier) / control-defect<br/>remediated
  escalated --> implementing : infra/human-stop resume
  escalated --> checks : infra/human-stop resume
  escalated --> review : infra/human-stop resume
  escalated --> abandoned : abandon

  note right of context : migrate-manifest (R-I-4) returns any state here — one shared note, not drawn per state

  rejected --> [*]
  merged --> [*]
  abandoned --> [*]

  classDef later stroke-dasharray:5 5,color:#666
  class pr_checks later
```

### Diagram 3 — the S5 blocking-tier gate

```mermaid
flowchart TB
  Preflight["S5 preflight (trusted, outside repo<br/>execution): plan approval/quorum,<br/>target/base/head/diff/deviation identity,<br/>trust+execution digests, R-S6-6 reviewer set"]
  PreflightFail["construction failure: one<br/>review_tuple_preflight result,<br/>non-waivable, no invented<br/>results for unrun checks"]
  ReviewTuple["review tuple created<br/>(via C4); every result below<br/>binds it; continues after red<br/>except tuple/sandbox-integrity failure"]

  ToImplementing["→ implementing<br/>(hand-back invalid)"]
  ToPlanningS4["→ planning or S4 removal<br/>(reviewer requirement)"]
  ToHuman["→ context / planning /<br/>clarifying: refresh, send-back,<br/>or abandon (stale base)"]
  ToRejected["→ rejected<br/>(pilot_excluded)"]
  ToEscalated["→ escalated<br/>(sandbox-integrity)"]

  subgraph ChkList["S5 ordered check list — A in plain checkouts; AB in the copies (security recipes and dependency verification are AB-only insertions)"]
    Chk_lint["lint"]
    Chk_compile["compile/type"]
    Chk_unit["unit-test"]
    Chk_integ["integration-test"]
    Chk_e2e["end-to-end<br/>(where already registered)"]
    Chk_basetest["base_test_diff +<br/>R-S4-10 planned-change runs"]
    Chk_security["security recipes: secret scan,<br/>static analysis, dep-vuln,<br/>licence policy (AB, in copies)"]
    Chk_depverify["dependency verification<br/>dep_verify (AB, in copies)"]
    Chk_size["size"]
    Chk_scope["scope"]
    Chk_decl["source_declaration_diff"]
    Chk_contract["behavior_contract_evidence"]
    Chk_reviewerset["final reviewer-set check<br/>(S6 race guard, R-S6-6)"]
    Chk_approvalbind["final approval-binding check"]
    Chk_lint --> Chk_compile --> Chk_unit --> Chk_integ --> Chk_e2e --> Chk_basetest
    Chk_basetest --> Chk_size
    Chk_basetest -.->|"AB insertion"| Chk_security -.-> Chk_depverify -.->|"rejoins"| Chk_size
    Chk_size --> Chk_scope --> Chk_decl --> Chk_contract --> Chk_reviewerset --> Chk_approvalbind
  end

  DidNotRun["did-not-run recipe: declared<br/>network policy or dependency<br/>the sandbox can't satisfy<br/>→ blind_spot (waivable)"]

  Results["aggregate: every result +<br/>governed output bound to<br/>the review tuple"]

  S6assembly["pass →<br/>S6 assembly<br/>(packet_assemble, pr_body_assemble)"]
  S4Fix["S4 fix round (R-S4-9), while<br/>rounds remain; a test-only<br/>diff is refused"]
  RedCheck["one red_check item"]
  Waivable["waivable blind_spot"]
  NonWaivable["non-waivable, per<br/>waiver-policy.yaml (F6, R-S5-13):<br/>identity/trust-approval kinds<br/>and a missing-artefact kind"]

  Preflight -->|"success"| ReviewTuple
  Preflight -->|"failure, by cause"| PreflightFail
  PreflightFail --> ToImplementing
  PreflightFail --> ToPlanningS4
  PreflightFail --> ToHuman
  PreflightFail --> ToRejected
  PreflightFail --> ToEscalated

  ReviewTuple --> Chk_lint
  ReviewTuple -->|"sandbox-integrity<br/>failure"| ToEscalated
  ChkList -.-> DidNotRun
  DidNotRun --> Waivable
  Chk_approvalbind --> Results

  Results -->|"all pass / validly waived"| S6assembly
  Results -->|"red confined to lint/compile/<br/>unit/integration, green at<br/>base, red at head"| S4Fix
  Results -->|"end-to-end red; mixed;<br/>exhausted rounds; other red"| RedCheck

  RedCheck --> Waivable
  RedCheck --> NonWaivable
  Waivable -->|"waiver granted<br/>(waiver-policy.yaml, F6)"| S6assembly
  Waivable -->|"send-back (tag)"| ToHuman
  Waivable -->|"abandon"| ToHuman
  NonWaivable -->|"send-back (tag)"| ToHuman
  NonWaivable -->|"abandon"| ToHuman
  NonWaivable -->|"plan-required<br/>sensitive path<br/>(pilot_excluded)"| ToRejected

  classDef later stroke-dasharray:5 5,color:#666
```

## Derivation table

One row per component or part drawn above. Block is the row's own Appendix A primary block (`docs/design/milestones.md` the map at lines 264–454); a block in parentheses is that row's Appendix A secondary. First step is the row's own Appendix A milestone. `C6` and `C9` are listed as separate groups since decision 5 splits them.

### C1 to C5

| Component / part | Block (Appendix A) | Requirement rows | First step |
|---|---|---|---|
| C1 `factory` command (ops node) | Stage interface | R-I-1 (B), R-I-8 (secondary: ticket and its state), R-I-9 (Later), R-H-13 | A (command and most ops; R-I-1 complete at B) |
| C1 governance-only audit sink | Trust profile (secondary: guard) | R-T-9 (charter C9's governance carve-out) | A |
| C1 Later: MCP server | Stage interface | R-I-9 | Later |
| C1 Later: host seam | Stage interface | milestones.md:84 (Host extension point) | Later |
| C2 state machine | Ticket and its state | R-T-5, R-S0-2, R-S1-8, R-S1-11 (secondary: queue item and decision), R-S2-12 (secondary: run), R-S4-6 (secondary: tag), R-I-10 (B, secondary: approval and quorum) | A (capacity-raise sub-feature at B) |
| C2 fence | Factory tree and change control | R-F-11 | A |
| C2 Later: orchestrator seam | Ticket and its state; stage interface | milestones.md:85 (Orchestrator extension point) | Later |
| C3 run tables | Run | R-T-12 (secondary: record) | A |
| C3 run-kind values + quota | Run | R-S4-5 (secondary: binding), R-S4-9 (secondary: check), R-I-6 (secondary: ticket and its state) | A |
| C3 lease/heartbeat/restart | Run | R-T-12, R-O-1 (secondary: external access) | A |
| C3 Later: S1 fan-out children | Run | R-S1-10 | Later |
| C4 canonical serialization + subject hashes | Binding | R-T-10 (secondary: approval and quorum) | A |
| C4 freshness check (3 boundaries) | Binding | R-S3-15 (secondary: approval and quorum), R-S5-12 (secondary: git trees), R-S6-10 (secondary: approval and quorum), R-S4-5 (secondary: binding), R-S6-6 (secondary: binding) | A |
| C5 guard seat | Trust profile (secondary: guard) | R-T-9, R-T-4 (secondary: guard) | A |

### C6 (stage drivers only)

A driver spans several blocks, since it runs rubric lines, check scripts and data-block writes together; the Block column names the block each cited row actually belongs to (primary, or secondary in parentheses) and every id is drawn here as the driver that runs it, not as that row's block home.

| Component / part | Block (Appendix A) | Requirement rows | First step |
|---|---|---|---|
| C6_s0 S0 driver | External access (R-S0-1); ticket and its state (R-S0-5, R-S0-6); queue item and decision (R-S0-7) | R-S0-1 (AB, secondary: check), R-S0-5 (secondary: approval and quorum), R-S0-6, R-S0-7 (secondary: approval and quorum) | A (R-S0-1's Atlassian leg AB) |
| C6_s1 S1 driver | Rubric (R-S1-2, R-S1-3, R-S1-6); external access (R-S1-4); context index (R-S1-7) | R-S1-2, R-S1-3 (secondary: context index), R-S1-4 (AB, secondary: rubric), R-S1-6, R-S1-7 (secondary: tag) | A (R-S1-4's Atlassian leg AB) |
| C6_s2 S2 driver | Question and assumption log (R-S2-5, R-S2-6, R-S2-7, R-S2-9, R-S2-14); rubric (R-S2-1, R-S2-4, R-S2-10); run (R-S2-3) | R-S2-1 (secondary: artefact), R-S2-3 (secondary: manifest), R-S2-4 (secondary: question and assumption log), R-S2-5, R-S2-6, R-S2-7, R-S2-9, R-S2-10 (secondary: question and assumption log), R-S2-14 | A |
| C6_s3 S3 driver | Rubric (R-S3-2, R-S3-3, R-S3-4, R-S3-5, R-S3-6, R-S3-7, R-S3-9, R-S3-10); artefact (R-S3-14) | R-S3-2, R-S3-3, R-S3-4, R-S3-5, R-S3-6, R-S3-7, R-S3-9, R-S3-10, R-S3-14 (block: artefact) | A |
| C6_s4 S4 driver | Artefact | R-S4-1, R-S4-2 | A |
| C6_s5 S5 driver | — (drivers only; the check content is C9's) | — | A |
| C6_s6 S6 driver | Artefact | R-S6-1, R-S6-2 | A |

### C9 (checks and gates, new)

| Component / part | Block (Appendix A) | Requirement rows | First step |
|---|---|---|---|
| C9_excl exclusion gate | Check (secondary: ticket and its state) | R-S0-8 | A |
| C9_struct structure/traceability + risk_map/handoff_ready | Rubric (R-S3-11, secondary: artefact); artefact (R-I-12, R-S3-19, R-S3-21) | R-S3-11, R-S3-12 (check), R-I-12 (secondary: check), R-S3-19, R-S3-21 (secondary: check) | A |
| C9_preflight S5 preflight + ordered check list | Check (AB) | R-S5-1, R-S5-2 (AB, secondary: sandbox), R-S5-4, R-S5-5, R-S5-10, R-S6-6 (primary: approval and quorum, secondary: binding), R-S4-10 (secondary: git trees) | A (plain-checkout subset; R-S5-4, R-S5-5, R-S5-10 at A); AB (full, in copies, with security recipes and R-S5-2's dependency verification) |
| C9_fixround fix rounds, race guard, waiver check | Run (R-S4-9, secondary: check) | R-S4-9, R-S6-3 (external access, AB, secondary: binding), R-S5-13 (approval and quorum, secondary: binding) | A |
| C9 Later: graders + advisory tier; compiled compatibility | Agent definition (R-S5-8, secondary: rubric); check (R-S5-5's Later extension) | R-S5-8 (owned by domain 5, see `L2-factory-as-code.md`), milestones.md:88 (Contract checker extension point) | Later |

### C7, C8

| Component / part | Block (Appendix A) | Requirement rows | First step |
|---|---|---|---|
| C7 ingress reads | External access | R-S0-1, R-S1-4 | A (stub reads); AB (real Atlassian reads) |
| C7 outbox + worker | External access | R-T-11 (secondary: ticket and its state), R-S6-3 (secondary: binding), R-H-3 (AB, secondary: queue item and decision) | A (stub deliverer, contract); AB (push authority; R-H-3's digest write) |
| C7 Later: GitHub reads, Confluence sync | External access | R-H-10 | Later |
| C8 git-tree operations | Git trees | R-S5-12 (binding, secondary: git trees), R-S4-10 (check, secondary: git trees) | A |

## Not drawn

- Read-only MCP server over the stage interface (R-I-9): Later; drawn as `C1`'s dashed node (diagram 1a).
- The host seam (an EC2 host behind the same `factory` command line) and the orchestrator seam (a workflow engine behind the state table): Later extension points, no PRD row; drawn as `C1`'s and `C2`'s dashed nodes (diagram 1a), per `milestones.md`'s Extension-points table (lines 84–85).
- `factory` command's outcome/exposure/coverage/graduation operations (R-I-1's B-half) and the parallel-ticket capacity raise (R-I-10, B): shown only as `(B)` inline on `C1_ops` and `C2_states`, not as separate nodes.
- Advisory tier / sliced advisory pass (R-S5-8, owned by domain 5, see `L2-factory-as-code.md`; R-S5-11) and compiled-compatibility contract checking: Later, drawn as `C9`'s dashed node (diagram 1b); not part of the blocking gate in diagram 3.
- S1 fan-out children merged to one brief (R-S1-10, Later): drawn as `C3`'s dashed node (diagram 1a).
- S7 PR-checks polling, `pr_checks_summary`, `sync_pr_head`, `close_survey`, `human_signal` reads, and Confluence sync (all Later, R-S7-*, R-H-10): shown as the `(Later)` state and edges in diagram 2, and as `C7`'s dashed node (diagram 1a).
- Second runtime adapter (Claude Code, Later): belongs to the execution-boundary domain's own file; `G1` is drawn here only as a border stub.
- Impact-method swap (import scan vs. dependency tree, `milestones.md:87`): a Later extension point on the Check block, but it is drawn where it executes, inside the sandbox recipe catalogue — see `L2-execution-boundary.md`, not here.
- Log content as a distinct guarded carrier (R-T-9 names logs among the seated carriers): no register component exists to draw a separate edge to at this layer; log writes ride inside the already-guarded `R1`/`R2` writes, not a twelfth carrier — stated in prose only (see the guard paragraph above).
- Never drawn, per the anti-goal list: a push before quorum (`C5_seat`'s edges to `E2`/`E3` are dotted-AB, labelled through the outbox, which pushes only after full quorum); an agent holding a GitHub or Slack credential (only `C7_outbox`, trusted-side, touches `E2`/`E3`, and the runtime key on `X5`/`X3`/`X11` never reaches domain 3 from `E5` directly — no edge from `E5` into `G1` or `G2`); the sandbox writing the record or the tree (no edge from `G1`/`G2` back into `R1`/`R2`/`F2`); the scheduler starting a stage (`E5`'s edges reach only `C7_cred` for credentials and `C1_ops` for the `factory digest` invocation, never `C2`/`C3`/`C6`/`C9`); a switchable S3 or S6 gate; cost or throughput as an objective; a content-bearing crossing that bypasses `C5` (the solid `C5_seat`→`E2` edge of v0.1, which duplicated the guarded outbox path at Milestone A, is removed; every `X2` write and mount-bound read now also passes `C5_seat`/`C5_stub`).
