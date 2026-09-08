# T-A-11 brief: measure views, the report, the context label

## What this delivers

The eighteen named SQL views `06-observability.md`'s Measure computations
table lists, the manifest-cohort and dedicated baseline helper views, and
the one script that reads any of them:

- `runner/schema.py` — `VIEWS` grows from one entry (the unnarrowed
  `stage_reliability_view`) to twenty: the eighteen measure views in the
  Measure computations table's own order, `v_ticket_manifest_cohorts` (the
  helper that resolves a ticket's manifest_hash for every ticket-grained
  view), and `v_baseline_revisions_per_ticket` (the dedicated baseline
  view). `stage_reliability_view` is narrowed in place to the first-attempt
  rule rather than replaced by a second view.
- `runner/db.py` — `USER_VERSION` bumped from 6 to 7.
- `factory/scripts/tools/report` — a standard-library-only script,
  structured like `manifest_hash`: no import of `runner`. It prints a
  header (database path, window, manifest hashes spanned), the primary
  panel (the thirteen non-context measures, unranked, each stating its own
  window), and a `context` block (the five context measures, each line
  labelled `[context]`), and ends by stating the proposal schema's absence.
  A measure whose view returns nothing prints `status: unavailable` and a
  `reason:` line instead of a number. `primary_measures()` and
  `context_measures()` expose the driving `(title, view, grouping columns)`
  table as data, so a caller (or a test) can check which list a view is in
  without parsing report text.
- `runner/cli.py` — a `report` subparser with the same `--manifest-hash`,
  `--window-days`, `--until` arguments, and a thin `report(db_path, ...)`
  function that runs the script as a subprocess and returns its stdout. No
  other line in this file changed.
- `factory/evals/scripts/tools/report/eval.yaml` and its `fixtures/`: a
  completed stub walk, an unavailable measure, a baseline-only ticket, a
  context cost row, and a rejection case (a database with no views at all).
- `runner/tests/test_views.py`, `runner/tests/test_report.py`, and an
  updated `runner/tests/test_reliability_view.py` (the narrowed shape; the
  utility-run exclusion test is unchanged).

## Rows covered

R-O-4, R-O-5, R-O-12 (`docs/prd/06-observability.md`): every measure the
report or the graduation gate reads is a named SQL view over the record;
factory-performance views exclude `baseline` tickets and accept a
`manifest_hash` filter; a migrated ticket is reported in both version
cohorts with the boundary visible; the report is the only reader of the
views and enforces windowing, an unranked primary panel, a labelled context
block, and an unavailable-status display instead of an invented number; no
view exists for a per-person breakdown, PR share, or savings estimate; and
cost, tickets-closed-per-window, and non-structural touchpoints are
context, never usable by a scorer or the (absent) proposal schema.

## The manifest-cohort rule, stated once

`ticket.factory_manifest_hash` is the pinned hash, changed in place only by
a human-approved migration; every `stage_run.manifest_hash` records the
manifest that specific run actually ran under. A ticket belongs to every
cohort it has stage runs under: `v_ticket_manifest_cohorts` groups a
ticket's stage runs by their own `manifest_hash`, one row per
`(ticket_id, manifest_hash)` pair actually observed, falling back to the
ticket's own pinned `factory_manifest_hash` only when it has no stage runs
yet. A ticket migrated mid-flight therefore surfaces once per manifest it
ran under, with `first_run_started_at`/`last_run_started_at` making the
migration boundary visible rather than attributing the ticket wholly to
one version. Every view built from `question`, `tag`, `queue_item`, or
`generated_test` rows (which carry no `manifest_hash` of their own) joins
through this helper to get one. A view built directly from `stage_run`
rows (cost, tool calls, fix rounds, stage reliability) reads that run's own
`manifest_hash` column instead, since it is authoritative for the run that
produced it and needs no cohort lookup.

## Owner decisions this ticket follows

- One script is the only reader of the views (R-O-5): a test scans every
  `.py` file under `runner/` (except `schema.py` and `runner/tests/`) and
  every file under `factory/scripts/` for the eighteen names plus
  `stage_reliability_view`, and asserts only the report script matches.
- Every factory-performance view carries a `manifest_hash` column a caller
  filters with a plain `WHERE manifest_hash = ?`; the two dedicated
  baseline views read only `baseline_measure` and carry none.
- The forbidden-view rule (no per-person breakdown, no PR share, no
  savings estimate, no cost-per-PR) is enforced by a schema-level test over
  `VIEWS`' SQL text and names, not by convention alone.
