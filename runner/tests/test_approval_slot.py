"""A second decision by an actor who already holds a current head for a slot on the same subject is
refused as a forked head, before `approvals.record_approval` ever writes a row that would create one.
"""
import pytest

from runner import approvals, queue, record
from runner.db import connect
from runner.tests.test_act import ABHISHEK
from runner.tests.test_act_guards import SECOND_REVIEWER, two_slot_owners_path, two_slot_plan_approval_item


@pytest.fixture
def conn(tmp_path):
    connection = connect(tmp_path / "factory.sqlite")
    yield connection
    connection.close()


def test_must_reject_a_second_approve_from_an_actor_who_already_satisfies_a_plan_approval_slot(conn, tmp_path):
    """A second `approve` by the same actor on a slot they already hold a current head for is refused
    as a forked head (`approvals.forked_heads`), and only one immutable row for that actor and slot remains."""
    owners_path = two_slot_owners_path(tmp_path)
    ticket_id, item_id = two_slot_plan_approval_item(conn, tmp_path, owners_path)

    queue.act(
        conn, item_id=item_id, action="approve", actor=ABHISHEK, bucket="under_2m",
        self_contained="yes", owners_path=owners_path, runs_dir=tmp_path,
    )
    # The item stays open (the second slot has no record yet), so a second
    # `approve` call is possible at all -- this is exactly the call the
    # forked-head guard must catch.
    assert record.get(conn, "queue_item", item_id)["resolved_at"] is None

    with pytest.raises(queue.ActionRefused, match="fork"):
        queue.act(
            conn, item_id=item_id, action="approve", actor=ABHISHEK, bucket="under_2m",
            self_contained="yes", owners_path=owners_path, runs_dir=tmp_path,
        )

    rows = conn.execute("SELECT * FROM approval_record WHERE gate = 'plan' AND actor_identity = ?", (ABHISHEK,)).fetchall()
    assert len(rows) == 1
    heads = approvals.current_heads(conn, "plan", rows[0]["subject_hash"])
    assert approvals.forked_heads(heads) == []

    # The other slot is unaffected: it can still be filled normally.
    queue.act(
        conn, item_id=item_id, action="approve", actor=SECOND_REVIEWER, bucket="under_2m",
        self_contained="yes", owners_path=owners_path, runs_dir=tmp_path,
    )
    assert record.get(conn, "queue_item", item_id)["resolved_at"] is not None
