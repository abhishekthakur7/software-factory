"""T-A-01 criteria 2, 3, 4, 5, 6, R-F-1.

Drives factory/scripts/tools/manifest_hash through the conformance fixtures
named in its eval.yaml, plus the uncommitted-edit and repeat-run behaviours
the ticket asks this file (not a fixture) to exercise.
"""
import hashlib
import shutil
import subprocess

import pytest
import yaml

from runner.paths import FACTORY_DIR, REPO_ROOT

SCRIPT = FACTORY_DIR / "scripts" / "tools" / "manifest_hash"
EVAL_DIR = FACTORY_DIR / "evals" / "scripts" / "tools" / "manifest_hash"
EVAL_SPEC = yaml.safe_load((EVAL_DIR / "eval.yaml").read_text())


def _run(root) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(SCRIPT), "--root", str(root)], capture_output=True, text=True
    )


def _build_repo(tmp_path, fixture_rel: str):
    repo = tmp_path / "repo"
    shutil.copytree(EVAL_DIR / fixture_rel / "factory", repo / "factory")
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=repo, check=True)
    subprocess.run(["git", "add", "factory"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True)
    return repo


OK_CASES = [c for c in EVAL_SPEC["cases"] if c["expect"] == "ok"]
REJECT_CASES = [c for c in EVAL_SPEC["cases"] if c["expect"] == "reject"]
assert OK_CASES and REJECT_CASES, "eval.yaml must define both an ok and a reject case"


@pytest.mark.parametrize("case", OK_CASES, ids=[c["name"] for c in OK_CASES])
def test_manifest_hash_accepts_conformance_case(tmp_path, case):
    """T-A-01 criterion 4, R-F-1."""
    repo = _build_repo(tmp_path, case["fixture"])
    result = _run(repo)
    assert result.returncode == 0, result.stderr
    committed = subprocess.run(
        ["git", "-C", str(repo), "show", "HEAD:factory/manifest.yaml"],
        capture_output=True,
    ).stdout
    assert result.stdout.strip() == hashlib.sha256(committed).hexdigest()


@pytest.mark.parametrize("case", REJECT_CASES, ids=[c["name"] for c in REJECT_CASES])
def test_must_reject_manifest_hash_conformance_case(tmp_path, case):
    """T-A-01 criterion 3, R-F-1."""
    repo = _build_repo(tmp_path, case["fixture"])
    result = _run(repo)
    assert result.returncode == 1
    assert result.stdout.strip() == ""
    assert result.stderr.strip() != ""


def test_repeated_runs_over_an_unchanged_tree_agree(tmp_path):
    """T-A-01 criterion 6, R-F-1."""
    repo = _build_repo(tmp_path, "fixtures/valid")
    first = _run(repo)
    second = _run(repo)
    assert first.returncode == second.returncode == 0
    assert first.stdout == second.stdout


def test_must_reject_uncommitted_manifest_edit(tmp_path):
    """T-A-01 criterion 5, R-F-1."""
    repo = _build_repo(tmp_path, "fixtures/valid")
    manifest = repo / "factory" / "manifest.yaml"
    manifest.write_text(manifest.read_text() + "\n# uncommitted local edit\n")
    result = _run(repo)
    assert result.returncode == 1
    assert result.stdout.strip() == ""


def test_every_real_manifest_entry_has_path_and_content_hash():
    """T-A-01 criterion 2, R-F-1."""
    manifest = yaml.safe_load((FACTORY_DIR / "manifest.yaml").read_text())
    assert manifest["files"], "manifest lists no files"
    for entry in manifest["files"]:
        assert isinstance(entry.get("path"), str) and entry["path"]
        assert isinstance(entry.get("content_hash"), str) and entry["content_hash"]


def _real_manifest_head_bytes():
    result = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "show", "HEAD:factory/manifest.yaml"],
        capture_output=True,
    )
    return result.stdout if result.returncode == 0 else None


@pytest.mark.skipif(
    _real_manifest_head_bytes() is None,
    reason="factory/manifest.yaml is not committed at HEAD yet; T-A-01 adds it in this commit",
)
def test_manifest_hash_over_real_repo_matches_committed_manifest():
    """T-A-01 criteria 4, 6, R-F-1: run against the real repo, not a fixture."""
    committed = _real_manifest_head_bytes()
    result = _run(REPO_ROOT)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == hashlib.sha256(committed).hexdigest()
