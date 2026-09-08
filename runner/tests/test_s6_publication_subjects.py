"""The publication target and the review-approval subject: both hashes `runner/publication.py` owns.

`seed_ticket`, `seed_review_tuple`, and `approve` are the shared fixture
helpers `test_s6_dispatch.py`, `test_s6_approval_wording.py`, and
`test_s6_self_containedness.py` import from here, the same way
`test_act.py` reuses `test_s5_waivers.py`'s waiver helper: one seeding
shape for a real review-approval subject (a bound blocking check result,
packet and `pr_body` artefacts, an effective reviewer set), rather than
four slightly different copies of it.
"""
import json
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from runner import artefact_registry, approvals, canonical, owners, publication, record
from runner.db import connect
from runner.reviewer_sets import Slot

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "s6_publication"
TICKET_FIXTURE = yaml.safe_load((FIXTURES_DIR / "ticket.yaml").read_text())["base"]

# The pilot's one committed identity: every role in the real `owners.yaml`
# resolves to it, which is exactly what the separation (criterion 6) and
# expiry (criterion 8) tests below need -- two *different* required roles,
# both held by the one real actor the authority check must still accept.
S6_REVIEWER_IDENTITY = owners.load_owners().roles["s6_reviewer"]["identity"]
SENSITIVE_PATH_OWNER_IDENTITY = owners.load_owners().roles["sensitive_path_owner"]["identity"]


@pytest.fixture
def conn(tmp_path):
    connection = connect(tmp_path / "factory.sqlite")
    yield connection
    connection.close()


@pytest.fixture
def runs_dir(tmp_path):
    return tmp_path / "runs"


def seed_ticket(conn, **overrides) -> int:
    fields = {**TICKET_FIXTURE, **overrides}
    fields.setdefault("opened_at", record.now())
    return record.insert(conn, "ticket", **fields)


def seed_review_tuple(
    conn, ticket_id: int, runs_dir: Path, *, slots: list[Slot], content_hash: str, check_result_hash: str | None = None,
) -> tuple[int, int]:
    """A review `evidence_tuple` over `slots`' effective set, one bound blocking `check_result`, and
    packet/`pr_body` artefacts -- everything `publication.review_approval_subject` needs. Returns
    `(review_tuple_id, reviewer_set_id)`."""
    reviewer_set_id = record.insert(
        conn, "reviewer_set", ticket_id=ticket_id, kind="effective",
        content_hash=f"effective-set-{content_hash}", slots=json.dumps([slot.to_json() for slot in slots]),
    )
    review_tuple_id = record.insert(
        conn, "evidence_tuple", kind="review", ticket_id=ticket_id,
        content_hash=content_hash, effective_reviewer_set_id=reviewer_set_id,
        effective_reviewer_set_hash=f"effective-set-{content_hash}", created_at=record.now(),
    )
    stage_run_id = record.insert(conn, "stage_run", ticket_id=ticket_id, stage="S5", attempt=1, outcome="pass")
    record.insert(
        conn, "check_result", stage_run_id=stage_run_id, evidence_tuple_id=review_tuple_id,
        check_name="fixture_check", check_tier="blocking", source="runner", result="pass",
        content_hash=check_result_hash or f"check-{content_hash}", canonical_serialization_version=1,
    )
    if artefact_registry.latest(conn, ticket_id, "packet") is None:
        packet_path = runs_dir / "tickets" / str(ticket_id) / "packet.md"
        packet_path.parent.mkdir(parents=True, exist_ok=True)
        packet_path.write_text("fixture packet\n")
        artefact_registry.register(conn, ticket_id=ticket_id, kind="packet", path=packet_path)
    if artefact_registry.latest(conn, ticket_id, "pr_body") is None:
        pr_body_path = runs_dir / "tickets" / str(ticket_id) / "pr_body.md"
        pr_body_path.parent.mkdir(parents=True, exist_ok=True)
        pr_body_path.write_text("fixture pr body\n")
        artefact_registry.register(conn, ticket_id=ticket_id, kind="pr_body", path=pr_body_path)
    return review_tuple_id, reviewer_set_id


