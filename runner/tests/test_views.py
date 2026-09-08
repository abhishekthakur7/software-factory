"""The eighteen named measure views, the manifest-cohort helper, and the
dedicated baseline views: baseline isolation, the migrated-ticket dual
cohort, the manifest_hash filter, and one value test per view.
"""
import pytest

from runner import record, schema
from runner.db import connect

MEASURE_VIEW_NAMES: tuple[str, ...] = tuple(
    name for name, _ in schema.VIEWS if name not in ("v_ticket_manifest_cohorts", "v_baseline_revisions_per_ticket")
)


def _open(tmp_path):
    return connect(tmp_path / "factory.sqlite")


def _rows(conn, view):
    return [dict(row) for row in conn.execute(f"SELECT * FROM {view}").fetchall()]


def _has_subset(rows: list[dict], expected: dict) -> bool:
    return any(all(row.get(k) == v for k, v in expected.items()) for row in rows)


def _seed_full_scenario(conn) -> dict[str, int]:
    """One ticket touching every one of the eighteen views, with a
    predictable, individually-checkable value in each.
    """
    ticket_id = record.insert(
        conn, "ticket", title="t", factory_manifest_hash="m1", tier_final="light",
        target_base_sha="base1", base_sha="base1", service="svc", ticket_type="type_a",
    )
    s4_run = record.insert(
        conn, "stage_run", ticket_id=ticket_id, stage="S4", tier="light", manifest_hash="m1",
        attempt=1, run_kind="task", outcome="pass", started_at="2026-01-01T00:00:00",
        cost=10.0, currency="USD", cost_basis="provider_settled",
    )
    record.insert(
        conn, "stage_run", ticket_id=ticket_id, stage="S4", tier="light", manifest_hash="m1",
        attempt=2, run_kind="fix_round", outcome="fail", started_at="2026-01-01T01:00:00",
    )
    record.insert(conn, "tool_call", stage_run_id=s4_run, seq=1, tool="grep", result_bytes=1024, inline=1)
    record.insert(conn, "tool_call", stage_run_id=s4_run, seq=2, tool="write", result_bytes=None, inline=0)
    record.insert(conn, "index_use", stage_run_id=s4_run, entry_path="docs/x.md", stale=1)

    question_id = record.insert(conn, "question", ticket_id=ticket_id, stage="S2", round=1, default_option=0)
    record.insert(
        conn, "queue_item", ticket_id=ticket_id, stage="S2", tier="light", kind="question",
        ref=str(question_id), queued_at="2026-01-01T00:00:00", resolved_at="2026-01-01T00:05:00",
        active_attention_bucket="under_2m",
    )
    record.insert(conn, "answer", question_id=question_id, resolution_kind="default_accepted", answered_at="2026-01-01T00:05:00")

    record.insert(conn, "tag", ticket_id=ticket_id, event_kind="revision_after_approval", fm_id="FM-01")
    record.insert(conn, "tag", ticket_id=ticket_id, event_kind="escalation", fm_id="FM-02", ref=str(s4_run))

    identity_id = record.insert(
        conn, "generated_test", record_kind="identity", ticket_id=ticket_id, stage_run_id=s4_run,
        initial_path="t.py", initial_hash="h1",
    )
    record.insert(conn, "generated_test", record_kind="decision", identity_id=identity_id, decision="kept")

    plan_tuple_id = record.insert(
        conn, "evidence_tuple", kind="plan", ticket_id=ticket_id,
        base_sha="base1", target_base_sha="base1", content_hash="plan_subject_1",
    )
    record.insert(
        conn, "approval_record", ticket_id=ticket_id, gate="plan", subject_hash="plan_subject_1",
        decision="approve", role="engineer", active_attention_bucket="under_2m",
    )
    review_tuple_id = record.insert(
        conn, "evidence_tuple", kind="review", ticket_id=ticket_id,
        plan_tuple_id=plan_tuple_id, content_hash="review_subject_1",
    )
    review_approval_id = record.insert(
        conn, "approval_record", ticket_id=ticket_id, gate="review", subject_hash="review_subject_1",
        decision="approve", role="engineer", active_attention_bucket="5_to_15m",
    )
    record.insert(conn, "tag", ticket_id=ticket_id, event_kind="packet_defect", fm_id="FM-10", ref=str(review_approval_id))

    record.insert(
        conn, "queue_item", ticket_id=ticket_id, stage="S6", tier="light", kind="packet_approval",
        queued_at="2026-01-02T00:00:00", resolved_at="2026-01-02T00:10:00",
    )
    record.insert(
        conn, "queue_item", ticket_id=ticket_id, stage="S4", tier="light", kind="red_check",
        queued_at="2026-01-01T00:00:00", resolved_at="2026-01-01T00:02:00",
    )

    event_id = record.insert(
        conn, "incident_observation", record_kind="production_incident_event",
        severity="sev2", occurred_at="2026-01-03T00:00:00",
    )
    record.insert(
        conn, "incident_observation", record_kind="production_disposition",
        event_id=event_id, attribution="attributable", disposition="open",
    )
    record.insert(
        conn, "incident_observation", record_kind="production_coverage",
        ticket_id=ticket_id, coverage_status="none_observed", observed_through="2026-01-06T00:00:00",
    )
    record.update(conn, "ticket", ticket_id, closed_at="2026-01-05T00:00:00", close_reason="merged")
    record.update(conn, "ticket", ticket_id, factory_completed_at="2026-01-04T00:00:00")

    return {"ticket_id": ticket_id, "s4_run": s4_run, "question_id": question_id}


