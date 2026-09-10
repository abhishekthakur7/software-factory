"""`java_compile`, `java_lint`, and `java_test`, driven through their own eval.yaml fixtures.

Each wrapper's exit code is the check's own outcome (unlike the later
scripts that always exit 0 and carry `result` in a printed JSON line):
`expected_exit_codes: [0]` in `command-recipes.yaml` is what makes a
non-zero exit here a failed check to the implementation/checks drivers that call these
scripts. Skips loudly, not silently, when no JDK is on `PATH`.
"""
import json
import shutil
import subprocess

import pytest
import yaml

from runner.paths import FACTORY_DIR

HAS_JAVAC = shutil.which("javac") is not None and shutil.which("java") is not None
SKIP_REASON = "javac/java not on PATH"

COMPILE_SCRIPT = FACTORY_DIR / "scripts" / "checks" / "java_compile"
LINT_SCRIPT = FACTORY_DIR / "scripts" / "checks" / "java_lint"
TEST_SCRIPT = FACTORY_DIR / "scripts" / "checks" / "java_test"

COMPILE_EVAL_DIR = FACTORY_DIR / "evals" / "scripts" / "checks" / "java_compile"
LINT_EVAL_DIR = FACTORY_DIR / "evals" / "scripts" / "checks" / "java_lint"
TEST_EVAL_DIR = FACTORY_DIR / "evals" / "scripts" / "checks" / "java_test"


def _case(eval_dir):
    spec = yaml.safe_load((eval_dir / "eval.yaml").read_text())
    return next(c for c in spec["cases"] if c["name"] == "ok")


@pytest.mark.skipif(not HAS_JAVAC, reason=SKIP_REASON)
def test_java_compile_passes_over_its_two_file_fixture(tmp_path):
    """`java_compile`'s eval directory carries a real, compiling two-file source tree."""
    fixture = COMPILE_EVAL_DIR / _case(COMPILE_EVAL_DIR)["fixture"]
    result = subprocess.run(
        [str(COMPILE_SCRIPT), "--source-root", str(fixture / "src"), "--classpath", "", "--out", str(tmp_path / "out")],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "out" / "com" / "example" / "Adder.class").is_file()


@pytest.mark.skipif(not HAS_JAVAC, reason=SKIP_REASON)
def test_java_lint_passes_over_its_two_file_fixture(tmp_path):
    """`java_lint`'s fixture compiles clean under `-Xlint:all -Werror`, no warnings."""
    fixture = LINT_EVAL_DIR / _case(LINT_EVAL_DIR)["fixture"]
    result = subprocess.run(
        [str(LINT_SCRIPT), "--source-root", str(fixture / "src"), "--classpath", "", "--out", str(tmp_path / "out")],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr.strip() == ""


@pytest.mark.skipif(not HAS_JAVAC, reason=SKIP_REASON)
def test_java_test_runs_its_fixtures_unit_test_and_reports_the_identity_that_ran(tmp_path):
    """`java_test`'s fixture compiles a main class plus a test class and runs it,
    printing the test identity the launcher parses off the final JSON line."""
    fixture = TEST_EVAL_DIR / _case(TEST_EVAL_DIR)["fixture"]
    result = subprocess.run(
        [
            str(TEST_SCRIPT),
            "--level", "unit",
            "--main-root", str(fixture / "main"),
            "--test-root", str(fixture / "test"),
            "--test-glob", str(fixture / "test" / "**" / "*UnitTest.java"),
            "--classpath", "",
            "--out", str(tmp_path / "out"),
        ],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    last_line = result.stdout.strip().splitlines()[-1]
    payload = json.loads(last_line)
    assert payload == {
        "level": "unit",
        "ran": [{"class": "com.example.CalculatorUnitTest", "method": "testAddSumsTwoNumbers"}],
    }


@pytest.mark.skipif(not HAS_JAVAC, reason=SKIP_REASON)
def test_must_reject_java_compile_over_a_source_tree_with_no_java_files(tmp_path):
    """`java_compile` refuses (usage error, not a silent pass) when nothing matches `--source-root`."""
    empty_root = tmp_path / "empty"
    empty_root.mkdir()
    result = subprocess.run(
        [str(COMPILE_SCRIPT), "--source-root", str(empty_root), "--classpath", "", "--out", str(tmp_path / "out")],
        capture_output=True, text=True,
    )
    assert result.returncode != 0
    assert "no .java files" in result.stderr
