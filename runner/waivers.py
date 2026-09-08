"""Waivers: validity of a `waiver` row, and the effective status of a blocking check result.

A `check_result` row is immutable, so `waived` is never stored on it. It is
derived here, at the moment of asking, from a `waiver` row that names the
result and is valid right now -- a waiver that expires, or whose subject,
evidence, policy, or actor authority no longer holds, stops covering the
result without any row changing. Every reader that must show or gate on a
result's effective status (the S6 evidence table, the checks gate, the
dispatch recheck, a `policy_exception` tag) asks this module rather than
joining the two tables itself, so the rule for what a valid waiver is lives
in exactly one place.
"""
import sqlite3
from dataclasses import dataclass

from runner import record

# `check_result.result` values a valid waiver may cover. A `fail` is a
# defect, never an epistemic gap, so no waiver ever turns one into `waived`.
WAIVABLE_RESULTS: frozenset[str] = frozenset({"blind_spot"})


@dataclass(frozen=True)
class Validity:
    valid: bool
    # Empty when valid; otherwise every reason the waiver no longer holds.
    reasons: tuple[str, ...]


def validity(conn: sqlite3.Connection, waiver_id: int, *, now: str | None = None) -> Validity:
    """Whether `waiver_id` names an existing, unexpired waiver at `now`."""
    row = record.get(conn, "waiver", waiver_id)
    if row is None:
        return Validity(False, ("no_such_waiver",))
    now = now or record.now()
    if row["expires_at"] <= now:
        return Validity(False, ("expired",))
    return Validity(True, ())


def waiver_for_result(conn: sqlite3.Connection, check_result_id: int, *, now: str | None = None) -> sqlite3.Row | None:
    """The newest valid waiver naming `check_result_id`, or None when no valid one does."""
    rows = conn.execute(
        "SELECT * FROM waiver WHERE waived_check_result_id = ? ORDER BY id DESC", (check_result_id,)
    ).fetchall()
    for row in rows:
        if validity(conn, row["id"], now=now).valid:
            return row
    return None


def effective_result(conn: sqlite3.Connection, check_result: sqlite3.Row, *, now: str | None = None) -> tuple[str, int | None]:
    """`(status, waiver_id)`: the stored result, or `("waived", id)` when a valid waiver covers a waivable result."""
    if check_result["result"] not in WAIVABLE_RESULTS:
        return check_result["result"], None
    waiver = waiver_for_result(conn, check_result["id"], now=now)
    if waiver is None:
        return check_result["result"], None
    return "waived", waiver["id"]


def blocking_status(conn: sqlite3.Connection, stage_run_id: int, *, now: str | None = None) -> list[dict]:
    """Every blocking-tier `check_result` of `stage_run_id`, in id order, with its effective status.

    Each entry carries the row's `id`, `check_name`, `content_hash`, the
    stored `result`, the effective `status` (`pass`, `fail`, `blind_spot`
    or `waived`) and the covering `waiver_id` when waived.
    """
    rows = conn.execute(
        "SELECT * FROM check_result WHERE stage_run_id = ? AND check_tier = 'blocking' ORDER BY id", (stage_run_id,)
    ).fetchall()
    entries = []
    for row in rows:
        status, waiver_id = effective_result(conn, row, now=now)
        entries.append({
            "id": row["id"], "check_name": row["check_name"], "content_hash": row["content_hash"],
            "result": row["result"], "status": status, "waiver_id": waiver_id,
        })
    return entries


def cleared(conn: sqlite3.Connection, stage_run_id: int, *, now: str | None = None) -> bool:
    """Whether every blocking result of `stage_run_id` is `pass` or validly `waived` at `now`."""
    entries = blocking_status(conn, stage_run_id, now=now)
    return bool(entries) and all(entry["status"] in ("pass", "waived") for entry in entries)
