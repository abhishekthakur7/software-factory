# T-A-16 brief: governed export, import and purge

## What this delivers

The governed record's one hand-over format: `factory export`, `factory
import` and `factory purge`, each a thin wrapper over a function in
`runner/export.py`, plus standalone entry-point scripts under
`factory/scripts/tools/` for the same three operations. Export writes one
directory per ticket holding its permitted rows, artefacts, guard
decisions and its branch as a patch; every crossing out of the record --
the export as a whole, then separately every table's row file and every
artefact file -- goes through the guard's `governed_export_display` route,
so a credential or a raw disallowed payload can never leave the record. A
deny on the whole export refuses before anything is written; a deny on one
item excludes only that item and records why under `manifest.json`'s
`excluded` list. Import recomputes every declared file's hash and the
manifest's own content hash before trusting any of it, refuses an absolute
path, a traversal segment, a symlink escaping the export directory, or an
undeclared file, and only then inserts rows -- preserving their original
ids -- inside one transaction, so a refusal leaves the target record
untouched. Purge deletes an export directory once its recorded retention
has passed and refuses otherwise, recording the outcome either way on a
utility run.

- `runner/export.py` (new) -- `export_ticket`, `import_export`,
  `purge_export`: the three public functions this ticket's scope names as
  one module, since they share the export directory's layout and its
  manifest reading.
- `runner/cli.py` -- `export`, `import`, `purge` verbs added to `main`'s
  argument parser and dispatch, each calling straight into
  `runner.export`, matching how `queue`/`act`/`abandon`/`refresh-base`/
  `tag` are dispatched today (no separate `cli.py`-level wrapper
  function).
- `runner/schema.py` -- a nullable `imported_from` column on `ticket` and
  `artefact`, holding the exporting record's content hash and null on
  every native row; neither column is `mutable`, since import sets it at
  insert time and it never changes afterward.
- `runner/db.py` -- `USER_VERSION` bumped for the schema change.
- `factory/scripts/tools/export`, `factory/scripts/tools/import`,
  `factory/scripts/tools/purge` (new) -- thin argparse entry points in
  `report`'s idiom, each importing `runner.export` directly rather than
  staying standalone: unlike `report`/`manifest_hash`/`impact_scan`, which
  avoid `runner` because they summarise or verify the trusted control
  plane's own artefacts without needing agent-reachable code, export,
  import and purge are themselves trusted-control-plane operations gated
  by the guard -- reimplementing that gate standalone would mean a second,
  divergent copy of it.
- `factory/evals/scripts/tools/export/`, `factory/evals/scripts/tools/import/`,
  `factory/evals/scripts/tools/purge/` (new) -- `eval.yaml` plus
  `fixtures/`, matching `factory/evals/scripts/tools/report/`'s shape.
- `runner/tests/test_export_import.py` and
  `runner/tests/fixtures/export_import/` (new) -- the fixture trust
  profile and owners file every export test activates, the same
  `profile_paths`/`_activate` convention `test_guard.py` and
  `test_outbox.py` use.
- `factory/manifest.yaml` -- every new `factory/` file's `content_hash`
  added, and the pre-existing stale duplicated `content_hash:` line under
  `factory/config/trust-profile.yaml` removed.

## Row covered

R-T-4 (`docs/prd/02-1-ticket-record.md` line 16): the governed record is
exportable as a single directory of permitted rows, artefacts, guard
decisions, reviewer/approval/waiver sets, evidence tuples, incident
observations, external-write receipts and the branch as a patch; export
requires an allowed R-T-9 route and guard decision, inherits
classification and retention, records its hash, and excludes credentials
and raw disallowed payloads; import verifies the export hash, rejects
absolute paths, traversal, escaping symlinks and undeclared files, and
marks imported prose as untrusted input.

## Owner decisions this ticket follows

- **Layout.** `<runs_dir>/exports/<ticket_id>/<export_id>/` holding
  `manifest.json`, `rows/<table>.json` (one array per exported table, all
  thirteen always written even when empty), `artefacts/<artefact_id>/<basename>`,
  and `branch.patch`.
- **Tables exported**, in the fixed order `ticket`, `stage_run`,
  `tool_call`, `artefact`, `guard_decision`, `reviewer_set`,
  `approval_record`, `waiver`, `evidence_tuple`, `incident_observation`,
  `external_write`, `check_result`, `tag`. Each row is written as an
  envelope of `data_class`/`redaction_state`/`retention_until` plus the
  row itself; `artefact` (and, for `data_class` alone, `ticket`) supplies
  those columns from its own row, every other table inherits the ticket's
  `data_class`, a null `redaction_state`, and a `retention_until` computed
  from the route's `retention_days` at export time.
- **Guard.** One decision authorises the export as a whole over
  `governed_export_display` with `input_classes = (ticket.data_class,)`
  and a metadata payload drawn only from the route's own field names
  (`ticket_record`, `artefacts`) -- never content -- so an admitted class
  with no secret in that metadata decides `allow`. A deny refuses the
  whole export before anything is written. A second decision per item --
  each table's row-file text and each artefact's file text -- runs on the
  same crossing and route; a deny excludes only that item.
- **Import** verifies the manifest's content hash against its own
  declared file list, then every declared file's hash against its actual
  bytes, rejects an absolute declared path, one with a `..` segment, or
  one whose resolved real path escapes the export directory, and rejects
  an undeclared file present in the directory. Only after every check
  passes does it check for a row-id collision in every table (refusing
  before any write), then inserts every row with its original id inside
  one transaction with `PRAGMA defer_foreign_keys = ON` (needed because
  `artefact.guard_decision_id` and `guard_decision.redacted_artefact_id`
  can reference each other), committing itself rather than leaving that
  to the caller -- the one function in this ticket that owns its own
  transaction, since "a refusal leaves the record untouched" needs the
  FK-deferred commit's own possible failure caught here, not surfaced
  later at some unrelated caller's `commit()`.
- **Purge** opens a `utility_run` of kind `purge`, refuses when
  `manifest.json`'s `retention_until` is in the future (parsed via
  `datetime.fromisoformat`, not compared as strings), otherwise
  `fs.remove_tree`s the directory; records the outcome either way.

## Decisions this brief did not already settle

- **`export_id` is a random hex token (`uuid.uuid4().hex`)**, not a
  sequence number: export creates no `stage_run`/`utility_run` of its own
  to derive one from (only `purge` opens a utility run, per scope), and a
  ticket may be exported more than once.
- **`export_ticket` takes `profile_path`/`owners_path` parameters**
  (defaulting to the committed `factory/config/` files), threaded to every
  `guard.decide` call and to `trust_profile.load_trust_profile`, the same
  way `outbox.dispatch` does -- needed so tests activate a tmp copy of the
  fixture profile instead of the real one, exactly like `test_outbox.py`
  and `test_guard.py` already do. `import_export`/`purge_export` take no
  such parameters: neither calls the guard.
- **`check_result` and `tool_call` carry no `ticket_id` of their own.**
  `tool_call` is gathered by joining through the ticket's `stage_run` ids;
  `check_result` (which can carry a null `stage_run_id`, e.g. a freshness
  refusal recorded before any stage run) is gathered by joining through
  both the ticket's `stage_run` ids and its `evidence_tuple` ids (via
  `plan_tuple_id`/`evidence_tuple_id`), since those are the only two ways
  a `check_result` row is ever tied back to a ticket.
- **The round-trip criterion is read literally as "every hash on the rows
  themselves"**, not the export directory's own file-content hashes: the
  latter would spuriously differ between the two exports whenever a table
  without its own `retention_until` column recomputes that fallback value
  against a different `now`. The test compares each table's `content_hash`
  or `hash` field, by row id, between the first and second export's
  `rows/<table>.json`.
- **An artefact excluded by the guard keeps its row envelope in
  `rows/artefact.json`** (metadata, not content) but writes no file under
  `artefacts/`; import copies a file only when one is present for that
  artefact id, leaving the row's `path` as recorded when none is (the row
  still exists as audit metadata even though its content never travelled).
- **The write barrier.** Every write in `runner/export.py` goes through
  `runner.fs`'s `write_text`/`write_bytes`/`remove_tree`, called as bare
  imported names (`from runner.fs import write_text`) rather than
  `fs.write_text(...)`: `test_write_barrier.py`'s scanner flags any
  `.write_text`/`.write_bytes` *attribute* call regardless of receiver, so
  the funnel functions must be imported and called by their bare name.

## Out of scope

Real per-stage agent logic; `factory pause`/`resume`/`stop`/`show`
(T-A-17); the eval harness that would actually execute `eval.yaml`'s
cases (this ticket only adds eval directories in the established
declarative shape, matching `factory/scripts/tools/report`'s and
`factory/scripts/checks/impact_scan`'s); a real deliverer for
`governed_export_display` (it stays a stub route in the trust profile,
unchanged by this ticket).
