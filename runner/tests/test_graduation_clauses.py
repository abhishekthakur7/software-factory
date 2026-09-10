"""The graduation clauses over a seeded window: exposure/coverage, incidents, stage reliability,
baseline revisions, control defects, blind spots, self-containedness, and the report's context
block and view provenance.

`_passing_window`, `_report`, and `CUTOFF` are shared with `test_graduation.py` rather than
redefined here, the same way `test_gate_ab.py` reuses `test_gate.py`'s repo builder.
"""
import pytest

from runner import graduation, record, tags
from runner.db import connect
from runner.tests.fixtures.graduation import seed
from runner.tests.test_graduation import CUTOFF, _passing_window, _report


def _conn(tmp_path):
    return connect(tmp_path / "factory.sqlite")


def _limits(**overrides):
    return {
        "window_min_outcomes": 1, "stage_min_first_attempts": 1, "stage_min_pass_share": 0.5,
        "baseline_min_comparable": 1, "severe_severities": ["sev1", "sev2"], **overrides,
    }


def test_a_merged_window_ticket_with_no_recorded_exposure_fails_exposure_coverage(tmp_path):
    conn = _conn(tmp_path)
    ticket_id = seed.seed_window_ticket(conn, closed_at="2026-01-10T00:00:00", close_reason="merged")
    conn.commit()

    result = graduation.exposure_coverage(conn, [ticket_id], CUTOFF)

    assert result["passed"] is False
    assert ticket_id in result["inputs"]["missing_exposure_ticket_ids"]


def test_a_merged_window_ticket_with_no_coverage_through_the_cutoff_fails_exposure_coverage(tmp_path):
    conn = _conn(tmp_path)
    ticket_id = seed.seed_window_ticket(conn, closed_at="2026-01-10T00:00:00", close_reason="merged")
    seed.seed_coverage(conn, ticket_id, observed_through="2026-01-15T00:00:00")  # before CUTOFF
    conn.commit()

    result = graduation.exposure_coverage(conn, [ticket_id], CUTOFF)

    assert result["passed"] is False
    assert ticket_id in result["inputs"]["missing_coverage_ticket_ids"]


def test_a_severe_attributable_incident_in_the_window_fails_the_incidents_clause(tmp_path):
    conn = _conn(tmp_path)
    ticket_id = seed.seed_window_ticket(conn, closed_at="2026-01-10T00:00:00")
    event_id = seed.seed_incident_event(conn, ticket_id, severity="sev1")
    seed.seed_disposition(conn, event_id, ticket_id, attribution="attributable", disposition="reviewed_no_change")
    conn.commit()

    result = graduation.incidents(conn, [ticket_id], _limits())

    assert result["passed"] is False
    assert event_id in result["inputs"]["severe_attributable_event_ids"]


def test_an_incident_with_no_reviewed_attribution_or_disposition_fails_the_incidents_clause(tmp_path):
    conn = _conn(tmp_path)
    ticket_id = seed.seed_window_ticket(conn, closed_at="2026-01-10T00:00:00")
    event_id = seed.seed_incident_event(conn, ticket_id, severity="sev3")  # not severe; still needs a disposition
    conn.commit()

    result = graduation.incidents(conn, [ticket_id], _limits())

    assert result["passed"] is False
    assert event_id in result["inputs"]["missing_disposition_event_ids"]
    assert event_id not in result["inputs"]["severe_attributable_event_ids"]


def test_a_stage_below_the_first_attempt_floor_fails_the_stage_clause(tmp_path):
    """The excluded-denominator test: too few first attempts fails the stage outright."""
    conn = _conn(tmp_path)
    ticket_id = seed.seed_window_ticket(conn, closed_at="2026-01-10T00:00:00")
    seed.seed_stage_run(conn, ticket_id, stage="planning", outcome="pass")
    conn.commit()

    result = graduation.stage_reliability(conn, _limits(stage_min_first_attempts=5), seed.DEFAULT_MANIFEST_HASH)

    assert result["passed"] is False
    assert "stage_below_threshold:planning" in result["reasons"]
    assert result["inputs"]["per_stage"]["planning"]["eligible_count"] == 1


