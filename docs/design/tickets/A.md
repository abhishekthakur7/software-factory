# Milestone A build tickets: walking skeleton

| | |
|---|---|
| Status | Draft v0.1 |
| Date | 2026-09-08 |
| Owner | Abhishek Thakur |
| Cites | `docs/design/milestones.md` v0.7 (section 3 "A, walking skeleton", Appendix A); `docs/prd/prd.md` v0.18 and its parts; `docs/charter.md` v0.14; `docs/design/hld/README.md` v0.3 |
| Milestone | A: the PRD's Milestone A, 89 requirement rows, every block alive in its thinnest shape |

## How to read

One ticket per section, in build order. A ticket depends only on tickets above it, so the file order is a topological order and the first tickets are the foundation. Every ticket names its milestone, its blocks by number from `milestones.md` section 1, its components by id from the HLD register, the tickets it depends on, the PRD rows it covers, what it builds and why, its scope in and out, numbered acceptance criteria that each restate one verification clause of one row as a test that passes or fails, and the test files and fixtures it adds. A row sits in exactly one ticket. `tools/tickets_check.py` enforces the format, the coverage of Appendix A, the placement, the dependency order and the citation of a row id on every criterion.

Two phases, fixed by `milestones.md` section 3. Phase 1, ledger and control (T-A-01 to T-A-17): the factory tree and manifest, the record, the artefact registry, the state table with the `factory` command and every stage a stub, the run ledger with leases, the owners file, the trust profile and the guard, the fixture project and git trees with the typed recipes, reviewer sets and approvals, binding, views and the report, queue items, the outbox with stub deliverers, freshness and refresh-base, crash recovery, export and import, and the stub walk with pause, resume and stop. Phase 2, the agent side (T-A-18 to T-A-35): the adapter, envelope and thin sandbox, the full manifest, then S0 to S6 stage by stage with the context index, tags and waivers where their rows first pass, and last the fixtures-and-evals walk that completes the adoption gate. Under PRD decision 39, each ticket's builder hand-writes `docs/build/<ticket-id>/brief.md` and `plan.md` before building that ticket; T-A-01 states the rule and writes its own pair, and T-A-27 and T-A-35 read the pairs every ticket before them wrote. Code locations not fixed by any source document are stated in T-A-01 and hold for every ticket: the runner is the Python package `runner/` with the `factory` command in `runner/cli.py`, its tests under `runner/tests/`, the adoption gate entry point `python3 -m runner.gate`, and eval directories under `factory/evals/<kind>/<name>/`.

## T-A-01: Factory tree, manifest file, hash script, fence and write barrier

| | |
|---|---|
| Milestone | A |
| Blocks | 8 Factory tree and change control; 4 Manifest |
| HLD components | F1, F2, C2 |
| Depends on | none |
| Rows covered | R-F-1, R-F-5, R-F-11 |

### Description

This ticket lays the `factory/` tree of PRD section 7 and the `runs/` directory outside version control, the foundation the rest of Milestone A builds files into. It fixes the code locations of brief section 3.7 for every later ticket: `runner/` as the trusted control plane, `runner/cli.py` as the `factory` command entry point, `runner/state_table.py` and `runner/anti_goals.py` as the fence of R-F-11, `runner/tests/` as the pytest suite, `factory/evals/<kind>/<name>/` as the eval-directory shape, and `python3 -m runner.gate` as the adoption-gate entry point. It builds `scripts/tools/manifest_hash` so the manifest hash is the hash of the committed manifest file, tested here on the tree it commits and not on completeness, since R-F-2's walk over every referenced file belongs to T-A-35. The write barrier keeps `factory/` read-only at run time, so a tag, a stale entry, a grader failure, or the engineer's own reading only ever produces a diff to review, never a runtime write (R-F-5). The fence keeps the state table and the anti-goals in runner code, outside the manifest and beyond any proposal path (R-F-11). It writes the hand-written pair `docs/build/T-A-01/brief.md` and `docs/build/T-A-01/plan.md` for itself under PRD decision 39, the rule every later ticket's builder follows for its own ticket before building it.

### Scope

**In:** `factory/manifest.yaml`; `factory/agents/`, `factory/skills/`, `factory/skills/shared/`; `factory/rubrics/`, `factory/rubrics/checklists/`; `factory/scripts/checks/`, `factory/scripts/tools/manifest_hash`; `factory/lints/`; `factory/evals/scripts/tools/manifest_hash/eval.yaml` and `factory/evals/scripts/tools/manifest_hash/fixtures/` (its own conformance fixture, so R-F-2 holds from the first commit); `factory/benchmarks/`, `factory/index/`, `factory/config/`, `factory/catalogue/`; `runs/` outside version control; `runner/state_table.py`, `runner/anti_goals.py`; `runner/gate.py` implementing `python3 -m runner.gate` in its thinnest form; `docs/build/T-A-01/brief.md` and `docs/build/T-A-01/plan.md`, this ticket's own hand-written pair under PRD decision 39; `runner/tests/test_tree_layout.py`; `runner/tests/test_manifest_hash.py`; `runner/tests/test_write_barrier.py`; `runner/tests/test_fence.py`.

**Out:** every referenced file existing and hashed, the manifest test's completeness walk (R-F-2) (T-A-35); the reviewed-change adoption path and its review-record and smoke-gate tests (R-F-4) (T-A-35); the manifest's full field set, model and budget resolution (R-I-4) (T-A-19); the state table's transition enforcement and the stub stage drivers (R-T-5) (T-A-04).

### Acceptance criteria

1. The `factory/` tree this ticket commits matches PRD section 7's layout: `manifest.yaml`, `agents/`, `skills/` with `skills/shared/`, `rubrics/` with `rubrics/checklists/`, `scripts/checks/`, `scripts/tools/`, `lints/`, `evals/`, `benchmarks/`, `index/`, `config/`, `catalogue/`, with `runs/` outside version control (R-F-1).
2. Every file entry in `factory/manifest.yaml` carries a `path` field and a `content_hash` field (R-F-1).
3. A manifest entry naming a path outside `factory/` is rejected by `scripts/tools/manifest_hash` (R-F-1).
4. `scripts/tools/manifest_hash` run over the committed tree returns the SHA-256 hash of the committed `factory/manifest.yaml` file (R-F-1).
5. Editing `factory/manifest.yaml` on disk without committing the change causes `scripts/tools/manifest_hash` to fail validation (R-F-1).
6. Running `scripts/tools/manifest_hash` before and after a walk that changes nothing under `factory/` returns the identical hash both times (R-F-1).
7. A script test scanning every module under `runner/` finds no call that opens a path under `factory/` for writing (R-F-5).
8. For each of a tag, a stale context-index entry, a repeated grader failure, and the engineer's own reading, a synthetic write attempt using that label as a stand-in event kind is tested against the same scan as criterion 7, and lands only as a git diff under `factory/` for the engineer to review, never as a runtime write (R-F-5).
9. `runner/state_table.py` holds the transition table that enforces R-T-5's gates, located outside `factory/` (R-F-11).
10. `runner/anti_goals.py` holds the anti-goals, located outside `factory/` (R-F-11).
11. A script test walking every file reference in `factory/manifest.yaml` finds none naming `runner/state_table.py` or `runner/anti_goals.py` (R-F-11).

### Verification

- `runner/tests/test_tree_layout.py`: criterion 1
- `runner/tests/test_manifest_hash.py`: criteria 2, 3, 4, 5, 6
- `runner/tests/test_write_barrier.py`: criteria 7, 8
- `runner/tests/test_fence.py`: criteria 9, 10, 11
- `factory/evals/scripts/tools/manifest_hash/fixtures/`: the `manifest_hash` conformance fixture backing criteria 4, 5, 6
- `runner/tests/fixtures/write_barrier/`: the synthetic write-attempt fixtures backing criterion 8

## T-A-02: Record: SQLite schema for every table, WAL, single writer

| | |
|---|---|
| Milestone | A |
| Blocks | 17 Record |
| HLD components | R1 |
| Depends on | T-A-01 |
| Rows covered | R-T-1 |

### Description

This ticket builds the one local record PRD 2.2 defines: a single SQLite database in WAL mode holding every Initial table, so no stage keeps state anywhere else between invocations (R-T-1). It sits on T-A-01's tree, since `runs/factory.sqlite` lives outside version control at the path that tree fixes. It creates every table brief section 3.4 names with every field `02-2-entities.md` gives it, and deliberately creates none of the five Later tables, `score`, `human_signal`, `proposal`, `benchmark`, and `fixture_candidate`, which land only with the migration accompanying the row that first writes each one. It also builds `runner/canonical.py`, the one canonical serialisation and content-hash function of PRD 2.2's preamble; every content hash and subject hash from this ticket on calls it. Append-only enforcement and the mutable-field allowlist are a separate concern the bare schema does not encode, built next once these tables exist.

### Scope

**In:** `runner/db.py` (opens `runs/factory.sqlite`, sets WAL mode, creates the schema); `runner/schema.py` (table and field definitions for `ticket`, `stage_run`, `utility_run`, `tool_call`, `artefact`, `queue_item`, `question`, `answer`, `assumption`, `deviation`, `generated_test`, `check_result`, `human_verdict`, `guard_decision`, `reviewer_set`, `approval_record`, `waiver`, `evidence_tuple`, `external_write`, `tag`, `incident_observation`, `index_use`, `baseline_measure`); `runner/canonical.py` (canonical JSON serialisation: UTF-8 strings, lexicographically ordered object keys, schema-fixed array order, SHA-256 over the result, excluding database ids, the hash field itself, and audit-only creation timestamps); `runner/tests/test_db_schema.py`; `runner/tests/test_db_isolation.py`.

**Out:** append-only enforcement and the mutable-field allowlist (R-T-3) (T-A-03); the state table and stub stage drivers that write into these tables (R-T-5) (T-A-04).

### Acceptance criteria

1. `runs/factory.sqlite` opens in WAL mode, confirmed by `PRAGMA journal_mode` returning `wal` (R-T-1).
2. For each of `ticket`, `stage_run`, `utility_run`, `tool_call`, `artefact`, `queue_item`, `question`, `answer`, `assumption`, `deviation`, `generated_test`, `check_result`, `human_verdict`, `guard_decision`, `reviewer_set`, `approval_record`, `waiver`, `evidence_tuple`, `external_write`, `tag`, `incident_observation`, `index_use`, and `baseline_measure`, the table exists with every field `02-2-entities.md` names for it (R-T-1).
3. None of `score`, `human_signal`, `proposal`, `benchmark`, or `fixture_candidate` exists as a table in the schema (R-T-1).
4. A stage run started against a database path pointing at a fresh, empty file finds no prior `ticket`, `stage_run`, or `artefact` rows (R-T-1).

### Verification

- `runner/tests/test_db_schema.py`: criteria 1, 2, 3
- `runner/tests/test_db_isolation.py`: criterion 4
- `runner/tests/test_canonical.py`: the canonical serialisation and content-hash function of `runner/canonical.py`, backing every later hash criterion

## T-A-03: Artefact registry and append-only enforcement

| | |
|---|---|
| Milestone | A |
| Blocks | 17 Record; 11 Artefact |
| HLD components | R1, R2 |
| Depends on | T-A-02 |
| Rows covered | R-T-3 |

### Description

This ticket builds the artefact registry, versioning files by kind, path, version, and content hash with a `supersedes` chain, and enforces append-only writes across the record so a new version is a new row and superseded versions stay readable (R-T-3). It builds the write-path allowlist that lets only the named mutable-exception fields change in place: ticket lifecycle fields, `question.state`, run outcome and lease fields, the one-time cost settlement of R-I-13, outbox state and receipt fields, and a queue item's one-time resolution fields, each change carrying its timestamp. It sits on T-A-02's schema, since the tables and fields it constrains must already exist.

### Scope

**In:** `runner/artefact_registry.py` (artefact registration by `kind`, `version`, `path`, `hash`, `supersedes`); `runner/record.py` (the write-path layer enforcing append-only inserts and the mutable-field allowlist over every table T-A-02 created); `runner/tests/test_append_only.py`; `runner/tests/test_mutable_exceptions.py`.

**Out:** the state table's transition enforcement (R-T-5) (T-A-04); the runtime adapter's one-time cost settlement write (R-I-13) (T-A-18); the outbox's state machine (R-T-11) (T-A-13); a queue item's resolution through `factory act` (T-A-12).

### Acceptance criteria

1. `artefact`: writing a new version of a registered file appends a new row whose `supersedes` field names the prior version; the prior row is never updated (R-T-3).
2. `assumption`: an existing row is never edited in place; superseding or withdrawing an assumption appends a new row naming the prior row (R-T-3).
3. `tag`: an existing tag row cannot be edited in place (R-T-3).
4. `deviation`: an existing deviation row cannot be edited in place (R-T-3).
5. `generated_test`: an existing identity or decision row cannot be edited in place; a later review appends a new decision row (R-T-3).
6. `answer`: an existing answer row cannot be edited in place (R-T-3).
7. `human_verdict`: an existing verdict row cannot be edited in place (R-T-3).
8. `guard_decision`: an existing guard decision row cannot be edited in place (R-T-3).
9. `reviewer_set`: an existing reviewer-set row cannot be edited in place (R-T-3).
10. `approval_record`: an existing approval record cannot be edited in place (R-T-3).
11. `waiver`: an existing waiver row cannot be edited in place (R-T-3).
12. `evidence_tuple`: an existing evidence tuple cannot be edited in place (R-T-3).
13. `incident_observation`: an existing incident observation row cannot be edited in place (R-T-3).
14. `question`: every field but `state` is append-only; an attempt to edit `question.reasoning` or `question.options` in place is rejected (R-T-3).
15. `ticket` lifecycle fields, `state`, `blocked_on`, `pause_requested`, `paused_at`, `tier_override_by`, `tier_override_at`, `tier_override_reason`, `opened_at`, `factory_completed_at`, `closed_at`, `close_reason`, `pr_url`, `pr_identity`, `last_remote_head_sha`, and `last_pr_body_hash`, are updatable in place, each change carrying a timestamp (R-T-3).
16. `question.state` is updatable in place (R-T-3).
17. `stage_run` outcome and lease fields, `outcome`, `failure_kind`, `started_at`, `heartbeat_at`, `lease_expires_at`, and `ended_at`, are updatable in place (R-T-3).
18. `stage_run` cost-settlement fields, `cost`, `currency`, `cost_basis`, `pricing_table_hash`, and `cost_settled_at`, are updatable exactly once, when the runtime settles cost after the run ends (R-T-3).
19. `external_write` state fields, `state`, `attempt`, its remote identity fields, and its governed receipt artefact fields, are updatable in place (R-T-3).
20. `queue_item` one-time resolution fields, `resolved_at`, `resolved_by`, `action`, `note`, and `active_attention_bucket`, are updatable exactly once (R-T-3).
21. A schema-level allowlist rejects an `UPDATE` naming any column of the append-only tables or `artefact` other than the fields named in criteria 15 to 20 (R-T-3).

### Verification

- `runner/tests/test_append_only.py`: criteria 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14
- `runner/tests/test_mutable_exceptions.py`: criteria 15, 16, 17, 18, 19, 20, 21

## T-A-04: State table as code, the `factory` command skeleton, every stage a stub

| | |
|---|---|
| Milestone | A |
| Blocks | 9 Ticket and its state; 18 Stage interface |
| HLD components | C2, C1, C6 |
| Depends on | T-A-01, T-A-02, T-A-03 |
| Rows covered | R-T-5 |

### Description

This ticket encodes the PRD 2.3 state table as data in `runner/state_table.py`, completing the fence T-A-01 opened, so every transition a ticket can take is enforced in trusted code and a stage invoked from the wrong state is refused and recorded (R-T-5). It builds `runner/cli.py`'s `factory advance`, `factory run`, and `factory show` verbs as thin wrappers over in-process functions, matching the brief's rule that every command is such a wrapper. It builds the stub stage drivers `runner/stages/S0.py` through `S6.py`, each moving the ticket to its next state, writing the stage's artefact kind as a registered stub file, and returning `pass`. Each stub's manifest entry names its stub agent, skill, and rubric files, each with its own eval directory and fixture, so R-F-2 holds from the first commit. It sits on T-A-02's schema and T-A-03's append-only write path, since every transition writes a `stage_run` row through that path. Transitions gated on quorum, a plan or review subject, an S6 assembly result, or an outbox receipt are tested here against seeded rows in the tables those later tickets fill live.

### Scope

**In:** `runner/state_table.py` (the complete PRD 2.3 transition table as data); `runner/cli.py` (`factory advance`, `factory run`, `factory show`, in thinnest form); `runner/stages/S0.py`, `S1.py`, `S2.py`, `S3.py`, `S4.py`, `S5.py`, `S6.py`; `factory/agents/S1.md`, `S2.md`, `S3.md`, `S4.md` (stub files); `factory/skills/S1.md`, `S2.md`, `S3.md`, `S4.md` (stub files); `factory/rubrics/S0.md`, `S1.md`, `S2.md`, `S3.md`, `S4.md`, `S5.md`, `S6.md` (stub files); `factory/manifest.yaml` entries naming these stub files by path and hash per stage; `factory/evals/agents/S1/` through `/S4/`, `factory/evals/skills/S1/` through `/S4/`, `factory/evals/rubrics/S0/` through `/S6/`, each with `eval.yaml` and `fixtures/`; `runner/tests/test_state_table.py`; `runner/tests/test_cli_skeleton.py`; `runner/tests/test_stub_stages.py`.

**Out:** real per-stage agent logic (T-A-20 through T-A-34, one ticket per stage); `factory queue` and `factory act` (R-H-1, R-H-12) (T-A-12); `factory pause`, `factory resume`, and `factory stop` (T-A-17); the full `factory show` status content of attempt, elapsed wall clock, budget remaining, and pause state (R-H-13) (T-A-17); `factory export`, `factory import`, and `factory purge` (R-T-4) (T-A-16); `factory tag` and `factory abandon` (T-A-12); the `tag` table and catalogue (R-T-6) (T-A-33); `factory refresh-base` (R-S5-12) (T-A-14); `factory migrate-manifest`'s re-approval mechanics (R-I-4) (T-A-19); `factory report` (R-O-5) (T-A-11); the manifest's full field set and model or budget resolution (R-I-4) (T-A-19); the exclusion of refused and `refused_request` runs from the first-attempt measure (R-O-4) (T-A-11); the live quorum computation and the S5 preflight's reviewer-set derivation over reviewer sets and approval records (R-S6-6) (T-A-09); the plan and review tuple construction, subject hashing, and preflight derivation (R-T-10) (T-A-10); the freshness checks at the plan-approval, S5 preflight, and pre-dispatch boundaries (R-S5-12) (T-A-14); the S6 assembly run itself (R-S6-1, R-S6-2) (T-A-31); the outbox's reconciliation of `external_write.state` (R-T-11) (T-A-13).

### Acceptance criteria

1. A newly created ticket enters `intake` (R-T-5).
2. A ticket in `intake` whose S0 scripts pass and whose `eligibility` item is granted moves to `context` (R-T-5).
3. A ticket in `intake` whose S0 scripts fail, or whose `eligibility` item is declined, moves to `rejected` (R-T-5).
4. For each of `intake`, `context`, `clarifying`, `planning`, `plan_review`, `implementing`, `checks`, `review`, and `escalated`, a ticket in that state on which `abandon` is recorded moves to `abandoned` (R-T-5).
5. A ticket in `context` whose S1 run outcome is `pass` moves to `clarifying` (R-T-5).
6. A ticket in `context` on which S1 discovers an Initial exclusion moves to `rejected` (R-T-5).
7. For each of `context`, `clarifying`, and `planning`, a ticket whose stage run fails a second time, or that is stopped, moves to `escalated` (R-T-5).
8. A ticket in `clarifying` that reaches S2 exit with no open blocking question moves to `planning` (R-T-5).
9. A ticket in `planning` for which S3 produces the criteria-and-plan approval bundle moves to `plan_review` (R-T-5).
10. A ticket in `planning` on which S3 discovers an Initial exclusion moves to `rejected` (R-T-5).
11. On a seeded `approval_record` row set representing full quorum for the same plan subject, and a seeded `evidence_tuple` row of kind `plan` whose recorded `base_sha` and target-base SHA equal the ticket's target branch head, a ticket in `plan_review` moves to `implementing` (R-T-5).
12. On a seeded `evidence_tuple` row of kind `plan` whose recorded base does not equal the ticket's target branch head, or on which `refresh_base` or a send-back is recorded, a ticket in `plan_review` moves to `context` (R-T-5).
13. For each of `planning` and `clarifying`, a ticket in `plan_review` on which a redirect is recorded with a `send_back` tag moves to that state (R-T-5).
14. A ticket in `implementing` on which S4 records a successful hand-back with `branch`, `head_sha`, and an explicit deviation set moves to `checks` (R-T-5).
15. On a seeded `evidence_tuple` row of kind `plan` whose recorded base is stale against the ticket's current target branch head, or on which `refresh_base` or a send-back is recorded, a ticket in `implementing` moves to `context` (R-T-5).
16. For each of `planning` and `clarifying`, a ticket in `implementing` on which a send-back is recorded moves to that state (R-T-5).
17. For each of the third verification failure, an exhausted infrastructure retry, budget abort, sandbox violation, an invalid recipe-policy binding, and stop, a ticket in `implementing` moves to `escalated` (R-T-5).
18. For each of a missing or malformed hand-back, an S4 removal return, and a fix round remaining, a ticket in `checks` moves back to `implementing` (R-T-5).
19. On a seeded `evidence_tuple` row of kind `review` whose recorded base is stale against the ticket's current target branch head, or on which a send-back is recorded, a ticket in `checks` moves to `context` (R-T-5).
20. On a seeded `reviewer_set` row representing a new or unresolved non-sensitive owner slot, or on which a send-back is recorded, a ticket in `checks` moves to `planning` (R-T-5).
21. A ticket in `checks` on which a send-back is recorded moves to `clarifying` (R-T-5).
22. A ticket in `checks` on which an accidental Initial-sensitive path required by the plan is discovered moves to `rejected` with `close_reason = pilot_excluded` (R-T-5).
23. For each of a sandbox-integrity failure, a second failure, and stop, a ticket in `checks` moves to `escalated` (R-T-5).
24. On a seeded `stage_run` row for stage `S5` with `outcome = 'pass'`, and a seeded `stage_run` row for the S6 assembly run with `outcome = 'pass'`, a ticket in `checks` moves to `review` (R-T-5).
25. For each of a seeded `approval_record` row set representing full quorum on the same review subject, and a seeded `external_write` row with `state = 'reconciled'` matching an already closed or merged remote pull request, a ticket in `review` moves to `pr_opened` (R-T-5).
26. On a seeded pre-dispatch mismatch of subject, authority, base, head, or destination superseding a seeded `external_write` intent, a ticket in `review` moves to `checks` (R-T-5).
27. For each of `planning` and `context`, a ticket in `review` on which a seeded pre-dispatch mismatch or a send-back is recorded moves to that state (R-T-5).
28. A ticket in `review` on which a send-back is recorded moves to `clarifying` (R-T-5).
29. A ticket in `review` on which request changes is recorded moves to `implementing` with a `revision_after_approval` tag (R-T-5).
30. For each of a non-retryable control failure, a second failure, and stop, a ticket in `review` moves to `escalated` (R-T-5).
31. A ticket in `pr_opened` on which the human records the merge moves to `merged`; a ticket in `pr_opened` on which the human records abandonment moves to `abandoned` (R-T-5).
32. For each of `context`, `clarifying`, `implementing`, and `planning`, a ticket in `pr_opened` on which a requested revision is recorded through that selected earlier stage moves to it (R-T-5).
33. For each of `planning`, `clarifying`, and `context`, a ticket in `escalated` whose verification exhaustion is resolved by a superseding plan-item version and new approval moves to that state (R-T-5).
34. A ticket in `escalated` whose control defect is remediated moves to `context` (R-T-5).
35. For each of `implementing`, `checks`, and `review`, a ticket in `escalated` whose infrastructure exhaustion or human stop is resumed moves back to that same state with verification count preserved (R-T-5).
36. For each of `rejected`, `merged`, and `abandoned`, the state accepts no further transition (R-T-5).
37. `factory migrate-manifest` moves a ticket from any state to `context` (R-T-5).
38. The `validation_only` run of R-S4-9 is recorded as an S4 run from `implementing` with no state change (R-T-5).
39. A stage invoked for an existing ticket from a state other than the one that precedes it in the transition table is refused, recorded as that ticket's `stage_run` with `outcome = 'refused'` (R-T-5).
40. `factory run` given a ticket id that does not exist is rejected before a `stage_run` exists, recorded as a `utility_run` of kind `refused_request` (R-T-5).
41. `factory run` given a stage not valid for the ticket's current state is rejected before a `stage_run` exists, recorded as a `utility_run` of kind `refused_request` (R-T-5).

