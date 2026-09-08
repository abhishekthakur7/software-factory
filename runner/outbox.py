"""The transactional outbox: every external write is an `external_write` intent row before it is anything else.

`create_intent` is the one writer of new intent rows. It computes the
operation's idempotency key from the row's own key columns, stores the
payload as a governed artefact with its digest, refuses a second intent that
would carry a different payload under an existing key, refuses to create
anything under a key whose earlier row is still ambiguously `sending`, and
supersedes the ticket's older pending intents for the same operation. It
never commits: the caller owns the transaction, which is what lets the
quorum-completing approval and the intent it authorises land together or
not at all.

`intent_for_review_quorum` is that caller's hook: given a ticket, it
evaluates the current review subject's quorum and, when it is satisfied,
creates the `pr_create` (no pull request yet) or `pr_update` (one exists)
intent for it, returning the existing intent when one already binds the
same subject and approval set. Dispatch, reconciliation and the deliverers
that perform an intent live beside this module and read the rows it writes.
"""
import json
import sqlite3
from pathlib import Path
from typing import Mapping

import yaml

from runner import approvals, artefact_registry, canonical, record
from runner.fs import write_text
from runner.paths import FACTORY_DIR, RUNS_DIR
from runner.reviewer_sets import Slot
from runner.schema import EXTERNAL_WRITE_OPERATIONS

DEFAULT_PROJECT_CONFIG = FACTORY_DIR / "config" / "project.yaml"

PR_OPERATIONS: frozenset[str] = frozenset({"pr_create", "pr_update"})

# The `external_write` columns each operation's idempotency key is taken
# over. A pull-request intent is keyed by what it publishes and where; an
# update is further keyed by the pull request it updates and the remote
# head it expects to find. The digest and Jira feedback are keyed by their
# content alone, so re-running the same digest sends nothing twice.
KEY_COLUMNS: dict[str, tuple[str, ...]] = {
    "pr_create": (
        "review_approval_subject_hash",
        "repository",
        "target_ref",
        "head_ref",
        "desired_remote_head_sha",
        "pr_body_hash",
    ),
    "pr_update": (
        "remote_pr_identity",
        "review_approval_subject_hash",
        "repository",
        "target_ref",
        "head_ref",
        "desired_remote_head_sha",
        "expected_prior_remote_head_sha",
        "pr_body_hash",
    ),
    "digest": ("payload_digest",),
    "jira_feedback": ("ticket_id", "payload_digest"),
}


class IntentRefused(Exception):
    """The intent cannot be created without breaking the one-key-one-payload or reconcile-first rule."""


def idempotency_key(operation: str, row: Mapping) -> str:
    """The canonical hash over `operation` and its `KEY_COLUMNS` values in `row`."""
    return canonical.content_hash(
        {"operation": operation, **{name: row.get(name) for name in KEY_COLUMNS[operation]}}
    )


def _store_payload(
    conn: sqlite3.Connection, ticket_id: int | None, key: str, payload: Mapping, runs_dir: Path
) -> int:
    root = runs_dir / "tickets" / str(ticket_id) / "outbox" if ticket_id is not None else runs_dir / "outbox"
    path = root / f"{key}.json"
    write_text(path, canonical.canonical_json(dict(payload)).decode() + "\n")
    return artefact_registry.register(conn, ticket_id=ticket_id, kind="outbox_payload", path=path)


