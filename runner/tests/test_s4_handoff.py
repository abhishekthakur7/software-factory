"""S4's hand-off assembly (R-S4-1): what `build_handoff` writes into `handoff.json`,
read only from the record and the plan's own tables, never the S3 transcript.
"""
import json
from pathlib import Path

import pytest
import yaml

from runner import artefact_registry, manifest, record, run_ledger, schema
from runner.db import connect
from runner.paths import FACTORY_DIR, PROJECT_CONFIG, REPO_ROOT
from runner.stages import S4, S5

FIXTURES = Path(__file__).parent / "fixtures" / "s4_handoff"
PLAN_TEXT = (FIXTURES / "plan.md").read_text()
CRITERIA_TEXT = (Path(__file__).parent / "fixtures" / "s3" / "criteria.md").read_text()

TIER = "standard"


def _conn(tmp_path):
    return connect(tmp_path / "factory.sqlite")


def _seed_ticket(conn, tmp_path, **fields) -> int:
    return record.insert(
        conn, "ticket", state="implementing", opened_at=record.now(),
        service="fixture-project", ticket_type="small_feature", tier_provisional=TIER,
        factory_manifest_hash=manifest.current_hash(), worktree_path=str(tmp_path / "worktree"),
        **fields,
    )


def _seed_plan_tuple(conn, ticket_id: int, **overrides) -> int:
    fields = {
        "plan_hash": "plan-hash-1", "criteria_hash": "criteria-hash-1",
        "current_assumption_set_hash": "assumption-set-hash-1",
        "semantic_checklist_hash": "checklist-hash-1",
        "base_sha": "deadbeef", "target_base_sha": "deadbeef",
        "content_hash": "plan-approval-subject-1",
    }
    fields.update(overrides)
    return record.insert(conn, "evidence_tuple", kind="plan", ticket_id=ticket_id, created_at=record.now(), **fields)


def _register_plan_and_criteria(conn, ticket_id: int, tmp_path) -> None:
    plan_path = tmp_path / "plan.md"
    plan_path.write_text(PLAN_TEXT)
    artefact_registry.register(conn, ticket_id=ticket_id, kind="plan", path=plan_path)
    criteria_path = tmp_path / "criteria.md"
    criteria_path.write_text(CRITERIA_TEXT)
    artefact_registry.register(conn, ticket_id=ticket_id, kind="criteria", path=criteria_path)


def _ready_ticket(conn, tmp_path, **ticket_fields) -> tuple[int, int]:
    """A ticket in `implementing` with a registered plan/criteria and a bound plan tuple; returns (ticket_id, plan_tuple_id)."""
    ticket_id = _seed_ticket(conn, tmp_path, **ticket_fields)
    plan_tuple_id = _seed_plan_tuple(conn, ticket_id)
    _register_plan_and_criteria(conn, ticket_id, tmp_path)
    return ticket_id, plan_tuple_id


def _build(conn, tmp_path, ticket_id) -> dict:
    ticket = record.get(conn, "ticket", ticket_id)
    stage_run_id = run_ledger.open_stage_run(conn, ticket_id=ticket_id, stage="S4")
    S4.build_handoff(conn, ticket, stage_run_id, runs_dir=tmp_path)
    handoff_artefact = artefact_registry.latest(conn, ticket_id, "handoff")
    return json.loads(Path(handoff_artefact["path"]).read_text())


# criterion 1: approved criteria and plan hashes


def test_handoff_carries_the_approved_criteria_and_plan_hashes(tmp_path):
    conn = _conn(tmp_path)
    ticket_id, _ = _ready_ticket(conn, tmp_path)
    payload = _build(conn, tmp_path, ticket_id)
    assert payload["plan_hash"] == "plan-hash-1"
    assert payload["criteria_hash"] == "criteria-hash-1"


# criterion 2: the plan tuple's id and the S3 plan-approval subject


def test_handoff_names_the_plan_tuple_id_that_carries_the_approval_subject(tmp_path):
    conn = _conn(tmp_path)
    ticket_id, plan_tuple_id = _ready_ticket(conn, tmp_path)
    payload = _build(conn, tmp_path, ticket_id)
    assert payload["plan_tuple_id"] == plan_tuple_id
    tuple_row = record.get(conn, "evidence_tuple", payload["plan_tuple_id"])
    assert tuple_row["content_hash"] == "plan-approval-subject-1"


# criterion 3: the current assumption-set hash and the plan's blind spots


def test_handoff_carries_the_assumption_set_hash_and_derived_blind_spots(tmp_path):
    conn = _conn(tmp_path)
    ticket_id, _ = _ready_ticket(conn, tmp_path)
    payload = _build(conn, tmp_path, ticket_id)
    assert payload["assumption_set_hash"] == "assumption-set-hash-1"

    readiness_spots = [s for s in payload["blind_spots"] if s["source"] == "readiness"]
    assert readiness_spots == [
        {"source": "readiness", "condition": "impact_evidence", "waiver_id": "W-1", "note": "one row's coverage is unknown"}
    ]
    contract_spots = [s for s in payload["blind_spots"] if s["source"] == "contract"]
    assert contract_spots == [
        {"source": "contract", "unit": "Widget.compute", "field": "compatibility", "note": "unknown: not yet decided"}
    ]


