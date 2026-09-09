"""Required adoption mechanics cannot be bypassed by a reduced test selection (R-F-14)."""
import shutil
import subprocess
import sys

import pytest
import yaml

from runner import evals, gate
from runner.paths import FACTORY_DIR, REPO_ROOT
from runner.tests.test_gate import _build_gated_repo, _git, _refresh_manifest, _write_tests_dir


@pytest.mark.parametrize("name", evals.REQUIRED_MECHANICS)
def test_required_fixture_is_registered_with_failure_modes(name):
    """R-F-14: the completeness walk includes each required mechanism and target failure mode."""
    directory = FACTORY_DIR / "evals" / name
    assert directory in evals.expected_eval_dirs()
    evals.check(directory)


@pytest.mark.parametrize("defect", ["missing", "empty", "unowned", "unredacted", "missing_case", "no_failure_modes"])
def test_must_reject_an_incomplete_required_eval_directory(tmp_path, defect):
    """R-F-14: each required case must be present, owned and reviewed before execution."""
    directory = tmp_path / "sandbox/copy-disposal"
    shutil.copytree(FACTORY_DIR / "evals/sandbox/copy-disposal", directory)
    spec_path = directory / "eval.yaml"
    spec = yaml.safe_load(spec_path.read_text())
    if defect == "missing":
        shutil.rmtree(directory)
    elif defect == "empty":
        spec["cases"] = []
    elif defect == "unowned":
        spec.pop("owner")
    elif defect == "unredacted":
        spec["cases"][0]["source"] = "real_ticket_export"
    elif defect == "missing_case":
        spec["cases"].append({"name": "missing", "fixture": "fixtures/absent"})
    else:
        spec.pop("failure_modes")
    if directory.exists():
        spec_path.write_text(yaml.safe_dump(spec))
    with pytest.raises(evals.EvalDirectoryError):
        evals.check(directory)


@pytest.mark.parametrize("name", evals.REQUIRED_MECHANICS)
def test_must_fail_gate_process_for_a_seeded_failing_required_fixture(tmp_path, name):
    """R-F-14: a valid, registered but failing fixture defeats an otherwise passing reduced suite."""
    repo = _build_gated_repo(tmp_path)
    directory = repo / "factory/evals" / name
    spec_path = directory / "eval.yaml"
    spec = yaml.safe_load(spec_path.read_text())
    if name == "sandbox/escape":
        spec["cases"][0]["expect"] = "ok"
        spec_path.write_text(yaml.safe_dump(spec))
    elif name == "sandbox/copy-disposal":
        (directory / spec["cases"][0]["fixture"]).write_text("expected_disposed: false\n")
    else:
        fixture = directory / spec["cases"][0]["fixture"]
        seed = yaml.safe_load(fixture.read_text())
        seed["rows"].append({"table": "incident_observation", "fields": {"ticket_id": 999999}})
        fixture.write_text(yaml.safe_dump(seed))
    _refresh_manifest(repo)
    _git(["add", "-A"], cwd=repo)
    _git(["commit", "-q", "-m", "Seed failing required fixture"], cwd=repo)
    tests = _write_tests_dir(tmp_path, passing=True, stem="required")
    result = subprocess.run(
        [sys.executable, "-m", "runner.gate", "--root", str(repo), "--tests", str(tests), "--close"],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    assert result.returncode != 0, result.stdout
    assert "eval directories: ok" in result.stdout, result.stdout
    assert "tests: FAIL" in result.stdout, result.stdout
    assert not (repo / "runs/adoption").exists()


def test_must_reject_a_versioned_mechanism_change_without_a_matching_fixture(tmp_path):
    """R-F-14: code-only adoption cannot omit the fixture for the affected mechanism."""
    repo = _build_gated_repo(tmp_path)
    path = repo / "runner/sandbox/copies.py"
    path.parent.mkdir(parents=True)
    path.write_text("changed implementation\n")
    _git(["add", "-A"], cwd=repo)
    _git(["commit", "-q", "-m", "Change copy mechanism"], cwd=repo)
    with pytest.raises(evals.EvalDirectoryError, match="copy-disposal"):
        gate.check_fixture_changes(repo)

    directory = repo / "factory/evals/sandbox/copy-disposal"
    with (directory / "eval.yaml").open("a") as stream:
        stream.write("\n# Revalidated disposal failure modes.\n")
    with (directory / "fixtures/recipes.yaml").open("a") as stream:
        stream.write("\n# Updated recipe replay coverage.\n")
    _git(["add", "-A"], cwd=repo)
    _git(["commit", "-q", "--amend", "--no-edit"], cwd=repo)
    gate.check_fixture_changes(repo)


def test_must_reject_a_mechanism_change_hidden_by_an_unrelated_followup_commit(tmp_path):
    """R-F-14: a later commit cannot hide an earlier missing regression fixture."""
    repo = _build_gated_repo(tmp_path)
    path = repo / "runner/sandbox/copies.py"
    path.parent.mkdir(parents=True)
    path.write_text("changed implementation\n")
    _git(["add", "-A"], cwd=repo)
    _git(["commit", "-q", "-m", "Change copy mechanism"], cwd=repo)
    (repo / "README.md").write_text("unrelated documentation\n")
    _git(["add", "-A"], cwd=repo)
    _git(["commit", "-q", "-m", "Update documentation"], cwd=repo)
    with pytest.raises(evals.EvalDirectoryError, match="copy-disposal"):
        gate.check_fixture_changes(repo)
