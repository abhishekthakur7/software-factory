"""The gate states: `intake`, `plan_review`, `checks`, `review`.

Each function derives at most one event from rows already recorded in the
database and returns it, or returns `None` when no rule fires: the ticket
is then waiting on a human, and `factory advance` says so rather than
guessing. This is the thin form later work replaces: real quorum and
reviewer-set derivation, plan and review tuple construction, and freshness
checks that fetch a real branch head all read the same rows this module
reads, with the actual computation in place of a stored equality check.

Every function here but `plan_review_gate` and `intake_gate` writes
nothing; the caller applies the returned event through
`transitions.apply`. `plan_review_gate` is the plan-approval commit
boundary, so its freshness check may itself write one invalidating
`check_result` row before withholding its event -- the same
recorded-invalidation contract `runner/freshness.py` documents, not a
second write path of this module's own. `intake_gate` pins
`ticket.factory_manifest_hash` to the manifest's current hash the first
time it is about to admit a ticket to `context`, since that pin has to
exist before this function's own returned event ever reaches
`transitions.apply` -- every later stage run checks its own resolved
manifest hash against exactly this pin (see
`runner.stages.invoke_agent`).
"""
import json
import sqlite3
from pathlib import Path
from typing import Callable

from runner import approvals, binding, freshness, manifest, plan_tuple, record, waivers
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


def _any_open_question(conn: sqlite3.Connection, ticket_id: int) -> bool:
    return conn.execute(
        "SELECT 1 FROM question WHERE ticket_id = ? AND state = 'open' LIMIT 1", (ticket_id,)
    ).fetchone() is not None


def _planned_slots(conn: sqlite3.Connection, plan_row: sqlite3.Row) -> list[Slot]:
    reviewer_set = conn.execute(
        "SELECT * FROM reviewer_set WHERE ticket_id = ? AND kind = 'planned' AND content_hash = ? "
        "ORDER BY id DESC LIMIT 1",
        (plan_row["ticket_id"], plan_row["planned_reviewer_set_hash"]),
    ).fetchone()
    if reviewer_set is None:
        return []
    return [Slot.from_json(item) for item in json.loads(reviewer_set["slots"] or "[]")]


def intake_gate(conn: sqlite3.Connection, ticket: sqlite3.Row, *, runs_dir: Path = RUNS_DIR) -> str | None:
    """A declined eligibility item rejects; a granted one admits once intake has passed, pinning the manifest hash first."""
    item = _latest(conn, "queue_item", ticket["id"], kind="eligibility")
    if item is None:
        return None
    if item["action"] == "declined":
        return "eligibility_declined"
    if item["action"] == "granted" and _latest_passed(conn, ticket["id"], "intake"):
        if ticket["factory_manifest_hash"] is None:
            record.update(conn, "ticket", ticket["id"], factory_manifest_hash=manifest.current_hash())
        return "eligibility_granted"
    return None


def plan_review_gate(conn: sqlite3.Connection, ticket: sqlite3.Row, *, runs_dir: Path = RUNS_DIR) -> str | None:
    """Full plan quorum, a still-current plan subject, plus the real `BEFORE_IMPLEMENTATION` freshness check admits to implementing.

    A stale base withholds this event rather than firing a redirect of its
    own (see `state_table`); `refresh_base` and the send-backs are applied
    by the caller that records the human's decision, never derived here.
    Any open question -- not only a blocking one -- also withholds it:
    approval can proceed once every question is answered or its
    assumption is explicitly accepted, never while one still owes a human
    a decision. Quorum is evaluated over the plan tuple's own planned
    reviewer set, the same slots the checklist's approval bound; a plan
    tuple that `plan_tuple.derive_components` no longer matches -- a
    changed answer, artefact, verdict, waiver, or any other bound field --
    withholds the event too, since an approval recorded against a
    superseded subject satisfies nothing.
    """
    if _any_open_question(conn, ticket["id"]):
        return None
    plan_row = _latest(conn, "evidence_tuple", ticket["id"], kind="plan")
    if plan_row is None:
        return None
    current = plan_tuple.derive_components(conn, ticket)
    if not binding.plan_tuple_currency(conn, plan_row["id"], current).current:
        return None
    quorum = approvals.evaluate(
        conn, gate="plan", subject_hash=plan_row["content_hash"], slots=_planned_slots(conn, plan_row),
    )
    if not quorum.satisfied:
        return None
    fresh = freshness.check(
        conn, ticket["id"], boundary=freshness.BEFORE_IMPLEMENTATION, target_branch=freshness.target_branch(), runs_dir=runs_dir,
    )
    return "plan_quorum_fresh" if fresh.fresh else None


def _reviewer_set_has_unresolved_slot(reviewer_set: sqlite3.Row) -> bool:
    slots = json.loads(reviewer_set["slots"]) if reviewer_set["slots"] else []
    return any(not slot.get("resolved", True) for slot in slots)


def _checks_cleared(conn: sqlite3.Connection, ticket_id: int) -> bool:
    """Whether checks no longer blocks: its latest run passed outright, or every blocking result on it is validly waived."""
    run = _latest(conn, "stage_run", ticket_id, stage="checks")
    if run is None:
        return False
    return run["outcome"] == "pass" or waivers.cleared(conn, run["id"])


