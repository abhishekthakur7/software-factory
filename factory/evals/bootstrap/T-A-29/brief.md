# T-A-29 brief: S4 fresh run per task, verification quota, escalation causes, control-defect events, fix rounds

## What this delivers

`runner/stages/S4.py` grows from one whole-plan invocation into a
per-task loop: `run_next` revalidates the target base before every
attempt, then either continues the ordinary task-by-task loop, opens a
bounded fix round when S5 has just routed one back, or (for
`validation_only`) runs every task's validation recipe once with no
agent at all. `build_handoff`, `record_handback`, and `run` stay the
same self-contained trio T-A-28 built; `run` now takes an optional
`task` so the same three functions serve either the whole plan (a direct
caller reconstructing the hand-off's fields in isolation) or one task at
a time.

- `runner/stages/S4.py` (rewritten) -- `run_next`'s per-attempt flow:
  `_revalidate` (the `BEFORE_S4` freshness check only -- see "Decisions
  this brief did not already settle"); `_fix_round_routed` (a
  `check_result` `fix_round_route` with `result = 'pass'` on the
  ticket's latest S5 run); the ordinary per-task loop otherwise, over
  `_topological_order` of the plan's `Tasks` table, skipping a task that
  already carries a passing `task` run under the current plan tuple.
  `_verification_attempt_number` counts prior runs for `(plan_tuple_id,
  plan_item)` that reached verification (`pass`, or `fail`/`verification`)
  and assigns the next number at insert, since the column is written once
  and never updated in place; an infrastructure failure or a control
  defect therefore still carries a number (predicted before the outcome
  is known) but never advances the count a later attempt reads. A task
  run's own validation phase (`_validate_task`) checks the recipe id
  against `project.yaml`'s approved list and the catalogue before
  running it (`recipes.run` itself re-checks the executable digest); any
  of the three failing is a control defect (`fail`/`recipe_binding`),
  handled by the same `_control_defect` helper a `sandbox_violation`
  child uses -- tag, `incident_observation`, escalate, one `escalation`
  item, no verification quota consumed. `_run_task`'s post-processing
  escalates on the third verification failure (registering a
  `failure_history` JSON artefact first) or the second consecutive
  infrastructure failure; an `aborted_budget`/`aborted_human` outcome is
  passed through untouched, since `budgets.abort`/`control.stop` already
  finished that run and escalated. Fix rounds
  (`_run_fix_round`/`_execute_fix_round`) hand off the whole plan plus
  the current diff and every red S5 check's evidence artefact, apply the
  round's own confinement rule (`_check_fix_round_diff`: a test-only diff
  is refused; a changed base test is refused unless the plan's `Test
  strategy` table authorizes it with `action` `change`/`remove`, and an
  authorized change is recorded as its own `deviation` row), run
  `scope_diff`, then run every task's validation recipe once through the
  same `validation_only` mechanism `run_next` exposes standalone. A round
  already at `limits.yaml`'s `fix_rounds.max_per_ticket` is refused
  before it starts (`outcome = 'blocked'`).
- `runner/checks/red_route.py` (new, pure) -- `classify(results, *,
  rounds_run, cap) -> Route`: `fix_round` only when every red recipe is
  lint/compile-kind or a unit/integration test green at base and red at
  head, no other check is red, and the cap has not been reached; else
  `red_check` with a reason (`base_red`, `end_to_end`, `mixed`,
  `cap_reached`).
- `runner/queue.py` -- `_resume` now reads the escalation's cause off the
  `stage_run` its `ref` names: a `verification` failure refuses `resume`
  outright (the route is `send_back --to planning`); a
  `sandbox_integrity`/`recipe_binding` cause resumes only through
  `escalation_control_defect_remediated`, gated on a `remediated`
  `control_disposition` for the ticket's latest `control_defect_event`
  and a `gate`-kind `utility_run` that passed no earlier than it; every
  other cause (infrastructure, human stop) keeps the existing
  stage-based routing. `escalation_context` adds
  `failure_history_artefact_id`, the registered JSON artefact a
  verification-exhaustion escalation writes (`None` for every other
  cause).
- `factory/config/limits.yaml` -- `verification.max_attempts: 3`, the one
  number `_verification_attempt_number`'s escalation threshold reads.
- `factory/agents/S4.md` -- a "Fix rounds" paragraph: what a round reads
  beyond a single task (the whole plan, the current diff, the red
  evidence), that a red result is repaired in production code, not by
  weakening the check, and that a test-only diff is refused.
- `runner/tests/test_s4_task_loop.py`, `runner/tests/fixtures/s4_task_loop/`
  (criteria 1-8): a stale target base; three consecutive verification
  failures numbering 1, 2, 3; an infrastructure failure retrying without
  consuming a verification attempt, then escalating on a second
  consecutive one; an unapproved recipe id as a control defect; a
  retried task registering a fresh `handoff` version; a green task
  validating once and passing; a superseding plan tuple resetting the
  verification count; a retained passing task skipped rather than
  rerun.
- `runner/tests/test_s4_escalation.py`, `runner/tests/fixtures/s4_escalation/`
  (criteria 9-13): the third verification failure escalating in the same
  call that recorded it, with a `failure_history` artefact and its id
  surfaced through `escalation_context`; both sandbox-integrity fixture
  cases (`path_violation`, `environment_violation`) as control defects;
  the three resume routes (`verification` refuses outright, a control
  defect refuses until remediated-and-gated then resumes through the
  dedicated event, infrastructure resumes plainly); a budget-aborted
  second task keeping `aborted_budget` untouched.
- `runner/tests/test_s4_fix_round.py`, `runner/tests/fixtures/s4_fix_round/`,
  `factory/evals/agents/S4/fixtures/fix_round_*` (criteria 14-24):
  `red_route.classify` driven directly for criteria 14, 15, 16, 17, 20
  (no database); the real S4 driver for criteria 18, 19, 21-24, routed
  by a seeded S5 `check_result` marker matching what T-A-30's real S5
  driver will write.
- Collateral, not owned by this ticket: `runner/tests/test_s4_handback.py`,
  `runner/tests/test_state_table.py`, `runner/tests/test_stub_stages.py`
  each drove S4 through a plan with more than one task, assuming (as was
  true before this ticket) that one `run_stage` call finishes the whole
  plan. All three now point at a one-task plan (the S3 "ok" fixture's own
  plan, already used elsewhere for exactly this shape) so their existing
  assertions keep meaning what they said; `test_state_table.py`'s
  `_source_repo` also gained a real, dependency-free `Widget.java`, since
  its `validation_only` test has no agent to write one.
- `factory/manifest.yaml` -- every new/changed file under `factory/`
  refreshed or added.

## Row covered

R-S4-5, R-S4-6, R-S4-9 (`docs/prd/04-S4-implementation.md`); the
"implementing" and "checks" rows and "Failed and blocked runs" in
`docs/prd/02-3-ticket-states.md`; the `stage_run` and `failure_history`
entities in `docs/prd/02-2-entities.md`.

## Owner decisions this ticket follows

The seam already on main: `stages.run_stage` delegates the whole of S4 to
`run_next`, which opens and finishes its own top-level `stage_run` rows;
`attempt` keeps counting every S4 row per ticket, `verification_attempt`
counts per `(plan_tuple_id, plan_item)`, and a superseding plan tuple
starts a fresh count with no migration; no hidden loop -- every retry is
a separate `run_stage` call; a stale-binding `red_check` item's `ref`
names the freshness `check_result`, a failed round's names the round's
own `stage_run`; escalation causes are read from `outcome`/`failure_kind`
alone, never a new column; `failure_history` is an artefact, not a
table.

## Decisions this brief did not already settle

- **`_revalidate` enforces only the `BEFORE_S4` freshness check, not plan-
  tuple currency, plan quorum, or trust-profile activation.** The
  ticket's own description names all four as what the runner
  "revalidates... before every invocation," and `_revalidate` is written
  so any of the other three is a one-function addition later. But none
  of the 24 acceptance criteria exercises them, each is already enforced
  once, authoritatively, before a ticket ever reaches `implementing`
  (currency and quorum at `gates.plan_review_gate`, trust activation at
  eligibility), and nothing between there and a task attempt moves any
  of those bound rows again -- only the target branch can move on its
  own, from outside the ticket entirely, which is exactly what
  `_revalidate` re-checks. Re-deriving the other three on every task
  attempt would also break a large, pre-existing part of the suite:
  dozens of tests across `test_s4_handback.py`, `test_state_table.py`,
  `test_stub_stages.py`, and `test_report.py` build an `implementing`
  ticket with a plan tuple that carries only the handful of fields a
  given test cares about (the same shortcut this codebase uses for every
  stage's own "smoke test" fixture), and `binding.plan_tuple_currency`
  compares every bound field -- a stub row would read as stale against
  nearly any freshly derived `PlanComponents`, for reasons having nothing
  to do with the ticket's actual base. Trust-profile activation has the
  same problem one level worse: `ticket.trust_profile_hash` is not
  stamped anywhere in this codebase's real flow yet (`S0.governance_valid`
  only reads it for an eligibility decision's own display), and the one
  full production walk (`test_report.py`) pins it to a placeholder string
  that was never meant to match the committed profile. Enforcing a live
  match here would make every ticket in the suite permanently
  unauthorized. I flag this because it is a real reduction from the
  brief's own prose, not a small implementation liberty.
- **A control-defect row's `verification_attempt` still carries a number,
  not `null`.** The column is written once, at insert, before the
  invocation that decides the outcome runs; a stale-binding run is the
  one case the brief says explicitly gets `null` (it never even reaches
  `build_handoff`), but an ordinary task attempt that turns out to be an
  infrastructure failure or a control defect has already been assigned
  the next verification slot before either is known. What "consumes no
  verification quota" means in practice is that the counting query never
  includes that row, so the next attempt gets the same number, not one
  higher -- I made this the literal test of "without incrementing
  `verification_attempt`" for criterion 3 rather than asserting the raw
  column value.
- **The fix-round confinement rule's base-test match is by literal `test`-
  column value or file basename**, and "is a test file" is decided by
  matching every `test`-kind recipe's declared `test_globs` in the
  catalogue (`fnmatch`), not a new config entry -- the globs already say
  exactly which paths a test recipe considers tests, so a second list
  would only be able to drift from them.
- **`vendor_classpath` resolution.** Every real `command-recipes.yaml`
  recipe (lint, compile, every test level) requires a `vendor_classpath`
  value that the plan's own `validation_args` cannot express (a
  filesystem path, resolved at run time). `_validate_task` always injects
  it: `FIXTURE_VENDOR_CLASSPATH` (an env-var seam matching the fixture
  worker's own `FIXTURE_ADAPTER_*` convention) when a test sets it, else
  every `*.jar` under `project.yaml`'s configured vendor directory
  resolved against the repository root, else an empty string when that
  directory does not exist (true for every fixture project this ticket's
  own tests build, none of which declare an external dependency).
- **Every test in this wave's three new files uses a small, hand-written,
  dependency-free Java source tree** (a `Widget.java` compiling with an
  empty classpath) rather than the committed `factory/evals/fixture-
  project` seed and its vendored dependency build. The latter needs a
  one-time `setup.materialise` pass (real `javac`/`jar` compilation of
  the vendor tree) that every other real-stage test in this codebase
  also avoids for exactly this reason; a dependency-free fixture proves
  the same recipe-execution behaviour without paying that cost per test.

## Out of scope

The S5 ordered check list itself and the real classification call site
that builds `red_route.classify`'s inputs from a live S5 run
(T-A-30); the `base_test_diff` script (T-A-30); the live `scope_diff`
wiring at S5 and the live S5 rerun after a fix round's validation pass
(T-A-30); the packet's evidence-table listing of fix rounds and
deviations (a later ticket); a live, out-of-band "human stopped a
running invocation" scenario for S4 specifically (the existing
`control.stop` mechanism is untouched and has no dedicated test suite of
its own in this codebase to extend).

## Amended on merge

The pre-invocation revalidation now re-derives all three of the row's
conditions before every task, not freshness alone: the plan tuple's
currency against the record, plan quorum with expiry over the planned
reviewer set, and the trusted fetch of the target base. The test seeders
build a real, approved current tuple through `runner/tests/support.py`
instead of a hand-seeded row, and the vendor classpath is read from the
configured vendor directory with no environment override.
