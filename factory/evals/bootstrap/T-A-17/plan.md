# T-A-17 plan

## Steps

| # | Step | Files touched | Proves |
|---|---|---|---|
| 1 | `control.live_run(conn, ticket_id)` and `control.live_run_refusal(ticket_id)`: the one open-and-alive `stage_run` predicate and its shared message. | `runner/control.py` | criterion 4 |
| 2 | `control.pause`/`control.pause_pending`/`control.resume`: the durable flag, the boundary check that stamps `paused_at` and opens one `manual_pause` item, and resume through `queue.act`'s existing `resume` action. | `runner/control.py` | criteria 6, 8, 11, 12 |
| 3 | `control.stop`: finish every open `stage_run` `aborted_human`, escalate, tag, open one `escalation` item. | `runner/control.py` | criteria 1, 2, 3 |
| 4 | `control.status`: state, open-or-latest run's stage/attempt/elapsed/budget-remaining/outputs, pause pending. | `runner/control.py` | criteria 7, 9 |
| 5 | `cli.advance`: live-run refusal up front; `pause_pending` immediately before the due-stage branch and immediately before the gate branch. `cli.run`: live-run refusal before `run_stage`. `cli.show`: append `control.status`'s fields. New `cli.pause`/`cli.resume`/`cli.stop` wrappers and their `main()` subparsers. | `runner/cli.py` | criteria 4, 6, 7, 8, 9, 12 |
| 6 | `queue.act`: live-run refusal for the item's ticket, via a function-local `control` import, before reconciliation or action validation. | `runner/queue.py` | criterion 4 |
| 7 | `test_stage_interface.py`: one or more tests per criterion 1-12. | `runner/tests/test_stage_interface.py` | criteria 1-12 |
| 8 | `test_stub_walk.py` and its fixtures: the walk driver (`_run_walk`, module-scoped through the `walk` fixture) plus one short test per criterion 13-21. | `runner/tests/test_stub_walk.py`, `runner/tests/fixtures/stub_walk/tables.yaml`, `runner/tests/fixtures/stub_walk/shell_recipe.yaml` | criteria 13-21 |
| 9 | This ticket's own brief and plan. | `docs/build/T-A-17/brief.md`, `docs/build/T-A-17/plan.md` | reviewed by the human, not a test |

## Test strategy

`test_stage_interface.py` seeds every "live" run with no monkeypatch at
all (`run_ledger.open_stage_run` with no override), so its
`process_identity` names the test process itself and `process_alive`
finds it genuinely alive -- the positive case of the same convention
`test_crash_recovery.py` uses for its own alive-process negative case.
Criteria 1-4 share one test: a live `S4` run refuses `pause`, `resume`,
`run`, `advance`, and `act` on an unrelated open item for the same
ticket, leaving the run, ticket state, and item all unchanged, and then
`stop` alone terminates it, recording `aborted_human` and escalating.
Criterion 5 registers one artefact against the live run and asserts its
file bytes, hash, and row are unchanged, and no new artefact appears,
across both a pause request and a stop. Criteria 6, 8, and 12 seed the
pause flag (once directly on the column, to prove it is the durable
value `advance` reads, and once through `cli.pause`) and assert a due
stage never runs while it is set, repeatably across two `advance` calls
with no duplicate `manual_pause` item. Criterion 11 resumes that same
paused ticket and asserts the next `advance` finally runs the held
stage. Criteria 7 and 9 seed a live run (respectively, a paused
mid-pipeline ticket with one registered artefact) and assert `show`'s
text contains the expected stage/attempt/budget/output/pause fields.
Criterion 10 is one parametrized test over the five open-item kinds that
accept `send_back`, each seeded in its own natural state, asserting the
ticket moves and no `approval_record` row appears.

`test_stub_walk.py` runs the whole walk exactly once, behind a
module-scoped `walk` fixture, and every criterion's test reads its
result rather than replaying it. `_kill_and_restart` is the one seam
that proves criterion 15 at each of the seven stages: it seeds a dead
run (a monkeypatched `process_identity` for exactly the one call that
opens it, undone immediately after, matching `test_crash_recovery.py`'s
`_open_dead_run`), calls one `cli.advance`, and asserts the dead run
ended `infrastructure_failure`/`expired_lease` with exactly one fresh,
passing attempt following it. The walk seeds a real, fetchable git base
before plan review (S4's and S5's freshness checks need one), grants
plan and packet approval through `queue.act`'s own `approve` action
against seeded reviewer sets -- the same shape `test_act.py` seeds --
and lets the packet approval's own effect (`outbox.intent_for_review_
quorum`) author the `pr_create` intent that a later `cli.advance` then
reconciles through the stub deliverer, matching `test_outbox.py`'s own
`_activate`/`give_real_base` conventions. The stop-and-resume-through-
escalation and pause-and-resume sequences run inline mid-walk, each
asserted immediately in `_run_walk` itself since they pin transient
states an assertion made afterward could no longer see. The manifest
hash script runs once before the walk starts and once after it ends,
both captured on the returned `WalkResult`, so the "before and after"
comparison brackets the walk's own execution rather than any other
test's. Criterion 18's shell-string refusal and criterion 21's
guard-bypass refusal need no ticket state at all and are written as
their own independent, fast tests.

## Verification

`uv run pytest -q`
