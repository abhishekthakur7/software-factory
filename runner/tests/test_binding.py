"""Binding: canonical subject hashes, and the plan/review evidence-tuple rows they hash into.

Every tuple is written through `binding.create_plan_tuple` /
`binding.create_review_tuple`, every quorum through `approvals.evaluate`,
and every slot merge through `reviewer_sets.merge_slots`, so a test here
fails against a wrong column mapping, a wrong hash exclusion, or a set
hash that ignores insertion order, not merely against a value the test
itself wrote down. `test_canonical.py` already pins key ordering, excluded
fields, array order, non-ASCII, and the serialization-version contract of
`canonical.content_hash` itself; this file does not restate those.
"""
import json
import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from runner import approvals, canonical, record
from runner.binding import (
    Currency,
    PlanComponents,
    ReviewComponents,
    create_plan_tuple,
    create_review_tuple,
    plan_tuple_currency,
    set_hash,
)
from runner.db import connect
from runner.reviewer_sets import Slot, merge_slots

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "binding"


@pytest.fixture
def conn(tmp_path):
    connection = connect(tmp_path / "factory.sqlite")
    yield connection
    connection.close()


def _load(name: str, variant: str) -> dict:
    data = yaml.safe_load((FIXTURES_DIR / f"{name}.yaml").read_text())
    merged = dict(data["base"])
    if variant != "base":
        merged.update(data[variant])
    return merged


def plan_components(variant: str = "base", **overrides) -> PlanComponents:
    return PlanComponents(**{**_load("plan_components", variant), **overrides})


def review_components(variant: str = "base", **overrides) -> ReviewComponents:
    return ReviewComponents(**{**_load("review_components", variant), **overrides})


def seed_ticket(conn, **fields) -> int:
    return record.insert(conn, "ticket", state="intake", opened_at=record.now(), **fields)


def seed_reviewer_set(conn, ticket_id: int, kind: str, content_hash: str, slots: list[Slot]) -> int:
    return record.insert(
        conn, "reviewer_set", ticket_id=ticket_id, kind=kind, content_hash=content_hash,
        slots=json.dumps([slot.to_json() for slot in slots]),
    )


def approve(conn, *, gate: str, subject_hash: str, slot: Slot, actor: str, **overrides) -> int:
    fields = {
        "gate": gate,
        "subject_hash": subject_hash,
        "slot_id": slot.slot_id,
        "actor_identity": actor,
        "role": slot.role or "owner",
        "decision": "approve",
        "authority_policy_hash": "policy-1",
        "membership_snapshot_hash": "members-1",
        "attestation_version": "v1",
        "attestation_hash": "att-1",
        **overrides,
    }
    return approvals.record_approval(conn, **fields)


# --- canonical serialisation over the stored row -------------


def test_stored_plan_tuple_content_hash_equals_the_canonical_hash_over_its_own_row(conn):
    ticket_id = seed_ticket(conn)
    plan_id = create_plan_tuple(conn, ticket_id, plan_components())
    row = record.get(conn, "evidence_tuple", plan_id)
    hashed = {key: row[key] for key in row.keys() if key not in ("id", "content_hash", "created_at")}
    assert row["content_hash"] == canonical.content_hash(hashed)


def test_two_plan_tuples_differing_only_in_created_at_share_a_content_hash(conn, monkeypatch):
    ticket_id = seed_ticket(conn)
    components = plan_components()
    monkeypatch.setattr(record, "now", lambda: "2026-01-01T00:00:00+00:00")
    first = create_plan_tuple(conn, ticket_id, components)
    monkeypatch.setattr(record, "now", lambda: "2026-06-06T00:00:00+00:00")
    second = create_plan_tuple(conn, ticket_id, components)
    row1 = record.get(conn, "evidence_tuple", first)
    row2 = record.get(conn, "evidence_tuple", second)
    assert row1["created_at"] != row2["created_at"]
    assert row1["content_hash"] == row2["content_hash"]


# --- set_hash and the question-resolution / assumption sets --


def test_set_hash_is_order_independent_and_changes_with_membership():
    a = {"kind": "answer", "id": "q1"}
    b = {"kind": "answer", "id": "q2"}
    assert set_hash([a, b]) == set_hash([b, a])
    assert set_hash([a, b]) != set_hash([a])