def approve(
    conn, *, subject_hash: str, slot: Slot, ticket_id: int, actor: str = S6_REVIEWER_IDENTITY,
    expires_at: str | None = None, authority_policy_hash: str | None = None,
) -> int:
    return approvals.record_approval(
        conn, gate="review", subject_hash=subject_hash, slot_id=slot.slot_id,
        actor_identity=actor, role=slot.role or "owner", decision="approve",
        authority_policy_hash=authority_policy_hash or owners.authority_policy_hash(),
        membership_snapshot_hash="members-1", attestation_version="v1", attestation_hash="att-1",
        expires_at=expires_at, ticket_id=ticket_id,
    )


def _write_project_config(path: Path, *, name: str, target_branch: str) -> None:
    path.write_text(yaml.safe_dump({"name": name, "target_branch": target_branch}))


# --- publication_target (criterion 1) -----------------------------------


def test_publication_target_folds_operation_repository_refs_identity_and_heads(conn):
    """R-S6-10, criterion 1: a ticket with no PR identity yet hashes a `pr_create` target."""
    ticket_id = seed_ticket(conn, branch="feature/x", head_sha="head-1", pr_identity=None, last_remote_head_sha=None)
    ticket = record.get(conn, "ticket", ticket_id)
    target = publication.publication_target(conn, ticket)
    assert target.operation == "pr_create"
    assert target.repository == "fixture-project"
    assert target.target_ref == "main"
    assert target.head_ref == "feature/x"
    assert target.pr_identity is None
    assert target.desired_head_sha == "head-1"
    assert target.expected_prior_remote_head_sha is None
    assert target.hash == canonical.content_hash({
        "operation": "pr_create", "repository": "fixture-project", "target_ref": "main", "head_ref": "feature/x",
        "pr_identity": None, "desired_head_sha": "head-1", "expected_prior_remote_head_sha": None,
    })


def test_publication_target_is_pr_update_once_the_ticket_carries_a_pr_identity(conn):
    """R-S6-10, criterion 1: a ticket already carrying `pr_identity` hashes a `pr_update` target."""
    ticket_id = seed_ticket(conn, pr_identity="fixture-project#1", last_remote_head_sha="head-0")
    ticket = record.get(conn, "ticket", ticket_id)
    target = publication.publication_target(conn, ticket)
    assert target.operation == "pr_update"
    assert target.pr_identity == "fixture-project#1"
    assert target.expected_prior_remote_head_sha == "head-0"


# --- review_approval_subject (criterion 2) ------------------------------


def test_review_approval_subject_folds_every_named_component(conn, runs_dir):
    """R-S6-10, criterion 2."""
    ticket_id = seed_ticket(conn)
    slot = Slot(source_rule="owners", role="s6_reviewer", min_count=1)
    review_tuple_id, _ = seed_review_tuple(conn, ticket_id, runs_dir, slots=[slot], content_hash="review-1")
    subject = publication.review_approval_subject(conn, ticket_id)

    review_tuple = record.get(conn, "evidence_tuple", review_tuple_id)
    ticket = record.get(conn, "ticket", ticket_id)
    check_result = conn.execute(
        "SELECT content_hash FROM check_result WHERE evidence_tuple_id = ?", (review_tuple_id,)
    ).fetchone()
    packet = artefact_registry.latest(conn, ticket_id, "packet")
    pr_body = artefact_registry.latest(conn, ticket_id, "pr_body")
    target = publication.publication_target(conn, ticket)

    assert subject.review_tuple_hash == review_tuple["content_hash"]
    assert subject.check_result_hashes == (check_result["content_hash"],)
    assert subject.waiver_hashes == ()
    assert subject.packet_hash == packet["hash"]
    assert subject.pr_body_hash == pr_body["hash"]
    assert subject.effective_reviewer_set_hash == review_tuple["effective_reviewer_set_hash"]
    assert subject.publication_target_hash == target.hash
    assert subject.hash == canonical.content_hash({
        "review_tuple_hash": subject.review_tuple_hash,
        "check_result_hashes": list(subject.check_result_hashes),
        "waiver_hashes": list(subject.waiver_hashes),
        "packet_hash": subject.packet_hash,
        "pr_body_hash": subject.pr_body_hash,
        "effective_reviewer_set_hash": subject.effective_reviewer_set_hash,
        "publication_target_hash": subject.publication_target_hash,
    })