def create_intent(
    conn: sqlite3.Connection,
    *,
    ticket_id: int | None,
    operation: str,
    payload: Mapping,
    runs_dir: Path = RUNS_DIR,
    stage_run_id: int | None = None,
    review_tuple_id: int | None = None,
    review_approval_subject_hash: str | None = None,
    review_approval_set_hash: str | None = None,
    repository: str | None = None,
    target_ref: str | None = None,
    head_ref: str | None = None,
    desired_remote_head_sha: str | None = None,
    expected_prior_remote_head_sha: str | None = None,
    remote_pr_identity: str | None = None,
) -> int:
    """Insert one `pending` intent for `operation` and return its id, or the id of the row its key already names.

    Raises `IntentRefused` when a row under the same key carries a different
    payload digest, or when one is still `sending`. Creating the intent
    marks the ticket's older `pending` rows for the same operation
    `superseded`. The caller commits.
    """
    if operation not in EXTERNAL_WRITE_OPERATIONS:
        raise ValueError(f"unknown external_write operation: {operation!r}")
    row = {
        "ticket_id": ticket_id,
        "stage_run_id": stage_run_id,
        "operation": operation,
        "payload_digest": canonical.content_hash({"payload": dict(payload)}),
        "review_tuple_id": review_tuple_id,
        "review_approval_subject_hash": review_approval_subject_hash,
        "review_approval_set_hash": review_approval_set_hash,
        "publication_target_hash": (
            canonical.content_hash({"repository": repository, "target_ref": target_ref})
            if repository is not None else None
        ),
        "repository": repository,
        "target_ref": target_ref,
        "head_ref": head_ref,
        "desired_remote_head_sha": desired_remote_head_sha,
        "expected_prior_remote_head_sha": expected_prior_remote_head_sha,
        "pr_body_hash": (
            canonical.content_hash({"pr_body": payload["pr_body"]}) if "pr_body" in payload else None
        ),
        "remote_pr_identity": remote_pr_identity,
    }
    key = idempotency_key(operation, row)

    for existing in conn.execute(
        "SELECT * FROM external_write WHERE idempotency_key = ? ORDER BY id", (key,)
    ):
        if existing["payload_digest"] != row["payload_digest"]:
            raise IntentRefused(f"idempotency key {key} already carries a different payload")
        if existing["state"] == "sending":
            raise IntentRefused(f"intent {existing['id']} is still sending; reconcile it first")
        if existing["state"] in ("pending", "reconciled"):
            return existing["id"]

    if ticket_id is not None:
        for stale in conn.execute(
            "SELECT id FROM external_write WHERE ticket_id = ? AND operation = ? AND state = 'pending'",
            (ticket_id, operation),
        ).fetchall():
            record.update(conn, "external_write", stale["id"], state="superseded")

    revision = None
    if operation in PR_OPERATIONS:
        revision = 1 + conn.execute(
            "SELECT COUNT(*) FROM external_write WHERE ticket_id = ? "
            "AND operation IN ('pr_create', 'pr_update') AND state = 'reconciled'",
            (ticket_id,),
        ).fetchone()[0]

    return record.insert(
        conn,
        "external_write",
        **row,
        idempotency_key=key,
        payload_artefact_id=_store_payload(conn, ticket_id, key, payload, runs_dir),
        revision=revision,
        state="pending",
        attempt_count=0,
        created_at=record.now(),
    )


def _pr_body(conn: sqlite3.Connection, ticket_id: int) -> str:
    """The text of the ticket's latest `pr_body` artefact, else its latest `packet`, else empty."""
    for kind in ("pr_body", "packet"):
        artefact = artefact_registry.latest(conn, ticket_id, kind)
        if artefact is not None:
            return Path(artefact["path"]).read_text()
    return ""


def intent_for_review_quorum(
    conn: sqlite3.Connection,
    ticket_id: int,
    *,
    runs_dir: Path = RUNS_DIR,
    project_path: Path = DEFAULT_PROJECT_CONFIG,
    now: str | None = None,
) -> int | None:
    """The pull-request intent the ticket's current review quorum authorises, or None while quorum is unmet.

    Reads the latest review tuple and its effective reviewer set, evaluates
    quorum on the tuple's content hash, and on satisfaction creates a
    `pr_update` when the ticket already carries a pull-request identity
    and a `pr_create` otherwise; the payload is the four fields the
    pull-request route admits. Never commits, so a caller that records the
    quorum-completing approval first lands both in one transaction.
    """
    ticket = record.get(conn, "ticket", ticket_id)
    if ticket is None:
        raise LookupError(f"no such ticket: {ticket_id}")
    review_tuple = conn.execute(
        "SELECT * FROM evidence_tuple WHERE ticket_id = ? AND kind = 'review' ORDER BY id DESC LIMIT 1",
        (ticket_id,),
    ).fetchone()
    if review_tuple is None:
        return None
    reviewer_set = record.get(conn, "reviewer_set", review_tuple["effective_reviewer_set_id"])
    slots = [Slot.from_json(item) for item in json.loads(reviewer_set["slots"] or "[]")] if reviewer_set else []
    quorum = approvals.evaluate(
        conn, gate="review", subject_hash=review_tuple["content_hash"], slots=slots, now=now
    )
    if not quorum.satisfied:
        return None

    project = yaml.safe_load(Path(project_path).read_text())
    target_ref = project["target_branch"]
    return create_intent(
        conn,
        ticket_id=ticket_id,
        operation="pr_update" if ticket["pr_identity"] else "pr_create",
        payload={
            "branch_ref": ticket["branch"],
            "head_sha": ticket["head_sha"],
            "target_ref": target_ref,
            "pr_body": _pr_body(conn, ticket_id),
        },
        runs_dir=runs_dir,
        review_tuple_id=review_tuple["id"],
        review_approval_subject_hash=review_tuple["content_hash"],
        review_approval_set_hash=quorum.approval_set_hash,
        repository=project["name"],
        target_ref=target_ref,
        head_ref=ticket["branch"],
        desired_remote_head_sha=ticket["head_sha"],
        expected_prior_remote_head_sha=ticket["last_remote_head_sha"],
        remote_pr_identity=ticket["pr_identity"],
    )