def test_a_plan_with_no_blind_spot_and_no_unknown_contract_field_reports_none(tmp_path):
    """Never a silent default: an absent blind spot is an empty list, not a missing key."""
    conn = _conn(tmp_path)
    clean_plan = PLAN_TEXT.replace("blind_spot", "pass").replace("W-1", "").replace(
        "unknown: not yet decided", "unchanged"
    )
    ticket_id = _seed_ticket(conn, tmp_path)
    _seed_plan_tuple(conn, ticket_id)
    plan_path = tmp_path / "plan.md"
    plan_path.write_text(clean_plan)
    artefact_registry.register(conn, ticket_id=ticket_id, kind="plan", path=plan_path)
    criteria_path = tmp_path / "criteria.md"
    criteria_path.write_text(CRITERIA_TEXT)
    artefact_registry.register(conn, ticket_id=ticket_id, kind="criteria", path=criteria_path)

    payload = _build(conn, tmp_path, ticket_id)
    assert payload["blind_spots"] == []


# criterion 4: tier and budget


def test_handoff_carries_the_tier_and_the_run_and_ticket_budgets(tmp_path):
    conn = _conn(tmp_path)
    ticket_id, _ = _ready_ticket(conn, tmp_path)
    payload = _build(conn, tmp_path, ticket_id)
    assert payload["tier"] == TIER
    assert payload["budget"]["run"] == run_ledger.budget("S4", TIER)
    assert payload["budget"]["ticket"] == run_ledger.s4_per_ticket_budget(TIER)


# criterion 5: required S5 check policies and recipe ids


def test_handoff_carries_the_s5_check_policies_and_the_project_recipe_ids(tmp_path):
    conn = _conn(tmp_path)
    ticket_id, _ = _ready_ticket(conn, tmp_path)
    payload = _build(conn, tmp_path, ticket_id)
    assert payload["check_policies"] == list(S5.CHECK_ORDER)
    project = yaml.safe_load(Path(PROJECT_CONFIG).read_text())
    assert payload["recipe_ids"] == project["recipes"]


# criterion 6: every task's allowed recipe ids and typed values


def test_handoff_carries_every_task_with_its_recipe_and_typed_validation_args(tmp_path):
    conn = _conn(tmp_path)
    ticket_id, _ = _ready_ticket(conn, tmp_path)
    payload = _build(conn, tmp_path, ticket_id)
    tasks = {task["id"]: task for task in payload["tasks"]}
    assert set(tasks) == {"T-1", "T-2"}
    assert tasks["T-1"]["validation_recipe"] == "fixture_compile"
    assert tasks["T-1"]["validation_args"] == {"target": "out/compile", "retries": 2}
    assert tasks["T-1"]["criteria"] == ["AC-1", "AC-2"]
    assert tasks["T-1"]["depends_on"] == []
    assert tasks["T-2"]["depends_on"] == ["T-1"]
    assert tasks["T-2"]["validation_args"] == {"strict": True}


# criterion 7: the bootstrap checklist hash and a reference to the deviation schema


def test_handoff_carries_the_bootstrap_checklist_hash_and_the_deviation_schema(tmp_path):
    conn = _conn(tmp_path)
    ticket_id, _ = _ready_ticket(conn, tmp_path)
    payload = _build(conn, tmp_path, ticket_id)
    assert payload["bootstrap_checklist_hash"] == "checklist-hash-1"
    assert payload["deviation_schema"] == [column.name for column in schema.table("deviation").columns]


# criterion 8: the loop note on a revision cycle, none on the first cycle


def test_a_first_cycle_handoff_carries_no_loop_note(tmp_path):
    conn = _conn(tmp_path)
    ticket_id, _ = _ready_ticket(conn, tmp_path)
    payload = _build(conn, tmp_path, ticket_id)
    assert payload["loop_note"] is None


def test_a_handoff_after_request_changes_carries_the_reviewers_revision_note(tmp_path):
    conn = _conn(tmp_path)
    ticket_id, _ = _ready_ticket(conn, tmp_path)
    record.insert(
        conn, "tag", ticket_id=ticket_id, event_kind="revision_after_approval", fm_id="FM-11",
        ref=f"ticket:{ticket_id}", note="tighten the null check before merge", tagged_by="abhishek",
        tagged_at=record.now(),
    )
    payload = _build(conn, tmp_path, ticket_id)
    assert payload["loop_note"] == "tighten the null check before merge"


