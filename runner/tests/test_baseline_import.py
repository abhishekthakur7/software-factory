"""Baseline cohorts are read through the real importer over injectable transports."""
import json
import runpy
import sqlite3
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
import yaml

from runner import baseline, governance, record, schema
from runner.db import connect
from runner.paths import FACTORY_DIR
from runner.readers.atlassian import AtlassianReader
from runner.readers.github import HttpTransport as GitHubHttpTransport
from runner.tests.fakes.atlassian_transport import FakeAtlassianTransport
from runner.tests.fakes.github_transport import FakeGitHubTransport

FAR_FUTURE = "2999-01-01T00:00:00+00:00"
BASELINE_IMPORT_SCRIPT = FACTORY_DIR / "scripts" / "tools" / "baseline_import"


@pytest.fixture
def conn(tmp_path):
    value = connect(tmp_path / "factory.sqlite")
    yield value
    value.close()


def _profile(tmp_path, conn):
    source = Path("factory/config/trust-profile.yaml")
    profile_path = tmp_path / "trust-profile.yaml"
    doc = yaml.safe_load(source.read_text())
    doc["routes"]["baseline_read"]["fields"] = [
        "id", "title", "status", "completed_at", "ticket_type", "service", "source_locator", "history", "pull_request_history", "agent_assisted",
    ]
    profile_path.write_text(yaml.safe_dump(doc, sort_keys=False))
    owners_path = Path("factory/config/owners.yaml")
    proposal = governance.propose(profile_path, owners_path)
    for role in ("security_approver", "legal_data_governance_approver"):
        governance.decide(conn, proposal, actor_identity="abhishek", role=role, decision="approve", expires_at=FAR_FUTURE,
                          attestation_version="v1", attestation_hash=role, profile_path=profile_path, owners_path=owners_path)
    conn.commit()
    return profile_path, owners_path


def _ticket(key, completed_at="2026-01-02T00:00:00+00:00"):
    return {"id": key, "title": f"{key} title", "status": "Done", "completed_at": completed_at, "ticket_type": "small_feature",
            "service": "fixture-project", "source_locator": f"jira:{key}", "agent_assisted": True}


def _pr_locator(key):
    return f"https://github.example/owner/repo/pull/{key.split('-')[-1].lstrip('0') or '1'}"


def _empty_readers():
    return AtlassianReader(FakeAtlassianTransport({}, completed=[])), __import__("runner.readers.github", fromlist=["GitHubReader"]).GitHubReader(FakeGitHubTransport(history_by_ref={}))


def test_must_reject_a_supplemental_file_or_cutoff_supplied_without_the_other(tmp_path):
    supplemental = tmp_path / "supplemental.json"
    supplemental.write_text("[]")
    result = subprocess.run(
        [str(BASELINE_IMPORT_SCRIPT), "--db", str(tmp_path / "factory.sqlite"), "--service", "fixture-project",
         "--cutoff", "2026-02-01T00:00:00+00:00", "--repository", "owner/repo", "--supplemental", str(supplemental)],
        capture_output=True, text=True,
    )
    assert result.returncode == 2
    assert "must be supplied together" in result.stderr


def test_must_reject_a_malformed_supplemental_json_input_before_reading_a_live_endpoint(tmp_path):
    supplemental = tmp_path / "supplemental.json"
    supplemental.write_text("[")
    result = subprocess.run(
        [str(BASELINE_IMPORT_SCRIPT), "--db", str(tmp_path / "factory.sqlite"), "--service", "fixture-project",
         "--cutoff", "2026-02-01T00:00:00+00:00", "--repository", "owner/repo", "--supplemental", str(supplemental),
         "--supplemental-cutoff", "2026-02-01T00:00:00+00:00"],
        capture_output=True, text=True,
    )
    assert result.returncode == 2
    assert "cannot read --supplemental JSON" in result.stderr


