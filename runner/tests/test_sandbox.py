"""The thin sandbox: launcher-built environment, out/results split, credential-by-role, sandbox integrity.

Every test launches the fixture worker under `runner/tests/fixtures/adapter/`
through `runner.launcher.launch` (or, for the stage_run-level integrity
outcome, through `adapters.cursor_sdk.invoke`), the same fixture
`test_adapter.py` uses. No OS-enforced policy, no loopback proxy, and no
copy-on-write copies exist yet at this milestone (R-I-14); these tests
prove the launcher-built environment allowlist, the `out/`/`results/`
split, per-role credential injection, and the sandbox-integrity check --
the whole of this milestone's isolation.
"""
import json
import os
import sys
from pathlib import Path

import yaml

from runner import launcher, manifest, record, tickets
from runner.adapters import cursor_sdk
from runner.db import connect

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "adapter"
WORKER_PATH = FIXTURES_DIR / "fixture_worker.py"
SANDBOX_PATH = FIXTURES_DIR / "sandbox.yaml"


def _envelope_stub(tmp_path: Path) -> Path:
    path = tmp_path / "envelope.json"
    path.write_text(json.dumps({"stage": "S1", "model_requested": "claude-sonnet-5"}))
    return path


def _launch(tmp_path, case: str, *, role: str = "agent", runtime_key_value: str | None = None, extra_env: dict | None = None):
    env_source = {"PATH": os.environ.get("PATH", ""), "FIXTURE_ADAPTER_CASE": case, "SECRET": "leaked-if-present"}
    if extra_env:
        env_source.update(extra_env)
    return launcher.launch(
        run_dir=tmp_path / "run", argv=[sys.executable, str(WORKER_PATH), str(_envelope_stub(tmp_path))],
        role=role, policy="thin", cwd=tmp_path, wall_clock_seconds=15,
        env_source=env_source, runtime_key_value=runtime_key_value, sandbox_path=SANDBOX_PATH,
    )


# ---------------------------------------------------------------------------
# Criterion 18: the child's environment is built only from the allowlist.
# ---------------------------------------------------------------------------


def test_child_environment_is_built_only_from_the_allowlist(tmp_path):
    """a name outside sandbox.yaml's allowlist (SECRET) never reaches the child, whatever env_source carries."""
    result = _launch(tmp_path, "environment_probe")
    assert "SECRET" not in result.integrity.environment_names
    allowlist = yaml.safe_load(SANDBOX_PATH.read_text())["policies"]["thin"]["env_allowlist"]
    assert set(result.integrity.environment_names) <= set(allowlist) | {
        "FACTORY_RUN_OUT", "FACTORY_ENVELOPE_PATH", "__CF_USER_TEXT_ENCODING", "LC_CTYPE",
    }


# ---------------------------------------------------------------------------
# Criterion 19: out/ is writable from inside; results/ only the runner writes.
# ---------------------------------------------------------------------------


def test_out_dir_is_writable_from_inside_and_results_dir_holds_only_runner_written_files(tmp_path):
    result = _launch(tmp_path, "with_output")
    assert (result.out_dir / "result.md").exists()
    assert {p.name for p in result.results_dir.iterdir()} == {"child.pid", "stdout.json", "stderr.txt", "exit.json"}


# ---------------------------------------------------------------------------
# Criterion 20: agent sandboxes alone receive the scoped runtime key; build
# sandboxes receive none of any kind.
# ---------------------------------------------------------------------------


def test_agent_role_receives_the_named_runtime_key(tmp_path):
    result = _launch(tmp_path, "environment_probe", role="agent", runtime_key_value="scoped-secret-value")
    # sandbox.yaml's credential_roles.agent names the environment variable
    # "runtime_key"; its presence in the reported names, never its value
    # (which this worker never echoes), is what proves injection.
    assert "runtime_key" in result.integrity.environment_names


def test_build_role_receives_no_credential_of_any_kind(tmp_path):
    result = _launch(tmp_path, "environment_probe", role="build", runtime_key_value="scoped-secret-value")
    assert "runtime_key" not in result.integrity.environment_names


# ---------------------------------------------------------------------------
# Criterion 21: codegraph starts inside the sandbox as the agent's only
# local server, when its command exists on the allowlisted PATH.
# ---------------------------------------------------------------------------


def test_codegraph_does_not_start_when_its_command_is_not_on_path(tmp_path):
    """sandbox.yaml's fixture names a nonexistent binary; the launcher records that none started, not a failure."""
    result = _launch(tmp_path, "environment_probe", role="agent")
    assert result.integrity.codegraph_started is False
    assert result.exit_code == 0


def test_codegraph_starts_for_the_agent_role_when_its_command_exists(tmp_path):
    sandbox_doc = yaml.safe_load(SANDBOX_PATH.read_text())
    sandbox_doc["policies"]["thin"]["codegraph_command"] = [sys.executable, "-c", "import time; time.sleep(5)"]
    custom_sandbox = tmp_path / "sandbox.yaml"
    custom_sandbox.write_text(yaml.safe_dump(sandbox_doc))

    result = launcher.launch(
        run_dir=tmp_path / "run", argv=[sys.executable, str(WORKER_PATH), str(_envelope_stub(tmp_path))],
        role="agent", policy="thin", cwd=tmp_path, wall_clock_seconds=15,
        env_source={"PATH": os.environ.get("PATH", ""), "FIXTURE_ADAPTER_CASE": "environment_probe"},
        sandbox_path=custom_sandbox,
    )
    assert result.integrity.codegraph_started is True


