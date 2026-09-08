# T-A-03 plan

## Steps

| # | Step | Files touched | Proves |
|---|---|---|---|
| 1 | Add mutability to `Column`: `mutable` (updatable in place) and `once=<sentinel>` (updatable in place exactly once, as the group of columns naming the same sentinel). Mark the named mutable-exception fields on `ticket`, `stage_run`, `queue_item`, `question`, `external_write`; leave every other column at its default (immutable). | `runner/schema.py` | `test_mutable_exceptions.py` criteria 15-21 |
| 2 | `ddl()` emits, per table, one `BEFORE UPDATE OF <every immutable column>` trigger that always aborts, and one `BEFORE UPDATE OF <group columns> WHEN OLD.<sentinel> IS NOT NULL` trigger per once-group. | `runner/schema.py` | `test_append_only.py`, `test_mutable_exceptions.py` |
| 3 | Bump the schema version since `ddl()` now creates triggers and four tables gained `updated_at`. | `runner/db.py` | existing reconnect/idempotency test still passes against the new schema |
| 4 | Add `updated_at` to the hand-written expected field lists for the four tables that gained it. | `runner/tests/test_db_schema.py` | field-presence tests stay accurate against the new schema |
| 5 | Append-only tests: one artefact-versioning test (supersedes chain, version increment, prior row unchanged, mismatched-supersedes refusal) and one `must_reject` in-place-edit test per append-only table, plus the assumption supersede/withdrawal pattern and the two question content-field rejections. | `runner/tests/test_append_only.py` | criteria 1-14 |
| 6 | Mutable-exception tests: one test per updatable-in-place group (ticket lifecycle, `question.state`, `stage_run` outcome/lease fields, `external_write` state fields), one first-succeeds/second-`must_reject` pair per once-group, the schema-wide allowlist sweep (hand-written per table, every column outside it rejected and every column inside it accepted), and the `record.update` timestamp-stamping test. | `runner/tests/test_mutable_exceptions.py` | criteria 15-21 |

## Test strategy

Every test opens its own `tmp_path` database through `runner.db.connect`,
never the real `runs/factory.sqlite`. The criterion-21 allowlist is typed
out by hand in the test file rather than imported from `runner/schema.py`,
for the same reason `test_db_schema.py`'s field lists are hand-written: an
allowlist test that reads its own allowlist from the module under test
cannot catch a mistake in that module. The set of columns to check per
table comes from the live database (`PRAGMA table_info`) so the sweep
covers every column that actually exists without duplicating the schema's
column lists. Every attempted `UPDATE` in the sweep sets its target column
to `NULL` on a freshly inserted row: SQLite's `UPDATE OF` fires because the
column is named, regardless of the value, so a single value works for
every column and type, and a fresh row per column keeps once-group columns
from contaminating each other's first-settlement check.
