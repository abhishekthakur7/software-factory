"""The stub stage drivers, run for real, plus the conformance walk over
every stub agent/skill/rubric's own eval directory: every referenced file
has an eval directory with at least one accepted and one rejected fixture.

Every stub run here is given `tmp_path` as its runs root, so the artefact
each driver writes and registers lands there rather than under the real
repository's `runs/`, which no test touches.
"""
from pathlib import Path

import pytest
import yaml

from runner import artefact_registry, gates, record, transitions
from runner.db import connect
from runner.definitions import DefinitionError, load_definition
from runner.paths import FACTORY_DIR
from runner.stages import run_stage

EVAL_ROOTS = (FACTORY_DIR / "evals" / "agents", FACTORY_DIR / "evals" / "skills", FACTORY_DIR / "evals" / "rubrics")


@pytest.fixture
def conn(tmp_path):
    connection = connect(tmp_path / "factory.sqlite")
    yield connection
    connection.close()


def _ticket_in(conn, state, **fields):
    return record.insert(conn, "ticket", state=state, opened_at=record.now(), **fields)


def test_s0_stub_runs_and_the_eligibility_gate_moves_intake_to_context(conn, tmp_path):
    """the real S0 stub driver runs (writing and registering a
    `ticket_source` artefact), then a granted eligibility item moves the
    ticket on; S0 passing by itself is not enough."""
    ticket_id = _ticket_in(conn, "intake")
    outcome = run_stage(conn, ticket_id, "S0", runs_dir=tmp_path)
    assert outcome == "pass"
    assert record.get(conn, "ticket", ticket_id)["state"] == "intake"  # S0 alone doesn't move it
    artefact = artefact_registry.latest(conn, ticket_id, "ticket_source")
    assert artefact is not None

    record.insert(conn, "queue_item", ticket_id=ticket_id, kind="eligibility", action="granted")
    ticket = record.get(conn, "ticket", ticket_id)
    event = gates.intake_gate(conn, ticket)
    assert transitions.apply(conn, ticket_id, event) == "context"


def test_s1_stub_writes_a_brief_and_passes_to_clarifying(conn, tmp_path):
    """the real S1 stub driver writes and registers a `brief`
    artefact and its pass moves context -> clarifying."""
    ticket_id = _ticket_in(conn, "context")
    outcome = run_stage(conn, ticket_id, "S1", runs_dir=tmp_path)
    assert outcome == "pass"
    assert record.get(conn, "ticket", ticket_id)["state"] == "clarifying"
    assert artefact_registry.latest(conn, ticket_id, "brief") is not None


def test_s2_stub_writes_criteria_and_passes_to_planning(conn, tmp_path):
    """the real S2 stub driver writes and registers a
    `criteria` artefact and its pass moves clarifying -> planning."""
    ticket_id = _ticket_in(conn, "clarifying")
    outcome = run_stage(conn, ticket_id, "S2", runs_dir=tmp_path)
    assert outcome == "pass"
    assert record.get(conn, "ticket", ticket_id)["state"] == "planning"
    assert artefact_registry.latest(conn, ticket_id, "criteria") is not None


def test_s3_stub_writes_a_plan_and_passes_to_plan_review(conn, tmp_path):
    """the real S3 stub driver writes and registers a `plan`
    artefact and its pass moves planning -> plan_review."""
    ticket_id = _ticket_in(conn, "planning")
    outcome = run_stage(conn, ticket_id, "S3", runs_dir=tmp_path)
    assert outcome == "pass"
    assert record.get(conn, "ticket", ticket_id)["state"] == "plan_review"
    assert artefact_registry.latest(conn, ticket_id, "plan") is not None


def test_s4_stub_writes_a_handoff_and_passes_to_checks(conn, tmp_path):
    """the real S4 stub driver writes and registers a
    `handoff` artefact and its pass moves implementing -> checks."""
    ticket_id = _ticket_in(conn, "implementing")
    outcome = run_stage(conn, ticket_id, "S4", runs_dir=tmp_path)
    assert outcome == "pass"
    assert record.get(conn, "ticket", ticket_id)["state"] == "checks"
    assert artefact_registry.latest(conn, ticket_id, "handoff") is not None


def test_s5_and_s6_stubs_run_and_the_checks_gate_moves_checks_to_review(conn, tmp_path):
    """the real S5 and S6 stub drivers each run (writing
    `check_evidence` and `packet` artefacts) without leaving `checks` on
    their own; only once both have passed does the checks gate fire."""
    ticket_id = _ticket_in(conn, "checks")
    s5_outcome = run_stage(conn, ticket_id, "S5", runs_dir=tmp_path)
    assert s5_outcome == "pass"
    assert record.get(conn, "ticket", ticket_id)["state"] == "checks"
    assert artefact_registry.latest(conn, ticket_id, "check_evidence") is not None

    s6_outcome = run_stage(conn, ticket_id, "S6", runs_dir=tmp_path)
    assert s6_outcome == "pass"
    assert record.get(conn, "ticket", ticket_id)["state"] == "checks"  # still not moved
    assert artefact_registry.latest(conn, ticket_id, "packet") is not None

    ticket = record.get(conn, "ticket", ticket_id)
    event = gates.checks_gate(conn, ticket)
    assert transitions.apply(conn, ticket_id, event) == "review"


def test_a_second_stub_run_supersedes_the_first_artefact(conn, tmp_path):
    """running a stage twice for the same ticket chains `supersedes` to the
    prior version rather than losing it, so a superseded version stays
    readable."""
    ticket_id = _ticket_in(conn, "context")
    run_stage(conn, ticket_id, "S1", runs_dir=tmp_path)
    first = artefact_registry.latest(conn, ticket_id, "brief")

    record.update(conn, "ticket", ticket_id, state="context")  # rerun from the same state
    run_stage(conn, ticket_id, "S1", runs_dir=tmp_path)
    second = artefact_registry.latest(conn, ticket_id, "brief")

    assert second["id"] != first["id"]
    assert second["supersedes"] == first["id"]
    assert second["version"] == first["version"] + 1


# --- every stub's own eval directory has an ok and a reject fixture ---


def _eval_directories():
    for root in EVAL_ROOTS:
        for eval_dir in sorted(root.iterdir()):
            if (eval_dir / "eval.yaml").is_file():
                yield eval_dir


EVAL_DIRS = list(_eval_directories())


@pytest.mark.parametrize("eval_dir", EVAL_DIRS, ids=[str(d.relative_to(FACTORY_DIR)) for d in EVAL_DIRS])
def test_stub_definition_eval_directory_has_an_ok_and_a_reject_fixture(eval_dir):
    """every stub agent/skill/rubric's eval directory names at least one ok
    and one reject case, each with a fixture `load_definition` actually
    accepts or actually rejects."""
    spec = yaml.safe_load((eval_dir / "eval.yaml").read_text())
    ok_cases = [c for c in spec["cases"] if c["expect"] == "ok"]
    reject_cases = [c for c in spec["cases"] if c["expect"] == "reject"]
    assert ok_cases and reject_cases

    for case in ok_cases:
        fixture_dir = eval_dir / case["fixture"]
        files = list(fixture_dir.glob("*.md"))
        assert len(files) == 1
        definition = load_definition(files[0])
        assert definition["kind"] in {"agent", "skill", "rubric"}
        assert definition["stage"]

    for case in reject_cases:
        fixture_dir = eval_dir / case["fixture"]
        files = list(fixture_dir.glob("*.md"))
        assert len(files) == 1
        with pytest.raises(DefinitionError):
            load_definition(files[0])
