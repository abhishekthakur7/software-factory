# T-A-27 plan

## Steps

| # | Step | Files touched | Proves |
|---|---|---|---|
| 1 | `checklist.py`: `expected_instances`, `checklist_hash`, `record_verdict`, `completeness`, `verdict_set`, `waiver_set`. | `runner/checklist.py` | criteria 1-8 |
| 2 | `plan_tuple.py`: `derive_components`, `ensure_current`, `current_subject`. | `runner/plan_tuple.py` | criteria 10, 14, 16 |
| 3 | `_match_paths` gains `flag_unmatched`; `derive_planned` added, sharing it with the unchanged `derive_actual`. | `runner/reviewer_sets.py` | criteria 9, 13 |
| 4 | `_reviewer_set_json` -> `_planned_reviewer_set` plus `_scope_paths`; the sensitivity check and the `plan_approval` queue item open after registration. | `runner/stages/S3.py` | criterion 9 (scope-derived), 13 (exclusion) |
| 5 | `queue.py`: the `verdict` action, `_act_verdict`, `_check_plan_approvable`, `_approval_subject_hash`, the plan-checklist `factory queue` context. | `runner/queue.py` | criteria 5, 6, 7, 10, 11 |
| 6 | `gates.py`: `plan_review_gate` rewritten over real quorum, currency, and the any-open-question rule; `_quorum` removed. | `runner/gates.py` | criteria 11, 12, 15, 17 |
| 7 | `cli.py`: `act`'s five new flags. | `runner/cli.py` | the CLI surface for step 5 |
| 8 | The checklist eval fixture: brief/criteria/plan, two standalone rubric files (one clean, one deliberately colliding with `S2.md`), the expected instance list, and a full verdict set. | `factory/evals/rubrics/S3/fixtures/checklist/`, `factory/evals/rubrics/S3/eval.yaml` | backs step 9's tests |
| 9 | `test_s3_checklist.py`: expected instances, duplicate/missing rejection, verdict binding and correction, pass/evidence refusals, fail send-backs, blind-spot/waiver relief, the two checklist-derived hashes. | `runner/tests/test_s3_checklist.py` | criteria 1-8, 18 |
| 10 | `test_plan_tuple.py`: the planned derivation (pilot slot, CODEOWNERS, no-CODEOWNERS, sensitivity), the completing verdict's tuple, multi-slot quorum and identity separation, the trusted fetch, `head_sha` exemption, the open-question block, all nineteen bound fields, and expiry. | `runner/tests/test_plan_tuple.py` | criteria 9-17 |
| 11 | Six pre-existing files rebuilt off real checklist/plan-tuple state instead of a bare hand-seeded tuple or approval. | `runner/tests/test_stub_walk.py`, `test_report.py`, `test_act.py`, `test_attention_bucket.py`, `test_freshness.py`, `test_state_table.py` | full-suite green under the new gate |
| 12 | Manifest hashes recomputed for the new eval fixture files. | `factory/manifest.yaml` | manifest validation |
| 13 | This ticket's own brief and plan. | `docs/build/T-A-27/brief.md`, `docs/build/T-A-27/plan.md` | reviewed by the human, not a test |

## Test strategy

`test_s3_checklist.py` drives everything through the real committed
`S1.md`/`S2.md` plus the fixture's own small S3-stage rubric file
(`factory/rubrics/S3.md` is still a stub while a parallel ticket builds
it), asserting `expected_instances` against a hand-computed
`expected.json`, one duplicate-collision case, missing/complete
completeness over a shared `verdicts.yaml`, binding correctness per
stage, a correction's newest-wins behaviour, every refusal
(`must_reject`), a parametrised fail-verdict-per-stage send-back test, and
blind-spot/waiver relief including expiry. `test_plan_tuple.py` reuses
`test_reviewer_sets.py`'s real-git-repository convention for the
CODEOWNERS-backed derivation tests, and drives every quorum/currency/
freshness scenario through `queue.act`'s real verdict-then-approve path
against a ticket cloned from a real repository, never a hand-seeded
tuple — including a parametrised sweep over every one of
`binding.PLAN_COMPONENT_FIELDS`, each changed alone via
`dataclasses.replace` against a real derived baseline, proving
`plan_tuple_currency` actually reads every bound field rather than a
subset. The six touched-not-owned files are fixed with the minimum
change that lets their own pre-existing assertions keep meaning what
they meant: a real plan tuple and a real planned reviewer set wherever
the file drives `plan_review_gate` or a `plan_approval` item's `approve`
action, built through `queue.act`'s own verdict/approve path.

## Verification

`uv run pytest -q`
