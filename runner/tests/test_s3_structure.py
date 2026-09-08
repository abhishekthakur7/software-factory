"""The general artefact structure check (R-I-12) and the S3 driver's readiness/ordering rules.

`runner.checks.artefact_structure.check` is exercised two ways: directly,
against hand-built and eval-fixture text, for every rule the plan carries
(R-S3-14, R-S3-18, R-S3-19, R-S3-21); and through the real S3 driver, for
the two rules only a live run can pin -- `handoff_ready`'s place in the
call order and the byte-identity between what it wrote and what got
registered.
"""
import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml

from runner import artefact_registry, artefacts, git_trees, manifest, record, recipes
from runner.checks import artefact_structure
from runner.db import connect
from runner.fs import write_text
from runner.paths import FACTORY_DIR
from runner.stages import run_stage

FIXTURES = Path(__file__).parent / "fixtures" / "s3"
CRITERIA_TEXT = (FIXTURES / "criteria.md").read_text()

EVAL_DIR = FACTORY_DIR / "evals" / "agents" / "S3"
EVAL_SPEC = yaml.safe_load((EVAL_DIR / "eval.yaml").read_text())
CATALOGUE = recipes.load_catalogue()
TIER = "standard"
LIMITS = yaml.safe_load((FACTORY_DIR / "config" / "tiers.yaml").read_text())["length_limits"]

PLAN_OK_CASES = [c for c in EVAL_SPEC["cases"] if c.get("expect") == "plan_structural_ok"]
PLAN_REJECT_CASES = [c for c in EVAL_SPEC["cases"] if c.get("expect") == "plan_structural_reject"]
assert PLAN_OK_CASES and PLAN_REJECT_CASES


def _check(kind: str, text: str, **kwargs) -> list[artefact_structure.Finding]:
    kwargs.setdefault("tier", TIER)
    kwargs.setdefault("criteria_text", CRITERIA_TEXT)
    kwargs.setdefault("catalogue", CATALOGUE)
    kwargs.setdefault("limits", LIMITS)
    return artefact_structure.check(kind, text, **kwargs)


# --- every fixed section must be present, for every kind (R-I-12) ---

@pytest.mark.parametrize("kind", ["brief", "criteria", "plan"])
def test_must_reject_a_version_missing_its_fixed_produces_section_list(kind):
    """R-I-12: a version with only the first fixed section is rejected for missing the rest."""
    first_section = artefacts.SECTIONS[kind][0]
    text = f"## {first_section}\n\nsome content.\n"
    findings = artefact_structure.check(kind, text)
    assert any(f.rule == "missing_section" for f in findings)


def test_must_reject_a_packet_fixture_missing_a_listed_section():
    """R-I-12: the packet kind's stipulated placeholder section list (Summary, Evidence,
    Test summary, Approvers) is not the real S6 content -- it stands in until that ticket lands."""
    assert artefacts.SECTIONS["packet"] == ("Summary", "Evidence", "Test summary", "Approvers")
    text = "## Summary\n\nprose.\n\n## Evidence\n\nprose.\n\n## Approvers\n\nprose.\n"
    findings = artefact_structure.check("packet", text)
    assert any(f.rule == "missing_section" and f.detail == "Test summary" for f in findings)


# --- the plan's own eval-fixture cases, one rule per case (R-I-12/R-S3-14/R-S3-18/R-S3-19) ---

@pytest.mark.parametrize("case", PLAN_OK_CASES, ids=[c["name"] for c in PLAN_OK_CASES])
def test_ok_plan_fixture_passes_the_structure_check(case):
    text = (EVAL_DIR / case["fixture"] / "out" / "plan.md").read_text()
    assert _check("plan", text) == []


