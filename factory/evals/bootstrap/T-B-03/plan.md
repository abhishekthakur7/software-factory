# T-B-03 plan

## Steps

| # | Step | Files touched | Proves |
|---|---|---|---|
| 1 | `graduation.window`: the candidate set (non-baseline, `merged`/`abandoned`, closed in `[start, cutoff]`), `start` as the later of the prior graduate-approve `decided_at` and the newest remediation of a severe attributable incident, and the open-incident reset. | `runner/graduation.py` | `test_graduation_window.py` (criteria 17-22) |
| 2 | `graduation.acceptance_gates`, `exposure_coverage`, `incidents`: the latest `gate`-kind `utility_run`'s outcome and a completed window ticket; per-merged-ticket exposure and coverage-through-cutoff; severe attributable events and disposition completeness. | `runner/graduation.py` | `test_graduation.py` (criteria 14, 15), `test_graduation_clauses.py` (criteria 23-26) |
| 3 | `graduation.stage_reliability`: `stage_reliability_view` summed over tiers per stage, the first-attempt floor and pass-share threshold, and the excluded-outcome counts reported separately. | `runner/graduation.py` | `test_graduation_clauses.py` (criteria 27, 28) |
| 4 | `graduation.baseline_revisions`: the window's mean post-plan revisions from `v_revisions_per_ticket_by_fm` against the mean of comparable `v_baseline_revisions_per_ticket` rows, the comparable-count floor, and the mechanically-tagged-decision refusal. | `runner/graduation.py` | `test_graduation_clauses.py` (criteria 29-32) |
| 5 | `graduation.control_defects`, `blind_spots`, `self_containedness`: open control-defect dispositions by category; unwaived blocking blind spots with no later pass; unresolved FM-10 packet defects over `decision_supported_without_transcript = 0` decisions. | `runner/graduation.py` | `test_graduation_clauses.py` (criteria 33-35) |
| 6 | `graduation.evaluate`: opens the `graduation`-kind `utility_run`, runs all nine clauses, assembles the report (thresholds, hashes, `clauses`, `views_read`, the `context` block of the five `v_ctx_` views), writes it as canonical JSON, registers the `graduation_report` artefact, and finishes the run by `passed`. | `runner/graduation.py` | `test_graduation.py` (criteria 1-4), `test_graduation_clauses.py` (criteria 36-38) |
| 7 | `graduation.approve`/`reject`/`quorum`: the ordered refusals, the subject hash binding the report/thresholds/configuration, the `factory_owner` slot and identity snapshot, and the supersedes-on-repeat rule. | `runner/graduation.py` | `test_graduation.py` (criteria 5-13) |
| 8 | `runner/run_ledger.py`: `open_utility_run` grows an optional `manifest_hash` keyword. `runner/gate.py`: every run opens and finishes one `gate`-kind `utility_run` at a new `--db` argument, `manifest_hash` set to the adoption hash or null. | `runner/run_ledger.py`, `runner/gate.py` | `test_graduation.py` (criterion 16), `test_gate.py`/`test_gate_ab.py` (unchanged, still green) |
| 9 | `runner/cli.py`: a `graduate` subparser block (`evaluate`, `approve`, `reject`) next to the existing `report` parser, and its three dispatch branches. | `runner/cli.py` | exercised through `graduation.py`'s own functions; no new CLI-level test file, matching how `migrate-manifest` and `waive` are covered |
| 10 | `runner/tests/fixtures/graduation/seed.py`: the shared seeding helper (window tickets, coverage, incident events and dispositions, control-defect events and dispositions, tags, stage runs, check results, approval records, gate runs, baseline measures, a temporary `limits.yaml`). | `runner/tests/fixtures/graduation/seed.py` | used by every test in the three files above |
| 11 | This ticket's own brief and plan, synced into `factory/evals/bootstrap/T-B-03/` by `tools/bootstrap_fixtures.py`, and `factory/manifest.yaml` refreshed to match. | `docs/build/T-B-03/brief.md`, `docs/build/T-B-03/plan.md`, `factory/evals/bootstrap/T-B-03/`, `factory/evals/bootstrap/eval.yaml`, `factory/manifest.yaml` | `test_bootstrap_fixtures.py`, `test_manifest_hash.py` |

## Test strategy

Every test opens its own `tmp_path` database (`runner.db.connect`) and
seeds rows through `record.insert` via the shared `seed.py` helpers,
never through `factory act` or a stub walk. `test_graduation.py` covers
`evaluate`'s own mechanics (the `utility_run`, the artefact, the report's
top-level shape), `approve`/`reject`/`quorum` (the subject hash, the slot,
the four ordered refusals, the supersedes rule), the two acceptance-gates
sub-conditions, and `runner/gate.py`'s own recorded run.
`test_graduation_window.py` isolates `graduation.window` against a fixed
`cutoff`, never wall-clock `now()`, covering the candidate filter, the
`start` computation from a prior approval and a remediation, the fresh-
window and incident-reset cases, and the window-size floor.
`test_graduation_clauses.py` calls each remaining clause function
directly with a hand-built ticket list, covering every one of criteria 23
through 35, the tagged-control test parametrized over the five control
categories, the report's `context` block and `views_read` list, and the
invariance test (seeding behind `v_default_shown_share`,
`v_default_accepted_share`, `v_plan_approved_no_redirect_share`, and the
context views, asserting every clause's `passed` is unchanged).
`test_graduation.py::test_gate_main_records_a_utility_run_of_kind_gate...`
builds a small committed repository the same way `test_gate.py` does and
asserts the new `--db` argument's row directly, rather than duplicating
`test_gate.py`'s own pass/fail coverage.

None of the three files' tests run the stub walk or read the pilot
ticket's own record; every window is built by hand for exactly the
clause under test.

## Verification

`set -o pipefail; uv run pytest -q runner/tests 2>&1 | tail -20` run in
the foreground; see the ticket's final report for the pass/fail/skip
counts actually observed on this worktree.

## Deviations from the brief

- The ticket's "Exposure/coverage" clause-rule prose covers what COMMON.md's
  function list splits into two functions, `exposure_coverage` and
  `incidents`; see brief.md's "Decisions this brief did not already
  settle".
- `self_containedness`'s verdict is derived from `approval_record`/`tag`
  directly rather than from `v_reconstruction_share_by_gate`, which is
  read into the clause's `inputs` for its aggregate rows only, since the
  view's own grouping cannot answer a per-approval-record question; see
  brief.md for the reasoning.
