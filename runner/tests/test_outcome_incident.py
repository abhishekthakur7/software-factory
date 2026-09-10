"""Production incidents, their dispositions, `incident-policy.yaml`, and its two severity-deriving call sites."""
import pytest
import yaml

from runner import incident_policy, queue, record
from runner.paths import FACTORY_DIR
from runner.stages import implementation
from runner.tests.test_outcome_revision import conn, ABHISHEK

POLICY_PATH = FACTORY_DIR / "config" / "incident-policy.yaml"
CONTROL_CATEGORIES = ("data_boundary", "execution_boundary", "approval_binding", "reviewer_enforcement", "audit_reconstruction")


def _seed_ticket(conn, **overrides) -> int:
    return record.insert(conn, "ticket", state="pr_opened", opened_at=record.now(), **overrides)


def test_incident_event_writes_the_row_and_its_required_incident_tag(conn):
    """One `production_incident_event` row and its human `incident` tag; the root is never superseded."""
    ticket_id = _seed_ticket(conn)
    queue.act(
        conn, ticket_id=ticket_id, action="incident_event", actor=ABHISHEK,
        fields={"severity": "sev2", "occurred_at": "2025-02-01T00:00:00+00:00", "fm_id": "question_noise", "note": "elevated error rate"},
    )
    event = conn.execute(
        "SELECT * FROM incident_observation WHERE ticket_id = ? AND record_kind = 'production_incident_event'", (ticket_id,)
    ).fetchone()
    assert event is not None
    assert event["severity"] == "sev2"
    assert event["supersedes"] is None
    tag_row = record.get(conn, "tag", event["tag_id"])
    assert tag_row["event_kind"] == "incident"
    assert tag_row["fm_id"] == "question_noise"
    assert tag_row["tagged_by"] == ABHISHEK


def test_disposition_supersedes_only_the_same_roots_earlier_disposition(conn):
    """`recorder_role` is `incident_reviewer`, and a disposition supersedes
    only an earlier `production_disposition` naming the same event root."""
    ticket_id = _seed_ticket(conn)
    for note in ("first incident", "second incident"):
        queue.act(
            conn, ticket_id=ticket_id, action="incident_event", actor=ABHISHEK,
            fields={"severity": "sev3", "occurred_at": "2025-02-01T00:00:00+00:00", "fm_id": "question_noise", "note": note},
        )
    events = conn.execute(
        "SELECT id FROM incident_observation WHERE ticket_id = ? AND record_kind = 'production_incident_event' ORDER BY id",
        (ticket_id,),
    ).fetchall()
    event_a, event_b = events[0]["id"], events[1]["id"]

    queue.act(
        conn, ticket_id=ticket_id, action="disposition", actor=ABHISHEK,
        fields={"event": str(event_a), "attribution": "undetermined", "disposition": "open"},
    )
    first_a = conn.execute(
        "SELECT id FROM incident_observation WHERE event_id = ? AND record_kind = 'production_disposition'", (event_a,)
    ).fetchone()
    queue.act(
        conn, ticket_id=ticket_id, action="disposition", actor=ABHISHEK,
        fields={"event": str(event_b), "attribution": "not_attributable", "disposition": "reviewed_no_change"},
    )
    disposition_b = conn.execute(
        "SELECT * FROM incident_observation WHERE event_id = ? AND record_kind = 'production_disposition'", (event_b,)
    ).fetchone()
    assert disposition_b["supersedes"] is None
    assert disposition_b["recorder_role"] == "incident_reviewer"

    queue.act(
        conn, ticket_id=ticket_id, action="disposition", actor=ABHISHEK,
        fields={
            "event": str(event_a), "attribution": "attributable", "disposition": "remediated",
            "remediation_ref": "catalogue:question_noise",
        },
    )
    second_a = conn.execute(
        "SELECT * FROM incident_observation WHERE event_id = ? AND record_kind = 'production_disposition' ORDER BY id DESC LIMIT 1",
        (event_a,),
    ).fetchone()
    assert second_a["supersedes"] == first_a["id"]


def test_must_reject_a_disposition_value_outside_the_policys_closed_set(conn):
    """A disposition the policy does not name is refused and writes no row."""
    ticket_id = _seed_ticket(conn)
    queue.act(
        conn, ticket_id=ticket_id, action="incident_event", actor=ABHISHEK,
        fields={"severity": "sev2", "occurred_at": "2025-02-01T00:00:00+00:00", "fm_id": "question_noise", "note": "elevated error rate"},
    )
    event_id = conn.execute(
        "SELECT id FROM incident_observation WHERE ticket_id = ? AND record_kind = 'production_incident_event'", (ticket_id,)
    ).fetchone()["id"]

    with pytest.raises(queue.ActionRefused):
        queue.act(
            conn, ticket_id=ticket_id, action="disposition", actor=ABHISHEK,
            fields={"event": str(event_id), "attribution": "attributable", "disposition": "not_applicable"},
        )

    assert conn.execute(
        "SELECT count(*) AS n FROM incident_observation WHERE record_kind = 'production_disposition'"
    ).fetchone()["n"] == 0


def test_incident_policy_yaml_declares_every_required_shape():
    policy = yaml.safe_load(POLICY_PATH.read_text())
    assert policy["severity_levels"] == ["sev1", "sev2", "sev3", "sev4"]
    assert set(policy["control_categories"]) == set(CONTROL_CATEGORIES)
    assert all(value == "sev2" for value in policy["control_categories"].values())
    assert policy["production_incident"]["severity_from"] == "severity_levels"
    assert set(policy["attribution_values"]) == {"attributable", "not_attributable", "undetermined"}
    assert set(policy["disposition_values"]) == {"open", "remediated", "reviewed_no_change"}
    assert set(policy["remediation_rule"]["remediated_requires_ref_prefixes"]) == {"catalogue:", "rubric:"}


def test_implementation_control_defect_event_reads_its_severity_from_the_incident_policy(conn):
    ticket_id = record.insert(conn, "ticket", state="implementing", opened_at=record.now())
    ticket = record.get(conn, "ticket", ticket_id)
    stage_run_id = record.insert(conn, "stage_run", ticket_id=ticket_id, stage="implementation", attempt=1)

    implementation._control_defect(conn, ticket, stage_run_id, failure_kind="sandbox_integrity")

    event = conn.execute(
        "SELECT * FROM incident_observation WHERE ticket_id = ? AND record_kind = 'control_defect_event'", (ticket_id,)
    ).fetchone()
    assert event["severity"] == incident_policy.severity_for("execution_boundary")


def test_control_event_with_no_severity_derives_it_from_the_policy_for_the_category(conn, tmp_path):
    ticket_id = record.insert(conn, "ticket", state="checks", opened_at=record.now())
    item_id = queue.open_item(conn, ticket_id=ticket_id, kind="red_check")

    queue.act(
        conn, item_id=item_id, action="control_event", actor=ABHISHEK,
        category="data_boundary", fm_id="data_boundary_breach", note="observed a boundary gap", runs_dir=tmp_path,
    )

    event = conn.execute(
        "SELECT * FROM incident_observation WHERE ticket_id = ? AND record_kind = 'control_defect_event'", (ticket_id,)
    ).fetchone()
    assert event["severity"] == incident_policy.severity_for("data_boundary")
