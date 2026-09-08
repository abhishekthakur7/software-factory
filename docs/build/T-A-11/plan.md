# T-A-11 plan

## Steps

| # | Step | Files touched | Proves |
|---|---|---|---|
| 1 | `v_ticket_manifest_cohorts`: one row per `(ticket_id, manifest_hash)` a ticket's stage runs actually ran under, falling back to the ticket's pinned hash when it has none yet; baseline tickets excluded. | `runner/schema.py` | `test_views.py`'s dual-cohort and baseline-exclusion tests (criteria 1, 2) |
| 2 | The twelve non-reliability primary views and the five context views, each joining through the cohort helper (question/tag/queue_item/generated_test-derived) or reading `stage_run.manifest_hash` directly (stage_run-derived), computed per the Measure computations table. | `runner/schema.py` | `test_views.py`'s per-view value tests (criterion 3) |
| 3 | `stage_reliability_view` narrowed in place to `run_kind = 'task'`, `attempt = 1`, `parent_run_id IS NULL`, and the five first-attempt outcomes, grouped by manifest, stage and tier. | `runner/schema.py` | `test_reliability_view.py` (rewritten), `test_views.py`'s narrowed-outcome tests (criterion 4) |
| 4 | The two dedicated baseline/helper views (`v_ticket_manifest_cohorts` from step 1; `v_baseline_revisions_per_ticket` reading only `baseline_measure`, no manifest hash). `runner/db.py`'s `USER_VERSION` bumped 6 to 7. | `runner/schema.py`, `runner/db.py` | `test_views.py`'s baseline-view test (criterion 2) |
| 5 | `factory/scripts/tools/report`: `PRIMARY_MEASURES`/`CONTEXT_MEASURES` as data, `generate()` building the header/primary/context text, `_measure_block` printing a row or `status: unavailable` plus `reason:`, `main()` refusing a database missing a required view. | `factory/scripts/tools/report` | `test_report.py`'s conformance and refusal tests (criteria 7, 8, 9, 10, 12) |
| 6 | `runner/cli.py`: `report` subparser (`--manifest-hash`, `--window-days`, `--until`) and a thin `report()` function running the script as a subprocess. Every other line unchanged. | `runner/cli.py` | `test_report.py`'s `factory report` test |
| 7 | `factory/evals/scripts/tools/report/eval.yaml` and its five fixtures (a completed stub walk, an unavailable measure, a baseline-only ticket, a context cost row, a database with no views). | `factory/evals/scripts/tools/report/` | `test_report.py`'s eval-driven tests (criteria 8, 9, 10, 11, 12, 13) |
| 8 | The forbidden-view, only-reader-scan, and objective-rule tests. | `runner/tests/test_report.py` | criteria 6, 13 |
| 9 | `factory/manifest.yaml` updated with every new file's path and content hash. | `factory/manifest.yaml` | `test_manifest_hash.py` (deselected in this uncommitted worktree; see report) |
| 10 | This ticket's own brief and plan. | `docs/build/T-A-11/brief.md`, `docs/build/T-A-11/plan.md` | reviewed by the human, not a test |

## Test strategy

`test_views.py` opens its own `tmp_path` database per test, the same
convention as `test_reliability_view.py`. One shared `_seed_full_scenario`
fixture seeds every table the eighteen views read at once (a question with
its queue item and default-accepted answer, a revision and an escalation
tag, a kept generated test, an approved plan and review with an
unresolved `packet_defect` tag, a stale index-use row, two tool calls, an
attributable incident and a merged ticket's coverage row, and a
cost-bearing and a fix-round `stage_run`), and one parametrised test over
the eighteen view names checks each against its own expected subset —
avoiding eighteen near-identical test functions while still asserting a
value the implementation could get wrong for every one of them. Separate,
targeted tests cover baseline exclusion (the same scenario reseeded with
`baseline = 1`, asserting every one of the eighteen views comes back
empty), the dual-cohort migration (two `stage_run` rows under different
manifests), the `manifest_hash` filter, the dedicated baseline view's
`approximate`/`unavailable` visibility, the narrowed reliability rule's
excluded outcomes, and the four `ticket_id`-join rules, pinned against the
views' own SQL text.

`test_report.py` consumes `factory/evals/scripts/tools/report/eval.yaml`
the same way `test_manifest_hash.py` consumes its own: `OK_CASES`/
`REJECT_CASES` parametrise conformance tests that build a database per
fixture (`seed.yaml` rows through `record.insert` for the static fixtures;
the completed-walk fixture is built with the real `runner.stages.run_stage`
and `runner.transitions.apply`, since a state-machine walk cannot be
expressed as flat seed rows; the rejection fixture is a bare SQLite file
with no schema at all) and checks the script's stdout/stderr/exit code.
The report script is also loaded directly with `importlib.machinery.SourceFileLoader`
(it carries no `.py` suffix, like `manifest_hash`) so the objective-rule
test can assert against `primary_measures()`/`context_measures()` as data
instead of parsing report text, and so the window/unranked/context-label
tests can call `generate()` directly against a `tmp_path` database without
a subprocess per assertion.

## Verification

`uv run pytest -q --deselect runner/tests/test_manifest_hash.py` — 499
tests pass (448 before this ticket, plus 30 in `test_views.py`, 14 in
`test_report.py`, and `test_reliability_view.py` growing from 11 to 18 as
part of the narrowing rewrite the narrowed reliability rule calls for).

## Note on the deselected manifest-hash test

`runner/tests/test_manifest_hash.py::test_manifest_hash_over_real_repo_matches_committed_manifest`
compares `factory/manifest.yaml` on disk against the version committed at
`HEAD`. This ticket edits that file in an uncommitted worktree, so the
comparison fails until the change is committed — expected, and the reason
the ticket's own instructions say to deselect it.
