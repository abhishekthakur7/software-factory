"""The record's schema, as data.

`TABLES` is the single source of truth: the append-only enforcement
derives its mutable-field allowlist from it and later migrations extend it, instead of a second copy
of the field lists living beside a hand-written `CREATE TABLE` string. No
ORM: a table is just a name and a tuple of columns, and `ddl()` is a pure
function from that data to SQL text.

Column types follow the field's evident meaning: INTEGER for counts,
sequence numbers, booleans and version numbers; REAL for measured
quantities (`cost`, wall-clock durations, the free-form measurement in
`baseline_measure.value`); TEXT for everything else, with lists and
structured values stored as JSON text (canonical encoding lives in
`runner/canonical.py`). `nullable=False` is used only
where the PRD states a field is required, non-null, or mandatory; every
other field defaults to nullable because most of the record is filled in
as work proceeds rather than at insert time. Only the five Later tables
(`score`, `human_signal`, `proposal`, `benchmark`,
`fixture_candidate`) are withheld — they arrive with the migration that
lands the row that first writes each one.

Every column is immutable in place unless its declaration says otherwise:
a column is either plain immutable (the default — the row is append-only,
so a change is always a new row), `mutable=True` (updatable in place, any
number of times), or `once=<sentinel>` (updatable in place exactly once,
together with every other column naming the same sentinel). `ddl()` turns those declarations into the
triggers that enforce them, so the allowlist has exactly one home: this
module. A later ticket that needs a new field mutable marks it here rather
than adding a second enforcement path.

A column may also declare `values`, a closed set of strings `ddl()` turns
into a `CHECK` constraint. SQLite evaluates `col IN (...)` to `NULL`, not to
false, when `col` is `NULL`, and a `CHECK` only rejects a row when its
expression is false — so a nullable column with `values` still accepts
`NULL` with no extra clause. Each value set used by more than one column is
a module-level constant so the two columns (or the code that writes them)
can never drift apart by hand-copying the list twice.

`VIEWS` names read-only `CREATE VIEW` statements over the tables above,
emitted by `ddl()` after every table and its triggers. A view earns a place
here only when it exists to exclude rows a plain `SELECT` would otherwise
have to filter at every call site.
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Column:
    name: str
    type: str  # "INTEGER" | "REAL" | "TEXT"
    nullable: bool = True
    references: str | None = None  # "table.column"
    mutable: bool = False  # updatable in place, any number of times
    # Names the sentinel column of a group that settles together exactly
    # once (a run's cost fields, a queue item's resolution fields): every
    # column naming the same sentinel is in the group, the sentinel names
    # itself, and a non-null sentinel means the group is already settled.
    once: str | None = None
    # The column's closed value set, or None for free text.
    values: tuple[str, ...] | None = None


@dataclass(frozen=True)
class Table:
    name: str
    columns: tuple[Column, ...] = field(default_factory=tuple)


def _id() -> Column:
    return Column("id", "INTEGER")


# stage_run.stage's closed set: the S0 to S7 stage range.
STAGES: tuple[str, ...] = ("S0", "S1", "S2", "S3", "S4", "S5", "S6", "S7")

# stage_run.run_kind's closed set: a plan-task execution with an agent, an
# agent fix round against failing machine checks, and the runner's
# script-only validation run after a fix round.
RUN_KINDS: tuple[str, ...] = ("task", "fix_round", "validation_only")

# stage_run.outcome's closed set.
OUTCOMES: tuple[str, ...] = (
    "pass",
    "fail",
    "infrastructure_failure",
    "sandbox_violation",
    "blocked",
    "aborted_budget",
    "aborted_human",
    "refused",
)

# stage_run.failure_kind's closed set; nullable, so a passing or still-open
# run simply carries no failure_kind rather than one of these values.
FAILURE_KINDS: tuple[str, ...] = (
    "implementation",
    "verification",
    "infrastructure",
    "sandbox_integrity",
    "structural",
    "expired_lease",
    "stale_binding",
)

# The cost-provenance basis, shared by stage_run and utility_run.
COST_BASES: tuple[str, ...] = (
    "provider_settled",
    "runtime_estimate",
    "price_table_estimate",
    "unavailable",
)

# guard_decision.decision's closed set.
GUARD_DECISIONS: tuple[str, ...] = ("allow", "redact", "deny")

# approval_record.gate's closed set: the five gates an approval can bind.
APPROVAL_GATES: tuple[str, ...] = ("trust_profile", "plan", "review", "graduation", "manifest")

# approval_record.decision's closed set.
APPROVAL_DECISIONS: tuple[str, ...] = ("approve", "reject", "redirect")

# reviewer_set.kind's closed set: the planned set from the plan's path table,
# the actual set from the exact diff, and the effective merge of the two.
REVIEWER_SET_KINDS: tuple[str, ...] = ("planned", "actual", "effective")

# evidence_tuple.kind's closed set.
EVIDENCE_TUPLE_KINDS: tuple[str, ...] = ("plan", "review")

# queue_item.kind's closed set: every Initial kind of item that needs a human.
QUEUE_ITEM_KINDS: tuple[str, ...] = (
    "question",
    "eligibility",
    "plan_approval",
    "packet_approval",
    "red_check",
    "escalation",
    "manual_pause",
    "pr_outcome",
    "rubric_inspection",
)

# The coarse active-attention bucket a human enters on a plan or review
# decision, and may enter on any other queue action. `unknown` is a value
# in its own right: the factory never derives a bucket from editor
# activity, so an unentered bucket is recorded as unknown, not inferred.
ATTENTION_BUCKETS: tuple[str, ...] = (
    "under_2m",
    "2_to_5m",
    "5_to_15m",
    "15_to_30m",
    "over_30m",
    "unknown",
)

# external_write.operation's closed set: the four Initial outbox intents.
EXTERNAL_WRITE_OPERATIONS: tuple[str, ...] = ("pr_create", "pr_update", "digest", "jira_feedback")

# external_write.state's closed set. `pending` is created and not yet
# sent; `sending` is ambiguous (the deliverer was called and no receipt
# was stored) and must reconcile before anything else under its key;
# `reconciled` holds a receipt whose remote object matches the intent;
# `failed` and `superseded` are terminal for the row.
EXTERNAL_WRITE_STATES: tuple[str, ...] = ("pending", "sending", "reconciled", "failed", "superseded")

# tag.event_kind's closed set.
TAG_EVENT_KINDS: tuple[str, ...] = (
    "revision_after_approval",
    "incident",
    "control_defect",
    "override",
    "abandoned",
    "escalation",
    "stale_index",
    "send_back",
    "packet_defect",
    "policy_exception",
)

# incident_observation.record_kind's closed set: an event root, a
# disposition over a root, or a coverage record, in the production and
# control series.
INCIDENT_RECORD_KINDS: tuple[str, ...] = (
    "production_incident_event",
    "production_disposition",
    "production_coverage",
    "control_defect_event",
    "control_disposition",
)

# utility_run.kind's closed set: work that is not itself a ticket stage.
UTILITY_KINDS: tuple[str, ...] = (
    "setup",
    "digest",
    "baseline_import",
    "purge",
    "reindex",
    "report",
    "fixture_replay",
    "improvement",
    "refused_request",
    "other",
)

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
            # Pinned at eligibility; moved only by a human-approved manifest
            # migration, which returns the ticket to context.
            Column("factory_manifest_hash", "TEXT", mutable=True),
            Column("tier_provisional", "TEXT"),
            Column("tier_final", "TEXT"),
            Column("tier_override_by", "TEXT", mutable=True),
            Column("tier_override_at", "TEXT", mutable=True),
            Column("tier_override_reason", "TEXT", mutable=True),
            Column("scrutiny_requested", "TEXT"),
            # Display summary, not an approval gate input.
            Column("required_approvers", "TEXT"),
            Column("state", "TEXT", mutable=True),
            # Null except while blocked; the single queue_item for the current wait.
            Column("blocked_on", "INTEGER", references="queue_item.id", mutable=True),
            Column("pause_requested", "INTEGER", mutable=True),
            Column("paused_at", "TEXT", mutable=True),
            # These five are pinned at eligibility, after the ticket row
            # already exists, so the first value is always an in-place
            # update rather than part of the insert; they are moved again
            # only by the human's refresh-base and by the S4 hand-back.
            Column("base_sha", "TEXT", mutable=True),
            Column("target_base_sha", "TEXT", mutable=True),
            Column("branch", "TEXT", mutable=True),
            Column("worktree_path", "TEXT", mutable=True),
            Column("head_sha", "TEXT", mutable=True),
            Column("pr_url", "TEXT", mutable=True),
            Column("pr_identity", "TEXT", mutable=True),
            Column("last_remote_head_sha", "TEXT", mutable=True),
            Column("last_pr_body_hash", "TEXT", mutable=True),
            # True only for the pre-factory baseline provenance rows.
            Column("baseline", "INTEGER"),
            Column("opened_at", "TEXT", mutable=True),
            Column("factory_completed_at", "TEXT", mutable=True),
            Column("closed_at", "TEXT", mutable=True),
            Column("close_reason", "TEXT", mutable=True),
            Column("final_head_sha", "TEXT"),
            Column("final_target_base_sha", "TEXT"),
            Column("final_pr_body_hash", "TEXT"),
            Column("merge_sha", "TEXT"),
            Column("required_checks_disposition", "TEXT"),
            Column("approval_disposition", "TEXT"),
            Column("external_revision_count", "INTEGER"),
            # Later field; reserved now so it never needs a migration.
            Column("close_survey", "TEXT"),
            Column("updated_at", "TEXT", mutable=True),
        ),
    ),
    Table(
        "stage_run",
        (
            _id(),
            Column("ticket_id", "INTEGER", nullable=False, references="ticket.id"),
            Column("stage", "TEXT", nullable=False, values=STAGES),
            Column("plan_item", "TEXT"),
            Column("plan_tuple_id", "INTEGER", references="evidence_tuple.id"),
            Column("attempt", "INTEGER"),
            Column("verification_attempt", "INTEGER"),
            Column("run_kind", "TEXT", values=RUN_KINDS),
            Column("parent_run_id", "INTEGER", references="stage_run.id"),
            Column("tier", "TEXT"),
            # The operating-system process that holds the lease, so a restart
            # can tell a slow live run from a dead one: a lease is expired
            # only when it has lapsed and this process is gone too.
            Column("process_identity", "TEXT"),
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
            # The agent's self-report arrives when the run ends, so it is
            # settled after the row exists, capped by tiers.yaml on write.
            Column("reasoning_summary", "TEXT", mutable=True),
            Column("tokens_in", "INTEGER"),
            Column("tokens_out", "INTEGER"),
            Column("cost", "REAL", once="cost_settled_at"),
            Column("currency", "TEXT", once="cost_settled_at"),
            Column("cost_basis", "TEXT", once="cost_settled_at", values=COST_BASES),
            Column("pricing_table_hash", "TEXT", once="cost_settled_at"),
            Column("cost_settled_at", "TEXT", once="cost_settled_at"),
            Column("wall_clock_seconds", "REAL"),
            Column("outcome", "TEXT", mutable=True, values=OUTCOMES),
            Column("failure_kind", "TEXT", mutable=True, values=FAILURE_KINDS),
            Column("started_at", "TEXT", mutable=True),
            Column("heartbeat_at", "TEXT", mutable=True),
            Column("lease_expires_at", "TEXT", mutable=True),
            Column("ended_at", "TEXT", mutable=True),
            Column("updated_at", "TEXT", mutable=True),
        ),
    ),
    Table(
        "utility_run",
        (
            _id(),
            Column("ticket_id", "INTEGER", references="ticket.id"),
            Column("kind", "TEXT", values=UTILITY_KINDS),
            Column("inputs", "TEXT"),
            Column("outputs", "TEXT"),
            Column("manifest_hash", "TEXT"),
            Column("process_identity", "TEXT"),
            # Same runtime/model identity fields as stage_run, filled only
            # when the utility run uses an agent.
            Column("runtime", "TEXT"),
            Column("runtime_version", "TEXT"),
            Column("adapter_version", "TEXT"),
            Column("model_requested", "TEXT"),
            Column("model_resolved", "TEXT"),
            Column("tokens", "INTEGER"),
            Column("cost", "REAL"),
            Column("currency", "TEXT"),
            Column("cost_basis", "TEXT", values=COST_BASES),
            Column("pricing_table_hash", "TEXT"),
            Column("wall_clock_seconds", "REAL"),
            # A utility run is opened and later finished, same as a stage
            # run: outcome and ended_at are unknown until the work
            # completes, and a live run's lease is renewed by heartbeat.
            Column("outcome", "TEXT", mutable=True),
            Column("heartbeat_at", "TEXT", mutable=True),
            Column("lease_expires_at", "TEXT", mutable=True),
            Column("started_at", "TEXT"),
            Column("ended_at", "TEXT", mutable=True),
            # record.update always stamps this on an in-place change; every
            # other table with a mutable field carries the same column.
            Column("updated_at", "TEXT", mutable=True),
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
            Column("kind", "TEXT", values=QUEUE_ITEM_KINDS),
            # Polymorphic: a question_set, question, artefact, check_result
            # or stage_run id depending on `kind` — not a single-table FK.
            Column("ref", "TEXT"),
            Column("queued_at", "TEXT"),
            Column("resolved_at", "TEXT", once="resolved_at"),
            Column("resolved_by", "TEXT", once="resolved_at"),
            Column("action", "TEXT", once="resolved_at"),
            Column("note", "TEXT", once="resolved_at"),
            Column("approval_subject_hash", "TEXT"),
            Column("reviewer_set_id", "INTEGER", references="reviewer_set.id"),
            Column("active_attention_bucket", "TEXT", once="resolved_at", values=ATTENTION_BUCKETS),
            Column("updated_at", "TEXT", mutable=True),
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
            Column("state", "TEXT", mutable=True),
            Column("updated_at", "TEXT", mutable=True),
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
            # 'identity' or 'decision'; the two
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
            Column("decision", "TEXT", values=GUARD_DECISIONS),
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
            Column("kind", "TEXT", values=REVIEWER_SET_KINDS),
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
            # owner, minimum count, distinct_from).
            Column("slots", "TEXT"),
        ),
    ),
    Table(
        "approval_record",
        (
            _id(),
            Column("ticket_id", "INTEGER", references="ticket.id"),
            Column("gate", "TEXT", values=APPROVAL_GATES),
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
            Column("decision", "TEXT", values=APPROVAL_DECISIONS),
            Column("attestation_version", "TEXT"),
            Column("attestation_hash", "TEXT"),
            Column("evidence_ids", "TEXT"),
            Column("evidence_hashes", "TEXT"),
            Column("decision_supported_without_transcript", "INTEGER"),
            Column("active_attention_bucket", "TEXT", values=ATTENTION_BUCKETS),
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
            # "mandatory expiry": the one NOT NULL the entity definitions state
            # in prose rather than as a field-level rule.
            Column("expires_at", "TEXT", nullable=False),
            Column("canonical_serialization_version", "INTEGER"),
            Column("content_hash", "TEXT"),
        ),
    ),
    Table(
        "evidence_tuple",
        (
            _id(),
            Column("kind", "TEXT", values=EVIDENCE_TUPLE_KINDS),
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
            Column("operation", "TEXT", values=EXTERNAL_WRITE_OPERATIONS),
            Column("idempotency_key", "TEXT"),
            Column("payload_artefact_id", "INTEGER", references="artefact.id"),
            Column("payload_digest", "TEXT"),
            # Set by the dispatch attempt, not at intent creation: the guard
            # commits its own decision row, so guarding inside the
            # approval-plus-intent transaction would split that commit.
            Column("guard_decision_id", "INTEGER", references="guard_decision.id", mutable=True),
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
            Column("remote_pr_identity", "TEXT", mutable=True),
            Column("state", "TEXT", mutable=True, values=EXTERNAL_WRITE_STATES),
            Column("attempt_count", "INTEGER", mutable=True),
            Column("remote_identity", "TEXT", mutable=True),
            Column("receipt_artefact_id", "INTEGER", references="artefact.id", mutable=True),
            Column("last_error", "TEXT", mutable=True),
            Column("created_at", "TEXT"),
            Column("updated_at", "TEXT", mutable=True),
        ),
    ),
    Table(
        "tag",
        (
            _id(),
            Column("ticket_id", "INTEGER", references="ticket.id"),
            Column("event_kind", "TEXT", values=TAG_EVENT_KINDS),
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
            Column("record_kind", "TEXT", values=INCIDENT_RECORD_KINDS),
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

# The Later tables: created only by the migration that lands the
# row that first writes each one, never by this schema.
LATER_TABLES: frozenset[str] = frozenset(
    {"score", "human_signal", "proposal", "benchmark", "fixture_candidate"}
)

# The baseline_measure.measure value the graduation gate compares against
# the factory's own post-plan-approval revision count. A module constant so
# the baseline view and whatever later reads it never hand-copy the string.
BASELINE_REVISIONS_MEASURE = "revisions_per_ticket_after_plan_approval"

# (name, select statement) pairs; `ddl()` emits one `CREATE VIEW IF NOT
# EXISTS <name> AS <select>` per entry, after every table and its triggers.
#
# Every measure view here reads only the record: no view joins outside the
# tables `TABLES` declares. A factory-performance view (everything except
# the two baseline views) excludes `baseline = 1` tickets and carries a
# `manifest_hash` column a caller filters on with `WHERE manifest_hash = ?`.
# `v_ticket_manifest_cohorts` is the one place that resolves a ticket's
# manifest_hash: a row per `(ticket_id, manifest_hash)` a ticket actually
# ran a stage under, falling back to the ticket's own pinned
# `factory_manifest_hash` only when it has no stage runs yet. A migrated
# ticket therefore surfaces once per manifest it ran under, and every
# ticket-grained view built on this table inherits that "belongs to every
# cohort it ran under" rule rather than re-deriving it. A view whose rows
# come from `stage_run` directly (cost, tool calls, fix rounds, stage
# reliability) instead reads that run's own `manifest_hash` column, which
# is authoritative for the run that produced it and needs no cohort lookup.
VIEWS: tuple[tuple[str, str], ...] = (
    (
        "v_ticket_manifest_cohorts",
        "SELECT t.id AS ticket_id, "
        "COALESCE(sr.manifest_hash, t.factory_manifest_hash) AS manifest_hash, "
        "MIN(sr.started_at) AS first_run_started_at, "
        "MAX(sr.started_at) AS last_run_started_at "
        "FROM ticket t "
        "LEFT JOIN stage_run sr ON sr.ticket_id = t.id AND sr.manifest_hash IS NOT NULL "
        "WHERE t.baseline IS NOT 1 "
        "GROUP BY t.id, COALESCE(sr.manifest_hash, t.factory_manifest_hash)",
    ),
    (
        "v_revisions_per_ticket_by_fm",
        "SELECT mc.ticket_id, mc.manifest_hash, tag.fm_id, COUNT(*) AS revision_count "
        "FROM tag "
        "JOIN v_ticket_manifest_cohorts mc ON mc.ticket_id = tag.ticket_id "
        "WHERE tag.event_kind = 'revision_after_approval' "
        "GROUP BY mc.ticket_id, mc.manifest_hash, tag.fm_id",
    ),
    (
        "v_questions_per_ticket",
        # A question's tier is not its own column: it is read off the
        # `question` kind queue_item raised for it. Polymorphic refs on
        # queue_item and tag are `<table>:<id>` strings.
        "SELECT mc.ticket_id, mc.manifest_hash, qi.tier AS tier, COUNT(*) AS question_count "
        "FROM question q "
        "JOIN v_ticket_manifest_cohorts mc ON mc.ticket_id = q.ticket_id "
        "LEFT JOIN queue_item qi ON qi.kind = 'question' AND qi.ref = 'question:' || q.id "
        "GROUP BY mc.ticket_id, mc.manifest_hash, qi.tier",
    ),
    (
        "v_default_shown_share",
        "SELECT mc.manifest_hash, COUNT(*) AS total_questions, "
        "SUM(CASE WHEN q.default_option IS NOT NULL THEN 1 ELSE 0 END) AS shown_count "
        "FROM question q "
        "JOIN v_ticket_manifest_cohorts mc ON mc.ticket_id = q.ticket_id "
        "GROUP BY mc.manifest_hash",
    ),
    (
        "v_default_accepted_share",
        # The denominator is questions shown with a default; the numerator
        # counts immutable default_accepted answer events over them. Answer
        # rows are never updated or deleted, so a later superseding answer
        # cannot erase an event already counted here.
        "SELECT mc.manifest_hash, "
        "COUNT(DISTINCT q.id) AS shown_with_default_count, "
        "COUNT(a.id) AS default_accepted_count "
        "FROM question q "
        "JOIN v_ticket_manifest_cohorts mc ON mc.ticket_id = q.ticket_id "
        "LEFT JOIN answer a ON a.question_id = q.id AND a.resolution_kind = 'default_accepted' "
        "WHERE q.default_option IS NOT NULL "
        "GROUP BY mc.manifest_hash",
    ),
    (
        "v_queue_latency_by_stage_tier",
        # SQLite has no interval type: julianday() gives fractional days, so
        # the difference is scaled by 86400 to land in seconds, the unit the
        # column name promises. Labelled queue_latency_seconds, never
        # "attention" -- that is a separate, human-entered measure below.
        "SELECT mc.manifest_hash, qi.stage, qi.tier, COUNT(*) AS item_count, "
        "AVG((julianday(qi.resolved_at) - julianday(qi.queued_at)) * 86400.0) AS queue_latency_seconds "
        "FROM queue_item qi "
        "JOIN v_ticket_manifest_cohorts mc ON mc.ticket_id = qi.ticket_id "
        "WHERE qi.stage IN ('S2', 'S3', 'S6') "
        "AND qi.kind IN ('question', 'plan_approval', 'packet_approval') "
        "AND qi.resolved_at IS NOT NULL "
        "GROUP BY mc.manifest_hash, qi.stage, qi.tier",
    ),
    (
        "v_active_attention_by_stage_tier_outcome",
        # Attention is read only off approval_record.active_attention_bucket,
        # never derived from queue latency; `unknown` groups like any other
        # bucket rather than being filtered out.
        "SELECT mc.manifest_hash, "
        "CASE ar.gate WHEN 'plan' THEN 'S3' WHEN 'review' THEN 'S6' END AS stage, "
        "t.tier_final AS tier, ar.decision, ar.active_attention_bucket AS bucket, "
        "COUNT(*) AS record_count "
        "FROM approval_record ar "
        "JOIN ticket t ON t.id = ar.ticket_id "
        "JOIN v_ticket_manifest_cohorts mc ON mc.ticket_id = ar.ticket_id "
        "WHERE ar.gate IN ('plan', 'review') "
        "GROUP BY mc.manifest_hash, stage, tier, ar.decision, ar.active_attention_bucket",
    ),
    (
        "v_generated_test_kept_share",
        # Only the latest decision row per identity counts (a later review
        # subject appends rather than edits), so the denominator is
        # identities with at least one decision -- zero-generated-test
        # tickets contribute no identity row and so are absent, not a zero.
        "WITH latest_decision AS ("
        "SELECT d.identity_id, d.decision FROM generated_test d "
        "WHERE d.record_kind = 'decision' AND d.id = ("
        "SELECT MAX(d2.id) FROM generated_test d2 "
        "WHERE d2.record_kind = 'decision' AND d2.identity_id = d.identity_id)) "
        "SELECT mc.manifest_hash, COUNT(*) AS judged_count, "
        "SUM(CASE WHEN ld.decision = 'kept' THEN 1 ELSE 0 END) AS kept_count "
        "FROM latest_decision ld "
        "JOIN generated_test identity_row ON identity_row.id = ld.identity_id "
        "JOIN v_ticket_manifest_cohorts mc ON mc.ticket_id = identity_row.ticket_id "
        "GROUP BY mc.manifest_hash",
    ),
    (
        "v_plan_approved_no_redirect_share",
        # Only a ticket's first plan evidence_tuple (lowest id) is its first
        # canonical plan-approval subject; later plan subjects from a
        # send-back never rewrite this outcome.
        "WITH first_plan_subject AS ("
        "SELECT et.ticket_id, et.content_hash AS subject_hash FROM evidence_tuple et "
        "WHERE et.kind = 'plan' AND et.id = ("
        "SELECT MIN(et2.id) FROM evidence_tuple et2 "
        "WHERE et2.kind = 'plan' AND et2.ticket_id = et.ticket_id)), "
        "plan_decisions AS ("
        "SELECT fps.ticket_id, ar.id AS approval_record_id, ar.decision FROM first_plan_subject fps "
        "JOIN approval_record ar ON ar.ticket_id = fps.ticket_id "
        "AND ar.gate = 'plan' AND ar.subject_hash = fps.subject_hash) "
        "SELECT mc.manifest_hash, "
        "COUNT(DISTINCT pd.ticket_id) AS decided_count, "
        "COUNT(DISTINCT CASE WHEN NOT EXISTS ("
        "SELECT 1 FROM plan_decisions pd2 WHERE pd2.ticket_id = pd.ticket_id "
        "AND pd2.decision IN ('reject', 'redirect')"
        ") AND NOT EXISTS ("
        "SELECT 1 FROM plan_decisions pd3 "
        "JOIN tag tg ON tg.event_kind = 'send_back' AND tg.ref = 'approval_record:' || pd3.approval_record_id "
        "WHERE pd3.ticket_id = pd.ticket_id"
        ") THEN pd.ticket_id END) AS approved_no_redirect_count "
        "FROM plan_decisions pd "
        "JOIN v_ticket_manifest_cohorts mc ON mc.ticket_id = pd.ticket_id "
        "GROUP BY mc.manifest_hash",
    ),
    (
        "v_production_incidents_attributable",
        # One view, two record shapes distinguished by record_type: an
        # `incident` row is the attributable-count breakdown by severity and
        # disposition; a `coverage` row is one merged ticket's latest
        # production-coverage status. Event roots are read directly (never
        # superseded) and only their latest disposition decides attribution,
        # so a reviewed re-disposition supersedes the count without the
        # event row itself ever changing.
        "SELECT 'incident' AS record_type, io.severity AS severity, "
        "latest_disp.attribution AS attribution, latest_disp.disposition AS disposition, "
        "COUNT(*) AS incident_count, NULL AS ticket_id, mc1.manifest_hash AS manifest_hash, "
        "NULL AS coverage_status, NULL AS exposure_source, NULL AS exposure_start, "
        "NULL AS observed_through "
        "FROM incident_observation io "
        "LEFT JOIN v_ticket_manifest_cohorts mc1 ON mc1.ticket_id = io.ticket_id "
        "JOIN (SELECT d.event_id, d.attribution, d.disposition FROM incident_observation d "
        "WHERE d.record_kind = 'production_disposition' AND d.id = ("
        "SELECT MAX(d2.id) FROM incident_observation d2 "
        "WHERE d2.record_kind = 'production_disposition' AND d2.event_id = d.event_id"
        ")) latest_disp ON latest_disp.event_id = io.id "
        "WHERE io.record_kind = 'production_incident_event' "
        "AND latest_disp.attribution = 'attributable' "
        "GROUP BY io.severity, latest_disp.attribution, latest_disp.disposition, mc1.manifest_hash "
        "UNION ALL "
        "SELECT 'coverage' AS record_type, NULL AS severity, NULL AS attribution, "
        "NULL AS disposition, NULL AS incident_count, t.id AS ticket_id, "
        "mc2.manifest_hash AS manifest_hash, "
        "latest_cov.coverage_status AS coverage_status, "
        "latest_cov.exposure_source AS exposure_source, "
        "latest_cov.exposure_start AS exposure_start, "
        "latest_cov.observed_through AS observed_through "
        "FROM ticket t "
        "JOIN v_ticket_manifest_cohorts mc2 ON mc2.ticket_id = t.id "
        "JOIN (SELECT c.ticket_id, c.coverage_status, c.exposure_source, c.exposure_start, "
        "c.observed_through FROM incident_observation c "
        "WHERE c.record_kind = 'production_coverage' AND c.id = ("
        "SELECT MAX(c2.id) FROM incident_observation c2 "
        "WHERE c2.record_kind = 'production_coverage' AND c2.ticket_id = c.ticket_id"
        ")) latest_cov ON latest_cov.ticket_id = t.id "
        "WHERE t.closed_at IS NOT NULL AND t.close_reason = 'merged'",
    ),
    (
        "v_reconstruction_share_by_gate",
        # `packet_defect` tags with fm_id FM-10 point straight at the
        # affected approval_record (never merely its shared queue item), so
        # the join back is a plain ref-to-id match. A defect is resolved
        # when some other tag names it through resolves_tag_id.
        "WITH defect_tags AS ("
        "SELECT tg.id AS tag_id, tg.ref AS approval_record_ref, "
        "EXISTS(SELECT 1 FROM tag r WHERE r.resolves_tag_id = tg.id) AS is_resolved "
        "FROM tag tg WHERE tg.event_kind = 'packet_defect' AND tg.fm_id = 'FM-10') "
        "SELECT mc.manifest_hash, ar.gate, t.tier_final AS tier, ar.role, ar.decision, "
        "ar.active_attention_bucket AS bucket, COUNT(*) AS decision_count, "
        "SUM(CASE WHEN dt.tag_id IS NOT NULL THEN 1 ELSE 0 END) AS defect_tagged_count, "
        "SUM(CASE WHEN dt.tag_id IS NOT NULL AND dt.is_resolved THEN 1 ELSE 0 END) AS defect_resolved_count, "
        "SUM(CASE WHEN dt.tag_id IS NOT NULL AND NOT dt.is_resolved THEN 1 ELSE 0 END) AS defect_unresolved_count "
        "FROM approval_record ar "
        "JOIN ticket t ON t.id = ar.ticket_id "
        "JOIN v_ticket_manifest_cohorts mc ON mc.ticket_id = ar.ticket_id "
        "LEFT JOIN defect_tags dt ON dt.approval_record_ref = 'approval_record:' || ar.id "
        "WHERE ar.gate IN ('plan', 'review') "
        "GROUP BY mc.manifest_hash, ar.gate, t.tier_final, ar.role, ar.decision, ar.active_attention_bucket",
    ),
    (
        "v_escalations_per_ticket",
        "SELECT mc.ticket_id, mc.manifest_hash, COUNT(*) AS escalation_count "
        "FROM tag tg "
        "JOIN stage_run sr ON tg.ref = 'stage_run:' || sr.id AND sr.stage = 'S4' "
        "JOIN v_ticket_manifest_cohorts mc ON mc.ticket_id = tg.ticket_id "
        "WHERE tg.event_kind = 'escalation' "
        "GROUP BY mc.ticket_id, mc.manifest_hash",
    ),
    (
        "v_stale_index_entries_per_ticket",
        "SELECT mc.ticket_id, mc.manifest_hash, COUNT(*) AS stale_count "
        "FROM index_use iu "
        "JOIN stage_run sr ON sr.id = iu.stage_run_id "
        "JOIN v_ticket_manifest_cohorts mc ON mc.ticket_id = sr.ticket_id "
        "WHERE iu.stale = 1 "
        "GROUP BY mc.ticket_id, mc.manifest_hash",
    ),
    (
        "stage_reliability_view",
        # Narrowed to the first-attempt rule: run_kind = 'task' excludes
        # fix_round and validation_only, attempt = 1 excludes every retry,
        # parent_run_id IS NULL excludes every child run, and the outcome
        # list excludes blocked, refused, and aborted_human (a cancellation,
        # not a first-attempt result). Selecting from stage_run alone is
        # what excludes utility_run by construction.
        "SELECT sr.manifest_hash, sr.stage, sr.tier, COUNT(*) AS eligible_count, "
        "SUM(CASE WHEN sr.outcome = 'pass' THEN 1 ELSE 0 END) AS passed_count "
        "FROM stage_run sr "
        "JOIN ticket t ON t.id = sr.ticket_id "
        "WHERE sr.run_kind = 'task' AND sr.attempt = 1 AND sr.parent_run_id IS NULL "
        "AND sr.outcome IN ('pass', 'fail', 'infrastructure_failure', 'sandbox_violation', 'aborted_budget') "
        "AND (t.baseline IS NOT 1) "
        "GROUP BY sr.manifest_hash, sr.stage, sr.tier",
    ),
    (
        "v_ctx_completions_outcomes_per_window",
        # factory_completed_at counts a draft PR; closed_at separately
        # counts a manually observed merge/abandon outcome. Neither column
        # is read as a stand-in for the other.
        "SELECT mc.ticket_id, mc.manifest_hash, t.factory_completed_at, t.closed_at, t.close_reason "
        "FROM ticket t "
        "JOIN v_ticket_manifest_cohorts mc ON mc.ticket_id = t.id "
        "WHERE t.factory_completed_at IS NOT NULL OR t.closed_at IS NOT NULL",
    ),
    (
        "v_ctx_cost_per_ticket",
        # Currencies are never combined (grouped separately) and cost_basis
        # stays a group key so an estimate is never presented as settled
        # cost; a cost_basis = 'unavailable' group's run_count is exactly
        # the count of runs with no usable cost.
        "SELECT sr.ticket_id, sr.manifest_hash, sr.stage, sr.tier, sr.currency, sr.cost_basis, "
        "SUM(sr.cost) AS total_cost, COUNT(*) AS run_count "
        "FROM stage_run sr "
        "JOIN ticket t ON t.id = sr.ticket_id "
        "WHERE (t.baseline IS NOT 1) "
        "GROUP BY sr.ticket_id, sr.manifest_hash, sr.stage, sr.tier, sr.currency, sr.cost_basis",
    ),
    (
        "v_ctx_non_structural_touchpoints",
        # Only question, red_check and escalation count: eligibility is
        # structural and rubric_inspection is a factory-health signal, and
        # pr_outcome is excluded here as everywhere else non-structural
        # touchpoints or attention are read.
        "SELECT mc.ticket_id, mc.manifest_hash, qi.tier, COUNT(*) AS touchpoint_count "
        "FROM queue_item qi "
        "JOIN v_ticket_manifest_cohorts mc ON mc.ticket_id = qi.ticket_id "
        "WHERE qi.kind IN ('question', 'red_check', 'escalation') "
        "GROUP BY mc.ticket_id, mc.manifest_hash, qi.tier",
    ),
    (
        "v_ctx_fix_rounds_per_ticket",
        "SELECT sr.ticket_id, sr.manifest_hash, COUNT(*) AS fix_round_count "
        "FROM stage_run sr "
        "JOIN ticket t ON t.id = sr.ticket_id "
        "WHERE sr.stage = 'S4' AND sr.run_kind = 'fix_round' AND (t.baseline IS NOT 1) "
        "GROUP BY sr.ticket_id, sr.manifest_hash",
    ),
    (
        "v_ctx_tool_calls_bytes_per_stage_run",
        # An unavailable result_bytes is counted (unavailable_size_count),
        # never estimated into total_result_bytes.
        "SELECT tc.stage_run_id, sr.stage, sr.tier, sr.manifest_hash, "
        "COUNT(*) AS tool_call_count, "
        "SUM(CASE WHEN tc.result_bytes IS NOT NULL THEN tc.result_bytes ELSE 0 END) AS total_result_bytes, "
        "SUM(CASE WHEN tc.result_bytes IS NULL THEN 1 ELSE 0 END) AS unavailable_size_count, "
        "SUM(CASE WHEN tc.inline = 1 THEN 1 ELSE 0 END) AS inline_count "
        "FROM tool_call tc "
        "JOIN stage_run sr ON sr.id = tc.stage_run_id "
        "JOIN ticket t ON t.id = sr.ticket_id "
        "WHERE (t.baseline IS NOT 1) "
        "GROUP BY tc.stage_run_id, sr.stage, sr.tier, sr.manifest_hash",
    ),
    (
        "v_baseline_revisions_per_ticket",
        # Dedicated baseline view: reads only baseline_measure, requires no
        # manifest hash, and keeps approximate/unavailable rows visible
        # rather than dropping them.
        "SELECT ticket_id, service, ticket_type, tier, value, status, unavailable_reason, "
        "source_kind, source_ref, source_observed_at "
        "FROM baseline_measure "
        f"WHERE measure = '{BASELINE_REVISIONS_MEASURE}'",
    ),
)


def table(name: str) -> Table:
    """The declared `Table` named `name`; raises `KeyError` for an unknown table."""
    for candidate in TABLES:
        if candidate.name == name:
            return candidate
    raise KeyError(name)


def _mutability_triggers(table: Table) -> list[str]:
    """The append-only and once-settlement triggers for one table.

    Every column neither `mutable` nor in a `once` group shares one
    `BEFORE UPDATE OF <those columns>` trigger that always aborts: naming
    any of them in an UPDATE is the violation, whether or not the value
    changes (SQLite fires `UPDATE OF` on a named column even when its value
    is unchanged). Each `once` group gets a trigger that aborts only when
    its sentinel already holds a value, so the first settlement succeeds
    and every later one is rejected. Deletion is not addressed here:
    governed purge is a separate, later rule.
    """
    triggers = []
    immutable = [c.name for c in table.columns if not c.mutable and c.once is None]
    if immutable:
        triggers.append(
            f"CREATE TRIGGER IF NOT EXISTS {table.name}_immutable_columns "
            f"BEFORE UPDATE OF {', '.join(immutable)} ON {table.name} "
            f"BEGIN SELECT RAISE(ABORT, "
            f"'{table.name}: this column is append-only and cannot be edited in place'); END"
        )
    sentinels = {c.once for c in table.columns if c.once is not None}
    for sentinel in sorted(sentinels):
        group = [c.name for c in table.columns if c.once == sentinel]
        assert sentinel in group, f"{table.name}.{sentinel} must name itself as its own sentinel"
        triggers.append(
            f"CREATE TRIGGER IF NOT EXISTS {table.name}_{sentinel}_settle_once "
            f"BEFORE UPDATE OF {', '.join(group)} ON {table.name} "
            f"WHEN OLD.{sentinel} IS NOT NULL "
            f"BEGIN SELECT RAISE(ABORT, '{table.name}: already settled once'); END"
        )
    return triggers


def ddl() -> list[str]:
    """Return one `CREATE TABLE IF NOT EXISTS` statement per table, that
    table's mutability-enforcing triggers, and then every `VIEWS` entry, in
    that order.
    """
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
            if column.values is not None:
                quoted = ", ".join(f"'{value}'" for value in column.values)
                piece += f" CHECK ({column.name} IN ({quoted}))"
            lines.append(piece)
        for column in table.columns:
            if column.references:
                ref_table, ref_column = column.references.split(".")
                lines.append(
                    f"FOREIGN KEY ({column.name}) REFERENCES {ref_table}({ref_column})"
                )
        body = ",\n    ".join(lines)
        statements.append(f"CREATE TABLE IF NOT EXISTS {table.name} (\n    {body}\n)")
        statements.extend(_mutability_triggers(table))
    for view_name, select_sql in VIEWS:
        statements.append(f"CREATE VIEW IF NOT EXISTS {view_name} AS {select_sql}")
    return statements
