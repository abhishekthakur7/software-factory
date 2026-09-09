"""The intake field gate: acceptance criteria, owner, parent/Confluence link, and issue type (R-S0-1)."""
from pathlib import Path

import pytest
import yaml

from runner import artefact_registry, record
from runner.checks import intake_fields
from runner.stages import S0
from runner.stages import run_stage

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "intake_fields"
FIELD_NAMES = S0.load_ticket_types()["jira_fields"]


def _payload(name: str) -> dict:
    return yaml.safe_load((FIXTURES_DIR / f"{name}.yaml").read_text())


# --- each reject reason, first hit wins (R-S0-1) ---

def test_must_reject_empty_acceptance_criteria():
    finding = intake_fields.check(_payload("missing_acceptance_criteria"), field_names=FIELD_NAMES)
    assert finding.result == "fail"
    assert finding.detail == "missing acceptance criteria"


def test_must_reject_no_named_owner():
    finding = intake_fields.check(_payload("missing_owner"), field_names=FIELD_NAMES)
    assert finding.result == "fail"
    assert finding.detail == "missing owner"


def test_must_reject_no_parent_or_confluence_link():
    finding = intake_fields.check(_payload("missing_link"), field_names=FIELD_NAMES)
    assert finding.result == "fail"
    assert finding.detail == "missing parent or Confluence link"


def test_must_reject_epic_issue_type_with_the_reason_named():
    finding = intake_fields.check(_payload("epic"), field_names=FIELD_NAMES)
    assert finding.result == "fail"
    assert finding.detail == "needs child tickets"


# --- a payload clearing every check passes, reading field names from ticket-types.yaml (R-S0-1) ---

def test_a_complete_payload_passes():
    finding = intake_fields.check(_payload("ok"), field_names=FIELD_NAMES)
    assert finding.result == "pass"


def test_check_reads_field_names_from_ticket_types_yaml_not_a_hardcoded_mapping():
    """the same fixture, read through a field-name mapping that points
    everywhere else, fails for a reason the real mapping would not raise --
    proving `check` truly reads `field_names` rather than fixed keys."""
    payload = _payload("ok")
    scrambled = {name: f"not-a-real-key-{name}" for name in FIELD_NAMES}
    finding = intake_fields.check(payload, field_names=scrambled)
    assert finding.result == "fail"
    assert finding.detail == "missing acceptance criteria"


# --- S0 calls the gate before classification, writing one check_result row (R-S0-1) ---

@pytest.fixture
def conn(tmp_path):
    from runner.db import connect
    connection = connect(tmp_path / "factory.sqlite")
    yield connection
    connection.close()


def _seed_ticket_source(conn, ticket_id, tmp_path, **overrides) -> int:
    front_matter = {
        "jira_issue_type": "Story",
        "estimate": 2,
        "label": None,
        "owner": None,
        "parent_link": None,
        "confluence_link": None,
        "acceptance_criteria": None,
        **overrides,
    }
    text = "---\n" + yaml.safe_dump(front_matter, sort_keys=False) + "---\n\nSummary body.\n"
    path = tmp_path / f"ticket_source_{ticket_id}.md"
    path.write_text(text)
    return artefact_registry.register(conn, ticket_id=ticket_id, kind="ticket_source", path=path)


def test_s0_driver_records_the_check_result_row_and_rejects_on_a_gate_failure(conn, tmp_path):
    """the S0 driver, not just the pure `check` function: a jira-sourced
    ticket whose already-registered source carries no owner sees one
    `intake_fields` check_result row and is rejected before classification."""
    ticket_id = record.insert(
        conn, "ticket", state="intake", opened_at=record.now(),
        source_kind="jira", source_ref="FIX-1", service="fixture-project",
    )
    _seed_ticket_source(conn, ticket_id, tmp_path, acceptance_criteria="Given...When...Then...", parent_link="FIX-0")

    outcome = run_stage(conn, ticket_id, "S0", runs_dir=tmp_path)

    assert outcome == "fail"
    check_result = conn.execute(
        "SELECT * FROM check_result WHERE stage_run_id IN "
        "(SELECT id FROM stage_run WHERE ticket_id = ? AND stage = 'S0') AND check_name = 'intake_fields'",
        (ticket_id,),
    ).fetchone()
    assert check_result is not None
    assert check_result["result"] == "fail"
    assert check_result["summary"] == "missing owner"
    ticket = record.get(conn, "ticket", ticket_id)
    assert ticket["state"] == "rejected"
    assert ticket["close_reason"] == "rejected_at_s0"
