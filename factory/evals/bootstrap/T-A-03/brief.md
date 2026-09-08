# T-A-03 brief: artefact registry and append-only enforcement

## What this delivers

The write-path layer over the schema the previous ticket built: an artefact
registry that versions a governed file by kind, path, version and content
hash with a `supersedes` chain, and a schema-level allowlist that makes
every column of every table immutable in place unless the schema says
otherwise. Two modules:

- `runner/artefact_registry.py` — `register()` records a new version of a
  file as a new `artefact` row (version 1, or `supersedes`'s version + 1
  after checking the prior row's ticket and kind match); `latest()` finds
  the current version of a kind for a ticket.
- `runner/record.py` — `insert`/`update`/`get`, the only way any other
  module writes a row. `update` always stamps `updated_at`; which columns
  an `UPDATE` may name is not decided here, it is declared on the column
  data in `runner/schema.py` and enforced by SQLite triggers `ddl()`
  generates from that data, so a raw `UPDATE` bypassing `record.update`
  is refused by the same rule.

## Row covered

R-T-3 (docs/prd/02-1-ticket-record.md): artefacts and the append-only
tables are never edited in place — a new version or new row, superseded
versions stay readable — except for a named, timestamp-carrying set of
mutable exceptions: ticket lifecycle fields, `question.state`, a run's
outcome/lease fields and its one-time cost settlement, an outbox row's
state/attempt/receipt fields, and a queue item's one-time resolution
fields.

## Owner decisions this ticket follows

- Enforcement lives in the database, not in `record.py`. `Column` in
  `runner/schema.py` carries its own mutability: immutable (the default),
  `mutable=True` (updatable in place, unboundedly), or a named
  `once=<sentinel>` (updatable in place exactly
  once, as a group). `ddl()` turns that data into per-table triggers, so
  the allowlist has exactly one home and `record.py` stays a thin helper
  with no hand-written column lists.
- Every in-place change carries its timestamp: `updated_at` now exists on
  `ticket`, `stage_run`, `queue_item` and `question` (`external_write`
  already had it), and `record.update()` stamps it on every call.
- The two once-groups are `stage_run`'s cost settlement (`cost`,
  `currency`, `cost_basis`, `pricing_table_hash`, `cost_settled_at`,
  sentinel `cost_settled_at`) and `queue_item`'s resolution (`resolved_at`,
  `resolved_by`, `action`, `note`, `active_attention_bucket`, sentinel
  `resolved_at`).
- No `DELETE` trigger: governed purge is a separate, later rule.
- `runner/db.py`'s `USER_VERSION` moves to 2 because the schema gained
  triggers and `updated_at` columns.

## Out of scope

The state table's transition enforcement, the runtime adapter's actual
cost-settlement write, the outbox's state machine, and a queue item's
resolution through the `factory act` command — this ticket only builds
the mechanism those later tickets write through.
