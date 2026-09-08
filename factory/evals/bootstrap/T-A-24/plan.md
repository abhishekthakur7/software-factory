# T-A-24 plan

## Steps

| # | Step | Files touched | Proves |
|---|---|---|---|
| 1 | `_check_criteria` added to the general structure check: `AC-n` id shape, EARS-field presence, example concreteness (GWT words plus a placeholder-token list), and forced-category resolution shape, wired in for `kind == "criteria"`. | `runner/checks/artefact_structure.py` | criteria 1, 5, 11, 12 |
| 2 | `questions.open_blocking(conn, ticket_id, stage=None)` replaces the driver-private helper; `gates.plan_review_gate` withholds its event while it is non-empty. | `runner/questions.py`, `runner/gates.py` | criteria 19, 20 |
| 3 | Two real checklists replace `rubrics/checklists/.gitkeep`; `factory/skills/S2.md` gains the missing `forced-categories.md` reference. | `factory/rubrics/checklists/forced-categories.md`, `factory/rubrics/checklists/split-patterns.md`, `factory/skills/S2.md` | criteria 11, 15, 16 |
| 4 | `factory/rubrics/S2.md` gains the R-S2-1, R-S2-2, R-S2-3, R-S2-4, R-S2-10, R-S2-12 lines; the R-S2-1/R-S2-2/R-S2-10 grader halves are bootstrap-checklist lines carrying the ticket's own judgment sentences. | `factory/rubrics/S2.md` | criteria 4, 6, 17 |
| 5 | `runner/stages/S2.py` rewritten: id-continuity, forced-category pre-fill, the agreement check (subject files, restatement children, comparison, table rewrite, candidate derivation), the split-presence check, candidate combination and a single `raise_round` call, the checked criteria artefact (front matter `assumption_log_hash`), and the blocking-only exit gate. | `runner/stages/S2.py` | criteria 1, 2, 3, 7, 8, 9, 10, 13, 14, 15, 16, 18, 19 |
| 6 | `factory/evals/rubrics/S2/`: `eval.yaml` extended; `r_s2_1_grader_{pass,fail}`, `r_s2_2_grader_{pass,fail}`, `r_s2_10_grader_{pass,fail}` `human_verdict.yaml` fixtures; `ears_form/{concrete,not_concrete}.md` script-check fixtures. | `factory/evals/rubrics/S2/eval.yaml`, `factory/evals/rubrics/S2/fixtures/**` | criteria 1, 2, 4, 5, 6, 17 |
| 7 | `factory/evals/agents/S2/fixtures/`: `criteria.md` added to `question_round`/`gate_rejected`; nine new cases (`criteria_clean`, `criteria_ambiguous`, `criteria_contradiction`, `criteria_uncovered`, `criteria_split_missing`, `criteria_split_present`, `criteria_unformalisable[_resolved]`, `criteria_open_category`, `criteria_id_conflict`), each with its `by_input/<AC-n>.<k>/restatement.md` set where the case needs restatement children; `eval.yaml` extended. | `factory/evals/agents/S2/fixtures/**`, `factory/evals/agents/S2/eval.yaml` | criteria 3, 7, 8, 9, 10, 13, 14, 15, 16, 18, 19 |
| 8 | `runner/tests/test_s2_questions.py`'s `_clarifying_ticket` registers `ticket_source`/`brief`; its second walk run points at `criteria_clean` instead of an empty round. | `runner/tests/test_s2_questions.py` | keeps the T-A-23 walk green under the new two-file contract |
| 9 | `runner/tests/test_s2_criteria.py`: unit tests over the pure helpers, structural-check tests over the `ears_form` fixtures, rubric grader-line tests, and full `run_stage` walks over every new agent-eval fixture. | `runner/tests/test_s2_criteria.py` | criteria 1-21 |
| 10 | Manifest hashes refreshed for every changed file; entries added for every new file under `factory/`; the removed `.gitkeep`'s entry dropped. | `factory/manifest.yaml` | `test_manifest_hash.py`, every walk that resolves a manifest entry |
| 11 | This ticket's own brief and plan. | `docs/build/T-A-24/brief.md`, `docs/build/T-A-24/plan.md` | reviewed by the human, not a test |

## Test strategy

`test_s2_criteria.py` splits into four groups. **Pure-function tests**
exercise `_check_id_continuity` (new id, kept id, reused id, gap, source
reassigned to a different id -- five cases), `_split_required`/
`_names_a_split_pattern`, `_s0_closed_categories`/
`_prefill_forced_categories` (a seeded `check_result` on a real `stage_run`
of stage `S0`), and `_open_category_candidates`, each called directly so a
failing assertion names the one rule that broke. **Structure-check tests**
call `artefact_structure.check("criteria", ...)` against the
`ears_form/concrete.md` and `ears_form/not_concrete.md` fixtures, proving
presence and concreteness together as one script rule (criteria 1, 5) and
the forced-category and id-shape rules against small hand-built texts
(criteria 2, 11, 12). **Rubric tests** load `factory/rubrics/S2.md` and
assert the three new grader lines carry `checklist = True` and the exact
judgment sentence the ticket states (criteria 4, 6, 17), plus that the six
new script lines exist. **Walk tests** drive `run_stage(conn, ticket_id,
"S2", runs_dir=)` with `FIXTURE_ADAPTER_OUT_DIR` set to each new fixture in
turn, against a ticket built by a local `_clarifying_ticket(conn, tmp_path)`
that also registers `ticket_source`/`brief`: `criteria_clean` proves the
happy path and id continuity across two versions of the same criterion
(criterion 2); `criteria_ambiguous`/`criteria_contradiction`/
`criteria_uncovered` each assert exactly one non-blocking question of the
expected shape and, for the first two, that the criterion's own `state`
row was downgraded to `provisional` (criteria 7, 8, 9); one of these walks
also asserts three sibling `stage_run` rows exist under the attempt on the
manifest's restatement model, and that `stage_reliability_view`'s
`eligible_count` for that stage/tier still counts the attempt alone
(criterion 10); `criteria_split_missing` proves the structural refusal and
`criteria_split_present` the accepted case (criteria 15, 16);
`criteria_unformalisable` proves the `blocked` exit with every other
criterion/category/question still written, and
`criteria_unformalisable_resolved` proves the next round passes once the
criterion is restated, both id-stable (criteria 3, 18, 19);
`criteria_open_category` proves the same blocking shape for a category
(criterion 14); `criteria_id_conflict` seeds a prior criteria artefact by
hand and proves the structural refusal on a reused id (criterion 2,
negative). Criteria 20 and 21 are asserted directly against
`questions.open_blocking`/`gates.plan_review_gate` and
`questions.supersede_assumption`/`questions.dependents_invalidated` --
functions `test_s2_questions.py` already exercises for their own write
paths -- rather than re-implemented: one test seeds a blocking question and
asserts `plan_review_gate` returns `None` even with quorum satisfied; one
seeds an accepted assumption, supersedes it, and asserts the plan artefact
recording the old hash is listed by `dependents_invalidated`.

## Verification

`uv run pytest -q` after `factory/manifest.yaml` is committed (every
walk test that reaches `stages.invoke_agent` resolves the manifest and
checks the ticket's pin against it).
