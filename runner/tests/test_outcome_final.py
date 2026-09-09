"""The `outcome` action's final disposition: `merged`/`abandoned`, the actor's recorded role, and the four `required_checks_disposition` values."""
import pytest

from runner import queue, record
from runner.tests.test_outcome_revision import conn, seed_pr_opened_ticket, seed_pr_outcome_item, ABHISHEK


def test_a_merged_outcome_closes_the_ticket_and_settles_its_final_fields(conn, tmp_path):
    """R-H-11: `merged` sets `close_reason`, `closed_at`, the final SHAs, and moves the ticket to `merged`."""
    ticket_id = seed_pr_opened_ticket(conn)
    item_id = seed_pr_outcome_item(conn, ticket_id)

    queue.act(
        conn, item_id=item_id, action="outcome", actor=ABHISHEK,
        fields={
            "result": "merged", "head_sha": "final-head", "target_base_sha": "final-base",
            "merge_sha": "merge-sha-1", "checks": "green", "observed_at": "2025-01-01T00:00:00+00:00",
        },
        runs_dir=tmp_path,
    )

    ticket = record.get(conn, "ticket", ticket_id)
    assert ticket["state"] == "merged"
    assert ticket["close_reason"] == "merged"
    assert ticket["closed_at"] is not None
    assert ticket["final_head_sha"] == "final-head"
    assert ticket["final_target_base_sha"] == "final-base"
    assert ticket["merge_sha"] == "merge-sha-1"
    assert ticket["required_checks_disposition"] == "green"


def test_an_abandoned_outcome_closes_the_ticket_and_leaves_merge_sha_null(conn, tmp_path):
    """R-H-11: `abandoned` sets the final SHAs and moves the ticket to `abandoned`, `merge_sha` stays null."""
    ticket_id = seed_pr_opened_ticket(conn)
    item_id = seed_pr_outcome_item(conn, ticket_id)

    queue.act(
        conn, item_id=item_id, action="outcome", actor=ABHISHEK,
        fields={
            "result": "abandoned", "head_sha": "final-head", "target_base_sha": "final-base",
            "checks": "unknown", "observed_at": "2025-01-01T00:00:00+00:00", "fm_id": "FM-07",
        },
        runs_dir=tmp_path,
    )

    ticket = record.get(conn, "ticket", ticket_id)
    assert ticket["state"] == "abandoned"
    assert ticket["close_reason"] == "abandoned"
    assert ticket["closed_at"] is not None
    assert ticket["final_head_sha"] == "final-head"
    assert ticket["final_target_base_sha"] == "final-base"
    assert ticket["merge_sha"] is None


def test_outcome_records_the_acting_identity_role_and_observed_at(conn, tmp_path):
    """R-H-11: `outcome_actor_role` is the recorder role from `owners.yaml`, `outcome_observed_at` is the given time."""
    ticket_id = seed_pr_opened_ticket(conn)
    item_id = seed_pr_outcome_item(conn, ticket_id)

    queue.act(
        conn, item_id=item_id, action="outcome", actor=ABHISHEK,
        fields={
            "result": "merged", "head_sha": "final-head", "target_base_sha": "final-base",
            "checks": "green", "observed_at": "2025-03-04T05:06:07+00:00",
        },
        runs_dir=tmp_path,
    )

    ticket = record.get(conn, "ticket", ticket_id)
    assert ticket["outcome_actor_role"] == "outcome_recorder"
    assert ticket["outcome_observed_at"] == "2025-03-04T05:06:07+00:00"


@pytest.mark.parametrize(
    "checks, checks_reason",
    [("green", None), ("waived", "flaky check waived by the owner"), ("red", None), ("unknown", None)],
)
def test_outcome_accepts_each_required_checks_disposition(conn, tmp_path, checks, checks_reason):
    """R-H-11: `outcome` accepts a seeded value of each of the four `required_checks_disposition` kinds."""
    ticket_id = seed_pr_opened_ticket(conn)
    item_id = seed_pr_outcome_item(conn, ticket_id)
    fields = {
        "result": "merged", "head_sha": "final-head", "target_base_sha": "final-base",
        "checks": checks, "observed_at": "2025-01-01T00:00:00+00:00",
    }
    if checks_reason is not None:
        fields["checks_reason"] = checks_reason

    queue.act(conn, item_id=item_id, action="outcome", actor=ABHISHEK, fields=fields, runs_dir=tmp_path)

    assert record.get(conn, "ticket", ticket_id)["required_checks_disposition"] == checks


def test_must_reject_a_waived_checks_disposition_with_no_reason(conn, tmp_path):
    """R-H-11: a `waived` value given with no `--checks-reason` is refused."""
    ticket_id = seed_pr_opened_ticket(conn)
    item_id = seed_pr_outcome_item(conn, ticket_id)

    with pytest.raises(queue.ActionRefused):
        queue.act(
            conn, item_id=item_id, action="outcome", actor=ABHISHEK,
            fields={
                "result": "merged", "head_sha": "final-head", "target_base_sha": "final-base",
                "checks": "waived", "observed_at": "2025-01-01T00:00:00+00:00",
            },
            runs_dir=tmp_path,
        )
    assert record.get(conn, "ticket", ticket_id)["outcome_observed_at"] is None
