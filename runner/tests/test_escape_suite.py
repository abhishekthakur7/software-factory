"""The escape suite: every category `factory/evals/sandbox/escape/eval.yaml` names, run for real on this host.

`os_policy.available()` is checked at import time, not inside a test: a
host where `sandbox-exec` cannot actually run the agent profile fails this
whole module's collection outright rather than letting every test skip
quietly, since a skip here would silently stop proving the one thing this
milestone exists to prove (R-I-14). Every probe is copied out of
`factory/evals/sandbox/escape/fixtures/<category>/probe.py` into this
run's own `tmp/`, the one path both the agent and the build profile grant
read access to without also granting it to `factory/` itself, then run
through `runner.launcher.launch` under the real, committed profiles --
never a test double.

"""
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from runner.paths import REPO_ROOT
from runner.sandbox import copies, os_policy
from runner.tests.support import launch_probe

EVAL_DIR = REPO_ROOT / "factory" / "evals" / "sandbox" / "escape"

if not os_policy.available():
    pytest.fail(
        "sandbox-exec cannot run the agent profile on this host; the escape suite fails "
        "outright rather than skip",
        pytrace=False,
    )

_CASES = {case["name"]: case for case in yaml.safe_load((EVAL_DIR / "eval.yaml").read_text())["cases"]}


def _git(args, cwd):
    return subprocess.run(
        ["git", "-c", "commit.gpgsign=false", *args], cwd=cwd, capture_output=True, text=True, check=True,
    )


def _tiny_repo(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    _git(["init", "-q"], cwd=root)
    _git(["checkout", "-q", "-b", "main"], cwd=root)
    (root / "README.md").write_text("seed\n")
    git_env = {
        **os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid",
    }
    subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "add", "-A"], cwd=root, capture_output=True, text=True, check=True,
    )
    subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "commit", "-q", "-m", "seed"], cwd=root,
        env=git_env, capture_output=True, text=True, check=True,
    )
    return root


def _run_probe(tmp_path: Path, category: str, **kwargs) -> dict:
    """Launch `category`'s probe for real, under the real committed profiles; return its parsed stdout JSON."""
    return launch_probe(tmp_path, EVAL_DIR / "fixtures" / category / "probe.py", **kwargs)


def _assert_matches_expect(payload: dict, category: str) -> None:
    expect = _CASES[category]["expect"]
    assert payload["attempted"] is True
    assert payload["refused"] == (expect == "reject"), f"{category}: expected refused={expect == 'reject'}, got {payload}"


def test_paths_probe_reading_the_host_home_directory_is_refused(tmp_path):
    payload = _run_probe(tmp_path, "paths", role="agent", ticket_dir=tmp_path / "ticket")
    _assert_matches_expect(payload, "paths")


def test_symlinks_probe_following_a_link_to_outside_every_mount_is_refused(tmp_path):
    ticket_dir = tmp_path / "ticket"
    ticket_dir.mkdir()
    outside_target = tmp_path / "outside" / "secret.txt"
    outside_target.parent.mkdir(parents=True)
    outside_target.write_text("outside content\n")
    link_path = ticket_dir / "escape_link"
    link_path.symlink_to(outside_target)
    payload = _run_probe(tmp_path, "symlinks", role="agent", ticket_dir=ticket_dir, extra_argv=(str(link_path),))
    _assert_matches_expect(payload, "symlinks")


def test_subprocesses_probe_execing_ls_under_the_build_profile_is_refused(tmp_path):
    copy_dir = _tiny_repo(tmp_path / "copy")
    payload = _run_probe(
        tmp_path, "subprocesses", role="build", stage="S5",
        copy_dir=copy_dir, build_dir=tmp_path / "build", scratch_dir=tmp_path / "scratch", cache_dir=tmp_path / "cache",
    )
    _assert_matches_expect(payload, "subprocesses")


def test_environment_probe_never_sees_an_unallowlisted_name(tmp_path):
    env_source = {"PATH": os.environ.get("PATH", ""), "ESCAPE_CANARY_SECRET": "leak-if-present"}
    payload = _run_probe(tmp_path, "environment", role="agent", ticket_dir=tmp_path / "ticket", env_source=env_source)
    _assert_matches_expect(payload, "environment")


def test_sockets_probe_opening_the_docker_socket_is_refused(tmp_path):
    payload = _run_probe(tmp_path, "sockets", role="agent", ticket_dir=tmp_path / "ticket")
    _assert_matches_expect(payload, "sockets")


