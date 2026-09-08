"""The queue's read side: every Initial `queue_item` kind is accepted and
displayed, `pr_outcome` is non-blocking and its latency is never labelled
attention, and an eligibility item's block carries the minimum governed
context a human needs to decide without any other transcript.

`load_scenario` inserts one fixture family's rows through `record.insert`,
resolving a bare `$name` value to a previously inserted row's id and an
embedded `$name` inside a larger string (the escalation item's polymorphic
`stage_run:<id>` ref) the same way, so the fixture never hard-codes an id a
real insert would assign differently on each run.
"""
from pathlib import Path

import pytest
import yaml

from runner import queue, record
from runner.db import connect
from runner.owners import DEFAULT_OWNERS_PATH
from runner.schema import QUEUE_ITEM_KINDS

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "queue"


@pytest.fixture
def conn(tmp_path):
    connection = connect(tmp_path / "factory.sqlite")
    yield connection
    connection.close()


def load_scenario(conn, family: str, scenario: str) -> dict[str, int]:
    data = yaml.safe_load((FIXTURES_DIR / f"{family}.yaml").read_text())[scenario]
    refs: dict[str, int] = {}

    def resolve(value):
        if isinstance(value, str) and value.startswith("$") and value[1:] in refs:
            return refs[value[1:]]
        if isinstance(value, str) and "$" in value:
            for name, row_id in refs.items():
                value = value.replace(f"${name}", str(row_id))
        return value

    for table, rows in data.items():
        for row in rows:
            row = dict(row)
            name = row.pop("as", None)
            row_id = record.insert(conn, table, **{k: resolve(v) for k, v in row.items()})
            if name:
                refs[name] = row_id
    return refs


def _item_text(output: str, item_id: int, kind: str) -> str:
    """Just `item_id`'s own block: from its header up to (not including) the next item's."""
    start_marker = f"queue_item {item_id}: {kind}"
    start = output.index(start_marker)
    rest = output[start + len(start_marker):]
    next_pos = rest.find("\nqueue_item ")
    end = start + len(start_marker) + (next_pos if next_pos != -1 else len(rest))
    return output[start:end]


def test_every_initial_queue_item_kind_is_accepted_and_displayed(conn):
    """R-H-1: a seeded row of each of the nine Initial kinds is accepted by
    the schema and appears in `factory queue`'s listing."""
    refs = load_scenario(conn, "items", "all_kinds")
    conn.commit()
    output = queue.list_queue(conn)
    seen_kinds = set()
    for kind in QUEUE_ITEM_KINDS:
        item_id = refs[f"item_{kind}"]
        row = record.get(conn, "queue_item", item_id)
        assert row["kind"] == kind
        assert f"queue_item {item_id}: {kind}" in output
        seen_kinds.add(kind)
    assert seen_kinds == set(QUEUE_ITEM_KINDS)


def test_queue_listing_shows_ticket_stage_tier_and_queued_at(conn):
    """R-H-1: every item's block names its ticket, stage, tier and `queued_at`."""
    refs = load_scenario(conn, "items", "all_kinds")
    conn.commit()
    output = queue.list_queue(conn)
    block = _item_text(output, refs["item_red_check"], "red_check")
    assert f"ticket {refs['ticket1']}: Sample fixture ticket" in block
    assert "stage: S5" in block
    assert "tier: standard" in block
    assert "queued_at: 2024-01-01T00:00:00+00:00" in block


def test_eligibility_item_shows_the_minimum_governed_context(conn):
    """R-H-1: an eligibility item's block shows the exact trust profile and
    approval-set hashes, the satisfying trust approval set, the planned RACI
    roles, the ticket type and data class to confirm, and the scrutiny
    paragraph -- everything a reader needs without another transcript."""
    refs = load_scenario(conn, "items", "all_kinds")
    from runner import approvals, canonical
    from runner.reviewer_sets import Slot

    slot = Slot(source_rule="trust-profile", role="security_approver")
    approvals.record_approval(
        conn, gate="trust_profile", subject_hash="trust-profile-hash-1",
        slot_id=slot.slot_id, actor_identity="abhishek", role="security_approver",
        decision="approve", authority_policy_hash="policy-1", membership_snapshot_hash="members-1",
        attestation_version="v1", attestation_hash="att-1", expires_at="2999-01-01T00:00:00+00:00",
    )
    conn.commit()

    output = queue.list_queue(conn)
    block = _item_text(output, refs["item_eligibility"], "eligibility")

    assert "trust profile hash: trust-profile-hash-1" in block
    assert "trust approval-set hash: trust-approval-set-hash-1" in block
    assert f"slot {slot.slot_id}: abhishek" in block
    assert "planned RACI roles:" in block
    assert "s3_reviewer: abhishek" in block
    assert "ticket type to confirm: bug_fix" in block
    assert "data class to confirm: internal" in block
    assert "Look hardest at the authorization check." in block


def test_pr_outcome_latency_is_labelled_queue_latency_never_attention(conn):
    """R-H-1: `pr_outcome` items are non-blocking, and a resolved item's
    latency line reads "queue latency", never "attention"."""
    refs = load_scenario(conn, "items", "all_kinds")
    record.update(
        conn, "queue_item", refs["item_pr_outcome"],
        resolved_at="2024-01-01T00:10:00+00:00", resolved_by="abhishek",
        action="merged", note=None, active_attention_bucket=None,
    )
    conn.commit()

    output = queue.list_queue(conn, include_resolved=True)
    block = _item_text(output, refs["item_pr_outcome"], "pr_outcome")
    assert "queue latency: 600.0s" in block
    assert "attention" not in block


def test_open_item_of_kind_pr_outcome_does_not_set_blocked_on(conn):
    """the seam every later stage calls: opening a `pr_outcome` item never
    blocks the ticket, since it is non-blocking by definition (R-H-1)."""
    ticket_id = record.insert(conn, "ticket", state="pr_opened", opened_at=record.now())
    other_id = queue.open_item(conn, ticket_id=ticket_id, kind="red_check")
    assert record.get(conn, "ticket", ticket_id)["blocked_on"] == other_id

    pr_outcome_id = queue.open_item(conn, ticket_id=ticket_id, kind="pr_outcome")
    assert record.get(conn, "ticket", ticket_id)["blocked_on"] == other_id
    assert pr_outcome_id != other_id
