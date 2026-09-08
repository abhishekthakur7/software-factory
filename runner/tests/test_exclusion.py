"""The exclusion gate: the pilot eligibility matrix, every excluded surface, the checks-stage
removal-vs-required decision, the S1/S3/S5 discovery clauses, and the tier-override refusal on
an excluded ticket (R-S0-8).
"""
from pathlib import Path

import pytest
import yaml

from runner import governance, queue, record, transitions
from runner.checks import exclusion
from runner.db import connect
from runner.stages import run_stage

ABHISHEK = "abhishek"
FAR_FUTURE = "2999-01-01T00:00:00+00:00"

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "exclusion"


@pytest.fixture
def conn(tmp_path):
    connection = connect(tmp_path / "factory.sqlite")
    yield connection
    connection.close()


def _governed_ticket_fields(conn) -> dict:
    """Ticket fields that satisfy `S0.governance_valid`, the committed trust profile's default-path activation."""
    proposal = governance.propose()
    for role in ("security_approver", "legal_data_governance_approver"):
        governance.decide(
            conn, proposal, actor_identity=ABHISHEK, role=role, decision="approve",
            expires_at=FAR_FUTURE, attestation_version="v1", attestation_hash=f"att-{role}",
        )
    activated = governance.activation(conn, proposal)
    return {
        "trust_profile_hash": proposal.profile_hash,
        "trust_approval_set_hash": activated.trust_approval_set_hash,
        "service": "fixture-project",
        "source_kind": "jira",
        "source_ref": "FIX-1",
    }


# --- criterion 14: a pilot-eligible ticket passes the matrix (R-S0-8) ---

def test_a_pilot_eligible_ticket_passes_the_eligibility_matrix():
    reasons = exclusion.eligible(
        {"ticket_type": "small_feature", "repository_count": 1, "service_count": 1},
        {"tier": "T2", "language": "java", "repositories": ["fixture-project"]},
    )
    assert reasons == []


@pytest.mark.parametrize(
    "ticket_fields, service_config, expected_reason",
    [
        (
            {"ticket_type": "small_feature", "repository_count": 1, "service_count": 1},
            {"tier": "T1", "language": "java", "repositories": ["fixture-project"]},
            "service tier not T2",
        ),
        (
            {"ticket_type": "small_feature", "repository_count": 1, "service_count": 1},
            {"tier": "T2", "language": "python", "repositories": ["fixture-project"]},
            "language not java",
        ),
        (
            {"ticket_type": "feature", "repository_count": 1, "service_count": 1},
            {"tier": "T2", "language": "java", "repositories": ["fixture-project"]},
            "type not eligible",
        ),
        (
            {"ticket_type": "small_feature", "repository_count": 2, "service_count": 1},
            {"tier": "T2", "language": "java", "repositories": ["fixture-project"]},
            "more than one repository or service",
        ),
    ],
)
def test_must_reject_a_ticket_that_fails_one_matrix_dimension(ticket_fields, service_config, expected_reason):
    reasons = exclusion.eligible(ticket_fields, service_config)
    assert expected_reason in reasons


# --- criteria 5 and 15: every excluded surface rejects mechanically at S0 (R-S0-5, R-S0-8) ---

_SURFACE_TITLES = {
    "sensitive_path": "Touch src/main/java/com/fixture/auth/Login.java",
    "auth_or_permission": "Rework the authentication flow",
    "payments_or_secrets": "Update the payment processor secret rotation",
    "schema_or_data_migration": "Run a database migration for orders",
    "infrastructure": "Update the kubernetes deployment pipeline",
    "regulated_or_disallowed_data": "Handle GDPR personal health information",
    "public_contract": "Add a new public API endpoint",
    "unavailable_production_facts": "Investigate the current production error budget",
}


@pytest.mark.parametrize("surface, title", sorted(_SURFACE_TITLES.items()))
def test_must_reject_every_excluded_surface_mechanically_at_s0(conn, tmp_path, surface, title):
    ticket_id = record.insert(
        conn, "ticket", state="intake", opened_at=record.now(), title=title,
        service="fixture-project", ticket_type="small_feature",
    )
    outcome = run_stage(conn, ticket_id, "S0", runs_dir=tmp_path)
    assert outcome == "fail"
    ticket = record.get(conn, "ticket", ticket_id)
    assert ticket["state"] == "rejected"
    assert ticket["close_reason"] == "pilot_excluded"


def test_surfaces_in_text_finds_the_surface_a_title_names():
    hits = exclusion.surfaces_in_text("Rework the authentication flow")
    assert "auth_or_permission" in hits


def test_surfaces_in_paths_finds_the_sensitive_path_surface_from_sensitive_paths_yaml():
    hits = exclusion.surfaces_in_paths(["src/main/java/com/fixture/auth/Login.java"])
    assert "sensitive_path" in hits


# --- criteria 16, 17, 18: S1/S3/S5 discovery clauses over recorded check_result rows (R-S0-8) ---

