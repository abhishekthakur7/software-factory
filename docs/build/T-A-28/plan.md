# T-A-28 plan: S4 hand-off and hand-back artefacts, deviation rows

## Steps

| # | Step | Files touched | Proves |
|---|---|---|---|
| 1 | `binding.deviation_set_hash(conn, ticket_id)`: `set_hash` over the ticket's `deviation` rows, `id` and `stage_run_id` dropped. | `runner/binding.py` | the S5 review tuple's future binding point; used by `record_handback`'s own summary |
| 2 | `git_trees.commit_worktree(worktree, message) -> sha`: commits under a fixed runner identity; returns the current HEAD unchanged when there is nothing to commit. | `runner/git_trees.py` | the one place S4 makes a git commit |
| 3 | `S4.build_handoff`: reads the latest plan tuple and the plan/criteria artefacts, derives tasks/scope/blind-spots from the plan's own tables, writes and registers `handoff.json`. | `runner/stages/S4.py` | criteria 1-10 |
| 4 | `S4.record_handback`: reads and validates `out/handback.json`, commits the worktree, writes the ticket's branch/head/worktree fields, inserts `deviation` rows, records the `handback_structure` check result. | `runner/stages/S4.py` | criteria 11-15 |
| 5 | `S4.run`: the missing-plan-tuple/plan-artefact guard, the hand-off call, one `stages.invoke_agent`, the hand-back call. | `runner/stages/S4.py` | the whole-plan single-invocation flow |
| 6 | `factory/agents/S4.md`: names `out/handback.json` and that the runner commits. | `factory/agents/S4.md`, `factory/evals/agents/S4/fixtures/ok/S4.md` | agent-definition eval walk still passes |
| 7 | `FIXTURE_ADAPTER_WORKTREE_DIR`: the fixture worker copies a fixture tree onto the ticket worktree and reports those paths in `files_written`. | `runner/tests/fixtures/adapter/fixture_worker.py`, `sandbox.yaml` | a real invocation can simulate the agent's own edits without running git |
| 8 | Hand-back eval fixtures: `ok` (two deviations, a small Java edit), `empty_deviations`, `missing_deviations`, `malformed_deviations`, `no_handback`; matching `eval.yaml` cases. | `factory/evals/agents/S4/fixtures/*`, `eval.yaml` | one fixture per hand-back outcome `test_s4_handback.py` walks |
| 9 | `test_s4_handoff.py`: `build_handoff` against a hand-seeded ticket/plan-tuple/plan fixture, direct assertions per criterion, a reconstruction test reading only the written file, and the two structural-guard tests. | `runner/tests/test_s4_handoff.py`, `runner/tests/fixtures/s4_handoff/plan.md` | criteria 1-10 |
| 10 | `test_s4_handback.py`: the real driver through `run_stage`, walking the eval directory's `handback_*` cases, plus a direct `commit_worktree` no-op test. | `runner/tests/test_s4_handback.py` | criteria 11-15 |
| 11 | The stub walk's S4 step now runs for real, served by the `ok` fixture; `deviation` added to the walk's every-table-carries-rows list. | `runner/tests/test_stub_walk.py`, `runner/tests/fixtures/stub_walk/tables.yaml` | the whole `intake`-to-`pr_opened` walk still passes with a real S4 |
| 12 | Manifest hashes recomputed for every changed file, entries added for every new one. | `factory/manifest.yaml` | `test_manifest_hash.py` |
| 13 | This ticket's own brief and plan. | `docs/build/T-A-28/brief.md`, `docs/build/T-A-28/plan.md` | reviewed by the human, not a test |

## Test strategy

`test_s4_handoff.py` builds a ticket in `implementing` with a hand-seeded
plan tuple (fixed, distinct hash strings for every bound field) and a
small hand-written plan fixture carrying one `blind_spot` readiness row,
one `unknown` `Contracts` cell, and two `Tasks` rows exercising
comma-separated lists and typed `validation_args`. Each of criteria 1-9
is one direct assertion against the written `handoff.json`; criterion 10
is a separate test that closes the database connection first and
re-derives the task list, recipe set, and budget from the written file,
`tiers.yaml`, and `project.yaml` alone. Two more tests cover `run`'s own
guard: no plan tuple, and no plan artefact, each a structural failure
with a `check_result` naming what is missing.

`test_s4_handback.py` runs the real driver end to end through
`run_stage`, parametrized over the eval directory's `handback_ok`/
`handback_reject` cases, against a ticket with a real cloned worktree.
`FIXTURE_ADAPTER_OUT_DIR` serves each case's `out/handback.json`;
`FIXTURE_ADAPTER_WORKTREE_DIR`, set only for the `ok` case, serves a real
one-file Java edit so the resulting commit and `head_sha` change are
provable, not merely asserted from a mocked git call. The reject cases
assert the ticket stays in `implementing`, the attempt's `stage_run`
carries `outcome=fail`/`failure_kind=structural`, no `deviation` row was
written, and no `red_check` queue item opened. A dedicated test asserts
the empty-deviations case's `check_result` summary carries exactly
`binding.set_hash([])` -- the canonical hash of the empty set, computed
independently of `record_handback` itself, not merely echoed back from
whatever the implementation happened to write. `commit_worktree`'s
own no-op path is proven directly, without going through the driver.

## Verification

`uv run pytest -q`
