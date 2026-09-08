"""The mutable-exception fields and the schema-wide allowlist that bounds them.

Every test opens its own `tmp_path` database. `ALLOWED_COLUMNS` below is
typed out by hand rather than imported from `runner/schema.py`, for the
same reason `test_db_schema.py`'s expected field lists are hand-written:
a test that reads its own allowlist from the module it is checking cannot
catch a mistake made in that module.
"""
import sqlite3

import pytest

from runner import record
from runner.db import connect

# Every table the schema creates, mapped to the columns an UPDATE may name.
# A table absent from this comment would be a bug in the sweep below, not
# in the allowlist: `test_allowlist_covers_every_table` catches that.
ALLOWED_COLUMNS = {
    "ticket": {
        "state", "blocked_on", "pause_requested", "paused_at",
        "service_tier", "ticket_type", "tier_provisional", "scrutiny_requested",
        "tier_final", "tier_override_by", "tier_override_at", "tier_override_reason",
        "opened_at", "factory_completed_at", "closed_at", "close_reason",
        "pr_url", "pr_identity", "last_remote_head_sha", "last_pr_body_hash",
        "base_sha", "target_base_sha", "branch", "worktree_path", "head_sha",
        "factory_manifest_hash", "updated_at",
    },
    "stage_run": {
        "outcome", "failure_kind", "started_at", "heartbeat_at",
        "lease_expires_at", "ended_at", "reasoning_summary",
        "cost", "currency", "cost_basis", "pricing_table_hash", "cost_settled_at",
        "updated_at",
    },
    "utility_run": {"outcome", "heartbeat_at", "lease_expires_at", "ended_at", "updated_at"},
    "tool_call": set(),
    "artefact": set(),
    "queue_item": {
        "resolved_at", "resolved_by", "resolved_role", "action", "note", "active_attention_bucket",
        "updated_at",
    },
    "question": {"state", "updated_at"},
    "answer": set(),
    "assumption": set(),
    "deviation": set(),
    "generated_test": set(),
    "check_result": set(),
    "human_verdict": set(),
    "guard_decision": set(),
    "reviewer_set": set(),
    "approval_record": set(),
    "waiver": set(),
    "evidence_tuple": set(),
    "external_write": {
        "state", "attempt_count", "remote_identity", "remote_pr_identity", "guard_decision_id",
        "receipt_artefact_id", "last_error", "updated_at",
    },
    "tag": set(),
    "incident_observation": set(),
    "index_use": set(),
    "baseline_measure": set(),
}

# Extra columns a fresh row of a table needs to satisfy its NOT NULL
# constraints, beyond the empty insert `record.insert` would otherwise try.
REQUIRED_INSERT_FIELDS = {
    "stage_run": {"stage": "S1"},
    "tag": {"fm_id": "override"},
    "waiver": {"expires_at": "2030-01-01T00:00:00+00:00"},
}


def _open(tmp_path):
    return connect(tmp_path / "factory.sqlite")


def _insert_row(conn, table, ticket_id):
    fields = dict(REQUIRED_INSERT_FIELDS.get(table, {}))
    if table == "stage_run":
        fields["ticket_id"] = ticket_id
    if fields:
        return record.insert(conn, table, **fields)
    # record.insert needs at least one column; every field here is
    # nullable, so a table with no required fields just takes its defaults.
    return conn.execute(f"INSERT INTO {table} DEFAULT VALUES").lastrowid