def test_review_approval_subject_orders_bound_check_result_hashes_by_id_not_by_value(conn, runs_dir):
    """R-S6-10, criterion 2: the check-result hashes are the canonical *ordered* set, in id order."""
    ticket_id = seed_ticket(conn)
    slot = Slot(source_rule="owners", role="s6_reviewer", min_count=1)
    review_tuple_id, _ = seed_review_tuple(conn, ticket_id, runs_dir, slots=[slot], content_hash="review-order")
    # A second blocking result bound to the same review tuple, whose
    # content hash sorts *before* the first one alphabetically -- if the
    # subject sorted rather than preserved id order, this would flip the
    # tuple relative to insertion order.
    record.insert(
        conn, "check_result", stage_run_id=None, evidence_tuple_id=review_tuple_id, check_name="second_check",
        check_tier="blocking", source="runner", result="pass", content_hash="aaa-comes-first-alphabetically",
        canonical_serialization_version=1,
    )
    subject = publication.review_approval_subject(conn, ticket_id)
    rows = conn.execute(
        "SELECT content_hash FROM check_result WHERE evidence_tuple_id = ? ORDER BY id", (review_tuple_id,)
    ).fetchall()
    assert subject.check_result_hashes == tuple(row["content_hash"] for row in rows)
    assert subject.check_result_hashes[0] != "aaa-comes-first-alphabetically"


@pytest.mark.parametrize("missing", ["review_tuple", "check_result", "packet"])
def test_must_reject_review_approval_subject_when_a_required_component_is_missing(conn, runs_dir, missing):
    """R-S6-10, criterion 2 (refusal half): each component is required, checked independently."""
    ticket_id = seed_ticket(conn)
    if missing == "review_tuple":
        pass
    elif missing == "check_result":
        slot = Slot(source_rule="owners", role="s6_reviewer")
        reviewer_set_id = record.insert(
            conn, "reviewer_set", ticket_id=ticket_id, kind="effective", content_hash="eff-nc",
            slots=json.dumps([slot.to_json()]),
        )
        record.insert(
            conn, "evidence_tuple", kind="review", ticket_id=ticket_id, content_hash="review-nc",
            effective_reviewer_set_id=reviewer_set_id, effective_reviewer_set_hash="eff-nc", created_at=record.now(),
        )
    elif missing == "packet":
        slot = Slot(source_rule="owners", role="s6_reviewer")
        reviewer_set_id = record.insert(
            conn, "reviewer_set", ticket_id=ticket_id, kind="effective", content_hash="eff-np",
            slots=json.dumps([slot.to_json()]),
        )
        review_tuple_id = record.insert(
            conn, "evidence_tuple", kind="review", ticket_id=ticket_id, content_hash="review-np",
            effective_reviewer_set_id=reviewer_set_id, effective_reviewer_set_hash="eff-np", created_at=record.now(),
        )
        record.insert(
            conn, "check_result", stage_run_id=None, evidence_tuple_id=review_tuple_id, check_name="c",
            check_tier="blocking", source="runner", result="pass", content_hash="check-np",
            canonical_serialization_version=1,
        )
    with pytest.raises(publication.PublicationSubjectIncomplete):
        publication.review_approval_subject(conn, ticket_id)


# --- sensitivity to bound evidence and the destination (criteria 3-4) --


