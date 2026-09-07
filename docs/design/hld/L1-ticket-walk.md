# Layer 1: one ticket across the domains

| Field | Value |
|---|---|
| Status | Draft v0.3 |
| Date | 2026-09-07 |
| Owner | Abhishek Thakur |
| Derived from | docs/prd/prd.md v0.18; docs/design/milestones.md v0.6; docs/charter.md v0.14; docs/design/hld/README.md v0.3 (register of record) |
| Layer | Layer 1 — one ticket's walk across the domains |
| Domain rule | A component sits in the domain where its code runs or its file lives, and under whose trust it acts; domain 1 is the exception the rule names — it is the person's view, and the code that renders it is C1. **Human surface**: what the person sees and does; trusted. **Control plane**: the trusted runner, one Python process per `factory` command, no daemon — the command, the state machine and the fence, run orchestration, binding and freshness, the guard, the stage drivers, the checks and gates (C9), external access, git-tree operations. **Execution boundary**: the wall the runner builds around every agent or build run — the runtime adapter and envelope (G1), the launcher, recipe runner, OS policy and loopback proxy (G2) — and the untrusted interior (G3); aliased `G` in the diagrams below, never `X`, so it never collides with the `X1`–`X11` crossing-id labels. **Record**: state on disk under `runs/` that the runner alone writes, including the measure views and the frozen baseline (R5). **Factory as code**: versioned content under `factory/`, read-only at run time, every file hashed by the manifest. **External systems**: everything outside the engineer's machine, plus the two host facilities the runner trusts (credential store, scheduler). A data block of `milestones.md` (queue item, question log, approval, binding, tag) is stored in the record; its contract is drawn where its rows are decided (the person's decisions in domain 1, runner-computed rows in domain 2) and its table is listed once under the record's ledger. |

## How to read this

Both diagrams are `sequenceDiagram`s over the same six participants, in the fixed order the brief sets — Person (`P`), Control plane (`C`), Execution boundary (`G`), Record (`R`), Factory as code (`F`), External systems (`E`) — because a ticket's walk is a sequence of crossings, not a map of components. Record and Factory as code are participants, not stores drawn once, because a write to the record (crossing X2) and a read of the tree into the envelope (X4) are themselves crossings the walk makes. An arrow carries a crossing id (`X1`–`X11`) in its label so every message traces back to the crossings table; a solid arrow (`->>`) is a call or a write, a dotted arrow (`-->>`) is what comes back (output files, receipts, check results). `rect` blocks group the messages belonging to one PRD stage, opening with a `Note` naming the stage; a trailing `Note over R` gives the ticket state the record is now in — the "Entered from" and "Leaves when" columns of `02-3-ticket-states.md` read as a sequence: `intake` at the top (the state a ticket starts in), `context`, `clarifying`, `planning`, `plan_review` the moment the `plan_approval` item is queued (not only once it clears), `implementing`, `checks`, `review`, `pr_opened`, and `merged` or `abandoned` at the close.

Unmarked messages hold from Milestone A. `(AB)` marks a message that reaches a real outside system only from Milestone AB — at Milestone A the same crossing hits a stub deliverer or, for the two target-branch fetches, the synthetic fixture repository that `milestones.md` materialises outside the manifest hash at the path `project.yaml` names (`docs/design/milestones.md` section 3, item 2); `(B)` marks the manual outcome record, which exists only from Milestone B. Every content-bearing crossing in this walk passes the guard (C5) and leaves one `guard_decision` row; C5's seats are drawn once, in `L2-control-plane.md`, so no message here names it again. `factory advance <ticket>` runs stages only until the next human touchpoint and exits — one Python process per command, no daemon (`08-configuration.md:112`) — so a fresh `P->>C: factory advance JIRA-123` message follows every human decision that must resume a stage; a loop in diagram 2 with no human touchpoint of its own draws none.

Diagram 1 deliberately omits: the manifest resolving again on every later stage (it is pinned once at S0 and only checked after, per R-I-4); the four Later-only queue-item kinds and the observer/grader path; the scheduled digest, the baseline read, and any crossing to the factory's own change control (X9, X10) — none of those carry this one ticket. Diagram 2 shows only the loops the happy path hides; it omits everything diagram 1 already established (the manifest pin, the S0–S1 messages) and re-enters at the point each loop actually branches off.

## Diagram 1: the happy path, `factory advance` to `pr_opened`

One ticket from the command that opens it to the draft pull request, one message per crossing that matters, grouped by stage S0–S6 and closing with the manual outcome record.

```mermaid
sequenceDiagram
    participant P as Person
    participant C as Control plane
    participant G as Execution boundary
    participant R as Record
    participant F as Factory as code
    participant E as External systems

    P->>C: factory advance JIRA-123 (X1)
    Note over R: state: intake - ticket picked up

    rect rgb(245,245,255)
    Note over P,E: S0 intake
    F->>C: manifest, agents, skills, rubric by hash (X4)
    C->>E: read Jira and Confluence fields (X5) (AB)
    C->>R: R-T-9 classifies/redacts into ticket_source, write tier, type, sensitive-path match (X2)
    C->>R: script fills the scrutiny paragraph from the R-S0-6 template (X2)
    C->>P: eligibility item - trust profile, RACI roles, template scrutiny (X1)
    P->>C: eligible, type confirmed, scrutiny approved (X1)
    C->>R: state = context (X2)
    end
    Note over R: state: context - manifest hash pinned, every later run must match it

    P->>C: factory advance JIRA-123 (X1)
    rect rgb(245,255,245)
    Note over P,E: S1 context gathering
    C->>G: dispatch S1 invocation, envelope by pinned hash (X3)
    R->>G: mount ticket worktree read-only, with its codegraph index (X7)
    F->>C: context index entries, skill, rubric and checklists by content hash (X4)
    C->>G: the same, inside the envelope (X3), passed across the wall by the launcher (X11)
    G->>E: prompt and context reach the hosted model (X6)
    G->>E: agent reads Atlassian via the proxy for archaeology (X6) (AB)
    G-->>C: brief file, tool_call rows, usage (X3)
    C->>R: register brief, index_use rows (X2)
    end
    Note over R: state: clarifying

    rect rgb(255,250,240)
    Note over P,E: S2 requirements clarification
    C->>G: dispatch S2 invocation - N restatement child runs, criteria, questions (X3)
    G-->>C: criteria, question_set (X3)
    C->>R: register criteria, question rows (X2)
    C->>P: question item (X1)
    P->>C: answer or accept the default (X1)
    C->>R: write answer, assumption log (X2)
    end
    Note over R: state: planning

    P->>C: factory advance JIRA-123 (X1)
    rect rgb(255,245,245)
    Note over P,E: S3 spec and plan, through plan_review
    C->>R: run risk_map script over touched-area candidates (C9) (X2)
    C->>G: dispatch S3 invocation - risk map, brief, criteria (X3)
    G-->>C: plan file (X3)
    C->>R: run handoff_ready, write readiness table, register plan (C9) (X2)
    C->>P: plan_approval item - criteria-and-plan bundle (X1)
    Note over R: state: plan_review
    P->>C: approve (plan tuple) (X1)
    C->>E: fetch target branch, confirm head equals bound base (X5) (AB)
    C->>R: write plan tuple, approval_record, state = implementing (X2)
    end
    Note over R: state: implementing

    P->>C: factory advance JIRA-123 (X1)
    rect rgb(245,245,255)
    Note over P,E: S4 implementation
    C->>G: dispatch fresh invocation per plan task (X3)
    R->>G: mount ticket worktree, read-write (X7)
    G-->>C: branch, head_sha, deviation set (X3)
    C->>G: run the task's validation recipes (X3)
    G-->>C: validation results (X3)
    C->>R: write check_result, register deviations, hand-back, state = checks (X2)
    end
    Note over R: state: checks

    rect rgb(245,255,245)
    Note over P,E: S5 cleanup pass (blocking tier, then the S6 script run)
    C->>E: fetch target branch, confirm head equals bound base (X5) (AB)
    C->>R: preflight verifies plan/base/head/diff identity, R-S6-6 ownership, creates review tuple (C9 through C4) (X2)
    R->>G: mount base and head copy-on-write views, per-run directory (X7) (AB)
    C->>G: run project and contract recipes in order (X3)
    C->>G: run security recipes - secret, static, dep-vuln, licence (X3) (AB)
    G-->>C: check results - lint, tests, security, contract evidence (X3)
    C->>R: write check_result rows, S6 race guard recomputes reviewer set (C9 through C4) (X2)
    C->>R: run packet_assemble, pr_body_assemble scripts, state = review (X2)
    end
    Note over R: state: review

    rect rgb(255,250,240)
    Note over P,E: S6 human review and publication
    C->>P: packet_approval item - packet, PR body (X1)
    P->>C: approve (approval_record, quorum) (X1)
    C->>R: last quorum-completing approval and outbox intent commit together (R-T-11) (X2)
    end

    P->>C: factory advance JIRA-123 (X1)
    C->>E: outbox worker rechecks subject, pushes ticket branch, opens draft PR (X5) (AB)
    E-->>C: receipt - PR identity, head, body hash (X5) (AB)
    C->>R: reconcile receipt, state = pr_opened, queue pr_outcome item (X2, its actions arrive at B)
    Note over R: state: pr_opened

    E->>P: draft pull request visible on GitHub (X8) (AB)
    P->>C: factory act - record merged or abandoned outcome (X1) (B)
    C->>R: write outcome, production-coverage record (X2) (B)
    Note over R: state: merged or abandoned
```

## Diagram 2: the loops the happy path hides

Three loops the happy path hides: an S2 run ending `blocked` on a question, answered in the list view, and rerun; an S5 red result confined to the project's lint, compile/type, unit-test or integration-test recipes — green at base and red at head — taking one fix round back to S4 with no verification quota consumed and no queue item, refusing a diff that touches only test files; and the other S5 red exit, one `red_check` item resolved by waiver, send-back with a tag, or abandonment. All three re-enter mid-walk: the manifest is already pinned and S0–S1 already happened.

```mermaid
sequenceDiagram
    participant P as Person
    participant C as Control plane
    participant G as Execution boundary
    participant R as Record
    participant F as Factory as code
    participant E as External systems

    rect rgb(255,245,245)
    Note over P,E: Loop 1 - S2 blocking question (attempt 1)
    C->>G: dispatch S2 invocation, attempt 1 (X3)
    G-->>C: partial criteria, one blocking question (X3)
    C->>R: write partial criteria, question row, run ends blocked (X2)
    C->>P: question item - blocking (X1)
    P->>C: answer recorded in the list view (X1)
    C->>R: write answer, assumption row (X2)
    P->>C: factory advance JIRA-123 (X1)
    C->>G: fresh S2 rerun, attempt 2, prior artefact plus answer (X3)
    G-->>C: criteria complete, no open question (X3)
    C->>R: register criteria, state = planning (X2)
    end

    rect rgb(245,255,245)
    Note over P,E: Loop 2a - S5 red confined to lint/compile-type, or to unit/integration tests green at base and red at head
    C->>R: preflight creates review tuple (X2)
    R->>G: mount base and head copy-on-write views (X7) (AB)
    C->>G: run project and contract recipes in order (X3)
    G-->>C: red confined to lint/compile-type recipes, or to unit/integration tests green at base and red at head (X3)
    C->>R: write check_result (red), no red_check item queued (X2)
    C->>G: fresh S4 fix_round invocation, no queue item, quota untouched (X3)
    R->>G: mount worktree, scope-limited write (X7)
    G-->>C: fix diff, deviation entries for every changed test - a test-only diff is refused (X3)
    C->>G: run validation_only recipes once (X3)
    G-->>C: validation_only results (X3)
    C->>R: write check_result, hand-back (X2)
    C->>G: S5 project and contract recipes rerun in full (X3)
    C->>G: S5 security recipes rerun (X3) (AB)
    G-->>C: check results, all pass (X3)
    C->>R: write check_result, review tuple advances, state = review (X2)
    end

    rect rgb(255,250,240)
    Note over P,E: Loop 2b - the other red exit, one red_check item
    C->>G: run project and contract recipes in order (X3)
    C->>G: run security recipes (X3) (AB)
    G-->>C: red result - end-to-end recipe, or fix rounds exhausted (X3)
    C->>R: aggregate failures and waivable blind spots into one red_check item (X2)
    C->>P: red_check item - failed and blind-spot results (X1)
    alt waiver under R-S5-13
        P->>C: waiver - policy, scope, expiry (X1)
        C->>R: write waiver, check_result advances to review (X2)
    else send back with a tag
        P->>C: send_back tag and note - to context, clarifying or planning (X1)
        C->>R: write send_back tag, target stage reruns at attempt + 1 (X2)
    else abandon
        P->>C: abandon (X1)
        C->>R: write abandoned tag, not_deployed coverage, state = abandoned (X2)
    end
    end
```

## Derivation table

One row per PRD stage S0–S6 and per loop: what the trusted runner does, what the agent does (script-only stages carry "none"), the human touchpoint, and the requirement or state-table rows behind it.

| Stage | What the runner does | What the agent does | The touchpoint | Rows |
|---|---|---|---|---|
| S0 intake | Mechanical field gate; R-T-9 classifies and redacts the permitted source fields into `ticket_source`; service-tier, ticket-type and provisional-tier lookups; sensitive-path match; pilot-exclusion check; a script fills the scrutiny paragraph from the R-S0-6 template; pins the resolved manifest hash on the ticket | None: no agent runs at S0; the manifest's S0 agent, skill and model entries are null | `eligibility` item: eligible or not, type, data class, tier override, template scrutiny to confirm or edit | R-S0-1, R-S0-2, R-S0-5, R-S0-6, R-S0-7, R-S0-8, R-T-9, R-I-4; `02-3-ticket-states.md`:intake |
| S1 context gathering | Reads the context index and records `index_use`; computes the final tier; assembles and registers the `brief` | Touched-area discovery via codegraph; two-step archaeology; dependency evidence; writes the fact-only summary | None in the happy path (a blocker is loop 1's S2 shape, not S1's — S1's own blocker is out of this walk) | R-S1-2, R-S1-3, R-S1-4, R-S1-6, R-S1-7, R-S1-8, R-S1-11 |
| S2 requirements clarification | Dispatches the N restatement child runs for the agreement check; runs the forced-category rubric, question gate, ranker, format and wording validators, classifier, split-rule checker | Restates each criterion in EARS form with one example; raises questions | `question` item: answer or accept the default | R-S2-1, R-S2-2, R-S2-3, R-S2-4, R-S2-5, R-S2-6, R-S2-7, R-S2-8, R-S2-9, R-S2-10, R-S2-11, R-S2-12, R-S2-14 |
| S3 spec and plan, through `plan_review` | Runs `risk_map` (C9) before the invocation and `handoff_ready` (C9) after it; assembles the bootstrap checklist; creates the plan tuple; fetches the target branch and checks freshness before commit | Names the three risk-worthy places; writes the plan with its fixed tables | `plan_approval` item: approve the criteria-and-plan bundle, or send back with a tag | R-S3-11, R-S3-15, R-S3-18, R-S3-19, R-S3-20, R-S3-21, R-T-10; `02-3-ticket-states.md`:plan_review |
| S4 implementation | Pre-task revalidation of subject/base/head, fetching the target (R-S5-12); one fresh invocation per plan task, dispatched into the sandbox; runs each approved recipe exactly once inside the sandbox (R-I-14) and writes only its evidence to the record (R-I-17); tracks the three-verification quota; escalates on the third failure | Implements the task; writes `branch`, `head_sha`, `worktree_path`, the deviation set | None in the happy path | R-S4-1, R-S4-2, R-S4-5, R-S4-6, R-S4-9, R-S4-10, R-I-14, R-I-17, R-S5-12 |
| S5 cleanup pass | Trusted preflight fetches the target and creates the review tuple, with R-S6-6 final ownership; provisions the base/head sandbox; runs the project and contract recipes, then the security recipes (AB); aggregates failures; the S6 race guard (C9 through C4) recomputes the reviewer set before `packet_assemble`/`pr_body_assemble`; routes to a fix round or the human | None — S5 is scripts and recipes only | None when every result is `pass` or a validly waived `blind_spot` (loop 2 covers the red exits) | R-S5-1, R-S5-10, R-S5-12, R-S5-13, R-S4-9, R-S4-10, R-S6-6, R-I-14 |
| S6 human review and publication | S6 race guard recomputes the reviewer set from `checks`, before assembly; `packet_assemble` and `pr_body_assemble` scripts; the last quorum-completing approval and the outbox intent commit together in one transaction (R-T-11); outbox selects `pr_create`/`pr_update`, rechecks the subject, dispatches, reconciles the receipt | None | `packet_approval` item: approve or request changes | R-S6-1, R-S6-2, R-S6-3, R-S6-6, R-S6-7, R-S6-10, R-T-11 |
| Loop — S2 blocking question | Ends the run `blocked` after finishing independent work; holds the ticket in `clarifying`; reruns from the record at `attempt + 1` once the answer lands | Raises the blocking question through the question gate before the run ends | `question` item, blocking | R-S2-5, R-S2-6, R-S2-7, R-S2-9, R-S2-12, R-S2-14; `02-3-ticket-states.md`:clarifying, "Failed and blocked runs" |
| Loop — S5 fix round | Detects a red confined to the project's lint/compile-type recipes, or to a unit-test/integration-test recipe green at base and red at head; returns to `implementing` with no queue item; runs the `validation_only` recipe pass once; reruns S5 in full; counts the round against the S4 budget, never the verification quota | Fix-round invocation edits only within the plan's scope table and discretion globs; may change a test this ticket added or a base test the plan lists, never another; a round whose diff touches only test files is refused | None — no human action while rounds remain | R-S4-9, R-S5-1, R-S5-10, R-S4-10 |
| Loop — S5 other red exit | Aggregates every failure and waivable blind spot into one `red_check` item once fix rounds are exhausted or do not apply | None | `red_check` item: waiver under R-S5-13, send-back with a tag, or abandon | R-S5-1, R-S5-13; `02-3-ticket-states.md` Send-back paragraph |

## Not drawn

- S7 and the `pr_checks` state: all Later (`10-later-items.md`; one-page version, "Explicitly not there").
- The scheduled digest (`factory digest`, R-H-3) and the baseline read (R-O-6): both real crossings, but neither carries this ticket — the digest walks the whole queue and the baseline is a separate utility run frozen once before Milestone B.
- `bloat_signal` (R-F-7, agent definition, domain 5), `close_survey` (R-S7-5, queue item and decision, domain 1), the observer pass and calibration (R-O-10, R-O-11, fixtures and evals, domain 5), and any `score` row: Later — see `docs/prd/06-observability.md`; each is owned by the domain named, not restated here.
- X9 (the engineer's own factory pull request) and X10 (a governed export becoming a fixture): both real, but neither is a step in a ticket's own advance — X9 changes the tree that a later ticket reads, and X10 happens after this ticket closes, as its own reviewed change.
- Confluence sync, dashboards, the read-only MCP server, stacked pull requests, containers, the Claude Code adapter: Later, owned by domain 2 (external access) and domain 3 (the wall, the adapter) — see `L2-control-plane.md`, `L2-external-systems.md` and `L2-execution-boundary.md`; not restated here.
- Never drawn, per the brief's anti-goals: a push before quorum (the outbox dispatch in S6 follows, never precedes, the last approval); an agent holding a GitHub or Slack credential (Execution boundary only ever reaches External systems for the hosted model, the Atlassian proxy leg at S1, and registries at S5); the sandbox writing the record directly (every Record write in both diagrams originates at Control plane); the scheduler starting a stage; an approval carried past a change (S6's race guard and the S5/S6 freshness checks are drawn precisely because they refuse that).
