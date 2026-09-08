"""`factory/scripts/tools/packet_assemble`, driven through its `eval.yaml` fixtures (R-S6-1).

The packet opens with tuple identity and freshness, then one evidence
table naming every element's source artefact and hash, in charter order;
an epistemic entry (an impact, declaration, or behaviour-limitation check)
never renders `pass`, whatever its seeded status.
"""
import json
import re
import subprocess

import pytest
import yaml

from runner.paths import FACTORY_DIR

SCRIPT = FACTORY_DIR / "scripts" / "tools" / "packet_assemble"
EVAL_DIR = FACTORY_DIR / "evals" / "scripts" / "tools" / "packet_assemble"
EVAL_SPEC = yaml.safe_load((EVAL_DIR / "eval.yaml").read_text())

_PACKET_SECTION_ORDER = (
    "Identity and freshness", "Evidence", "Intent", "Scrutiny", "Decisions", "Not touched", "Risk map",
    "Deviations", "Assumptions", "Test summary", "Blind spots", "Diff",
)


def _run(case: dict, tmp_path) -> tuple[subprocess.CompletedProcess, "Path"]:
    fixture = EVAL_DIR / case["fixture"]
    inputs = json.loads((fixture / "packet_inputs.json").read_text())
    if inputs.get("diff_path"):
        inputs["diff_path"] = str(fixture / inputs["diff_path"])
    inputs_path = tmp_path / "packet_inputs.json"
    inputs_path.write_text(json.dumps(inputs))
    out_path = tmp_path / "packet.md"
    completed = subprocess.run(
        [str(SCRIPT), "--inputs", str(inputs_path), "--out", str(out_path)], capture_output=True, text=True,
    )
    return completed, out_path


@pytest.mark.parametrize("case", EVAL_SPEC["cases"], ids=[c["name"] for c in EVAL_SPEC["cases"]])
def test_packet_assemble_conformance_case(case, tmp_path):
    completed, out_path = _run(case, tmp_path)
    if case["expect"] == "ok":
        assert completed.returncode == 0, completed.stderr
        assert out_path.is_file()
    else:
        assert completed.returncode != 0
        assert completed.stderr.strip()
        assert not out_path.is_file()


def test_the_full_packet_opens_with_identity_and_freshness_then_one_evidence_table_in_charter_order(tmp_path):
    """R-S6-1: the packet's sections appear, in order, exactly as the charter's
    review-packet paragraph fixes them."""
    case = next(c for c in EVAL_SPEC["cases"] if c["name"] == "full_ordered_packet")
    completed, out_path = _run(case, tmp_path)
    assert completed.returncode == 0, completed.stderr
    text = out_path.read_text()
    titles = re.findall(r"^## (.+)$", text, re.MULTILINE)
    assert titles == list(_PACKET_SECTION_ORDER)


def test_every_evidence_row_names_its_source_artefact_and_its_hash(tmp_path):
    """R-S6-1: every element in the evidence table carries a non-empty
    `source_artefact` cell, and a `hash` cell wherever the input row named one -- a fix
    round's own `stage_run` carries no content hash of its own to cite."""
    case = next(c for c in EVAL_SPEC["cases"] if c["name"] == "full_ordered_packet")
    completed, out_path = _run(case, tmp_path)
    assert completed.returncode == 0, completed.stderr
    text = out_path.read_text()
    evidence = text.split("## Evidence")[1].split("## Intent")[0]
    rows = [line for line in evidence.splitlines() if line.startswith("|") and "---" not in line][1:]
    assert rows
    for row in rows:
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        element, kind, source_artefact, row_hash = cells[0], cells[1], cells[2], cells[3]
        assert source_artefact, f"{kind} row for {element!r} names no source artefact"
        if kind != "fix_round":
            assert row_hash, f"{kind} row for {element!r} names no hash"


def test_the_evidence_table_lists_every_check_fix_round_base_test_change_readiness_approval_and_waiver(tmp_path):
    """R-S6-1: the evidence table's rows cover every blocking check, fix round,
    base-test change, readiness row, approval record, and waiver the inputs named."""
    case = next(c for c in EVAL_SPEC["cases"] if c["name"] == "full_ordered_packet")
    completed, out_path = _run(case, tmp_path)
    assert completed.returncode == 0, completed.stderr
    text = out_path.read_text()
    evidence = text.split("## Evidence")[1].split("## Intent")[0]
    kinds = {line.split("|")[2].strip() for line in evidence.splitlines() if line.startswith("|") and "---" not in line}
    kinds.discard("kind")  # the header row's own cell
    assert kinds == {"check", "fix_round", "base_test_change", "readiness", "approval", "waiver"}


def test_an_impact_entry_seeded_pass_is_relabelled_blind_spot_never_pass(tmp_path):
    """R-S6-1: a seeded impact, declaration, or behaviour-limitation entry
    is labelled `blind_spot` in the evidence table, never `pass`."""
    case = next(c for c in EVAL_SPEC["cases"] if c["name"] == "impact_entry_relabelled_blind_spot")
    completed, out_path = _run(case, tmp_path)
    assert completed.returncode == 0, completed.stderr
    text = out_path.read_text()
    evidence = text.split("## Evidence")[1].split("## Intent")[0]
    row = next(line for line in evidence.splitlines() if "impact_scan" in line)
    cells = [cell.strip() for cell in row.strip("|").split("|")]
    assert cells[4] == "blind_spot"
    assert "pass" not in cells


def test_malformed_inputs_exit_non_zero_with_a_message(tmp_path):
    """`packet_assemble` refuses a `packet_inputs.json` missing required keys, non-zero with a message."""
    case = next(c for c in EVAL_SPEC["cases"] if c["name"] == "malformed_inputs_missing_keys")
    completed, out_path = _run(case, tmp_path)
    assert completed.returncode != 0
    assert completed.stderr.strip()
    assert not out_path.is_file()
