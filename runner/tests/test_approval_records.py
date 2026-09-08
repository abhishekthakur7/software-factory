"""Approval records: the row shape, quorum over distinct actors, and forked-head detection.

Every row is written through `approvals.record_approval` and every count
through `approvals.evaluate`, so a test here fails against a wrong count,
a wrong expiry comparison, or a fork the query misses, not merely against
a value the test itself wrote down.
"""
import pytest

from runner import approvals, canonical
from runner.db import connect
from runner.reviewer_sets import Slot, derive_actual
from runner.tests.test_reviewer_sets import OWNERS, _commit_codeowners, _init_repo, _ticket

SUBJECT = "subject-1"
ATTESTATION = {"attestation_version": "v1", "attestation_hash": "att-1"}
AUTHORITY = {"authority_policy_hash": "policy-1", "membership_snapshot_hash": "members-1"}


@pytest.fixture
def conn(tmp_path):
    connection = connect(tmp_path / "factory.sqlite")
    yield connection
    connection.close()


def _approve(conn, slot, actor, **overrides):
    fields = {
        "gate": "plan",
        "subject_hash": SUBJECT,
        "slot_id": slot.slot_id,
        "actor_identity": actor,
        "role": slot.role or "owner",
        "decision": "approve",
        **AUTHORITY,
        **ATTESTATION,
        **overrides,
    }
    return approvals.record_approval(conn, **fields)


def test_must_reject_unknown_column_on_an_approval_record(conn):
    slot = Slot(source_rule="CODEOWNERS:1", owner="alice")
    with pytest.raises(ValueError):
        _approve(conn, slot, "alice", not_a_column="x")


def test_approval_record_row_carries_every_binding_field_and_its_own_content_hash(conn):
    """the row binds gate, subject, slot id and scope, actor, role, authority
    policy and membership snapshot, decision, attestation, decision time and
    expiry, and its content hash is the canonical hash over those fields."""
    slot = Slot(source_rule="CODEOWNERS:1", owner="abhishek")
    row_id = _approve(conn, slot, "abhishek", scope="ticket:1", expires_at="2999-01-01T00:00:00+00:00")
    row = conn.execute("SELECT * FROM approval_record WHERE id = ?", (row_id,)).fetchone()
    assert row["gate"] == "plan"
    assert row["subject_hash"] == SUBJECT
    assert row["slot_id"] == slot.slot_id
    assert row["scope"] == "ticket:1"
    assert row["actor_identity"] == "abhishek"
    assert row["role"] == "owner"
    assert row["authority_policy_hash"] == "policy-1"
    assert row["membership_snapshot_hash"] == "members-1"
    assert row["decision"] == "approve"
    assert row["attestation_version"] == "v1"
    assert row["attestation_hash"] == "att-1"
    assert row["decided_at"]
    assert row["expires_at"] == "2999-01-01T00:00:00+00:00"
    assert row["canonical_serialization_version"] == canonical.SERIALIZATION_VERSION
    hashed = {key: row[key] for key in row.keys() if key not in ("id", "content_hash")}
    assert row["content_hash"] == canonical.content_hash(hashed)


def test_must_reject_trust_profile_approval_without_expiry(conn):
    slot = Slot(source_rule="trust-profile", role="security_approver")
    with pytest.raises(ValueError):
        _approve(conn, slot, "abhishek", gate="trust_profile")


def test_quorum_counts_distinct_actors_so_one_actor_twice_counts_once(conn):
    """a re-approval supersedes the actor's earlier row; it does not add a second actor."""
    slot = Slot(source_rule="CODEOWNERS:1", owner="team", min_count=2)
    first = _approve(conn, slot, "alice")
    _approve(conn, slot, "alice", supersedes=first)
    assert not approvals.evaluate(conn, gate="plan", subject_hash=SUBJECT, slots=[slot]).satisfied
    _approve(conn, slot, "bob")
    quorum = approvals.evaluate(conn, gate="plan", subject_hash=SUBJECT, slots=[slot])
    assert quorum.satisfied
    assert quorum.actors[slot.slot_id] == ("alice", "bob")
    assert quorum.approval_set_hash


