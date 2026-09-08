# T-A-02 brief: record — SQLite schema for every table, WAL, single writer

## What this delivers

The one local record PRD 2.2 defines: a single SQLite database, opened in
WAL mode, holding every Initial table named by R-T-1, so no stage keeps
state anywhere else between invocations. Three modules:

- `runner/schema.py` — the 23 Initial tables as plain data (`Column`,
  `Table`, `TABLES`, `ddl()`), so T-A-03 can derive the mutable-field
  allowlist and later migrations from the same declarations instead of a
  second copy.
- `runner/db.py` — `connect(path)` opens the database, turns on WAL and
  foreign keys, applies `ddl()` idempotently, and sets `PRAGMA
  user_version = 1`.
- `runner/canonical.py` — the one canonical-JSON and content-hash function
  PRD 2.2's preamble specifies; every content hash and subject hash in the
  record calls it starting with this ticket.

## Row covered

R-T-1 (docs/prd/02-1-ticket-record.md line 13): one SQLite database holds
all run state; the five Later tables are created only by the migration
that lands with the row that first writes them.

## Owner decisions this ticket follows

- Typed schema, integer ids, constraints: every table has
  `id INTEGER PRIMARY KEY`; INTEGER for counts/sequence numbers/booleans/
  versions, REAL for `cost`, TEXT elsewhere with lists and structured
  values as JSON text; `NOT NULL` only where the PRD states a field is
  required, non-null, or mandatory (`stage_run.ticket_id`,
  `stage_run.stage`, `tag.fm_id`, `waiver.expires_at`); FOREIGN KEY on the
  relations the PRD names; `foreign_keys` on per connection.
- Schema as data: a frozen `Column`/`Table` dataclass pair and a
  `TABLES` tuple in PRD order, no ORM, no third-party library.
- No migration framework: `db.py` applies `ddl()` idempotently on every
  connect and sets `PRAGMA user_version = 1`; later tables bump it.
- No lock file: SQLite's own WAL locking plus a busy timeout satisfies the
  ticket title's "single writer".

## Out of scope

Append-only enforcement and the mutable-field allowlist (R-T-3, T-A-03);
the state table and stub stage drivers that write into these tables
(R-T-5, T-A-04). This ticket only creates the tables and the hash
function; nothing here writes a row.
