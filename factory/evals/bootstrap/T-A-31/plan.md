# T-A-31 plan

## Steps

| # | Step | Files touched | Proves |
|---|---|---|---|
| 1 | `runner/artefacts.py`: `SECTIONS["packet"]` replaced with the charter's twelve-section order, `SECTIONS["pr_body"]` added, `PACKET_TABLES` registers the evidence table's columns. | `runner/artefacts.py` | criterion 1 |
| 2 | `runner/checks/artefact_structure.py`: `KIND_TABLES["packet"]` wired to `PACKET_TABLES`. | `runner/checks/artefact_structure.py` | criterion 1 |
| 3 | `packet_render.py`: the shared section builders (identity/freshness, evidence table, decisions, not-touched, risk map, deviations with base-test diffs, assumptions, test summary, blind spots, diff). | `factory/scripts/tools/packet_render.py` | criteria 1-8 |
| 4 | `packet_assemble` / `pr_body_assemble`: thin CLIs over `packet_render`, non-zero exit with a message on malformed inputs. | `factory/scripts/tools/packet_assemble`, `pr_body_assemble` | criteria 1-5 |
| 5 | Eval fixtures: a full ordered packet, an impact entry seeded `pass` relabelled `blind_spot`, an unplanned test file, a malformed-inputs case; the `pr_body` eval reuses the full fixture. | `factory/evals/scripts/tools/packet_assemble/`, `pr_body_assemble/` | criteria 1-5 |
| 6 | `test_s6_packet_assemble.py`, `test_s6_pr_body_assemble.py`, `test_s6_test_summary.py`. | `runner/tests/test_s6_*.py` | criteria 1-8 |
| 7 | `base_test_diff`: `--tests-head-in-base`, per-row rerun verdicts (`pass`/`blind_spot`/`exempt`), overall `result` folds in a planned blind spot. | `factory/scripts/checks/base_test_diff` | criteria 13-15 |
| 8 | Eval fixtures for the three rerun verdicts; `test_s5_base_test_diff.py` extended with matching tests. | `factory/evals/scripts/checks/base_test_diff/fixtures/both_views_*`, `runner/tests/test_s5_base_test_diff.py` | criteria 13-15 |
| 9 | `runner/stages/S5.py`: the both-views rerun wired into `run`, passing `--tests-head-in-base`; the `check_tier` fix for governed/base-side recipe results (advisory, not blocking) that `waivers.cleared` needed to be usable at all. | `runner/stages/S5.py` | criteria 13-15, the S6 walk |
| 10 | `runner/stages/S4.py`: `record_handback` gains `plan_text`/`base_sha`, writes base-test-change `deviation` rows unconditionally at hand-back; both call sites pass them; `_check_fix_round_diff` drops its own now-duplicate deviation write. | `runner/stages/S4.py` | criteria 16-18 |
| 11 | `test_s4_handback.py`/`test_s4_fix_round.py`: adjusted assertions where the generalised recording changed what a test could read (`why` no longer names the criterion; an unauthorized change now leaves one `unplanned` deviation row instead of zero). | `runner/tests/test_s4_handback.py`, `test_s4_fix_round.py` | criteria 16-18 |
| 12 | `runner/stages/S6.py`: the real driver -- race guard, freshness recheck, S5-cleared check, `packet_inputs.json` gathering, both scripts, artefact registration, `packet_approval`. | `runner/stages/S6.py` | criteria 1-5, 9-18 (via the walk) |
| 13 | `test_stub_walk.py`: `_grant_packet_approval` approves the item the real S6 opened (pre-approving every other CODEOWNERS-matched slot first, same shape as `_grant_plan_approval`) instead of seeding its own tuple. | `runner/tests/test_stub_walk.py` | the walk reaches `pr_opened` through a real S6 |
| 14 | Manifest refresh. | `factory/manifest.yaml` | `test_manifest_hash.py` |
| 15 | This part's own brief and plan. | `docs/build/T-A-31/brief.md`, `plan.md` | reviewed by the human |

## Test strategy

`packet_assemble`/`pr_body_assemble` get one eval directory each
(`eval.yaml` with `subject`, `owner: abhishek`, `cases`), matching
`test_s6_packet_assemble.py`/`test_s6_pr_body_assemble.py`, which run the
script as a subprocess per case and assert `returncode`/`result`/section
order/evidence-row shape -- the same convention `test_s5_base_test_diff.py`
already uses for standalone scripts. `test_s6_test_summary.py` imports
`packet_render.py` directly (no subprocess) since the matching logic
between the diff's test files and the plan's `Test strategy` table is a
pure function worth testing at that grain, and the ticket names no
dedicated eval directory for it.

`base_test_diff`'s three new fixtures each carry a `tests_head_in_base.json`
the existing five fixtures don't pass, so the new `--tests-head-in-base`
argument stays fully backward compatible with every case that predates
it -- proven by leaving those five cases and their exact assertions
unmodified.

The S6 driver itself is proven only through the real, javac-gated walk in
`test_stub_walk.py`: no separate database-level S6 unit-test file exists,
since every numbered acceptance criterion for the driver's own behaviour
(criteria 1-5, 9) is really about what the two scripts produce from a
given `packet_inputs.json`, already covered at that grain, and criteria
9-18 are S4/S5 script-level behaviour the base-test-diff and hand-back
tests already prove directly. The walk is what proves the driver wires
those pieces together correctly end to end: the race guard, the
freshness recheck, the S5-cleared check, real artefact registration, and
a `packet_approval` item a human can actually resolve.
