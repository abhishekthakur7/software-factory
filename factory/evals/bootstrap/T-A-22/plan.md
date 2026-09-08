# T-A-22 plan

## Steps

| # | Step | Files touched | Proves |
|---|---|---|---|
| 1 | `factory/scripts/tools/reindex`: `codegraph index <worktree>`, one JSON line, exit 0/1; its eval dir. | `factory/scripts/tools/reindex`, `factory/evals/scripts/tools/reindex/` | reindex's own ok/absent-binary tests in `test_s1.py` |
| 2 | `runner/checks/brief.py`: pure `Finding`-returning checks (summary word limit, flags-are-code-references, live-state-confined-to-blind-spots, impact-evidence-valid, inbound-coverage-matches-caller-freshness, discovers-excluded-scope) plus the counting and tier helpers (`count_files_touched`, `touched_services`, `count_unknowns`, `final_tier_rule`, `impact_derived_tier`). | `runner/checks/brief.py` | all `checks_brief.*` unit tests |
| 3 | `runner/stages/S1.py` rewritten: reindex utility_run, impact_scan registered as an `impact_scan` artefact, context-index reads registered as an `index_reads` artefact, the agent invoked with both as fixed inputs, the raw brief parsed and structurally validated, tier numbers computed and the Final tier section overwritten before the checked brief is registered, then the exclusion check and the content checks in turn. | `runner/stages/S1.py` | every driver-level test in `test_s1.py`; the full-suite collateral tests |
| 4 | `factory/rubrics/S1.md`: a real ten-line table -- script and grader halves for the summary, impact-evidence, and flags/live-state rows (the grader judgment text copied verbatim from the criteria that dictate it), script-only for the index-reads and final-tier rows, script and grader halves for the impact-derived-tiering row. | `factory/rubrics/S1.md` | the rubric-line assertions in `test_s1.py` |
| 5 | `factory/evals/rubrics/S1/`: `owner: abhishek` added to `eval.yaml`; a fact-only-summary fixture; four seeded `human_verdict` scenario documents. | `factory/evals/rubrics/S1/eval.yaml`, `factory/evals/rubrics/S1/fixtures/fact_only_summary/`, `factory/evals/rubrics/S1/fixtures/human_verdict/` | the rubric-fixture assertions in `test_s1.py` |
| 6 | `factory/evals/agents/S1/fixtures/`: eight new `out/brief.md` fixtures (HTTP, messaging, config, stale-catalogue, unmapped-package, authoritative-build-graph, eligibility-triggering-unknown, plain-ok), named under a new `driver_cases` key in `eval.yaml` kept separate from the existing `cases` key. | `factory/evals/agents/S1/eval.yaml`, `factory/evals/agents/S1/fixtures/*/out/brief.md` | the fixture-driven driver tests in `test_s1.py` |
| 7 | `factory/manifest.yaml`: `factory/rubrics/S1.md`'s hash refreshed; new entries for every file steps 1, 5, and 6 add. | `factory/manifest.yaml` | `test_manifest_hash.py`; every test that resolves the S1 manifest entry |
| 8 | `runner/tests/test_s1.py`: every acceptance criterion, plus the reindex tool's own tests. | `runner/tests/test_s1.py` | criteria 1-18 |
| 9 | Collateral fixes: every place the suite already ran a ticket through S1 as a stub now needs a real worktree, a manifest pin, and (where S1 must pass) a `FIXTURE_ADAPTER_OUT_DIR`; two counting assertions move to `parent_run_id IS NULL` now that a passing S1 opens a child `stage_run` for its own agent invocation, matching the same stage name. | `runner/tests/test_stub_stages.py`, `runner/tests/test_stub_walk.py`, `runner/tests/test_cli_skeleton.py`, `runner/tests/test_crash_recovery.py`, `runner/tests/fixtures/crash_recovery/per_stage.yaml`, `runner/tests/test_report.py`, `runner/tests/test_stage_interface.py` | full-suite green |
| 10 | This ticket's own brief and plan. | `docs/build/T-A-22/brief.md`, `docs/build/T-A-22/plan.md` | reviewed by the human, not a test |

## Test strategy

`test_s1.py` drives every acceptance criterion. Criterion 1 and the
rubric-line criteria (2, 10, 13, 18) are pure: the fact-only-summary
fixture and an over-limit synthetic string against
`checks_brief.summary_word_limit`, and `rubrics.load` against the real
`factory/rubrics/S1.md` for the exact dictated grader judgment text,
plus a light consistency check on each seeded `human_verdict` fixture.
Criteria 3, 4, 5 share one parametrized driver test over the HTTP,
messaging, and config fixtures, each asserting the checked brief's own
impact-evidence row carries every required field. Criterion 6 seeds a
stale `caller` context-index entry and drives the `stale_catalogue`
fixture through the full driver, asserting the row is `unknown` and the
stale read is recorded; its negative half
(`inbound_coverage_matches_caller_freshness`) is proven directly.
Criteria 7 and 8 drive the `unmapped_package` and
`authoritative_build_graph` fixtures against a worktree pom carrying the
matching dependency, cross-checking the checked brief's row against the
real `impact_scan` payload registered alongside it. Criterion 9 drives
the `eligibility_triggering_unknown` fixture and asserts the ticket lands
`rejected`/`pilot_excluded` with a failed `exclusion` check_result;
`discovers_excluded_scope` is also proven directly, both for the
service-discovery clause and the eligibility-blind-spot clause.
Criteria 11 and 12 (R-S1-6's script half) are pure, positive and negative,
over `flags_are_code_references` and `live_state_confined_to_blind_spots`.
Criterion 14 parametrizes `final_tier_rule` over each of the three
threshold triggers plus the no-trigger case, and a `must_reject` case
pins that it never lowers an already-higher tier. Criteria 15 and 16
call `impact_derived_tier` directly for the T1-consumer and
unknown-consumer cases; 16 also drives a full run to pin that the
`brief_impact_unknown` check_result is always written, pass or fail.
Criterion 17 runs `discovers_excluded_scope` directly and then through
the full driver, pointing a worktree pom's one dependency at a
test-local mapping file naming a different service. R-S1-7's own script
line and the empty-index "no entries" case round out coverage the
`Verification` section does not enumerate by number but the row's own
acceptance text requires.

Collateral: making S1 real broke every existing test that ran a ticket
through it as a stub with no worktree, no manifest pin, and no fixture
output -- the same shape of fix T-A-20 needed when S0 went real. Fixing
`runner/stages/S1.py`'s own `_run_reindex` helper (it called
`run_ledger.finish` without `table="utility_run"`, silently overwriting
whatever `stage_run` row happened to share the utility run's id) was
caught by `test_stub_walk.py`'s wrong-state-refusal assertion, not by
`test_s1.py`'s own tests, since none of them had a pre-existing
`stage_run` row to collide with -- worth naming since it is the one real
bug this pass found outside the ticket's own new code.

## Verification

`uv run pytest -q`
