"""Ticket creation: the one function that inserts a new ticket row.

No `factory` verb calls this -- intake (reading the source ticket, running
the intake stage) belongs to a later ticket. This is the seam that ticket, and every test
here, uses to get a ticket into the record at all.
"""
import sqlite3

from runner import record


def open_ticket(conn: sqlite3.Connection, **fields) -> int:
    """Insert a new ticket in `intake` and return its id."""
    return record.insert(conn, "ticket", state="intake", opened_at=record.now(), **fields)