def test_import_writes_observed_and_approximate_rows_then_freezes_the_selection(conn, tmp_path):
    profile_path, owners_path = _profile(tmp_path, conn)
    atlassian = AtlassianReader(FakeAtlassianTransport({}, completed=[_ticket("FIX-2"), _ticket("FIX-1", "2026-01-01T00:00:00+00:00")], histories={
        "FIX-2": {"decisions": [{"kind": "approved_plan", "at": "2025-12-01T00:00:00+00:00"}], "questions": 2, "latency_minutes": 5, "attention_minutes": 3, "source_locator": "jira:FIX-2", "pull_request_locator": _pr_locator("FIX-2")},
        "FIX-1": {"decisions": [], "questions": 1, "latency_minutes": 2, "attention_minutes": 1, "source_locator": "jira:FIX-1", "pull_request_locator": _pr_locator("FIX-1")},
    }))
    github = __import__("runner.readers.github", fromlist=["GitHubReader"]).GitHubReader(FakeGitHubTransport(history_by_ref={
        _pr_locator("FIX-2"): [{"kind": "revision", "at": "2025-12-02T00:00:00+00:00"}], _pr_locator("FIX-1"): [{"kind": "revision", "at": "2025-12-02T00:00:00+00:00"}],
    }))

    cohort_id = baseline.import_baseline(conn, atlassian=atlassian, github=github, service="fixture-project", admitted_types={"small_feature"},
                                         retrospective_cutoff="2026-02-01T00:00:00+00:00", repository="owner/repo", runs_dir=tmp_path,
                                         profile_path=profile_path, owners_path=owners_path)

    cohort = record.get(conn, "artefact", cohort_id)
    assert cohort["utility_run_id"] is not None and cohort["frozen_at"] is None
    assert conn.execute("SELECT COUNT(*) FROM ticket WHERE baseline = 1").fetchone()[0] == 2
    rows = conn.execute("SELECT measure, status, value FROM baseline_measure ORDER BY ticket_id, measure").fetchall()
    assert any(row["measure"] == baseline.POST_PLAN_REVISIONS and row["status"] == "observed" and row["value"] == 1 for row in rows)
    assert any(row["measure"] == baseline.POST_PLAN_REVISIONS and row["status"] == "unavailable" for row in rows)
    source_backed = {"questions_per_ticket", "latency_minutes", "attention_minutes"}
    assert all(row["status"] == "approximate" for row in rows if row["measure"] in source_backed)
    assert {row["measure"] for row in rows} == set(baseline.REQUESTED_MEASURES)
    assert all(row["status"] == "unavailable" for row in rows if row["measure"] not in {*source_backed, baseline.POST_PLAN_REVISIONS})
    record.update(conn, "artefact", cohort_id, frozen_at=record.now())
    with pytest.raises(baseline.FrozenCohortError):
        baseline.add_ticket(conn, cohort_id, _ticket("LATE-1"))


def test_must_reject_secret_source_before_a_baseline_row_is_written(conn, tmp_path):
    profile_path, owners_path = _profile(tmp_path, conn)
    secret = {**_ticket("FIX-SECRET"), "history": "token=ghp_abcdefghijklmnopqrstuvwxyz0123456789"}
    atlassian = AtlassianReader(FakeAtlassianTransport({}, completed=[secret], histories={"FIX-SECRET": {}}))
    github = __import__("runner.readers.github", fromlist=["GitHubReader"]).GitHubReader(FakeGitHubTransport(history_by_ref={}))

    with pytest.raises(baseline.BaselineImportRefused, match="secret"):
        baseline.import_baseline(conn, atlassian=atlassian, github=github, service="fixture-project", admitted_types={"small_feature"},
                                 retrospective_cutoff="2026-02-01T00:00:00+00:00", repository="owner/repo", runs_dir=tmp_path,
                                 profile_path=profile_path, owners_path=owners_path)
    assert conn.execute("SELECT COUNT(*) FROM ticket WHERE baseline = 1").fetchone()[0] == 0


