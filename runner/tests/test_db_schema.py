"""T-A-02 schema tests (R-T-1, docs/prd/02-1-ticket-record.md line 13).

Field lists below are hand-transcribed from docs/prd/02-2-entities.md, not
imported from runner/schema.py: importing them would make a typo or a
missing column in the schema module invisible, since the test would just
be checking the module against itself.
"""
import pytest

from runner.db import connect

# The 12 entities 02-2-entities.md describes as field tables: every named
# field is checked.
EXPECTED_FIELDS = {
    "ticket": {
        "id", "source_kind", "source_ref", "title", "data_class",
        "trust_profile_hash", "trust_approval_set_hash", "service",
        "service_tier", "ticket_type", "factory_manifest_hash",
        "tier_provisional", "tier_final", "tier_override_by",
        "tier_override_at", "tier_override_reason", "scrutiny_requested",
        "required_approvers", "state", "blocked_on", "pause_requested",
        "paused_at", "base_sha", "target_base_sha", "branch",
        "worktree_path", "head_sha", "pr_url", "pr_identity",
        "last_remote_head_sha", "last_pr_body_hash", "baseline",
        "opened_at", "factory_completed_at", "closed_at", "close_reason",
        "final_head_sha", "final_target_base_sha", "final_pr_body_hash",
        "merge_sha", "required_checks_disposition", "approval_disposition",
        "external_revision_count",
    },
    "stage_run": {
        "id", "ticket_id", "stage", "plan_item", "plan_tuple_id", "attempt",
        "verification_attempt", "run_kind", "parent_run_id", "tier",
        "runtime", "runtime_version", "adapter_version", "model_requested",
        "model_resolved", "agent_ref", "skill_ref", "rubric_ref",
        "manifest_hash", "trust_profile_hash", "trust_approval_set_hash",
        "tool_allowlist", "sandbox_digest", "toolchain_digest",
        "recipe_set_hash", "inputs", "outputs", "reasoning_summary",
        "tokens_in", "tokens_out", "cost", "currency", "cost_basis",
        "pricing_table_hash", "cost_settled_at", "wall_clock_seconds",
        "outcome", "failure_kind", "started_at", "heartbeat_at",
        "lease_expires_at", "ended_at",
    },
    "tool_call": {
        "id", "stage_run_id", "seq", "guard_decision_id", "tool",
        "tool_version", "args_digest", "result_digest", "args_artefact",
        "result_artefact", "duration_ms", "tokens", "result_bytes", "inline",
    },
    "artefact": {
        "id", "ticket_id", "stage_run_id", "guard_decision_id", "kind",
        "version", "path", "hash", "created_at", "data_class",
        "redaction_state", "retention_until", "supersedes",
    },
    "queue_item": {
        "id", "ticket_id", "stage", "tier", "kind", "ref", "queued_at",
        "resolved_at", "resolved_by", "action", "note",
        "approval_subject_hash", "reviewer_set_id", "active_attention_bucket",
    },
    "question": {
        "id", "ticket_id", "stage", "round", "rank", "affects", "reasoning",
        "options", "default_option", "consequential", "hard_to_reverse",
        "blocking", "rank_inputs", "raised_by_answer", "state",
    },
    "answer": {
        "id", "question_id", "question_version_hash", "resolution_kind",
        "chosen_option", "free_text", "answered_by", "answered_at",
    },
    "assumption": {
        "id", "ticket_id", "text", "origin", "supersedes", "withdrawn",
        "withdrawal_reason", "created_at",
    },
    "deviation": {
        "id", "ticket_id", "stage_run_id", "plan_item", "plan_said",
        "agent_did", "why", "kind", "contract_change",
    },
    "check_result": {
        "id", "stage_run_id", "check_name", "check_tier",
        "evidence_tuple_id", "plan_tuple_id", "source", "result",
        "external_status", "external_run_identity", "observed_head_sha",
        "observed_target_base_sha", "observed_merge_group_sha",
        "evidence_artefact", "summary", "canonical_serialization_version",
        "content_hash",
    },
    "tag": {
        "id", "ticket_id", "event_kind", "fm_id", "ref", "severity", "note",
        "tagged_by", "tagged_at", "resolves_tag_id", "resolution_evidence_ref",
    },
    "index_use": {
        "id", "stage_run_id", "entry_path", "entry_last_verified", "stale",
    },
    # The remaining tables are described in prose. This is a representative
    # subset: the datums 02-2-entities.md names explicitly by word for each,
    # not every derived column.
    "generated_test": {
        "id", "record_kind", "ticket_id", "initial_path", "initial_hash",
        "generating_actor_kind", "created_at", "decision", "final_path",
        "final_hash", "reason", "actor",
    },
    "human_verdict": {
        "id", "ticket_id", "queue_item_id", "rubric_line_id",
        "subject_item_key", "rubric_hash", "verdict", "evidence_ids",
        "reviewer_identity", "reviewer_role",
        "canonical_serialization_version", "content_hash",
    },
    "guard_decision": {
        "id", "ticket_id", "operation", "route_id", "source_identity",
        "destination_identity", "input_data_class", "effective_data_class",
        "decision", "reason_codes", "canonical_serialization_version",
        "content_hash",
    },
    "reviewer_set": {
        "id", "ticket_id", "kind", "subject_hash", "base_sha", "head_sha",
        "codeowners_path", "codeowners_blob_sha",
        "canonical_serialization_version", "content_hash", "slots",
    },
    "approval_record": {
        "id", "ticket_id", "gate", "subject_hash", "reviewer_set_id",
        "slot_id", "actor_identity", "role", "decision",
        "decision_supported_without_transcript", "decided_at", "expires_at",
        "supersedes", "canonical_serialization_version", "content_hash",
    },
    "waiver": {
        "id", "ticket_id", "policy_id", "policy_version", "policy_hash",
        "subject_kind", "subject_hash", "actor_identity", "actor_role",
        "reason", "scope", "compensating_controls", "issued_at",
        "expires_at", "canonical_serialization_version", "content_hash",
    },
    "evidence_tuple": {
        "id", "kind", "ticket_id", "target_base_sha", "manifest_hash",
        "sandbox_digest", "toolchain_digest", "created_at",
        "canonical_serialization_version", "content_hash", "plan_hash",
        "base_sha", "plan_tuple_id", "head_sha", "diff_hash",
        "deviation_set_hash",
    },
    "external_write": {
        "id", "ticket_id", "operation", "idempotency_key", "payload_digest",
        "publication_target_hash", "repository", "desired_remote_head_sha",
        "pr_body_hash", "revision", "remote_pr_identity", "state",
        "attempt_count", "last_error",
    },
    "incident_observation": {
        "id", "ticket_id", "factory_manifest_hash", "record_kind",
        "control_category", "recorder_identity", "recorder_role",
        "created_at", "severity", "occurred_at", "note", "event_id",
        "attribution", "disposition", "supersedes", "coverage_status",
        "observed_through",
    },
    "baseline_measure": {
        "id", "ticket_id", "measure", "measure_definition_hash", "service",
        "ticket_type", "tier", "value", "status", "source_kind",
        "source_ref", "content_hash", "source_observed_at", "entered_by",
        "entered_at", "unavailable_reason",
    },
    "utility_run": {
        "id", "ticket_id", "kind", "inputs", "outputs", "manifest_hash",
        "runtime", "model_requested", "model_resolved", "tokens", "cost",
        "currency", "cost_basis", "outcome", "heartbeat_at",
        "lease_expires_at", "started_at", "ended_at",
    },
}

