"""Every resolved `queue_item` carries the acting identity and role, and an approval's own row records the same."""
import pytest

from runner import owners, queue, record
from runner.db import connect
from runner.tests.test_act import ABHISHEK, _seed_item

ABHISHEKS_LOWEST_ROLE = sorted(role for role, entry in owners.load_owners().roles.items() if entry["identity"] == ABHISHEK)[0]


@pytest.fixture
def conn(tmp_path):
    connection = connect(tmp_path / "factory.sqlite")
    yield connection
    connection.close()


def test_a_resolved_queue_item_carries_the_acting_identity_and_the_role_read_from_owners_yaml(conn):
    """R-H-4: `resolved_by` names the acting identity, `resolved_role` the lowest-sorted role that identity holds."""
    ticket_id = record.insert(conn, "ticket", state="checks", opened_at=record.now())
    item_id = queue.open_item(conn, ticket_id=ticket_id, kind="red_check")
    queue.act(conn, item_id=item_id, action="abandon", actor=ABHISHEK, fm_id="FM-07")
    item = record.get(conn, "queue_item", item_id)
    assert item["resolved_by"] == ABHISHEK
    assert item["resolved_role"] == ABHISHEKS_LOWEST_ROLE


def test_an_approval_record_carries_the_deciding_actors_own_identity_and_slot_role(conn, tmp_path):
    """R-H-4: `approval_record.actor_identity`/`role` name the slot's own actor and role, never a ticket-level default."""
    ticket_id, item_id = _seed_item(conn, "plan_approval")
    queue.act(
        conn, item_id=item_id, action="approve", actor=ABHISHEK, bucket="under_2m",
        self_contained="yes", runs_dir=tmp_path,
    )
    row = conn.execute("SELECT * FROM approval_record WHERE gate = 'plan' ORDER BY id DESC LIMIT 1").fetchone()
    assert row["actor_identity"] == ABHISHEK
    assert row["role"] == "s3_reviewer"


def test_ticket_scoped_disposition_records_the_actors_incident_reviewer_role(conn):
    """R-H-4: `disposition`'s `recorder_role` is the fixed `incident_reviewer` role, not `resolved_role`'s derivation."""
    ticket_id = record.insert(conn, "ticket", state="pr_opened", opened_at=record.now())
    queue.act(
        conn, ticket_id=ticket_id, action="incident_event", actor=ABHISHEK,
        fields={"severity": "sev3", "occurred_at": "2025-02-01T00:00:00+00:00", "fm_id": "FM-07", "note": "an incident"},
    )
    event = conn.execute(
        "SELECT id FROM incident_observation WHERE ticket_id = ? AND record_kind = 'production_incident_event'",
        (ticket_id,),
    ).fetchone()
    queue.act(
        conn, ticket_id=ticket_id, action="disposition", actor=ABHISHEK,
        fields={"event": str(event["id"]), "attribution": "undetermined", "disposition": "open"},
    )
    row = conn.execute(
        "SELECT * FROM incident_observation WHERE ticket_id = ? AND record_kind = 'production_disposition'",
        (ticket_id,),
    ).fetchone()
    assert row["recorder_identity"] == ABHISHEK
    assert row["recorder_role"] == "incident_reviewer"
