# T-A-05 brief: the run ledger — kinds, attempts, leases, heartbeat, budgets, cost provenance

## What this delivers

The PRD 2.2 run ledger, as one write path instead of scattered
`record.insert`/`record.update` calls:

- `runner/run_ledger.py` — `open_stage_run`, `open_utility_run`,
  `heartbeat`, `finish`, and `settle_cost`. `open_stage_run` computes
  `attempt` as the count of the ticket's prior rows for that stage, plus
  one, and starts the row's lease (`started_at`, `heartbeat_at`,
  `lease_expires_at`, from `factory/config/tiers.yaml`'s default lease
  length unless the caller overrides it). `heartbeat` renews a live run's
  lease; `finish` stamps `outcome`/`ended_at` (and `failure_kind` on a
  `stage_run`). `settle_cost` writes a `stage_run`'s cost group once,
  checking the provenance contract in Python before the schema's
  settle-once trigger gets a chance to run: `cost_basis` must be one of the
  four bases, a non-null `cost` needs a `currency`, and
  `pricing_table_hash` is required exactly when `cost_basis` is
  `price_table_estimate`. `budget` and `s4_per_ticket_budget` read the
  token/wall-clock figures straight out of `tiers.yaml`.
- `runner/schema.py` — a `values` field on `Column`; `ddl()` turns it into
  a `CHECK (col IN (...))` constraint, which SQLite already lets a
  nullable column's `NULL` through. Six new module-level closed-value
  tuples (stage names, run kinds, outcomes, failure kinds, cost bases,
  utility kinds) are each declared once and used by both the schema and
  `run_ledger`. `utility_run` gained mutable `outcome`, `heartbeat_at`,
  `lease_expires_at`, `ended_at`, and `updated_at` columns, since it is now
  opened and finished as two separate writes the same way a `stage_run`
  is. A `VIEWS` tuple and its emission in `ddl()` add
  `stage_reliability_view`, a plain `SELECT` over `stage_run` alone.
- `runner/stages/__init__.py` — `run_stage` now opens, finishes, and
  refuses every `stage_run`/`utility_run` through `run_ledger` instead of
  calling `record.insert`/`record.update` itself. Its observable behaviour
  is unchanged: a missing ticket or unknown stage is still refused as a
  `utility_run` of kind `refused_request` before any `stage_run` exists; a
  stage invoked from the wrong state is still refused as that ticket's own
  `stage_run` with outcome `refused`.
- `factory/config/tiers.yaml` — the tier list, the placeholder per-stage
  budgets (tokens and wall-clock seconds) by tier, an S4-specific
  cumulative per-ticket budget by tier, S5's wall-clock override to `null`
  (expressed as a data override rather than a stage check in code), and
  the default lease length in seconds.

## Row covered

R-T-12 (`docs/prd/02-2-entities.md` lines 34-51, 216): `stage_run` is
always bound to a non-null ticket and a stage in S0 to S7; a child
invocation carries `parent_run_id`; `utility_run` is a separate table for
non-stage work and is excluded from stage reliability by construction.

## Owner decisions this ticket follows

- One write path: `run_ledger` is the only module that inserts or updates
  `stage_run`/`utility_run` rows; `run_stage` calls it rather than
  `record.insert`/`record.update` directly.
- Closed value sets are `CHECK` constraints built from schema data, each
  named tuple declared once in `runner/schema.py` and imported by
  `run_ledger` rather than redeclared.
- `factory/config/tiers.yaml` is read-only at run time (`run_ledger` never
  writes under `factory/`); its budgets are explicitly marked as
  placeholders pending recalibration from real pilot runs.
- `stage_reliability_view` stays minimal (id, ticket_id, stage, attempt,
  verification_attempt, run_kind, outcome, failure_kind, started_at,
  ended_at); narrowing it to first attempts is later work.
- `factory/manifest.yaml`, `factory/config/owners.yaml`, and
  `factory/config/trust-profile.yaml` are untouched — the manifest gets
  its `tiers.yaml` entry once every parallel builder has finished, and the
  owners/trust-profile files belong to a sibling ticket.

## Decisions this brief did not already settle

- A refused-request `utility_run`'s `outcome` is stamped
  `"refused_request"` (matching its `kind`) rather than left `NULL`: the
  prior code never set `outcome` on that row at all, but `finish`'s
  contract is to always stamp an outcome, and no test depends on the
  column staying null.
- `utility_run` needed four columns turned `mutable=True`
  (`outcome`, `heartbeat_at`, `lease_expires_at`, `ended_at`) plus a new
  `updated_at` column, since `record.update` always stamps `updated_at`
  and `utility_run` previously had no mutable columns at all — it was
  always written as a single, fully-formed insert. Opening then finishing
  a utility run as two ledger calls needs somewhere for the second call to
  land.
- Two pre-existing tests in `test_mutable_exceptions.py` asserted a
  cost-settlement write using `cost_basis = "list_price"`, a value that
  was never in the PRD's actual four-value set; both now use
  `"price_table_estimate"` (paired with the `pricing_table_hash` they
  already supplied), which is what that literal was standing in for.
- `budget`'s per-stage override (S5's null wall clock) is expressed as a
  `tiers.yaml` `overrides` map keyed by stage, merged generically over the
  per-tier defaults — not a `budgets` table duplicated eight times, and not
  an `if stage == "S5"` in `run_ledger`.

## Out of scope

Crash recovery over expired leases and outbox-first restart (T-A-15);
budget-abort enforcement and manifest migration on a changed budget
(T-A-19); the reasoning-summary length cap (T-A-15); the first-attempt
narrowing of `stage_reliability_view` and the full measure-view set
(T-A-11); the manifest's own `tiers.yaml` entry (added once every parallel
builder finishes).
