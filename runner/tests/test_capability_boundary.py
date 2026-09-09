"""Boundary tests over the manifest and the OS-enforced sandbox: undeclared tools, source writes, path and
symlink escapes, an arbitrary shell string, ambient credentials, a push attempt, and the resolved tool set's
own timing.

This module builds no new mechanism: every test proves that a real,
already-committed boundary -- the manifest's resolved tool set, the
agent/build Seatbelt profiles, the loopback proxy, `recipes.run`'s own
digest check -- refuses what it is supposed to refuse. Every sandboxed
probe is a standalone script under `fixtures/capability_boundary/<name>/`,
launched for real through `runner.launcher.launch` (via
`runner/tests/support.py`'s `launch_probe`, or a direct call where a test
needs to seed run-directory state first), never mocked. `os_policy` is
imported and checked for real Seatbelt availability at collection time,
the same way `test_escape_suite.py` does, so a host that cannot actually
run the agent profile fails this module outright rather than skipping
quietly.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from runner import git_trees, manifest, record, run_ledger, tickets
from runner.adapters import cursor_sdk
from runner.db import connect
from runner.sandbox import os_policy
from runner.stages import S4
from runner.tests.support import launch_probe

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "capability_boundary"
ADAPTER_FIXTURES_DIR = Path(__file__).parent / "fixtures" / "adapter"
ENTRY_FIXTURE = FIXTURES_DIR / "entry" / "factory"

if not os_policy.available():
    pytest.fail(
        "sandbox-exec cannot run the agent profile on this host; the capability-boundary "
        "suite fails outright rather than skip",
        pytrace=False,
    )

_COMMIT_ENV = {
    "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@example.invalid",
}


def _git(args, cwd, env=None):
    full_env = {**os.environ, **(env or {})}
    return subprocess.run(
        ["git", "-c", "commit.gpgsign=false", *args], cwd=cwd, env=full_env, capture_output=True, text=True, check=True,
    )


def _committed_copy(tmp_path: Path, source: Path, name: str) -> Path:
    """Copy `source` (a `factory/` tree) into a fresh, committed git repo under `tmp_path`; return its root."""
    repo = tmp_path / name
    shutil.copytree(source, repo / "factory")
    _git(["init", "-q"], cwd=repo)
    _git(["add", "factory"], cwd=repo)
    _git(["commit", "-q", "-m", "init"], cwd=repo, env=_COMMIT_ENV)
    return repo


def _resolved_entry(tmp_path: Path, stage: str = "S1", tier: str = "light") -> manifest.Entry:
    repo = _committed_copy(tmp_path, ENTRY_FIXTURE, "entry_repo")
    m = manifest.load(repo / "factory" / "manifest.yaml")
    return manifest.resolve(m, stage, tier)


def _fixture_runtime_path(tmp_path: Path) -> Path:
    """A `runtime.yaml` naming the real fixture worker, the way `test_manifest.py`'s own model-check tests do."""
    doc = yaml.safe_load((ADAPTER_FIXTURES_DIR / "runtime.yaml").read_text())
    doc["adapters"]["cursor_sdk"]["command"] = [sys.executable, str(ADAPTER_FIXTURES_DIR / "fixture_worker.py")]
    path = tmp_path / "runtime.yaml"
    path.write_text(yaml.safe_dump(doc))
    return path


def _tiny_pushless_repo(root: Path) -> Path:
    """A tiny git repo whose push URL is disabled, the same way `git_trees.clone_for_ticket` leaves every clone."""
    root.mkdir(parents=True, exist_ok=True)
    _git(["init", "-q"], cwd=root)
    _git(["checkout", "-q", "-b", "main"], cwd=root)
    (root / "README.md").write_text("seed\n")
    _git(["add", "-A"], cwd=root)
    _git(["commit", "-q", "-m", "seed"], cwd=root, env=_COMMIT_ENV)
    _git(["remote", "add", "origin", "https://example.invalid/not-real.git"], cwd=root)
    _git(["remote", "set-url", "--push", "origin", git_trees.DISABLED_PUSH_URL], cwd=root)
    return root