def test_a_recorded_s1_exclusion_moves_the_ticket_from_context_to_rejected(conn):
    ticket_id = record.insert(conn, "ticket", state="context", opened_at=record.now())
    stage_run_id = record.insert(conn, "stage_run", ticket_id=ticket_id, stage="S1", attempt=1)
    record.insert(
        conn, "check_result", stage_run_id=stage_run_id, check_name="exclusion", result="fail",
        summary="auth_or_permission surface discovered in the touched files",
    )

    event = exclusion.apply_recorded_exclusion(conn, ticket_id)

    assert event == "rejected"
    ticket = record.get(conn, "ticket", ticket_id)
    assert ticket["state"] == "rejected"
    assert ticket["close_reason"] == "pilot_excluded"


def test_a_recorded_s3_exclusion_moves_the_ticket_from_planning_to_rejected(conn):
    ticket_id = record.insert(conn, "ticket", state="planning", opened_at=record.now())
    stage_run_id = record.insert(conn, "stage_run", ticket_id=ticket_id, stage="S3", attempt=1)
    record.insert(
        conn, "check_result", stage_run_id=stage_run_id, check_name="exclusion", result="fail",
        summary="schema_or_data_migration surface discovered in the plan's scope",
    )

    event = exclusion.apply_recorded_exclusion(conn, ticket_id)

    assert event == "rejected"
    ticket = record.get(conn, "ticket", ticket_id)
    assert ticket["state"] == "rejected"
    assert ticket["close_reason"] == "pilot_excluded"


def test_a_recorded_s5_required_surface_moves_the_ticket_from_checks_to_rejected(conn):
    ticket_id = record.insert(conn, "ticket", state="checks", opened_at=record.now())
    stage_run_id = record.insert(conn, "stage_run", ticket_id=ticket_id, stage="S5", attempt=1)
    record.insert(
        conn, "check_result", stage_run_id=stage_run_id, check_name="exclusion", result="fail",
        summary="payments_or_secrets surface required by the plan's own paths",
    )

    event = exclusion.apply_recorded_exclusion(conn, ticket_id)

    assert event == "rejected"
    ticket = record.get(conn, "ticket", ticket_id)
    assert ticket["state"] == "rejected"
    assert ticket["close_reason"] == "pilot_excluded"


def test_must_reject_applying_a_recorded_exclusion_with_no_check_result(conn):
    ticket_id = record.insert(conn, "ticket", state="context", opened_at=record.now())
    with pytest.raises(LookupError):
        exclusion.apply_recorded_exclusion(conn, ticket_id)


# --- criterion 19: an accidental excluded path returns to implementing for removal; a plan-required one does not (R-S0-8) ---

def test_an_accidental_excluded_path_not_required_by_the_plan_returns_for_removal():
    fixture = yaml.safe_load((FIXTURES_DIR / "accidental_removal.yaml").read_text())
    event = exclusion.decide_at_checks(plan_paths=fixture["plan_paths"], diff_paths=fixture["diff_paths"])
    assert event == "checks_removal_return"


def test_an_excluded_path_the_plan_itself_requires_is_sensitive_path_required():
    fixture = yaml.safe_load((FIXTURES_DIR / "required_by_plan.yaml").read_text())
    event = exclusion.decide_at_checks(plan_paths=fixture["plan_paths"], diff_paths=fixture["diff_paths"])
    assert event == "checks_sensitive_path_required"


def test_the_removal_event_applies_from_checks_to_implementing(conn):
    fixture = yaml.safe_load((FIXTURES_DIR / "accidental_removal.yaml").read_text())
    ticket_id = record.insert(conn, "ticket", state="checks", opened_at=record.now())
    event = exclusion.decide_at_checks(plan_paths=fixture["plan_paths"], diff_paths=fixture["diff_paths"])
    assert transitions.apply(conn, ticket_id, event) == "implementing"


def test_must_reject_deciding_at_checks_with_no_excluded_path_in_the_diff():
    with pytest.raises(ValueError):
        exclusion.decide_at_checks(
            plan_paths=["src/main/java/com/fixture/service/OrderService.java"],
            diff_paths=["src/main/java/com/fixture/service/OrderService.java"],
        )


# --- criterion 20: an override refuses on a ticket excluded by a later-stage discovery (R-S0-8) ---

def test_must_reject_override_on_a_ticket_excluded_via_a_recorded_s1_check(conn, tmp_path):
    fields = _governed_ticket_fields(conn)
    ticket_id = record.insert(conn, "ticket", state="context", opened_at=record.now(), **fields)
    stage_run_id = record.insert(conn, "stage_run", ticket_id=ticket_id, stage="S1", attempt=1)
    record.insert(
        conn, "check_result", stage_run_id=stage_run_id, check_name="exclusion", result="fail",
        summary="auth_or_permission surface discovered in the touched files",
    )
    exclusion.apply_recorded_exclusion(conn, ticket_id)

    item_id = queue.open_item(conn, ticket_id=ticket_id, kind="eligibility")
    with pytest.raises(queue.ActionRefused):
        queue.act(
            conn, item_id=item_id, action="override", actor=ABHISHEK, tier="heavy",
            fm_id="FM-05", runs_dir=tmp_path,
        )
    assert record.get(conn, "ticket", ticket_id)["tier_override_by"] is None
