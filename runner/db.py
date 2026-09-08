"""Open the record: one SQLite database, WAL mode, `foreign_keys` on.

`connect` is the entire module. There is no ORM, no repository layer, and
no module-level connection: every caller opens its own connection and is
responsible for closing it. SQLite's own WAL locking plus a busy timeout
is the record's single writer — a second lock file would just be another
thing that can go stale.
"""
import sqlite3
from pathlib import Path

from runner.paths import RUNS_DIR
from runner.schema import ddl

# Bumped by later tickets when they extend or migrate the schema.
USER_VERSION = 9

_BUSY_TIMEOUT_MS = 5000


def connect(path: Path = RUNS_DIR / "factory.sqlite") -> sqlite3.Connection:
    """Open `path`, creating and migrating the schema in place if needed.

    Safe to call repeatedly against the same file: `ddl()` statements are
    `CREATE TABLE IF NOT EXISTS`, so a second connect neither errors nor
    duplicates state.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute(f"PRAGMA busy_timeout = {_BUSY_TIMEOUT_MS}")
    for statement in ddl():
        connection.execute(statement)
    # PRAGMA does not accept bound parameters; USER_VERSION is a module
    # constant, never user input.
    connection.execute(f"PRAGMA user_version = {USER_VERSION}")
    connection.commit()
    return connection
