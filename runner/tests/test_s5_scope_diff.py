"""`factory/scripts/checks/scope_diff`, driven through its eval.yaml fixtures (R-S5-4).

Every file the diff touches must land inside the approved plan's own
`Scope and discretion` table -- either a literal `touch`/`create`/`delete`
path or a `discretion` row's glob -- with no model, network, git or
checkout involved: the diff text and the plan text alone.
"""
import ast
import json
import subprocess

import pytest
import yaml

from runner.paths import FACTORY_DIR

SCRIPT = FACTORY_DIR / "scripts" / "checks" / "scope_diff"
EVAL_DIR = FACTORY_DIR / "evals" / "scripts" / "checks" / "scope_diff"
EVAL_SPEC = yaml.safe_load((EVAL_DIR / "eval.yaml").read_text())


def _run(case: dict) -> subprocess.CompletedProcess:
    fixture = EVAL_DIR / case["fixture"]
    argv = [str(SCRIPT), "--diff", str(fixture / "diff.txt"), "--plan", str(fixture / "plan.md")]
    return subprocess.run(argv, capture_output=True, text=True)


@pytest.mark.parametrize("case", EVAL_SPEC["cases"], ids=[c["name"] for c in EVAL_SPEC["cases"]])
def test_scope_diff_conformance_case(case):
    """R-S5-4: a diff wholly inside the plan's scope table and discretion globs passes;
    a file outside both is a blocking failure listing the out-of-scope paths (criteria 1, 2)."""
    result = _run(case)
    payload = json.loads(result.stdout)
    assert payload["result"] == case["expect"]
    assert result.returncode == 0  # a failed check is still a clean run, never a usage error


def test_out_of_scope_case_lists_the_offending_path():
    """Criterion 2: the failure names the file that fell outside scope, not just a bare fail."""
    case = next(c for c in EVAL_SPEC["cases"] if c["name"] == "file_outside_scope_and_discretion")
    payload = json.loads(_run(case).stdout)
    assert payload["out_of_scope"] == ["src/main/java/com/fixture/Unrelated.java"]
    assert "src/main/java/com/fixture/Widget.java" in payload["in_scope"]


def test_scope_diff_imports_no_network_subprocess_or_model_client_and_takes_no_checkout_argument():
    """Criterion 3: the script computes its result from the diff and plan text alone.

    A static check over the script's own source -- no `subprocess`, socket,
    `requests` or similar import, and no `--base`/`--head`/checkout-shaped
    argument in its argparse definition -- so the "no model, no network, no
    git" claim in R-S5-4 is something this test could actually catch a
    regression against, not just documentation.
    """
    source = SCRIPT.read_text()
    tree = ast.parse(source)
    imported_modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module.split(".")[0])
    forbidden = {"subprocess", "socket", "requests", "urllib", "http", "runner"}
    assert not (imported_modules & forbidden), imported_modules & forbidden
    assert "--base" not in source and "--head" not in source and "--checkout" not in source