### Verification

- `runner/tests/test_state_table.py`: criteria 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38
- `runner/tests/test_cli_skeleton.py`: criteria 39, 40, 41
- `runner/tests/test_stub_stages.py`: criteria 2, 5, 8, 9, 14, 24
- `runner/tests/fixtures/state_table/`: seed rows for the quorum, plan and review subject, S6 assembly, and outbox-receipt transition families, one file per family, backing criteria 11, 12, 15, 19, 20, 24, 25, 26, 27
- `factory/evals/agents/S1/fixtures/` through `/S4/fixtures/`: the stub agents' own conformance fixtures, R-F-2 held from the first commit
- `factory/evals/skills/S1/fixtures/` through `/S4/fixtures/`: the stub skills' own conformance fixtures
- `factory/evals/rubrics/S0/fixtures/` through `/S6/fixtures/`: the stub rubrics' own conformance fixtures

## T-A-05: Run ledger: kinds, attempts, leases, heartbeat, budgets from `tiers.yaml`, cost provenance

| | |
|---|---|
| Milestone | A |
| Blocks | 10 Run |
| HLD components | C3 |
| Depends on | T-A-02, T-A-04 |
| Rows covered | R-T-12 |

### Description

This ticket builds the run ledger PRD 2.2 describes: `stage_run` always bound to a non-null ticket and a stage `S0` to `S7`, with child invocations keeping `parent_run_id`, and a separate `utility_run` table for work that is not itself a ticket stage (R-T-12). It closes the run-kind set the A-shape names, `task`, `fix_round`, and `validation_only` on `stage_run` alongside `utility_run`, with `attempt` and `verification_attempt` counters and the outcome and failure-kind values the shape lists, including `refused`, `aborted_human`, `infrastructure_failure`, and `expired_lease`. It seeds `factory/config/tiers.yaml` with the placeholder token and wall-clock budgets of PRD section 8 and the cost-provenance fields the record carries. It sits on T-A-02's schema and T-A-04's state table, since every run this ledger writes advances through that table. Crash recovery over these leases is T-A-15's; budget abort against these budgets is T-A-19's.

### Scope

**In:** `factory/config/tiers.yaml` (tier matrix, budgets per stage and tier as `tokens` and `wall_clock_seconds`, the S4 per-ticket cumulative budgets); `runner/run_ledger.py` (writes `stage_run` and `utility_run` rows, the `run_kind` values `task`, `fix_round`, and `validation_only`, the `outcome` and `failure_kind` values, lease and heartbeat fields, cost-provenance fields `cost_basis`, `pricing_table_hash`, and `cost_settled_at`); a minimal `stage_reliability_view` over `stage_run` (utility-run exclusion only), narrowed further by T-A-11 into the R-O-4 first-attempt view of the same name; `runner/tests/test_run_ledger.py`; `runner/tests/test_reliability_view.py`.

**Out:** crash recovery over expired leases and outbox-first restart (R-O-1) (T-A-15); budget-abort enforcement and manifest migration on a changed budget (R-I-6) (T-A-19); the reasoning-summary length cap (R-O-1) (T-A-15); the R-O-4 first-attempt narrowing of `stage_reliability_view` and the full measure-view set (R-O-4) (T-A-11).

### Acceptance criteria

1. Creating a `stage_run` row with a null `ticket_id` is rejected by the schema (R-T-12).
2. Creating a `stage_run` row with a `stage` value outside `S0` to `S7` is rejected by the schema (R-T-12).
3. A child `stage_run` created during a parent's execution, such as an S2 restatement, carries `parent_run_id` pointing at the parent run (R-T-12).
4. For each of `setup`, `digest`, `baseline_import`, `purge`, `reindex`, `report`, `fixture_replay`, `improvement`, and other non-stage work, a seeded `utility_run` row of that kind is excluded from `stage_reliability_view` (R-T-12).

### Verification

- `runner/tests/test_run_ledger.py`: criteria 1, 2, 3
- `runner/tests/test_reliability_view.py`: criterion 4

## T-A-06: Owners file, roles, authority-policy hash and identity snapshot

| | |
|---|---|
| Milestone | A |
| Blocks | 14 Approval and quorum |
| HLD components | H1, H4, F6 |
| Depends on | T-A-01, T-A-02 |
| Rows covered | R-F-13 |

### Description

This ticket builds `factory/config/owners.yaml`, the authority policy R-F-13 names: factory owner, security approver, legal/data-governance approver, service and sensitive-path owners, ticket engineer, S3 reviewer, S6 reviewer, outcome recorder, and incident reviewer, each with its stated responsibilities. The file's content hash becomes the authority-policy hash bound into every trust and ticket approval, while identity and team membership are snapshotted separately at each decision, so a role assignment and a person's identity at decision time are never conflated. It records where one pilot person holds several non-sensitive roles, and gates one identity filling both trust roles on the `both_trust_roles_identity` key this ticket also seeds in a thin `factory/config/trust-profile.yaml`, per the placement decision that leaves the profile's remaining content to a later ticket. It sits on T-A-01's tree and T-A-02's `approval_record` schema, since the hash and snapshot fields it populates already exist there.

### Scope

**In:** `factory/config/owners.yaml`; `factory/config/trust-profile.yaml` (carrying only the `both_trust_roles_identity` key); `runner/owners.py` (loads and validates `owners.yaml`, computes its content hash as the authority-policy hash, exposes role identities and the `both_trust_roles_identity` check); `runner/tests/test_owners.py`; `runner/tests/test_trust_role_permission.py`.

**Out:** `trust-profile.yaml`'s remaining content, routes, classes, and sanitiser identities (R-T-9) (T-A-07); reviewer sets, approval records, and quorum computation (R-S6-6) (T-A-09); the sensitive-path Initial-exclusion enforcement (R-S0-5, R-S0-8) (T-A-20).

### Acceptance criteria

1. `factory/config/owners.yaml` names an identity for factory owner, security approver, legal/data-governance approver, service owner, sensitive-path owner, ticket engineer, S3 reviewer, S6 reviewer, outcome recorder, and incident reviewer (R-F-13).
2. `factory/config/owners.yaml` records against each role the specific responsibility categories it owns from tiers, topology, trust policy, sandbox/recipes, manifests/rubrics, waivers, approvals, and incident attribution/disposition, and a schema test rejects a role entry whose responsibilities list is empty (R-F-13).
3. A schema test over `factory/config/owners.yaml` fails when a required role has no assigned identity (R-F-13).
4. The content hash of `factory/config/owners.yaml` is recorded as `approval_record.authority_policy_hash` (R-F-13).
5. `approval_record`'s identity/team-membership snapshot is written fresh at each decision, independent of the authority-policy hash (R-F-13).
6. A seeded pilot identity holding two non-sensitive roles is recorded in `owners.yaml` with a note stating both roles are held by that identity (R-F-13).
7. Assigning one identity to both the security-approver and legal/data-governance-approver role slots is accepted only when `factory/config/trust-profile.yaml`'s `both_trust_roles_identity` key names that identity, and rejected when the key is unset (R-F-13).
8. `owners.yaml` names a sensitive-path owner role distinct from the ticket-engineer role (R-F-13).
9. `factory/config/trust-profile.yaml`, as built by this ticket, carries only the `both_trust_roles_identity` field (R-F-13).

### Verification

- `runner/tests/test_owners.py`: criteria 1, 2, 3, 4, 5, 6, 8, 9
- `runner/tests/test_trust_role_permission.py`: criterion 7

## T-A-07: Trust profile, governance approvals and the guard on every crossing

| | |
|---|---|
| Milestone | A |
| Blocks | 6 Trust profile; 23 Guard |
| HLD components | F6, C5, H4, C1 |
| Depends on | T-A-02, T-A-03, T-A-04, T-A-06 |
| Rows covered | R-T-9 |

### Description

Data governance is fail-closed, the trust boundary charter C9 requires. This ticket builds `config/trust-profile.yaml` as the one content-addressed policy the guard enforces: its classification taxonomy, join and default-deny rules, admitted scopes, and every route the walk crosses at A, each with a stub deliverer where the route is not real yet. A governance-only console shows the proposed profile and `owners.yaml` metadata to the security and legal approvers before activation and writes only a metadata-only decision. Thereafter one runner-owned guard sits on every content-bearing crossing, denying an unknown class, an absent route, a missing or expired approval, or a secret hit, and never storing rejected secret material (FM-24). The trust-approval subject hash and the authority-policy hash it binds both call the one canonical serialisation function `runner/canonical.py` builds (T-A-02); this ticket adds no separate hashing routine. It builds on the canonical function (T-A-02), the artefact registry (T-A-03), the state table (T-A-04), and the owners file (T-A-06), whose content hash is the authority-policy hash the trust approval binds.

### Scope

