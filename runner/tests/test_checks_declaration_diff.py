"""`source_declaration_diff` and `behavior_contract_evidence`, driven through their eval.yaml fixtures.

`source_declaration_diff` extracts public/protected Java declarations at
base and head and blocks on an unplanned add/remove or a declaration the
plan calls unchanged that in fact changed (criteria 4 to 6).
`behavior_contract_evidence` never claims semantic proof -- it only checks
that every contract field and verdict points to test or characterisation
evidence, passing when that holds (criterion 7) and naming a blind spot,
never a fail on its own, for each of the six lax detections it runs
(criterion 8).
"""
import json
import subprocess

import pytest
import yaml

from runner.paths import FACTORY_DIR

DECL_SCRIPT = FACTORY_DIR / "scripts" / "checks" / "source_declaration_diff"
DECL_EVAL_DIR = FACTORY_DIR / "evals" / "scripts" / "checks" / "source_declaration_diff"
DECL_EVAL_SPEC = yaml.safe_load((DECL_EVAL_DIR / "eval.yaml").read_text())

EVIDENCE_SCRIPT = FACTORY_DIR / "scripts" / "checks" / "behavior_contract_evidence"
EVIDENCE_EVAL_DIR = FACTORY_DIR / "evals" / "scripts" / "checks" / "behavior_contract_evidence"
EVIDENCE_EVAL_SPEC = yaml.safe_load((EVIDENCE_EVAL_DIR / "eval.yaml").read_text())


def _run_declaration_diff(case: dict) -> subprocess.CompletedProcess:
    fixture = DECL_EVAL_DIR / case["fixture"]
    argv = [
        str(DECL_SCRIPT),
        "--base", str(fixture / "base"),
        "--head", str(fixture / "head"),
        "--files", str(fixture / "files.txt"),
        "--plan", str(fixture / "plan.md"),
    ]
    return subprocess.run(argv, capture_output=True, text=True)


@pytest.mark.parametrize("case", DECL_EVAL_SPEC["cases"], ids=[c["name"] for c in DECL_EVAL_SPEC["cases"]])
def test_source_declaration_diff_conformance_case(case):
    """An unplanned add/remove or a wrongly-claimed-unchanged
    declaration blocks; a plan that names every declaration passes."""
    result = _run_declaration_diff(case)
    payload = json.loads(result.stdout)
    assert payload["result"] == case["expect"]
    assert result.returncode == 0


def test_added_declaration_not_named_in_contracts_is_listed():
    """Criterion 4: the failure names the added declaration, not just a bare fail."""
    case = next(c for c in DECL_EVAL_SPEC["cases"] if c["name"] == "declaration_added_and_unnamed_in_contracts")
    payload = json.loads(_run_declaration_diff(case).stdout)
    assert [d["name"] for d in payload["added"]] == ["computeTwice(int)"]
    assert [d["name"] for d in payload["unplanned"]] == ["computeTwice(int)"]
    assert payload["removed"] == []


def test_removed_declaration_not_named_in_contracts_is_listed():
    """Criterion 5: the failure names the removed declaration, not just a bare fail."""
    case = next(c for c in DECL_EVAL_SPEC["cases"] if c["name"] == "declaration_removed_and_unnamed_in_contracts")
    payload = json.loads(_run_declaration_diff(case).stdout)
    assert [d["name"] for d in payload["removed"]] == ["computeTwice(int)"]
    assert [d["name"] for d in payload["unplanned"]] == ["computeTwice(int)"]
    assert payload["added"] == []


def test_unchanged_but_changed_declaration_is_the_same_method_not_a_remove_plus_add():
    """Criterion 6: a parameter-list change on an existing method is one `changed`
    finding keyed by method identity, not a spurious remove-plus-add pair."""
    case = next(c for c in DECL_EVAL_SPEC["cases"] if c["name"] == "declaration_marked_unchanged_but_signature_differs")
    payload = json.loads(_run_declaration_diff(case).stdout)
    assert payload["added"] == [] and payload["removed"] == []
    assert [d["name"] for d in payload["changed"]] == ["compute(int,int)"]
    assert [d["name"] for d in payload["unchanged_but_changed"]] == ["compute(int,int)"]


def test_declaration_diff_limitations_state_it_is_a_source_text_extractor():
    """The declared caveat is always present, whatever the fixture: this is regex
    over text, never a compiler with a real symbol table."""
    case = DECL_EVAL_SPEC["cases"][0]
    payload = json.loads(_run_declaration_diff(case).stdout)
    assert "source-text extractor, not a compiler" in payload["limitations"]


# -- behavior_contract_evidence -------------------------------------------------

def _run_evidence(case: dict) -> subprocess.CompletedProcess:
    fixture = EVIDENCE_EVAL_DIR / case["fixture"]
    argv = [
        str(EVIDENCE_SCRIPT),
        "--plan", str(fixture / "plan.md"),
        "--verdicts", str(fixture / "verdicts.json"),
        "--tests-base", str(fixture / "tests_base.json"),
        "--tests-head", str(fixture / "tests_head.json"),
        "--declarations", str(fixture / "declarations.json"),
        "--generated-paths", case.get("generated_paths", ""),
    ]
    return subprocess.run(argv, capture_output=True, text=True)


@pytest.mark.parametrize("case", EVIDENCE_EVAL_SPEC["cases"], ids=[c["name"] for c in EVIDENCE_EVAL_SPEC["cases"]])
def test_behavior_contract_evidence_conformance_case(case):
    """Every contract field and verdict pointing to
    real evidence passes and claims no semantic proof; each of the six lax
    detections names its own blind spot without failing on its own."""
    result = _run_evidence(case)
    payload = json.loads(result.stdout)
    assert payload["result"] == case["expect"]
    assert result.returncode == 0
    assert payload["claims"] == "evidence links only, no semantic proof"


def test_behavior_contract_evidence_pass_case_has_no_blind_spots():
    """Criterion 7: every field and verdict pointing to recorded evidence leaves nothing to flag."""
    case = next(c for c in EVIDENCE_EVAL_SPEC["cases"] if c["name"] == "every_field_and_verdict_has_evidence")
    payload = json.loads(_run_evidence(case).stdout)
    assert payload["blind_spots"] == []


def test_behavior_contract_evidence_names_all_six_blind_spots():
    """Criterion 8: missing grammar/unit, inheritance, reflection, generated API,
    binary compatibility and unchecked behavioural change each produce their own entry."""
    case = next(c for c in EVIDENCE_EVAL_SPEC["cases"] if c["name"] == "six_named_blind_spots")
    payload = json.loads(_run_evidence(case).stdout)
    reasons = {spot["reason"] for spot in payload["blind_spots"]}
    for expected in (
        "missing grammar or unit", "inheritance", "reflection",
        "generated API", "binary compatibility", "unchecked behavioural change",
    ):
        assert any(expected in reason for reason in reasons), (expected, reasons)
    assert payload["result"] == "blind_spot"  # blind spots alone never fail the check on their own