def test_must_reject_unpermitted_source_fields_before_rows_are_written(conn, tmp_path):
    profile_path, owners_path = _profile(tmp_path, conn)
    atlassian = AtlassianReader(FakeAtlassianTransport({}, completed=[{**_ticket("FIX-EXTRA"), "description": "outside baseline contract"}]))
    github = __import__("runner.readers.github", fromlist=["GitHubReader"]).GitHubReader(FakeGitHubTransport(history_by_ref={}))
    with pytest.raises(baseline.BaselineImportRefused, match="unpermitted"):
        baseline.import_baseline(conn, atlassian=atlassian, github=github, service="fixture-project", admitted_types={"small_feature"},
                                 retrospective_cutoff="2026-02-01T00:00:00+00:00", repository="owner/repo", runs_dir=tmp_path,
                                 profile_path=profile_path, owners_path=owners_path)
    assert conn.execute("SELECT COUNT(*) FROM baseline_measure").fetchone()[0] == 0


def test_must_reject_a_baseline_read_attempted_on_another_route(conn, tmp_path):
    profile_path, owners_path = _profile(tmp_path, conn)
    with pytest.raises(baseline.BaselineImportRefused, match="baseline_read"):
        baseline.guard_baseline_payload(conn, _ticket("FIX-1"), source="atlassian", route_id="atlassian_read",
                                        profile_path=profile_path, owners_path=owners_path)


def test_ten_comparable_observations_freeze_the_combined_cohort(conn, tmp_path):
    profile_path, owners_path = _profile(tmp_path, conn)
    tickets = [_ticket(f"FIX-{number:02}", f"2026-01-{number:02}T00:00:00+00:00") for number in range(1, 11)]
    histories = {ticket["id"]: {"decisions": [{"kind": "design_decision", "at": "2025-12-01T00:00:00+00:00"}],
                                "source_locator": f"jira:{ticket['id']}", "pull_request_locator": _pr_locator(ticket['id'])} for ticket in tickets}
    atlassian = AtlassianReader(FakeAtlassianTransport({}, completed=tickets, histories=histories))
    events = {_pr_locator(ticket["id"]): [{"kind": "revision", "at": "2025-12-02T00:00:00+00:00"}] for ticket in tickets}
    github = __import__("runner.readers.github", fromlist=["GitHubReader"]).GitHubReader(FakeGitHubTransport(history_by_ref=events))

    cohort_id = baseline.import_baseline(conn, atlassian=atlassian, github=github, service="fixture-project", admitted_types={"small_feature"},
                                         retrospective_cutoff="2026-02-01T00:00:00+00:00", repository="owner/repo", runs_dir=tmp_path,
                                         profile_path=profile_path, owners_path=owners_path)

    assert record.get(conn, "artefact", cohort_id)["frozen_at"] is not None


def test_must_reject_a_new_import_after_a_frozen_cohort_exists(conn, tmp_path):
    profile_path, owners_path = _profile(tmp_path, conn)
    tickets = [_ticket(f"FIX-{number:02}", f"2026-01-{number:02}T00:00:00+00:00") for number in range(1, 11)]
    histories = {ticket["id"]: {"decisions": [{"kind": "approved_plan", "at": "2025-12-01T00:00:00+00:00"}], "source_locator": f"jira:{ticket['id']}", "pull_request_locator": _pr_locator(ticket["id"])} for ticket in tickets}
    events = {_pr_locator(ticket["id"]): [{"kind": "revision", "at": "2025-12-02T00:00:00+00:00"}] for ticket in tickets}
    baseline.import_baseline(conn, atlassian=AtlassianReader(FakeAtlassianTransport({}, completed=tickets, histories=histories)), github=__import__("runner.readers.github", fromlist=["GitHubReader"]).GitHubReader(FakeGitHubTransport(history_by_ref=events)), service="fixture-project", admitted_types={"small_feature"}, retrospective_cutoff="2026-02-01T00:00:00+00:00", repository="owner/repo", runs_dir=tmp_path, profile_path=profile_path, owners_path=owners_path)
    atlassian, github = _empty_readers()
    with pytest.raises(baseline.BaselineImportRefused, match="frozen baseline cohort"):
        baseline.import_baseline(conn, atlassian=atlassian, github=github, service="fixture-project", admitted_types={"small_feature"}, retrospective_cutoff="2026-02-01T00:00:00+00:00", repository="owner/repo", runs_dir=tmp_path, profile_path=profile_path, owners_path=owners_path)
    assert conn.execute("SELECT COUNT(*) FROM artefact WHERE kind = 'baseline_selection'").fetchone()[0] == 1