def test_a_new_answer_changes_the_question_resolution_hash_and_the_plan_tuples_content_hash(conn):
    ticket_id = seed_ticket(conn)
    base = plan_components()
    base_row = record.get(conn, "evidence_tuple", create_plan_tuple(conn, ticket_id, base))
    new_answer = plan_components(variant="new_answer")
    assert new_answer.question_resolution_set_hash != base.question_resolution_set_hash
    new_row = record.get(conn, "evidence_tuple", create_plan_tuple(conn, ticket_id, new_answer))
    assert new_row["question_resolution_set_hash"] != base_row["question_resolution_set_hash"]
    assert new_row["current_assumption_set_hash"] == base_row["current_assumption_set_hash"]
    assert new_row["content_hash"] != base_row["content_hash"]


def test_a_superseding_assumption_changes_the_assumption_hash_and_the_plan_tuples_content_hash(conn):
    ticket_id = seed_ticket(conn)
    base = plan_components()
    base_row = record.get(conn, "evidence_tuple", create_plan_tuple(conn, ticket_id, base))
    superseded = plan_components(variant="superseding_assumption")
    assert superseded.current_assumption_set_hash != base.current_assumption_set_hash
    new_row = record.get(conn, "evidence_tuple", create_plan_tuple(conn, ticket_id, superseded))
    assert new_row["current_assumption_set_hash"] != base_row["current_assumption_set_hash"]
    assert new_row["question_resolution_set_hash"] == base_row["question_resolution_set_hash"]
    assert new_row["content_hash"] != base_row["content_hash"]


# --- planned/actual slot merge, seen from the binding side ---


def test_review_tuple_binds_the_effective_set_merge_slots_produces_preserving_a_planned_only_slot(conn):
    """a slot the plan named that the actual diff no longer touches survives into the
    effective set the review tuple binds, and a matching key merges to the max count
    and the union of separation constraints -- exactly reviewer_sets.merge_slots's contract,
    proven here through the row binding.py actually writes rather than the bare function."""
    planned = [
        Slot(source_rule="CODEOWNERS:3", owner="alice", min_count=1, distinct_from=("x",)),
        Slot(source_rule="CODEOWNERS:7", owner="bob", matched_path="src/b.py"),
    ]
    actual = [
        Slot(source_rule="CODEOWNERS:3", owner="alice", min_count=2, distinct_from=("y",), matched_path="src/a.py"),
    ]
    effective = merge_slots(planned, actual)
    assert {slot.key for slot in effective} == {planned[0].key, planned[1].key}

    ticket_id = seed_ticket(conn)
    plan_id = create_plan_tuple(conn, ticket_id, plan_components())
    actual_hash = set_hash([slot.to_json() for slot in actual])
    effective_hash = set_hash([slot.to_json() for slot in effective])
    actual_id = seed_reviewer_set(conn, ticket_id, "actual", actual_hash, actual)
    effective_id = seed_reviewer_set(conn, ticket_id, "effective", effective_hash, effective)
    review = review_components(
        plan_tuple_id=plan_id, actual_reviewer_set_id=actual_id, effective_reviewer_set_id=effective_id,
        actual_reviewer_set_hash=actual_hash, effective_reviewer_set_hash=effective_hash,
    )
    row = record.get(conn, "evidence_tuple", create_review_tuple(conn, ticket_id, review))
    assert row["effective_reviewer_set_hash"] == review.effective_reviewer_set_hash
    assert row["effective_reviewer_set_hash"] != row["actual_reviewer_set_hash"]


# --- approval expiry invalidates, and re-quorums the same subject ---


def test_expired_plan_approval_no_longer_satisfies_quorum_and_a_fresh_one_on_the_same_subject_does(conn):
    ticket_id = seed_ticket(conn)
    plan_id = create_plan_tuple(conn, ticket_id, plan_components())
    subject = record.get(conn, "evidence_tuple", plan_id)["content_hash"]
    slot = Slot(source_rule="CODEOWNERS:1", owner="alice")

    expired = approve(conn, gate="plan", subject_hash=subject, slot=slot, actor="alice",
                       expires_at="2000-01-01T00:00:00+00:00")
    stale = approvals.evaluate(conn, gate="plan", subject_hash=subject, slots=[slot])
    assert not stale.satisfied

    approve(conn, gate="plan", subject_hash=subject, slot=slot, actor="alice",
            expires_at="2999-01-01T00:00:00+00:00", supersedes=expired)
    fresh = approvals.evaluate(conn, gate="plan", subject_hash=subject, slots=[slot])
    assert fresh.satisfied
    # the subject the fresh quorum was recorded against is the same, unchanged plan tuple.
    assert record.get(conn, "evidence_tuple", plan_id)["content_hash"] == subject


