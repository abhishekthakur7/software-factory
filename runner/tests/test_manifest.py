"""The manifest's full field set, fail-closed resolution, and human-approved migration.

Every fixture under `fixtures/manifest/` is a small, self-contained
`factory/` tree of its own (its own tiny agent/skill/rubric/`tiers.yaml`,
hashed against its own `manifest.yaml`), the same shape as
`factory/evals/scripts/tools/manifest_hash/fixtures/`. `resolve` and
`manifest.current_hash` both require a committed tree (they share the
`manifest_hash` script's own rule), so every test that reaches either one
commits its fixture copy into a fresh git repository first, the same
convention `test_manifest_hash.py` uses.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from runner import artefact_registry, gates, manifest, record, stages, tickets
from runner.adapters import cursor_sdk
from runner.db import connect

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "manifest"
OWNERS_PATH = FIXTURES_DIR / "owners.yaml"
ADAPTER_FIXTURES_DIR = Path(__file__).parent / "fixtures" / "adapter"

_COMMIT_ENV = {
    "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@example.invalid",
}


def _git(args, cwd):
    return subprocess.run(
        ["git", "-c", "commit.gpgsign=false", *args], cwd=cwd, env={**os.environ, **_COMMIT_ENV},
        capture_output=True, text=True, check=True,
    )


def _committed_copy(tmp_path: Path, fixture_name: str) -> Path:
    """Copy `fixtures/manifest/<fixture_name>/factory` into a fresh, committed git repo; return its root."""
    repo = tmp_path / fixture_name
    shutil.copytree(FIXTURES_DIR / fixture_name / "factory", repo / "factory")
    _git(["init", "-q"], cwd=repo)
    _git(["add", "factory"], cwd=repo)
    _git(["commit", "-q", "-m", "init"], cwd=repo)
    return repo


# ---- the manifest's full field set, per stage (criterion 1) ----

def test_every_stage_default_entry_carries_the_full_field_set():
    """`factory/manifest.yaml` names a `default` entry for intake-human_review with every required field, and clarification's restatement_model."""
    m = manifest.load()
    assert set(m.stages) == set(manifest.STAGES)
    for stage in manifest.STAGES:
        default = m.stages[stage]["default"]
        for field_name in manifest.REQUIRED_ENTRY_FIELDS:
            assert field_name in default, f"{stage} default missing {field_name!r}"
    assert "restatement_model" in m.stages["clarification"]["default"]
    for stage in ("intake", "context_gathering", "planning", "implementation", "checks", "human_review"):
        assert "restatement_model" not in m.stages[stage]["default"]


def test_must_reject_manifest_entry_missing_a_required_field():
    """A manifest entry missing a required field fails closed, naming the field."""
    with pytest.raises(manifest.ManifestError, match="missing field"):
        manifest.load(FIXTURES_DIR / "missing_required_field" / "factory" / "manifest.yaml")


def test_resolution_failure_opens_no_stage_run(tmp_path):
    """Resolution never touches the database: a failing `load` call leaves `stage_run` empty."""
    conn = connect(tmp_path / "factory.sqlite")
    assert conn.execute("SELECT COUNT(*) FROM stage_run").fetchone()[0] == 0
    with pytest.raises(manifest.ManifestError):
        manifest.load(FIXTURES_DIR / "missing_required_field" / "factory" / "manifest.yaml")
    assert conn.execute("SELECT COUNT(*) FROM stage_run").fetchone()[0] == 0
    conn.close()


# ---- every referenced file is path plus hash; runtime version is exact (criterion 2) ----

def test_resolved_entry_carries_file_hashes_and_the_current_manifest_hash(tmp_path):
    """`resolve` returns the agent/skill/rubric hashes straight from `files`, plus the manifest's own current hash."""
    repo = _committed_copy(tmp_path, "valid")
    m = manifest.load(repo / "factory" / "manifest.yaml")
    entry = manifest.resolve(m, "context_gathering", "light")
    assert entry.agent == "factory/agents/agent.md"
    assert entry.agent_hash == m.files["factory/agents/agent.md"]
    assert entry.skill_hash == m.files["factory/skills/skill.md"]
    assert entry.rubric_hash == m.files["factory/rubrics/rubric.md"]
    assert entry.manifest_hash == manifest.current_hash(repo)


def test_must_reject_referenced_file_absent_from_files():
    """An entry naming a file with no `files` entry fails closed under the manifest's path-plus-hash rule."""
    with pytest.raises(manifest.ManifestError, match="absent from 'files'"):
        manifest.load(FIXTURES_DIR / "missing_referenced_file" / "factory" / "manifest.yaml")