def test_must_reject_an_import_after_a_real_factory_result_exists(conn, tmp_path):
    profile_path, owners_path = _profile(tmp_path, conn)
    record.insert(conn, "ticket", baseline=0, state="merged", factory_completed_at=record.now())
    atlassian, github = _empty_readers()
    with pytest.raises(baseline.BaselineImportRefused, match="factory result"):
        baseline.import_baseline(conn, atlassian=atlassian, github=github, service="fixture-project", admitted_types={"small_feature"}, retrospective_cutoff="2026-02-01T00:00:00+00:00", repository="owner/repo", runs_dir=tmp_path, profile_path=profile_path, owners_path=owners_path)
    assert conn.execute("SELECT COUNT(*) FROM artefact WHERE kind = 'baseline_selection'").fetchone()[0] == 0


def test_must_reject_reimport_of_an_open_cohort_and_direct_writes_after_a_real_result(conn, tmp_path):
    profile_path, owners_path = _profile(tmp_path, conn)
    ticket = _ticket("FIX-OPEN")
    atlassian = AtlassianReader(FakeAtlassianTransport({}, completed=[ticket], histories={"FIX-OPEN": {"decisions": [], "source_locator": "jira:FIX-OPEN"}}))
    github = __import__("runner.readers.github", fromlist=["GitHubReader"]).GitHubReader(FakeGitHubTransport(history_by_ref={}))
    cohort_id = baseline.import_baseline(conn, atlassian=atlassian, github=github, service="fixture-project", admitted_types={"small_feature"}, retrospective_cutoff="2026-02-01T00:00:00+00:00", repository="owner/repo", runs_dir=tmp_path, profile_path=profile_path, owners_path=owners_path)
    with pytest.raises(baseline.BaselineImportRefused, match="open baseline cohort"):
        baseline.import_baseline(conn, atlassian=atlassian, github=github, service="fixture-project", admitted_types={"small_feature"}, retrospective_cutoff="2026-02-01T00:00:00+00:00", repository="owner/repo", runs_dir=tmp_path, profile_path=profile_path, owners_path=owners_path)
    record.insert(conn, "ticket", baseline=0, state="merged", factory_completed_at=record.now())
    baseline_ticket_id = conn.execute("SELECT id FROM ticket WHERE baseline_cohort_id = ?", (cohort_id,)).fetchone()[0]
    with pytest.raises(baseline.BaselineImportRefused, match="factory result"):
        baseline.add_ticket(conn, cohort_id, _ticket("LATE"))
    with pytest.raises(baseline.BaselineImportRefused, match="factory result"):
        baseline.add_measure(conn, cohort_id, baseline_ticket_id, measure_name="late", definition_hash="definition", ticket=ticket, result={"value": None, "status": "unavailable", "unavailable_reason": "late"})


def test_import_persists_a_row_for_every_report_measure_view(conn, tmp_path):
    profile_path, owners_path = _profile(tmp_path, conn)
    ticket = _ticket("FIX-REPORT")
    atlassian = AtlassianReader(FakeAtlassianTransport({}, completed=[ticket], histories={"FIX-REPORT": {"decisions": [], "source_locator": "jira:FIX-REPORT"}}))
    github = __import__("runner.readers.github", fromlist=["GitHubReader"]).GitHubReader(FakeGitHubTransport(history_by_ref={}))
    cohort_id = baseline.import_baseline(conn, atlassian=atlassian, github=github, service="fixture-project", admitted_types={"small_feature"}, retrospective_cutoff="2026-02-01T00:00:00+00:00", repository="owner/repo", runs_dir=tmp_path, profile_path=profile_path, owners_path=owners_path)
    report = runpy.run_path(str(FACTORY_DIR / "scripts" / "tools" / "report"))
    mapping = report["baseline_measures"]()
    assert set(mapping) == {view for _title, view, _columns in (*report["primary_measures"](), *report["context_measures"]())}
    expected = set(mapping.values())
    actual = {row[0] for row in conn.execute("SELECT DISTINCT measure FROM baseline_measure WHERE baseline_cohort_id = ?", (cohort_id,))}
    assert actual == expected