def test_a_stage_at_or_below_the_pass_share_floor_fails_the_stage_clause(tmp_path):
    conn = _conn(tmp_path)
    ticket_id = seed.seed_window_ticket(conn, closed_at="2026-01-10T00:00:00")
    seed.seed_stage_run(conn, ticket_id, stage="implementation", outcome="pass")
    seed.seed_stage_run(conn, ticket_id, stage="implementation", outcome="fail")
    conn.commit()

    result = graduation.stage_reliability(
        conn, _limits(stage_min_first_attempts=1, stage_min_pass_share=0.5), seed.DEFAULT_MANIFEST_HASH,
    )

    assert result["passed"] is False
    assert "stage_below_threshold:implementation" in result["reasons"]
    assert result["inputs"]["per_stage"]["implementation"]["pass_share"] == 0.5


def test_stage_clause_reports_excluded_outcomes_separately_from_eligible_runs(tmp_path):
    """The excluded outcomes never enter `eligible_count`, and are reported in `inputs` on their own."""
    conn = _conn(tmp_path)
    ticket_id = seed.seed_window_ticket(conn, closed_at="2026-01-10T00:00:00")
    parent_id = seed.seed_stage_run(conn, ticket_id, stage="implementation", outcome="pass")
    seed.seed_stage_run(conn, ticket_id, stage="implementation", outcome="blocked")
    seed.seed_stage_run(conn, ticket_id, stage="implementation", outcome="refused")
    seed.seed_stage_run(conn, ticket_id, stage="implementation", outcome="aborted_human")
    seed.seed_stage_run(conn, ticket_id, stage="implementation", outcome="pass", parent_run_id=parent_id)
    seed.seed_stage_run(conn, ticket_id, stage="implementation", outcome="pass", run_kind="fix_round")
    conn.commit()

    result = graduation.stage_reliability(
        conn, _limits(stage_min_first_attempts=1, stage_min_pass_share=0.5), seed.DEFAULT_MANIFEST_HASH,
    )

    assert result["inputs"]["per_stage"]["implementation"]["eligible_count"] == 1  # only the top-level passing run
    excluded = result["inputs"]["excluded"]["implementation"]
    assert excluded["blocked"] == 1
    assert excluded["refused"] == 1
    assert excluded["aborted_human"] == 1
    assert excluded["child_runs"] == 1
    assert excluded["non_task_run_kind"] == 1


def test_baseline_clause_compares_the_factory_mean_against_the_observed_baseline_mean(tmp_path):
    conn = _conn(tmp_path)
    ticket_id = seed.seed_window_ticket(conn, closed_at="2026-01-10T00:00:00")
    seed.seed_tag(conn, ticket_id, event_kind="revision_after_approval", tagged_by="abhishek")
    seed.seed_baseline_measure(conn, value=1.0, status="observed")
    conn.commit()

    result = graduation.baseline_revisions(conn, _limits(baseline_min_comparable=1), [ticket_id])

    assert result["inputs"]["factory_mean_revisions"] == 1.0
    assert result["inputs"]["baseline_mean_revisions"] == 1.0
    assert result["passed"] is True


def test_must_fail_baseline_clause_with_fewer_than_baseline_min_comparable_observed_rows(tmp_path):
    """The unavailable-baseline test."""
    conn = _conn(tmp_path)
    ticket_id = seed.seed_window_ticket(conn, closed_at="2026-01-10T00:00:00")
    seed.seed_baseline_measure(conn, value=1.0, status="observed")
    conn.commit()

    result = graduation.baseline_revisions(conn, _limits(baseline_min_comparable=2), [ticket_id])

    assert result["passed"] is False
    assert "unavailable_baseline" in result["reasons"]


def test_approximate_or_unavailable_baseline_rows_never_count_as_comparable(tmp_path):
    conn = _conn(tmp_path)
    ticket_id = seed.seed_window_ticket(conn, closed_at="2026-01-10T00:00:00")
    seed.seed_baseline_measure(conn, value=1.0, status="approximate")
    seed.seed_baseline_measure(conn, value=2.0, status="unavailable")
    conn.commit()

    result = graduation.baseline_revisions(conn, _limits(baseline_min_comparable=1), [ticket_id])

    assert result["passed"] is False
    assert "unavailable_baseline" in result["reasons"]
    assert result["inputs"]["observed_comparable_count"] == 0