def test_changing_a_bound_check_result_changes_the_review_approval_subject_hash(conn, runs_dir):
    """R-S6-10, criterion 3."""
    slot = Slot(source_rule="owners", role="s6_reviewer")
    ticket_a = seed_ticket(conn)
    seed_review_tuple(conn, ticket_a, runs_dir, slots=[slot], content_hash="review-shared", check_result_hash="check-a")
    subject_a = publication.review_approval_subject(conn, ticket_a)

    ticket_b = seed_ticket(conn)
    seed_review_tuple(conn, ticket_b, runs_dir, slots=[slot], content_hash="review-shared", check_result_hash="check-b")
    subject_b = publication.review_approval_subject(conn, ticket_b)

    assert subject_a.hash != subject_b.hash


def test_changing_the_head_ref_or_desired_head_changes_the_target_and_the_subject(conn, runs_dir):
    """R-S6-10, criterion 4: a different head ref or desired head hashes a different publication target
    and therefore a different review-approval subject."""
    slot = Slot(source_rule="owners", role="s6_reviewer")
    ticket_a = seed_ticket(conn, branch="feature/a", head_sha="head-a")
    seed_review_tuple(conn, ticket_a, runs_dir, slots=[slot], content_hash="review-dest")
    target_a = publication.publication_target(conn, record.get(conn, "ticket", ticket_a))
    subject_a = publication.review_approval_subject(conn, ticket_a)

    ticket_b = seed_ticket(conn, branch="feature/b", head_sha="head-b")
    seed_review_tuple(conn, ticket_b, runs_dir, slots=[slot], content_hash="review-dest")
    target_b = publication.publication_target(conn, record.get(conn, "ticket", ticket_b))
    subject_b = publication.review_approval_subject(conn, ticket_b)

    assert target_a.hash != target_b.hash
    assert subject_a.hash != subject_b.hash


def test_changing_the_repository_or_target_ref_changes_the_publication_target_hash(conn, tmp_path):
    """R-S6-10, criterion 4: the project configuration's own repository name and target branch are bound too."""
    ticket_id = seed_ticket(conn)
    ticket = record.get(conn, "ticket", ticket_id)
    project_a = tmp_path / "project_a.yaml"
    project_b = tmp_path / "project_b.yaml"
    _write_project_config(project_a, name="repo-a", target_branch="main")
    _write_project_config(project_b, name="repo-b", target_branch="develop")
    target_a = publication.publication_target(conn, ticket, project_path=project_a)
    target_b = publication.publication_target(conn, ticket, project_path=project_b)
    assert target_a.hash != target_b.hash


# --- quorum: count, separation, authority, expiry (criteria 5-8) -------


def test_fewer_approval_records_than_the_slots_minimum_count_refuses_publication(conn, runs_dir):
    """R-S6-10, criterion 5."""
    slot = Slot(source_rule="owners", role="s6_reviewer", min_count=2)
    ticket_id = seed_ticket(conn)
    seed_review_tuple(conn, ticket_id, runs_dir, slots=[slot], content_hash="review-min-count")
    subject = publication.review_approval_subject(conn, ticket_id)
    approve(conn, subject_hash=subject.hash, slot=slot, ticket_id=ticket_id)

    result = publication.quorum(conn, ticket_id)
    assert not result.satisfied
    assert any(reason.startswith("insufficient:") for reason in result.reasons)


