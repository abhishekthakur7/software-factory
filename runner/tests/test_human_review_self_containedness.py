"""The self-containedness rule: `--self-contained`, the `packet_defect` binding, and resolution.

Reuses `test_human_review_publication_subjects.py`'s ticket helper and
`test_human_review_approval_wording.py`'s `_open_packet_approval_item`, the same
cross-file reuse pattern `test_act.py` already applies to
`test_checks_waivers.py`.
"""
import json

import pytest

from runner import artefact_registry, queue, record, tags
from runner.reviewer_sets import Slot
from runner.stages import implementation
from runner.tests.test_human_review_approval_wording import _open_packet_approval_item
from runner.tests.test_human_review_publication_subjects import PACKET_REVIEWER_IDENTITY, conn, seed_ticket

__all__ = ["conn"]


@pytest.fixture
def runs_dir(tmp_path):
    return tmp_path / "runs"


def _open_question_item(conn, ticket_id) -> tuple[int, int]:
    question_id = record.insert(
        conn, "question", ticket_id=ticket_id, stage="clarification", round=1, rank=1,
        options='[{"label": "A", "consequence": "does A"}]', default_option=0, state="open",
    )
    item_id = queue.open_item(conn, ticket_id=ticket_id, kind="question", ref=f"question:{question_id}")
    return item_id, question_id


def _seed_escalation_item_with_failure_history(conn, ticket_id, tmp_path, *, failure_kind=None) -> tuple[int, int]:
    """An `escalation` item whose stage run registered a `failure_history` artefact, built directly
    rather than through the full implementation verification-exhaustion pipeline this file does not otherwise need."""
    stage_run_id = record.insert(
        conn, "stage_run", ticket_id=ticket_id, stage="implementation", attempt=1, outcome="fail", failure_kind=failure_kind,
    )
    payload_path = tmp_path / f"failure_history_{ticket_id}.json"
    payload_path.write_text(json.dumps({"plan_item": "T1", "self_containedness": implementation.SELF_CONTAINEDNESS_RULE}))
    history_id = artefact_registry.register(
        conn, ticket_id=ticket_id, kind="failure_history", path=payload_path, stage_run_id=stage_run_id,
    )
    item_id = queue.open_item(conn, ticket_id=ticket_id, kind="escalation", stage="implementation", ref=f"stage_run:{stage_run_id}")
    return item_id, history_id


def test_a_true_self_containedness_answer_is_recorded_on_the_approval_record_and_the_answer_row(conn, runs_dir):
    """Standing in for a grader at A, the engineer's own reading is recorded
    on a packet decision's `approval_record` and on a question's `answer` row."""
    ticket_id = seed_ticket(conn, state="review")
    slot = Slot(source_rule="owners", role="packet_reviewer", min_count=1)
    item_id = _open_packet_approval_item(conn, ticket_id, runs_dir, slot)
    queue.act(
        conn, item_id=item_id, action="approve", actor=PACKET_REVIEWER_IDENTITY, bucket="under_2m",
        self_contained="yes", runs_dir=runs_dir,
    )
    approval_row = conn.execute(
        "SELECT * FROM approval_record WHERE ticket_id = ? AND gate = 'review' ORDER BY id DESC LIMIT 1", (ticket_id,)
    ).fetchone()
    assert approval_row["decision_supported_without_transcript"] == 1

    question_ticket_id = seed_ticket(conn, state="clarifying")
    q_item_id, question_id = _open_question_item(conn, question_ticket_id)
    queue.act(conn, item_id=q_item_id, action="answer", actor=PACKET_REVIEWER_IDENTITY, option=0, self_contained="yes", runs_dir=runs_dir)
    answer = conn.execute("SELECT * FROM answer WHERE question_id = ? ORDER BY id DESC LIMIT 1", (question_id,)).fetchone()
    assert answer["supported_without_transcript"] == 1