**In:** `factory/config/trust-profile.yaml`; `runner/trust_profile.py` (schema, class-join, sanitizer-route resolution, subject and authority-policy hashes computed by calling T-A-02's `runner/canonical.py`); `runner/governance.py` (the governance-only console as an in-process function); `runner/guard.py` (the single guard seat, `guard_decision` writes); `approval_record` rows with `gate = 'trust_profile'`; `runner/tests/test_trust_profile.py`; `runner/tests/test_guard.py`; `runner/tests/fixtures/trust_profile/`; `runner/tests/fixtures/guard/`.

**Out:** the pilot repository and its real routes (AB); the Atlassian read routes (AB); the outbox's own stub deliverers (T-A-13); governed export, import and purge under the profile's rules (T-A-16); the reviewer-set derivation behind the governance-quorum approval slots (T-A-09).

### Acceptance criteria

1. A fixture `config/trust-profile.yaml` validates against its schema for each of: the classification taxonomy, the dominance/join rules, the default-deny rule, the admitted repository, Jira-project and Confluence-space scopes, and, per permitted route, purpose, fields, provider/model or MCP endpoint, processing and storage location, logging and training/reuse terms, subprocessors, residency, reader roles, export rule, retention/deletion rule, and classifier/redactor/secret-rule hash, plus the immutable references to the approved provider terms/DPA and security assessment; a file missing one of these fields fails validation (R-T-9)
2. Before `trust-profile.yaml` is activated, the governance-only console displays only the proposed profile and `owners.yaml` authority metadata to the configured security and legal/data-governance approvers, writes their signed metadata-only decisions to a trusted audit sink, and a fixture asserts the console cannot read, persist or dispatch production content (R-T-9)
3. A seeded pair of input data classes with no valid join in the profile's dominance/join rules is submitted to the guard, and the operation is denied (R-T-9)
4. A seeded approval set that does not satisfy the profile's configured slots and separation rule fails activation, and a seeded approval set that does satisfy them, over the trust-approval subject hash of the profile plus the authority-policy hash, activates it (R-T-9)
5. A seeded security or legal `approval_record` row with `gate = 'trust_profile'` and a past `expiry` no longer satisfies the profile's activation quorum, since expiry is mandatory for every `trust_profile` approval (R-T-9)
6. A seeded change to `owners.yaml`'s content hash changes the authority-policy hash bound into the trust-approval subject, and a previously satisfying approval set no longer satisfies the new subject (R-T-9)
7. A seeded sanitizer implementation/rule hash permitted only for one named source-to-target class pair is denied by the guard when invoked outside that pair, and records the permitted downgrade instead of the plain join when invoked inside it (R-T-9)
8. For each of the guard's seated crossings, content-bearing ingress, persistence, display, sandbox mounting, logs, model/MCP/tool dispatch, outbox payloads, and exports, a seeded content-bearing operation attempted outside the guard is refused; the sandbox-mounting, outbox-payload, and export crossings are exercised through seeded operation fixtures under `runner/tests/fixtures/guard/` against the bare guard module rather than through T-A-13's, T-A-16's, or T-A-18's live code (R-T-9)
9. For each of the guard's seated crossings, content-bearing ingress, persistence, display, sandbox mounting, logs, model/MCP/tool dispatch, outbox payloads, and exports, a seeded content-bearing operation routed through the guard writes exactly one `guard_decision` row (R-T-9)
10. A seeded ticket or repository text containing an instruction to widen tools, recipes, mounts, or credentials is treated as untrusted content, and the operation's allowed tools, recipes, mounts and credentials are unchanged (R-T-9)
11. A seeded secret or restricted-pattern hit is denied by the guard, and the resulting `guard_decision` row stores only the rule id and safe provenance, never the match, surrounding text, raw payload, or a reversible digest (R-T-9)
12. A seeded content-bearing operation naming a route absent from `trust-profile.yaml` is denied by the guard (R-T-9)
13. A seeded content-bearing operation attempted while the guard is unavailable is denied (R-T-9)
14. A seeded digest payload carrying full ticket text, code, or question options is submitted through the guard toward the digest route's declared destination fixture, and only ticket identifier, tier, item kind, age and local command/link pass through (R-T-9)
15. `trust-profile.yaml`'s `both_trust_roles_identity` field names one identity, and a seeded approval set for that identity holding both the security and legal/data-governance slots activates the profile only because the field is set (R-T-9)
16. A seeded export request over the governed export and display route is evaluated against that route's export-rule field in `trust-profile.yaml`, and a request outside the rule is denied (R-T-9)
17. A seeded artefact past the display route's retention/deletion-rule value from `trust-profile.yaml` is flagged as subject to deletion, distinct from one still inside its retention window (R-T-9)
18. For each of the trust profile's five routes crossed by the walk, the hosted model endpoint, the governed export and display route, GitHub `pr_create`/`pr_update`, the Slack digest intent, and the optional Jira feedback intent, `trust-profile.yaml` names its provider and reader role, and every route but the hosted model ends at a stub deliverer (R-T-9)
19. The governance view records one `approval_record` row per acting security or legal/data-governance approver with `gate = 'trust_profile'`, a mandatory `expiry`, and the canonical trust-approval subject hash (R-T-9)
20. A seeded secret in an export payload over the governed export route is denied by the guard, and the `guard_decision` row stores no match, raw payload, or reversible digest, matching A's exit test (R-T-9)

### Verification

`runner/tests/test_trust_profile.py`: criteria 1, 6, 7, 15, 16, 17, 18
`runner/tests/test_guard.py`: criteria 2, 3, 4, 5, 8, 9, 10, 11, 12, 13, 14, 19, 20
`runner/tests/fixtures/trust_profile/`: seeded profile, class-taxonomy, route, and approval-set fixtures for criteria 1, 3, 4, 6, 7, 15, 16, 17, 18
`runner/tests/fixtures/guard/`: seeded content-bearing operation, absent-route, unavailable-guard, secret-hit, digest-payload, injected-instruction, and sandbox-mounting/outbox-payload/export operation fixtures for criteria 2, 5, 8, 9, 10, 11, 12, 13, 14, 19, 20

## T-A-08: Fixture project seed and git trees; typed recipe catalogue, validator, execution by id, the fixture project's recipes and impact method

| | |
|---|---|
| Milestone | A |
| Blocks | 25 Git trees; 21 Recipe; 7 Fixtures and evals |
| HLD components | R3, C8, G2, F6, F8 |
| Depends on | T-A-01, T-A-04, T-A-07 |
| Rows covered | R-I-16 |

### Description

Commands are versioned typed recipes, never plan-authored shell, against untrusted execution escaping its bounds (FM-23). This ticket seeds the synthetic Java fixture project under `factory/evals/fixture-project/`, with its vendored dependency repository, a `CODEOWNERS` file, one sensitive path, and its own rows in `service-tiers.yaml` and `ticket-types.yaml`, and materialises it at setup as a pinned git repository outside `factory/` and the manifest hash. It builds the per-ticket clone and worktree, plain base and head checkouts and their throwaway copies, and the typed recipe catalogue and validator, refusing shell interpolation, an undeclared executable, a cwd escape, an environment leak, a timeout overrun, or an unexpected result. The fixture project's lint, compile, unit, integration and one end-to-end recipe, and its `impact_scan` import-scan method over `artifact-to-service.yaml`, run against this same repository. It depends on the factory tree (T-A-01), the state table (T-A-04), and the trust profile (T-A-07) whose admitted scope is this repository.

### Scope

**In:** `factory/evals/fixture-project/` (seed, `vendor/`, `CODEOWNERS`, one sensitive path); `factory/config/service-tiers.yaml`, `factory/config/ticket-types.yaml` (fixture-project rows); `factory/config/project.yaml` (checkout path, target branch); `runner/setup.py` (materialisation); `runner/git_trees.py` (clone, worktree, plain checkouts, throwaway copies); `factory/config/command-recipes.yaml`; `runner/recipes.py` (catalogue validator, execution by id); `factory/scripts/checks/impact_scan`; `factory/config/artifact-to-service.yaml`; `factory/evals/scripts/checks/impact_scan/` (eval.yaml, fixtures); `runner/tests/test_recipes.py`; `runner/tests/test_fixture_project.py`; `runner/tests/fixtures/command-recipes/`.

**Out:** freshness at the three boundaries and `refresh-base` (T-A-14); the pilot repository's own recipes and the security recipes (AB); binding a recipe result to a review tuple and the ordered S5 check list itself (T-A-10, T-A-30); result delivery to the agent through the proxy and the inline-truncation limit of R-I-17 (AB).

### Acceptance criteria

1. A recipe entry validates against its schema for each of: `id`, executable digest or sandbox-image path, argument vector with typed placeholders, fixed working-directory role, permitted stages, timeout, expected exit codes, environment-name allowlist, network policy, output-retention rule, and, for a test recipe, its level (unit, integration, end-to-end); a recipe missing one of these fields fails validation (R-I-16)
2. A recipe entry constructed with shell interpolation or command-substitution syntax in an argument value is refused by the catalogue validator before dispatch (R-I-16)
3. A recipe entry constructed with a redirection operator in an argument value is refused by the catalogue validator before dispatch (R-I-16)
4. A recipe invocation naming an executable digest not present in the entry's declared digest is refused by the validator (R-I-16)
5. A recipe argument that resolves outside its declared fixed working-directory role is refused by the validator (R-I-16)
6. A recipe requesting an environment variable outside its declared environment-name allowlist is refused by the launcher before dispatch (R-I-16)
7. A recipe run past its declared timeout is terminated and recorded with a timeout outcome (R-I-16)
8. A recipe whose exit code falls outside its declared expected exit codes is recorded as a failed result (R-I-16)
9. A recipe is invoked only by its catalogue id and typed argument values, and a plan-authored shell string given in place of a recipe id is refused (R-I-16)
10. `factory/evals/fixture-project/` holds the committed seed of the synthetic Java fixture project with a `CODEOWNERS` file and one sensitive path (R-I-16)
11. `factory/evals/fixture-project/vendor/` holds the vendored dependency repository, and the fixture project's dependency resolution reads it, never a registry endpoint (R-I-16)
12. The fixture project's own service is seeded as a T2 row in `factory/config/service-tiers.yaml` and as a `small_feature`-eligible row in `factory/config/ticket-types.yaml` (R-I-16)
13. `runner/setup.py` materialises the fixture-project seed as a git repository at the path `factory/config/project.yaml` names, with the vendored repository beside it, outside `factory/` and outside the manifest hash (R-I-16)
14. At eligibility the runner creates an isolated clone and worktree under `runs/tickets/<id>/`, recording `base_sha` and `target_base_sha`, and later `head_sha`, with no push URL configured (R-I-16)
15. The runner produces a plain base checkout and a plain head checkout of the fixture project, each usable independently of the ticket worktree (R-I-16)
16. A check that must write into a checkout runs against a throwaway copy of the base or head checkout, leaving the original checkout unmodified (R-I-16)
17. For each of the fixture project's `lint` and `compile` recipes, invoking it by id runs the corresponding tool and reports a pass or fail result (R-I-16)
18. For each of the fixture project's `unit`, `integration`, and one `end-to-end` test recipe, invoking it by id carries its declared `level`, its test-file globs, and reports the test identities it ran (R-I-16)
19. `factory/scripts/checks/impact_scan`, run over the fixture project, resolves its Maven or Gradle dependency tree through `factory/config/artifact-to-service.yaml`'s mapping filled for the fixture project, and records each resolved dependency's coverage as `authoritative`, `partial`, or `unknown` (R-I-16)

### Verification

`runner/tests/test_recipes.py`: criteria 1, 2, 3, 4, 5, 6, 7, 8, 9
`runner/tests/test_fixture_project.py`: criteria 10, 11, 12, 13, 14, 15, 16, 17, 18, 19
`runner/tests/fixtures/command-recipes/`: injection, redirection, undeclared-executable, cwd-escape, environment-leak, timeout, and expected-result fixtures for criteria 2, 3, 4, 5, 6, 7, 8
`factory/evals/scripts/checks/impact_scan/eval.yaml`, `factory/evals/scripts/checks/impact_scan/fixtures/`: criterion 19

## T-A-09: Reviewer sets from CODEOWNERS and the owners file into slots, approval records, quorum

| | |
|---|---|
| Milestone | A |
| Blocks | 14 Approval and quorum |
| HLD components | H4, C9, C8 |
| Depends on | T-A-02, T-A-06, T-A-08 |
| Rows covered | R-S6-6 |

### Description

Who must approve what is derived from CODEOWNERS and the owners file, never from an agent's own say-so, since autonomy stays bounded by verification. This ticket derives the actual `reviewer_set` at S5 preflight from the exact diff read at the recorded target-base SHA, merging a planned/actual collision to the maximum count and the union of separation constraints while preserving a nonmatching slot, and flagging a new or unresolved owner as a blocking result. It builds the `approval_record` shape, one immutable row per actor and slot with its attestation version and hash, and quorum counted over distinct canonical actors with forked-head detection. Reviewer-set and approval-record content hashes call the one canonical serialisation function `runner/canonical.py` builds (T-A-02); this ticket adds no separate hashing routine. The S6 race guard recomputes the same derivation, exposed as an in-process function, immediately before packet assembly and dispatch. It depends on the canonical function (T-A-02), the owners file (T-A-06), and the fixture project's `CODEOWNERS` (T-A-08).

### Scope

**In:** `runner/reviewer_sets.py` (CODEOWNERS read at the pinned checkout, slot derivation, collision merge, race-guard recompute); `reviewer_set` rows of kind `actual`; `approval_record` schema fields (gate, subject hash, slot, actor, attestation version/hash, decision, expiry), with reviewer-set and approval-record content hashes calling T-A-02's `runner/canonical.py`; `runner/approvals.py` (quorum over distinct actors, forked-head detection); `runner/tests/test_reviewer_sets.py`; `runner/tests/test_approval_records.py`; `runner/tests/test_race_guard.py`; `runner/tests/fixtures/reviewer_sets/`.

**Out:** the plan/review evidence tuples the reviewer-set hashes bind into, and the refusal of review-tuple creation on an unresolved owner (T-A-10); waivers over a blocking blind spot (T-A-32); the post-graduation distinct-owner rule (B).

### Acceptance criteria

1. During S5 preflight, the actual `reviewer_set` is derived from the exact diff using CODEOWNERS read at the recorded `target_base_sha`, and every path-to-rule-to-owner match is recorded on the resulting row (R-S6-6)
2. A planned and actual slot sharing one canonical key of role, owner and source rule merges into the effective set using the maximum of their minimum approval counts and the union of their `distinct_from` constraints; removing a planned path never removes its slot, and a nonmatching slot is preserved (R-S6-6)
3. A new or unresolved owner on the actual diff makes the actual `reviewer_set` derivation return an unresolved-owner block result instead of a satisfying set; for a non-sensitive mismatch the ticket may return to planning, return to S4 to remove the path, or abandon (R-S6-6)
4. For an Initial sensitive-path match, the only routes are returning to S4 to remove the path or closing the ticket `pilot_excluded`, and neither route is waivable (R-S6-6)
5. A seeded `reviewer_set` slot carrying a `distinct_from` constraint against another slot's owner blocks the gate when both slots would be satisfied by the same actor identity (R-S6-6)
6. S6 recomputes the actual-reviewer-set derivation, exposed as an in-process function, immediately before packet assembly and dispatch (R-S6-6)
7. A change to the actual diff after S5 preflight invalidates the previously derived actual `reviewer_set`, and the S6 recompute produces a fresh one before dispatch (R-S6-6)
8. A `reviewer_set` row of kind `actual` carries a canonical slot per match with its canonical key of role, owner and source rule, matched path, source rule and pattern, precedence, canonical role or owner, minimum approval count, and `distinct_from` constraints (R-S6-6)
9. An `approval_record` row carries gate, canonical subject hash, slot id and scope, actor canonical identity, role, authority-policy hash and membership snapshot, decision, attestation version and hash, decision time, and optional expiry (R-S6-6)
10. Quorum for a gate counts only distinct canonical actor identities; two `approval_record` rows from the same actor for one slot count once (R-S6-6)
11. For one `(gate, subject, slot, actor)`, a seeded second unsuperseded `approval_record` head blocks the gate as a forked head (R-S6-6)

### Verification

`runner/tests/test_reviewer_sets.py`: criteria 1, 2, 3, 4, 5, 7, 8
`runner/tests/test_approval_records.py`: criteria 9, 10, 11
`runner/tests/test_race_guard.py`: criterion 6
`runner/tests/fixtures/reviewer_sets/`: CODEOWNERS, sensitive-path, and planned/actual collision fixtures for criteria 1, 2, 3, 4, 5, 7, 8

## T-A-10: Binding: canonical serialisation, subject hashes, plan and review tuples, preflight construction

| | |
|---|---|
| Milestone | A |
| Blocks | 15 Binding |
| HLD components | C4 |
| Depends on | T-A-02, T-A-03, T-A-07, T-A-09 |
| Rows covered | R-T-10 |

### Description

A binding is a hash over exactly what a decision, tuple, or invocation refers to, stale the moment any input changes, since a stale approval must never reach a pull request or merge unreviewed. T-A-02's `runner/canonical.py` implements the one canonical serialisation function of PRD 2.2's preamble, SHA-256 over lexicographically ordered UTF-8 JSON excluding database ids and audit-only timestamps; this ticket adds the plan and review `evidence_tuple` rows it hashes: the plan tuple's ticket-source, brief, criteria, plan, question-resolution and assumption-set hashes bound to `base_sha`, and the review tuple's added head, diff, and reviewer-set hashes. S5 preflight constructs the review tuple, exposed as an in-process function, only after every candidate component is current; expiry invalidates a satisfying approval set, while an expected S4 head change never invalidates the plan tuple. It depends on the canonical function (T-A-02), the artefact registry (T-A-03), the trust profile (T-A-07), and reviewer sets (T-A-09).

### Scope

**In:** `runner/binding.py` (the plan and review `evidence_tuple` compositions and S5-preflight tuple construction, calling T-A-02's `runner/canonical.py`); `evidence_tuple` rows of kind `plan` and `review`; the plan-tuple and review-tuple field sets; S5-preflight tuple construction as an in-process function; `runner/tests/test_binding.py`; `runner/tests/test_preflight.py`; `runner/tests/fixtures/binding/`.

**Out:** the freshness boundaries that invalidate a tuple's target-base SHA and `refresh-base` (T-A-14); waivers bound into the plan or review tuple (T-A-32); the S6 publication-target and review-approval subject added to the review tuple (T-A-34).

### Acceptance criteria

1. T-A-02's canonical serialisation function orders object keys lexicographically, fixes schema-defined array ordering, encodes UTF-8 strings, and hashes with SHA-256, excluding database ids, the hash field itself, and audit-only creation timestamps from every subject hash (R-T-10)
2. A seeded new answer changes the plan tuple's question-resolution-set hash, and a seeded superseding assumption changes its current-assumption-set hash; either change produces a new plan-tuple content hash (R-T-10)
3. A reviewer slot's planned and actual instances sharing one canonical key of role, owner and source rule merge to the maximum required count and the union of all separation constraints, and removing a planned path never removes its slot (R-T-10)
4. Expiry of a satisfying approval record invalidates the plan or review tuple's satisfying approval set and requires a fresh quorum recorded against the same unchanged subject hash (R-T-10)
5. The review tuple's actual and effective reviewer-set hashes and their provenance are bound into its content hash, distinct from the plan tuple's planned reviewer-set hash (R-T-10)
6. S5 preflight constructs the review tuple, exposed as an in-process function over seeded plan-tuple, diff, and reviewer-set components, only after every candidate component is verified present and current; a missing or stale component refuses tuple creation (R-T-10)
7. A gate passes only when the current, unexpired approval records for every required slot approve the identical subject and meet each slot's minimum count and `distinct_from` constraint (R-T-10)
8. A seeded S4 hand-back that advances `ticket.head_sha` through one or more task commits, with `base_sha` unchanged, does not invalidate the already-approved plan tuple, since the plan tuple binds `base_sha`, not `head_sha` (R-T-10)
9. A `plan` `evidence_tuple` row binds ticket-source, brief, criteria and plan hashes, question-resolution-set and current-assumption-set hashes, `base_sha`, manifest, project-config, trust-profile, trust-approval-set, recipe-set, sandbox and toolchain hashes, the planned reviewer-set hash, and the semantic-checklist, human-verdict-set and plan-waiver-set hashes, with its content hash the exact plan-approval subject; of these, only the sandbox and toolchain digests are seeded placeholder values at this ticket, their real values arriving with T-A-18 and T-A-19 (R-T-10)
10. A `review` `evidence_tuple` row references its `plan_tuple_id` and satisfying plan-approval-set hash, and adds the exact `head_sha`, diff hash, deviation-set hash, current target-base SHA, and actual and effective reviewer-set hashes (R-T-10)
11. An `evidence_tuple` row is never updated after creation; a changed bound component or authority-policy hash is asserted only by comparison against current state, producing a new subject rather than mutating the existing row (R-T-10)

### Verification

`runner/tests/test_binding.py`: criteria 1, 2, 3, 4, 5, 7, 8, 9, 10, 11
`runner/tests/test_preflight.py`: criterion 6
`runner/tests/fixtures/binding/`: seeded plan-tuple and review-tuple component fixtures for criteria 1, 2, 6, 9, 10

## T-A-11: Measure views, the report, the context label

| | |
|---|---|
| Milestone | A |
| Blocks | 17 Record |
| HLD components | R5, C1 |
| Depends on | T-A-02, T-A-05 |
| Rows covered | R-O-4, R-O-5, R-O-12 |

### Description

Every measure the report or the graduation gate reads is a named SQL view over the record, and nothing outside the governed record enters one, the true-grain recording rule of charter C5. This ticket creates the eighteen named views `06-observability.md`'s Measure computations table lists, narrowing T-A-05's `stage_reliability_view` to R-O-4's first-attempt rule rather than creating a second reliability view, and building the factory views isolating `baseline` tickets from real ones. `scripts/tools/report`, behind `factory report`, is the only reader: it windows every growth figure, keeps the primary panel unranked, and shows an unavailable measure's status and reason rather than inventing a number. It labels cost, tickets-closed-per-window, and non-structural touchpoints as context, unusable by a scorer, and states the `proposal` schema's absence at A rather than building it early. It depends on the record schema (T-A-02) and the run ledger (T-A-05).

### Scope

**In:** the eighteen named SQL views `06-observability.md`'s Measure computations table requires, one per measure row in table order: `v_revisions_per_ticket_by_fm`, `v_questions_per_ticket`, `v_default_shown_share`, `v_default_accepted_share`, `v_queue_latency_by_stage_tier`, `v_active_attention_by_stage_tier_outcome`, `v_generated_test_kept_share`, `v_plan_approved_no_redirect_share`, `v_production_incidents_attributable`, `v_reconstruction_share_by_gate`, `v_escalations_per_ticket`, `v_stale_index_entries_per_ticket`, T-A-05's `stage_reliability_view` narrowed here to the first-attempt rule, `v_ctx_completions_outcomes_per_window`, `v_ctx_cost_per_ticket`, `v_ctx_non_structural_touchpoints`, `v_ctx_fix_rounds_per_ticket`, `v_ctx_tool_calls_bytes_per_stage_run`; factory-performance views accepting a `manifest_hash` filter; dedicated baseline views over `baseline_measure`; `scripts/tools/report`; the `factory report` command; `factory/evals/scripts/tools/report/` (eval.yaml, fixtures); `runner/tests/test_views.py`; `runner/tests/test_report.py`.

**Out:** the frozen retrospective and supplemental baseline cohort itself (AB, R-O-6); the `proposal` table (Later, R-F-10); a graphical dashboard (Later, R-O-8).

### Acceptance criteria

1. A seeded `baseline = true` ticket is excluded from every factory-performance view, and a seeded ticket explicitly migrated to a new `factory_manifest_hash` is reported in both version cohorts with the migration boundary visible (R-O-4)
2. A factory-performance view accepts a `manifest_hash` filter using a seeded ticket's `factory_manifest_hash`, and a dedicated baseline view reads seeded `baseline_measure` rows without requiring a pre-factory manifest (R-O-4)
3. For each of the eighteen measures `06-observability.md`'s Measure computations table names as read by the Initial report or the graduation gate, revisions per ticket after plan approval by failure mode; questions surfaced per ticket by tier; share shown with a default; share where the default was accepted; queue latency at S2, S3 and S6 by tier; active attention at S3 and S6 by tier and outcome; share of generated tests kept after review; share of plans approved without redirect; production incidents attributable to factory changes and coverage status; share of S3 and S6 decisions needing reconstruction; escalations per ticket from S4; index entries found stale per ticket; share of stage runs passing on the first attempt by stage and tier; context cost per ticket by stage and tier; context factory completions and external outcomes per window; context non-structural touchpoints per ticket by tier; context fix rounds per ticket; and context tool calls and tool-result bytes per stage run, the named SQL view Scope In lists for that measure exists over the record (R-O-4)
4. T-A-05's `stage_reliability_view`, narrowed here to the first-attempt rule, excludes `blocked`, `refused`, and `aborted_human` runs, every child and utility run, and every `stage_run` whose `run_kind` is not `task`, counting only first-attempt outcomes `pass`, `fail`, `infrastructure_failure`, `sandbox_violation`, and `aborted_budget` (R-O-4)
5. The views over `question`, `queue_item`, `tag`, and `index_use` join to their ticket through `ticket_id` (R-O-4)
6. For each of: agent-attributed share of pull requests, estimated savings over human work, cost per pull request as distinct from cost per ticket, and any breakdown by person, no SQL view exists in the schema (R-O-5)
7. A requested measure with no available data shows a status and a reason on the report, never an invented number (R-O-5)
8. `scripts/tools/report`, run through `factory report`, is the only reader of the views, produces a text report on demand, gives every growth figure its window, and keeps the primary panel unranked (R-O-5)
9. The report places context measures in their own block labelled as context, separate from the primary panel (R-O-5)
10. `factory report`, run over the fixture ticket's completed walk, includes its measures and labels its context columns, matching A's exit test (R-O-5)
11. The report generator labels cost, tickets-closed-per-window, and non-structural touchpoints as context columns, distinct from the primary measures and rubric-line scores an improvement pass, grader, or benchmark may use (R-O-12)
12. The `proposal` table does not exist in the schema at A, since it is created only by the migration landing with R-F-10; R-O-12's schema-test clause for it is satisfied by that absence, not by an early stub table (R-O-12)
13. A seeded context measure, cost per ticket, presented on the report cannot be selected by a seeded objective-rule check as a primary measure or rubric-line score (R-O-12)

### Verification

`runner/tests/test_views.py`: criteria 1, 2, 3, 4, 5
`runner/tests/test_report.py`: criteria 6, 7, 8, 9, 10, 11, 12, 13
`factory/evals/scripts/tools/report/eval.yaml`, `factory/evals/scripts/tools/report/fixtures/`: criteria 8, 9, 10, 11, 12, 13

## T-A-12: Queue items, `factory queue` and `factory act`: item kinds, minimum context, latency, attention bucket, human tags on transitions

| | |
|---|---|
| Milestone | A |
| Blocks | 12 Queue item and decision |
| HLD components | H2, C1 |
| Depends on | T-A-04, T-A-09, T-A-11 |
| Rows covered | R-H-1, R-H-12 |

### Description

The queue is the only channel to a human (D17), so every Initial item kind lives in one table from the first commit. This ticket builds the nine Initial `queue_item` kinds with their minimum governed context, the `factory queue`, `factory act`, `factory abandon`, and `factory tag` commands as in-process functions, and the one-time resolution fields `resolved_at`, `resolved_by`, `action`, and `note`. It carries the `active_attention_bucket` required on every plan and packet approval record, including `unknown`, kept separate from queue latency, and proves the factory collects no keystroke, focus-event, or editor-telemetry signal, keeping the human a collaborator rather than a surveilled subject. A send-back, abandon, or override action writes the human-transition tag T-A-33 later completes. It depends on the state table (T-A-04), reviewer sets (T-A-09), and the report's views (T-A-11).

### Scope

**In:** `queue_item` kind enum and minimum-context display; this ticket's day-one `queue_item.kind`-to-`action` mapping, cited by R-H-1: `question` accepts answer and accept default; `eligibility` accepts decide eligibility, edit scrutiny, and override; `plan_approval` accepts approve, redirect, send back, and abandon; `packet_approval` accepts approve, request changes, and send back; `red_check` accepts send back and abandon; `escalation` accepts resume, send back, and abandon; `manual_pause` accepts resume, stop, and send back; `rubric_inspection` accepts close inspection; `pr_outcome` accepts none of these actions at A; `runner/queue.py` (`factory queue`, `factory act`, `factory abandon`, `factory tag` in-process functions, one-time resolution fields); `active_attention_bucket` on `approval_record` and `queue_item`; the human-transition tag write; `factory abandon` and `factory tag` commands in `runner/cli.py`; `runner/tests/test_queue.py`; `runner/tests/test_act.py`; `runner/tests/test_attention_bucket.py`; `runner/tests/fixtures/queue/`.

**Out:** the full tag catalogue and its kinds (T-A-33); the control-defect category enum and disposition path (T-A-29); the `pr_outcome` item's own actions (B).

### Acceptance criteria

1. For each of the nine Initial `queue_item` kinds, `question`, `eligibility`, `plan_approval`, `packet_approval`, `red_check`, `escalation`, `manual_pause`, `pr_outcome`, and `rubric_inspection`, a seeded row of that kind is accepted by the schema and displayed by `factory queue` (R-H-1)
2. `pr_outcome` queue items are excluded from the non-structural-touchpoints and active-attention measures, and queue latency is never labelled active attention (R-H-1)
3. `factory queue` over a seeded set of items across every Initial kind lists each with its ticket, stage, tier and `queued_at`, and a seeded `eligibility` item shows the exact trust profile, the satisfying approval set, the planned RACI roles, the ticket type and data class to confirm, and the scrutiny paragraph (R-H-1)
4. A seeded plan or packet decision with more than one required reviewer shows each reviewer's own `active_attention_bucket`, including a seeded `unknown` value, distinct from queue latency and the decision outcome (R-H-12)
5. No manifest entry or configuration file names a keystroke, focus-event, or editor-telemetry source for `active_attention_bucket` (R-H-12)
6. No runner code path derives `active_attention_bucket` from editor activity; every value is either human-entered or `unknown` (R-H-12)
7. `factory queue` and `factory act` are thin wrappers over in-process functions, and `factory act` records the decision on the named item and resumes the ticket only when the action permits it (R-H-1)
8. For each pairing of a `queue_item.kind` and its valid actions in this ticket's day-one mapping, `question` with answer or accept default, `eligibility` with decide eligibility, edit scrutiny, or override, `plan_approval` with approve, redirect, send back, or abandon, `packet_approval` with approve, request changes, or send back, `red_check` with send back or abandon, `escalation` with resume, send back, or abandon, `manual_pause` with resume, stop, or send back, and `rubric_inspection` with close inspection, a seeded `factory act` call with that action on that kind is accepted, and a seeded call with that action on a kind not in its list, `pr_outcome` among them, is refused (R-H-1)
9. A seeded `queue_item` is resolved once, setting `resolved_at`, `resolved_by`, `action`, and `note`, and a second `factory act` call against the same already-resolved item is refused (R-H-1)
10. Queue latency is computed as `resolved_at` minus `queued_at` per item (R-H-1)
11. Every plan and packet `approval_record`, including a redirect or reject decision, requires the acting human's `active_attention_bucket` from the six coarse values including `unknown`; a non-approval queue action may record one optionally (R-H-12)
12. A `send_back`, `abandon`, or `override` action from `factory act` writes one `tag` row on the ticket naming the transition, which T-A-33 later extends into the full catalogue (R-H-1)
13. `factory act` additionally accepts a control-event action recording an `incident_observation` row with actor and timestamp; its category enum and disposition path are completed by T-A-29 (R-H-1)
14. `factory abandon`, given a seeded ticket id in an open state, is a thin wrapper over an in-process function that records the ticket's `abandoned` tag and the `not_deployed` coverage record without a queued item (R-H-1)
15. `factory tag`, given a seeded ticket, run, decision, or artefact identifier and a chosen tag kind, is a thin wrapper over an in-process function that records one human tag row on the named target (R-H-1)

### Verification

`runner/tests/test_queue.py`: criteria 1, 2, 3
`runner/tests/test_act.py`: criteria 7, 8, 9, 10, 12, 13, 14, 15
`runner/tests/test_attention_bucket.py`: criteria 4, 5, 6, 11
`runner/tests/fixtures/queue/`: seeded queue-item fixtures across every Initial kind for criteria 1, 3

## T-A-13: Outbox with every intent kind and stub deliverers

| | |
|---|---|
| Milestone | A |
| Blocks | 24 External access |
| HLD components | C7 |
| Depends on | T-A-02, T-A-07, T-A-09, T-A-10, T-A-12 |
| Rows covered | R-T-11 |

### Description

Every external write to Jira, GitHub or Slack goes through one transactional outbox, so a crash or a race never produces two remote objects for one ticket action (R-T-11). The `external_write` table already exists from the record schema; this ticket builds the outbox worker and stub deliverers that hold remote state, branch head, pull-request identity and body hash for `pr_create`, `pr_update`, the digest and Jira feedback, under one idempotency-key rule. The last quorum-completing approval and the intent it authorises commit together, and reconciliation runs before every state-advancing command touches ticket state. This sits on the reviewer sets and quorum of T-A-09, the subject hashes of T-A-10, and the queue items of T-A-12, since an intent's key and its authorising guard decision depend on those mechanisms. The stub deliverers stand in for GitHub, Slack and Jira until AB adds real credentials and push authority.

### Scope

**In:** `runner/outbox.py` (intent creation, dispatch and reconciliation over the `external_write` table built at T-A-02); `runner/deliverers/stub.py` (stub deliverers holding remote state, branch head, pull-request identity and body hash, drivable to return an unexpected head, an existing object, or a duplicate key); the reconciliation call wired into every state-advancing entry point in `runner/cli.py`; `runner/tests/test_outbox.py`; `runner/tests/fixtures/outbox/`.

**Out:** the worker's pre-dispatch freshness recheck of target, branch and subject equality (T-A-14); S6's automatic dispatch of `pr_create`/`pr_update` after quorum and the packet/PR-body content it sends (T-A-31, T-A-34).

### Acceptance criteria

1. A seeded `external_write` row carries `id`, `ticket_id`, `stage_run_id`, `operation`, `idempotency_key`, a payload artefact id and digest, `guard_decision_id`, review-tuple and review-approval-subject/set hashes where applicable, a publication-target hash, repository/target/head refs, desired and expected prior remote head SHAs, a PR-body hash, a revision number, remote PR identity, `state`, an attempt count, remote identity and a governed receipt artefact, `last_error`, and timestamps (R-T-11)
2. For a `pr_create` or `pr_update` operation, a seeded `external_write` row's review-tuple and review-approval-subject/set hash fields are populated; for a `digest` or `jira_feedback` operation, those fields are null (R-T-11)
3. For each of `pr_create`, `pr_update`, `digest`, and `jira_feedback`, a seeded intent of that operation writes one `external_write` row under the same idempotency-key rule (R-T-11)
4. A seeded `pr_create` intent keyed by the review-approval subject hash, repository, target and head refs, desired head, and PR-body hash reconciles an existing branch and open pull request before creating either, and never overwrites an unexpected remote head (R-T-11)
5. A seeded `pr_update` intent keyed by pull-request identity plus the review-approval subject, destination, and desired/expected head and body-hash bindings requires the previously reconciled remote head, applies compare-and-set or force-with-lease semantics, and updates that same draft pull request's branch and body without opening a replacement (R-T-11)
6. The last quorum-completing `approval_record` and the `external_write` intent row it authorises commit in one transaction, so no state exists with the approval recorded and no intent row (R-T-11)
7. The stub deliverer in `runner/deliverers/stub.py` holds remote state, branch head, pull-request identity, and body hash across calls for one ticket (R-T-11)
8. For each of an unexpected remote head, an existing remote object, and a duplicate idempotency key, the stub deliverer can be driven to return it, and the worker reconciles without creating a second remote object (R-T-11)
9. Crash injection before send: a `pr_create` intent killed before the stub deliverer is called leaves one `external_write` row in `state = 'pending'`, and the retried command produces exactly one remote object (R-T-11)
10. Crash injection after remote success: a `pr_create` intent killed after the stub deliverer records success but before the receipt is stored reconciles on retry to the same remote object with no duplicate (R-T-11)
11. Crash injection before local commit: a `pr_create` intent killed after the stub deliverer returns a receipt but before the runner commits it reconciles by remote identity on retry to the same object (R-T-11)
12. Race on unexpected remote head: a `pr_update` intent driven against a stub deliverer returning a head other than the expected prior head is refused, and the `external_write` row moves to `state = 'failed'` without overwriting that head (R-T-11)
13. Race on same-key/different-payload: two `external_write` rows sharing one `idempotency_key` with different payload hashes are refused, so one key never carries a different payload (R-T-11)
14. Race across create/update: a `pr_update` intent dispatched against a stub deliverer already holding an open pull request from a driven `pr_create` reconciles to that existing object rather than creating a replacement (R-T-11)
15. Every state-advancing `factory` command reconciles pending `external_write` rows before it runs, exercised on a ticket seeded with a `pending` row (R-T-11)
16. A stale pending `external_write` intent becomes `state = 'superseded'` when a newer intent for the same ticket and operation is created (R-T-11)
17. An ambiguous `sending` `external_write` row must reconcile before another intent under the same key is created (R-T-11)
18. The `review` to `pr_opened` transition advances only from an `external_write` row with `state = 'reconciled'` whose remote head and payload hash match the desired values (R-T-11)
19. Every outbox payload and every stub deliverer receipt passes the guard, leaving one `guard_decision` row per dispatched intent (R-T-11)
20. On a ticket with full plan-and-review quorum, the outbox stub receives one `pr_create` intent, and on a ticket seeded at `pr_opened` with a recorded revision, a second approval produces one `pr_update` intent, each with a receipt (R-T-11)

### Verification

`runner/tests/test_outbox.py`: criteria 1-20.
`runner/tests/fixtures/outbox/`: seeded ticket, quorum, and stub-deliverer fixtures for criteria 2-20.

## T-A-14: Freshness at three boundaries and `refresh-base`

| | |
|---|---|
| Milestone | A |
| Blocks | 15 Binding; 25 Git trees |
| HLD components | C4, C8 |
| Depends on | T-A-08, T-A-10, T-A-13 |
| Rows covered | R-S5-12 |

### Description

Base freshness is blocking at three boundaries, so a moved target branch never lets a stale plan or a stale diff reach a pull request (R-S5-12). This ticket builds the trusted fetch-and-compare check the runner runs before S4 and at the plan-approval commit, again in S5 preflight with the exact candidate branch head and diff, and once more by the worker immediately before dispatch. It builds `factory refresh-base`, the human action that rebases the ticket branch onto the fetched head, records a new base and head or escalates a conflict without resolving it, and returns the ticket to `context`. It sits on the fixture project and git trees of T-A-08, the plan tuple of T-A-10, and the pre-dispatch boundary is checked by the worker T-A-13 built.

### Scope

**In:** `runner/freshness.py` (the three boundary checks against `ticket.base_sha`, `ticket.target_base_sha`, and `ticket.head_sha`); `runner/refresh_base.py` (the trusted rebase script); the `factory refresh-base` command wired in `runner/cli.py`; `runner/tests/test_freshness.py`; `runner/tests/fixtures/freshness/` (a fixture-project target-branch movement, a clean rebase, and a conflicting rebase).

**Out:** none.

### Acceptance criteria

1. For each of the three freshness boundaries, before S4 and at the plan-approval commit, S5 preflight, and immediately before PR dispatch, a movement of the fixture project's target branch is detected against the plan tuple's `base_sha` and recorded target head (R-S5-12)
2. At S5 preflight, the freshness check additionally requires the exact candidate branch head and diff to match what the plan tuple bound (R-S5-12)
3. `refresh_base` rebases a ticket branch that already carries S4 commits onto the newly fetched target head, preserving those commits as a dirty build (R-S5-12)
4. `refresh_base` records a new `base_sha` and `head_sha` when the rebase completes with no conflict (R-S5-12)
5. `refresh_base` run against a target movement that conflicts with the ticket branch escalates the conflict without resolving it (R-S5-12)
6. A boundary that detects target movement invalidates the evidence tuples bound to the stale base (R-S5-12)
7. `factory refresh-base` returns the ticket to `context` and requires new context, plan approval, S4 validation, and S5 before it can advance again (R-S5-12)
8. Immediately before PR dispatch, the worker repeats the target, branch, and subject equality check the earlier two boundaries ran (R-S5-12)

### Verification

`runner/tests/test_freshness.py`: criteria 1-8.
`runner/tests/fixtures/freshness/`: criteria 1, 3, 4, 5.

## T-A-15: Crash recovery: killed runs, expired leases, outbox-first restart, reasoning-summary cap

| | |
|---|---|
| Milestone | A |
| Blocks | 10 Run |
| HLD components | C3, C7 |
| Depends on | T-A-05, T-A-13 |
| Rows covered | R-O-1 |

### Description

Every ledger row is written as work proceeds, so a restart never reconstructs history and never fabricates a duplicate (R-O-1). This ticket builds the restart path over the lease and heartbeat T-A-05 gave `stage_run`: it expires only a run whose lease and process identity are both dead, records `infrastructure_failure` with `failure_kind = expired_lease`, preserves registered outputs and the worktree, and reconciles the outbox T-A-13 built before any state advance. A fresh attempt is then offered. Reasoning summaries are governed and length-limited from `tiers.yaml`, so an agent's self-report cannot grow without bound.

### Scope

**In:** the restart and lease-expiry check added to `runner/run_ledger.py` (built at T-A-05); the outbox-reconciliation call at the start of `factory advance` in `runner/cli.py`; `stage_run.failure_kind = 'expired_lease'`; the `tiers.yaml` reasoning-summary cap enforced on `stage_run.reasoning_summary`; `runner/tests/test_crash_recovery.py`; `runner/tests/fixtures/crash_recovery/`.

**Out:** the full stub walk exercising a kill at every stage of one continuous run from `intake` to `pr_opened` (T-A-17).

### Acceptance criteria

1. A `stage_run` process killed mid-execution and restarted via `factory advance` produces no duplicate `stage_run` row for that attempt (R-O-1)
2. A `stage_run` whose `lease_expires_at` has passed but whose process is still alive is not expired on restart (R-O-1)
3. A `stage_run` whose lease has expired and whose process identity is also dead is expired on restart and recorded as `infrastructure_failure` with `failure_kind = 'expired_lease'` (R-O-1)
4. Expiring a dead run preserves its registered `artefact` rows and the ticket's `worktree_path` unchanged (R-O-1)
5. Restart reconciles pending `external_write` rows before any ticket state advance runs, exercised on a ticket seeded with a `pending` intent and a killed run (R-O-1)
6. After expiring a dead lease and reconciling the outbox, `factory advance` offers a fresh attempt of the same stage with `attempt + 1` (R-O-1)
7. A reasoning summary over the `tiers.yaml` 200-word cap is stored as at most that cap in `stage_run.reasoning_summary` (R-O-1)
8. For each stage `S0` to `S6`, killing the run and rerunning the same `factory advance` command completes the walk with no duplicate `stage_run` row (R-O-1)

### Verification

`runner/tests/test_crash_recovery.py`: criteria 1-8.
`runner/tests/fixtures/crash_recovery/`: criteria 1, 3, 5, 8.

## T-A-16: Governed export, import and purge

| | |
|---|---|
| Milestone | A |
| Blocks | 17 Record |
| HLD components | C1, R2, C5 |
| Depends on | T-A-02, T-A-07, T-A-08, T-A-13 |
| Rows covered | R-T-4 |

### Description

The governed record is exportable as a single directory, so a hand-over never carries a credential or a raw disallowed payload (R-T-4). This ticket builds `factory export`, `factory import`, and `factory purge` as scripts under `factory/scripts/tools/`. Export requires an allowed route and a guard decision from the trust profile T-A-07 built, inherits classification and retention, records a content hash through T-A-02's `runner/canonical.py`, and excludes credentials and disallowed payloads. Import verifies that hash and refuses a malicious path. The export directory is also the eval fixture and hand-over the fixture project of T-A-08 and the outbox receipts of T-A-13 feed into.

### Scope

**In:** `factory/scripts/tools/export`, `factory/scripts/tools/import`, `factory/scripts/tools/purge`; the `export` artefact kind (a directory); the `factory export`, `factory import`, `factory purge` commands in `runner/cli.py`; `factory/evals/scripts/tools/export/`, `factory/evals/scripts/tools/import/`, `factory/evals/scripts/tools/purge/` (each with `eval.yaml` and `fixtures/`); `runner/tests/test_export_import.py`; `runner/tests/fixtures/export_import/`.

**Out:** none.

### Acceptance criteria

1. `factory export` on a ticket with permitted rows writes an `export` artefact directory containing ticket rows and artefacts, guard decisions, reviewer/approval/waiver sets, evidence tuples, incident observations, external-write receipts, and the branch as a patch against `base_sha` (R-T-4)
2. `factory export` proceeds and records one `guard_decision` row of `decision = 'allow'` only when `trust-profile.yaml` authorises the export/display route for that ticket's data class; an unauthorised route is refused (R-T-4)
3. Every row in the export directory carries the `data_class` and `redaction_state` it had in the record (R-T-4)
4. Every row in the export directory carries its `retention_until` value from the record (R-T-4)
5. `factory export` records a content hash on the export directory when it is created (R-T-4)
6. For each of a seeded credential value and a seeded raw disallowed payload, the value is absent from the export directory (R-T-4)
7. `factory import` verifies the export directory's recorded content hash before importing, and refuses an export whose content no longer matches that hash (R-T-4)
8. `factory import` rejects an export entry naming an absolute path (R-T-4)
9. `factory import` rejects an export entry containing a path-traversal segment (R-T-4)
10. `factory import` rejects an export entry whose symlink resolves outside the export directory (R-T-4)
11. `factory import` rejects a file present in the export directory but not declared in its manifest (R-T-4)
12. Prose content brought in by `factory import` is marked untrusted input in the imported record (R-T-4)
13. `factory purge` removes an export directory whose `retention_until` has passed and refuses to purge one still within retention (R-T-4)
14. Exporting a ticket with `factory export` and then running `factory import` into an empty record reproduces every hash from the original export (R-T-4)

### Verification

`runner/tests/test_export_import.py`: criteria 1-14.
`runner/tests/fixtures/export_import/`: criteria 1, 6, 7, 8, 9, 10, 11, 13, 14.
`factory/evals/scripts/tools/export/`: criterion 1.
`factory/evals/scripts/tools/import/`: criteria 7-12.
`factory/evals/scripts/tools/purge/`: criterion 13.

## T-A-17: Pause, resume, stop, status, and the stub walk from `intake` to `pr_opened`

| | |
|---|---|
| Milestone | A |
| Blocks | 18 Stage interface |
| HLD components | C1, C2 |
| Depends on | T-A-04, T-A-05, T-A-08, T-A-12, T-A-13, T-A-15 |
| Rows covered | R-I-8, R-H-13 |

### Description

Stop and pause are the only human interventions inside a running stage, and neither may inject steering text into a live model context (R-I-8). This ticket builds `factory pause`, `factory resume`, `factory stop`, and `factory show` over the durable pause flag `advance` checks before every recorded boundary (R-H-13). It closes phase 1 by assembling the stub walk: a synthetic ticket advances from `intake` to `pr_opened` through every stub stage `S0` to `S6`, exercising the state table of T-A-04, the leases of T-A-05, the queue of T-A-12, the outbox of T-A-13, and the crash recovery of T-A-15 together as one continuous run. This is the milestone's exit test for the stage interface: every stage and command in one call surface, proven end to end before any stage becomes real.

### Scope

**In:** `factory pause`, `factory resume`, `factory stop`, `factory show` in `runner/cli.py`; the durable pause-flag check in the `advance` boundary loop; `runner/tests/test_stage_interface.py`; `runner/tests/test_stub_walk.py`; `runner/tests/fixtures/stub_walk/`.

**Out:** every stage `S0` to `S6` running for real instead of as a stub (T-A-20 onward); the thin sandbox's registered-inputs-only guarantee during a real invocation (T-A-18); the manifest's full field set and fail-closed resolution (T-A-19).

### Acceptance criteria

1. `factory stop` terminates a running stage (R-I-8)
2. `factory stop` records `stage_run.outcome = 'aborted_human'` with the reasoning summary and the governed outputs registered so far (R-I-8)
3. `factory stop` moves the ticket to `escalated` (R-I-8)
4. A seeded stage run in progress refuses every command but `factory stop`: `factory pause`, `factory resume`, `factory run`, and `factory act` on that ticket's open item each return an error and the run continues unaffected, while `factory stop` alone terminates it (R-I-8)
5. Neither `factory stop` nor `factory pause` injects steering text into a live model context (R-I-8)
6. A `factory pause` request takes effect at the next stage or S4-attempt boundary rather than immediately (R-I-8, R-H-13)
7. `factory show` reports stage, attempt, elapsed wall clock, budget remaining, current registered outputs, and whether a pause is pending (R-H-13)
8. `advance` checks the durable `ticket.pause_requested` flag before starting each recorded boundary (R-H-13)
9. Given a ticket paused mid-stage with one registered output artefact, `factory show` lists that artefact's path or id among the run's currently registered outputs (R-H-13)
10. From any open queue item, plan approval, red check, packet approval, escalation, or manual pause, the human may send the ticket back with a `send_back` tag and note, with no routine approval added (R-H-13)
11. `factory resume` continues a paused ticket's stage from its held boundary (R-H-13)
12. A pause request arriving at the same moment as a boundary crossing resolves to pausing at the next boundary, never mid-invocation (R-H-13)
13. A synthetic ticket advances from `intake` to `pr_opened` through stub stages `S0` to `S6`, and every table the walk touches carries its rows (R-I-8, R-H-13)
14. A stage invoked from a state other than the one the transition table permits is refused and recorded during the stub walk (R-I-8, R-H-13)
15. A kill at each stage of the stub walk followed by the same `factory advance` command completes the walk with no duplicate `stage_run` row (R-I-8, R-H-13)
16. During the stub walk, a pause takes effect at the next boundary and a stop ends the open run as `aborted_human` (R-I-8, R-H-13)
17. During the stub walk, an in-place edit attempted on an append-only row is refused (R-I-8, R-H-13)
18. During the stub walk, a recipe given a shell string is refused (R-I-8, R-H-13)
19. The manifest hash validates before and after the stub walk with nothing under `factory/` changed (R-I-8, R-H-13)
20. Every content-bearing crossing of the stub walk leaves one `guard_decision` row (R-I-8, R-H-13)
21. During the stub walk, a crossing that bypasses the guard fails (R-I-8, R-H-13)

### Verification

`runner/tests/test_stage_interface.py`: criteria 1-12.
`runner/tests/test_stub_walk.py`: criteria 13-21.
`runner/tests/fixtures/stub_walk/`: criteria 13, 15, 19, 20.

## T-A-18: Cursor SDK adapter, invocation envelope, thin sandbox, tool-call rows

| | |
|---|---|
| Milestone | A |
| Blocks | 19 Invocation and runtime adapter; 20 Sandbox |
| HLD components | G1, G2, G3 |
| Depends on | T-A-05, T-A-07, T-A-08, T-A-17 |
| Rows covered | R-I-2, R-I-13, R-I-15 |

### Description

Each agent attempt is a fresh invocation that receives only the governed artefacts a manifest entry names, so an agent never carries a prior transcript or a user-level setting into a new attempt (R-I-2). This ticket builds `runner/adapters/cursor_sdk.py`, the first runtime adapter, which takes the complete envelope of R-I-15, starts the thin sandbox, invokes the requested model, and returns every available usage, cost, duration and outcome field alongside one governed `tool_call` row per call (R-I-13). The envelope itself is resolved by hash from the manifest and the record, so an audit can reconstruct what a stage saw without depending on which adapter ran. It sits on the run ledger of T-A-05, the guard of T-A-07, and the fixture-project worktree of T-A-08, and it completes the stub walk T-A-17 assembled by making a real invocation possible for the first time. The OS policy, the loopback proxy, and their enforcement are absent; the launcher-built allowlist environment is the only isolation this milestone builds. This ticket creates `factory/config/limits.yaml` for its tool-result inline limit; T-A-29 later adds that same file's fix-round cap entry.

### Scope

**In:** `runner/adapters/cursor_sdk.py`; `factory/config/limits.yaml`'s tool-result inline limit entry, created here for the first time (200 lines or 8 KB, whichever is reached first, with an excerpt of the first 40 and last 20 lines truncated to 4 KB at each end); `factory/config/pricing.yaml` (dated provider/model token prices and currency); `runner/launcher.py` (the thin sandbox: subprocess, launcher-built environment from `sandbox.yaml`'s allowlist, per-run directory with `out/` and `results/`); `factory/config/sandbox.yaml` and `factory/config/runtime.yaml` content; the pre-invocation requested-model check and post-invocation resolved-model check in `runner/adapters/cursor_sdk.py` against the phase-1 manifest's stub model field, whose dedicated fixtures land at T-A-19; `stage_run.replayability`, `stage_run.replayability_blind_spot`; `factory/evals/adapters/cursor_sdk/` (`eval.yaml` and `fixtures/`); `runner/tests/test_adapter.py`; `runner/tests/test_sandbox.py`; `runner/tests/fixtures/adapter/`.

**Out:** the manifest's full field set, fail-closed resolution for every stage-and-tier entry, and budget abort (T-A-19); real per-stage agent, skill and rubric content for `S1` to `S4` (T-A-21 onward); the OS policy, the copy-on-write copies, the loopback proxy, and the escape suite (absent at A).

### Acceptance criteria

1. Each agent attempt is invoked as a fresh invocation, receiving nothing from an earlier invocation's transcript (R-I-2)
2. The invocation receives the governed ticket artefacts named in the manifest for that stage, and their hashes (R-I-2)
3. The invocation receives the rubric file (R-I-2)
4. The invocation receives nothing from user-level runtime configuration (R-I-2)
5. A rerun after a blocking question, a failed S4 verification, or an escalation learns the round and full recorded history from registered artefacts alone (R-I-2)
6. The invocation envelope can be rebuilt from the governed record alone; reconstructable does not require the hosted model to return identical output on replay (R-I-2)
7. A child invocation, such as a restatement sub-run, records its own runtime, model, tokens, cost, and wall clock under `parent_run_id`, separate from its parent (R-I-2)
8. Settled fixture: an adapter contract test with a provider-settled result sets `stage_run.cost_basis = 'provider_settled'`, cost, currency, and `cost_settled_at` (R-I-13)
9. Runtime-estimate fixture: an adapter contract test with a runtime-reported non-settled estimate sets `cost_basis = 'runtime_estimate'` (R-I-13)
10. Price-table fixture: an adapter contract test whose only cost source is `pricing.yaml` sets `cost_basis = 'price_table_estimate'` and records `pricing_table_hash` (R-I-13)
11. Null fixture: an adapter contract test with no available cost data leaves the cost fields null and `cost_basis = 'unavailable'` (R-I-13)
12. Silent-fallback fixture: when the underlying runtime would substitute a different model without flagging it, the adapter still reports the model it actually used as `model_resolved`, never presenting the substitute as the requested model (R-I-13)
13. The adapter returns requested model, resolved model, exact runtime and adapter versions, every available usage, cost, duration and outcome field, and a reasoning summary (R-I-13)
14. The adapter records one governed `tool_call` row per call (R-I-13)
15. Missing runtime fields remain null and are never estimated for tokens, duration, or per-tool-call usage (R-I-13)
16. The record schema and stage behavior do not depend on which adapter ran, and an adapter upgrade must pass the `python3 -m runner.gate` adoption gate (R-I-13)
17. A tool result over the `limits.yaml` inline limit is stored as a `tool_call.result_artefact` with an excerpt rather than returned inline, and `tool_call.inline` reflects this (R-I-13)
18. Starting a stage run launches a subprocess whose environment is built only from `sandbox.yaml`'s allowlist (R-I-13)
19. The per-run directory has an `out/` subpath the sandbox writes and the runner registers from, and a `results/` subpath only the trusted runner writes (R-I-13)
20. An agent sandbox alone receives the scoped runtime key by role from `runtime.yaml`; a build sandbox receives no credential of any kind (R-I-13)
21. codegraph starts inside the sandbox as the agent's only local server (R-I-13)
22. Every run records a sandbox-integrity result, and a violation is recorded as `stage_run.outcome = 'sandbox_violation'` with `failure_kind = 'sandbox_integrity'` (R-I-13)
23. A run in the thin sandbox is given only its registered inputs and the worktree, an environment built from the allowlist, no ambient credential, and no push URL (R-I-13, R-I-15)
24. Export/reconstruct fixture: exporting a `stage_run`'s envelope and reconstructing it from the governed record alone reproduces every recorded hash and version identity (R-I-15)
25. Governance-binding fixture: the envelope binds guard decisions and the trust-profile and trust-approval-set hashes in force for that run; for an `S3`, `S5`, or `S6` `stage_run`, the envelope additionally binds the plan- or review-approval subject then in force; for an `S0`, `S1`, `S2`, or `S4` `stage_run`, the envelope carries no reviewer/approval subject (R-I-15)
26. Unavailable-provider-field fixture: when a provider exposes no immutable model build, or a tool result cannot lawfully be retained, `stage_run.replayability` is set to `'best_effort'` with `replayability_blind_spot` naming the gap, and it is never called exact replay (R-I-15)
27. A `stage_run`'s envelope records ordered input artefact ids and hashes, rubric/agent/skill hashes, the manifest hash, the recipe-set hash, exact adapter/runtime/tool/MCP-server versions, sandbox and toolchain digests, base and head SHAs, data class, tool allowlist, and the governed tool arguments and results used by the output (R-I-15)
28. The envelope records the provider request id where available (R-I-15)

### Verification

`runner/tests/test_adapter.py`: criteria 1-17, 24-28.
`runner/tests/test_sandbox.py`: criteria 18-23.
`runner/tests/fixtures/adapter/`: criteria 8-12, 24, 26.
`factory/evals/adapters/cursor_sdk/`: criteria 1, 13, 16.

## T-A-19: Manifest: full field set, fail-closed resolution, model checks, migration with re-approval, budget abort

| | |
|---|---|
| Milestone | A |
| Blocks | 4 Manifest; 10 Run |
| HLD components | F2, C1, C3 |
| Depends on | T-A-01, T-A-09, T-A-18 |
| Rows covered | R-I-4, R-I-6 |

### Description

The manifest names, per stage and tier, everything a run needs, with a `default` entry the pilot resolves against, so an unresolved or unavailable entry fails closed rather than silently substituting something else (R-I-4). This ticket fills the manifest's full field set on the tree T-A-01 committed, wires `factory migrate-manifest` for a human-approved change, and builds the fail-closed checks the adapter T-A-18 built already calls. It also builds budget abort: a stage run or an S4 execution that exceeds its `tiers.yaml` budget stops as `aborted_budget` and escalates, with a child run's usage counting against its parent (R-I-6). A changed budget is plan-bound and needs the same migration and re-approval T-A-09's quorum enforces.

### Scope

**In:** `factory/manifest.yaml` (full per-stage, per-tier entries with a `default`); `factory/config/tiers.yaml` budgets; `runner/manifest.py` (resolution, fail-closed checks, migration); the `factory migrate-manifest` command in `runner/cli.py`; `ticket.factory_manifest_hash` pinning at S0; `stage_run.outcome = 'aborted_budget'`; the `escalation` queue item's budget-abort content; `runner/tests/test_manifest.py`; `runner/tests/test_budgets.py`; `runner/tests/fixtures/manifest/`.

**Out:** real per-stage agent, skill and rubric entries for `S1` to `S4` beyond the `default` entry (T-A-21 onward, as each stage's real content is built).

### Acceptance criteria

1. `factory/manifest.yaml` names, per stage and tier, a `default` entry with agent, skill and any shared skills, rubric, tool allowlist, budget, runtime adapter and exact package version, approved requested model, grader model, sandbox policy, toolchain, and for S2 the restatement model (R-I-4)
2. Every file the manifest references is named by path plus content hash, and every referenced adapter or runtime version is an immutable version or digest (R-I-4)
3. Budgets are keyed only as `tokens` and `wall_clock_seconds`; a schema test rejects any other budget key (R-I-4)
4. For each of `S0`, `S5`, and `S6`, the manifest carries null agent, skill, and model fields (R-I-4)
5. A manifest entry missing a required field fails closed before the stage it names is invoked (R-I-4)
6. Unavailable-model fixture: an invocation whose requested model is absent from `runtime.yaml`'s list is refused before it starts, with no output registered (R-I-4)
7. Resolved-model-mismatch fixture: an invocation whose resolved model differs from the requested one after execution is recorded as `infrastructure_failure` with no output registered (R-I-4)
8. `ticket.factory_manifest_hash` is pinned at S0 eligibility, and every later stage run on that ticket must match it or fail closed (R-I-4)
9. Migration fixture: `factory migrate-manifest` on a human-approved change invalidates every artefact from S1 onward and returns the ticket to `context` (R-I-4)
10. `factory migrate-manifest` requires human approval through the quorum T-A-09 built before the migration takes effect (R-I-4)
11. A stage run that exceeds its `tiers.yaml` per-stage-and-tier token or wall-clock budget stops with `stage_run.outcome = 'aborted_budget'` and moves the ticket to `escalated` (R-I-6)
12. An S4 execution whose cumulative tokens or wall clock across all its task invocations exceeds the per-ticket S4 budget stops as `aborted_budget` and moves the ticket to `escalated` (R-I-6)
13. Wall clock is enforced live during a run, and settled tokens are checked at each invocation boundary (R-I-6)
14. Cumulative S4 budget totals are checked before every fresh S4 execution starts (R-I-6)
15. A child run's tokens and wall clock count against its parent's budget through `parent_run_id` (R-I-6)
16. The `escalation` queue item created on budget abort carries the reasoning summary, registered outputs, current binding if one exists, and failure history (R-I-6)
17. Budget abort does not consume S4's three-verification quota; the run ends without starting a new verification attempt (R-I-6)
18. Stopped work remains isolated in its worktree, and the escalation item names the last completed task, execution, and verification count (R-I-6)
19. Reapproval test: a changed S4 budget in `tiers.yaml` is plan-bound and requires `factory migrate-manifest` and re-approval before it takes effect (R-I-6)

### Verification

`runner/tests/test_manifest.py`: criteria 1-10.
`runner/tests/test_budgets.py`: criteria 11-19.
`runner/tests/fixtures/manifest/`: criteria 1, 4, 5, 6, 7, 9, 19.

## T-A-20: S0: lookups, provisional tier, sensitive paths, scrutiny template, eligibility item, exclusion gate

| | |
|---|---|
| Milestone | A |
| Blocks | 9 Ticket and its state; 12 Queue item and decision; 22 Check |
| HLD components | C6, C9, H2 |
| Depends on | T-A-09, T-A-12, T-A-17 |
| Rows covered | R-S0-2, R-S0-5, R-S0-6, R-S0-7, R-S0-8 |

### Description

S0 runs only scripts, with no agent, skill or model, so this ticket replaces the stub `runner/stages/S0.py` with the real driver. It builds R-S0-2's lookups over the section 8 matrices. R-S0-5 forces Heavy tier and a distinct reviewer slot on a sensitive-path match. R-S0-6's template-filled scrutiny paragraph holds a ticket at `intake` when empty. R-S0-7 gives the human the `eligibility` item T-A-12 lists, showing the trust profile and approval set T-A-09 derives. It fails closed on invalid authority, expiry, scope, or route. R-S0-8's whole exclusion matrix runs for real at S0. Its S1, S3, S4, and S5 clauses run on seeded `check_result` rows and fixture diffs, since no live S1 to S5 driver exists yet.

### Scope

**In:** `runner/stages/S0.py`; `runner/checks/exclusion.py`; `factory/config/service-tiers.yaml`; `factory/config/ticket-types.yaml`; `factory/config/sensitive-paths.yaml`; `ticket.service_tier`, `ticket.ticket_type`, `ticket.tier_provisional`, `ticket.tier_final`, `ticket.scrutiny_requested`, `ticket.tier_override_by`, `ticket.tier_override_at`, `ticket.tier_override_reason`; the `eligibility` item's `factory act` handling for approve, override and decline; `runner/tests/test_s0.py`; `runner/tests/test_exclusion.py`; `runner/tests/fixtures/s0/`; `runner/tests/fixtures/exclusion/`.

**Out:** the real S1 final-tier computation over touched files, services and unknowns (T-A-22); the real S3 plan and its planned reviewer-set derivation bound into the plan tuple (T-A-27); the real S5 preflight driver's actual-diff exclusion proof (T-A-30).

### Acceptance criteria

1. For each of the 15 `service_tier`/`ticket_type` cells of the section 8 provisional-tier matrix, a seeded ticket with that pair gets the matching `ticket.tier_provisional`: T1 bug, small_feature, feature, and refactor plus T2 feature are `Heavy`; T1 config_or_docs, T2 bug, small_feature, and refactor, and T3 feature and refactor are `Standard`; T2 config_or_docs and T3 bug, small_feature, and config_or_docs are `Light` (R-S0-2).
2. For each of a service absent from `service-tiers.yaml` and a Jira issue type of `Epic`, the S0 lookup script fails, the absent-service case with the literal reason `service not tiered` (R-S0-2).
3. Given a seeded candidate path under the fixture project's `authentication` glob in `sensitive-paths.yaml`, the sensitivity-match script flags the ticket a sensitive-path candidate and raises `ticket.tier_final` to at least Heavy (R-S0-5).
4. Given a seeded S5 actual-diff fixture touching a path under the `payments` glob in `sensitive-paths.yaml`, the sensitivity-match script marks the match authoritative and confirms Heavy tier (R-S0-5).
5. A ticket with a confirmed sensitive-path match is excluded at Initial under R-S0-8 with `close_reason = pilot_excluded`, rather than proceeding with an added reviewer slot (R-S0-5).
6. Given a seeded ticket whose engineer identity equals `sensitive-paths.yaml`'s configured owner for the matched path, the planned `reviewer_set`'s path-owner slot's `distinct_from` constraint rejects that identity (R-S0-5).
7. Given a ticket with `ticket_type = small_feature`, `tier_provisional = Standard`, and no sensitive-path match, the S0 template-fill script writes a non-empty `ticket.scrutiny_requested` naming the ticket type, tier and match state (R-S0-6).
8. A ticket for which the template-fill script produces an empty `scrutiny_requested` string remains in `intake` with no `eligibility` queue item queued (R-S0-6).
9. Given a seeded `eligibility` item showing the ticket's exact `trust_profile_hash`, the satisfying security/legal approval set, and the planned RACI roles, a `factory act` decision with `action = approve` moves the ticket from `intake` to `context` (R-S0-7).
10. For each of an expired, an unauthorised, a wrong-source-scope, and an invalid-route governance state, an `act` on the `eligibility` item is refused and the ticket remains in `intake` (R-S0-7).
11. Given a human with the `ticket engineer` role recorded in `config/owners.yaml` decides eligibility, `queue_item.resolved_by` records that identity and role (R-S0-7).
12. A human `act` on the `eligibility` item with `action = override` and a new `tier_final` writes `ticket.tier_override_by`, `tier_override_at`, `tier_override_reason` and an `override` tag (R-S0-7).
13. An `act` on the `eligibility` item attempting to override an R-S0-8 Initial exclusion is refused with no state change (R-S0-7).
14. A seeded ticket with `service_tier = T2`, written in Java, `ticket_type = small_feature`, exactly one repository and one target service passes the S0 eligibility matrix (R-S0-8).
15. For each of a sensitive-path match, authentication or permission behavior, payments or secrets, schema or data migration, infrastructure, regulated or disallowed data, a new or changed public API, event, or serialized-data contract, and a plan depending on unavailable production facts, S0 rejects the ticket mechanically with `close_reason = pilot_excluded` (R-S0-8).
16. On a seeded `check_result` row recording an S1-stage discovery of an excluded surface, the ticket moves to `rejected` with `close_reason = pilot_excluded` (R-S0-8).
17. On a seeded `check_result` row recording an S3-stage discovery of an excluded surface, the ticket moves to `rejected` with `close_reason = pilot_excluded` (R-S0-8).
18. On a seeded `check_result` row recording an S5 proof that the required change needs an excluded surface, the ticket moves to `rejected` with `close_reason = pilot_excluded` (R-S0-8).
19. Given a seeded fixture diff with an accidental excluded path not required by the plan, the exclusion gate returns the ticket from `checks` to `implementing` for removal instead of closing `pilot_excluded` (R-S0-8).
20. An attempted tier-override action on a ticket subject to an R-S0-8 exclusion is refused, since widening eligibility needs the R-O-13 graduation decision (R-S0-8).

### Verification

`runner/tests/test_s0.py`: criteria 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13.
`runner/tests/test_exclusion.py`: criteria 5, 14, 15, 16, 17, 18, 19, 20.
`runner/tests/fixtures/s0/`: seeded matrix, template and eligibility fixtures for criteria 1, 2, 7, 8, 9, 10, 11, 12, 13.
`runner/tests/fixtures/exclusion/`: seeded `check_result` and fixture-diff cases for criteria 14 through 20.

## T-A-21: Context index entries, staleness and index-use rows; agent definitions and skills capped

| | |
|---|---|
| Milestone | A |
| Blocks | 5 Context index; 1 Agent definition; 2 Skill |
| HLD components | F5, F3 |
| Depends on | T-A-01, T-A-18 |
| Rows covered | R-F-6, R-S1-7, R-F-7 |

### Description

This ticket writes the real context index and the real agent and skill files, replacing the eval-directory stubs T-A-01 created. R-F-6 fixes every `factory/index/*.md` entry's front matter and its at-read-time staleness rule, with no `last_verified` counting as stale. R-S1-7 records every entry a stage reads in `index_use` with its last-verified date, tags a stale read `stale_index` with FM-17, and allows an empty index. R-F-7 caps `factory/agents/S1.md` through `S4.md`, `factory/skills/S1.md` through `S4.md`, and the one shared skill at A, `factory/skills/shared/codegraph-lookup.md`, at the section 8 line limit. Each file attaches to a stage only through T-A-18's manifest entry, the shared skill to S1, S3 and S4.

### Scope

**In:** `factory/index/*.md`, its three hand-written entries being the fixture project's conventions, its sensitive paths, and one `caller` entry for its T1 consumer; `index_use` table and its write path; `tag.event_kind = 'stale_index'`; `factory/agents/S1.md` .. `S4.md`; `factory/skills/S1.md` .. `S4.md`; `factory/skills/shared/codegraph-lookup.md`; `runner/tests/test_context_index.py`; `runner/tests/test_agent_skill_files.py`; `factory/evals/agents/S1/` .. `S4/`, with real content replacing the stub fixtures; `factory/evals/skills/S1/` .. `S4/`; `factory/evals/skills/shared/codegraph-lookup/`.

**Out:** `scripts/tools/reindex` run before each real S1 invocation (T-A-22); the brief's "index entries used and stale" section content (T-A-22).

### Acceptance criteria

1. Given the fixture project's `conventions` context-index entry, its front matter carries `kind`, `source`, `owner`, `last_verified`, `staleness_rule`, `paths` (R-F-6).
2. Given a context-index entry more than 90 days past its `last_verified`, or with a base-branch commit since then touching its `paths`, the staleness rule marks it stale at read time (R-F-6).
3. A context-index entry with no `last_verified` is marked stale (R-F-6).
4. The context index carries exactly three hand-written entries at A: the fixture project's conventions, its sensitive paths, and one `caller` entry for its one T1 consumer (R-F-6).
5. Given a stage run that reads `factory/index/conventions.md`, an `index_use` row is written with that `stage_run_id`, `entry_path`, and `entry_last_verified` (R-S1-7).
6. A context-index entry read past its staleness rule is listed as stale in the reading stage's output (R-S1-7).
7. A stage run that reads a stale context-index entry writes a `tag` row with `event_kind = stale_index` and `fm_id = FM-17` (R-S1-7).
8. An empty `factory/index/` directory is permitted and a reading stage records "no entries" rather than failing (R-S1-7).
9. Each of `factory/agents/S1.md` through `S4.md` and `factory/skills/S1.md` through `S4.md` is under the section 8 instruction-file limit of 300 lines (R-F-7).
10. The shared skill file `factory/skills/shared/codegraph-lookup.md` is under the same 300-line limit (R-F-7).
11. The shared skill file `factory/skills/shared/codegraph-lookup.md` is attached to S1, S3, and S4 only through each stage's manifest entry, never by path convention alone (R-F-7).
12. The manifest test walking `factory/evals/agents/S1/` .. `S4/`, `factory/evals/skills/S1/` .. `S4/`, and `factory/evals/skills/shared/codegraph-lookup/` fails an empty or unowned eval directory (R-F-7).
13. No path-scoped agent or skill file exists at A, since R-F-7's path-scoped clause has no subject before Later (R-F-7).

### Verification

`runner/tests/test_context_index.py`: criteria 1, 2, 3, 4, 5, 6, 7, 8.
`runner/tests/test_agent_skill_files.py`: criteria 9, 10, 11, 12, 13.
`factory/evals/agents/S1/fixtures/` .. `S4/fixtures/`: real agent-file fixtures for criteria 9, 12.
`factory/evals/skills/S1/fixtures/` .. `S4/fixtures/`: real skill-file fixtures for criteria 9, 12.
`factory/evals/skills/shared/codegraph-lookup/fixtures/`: shared-skill fixture for criteria 10, 11, 12.

## T-A-22: S1: brief rubric, impact evidence, final tier, impact-derived tiering

| | |
|---|---|
| Milestone | A |
| Blocks | 3 Rubric; 9 Ticket and its state |
| HLD components | C6, F4, C9 |
| Depends on | T-A-08, T-A-18, T-A-20, T-A-21 |
| Rows covered | R-S1-2, R-S1-3, R-S1-6, R-S1-8, R-S1-11 |

### Description

This ticket replaces the stub `runner/stages/S1.py` with the real driver, running the S1 agent over the fixture project through T-A-18's adapter. It uses the agent and skill files T-A-21 capped. R-S1-2 keeps the brief's ticket summary fact-only and under the word limit. R-S1-3 makes impact evidence, not a completeness claim, recording direction, method, source, and coverage per dependency. Callers are read as T-A-21's context-index entries. R-S1-6 forbids asserting production facts and inventories flags from code references only. R-S1-8 computes the final tier from files, services, and unknowns touched, never lower than the provisional tier T-A-20 set. R-S1-11 derives impact-based tiering from the highest known criticality among affected services, with an unknown-impact flag, and triggers R-S0-8 on Initial multi-service discovery.

### Scope

**In:** `runner/stages/S1.py`; `factory/rubrics/S1.md`, real content generated by `rubric_gen` replacing the stub; the `brief` artefact's fixed sections, being ticket summary, linked sources, touched area candidates, history, impact evidence by direction, flags, blind spots, unknowns, index entries used and stale, final tier, pilot-exclusion recheck, and blockers; `ticket.tier_final`; the read of `factory/config/artifact-to-service.yaml` and `scripts/checks/impact_scan` seeded at T-A-08; the `scripts/tools/reindex` call before each S1 run; `runner/tests/test_s1.py`; `factory/evals/agents/S1/fixtures/`, extended; `factory/evals/skills/S1/fixtures/`, extended; `factory/evals/rubrics/S1/` with `eval.yaml` and fixtures.

**Out:** the question and assumption mechanics of S2 (T-A-23); the criteria rubric and S2 exit gate (T-A-24); the `human_verdict` routing over these lines, a fail verdict sending the ticket back (T-A-27).

### Acceptance criteria

1. The brief's ticket summary is under the section 8 word limit of 300 words (R-S1-2).
2. The generated `rubrics/S1.md` line for R-S1-2 marks its grader half as a bootstrap-checklist line whose judgment reads: fail when a ticket summary states a recommendation or an approach instead of facts alone (R-S1-2).
3. Given an HTTP-dependency fixture, the brief's impact evidence records direction, method, source commit/date, mapping used, owner, and coverage `authoritative`, `partial`, or `unknown` (R-S1-3).
4. Given a messaging-dependency fixture, the same impact-evidence fields are recorded with method-specific blind spots (R-S1-3).
5. Given a config-dependency fixture, the same impact-evidence fields are recorded with method-specific blind spots (R-S1-3).
6. Given a stale context-index `caller` entry fixture, the brief marks inbound callers unknown rather than asserting them (R-S1-3).
7. Given an unmapped-package fixture, `impact_scan`'s Maven or Gradle output maps to a service only through `artifact-to-service.yaml`, else the row is `unknown` (R-S1-3).
8. Given an authoritative build-graph fixture, the outbound dependency's coverage is recorded `authoritative` (R-S1-3).
9. A seeded `unknown` impact-evidence row that changes eligibility or names a new or changed public contract triggers R-S0-8's exclusion gate instead of proceeding to S3 unresolved (R-S1-3).
10. The generated `rubrics/S1.md` line for R-S1-3 marks its grader half as a bootstrap-checklist line whose judgment reads: fail when the plan names an owner other than the one the brief's impact evidence names (R-S1-3).
11. The brief's flags section inventories flags in the touched path from code references only, never from asserted production state (R-S1-6).
12. Live production state, SLIs, error budget, and logs appear only in the brief's blind spots section, each with what the plan will assume about it (R-S1-6).
13. The generated `rubrics/S1.md` line for R-S1-6 marks its grader half as a bootstrap-checklist line whose judgment reads: fail when a brief asserts a live production fact, such as an SLI or an error-budget value, outside the blind spots section (R-S1-6).
14. Given a ticket touching two or more services, more than 10 files, or three or more unknowns, `ticket.tier_final` is raised one level above `tier_provisional`, and never lowered (R-S1-8).
15. Given a T2 target service with a T1 consumer, impact-derived tiering sets `tier_final` from the highest known criticality among target and impacted services (R-S1-11).
16. Given an unknown consumer set, impact-derived tiering sets an explicit unknown-impact flag rather than relying on a partial-scan count (R-S1-11).
17. Given the brief's impact evidence discovering another service or repository, the ticket triggers R-S0-8's exclusion, since Initial eligibility is exactly one repository and target service (R-S1-11).
18. The generated `rubrics/S1.md` line for R-S1-11 marks its grader half as a bootstrap-checklist line whose judgment reads: fail when the plan's contracts table does not restate the brief's impact evidence and blind spots by name (R-S1-11).

### Verification

`runner/tests/test_s1.py`: criteria 1, 2, 10, 11, 12, 13, 14, 15, 16, 17, 18.
`factory/evals/agents/S1/fixtures/`: HTTP, messaging, config, stale-catalogue, unmapped-package, authoritative-build-graph, and eligibility-triggering-unknown fixtures for criteria 3, 4, 5, 6, 7, 8, 9.
`factory/evals/rubrics/S1/fixtures/`: fact-only-summary fixture for criterion 1; seeded `human_verdict` fixtures for the R-S1-2, R-S1-3, R-S1-6, and R-S1-11 grader lines for criteria 2, 10, 13, 18.

## T-A-23: S2: question gate, format, ranking, flags, rounds, wording, assumption log

| | |
|---|---|
| Milestone | A |
| Blocks | 13 Question and assumption log |
| HLD components | H3, C6 |
| Depends on | T-A-12, T-A-18, T-A-22 |
| Rows covered | R-S2-5, R-S2-6, R-S2-7, R-S2-8, R-S2-9, R-S2-11, R-S2-14 |

### Description

This ticket gives the stub `runner/stages/S2.py` its question and assumption half, sitting on T-A-22's S1 driver and T-A-12's queue items. R-S2-5's pre-queue gate emits a question only when the agent lists sources tried and names what the answer changes. R-S2-6 ranks questions by impact times decision uncertainty, storing the inputs in `rank_inputs` even when a question has no default. R-S2-7 validates two-to-four options with a default, unless R-S2-8's `consequential` and `hard_to_reverse` are both true or a sensitive decision applies. A human may correct either flag. R-S2-9 names a follow-up question by its raising answer and gates a new round on the prior round's blocking questions. R-S2-14 bans requirement, principle, decision, stage, artefact, script, and table identifiers from question text. R-S2-11 writes the append-only `assumption` log on an accepted default or an S3-accepted assumption, with supersession invalidating every dependent artefact and approval.

### Scope

**In:** `runner/stages/S2.py`, its question and assumption half only, since the criteria half and exit gate are T-A-24; `question`, `answer`, `assumption` tables and their write paths; `runner/checks/question_gate.py`, the format and identifier validator; `runner/tests/test_s2_questions.py`; `factory/evals/agents/S2/fixtures/`, question-path fixtures.

**Out:** the criteria rubric, restatement child runs and S2 exit gate (T-A-24); the grader-verdict recording for the search-adequacy and readability judgments below, through the bootstrap checklist (T-A-27).

### Acceptance criteria

1. Given a candidate question, the gate requires a non-empty `question.reasoning` naming sources tried and a non-empty `question.affects` naming the eligibility condition, brief fact, criterion, plan item, or human decision it changes, rejecting a question missing either (R-S2-5).
2. The generated `rubrics/S2.md` line for R-S2-5 marks its grader half as a bootstrap-checklist line whose judgment reads: fail when a question's `reasoning` names a source that never mentions the fact the question asks about (R-S2-5).
3. Given a ranked question, `question.rank_inputs` stores the impact and decision-uncertainty estimates used to compute `question.rank` (R-S2-6).
4. Given a question with `default_option = null`, the ranking script still computes and stores its `rank` and `rank_inputs` (R-S2-6).
5. For each of the four `consequential`/`hard_to_reverse` combinations, a question's `default_option` is required except when both are true or D15's sensitive-decision rule applies, when it must be null (R-S2-7).
6. A candidate question missing `reasoning`, with fewer than two or more than four `options`, or without a "none of these" option, is rejected before queueing (R-S2-7).
7. Given a seeded question whose answer changes a declared contract, migration, permission boundary, public interface, rollout strategy, or sensitive path, `question.consequential` is set true (R-S2-8).
8. Given a seeded question whose answer cannot cheaply restore prior data, interface, authorization, or customer-visible state, `question.hard_to_reverse` is set true (R-S2-8).
9. A sensitive security or data decision sets `question.consequential = true` regardless of `hard_to_reverse` (R-S2-8).
10. A human correcting either `question.consequential` or `question.hard_to_reverse` writes a recorded reason for the change (R-S2-8).
11. A follow-up question's `raised_by_answer` names the answer id that raised it (R-S2-9).
12. A new question round is queued only after every blocking question of the previous round is resolved, with `question.round` read from the record (R-S2-9).
13. Given an `answer.resolution_kind = 'default_accepted'`, an `assumption` row is written naming its question (R-S2-11).
14. Given an S3 reviewer accepting a proposed assumption for an open non-blocking question, `question.state = 'assumption_accepted'` and an `assumption` row is written naming that question (R-S2-11).
15. Replacing or withdrawing an `assumption` row appends a superseding row, creates a new assumption-log version, and invalidates every dependent artefact and approval (R-S2-11).
16. A question or option text containing a requirement, principle, failure-mode, or decision id, a stage code, or an artefact, script, or table name is rejected back to the agent, except a name from the service's own code (R-S2-14).
17. Every option, including the default, carries a one-sentence consequence, with the default's consequence stating what happens if nobody answers (R-S2-14).
18. The generated `rubrics/S2.md` line for R-S2-14 marks its grader half as a bootstrap-checklist line whose judgment reads: fail when a reader with no access to the referenced artefact cannot give the right answer to the question (R-S2-14).
19. On the fixture ticket's S2 walk, one question round is raised, ranked, and answered, and one default is accepted into the assumption log, matching A's exit test (R-S2-6, R-S2-11).

### Verification

`runner/tests/test_s2_questions.py`: criteria 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19.
`factory/evals/agents/S2/fixtures/`: seeded question, ranking, and assumption fixtures for criteria 1, 3 through 17, 19.
`factory/evals/rubrics/S2/fixtures/`: seeded `human_verdict` fixtures for the R-S2-5 and R-S2-14 grader lines for criteria 2, 18.

## T-A-24: S2: criteria rubric, forced categories, split patterns, restatement child runs, exit gate

| | |
|---|---|
| Milestone | A |
| Blocks | 3 Rubric; 10 Run; 9 Ticket and its state |
| HLD components | C6, F4 |
| Depends on | T-A-19, T-A-23 |
| Rows covered | R-S2-1, R-S2-2, R-S2-3, R-S2-4, R-S2-10, R-S2-12 |

### Description

This ticket completes `runner/stages/S2.py` with the criteria half, sitting beside T-A-23's question mechanics. It adds restatement, the agreement check, the forced-category and split checklists, and the S2 exit gate. R-S2-1 restates every acceptance criterion in EARS form with a stable `AC-n` id; R-S2-2 requires a concrete example per criterion. R-S2-3's agreement check restates each criterion in `N` fresh child `stage_run` contexts under the S2 run, on the manifest's restatement model. Disagreement, contradiction, or an uncovered input region raises a question. R-S2-4 runs the forced-category checklist over eight categories, pre-filling a category R-S0-8 already closed. R-S2-10 proposes a split as a consequential question when the criteria are not one vertical slice or the size estimate exceeds the tier's threshold. R-S2-12 holds `clarifying` on an open blocking question and gates the S2 exit on every criterion formalised, every category resolved, and no blocking question open.

### Scope

**In:** `runner/stages/S2.py`, its criteria half and S2 exit gate; `factory/rubrics/S2.md`, real content replacing the stub; `factory/rubrics/checklists/forced-categories.md`; `factory/rubrics/checklists/split-patterns.md`; the `criteria` artefact and its `AC-n` id scheme; a criteria-kind structural check built as scope for the S2 exit gate, later generalised into the R-I-12 structure check T-A-25 builds; `runner/tests/test_s2_criteria.py`; `factory/evals/rubrics/S2/` with `eval.yaml` and fixtures; `factory/evals/agents/S2/fixtures/`, extended for restatement and split fixtures.

**Out:** the plan artefact's own structure check and the general R-I-12 script (T-A-25); the bootstrap-checklist recording of this ticket's grader halves (T-A-27).

### Acceptance criteria

1. Every acceptance criterion restated by S2 carries an EARS form: optional precondition, optional trigger, the system, and the response (R-S2-1).
2. Each restated criterion carries an `AC-n` id assigned in restatement order, which a later criteria version keeps and never reuses (R-S2-1).
3. A criterion that cannot be restated is marked `unformalisable` and becomes a `question` (R-S2-1).
4. The generated `rubrics/S2.md` line for R-S2-1 marks its grader half as a bootstrap-checklist line whose judgment reads: fail when a restated `AC-n` criterion changes the meaning of its source acceptance criterion (R-S2-1).
5. Every acceptance criterion carries at least one Given/When/Then example with real values, not placeholders (R-S2-2).
6. The generated `rubrics/S2.md` line for R-S2-2 marks its grader half as a bootstrap-checklist line whose judgment reads: fail when a Given/When/Then example states no real values, only generic placeholders (R-S2-2).
7. A seeded ambiguous criterion, restated independently in 3 fresh child `stage_run` contexts under the S2 run's `parent_run_id`, disagreeing on precondition, trigger, or response, raises a `question` (R-S2-3).
8. A seeded contradictory pair of criteria raises a `question` (R-S2-3).
9. A seeded input region no criterion covers raises a `question` (R-S2-3).
10. Each criterion's agreement check writes exactly 3 child `stage_run` rows on the manifest's S2 restatement model, counted in the S2 budget and excluded from the first-attempt measure (R-S2-3).
11. The forced-category checklist `rubrics/checklists/forced-categories.md` runs against the criteria over error paths, concurrency, migration, backward compatibility, permissions, observability, rollback, and data retention (R-S2-4).
12. Each category resolves to `covered by criterion n`, `not applicable because`, or `open`, with no category left silent (R-S2-4).
13. Given a ticket whose R-S0-8 exclusion record already closes migration or permissions, that category is pre-filled `not applicable because` naming the S0 record and is not re-evaluated (R-S2-4).
14. An `open` category becomes a ranked `question` (R-S2-4).
15. Given a seeded ticket whose criteria's size estimate exceeds 60 percent of the tier's size gate as estimated lines, or exceeds 10 files, the agent proposes a split as a consequential `question` using `rubrics/checklists/split-patterns.md` (R-S2-10).
16. The proposed split names one of workflow steps, business-rule variations, data variations, interface variations, defer performance, or simple-then-complex (R-S2-10).
17. The generated `rubrics/S2.md` line for R-S2-10 marks its grader half as a bootstrap-checklist line whose judgment reads: fail when criteria describe no single vertical slice with observable value (R-S2-10).
18. Given a run that raises a blocking `question`, the run completes every criterion, category, and question not depending on the answer, then ends `stage_run.outcome = 'blocked'`, holding the ticket in `clarifying` (R-S2-12).
19. S2 exits to `planning` only when every criterion is formalised or its `unformalisable` question answered, every category is resolved, the criteria artefact passes its structure check, and no blocking question is open (R-S2-12).
20. Given every remaining question answered or its assumption explicitly accepted by the S3 reviewer, S3 approval proceeds on that basis; otherwise it is refused (R-S2-12).
21. A later answer contradicting an accepted assumption invalidates the S3 plan and every dependent downstream artefact (R-S2-12).

### Verification

`runner/tests/test_s2_criteria.py`: criteria 1, 2, 3, 4, 5, 6, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21.
`factory/evals/agents/S2/fixtures/`: restatement-agreement fixtures for an ambiguous criterion, a contradictory pair, and an uncovered region, exercising criteria 7, 8, 9, 10.
`factory/evals/rubrics/S2/fixtures/`: EARS-form and example fixtures for criteria 1, 2, 5; seeded `human_verdict` fixtures for the R-S2-1, R-S2-2, and R-S2-10 grader lines for criteria 4, 6, 17.

## T-A-25: S3: plan artefact, fixed tables, ceilings, traceability, structure check, size gate, readiness table

| | |
|---|---|
| Milestone | A |
| Blocks | 11 Artefact; 22 Check |
| HLD components | R2, C9, C6 |
| Depends on | T-A-08, T-A-24 |
| Rows covered | R-I-12, R-S3-12, R-S3-14, R-S3-18, R-S3-19, R-S3-21 |

### Description

This ticket replaces the stub `runner/stages/S3.py` with the real driver order. The `risk_map` script runs before the agent invocation, and the plan artefact is then structure-checked. `handoff_ready` writes the readiness table, and `size_gate` runs over the plan's size table before `plan_approval` is queued. R-I-12 generalises the structural check T-A-24 scoped for criteria into one script covering every artefact kind's fixed sections and every plan table's fixed columns. R-S3-14 keeps the plan judgeable in one sitting under the tier's length and row ceilings. R-S3-18 restricts every plan table to typed R-I-16 recipe ids, never free-form commands. R-S3-19 checks `AC-n` traceability both ways between the tasks and test-strategy tables. R-S3-12's size gate runs at S3 over the plan's size table, and again over a seeded fixture diff standing in for T-A-30's S5 call.

### Scope

**In:** `runner/stages/S3.py`; `runner/checks/artefact_structure.py`, the general R-I-12 structure and R-S3-19 traceability check that supersedes T-A-24's scoped criteria-only check; `factory/scripts/checks/size_gate`; `factory/scripts/checks/risk_map`, built here as the script T-A-26 later tests the computation of; `factory/scripts/tools/handoff_ready`; the `plan` artefact and its Readiness, Scope, Dependencies, Contracts, Tasks, Test strategy, and Size tables; `factory/config/project.yaml`'s generated-path and lockfile exclusions; `runner/tests/test_s3_structure.py`; `runner/tests/test_size_gate.py`; `factory/evals/scripts/checks/size_gate/` with `eval.yaml` and fixtures; `factory/evals/scripts/checks/risk_map/` with `eval.yaml` and fixtures; `factory/evals/scripts/tools/handoff_ready/` with `eval.yaml` and fixtures.

**Out:** the S3 rubric lines and the risk map's computed content (T-A-26); the bootstrap checklist, human verdicts, plan tuple and approval (T-A-27); the real S5 wiring of `size_gate` into the ordered check list (T-A-30); the packet artefact's real fixed-section content (T-A-31).

### Acceptance criteria

1. For each of `brief`, `criteria`, and `plan`, the structure-check script rejects a version missing its fixed Produces section list (R-I-12).
2. Given a stipulated placeholder Produces section list for the `packet` artefact kind, explicitly noted as a placeholder and not the packet's real S6 content, the structure-check script rejects a packet fixture missing a listed section (R-I-12).
3. For each of the plan's Readiness, Scope, Dependencies, Contracts, Tasks, Test strategy, and Size tables, the structure-check script rejects a version missing that table's exact section 8 columns (R-I-12).
4. A section marked `pending answer` from a run that ended `blocked` is exempt from the structure check until the fresh rerun (R-I-12).
5. Given a plan's size table with estimated changed lines over the tier threshold and no split proposal or justification, the `size_gate` script fails at S3 (R-S3-12).
6. Given a plan's size table with estimated changed lines over the tier threshold and a justification approved with the plan, the `size_gate` script passes at S3 (R-S3-12).
7. Given a seeded fixture diff whose added-plus-removed lines, excluding lockfiles and `project.yaml`'s generated paths, exceed the tier threshold with no justification in the approved plan's size table, the `size_gate` script fails (R-S3-12).
8. Given the same seeded fixture diff with a justification present in the approved plan's size table, the `size_gate` script passes and states so (R-S3-12).
9. A plan whose prose exceeds the tier's length ceiling, excluding tables, fails the structure check (R-S3-14).
10. A plan whose tables exceed the tier's row ceiling in total fails the structure check (R-S3-14).
11. A plan whose intent, scrutiny, readiness table, or risk map falls outside the first 60 lines fails the structure check (R-S3-14).
12. A plan fixture missing a section 8 table column fails the structure check (R-S3-18).
13. A plan fixture whose task carries a free-form shell command instead of a typed R-I-16 recipe id fails the structure check as a structural failure (R-S3-18).
14. A plan fixture whose task cites a recipe id not in the catalogue fails the structure check (R-S3-18).
15. A plan fixture describing a task only in prose, with no table row, fails the structure check (R-S3-18).
16. A plan whose tasks or test-strategy table cites an `AC-n` id absent from the criteria fails the structure check (R-S3-19).
17. A plan whose criteria include an `AC-n` id served by no task row, or served by no test row, fails the structure check (R-S3-19).
18. A plan task row citing no `AC-n` id and not flagged `no_behaviour_change` fails the structure check (R-S3-19).
19. For each of the readiness table's seven condition keys, `restatement_agreed`, `questions_closed`, `impact_evidence`, `risk_map`, `linked_sources`, `size_gate`, and `reviewer_set`, `handoff_ready` writes a row with `status`, `source_artefact`, `hash`, `waiver_id`, and `note` (R-S3-21).
20. A plan missing the readiness table, or carrying any row with `status = 'pending'`, fails the structure check (R-S3-21).
21. A `blind_spot` readiness row with no R-S5-13 waiver id counts as `pending` and fails the structure check (R-S3-21).
22. `handoff_ready` runs after the S3 agent invocation ends and before the R-S3-20 checklist is assembled (R-S3-21).
23. The readiness table's `hash` column binds the plan version every `human_verdict` and the plan tuple bind (R-S3-21).
24. The readiness table appears within the plan's first 60 lines (R-S3-21).

### Verification

`runner/tests/test_s3_structure.py`: criteria 1, 2, 3, 4, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24.
`runner/tests/test_size_gate.py`: criteria 5, 6, 7, 8.
`factory/evals/scripts/checks/size_gate/fixtures/`: over-threshold and justified fixtures for criteria 5, 6, 7, 8.
`factory/evals/scripts/checks/risk_map/fixtures/`: fixture project churn fixture for criterion 11's attachment check.
`factory/evals/scripts/tools/handoff_ready/fixtures/`: seven-condition-key readiness fixtures for criteria 19, 20, 21, 22, 23, 24.

## T-A-26: S3: plan rubric lines and the risk-map line

| | |
|---|---|
| Milestone | A |
| Blocks | 3 Rubric |
| HLD components | F4, C6, C9 |
| Depends on | T-A-25 |
| Rows covered | R-S3-2, R-S3-3, R-S3-4, R-S3-5, R-S3-6, R-S3-7, R-S3-9, R-S3-10, R-S3-11 |

### Description

This ticket writes `factory/rubrics/S3.md`'s deterministic rubric lines over the plan T-A-25 structure-checks, one script line per row. R-S3-2 requires a reason per rejected alternative, and R-S3-3 requires three cited near-duplicates or a named risk before a new shared abstraction. R-S3-4 ties archaeology classification to a characterization test, a named risk, and carries the brief's classification into the plan before the candidate's code changes. R-S3-5 isolates no-behaviour-change work as its own flagged, tested task. R-S3-6 requires a recorded search before a new utility. R-S3-7 requires the contracts table over every touched unit. R-S3-9 requires the test-strategy table's size, action, and recipe mapping, and R-S3-10 requires the rollout section's flags, ramp, guardrails, and kill trigger. R-S3-11 reads the `risk_map` script T-A-25 built, testing its computation and requiring three named places worth a reviewer's eyes.

### Scope

**In:** `factory/rubrics/S3.md`'s rubric-line content, alongside the bootstrap checklist T-A-27 adds to the same file; `runner/tests/test_s3_rubric.py`; `factory/evals/rubrics/S3/` with `eval.yaml` and fixtures.

**Out:** the bootstrap checklist, human verdicts, plan tuple and approval (T-A-27).

### Acceptance criteria

1. Every rejected alternative in the plan's alternatives section names what it was and why it was rejected (R-S3-2).
2. The generated `rubrics/S3.md` line for R-S3-2 marks its grader half as a bootstrap-checklist line whose judgment reads: fail when a rejected alternative's stated reason restates the alternative itself rather than naming a fact about cost, risk, or capability (R-S3-2).
3. A new file under a shared path cites at least three existing near-duplicates it replaces, or names pre-abstraction as a risk, in the plan's abstraction section (R-S3-3).
4. A plan adding both a parameter and a conditional to a shared function serving two or more unrelated callers states why inlining was not chosen (R-S3-3).
5. The generated `rubrics/S3.md` line for R-S3-3 marks its grader half as a bootstrap-checklist line whose judgment reads: fail when a shared-path abstraction cites fewer than three existing near-duplicates and names no pre-abstraction risk (R-S3-3).
6. Given the brief's history section marking a touched-area candidate `unexplained` or `contradictory`, the plan's task list includes a characterization test for it (R-S3-4).
7. A plan change altering captured behaviour of such a candidate is a named risk in the plan's unknowns, for the human to rule load-bearing or accidental (R-S3-4).
8. Given a touched-area candidate the brief classifies `explained`, `unexplained`, or `contradictory`, the plan carries that same classification for the candidate before its code is modified (R-S3-4).
9. A task whose entire justification is "no behaviour change" is its own task row flagged `no_behaviour_change`, with a behaviour-preserving test-strategy row (R-S3-5).
10. Absent stacked pull requests, a `no_behaviour_change` task is its own ticket or a named exception the human approves at S3 (R-S3-5).
11. The generated `rubrics/S3.md` line for R-S3-5 marks its grader half as a bootstrap-checklist line whose judgment reads: fail when a task flagged `no_behaviour_change` describes a change that in fact alters behaviour (R-S3-5).
12. Before proposing a new utility, helper, or pattern, the plan records the existing candidates found in the context index or component catalogue and why each was rejected (R-S3-6).
13. The generated `rubrics/S3.md` line for R-S3-6 marks its grader half as a bootstrap-checklist line whose judgment reads: fail when a recorded utility search names no context-index entry and no component-catalogue entry checked before proposing the new utility (R-S3-6).
14. For every touched function, module, endpoint, event, or serialized shape, the plan's contracts table declares source declaration, input, output, errors, side effects, invariants, authorization, ordering/concurrency, transaction/persistence, and compatibility, each `unchanged`, `changed`, or `unknown` with evidence (R-S3-7).
15. A `changed` contract field with no named decision, and no consequential question when unanswered, fails the check (R-S3-7).
16. Given a seeded contract field marked `unknown`, it appears as an explicitly accepted blind spot at S3 and can trigger R-S0-8 (R-S3-7).
17. The plan's test strategy table states tests by `small`, `medium`, or `large` against the section 8 test-mix target, each with `action` `add`, `change`, or `remove` (R-S3-9).
18. Small, medium, and large tests run under the project's unit-test, integration-test, and end-to-end recipe respectively (R-S3-9).
19. A `change` or `remove` test-strategy row names a base test and either the `AC-n` criterion that makes its assertion wrong or the `no_behaviour_change` task it serves (R-S3-9).
20. A large test is planned only where the repository already registers an end-to-end recipe, and no ticket creates an end-to-end suite (R-S3-9).
21. The generated `rubrics/S3.md` line for R-S3-9 marks its grader half as a bootstrap-checklist line whose judgment reads: fail when a planned test's stated `proves` value names no `AC-n` criterion and no specific assertion the test's action checks (R-S3-9).
22. The plan's human-executed rollout section names any flag with expected life, owner, removal condition, and a cleanup task (R-S3-10).
23. The rollout section states ramp steps, at most 12 guardrail metrics each as a query with a critical threshold, the kill trigger with rollback as the default response, and log-verification queries with pass and fail patterns (R-S3-10).
24. The generated `rubrics/S3.md` line for R-S3-10 marks its grader half as a bootstrap-checklist line whose judgment reads: fail when a rollout section's guardrail metrics carry no critical threshold, or its kill trigger names no rollback as the default response (R-S3-10).
25. The `risk_map` script computes the risk map from git over the brief's touched-area candidates before the S3 agent invocation runs (R-S3-11).
26. The computed risk map is attached as a `risk_map` artefact input, with per-candidate-file commits in the 12-month churn window and top-author share (R-S3-11).
27. A file in the top decile of churn times size within the candidate set, or with no clear owner, meaning the top author's share is under 40 percent, is a named entry (R-S3-11).
28. The agent names three places worth a reviewer's eyes and why, in the plan's risk map section (R-S3-11).
29. The generated `rubrics/S3.md` line for R-S3-11 marks its grader half as a bootstrap-checklist line whose judgment reads: fail when a risk-map section reuses boilerplate language with no candidate-specific reasoning (R-S3-11).

### Verification

`runner/tests/test_s3_rubric.py`: criteria 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24.
`factory/evals/rubrics/S3/fixtures/`: alternatives, abstraction, archaeology, no-behaviour-change, contracts, test-strategy, and rollout fixtures for criteria 1, 3, 4, 6, 7, 8, 9, 10, 12, 14, 15, 16, 17, 18, 19, 20, 22, 23; seeded `human_verdict` fixtures for the R-S3-2, R-S3-3, R-S3-5, R-S3-6, R-S3-9, and R-S3-10 grader lines for criteria 2, 5, 11, 13, 21, 24.
`factory/evals/scripts/checks/risk_map/fixtures/`: churn-window computation fixture for criteria 25, 26, 27, 28; seeded `human_verdict` fixture for the R-S3-11 grader line for criterion 29.

## T-A-27: S3: bootstrap checklist, human verdicts, plan tuple and approval, race guard

| | |
|---|---|
| Milestone | A |
| Blocks | 3 Rubric; 15 Binding |
| HLD components | H4, C4 |
| Depends on | T-A-10, T-A-14, T-A-22, T-A-23, T-A-24, T-A-26 |
| Rows covered | R-S3-20, R-S3-15 |

### Description

Until calibrated graders exist, this ticket assembles one bootstrap checklist inside `factory/rubrics/S3.md`, standing in for every grader-only Initial rubric line T-A-22, T-A-23, T-A-24 and T-A-26 generated for S1, S2, and S3. It also derives the plan tuple and its approval. R-S3-20 derives the expected set of `rubric_line_id`/`subject_item_key` pairs from the pinned rubrics, and rejects a missing or duplicate entry. Each `human_verdict` binds its rubric hash, subject artefact hash, and reviewer identity, and the complete verdict set hashes into the plan tuple. R-S3-15 derives the planned reviewer set from the exact plan scope, and creates the plan tuple after R-S3-20 completes. `implementing` is admitted only when every required `approval_record` approves that subject, quorum and identity-separation pass, and a trusted fetch confirms the target head still matches. This sits on T-A-10's binding and T-A-14's freshness boundaries.

### Scope

**In:** `factory/rubrics/S3.md`'s bootstrap-checklist section, alongside T-A-26's rubric lines; `human_verdict` table and its write path through `factory act` on the `plan_approval` item; the `evidence_tuple` table's `plan` kind, including its human-verdict-set and plan-waiver-set hashes; the plan tuple's creation and content hash as the plan-approval subject; the planned `reviewer_set` derived from plan scope; `approval_record` writes for the S3 slot; the pre-transition trusted fetch before `plan_review -> implementing`; `runner/tests/test_s3_checklist.py`; `runner/tests/test_plan_tuple.py`; the `docs/build/<ticket-id>/brief.md` and `plan.md` pairs every ticket before this one wrote under PRD decision 39, the rule T-A-01 states, feeding `factory/evals/rubrics/S3/fixtures/`.

**Out:** the real S4 execution that consumes the approved plan tuple (T-A-28); validating a named waiver against `waiver-policy.yaml`'s real policy content (T-A-32).

### Acceptance criteria

1. The runner derives the expected set of `rubric_line_id`/`subject_item_key` pairs from the pinned rubrics and assembles one bootstrap checklist containing every grader-only Initial rubric line from S1, S2, and S3 (R-S3-20).
2. A checklist missing an expected `rubric_line_id`/`subject_item_key` instance, or carrying a duplicate, is rejected (R-S3-20).
3. Each `human_verdict` binds the stable instance, rubric hash, exact subject artefact and evidence hashes, reviewer identity and role, and time (R-S3-20).
4. A `human_verdict` with `verdict = 'pass'` cites at least one evidence id or hash (R-S3-20).
5. A `human_verdict` with `verdict = 'fail'` returns the ticket to the prior stage, since a fail verdict sends the ticket back (R-S3-20).
6. A `human_verdict` with `verdict = 'blind_spot'` and no named `waiver` row blocks the plan-approval subject from being satisfied (R-S3-20).
7. A `human_verdict` with `verdict = 'blind_spot'` naming a seeded `waiver` row for that condition does not block the plan-approval subject from being satisfied (R-S3-20).
8. The canonical complete `human_verdict` set is hashed into the plan tuple, so a rubric, artefact, evidence, verdict, or waiver change creates a new plan subject (R-S3-20).
9. S3 derives an immutable planned `reviewer_set` from the exact plan scope (R-S3-15).
10. After the R-S3-20 checklist is complete, the runner creates the plan tuple whose content hash is the canonical plan-approval subject (R-S3-15).
11. Each required slot produces a separate `approval_record`; the ticket enters `implementing` only when every record approves that same subject and quorum and identity-separation pass (R-S3-15).
12. A trusted fetch immediately before the `plan_review -> implementing` transition confirms the target head still equals the plan tuple's base and recorded target head, else no S4 work starts (R-S3-15).
13. Initial has one S3 slot and excludes work needing a sensitive-owner slot, per R-S0-8 (R-S3-15).
14. A seeded S4 hand-back that changes the ticket's head SHA while `base_sha` and the plan tuple's bound components are unchanged does not create a new plan-approval subject, and the plan tuple's satisfying approval set continues to satisfy it (R-S3-15).
15. A ticket with a question neither answered nor accepted as an assumption has no satisfied plan-approval subject, since an unresolved question blocks S3 approval (R-S3-15).
16. For each of a changed answer, assumption, source, brief, criteria, plan, impact evidence, base, manifest, trust approval, recipe or execution policy, reviewer set, authority policy, verdict set, or waiver set, a new plan subject is created requiring full approval (R-S3-15).
17. Expiry invalidates the satisfying approval set and requires fresh full quorum against the same subject (R-S3-15).
18. On the fixture ticket's real-invocation walk, every rubric script line for S0 through S6 passes and every semantic rubric line or half-line from S1 to S3 has a recorded `human_verdict` row, matching A's exit test (R-S3-20).

### Verification

`runner/tests/test_s3_checklist.py`: criteria 1, 2, 3, 4, 5, 6, 7, 8, 18.
`runner/tests/test_plan_tuple.py`: criteria 9, 10, 11, 12, 13, 14, 15, 16, 17.
`factory/evals/rubrics/S3/fixtures/`: the `docs/build/<ticket-id>/brief.md` and `plan.md` pairs every ticket before this one wrote under PRD decision 39 exercising criteria 1, 2, 3, 4, 5, 6, 7, 18.

## T-A-28: S4: handoff and hand-back artefacts, deviation rows

| | |
|---|---|
| Milestone | A |
| Blocks | 11 Artefact |
| HLD components | R2, C6 |
| Depends on | T-A-27 |
| Rows covered | R-S4-1, R-S4-2 |

### Description

S4 hands work to an implementer through one self-contained `handoff` artefact (R-S4-1). A fresh context with no transcript can start the ticket's tasks from the handoff alone. The handoff carries no credential and no ungoverned source. Hand-back writes `branch`, `head_sha`, and `worktree_path` on the ticket, and a `deviation` row set from what S4 actually did (R-S4-2). An explicit, canonically hashed empty set stands for no deviations, and a missing or malformed set is a structural failure that never reaches S5. This ticket builds on T-A-27's approved plan tuple and bootstrap checklist, which the handoff carries by hash.

### Scope

**In:** `runner/stages/S4.py` handoff assembly reading the plan tuple, the readiness table's bootstrap-checklist hash, the approved criteria and plan hashes, the current assumption-set hash and blind spots, tier and budget, required S5 check policies and recipe ids, every task's allowed recipe ids and typed values from T-A-27's plan artefact, and the ticket's most recent `revision_after_approval` tag note, if any; `artefact.kind = 'handoff'`; the hand-back write path setting `ticket.branch`, `ticket.head_sha`, `ticket.worktree_path`; the `deviation` table (`id`, `ticket_id`, `stage_run_id`, `plan_item`, `plan_said`, `agent_did`, `why`, `kind`, `contract_change`) populated from the S4 hand-back; the canonical, content-hashed empty deviation set; the structural-failure classification for a missing or malformed deviation set.

**Out:** running the plan-task loop that produces a hand-back (T-A-29); the S5 checks that read the handoff's recipe ids and check policies (T-A-30); the packet's listing of deviation rows in its evidence table (T-A-31).

### Acceptance criteria

1. A `handoff` artefact for a ticket in `implementing` includes the approved criteria hash and the approved plan hash (R-S4-1).
2. It includes the plan tuple's id, the S3 plan-approval subject (R-S4-1).
3. It includes the current assumption-set hash and the blind spots from the readiness table (R-S4-1).
4. It includes the tier and the budget (R-S4-1).
5. It includes the required S5 check policies and recipe ids (R-S4-1).
6. It includes, for every task, its allowed recipe ids and typed values (R-S4-1).
7. It includes the bootstrap checklist hash and a reference to the `deviation` schema (R-S4-1).
8. A `handoff` produced after a request-changes decision includes the reviewer's `revision_after_approval` note from the prior review cycle; a `handoff` on a ticket's first cycle carries no such note (R-S4-1).
9. It carries no credential and no ungoverned source (R-S4-1).
10. Given only the `handoff` artefact file and the registered sandbox mounts, with no access to the S3 `stage_run` transcript, a reconstruction test derives the same task list, recipe set, and budget the approved plan names (R-S4-1).
11. A seeded S4 hand-back with `branch`, `head_sha`, and `worktree_path` set and a non-empty `deviation` row set matching the 2.2 schema moves the ticket to `checks` with those fields recorded (R-S4-2).
12. A seeded S4 hand-back with no deviations writes an explicit, canonically hashed empty `deviation` set rather than omitting the field (R-S4-2).
13. A seeded S4 hand-back with the `deviation` set missing entirely is a structural S4 failure: the ticket does not enter `checks` and the failure cannot be waived (R-S4-2).
14. A seeded S4 hand-back with a `deviation` set that does not conform to the 2.2 schema is a structural S4 failure, refused on the same terms as a missing set (R-S4-2).
15. A hand-back on a ticket's first cycle creates no pull request, and a hand-back on a ticket with an existing revision PR leaves `ticket.pr_url` and `pr_identity` unchanged (R-S4-2).

### Verification

`runner/tests/test_s4_handoff.py`, criteria 1 to 10.
`runner/tests/fixtures/s4_handoff/`: first-cycle and revision-cycle ticket seeds for criterion 8.
`runner/tests/test_s4_handback.py`, criteria 11 to 15.

## T-A-29: S4: fresh run per task, verification quota, escalation causes, control-defect events, fix rounds

| | |
|---|---|
| Milestone | A |
| Blocks | 10 Run; 9 Ticket and its state |
| HLD components | C3, C2, C6 |
| Depends on | T-A-09, T-A-10, T-A-14, T-A-18, T-A-28 |
| Rows covered | R-S4-5, R-S4-6, R-S4-9 |

### Description

Automated S4 gives each plan task one fresh `stage_run`, in dependency order. The runner revalidates the plan subject, quorum, trust approvals, and the target head before every invocation, so a stale binding starts no agent (R-S4-5). Three verification failures per approved plan-item version atomically escalate the ticket with complete failure history and an escalation tag (R-S4-6). A sandbox-integrity, undeclared-capability, or invalid recipe-policy binding instead escalates immediately as a control defect with its own incident event. Fix rounds give the machine one bounded repair loop against a red result confined to lint, compile-type, or a base-green head-red test (R-S4-9). A fix round stays inside the S4 budget and is a recorded run, never a hidden repair loop. This ticket builds on T-A-28's handoff and hand-back and on T-A-14's freshness checks.

### Scope

**In:** `runner/stages/S4.py` task-execution loop writing one `stage_run` per plan task in dependency order; the pre-invocation revalidation call against T-A-10's plan tuple and T-A-09's reviewer quorum; `stage_run.verification_attempt` counting 1 to 3 per approved plan-item version; `stage_run.outcome` and `failure_kind` values for stale binding, infrastructure failure, and control defect; `tag.event_kind = 'escalation'` with `fm_id = 'FM-19'`, and `= 'control_defect'` with `fm_id = 'FM-23'` when the execution boundary is implicated; `incident_observation` rows of `record_kind = 'control_defect_event'`, `control_category = 'execution_boundary'`; `failure_history` artefact writes at escalation; `stage_run.run_kind` values `fix_round` and `validation_only`; the fix-round cap entry added to the `factory/config/limits.yaml` that T-A-18 creates; the `deviation` rows a fix round's test-file changes add.

**Out:** the S5 ordered check list that classifies a red result as machine-only or not (T-A-30); the `base_test_diff` script itself (T-A-30); the live `scope_diff` script and its wiring into a fix round (T-A-30); the live S5 rerun after a fix round's validation pass (T-A-30); the packet's evidence-table listing of fix rounds and deviations (T-A-31).

### Acceptance criteria

1. Immediately before a task invocation, seeded with a target head that does not equal the plan tuple's `base_sha` and recorded target head: no agent starts, `stage_run.outcome = 'fail'` with `failure_kind = 'stale_binding'` and a null `verification_attempt` is written, one `red_check` queue item is created, and the ticket remains `implementing` (R-S4-5).
2. Three consecutive task failures on the same approved plan-item version consume `verification_attempt` 1, then 2, then 3 (R-S4-5).
3. A `stage_run` with `outcome = 'infrastructure_failure'` on an unavailable approved runtime receives one ordinary retry without incrementing `verification_attempt` (R-S4-5).
4. A task whose recipe id is not approved, or whose approved-recipe binding is invalid, ends its `stage_run` as a control defect and escalates immediately, consuming no verification quota (R-S4-5).
5. A retried task's `stage_run` is a fresh invocation with newly registered evidence, never a continuation of the failed run's context (R-S4-5).
6. A successful invocation's validation phase executes each approved typed recipe exactly once; green recipes leave `stage_run.outcome = 'pass'` (R-S4-5).
7. `verification_attempt` is tracked per approved plan-item version, and a new plan-item version starts a fresh count (R-S4-5).
8. After feedback, only the named tasks rerun; a task whose plan-bound inputs are unchanged keeps its retained result and is not rerun (R-S4-5).
9. The third verification failure for an approved plan-item version leaves `stage_run.outcome = 'fail'` and moves the ticket to `escalated` in the same transaction (R-S4-6).
10. A repeat infrastructure failure escalates the ticket with `stage_run.outcome = 'infrastructure_failure'` without consuming a `verification_attempt`; a budget stop keeps `aborted_budget` and a human stop keeps `aborted_human` on their own `stage_run` rows (R-S4-6).
11. For each of a sandbox-integrity failure, an undeclared-capability failure, and an invalid recipe-policy-binding failure, seeded on a task's `stage_run`: the applicable failure outcome is recorded, a `control_defect` tag is written with `fm_id = 'FM-23'` when the execution boundary is implicated, an `incident_observation` row of `control_category = 'execution_boundary'` opens, and the ticket escalates immediately (R-S4-6).
12. For each of verification exhaustion, which resumes only with a superseding plan-item version and new S3 approval; infrastructure or human-stop resolution, which resumes the same item with quota preserved; and control-defect resolution, which requires a factory fix, a `remediated` disposition, and a passing adoption-gate run: a seeded `escalated` ticket resumes only through its own route (R-S4-6).
13. The `escalation` queue item carries complete per-attempt `failure_history` for the escalated ticket (R-S4-6).
14. A seeded S5 pass ending red, where every red result comes from the project's lint or compile-type recipes, or from a unit-test or integration-test recipe green at base and red at head, with fewer than `limits.yaml`'s fix-round cap already run: the runner returns the ticket to `implementing` with no queue item and starts one `stage_run` with `run_kind = 'fix_round'` (R-S4-9).
15. A seeded red result on a unit-test or integration-test recipe already red at base refuses the machine-only route and queues a `red_check` item instead (R-S4-9).
16. A seeded red result on an end-to-end recipe refuses the machine-only route regardless of its base result, and queues a `red_check` item (R-S4-9).
17. A seeded S5 pass with a red result outside lint, compile-type, unit-test, and integration-test recipes, alongside an otherwise-eligible red result, refuses the machine-only route (R-S4-9).
18. A fix round's diff may change a test the ticket added or a base test the approved plan lists with `action` `change` or `remove`; an attempt to change any other base test is refused (R-S4-9).
19. A fix round whose diff touches only test files is refused (R-S4-9).
20. A ticket that has already run `limits.yaml`'s fix-round cap number of `fix_round` runs is refused a further fix round and queues a `red_check` item (R-S4-9).
21. A `fix_round` `stage_run` that exceeds the per-ticket S4 budget aborts with `outcome = 'aborted_budget'`, counting against that budget without consuming a `verification_attempt` (R-S4-9).
22. A seeded `scope_diff` `check_result` with `result = 'fail'` blocks a fix round's hand-back the same way it blocks an ordinary task's hand-back (R-S4-9).
23. After a fix round's hand-back, the runner executes every task's validation recipes once as a `stage_run` with `run_kind = 'validation_only'`; a red `validation_only` run fails the fix round, and a seeded still-red S5 pass following it also fails the fix round (R-S4-9).
24. Every test-file change inside a fix round's diff is recorded as a `deviation` row naming its criterion or task (R-S4-9).

### Verification

`runner/tests/test_s4_task_loop.py`, criteria 1 to 8.
`runner/tests/fixtures/s4_task_loop/`: seeded scenarios for criteria 1 to 8.
`runner/tests/test_s4_escalation.py`, criteria 9 to 13.
`runner/tests/fixtures/s4_escalation/`: seeded scenarios for criteria 9 to 13.
`runner/tests/test_s4_fix_round.py`, criteria 14 to 24.
`runner/tests/fixtures/s4_fix_round/`: seeded scenarios for criteria 14 to 24.

## T-A-30: S5: preflight and review tuple, the ordered check list at A, scope diff, declaration diff, regression-only, base-test protection, red checks as one item

| | |
|---|---|
| Milestone | A |
| Blocks | 22 Check |
| HLD components | C9, F7, C6 |
| Depends on | T-A-09, T-A-10, T-A-14, T-A-20, T-A-25, T-A-29 |
| Rows covered | R-S5-4, R-S5-5, R-S5-10 |

### Description

The S5 driver runs the checks that exist at A over the fixture project's base and head, in plain checkouts and their throwaway copies. It binds every result to one review tuple, built from T-A-10's tuple construction and T-A-09's reviewer-set derivation. Scope diff flags any file outside the plan's scope table and discretion globs, with no model involved (R-S5-4). Source-declaration diff and behaviour-contract evidence compare declarations and named blind spots at base and head, never claiming semantic proof (R-S5-5). Regression-only comparison blocks a lint, compile-type, integration, or end-to-end result only when it worsens at head, so `factory/lints/` adds no blocking rule (R-S5-10). The driver also runs `base_test_diff`, whose base-test-protection result feeds T-A-31's `deviation` row and evidence-table listing. This ticket also computes the routing inputs T-A-29's fix round consumes.

### Scope

**In:** `runner/stages/S5.py` driver calling preflight, built from T-A-10's plan and review tuple construction and T-A-09's reviewer-set derivation, to create one review tuple or write one `review_tuple_preflight` check_result on construction failure; `size_gate`, the script T-A-25 builds, wired into the ordered S5 check list over the actual diff; `factory/scripts/checks/scope_diff`; `factory/scripts/checks/source_declaration_diff`; `factory/scripts/checks/behavior_contract_evidence`; the regression-only comparison logic inside the lint, compile-type, unit-test, integration-test, and end-to-end recipe invocations; `factory/scripts/checks/base_test_diff` computing the base-test-change detection that feeds T-A-31's `deviation` row; running the fixture project's recipes at base and head in plain checkouts, with a throwaway copy where a check writes into a checkout; `check_result` rows bound to the review tuple; aggregating red and waivable blind-spot results into one `red_check` item; computing the routing inputs T-A-29's `fix_round` run kind consumes; eval directories `factory/evals/scripts/checks/scope_diff/`, `source_declaration_diff/`, `behavior_contract_evidence/`, `base_test_diff/`, each with `eval.yaml` and a fixture.

**Out:** R-S4-10's base-test-protection detection, `deviation`, and evidence-table criteria (T-A-31); the waiver mechanism a blind spot advances through (T-A-32); the security recipes, dependency verification, and copy-on-write copies that sit at AB (R-S5-1, R-S5-2).

### Acceptance criteria

1. A seeded diff with every file inside the plan's scope table paths or discretion globs: `scope_diff` writes a `check_result` with `check_name = 'scope_diff'`, `result = 'pass'` (R-S5-4).
2. A seeded diff with a file outside both the plan's scope table paths and discretion globs: `scope_diff` writes a `check_result` with `check_tier = 'blocking'`, `result = 'fail'`, listing the out-of-scope files (R-S5-4).
3. `scope_diff` computes its result from the diff and the plan's scope table alone, with no model or agent invocation (R-S5-4).
4. A seeded fixture with a new public or protected declaration added at head, not named in the plan's contracts table: `source_declaration_diff` writes a blocking failure listing the added declaration (R-S5-5).
5. A seeded fixture with a public or protected declaration removed at head: `source_declaration_diff` writes a blocking failure listing the removed declaration (R-S5-5).
6. A seeded fixture with a declaration the plan marks unchanged that in fact changed at head: `source_declaration_diff` writes a blocking failure (R-S5-5).
7. A seeded fixture where every plan contract field and R-S3-20 line points to recorded test or characterisation evidence: `behavior_contract_evidence` writes `result = 'pass'` and claims no semantic proof (R-S5-5).
8. For each of missing grammar or unit, missing inheritance, missing reflection, missing generated API, missing binary compatibility, and unchecked behavioural changes, seeded in a fixture: the check writes a `blind_spot` naming that item (R-S5-5).
9. A seeded fixture where a `behavior_contract_evidence` blind spot is a public-compatibility change on the Initial Java slice: the check_result triggers the exclusion-gate script `runner/checks/exclusion.py` (R-S5-5).
10. A seeded lint or compile-type diagnostic new or worsened at head, absent or green at base: regression-only writes a blocking failure (R-S5-10).
11. A seeded lint or compile-type diagnostic already present at base and unchanged at head: regression-only does not block, and the diagnostic remains visible as inherited debt (R-S5-10).
12. A seeded integration or end-to-end test result new-red or worsened at head relative to base: regression-only writes a blocking failure (R-S5-10).
13. A seeded integration or end-to-end test already red at base and still red at head: regression-only does not block (R-S5-10).
14. `factory/lints/`'s own configuration contributes no blocking rule regardless of its diagnostics (R-S5-10).
15. For each of freshness, unit tests, security, dependency policy, size, scope, contract evidence, reviewer or approval binding, and blind spots: the regression-only exception does not govern it, and each retains its own blocking rule (R-S5-10).
16. On the fixture ticket's S5 pass, every check the A shape holds, `size_gate`, `scope_diff`, `source_declaration_diff`, `behavior_contract_evidence`, the regression-only comparison, and `base_test_diff`, plus the fixture repository's recipes, runs at base and head in plain checkouts with no security recipe and no copy-on-write copy, and every `check_result` is bound to one review tuple (R-S5-4, R-S5-5, R-S5-10).

### Verification

`runner/tests/test_s5_scope_diff.py` with `factory/evals/scripts/checks/scope_diff/`, criteria 1 to 3.
`runner/tests/test_s5_declaration_diff.py` with `factory/evals/scripts/checks/source_declaration_diff/` and `factory/evals/scripts/checks/behavior_contract_evidence/`, criteria 4 to 9.
`runner/tests/test_s5_regression_only.py`, criteria 10 to 15.
`runner/tests/test_s5_order.py` with `factory/evals/scripts/checks/base_test_diff/`, criterion 16.

## T-A-31: S6: packet and PR body, evidence table, test summary, the assembly run and race guard

| | |
|---|---|
| Milestone | A |
| Blocks | 11 Artefact |
| HLD components | R2, C6, C9 |
| Depends on | T-A-09, T-A-14, T-A-29, T-A-30 |
| Rows covered | R-S6-1, R-S6-2, R-S4-10 |

### Description

The local packet and the `pr_body` are assembled by script in charter order, opening with tuple identity and freshness and then one evidence table (R-S6-1). No element is authored at S6, and packet length is never a proxy. The evidence table lists every blocking check T-A-30 ran, the fix rounds T-A-29 took, and the base-test changes T-A-30's `base_test_diff` recorded. It also lists the readiness table and every recorded approval and waiver. The test summary matches the plan's test strategy table to the diff's test files and flags an unplanned one (R-S6-2). The assembly run executes from `checks`, calling T-A-09's race guard and T-A-14's freshness, and only its pass queues `packet_approval`. Every base-test change or removal T-A-30's `base_test_diff` detects is recorded as a `deviation` row and appears in the evidence table with its diff (R-S4-10).

### Scope

**In:** `factory/scripts/tools/packet_assemble`; `factory/scripts/tools/pr_body_assemble`; `artefact.kind = 'packet'`, `= 'pr_body'`; the S6 assembly `stage_run` invoked from `checks`, calling T-A-09's reviewer-set race guard and T-A-14's freshness recheck; `queue_item.kind = 'packet_approval'` queued only on a passing assembly run; the base-test-protection detection tests, the `deviation` write, and the evidence-table listing against T-A-30's `factory/scripts/checks/base_test_diff` and its `factory/evals/scripts/checks/base_test_diff/` fixtures; eval directories `factory/evals/scripts/tools/packet_assemble/`, `pr_body_assemble/`, each with `eval.yaml` and a fixture.

**Out:** the `publication_target` and review-approval subject hashes and final-review `approval_record` rows (T-A-34).

### Acceptance criteria

1. `packet_assemble` produces a `packet` artefact whose sections open with tuple identity and freshness, then one evidence table, in charter order (R-S6-1).
2. Each evidence-table element names its source artefact and its hash (R-S6-1).
3. The evidence table lists every blocking `check_result` bound to the review tuple with `result` `pass`, `blind_spot`, or `waived` and its evidence hash, the fix rounds taken with the recipes they cleared, the base-test changes and removals with their criteria or tasks and diffs, the readiness table, and every `approval_record` and `waiver` (R-S6-1).
4. `pr_body_assemble` produces a `pr_body` artefact with the same narrative and evidence links as the packet, omitting the literal branch diff, which the packet alone carries (R-S6-1).
5. A seeded impact, declaration, or behaviour-limitation entry in the evidence table is labelled `blind_spot`, never `pass` (R-S6-1).
6. A test file in the diff with no matching test-strategy row is listed in the test summary as "unplanned test, purpose not stated" (R-S6-2).
7. A test-strategy row with `action` `change` or `remove` is summarised in the test summary against the `AC-n` criterion or task it names (R-S6-2).
8. The test summary's matched rows correspond to the plan's test strategy table entries whose test file appears in the diff (R-S6-2).
9. A seeded plan test-strategy table with no row naming a base test, that test edited at head: `base_test_diff` writes a blocking failure listing the file and test identity (R-S4-10).
10. The same setup with the test deleted at head: `base_test_diff` writes a blocking failure listing the file and test identity (R-S4-10).
11. The same setup with the test renamed at head: `base_test_diff` writes a blocking failure listing the file and test identity (R-S4-10).
12. The same setup with the test excluded from running through build or runner configuration at head: `base_test_diff` writes a blocking failure listing the file and test identity (R-S4-10).
13. A seeded plan row with `action = 'change'` naming criterion `AC-n`, whose head version of the test fails when run in the base view and passes at head: `base_test_diff` records `pass` for that planned change (R-S4-10).
14. The same row, whose head version of the test also passes when run in the base view: `base_test_diff` records a `blind_spot` (R-S4-10).
15. A seeded plan row naming a `no_behaviour_change` task instead of a criterion is exempt from the both-views rerun (R-S4-10).
16. A fix round's diff changing a test the ticket added or a base test the plan lists passes `base_test_diff`; changing any other base test is refused (R-S4-10).
17. A seeded base-test change or removal in the fixture diff is recorded as a `deviation` row naming its criterion or task (R-S4-10).
18. That `deviation` row appears in `packet_assemble`'s evidence table with its diff (R-S4-10).

### Verification

`runner/tests/test_s6_packet_assemble.py` with `factory/evals/scripts/tools/packet_assemble/`, criteria 1, 2, 3 and 5.
`runner/tests/test_s6_pr_body_assemble.py` with `factory/evals/scripts/tools/pr_body_assemble/`, criterion 4.
`runner/tests/test_s6_test_summary.py`, criteria 6 to 8.
`runner/tests/test_s5_base_test_diff.py` with `factory/evals/scripts/checks/base_test_diff/` from T-A-30, criteria 9 to 18.

## T-A-32: S5: waivers and the non-waivable list

| | |
|---|---|
| Milestone | A |
| Blocks | 14 Approval and quorum |
| HLD components | H4, C9 |
| Depends on | T-A-30, T-A-31 |
| Rows covered | R-S5-13 |

### Description

A blocking epistemic blind spot advances only through a `waiver` whose exact `waiver-policy.yaml` policy permits that condition and the actor's role (R-S5-13). A plan waiver binds the candidate subject into the plan tuple. An S5 waiver binds the review tuple, sharing the `red_check` item with the failures T-A-30's checks produced. Nine conditions are never waivable, including a sandbox-integrity failure that milestones.md seeds since the thin sandbox also reports it for real. Every waiver is rechecked at its own gate, at S6, and at dispatch, and its reporting tag grants no authority of its own. This ticket also confirms a waiver's appearance in the packet T-A-31 assembles.

### Scope

**In:** `waiver` table (`id`, `ticket_id`, policy id/version/hash, waived `check_result` or `human_verdict`, `subject_kind`, canonical subject hash, `evidence_tuple_id`, actor identity and role, reason, exact scope, compensating controls, evidence ids and hashes, issued time, mandatory expiry, canonical serialization version, `content_hash`, the two hashes computed by calling T-A-02's `runner/canonical.py`); `factory/config/waiver-policy.yaml`; the plan-waiver and review-waiver subject binding; the recheck at the waiver's own gate, at S6, and at dispatch; `tag.event_kind = 'policy_exception'` referencing a valid `waiver`.

**Out:** the dispatch recheck's outbox wiring (T-A-34).

### Acceptance criteria

1. A seeded blocking `blind_spot` on a plan-candidate artefact or verdict advances only under a `waiver` with `subject_kind = 'plan_candidate'` whose exact `waiver-policy.yaml` policy permits the condition and the actor's role; that waiver binds the candidate subject and enters the plan tuple (R-S5-13).
2. A seeded blocking `blind_spot` in an S5 result advances only under a `waiver` with `subject_kind = 'review_tuple'` binding the review tuple, sharing the `red_check` item with the failures (R-S5-13).
3. A `waiver` issued by an actor whose role the exact policy does not authorise for that condition is refused (R-S5-13).
4. A `waiver` row records the exact `waiver-policy.yaml` policy id, version, and content hash it was issued under (R-S5-13).
5. A `waiver` past its mandatory expiry no longer permits advancement and blocks (R-S5-13).
6. A `waiver` missing compensating controls or supporting evidence ids and hashes is refused (R-S5-13).
7. A seeded review-tuple `waiver` over a waived `check_result` appears in `packet_assemble`'s evidence table with its waiver id, exact scope, and mandatory expiry (R-S5-13).
8. A `waiver` is rechecked at its own gate, at S6, and at dispatch; a changed subject, changed evidence, or lost authority discovered at any recheck blocks (R-S5-13).
9. A `waiver`'s `policy_exception` tag grants no authority beyond what the waiver itself permits (R-S5-13).
10. For each of a secret or restricted-pattern hit, an unknown classification, an unknown or missing trust approval, a sandbox-integrity failure seeded as a `check_result` row, a stale base, head, or tuple, a reviewer-set or quorum mismatch, an approval mismatch, a missing required artefact, and Initial-scope exclusion: no `waiver` permits it and the ticket is refused (R-S5-13).

### Verification

`runner/tests/test_s5_waivers.py`, criteria 1 to 10.
`runner/tests/fixtures/waivers/`: one fixture per non-waivable condition of criterion 10, plus authorised, unauthorised, and expired waiver fixtures for criteria 1 to 9.

## T-A-33: Tags: catalogue, human tags, mechanical tags, cause map, policy exception, resolution chains

| | |
|---|---|
| Milestone | A |
| Blocks | 16 Tag |
| HLD components | R1, F6, H2 |
| Depends on | T-A-02, T-A-12, T-A-20, T-A-29, T-A-32 |
| Rows covered | R-T-6 |

### Description

The factory never infers a human tag. Every transition a human decides against the factory's output commits only with a `tag` row carrying a catalogue failure-mode id the human chose (R-T-6). The factory writes its own mechanical tags, stale index, cause-specific escalation, and mechanically detected control defects, and an incident reviewer supplies attribution and disposition. A mechanical pilot exclusion carries the recorded rule and evidence instead of a human tag, and a policy exception classifies a valid waiver without granting one. This ticket sits after T-A-20's exclusion gate, T-A-29's control-defect events, and T-A-32's waivers, which its tests read.

### Scope

**In:** the full `event_kind` catalogue and write paths over the `tag` table T-A-02 created; `factory/catalogue/failure-modes.md`; `factory/catalogue/decisions.md`; `factory/rubrics/checklists/send-back-grounds.md`; the mechanical-versus-human `tagged_by` distinction; the `close_reason = 'pilot_excluded'` no-human-tag path; the seeded-decision-record write path for `revision_after_approval` and `packet_defect` tags.

**Out:** the live request-changes and self-containedness decisions routed through that write path, including the `packet_defect` tag's exact `approval_record` binding (T-A-34).

### Acceptance criteria

1. For each of `override`, `send_back`, and `abandoned`: a human decision against the factory's output on the named transition, through `factory act`, commits only together with a `tag` row of that `event_kind`, with `tagged_by` the human (R-T-6).
2. For each of `revision_after_approval` and `packet_defect`: a seeded decision record passed to this ticket's `tag` write path commits only together with a `tag` row of that `event_kind`, with `tagged_by` the human (R-T-6).
3. A `send_back` tag's `note` names one of the checklist's six grounds, for each of duplicates existing work, technically unsound, missing backward-compatibility or migration analysis, contradicts a stated non-goal, built on a wrong brief or wrong criteria naming the target stage, and other with a note, from `send-back-grounds.md` (R-T-6).
4. A ticket closed `pilot_excluded` for a mechanical exclusion match at S0, S1, S3, or S5 carries the recorded rule and evidence and writes no human failure `tag` (R-T-6).
5. For each of `stale_index`, `escalation`, and `control_defect`: the factory writes that tag with `tagged_by` mechanical, never a human, and an incident reviewer supplies attribution and disposition on `control_defect` and `incident` tags (R-T-6).
6. A ticket carrying only a `policy_exception` tag with no matching `waiver` row is refused authority; a `policy_exception` tag referencing a valid `waiver` classifies it without granting authority (R-T-6).
7. For each of a `send_back`, `abandoned`, or `override` decision: an `act` of that kind with no accompanying `tag` row is refused (R-T-6).
8. A later corrected packet or question appends a `tag` with `resolves_tag_id` pointing at the original `packet_defect` row and a `resolution_evidence_ref`, without deleting or overwriting that original row (R-T-6).

### Verification

`runner/tests/test_tags.py`, criteria 1 to 8.
`runner/tests/fixtures/tags/`: seeded ticket/tag scenarios for criteria 1 to 8.

## T-A-34: S6: publication target and review-approval subject, approval wording and request-changes routing, self-containedness answer and packet defect

| | |
|---|---|
| Milestone | A |
| Blocks | 15 Binding; 14 Approval and quorum |
| HLD components | C4, H4 |
| Depends on | T-A-13, T-A-31, T-A-32, T-A-33 |
| Rows covered | R-S6-10, R-S6-7, R-H-8 |

### Description

Publication binds one hashed `publication_target` and one review-approval subject (R-S6-10). Every required final-review slot must approve the same destination and evidence before dispatch. The approval line reads verbatim that approval certifies judgment, intent, and residual risk, and that defect evidence was supplied by S5 (R-S6-7). Request changes returns the ticket to `implementing` with a `revision_after_approval` tag T-A-33 defines and a note the next handoff carries. Every packet and question must be self-contained, so a false self-containedness answer writes a `packet_defect` tag on the exact `approval_record` or question version (R-H-8). Both subject hashes are computed by calling T-A-02's `runner/canonical.py`, the one canonical serialisation every subject hash in the record uses. This ticket completes T-A-31's packet with the subjects and approval flow, and drives `pr_create` and `pr_update` through T-A-13's stub deliverer.

### Scope

**In:** the `publication_target` hash function and the review-approval subject hash function, both computed by calling T-A-02's `runner/canonical.py`; `approval_record` rows for required final-review slots with `decision_supported_without_transcript` and `active_attention_bucket`; the verbatim attestation text and its version hash; `tag.event_kind = 'revision_after_approval'` and `= 'packet_defect'` with `fm_id = 'FM-10'`, writes bound to the exact `approval_record` or question version; `tag.resolves_tag_id`/`resolution_evidence_ref` for a corrected packet or question; the thin, A-shaped `pr_create`/`pr_update` intent creation on satisfied quorum, dispatched through T-A-13's stub deliverer.

**Out:** the full dispatch race protection and compare-and-set semantics of `pr_create`/`pr_update`, which sit at AB (R-S6-3).

### Acceptance criteria

1. The runner hashes one `publication_target` from operation kind, repository, target and head refs, current PR identity if any, desired head, and expected prior remote head (R-S6-10).
2. The runner hashes one review-approval subject from the review tuple, the canonical ordered blocking-check-result content hashes, waiver content hashes, the packet hash, the `pr_body` hash, the effective reviewer-set hash, and the `publication_target` hash (R-S6-10).
3. Changing a bound `check_result` or its evidence produces a different review-approval-subject hash (R-S6-10).
4. Changing the `publication_target`'s repository, target ref, head ref, or desired head produces a different `publication_target` hash and a different review-approval subject (R-S6-10).
5. A seeded approval set with fewer `approval_record` rows than a required final-review slot's minimum approval count refuses publication (R-S6-10).
6. A seeded pair of required final-review slots whose `reviewer_set` entry carries a `distinct_from` constraint between them, both satisfied by `approval_record` rows from the same canonical actor identity, refuses publication (R-S6-10).
7. A seeded `approval_record` from an actor whose role the authority-policy hash does not permit for that slot refuses publication (R-S6-10).
8. An `approval_record` past its mandatory expiry invalidates the satisfying set and requires fresh full quorum against the same subject (R-S6-10).
9. Full quorum on the review-approval subject for a ticket with no PR identity creates one `pr_create` outbox intent through T-A-13's stub deliverer, returning a receipt; a second quorum on a ticket seeded at `pr_opened` with a recorded revision creates one `pr_update` intent through the same deliverer, returning a receipt (R-S6-10).
10. Every required final-review `approval_record` carries the verbatim attestation line, that approval certifies judgment, intent, and residual risk, and that defect evidence was supplied by S5 (R-S6-7).
11. A request-changes decision on a ticket in `review` returns it to `implementing` with a `revision_after_approval` tag and the reviewer's note (R-S6-7).
12. The reviewer's note from a request-changes decision is carried into the next S4 `handoff` artefact (R-S6-7).
13. A ticket whose blocking tier is red cannot enter `review` (R-S6-7).
14. The engineer records a self-containedness answer for the fixture ticket's question set and its packet, standing in for a grader at A (R-H-8).
15. A seeded false self-containedness answer on a plan or review decision writes a `packet_defect` tag with `fm_id = 'FM-10'` bound to the exact `approval_record`; on a question, bound to the exact question version, on approve or answer as well as on request changes (R-H-8).
16. A later corrected packet or question appends a `tag` with `resolves_tag_id` and `resolution_evidence_ref` without erasing the original `packet_defect` row (R-H-8).
17. An escalation's `failure_history` artefact carries the same self-containedness rule, with the engineer's reading standing in for the Later observer-pass grader at A (R-H-8).

### Verification

`runner/tests/test_s6_publication_subjects.py`, criteria 1 to 8.
`runner/tests/fixtures/s6_publication/`: seeded approval-record sets for criteria 5 to 8, and false self-containedness scenarios for criterion 15.
`runner/tests/test_s6_dispatch.py`, criterion 9.
`runner/tests/test_s6_approval_wording.py`, criteria 10 to 13.
`runner/tests/test_s6_self_containedness.py`, criteria 14 to 17.

## T-A-35: Fixtures and evals: eval directories complete, manifest test, bootstrap fixtures, the gate, the adoption path

| | |
|---|---|
| Milestone | A |
| Blocks | 7 Fixtures and evals; 8 Factory tree and change control |
| HLD components | F8, F1 |
| Depends on | T-A-34 |
| Rows covered | R-F-2, R-F-4 |

### Description

Every referenced agent, skill, adapter, script, and rubric needs an eval directory with at least one synthetic, redacted fixture before A (R-F-2). Every stub T-A-01 built now has a real counterpart to walk. A change to any file under `factory/` changes the manifest hash and is adopted only through a reviewed change that passes the gate (R-F-4). This ticket completes the eval-directory walk T-A-01 started, now that phase two's real agents, skills, adapters, and scripts exist, and wires `python3 -m runner.gate` over the complete A subset.

### Scope

**In:** `factory/evals/agents/S1/` through `S4/`; `factory/evals/skills/S1/` through `S4/`, `skills/shared/<name>/`; `factory/evals/adapters/cursor_sdk/`; `factory/evals/scripts/checks/<name>/` and `scripts/tools/<name>/` for every script built since T-A-01; `factory/evals/rubrics/S0/` through `S6/`; `factory/evals/bootstrap/` copying the `docs/build/<ticket-id>/brief.md` and `plan.md` pairs every ticket wrote under PRD decision 39, the rule T-A-01 states, into the eval directories of the rubrics and scripts they exercise; the manifest-test rejection of a missing, empty, unredacted, or unowned eval directory; `python3 -m runner.gate` completing the walk over every fixture that exists without the OS sandbox.

**Out:** R-F-14's sandbox-escape and copy-disposal fixtures, which need the OS sandbox and sit at AB.

### Acceptance criteria

1. An eval directory absent for a referenced agent, skill, adapter, script, or rubric fails the manifest test (R-F-2).
2. An eval directory present with an empty fixture list fails the manifest test, and the manifest itself refuses an empty fixture list (R-F-2).
3. An eval directory with an unredacted real-ticket fixture fails the manifest test (R-F-2).
4. An eval directory whose `eval.yaml` names no owner fails the manifest test (R-F-2).
5. `python3 -m runner.gate` walks every eval directory of section 3.7, agents S1 to S4, skills S1 to S4 and shared, `adapters/cursor_sdk`, every `scripts/checks/<name>` and `scripts/tools/<name>`, and rubrics S0 to S6, and each holds `eval.yaml` and `fixtures/` with at least one synthetic, redacted fixture (R-F-2).
6. The first governed real-ticket export fixture is added only after a recorded redaction review (R-F-2).
7. For every ticket under `docs/build/<ticket-id>/`, its `brief.md` and `plan.md`, written by that ticket's own builder under PRD decision 39, are copied into the eval directories of the rubrics and scripts they exercise, under `factory/evals/bootstrap/` (R-F-2).
8. `factory/evals/fixture-project/` sits outside the manifest test's eval-directory walk (R-F-2).
9. A change to any file under `factory/`, a skill, agent, rubric, checklist, adapter, recipe, script, or configuration, changes the manifest hash (R-F-4).
10. `python3 -m runner.gate` reads the review record as the factory repository's own local git history, with no outside network call (R-F-4).
11. `python3 -m runner.gate` runs every fixture under the walked eval directories and the `runner/tests/` suite, and exits non-zero on any failure, over the subset of fixtures that exists without the OS sandbox (R-F-4).
12. A direct edit to `factory/` that does not pass `python3 -m runner.gate` is not an adopted change, whether or not the repository enforces branch protection (R-F-4).

### Verification

`runner/tests/test_manifest_eval_walk.py`, criteria 1 to 6.
`runner/tests/test_bootstrap_fixtures.py`, criteria 7 to 8.
`runner/tests/test_gate.py`, criteria 9 to 12.
