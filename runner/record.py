"""The record's write path: every row insert and in-place update goes through here.

`insert` appends a row and returns its id. `update` changes a row in place
and always stamps `updated_at`, so an in-place change can never be written
without its timestamp. Which columns may change in place is not decided
here: the schema declares it and the database enforces it, so a raw
`UPDATE` from any other path is refused by the same rule. Neither helper
commits; the caller owns the transaction so that several writes that must
land together can share one.
"""
import sqlite3
from datetime import UTC, datetime


def now() -> str:
    """The record's timestamp format: ISO-8601 in UTC with second precision."""
    return datetime.now(UTC).isoformat(timespec="seconds")


def insert(conn: sqlite3.Connection, table: str, **fields) -> int:
    columns = ", ".join(fields)
    placeholders = ", ".join("?" for _ in fields)
    cursor = conn.execute(
        f"INSERT INTO {table} ({columns}) VALUES ({placeholders})", tuple(fields.values())
    )
    return cursor.lastrowid


def update(conn: sqlite3.Connection, table: str, row_id: int, **fields) -> None:
    """Change `fields` on the row `row_id` of `table`, stamping `updated_at`.

    Raises `sqlite3.IntegrityError` when the schema forbids changing one of
    the named columns in place, or when a one-time field is written twice,
    and `LookupError` when no such row exists.
    """
    fields = {**fields, "updated_at": now()}
    assignments = ", ".join(f"{name} = ?" for name in fields)
    cursor = conn.execute(
        f"UPDATE {table} SET {assignments} WHERE id = ?", (*fields.values(), row_id)
    )
    if cursor.rowcount == 0:
        raise LookupError(f"{table} has no row {row_id}")


def get(conn: sqlite3.Connection, table: str, row_id: int) -> sqlite3.Row | None:
    return conn.execute(f"SELECT * FROM {table} WHERE id = ?", (row_id,)).fetchone()