def test_a_mechanically_tagged_revision_or_abandonment_fails_the_baseline_clause(tmp_path):
    """A human-chosen failure mode is one a human tagged; a mechanical tag on either kind fails the clause."""
    conn = _conn(tmp_path)
    ticket_id = seed.seed_window_ticket(conn, closed_at="2026-01-10T00:00:00")
    seed.seed_baseline_measure(conn, value=1.0, status="observed")
    seed.seed_tag(conn, ticket_id, event_kind="abandoned", tagged_by=tags.MECHANICAL_ACTOR)
    conn.commit()

    result = graduation.baseline_revisions(conn, _limits(baseline_min_comparable=1), [ticket_id])

    assert result["passed"] is False
    assert any("mechanically_tagged_human_decision" in reason for reason in result["reasons"])


CONTROL_CATEGORIES = ("data_boundary", "execution_boundary", "approval_binding", "reviewer_enforcement", "audit_reconstruction")


@pytest.mark.parametrize("category", CONTROL_CATEGORIES)
def test_an_open_control_defect_fails_the_control_defect_clause(tmp_path, category):
    conn = _conn(tmp_path)
    ticket_id = seed.seed_window_ticket(conn, closed_at="2026-01-10T00:00:00")
    tag_id = seed.seed_tag(conn, ticket_id, event_kind="control_defect", tagged_by="runner")
    event_id = seed.seed_control_defect_event(conn, ticket_id, tag_id, control_category=category)
    seed.seed_control_disposition(conn, event_id, ticket_id, disposition="open")
    conn.commit()

    result = graduation.control_defects(conn, [ticket_id])

    assert result["passed"] is False
    assert category in result["inputs"]["failing_categories"]


def test_a_remediated_control_defect_clears_the_control_defect_clause(tmp_path):
    conn = _conn(tmp_path)
    ticket_id = seed.seed_window_ticket(conn, closed_at="2026-01-10T00:00:00")
    tag_id = seed.seed_tag(conn, ticket_id, event_kind="control_defect", tagged_by="runner")
    event_id = seed.seed_control_defect_event(conn, ticket_id, tag_id, control_category="data_boundary")
    seed.seed_control_disposition(conn, event_id, ticket_id, disposition="remediated")
    conn.commit()

    result = graduation.control_defects(conn, [ticket_id])

    assert result["passed"] is True


def test_an_unresolved_blind_spot_fails_the_blind_spot_clause(tmp_path):
    conn = _conn(tmp_path)
    ticket_id = seed.seed_window_ticket(conn, closed_at="2026-01-10T00:00:00")
    stage_run_id = seed.seed_stage_run(conn, ticket_id, stage="checks")
    check_result_id = seed.seed_check_result(conn, stage_run_id, check_name="checkA", result="blind_spot")
    conn.commit()

    result = graduation.blind_spots(conn, [ticket_id], CUTOFF)

    assert result["passed"] is False
    assert check_result_id in result["inputs"]["failing_check_result_ids"]


def test_a_later_passing_result_on_the_same_check_resolves_a_blind_spot(tmp_path):
    conn = _conn(tmp_path)
    ticket_id = seed.seed_window_ticket(conn, closed_at="2026-01-10T00:00:00")
    stage_run_id = seed.seed_stage_run(conn, ticket_id, stage="checks")
    seed.seed_check_result(conn, stage_run_id, check_name="checkA", result="blind_spot")
    seed.seed_check_result(conn, stage_run_id, check_name="checkA", result="pass")
    conn.commit()

    result = graduation.blind_spots(conn, [ticket_id], CUTOFF)

    assert result["passed"] is True


def test_an_unsupported_decision_with_no_resolved_packet_defect_fails_self_containedness(tmp_path):
    conn = _conn(tmp_path)
    ticket_id = seed.seed_window_ticket(conn, closed_at="2026-01-10T00:00:00")
    approval_id = seed.seed_approval_record(conn, ticket_id, gate="review", decision_supported_without_transcript=0)
    conn.commit()

    result = graduation.self_containedness(conn, [ticket_id])

    assert result["passed"] is False
    assert approval_id in result["inputs"]["failing_approval_record_ids"]


