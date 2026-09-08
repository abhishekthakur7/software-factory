# T-A-15 plan

## Steps

| # | Step | Files touched | Proves |
|---|---|---|---|
| 1 | `expire_dead_runs(conn, ticket_id, *, now=None)`: open, lease-lapsed, process-dead rows on both `stage_run` and `utility_run` finish `infrastructure_failure`/`expired_lease`; anything else is left alone. | `runner/run_ledger.py` | criteria 2, 3, 4 |
| 2 | `record_reasoning_summary(conn, run_id, text)`: word-cap read fresh from `tiers.yaml`. | `runner/run_ledger.py` | criterion 7 |
| 3 | `stage_run.reasoning_summary` marked `mutable=True`; `USER_VERSION` bumped. | `runner/schema.py`, `runner/db.py` | criterion 7 |
| 4 | `reasoning_summary` added to `stage_run`'s allowlist. | `runner/tests/test_mutable_exceptions.py` | criterion 7 (allowlist sweep) |
| 5 | `reasoning_summary: {max_words: 200}` block; `tiers.yaml`'s `content_hash` recomputed. | `factory/config/tiers.yaml`, `factory/manifest.yaml` | criterion 7 |
| 6 | `expire_dead_runs` wired into `advance`, right after `reconcile_pending` and before due-stage/gate logic. | `runner/cli.py` | criteria 1, 5, 6, 8 |
| 7 | Per-stage and outbox-first seed fixtures. | `runner/tests/fixtures/crash_recovery/*.yaml` | criteria 1, 3, 5, 8 |
| 8 | `test_crash_recovery.py`: one or more tests per criterion, `must_reject` naming on the alive-process and over-cap refusals. | `runner/tests/test_crash_recovery.py` | criteria 1-8 |
| 9 | This ticket's own brief and plan. | `docs/build/T-A-15/brief.md`, `docs/build/T-A-15/plan.md` | reviewed by the human, not a test |

## Test strategy

`_open_dead_run` is the one seam every "killed run" test in the file goes
through: it monkeypatches `run_ledger.process_identity` for exactly the
`open_stage_run`/`open_utility_run` call that needs a dead identity, then
undoes the patch immediately, so `process_alive`'s later, real check sees
a pid that provably does not exist. The alive-process negative case opens
with no monkeypatching at all, so its identity is this very test process.

Criteria 1, 3, and 6 share one test: a killed `S1` run restarted through
`cli.advance` ends `infrastructure_failure`/`expired_lease`, and exactly
one fresh `attempt = 2` row exists alongside it. Criterion 2 and the
over-cap criterion 7 are titled `test_must_reject_...` and assert the
refusal directly: the lease stays open, or the stored summary is exactly
`max_words` long. Criterion 4 seeds an artefact and a `worktree_path`
before expiring the run and asserts both are byte-for-byte unchanged
after. Criterion 5 activates the default trust profile the way
`test_outbox.py`'s reconcile-first test does, seeds a pending `digest`
intent and a killed `S5` run on one ticket, and after one `cli.advance`
call asserts the intent is `reconciled` and its receipt artefact's row id
is lower than the fresh attempt's own `check_evidence` artefact's id --
the one pair of ids in this scenario that actually share a sequence.
Criterion 8 is a single parametrized test over `per_stage.yaml`'s seven
entries (`S0` through `S6`), each bringing a ticket to the state the named
stage runs from (S6's entry alone seeding a real passed `S5` run first,
since `checks`' due-stage logic reads it), then repeating the same
kill-and-restart assertion as criteria 1/3/6.

## Verification

`uv run pytest -q --deselect runner/tests/test_manifest_hash.py`
(deselected because the committed-bytes check in that file fails against
an uncommitted `factory/manifest.yaml` edit in this worktree).
