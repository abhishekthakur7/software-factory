# T-A-02 plan

## Steps

| # | Step | Files touched | Proves |
|---|---|---|---|
| 1 | Declare the schema as data: frozen `Column`/`Table` dataclasses, `TABLES` (23 tables, PRD order), `ddl()` returning `CREATE TABLE IF NOT EXISTS` statements with typed columns, `NOT NULL` and `FOREIGN KEY` clauses. | `runner/schema.py` | `test_db_schema.py` field-presence tests (criterion 2) and the Later-table exclusion test (criterion 3) |
| 2 | `connect(path)`: create parent directory, open the file, set `journal_mode=WAL`, `foreign_keys=ON`, a busy timeout, `row_factory = sqlite3.Row`, run `ddl()`, set `user_version`. | `runner/db.py` | `test_db_schema.py` WAL/foreign-keys test (criterion 1) and the idempotent-reconnect test |
| 3 | `canonical_json()` (sorted keys, no whitespace, UTF-8, `ensure_ascii=False`, default JSON type rejection) and `content_hash()` (exclude `id`/`content_hash`/`created_at`, fold in `SERIALIZATION_VERSION`, SHA-256 of the canonical bytes). | `runner/canonical.py` | `test_canonical.py` |
| 4 | Schema tests: WAL mode, foreign keys on, per-table field presence (hand-written expected lists, not imported from `schema.py`), Later-table absence, idempotent reconnect. | `runner/tests/test_db_schema.py` | criteria 1, 2, 3 |
| 5 | Isolation test: populate `ticket`/`stage_run`/`artefact` in database A, open a fresh database B, assert B is empty and A is unchanged. | `runner/tests/test_db_isolation.py` | criterion 4 |
| 6 | Canonical-serialization tests: key-order independence, exclusion set, a bound-field change alters the hash, array order matters, non-ASCII round-trip, version participates in the hash, non-JSON value rejected. | `runner/tests/test_canonical.py` | orchestrator-added verification row |

## Test strategy

Every test opens its own `tmp_path` database; the real `runs/factory.sqlite`
is never touched by a test. `test_db_schema.py`'s field lists are written
out by hand from `docs/prd/02-2-entities.md` rather than imported from
`runner/schema.py`, so a typo or omission in the schema module cannot pass
by echoing itself. `test_canonical.py` treats `canonical.py` as a pure
function library and needs no database.
