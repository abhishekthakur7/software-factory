"""`python3 -m runner.gate`: the adoption record, the eval-directory walk, then the test suite,
each read from local git history alone.

Every case builds its own temp git repository from a real copy of the
committed `factory/` tree with a freshly regenerated manifest, and always
points `--tests` at a small temp directory it builds itself -- the gate is
never run here over the real `runner/tests/`, which would make this test
file recurse into the very suite it is part of.
"""
import os
import shutil
import subprocess
import sys

from runner import gate, manifest
from runner.paths import FACTORY_DIR, REPO_ROOT

REFRESH_SCRIPT = REPO_ROOT / "tools" / "refresh_manifest.py"

_COMMIT_ENV = {
    "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@example.invalid",
}


def _git(args, cwd):
    return subprocess.run(
        ["git", "-c", "commit.gpgsign=false", *args], cwd=cwd, env={**os.environ, **_COMMIT_ENV},
        capture_output=True, text=True, check=True,
    )


def _refresh_manifest(repo):
    result = subprocess.run(
        [sys.executable, str(REFRESH_SCRIPT), str(repo)], capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr


def _build_gated_repo(tmp_path):
    """A temp git repo whose `factory/` is a real copy of the committed tree, manifest
    freshly regenerated to match, committed clean."""
    repo = tmp_path / "repo"
    shutil.copytree(FACTORY_DIR, repo / "factory")
    _refresh_manifest(repo)
    _git(["init", "-q"], cwd=repo)
    _git(["checkout", "-q", "-b", "main"], cwd=repo)
    _git(["add", "-A"], cwd=repo)
    _git(["commit", "-q", "-m", "init"], cwd=repo)
    return repo


def _write_tests_dir(tmp_path, *, passing: bool, stem: str):
    # Every call within this file shares one pytest process, and `gate.main`
    # collects each temp directory through a fresh `pytest.main()` of its
    # own -- a repeated basename (`test_probe.py`) collides in pytest's
    # module cache across those nested runs, so each case's probe file
    # needs a name no other case in this file also uses.
    tests_dir = tmp_path / f"tests_{stem}"
    tests_dir.mkdir()
    body = "assert True" if passing else "assert False"
    (tests_dir / f"test_probe_{stem}.py").write_text(f"def test_probe_{stem}():\n    {body}\n")
    return tests_dir


def test_editing_a_factory_file_and_recommitting_with_a_refreshed_manifest_changes_the_hash(tmp_path):
    repo = _build_gated_repo(tmp_path)
    hash_before = manifest.current_hash(repo)

    (repo / "factory" / "rubrics" / "context_gathering.md").write_text(
        (repo / "factory" / "rubrics" / "context_gathering.md").read_text() + "\n<!-- edited -->\n"
    )
    _refresh_manifest(repo)
    _git(["add", "-A"], cwd=repo)
    _git(["commit", "-q", "-m", "edit"], cwd=repo)

    hash_after = manifest.current_hash(repo)
    assert hash_after != hash_before


def test_the_gate_passes_over_a_clean_committed_repo_and_a_passing_temp_tests_dir(tmp_path):
    repo = _build_gated_repo(tmp_path)
    tests_dir = _write_tests_dir(tmp_path, passing=True, stem="clean")
    rc = gate.main(["--root", str(repo), "--tests", str(tests_dir)])
    assert rc == 0


def test_the_gate_exits_non_zero_over_a_failing_temp_tests_dir(tmp_path):
    repo = _build_gated_repo(tmp_path)
    tests_dir = _write_tests_dir(tmp_path, passing=False, stem="failing")
    rc = gate.main(["--root", str(repo), "--tests", str(tests_dir)])
    assert rc != 0


def test_must_reject_a_dirty_uncommitted_factory_edit(tmp_path):
    """must-reject: an uncommitted edit to `factory/manifest.yaml` itself -- the one file the
    adoption record's hash is actually computed from -- fails the gate before any other step runs."""
    repo = _build_gated_repo(tmp_path)
    manifest_path = repo / "factory" / "manifest.yaml"
    manifest_path.write_text(manifest_path.read_text() + "\n# uncommitted local edit\n")
    tests_dir = _write_tests_dir(tmp_path, passing=True, stem="dirty")

    rc = gate.main(["--root", str(repo), "--tests", str(tests_dir)])
    assert rc != 0


def test_gate_module_source_names_no_fetch_or_remote_call():
    source = (REPO_ROOT / "runner" / "gate.py").read_text().lower()
    assert "fetch" not in source
    assert "remote" not in source


def test_the_gate_makes_no_network_call_only_a_read_only_git_log(tmp_path, monkeypatch):
    """A monkeypatched `subprocess.run` refuses any `git` verb but `log`; the gate still
    completes, proving that is the only git call it issues itself."""
    repo = _build_gated_repo(tmp_path)
    tests_dir = _write_tests_dir(tmp_path, passing=True, stem="network")
    real_run = subprocess.run

    def guarded_run(cmd, *args, **kwargs):
        if isinstance(cmd, (list, tuple)) and cmd and cmd[0] == "git":
            verb = cmd[3] if len(cmd) > 3 and cmd[1] == "-C" else cmd[1]
            if verb != "log":
                raise AssertionError(f"gate issued a non-read-only git verb: {verb!r} ({cmd})")
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", guarded_run)
    rc = gate.main(["--root", str(repo), "--tests", str(tests_dir)])
    assert rc == 0
