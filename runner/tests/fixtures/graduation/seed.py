"""Shared seeding for the graduation gate's tests.

Every graduation test builds its own small window by hand through these
helpers rather than `tags.tag`/`approvals.record_approval`'s own
validation: a clause under test often needs a row those writers would
themselves refuse (a mechanically-tagged human decision, an unresolved
defect, a stale disposition), and seeding it directly is the only way to
put the record in the state the clause must then judge.
"""
from pathlib import Path

import yaml

from runner import record

DEFAULT_MANIFEST_HASH = "mh-graduation-1"


def write_limits(tmp_path: Path, **overrides) -> Path:
    """A temporary `limits.yaml` carrying only a `graduation:` section, defaults overridable per test."""
    graduation = {
        "window_min_outcomes": 1,
        "stage_min_first_attempts": 1,
        "stage_min_pass_share": 0.5,
        "baseline_min_comparable": 1,
        "severe_severities": ["sev1", "sev2"],
        **overrides,
    }
    path = tmp_path / "limits.yaml"
    path.write_text(yaml.safe_dump({"graduation": graduation}))
    return path


def seed_ticket(
    conn, *, closed_at: str | None = None, close_reason: str | None = None, baseline: int = 0,
    manifest_hash: str = DEFAULT_MANIFEST_HASH, factory_completed_at: str | None = None,
) -> int:
    return record.insert(
        conn, "ticket", title="t", baseline=baseline, close_reason=close_reason, closed_at=closed_at,
        factory_manifest_hash=manifest_hash, factory_completed_at=factory_completed_at,
    )


def seed_window_ticket(
    conn, *, closed_at: str, close_reason: str = "merged", manifest_hash: str = DEFAULT_MANIFEST_HASH,
    factory_completed_at: str | None = None,
) -> int:
    """A ticket eligible for the window on its own: `baseline = 0`, closed with a countable reason."""
    return seed_ticket(
        conn, closed_at=closed_at, close_reason=close_reason, manifest_hash=manifest_hash,
        factory_completed_at=factory_completed_at if factory_completed_at is not None else closed_at,
    )


def seed_coverage(
    conn, ticket_id: int, *, coverage_status: str = "none_observed", exposure_start: str | None = "2026-01-01T00:00:00",
    exposure_source: str | None = "deployment", observed_through: str | None = "2026-02-01T00:00:00",
) -> int:
    return record.insert(
        conn, "incident_observation", ticket_id=ticket_id, record_kind="production_coverage",
        coverage_status=coverage_status, exposure_start=exposure_start, exposure_source=exposure_source,
        observed_through=observed_through, created_at=record.now(),
    )


def seed_incident_event(
    conn, ticket_id: int, *, severity: str = "sev1", occurred_at: str = "2026-01-05T00:00:00",
) -> int:
    return record.insert(
        conn, "incident_observation", ticket_id=ticket_id, record_kind="production_incident_event",
        severity=severity, occurred_at=occurred_at, created_at=record.now(),
    )


def seed_disposition(
    conn, event_id: int, ticket_id: int, *, attribution: str = "attributable", disposition: str = "remediated",
    created_at: str | None = None,
) -> int:
    return record.insert(
        conn, "incident_observation", ticket_id=ticket_id, record_kind="production_disposition",
        event_id=event_id, attribution=attribution, disposition=disposition,
        created_at=created_at or record.now(),
    )


def seed_control_defect_event(
    conn, ticket_id: int, tag_id: int, *, control_category: str = "data_boundary",
) -> int:
    return record.insert(
        conn, "incident_observation", ticket_id=ticket_id, record_kind="control_defect_event",
        control_category=control_category, tag_id=tag_id, created_at=record.now(),
    )


def seed_control_disposition(conn, event_id: int, ticket_id: int, *, disposition: str = "open") -> int:
    return record.insert(
        conn, "incident_observation", ticket_id=ticket_id, record_kind="control_disposition",
        event_id=event_id, disposition=disposition, created_at=record.now(),
    )


def seed_tag(
    conn, ticket_id: int, *, event_kind: str, fm_id: str = "FM-01", ref: str | None = None,
    tagged_by: str = "abhishek", resolves_tag_id: int | None = None, resolution_evidence_ref: str | None = None,
) -> int:
    return record.insert(
        conn, "tag", ticket_id=ticket_id, event_kind=event_kind, fm_id=fm_id, ref=ref or f"ticket:{ticket_id}",
        tagged_by=tagged_by, tagged_at=record.now(),
        resolves_tag_id=resolves_tag_id, resolution_evidence_ref=resolution_evidence_ref,
    )


def seed_stage_run(
    conn, ticket_id: int, *, stage: str, tier: str = "light", manifest_hash: str = DEFAULT_MANIFEST_HASH,
    attempt: int = 1, run_kind: str = "task", outcome: str = "pass", parent_run_id: int | None = None,
) -> int:
    return record.insert(
        conn, "stage_run", ticket_id=ticket_id, stage=stage, tier=tier, manifest_hash=manifest_hash,
        attempt=attempt, run_kind=run_kind, outcome=outcome, parent_run_id=parent_run_id,
    )


def seed_check_result(
    conn, stage_run_id: int, *, check_name: str = "check-a", check_tier: str = "blocking", result: str = "blind_spot",
    evidence_tuple_id: int | None = None,
) -> int:
    return record.insert(
        conn, "check_result", stage_run_id=stage_run_id, check_name=check_name, check_tier=check_tier,
        result=result, evidence_tuple_id=evidence_tuple_id,
    )


def seed_approval_record(
    conn, ticket_id: int, *, gate: str, decision: str = "approve", decision_supported_without_transcript: int = 1,
    evidence_tuple_id: int | None = None, decided_at: str | None = None,
) -> int:
    return record.insert(
        conn, "approval_record", ticket_id=ticket_id, gate=gate, decision=decision,
        decision_supported_without_transcript=decision_supported_without_transcript,
        evidence_tuple_id=evidence_tuple_id, decided_at=decided_at or record.now(),
    )


def seed_gate_run(conn, *, manifest_hash: str = DEFAULT_MANIFEST_HASH, outcome: str = "pass") -> int:
    return record.insert(conn, "utility_run", kind="gate", manifest_hash=manifest_hash, outcome=outcome)


def seed_baseline_measure(
    conn, *, value: float, status: str = "observed", measure: str = "revisions_per_ticket_after_plan_approval",
) -> int:
    return record.insert(conn, "baseline_measure", measure=measure, value=value, status=status)