def test_only_the_latest_of_several_revision_notes_is_carried(tmp_path):
    conn = _conn(tmp_path)
    ticket_id, _ = _ready_ticket(conn, tmp_path)
    for note in ("first round note", "second round note"):
        record.insert(
            conn, "tag", ticket_id=ticket_id, event_kind="revision_after_approval", fm_id="FM-11",
            ref=f"ticket:{ticket_id}", note=note, tagged_by="abhishek", tagged_at=record.now(),
        )
    payload = _build(conn, tmp_path, ticket_id)
    assert payload["loop_note"] == "second round note"


# criterion 9: no credential, no path outside runs_dir or the worktree


def test_handoff_carries_no_credential_and_no_path_outside_the_run_tree_or_worktree(tmp_path, monkeypatch):
    monkeypatch.setenv("CURSOR_API_KEY", "fake-super-secret-runtime-key")
    conn = _conn(tmp_path)
    ticket_id, _ = _ready_ticket(conn, tmp_path)
    ticket = record.get(conn, "ticket", ticket_id)
    stage_run_id = run_ledger.open_stage_run(conn, ticket_id=ticket_id, stage="S4")
    S4.build_handoff(conn, ticket, stage_run_id, runs_dir=tmp_path)
    handoff_artefact = artefact_registry.latest(conn, ticket_id, "handoff")
    text = Path(handoff_artefact["path"]).read_text()

    assert "fake-super-secret-runtime-key" not in text
    # No absolute repository path leaked in either: every path this
    # payload could name is a plan-table-relative path or a run-tree path,
    # never an on-disk location outside `runs_dir`/the worktree.
    assert str(REPO_ROOT) not in text
    assert str(FACTORY_DIR) not in text


# criterion 10: reconstruction from the handoff file alone, no database


def test_the_task_list_recipe_set_and_budget_reconstruct_from_the_handoff_file_alone(tmp_path):
    conn = _conn(tmp_path)
    ticket_id, _ = _ready_ticket(conn, tmp_path)
    payload = _build(conn, tmp_path, ticket_id)
    handoff_artefact = artefact_registry.latest(conn, ticket_id, "handoff")
    conn.close()

    # From here on: the handoff file's own bytes, `tiers.yaml` and
    # `project.yaml` (the "registered sandbox mounts") only -- no database,
    # no S3 stage_run transcript.
    reconstructed = json.loads(Path(handoff_artefact["path"]).read_text())
    project = yaml.safe_load(Path(PROJECT_CONFIG).read_text())
    tiers = yaml.safe_load((FACTORY_DIR / "config" / "tiers.yaml").read_text())

    assert {task["id"] for task in reconstructed["tasks"]} == {"T-1", "T-2"}
    assert set(reconstructed["recipe_ids"]) == set(project["recipes"])
    expected_budget = dict(tiers["budgets"]["by_tier"][reconstructed["tier"]])
    expected_budget.update(tiers["budgets"].get("overrides", {}).get("S4", {}))
    assert reconstructed["budget"]["run"] == expected_budget
    assert reconstructed["budget"]["ticket"] == dict(tiers["s4_per_ticket"][reconstructed["tier"]])


# run(): missing plan tuple / plan artefact is a structural failure, no invocation attempted


def test_run_on_a_ticket_with_no_plan_tuple_is_a_structural_failure(tmp_path):
    conn = _conn(tmp_path)
    ticket_id = _seed_ticket(conn, tmp_path)
    plan_path = tmp_path / "plan.md"
    plan_path.write_text(PLAN_TEXT)
    artefact_registry.register(conn, ticket_id=ticket_id, kind="plan", path=plan_path)
    ticket = record.get(conn, "ticket", ticket_id)
    stage_run_id = run_ledger.open_stage_run(conn, ticket_id=ticket_id, stage="S4")

    outcome = S4.run(conn, ticket, stage_run_id, runs_dir=tmp_path)
    assert outcome == ("fail", "structural")
    checks = conn.execute("SELECT * FROM check_result WHERE stage_run_id = ?", (stage_run_id,)).fetchall()
    assert any("plan tuple" in row["summary"] for row in checks)


def test_run_on_a_ticket_with_no_plan_artefact_is_a_structural_failure(tmp_path):
    conn = _conn(tmp_path)
    ticket_id = _seed_ticket(conn, tmp_path)
    _seed_plan_tuple(conn, ticket_id)
    ticket = record.get(conn, "ticket", ticket_id)
    stage_run_id = run_ledger.open_stage_run(conn, ticket_id=ticket_id, stage="S4")

    outcome = S4.run(conn, ticket, stage_run_id, runs_dir=tmp_path)
    assert outcome == ("fail", "structural")
    checks = conn.execute("SELECT * FROM check_result WHERE stage_run_id = ?", (stage_run_id,)).fetchall()
    assert any("plan artefact" in row["summary"] for row in checks)
