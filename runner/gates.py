"""The gate states: `intake`, `plan_review`, `checks`, `review`.

Each function derives at most one event from rows already recorded in the
database and returns it, or returns `None` when no rule fires: the ticket
is then waiting on a human, and `factory advance` says so rather than
guessing. This is the thin form later work replaces: real quorum and
reviewer-set derivation, plan and review tuple construction, and freshness
checks that fetch a real branch head all read the same rows this module
reads, with the actual computation in place of a stored equality check.

Every function here but `plan_review_gate` writes nothing; the caller
applies the returned event through `transitions.apply`. `plan_review_gate`
is the plan-approval commit boundary, so its freshness check may itself
write one invalidating `check_result` row before withholding its event --
the same recorded-invalidation contract `runner/freshness.py` documents,
not a second write path of this module's own.
"""
import json
import sqlite3
from pathlib import Path
from typing import Callable

from runner import approvals, freshness
from runner.paths import RUNS_DIR
from runner.reviewer_sets import Slot


def _latest(conn: sqlite3.Connection, table: str, ticket_id: int, **where) -> sqlite3.Row | None:
    clauses = ["ticket_id = ?"]
    params: list = [ticket_id]
    for column, value in where.items():
        clauses.append(f"{column} = ?")
        params.append(value)
    query = f"SELECT * FROM {table} WHERE {' AND '.join(clauses)} ORDER BY id DESC LIMIT 1"
    return conn.execute(query, params).fetchone()


def _latest_passed(conn: sqlite3.Connection, ticket_id: int, stage: str) -> bool:
    run = _latest(conn, "stage_run", ticket_id, stage=stage)
    return run is not None and run["outcome"] == "pass"


def _quorum(conn: sqlite3.Connection, ticket_id: int, gate: str, subject_hash: str | None) -> bool:
    """At least one approving `approval_record` bound to this exact subject.

    "At least one" is the thin quorum; the real per-role minimum count and
    identity-separation computation replaces this body later.
    """
    if subject_hash is None:
        return False
    row = conn.execute(
        "SELECT 1 FROM approval_record WHERE ticket_id = ? AND gate = ? "
        "AND decision = 'approve' AND subject_hash = ? LIMIT 1",
        (ticket_id, gate, subject_hash),
    ).fetchone()
    return row is not None


def intake_gate(conn: sqlite3.Connection, ticket: sqlite3.Row, *, runs_dir: Path = RUNS_DIR) -> str | None:
    """A declined eligibility item rejects; a granted one admits once S0 has passed."""
    item = _latest(conn, "queue_item", ticket["id"], kind="eligibility")
    if item is None:
        return None
    if item["action"] == "declined":
        return "eligibility_declined"
    if item["action"] == "granted" and _latest_passed(conn, ticket["id"], "S0"):
        return "eligibility_granted"
    return None


def plan_review_gate(conn: sqlite3.Connection, ticket: sqlite3.Row, *, runs_dir: Path = RUNS_DIR) -> str | None:
    """Full plan quorum plus the real `BEFORE_S4` freshness check admits to implementing.

    A stale base withholds this event rather than firing a redirect of its
    own (see `state_table`); `refresh_base` and the send-backs are applied
    by the caller that records the human's decision, never derived here.
    """
    plan_tuple = _latest(conn, "evidence_tuple", ticket["id"], kind="plan")
    if plan_tuple is None or not _quorum(conn, ticket["id"], "plan", plan_tuple["content_hash"]):
        return None
    fresh = freshness.check(
        conn, ticket["id"], boundary=freshness.BEFORE_S4, target_branch=freshness.target_branch(), runs_dir=runs_dir,
    )
    return "plan_quorum_fresh" if fresh.fresh else None


def _reviewer_set_has_unresolved_slot(reviewer_set: sqlite3.Row) -> bool:
    slots = json.loads(reviewer_set["slots"]) if reviewer_set["slots"] else []
    return any(not slot.get("resolved", True) for slot in slots)