def test_a_resolved_packet_defect_clears_self_containedness(tmp_path):
    conn = _conn(tmp_path)
    ticket_id = seed.seed_window_ticket(conn, closed_at="2026-01-10T00:00:00")
    approval_id = seed.seed_approval_record(conn, ticket_id, gate="review", decision_supported_without_transcript=0)
    defect_tag_id = seed.seed_tag(
        conn, ticket_id, event_kind="packet_defect", fm_id="unreviewable_diff", ref=f"approval_record:{approval_id}",
    )
    seed.seed_tag(
        conn, ticket_id, event_kind="flag_correction", resolves_tag_id=defect_tag_id, resolution_evidence_ref="pr:123",
    )
    conn.commit()

    result = graduation.self_containedness(conn, [ticket_id])

    assert result["passed"] is True
    assert approval_id not in result["inputs"]["failing_approval_record_ids"]


def test_a_decision_that_is_self_contained_needs_no_packet_defect_at_all(tmp_path):
    conn = _conn(tmp_path)
    ticket_id = seed.seed_window_ticket(conn, closed_at="2026-01-10T00:00:00")
    seed.seed_approval_record(conn, ticket_id, gate="plan", decision_supported_without_transcript=1)
    conn.commit()

    result = graduation.self_containedness(conn, [ticket_id])

    assert result["passed"] is True


def test_report_carries_the_context_measures_in_a_labelled_context_block(tmp_path):
    conn = _conn(tmp_path)
    limits_path, manifest_hash = _passing_window(conn, tmp_path)
    conn.commit()
    artefact_id = graduation.evaluate(conn, limits_path=limits_path, manifest_hash=manifest_hash, cutoff=CUTOFF)
    conn.commit()
    doc = _report(conn, artefact_id)

    assert set(doc["context"]) == set(graduation._CONTEXT_VIEWS)


def test_views_read_names_exactly_the_five_clause_views_never_the_excluded_ones(tmp_path):
    conn = _conn(tmp_path)
    limits_path, manifest_hash = _passing_window(conn, tmp_path)
    conn.commit()
    artefact_id = graduation.evaluate(conn, limits_path=limits_path, manifest_hash=manifest_hash, cutoff=CUTOFF)
    conn.commit()
    doc = _report(conn, artefact_id)

    assert set(doc["views_read"]) == set(graduation.VIEWS_READ)
    excluded = {"v_default_shown_share", "v_default_accepted_share", "v_plan_approved_no_redirect_share"}
    assert not (excluded & set(doc["views_read"]))
    assert not any(name.startswith("v_ctx_") for name in doc["views_read"])


def test_seeding_behind_the_excluded_views_never_changes_any_clause_verdict(tmp_path):
    """Changing every seeded value behind `v_default_shown_share`, `v_default_accepted_share`,
    `v_plan_approved_no_redirect_share`, and every context measure leaves every clause's verdict unchanged."""
    conn = _conn(tmp_path)
    limits_path, manifest_hash = _passing_window(conn, tmp_path)
    conn.commit()
    before_id = graduation.evaluate(conn, limits_path=limits_path, manifest_hash=manifest_hash, cutoff=CUTOFF)
    conn.commit()
    before = _report(conn, before_id)

    other_ticket_id = seed.seed_ticket(conn, closed_at=None, close_reason=None, manifest_hash=manifest_hash)
    # v_default_shown_share / v_default_accepted_share
    question_id = record.insert(conn, "question", ticket_id=other_ticket_id, text="q", default_option=0)
    record.insert(conn, "answer", question_id=question_id, resolution_kind="default_accepted")
    # v_plan_approved_no_redirect_share
    record.insert(conn, "evidence_tuple", ticket_id=other_ticket_id, kind="plan", content_hash="plan-1")
    plan_approval_id = record.insert(
        conn, "approval_record", ticket_id=other_ticket_id, gate="plan", decision="approve",
        subject_hash="plan-1", slot_id="plan_reviewer|", actor_identity="abhishek", role="plan_reviewer",
    )
    record.insert(
        conn, "tag", ticket_id=other_ticket_id, event_kind="send_back", fm_id="unjustified_abstraction",
        ref=f"approval_record:{plan_approval_id}", tagged_by="abhishek", tagged_at=record.now(),
    )
    # v_ctx_non_structural_touchpoints and friends
    record.insert(conn, "queue_item", ticket_id=other_ticket_id, kind="question", queued_at=record.now())
    conn.commit()

    after_id = graduation.evaluate(conn, limits_path=limits_path, manifest_hash=manifest_hash, cutoff=CUTOFF)
    conn.commit()
    after = _report(conn, after_id)

    for clause_name in before["clauses"]:
        assert after["clauses"][clause_name]["passed"] == before["clauses"][clause_name]["passed"], clause_name