def test_must_reject_on_disk_file_hash_drifted_from_the_manifest(tmp_path):
    """A referenced file whose on-disk bytes no longer match its manifest hash fails resolution."""
    repo = _committed_copy(tmp_path, "valid")
    m = manifest.load(repo / "factory" / "manifest.yaml")
    (repo / "factory" / "agents" / "agent.md").write_text("tampered after load\n")
    with pytest.raises(manifest.ManifestError, match="no longer matches"):
        manifest.resolve(m, "context_gathering", "light")


def test_must_reject_a_runtime_version_expressed_as_a_range(tmp_path):
    """`runtime_version` must be an exact version or digest, not a range; loading needs no git commit."""
    shutil.copytree(FIXTURES_DIR / "valid" / "factory", tmp_path / "factory")
    manifest_path = tmp_path / "factory" / "manifest.yaml"
    text = manifest_path.read_text().replace('runtime_version: "1.0.0"', 'runtime_version: "^1.0.0"', 1)
    manifest_path.write_text(text)
    with pytest.raises(manifest.ManifestError, match="exact version"):
        manifest.load(manifest_path)


# ---- budgets are keyed only as tokens/wall_clock_seconds (criterion 3) ----

def test_the_real_manifest_budgets_carry_only_the_two_allowed_keys():
    """Loading the committed manifest also validates every budget key `tiers.yaml` names, by every entry's `budget` path."""
    manifest.load()  # raises ManifestError if any budget key strays from tokens/wall_clock_seconds


def test_must_reject_a_budget_key_outside_tokens_and_wall_clock_seconds():
    """A budget key other than `tokens`/`wall_clock_seconds` fails closed."""
    with pytest.raises(manifest.ManifestError, match="budget key"):
        manifest.load(FIXTURES_DIR / "invalid_budget_key" / "factory" / "manifest.yaml")


# ---- intake, checks, human_review carry null agent/skill/model fields; the others do not (criterion 4) ----

def test_null_agent_skill_and_model_fields_on_script_only_stages():
    """intake, checks and human_review carry null agent, skill and model fields; the agent-driven stages carry none of them null."""
    m = manifest.load()
    for stage in ("intake", "checks", "human_review"):
        default = m.stages[stage]["default"]
        assert default["agent"] is None
        assert default["skill"] is None
        assert default["model_requested"] is None
        assert default["grader_model"] is None
    for stage in ("context_gathering", "clarification", "planning", "implementation"):
        default = m.stages[stage]["default"]
        assert default["agent"] is not None
        assert default["skill"] is not None
        assert default["model_requested"] is not None
        assert default["grader_model"] is not None


def test_must_reject_a_non_null_agent_on_a_script_only_stage():
    """A script-only stage (checks here) carrying a non-null agent fails closed."""
    with pytest.raises(manifest.ManifestError, match="must be null"):
        manifest.load(FIXTURES_DIR / "non_null_agent_on_checks" / "factory" / "manifest.yaml")


# ---- migration invalidates context_gathering-onward artefacts and requires factory_owner quorum (criteria 9, 10) ----

def test_migration_invalidates_context_gathering_onward_artefacts_and_returns_the_ticket_to_context(tmp_path):
    """A human-approved manifest change invalidates every context_gathering-onward artefact and returns the ticket to `context`."""
    repo = _committed_copy(tmp_path, "migration_seed")
    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = tickets.open_ticket(conn, factory_manifest_hash="stale-hash")
    record.update(conn, "ticket", ticket_id, state="implementing")
    intake_run = record.insert(conn, "stage_run", ticket_id=ticket_id, stage="intake", attempt=1)
    context_gathering_run = record.insert(conn, "stage_run", ticket_id=ticket_id, stage="context_gathering", attempt=1)
    clarification_run = record.insert(conn, "stage_run", ticket_id=ticket_id, stage="clarification", attempt=1)
    eligibility, brief, criteria = tmp_path / "e.txt", tmp_path / "b.txt", tmp_path / "c.txt"
    eligibility.write_text("e")
    brief.write_text("b")
    criteria.write_text("c")
    eligibility_id = artefact_registry.register(
        conn, ticket_id=ticket_id, kind="eligibility", path=eligibility, stage_run_id=intake_run
    )
    brief_id = artefact_registry.register(conn, ticket_id=ticket_id, kind="brief", path=brief, stage_run_id=context_gathering_run)
    criteria_id = artefact_registry.register(
        conn, ticket_id=ticket_id, kind="criteria", path=criteria, stage_run_id=clarification_run
    )
    conn.commit()

    manifest.migrate(conn, actor="abhishek", root=repo, owners_path=OWNERS_PATH)
    conn.commit()

    ticket = record.get(conn, "ticket", ticket_id)
    new_hash = manifest.current_hash(repo)
    assert ticket["state"] == "context"
    assert ticket["factory_manifest_hash"] == new_hash
    check_result = conn.execute("SELECT * FROM check_result WHERE check_name = 'manifest_migration'").fetchone()
    # Names exactly the context_gathering/clarification artefacts, in id order; the intake (`eligibility_id`)
    # artefact this same ticket registered is not among them.
    assert check_result["summary"].endswith(f"invalidates artefact(s) [{brief_id}, {criteria_id}]")
    conn.close()


