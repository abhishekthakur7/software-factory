# T-A-17 brief: pause, resume, stop, status, and the stub walk from `intake` to `pr_opened`

## What this delivers

Stop and pause are the only human interventions inside a running stage,
and neither may inject steering text into a live model context. A new
module, `runner/control.py`, holds the one predicate that governs both --
whether a ticket has a live run -- plus the pause/resume/stop mechanics
and the data `factory show` reports, so `runner/cli.py`'s new verbs and
`runner/queue.py`'s `act` all read the same rule instead of each
reimplementing it. The stub walk assembles every module built through
phase 1 (the state table, leases, the queue, the outbox, crash recovery)
into one continuous run of a synthetic ticket from `intake` to
`pr_opened`, proving the whole stage interface end to end before any
stage becomes real.

- `runner/control.py` (new) -- `live_run(conn, ticket_id) -> stage_run row
  | None`: the ticket's one open (`outcome IS NULL`) `stage_run` whose
  process is still alive per `run_ledger.process_alive`, or `None`.
  `live_run_refusal(ticket_id) -> str`: the shared refusal message every
  command but `stop` returns while a run is live. `pause(conn,
  ticket_id) -> str`: sets `ticket.pause_requested = 1`, refusing while a
  run is live. `pause_pending(conn, ticket_id) -> bool`: the boundary
  check `advance` calls immediately before starting a due stage or
  evaluating a gate -- if the flag is set, stamps `paused_at` once and
  opens one `manual_pause` item (unless one is already open), and returns
  `True`. `resume(conn, ticket_id, *, actor, runs_dir) -> str`: resolves
  the ticket's open `manual_pause` item through `queue.act`'s existing
  `resume` action, refusing while a run is live or when no such item is
  open. `stop(conn, ticket_id, *, actor, fm_id, note) -> str`: finishes
  every open `stage_run` `aborted_human` (storing `note` as the
  reasoning summary only for a run that has none yet), applies `escalate`
  through `transitions.apply`, tags the ticket `escalation`, and opens one
  `escalation` item referencing the run. `status(conn, ticket_id) ->
  dict`: the ticket's state, its open-or-latest run's stage, attempt,
  elapsed wall clock, tier budget remaining (from `run_ledger.budget`),
  currently registered outputs (artefact id/kind/path), and whether a
  pause is pending -- the data `cli.show` formats into text.
- `runner/cli.py` -- three new verbs, `pause`, `resume`, `stop`, each a
  thin wrapper over `control`; `advance` refuses outright while a live run
  exists, and calls `control.pause_pending` immediately before starting a
  due stage and immediately before evaluating a gate; `run` refuses
  outright while a live run exists, before ever reaching `run_stage`;
  `show` appends `control.status`'s fields (current stage/attempt/elapsed,
  budget remaining, registered outputs, pause pending) after its existing
  per-run lines.
- `runner/queue.py` -- `act` refuses with `ActionRefused` when the item's
  ticket has a live run, before reconciling the outbox or validating the
  action; imports `control` lazily inside the function body, since
  `control.resume` itself calls `queue.act`.
- `runner/tests/test_stage_interface.py` (new) -- criteria 1-12: stop
  terminating a live run, recording `aborted_human` and the reasoning
  summary, and escalating; every command but stop refusing a live run
  unaffected; pause and stop leaving a run's registered artefacts
  byte-for-byte unchanged; pause taking effect only at the next boundary,
  read from the durable column, idempotently across repeated boundary
  hits; resume continuing from the held boundary; `show` reporting stage,
  attempt, elapsed, budget, outputs, and pause state; send-back from every
  open item kind adding no approval record.
- `runner/tests/test_stub_walk.py` (new) and
  `runner/tests/fixtures/stub_walk/` -- criteria 13-21: one synthetic
  ticket walked from `intake` to `pr_opened` through every stub stage,
  each killed once and restarted with no duplicate attempt; a wrong-state
  invocation refused and recorded; the stop-and-resume-from-escalation and
  pause-and-resume sequences exercised mid-walk; every table the walk
  touches carrying rows; an in-place edit on an append-only row refused;
  a shell-string recipe refused; the manifest hash script validating
  identically before and after (the walk never writes under `factory/`);
  the walk's one `pr_create` dispatch leaving exactly two `guard_decision`
  rows (the outbound payload and the inbound receipt); `guard.pass_through`
  refusing a hand-built decision.

## Row covered

R-I-8 (`docs/prd/03-stage-interface.md` line 12): stop terminates a
running stage, records `aborted_human` with the reasoning summary and
governed outputs so far, and moves the ticket to `escalated`; a pause
request instead takes effect at the next stage or S4-attempt boundary;
stop is the only mid-invocation intervention and neither action injects
steering text into a live model context.