def test_must_reject_approve_with_no_self_contained_answer(conn, runs_dir):
    """`--self-contained` is mandatory on `approve`."""
    ticket_id = seed_ticket(conn, state="review")
    slot = Slot(source_rule="owners", role="packet_reviewer", min_count=1)
    item_id = _open_packet_approval_item(conn, ticket_id, runs_dir, slot)
    with pytest.raises(queue.ActionRefused):
        queue.act(conn, item_id=item_id, action="approve", actor=PACKET_REVIEWER_IDENTITY, bucket="under_2m", runs_dir=runs_dir)


def test_a_false_self_containedness_answer_on_approve_writes_a_packet_defect_bound_to_the_approval_record(conn, runs_dir):
    """On a plan or review decision, bound to the exact `approval_record`."""
    ticket_id = seed_ticket(conn, state="review")
    slot = Slot(source_rule="owners", role="packet_reviewer", min_count=1)
    item_id = _open_packet_approval_item(conn, ticket_id, runs_dir, slot)

    queue.act(
        conn, item_id=item_id, action="approve", actor=PACKET_REVIEWER_IDENTITY, bucket="under_2m",
        self_contained="no", runs_dir=runs_dir,
    )

    approval_row = conn.execute(
        "SELECT * FROM approval_record WHERE ticket_id = ? AND gate = 'review' ORDER BY id DESC LIMIT 1", (ticket_id,)
    ).fetchone()
    assert approval_row["decision_supported_without_transcript"] == 0
    tag = conn.execute(
        "SELECT * FROM tag WHERE ticket_id = ? AND event_kind = 'packet_defect' ORDER BY id DESC LIMIT 1", (ticket_id,)
    ).fetchone()
    assert tag is not None
    assert tag["fm_id"] == "unreviewable_diff"
    assert tag["ref"] == f"approval_record:{approval_row['id']}"


def test_a_false_self_containedness_answer_on_request_changes_writes_a_packet_defect_bound_to_the_approval_record(conn, runs_dir):
    ticket_id = seed_ticket(conn, state="review")
    slot = Slot(source_rule="owners", role="packet_reviewer", min_count=1)
    item_id = _open_packet_approval_item(conn, ticket_id, runs_dir, slot)

    queue.act(
        conn, item_id=item_id, action="request_changes", actor=PACKET_REVIEWER_IDENTITY, bucket="under_2m",
        fm_id="agent_only_review", note="needs another look", self_contained="no", runs_dir=runs_dir,
    )

    approval_row = conn.execute(
        "SELECT * FROM approval_record WHERE ticket_id = ? AND gate = 'review' ORDER BY id DESC LIMIT 1", (ticket_id,)
    ).fetchone()
    tag = conn.execute(
        "SELECT * FROM tag WHERE ticket_id = ? AND event_kind = 'packet_defect' ORDER BY id DESC LIMIT 1", (ticket_id,)
    ).fetchone()
    assert tag is not None
    assert tag["ref"] == f"approval_record:{approval_row['id']}"


def test_a_false_self_containedness_answer_on_a_question_writes_a_packet_defect_bound_to_the_exact_question(conn, runs_dir):
    """On a question, bound to its exact version (id)."""
    ticket_id = seed_ticket(conn, state="clarifying")
    item_id, question_id = _open_question_item(conn, ticket_id)

    queue.act(conn, item_id=item_id, action="answer", actor=PACKET_REVIEWER_IDENTITY, option=0, self_contained="no", runs_dir=runs_dir)

    answer = conn.execute("SELECT * FROM answer WHERE question_id = ? ORDER BY id DESC LIMIT 1", (question_id,)).fetchone()
    assert answer["supported_without_transcript"] == 0
    tag = conn.execute(
        "SELECT * FROM tag WHERE ticket_id = ? AND event_kind = 'packet_defect' ORDER BY id DESC LIMIT 1", (ticket_id,)
    ).fetchone()
    assert tag is not None
    assert tag["ref"] == f"question:{question_id}"


