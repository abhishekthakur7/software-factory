"""Publication target and review-approval subject: the one home of both hashes final review binds.

`publication_target` names exactly where and what a `pr_create`/`pr_update`
would publish: the operation kind, repository, refs, current PR identity if
any, the desired head, and the remote head the ticket last observed.
`review_approval_subject` folds that destination together with every piece
of evidence a final reviewer's approval must bind -- the review tuple, its
bound blocking check results, the waivers currently covering any of them,
the packet and PR-narrative artefacts, and the effective reviewer set --
into the one subject hash every required final-review slot approves against
(C11, "approvals bind immutable evidence"). Both hashes are taken with
`runner.canonical.content_hash`, the one canonical serialisation every
subject hash in the record uses. `quorum` layers the authority check
`approvals.evaluate` does not make on top of it: a counted approval whose
recorded authority-policy hash or actor-role no longer matches `owners.yaml`
is dropped before counting, so a role reassignment revokes standing quorum
without any row changing.
"""
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from runner import approvals, artefact_registry, canonical, owners, project as project_config, record, waivers
from runner.reviewer_sets import Slot


class PublicationSubjectIncomplete(ValueError):
    """A component the publication target or the review-approval subject requires is not yet on record."""


@dataclass(frozen=True)
class Target:
    operation: str
    repository: str
    target_ref: str
    head_ref: str
    pr_identity: str | None
    desired_head_sha: str
    expected_prior_remote_head_sha: str | None
    hash: str


def _project(project_path: Path) -> dict:
    return project_config.pilot(path=project_path)


def publication_target(
    conn: sqlite3.Connection, ticket: sqlite3.Row, *, project_path: Path = project_config.DEFAULT_PROJECT_CONFIG_PATH,
) -> Target:
    """The exact destination a `pr_create`/`pr_update` intent for `ticket` would publish, hashed.

    `operation` is `pr_update` once the ticket already carries a PR
    identity, `pr_create` otherwise -- the same rule `outbox` used before
    this module existed, now the one place it is decided.
    """
    project = _project(project_path)
    fields = {
        "operation": "pr_update" if ticket["pr_identity"] else "pr_create",
        "repository": project["name"],
        "target_ref": project["target_branch"],
        "head_ref": ticket["branch"],
        "pr_identity": ticket["pr_identity"],
        "desired_head_sha": ticket["head_sha"],
        "expected_prior_remote_head_sha": ticket["last_remote_head_sha"],
    }
    return Target(**fields, hash=canonical.content_hash(fields))


@dataclass(frozen=True)
class Subject:
    review_tuple_hash: str
    check_result_hashes: tuple[str, ...]
    waiver_hashes: tuple[str, ...]
    packet_hash: str
    pr_body_hash: str
    effective_reviewer_set_hash: str
    publication_target_hash: str
    hash: str


def _latest_review_tuple(conn: sqlite3.Connection, ticket_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM evidence_tuple WHERE ticket_id = ? AND kind = 'review' ORDER BY id DESC LIMIT 1",
        (ticket_id,),
    ).fetchone()


def _bound_blocking_check_result_hashes(conn: sqlite3.Connection, review_tuple_id: int) -> tuple[str, ...]:
    rows = conn.execute(
        "SELECT content_hash FROM check_result WHERE evidence_tuple_id = ? AND check_tier = 'blocking' ORDER BY id",
        (review_tuple_id,),
    ).fetchall()
    return tuple(row["content_hash"] for row in rows)


def _valid_review_waiver_hashes(conn: sqlite3.Connection, ticket_id: int, review_tuple: sqlite3.Row, *, now: str | None) -> tuple[str, ...]:
    validity_by_id = waivers.recheck(conn, ticket_id, now=now)
    rows = conn.execute(
        "SELECT * FROM waiver WHERE subject_kind = 'review_tuple' AND subject_hash = ? ORDER BY id",
        (review_tuple["content_hash"],),
    ).fetchall()
    hashes = [
        row["content_hash"] for row in rows
        if validity_by_id.get(row["id"], waivers.Validity(False, ())).valid
    ]
    return tuple(sorted(hashes))