def test_selection_keeps_ten_newest_completed_agent_assisted_tickets_and_exclusions(conn, tmp_path):
    """Selection records its cutoff, query, immutable locators, and every exclusion."""
    profile_path, owners_path = _profile(tmp_path, conn)
    tickets = [_ticket(f"FIX-{number:02}", f"2026-01-{number:02}T00:00:00+00:00") for number in range(1, 12)]
    tickets += [{**_ticket("FIX-MANUAL"), "agent_assisted": False}, {**_ticket("FIX-OPEN"), "status": "Open"}]
    histories = {ticket["id"]: {"decisions": [], "source_locator": f"jira:{ticket['id']}"} for ticket in tickets}
    atlassian = AtlassianReader(FakeAtlassianTransport({}, completed=tickets, histories=histories))
    github = __import__("runner.readers.github", fromlist=["GitHubReader"]).GitHubReader(FakeGitHubTransport(history_by_ref={}))
    cohort_id = baseline.import_baseline(conn, atlassian=atlassian, github=github, service="fixture-project", admitted_types={"small_feature"},
                                         retrospective_cutoff="2026-02-01T00:00:00+00:00", repository="owner/repo", runs_dir=tmp_path,
                                         profile_path=profile_path, owners_path=owners_path)
    selection = json.loads(Path(record.get(conn, "artefact", cohort_id)["path"]).read_text())
    assert selection["query"] == {"completed": True, "agent_assisted": True, "admitted_types": ["small_feature"]}
    assert len(selection["included"]) == 10
    assert selection["included"][0]["id"] == "FIX-11"
    assert {"FIX-01", "FIX-MANUAL", "FIX-OPEN"} <= set(selection["excluded"])


def test_supplemental_cohort_requires_same_endpoint_and_reuses_measure_definitions(conn, tmp_path):
    """A short retrospective adds a separately-cut-off, endpoint-equivalent supplemental cohort."""
    profile_path, owners_path = _profile(tmp_path, conn)
    retrospective = [_ticket(f"RET-{number}") for number in range(2)]
    supplemental = [_ticket(f"SUP-{number}", "2026-01-15T00:00:00+00:00") for number in range(8)]
    histories = {ticket["id"]: {"decisions": [{"kind": "approved_plan", "at": "2025-12-01T00:00:00+00:00"}],
                                "source_locator": f"jira:{ticket['id']}", "pull_request_locator": _pr_locator(ticket['id'])}
                 for ticket in [*retrospective, *supplemental]}
    events = {_pr_locator(ticket_id): [{"kind": "revision", "at": "2025-12-02T00:00:00+00:00"}] for ticket_id in histories}
    atlassian = AtlassianReader(FakeAtlassianTransport({}, completed=retrospective, histories=histories))
    github = __import__("runner.readers.github", fromlist=["GitHubReader"]).GitHubReader(FakeGitHubTransport(history_by_ref=events))
    cohort_id = baseline.import_baseline(conn, atlassian=atlassian, github=github, service="fixture-project", admitted_types={"small_feature"},
                                         retrospective_cutoff="2026-02-01T00:00:00+00:00", supplemental=supplemental,
                                         supplemental_cutoff="2026-02-01T00:00:00+00:00", repository="owner/repo", runs_dir=tmp_path,
                                         profile_path=profile_path, owners_path=owners_path)
    rows = conn.execute("SELECT measure_definition_hash FROM baseline_measure WHERE baseline_cohort_id = ? AND measure = ?", (cohort_id, schema.BASELINE_REVISIONS_MEASURE)).fetchall()
    assert len(rows) == 10 and len({row["measure_definition_hash"] for row in rows}) == 1
    assert record.get(conn, "artefact", cohort_id)["frozen_at"] is not None


