"""The `outcome` action's comparison against the ticket's approved subject: `approval_disposition`,
the mismatch's own control-defect observation, and the once-settled field's immunity to later tags."""
import pytest

from runner import canonical, queue, record, tags
from runner.tests.test_outcome_revision import conn, seed_pr_outcome_item, ABHISHEK
from runner.tests.test_s5_waivers import issue_review_waiver

APPROVED_BODY = "approved text"


def _seed_matching_ticket(conn) -> int:
    """A `pr_opened` ticket whose approved subject (`last_remote_head_sha`, the review
    tuple's `target_base_sha`, `last_pr_body_hash`) is fully known, for a test to match or diverge from."""
    ticket_id = record.insert(
        conn, "ticket", state="pr_opened", opened_at=record.now(),
        last_remote_head_sha="approved-head", last_pr_body_hash=canonical.content_hash({"pr_body": APPROVED_BODY}),
    )
    record.insert(
        conn, "evidence_tuple", kind="review", ticket_id=ticket_id,
        content_hash=f"review-tuple-{ticket_id}", target_base_sha="approved-base", created_at=record.now(),
    )
    return ticket_id


def _record_outcome(conn, tmp_path, ticket_id, *, head_sha, target_base_sha, body_text, checks):
    item_id = seed_pr_outcome_item(conn, ticket_id)
    body_path = tmp_path / f"body-{item_id}.md"
    body_path.write_text(body_text)
    queue.act(
        conn, item_id=item_id, action="outcome", actor=ABHISHEK,
        fields={
            "result": "merged", "head_sha": head_sha, "target_base_sha": target_base_sha,
            "checks": checks, "observed_at": "2025-01-01T00:00:00+00:00", "body_file": str(body_path),
        },
        runs_dir=tmp_path,
    )
    return item_id


@pytest.mark.parametrize(
    "head_sha, target_base_sha, body_text, checks",
    [
        ("different-head", "approved-base", APPROVED_BODY, "green"),
        ("approved-head", "different-base", APPROVED_BODY, "green"),
        ("approved-head", "approved-base", "a different, unapproved body", "green"),
        ("approved-head", "approved-base", APPROVED_BODY, "red"),
    ],
    ids=["head_mismatch", "target_base_mismatch", "body_mismatch", "checks_red"],
)
def test_each_mismatch_case_still_records_the_outcome_as_mismatched(conn, tmp_path, head_sha, target_base_sha, body_text, checks):
    """R-H-11 criteria 14, 15: a diverging head, target base, body, or a red check disposition
    is still recorded -- `outcome` never refuses for it -- and sets `approval_disposition = 'mismatched'`."""
    ticket_id = _seed_matching_ticket(conn)
    _record_outcome(conn, tmp_path, ticket_id, head_sha=head_sha, target_base_sha=target_base_sha, body_text=body_text, checks=checks)
    assert record.get(conn, "ticket", ticket_id)["approval_disposition"] == "mismatched"


def test_a_mismatched_outcome_appends_a_mechanical_control_defect_tag(conn, tmp_path):
    """R-H-11 criterion 16: one `control_defect` tag, `fm_id = 'FM-25'`, `tagged_by` mechanical, in the same call."""
    ticket_id = _seed_matching_ticket(conn)
    _record_outcome(conn, tmp_path, ticket_id, head_sha="different-head", target_base_sha="approved-base", body_text=APPROVED_BODY, checks="green")

    rows = conn.execute("SELECT * FROM tag WHERE ticket_id = ? AND event_kind = 'control_defect'", (ticket_id,)).fetchall()
    assert len(rows) == 1
    assert rows[0]["fm_id"] == "FM-25"
    assert rows[0]["tagged_by"] == tags.MECHANICAL_ACTOR


