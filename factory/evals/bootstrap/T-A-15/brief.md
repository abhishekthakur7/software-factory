# T-A-15 brief: crash recovery, expired leases, outbox-first restart, reasoning-summary cap

## What this delivers

The restart path over the lease and heartbeat T-A-05 already gave
`stage_run`: a process that dies mid-run leaves its lease to lapse, and
the next `factory advance` for that ticket expires only the runs that are
both lease-lapsed and process-dead, records why, and then offers a fresh
attempt through the ordinary attempt-numbering path -- never a
reconstruction, never a duplicate. Restart also never advances ticket
state on an outbox row a crashed attempt left ambiguous, so reconciliation
runs first. A governed cap on `stage_run.reasoning_summary` closes the one
field an agent could otherwise grow without bound.

- `runner/run_ledger.py` (extended) -- `expire_dead_runs(conn, ticket_id,
  *, now=None) -> list[int]`: for the ticket's still-open (`outcome IS
  NULL`) `stage_run` and `utility_run` rows whose `lease_expires_at` is
  before `now` and whose `process_identity` `process_alive` says is gone,
  finishes each `infrastructure_failure`/`expired_lease` (the
  `utility_run` table carries no `failure_kind` column; `finish` already
  applies it only to `stage_run`, so one call site covers both). A lapsed
  lease whose process is alive, or an open run whose lease has not
  lapsed, is left untouched. Returns the ids it expired.
  `record_reasoning_summary(conn, run_id, text) -> str`: stores at most
  `tiers.yaml`'s `reasoning_summary.max_words` whitespace-split words of
  `text` on `stage_run.reasoning_summary`, read fresh from `tiers.yaml`
  like every other budget in this module, and returns what was stored.
- `runner/cli.py` -- `advance` calls `run_ledger.expire_dead_runs` right
  after `outbox.reconcile_pending` and before computing the due stage or
  evaluating the state's gate.
- `runner/schema.py` -- `stage_run.reasoning_summary` marked `mutable=True`
  (an agent's actual self-report lands at run end, after the row already
  exists at run open, so the field settles in place rather than at
  insert).
- `runner/db.py` -- `USER_VERSION` bumped for the mutability change.
- `factory/config/tiers.yaml` -- a `reasoning_summary: {max_words: 200}`
  block, with its `content_hash` recomputed in `factory/manifest.yaml`.
- `runner/tests/test_crash_recovery.py` and
  `runner/tests/fixtures/crash_recovery/`.
- `runner/tests/test_mutable_exceptions.py` -- `reasoning_summary` added
  to `stage_run`'s hand-written allowlist, since that test keeps its own
  copy by design rather than reading `runner/schema.py`.

## Row covered

R-O-1 (`docs/prd/06-observability.md` line 7; the "Failed and blocked
runs" paragraph of `docs/prd/02-3-ticket-states.md`): every ledger row is
written as work proceeds, never reconstructed after a restart; restart
expires only a run whose lease and process identity are both dead,
records `infrastructure_failure`/`expired_lease`, preserves registered
outputs and the worktree, and reconciles pending external writes before
any state advance; reasoning summaries are governed and length-limited.

## Owner decisions this ticket follows

- The fixed order at the start of `factory advance`: ticket-exists check,
  `outbox.reconcile_pending`, `run_ledger.expire_dead_runs`, then the
  existing due-stage/gate logic. Nothing else in `advance` changed.
- A "killed" run in a test is an open `stage_run`/`utility_run` row (no
  `outcome`) whose `process_identity` names a pid that does not exist,
  seeded by monkeypatching `run_ledger.process_identity` for the single
  call that opens the run and undoing the patch immediately after, so
  every later liveness check in the same test runs the real function
  against the real process.
- `stage_run.reasoning_summary` becomes mutable rather than gaining a
  schema migration path of its own, since it is the one field in this
  ticket's scope that both exists already and needs to change after the
  row is opened; `USER_VERSION` moves with it.

## Decisions this brief did not already settle

- **`expire_dead_runs` shares one query shape across both tables** rather
  than one function per table: `stage_run` and `utility_run` differ only
  in whether `failure_kind` applies, and `finish` already resolves that
  difference, so branching in `expire_dead_runs` itself would just
  duplicate the same open-lease-and-dead-process predicate twice.
- **The per-stage kill-walk fixture (`runner/tests/fixtures/crash_recovery/
  per_stage.yaml`) sets each ticket's state directly**, the same way
  `test_stub_stages.py`'s `_ticket_in` does, rather than walking every
  ticket through its preceding stages and gates from `intake`. The
  criterion under test is the restart mechanic (expire, reconcile,
  reattempt), not gate correctness, which every other stub-stage and
  state-table test already covers; S6's entry alone needs a real prior
  `stage_run` (a passed S5), since `checks`' due-stage logic reads S5's
  latest outcome to decide whether S6 is next.
- **The outbox-first fixture seeds a ticket in `checks`, not `review`.**
  Restart's ordering claim -- reconciliation before any fresh attempt
  opens -- only has a fresh attempt to compare against when a stage is
  actually due; `review` carries no stage. The fixture keeps the rest of
  `test_outbox.py`'s reconcile-first convention (the default trust
  profile and owners, activated through `governance.propose`/`decide`, a
  `digest` intent against the real stub deliverer) and seeds a killed S5
  run so `factory advance` reconciles the intent, expires the dead lease,
  and opens attempt 2 of S5 in one call. The receipt artefact and the
  fresh attempt's own `check_evidence` artefact land in the same
  `artefact` table, so their row ids are directly comparable proof of
  order; a stage_run id and an artefact id are not, since every table
  keeps its own row-id sequence.
- **No new fixture file for the alive-process and not-yet-lapsed
  negative cases.** Both are one-line variations on the same seeding
  helper (`_open_dead_run`), so they stay inline in
  `test_crash_recovery.py` rather than in a YAML file that would just
  restate the same two field values the test already shows.

## Out of scope

The base-freshness check another agent is building in parallel
(`runner/freshness.py`, `runner/refresh_base.py`, the `refresh-base` verb,
and the pre-S4 freshness call inside `advance`); the full stub walk from
`intake` to `pr_opened` continuously across a single ticket (T-A-17);
anything in `runner/gates.py`, `runner/stages/S5.py`,
`runner/stages/__init__.py`, or `runner/outbox.py` beyond what already
existed on `main`.