def test_ticket_lifecycle_fields_are_updatable_in_place(tmp_path):
    """ticket's lifecycle fields change in place and each change stamps updated_at."""
    conn = _open(tmp_path)
    ticket_id = record.insert(conn, "ticket", title="t")
    lifecycle_values = {
        "state": "planning",
        "blocked_on": None,
        "pause_requested": 1,
        "paused_at": "2026-01-01T00:00:00+00:00",
        "tier_override_by": "owner",
        "tier_override_at": "2026-01-01T00:00:00+00:00",
        "tier_override_reason": "urgent",
        "opened_at": "2026-01-01T00:00:00+00:00",
        "factory_completed_at": "2026-01-02T00:00:00+00:00",
        "closed_at": "2026-01-03T00:00:00+00:00",
        "close_reason": "merged",
        "pr_url": "https://example.invalid/pr/1",
        "pr_identity": "pr-1",
        "last_remote_head_sha": "abc123",
        "last_pr_body_hash": "def456",
        "base_sha": "base123",
        "target_base_sha": "targetbase123",
        "branch": "ticket/t-1",
        "worktree_path": "runs/tickets/t-1/worktree",
        "head_sha": "head123",
    }
    for field_name, value in lifecycle_values.items():
        record.update(conn, "ticket", ticket_id, **{field_name: value})
        row = record.get(conn, "ticket", ticket_id)
        assert row[field_name] == value
        assert row["updated_at"] is not None


def test_question_state_is_updatable_in_place(tmp_path):
    """question.state changes in place."""
    conn = _open(tmp_path)
    question_id = record.insert(conn, "question", reasoning="why we're asking")

    record.update(conn, "question", question_id, state="answered")

    row = record.get(conn, "question", question_id)
    assert row["state"] == "answered"
    assert row["reasoning"] == "why we're asking"


def test_stage_run_outcome_and_lease_fields_are_updatable_in_place(tmp_path):
    """stage_run's outcome and lease fields change in place."""
    conn = _open(tmp_path)
    ticket_id = record.insert(conn, "ticket", title="t")
    stage_run_id = record.insert(conn, "stage_run", ticket_id=ticket_id, stage="S1")

    lease_values = {
        "outcome": "pass",
        "failure_kind": None,
        "started_at": "2026-01-01T00:00:00+00:00",
        "heartbeat_at": "2026-01-01T00:01:00+00:00",
        "lease_expires_at": "2026-01-01T00:05:00+00:00",
        "ended_at": "2026-01-01T00:02:00+00:00",
    }
    for field_name, value in lease_values.items():
        record.update(conn, "stage_run", stage_run_id, **{field_name: value})
        row = record.get(conn, "stage_run", stage_run_id)
        assert row[field_name] == value


def test_stage_run_cost_settlement_can_be_written_once(tmp_path):
    """the cost settlement group can be written once, all together."""
    conn = _open(tmp_path)
    ticket_id = record.insert(conn, "ticket", title="t")
    stage_run_id = record.insert(conn, "stage_run", ticket_id=ticket_id, stage="S1")

    conn.execute(
        "UPDATE stage_run SET cost = ?, currency = ?, cost_basis = ?, "
        "pricing_table_hash = ?, cost_settled_at = ? WHERE id = ?",
        (1.5, "USD", "price_table_estimate", "priceshash", "2026-01-01T00:00:00+00:00", stage_run_id),
    )

    row = record.get(conn, "stage_run", stage_run_id)
    assert row["cost"] == 1.5
    assert row["cost_settled_at"] == "2026-01-01T00:00:00+00:00"


def test_must_reject_stage_run_cost_settlement_second_write(tmp_path):
    """a second settlement of the same run's cost is rejected."""
    conn = _open(tmp_path)
    ticket_id = record.insert(conn, "ticket", title="t")
    stage_run_id = record.insert(conn, "stage_run", ticket_id=ticket_id, stage="S1")
    conn.execute(
        "UPDATE stage_run SET cost = ?, currency = ?, cost_basis = ?, "
        "pricing_table_hash = ?, cost_settled_at = ? WHERE id = ?",
        (1.5, "USD", "price_table_estimate", "priceshash", "2026-01-01T00:00:00+00:00", stage_run_id),
    )

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE stage_run SET cost = ? WHERE id = ?", (2.5, stage_run_id))


def test_external_write_state_fields_are_updatable_in_place(tmp_path):
    """external_write's state, attempt and identity/receipt fields change in place."""
    conn = _open(tmp_path)
    external_write_id = record.insert(conn, "external_write", operation="pr_create")

    values = {
        "state": "sending",
        "attempt_count": 1,
        "remote_identity": "gh-app-123",
        "remote_pr_identity": "owner/repo#42",
        "receipt_artefact_id": None,
        "last_error": None,
    }
    for field_name, value in values.items():
        record.update(conn, "external_write", external_write_id, **{field_name: value})
        row = record.get(conn, "external_write", external_write_id)
        assert row[field_name] == value


