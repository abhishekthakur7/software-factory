"""The `pr_outcome` item's non-blocking opening and its `revision` action.

`seed_pr_opened_ticket` and `seed_reconciled_receipt` are the shared seed
helpers the other `test_outcome_*` files import from here rather than
duplicating: a ticket parked directly in `pr_opened` (the same convention
`test_act.py` uses for every other kind), plus, where a test needs one, a
real reconciled `external_write` row carrying a registered receipt
artefact -- everything `outcome.open_pr_outcome_item` and `outcome.outcome`
read.
"""
import pytest

from runner import artefact_registry, outcome, queue, record, tags, transitions
from runner.db import connect

ABHISHEK = "abhishek"


@pytest.fixture
def conn(tmp_path):
    connection = connect(tmp_path / "factory.sqlite")
    yield connection
    connection.close()


def seed_pr_opened_ticket(conn, **overrides) -> int:
    """A ticket parked directly in `pr_opened`, the state every `pr_outcome` test starts from."""
    fields = {"opened_at": record.now(), **overrides}
    return record.insert(conn, "ticket", state="pr_opened", **fields)


def seed_reconciled_receipt(conn, ticket_id: int, tmp_path, *, operation="pr_create") -> int:
    """A reconciled `external_write` row carrying a registered receipt artefact; returns the artefact id."""
    receipt_path = tmp_path / f"receipt-{ticket_id}-{operation}.json"
    receipt_path.write_text('{"remote_head_sha": "head-1", "payload_digest": "digest-1"}')
    artefact_id = artefact_registry.register(conn, ticket_id=ticket_id, kind="receipt", path=receipt_path)
    record.insert(
        conn, "external_write", ticket_id=ticket_id, operation=operation, state="reconciled",
        receipt_artefact_id=artefact_id, idempotency_key=f"key-{ticket_id}-{operation}-{artefact_id}",
        created_at=record.now(),
    )
    return artefact_id


def seed_pr_outcome_item(conn, ticket_id: int) -> int:
    return queue.open_item(conn, ticket_id=ticket_id, kind="pr_outcome")


def test_a_reconciled_receipt_opens_exactly_one_non_blocking_pr_outcome_item(conn, tmp_path):
    """The item carries `blocked_on` null and `ref` naming the reconciled receipt's artefact."""
    ticket_id = seed_pr_opened_ticket(conn)
    artefact_id = seed_reconciled_receipt(conn, ticket_id, tmp_path)
    item_id = outcome.open_pr_outcome_item(conn, ticket_id)
    assert item_id is not None
    item = record.get(conn, "queue_item", item_id)
    assert item["kind"] == "pr_outcome"
    assert item["ref"] == f"artefact:{artefact_id}"
    assert record.get(conn, "ticket", ticket_id)["blocked_on"] is None


def test_a_second_reconciled_receipt_opens_no_second_pr_outcome_item(conn, tmp_path):
    """Exactly one current `pr_outcome` item survives create and update cycles."""
    ticket_id = seed_pr_opened_ticket(conn)
    seed_reconciled_receipt(conn, ticket_id, tmp_path, operation="pr_create")
    first_item_id = outcome.open_pr_outcome_item(conn, ticket_id)

    seed_reconciled_receipt(conn, ticket_id, tmp_path, operation="pr_update")
    second_call = outcome.open_pr_outcome_item(conn, ticket_id)

    assert second_call is None
    open_items = conn.execute(
        "SELECT id FROM queue_item WHERE ticket_id = ? AND kind = 'pr_outcome' AND resolved_at IS NULL",
        (ticket_id,),
    ).fetchall()
    assert [row["id"] for row in open_items] == [first_item_id]