def test_codegraph_does_not_start_for_the_build_role(tmp_path):
    sandbox_doc = yaml.safe_load(SANDBOX_PATH.read_text())
    sandbox_doc["policies"]["thin"]["codegraph_command"] = [sys.executable, "-c", "import time; time.sleep(5)"]
    custom_sandbox = tmp_path / "sandbox.yaml"
    custom_sandbox.write_text(yaml.safe_dump(sandbox_doc))

    result = launcher.launch(
        run_dir=tmp_path / "run", argv=[sys.executable, str(WORKER_PATH), str(_envelope_stub(tmp_path))],
        role="build", policy="thin", cwd=tmp_path, wall_clock_seconds=15,
        env_source={"PATH": os.environ.get("PATH", ""), "FIXTURE_ADAPTER_CASE": "environment_probe"},
        sandbox_path=custom_sandbox,
    )
    assert result.integrity.codegraph_started is False


# ---------------------------------------------------------------------------
# Criterion 22: every run records a sandbox-integrity result; a violation
# is recorded stage_run.outcome = sandbox_violation / sandbox_integrity.
# ---------------------------------------------------------------------------


def test_must_reject_a_reported_environment_name_outside_the_allowlist(tmp_path):
    result = _launch(tmp_path, "environment_violation")
    assert result.integrity.ok is False
    assert any("SECRET_LEAK" in violation for violation in result.integrity.violations)


def test_must_reject_a_reported_file_written_outside_out_and_the_worktree(tmp_path):
    result = _launch(tmp_path, "path_violation")
    assert result.integrity.ok is False


def test_a_passing_run_records_a_clean_sandbox_integrity_result(tmp_path):
    result = _launch(tmp_path, "settled")
    assert result.integrity.ok is True
    assert result.integrity.violations == ()


def _open(tmp_path):
    return connect(tmp_path / "factory.sqlite")


def test_sandbox_violation_finishes_the_stage_run_sandbox_violation_with_sandbox_integrity_failure_kind(tmp_path):
    """the same violation, driven through the full adapter, lands on stage_run.outcome/failure_kind."""
    conn = _open(tmp_path)
    ticket_id = tickets.open_ticket(
        conn, title="t", trust_profile_hash="tph", trust_approval_set_hash="tash", data_class="internal",
        base_sha="base", head_sha="head", worktree_path=str(tmp_path / "worktree"),
    )
    (tmp_path / "worktree").mkdir(parents=True, exist_ok=True)
    ticket = record.get(conn, "ticket", ticket_id)

    runtime_doc = yaml.safe_load((FIXTURES_DIR / "runtime.yaml").read_text())
    runtime_doc["adapters"]["cursor_sdk"]["command"] = [sys.executable, str(WORKER_PATH)]
    runtime_path = tmp_path / "runtime.yaml"
    runtime_path.write_text(yaml.safe_dump(runtime_doc))

    entry = manifest.Entry(
        stage="S1", tier="standard", agent="factory/agents/S1.md", skill="factory/skills/S1.md",
        shared_skills=(), rubric="factory/rubrics/S1.md", tool_allowlist=("read_file",),
        budget_source="factory/config/tiers.yaml", budget={"tokens": 400000, "wall_clock_seconds": 1200},
        runtime_adapter="cursor_sdk", runtime_version="1.0.31", model_requested="claude-sonnet-5",
        grader_model="claude-sonnet-5", sandbox_policy="thin", toolchain={"jdk": "17"},
        restatement_model=None, agent_hash="a", skill_hash="s", shared_skill_hashes=(),
        rubric_hash="r", manifest_hash="m",
    )
    result = cursor_sdk.invoke(
        conn, ticket=ticket, stage="S1", tier="standard", entry=entry, runs_dir=tmp_path / "runs",
        runtime_path=runtime_path, sandbox_path=SANDBOX_PATH,
        env_source={"PATH": os.environ.get("PATH", ""), "FIXTURE_ADAPTER_CASE": "environment_violation"},
    )
    assert result.outcome == "sandbox_violation"
    assert result.failure_kind == "sandbox_integrity"
    run = record.get(conn, "stage_run", result.stage_run_id)
    assert run["outcome"] == "sandbox_violation"
    assert run["failure_kind"] == "sandbox_integrity"


# ---------------------------------------------------------------------------
# Criterion 23: only registered inputs and the worktree, an allowlisted
# environment, no ambient credential, no push URL.
# ---------------------------------------------------------------------------


def test_must_reject_a_push_url_ever_entering_the_child_environment(tmp_path):
    """no allowlist entry, credential role, or injected name is ever a push URL or git remote override."""
    allowlist = yaml.safe_load(SANDBOX_PATH.read_text())["policies"]["thin"]["env_allowlist"]
    assert not any("PUSH" in name.upper() or "GIT_" in name.upper() for name in allowlist)


def test_build_role_gets_no_ambient_credential_even_when_env_source_carries_one(tmp_path):
    """env_source simulating an ambient CURSOR_API_KEY in the launching process's own environment never crosses."""
    result = _launch(tmp_path, "environment_probe", role="build", extra_env={"CURSOR_API_KEY": "ambient-should-not-cross"})
    assert "CURSOR_API_KEY" not in result.integrity.environment_names
