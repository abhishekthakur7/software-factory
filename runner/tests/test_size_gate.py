"""`factory/scripts/checks/size_gate`, driven through its eval.yaml fixtures.

One tier threshold applied twice: at planning over the plan's own size estimate
(`--plan` alone), and standing in for checks over a real diff (`--plan --diff`),
excluding lockfiles and `project.yaml`'s generated paths either way.
"""
import json
import subprocess

import pytest
import yaml

from runner.paths import FACTORY_DIR

SCRIPT = FACTORY_DIR / "scripts" / "checks" / "size_gate"
EVAL_DIR = FACTORY_DIR / "evals" / "scripts" / "checks" / "size_gate"
EVAL_SPEC = yaml.safe_load((EVAL_DIR / "eval.yaml").read_text())
TIERS_CONFIG = FACTORY_DIR / "config" / "tiers.yaml"
PROJECT_CONFIG = FACTORY_DIR / "config" / "project.yaml"


def _run(case: dict) -> subprocess.CompletedProcess:
    fixture = EVAL_DIR / case["fixture"]
    argv = [str(SCRIPT), "--plan", str(fixture / "plan.md"), "--tier", case["tier"], "--tiers-config", str(TIERS_CONFIG)]
    if case["mode"] == "diff":
        argv += ["--diff", str(fixture / "diff.txt"), "--project-config", str(PROJECT_CONFIG)]
    return subprocess.run(argv, capture_output=True, text=True)


@pytest.mark.parametrize("case", EVAL_SPEC["cases"], ids=[c["name"] for c in EVAL_SPEC["cases"]])
def test_size_gate_conformance_case(case):
    """Over-threshold-with-no-justification fails at both planning's plan-estimate
    mode and the checks stand-in diff mode; a justification present on the approved plan passes
    either way and says so."""
    result = _run(case)
    payload = json.loads(result.stdout)
    assert payload["result"] == case["expect"]
    assert result.returncode == (0 if case["expect"] == "pass" else 1)
    if payload["lines"] > payload["threshold"]:
        # every fixture here is deliberately over threshold; the verdict
        # then turns entirely on whether the plan's Size table justifies it.
        assert ("justified" in payload["reason"]) == (case["expect"] == "pass")


def test_plan_mode_reads_the_estimate_from_the_plans_own_size_table():
    """The plan-mode number is the Size table's estimated_lines, not a diff count."""
    over = next(c for c in EVAL_SPEC["cases"] if c["name"] == "plan_over_threshold")
    payload = json.loads(_run(over).stdout)
    assert payload["lines"] == 500


def test_diff_mode_excludes_lockfiles_and_generated_paths():
    """The seeded fixture diff's lockfile hunk (uv.lock) never counts toward the total."""
    over = next(c for c in EVAL_SPEC["cases"] if c["name"] == "diff_over_threshold")
    diff_text = (EVAL_DIR / over["fixture"] / "diff.txt").read_text()
    assert "uv.lock" in diff_text  # the fixture really does carry an excluded hunk
    payload = json.loads(_run(over).stdout)
    assert payload["lines"] == 350  # only the non-lockfile file's added+removed lines
