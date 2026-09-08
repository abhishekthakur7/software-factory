# T-A-16 plan

## Steps

| # | Step | Files touched | Proves |
|---|---|---|---|
| 1 | `imported_from` nullable column added to `ticket` and `artefact`; `USER_VERSION` bumped. | `runner/schema.py`, `runner/db.py` | criterion 12 |
| 2 | `export_ticket(conn, ticket_id, ...)`: gathers rows across the thirteen exported tables (joining `tool_call`/`check_result` through `stage_run`/`evidence_tuple` ids), decides the whole-export guard operation, writes `rows/<table>.json` and `artefacts/<id>/<basename>` each behind its own guard decision, writes `branch.patch` via `git diff base_sha..head_sha` from the ticket's own clone (empty when there is no branch), and writes `manifest.json` with the declared file list and content hash, registering it as an `export` artefact. | `runner/export.py` | criteria 1, 2, 3, 4, 5, 6 |
| 3 | `import_export(conn, export_dir, ...)`: verifies the manifest's content hash, every declared file's hash and path safety, and the absence of an undeclared file; checks every row-id collision up front; inserts every row with its original id (marking `ticket`/`artefact` rows `imported_from`) inside one transaction with foreign keys deferred, committing or rolling back itself. | `runner/export.py` | criteria 7, 8, 9, 10, 11, 12 |
| 4 | `purge_export(conn, export_dir, ...)`: opens a `utility_run` of kind `purge`, refuses (recording the outcome) when `retention_until` is still ahead, else `fs.remove_tree`s the directory and records `pass`. | `runner/export.py` | criterion 13 |
| 5 | `export`, `import`, `purge` verbs wired into `main`'s argument parser and dispatch, calling `runner.export` directly. | `runner/cli.py` | criteria 1, 7, 13 (exercised end to end) |
| 6 | Standalone entry-point scripts, importing `runner.export` since the operations are trusted-control-plane writes, not read-only summaries. | `factory/scripts/tools/export`, `factory/scripts/tools/import`, `factory/scripts/tools/purge` | criteria 1, 7-12, 13 |
| 7 | Eval directories in `report`'s declarative shape: one `ok` case for export (a README pointing at the test file, since a flat seed list cannot express an activated trust profile); one `ok` and five `reject` cases for import, each fixture a real export directory with exactly one defect; one `ok` and one `reject` case for purge. | `factory/evals/scripts/tools/export/**`, `factory/evals/scripts/tools/import/**`, `factory/evals/scripts/tools/purge/**` | criteria 1, 7-12, 13 |
| 8 | The fixture trust profile and owners file every export test activates. | `runner/tests/fixtures/export_import/trust-profile.yaml`, `runner/tests/fixtures/export_import/owners.yaml` | supports criteria 1-6, 14 |
| 9 | `test_export_import.py`: one or more titled tests per criterion, `must_reject` naming on every negative case. | `runner/tests/test_export_import.py` | criteria 1-14 |
| 10 | Every new `factory/` file's `content_hash` added; the stale duplicated `content_hash:` line under `trust-profile.yaml` removed. | `factory/manifest.yaml` | manifest-hash tests |
| 11 | This ticket's own brief and plan. | `docs/build/T-A-16/brief.md`, `docs/build/T-A-16/plan.md` | reviewed by the human, not a test |

## Test strategy

`profile_paths`/`_activate` copy the fixture trust profile and owners file
into `tmp_path` and satisfy governance quorum through the real
`governance.propose`/`decide`, exactly like `test_guard.py` and
`test_outbox.py`, so a wrong quorum computation fails these tests too.
`_seed_ticket` opens a ticket then moves it to `review` (`open_ticket`
always opens in `intake`); `_seed_full_ticket_rows` seeds one row in every
exported table besides `ticket`/`artefact` with free-form `content_hash`
strings, matching `test_freshness.py`'s and `test_outbox.py`'s own
`content_hash="plan-1"`-style seeding.

Every malicious-import test (criteria 7-11) starts from a genuinely valid
export `export_ticket` produced, then introduces exactly one defect --
renaming a declared key to an absolute or traversal path, adding a
symlinked entry that resolves outside the directory, dropping an
undeclared file into the tree, or tampering a file's bytes after export --
recomputing `manifest["content_hash"]` after every mutation except the
byte-tamper case, so each test proves the one check named in its title
refuses rather than an incidental hash mismatch a hand-built manifest
would also trip.

Criterion 6 seeds one artefact whose text contains an `AKIA...` key
matching `secret_rules` and a second artefact registered against a
directly-inserted `guard_decision` row of `decision = 'deny'`; the test
asserts both artefact ids land under `manifest.json`'s `excluded.artefacts`
and that neither the key nor the disallowed text appears in any file under
the export directory.

Criterion 14's round trip exports a ticket, imports it into a second,
empty connection, activates the same trust profile there, exports again,
and compares each of `artefact.hash`, `evidence_tuple.content_hash`,
`approval_record.content_hash`, `reviewer_set.content_hash`,
`waiver.content_hash` and `check_result.content_hash` by row id between
the two exports' `rows/<table>.json` -- the fields that already existed on
those rows before export, which import must carry through unchanged.

## Verification

`uv run pytest -q`