EXPECTED: dict[str, dict] = {
    "v_revisions_per_ticket_by_fm": {"manifest_hash": "m1", "fm_id": "FM-01", "revision_count": 1},
    "v_questions_per_ticket": {"manifest_hash": "m1", "tier": "light", "question_count": 1},
    "v_default_shown_share": {"manifest_hash": "m1", "total_questions": 1, "shown_count": 1},
    "v_default_accepted_share": {"manifest_hash": "m1", "shown_with_default_count": 1, "default_accepted_count": 1},
    "v_queue_latency_by_stage_tier": {"manifest_hash": "m1", "stage": "S2", "tier": "light", "item_count": 1},
    "v_active_attention_by_stage_tier_outcome": {
        "manifest_hash": "m1", "stage": "S3", "tier": "light", "decision": "approve", "bucket": "under_2m",
    },
    "v_generated_test_kept_share": {"manifest_hash": "m1", "judged_count": 1, "kept_count": 1},
    "v_plan_approved_no_redirect_share": {"manifest_hash": "m1", "decided_count": 1, "approved_no_redirect_count": 1},
    "v_production_incidents_attributable": {"record_type": "incident", "severity": "sev2", "attribution": "attributable", "incident_count": 1},
    "v_reconstruction_share_by_gate": {
        "manifest_hash": "m1", "gate": "review", "tier": "light", "role": "engineer",
        "decision": "approve", "defect_tagged_count": 1, "defect_unresolved_count": 1,
    },
    "v_escalations_per_ticket": {"manifest_hash": "m1", "escalation_count": 1},
    "v_stale_index_entries_per_ticket": {"manifest_hash": "m1", "stale_count": 1},
    "stage_reliability_view": {"manifest_hash": "m1", "stage": "S4", "tier": "light", "eligible_count": 1, "passed_count": 1},
    "v_ctx_completions_outcomes_per_window": {"manifest_hash": "m1", "close_reason": "merged"},
    "v_ctx_cost_per_ticket": {"manifest_hash": "m1", "stage": "S4", "currency": "USD", "cost_basis": "provider_settled", "total_cost": 10.0},
    "v_ctx_non_structural_touchpoints": {"manifest_hash": "m1", "tier": "light", "touchpoint_count": 2},
    "v_ctx_fix_rounds_per_ticket": {"manifest_hash": "m1", "fix_round_count": 1},
    "v_ctx_tool_calls_bytes_per_stage_run": {
        "stage": "S4", "manifest_hash": "m1", "tool_call_count": 2,
        "total_result_bytes": 1024, "unavailable_size_count": 1, "inline_count": 1,
    },
}