def test_must_reject_migration_without_factory_owner_quorum(tmp_path):
    """Without a `factory_owner` approval, the migration attempt is recorded but changes no ticket."""
    repo = _committed_copy(tmp_path, "migration_seed")
    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = tickets.open_ticket(conn, factory_manifest_hash="stale-hash")
    record.update(conn, "ticket", ticket_id, state="implementing")
    conn.commit()

    message = manifest.migrate(conn, actor="not-the-factory-owner", root=repo, owners_path=OWNERS_PATH)
    conn.commit()

    assert "waiting" in message
    ticket = record.get(conn, "ticket", ticket_id)
    assert ticket["state"] == "implementing"
    assert ticket["factory_manifest_hash"] == "stale-hash"
    approval = conn.execute("SELECT * FROM approval_record WHERE gate = 'manifest'").fetchone()
    assert approval is not None
    assert approval["decision"] == "reject"
    assert conn.execute("SELECT COUNT(*) FROM check_result WHERE check_name = 'manifest_migration'").fetchone()[0] == 0
    conn.close()


def test_migration_leaves_a_terminal_ticket_untouched(tmp_path):
    """A ticket already in a terminal state is never migrated, even when its hash differs."""
    repo = _committed_copy(tmp_path, "migration_seed")
    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = tickets.open_ticket(conn, factory_manifest_hash="stale-hash")
    record.update(conn, "ticket", ticket_id, state="abandoned", closed_at=record.now(), close_reason="abandoned")
    conn.commit()

    manifest.migrate(conn, actor="abhishek", root=repo, owners_path=OWNERS_PATH)
    conn.commit()

    ticket = record.get(conn, "ticket", ticket_id)
    assert ticket["state"] == "abandoned"
    assert ticket["factory_manifest_hash"] == "stale-hash"
    conn.close()


# ---- fail-closed model checks over a manifest-resolved entry (criteria 6, 7) ----


def _model_check_runtime(tmp_path: Path, fixture_name: str) -> Path:
    """A copy of `model_check/<fixture_name>` with its worker command resolved to the running interpreter."""
    doc = yaml.safe_load((FIXTURES_DIR / "model_check" / fixture_name).read_text())
    doc["adapters"]["cursor_sdk"]["command"] = [sys.executable, str(ADAPTER_FIXTURES_DIR / "fixture_worker.py")]
    path = tmp_path / "runtime.yaml"
    path.write_text(yaml.safe_dump(doc))
    return path


def _resolved_entry(tmp_path: Path, stage: str = "context_gathering", tier: str = "light") -> manifest.Entry:
    repo = _committed_copy(tmp_path, "valid")
    m = manifest.load(repo / "factory" / "manifest.yaml")
    return manifest.resolve(m, stage, tier)


def test_must_reject_a_model_requested_absent_from_runtime_yaml(tmp_path):
    """criterion 6: an invocation whose requested model is absent from runtime.yaml's list is refused before it starts, no output registered."""
    entry = _resolved_entry(tmp_path)
    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = tickets.open_ticket(conn)
    ticket = record.get(conn, "ticket", ticket_id)

    result = cursor_sdk.invoke(
        conn, ticket=ticket, stage="context_gathering", tier="light", entry=entry, runs_dir=tmp_path / "runs",
        runtime_path=_model_check_runtime(tmp_path, "unavailable_runtime.yaml"),
        sandbox_path=ADAPTER_FIXTURES_DIR / "sandbox.yaml",
    )

    assert result.outcome == "infrastructure_failure"
    assert result.stage_run_id == -1
    assert conn.execute("SELECT COUNT(*) FROM stage_run").fetchone()[0] == 0