# An undeclared, workspace-level tool never reaches the resolved tool set.

def test_stage_run_tool_allowlist_never_admits_a_workspace_level_mcp_server(tmp_path):
    """The resolved `stage_run.tool_allowlist` comes from the manifest entry alone; an env-carried
    workspace tool name never merges into it."""
    entry = _resolved_entry(tmp_path, "S1", "light")
    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = tickets.open_ticket(conn)
    ticket = record.get(conn, "ticket", ticket_id)

    result = cursor_sdk.invoke(
        conn, ticket=ticket, stage="S1", tier="light", entry=entry, runs_dir=tmp_path / "runs",
        runtime_path=_fixture_runtime_path(tmp_path), sandbox_path=ADAPTER_FIXTURES_DIR / "sandbox.yaml",
        env_source={"PATH": os.environ.get("PATH", ""), "CURSOR_MCP_SERVERS": "workspace_leaked_tool"},
    )

    assert result.outcome == "pass"
    row = record.get(conn, "stage_run", result.stage_run_id)
    assert json.loads(row["tool_allowlist"]) == list(entry.tool_allowlist)
    assert "workspace_leaked_tool" not in row["tool_allowlist"]


def test_a_server_named_by_an_mcp_config_inside_the_worktree_is_unreachable(tmp_path):
    """A `.cursor/mcp.json` inside the ticket's own worktree is readable like any other checked-in file, but the
    server it names is not on the stage's proxy allowlist, so the sandbox's one way out refuses it."""
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    (worktree / ".cursor").mkdir()
    mcp_config = worktree / ".cursor" / "mcp.json"
    mcp_config.write_text(json.dumps({"mcpServers": {"workspace_leaked_tool": {"host": "mcp.example.test", "port": 443}}}))

    payload = launch_probe(
        tmp_path, FIXTURES_DIR / "mcp_config" / "probe.py", role="agent", stage="S1",
        ticket_dir=tmp_path / "ticket", worktree_path=worktree, extra_argv=(str(mcp_config),),
    )
    assert payload == {"attempted": True, "refused": True, "read": True}


# A recipe invocation at a stage other than S4 attempting to write into the ticket worktree.

def test_a_build_profile_recipe_run_writing_the_worktree_is_refused(tmp_path):
    """A recipe invocation runs under the build profile against a copy; the build profile never even
    mounts a path shaped like the ticket's worktree, so a write there is refused regardless of stage."""
    worktree_shaped_path = tmp_path / "worktree"
    worktree_shaped_path.mkdir()
    payload = launch_probe(
        tmp_path, FIXTURES_DIR / "source_write" / "probe.py", role="build", stage="S4",
        copy_dir=tmp_path / "copy", build_dir=tmp_path / "build", scratch_dir=tmp_path / "scratch",
        cache_dir=tmp_path / "cache", extra_argv=(str(worktree_shaped_path),),
    )
    assert payload == {"attempted": True, "refused": True}


# A relative-path traversal and a symlink escape, both from an allowed mount.

def test_a_relative_traversal_from_the_worktree_to_the_host_home_directory_is_refused(tmp_path):
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    payload = launch_probe(
        tmp_path, FIXTURES_DIR / "traversal" / "probe.py", role="agent", stage="S4",
        ticket_dir=tmp_path / "ticket", worktree_path=worktree, extra_argv=(str(worktree),),
    )
    assert payload == {"attempted": True, "refused": True}