def test_queue_item_resolution_can_be_written_once(tmp_path):
    """the resolution group can be written once, all together."""
    conn = _open(tmp_path)
    queue_item_id = record.insert(conn, "queue_item", kind="question")

    conn.execute(
        "UPDATE queue_item SET resolved_at = ?, resolved_by = ?, action = ?, "
        "note = ?, active_attention_bucket = ? WHERE id = ?",
        ("2026-01-01T00:00:00+00:00", "reviewer", "approve", "looks fine", "unknown", queue_item_id),
    )

    row = record.get(conn, "queue_item", queue_item_id)
    assert row["resolved_by"] == "reviewer"
    assert row["action"] == "approve"


def test_must_reject_queue_item_resolution_second_write(tmp_path):
    """a second resolution of the same queue item is rejected."""
    conn = _open(tmp_path)
    queue_item_id = record.insert(conn, "queue_item", kind="question")
    conn.execute(
        "UPDATE queue_item SET resolved_at = ?, resolved_by = ?, action = ?, "
        "note = ?, active_attention_bucket = ? WHERE id = ?",
        ("2026-01-01T00:00:00+00:00", "reviewer", "approve", "looks fine", "unknown", queue_item_id),
    )

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "UPDATE queue_item SET resolved_by = ? WHERE id = ?", ("someone_else", queue_item_id)
        )


def test_allowlist_covers_every_table(tmp_path):
    """the hand-written allowlist names every table the schema actually creates."""
    conn = _open(tmp_path)
    tables = {
        row["name"]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )
    }
    assert tables == set(ALLOWED_COLUMNS)


@pytest.mark.parametrize("table_name", sorted(ALLOWED_COLUMNS))
def test_must_reject_update_of_columns_outside_the_allowlist(tmp_path, table_name):
    """every column outside a table's allowlist rejects an UPDATE naming it."""
    conn = _open(tmp_path)
    ticket_id = record.insert(conn, "ticket", title="t")
    columns = [
        row["name"] for row in conn.execute(f"PRAGMA table_info({table_name})")
    ]
    forbidden = [name for name in columns if name not in ALLOWED_COLUMNS[table_name]]
    assert forbidden, f"{table_name} has no immutable column to test"

    for column_name in forbidden:
        row_id = _insert_row(conn, table_name, ticket_id)
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(f"UPDATE {table_name} SET {column_name} = NULL WHERE id = ?", (row_id,))


@pytest.mark.parametrize(
    "table_name", sorted(name for name, allowed in ALLOWED_COLUMNS.items() if allowed)
)
def test_update_of_columns_inside_the_allowlist_succeeds(tmp_path, table_name):
    """every column inside a table's allowlist accepts an UPDATE naming it."""
    conn = _open(tmp_path)
    ticket_id = record.insert(conn, "ticket", title="t")

    for column_name in sorted(ALLOWED_COLUMNS[table_name]):
        row_id = _insert_row(conn, table_name, ticket_id)
        conn.execute(f"UPDATE {table_name} SET {column_name} = NULL WHERE id = ?", (row_id,))
        assert record.get(conn, table_name, row_id) is not None


def test_record_update_stamps_updated_at(tmp_path):
    """record.update always stamps updated_at; a raw UPDATE need not."""
    conn = _open(tmp_path)
    ticket_id = record.insert(conn, "ticket", title="t")
    assert record.get(conn, "ticket", ticket_id)["updated_at"] is None

    record.update(conn, "ticket", ticket_id, state="planning")
    assert record.get(conn, "ticket", ticket_id)["updated_at"] is not None

    # a raw UPDATE through an allowed column is accepted without stamping
    # updated_at: the timestamp discipline is record.update's convention,
    # not something the schema itself demands.
    conn.execute("UPDATE ticket SET close_reason = ? WHERE id = ?", ("done", ticket_id))
    row = record.get(conn, "ticket", ticket_id)
    assert row["close_reason"] == "done"
