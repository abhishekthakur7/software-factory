# T-A-14 brief: freshness at three boundaries and `refresh-base`

## What this delivers

The one trusted fetch-and-compare the runner already promised at three
points in the ticket lifecycle, and the human action that absorbs a moved
target branch without ever letting stale evidence reach a pull request.

- `runner/freshness.py` -- `fetch_target_head(repo, target_branch)`, the
  one place this module reaches another repository: `git fetch origin
  <branch>` inside the ticket's own clone, then `git rev-parse
  origin/<branch>`. `check(conn, ticket_id, *, boundary, target_branch,
  runs_dir)`, the one function every boundary calls: every boundary
  requires the fetched head to equal the latest plan tuple's `base_sha`
  and the ticket's recorded `target_base_sha`; `S5_PREFLIGHT` additionally
  requires the worktree's actual HEAD to still equal `ticket.head_sha`
  and, when it does, that head's diff against the plan tuple's base to
  hash to the latest review tuple's `diff_hash` (or, absent a review
  tuple yet, simply records the computed hash for the caller to bind);
  `BEFORE_DISPATCH` additionally requires the pending pull-request
  intent's `head_ref`/`desired_remote_head_sha`/
  `review_approval_subject_hash` to still match the ticket and its latest
  review tuple. Returns a frozen `Freshness` (`fresh`, `boundary`,
  `fetched_target_head`, `reasons`, `diff_hash`, `check_result_id`). A
  stale result writes exactly one `check_result` row (`check_name =
  "freshness"`, `check_tier = "blocking"`, `result = "fail"`, `source =
  "runner"`, naming the plan/review tuples it invalidates); a fresh result
  writes nothing. `invalidated_tuples(conn, ticket_id)` reads those rows
  back into the set of tuple ids a gate or preflight must refuse to build
  on.
- `runner/refresh_base.py` -- `refresh_base(conn, ticket_id, *, actor,
  note, target_branch, runs_dir)`: reconciles pending external writes
  first, refuses immediately (before any git call) when the ticket's
  state carries no `refresh_base` row in `state_table.TABLE`, fetches the
  target and rebases the ticket branch onto it in its worktree. On a
  clean rebase, records the new `base_sha`/`target_base_sha`/`head_sha`
  and applies `refresh_base`, which the state table already returns to
  `context`. On a conflict, captures the conflicting paths, aborts the
  rebase, writes one `check_result` row (`check_name = "refresh_base"`),
  applies `escalate`, and opens one `escalation` queue item referencing
  it.
- `runner/cli.py` -- the `refresh-base` subparser and dispatch branch; a
  `BEFORE_S4` freshness check as the first thing `advance` does once it
  determines S4 is the due stage (queuing one `red_check` unless the
  ticket already has an open one, and running no stage on a stale
  result); the same check backs `plan_review`'s own gate call.
- `runner/gates.py` -- `plan_review_gate` now takes `target_branch` and
  `runs_dir` and calls `freshness.check(boundary=BEFORE_S4)` in place of
  its stored-equality check.
- `runner/stages/S5.py` -- runs the `S5_PREFLIGHT` check before writing
  the stub `check_evidence` artefact; a stale result returns `("fail",
  "stale_binding")` instead of writing anything.
- `runner/stages/__init__.py` -- `run_stage` accepts either a driver's
  plain outcome string or a `(outcome, failure_kind)` pair, passing
  `failure_kind` through to `run_ledger.finish` in the latter case; every
  driver but S5 keeps returning a bare string.
- `runner/outbox.py` -- `_dispatch_pending` repeats the `BEFORE_DISPATCH`
  check immediately before its own call to `dispatch` for a
  `pr_create`/`pr_update` row (after the existing-pull-request adoption
  and unexpected-remote-head checks, which already short-circuit before
  ever reaching a fresh dispatch); a stale result marks the row
  `superseded` with `last_error` naming the reasons and never calls the
  deliverer.
- `runner/state_table.py` -- `escalate` is now valid from `plan_review`
  too, so `refresh_base`'s conflict path can reach `escalated` from every
  state it may be called from (`plan_review`, `implementing`, `checks`);
  it was previously valid only from the five states no refresh-conflict
  path used.
- `runner/tests/test_freshness.py` and `runner/tests/fixtures/freshness/`
  (three scenarios: target-branch movement, a clean rebase, a conflicting
  rebase).
- Updated as a consequence of `plan_review_gate` and the S5 stub driver
  each now performing a real git fetch instead of a stored-equality
  check: `runner/tests/test_state_table.py`'s two `plan_review_gate`
  scenarios (now built against a real cloned repository instead of a bare
  ticket row with fixture SHA strings; the now-unused `quorum.yaml`
  fixture is removed and `plan_subject.yaml`'s `stale_at_plan_review`
  scenario is trimmed to the still-used `stale_at_implementing` one),
  `runner/tests/test_stub_stages.py`'s S5/S6 stub-driver test, and
  `runner/tests/test_report.py`'s completed-walk fixture builder.

## Row covered

R-S5-12 (`docs/prd/04-S5-cleanup-pass.md` line 16; the `plan_review`,
`implementing`, `checks`, and `escalated` rows of
`docs/prd/02-3-ticket-states.md`; the "Failed and blocked runs"
paragraph): base freshness is blocking at three boundaries -- before S4
and at the plan-approval commit, again in S5 preflight with the exact
candidate branch head and diff, and once more immediately before PR
dispatch; movement invalidates affected downstream evidence;
`refresh_base` rebases onto the fetched head, records the new base/head or
escalates a conflict without resolving it, and returns to `context`,
requiring new context, plan approval, S4 validation, and S5 before the
ticket can advance again.

## Owner decisions this ticket follows

- One `check(...)` function serving all three boundaries, distinguished
  only by the `boundary` module constant and the extra checks each
  boundary adds on top of the shared target/plan-tuple/ticket comparison
  -- never three separate functions duplicating that shared comparison.
- A stale result is a recorded row, never only a returned flag: every
  boundary that finds staleness writes one `check_result` before
  returning, so `invalidated_tuples` can name exactly which plan/review
  tuples are unsafe to build on from the database alone.
- `refresh_base` refuses a call from the wrong state before any git
  operation, by checking `state_table.TABLE` directly rather than letting
  a rebase run and then discovering the transition would have been
  refused anyway -- an invalid call must never leave a worktree mid-way
  through a rebase for the exception to strand.
- `advance`'s `BEFORE_S4` check and `plan_review_gate`'s freshness check
  are the same boundary, run at the two places the ticket names for it
  (the due-stage guard, and the plan-approval commit); both read the
  target branch from the same `project.yaml` `outbox.DEFAULT_PROJECT_CONFIG`
  read `intent_for_review_quorum` already uses, fresh on every call.

## Decisions this brief did not already settle

- **`Freshness` carries two fields beyond the four the ticket names.**
  `diff_hash` is required by the ticket text itself ("record the computed
  hash... so S5 preflight can bind it"); `check_result_id` is added so a
  caller that just found staleness (`advance`, `_dispatch_pending`) can
  reference the exact row it wrote (as a `red_check` item's `ref`, or in
  `last_error`) without a second query.
- **`BEFORE_DISPATCH`'s "pending intent" is re-queried inside `check`,
  not passed in.** The ticket's exact signature for `check` takes no
  `external_write` row, so `check` finds the ticket's own latest `pending`
  `pr_create`/`pr_update` row itself. At most one such row exists at a
  time (`create_intent` supersedes a ticket's older pending rows for the
  same operation on creation), and `_dispatch_pending` only ever calls
  `check` for the row it is itself about to dispatch, so the row `check`
  finds is always that same row.
- **No `tag` row on a `refresh_base` conflict.** Every other place a
  human-recorded event fires alongside a state transition writes a `tag`
  (`abandon`, `request_changes`, a redirect); `refresh_base`'s owner
  decisions name only the `check_result` row and the `escalation` queue
  item for its conflict path, and `queue.py`'s own `stop` action
  (`transitions.apply(conn, item["ticket_id"], "escalate")`) shows
  `escalate` reaching `escalated` elsewhere with no tag of its own
  either. `actor` and `note` are folded into the `check_result` summary
  and the returned message instead, so they are not silently dropped.
- **`state_table.TABLE` gains one row: `("plan_review", "escalate")`.**
  Every other state `refresh_base` may be called from (`implementing`,
  `checks`) already carried an `escalate` row; `plan_review` did not,
  because nothing before this ticket ever escalated from there. Since a
  human may call `refresh_base` while a ticket sits in `plan_review`
  (the state itself withholds `plan_quorum_fresh` on a stale base rather
  than moving the ticket anywhere), its conflict path needs `escalate` to
  be valid from that state too. `state_table.py` and `transitions.py` are
  not on the concurrent agent's excluded-files list, and the addition is
  purely additive (one more state added to an existing dict-comprehension
  set, not a changed row).
- **`outbox._dispatch_pending` gained one keyword, `project_path`,
  defaulting to `DEFAULT_PROJECT_CONFIG`.** It is explicitly listed as
  "private, yours to extend"; `reconcile_pending`'s own signature (which
  is protected) is unchanged, and its call to `_dispatch_pending` never
  passes the new keyword, so every existing caller is unaffected.
- **Existing tests that drove `plan_review_gate` or the S5 stub driver off
  a bare ticket row with hand-written SHA strings needed a real git
  repository once those two call sites started performing a real fetch.**
  `test_state_table.py`'s two `plan_review_gate` scenarios,
  `test_stub_stages.py`'s S5/S6 stub-driver test, and
  `test_report.py`'s completed-walk builder now clone a small real
  repository (mirroring `test_fixture_project.py`'s own
  `_bare_git_project` convention) on the real `factory/config/project.yaml`
  target branch (`main`) instead of writing literal placeholder SHAs. This
  mirrors what T-A-13 already did to `outbox_receipt.yaml` when
  `review_gate` stopped being a stored-equality check.

## Out of scope

R-S5-14's disjoint base advance (Later); a live deliverer notification
on a superseded pre-dispatch intent beyond the existing supersede-and-
route-to-`checks` path `review_gate` already has; anything under
`factory/`; `runner/schema.py`, `runner/db.py`, `runner/queue.py`,
`runner/tags.py`, `runner/approvals.py`, `runner/binding.py`,
`runner/run_ledger.py`, all untouched by this ticket.
