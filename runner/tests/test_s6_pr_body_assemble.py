"""`factory/scripts/tools/pr_body_assemble`, driven through its `eval.yaml` fixtures (R-S6-1).

The `pr_body` carries the packet's own narrative and evidence links but
never the literal branch diff -- GitHub's own diff view is the pull
request's diff surface.
"""
import json
import subprocess

import pytest
import yaml

from runner.paths import FACTORY_DIR

PACKET_SCRIPT = FACTORY_DIR / "scripts" / "tools" / "packet_assemble"
PR_BODY_SCRIPT = FACTORY_DIR / "scripts" / "tools" / "pr_body_assemble"
EVAL_DIR = FACTORY_DIR / "evals" / "scripts" / "tools" / "pr_body_assemble"
EVAL_SPEC = yaml.safe_load((EVAL_DIR / "eval.yaml").read_text())


def _rewritten_inputs(case: dict, tmp_path):
    fixture = EVAL_DIR / case["fixture"]
    inputs = json.loads((fixture / "packet_inputs.json").read_text())
    if inputs.get("diff_path"):
        inputs["diff_path"] = str(fixture / inputs["diff_path"])
    tmp_path.mkdir(parents=True, exist_ok=True)
    inputs_path = tmp_path / "packet_inputs.json"
    inputs_path.write_text(json.dumps(inputs))
    return inputs_path


def _run(case: dict, tmp_path) -> tuple[subprocess.CompletedProcess, "Path"]:
    inputs_path = _rewritten_inputs(case, tmp_path)
    out_path = tmp_path / "pr_body.md"
    completed = subprocess.run(
        [str(PR_BODY_SCRIPT), "--inputs", str(inputs_path), "--out", str(out_path)], capture_output=True, text=True,
    )
    return completed, out_path


@pytest.mark.parametrize("case", EVAL_SPEC["cases"], ids=[c["name"] for c in EVAL_SPEC["cases"]])
def test_pr_body_assemble_conformance_case(case, tmp_path):
    completed, out_path = _run(case, tmp_path)
    if case["expect"] == "ok":
        assert completed.returncode == 0, completed.stderr
        assert out_path.is_file()
    else:
        assert completed.returncode != 0
        assert completed.stderr.strip()
        assert not out_path.is_file()


def test_the_pr_body_carries_the_packets_narrative_and_evidence_but_never_the_literal_diff(tmp_path):
    """R-S6-1 criterion 4: `pr_body_assemble` produces the same narrative and evidence links
    as `packet_assemble` over the identical inputs, but its own `Diff` section and the exact
    diff text never appear."""
    case = next(c for c in EVAL_SPEC["cases"] if c["name"] == "full_ordered_pr_body")

    packet_inputs_path = _rewritten_inputs(case, tmp_path / "packet")
    packet_out = tmp_path / "packet.md"
    packet_completed = subprocess.run(
        [str(PACKET_SCRIPT), "--inputs", str(packet_inputs_path), "--out", str(packet_out)],
        capture_output=True, text=True,
    )
    assert packet_completed.returncode == 0, packet_completed.stderr

    pr_body_completed, pr_body_out = _run(case, tmp_path / "pr_body")
    assert pr_body_completed.returncode == 0, pr_body_completed.stderr

    packet_text = packet_out.read_text()
    pr_body_text = pr_body_out.read_text()

    assert "## Diff" not in pr_body_text
    diff_line = "if (n < 0) {"
    assert diff_line in packet_text
    assert diff_line not in pr_body_text

    for section in ("Identity and freshness", "Evidence", "Intent", "Scrutiny", "Decisions", "Test summary"):
        assert f"## {section}" in pr_body_text

    packet_evidence = packet_text.split("## Evidence")[1].split("## Intent")[0]
    pr_body_evidence = pr_body_text.split("## Evidence")[1].split("## Intent")[0]
    assert packet_evidence == pr_body_evidence