def test_must_reject_a_resolved_model_that_differs_from_the_one_requested(tmp_path):
    """criterion 7: an invocation whose resolved model differs from the requested one is recorded infrastructure_failure with no output registered."""
    entry = _resolved_entry(tmp_path)
    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = tickets.open_ticket(conn)
    ticket = record.get(conn, "ticket", ticket_id)

    result = cursor_sdk.invoke(
        conn, ticket=ticket, stage="context_gathering", tier="light", entry=entry, runs_dir=tmp_path / "runs",
        runtime_path=_model_check_runtime(tmp_path, "mismatch_runtime.yaml"),
        sandbox_path=ADAPTER_FIXTURES_DIR / "sandbox.yaml",
        env_source={"PATH": os.environ.get("PATH", ""), "FIXTURE_ADAPTER_CASE": "silent_fallback"},
    )

    assert result.outcome == "infrastructure_failure"
    assert result.failure_kind == "infrastructure"
    assert result.model_resolved == "claude-haiku-5-20260115"
    assert conn.execute(
        "SELECT COUNT(*) FROM artefact WHERE stage_run_id = ?", (result.stage_run_id,)
    ).fetchone()[0] == 0


# ---- the manifest-hash pin at intake eligibility, enforced on every later stage run (criterion 8) ----


def test_must_reject_a_stage_run_on_a_ticket_with_no_manifest_pin(tmp_path):
    """criterion 8: a ticket with no `factory_manifest_hash` pin is refused before any stage_run opens."""
    repo = _committed_copy(tmp_path, "valid")
    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = tickets.open_ticket(conn)
    record.update(conn, "ticket", ticket_id, state="checks")
    ticket = record.get(conn, "ticket", ticket_id)

    outcome = stages.invoke_agent(
        conn, ticket, "checks", tier="light", manifest_path=repo / "factory" / "manifest.yaml", runs_dir=tmp_path,
    ).outcome

    assert outcome == "refused_request"
    assert conn.execute("SELECT COUNT(*) FROM stage_run").fetchone()[0] == 0
    refusal = conn.execute("SELECT outputs FROM utility_run WHERE kind = 'refused_request'").fetchone()
    assert "no manifest pin" in refusal["outputs"]


def test_must_reject_a_stage_run_whose_pin_no_longer_matches_the_resolved_manifest_hash(tmp_path):
    """criterion 8: a stale `factory_manifest_hash` pin refuses every later stage run, no stage_run opened."""
    repo = _committed_copy(tmp_path, "valid")
    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = tickets.open_ticket(conn, factory_manifest_hash="stale-pin")
    record.update(conn, "ticket", ticket_id, state="checks")
    ticket = record.get(conn, "ticket", ticket_id)

    outcome = stages.invoke_agent(
        conn, ticket, "checks", tier="light", manifest_path=repo / "factory" / "manifest.yaml", runs_dir=tmp_path,
    ).outcome

    assert outcome == "refused_request"
    assert conn.execute("SELECT COUNT(*) FROM stage_run").fetchone()[0] == 0


def test_a_matching_pin_lets_a_later_stage_run_through(tmp_path):
    """criterion 8: a ticket pinned to the resolved manifest's own hash runs normally."""
    repo = _committed_copy(tmp_path, "valid")
    current = manifest.current_hash(repo)
    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = tickets.open_ticket(conn, factory_manifest_hash=current)
    record.update(conn, "ticket", ticket_id, state="checks")
    ticket = record.get(conn, "ticket", ticket_id)

    outcome = stages.invoke_agent(
        conn, ticket, "checks", tier="light", manifest_path=repo / "factory" / "manifest.yaml", runs_dir=tmp_path,
    ).outcome

    assert outcome == "pass"
    assert conn.execute("SELECT COUNT(*) FROM utility_run WHERE kind = 'refused_request'").fetchone()[0] == 0


def test_intake_is_exempt_from_the_pin_check(tmp_path):
    """criterion 8: intake needs no pin yet, since the pin is not written until eligibility is granted."""
    repo = _committed_copy(tmp_path, "valid")
    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = tickets.open_ticket(conn)  # state=intake, no pin
    ticket = record.get(conn, "ticket", ticket_id)

    outcome = stages.invoke_agent(
        conn, ticket, "intake", tier="light", manifest_path=repo / "factory" / "manifest.yaml", runs_dir=tmp_path,
    ).outcome

    assert outcome == "pass"


def test_eligibility_granted_pins_the_manifest_hash_when_the_ticket_has_none(tmp_path):
    """criterion 8: the eligibility_granted path pins ticket.factory_manifest_hash the first time, from the real committed manifest."""
    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = tickets.open_ticket(conn)
    record.insert(conn, "stage_run", ticket_id=ticket_id, stage="intake", attempt=1, outcome="pass")
    record.insert(conn, "queue_item", ticket_id=ticket_id, kind="eligibility", action="granted")
    ticket = record.get(conn, "ticket", ticket_id)

    event = gates.intake_gate(conn, ticket)

    assert event == "eligibility_granted"
    assert record.get(conn, "ticket", ticket_id)["factory_manifest_hash"] == manifest.current_hash()
