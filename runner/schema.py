"""The record's schema, as data (R-T-1, docs/prd/02-2-entities.md).

`TABLES` is the single source of truth: T-A-03 derives the mutable-field
allowlist from it and later migrations extend it, instead of a second copy
of the field lists living beside a hand-written `CREATE TABLE` string. No
ORM: a table is just a name and a tuple of columns, and `ddl()` is a pure
function from that data to SQL text.

Column types follow the field's evident meaning: INTEGER for counts,
sequence numbers, booleans and version numbers; REAL for measured
quantities (`cost`, wall-clock durations, the free-form measurement in
`baseline_measure.value`); TEXT for everything else, with lists and
structured values stored as JSON text (the PRD 2.2 preamble; canonical
encoding lives in `runner/canonical.py`). `nullable=False` is used only
where the PRD states a field is required, non-null, or mandatory; every
other field defaults to nullable because most of the record is filled in
as work proceeds rather than at insert time. Only the five Later tables
named by R-T-1 (`score`, `human_signal`, `proposal`, `benchmark`,
`fixture_candidate`) are withheld — they arrive with the migration that
lands the row that first writes each one.
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Column:
    name: str
    type: str  # "INTEGER" | "REAL" | "TEXT"
    nullable: bool = True
    references: str | None = None  # "table.column"


@dataclass(frozen=True)
class Table:
    name: str
    columns: tuple[Column, ...] = field(default_factory=tuple)


def _id() -> Column:
    return Column("id", "INTEGER")


TABLES: tuple[Table, ...] = (
    Table(
        "ticket",
        (
            _id(),
            Column("source_kind", "TEXT"),
            Column("source_ref", "TEXT"),
            Column("title", "TEXT"),
            Column("data_class", "TEXT"),
            Column("trust_profile_hash", "TEXT"),
            Column("trust_approval_set_hash", "TEXT"),
            Column("service", "TEXT"),
            Column("service_tier", "TEXT"),
            Column("ticket_type", "TEXT"),
            Column("factory_manifest_hash", "TEXT"),
            Column("tier_provisional", "TEXT"),
            Column("tier_final", "TEXT"),
            Column("tier_override_by", "TEXT"),
            Column("tier_override_at", "TEXT"),
            Column("tier_override_reason", "TEXT"),
            Column("scrutiny_requested", "TEXT"),
            # Display summary, not an approval gate input (02-2-entities.md).
            Column("required_approvers", "TEXT"),
            Column("state", "TEXT"),
            # Null except while blocked; the single queue_item for the current wait.
            Column("blocked_on", "INTEGER", references="queue_item.id"),
            Column("pause_requested", "INTEGER"),
            Column("paused_at", "TEXT"),
            Column("base_sha", "TEXT"),
            Column("target_base_sha", "TEXT"),
            Column("branch", "TEXT"),
            Column("worktree_path", "TEXT"),
            Column("head_sha", "TEXT"),
            Column("pr_url", "TEXT"),
            Column("pr_identity", "TEXT"),
            Column("last_remote_head_sha", "TEXT"),
            Column("last_pr_body_hash", "TEXT"),
            # True only for the pre-factory provenance rows of R-O-6.
            Column("baseline", "INTEGER"),
            Column("opened_at", "TEXT"),
            Column("factory_completed_at", "TEXT"),
            Column("closed_at", "TEXT"),
            Column("close_reason", "TEXT"),
            Column("final_head_sha", "TEXT"),
            Column("final_target_base_sha", "TEXT"),
            Column("final_pr_body_hash", "TEXT"),
            Column("merge_sha", "TEXT"),
            Column("required_checks_disposition", "TEXT"),
            Column("approval_disposition", "TEXT"),
            Column("external_revision_count", "INTEGER"),
            # Later field (FM-09); reserved now so it never needs a migration.
            Column("close_survey", "TEXT"),
        ),
    ),
    Table(
        "stage_run",
        (
            _id(),
            Column("ticket_id", "INTEGER", nullable=False, references="ticket.id"),
            Column("stage", "TEXT", nullable=False),
            Column("plan_item", "TEXT"),
            Column("plan_tuple_id", "INTEGER", references="evidence_tuple.id"),
            Column("attempt", "INTEGER"),
            Column("verification_attempt", "INTEGER"),
            Column("run_kind", "TEXT"),
            Column("parent_run_id", "INTEGER", references="stage_run.id"),
            Column("tier", "TEXT"),
            Column("runtime", "TEXT"),
            Column("runtime_version", "TEXT"),
            Column("adapter_version", "TEXT"),
            Column("model_requested", "TEXT"),
            Column("model_resolved", "TEXT"),
            Column("agent_ref", "TEXT"),
            Column("skill_ref", "TEXT"),
            Column("rubric_ref", "TEXT"),
            Column("manifest_hash", "TEXT"),
            Column("trust_profile_hash", "TEXT"),
            Column("trust_approval_set_hash", "TEXT"),
            Column("tool_allowlist", "TEXT"),
            Column("sandbox_digest", "TEXT"),
            Column("toolchain_digest", "TEXT"),
            Column("recipe_set_hash", "TEXT"),
            Column("inputs", "TEXT"),
            Column("outputs", "TEXT"),
            Column("reasoning_summary", "TEXT"),
            Column("tokens_in", "INTEGER"),
            Column("tokens_out", "INTEGER"),
            Column("cost", "REAL"),
            Column("currency", "TEXT"),
            Column("cost_basis", "TEXT"),
            Column("pricing_table_hash", "TEXT"),
            Column("cost_settled_at", "TEXT"),
            Column("wall_clock_seconds", "REAL"),
            Column("outcome", "TEXT"),
            Column("failure_kind", "TEXT"),
            Column("started_at", "TEXT"),
            Column("heartbeat_at", "TEXT"),
            Column("lease_expires_at", "TEXT"),
            Column("ended_at", "TEXT"),
        ),
    ),
    Table(
        "utility_run",
        (
            _id(),
            Column("ticket_id", "INTEGER", references="ticket.id"),
            Column("kind", "TEXT"),
            Column("inputs", "TEXT"),
            Column("outputs", "TEXT"),
            Column("manifest_hash", "TEXT"),
            # Same runtime/model identity fields as stage_run, filled only
            # when the utility run uses an agent (02-2-entities.md).
            Column("runtime", "TEXT"),
            Column("runtime_version", "TEXT"),
            Column("adapter_version", "TEXT"),
            Column("model_requested", "TEXT"),
            Column("model_resolved", "TEXT"),
            Column("tokens", "INTEGER"),
            Column("cost", "REAL"),
            Column("currency", "TEXT"),
            Column("cost_basis", "TEXT"),
            Column("pricing_table_hash", "TEXT"),
            Column("wall_clock_seconds", "REAL"),
            Column("outcome", "TEXT"),
            Column("heartbeat_at", "TEXT"),
            Column("lease_expires_at", "TEXT"),
            Column("started_at", "TEXT"),
            Column("ended_at", "TEXT"),
        ),
    ),
    Table(
        "tool_call",
        (
            _id(),
            Column("stage_run_id", "INTEGER", references="stage_run.id"),
            Column("seq", "INTEGER"),
            Column("guard_decision_id", "INTEGER", references="guard_decision.id"),
            Column("tool", "TEXT"),
            Column("tool_version", "TEXT"),
            Column("args_digest", "TEXT"),
            Column("result_digest", "TEXT"),
            Column("args_artefact", "INTEGER", references="artefact.id"),
            Column("result_artefact", "INTEGER", references="artefact.id"),
            Column("duration_ms", "INTEGER"),
            Column("tokens", "INTEGER"),
            Column("result_bytes", "INTEGER"),
            Column("inline", "INTEGER"),
        ),
    ),
    Table(
        "artefact",
        (
            _id(),
            Column("ticket_id", "INTEGER", references="ticket.id"),
            Column("stage_run_id", "INTEGER", references="stage_run.id"),
            Column("guard_decision_id", "INTEGER", references="guard_decision.id"),
            Column("kind", "TEXT"),
            Column("version", "INTEGER"),
            Column("path", "TEXT"),
            Column("hash", "TEXT"),
            Column("created_at", "TEXT"),
            Column("data_class", "TEXT"),
            Column("redaction_state", "TEXT"),
            Column("retention_until", "TEXT"),
            Column("supersedes", "INTEGER", references="artefact.id"),
        ),
    ),
    Table(
        "queue_item",
        (
            _id(),
            Column("ticket_id", "INTEGER", references="ticket.id"),
            Column("stage", "TEXT"),
            Column("tier", "TEXT"),
            Column("kind", "TEXT"),
            # Polymorphic: a question_set, question, artefact, check_result
            # or stage_run id depending on `kind` — not a single-table FK.
            Column("ref", "TEXT"),
            Column("queued_at", "TEXT"),
            Column("resolved_at", "TEXT"),
            Column("resolved_by", "TEXT"),
            Column("action", "TEXT"),
            Column("note", "TEXT"),
            Column("approval_subject_hash", "TEXT"),
            Column("reviewer_set_id", "INTEGER", references="reviewer_set.id"),
            Column("active_attention_bucket", "TEXT"),
        ),
    ),
    Table(
        "question",
        (
            _id(),
            Column("ticket_id", "INTEGER", references="ticket.id"),
            Column("stage", "TEXT"),
            Column("round", "INTEGER"),
            Column("rank", "INTEGER"),
            Column("affects", "TEXT"),
            Column("reasoning", "TEXT"),
            Column("options", "TEXT"),
            Column("default_option", "INTEGER"),
            Column("consequential", "INTEGER"),
            Column("hard_to_reverse", "INTEGER"),
            Column("blocking", "INTEGER"),
            Column("rank_inputs", "TEXT"),
            Column("raised_by_answer", "INTEGER", references="answer.id"),
            Column("state", "TEXT"),
        ),
    ),
    Table(
        "answer",
        (
            _id(),
            Column("question_id", "INTEGER", references="question.id"),
            Column("question_version_hash", "TEXT"),
            Column("resolution_kind", "TEXT"),
            # May hold the literal "none of these" rather than an option
            # index, which is why free_text is required alongside it.
            Column("chosen_option", "TEXT"),
            Column("free_text", "TEXT"),
            Column("answered_by", "TEXT"),
            Column("answered_at", "TEXT"),
        ),
    ),
    Table(
        "assumption",
        (
            _id(),
            Column("ticket_id", "INTEGER", references="ticket.id"),
            Column("text", "TEXT"),
            # A question id (accepted default) or the literal "agent".
            Column("origin", "TEXT"),
            Column("supersedes", "INTEGER", references="assumption.id"),
            Column("withdrawn", "INTEGER"),
            Column("withdrawal_reason", "TEXT"),
            Column("created_at", "TEXT"),
        ),
    ),
    Table(
        "deviation",
        (
            _id(),
            Column("ticket_id", "INTEGER", references="ticket.id"),
            Column("stage_run_id", "INTEGER", references="stage_run.id"),
            Column("plan_item", "TEXT"),
            Column("plan_said", "TEXT"),
            Column("agent_did", "TEXT"),
            Column("why", "TEXT"),
            Column("kind", "TEXT"),
            Column("contract_change", "INTEGER"),
        ),
    ),
    Table(
        "generated_test",
        (
            _id(),
            # 'identity' or 'decision' (02-2-entities.md prose); the two
            # kinds share this table and populate disjoint column groups.
            Column("record_kind", "TEXT"),
            Column("ticket_id", "INTEGER", references="ticket.id"),
            Column("stage_run_id", "INTEGER", references="stage_run.id"),
            # identity-row id, set only on a decision row
            Column("identity_id", "INTEGER", references="generated_test.id"),
            Column("initial_path", "TEXT"),
            Column("initial_hash", "TEXT"),
            Column("generating_actor_kind", "TEXT"),
            Column("created_at", "TEXT"),
            Column("decided_subject_hash", "TEXT"),
            Column("decision", "TEXT"),
            Column("final_path", "TEXT"),
            Column("final_hash", "TEXT"),
            Column("reason", "TEXT"),
            Column("actor", "TEXT"),
            Column("decided_at", "TEXT"),
        ),
    ),
    Table(
        "check_result",
        (
            _id(),
            Column("stage_run_id", "INTEGER", references="stage_run.id"),
            Column("check_name", "TEXT"),
            Column("check_tier", "TEXT"),
            Column("evidence_tuple_id", "INTEGER", references="evidence_tuple.id"),
            Column("plan_tuple_id", "INTEGER", references="evidence_tuple.id"),
            Column("source", "TEXT"),
            Column("result", "TEXT"),
            Column("external_status", "TEXT"),
            Column("external_run_identity", "TEXT"),
            Column("observed_head_sha", "TEXT"),
            Column("observed_target_base_sha", "TEXT"),
            Column("observed_merge_group_sha", "TEXT"),
            Column("evidence_artefact", "INTEGER", references="artefact.id"),
            Column("summary", "TEXT"),
            Column("canonical_serialization_version", "INTEGER"),
            Column("content_hash", "TEXT"),
        ),
    ),
    Table(
        "human_verdict",
        (
            _id(),
            Column("ticket_id", "INTEGER", references="ticket.id"),
            Column("queue_item_id", "INTEGER", references="queue_item.id"),
            Column("rubric_line_id", "TEXT"),
            Column("subject_item_key", "TEXT"),
            Column("rubric_file", "TEXT"),
            Column("rubric_hash", "TEXT"),
            Column("subject_artefact_id", "INTEGER", references="artefact.id"),
            Column("subject_artefact_hash", "TEXT"),
            Column("verdict", "TEXT"),
            Column("evidence_ids", "TEXT"),
            Column("evidence_hashes", "TEXT"),
            Column("note", "TEXT"),
            Column("reviewer_identity", "TEXT"),
            Column("reviewer_role", "TEXT"),
            Column("created_at", "TEXT"),
            Column("canonical_serialization_version", "INTEGER"),
            Column("content_hash", "TEXT"),
        ),
    ),
    Table(
        "guard_decision",
        (
            _id(),
            Column("ticket_id", "INTEGER", references="ticket.id"),
            Column("stage_run_id", "INTEGER", references="stage_run.id"),
            Column("operation", "TEXT"),
            Column("route_id", "TEXT"),
            Column("source_identity", "TEXT"),
            Column("destination_identity", "TEXT"),
            Column("content_provenance", "TEXT"),
            Column("input_data_class", "TEXT"),
            Column("effective_data_class", "TEXT"),
            Column("trust_profile_hash", "TEXT"),
            Column("trust_approval_set_hash", "TEXT"),
            Column("rule_set_hash", "TEXT"),
            Column("allowed_content_digest", "TEXT"),
            Column("sanitizer_rule_id", "TEXT"),
            Column("decision", "TEXT"),
            Column("reason_codes", "TEXT"),
            Column("redacted_artefact_id", "INTEGER", references="artefact.id"),
            Column("created_at", "TEXT"),
            Column("canonical_serialization_version", "INTEGER"),
            Column("content_hash", "TEXT"),
        ),
    ),
    Table(
        "reviewer_set",
        (
            _id(),
            Column("ticket_id", "INTEGER", references="ticket.id"),
            Column("kind", "TEXT"),
            Column("subject_hash", "TEXT"),
            Column("base_sha", "TEXT"),
            Column("head_sha", "TEXT"),
            Column("path_set_hash", "TEXT"),
            Column("codeowners_path", "TEXT"),
            Column("codeowners_blob_sha", "TEXT"),
            Column("sensitive_path_hash", "TEXT"),
            Column("owner_config_hash", "TEXT"),
            Column("membership_snapshot_hash", "TEXT"),
            Column("canonical_serialization_version", "INTEGER"),
            Column("content_hash", "TEXT"),
            # The canonical requirement slots, one JSON list (each slot:
            # key, matched path, source rule/pattern, precedence, role or
            # owner, minimum count, distinct_from) — 02-2-entities.md.
            Column("slots", "TEXT"),
        ),
    ),
    Table(
        "approval_record",
        (
            _id(),
            Column("ticket_id", "INTEGER", references="ticket.id"),
            Column("gate", "TEXT"),
            Column("subject_hash", "TEXT"),
            Column("evidence_tuple_id", "INTEGER", references="evidence_tuple.id"),
            Column("evidence_tuple_hash", "TEXT"),
            Column("reviewer_set_id", "INTEGER", references="reviewer_set.id"),
            Column("reviewer_set_hash", "TEXT"),
            Column("publication_target_hash", "TEXT"),
            Column("slot_id", "TEXT"),
            Column("scope", "TEXT"),
            Column("actor_identity", "TEXT"),
            Column("identity_source", "TEXT"),
            Column("role", "TEXT"),
            Column("authority_policy_hash", "TEXT"),
            Column("membership_snapshot_hash", "TEXT"),
            Column("decision", "TEXT"),
            Column("attestation_version", "TEXT"),
            Column("attestation_hash", "TEXT"),
            Column("evidence_ids", "TEXT"),
            Column("evidence_hashes", "TEXT"),
            Column("decision_supported_without_transcript", "INTEGER"),
            Column("active_attention_bucket", "TEXT"),
            Column("decided_at", "TEXT"),
            Column("expires_at", "TEXT"),
            Column("supersedes", "INTEGER", references="approval_record.id"),
            Column("canonical_serialization_version", "INTEGER"),
            Column("content_hash", "TEXT"),
        ),
    ),
    Table(
        "waiver",
        (
            _id(),
            Column("ticket_id", "INTEGER", references="ticket.id"),
            Column("policy_id", "TEXT"),
            Column("policy_version", "TEXT"),
            Column("policy_hash", "TEXT"),
            Column("waived_check_result_id", "INTEGER", references="check_result.id"),
            Column("waived_human_verdict_id", "INTEGER", references="human_verdict.id"),
            Column("subject_kind", "TEXT"),
            Column("subject_hash", "TEXT"),
            Column("evidence_tuple_id", "INTEGER", references="evidence_tuple.id"),
            Column("actor_identity", "TEXT"),
            Column("actor_role", "TEXT"),
            Column("reason", "TEXT"),
            Column("scope", "TEXT"),
            Column("compensating_controls", "TEXT"),
            Column("evidence_ids", "TEXT"),
            Column("evidence_hashes", "TEXT"),
            Column("issued_at", "TEXT"),
            # "mandatory expiry" (02-2-entities.md) — the one unconditional
            # NOT NULL this ticket adds beyond the owner's named examples.
            Column("expires_at", "TEXT", nullable=False),
            Column("canonical_serialization_version", "INTEGER"),
            Column("content_hash", "TEXT"),
        ),
    ),
    Table(
        "evidence_tuple",
        (
            _id(),
            Column("kind", "TEXT"),
            Column("ticket_id", "INTEGER", references="ticket.id"),
            Column("target_base_sha", "TEXT"),
            Column("manifest_hash", "TEXT"),
            Column("project_config_hash", "TEXT"),
            Column("trust_profile_hash", "TEXT"),
            Column("trust_approval_set_hash", "TEXT"),
            Column("recipe_hash", "TEXT"),
            Column("sandbox_digest", "TEXT"),
            Column("toolchain_digest", "TEXT"),
            Column("created_at", "TEXT"),
            Column("canonical_serialization_version", "INTEGER"),
            Column("content_hash", "TEXT"),
            # Plan-tuple-only fields, null on a review tuple.
            Column("ticket_source_hash", "TEXT"),
            Column("brief_hash", "TEXT"),
            Column("criteria_hash", "TEXT"),
            Column("plan_hash", "TEXT"),
            Column("question_resolution_set_hash", "TEXT"),
            Column("current_assumption_set_hash", "TEXT"),
            Column("base_sha", "TEXT"),
            Column("planned_reviewer_set_hash", "TEXT"),
            Column("semantic_checklist_hash", "TEXT"),
            Column("human_verdict_set_hash", "TEXT"),
            Column("plan_waiver_set_hash", "TEXT"),
            # Review-tuple-only fields, null on a plan tuple.
            Column("plan_tuple_id", "INTEGER", references="evidence_tuple.id"),
            Column("plan_approval_set_hash", "TEXT"),
            Column("head_sha", "TEXT"),
            Column("diff_hash", "TEXT"),
            Column("deviation_set_hash", "TEXT"),
            Column("actual_reviewer_set_id", "INTEGER", references="reviewer_set.id"),
            Column("actual_reviewer_set_hash", "TEXT"),
            Column("effective_reviewer_set_id", "INTEGER", references="reviewer_set.id"),
            Column("effective_reviewer_set_hash", "TEXT"),
        ),
    ),
    Table(
        "external_write",
        (
            _id(),
            Column("ticket_id", "INTEGER", references="ticket.id"),
            Column("stage_run_id", "INTEGER", references="stage_run.id"),
            Column("operation", "TEXT"),
            Column("idempotency_key", "TEXT"),
            Column("payload_artefact_id", "INTEGER", references="artefact.id"),
            Column("payload_digest", "TEXT"),
            Column("guard_decision_id", "INTEGER", references="guard_decision.id"),
            Column("review_tuple_id", "INTEGER", references="evidence_tuple.id"),
            Column("review_approval_subject_hash", "TEXT"),
            Column("review_approval_set_hash", "TEXT"),
            Column("publication_target_hash", "TEXT"),
            Column("repository", "TEXT"),
            Column("target_ref", "TEXT"),
            Column("head_ref", "TEXT"),
            Column("desired_remote_head_sha", "TEXT"),
            Column("expected_prior_remote_head_sha", "TEXT"),
            Column("pr_body_hash", "TEXT"),
            Column("revision", "INTEGER"),
            Column("remote_pr_identity", "TEXT"),
            Column("state", "TEXT"),
            Column("attempt_count", "INTEGER"),
            Column("remote_identity", "TEXT"),
            Column("receipt_artefact_id", "INTEGER", references="artefact.id"),
            Column("last_error", "TEXT"),
            Column("created_at", "TEXT"),
            Column("updated_at", "TEXT"),
        ),
    ),
    Table(
        "tag",
        (
            _id(),
            Column("ticket_id", "INTEGER", references="ticket.id"),
            Column("event_kind", "TEXT"),
            Column("fm_id", "TEXT", nullable=False),
            # Polymorphic: the stage run, question/version, artefact, queue
            # item, approval record, or external incident this tag names.
            Column("ref", "TEXT"),
            Column("severity", "TEXT"),
            Column("note", "TEXT"),
            Column("tagged_by", "TEXT"),
            Column("tagged_at", "TEXT"),
            Column("resolves_tag_id", "INTEGER", references="tag.id"),
            Column("resolution_evidence_ref", "TEXT"),
        ),
    ),
    Table(
        "incident_observation",
        (
            _id(),
            Column("ticket_id", "INTEGER", references="ticket.id"),
            Column("factory_manifest_hash", "TEXT"),
            # production_incident_event | production_disposition |
            # production_coverage | control_defect_event | control_disposition
            Column("record_kind", "TEXT"),
            Column("control_category", "TEXT"),
            Column("recorder_identity", "TEXT"),
            Column("recorder_role", "TEXT"),
            Column("created_at", "TEXT"),
            Column("evidence_refs", "TEXT"),
            # Event-row fields (production_incident_event, control_defect_event).
            Column("tag_id", "INTEGER", references="tag.id"),
            Column("severity", "TEXT"),
            Column("occurred_at", "TEXT"),
            Column("note", "TEXT"),
            # Disposition-row fields: the event root and this disposition's
            # predecessor (an event is never superseded; a disposition may
            # supersede only an earlier disposition for the same root).
            Column("event_id", "INTEGER", references="incident_observation.id"),
            Column("attribution", "TEXT"),
            Column("disposition", "TEXT"),
            Column("remediation_ref", "TEXT"),
            Column("supersedes", "INTEGER", references="incident_observation.id"),
            # Coverage-row fields (production_coverage).
            Column("coverage_status", "TEXT"),
            Column("exposure_start", "TEXT"),
            Column("exposure_source", "TEXT"),
            Column("observed_through", "TEXT"),
        ),
    ),
    Table(
        "index_use",
        (
            _id(),
            Column("stage_run_id", "INTEGER", references="stage_run.id"),
            Column("entry_path", "TEXT"),
            Column("entry_last_verified", "TEXT"),
            Column("stale", "INTEGER"),
        ),
    ),
    Table(
        "baseline_measure",
        (
            _id(),
            Column("ticket_id", "INTEGER", references="ticket.id"),
            Column("measure", "TEXT"),
            Column("measure_definition_hash", "TEXT"),
            Column("service", "TEXT"),
            Column("ticket_type", "TEXT"),
            Column("tier", "TEXT"),
            Column("tier_rule_hash", "TEXT"),
            Column("value", "REAL"),
            Column("status", "TEXT"),
            Column("source_kind", "TEXT"),
            Column("source_ref", "TEXT"),
            Column("content_hash", "TEXT"),
            Column("source_observed_at", "TEXT"),
            Column("entered_by", "TEXT"),
            Column("entered_at", "TEXT"),
            Column("unavailable_reason", "TEXT"),
        ),
    ),
)

# The Later tables of R-T-1: created only by the migration that lands the
# row that first writes each one, never by this schema.
LATER_TABLES: frozenset[str] = frozenset(
    {"score", "human_signal", "proposal", "benchmark", "fixture_candidate"}
)


def ddl() -> list[str]:
    """Return one `CREATE TABLE IF NOT EXISTS` statement per table in `TABLES`."""
    statements = []
    for table in TABLES:
        lines = []
        for column in table.columns:
            if column.name == "id":
                lines.append("id INTEGER PRIMARY KEY")
                continue
            piece = f"{column.name} {column.type}"
            if not column.nullable:
                piece += " NOT NULL"
            lines.append(piece)
        for column in table.columns:
            if column.references:
                ref_table, ref_column = column.references.split(".")
                lines.append(
                    f"FOREIGN KEY ({column.name}) REFERENCES {ref_table}({ref_column})"
                )
        body = ",\n    ".join(lines)
        statements.append(f"CREATE TABLE IF NOT EXISTS {table.name} (\n    {body}\n)")
    return statements
