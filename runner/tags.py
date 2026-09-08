"""Human tags: the one place any `tag` row is written.

Every event recorded against a human transition -- a send-back, an
abandonment, a tier override, a request for changes, a control-defect
observation -- goes through `tag`, so the target-shape and required-field
rules below are enforced exactly once rather than re-checked at each call
site. `target` is validated against the record before insert: an unknown
target kind or a target row that does not exist fails before anything is
written, and the tag's own `ticket_id` is derived from that row rather than
taken on faith from the caller.
"""
import sqlite3

from runner import record
from runner.schema import TAG_EVENT_KINDS

# event kinds the entity definition marks severity-required; every other
# kind leaves severity null.
SEVERITY_REQUIRED_KINDS = frozenset({"incident", "control_defect", "policy_exception"})

# The target shapes `tag` accepts: `<table>:<id>` for these tables, each of
# whose rows carries `ticket_id` (or, for `ticket`, is the ticket).
_TARGET_TABLES: frozenset[str] = frozenset({"ticket", "stage_run", "approval_record", "queue_item", "artefact", "question"})


class TagRefused(ValueError):
    """The target, kind, fm_id, or severity fails validation before any row is written."""


def _resolve_target(conn: sqlite3.Connection, target: str) -> int | None:
    """The ticket id `target` belongs to, after checking it names a real row."""
    table, _, raw_id = target.partition(":")
    if table not in _TARGET_TABLES or not raw_id:
        raise TagRefused(f"tag target must be one of {sorted(_TARGET_TABLES)}, got {target!r}")
    try:
        target_id = int(raw_id)
    except ValueError as exc:
        raise TagRefused(f"tag target id is not an integer: {target!r}") from exc
    row = record.get(conn, table, target_id)
    if row is None:
        raise TagRefused(f"no such {table}: {target_id}")
    return target_id if table == "ticket" else row["ticket_id"]


def tag(
    conn: sqlite3.Connection,
    *,
    target: str,
    kind: str,
    fm_id: str,
    actor: str,
    note: str | None = None,
    severity: str | None = None,
) -> int:
    """Insert one immutable `tag` row naming `target`'s event and return its id."""
    if kind not in TAG_EVENT_KINDS:
        raise TagRefused(f"unknown tag kind: {kind!r}")
    if not fm_id:
        raise TagRefused(f"a {kind!r} tag requires a failure-mode id")
    if kind in SEVERITY_REQUIRED_KINDS and not severity:
        raise TagRefused(f"a {kind!r} tag requires a severity")
    ticket_id = _resolve_target(conn, target)
    return record.insert(
        conn,
        "tag",
        ticket_id=ticket_id,
        event_kind=kind,
        fm_id=fm_id,
        ref=target,
        severity=severity,
        note=note,
        tagged_by=actor,
        tagged_at=record.now(),
    )