R-H-13 (`docs/prd/05-human-interaction.md` line 14): every stage and S4
attempt has visible start/end boundaries; status shows stage, attempt,
elapsed wall clock, budget remaining, current registered outputs, and
whether a pause is pending; a human may request pause at the next
boundary, stop immediately, inspect completed output, or send back from a
pause with no routine approval added; `advance` checks the durable pause
flag before starting each boundary.

## Owner decisions this ticket follows

- A live run is an open `stage_run` whose process is alive; the one
  predicate lives in `control.live_run` and every command that must
  refuse a live run calls it rather than re-deriving the condition.
- Pause sets the durable flag and nothing else; `advance`'s
  `pause_pending` boundary check is what actually stamps `paused_at` and
  opens the `manual_pause` item, always immediately before a due stage
  starts or a gate is evaluated, never mid-invocation.
- Resume resolves the open `manual_pause` item through the existing
  `resume` action in `queue.ACTIONS`, which already clears
  `ticket.pause_requested`/`paused_at` -- no second write path.
- Stop finishes every open `stage_run` `aborted_human`, escalates, tags,
  and opens one `escalation` item with `ref = "stage_run:<id>"`; it never
  checks `live_run`, since it is the one command a live run does not
  refuse.
- Send-back from `plan_approval`, `red_check`, `escalation`,
  `manual_pause`, and `packet_approval` already works through
  `queue.ACTIONS`/`_send_back`; this ticket's own test proves each once,
  with no `approval_record` added.
- The stub walk drives the ticket through `cli.advance` and the same
  human decisions a real run would need (eligibility granted, a plan
  approval, a packet approval that authors the review's own `pr_create`
  outbox intent, and the stub PR deliverer), reusing the real-base-clone
  and trust-profile-activation helpers `test_outbox.py` and
  `test_crash_recovery.py` already established, rather than inventing a
  parallel shortcut.

## Decisions this brief did not already settle

- **`live_run`'s refusal in `queue.act` uses a function-local import of
  `runner.control`.** `control.resume` calls `queue.act` at module scope,
  so importing `control` back at `queue.py`'s own module scope would
  cycle; deferring the import into the one function body that needs it
  breaks the cycle without moving the predicate out of `control.py`,
  which is where the brief for this ticket places it.
- **`factory show`'s new fields live behind `control.status`, a plain
  dict, with `cli.show` doing the text formatting** -- matching `show`'s
  existing convention of building its own line list, and keeping
  `control.py` free of any print-formatting concern.
- **The stop demonstration inside the stub walk targets `S4`.** `stop`
  applies the generic `escalate` event, which `state_table.TABLE` defines
  from every open state except `intake` and `pr_opened` (neither of which
  is where the walk's own dead-run kills land); resuming an escalation
  through `queue.act`'s `resume` action is itself only routed for a
  referenced run whose stage is `S4`, `S5`, or `S6`. `S4` is the only one
  of those three the walk visits while genuinely mid-implementing, so the
  walk stops and resumes there rather than manufacturing an artificial
  `S5`/`S6` detour just to exercise every possible resume route; those
  routes are already reachable through `queue.ACTIONS`/`_resume` without
  a walk-specific test, since `test_act.py` already proves the mapping.
  `intake`'s missing `escalate` row (a gap in `state_table.py`, which
  this ticket does not own) means `factory stop` cannot escalate a ticket
  whose only live run is `S0`; no criterion needs it to, and fixing it
  would touch a file this ticket's brief does not permit editing.
- **`control.status`'s budget-remaining figure reads `tokens_in`/
  `tokens_out` and computed elapsed time, never a stored
  `wall_clock_seconds`.** No driver in this milestone writes that column
  yet (a real invocation, T-A-18 onward, is what will), so reading it
  would always show a full, un-consumed budget regardless of how long a
  run had actually been open; the elapsed time `status` itself computes
  from `started_at`/`ended_at` is the only figure available now that
  reflects reality.
- **The stub walk's guard-crossing count (criterion 20) is exactly two,
  not "one per dispatch."** `outbox.dispatch` guards the outbound payload
  before sending and `outbox._finalize_receipt` separately guards the
  inbound receipt after -- two distinct content-bearing crossings for the
  walk's one successful `pr_create`, each its own `guard_decision` row;
  the test asserts the count and mechanism explicitly rather than a vague
  lower bound.

## Out of scope

Every stage `S0` to `S6` running for real instead of as a stub (T-A-20
onward); the thin sandbox's registered-inputs-only guarantee during a
real invocation (T-A-18); the manifest's full field set and fail-closed
resolution (T-A-19); killing a launcher's child process on `stop` (a
later ticket, once a launcher exists); `intake`'s missing `escalate` row
in `state_table.py` (owned by T-A-04, not this ticket).