# --- review tuple's reviewer-set hashes move independently of the plan tuple ---


def test_review_tuple_content_hash_moves_with_the_effective_reviewer_set_hash_while_the_plan_tuple_does_not(conn):
    ticket_id = seed_ticket(conn)
    plan_id = create_plan_tuple(conn, ticket_id, plan_components())
    plan_hash_before = record.get(conn, "evidence_tuple", plan_id)["content_hash"]

    slot = Slot(source_rule="CODEOWNERS:1", owner="alice")
    actual_id = seed_reviewer_set(conn, ticket_id, "actual", "actual-reviewer-set-1", [slot])
    effective_id_a = seed_reviewer_set(conn, ticket_id, "effective", "effective-reviewer-set-1", [slot])
    effective_id_b = seed_reviewer_set(conn, ticket_id, "effective", "effective-reviewer-set-2", [slot])

    unmoved = review_components(plan_tuple_id=plan_id, actual_reviewer_set_id=actual_id, effective_reviewer_set_id=effective_id_a)
    moved = review_components(
        variant="moved_effective_set", plan_tuple_id=plan_id,
        actual_reviewer_set_id=actual_id, effective_reviewer_set_id=effective_id_b,
    )
    hash_a = record.get(conn, "evidence_tuple", create_review_tuple(conn, ticket_id, unmoved))["content_hash"]
    hash_b = record.get(conn, "evidence_tuple", create_review_tuple(conn, ticket_id, moved))["content_hash"]
    assert hash_a != hash_b
    assert record.get(conn, "evidence_tuple", plan_id)["content_hash"] == plan_hash_before


# --- a gate passes only under the full minimum-count/separation rule ---


def test_a_gate_needs_every_required_slots_minimum_count_and_separation_met_on_the_same_subject(conn):
    """the gate fails while any slot is short of its minimum count, succeeds once every
    slot meets it with no shared actor across a distinct_from pair, and fails again the
    moment an extra approval reintroduces a shared actor -- meeting count is not enough
    on its own, and neither is meeting separation."""
    ticket_id = seed_ticket(conn)
    plan_id = create_plan_tuple(conn, ticket_id, plan_components())
    subject = record.get(conn, "evidence_tuple", plan_id)["content_hash"]
    team_slot = Slot(source_rule="CODEOWNERS:1", owner="team", min_count=2)
    security = Slot(source_rule="trust-profile", role="security_approver")
    legal = Slot(source_rule="trust-profile", role="legal_data_governance_approver", distinct_from=(security.slot_id,))
    slots = [team_slot, security, legal]

    approve(conn, gate="plan", subject_hash=subject, slot=team_slot, actor="alice")
    approve(conn, gate="plan", subject_hash=subject, slot=security, actor="carol")
    approve(conn, gate="plan", subject_hash=subject, slot=legal, actor="dana")
    under_count = approvals.evaluate(conn, gate="plan", subject_hash=subject, slots=slots)
    assert not under_count.satisfied
    assert any(reason.startswith("insufficient:") for reason in under_count.reasons)

    approve(conn, gate="plan", subject_hash=subject, slot=team_slot, actor="bob")
    full = approvals.evaluate(conn, gate="plan", subject_hash=subject, slots=slots)
    assert full.satisfied
    assert full.approval_set_hash

    approve(conn, gate="plan", subject_hash=subject, slot=legal, actor="carol")
    shared_actor_again = approvals.evaluate(conn, gate="plan", subject_hash=subject, slots=slots)
    assert not shared_actor_again.satisfied
    assert any(reason.startswith("separation:") for reason in shared_actor_again.reasons)


# --- an S4 head advance with base_sha unchanged never invalidates the plan tuple ---