def test_a_false_self_containedness_answer_on_an_escalation_resume_writes_a_packet_defect_bound_to_the_failure_history_artefact(conn, tmp_path):
    """An escalation's decision is held to the rule through its `failure_history` artefact."""
    ticket_id = seed_ticket(conn, state="escalated")
    item_id, history_id = _seed_escalation_item_with_failure_history(conn, ticket_id, tmp_path)

    queue.act(conn, item_id=item_id, action="resume", actor=PACKET_REVIEWER_IDENTITY, self_contained="no", runs_dir=tmp_path)

    assert record.get(conn, "ticket", ticket_id)["state"] == "implementing"
    tag = conn.execute(
        "SELECT * FROM tag WHERE ticket_id = ? AND event_kind = 'packet_defect' ORDER BY id DESC LIMIT 1", (ticket_id,)
    ).fetchone()
    assert tag is not None
    assert tag["fm_id"] == "unreviewable_diff"
    assert tag["ref"] == f"artefact:{history_id}"


def test_must_reject_a_false_self_containedness_answer_on_an_escalation_with_no_failure_history_artefact(conn, tmp_path):
    """An escalation whose stage run registered no `failure_history` artefact has nothing to bind a
    false answer to, so the decision itself is refused rather than silently accepted."""
    ticket_id = seed_ticket(conn, state="escalated")
    stage_run_id = record.insert(conn, "stage_run", ticket_id=ticket_id, stage="implementation", attempt=1, outcome="aborted_human")
    item_id = queue.open_item(conn, ticket_id=ticket_id, kind="escalation", stage="implementation", ref=f"stage_run:{stage_run_id}")

    with pytest.raises(queue.ActionRefused):
        queue.act(conn, item_id=item_id, action="resume", actor=PACKET_REVIEWER_IDENTITY, self_contained="no", runs_dir=tmp_path)


def test_a_later_correction_appends_a_resolution_tag_without_erasing_the_original_packet_defect(conn, runs_dir):
    ticket_id = seed_ticket(conn, state="review")
    slot = Slot(source_rule="owners", role="packet_reviewer", min_count=1)
    item_id = _open_packet_approval_item(conn, ticket_id, runs_dir, slot)
    queue.act(
        conn, item_id=item_id, action="approve", actor=PACKET_REVIEWER_IDENTITY, bucket="under_2m",
        self_contained="no", runs_dir=runs_dir,
    )
    original = conn.execute(
        "SELECT * FROM tag WHERE ticket_id = ? AND event_kind = 'packet_defect' ORDER BY id DESC LIMIT 1", (ticket_id,)
    ).fetchone()

    resolution_id = tags.tag(
        conn, target=original["ref"], kind="packet_defect", fm_id="unreviewable_diff", actor=PACKET_REVIEWER_IDENTITY,
        note="corrected in the reissued packet", resolves_tag_id=original["id"], resolution_evidence_ref="artefact:99",
    )

    resolution = record.get(conn, "tag", resolution_id)
    assert resolution["resolves_tag_id"] == original["id"]
    assert resolution["resolution_evidence_ref"] == "artefact:99"
    unchanged = record.get(conn, "tag", original["id"])
    assert unchanged["resolves_tag_id"] is None
    assert unchanged["note"] == original["note"]
    assert unchanged["ref"] == original["ref"]


def test_failure_history_payload_states_the_self_containedness_rule(conn):
    assert implementation.SELF_CONTAINEDNESS_RULE == "a reader with no transcript can decide from this item alone"
    ticket_id = seed_ticket(conn)
    ticket = record.get(conn, "ticket", ticket_id)
    task = {"id": "T1", "validation_recipe": "fixture_unit", "expected_result": "pass"}
    payload = implementation._failure_history_payload(conn, ticket, plan_tuple_id=1, task=task, tasks_ordered=[task])
    assert payload["self_containedness"] == implementation.SELF_CONTAINEDNESS_RULE