def test_a_symlink_inside_out_pointing_outside_every_mount_is_refused(tmp_path):
    run_dir = tmp_path / "run"
    out_dir = run_dir / "out"
    out_dir.mkdir(parents=True)
    link_path = out_dir / "escape_link"
    link_path.symlink_to(Path(os.path.expanduser("~")) / ".ssh")
    payload = launch_probe(
        tmp_path, FIXTURES_DIR / "symlink_out" / "probe.py", role="agent", stage="S1",
        ticket_dir=tmp_path / "ticket", extra_argv=(str(link_path),),
    )
    assert payload == {"attempted": True, "refused": True}


# An agent-issued shell string in place of a typed recipe id.

def test_must_reject_a_shell_string_arriving_through_the_s4_hand_backs_validation_recipe_field(tmp_path):
    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = tickets.open_ticket(conn)
    ticket = record.get(conn, "ticket", ticket_id)
    stage_run_id = run_ledger.open_stage_run(conn, ticket_id=ticket_id, stage="S4")

    task = {"validation_recipe": "; rm -rf / #", "validation_args": {}, "id": 1}
    outcome, failure_kind = S4._validate_task(conn, ticket, stage_run_id, task, runs_dir=tmp_path)

    assert outcome == "fail"
    assert failure_kind == "recipe_binding"
    refusal = conn.execute(
        "SELECT result, summary FROM check_result WHERE stage_run_id = ? AND check_name = 'recipe_binding'",
        (stage_run_id,),
    ).fetchone()
    assert refusal["result"] == "fail"
    assert "; rm -rf / #" in refusal["summary"]


# A task-validation recipe runs under the same OS-enforced build sandbox as any other recipe.

def test_a_task_validation_recipe_is_launched_under_the_build_role_with_the_enforced_policy(tmp_path):
    """`_validate_task` used to dispatch its recipe through the bare-subprocess branch of
    `recipes.run`, never through `launcher.launch`. The launch record it now produces --
    `exit.json` under its own sandbox run directory -- is the same evidence
    `test_dependency_resolution_recipe_runs_under_the_build_profile` in `test_recipes.py`
    already treats as proof of a real, non-mocked Seatbelt-wrapped execution."""
    conn = connect(tmp_path / "factory.sqlite")
    worktree = tmp_path / "worktree"
    (worktree / "src" / "main" / "java" / "com" / "fixture").mkdir(parents=True)
    (worktree / "src" / "main" / "java" / "com" / "fixture" / "Widget.java").write_text(
        "package com.fixture;\n\npublic class Widget {}\n"
    )
    ticket_id = tickets.open_ticket(conn, worktree_path=str(worktree))
    ticket = record.get(conn, "ticket", ticket_id)
    stage_run_id = run_ledger.open_stage_run(conn, ticket_id=ticket_id, stage="S4")

    task = {"id": 1, "validation_recipe": "fixture_compile", "validation_args": {}}
    outcome, failure_kind = S4._validate_task(conn, ticket, stage_run_id, task, runs_dir=tmp_path)

    assert outcome == "pass", failure_kind
    exit_json = (
        tmp_path / "tickets" / str(ticket_id) / "runs" / str(stage_run_id)
        / "sandbox" / "1" / "fixture_compile" / "results" / "exit.json"
    )
    assert json.loads(exit_json.read_text())["os_policy"] is True


def test_must_reject_a_task_validation_recipe_returning_without_an_applied_os_policy(tmp_path, monkeypatch):
    """Once `_validate_task` routes through `launcher.launch`, a launch that comes back
    without an applied Seatbelt profile is the same control defect `recipes.run` already
    refuses for an S5 build recipe (`test_must_reject_a_build_result_without_policy_or_integrity_proof`
    in `test_recipes.py`) -- never a silently accepted pass."""
    from runner import launcher

    conn = connect(tmp_path / "factory.sqlite")
    worktree = tmp_path / "worktree"
    (worktree / "src" / "main" / "java" / "com" / "fixture").mkdir(parents=True)
    ticket_id = tickets.open_ticket(conn, worktree_path=str(worktree))
    ticket = record.get(conn, "ticket", ticket_id)
    stage_run_id = run_ledger.open_stage_run(conn, ticket_id=ticket_id, stage="S4")

    class _StubLaunched:
        os_policy_applied = False
        integrity = type("_Integrity", (), {"ok": True, "violations": ()})()
        stdout_text = ""
        stderr_text = ""
        timed_out = False
        exit_code = 0

    monkeypatch.setattr(launcher, "launch", lambda **_: _StubLaunched())

    task = {"id": 1, "validation_recipe": "fixture_compile", "validation_args": {}}
    outcome, failure_kind = S4._validate_task(conn, ticket, stage_run_id, task, runs_dir=tmp_path)

    assert outcome == "fail"
    assert failure_kind == "recipe_binding"