def test_distinct_from_slots_satisfied_by_the_same_actor_refuses_publication(conn, runs_dir):
    """R-S6-10, criterion 6."""
    slot_a = Slot(source_rule="owners", role="s6_reviewer", min_count=1)
    slot_b = Slot(source_rule="sensitive_paths", role="sensitive_path_owner", min_count=1, distinct_from=(slot_a.slot_id,))
    slot_a = replace(slot_a, distinct_from=(slot_b.slot_id,))
    ticket_id = seed_ticket(conn)
    seed_review_tuple(conn, ticket_id, runs_dir, slots=[slot_a, slot_b], content_hash="review-separation")
    subject = publication.review_approval_subject(conn, ticket_id)
    approve(conn, subject_hash=subject.hash, slot=slot_a, ticket_id=ticket_id, actor=S6_REVIEWER_IDENTITY)
    approve(conn, subject_hash=subject.hash, slot=slot_b, ticket_id=ticket_id, actor=SENSITIVE_PATH_OWNER_IDENTITY)

    result = publication.quorum(conn, ticket_id)
    assert not result.satisfied
    assert any(reason.startswith("separation:") for reason in result.reasons)


def test_an_approval_the_authority_policy_no_longer_permits_for_the_slot_refuses_publication(conn, runs_dir):
    """R-S6-10, criterion 7."""
    slot = Slot(source_rule="owners", role="s6_reviewer", min_count=1)
    ticket_id = seed_ticket(conn)
    seed_review_tuple(conn, ticket_id, runs_dir, slots=[slot], content_hash="review-unauthorised")
    subject = publication.review_approval_subject(conn, ticket_id)
    approve(conn, subject_hash=subject.hash, slot=slot, ticket_id=ticket_id, actor="not-a-reviewer")

    result = publication.quorum(conn, ticket_id)
    assert not result.satisfied
    assert any(reason.startswith("unauthorised:") for reason in result.reasons)


def test_expired_approvals_invalidate_the_set_and_fresh_full_quorum_satisfies_it(conn, runs_dir):
    """R-S6-10, criterion 8: two required slots' approvals both expire; nothing counts until two
    fresh records against the same subject satisfy them."""
    slot_a = Slot(source_rule="owners", role="s6_reviewer", min_count=1)
    slot_b = Slot(source_rule="sensitive_paths", role="sensitive_path_owner", min_count=1)
    ticket_id = seed_ticket(conn)
    seed_review_tuple(conn, ticket_id, runs_dir, slots=[slot_a, slot_b], content_hash="review-expiry")
    subject = publication.review_approval_subject(conn, ticket_id)
    past, now, future = "2000-01-01T00:00:00+00:00", "2020-01-01T00:00:00+00:00", "2999-01-01T00:00:00+00:00"

    expired_a = approve(conn, subject_hash=subject.hash, slot=slot_a, ticket_id=ticket_id, expires_at=past, actor=S6_REVIEWER_IDENTITY)
    expired_b = approve(
        conn, subject_hash=subject.hash, slot=slot_b, ticket_id=ticket_id, expires_at=past, actor=SENSITIVE_PATH_OWNER_IDENTITY,
    )
    expired = publication.quorum(conn, ticket_id, now=now)
    assert not expired.satisfied

    # `supersedes` keeps the same-actor same-slot pair from forking: a
    # second unsuperseded head for one (gate, subject, slot, actor) would
    # refuse quorum outright regardless of either row's own expiry.
    approvals.record_approval(
        conn, gate="review", subject_hash=subject.hash, slot_id=slot_a.slot_id, actor_identity=S6_REVIEWER_IDENTITY,
        role=slot_a.role, decision="approve", authority_policy_hash=owners.authority_policy_hash(),
        membership_snapshot_hash="members-1", attestation_version="v1", attestation_hash="att-1",
        expires_at=future, ticket_id=ticket_id, supersedes=expired_a,
    )
    approvals.record_approval(
        conn, gate="review", subject_hash=subject.hash, slot_id=slot_b.slot_id, actor_identity=SENSITIVE_PATH_OWNER_IDENTITY,
        role=slot_b.role, decision="approve", authority_policy_hash=owners.authority_policy_hash(),
        membership_snapshot_hash="members-1", attestation_version="v1", attestation_hash="att-1",
        expires_at=future, ticket_id=ticket_id, supersedes=expired_b,
    )
    fresh = publication.quorum(conn, ticket_id, now=now)
    assert fresh.satisfied