def test_must_reject_supplemental_endpoint_mismatch_before_it_can_freeze(conn, tmp_path):
    profile_path, owners_path = _profile(tmp_path, conn)
    atlassian = AtlassianReader(FakeAtlassianTransport({}, completed=[]))
    github = __import__("runner.readers.github", fromlist=["GitHubReader"]).GitHubReader(FakeGitHubTransport(history_by_ref={}))
    with pytest.raises(baseline.BaselineImportRefused, match="endpoint"):
        baseline.import_baseline(conn, atlassian=atlassian, github=github, service="fixture-project", admitted_types={"small_feature"},
                                 retrospective_cutoff="2026-02-01T00:00:00+00:00", supplemental=[{**_ticket("SUP-BAD"), "service": "other"}],
                                 supplemental_cutoff="2026-02-01T00:00:00+00:00", repository="owner/repo", runs_dir=tmp_path,
                                 profile_path=profile_path, owners_path=owners_path)


def test_must_reject_secret_supplemental_before_selection_file_or_rows_exist(conn, tmp_path):
    profile_path, owners_path = _profile(tmp_path, conn)
    atlassian = AtlassianReader(FakeAtlassianTransport({}, completed=[]))
    github = __import__("runner.readers.github", fromlist=["GitHubReader"]).GitHubReader(FakeGitHubTransport(history_by_ref={}))
    with pytest.raises(baseline.BaselineImportRefused, match="secret"):
        baseline.import_baseline(conn, atlassian=atlassian, github=github, service="fixture-project", admitted_types={"small_feature"},
                                 retrospective_cutoff="2026-02-01T00:00:00+00:00", supplemental=[{**_ticket("SUP-SECRET"), "source_locator": "ghp_abcdefghijklmnopqrstuvwxyz0123456789"}],
                                 supplemental_cutoff="2026-02-01T00:00:00+00:00", repository="owner/repo", runs_dir=tmp_path,
                                 profile_path=profile_path, owners_path=owners_path)
    assert not list((tmp_path / "baseline").rglob("selection.json"))
    assert conn.execute("SELECT COUNT(*) FROM ticket WHERE baseline = 1").fetchone()[0] == 0


def test_must_reject_duplicate_supplemental_ids_before_creating_a_selection(conn, tmp_path):
    """Supplemental evidence cannot include one ticket twice, even under separate source objects."""
    profile_path, owners_path = _profile(tmp_path, conn)
    atlassian = AtlassianReader(FakeAtlassianTransport({}, completed=[]))
    github = __import__("runner.readers.github", fromlist=["GitHubReader"]).GitHubReader(FakeGitHubTransport(history_by_ref={}))

    with pytest.raises(baseline.BaselineImportRefused, match="duplicate"):
        baseline.import_baseline(conn, atlassian=atlassian, github=github, service="fixture-project", admitted_types={"small_feature"},
                                 retrospective_cutoff="2026-02-01T00:00:00+00:00", supplemental=[_ticket("SUP-1"), _ticket("SUP-1")],
                                 supplemental_cutoff="2026-02-01T00:00:00+00:00", repository="owner/repo", runs_dir=tmp_path,
                                 profile_path=profile_path, owners_path=owners_path)

    assert not list((tmp_path / "baseline").rglob("selection.json"))
    assert conn.execute("SELECT COUNT(*) FROM artefact WHERE kind = 'baseline_selection'").fetchone()[0] == 0


def test_timezone_aware_candidate_cutoff_uses_the_actual_instant(conn, tmp_path):
    """A candidate before the UTC cutoff remains eligible when its local offset sorts differently as text."""
    profile_path, owners_path = _profile(tmp_path, conn)
    ticket = _ticket("FIX-OFFSET", "2026-02-01T00:30:00+01:00")
    atlassian = AtlassianReader(FakeAtlassianTransport({}, completed=[ticket], histories={"FIX-OFFSET": {"decisions": [], "source_locator": "jira:FIX-OFFSET"}}))
    github = __import__("runner.readers.github", fromlist=["GitHubReader"]).GitHubReader(FakeGitHubTransport(history_by_ref={}))

    cohort_id = baseline.import_baseline(conn, atlassian=atlassian, github=github, service="fixture-project", admitted_types={"small_feature"},
                                         retrospective_cutoff="2026-02-01T00:00:00+00:00", repository="owner/repo", runs_dir=tmp_path,
                                         profile_path=profile_path, owners_path=owners_path)

    selection = json.loads(Path(record.get(conn, "artefact", cohort_id)["path"]).read_text())
    assert selection["included"] == [{"id": "FIX-OFFSET", "source_locator": "jira:FIX-OFFSET"}]