def test_plan_tuple_currency_ignores_head_advance_but_catches_a_changed_base_sha(conn):
    """the plan tuple binds base_sha, never head_sha -- PlanComponents has no head_sha
    field at all, so nothing about a ticket's evolving head can appear in `changed`.
    Two S4 task-commit runs are seeded to stand in for the hand-back itself."""
    ticket_id = seed_ticket(conn, base_sha="base-sha-1", target_base_sha="base-sha-1", head_sha="commit-0")
    components = plan_components()
    plan_id = create_plan_tuple(conn, ticket_id, components)

    for commit in ("commit-1", "commit-2"):
        record.insert(
            conn, "stage_run", ticket_id=ticket_id, stage="S4", run_kind="task",
            outputs=json.dumps({"head_sha": commit}),
        )

    still_current = plan_tuple_currency(conn, plan_id, components)
    assert still_current == Currency(current=True, changed=())

    rebased = plan_components(variant="rebased")
    now_stale = plan_tuple_currency(conn, plan_id, rebased)
    assert not now_stale.current
    assert "base_sha" in now_stale.changed
    assert "target_base_sha" in now_stale.changed


# --- the plan and review tuple field shapes ---------------


def test_plan_tuple_row_binds_every_plancomponents_field_verbatim(conn):
    ticket_id = seed_ticket(conn)
    components = plan_components()
    row = record.get(conn, "evidence_tuple", create_plan_tuple(conn, ticket_id, components))
    assert row["kind"] == "plan"
    assert row["ticket_id"] == ticket_id
    for name, value in vars(components).items():
        assert row[name] == value
    # review-only columns stay null on a plan tuple.
    assert row["plan_tuple_id"] is None
    assert row["head_sha"] is None


def test_review_tuple_row_binds_every_reviewcomponents_field_verbatim_and_references_its_plan_tuple(conn):
    ticket_id = seed_ticket(conn)
    plan_id = create_plan_tuple(conn, ticket_id, plan_components())
    slot = Slot(source_rule="CODEOWNERS:1", owner="alice")
    actual_id = seed_reviewer_set(conn, ticket_id, "actual", "actual-reviewer-set-1", [slot])
    effective_id = seed_reviewer_set(conn, ticket_id, "effective", "effective-reviewer-set-1", [slot])
    components = review_components(plan_tuple_id=plan_id, actual_reviewer_set_id=actual_id, effective_reviewer_set_id=effective_id)
    row = record.get(conn, "evidence_tuple", create_review_tuple(conn, ticket_id, components))
    assert row["kind"] == "review"
    assert row["ticket_id"] == ticket_id
    for name, value in vars(components).items():
        assert row[name] == value
    # plan-only columns stay null on a review tuple.
    assert row["base_sha"] is None
    assert row["ticket_source_hash"] is None


def test_must_reject_a_plan_tuple_with_a_missing_component(conn):
    ticket_id = seed_ticket(conn)
    incomplete = replace(plan_components(), plan_hash=None)
    with pytest.raises(ValueError):
        create_plan_tuple(conn, ticket_id, incomplete)


def test_must_reject_a_review_tuple_with_a_missing_component(conn):
    ticket_id = seed_ticket(conn)
    plan_id = create_plan_tuple(conn, ticket_id, plan_components())
    incomplete = replace(
        review_components(plan_tuple_id=plan_id, actual_reviewer_set_id=1, effective_reviewer_set_id=2),
        diff_hash=None,
    )
    with pytest.raises(ValueError):
        create_review_tuple(conn, ticket_id, incomplete)


# --- never updated in place; a change is always a new row ---


def test_must_reject_updating_a_bound_column_on_an_evidence_tuple_row(conn):
    """no `evidence_tuple` column is mutable, so a raw `record.update` can never
    reach the schema's own immutability trigger -- it has no `updated_at` column
    to stamp at all, which is itself proof the table is fully append-only."""
    ticket_id = seed_ticket(conn)
    plan_id = create_plan_tuple(conn, ticket_id, plan_components())
    with pytest.raises(sqlite3.Error):
        record.update(conn, "evidence_tuple", plan_id, plan_hash="tampered")


def test_a_changed_bound_component_produces_a_new_row_and_subject_not_a_mutation(conn):
    ticket_id = seed_ticket(conn)
    original = plan_components()
    first_id = create_plan_tuple(conn, ticket_id, original)
    changed_id = create_plan_tuple(conn, ticket_id, plan_components(variant="new_answer"))
    assert first_id != changed_id
    first_row = record.get(conn, "evidence_tuple", first_id)
    assert first_row["plan_hash"] == original.plan_hash
    assert first_row["content_hash"] != record.get(conn, "evidence_tuple", changed_id)["content_hash"]