- Queue latency views are computed exactly as `AVG((julianday(resolved_at)
  - julianday(queued_at)) * 86400)`, grouped by manifest, stage and tier,
  and labelled `queue_latency_seconds`; active attention is read only from
  `approval_record.active_attention_bucket`, grouped separately, and never
  derived from a latency value.
- `pr_outcome` queue items are excluded from `v_ctx_non_structural_touchpoints`
  by the `kind IN ('question', 'red_check', 'escalation')` filter, and from
  every attention view by construction (attention views read
  `approval_record`, never `queue_item`, at all).

## Decisions this brief did not already settle

- **A question's tier.** `question` carries no `tier` column of its own;
  the Measure computations table asks for "questions surfaced per ticket,
  by tier" using "the tier on the question's `queue_item`". The schema's
  `queue_item.ref` is polymorphic and the `question_set` grouping table it
  can name for a round of blocking questions does not exist yet (out of
  scope here). `v_questions_per_ticket` therefore joins a `question` to the
  `queue_item` whose `kind = 'question'` and whose `ref` equals the
  question's own id as text — correct for one question, one item, and
  revisited once `question_set` exists.
- **Production incidents attributable, and coverage, as one view.** The
  Measure computations row combines two shapes at different grains: an
  attributable-incident count by severity and disposition, and every
  merged ticket's latest coverage status. Scope In names exactly one view,
  `v_production_incidents_attributable`, for the whole row, so it carries
  both shapes with a `record_type` discriminator (`incident` or
  `coverage`) rather than splitting into a second, unlisted view.
- **Fix rounds and "the recipes that failed before each fix round".** The
  schema has no column naming which recipe failed before an S4 fix round
  (that association is not yet a stored field on `stage_run` or a sibling
  table). `v_ctx_fix_rounds_per_ticket` reports the count the Measure
  computations row asks for; the per-recipe detail is left to whichever
  later ticket adds that column, rather than invented here as a text blob.
- **Reconciliation share's "reconstruction" tag lookup.** A
  `packet_defect` tag with `fm_id = FM-10` names the affected
  `approval_record` directly through `ref` (the entity definition states
  this explicitly, unlike most polymorphic `ref` uses), so the join is a
  plain `ref = CAST(approval_record.id AS TEXT)` rather than a lookup
  through the record's shared queue item.
- **Plan-approved-without-redirect's "subject-bound send-back".** Read as:
  a `send_back` tag whose `ref` names one of the first plan subject's own
  `approval_record` rows. No `send_back` tag in the fixtures points
  anywhere else, so this is the narrowest reading that satisfies the
  Measure computations sentence without inventing a second ref shape.
- **Baseline measure name.** `baseline_measure.measure` is free text; the
  gate-compared measure needs one fixed string so the dedicated baseline
  view can filter on it. `schema.BASELINE_REVISIONS_MEASURE` is that
  constant (`"revisions_per_ticket_after_plan_approval"`), defined once so
  the view and any future writer of `baseline_measure` share it rather than
  each hand-copying the string.
- **Window filtering on already-aggregated views.** Views are plain SQL
  with no bound parameters, so a manifest filter is a `WHERE` clause the
  caller supplies, but a *date* window over an aggregate that already
  spans all time cannot be re-scoped after the fact. The report states its
  window on every measure block (literally satisfying "every growth figure
  states its window") and additionally re-filters the one view that
  carries its own timestamps in the row (`v_ctx_completions_outcomes_per_window`)
  to the requested window in Python. The other seventeen views report
  their full history; narrowing them to a rolling window is left to
  whichever later ticket adds a time-bounded variant.
- **Report's database access.** The report opens a plain read-write
  `sqlite3.connect`, exactly like `manifest_hash`, rather than a URI
  `mode=ro` connection: SQLite's WAL mode can require write access to a
  `-shm` file even for a reader, and the report's own contract (never
  writing) is enforced by never issuing anything but `SELECT`, not by the
  connection flag.

## Out of scope

The frozen retrospective and supplemental baseline cohort itself (AB); the
`proposal` table (Later; its absence is the explicit behaviour tested
here); a graphical dashboard (Later); `runner/gates.py`,
`runner/run_ledger.py`, `runner/stages/*`, `runner/transitions.py`,
`runner/state_table.py`, and `factory/config/*`, all untouched by this
ticket; every line of `runner/cli.py` other than the `report` subparser,
its dispatch branch, and the `report` function.
