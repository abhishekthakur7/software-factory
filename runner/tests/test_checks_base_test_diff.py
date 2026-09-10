"""`factory/scripts/checks/base_test_diff`, driven through its eval.yaml fixtures.

A test that exists at base and is edited, deleted, renamed (its old
identity simply stops appearing at head), or excluded through a narrower
head recipe glob is unplanned -- and a blocking failure -- unless the
approved plan's `Test strategy` table names it with action `change` or
`remove` and a non-empty `criteria` cell. The both-views rerun and the
`deviation` row a later ticket adds extend this file; it covers the four
detections alone.
"""
import json
import subprocess

import pytest
import yaml

from runner.paths import FACTORY_DIR

SCRIPT = FACTORY_DIR / "scripts" / "checks" / "base_test_diff"
EVAL_DIR = FACTORY_DIR / "evals" / "scripts" / "checks" / "base_test_diff"
EVAL_SPEC = yaml.safe_load((EVAL_DIR / "eval.yaml").read_text())


def _run(case: dict) -> subprocess.CompletedProcess:
    fixture = EVAL_DIR / case["fixture"]
    argv = [
        str(SCRIPT),
        "--base", str(fixture / "base"),
        "--head", str(fixture / "head"),
        "--globs", case["globs"],
        "--plan", str(fixture / "plan.md"),
        "--tests-base", str(fixture / "tests_base.json"),
        "--tests-head", str(fixture / "tests_head.json"),
    ]
    if case.get("globs_base"):
        argv += ["--globs-base", case["globs_base"]]
    if case.get("tests_head_in_base"):
        argv += ["--tests-head-in-base", str(fixture / "tests_head_in_base.json")]
    return subprocess.run(argv, capture_output=True, text=True)


@pytest.mark.parametrize("case", EVAL_SPEC["cases"], ids=[c["name"] for c in EVAL_SPEC["cases"]])
def test_base_test_diff_conformance_case(case):
    """An unplanned base-test edit, delete, rename or configuration
    exclusion blocks; a plan-named change with a non-empty criteria cell passes."""
    result = _run(case)
    payload = json.loads(result.stdout)
    assert payload["result"] == case["expect"]
    assert result.returncode == 0


def test_edited_base_test_is_reported_with_reason_edited():
    case = next(c for c in EVAL_SPEC["cases"] if c["name"] == "base_test_edited_and_unplanned")
    payload = json.loads(_run(case).stdout)
    assert payload["changed_files"] == [{"path": "src/test/java/com/fixture/WidgetTest.java", "reason": "edited"}]
    assert "src/test/java/com/fixture/WidgetTest.java" in payload["unplanned"]


def test_deleted_base_test_is_reported_with_reason_deleted():
    case = next(c for c in EVAL_SPEC["cases"] if c["name"] == "base_test_deleted_and_unplanned")
    payload = json.loads(_run(case).stdout)
    assert payload["changed_files"] == [{"path": "src/test/java/com/fixture/WidgetTest.java", "reason": "deleted"}]


def test_renamed_base_test_surfaces_as_a_missing_identity():
    """A rename has no distinct file-path signal of its own; it shows up because
    the old class's test identity stops appearing in the head test run."""
    case = next(c for c in EVAL_SPEC["cases"] if c["name"] == "base_test_renamed_and_unplanned")
    payload = json.loads(_run(case).stdout)
    assert payload["missing_identities"] == ["com.fixture.WidgetTest#computes"]
    assert "com.fixture.WidgetTest#computes" in payload["unplanned"]


def test_excluded_base_test_survives_on_disk_but_drops_out_of_the_narrower_head_glob():
    """The file is byte-for-byte identical at head; only the recipe's glob narrowed,
    which `--globs-base` is what lets the script tell apart from "never covered"."""
    case = next(c for c in EVAL_SPEC["cases"] if c["name"] == "base_test_excluded_through_narrower_head_globs")
    payload = json.loads(_run(case).stdout)
    assert payload["changed_files"] == [{"path": "src/test/java/com/fixture/OrderUnitTest.java", "reason": "excluded"}]


def test_planned_change_with_criteria_is_not_unplanned():
    """A `Test strategy` row naming the test with action `change` and a non-empty
    `criteria` cell keeps the edit out of `unplanned` and the result passes."""
    case = next(c for c in EVAL_SPEC["cases"] if c["name"] == "base_test_change_named_in_test_strategy")
    payload = json.loads(_run(case).stdout)
    assert payload["unplanned"] == []
    assert payload["planned"] == [{"test": "src/test/java/com/fixture/WidgetTest.java", "action": "change", "names": ["AC-3"]}]


def test_both_views_rerun_records_pass_when_the_head_test_fails_at_base_and_passes_at_head():
    """A planned change naming an `AC-n` criterion whose head-version test fails
    when rerun against base production code -- a real regression caught -- records `verdict:
    pass` for that entry, and the check's own overall result is `pass`."""
    case = next(c for c in EVAL_SPEC["cases"] if c["name"] == "both_views_rerun_proves_the_change")
    result = _run(case)
    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["result"] == "pass"
    assert payload["planned"] == [
        {"test": "src/test/java/com/fixture/WidgetTest.java", "action": "change", "names": ["AC-3"], "verdict": "pass"}
    ]


def test_both_views_rerun_records_a_blind_spot_when_the_head_test_passes_at_base_too():
    """The same planned change, but its head-version test also passes when rerun
    against base -- it proves nothing about the change -- records `verdict: blind_spot`, and
    the check's own overall result is `blind_spot`, not `fail`."""
    case = next(c for c in EVAL_SPEC["cases"] if c["name"] == "both_views_rerun_proves_nothing")
    result = _run(case)
    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["result"] == "blind_spot"
    assert payload["planned"][0]["verdict"] == "blind_spot"


def test_a_no_behaviour_change_task_row_is_exempt_from_the_both_views_rerun():
    """A planned `change` row naming a `no_behaviour_change` task instead of an
    `AC-n` criterion is `exempt` -- never rerun -- and still passes."""
    case = next(c for c in EVAL_SPEC["cases"] if c["name"] == "no_behaviour_change_task_is_exempt_from_the_rerun")
    result = _run(case)
    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["result"] == "pass"
    assert payload["planned"][0]["verdict"] == "exempt"