# No ambient credential is visible inside a non-agent (build) sandbox.

def test_no_ambient_credential_is_visible_from_inside_a_build_sandbox(tmp_path):
    payload = launch_probe(
        tmp_path, FIXTURES_DIR / "credentials_build" / "probe.py", role="build", stage="S5",
        copy_dir=tmp_path / "copy", build_dir=tmp_path / "build", scratch_dir=tmp_path / "scratch",
        cache_dir=tmp_path / "cache",
    )
    assert payload == {"attempted": True, "refused": True}


# A push attempt is refused from inside any sandbox.

def test_must_reject_git_push_from_inside_an_s4_sandbox(tmp_path):
    """Even from a fully writable worktree mount, a push fails: the clone's push URL is disabled
    and the profile admits no network beyond the loopback proxy."""
    repo = _tiny_pushless_repo(tmp_path / "repo")
    payload = launch_probe(
        tmp_path, FIXTURES_DIR / "git_push" / "probe.py", role="agent", stage="S4",
        ticket_dir=tmp_path / "ticket", worktree_path=repo, extra_argv=(str(repo),),
    )
    assert payload == {"attempted": True, "refused": True}


def test_must_reject_git_push_from_inside_a_build_sandbox(tmp_path):
    repo = _tiny_pushless_repo(tmp_path / "repo")
    payload = launch_probe(
        tmp_path, FIXTURES_DIR / "git_push" / "probe.py", role="build", stage="S5",
        copy_dir=repo, build_dir=tmp_path / "build", scratch_dir=tmp_path / "scratch",
        cache_dir=tmp_path / "cache", extra_argv=(str(repo),),
    )
    assert payload == {"attempted": True, "refused": True}


# The resolved tool set is written to the record before the child ever launches.

def test_stage_run_tool_allowlist_is_set_before_launcher_launch_is_ever_called(tmp_path, monkeypatch):
    entry = _resolved_entry(tmp_path, "S1", "light")
    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = tickets.open_ticket(conn)
    ticket = record.get(conn, "ticket", ticket_id)

    from runner import launcher

    seen: dict = {}
    real_launch = launcher.launch

    def _capturing_launch(*args, **kwargs):
        row = conn.execute(
            "SELECT tool_allowlist FROM stage_run WHERE ticket_id = ? ORDER BY id DESC LIMIT 1", (ticket_id,)
        ).fetchone()
        seen["tool_allowlist"] = row["tool_allowlist"] if row else None
        return real_launch(*args, **kwargs)

    monkeypatch.setattr(launcher, "launch", _capturing_launch)

    result = cursor_sdk.invoke(
        conn, ticket=ticket, stage="S1", tier="light", entry=entry, runs_dir=tmp_path / "runs",
        runtime_path=_fixture_runtime_path(tmp_path), sandbox_path=ADAPTER_FIXTURES_DIR / "sandbox.yaml",
    )

    assert result.outcome == "pass"
    assert seen["tool_allowlist"] is not None, "the row must carry a tool_allowlist before launch is ever called"
    assert json.loads(seen["tool_allowlist"]) == list(entry.tool_allowlist)