def test_network_probe_connecting_outside_the_proxy_allowlist_is_refused(tmp_path):
    payload = _run_probe(tmp_path, "network", role="agent", ticket_dir=tmp_path / "ticket")
    _assert_matches_expect(payload, "network")


def test_mounts_probe_reading_an_unregistered_sibling_checkout_is_refused(tmp_path):
    ticket_dir = tmp_path / "ticket"
    ticket_dir.mkdir()
    sibling = tmp_path / "sibling-checkout" / "file.txt"
    sibling.parent.mkdir(parents=True)
    sibling.write_text("someone else's ticket\n")
    payload = _run_probe(tmp_path, "mounts", role="agent", ticket_dir=ticket_dir, extra_argv=(str(sibling),))
    _assert_matches_expect(payload, "mounts")


def test_base_head_isolation_probe_a_base_write_never_reaches_head(tmp_path):
    source = _tiny_repo(tmp_path / "source")
    provisioned = copies.provision(
        ticket_id=1, stage_run_id=1, base_checkout=source, head_checkout=source, runs_dir=tmp_path / "runs",
    )
    payload = _run_probe(
        tmp_path, "base-head-isolation", role="build", stage="S5",
        copy_dir=provisioned.base, build_dir=provisioned.base / "target",
        scratch_dir=provisioned.base / "scratch", cache_dir=provisioned.base / "cache",
        extra_argv=(str(provisioned.base), str(provisioned.head)),
    )
    _assert_matches_expect(payload, "base-head-isolation")
    assert (provisioned.base / "escape_marker.txt").exists()
    assert not (provisioned.head / "escape_marker.txt").exists()
    copies.dispose(provisioned)


def test_source_immutability_probe_writing_the_immutable_checkout_is_refused(tmp_path):
    source = _tiny_repo(tmp_path / "source")
    provisioned = copies.provision(
        ticket_id=1, stage_run_id=1, base_checkout=source, head_checkout=source, runs_dir=tmp_path / "runs",
    )
    payload = _run_probe(
        tmp_path, "source-immutability", role="build", stage="S5",
        copy_dir=provisioned.base, build_dir=provisioned.base / "target",
        scratch_dir=provisioned.base / "scratch", cache_dir=provisioned.base / "cache",
        extra_argv=(str(source),),
    )
    _assert_matches_expect(payload, "source-immutability")
    assert not (source / "escape_write.txt").exists()
    copies.dispose(provisioned)


def test_copy_disposal_probe_neither_copy_exists_once_disposed(tmp_path):
    source = _tiny_repo(tmp_path / "source")
    provisioned = copies.provision(
        ticket_id=1, stage_run_id=1, base_checkout=source, head_checkout=source, runs_dir=tmp_path / "runs",
    )
    payload = _run_probe(
        tmp_path, "copy-disposal", role="build", stage="S5",
        copy_dir=provisioned.base, build_dir=provisioned.base / "target",
        scratch_dir=provisioned.base / "scratch", cache_dir=provisioned.base / "cache",
        extra_argv=(str(provisioned.base),),
    )
    _assert_matches_expect(payload, "copy-disposal")
    assert (provisioned.base / "copy_disposal_marker.txt").exists()
    copies.dispose(provisioned)
    assert not provisioned.base.exists()
    assert not provisioned.head.exists()


def test_credentials_probe_no_ambient_credential_material_ever_surfaces(tmp_path):
    payload = _run_probe(tmp_path, "credentials", role="agent", ticket_dir=tmp_path / "ticket")
    _assert_matches_expect(payload, "credentials")


def test_ok_control_case_reads_back_its_own_out(tmp_path):
    """The one positive control every real category is judged against: an ordinary write-then-read still works."""
    payload = _run_probe(tmp_path, "ok", role="agent", ticket_dir=tmp_path / "ticket")
    _assert_matches_expect(payload, "ok")


def test_eval_directory_names_every_category_this_module_exercises():
    """R-I-14 criterion 36: the suite covers every category the eval directory names, none silently dropped."""
    exercised = {
        "paths", "symlinks", "subprocesses", "environment", "sockets", "network", "mounts",
        "base-head-isolation", "source-immutability", "copy-disposal", "credentials", "ok",
    }
    assert set(_CASES) == exercised
