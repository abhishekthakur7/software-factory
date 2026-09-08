# T-A-14 plan

## Steps

| # | Step | Files touched | Proves |
|---|---|---|---|
| 1 | `freshness.py`: `fetch_target_head`, the `Freshness` dataclass, the three boundary constants, `check` (shared target/plan-tuple comparison, `S5_PREFLIGHT`'s head/diff addition, `BEFORE_DISPATCH`'s intent-identity addition, the one invalidating `check_result` write), `invalidated_tuples`. | `runner/freshness.py` | criteria 1, 2, 6 |
| 2 | `refresh_base.py`: the pre-flight state-table refusal, the fetch-and-rebase, the clean-rebase recording and `refresh_base` transition, the conflict path (capture, abort, `check_result`, `escalate`, one `escalation` item). | `runner/refresh_base.py` | criteria 3, 4, 5, 7 |
| 3 | One additive row, `("plan_review", "escalate")`, so a `refresh_base` conflict from `plan_review` can reach `escalated` like it already can from `implementing`/`checks`. | `runner/state_table.py` | criterion 5 (the plan_review-conflict case) |
| 4 | `plan_review_gate` takes `target_branch`/`runs_dir` and calls `freshness.check(boundary=BEFORE_S4)`. | `runner/gates.py` | criterion 1 (plan-approval commit boundary) |
| 5 | S5's stub driver runs the `S5_PREFLIGHT` check before writing its artefact, returning `("fail", "stale_binding")` on a stale result; `run_stage` passes a driver's optional `failure_kind` through to `run_ledger.finish`. | `runner/stages/S5.py`, `runner/stages/__init__.py` | criterion 1 (S5 preflight boundary), criterion 2 |
| 6 | `advance`'s own `BEFORE_S4` check (queues one `red_check` unless one is already open, runs no stage on a stale result) and the `refresh-base` subparser/dispatch branch. | `runner/cli.py` | criterion 1 (due-stage boundary), criteria 3-7 (CLI surface) |
| 7 | `_dispatch_pending` repeats `BEFORE_DISPATCH` immediately before its own call to `dispatch`, superseding a stale row instead of ever calling the deliverer. | `runner/outbox.py` | criterion 8 |
| 8 | Fixture scenarios: a target-branch movement, a clean rebase (disjoint files), a conflicting rebase (same lines). | `runner/tests/fixtures/freshness/*.yaml` | criteria 1, 3, 4, 5 |
| 9 | `test_freshness.py`: one or more tests per criterion, `must_reject` naming on the S5-preflight head-drift refusal. | `runner/tests/test_freshness.py` | criteria 1-8 |
| 10 | Fix the tests that exercised `plan_review_gate` or the S5 stub driver against a bare ticket row with fixture SHA strings, which a real fetch can no longer satisfy: rebuild them against a small real cloned repository, mirroring `test_fixture_project.py`'s `_bare_git_project` convention. | `runner/tests/test_state_table.py`, `runner/tests/fixtures/state_table/plan_subject.yaml` (trimmed), `runner/tests/fixtures/state_table/quorum.yaml` (removed, now unused), `runner/tests/test_stub_stages.py`, `runner/tests/test_report.py` | every previously-passing test in these files stays green |
| 11 | This ticket's own brief and plan. | `docs/build/T-A-14/brief.md`, `docs/build/T-A-14/plan.md` | reviewed by the human, not a test |

## Test strategy

`test_freshness.py` builds real git repositories the same way
`test_fixture_project.py`'s `_bare_git_project` does (a plain repo, no
JDK), clones a ticket from one with `git_trees.clone_for_ticket`, and
moves the "target" by committing again on the source repository after the
clone -- exactly the ticket's own definition of target movement. Each of
the three boundaries gets a direct `freshness.check(...)` call proving
detection and, for `S5_PREFLIGHT`, the additional head/diff requirement
(a `must_reject` test for the worktree-head-moved-past-`ticket.head_sha`
case). Wiring is proved once per boundary through its real call site:
`cli.advance` refusing to start S4 and queuing exactly one `red_check`
(and not a second one on a repeated call), `gates.plan_review_gate`
withholding `plan_quorum_fresh`, and `outbox.reconcile_pending` marking a
`pr_create` row `superseded` with the stub deliverer receiving nothing.

`refresh_base` gets one test per scenario: a dirty build (a real S4-style
commit on the ticket branch touching one file, a target commit touching a
different file) preserved on top of the new base after a clean rebase,
with the new `base_sha`/`target_base_sha`/`head_sha` recorded and the
ticket back in `context`; a conflicting rebase (both commits touching the
same lines of one file) aborted with the worktree left clean, the ticket
`escalated`, and exactly one `escalation` queue item referencing the
`check_result` row that names the conflicting path.

Invalidation is proved by calling `freshness.invalidated_tuples` after a
stale `check` call and asserting it returns the plan (and, once one
exists, review) tuple id the row named. The post-refresh requirement of a
new plan tuple and quorum is proved by showing the *old* plan tuple and
its approval, still on the ticket after `refresh_base` moved
`target_base_sha`, no longer satisfy `plan_review_gate` -- nothing further
needs to be built to prove that, since it falls directly out of
`freshness.check` comparing the fetched head against the plan tuple's own
(unmoved) `base_sha`.

## Verification

`uv run pytest -q`