def test_every_named_measure_view_exists():
    """R-O-4: the eighteen names `06-observability.md`'s Measure
    computations table lists are all present in the schema, in order."""
    assert len(MEASURE_VIEW_NAMES) == 18


@pytest.mark.parametrize("view_name", MEASURE_VIEW_NAMES)
def test_the_view_returns_its_computed_value_for_seeded_rows(tmp_path, view_name):
    """R-O-4: each of the eighteen views, queried directly with no report
    script involved, produces the value its Measure computations row
    describes for a scenario seeding every measure at once."""
    conn = _open(tmp_path)
    _seed_full_scenario(conn)

    rows = _rows(conn, view_name)

    assert _has_subset(rows, EXPECTED[view_name]), rows


def test_a_baseline_ticket_is_excluded_from_every_factory_performance_view(tmp_path):
    """R-O-4: a `baseline = true` ticket's rows never surface in any of the
    eighteen measure views, even though the same scenario populates every
    one of them for a real ticket."""
    conn = _open(tmp_path)
    ticket_id = record.insert(conn, "ticket", title="baseline t", baseline=1, service="svc", ticket_type="type_a")
    s4_run = record.insert(
        conn, "stage_run", ticket_id=ticket_id, stage="S4", tier="light", manifest_hash="m1",
        attempt=1, run_kind="task", outcome="pass", cost=5.0, currency="USD", cost_basis="provider_settled",
    )
    record.insert(conn, "tag", ticket_id=ticket_id, event_kind="revision_after_approval", fm_id="FM-01")
    record.insert(conn, "tag", ticket_id=ticket_id, event_kind="escalation", fm_id="FM-02", ref=str(s4_run))
    record.insert(conn, "index_use", stage_run_id=s4_run, entry_path="docs/x.md", stale=1)
    record.insert(
        conn, "tool_call", stage_run_id=s4_run, seq=1, tool="grep", result_bytes=1024, inline=1,
    )

    for view_name in MEASURE_VIEW_NAMES:
        assert _rows(conn, view_name) == [], f"{view_name} leaked a baseline ticket's row"


def test_a_ticket_migrated_to_a_new_manifest_appears_in_both_cohorts(tmp_path):
    """R-O-4: a ticket with stage runs under two manifest hashes belongs to
    both cohorts, and the cohort helper view makes the migration boundary
    (first/last run timestamp per hash) visible."""
    conn = _open(tmp_path)
    ticket_id = record.insert(conn, "ticket", title="t", factory_manifest_hash="m2")
    s4_run = record.insert(
        conn, "stage_run", ticket_id=ticket_id, stage="S4", tier="light", manifest_hash="m1",
        attempt=1, run_kind="task", outcome="pass", started_at="2026-01-01T00:00:00",
    )
    record.insert(
        conn, "stage_run", ticket_id=ticket_id, stage="S4", tier="light", manifest_hash="m2",
        attempt=2, run_kind="task", outcome="pass", started_at="2026-02-01T00:00:00",
    )
    record.insert(conn, "tag", ticket_id=ticket_id, event_kind="escalation", fm_id="FM-02", ref=str(s4_run))

    cohorts = {row["manifest_hash"]: row for row in _rows(conn, "v_ticket_manifest_cohorts") if row["ticket_id"] == ticket_id}
    assert set(cohorts) == {"m1", "m2"}
    assert cohorts["m1"]["first_run_started_at"] == "2026-01-01T00:00:00"
    assert cohorts["m2"]["first_run_started_at"] == "2026-02-01T00:00:00"

    escalations = {row["manifest_hash"]: row["escalation_count"] for row in _rows(conn, "v_escalations_per_ticket")}
    assert escalations == {"m1": 1, "m2": 1}


