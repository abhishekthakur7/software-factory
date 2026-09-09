# T-B-03 brief: graduation

## What this delivers

`runner/graduation.py` (new): the canonical graduation report, its clause
functions, and the recorded owner approval that binds it.

- `evaluate(conn, *, cutoff=None, limits_path=..., manifest_hash=None,
  runs_dir=..., now=None) -> int` opens a `utility_run` of `kind =
  'graduation'`, computes a candidate window and nine clause verdicts,
  writes one `graduation_report` artefact as canonical JSON, and finishes
  the run `pass` only when every clause passed.
- Nine clause functions -- `window`, `acceptance_gates`,
  `exposure_coverage`, `incidents`, `stage_reliability`,
  `baseline_revisions`, `control_defects`, `blind_spots`,
  `self_containedness` -- each returning `{"passed", "inputs",
  "reasons"}`, reading `stage_reliability_view`,
  `v_revisions_per_ticket_by_fm`, `v_production_incidents_attributable`,
  `v_reconstruction_share_by_gate` and `v_baseline_revisions_per_ticket`
  where a view covers the clause, and the record directly (tags, waivers,
  check results, approvals, incident observations) where none does.
- `approve`/`reject(conn, report_artefact_id, *, actor, config_path,
  config_hash, ...)` write the one `approval_record` a graduation decision
  is, refusing (`GraduationRefused`) an unknown report, a non-owner actor,
  a mismatched configuration, a moved manifest hash, or (approve only) a
  report that did not pass; a repeat decision on the same subject
  supersedes its own prior head. `quorum(conn, report_artefact_id) ->
  bool` asks `approvals.evaluate` the same question every other gate asks.
- `runner/cli.py`: a `graduate` subcommand with `evaluate`, `approve`, and
  `reject` subparsers, added as one block near the existing `report`
  parser.
- `runner/gate.py`: every run now opens and finishes one `utility_run` of
  `kind = 'gate'` at a new `--db` argument (default `<root>/runs/
  factory.sqlite`), `manifest_hash` set to the adoption record's hash or
  null when that step itself failed.
- `runner/run_ledger.py`: `open_utility_run` grows an optional
  `manifest_hash` keyword, the same column `stage_run` already carries,
  so `runner/gate.py` can set it without a second write path.
- `runner/tests/test_graduation.py`, `test_graduation_window.py`,
  `test_graduation_clauses.py`, and `runner/tests/fixtures/graduation/
  seed.py`, a shared seeding helper every graduation test builds its
  window through.

## Rows covered

R-O-13 (`docs/prd/06-observability.md` and `02-3-ticket-states.md`):
graduation is a recorded owner decision against a canonical report, never
automatic; the report holds the window, the thresholds and their hash,
the evaluated configuration's hash, and every clause's inputs and
verdict; the window excludes context measures and resets only after a
severe attributable incident's remediation lands; the acceptance-gates
clause reads the factory's own last recorded `gate` run; exposure and
coverage, incident disposition completeness, stage first-attempt
reliability, the baseline revision comparison, open control defects,
unresolved blind spots, and self-containedness each get their own clause;
the report is the only reader of `v_reconstruction_share_by_gate` and
`v_production_incidents_attributable` this ticket adds a caller for.

## Owner decisions this ticket follows

- The nine clause functions are exactly the ones COMMON.md names, in that
  order, each returning the same three-key shape so the report's
  `clauses` block never needs a fourth format.
- The report's `views_read` list is the five views the ticket names,
  computed as a fixed module constant and genuinely queried by the
  clauses that use them (`stage_reliability` for `stage_reliability_view`;
  `baseline_revisions` for `v_revisions_per_ticket_by_fm` and
  `v_baseline_revisions_per_ticket`; `exposure_coverage` and `incidents`
  for `v_production_incidents_attributable`; `self_containedness` for
  `v_reconstruction_share_by_gate`) -- never `v_default_shown_share`,
  `v_default_accepted_share`, `v_plan_approved_no_redirect_share`, or any
  `v_ctx_` view, which the report's separate `context` block reads for
  information only.
