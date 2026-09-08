"""The stub stage drivers, run for real, plus the conformance walk over
every stub agent/skill/rubric's own eval directory: every referenced file
has an eval directory with at least one accepted and one rejected fixture.

Every stub run here is given `tmp_path` as its runs root, so the artefact
each driver writes and registers lands there rather than under the real
repository's `runs/`, which no test touches.
"""
import os
import subprocess
from pathlib import Path

import pytest
import yaml

from runner import artefact_registry, gates, git_trees, governance, manifest, record, transitions
from runner.db import connect
from runner.definitions import DefinitionError, load_definition
from runner.fs import write_text
from runner.paths import FACTORY_DIR
from runner.stages import run_stage

ABHISHEK = "abhishek"
FAR_FUTURE = "2999-01-01T00:00:00+00:00"
S1_FIXTURE_OUT = FACTORY_DIR / "evals" / "agents" / "S1" / "fixtures" / "plain_ok" / "out"

EVAL_ROOTS = (FACTORY_DIR / "evals" / "agents", FACTORY_DIR / "evals" / "skills", FACTORY_DIR / "evals" / "rubrics")


@pytest.fixture
def conn(tmp_path):
    connection = connect(tmp_path / "factory.sqlite")
    yield connection
    connection.close()


def _ticket_in(conn, state, **fields):
    return record.insert(conn, "ticket", state=state, opened_at=record.now(), **fields)


_COMMIT_ENV = {
    "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@example.invalid",
}


def _git(args, cwd, env=None):
    full_env = {**os.environ, **env} if env else None
    return subprocess.run(
        ["git", "-c", "commit.gpgsign=false", *args], cwd=cwd, env=full_env,
        capture_output=True, text=True, check=True,
    )


def _source_repo(tmp_path):
    repo = tmp_path / "source-repo"
    repo.mkdir()
    _git(["init", "-q"], cwd=repo)
    _git(["checkout", "-q", "-b", "main"], cwd=repo)
    (repo / "README.md").write_text("seed\n")
    # A minimal pom so a real S1 run's impact_scan has something to read;
    # the dependency itself matches the committed artifact-to-service.yaml's
    # one authoritative entry, so a real S1 run needs no fixture override.
    (repo / "pom.xml").write_text(
        "<project>\n  <groupId>com.example</groupId>\n  <artifactId>widget</artifactId>\n  <version>1.0.0</version>\n"
        "  <dependencies>\n    <dependency>\n      <groupId>com.fixturevendor</groupId>\n"
        "      <artifactId>strings</artifactId>\n      <version>1.0.0</version>\n    </dependency>\n  </dependencies>\n"
        "</project>\n"
    )
    src = repo / "src" / "main" / "java" / "com" / "example"
    src.mkdir(parents=True)
    (src / "Handler.java").write_text("package com.example;\n\npublic class Handler {\n}\n")
    _git(["add", "-A"], cwd=repo)
    _git(["commit", "-q", "-m", "init"], cwd=repo, env=_COMMIT_ENV)
    return repo


def _governed_ticket_fields(conn) -> dict:
    """Ticket fields that satisfy the committed trust profile's default-path activation."""
    proposal = governance.propose()
    for role in ("security_approver", "legal_data_governance_approver"):
        governance.decide(
            conn, proposal, actor_identity=ABHISHEK, role=role, decision="approve",
            expires_at=FAR_FUTURE, attestation_version="v1", attestation_hash=f"att-{role}",
        )
    activated = governance.activation(conn, proposal)
    return {
        "trust_profile_hash": proposal.profile_hash, "trust_approval_set_hash": activated.trust_approval_set_hash,
        "service": "fixture-project", "source_kind": "jira", "source_ref": "FIX-1",
    }


def _s1_ready_ticket(conn, tmp_path):
    """A ticket in `context`, cloned from a real worktree, pinned and eligible to invoke a real S1."""
    source = _source_repo(tmp_path)
    ticket_id = _ticket_in(
        conn, "context", ticket_type="small_feature", service_tier="T2", tier_provisional="standard",
        factory_manifest_hash=manifest.current_hash(), **_governed_ticket_fields(conn),
    )
    trees = git_trees.clone_for_ticket(conn, ticket_id, source_checkout=source, target_branch="main", runs_dir=tmp_path)
    git_trees.record_head(conn, ticket_id, trees.worktree)
    return ticket_id