def test_a_mismatched_outcome_appends_an_approval_binding_control_defect_event(conn, tmp_path):
    """R-H-11 criterion 17: one `control_defect_event` row, `control_category = 'approval_binding'`, severity from the policy."""
    ticket_id = _seed_matching_ticket(conn)
    _record_outcome(conn, tmp_path, ticket_id, head_sha="approved-head", target_base_sha="different-base", body_text=APPROVED_BODY, checks="green")

    rows = conn.execute(
        "SELECT * FROM incident_observation WHERE ticket_id = ? AND record_kind = 'control_defect_event'", (ticket_id,)
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["control_category"] == "approval_binding"
    assert rows[0]["severity"] == "sev2"


def test_a_mismatched_outcome_appends_an_open_control_disposition_naming_the_event(conn, tmp_path):
    """R-H-11 criterion 18: one `control_disposition` row naming the event root, `disposition = 'open'`."""
    ticket_id = _seed_matching_ticket(conn)
    _record_outcome(conn, tmp_path, ticket_id, head_sha="approved-head", target_base_sha="approved-base", body_text="an unapproved body", checks="green")

    event = conn.execute(
        "SELECT * FROM incident_observation WHERE ticket_id = ? AND record_kind = 'control_defect_event'", (ticket_id,)
    ).fetchone()
    disposition_rows = conn.execute(
        "SELECT * FROM incident_observation WHERE ticket_id = ? AND record_kind = 'control_disposition'", (ticket_id,)
    ).fetchall()
    assert len(disposition_rows) == 1
    assert disposition_rows[0]["event_id"] == event["id"]
    assert disposition_rows[0]["disposition"] == "open"


def test_a_later_policy_exception_tag_does_not_change_the_settled_approval_disposition(conn, tmp_path):
    """R-H-11 criterion 19: a `waiver`/`policy_exception` tag recorded after a mismatch does not move
    `approval_disposition` -- the once-settled column has no write path left for anything to reach."""
    waiver_info = issue_review_waiver(conn, tmp_path)
    ticket_id, waiver_id = waiver_info["ticket_id"], waiver_info["waiver_id"]
    record.update(
        conn, "ticket", ticket_id, state="pr_opened",
        last_remote_head_sha="approved-head", last_pr_body_hash=canonical.content_hash({"pr_body": APPROVED_BODY}),
    )
    _record_outcome(conn, tmp_path, ticket_id, head_sha="a-different-head", target_base_sha="approved-base", body_text=APPROVED_BODY, checks="green")
    settled = record.get(conn, "ticket", ticket_id)["approval_disposition"]
    assert settled == "mismatched"

    tags.tag(
        conn, target=f"waiver:{waiver_id}", kind="policy_exception", fm_id="FM-25", actor=ABHISHEK,
        severity="sev4", note="reviewed and accepted the mismatch after the fact",
    )

    assert record.get(conn, "ticket", ticket_id)["approval_disposition"] == settled


def test_outcome_with_every_pair_available_and_equal_and_checks_not_red_is_matched(conn, tmp_path):
    """R-H-11 criterion 20: head, target base, and body hash all equal the approved subject and checks is not red."""
    ticket_id = _seed_matching_ticket(conn)
    _record_outcome(conn, tmp_path, ticket_id, head_sha="approved-head", target_base_sha="approved-base", body_text=APPROVED_BODY, checks="green")
    assert record.get(conn, "ticket", ticket_id)["approval_disposition"] == "matched"


def test_outcome_with_no_mismatch_but_an_unavailable_pair_is_unknown(conn, tmp_path):
    """R-H-11 criterion 21: no mismatch found, but the body hash is unavailable (neither body source given)."""
    ticket_id = _seed_matching_ticket(conn)
    item_id = seed_pr_outcome_item(conn, ticket_id)
    queue.act(
        conn, item_id=item_id, action="outcome", actor=ABHISHEK,
        fields={
            "result": "merged", "head_sha": "approved-head", "target_base_sha": "approved-base",
            "checks": "green", "observed_at": "2025-01-01T00:00:00+00:00",
        },
        runs_dir=tmp_path,
    )
    assert record.get(conn, "ticket", ticket_id)["approval_disposition"] == "unknown"
