"""The artefact registry: one `artefact` row per version of a governed file.

A version is a new row and a new file; the prior row is never touched, and
`supersedes` links each version to the one before it so every superseded
version stays readable. The registry hashes the file it is given and
records its resolved absolute path: the record is machine-local run state,
and a governed export copies artefacts out under its own layout. It never
writes or moves the file itself, so the caller keeps control of where a
stage's output lands.
"""
import hashlib
import sqlite3
from pathlib import Path

from runner import record


def register(
    conn: sqlite3.Connection,
    *,
    ticket_id: int,
    kind: str,
    path: Path,
    stage_run_id: int | None = None,
    supersedes: int | None = None,
    data_class: str | None = None,
) -> int:
    """Register the existing file at `path` as a new `artefact` row and return its id.

    With `supersedes`, the new row is the next version of that artefact and
    must share its ticket and kind; a mismatch is a caller error and raises
    `ValueError` before anything is written. Without it, the row is version 1.
    """
    resolved = Path(path).resolve()
    version = 1
    if supersedes is not None:
        prior = record.get(conn, "artefact", supersedes)
        if prior is None:
            raise ValueError(f"artefact {supersedes} does not exist")
        if prior["ticket_id"] != ticket_id or prior["kind"] != kind:
            raise ValueError(
                f"artefact {supersedes} is {prior['kind']} of ticket {prior['ticket_id']}, "
                f"not {kind} of ticket {ticket_id}"
            )
        version = prior["version"] + 1
    return record.insert(
        conn,
        "artefact",
        ticket_id=ticket_id,
        stage_run_id=stage_run_id,
        kind=kind,
        version=version,
        path=str(resolved),
        hash=hashlib.sha256(resolved.read_bytes()).hexdigest(),
        created_at=record.now(),
        data_class=data_class,
        supersedes=supersedes,
    )


def latest(conn: sqlite3.Connection, ticket_id: int, kind: str) -> sqlite3.Row | None:
    """The highest-version `artefact` row of `kind` for `ticket_id`, or None."""
    return conn.execute(
        "SELECT * FROM artefact WHERE ticket_id = ? AND kind = ? "
        "ORDER BY version DESC, id DESC LIMIT 1",
        (ticket_id, kind),
    ).fetchone()