@pytest.mark.parametrize("case", PLAN_REJECT_CASES, ids=[c["name"] for c in PLAN_REJECT_CASES])
def test_plan_fixture_rejected_for_its_named_rule(case):
    """R-S3-14/R-S3-18/R-S3-19: each fixture carries exactly one deliberate defect and the
    check reports it by name (missing column, free shell, unregistered recipe, prose-only
    task, dangling AC-n, unserved criterion, unflagged task, both ceilings, first-page order)."""
    text = (EVAL_DIR / case["fixture"] / "out" / "plan.md").read_text()
    findings = _check("plan", text)
    assert findings
    assert any(f.rule == case["rule"] for f in findings), f"expected {case['rule']!r} in {findings}"


# --- pending answer exemption (R-I-12) ---

def test_pending_section_is_exempt_only_when_pending_allowed():
    text = "## Ticket summary\n\npending answer\n\n" + "".join(
        f"## {name}\n\nprose.\n" for name in artefacts.SECTIONS["brief"][1:]
    )
    blocked_rerun = artefact_structure.check("brief", text, pending_allowed=True)
    assert not any(f.rule in ("pending_section", "empty_section") for f in blocked_rerun)

    fresh_run = artefact_structure.check("brief", text, pending_allowed=False)
    assert any(f.rule == "pending_section" and f.detail == "Ticket summary" for f in fresh_run)


# --- handoff_ready writes every condition key's row (R-S3-21) ---

HANDOFF_READY = FACTORY_DIR / "scripts" / "tools" / "handoff_ready"
HANDOFF_EVAL_DIR = FACTORY_DIR / "evals" / "scripts" / "tools" / "handoff_ready"
HANDOFF_SPEC = yaml.safe_load((HANDOFF_EVAL_DIR / "eval.yaml").read_text())