- `approve`/`reject` share one function (`decision` is the only
  difference), matching `manifest.migrate`'s own convention of folding a
  human note into the attestation hash rather than giving `approval_record`
  a column it does not have.
- A second approval from the same actor on the same subject supersedes
  its own prior head (`approvals.current_heads`, matched by `slot_id` and
  `actor_identity`), the same guard `manifest.migrate` needs for a
  repeated migration approval.

## Decisions this brief did not already settle

- **Splitting "exposure/coverage" into two clause functions.** COMMON.md
  names nine clause functions including a standalone `incidents`, but the
  ticket's "Clause rules" section states the ticket-level coverage
  requirement and the incident-level severity/disposition requirement in
  one paragraph headed "Exposure/coverage". The two are different
  granularities -- one is about a merged ticket's own coverage row, the
  other about every production incident event tied to a window ticket --
  so they are two functions, `exposure_coverage` and `incidents`, matching
  COMMON.md's function list rather than the prose's paragraph break.
- **`v_production_incidents_attributable`'s two record shapes.** Its
  `coverage` rows carry `ticket_id` and serve `exposure_coverage`
  directly. Its `incident` rows are pre-aggregated by severity,
  attribution and disposition with `ticket_id` always null (the view
  groups across every ticket at once), so they cannot answer "which
  window ticket's event is this" on their own. `incidents` reads the view
  for its aggregate rows (carried into the clause's own `inputs` for
  transparency) and derives its actual per-event verdict from
  `incident_observation` directly, scoped to the window's ticket ids --
  the "direct table read where no view covers the clause" COMMON.md
  allows.
- **The blind-spot clause's "the covering approval's decided_at".** A
  `check_result` names its `evidence_tuple_id`; the review `approval_record`
  whose own `evidence_tuple_id` matches it is that check's covering
  decision, so its `decided_at` is the reference time `waivers.validity`
  reruns at. A check result bound to no review tuple at all (no covering
  approval exists yet) falls back to the report's own `cutoff`, so the
  clause still has a defined answer rather than raising.
- **`self_containedness`'s use of `v_reconstruction_share_by_gate`.** The
  view is grouped by `(manifest_hash, gate, tier, role, decision, bucket)`,
  losing the individual `approval_record` id a per-decision pass/fail
  needs and never carrying `decision_supported_without_transcript` at
  all. The clause's verdict is derived from `approval_record` and `tag`
  directly; the view is read into the clause's `inputs` as the
  reconstruction-share rows for the window's gates, satisfying "reads the
  record through the view where one exists" without asking the view a
  question its own grouping cannot answer.
- **`quorum`'s subject.** `approvals.evaluate` needs one subject hash, but
  a report can in principle be evaluated for approval against different
  proposed configurations, each its own subject. `quorum` reads the
  subject off the newest recorded `approval_record` naming the report in
  its `evidence_ids`; every repeat decision on one configuration shares
  that subject already (the point of the `supersedes` rule above), so
  this answers "is the gate's own quorum met right now" for the decision
  actually on record, without re-deriving a configuration `quorum` itself
  is never given.
- **`runner/gate.py`'s own database write.** The ticket asks for a new
  `--db` argument defaulting to `<root>/runs/factory.sqlite`; `--root`
  already defaults to this repository's own root, so the default resolves
  to the real run database exactly where every other `factory` command
  writes, with no separate constant to keep in sync.

## Out of scope

The parallel-limit raise that reads a graduation approval (T-B-04);
`runner/stage_interface.py`'s export of `graduate_evaluate`/
`graduate_approve` (T-B-05); the manual outcome, exposure, coverage and
incident rows the window reads (T-B-01, already committed); the closing
run's criterion 40, added later to `runner/tests/test_pilot_walk.py` by
another builder; `runner/schema.py`, `runner/db.py`,
`factory/config/limits.yaml`'s `graduation` keys (read only), and every
other file this ticket's Scope Out already names.