def test_timezone_aware_supplemental_cutoff_uses_the_actual_instant(conn, tmp_path):
    """Supplemental eligibility compares timestamps after offset normalization."""
    profile_path, owners_path = _profile(tmp_path, conn)
    retrospective = _ticket("RET-1")
    supplemental = _ticket("SUP-OFFSET", "2026-02-01T00:30:00+01:00")
    atlassian = AtlassianReader(FakeAtlassianTransport({}, completed=[retrospective], histories={
        "RET-1": {"decisions": [], "source_locator": "jira:RET-1"},
        "SUP-OFFSET": {"decisions": [], "source_locator": "jira:SUP-OFFSET"},
    }))
    github = __import__("runner.readers.github", fromlist=["GitHubReader"]).GitHubReader(FakeGitHubTransport(history_by_ref={}))

    cohort_id = baseline.import_baseline(conn, atlassian=atlassian, github=github, service="fixture-project", admitted_types={"small_feature"},
                                         retrospective_cutoff="2026-02-01T00:00:00+00:00", supplemental=[supplemental],
                                         supplemental_cutoff="2026-02-01T00:00:00+00:00", repository="owner/repo", runs_dir=tmp_path,
                                         profile_path=profile_path, owners_path=owners_path)

    selection = json.loads(Path(record.get(conn, "artefact", cohort_id)["path"]).read_text())
    assert selection["supplemental_included"] == [{"id": "SUP-OFFSET", "source_locator": "jira:SUP-OFFSET"}]


def test_partial_cohort_write_rolls_back_rows_and_selection_but_preserves_a_refused_audit(conn, tmp_path, monkeypatch):
    """A persistence fault cannot leave a partial cohort or orphan selection output behind."""
    profile_path, owners_path = _profile(tmp_path, conn)
    approvals_before = conn.execute("SELECT COUNT(*) FROM approval_record").fetchone()[0]
    tickets = [_ticket("FIX-1"), _ticket("FIX-2")]
    atlassian = AtlassianReader(FakeAtlassianTransport({}, completed=tickets, histories={
        ticket["id"]: {"decisions": [], "source_locator": f"jira:{ticket['id']}"} for ticket in tickets
    }))
    github = __import__("runner.readers.github", fromlist=["GitHubReader"]).GitHubReader(FakeGitHubTransport(history_by_ref={}))
    original_add_measure = baseline.add_measure
    calls = 0

    def fail_after_first_measure(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise sqlite3.OperationalError("injected baseline measure write failure")
        return original_add_measure(*args, **kwargs)

    monkeypatch.setattr(baseline, "add_measure", fail_after_first_measure)
    with pytest.raises(sqlite3.OperationalError, match="injected"):
        baseline.import_baseline(conn, atlassian=atlassian, github=github, service="fixture-project", admitted_types={"small_feature"},
                                 retrospective_cutoff="2026-02-01T00:00:00+00:00", repository="owner/repo", runs_dir=tmp_path,
                                 profile_path=profile_path, owners_path=owners_path)

    assert conn.execute("SELECT COUNT(*) FROM artefact WHERE kind = 'baseline_selection'").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM ticket WHERE baseline = 1").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM baseline_measure").fetchone()[0] == 0
    assert not list((tmp_path / "baseline").rglob("selection.json"))
    assert conn.execute("SELECT outcome FROM utility_run WHERE kind = 'baseline_import' ORDER BY id DESC LIMIT 1").fetchone()[0] == "refused"
    assert conn.execute("SELECT COUNT(*) FROM approval_record").fetchone()[0] == approvals_before