def test_must_reject_forked_head_for_one_gate_subject_slot_actor(conn):
    """a second unsuperseded row by the same actor on the same slot is a
    fork; superseding the first row resolves it."""
    slot = Slot(source_rule="CODEOWNERS:1", owner="alice")
    first = _approve(conn, slot, "alice")
    _approve(conn, slot, "alice", decision="reject")
    quorum = approvals.evaluate(conn, gate="plan", subject_hash=SUBJECT, slots=[slot])
    assert not quorum.satisfied
    assert any(reason.startswith("forked_head:") for reason in quorum.reasons)
    _approve(conn, slot, "alice", supersedes=first)
    heads = approvals.current_heads(conn, "plan", SUBJECT)
    assert approvals.forked_heads(heads) == [(slot.slot_id, "alice")]


def test_expired_approval_no_longer_counts_toward_quorum(conn):
    slot = Slot(source_rule="CODEOWNERS:1", owner="alice")
    expired = _approve(conn, slot, "alice", expires_at="2000-01-01T00:00:00+00:00")
    assert not approvals.evaluate(conn, gate="plan", subject_hash=SUBJECT, slots=[slot]).satisfied
    _approve(conn, slot, "alice", expires_at="2999-01-01T00:00:00+00:00", supersedes=expired)
    assert approvals.evaluate(conn, gate="plan", subject_hash=SUBJECT, slots=[slot]).satisfied


def test_must_reject_same_actor_across_distinct_from_slots_unless_exempt(conn):
    security = Slot(source_rule="trust-profile", role="security_approver")
    legal = Slot(
        source_rule="trust-profile", role="legal_data_governance_approver",
        distinct_from=(security.slot_id,),
    )
    _approve(conn, security, "abhishek")
    _approve(conn, legal, "abhishek")
    slots = [security, legal]
    blocked = approvals.evaluate(conn, gate="plan", subject_hash=SUBJECT, slots=slots)
    assert not blocked.satisfied
    assert any(reason.startswith("separation:") for reason in blocked.reasons)
    exempt = approvals.evaluate(
        conn, gate="plan", subject_hash=SUBJECT, slots=slots,
        separation_exempt_identities=frozenset({"abhishek"}),
    )
    assert exempt.satisfied


def test_approval_set_hash_is_order_independent_over_the_qualifying_rows(conn):
    slot = Slot(source_rule="CODEOWNERS:1", owner="team", min_count=2)
    _approve(conn, slot, "alice")
    _approve(conn, slot, "bob")
    rows = approvals.current_heads(conn, "plan", SUBJECT)
    assert approvals.approval_set_hash(rows) == approvals.approval_set_hash(list(reversed(rows)))
    assert approvals.approval_set_hash(rows) != approvals.approval_set_hash(rows[:1])


def test_a_recorded_approvals_slot_id_and_scope_trace_back_to_a_derived_reviewer_sets_slot(conn, tmp_path):
    """the slot id and scope stored on an approval are the exact `slot_id`
    and matched path a real CODEOWNERS derivation produced, not a
    hand-typed string that merely happens to look like one (R-S6-6)."""
    repo = _init_repo(tmp_path)
    sha = _commit_codeowners(repo, "CODEOWNERS_precedence")
    derivation = derive_actual(
        conn, ticket_id=_ticket(conn), repo_path=repo, target_base_sha=sha,
        changed_paths=["README.md"], owners=OWNERS, sensitive_paths={},
        authority_policy_hash="policy-1", membership_snapshot_hash="members-1",
    )
    [slot] = derivation.slots

    row_id = approvals.record_approval(
        conn, gate="review", subject_hash="subject-review-1",
        slot_id=slot.slot_id, scope=slot.matched_path, actor_identity=slot.owner,
        role="owner", decision="approve", **AUTHORITY, **ATTESTATION,
    )
    row = conn.execute("SELECT * FROM approval_record WHERE id = ?", (row_id,)).fetchone()
    assert row["slot_id"] == slot.slot_id == "|alice|CODEOWNERS:3"
    assert row["scope"] == slot.matched_path == "README.md"
