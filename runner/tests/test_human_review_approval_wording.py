"""The final-review attestation, request-changes routing, and the red-tier bar.

Reuses `test_human_review_publication_subjects.py`'s ticket/review-tuple helpers for
the approval half, and `test_implementation_handoff.py`'s plan-tuple/hand-off helpers
for the loop-note half -- the same cross-file reuse `test_act.py` already
uses for `test_checks_waivers.py`'s waiver helper, rather than a third copy of
either fixture shape.
"""
import pytest

from runner import approvals, canonical, gates, publication, queue, record
from runner.reviewer_sets import Slot
from runner.tests.test_implementation_handoff import _build
from runner.tests.test_human_review_publication_subjects import PACKET_REVIEWER_IDENTITY, conn, seed_review_tuple, seed_ticket

__all__ = ["conn"]


@pytest.fixture
def runs_dir(tmp_path):
    return tmp_path / "runs"


def _open_packet_approval_item(conn, ticket_id, runs_dir, slot):
    _, reviewer_set_id = seed_review_tuple(conn, ticket_id, runs_dir, slots=[slot], content_hash=f"review-{ticket_id}")
    subject = publication.review_approval_subject(conn, ticket_id)
    return queue.open_item(
        conn, ticket_id=ticket_id, kind="packet_approval", reviewer_set_id=reviewer_set_id,
        approval_subject_hash=subject.hash,
    )


def test_final_review_attestation_is_the_verbatim_line_with_its_own_version():
    """The exact attestation text and version are pinned."""
    assert approvals.FINAL_REVIEW_ATTESTATION == (
        "Approval certifies judgment, intent, and residual risk; defect evidence was supplied by checks."
    )
    assert approvals.FINAL_REVIEW_ATTESTATION_VERSION == "final-review-v1"


def test_every_required_final_review_approval_record_carries_the_attestation(conn, runs_dir):
    """An `approve` on a `packet_approval` item stamps the verbatim line and its hash."""
    ticket_id = seed_ticket(conn, state="review")
    slot = Slot(source_rule="owners", role="packet_reviewer", min_count=1)
    item_id = _open_packet_approval_item(conn, ticket_id, runs_dir, slot)

    queue.act(
        conn, item_id=item_id, action="approve", actor=PACKET_REVIEWER_IDENTITY, bucket="under_2m",
        self_contained="yes", runs_dir=runs_dir,
    )

    row = conn.execute(
        "SELECT * FROM approval_record WHERE ticket_id = ? AND gate = 'review' ORDER BY id DESC LIMIT 1", (ticket_id,)
    ).fetchone()
    assert row["attestation_version"] == approvals.FINAL_REVIEW_ATTESTATION_VERSION
    assert row["attestation_hash"] == canonical.content_hash({"text": approvals.FINAL_REVIEW_ATTESTATION})


def test_request_changes_returns_the_ticket_to_implementing_with_a_revision_after_approval_tag(conn, runs_dir):
    ticket_id = seed_ticket(conn, state="review")
    slot = Slot(source_rule="owners", role="packet_reviewer", min_count=1)
    item_id = _open_packet_approval_item(conn, ticket_id, runs_dir, slot)

    queue.act(
        conn, item_id=item_id, action="request_changes", actor=PACKET_REVIEWER_IDENTITY, bucket="under_2m",
        fm_id="agent_only_review", note="tighten the retry backoff before merge", self_contained="yes", runs_dir=runs_dir,
    )

    assert record.get(conn, "ticket", ticket_id)["state"] == "implementing"
    tag = conn.execute(
        "SELECT * FROM tag WHERE ticket_id = ? AND event_kind = 'revision_after_approval' ORDER BY id DESC LIMIT 1",
        (ticket_id,),
    ).fetchone()
    assert tag is not None
    assert tag["note"] == "tighten the retry backoff before merge"
    assert tag["tagged_by"] == PACKET_REVIEWER_IDENTITY


def test_the_request_changes_note_is_carried_into_the_next_implementation_handoff(tmp_path):
    """The real `queue.act` write path and implementation's real read path connect."""
    from runner.db import connect
    from runner.tests.test_implementation_handoff import _register_plan_and_criteria, _seed_plan_tuple

    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = seed_ticket(conn, state="review")
    slot = Slot(source_rule="owners", role="packet_reviewer", min_count=1)
    item_id = _open_packet_approval_item(conn, ticket_id, tmp_path / "runs", slot)
    queue.act(
        conn, item_id=item_id, action="request_changes", actor=PACKET_REVIEWER_IDENTITY, bucket="under_2m",
        fm_id="agent_only_review", note="tighten the retry backoff before merge", self_contained="yes", runs_dir=tmp_path / "runs",
    )
    assert record.get(conn, "ticket", ticket_id)["state"] == "implementing"

    # The next implementation attempt reads `handoff.json` back from this same ticket:
    # a plan tuple and registered plan/criteria artefacts, exactly what a
    # real revision cycle would have on record by the time implementation runs again.
    _seed_plan_tuple(conn, ticket_id)
    _register_plan_and_criteria(conn, ticket_id, tmp_path)
    payload = _build(conn, tmp_path, ticket_id)
    assert payload["loop_note"] == "tighten the retry backoff before merge"


def test_a_ticket_whose_blocking_tier_is_red_cannot_enter_review(conn):
    """An unwaived blocking fail in the ticket's latest checks run withholds `checks_pass_to_review`,
    even once human_review itself has passed."""
    ticket_id = seed_ticket(conn, state="checks")
    checks_run_id = record.insert(conn, "stage_run", ticket_id=ticket_id, stage="checks", attempt=1, outcome="fail")
    record.insert(
        conn, "check_result", stage_run_id=checks_run_id, check_name="red_check", check_tier="blocking",
        source="factory", result="fail", content_hash="red-check-1", canonical_serialization_version=1,
    )
    record.insert(conn, "stage_run", ticket_id=ticket_id, stage="human_review", attempt=1, outcome="pass")

    ticket = record.get(conn, "ticket", ticket_id)
    assert gates.checks_gate(conn, ticket) is None