def review_approval_subject(
    conn: sqlite3.Connection, ticket_id: int, *, now: str | None = None, project_path: Path = project_config.DEFAULT_PROJECT_CONFIG_PATH,
) -> Subject:
    """The one subject every required final-review slot must approve identically, hashed.

    Refuses with `PublicationSubjectIncomplete` when the ticket carries no
    review tuple, no bound blocking check result, no packet or `pr_body`
    artefact, or no effective reviewer set -- final review has nothing to
    bind evidence against until every one of those exists.
    """
    ticket = record.get(conn, "ticket", ticket_id)
    if ticket is None:
        raise PublicationSubjectIncomplete(f"no such ticket: {ticket_id}")
    review_tuple = _latest_review_tuple(conn, ticket_id)
    if review_tuple is None:
        raise PublicationSubjectIncomplete(f"ticket {ticket_id} carries no review tuple")

    check_result_hashes = _bound_blocking_check_result_hashes(conn, review_tuple["id"])
    if not check_result_hashes:
        raise PublicationSubjectIncomplete(f"review tuple {review_tuple['id']} binds no blocking check result")

    packet = artefact_registry.latest(conn, ticket_id, "packet")
    if packet is None:
        raise PublicationSubjectIncomplete(f"ticket {ticket_id} carries no packet artefact")
    pr_body = artefact_registry.latest(conn, ticket_id, "pr_body")
    if pr_body is None:
        raise PublicationSubjectIncomplete(f"ticket {ticket_id} carries no pr_body artefact")

    if not review_tuple["effective_reviewer_set_hash"]:
        raise PublicationSubjectIncomplete(f"review tuple {review_tuple['id']} carries no effective reviewer set")

    waiver_hashes = _valid_review_waiver_hashes(conn, ticket_id, review_tuple, now=now)
    target = publication_target(conn, ticket, project_path=project_path)

    fields = {
        "review_tuple_hash": review_tuple["content_hash"],
        "check_result_hashes": list(check_result_hashes),
        "waiver_hashes": list(waiver_hashes),
        "packet_hash": packet["hash"],
        "pr_body_hash": pr_body["hash"],
        "effective_reviewer_set_hash": review_tuple["effective_reviewer_set_hash"],
        "publication_target_hash": target.hash,
    }
    return Subject(
        review_tuple_hash=fields["review_tuple_hash"],
        check_result_hashes=check_result_hashes,
        waiver_hashes=waiver_hashes,
        packet_hash=fields["packet_hash"],
        pr_body_hash=fields["pr_body_hash"],
        effective_reviewer_set_hash=fields["effective_reviewer_set_hash"],
        publication_target_hash=fields["publication_target_hash"],
        hash=canonical.content_hash(fields),
    )


def _reviewer_set_slots(conn: sqlite3.Connection, review_tuple: sqlite3.Row) -> list[Slot]:
    reviewer_set = record.get(conn, "reviewer_set", review_tuple["effective_reviewer_set_id"])
    if reviewer_set is None:
        return []
    return [Slot.from_json(item) for item in json.loads(reviewer_set["slots"] or "[]")]


def _slot_permits_actor(owners_obj: owners.Owners, slot: Slot, actor: str) -> bool:
    """Whether `actor` is still the identity `owners.yaml` names for `slot`'s role, or still its named owner."""
    if slot.role is not None:
        return owners_obj.roles.get(slot.role, {}).get("identity") == actor
    return slot.owner == actor


def quorum(
    conn: sqlite3.Connection,
    ticket_id: int,
    *,
    now: str | None = None,
    owners_path: Path = owners.DEFAULT_OWNERS_PATH,
    project_path: Path = project_config.DEFAULT_PROJECT_CONFIG_PATH,
) -> approvals.Quorum:
    """Full review-gate quorum on the current review-approval subject, with `evaluate`'s missing authority check applied.

    Every current, unexpired, approving `approval_record` on the subject
    is re-checked here against `owners.yaml` right now: a row whose
    `authority_policy_hash` no longer matches the file's current bytes, or
    whose actor no longer holds the slot's role (or is no longer its named
    owner), is dropped before `approvals.evaluate` ever counts it --
    `evaluate` itself only ever asks whether *a* row exists per slot, never
    whether the authority it was recorded under still holds.
    """
    now = now or record.now()
    ticket = record.get(conn, "ticket", ticket_id)
    if ticket is None:
        raise PublicationSubjectIncomplete(f"no such ticket: {ticket_id}")
    review_tuple = _latest_review_tuple(conn, ticket_id)
    if review_tuple is None:
        raise PublicationSubjectIncomplete(f"ticket {ticket_id} carries no review tuple")

    subject = review_approval_subject(conn, ticket_id, now=now, project_path=project_path)
    slots = _reviewer_set_slots(conn, review_tuple)
    slot_by_id = {slot.slot_id: slot for slot in slots}

    owners_obj = owners.load_owners(owners_path)
    policy_hash = owners.authority_policy_hash(owners_path)
    unauthorised_ids: set[int] = set()
    unauthorised_reasons: list[str] = []
    for row in approvals.current_heads(conn, gate="review", subject_hash=subject.hash):
        slot = slot_by_id.get(row["slot_id"])
        if slot is None:
            continue
        authorised = row["authority_policy_hash"] == policy_hash and _slot_permits_actor(owners_obj, slot, row["actor_identity"])
        if not authorised:
            unauthorised_ids.add(row["id"])
            unauthorised_reasons.append(f"unauthorised:{slot.slot_id}:{row['actor_identity']}")

    base = approvals.evaluate(
        conn, gate="review", subject_hash=subject.hash, slots=slots, now=now, excluded_ids=frozenset(unauthorised_ids),
    )
    if unauthorised_reasons:
        return approvals.Quorum(False, tuple(unauthorised_reasons) + base.reasons, None, base.actors)
    return base