def checks_gate(conn: sqlite3.Connection, ticket: sqlite3.Row, *, runs_dir: Path = RUNS_DIR) -> str | None:
    """A new or unresolved reviewer slot returns to planning; otherwise S5 and S6 both passed admits to review.

    A stale review base, like plan_review's stale base, withholds this
    event rather than firing a redirect; only `refresh_base` and the
    send-backs move the ticket away from a stale binding.
    """
    reviewer_set = _latest(conn, "reviewer_set", ticket["id"])
    if reviewer_set is not None and _reviewer_set_has_unresolved_slot(reviewer_set):
        return "checks_new_reviewer_slot"
    if _latest_passed(conn, ticket["id"], "S5") and _latest_passed(conn, ticket["id"], "S6"):
        return "checks_pass_to_review"
    return None


def _effective_slots(conn: sqlite3.Connection, review_tuple: sqlite3.Row) -> list[Slot]:
    reviewer_set = conn.execute(
        "SELECT * FROM reviewer_set WHERE id = ?", (review_tuple["effective_reviewer_set_id"],)
    ).fetchone()
    if reviewer_set is None:
        return []
    return [Slot.from_json(item) for item in json.loads(reviewer_set["slots"] or "[]")]


def _review_quorum_satisfied(conn: sqlite3.Connection, review_tuple: sqlite3.Row) -> bool:
    """Full quorum over the review tuple's effective reviewer set -- the same evaluation `outbox.intent_for_review_quorum` makes before creating the pull-request intent."""
    quorum = approvals.evaluate(
        conn, gate="review", subject_hash=review_tuple["content_hash"], slots=_effective_slots(conn, review_tuple),
    )
    return quorum.satisfied


def _receipt_matches_desired(conn: sqlite3.Connection, write: sqlite3.Row) -> bool:
    """Whether `write`'s stored receipt confirms the remote head and payload the ticket wanted published."""
    if not write["remote_identity"] or write["receipt_artefact_id"] is None:
        return False
    artefact = conn.execute("SELECT * FROM artefact WHERE id = ?", (write["receipt_artefact_id"],)).fetchone()
    if artefact is None:
        return False
    receipt = json.loads(Path(artefact["path"]).read_text())
    return (
        receipt.get("remote_head_sha") == write["desired_remote_head_sha"]
        and receipt.get("payload_digest") == write["payload_digest"]
    )


def review_gate(conn: sqlite3.Connection, ticket: sqlite3.Row, *, runs_dir: Path = RUNS_DIR) -> str | None:
    """Full review quorum plus a reconciled, matching receipt opens the pull request; a superseded intent routes back to checks.

    "Reconciled" alone is not enough: the latest `external_write` row must
    also carry a remote identity and a stored receipt whose head and
    payload digest are exactly what the ticket wanted published, so a
    reconciliation that adopted a stale or partial remote object never
    advances the ticket by itself. The state table routes a pre-dispatch
    mismatch to checks, planning or context "as applicable"; which applies
    is the outbox's reconciliation, which arrives later. Until then every
    superseded intent routes to checks, and the planning and context
    routes are applied only by a caller that decides them.
    """
    review_tuple = _latest(conn, "evidence_tuple", ticket["id"], kind="review")
    write = _latest(conn, "external_write", ticket["id"])
    if write is None:
        return None
    if (
        write["state"] == "reconciled"
        and review_tuple is not None
        and _receipt_matches_desired(conn, write)
        and _review_quorum_satisfied(conn, review_tuple)
    ):
        return "review_quorum_reconciled"
    if write["state"] == "superseded":
        return "review_predispatch_mismatch_to_checks"
    return None


# Every gate takes the run tree root, since the plan-review gate's freshness
# check needs the ticket clone under it; the others accept and ignore it so
# `advance` calls each the same way.
GATES: dict[str, Callable[..., str | None]] = {
    "intake": intake_gate,
    "plan_review": plan_review_gate,
    "checks": checks_gate,
    "review": review_gate,
}