def checks_gate(conn: sqlite3.Connection, ticket: sqlite3.Row, *, runs_dir: Path = RUNS_DIR) -> str | None:
    """A new or unresolved reviewer slot returns to planning; otherwise a cleared checks stage and a passed human_review admit to review.

    A stale review base, like plan_review's stale base, withholds this
    event rather than firing a redirect; only `refresh_base` and the
    send-backs move the ticket away from a stale binding. The checks stage
    counts as cleared either because its latest run passed outright or because
    every blocking result it left is `pass` or a validly waived
    `blind_spot` (`runner.waivers.cleared`); either way the checks stage itself is not
    rerun for it.
    """
    reviewer_set = _latest(conn, "reviewer_set", ticket["id"])
    if reviewer_set is not None and _reviewer_set_has_unresolved_slot(reviewer_set):
        return "checks_new_reviewer_slot"
    if _checks_cleared(conn, ticket["id"]) and _latest_passed(conn, ticket["id"], "human_review"):
        return "checks_pass_to_review"
    return None


def _effective_slots(conn: sqlite3.Connection, review_tuple: sqlite3.Row) -> list[Slot]:
    reviewer_set = conn.execute(
        "SELECT * FROM reviewer_set WHERE id = ?", (review_tuple["effective_reviewer_set_id"],)
    ).fetchone()
    if reviewer_set is None:
        return []
    return [Slot.from_json(item) for item in json.loads(reviewer_set["slots"] or "[]")]


def _review_quorum_satisfied(conn: sqlite3.Connection, review_tuple: sqlite3.Row, write: sqlite3.Row) -> bool:
    """Full quorum on the exact publication subject `write` -- the reconciled intent -- was dispatched under.

    Reads `write["review_approval_subject_hash"]` rather than recomputing
    `publication.review_approval_subject` fresh: a reconciled `pr_create`
    itself moves `ticket.last_remote_head_sha`, which is one of the
    publication target's own fields, so a live recompute here would
    always find yesterday's dispatch "stale" the moment it succeeds. The
    subject a reviewer actually approved is the one this gate confirms
    quorum against, not whatever the target happens to hash to right now.
    """
    quorum = approvals.evaluate(
        conn, gate="review", subject_hash=write["review_approval_subject_hash"], slots=_effective_slots(conn, review_tuple),
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


# The `external_write.last_error` prefix `outbox` writes on a pre-dispatch
# mismatch, naming which route the mismatch traces to. Mirrors
# `outbox.PREDISPATCH_MISMATCH_PREFIX` without importing `outbox`, which
# would make a gate module depend on the worker that dispatches for it.
_PREDISPATCH_MISMATCH_PREFIX = "predispatch_mismatch"

_PREDISPATCH_MISMATCH_EVENTS: dict[str, str] = {
    "context": "review_predispatch_mismatch_to_context",
    "planning": "review_predispatch_mismatch_to_planning",
    "checks": "review_predispatch_mismatch_to_checks",
}


def _predispatch_mismatch_event(write: sqlite3.Row) -> str:
    """The route the outbox's pre-dispatch recheck recorded for `write`, or checks as the fail-safe.

    A superseded write the recheck traced to no component -- an
    already-closed remote pull request routes here too, since that is not
    a binding mismatch at all -- has nothing narrower to redirect to, so
    it takes the same route a review-subject, head, or destination
    mismatch does: checks and human_review simply rebuild the packet.
    """
    reason = write["last_error"] or ""
    prefix = f"{_PREDISPATCH_MISMATCH_PREFIX}:"
    if reason.startswith(prefix):
        component = reason[len(prefix):].split(":", 1)[0].strip()
        if component in _PREDISPATCH_MISMATCH_EVENTS:
            return _PREDISPATCH_MISMATCH_EVENTS[component]
    return _PREDISPATCH_MISMATCH_EVENTS["checks"]


def review_gate(conn: sqlite3.Connection, ticket: sqlite3.Row, *, runs_dir: Path = RUNS_DIR) -> str | None:
    """Full review quorum plus a reconciled, matching receipt opens the pull request; a superseded intent redirects.

    "Reconciled" alone is not enough: the latest `external_write` row must
    also carry a remote identity and a stored receipt whose head and
    payload digest are exactly what the ticket wanted published, so a
    reconciliation that adopted a stale or partial remote object never
    advances the ticket by itself. A superseded intent routes to checks,
    planning or context by reading which binding component the outbox's
    pre-dispatch recheck recorded on it (`_predispatch_mismatch_event`):
    checks when the review subject, ticket head, or destination moved;
    planning when the plan itself moved out from under the review's
    approvals; context when the target base or trust binding moved.
    """
    review_tuple = _latest(conn, "evidence_tuple", ticket["id"], kind="review")
    write = _latest(conn, "external_write", ticket["id"])
    if write is None:
        return None
    if (
        write["state"] == "reconciled"
        and review_tuple is not None
        and _receipt_matches_desired(conn, write)
        and _review_quorum_satisfied(conn, review_tuple, write)
    ):
        return "review_quorum_reconciled"
    if write["state"] == "superseded":
        return _predispatch_mismatch_event(write)
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