@pytest.mark.parametrize("case", HANDOFF_SPEC["cases"], ids=[c["name"] for c in HANDOFF_SPEC["cases"]])
def test_handoff_ready_writes_a_row_for_every_condition_key(case):
    fixture = HANDOFF_EVAL_DIR / case["fixture"]
    argv = [
        str(HANDOFF_READY), "--plan", str(fixture / "plan.md"), "--criteria", str(fixture / "criteria.md"),
        "--brief", str(fixture / "brief.md"), "--questions", str(fixture / "questions.json"),
        "--assumptions", str(fixture / "assumptions.json"), "--risk-map", str(fixture / "risk_map.json"),
        "--reviewer-set", str(fixture / "reviewer_set.json"), "--tier", case["tier"],
        "--tiers-config", str(FACTORY_DIR / "config" / "tiers.yaml"),
    ]
    for condition, waiver_id in case["waivers"].items():
        argv += ["--waiver", f"{condition}={waiver_id}"]
    result = subprocess.run(argv, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr

    rows = artefacts.parse(result.stdout).section("Readiness").table()
    assert {row["condition"] for row in rows} == set(artefacts.READINESS_CONDITIONS)
    for row in rows:
        assert row["status"] == case["expect"][row["condition"]]
        assert row["hash"], f"{row['condition']} carries no hash"


# --- risk_map: churn, ownership concentration, and size, attached as a plan input (R-S3-11) ---

RISK_MAP = FACTORY_DIR / "scripts" / "checks" / "risk_map"
RISK_MAP_EVAL_DIR = FACTORY_DIR / "evals" / "scripts" / "checks" / "risk_map"
RISK_MAP_SPEC = yaml.safe_load((RISK_MAP_EVAL_DIR / "eval.yaml").read_text())


def _churn_repo(tmp_path):
    """`a.txt`: two commits from one author, thirteen bytes at HEAD; `b.txt`: one commit,
    six bytes -- matching `fixtures/churn/expected.json` exactly (see that fixture's eval.yaml
    comment for why the repository is built here instead of committed)."""
    repo = tmp_path / "churn-repo"
    repo.mkdir()
    _git(["init", "-q"], repo)
    _git(["checkout", "-q", "-b", "main"], repo)
    (repo / "a.txt").write_text("hello\n")
    (repo / "b.txt").write_text("world\n")
    _git(["add", "-A"], repo)
    _git(["commit", "-q", "-m", "init"], repo)
    (repo / "a.txt").write_text("hello\nhello2\n")
    _git(["commit", "-qam", "touch a"], repo)
    return repo


@pytest.mark.parametrize("case", RISK_MAP_SPEC["cases"], ids=[c["name"] for c in RISK_MAP_SPEC["cases"]])
def test_risk_map_scores_and_names_candidates_from_a_real_repository(tmp_path, case):
    fixture = RISK_MAP_EVAL_DIR / case["fixture"]
    repo = _churn_repo(tmp_path)
    result = subprocess.run(
        [
            str(RISK_MAP), "--checkout", str(repo), "--branch", case["branch"],
            "--candidates", str(fixture / "candidates.txt"), "--months", str(case["months"]),
            "--min-share", str(case["min_share"]),
        ],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    expected = json.loads((RISK_MAP_EVAL_DIR / case["expected"]).read_text())
    assert json.loads(result.stdout) == expected


# --- missing/pending readiness rows fail the structure check (R-S3-21) ---

def _ok_plan_text() -> str:
    return (EVAL_DIR / "fixtures" / "ok" / "out" / "plan.md").read_text()


def test_must_reject_a_plan_carrying_a_pending_readiness_row():
    text = _ok_plan_text().replace(
        "| restatement_agreed | pass | criteria | cccccccc |  | both criteria agreed |",
        "| restatement_agreed | pending | criteria | cccccccc |  | not yet agreed |",
    )
    findings = _check("plan", text)
    assert any(f.rule == "pending_readiness_row" and f.detail == "restatement_agreed" for f in findings)


def test_must_reject_a_plan_missing_the_readiness_table():
    text = _ok_plan_text().replace(
        artefacts.parse(_ok_plan_text()).section("Readiness").body, "the readiness table was never written",
    )
    findings = _check("plan", text)
    assert any(f.rule in ("missing_table", "empty_section") for f in findings)


def test_a_blind_spot_readiness_row_with_no_waiver_id_counts_as_pending():
    """R-S3-21: a blind_spot row names the waiver that permits it; without one it is exactly
    as unresolved as a pending row and fails the same way."""
    text = _ok_plan_text().replace(
        "| impact_evidence | pass | brief | bbbbbbbb |  | every row covered |",
        "| impact_evidence | blind_spot | brief | bbbbbbbb |  | unknown coverage, no waiver |",
    )
    findings = _check("plan", text)
    assert any(f.rule == "pending_readiness_row" and "impact_evidence" in f.detail for f in findings)


# --- driver-level ordering and hash binding (R-S3-21), through a real run ---

_COMMIT_ENV = {
    "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@example.invalid",
}


def _git(args, cwd):
    subprocess.run(["git", "-c", "commit.gpgsign=false", *args], cwd=cwd, env={**os.environ, **_COMMIT_ENV}, check=True, capture_output=True, text=True)


def _source_repo(tmp_path):
    repo = tmp_path / "source-repo"
    repo.mkdir()
    _git(["init", "-q"], repo)
    _git(["checkout", "-q", "-b", "main"], repo)
    (repo / "README.md").write_text("seed\n")
    _git(["add", "-A"], repo)
    _git(["commit", "-q", "-m", "init"], repo)
    return repo


_S3_BRIEF_TEXT = """## Touched area candidates

| path | reason |
|---|---|
| README.md | the file this ticket's plan touches |

## Linked sources

| source | date |
|---|---|
| JIRA-123 | 2026-01-01 |

## Impact evidence

| direction | dependency | method | source | mapping | owner | coverage | blind_spots |
|---|---|---|---|---|---|---|---|
| outbound | svc-x | import_scan | pom.xml | mapping.yaml | abhishek | authoritative | none |
"""


@pytest.fixture
def planning_ticket(tmp_path, monkeypatch):
    """A ticket in `planning`, with a real worktree, manifest pin, and brief/criteria, ready to run S3."""
    conn = connect(tmp_path / "factory.sqlite")
    source = _source_repo(tmp_path)
    ticket_id = record.insert(
        conn, "ticket", state="intake", opened_at=record.now(), factory_manifest_hash=manifest.current_hash(),
        tier_final="light",
    )
    trees = git_trees.clone_for_ticket(conn, ticket_id, source_checkout=source, target_branch="main", runs_dir=tmp_path)
    git_trees.record_head(conn, ticket_id, trees.worktree)
    record.update(conn, "ticket", ticket_id, state="planning")

    brief_path = tmp_path / "brief.md"
    write_text(brief_path, _S3_BRIEF_TEXT)
    artefact_registry.register(conn, ticket_id=ticket_id, kind="brief", path=brief_path)
    artefact_registry.register(conn, ticket_id=ticket_id, kind="criteria", path=FIXTURES / "criteria.md")

    monkeypatch.setenv("FIXTURE_ADAPTER_OUT_DIR", str(EVAL_DIR / "fixtures" / "ok" / "out"))
    return conn, ticket_id, tmp_path


def test_handoff_ready_runs_after_the_agent_invocation_and_before_registration(planning_ticket):
    """R-S3-21: the registered `plan` version already carries the readiness table handoff_ready
    derived, and that derivation happened strictly after the agent's own child invocation --
    proven by the child's raw `out/plan.md` still holding the fixture's placeholder hashes
    while the registered version carries the real ones handoff_ready computed on top of it."""
    conn, ticket_id, tmp_path = planning_ticket
    outcome = run_stage(conn, ticket_id, "S3", runs_dir=tmp_path)
    assert outcome == "pass"

    child_run = conn.execute(
        "SELECT id FROM stage_run WHERE ticket_id = ? AND stage = 'S3' AND parent_run_id IS NOT NULL "
        "ORDER BY id ASC LIMIT 1",
        (ticket_id,),
    ).fetchone()
    raw_out = tmp_path / "tickets" / str(ticket_id) / "runs" / str(child_run["id"]) / "out" / "plan.md"
    raw_rows = artefacts.parse(raw_out.read_text()).section("Readiness").table()
    assert {row["hash"] for row in raw_rows} == {"cccccccc", "qqqqqqqq", "bbbbbbbb", "rrrrrrrr", "ssssssss", "vvvvvvvv"}

    plan_artefact = artefact_registry.latest(conn, ticket_id, "plan")
    final_rows = artefacts.parse(Path(plan_artefact["path"]).read_text()).section("Readiness").table()
    assert {row["condition"] for row in final_rows} == set(artefacts.READINESS_CONDITIONS)
    assert not any(row["status"] == "pending" for row in final_rows)
    # None of the placeholder hashes survive: handoff_ready overwrote every row after the
    # agent's own child invocation had already ended and left this exact file behind.
    assert not ({row["hash"] for row in final_rows} & {row["hash"] for row in raw_rows})


def test_registered_plan_hash_binds_the_readiness_rows_source_hashes(planning_ticket):
    """R-S3-21: the registered plan's own hash is the exact file handoff_ready produced, and
    every readiness row's hash column is that condition's own source artefact hash, not the plan's."""
    conn, ticket_id, tmp_path = planning_ticket
    outcome = run_stage(conn, ticket_id, "S3", runs_dir=tmp_path)
    assert outcome == "pass"

    plan_artefact = artefact_registry.latest(conn, ticket_id, "plan")
    plan_bytes = Path(plan_artefact["path"]).read_bytes()
    assert plan_artefact["hash"] == hashlib.sha256(plan_bytes).hexdigest()

    criteria_artefact = artefact_registry.latest(conn, ticket_id, "criteria")
    brief_artefact = artefact_registry.latest(conn, ticket_id, "brief")
    rows = artefacts.parse(plan_bytes.decode()).section("Readiness").table()
    by_condition = {row["condition"]: row for row in rows}
    assert by_condition["restatement_agreed"]["hash"] == criteria_artefact["hash"]
    assert by_condition["linked_sources"]["hash"] == brief_artefact["hash"]
    # The plan's own version is bound by the artefact row's hash, not repeated inside itself.
    assert plan_artefact["hash"] not in {row["hash"] for row in rows}