def _checks_ticket_with_fresh_base(conn, tmp_path):
    """A ticket cloned from a real repository, sitting in `checks` with a
    plan tuple that matches its base -- S5's preflight now fetches the
    real target branch, so a ticket with no git trees at all can no longer
    stand in for one running S5."""
    source = _source_repo(tmp_path)
    ticket_id = record.insert(conn, "ticket", state="intake", opened_at=record.now())
    trees = git_trees.clone_for_ticket(conn, ticket_id, source_checkout=source, target_branch="main", runs_dir=tmp_path)
    git_trees.record_head(conn, ticket_id, trees.worktree)
    record.update(conn, "ticket", ticket_id, state="checks")
    record.insert(
        conn, "evidence_tuple", kind="plan", ticket_id=ticket_id,
        base_sha=trees.base_sha, target_base_sha=trees.base_sha, content_hash="plan-subject-checks",
    )
    return ticket_id


# S3 is real, not a stub: it needs a worktree (for `risk_map`), the real
# manifest pin, and a brief/criteria to plan against. `_WALK_BRIEF_TEXT`
# gives risk_map a real candidate path and handoff_ready's brief-derived
# conditions something to read; the criteria fixture is the one
# `runner/tests/test_s3_structure.py` also drives directly.
_S3_BRIEF_TEXT = """## Touched area candidates

| path | reason |
|---|---|
| README.md | the file this ticket's plan touches |

## Linked sources

| source | date |
|---|---|
| JIRA-123 | 2026-01-01 |

## Impact evidence

| direction | dependency | method | source | mapping | owner | coverage | blind_spots |
|---|---|---|---|---|---|---|---|
| outbound | svc-x | import_scan | pom.xml | mapping.yaml | abhishek | authoritative | none |
"""


def _planning_ticket_with_plan_inputs(conn, tmp_path):
    """A ticket sitting in `planning` with a real worktree, manifest pin, and brief/criteria for S3 to plan against."""
    source = _source_repo(tmp_path)
    ticket_id = record.insert(
        conn, "ticket", state="intake", opened_at=record.now(), factory_manifest_hash=manifest.current_hash(),
        tier_final="light",
    )
    trees = git_trees.clone_for_ticket(conn, ticket_id, source_checkout=source, target_branch="main", runs_dir=tmp_path)
    git_trees.record_head(conn, ticket_id, trees.worktree)
    record.update(conn, "ticket", ticket_id, state="planning")

    brief_path = tmp_path / "s3_brief.md"
    write_text(brief_path, _S3_BRIEF_TEXT)
    artefact_registry.register(conn, ticket_id=ticket_id, kind="brief", path=brief_path)
    criteria_path = Path(__file__).parent / "fixtures" / "s3" / "criteria.md"
    artefact_registry.register(conn, ticket_id=ticket_id, kind="criteria", path=criteria_path)
    return ticket_id


def test_s0_stub_runs_and_the_eligibility_gate_moves_intake_to_context(conn, tmp_path):
    """the real S0 driver runs (writing and registering a
    `ticket_source` artefact), then a granted eligibility item moves the
    ticket on; S0 passing by itself is not enough. `service`/`ticket_type`
    are seeded here since S0's own lookups now need a real pilot-eligible
    pair to pass rather than reject."""
    ticket_id = _ticket_in(conn, "intake", service="fixture-project", ticket_type="small_feature")
    outcome = run_stage(conn, ticket_id, "S0", runs_dir=tmp_path)
    assert outcome == "pass"
    assert record.get(conn, "ticket", ticket_id)["state"] == "intake"  # S0 alone doesn't move it
    artefact = artefact_registry.latest(conn, ticket_id, "ticket_source")
    assert artefact is not None

    record.insert(conn, "queue_item", ticket_id=ticket_id, kind="eligibility", action="granted")
    ticket = record.get(conn, "ticket", ticket_id)
    event = gates.intake_gate(conn, ticket)
    assert transitions.apply(conn, ticket_id, event) == "context"


def test_s1_stub_writes_a_brief_and_passes_to_clarifying(conn, tmp_path, monkeypatch):
    """the real S1 driver writes and registers a checked `brief`
    artefact and its pass moves context -> clarifying; the full driver's
    own behaviour is `test_s1.py`'s, this is the conformance-suite's own
    smoke test that the wiring in `run_stage`/`DRIVERS` still holds."""
    monkeypatch.setenv("FIXTURE_ADAPTER_OUT_DIR", str(S1_FIXTURE_OUT))
    ticket_id = _s1_ready_ticket(conn, tmp_path)
    outcome = run_stage(conn, ticket_id, "S1", runs_dir=tmp_path)
    assert outcome == "pass"
    assert record.get(conn, "ticket", ticket_id)["state"] == "clarifying"
    assert artefact_registry.latest(conn, ticket_id, "brief") is not None


# S2 is no longer a stub: its question and assumption half is exercised
# end to end in test_s2_questions.py (test_s2_walk_...), including the
# clarifying -> planning pass this module's other stub tests each cover
# for their own still-stub stage.


