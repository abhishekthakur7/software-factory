# T-A-04 brief: state table as code, the `factory` command skeleton, every stage a stub

## What this delivers

The PRD 2.3 state table encoded as data and enforced in trusted code, so
every ticket transition is either a table lookup or a refusal, never an
`if` chain scattered through the runner. Six modules:

- `runner/state_table.py` — `STATES`, `STAGE_STATE` (the state each stage
  S0-S6 runs from), `TERMINAL_STATES`, the event-keyed transition table,
  and the event-to-close-reason map for a terminal entry. The earlier
  entered-from sets are gone; `test_fence.py` now checks the event table's
  endpoints instead.
- `runner/transitions.py` — `apply(conn, ticket_id, event)`: looks up
  `(current_state, event)`, refuses with a clear exception when no row
  exists, updates `ticket.state`, and stamps `closed_at`/`close_reason` on
  entry to a terminal state.
- `runner/gates.py` — the four gate states (`intake`, `plan_review`,
  `checks`, `review`) each get one thin function deriving an event from
  already-recorded rows (approval quorum, evidence-tuple freshness,
  reviewer-set slots, stage-run outcomes, outbox receipts); no rule firing
  means "waiting on a human."
- `runner/tickets.py` — `open_ticket`, the one function that inserts a new
  ticket row in `intake`.
- `runner/stages/` — `run_stage(conn, ticket_id, stage)` plus one stub
  driver per stage, `S0.py` through `S6.py`. Each driver writes a one-line
  stub artefact of its stage's kind, registers it, and returns `pass`;
  `run_stage` handles attempt numbering, the stage/state precondition, and
  applying a stage's pass event when it has one (S0, S5, S6 don't — their
  exits are gates, not automatic).
- `runner/cli.py` — `factory advance|run|show`, each a thin wrapper.
  `advance` runs the stage due in the ticket's state (a stage whose pass
  leaves the state is always due; S0, S5 and S6 are due until their latest
  run passed), else evaluates the state's gate, else reports the wait on a
  human; `run` is a direct `run_stage` call; `show` prints state and stage
  runs. The run tree lives beside the database, so `--db` moves both.
- `runner/definitions.py` — parses the small YAML front matter every stub
  agent/skill/rubric file carries and rejects a file with none.

Plus the stub `factory/agents/S1-S4.md`, `factory/skills/S1-S4.md`,
`factory/rubrics/S0-S6.md`, their 15 eval directories (one ok fixture, one
front-matter-less reject fixture each), and the manifest additions naming
them and a new `stages:` map.

## Row covered

R-T-5 (docs/prd/02-1-ticket-record.md line 17): the state table is
enforced; a stage invoked from the wrong state is refused and recorded; a
missing ticket or stage is refused before any stage run exists.

## Owner decisions this ticket follows

- Mutable ticket/stage_run/question/external_write/queue_item fields per
  the trigger the sibling ticket is adding; every state or outcome change
  here goes through `record.update`, nothing else.
- Code locations: `runner/cli.py`'s `factory` command, `runner/stages/SN.py`
  drivers, stub files as Markdown with YAML front matter, one eval
  directory each with an ok and a reject fixture.
- Human decisions (abandon, stop, send-backs, refresh_base, request
  changes, merge recorded, escalation resolutions) apply their event
  through `transitions.apply` directly; no gate infers them.

## Thin gate rules

`intake_gate` admits on a granted eligibility item only once the latest S0
run passed; `plan_review_gate` and `checks_gate` withhold their event on a
stale base rather than redirecting; `review_gate` opens the pull request
on quorum plus a reconciled receipt and routes every superseded intent to
`checks`, since which of checks, planning or context "applies" to a
pre-dispatch mismatch is the outbox's reconciliation and arrives with it.
Artefacts are recorded by absolute path: the record is machine-local run
state, and export lays files out under its own scheme.

## Out of scope

Real per-stage agent logic (T-A-20 through T-A-34); `factory queue`,
`act`, `pause`, `resume`, `stop`, `tag`, `abandon`, `export`, `import`,
`purge`, `refresh-base`, `report`; the live quorum/reviewer-set
computation (T-A-09); plan/review tuple construction (T-A-10); freshness
checks that fetch a real branch head (T-A-14); the outbox's real
reconciliation (T-A-13); the manifest's model/budget resolution (T-A-19).
Every gate in `runner/gates.py` reads already-recorded rows only.