def test_revision_writes_a_tag_and_moves_the_ticket_back_to_its_target_stage(conn, tmp_path):
    """`revision` to `implementing` writes one `revision_after_approval` tag and transitions the ticket."""
    ticket_id = seed_pr_opened_ticket(conn)
    item_id = seed_pr_outcome_item(conn, ticket_id)

    queue.act(
        conn, item_id=item_id, action="revision", actor=ABHISHEK,
        fields={"to": "implementing", "fm_id": "question_noise", "note": "reviewer asked for one more pass"},
        runs_dir=tmp_path,
    )

    tag_rows = conn.execute("SELECT * FROM tag WHERE ticket_id = ?", (ticket_id,)).fetchall()
    assert [row["event_kind"] for row in tag_rows] == ["revision_after_approval"]
    assert tag_rows[0]["fm_id"] == "question_noise"
    assert record.get(conn, "ticket", ticket_id)["state"] == "implementing"
    assert record.get(conn, "queue_item", item_id)["resolved_at"] is not None


def test_must_reject_a_revision_to_a_stage_pr_opened_cannot_return_to(conn, tmp_path):
    """An out-of-set `--to` is refused before any tag row or transition is written."""
    ticket_id = seed_pr_opened_ticket(conn)
    item_id = seed_pr_outcome_item(conn, ticket_id)

    with pytest.raises(queue.ActionRefused):
        queue.act(
            conn, item_id=item_id, action="revision", actor=ABHISHEK,
            fields={"to": "checks", "fm_id": "question_noise", "note": "not a real revision target"},
            runs_dir=tmp_path,
        )

    assert conn.execute("SELECT COUNT(*) FROM tag WHERE ticket_id = ?", (ticket_id,)).fetchone()[0] == 0
    assert record.get(conn, "ticket", ticket_id)["state"] == "pr_opened"
    assert record.get(conn, "queue_item", item_id)["resolved_at"] is None


def test_a_recorded_revision_leaves_the_prior_review_approval_unusable_for_a_new_pr_update(conn, tmp_path):
    """The ticket must revisit `plan_review` through `review`; the resolved packet
    approval that got it to `pr_opened` cannot be replayed to authorise a fresh `pr_update`."""
    ticket_id = seed_pr_opened_ticket(conn)
    item_id = seed_pr_outcome_item(conn, ticket_id)
    packet_item_id = record.insert(
        conn, "queue_item", ticket_id=ticket_id, kind="packet_approval", queued_at=record.now(),
        resolved_at=record.now(), resolved_by=ABHISHEK, action="approve",
    )

    queue.act(
        conn, item_id=item_id, action="revision", actor=ABHISHEK,
        fields={"to": "implementing", "fm_id": "question_noise", "note": "found a missed edge case"},
        runs_dir=tmp_path,
    )

    assert record.get(conn, "ticket", ticket_id)["state"] == "implementing"
    with pytest.raises(queue.ActionRefused):
        queue.act(conn, item_id=packet_item_id, action="approve", actor=ABHISHEK, bucket="under_2m", runs_dir=tmp_path)


def test_revision_leaves_the_remote_branch_and_pull_request_untouched(conn, tmp_path):
    """No outbox intent is created, so the ticket's own remote-publication fields do not move."""
    ticket_id = seed_pr_opened_ticket(
        conn, pr_url="https://github.example/fixture/pull/1", pr_identity="1",
        last_remote_head_sha="head-1", branch="scratch/ticket-1",
    )
    item_id = seed_pr_outcome_item(conn, ticket_id)
    before = record.get(conn, "ticket", ticket_id)

    queue.act(
        conn, item_id=item_id, action="revision", actor=ABHISHEK,
        fields={"to": "context", "fm_id": "question_noise", "note": "needs re-scoping"},
        runs_dir=tmp_path,
    )

    after = record.get(conn, "ticket", ticket_id)
    for column in ("pr_url", "pr_identity", "last_remote_head_sha", "branch"):
        assert after[column] == before[column]
    assert conn.execute("SELECT COUNT(*) FROM external_write WHERE ticket_id = ?", (ticket_id,)).fetchone()[0] == 0
