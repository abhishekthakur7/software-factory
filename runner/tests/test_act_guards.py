"""Three guards on `factory act`'s resolution behaviour: a control-defect escalation's resume gate,
a multi-slot plan approval's own quorum, and `close_inspection` carrying no state transition.
"""
import json
from pathlib import Path

import pytest
import yaml

from runner import artefact_registry, artefacts, checklist, manifest, owners, queue, record
from runner.db import connect
from runner.reviewer_sets import Slot
from runner.tests.test_act import ABHISHEK

SECOND_REVIEWER = "reviewer_two"


@pytest.fixture
def conn(tmp_path):
    connection = connect(tmp_path / "factory.sqlite")
    yield connection
    connection.close()


def two_slot_owners_path(tmp_path: Path) -> Path:
    """A copy of the default `owners.yaml` roles with one extra role held by a second, distinct identity."""
    default = owners.load_owners()
    roles = {name: dict(entry) for name, entry in default.roles.items()}
    roles["second_reviewer"] = {"identity": SECOND_REVIEWER, "responsibilities": ["approvals"]}
    path = tmp_path / "owners.yaml"
    path.write_text(yaml.safe_dump({"roles": roles, "shared_identities": []}))
    return path


def two_slot_plan_approval_item(conn, tmp_path: Path, owners_path: Path) -> tuple[int, int]:
    """A `plan_approval` item whose planned reviewer set names two slots held by two distinct identities,
    its bootstrap checklist already fully satisfied with `pass` verdicts."""
    ticket_id = record.insert(
        conn, "ticket", state="plan_review", opened_at=record.now(),
        trust_profile_hash="trust-1", trust_approval_set_hash="trust-approval-1",
        factory_manifest_hash=manifest.current_hash(), base_sha="base-1", target_base_sha="base-1",
    )
    stub_dir = tmp_path / "stub"
    stub_dir.mkdir(exist_ok=True)
    for artefact_kind in ("brief", "criteria", "plan"):
        path = stub_dir / f"{artefact_kind}.md"
        path.write_text(f"## {artefacts.SECTIONS[artefact_kind][0]}\n\nstub\n")
        artefact_registry.register(conn, ticket_id=ticket_id, kind=artefact_kind, path=path)
    slots = [
        Slot(source_rule="s3_reviewer_role", role="s3_reviewer", owner=ABHISHEK, min_count=1),
        Slot(source_rule="second_reviewer_role", role="second_reviewer", owner=SECOND_REVIEWER, min_count=1),
    ]
    reviewer_set_id = record.insert(
        conn, "reviewer_set", ticket_id=ticket_id, kind="planned", content_hash="planned-subj-2slot",
        slots=json.dumps([slot.to_json() for slot in slots]),
    )
    item_id = queue.open_item(conn, ticket_id=ticket_id, kind="plan_approval", reviewer_set_id=reviewer_set_id)
    ticket = record.get(conn, "ticket", ticket_id)
    plan_artefact = artefact_registry.latest(conn, ticket_id, "plan")
    for instance in checklist.expected_instances(conn, ticket):
        queue.act(
            conn, item_id=item_id, action="verdict", actor=ABHISHEK, line=instance.rubric_line_id,
            key=instance.subject_item_key, verdict="pass", evidence=[plan_artefact["id"]],
            owners_path=owners_path, runs_dir=stub_dir,
        )
    return ticket_id, item_id


def test_a_control_defect_escalations_resume_is_refused_until_remediated_and_gated(conn, tmp_path):
    """R-H-4: a plain `resume` is refused while the escalation's control-defect event carries no `remediated`
    disposition or no newer passing `gate` run, and accepted once both exist."""
    ticket_id = record.insert(conn, "ticket", state="escalated", opened_at=record.now())
    stage_run_id = record.insert(
        conn, "stage_run", ticket_id=ticket_id, stage="S4", attempt=1, outcome="fail", failure_kind="sandbox_integrity",
    )
    item_id = queue.open_item(conn, ticket_id=ticket_id, kind="escalation", ref=f"stage_run:{stage_run_id}")

    with pytest.raises(queue.ActionRefused):
        queue.act(conn, item_id=item_id, action="resume", actor=ABHISHEK, self_contained="yes", runs_dir=tmp_path)

    event_id = record.insert(
        conn, "incident_observation", ticket_id=ticket_id, record_kind="control_defect_event",
        control_category="execution_boundary", recorder_identity="runner", created_at=record.now(),
    )
    record.insert(
        conn, "incident_observation", ticket_id=ticket_id, record_kind="control_disposition", event_id=event_id,
        disposition="remediated", recorder_identity=ABHISHEK, created_at=record.now(),
    )

    with pytest.raises(queue.ActionRefused):
        # A disposition alone, with no passing gate run newer than the event, still refuses.
        queue.act(conn, item_id=item_id, action="resume", actor=ABHISHEK, self_contained="yes", runs_dir=tmp_path)

    record.insert(conn, "utility_run", ticket_id=ticket_id, kind="gate", outcome="pass", started_at=record.now())

    queue.act(conn, item_id=item_id, action="resume", actor=ABHISHEK, self_contained="yes", runs_dir=tmp_path)
    assert record.get(conn, "ticket", ticket_id)["state"] == "context"
    assert record.get(conn, "queue_item", item_id)["resolved_at"] is not None


def test_a_two_slot_plan_approval_leaves_the_ticket_open_until_the_second_slots_record_exists(conn, tmp_path):
    """R-H-4: `approve` resolves the item only once every named slot holds its own approval record,
    not on the first slot's alone."""
    owners_path = two_slot_owners_path(tmp_path)
    ticket_id, item_id = two_slot_plan_approval_item(conn, tmp_path, owners_path)

    queue.act(
        conn, item_id=item_id, action="approve", actor=ABHISHEK, bucket="under_2m",
        self_contained="yes", owners_path=owners_path, runs_dir=tmp_path,
    )
    assert record.get(conn, "queue_item", item_id)["resolved_at"] is None
    assert record.get(conn, "ticket", ticket_id)["state"] == "plan_review"

    queue.act(
        conn, item_id=item_id, action="approve", actor=SECOND_REVIEWER, bucket="under_2m",
        self_contained="yes", owners_path=owners_path, runs_dir=tmp_path,
    )
    assert record.get(conn, "queue_item", item_id)["resolved_at"] is not None
    rows = conn.execute("SELECT actor_identity FROM approval_record WHERE gate = 'plan' ORDER BY id").fetchall()
    assert {row["actor_identity"] for row in rows} == {ABHISHEK, SECOND_REVIEWER}


def test_close_inspection_resolves_the_item_and_carries_no_state_transition_of_its_own(conn):
    """R-H-4: `close_inspection` settles the item's own resolution columns and leaves the ticket's state untouched."""
    ticket_id = record.insert(conn, "ticket", state="planning", opened_at=record.now())
    item_id = queue.open_item(conn, ticket_id=ticket_id, kind="rubric_inspection")

    queue.act(conn, item_id=item_id, action="close_inspection", actor=ABHISHEK)

    assert record.get(conn, "queue_item", item_id)["resolved_at"] is not None
    assert record.get(conn, "ticket", ticket_id)["state"] == "planning"