def test_s3_runs_for_real_and_passes_to_plan_review(conn, tmp_path):
    """the real S3 driver plans against a real brief/criteria, writes and
    registers a `plan` artefact carrying the derived readiness table, and
    its pass moves planning -> plan_review; `test_s3_structure.py` covers
    the driver's checks in depth, this is the stage-walk smoke test."""
    ticket_id = _planning_ticket_with_plan_inputs(conn, tmp_path)
    os.environ["FIXTURE_ADAPTER_OUT_DIR"] = str(FACTORY_DIR / "evals" / "agents" / "S3" / "fixtures" / "ok" / "out")
    try:
        outcome = run_stage(conn, ticket_id, "S3", runs_dir=tmp_path)
    finally:
        os.environ.pop("FIXTURE_ADAPTER_OUT_DIR", None)
    assert outcome == "pass"
    assert record.get(conn, "ticket", ticket_id)["state"] == "plan_review"
    plan = artefact_registry.latest(conn, ticket_id, "plan")
    assert plan is not None
    assert "| reviewer_set | pass |" in Path(plan["path"]).read_text()


def _implementing_ticket_with_plan_inputs(conn, tmp_path):
    """A ticket sitting in `implementing` with a real worktree, manifest pin, and a bound plan tuple for S4 to hand off."""
    source = _source_repo(tmp_path)
    ticket_id = record.insert(
        conn, "ticket", state="intake", opened_at=record.now(), factory_manifest_hash=manifest.current_hash(),
        tier_final="standard",
    )
    trees = git_trees.clone_for_ticket(conn, ticket_id, source_checkout=source, target_branch="main", runs_dir=tmp_path)
    git_trees.record_head(conn, ticket_id, trees.worktree)
    record.update(conn, "ticket", ticket_id, state="implementing")
    record.insert(
        conn, "evidence_tuple", kind="plan", ticket_id=ticket_id,
        base_sha=trees.base_sha, target_base_sha=trees.base_sha, content_hash="plan-subject-implementing",
    )
    plan_path = Path(__file__).parent / "fixtures" / "s4_handoff" / "plan.md"
    artefact_registry.register(conn, ticket_id=ticket_id, kind="plan", path=plan_path)
    criteria_path = Path(__file__).parent / "fixtures" / "s3" / "criteria.md"
    artefact_registry.register(conn, ticket_id=ticket_id, kind="criteria", path=criteria_path)
    return ticket_id


def test_s4_runs_for_real_and_passes_to_checks(conn, tmp_path):
    """the real S4 driver hands off, invokes the fixture worker, records the
    hand-back's branch/head/deviation rows, and its pass moves
    implementing -> checks; `test_s4_handoff.py`/`test_s4_handback.py`
    cover the driver in depth, this is the stage-walk smoke test."""
    ticket_id = _implementing_ticket_with_plan_inputs(conn, tmp_path)
    os.environ["FIXTURE_ADAPTER_OUT_DIR"] = str(FACTORY_DIR / "evals" / "agents" / "S4" / "fixtures" / "ok" / "out")
    os.environ["FIXTURE_ADAPTER_WORKTREE_DIR"] = str(FACTORY_DIR / "evals" / "agents" / "S4" / "fixtures" / "ok" / "worktree")
    try:
        outcome = run_stage(conn, ticket_id, "S4", runs_dir=tmp_path)
    finally:
        os.environ.pop("FIXTURE_ADAPTER_OUT_DIR", None)
        os.environ.pop("FIXTURE_ADAPTER_WORKTREE_DIR", None)
    assert outcome == "pass"
    assert record.get(conn, "ticket", ticket_id)["state"] == "checks"
    assert artefact_registry.latest(conn, ticket_id, "handoff") is not None
    assert conn.execute("SELECT COUNT(*) FROM deviation WHERE ticket_id = ?", (ticket_id,)).fetchone()[0] == 2


def test_s5_and_s6_stubs_run_and_the_checks_gate_moves_checks_to_review(conn, tmp_path):
    """the real S5 and S6 stub drivers each run (writing
    `check_evidence` and `packet` artefacts) without leaving `checks` on
    their own; only once both have passed does the checks gate fire."""
    ticket_id = _checks_ticket_with_fresh_base(conn, tmp_path)
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


def test_a_second_stub_run_supersedes_the_first_artefact(conn, tmp_path, monkeypatch):
    """running a stage twice for the same ticket chains `supersedes` to the
    prior version rather than losing it, so a superseded version stays
    readable."""
    monkeypatch.setenv("FIXTURE_ADAPTER_OUT_DIR", str(S1_FIXTURE_OUT))
    ticket_id = _s1_ready_ticket(conn, tmp_path)
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