def test_committed_profile_admits_the_normalized_reader_contract(conn, tmp_path):
    """Committed baseline fields match the reader's normalized evidence without test-only widening."""
    proposal = governance.propose()
    for role in ("security_approver", "legal_data_governance_approver"):
        governance.decide(conn, proposal, actor_identity="abhishek", role=role, decision="approve", expires_at=FAR_FUTURE, attestation_version="v1", attestation_hash=role)
    ticket = {"ticket_id": "FIX-1", "title": "normal", "status": "Done", "completed_at": "2026-01-01T00:00:00+00:00", "issue_type": "Story", "ticket_type": "small_feature", "service": "fixture-project", "agent_assisted": True, "source_locator": "jira:FIX-1"}
    passed = baseline.guard_baseline_payload(conn, ticket, source="atlassian")
    assert passed == ticket


def test_must_reject_raw_ticket_and_measure_inserts_after_a_cohort_freezes(conn, tmp_path):
    """The database trigger protects frozen cohorts even when callers skip helpers."""
    profile_path, owners_path = _profile(tmp_path, conn)
    tickets = [_ticket(f"FIX-{number:02}", f"2026-01-{number:02}T00:00:00+00:00") for number in range(1, 11)]
    histories = {ticket["id"]: {"decisions": [{"kind": "approved_plan", "at": "2025-12-01T00:00:00+00:00"}], "source_locator": "jira", "pull_request_locator": _pr_locator(ticket['id'])} for ticket in tickets}
    atlassian = AtlassianReader(FakeAtlassianTransport({}, completed=tickets, histories=histories))
    github = __import__("runner.readers.github", fromlist=["GitHubReader"]).GitHubReader(FakeGitHubTransport(history_by_ref={_pr_locator(ticket["id"]): [{"kind": "revision", "at": "2025-12-02T00:00:00+00:00"}] for ticket in tickets}))
    cohort_id = baseline.import_baseline(conn, atlassian=atlassian, github=github, service="fixture-project", admitted_types={"small_feature"}, retrospective_cutoff="2026-02-01T00:00:00+00:00", repository="owner/repo", runs_dir=tmp_path, profile_path=profile_path, owners_path=owners_path)
    record.insert(conn, "ticket", title="real factory result", baseline=0, state="merged", factory_completed_at=record.now())
    with pytest.raises(sqlite3.IntegrityError, match="frozen"):
        record.insert(conn, "ticket", baseline=1, baseline_cohort_id=cohort_id, title="late")
    with pytest.raises(sqlite3.IntegrityError, match="frozen"):
        record.insert(conn, "baseline_measure", baseline_cohort_id=cohort_id, measure="late")


def test_real_github_transport_uses_a_numeric_pull_request_locator_not_a_jira_key():
    """The real REST seam resolves only a GitHub PR locator before fetching history."""
    seen = []
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            seen.append(self.path)
            self.send_response(200); self.end_headers(); self.wfile.write(b'[{"kind":"revision"}]')
        def log_message(self, *_args):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        transport = GitHubHttpTransport(base_url=f"http://127.0.0.1:{server.server_port}", fetch=lambda _role: "secret")
        assert transport("read_pull_request_history", {"repository": "owner/repo", "pull_request_locator": "https://github.example/owner/repo/pull/42"}) == [{"kind": "revision"}]
        assert seen == ["/repos/owner/repo/issues/42/timeline"]
        with pytest.raises(ValueError, match="numeric"):
            transport("read_pull_request_history", {"repository": "owner/repo", "pull_request_locator": "FIX-42"})
    finally:
        server.shutdown(); thread.join()


def test_must_mark_malformed_or_non_attributable_revision_history_unavailable():
    """Malformed timestamps and unclassified remote events never become observed zero."""
    history = {"decisions": [{"kind": "approved_plan", "at": "2026-01-01T00:00:00+00:00"}], "source_locator": "jira:FIX-1", "pull_request_locator": _pr_locator("FIX-1")}
    result = baseline.measures(history, [{"kind": "opened", "at": "not-a-time"}])
    assert result[baseline.POST_PLAN_REVISIONS] == {"value": None, "status": "unavailable", "unavailable_reason": "pull-request history is malformed or not attributable"}
