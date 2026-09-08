# T-A-05 plan

## Steps

| # | Step | Files touched | Proves |
|---|---|---|---|
| 1 | Add `values` to `Column`; six module-level closed-value tuples (`STAGES`, `RUN_KINDS`, `OUTCOMES`, `FAILURE_KINDS`, `COST_BASES`, `UTILITY_KINDS`); apply them to `stage_run.stage`/`run_kind`/`outcome`/`failure_kind`/`cost_basis` and `utility_run.kind`/`cost_basis`; `ddl()` emits a `CHECK` per column carrying `values`. | `runner/schema.py` | `test_run_ledger.py`'s closed-value-set rejection tests; `test_db_schema.py` (unchanged, still passes) |
| 2 | Turn `utility_run.outcome`, `heartbeat_at`, `lease_expires_at`, `ended_at` mutable and add a mutable `updated_at` column, so a utility run can be opened and finished as two writes the same way a stage run is. | `runner/schema.py` | `test_run_ledger.py`'s `finish`-on-`utility_run` test; `test_mutable_exceptions.py` (its hand-written allowlist updated to match) |
| 3 | `VIEWS` tuple naming `stage_reliability_view`; `ddl()` emits `CREATE VIEW IF NOT EXISTS` for each entry after every table. | `runner/schema.py` | `test_reliability_view.py` |
| 4 | Bump the schema version. | `runner/db.py` | `test_db_schema.py`'s reconnect-is-idempotent test still passes against the new version |
| 5 | `factory/config/tiers.yaml`: `tiers`, per-tier `budgets.by_tier`, the `S5` wall-clock override under `budgets.overrides`, `s4_per_ticket`, and `leases.seconds`. | `factory/config/tiers.yaml` | `test_run_ledger.py`'s budget-lookup tests |
| 6 | `runner/run_ledger.py`: `open_stage_run` (attempt numbering, lease/heartbeat start), `open_utility_run`, `heartbeat`, `finish`, `settle_cost` (provenance checks before the write), `budget`, `s4_per_ticket_budget`. | `runner/run_ledger.py` | `test_run_ledger.py` in full |
| 7 | Refactor `run_stage` to open/finish every `stage_run`/`utility_run` through `run_ledger`, preserving its refusal behaviour exactly. | `runner/stages/__init__.py` | `test_stub_stages.py`, `test_state_table.py`, `test_cli_skeleton.py` (all unchanged, still passing) |
| 8 | Fix two pre-existing tests whose `cost_basis` literal (`"list_price"`) never matched the PRD's real four-value set, now that the schema enforces it. | `runner/tests/test_mutable_exceptions.py` | those two tests, now exercising a value the schema actually accepts |
| 9 | This ticket's own brief and plan. | `docs/build/T-A-05/brief.md`, `docs/build/T-A-05/plan.md` | reviewed by the human, not a test |

## Test strategy

`test_run_ledger.py` opens its own `tmp_path` database per test, the same
convention as the rest of the record/schema suite. Closed-value-set
rejection is tested with a raw `record.insert` naming an out-of-set value,
never through `run_ledger` itself, so a schema regression (a removed
`CHECK`) fails independently of whether `run_ledger` happens to only ever
pass valid values. `settle_cost`'s provenance rules are tested as
`ValueError` cases that never reach the database, plus one raw-SQL second
write that exercises the schema's own settle-once trigger. `budget` and
`s4_per_ticket_budget` are asserted against the literal figures
`tiers.yaml` holds, so a wrong number in the file or a wrong lookup key in
the code each fail on their own.

`test_reliability_view.py` seeds one `stage_run` and asserts its own
fields come back through the view unchanged, and separately seeds one
`utility_run` of each kind in `UTILITY_KINDS` with no `stage_run` present,
asserting the view is empty — so the view's exclusion of `utility_run` is
tested by construction (selecting from `stage_run` alone) rather than by a
`WHERE` clause a future edit could accidentally drop.

`test_stub_stages.py`, `test_state_table.py`, and `test_cli_skeleton.py`
are unchanged and pass against the refactored `run_stage`, which is the
check that the ledger refactor preserved `run_stage`'s observable
behaviour exactly.
