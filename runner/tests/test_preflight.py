"""S5 preflight: `binding.preflight_review_tuple` verifies every candidate component,
in order, before creating the review tuple -- a missing or stale one refuses tuple
creation before any write, and success creates exactly one row.
"""
import json
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from runner import approvals, record
from runner.binding import (
    PlanComponents,
    PreflightRefused,
    ReviewComponents,
    create_plan_tuple,
    preflight_review_tuple,
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
    return record.insert(conn, "ticket", state="checks", opened_at=record.now(), **fields)


def seed_reviewer_set(conn, ticket_id: int, kind: str, content_hash: str, slots: list[Slot]) -> int:
    return record.insert(
        conn, "reviewer_set", ticket_id=ticket_id, kind=kind, content_hash=content_hash,
        slots=json.dumps([slot.to_json() for slot in slots]),
    )


def approve(conn, *, subject_hash: str, slot: Slot, actor: str, **overrides) -> int:
    fields = {
        "gate": "plan",
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


class Scenario:
    """A fully wired, passing preflight setup; each test mutates exactly one thing."""

    def __init__(self, conn):
        self.conn = conn
        self.ticket_id = seed_ticket(conn, base_sha="base-sha-1", target_base_sha="base-sha-1")
        self.plan_components = plan_components()
        self.plan_tuple_id = create_plan_tuple(conn, self.ticket_id, self.plan_components)
        self.plan_row = record.get(conn, "evidence_tuple", self.plan_tuple_id)

        self.planned_slots = [Slot(source_rule="CODEOWNERS:1", owner="alice")]
        self.actual_slots = [Slot(source_rule="CODEOWNERS:1", owner="alice", matched_path="src/a.py")]
        self.effective_slots = merge_slots(self.planned_slots, self.actual_slots)

        seed_reviewer_set(
            conn, self.ticket_id, "planned", self.plan_components.planned_reviewer_set_hash, self.planned_slots,
        )
        self.actual_id = seed_reviewer_set(conn, self.ticket_id, "actual", "actual-reviewer-set-1", self.actual_slots)
        self.effective_id = seed_reviewer_set(
            conn, self.ticket_id, "effective", "effective-reviewer-set-1", self.effective_slots,
        )

        self.plan_slots = [Slot(source_rule="CODEOWNERS:2", owner="reviewer")]
        approve(conn, subject_hash=self.plan_row["content_hash"], slot=self.plan_slots[0], actor="reviewer-1")
        self.quorum = approvals.evaluate(
            conn, gate="plan", subject_hash=self.plan_row["content_hash"], slots=self.plan_slots,
        )
        assert self.quorum.satisfied

        self.review_components = review_components(
            plan_tuple_id=self.plan_tuple_id,
            plan_approval_set_hash=self.quorum.approval_set_hash,
            actual_reviewer_set_id=self.actual_id,
            actual_reviewer_set_hash="actual-reviewer-set-1",
            effective_reviewer_set_id=self.effective_id,
            effective_reviewer_set_hash="effective-reviewer-set-1",
        )

    def run(self, **overrides):
        return preflight_review_tuple(
            self.conn,
            self.ticket_id,
            plan_tuple_id=overrides.pop("plan_tuple_id", self.plan_tuple_id),
            plan_slots=overrides.pop("plan_slots", self.plan_slots),
            components=overrides.pop("components", self.review_components),
            current_plan=overrides.pop("current_plan", self.plan_components),
            now=overrides.pop("now", None),
        )


def test_preflight_success_creates_the_review_tuple_and_it_reads_back(conn):
    scenario = Scenario(conn)
    review_id = scenario.run()
    row = record.get(conn, "evidence_tuple", review_id)
    assert row["kind"] == "review"
    assert row["plan_tuple_id"] == scenario.plan_tuple_id
    assert row["plan_approval_set_hash"] == scenario.quorum.approval_set_hash
    assert row["actual_reviewer_set_id"] == scenario.actual_id
    assert row["effective_reviewer_set_id"] == scenario.effective_id
    assert row["head_sha"] == scenario.review_components.head_sha
    assert row["diff_hash"] == scenario.review_components.diff_hash


def test_must_reject_a_missing_plan_tuple(conn):
    scenario = Scenario(conn)
    with pytest.raises(PreflightRefused, match="missing_plan_tuple"):
        scenario.run(plan_tuple_id=scenario.plan_tuple_id + 1000)


def test_must_reject_a_stale_plan_tuple(conn):
    scenario = Scenario(conn)
    stale_current = plan_components(variant="rebased")
    with pytest.raises(PreflightRefused, match="stale_plan_tuple"):
        scenario.run(current_plan=stale_current)


def test_must_reject_no_quorum(conn):
    scenario = Scenario(conn)
    unapproved_slot = Slot(source_rule="CODEOWNERS:9", owner="nobody")
    with pytest.raises(PreflightRefused, match="no_plan_quorum"):
        scenario.run(plan_slots=[unapproved_slot])


def test_must_reject_expired_quorum(conn):
    scenario = Scenario(conn)
    expiring_slot = Slot(source_rule="CODEOWNERS:3", owner="expiring")
    approve(
        conn, subject_hash=scenario.plan_row["content_hash"], slot=expiring_slot, actor="reviewer-2",
        expires_at="2000-01-01T00:00:00+00:00",
    )
    with pytest.raises(PreflightRefused, match="no_plan_quorum"):
        scenario.run(plan_slots=[expiring_slot])


def test_must_reject_wrong_approval_set_hash(conn):
    scenario = Scenario(conn)
    wrong = replace(scenario.review_components, plan_approval_set_hash="not-the-real-approval-set-hash")
    with pytest.raises(PreflightRefused, match="wrong_approval_set_hash"):
        scenario.run(components=wrong)


def test_must_reject_missing_planned_reviewer_set(conn):
    scenario = Scenario(conn)
    wrong_plan = replace(scenario.plan_components, planned_reviewer_set_hash="no-such-planned-set")
    other_plan_id = create_plan_tuple(conn, scenario.ticket_id, wrong_plan)
    other_plan_row = record.get(conn, "evidence_tuple", other_plan_id)
    approve(conn, subject_hash=other_plan_row["content_hash"], slot=scenario.plan_slots[0], actor="reviewer-1")
    quorum = approvals.evaluate(
        conn, gate="plan", subject_hash=other_plan_row["content_hash"], slots=scenario.plan_slots,
    )
    assert quorum.satisfied
    components = replace(scenario.review_components, plan_approval_set_hash=quorum.approval_set_hash)
    with pytest.raises(PreflightRefused, match="missing_reviewer_set:planned"):
        scenario.run(plan_tuple_id=other_plan_id, current_plan=wrong_plan, components=components)


def test_must_reject_missing_actual_reviewer_set(conn):
    scenario = Scenario(conn)
    wrong = replace(scenario.review_components, actual_reviewer_set_id=scenario.actual_id + 1000)
    with pytest.raises(PreflightRefused, match="missing_reviewer_set:actual"):
        scenario.run(components=wrong)


def test_must_reject_missing_effective_reviewer_set(conn):
    scenario = Scenario(conn)
    wrong = replace(scenario.review_components, effective_reviewer_set_hash="not-the-stored-hash")
    with pytest.raises(PreflightRefused, match="missing_reviewer_set:effective"):
        scenario.run(components=wrong)


def test_must_reject_an_effective_set_that_is_not_the_merge(conn):
    scenario = Scenario(conn)
    wrong_effective = seed_reviewer_set(
        conn, scenario.ticket_id, "effective", "effective-reviewer-set-wrong",
        [Slot(source_rule="CODEOWNERS:1", owner="somebody-else")],
    )
    wrong = replace(
        scenario.review_components,
        effective_reviewer_set_id=wrong_effective, effective_reviewer_set_hash="effective-reviewer-set-wrong",
    )
    with pytest.raises(PreflightRefused, match="effective_reviewer_set_not_merge"):
        scenario.run(components=wrong)


def test_must_reject_a_stale_target_base(conn):
    scenario = Scenario(conn)
    wrong = replace(scenario.review_components, target_base_sha="a-different-base")
    with pytest.raises(PreflightRefused, match="stale_target_base"):
        scenario.run(components=wrong)


def test_must_reject_a_missing_head_sha(conn):
    scenario = Scenario(conn)
    wrong = replace(scenario.review_components, head_sha=None)
    with pytest.raises(PreflightRefused, match="missing_head_or_diff"):
        scenario.run(components=wrong)


def test_must_reject_a_missing_diff_hash(conn):
    scenario = Scenario(conn)
    wrong = replace(scenario.review_components, diff_hash=None)
    with pytest.raises(PreflightRefused, match="missing_head_or_diff"):
        scenario.run(components=wrong)


def test_a_refused_preflight_leaves_no_review_tuple_behind(conn):
    scenario = Scenario(conn)
    before = conn.execute("SELECT COUNT(*) AS n FROM evidence_tuple WHERE kind = 'review'").fetchone()["n"]
    with pytest.raises(PreflightRefused):
        scenario.run(plan_tuple_id=scenario.plan_tuple_id + 1000)
    after = conn.execute("SELECT COUNT(*) AS n FROM evidence_tuple WHERE kind = 'review'").fetchone()["n"]
    assert after == before