LATER_TABLES = ("score", "human_signal", "proposal", "benchmark", "fixture_candidate")


def _table_columns(connection, table_name):
    return {row["name"] for row in connection.execute(f"PRAGMA table_info({table_name})")}


def test_wal_mode(tmp_path):
    """T-A-02 criterion 1, R-T-1: the database opens in WAL mode."""
    connection = connect(tmp_path / "factory.sqlite")
    mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"


def test_foreign_keys_enabled(tmp_path):
    """T-A-02 criterion 1, R-T-1: foreign key enforcement is on per connection."""
    connection = connect(tmp_path / "factory.sqlite")
    assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1


@pytest.mark.parametrize("table_name,expected", sorted(EXPECTED_FIELDS.items()))
def test_table_has_every_named_field(tmp_path, table_name, expected):
    """T-A-02 criterion 2, R-T-1: every field 02-2-entities.md names exists."""
    connection = connect(tmp_path / "factory.sqlite")
    columns = _table_columns(connection, table_name)
    missing = expected - columns
    assert not missing, f"{table_name} is missing {sorted(missing)}"


@pytest.mark.parametrize("table_name", LATER_TABLES)
def test_later_table_absent(tmp_path, table_name):
    """T-A-02 criterion 3, R-T-1, must-reject: no Later table exists early."""
    connection = connect(tmp_path / "factory.sqlite")
    row = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    assert row is None


def test_reconnect_is_idempotent(tmp_path):
    """T-A-02, R-T-1: connecting twice to the same file changes nothing."""
    path = tmp_path / "factory.sqlite"
    first = connect(path)
    count_first = first.execute(
        "SELECT count(*) FROM sqlite_master WHERE type = 'table'"
    ).fetchone()[0]
    first.close()

    second = connect(path)
    count_second = second.execute(
        "SELECT count(*) FROM sqlite_master WHERE type = 'table'"
    ).fetchone()[0]

    assert count_second == count_first