def test_a_factory_performance_view_filters_by_a_seeded_tickets_manifest_hash(tmp_path):
    """R-O-4: a caller narrows a factory-performance view to one manifest
    with a plain `WHERE manifest_hash = ?`, using the ticket's own pinned
    `factory_manifest_hash`."""
    conn = _open(tmp_path)
    ticket_id = record.insert(conn, "ticket", title="t", factory_manifest_hash="m1")
    record.insert(conn, "tag", ticket_id=ticket_id, event_kind="revision_after_approval", fm_id="FM-01")
    other_ticket_id = record.insert(conn, "ticket", title="other", factory_manifest_hash="m2")
    record.insert(conn, "tag", ticket_id=other_ticket_id, event_kind="revision_after_approval", fm_id="FM-01")

    rows = conn.execute(
        "SELECT * FROM v_revisions_per_ticket_by_fm WHERE manifest_hash = ?", ("m1",)
    ).fetchall()

    assert [row["ticket_id"] for row in rows] == [ticket_id]


def test_the_dedicated_baseline_view_reads_baseline_measure_without_a_manifest(tmp_path):
    """R-O-4: the baseline view reads only `baseline_measure`, needs no
    manifest hash, and keeps approximate/unavailable rows visible."""
    conn = _open(tmp_path)
    ticket_id = record.insert(conn, "ticket", title="baseline t", baseline=1, service="svc", ticket_type="type_a")
    record.insert(
        conn, "baseline_measure", ticket_id=ticket_id, measure=schema.BASELINE_REVISIONS_MEASURE,
        service="svc", ticket_type="type_a", tier="light", value=2.0, status="observed",
    )
    unavailable_ticket_id = record.insert(conn, "ticket", title="baseline u", baseline=1)
    record.insert(
        conn, "baseline_measure", ticket_id=unavailable_ticket_id, measure=schema.BASELINE_REVISIONS_MEASURE,
        status="unavailable", unavailable_reason="no timestamped approved plan found",
    )

    rows = {row["ticket_id"]: row for row in _rows(conn, "v_baseline_revisions_per_ticket")}

    assert rows[ticket_id]["status"] == "observed"
    assert rows[ticket_id]["value"] == 2.0
    assert rows[unavailable_ticket_id]["status"] == "unavailable"
    assert rows[unavailable_ticket_id]["unavailable_reason"] == "no timestamped approved plan found"


@pytest.mark.parametrize(
    "outcome",
    ["blocked", "refused", "aborted_human"],
)
def test_a_narrowed_out_first_attempt_outcome_is_excluded_from_stage_reliability(tmp_path, outcome):
    """R-O-4: the narrowed `stage_reliability_view` excludes `blocked`,
    `refused`, and `aborted_human` even at attempt 1 with no parent."""
    conn = _open(tmp_path)
    ticket_id = record.insert(conn, "ticket", title="t")
    record.insert(
        conn, "stage_run", ticket_id=ticket_id, stage="S4", tier="light", manifest_hash="m1",
        attempt=1, run_kind="task", outcome=outcome,
    )

    assert _rows(conn, "stage_reliability_view") == []


@pytest.mark.parametrize(
    ("view_name", "join_fragment"),
    [
        ("v_revisions_per_ticket_by_fm", "tag.ticket_id"),
        ("v_questions_per_ticket", "q.ticket_id"),
        ("v_escalations_per_ticket", "tg.ticket_id"),
        ("v_stale_index_entries_per_ticket", "sr.ticket_id"),
    ],
)
def test_the_view_joins_to_its_ticket_through_ticket_id(view_name, join_fragment):
    """R-O-4: views over `question`, `queue_item`, `tag`, and `index_use`
    join to their ticket through `ticket_id` (`index_use` through
    `stage_run.ticket_id`), never through a polymorphic `ref` chain."""
    sql = dict(schema.VIEWS)[view_name]
    assert join_fragment in sql
