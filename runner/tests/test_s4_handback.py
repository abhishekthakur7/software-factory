"""S4's hand-back (R-S4-2): `record_handback` through the real driver, walking
`factory/evals/agents/S4/`'s `handback_*` eval cases end to end -- a real
worktree, a real invocation through the fixture adapter, and the write path
onto `ticket.branch`/`head_sha`/`worktree_path` and the `deviation` table.
"""
import os
import subprocess
from pathlib import Path

import pytest
import yaml

from runner import artefact_registry, binding, git_trees, manifest, record, run_ledger, schema
from runner.db import connect
from runner.paths import FACTORY_DIR
from runner.stages import run_stage

EVAL_DIR = FACTORY_DIR / "evals" / "agents" / "S4"
EVAL_SPEC = yaml.safe_load((EVAL_DIR / "eval.yaml").read_text())
HANDBACK_OK_CASES = [c for c in EVAL_SPEC["cases"] if c.get("expect") == "handback_ok"]
HANDBACK_REJECT_CASES = [c for c in EVAL_SPEC["cases"] if c.get("expect") == "handback_reject"]
assert HANDBACK_OK_CASES and HANDBACK_REJECT_CASES

FIXTURES = Path(__file__).parent / "fixtures" / "s4_handoff"
PLAN_TEXT = (FIXTURES / "plan.md").read_text()
CRITERIA_TEXT = (Path(__file__).parent / "fixtures" / "s3" / "criteria.md").read_text()

_COMMIT_ENV = {
    "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@example.invalid",
}


def _git(args, cwd, env=None):
    full_env = {**os.environ, **env} if env else None
    return subprocess.run(
        ["git", "-c", "commit.gpgsign=false", *args], cwd=cwd, env=full_env,
        capture_output=True, text=True, check=True,
    )


def _source_repo(tmp_path) -> Path:
    """A one-commit repository carrying the `Widget.java` the `ok`/`empty_deviations` fixtures edit."""
    repo = tmp_path / "source-repo"
    repo.mkdir()
    _git(["init", "-q"], cwd=repo)
    _git(["checkout", "-q", "-b", "main"], cwd=repo)
    src = repo / "src" / "main" / "java" / "com" / "fixture"
    src.mkdir(parents=True)
    (src / "Widget.java").write_text(
        "package com.fixture;\n\npublic class Widget {\n    public int compute(int x) {\n        return x * 2;\n    }\n}\n"
    )
    (repo / "README.md").write_text("seed\n")
    _git(["add", "-A"], cwd=repo)
    _git(["commit", "-q", "-m", "init"], cwd=repo, env=_COMMIT_ENV)
    return repo


def _ready_ticket(conn, tmp_path, **ticket_fields) -> int:
    """A ticket in `implementing` with a real worktree, a bound plan tuple, and a registered plan/criteria."""
    ticket_id = record.insert(
        conn, "ticket", state="implementing", opened_at=record.now(),
        service="fixture-project", ticket_type="small_feature", tier_provisional="standard",
        factory_manifest_hash=manifest.current_hash(), **ticket_fields,
    )
    source = _source_repo(tmp_path)
    trees = git_trees.clone_for_ticket(conn, ticket_id, source_checkout=source, target_branch="main", runs_dir=tmp_path)
    git_trees.record_head(conn, ticket_id, trees.worktree)
    record.insert(
        conn, "evidence_tuple", kind="plan", ticket_id=ticket_id, created_at=record.now(),
        base_sha=trees.base_sha, target_base_sha=trees.base_sha, content_hash=f"plan-subject-{ticket_id}",
        plan_hash="plan-hash-1", criteria_hash="criteria-hash-1",
        current_assumption_set_hash="assumption-set-hash-1", semantic_checklist_hash="checklist-hash-1",
    )
    plan_path = tmp_path / f"plan-{ticket_id}.md"
    plan_path.write_text(PLAN_TEXT)
    artefact_registry.register(conn, ticket_id=ticket_id, kind="plan", path=plan_path)
    criteria_path = tmp_path / f"criteria-{ticket_id}.md"
    criteria_path.write_text(CRITERIA_TEXT)
    artefact_registry.register(conn, ticket_id=ticket_id, kind="criteria", path=criteria_path)
    return ticket_id


def _run_s4(conn, ticket_id, tmp_path, case) -> str:
    os.environ["FIXTURE_ADAPTER_OUT_DIR"] = str(EVAL_DIR / case["fixture"] / "out")
    worktree_fixture = EVAL_DIR / case["fixture"] / "worktree"
    if worktree_fixture.is_dir():
        os.environ["FIXTURE_ADAPTER_WORKTREE_DIR"] = str(worktree_fixture)
    try:
        return run_stage(conn, ticket_id, "S4", runs_dir=tmp_path)
    finally:
        del os.environ["FIXTURE_ADAPTER_OUT_DIR"]
        os.environ.pop("FIXTURE_ADAPTER_WORKTREE_DIR", None)


# a non-empty, schema-conformant deviation set moves the ticket to `checks` (R-S4-2)


def test_a_conformant_nonempty_handback_moves_the_ticket_to_checks_with_its_fields_recorded(tmp_path):
    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = _ready_ticket(conn, tmp_path)
    before = record.get(conn, "ticket", ticket_id)

    outcome = _run_s4(conn, ticket_id, tmp_path, next(c for c in HANDBACK_OK_CASES if c["name"] == "handback_ok"))

    assert outcome == "pass"
    after = record.get(conn, "ticket", ticket_id)
    assert after["state"] == "checks"
    assert after["branch"] == before["branch"]
    assert after["worktree_path"] == before["worktree_path"]
    assert after["head_sha"] != before["head_sha"]

    rows = conn.execute("SELECT * FROM deviation WHERE ticket_id = ? ORDER BY id", (ticket_id,)).fetchall()
    assert len(rows) == 2
    kinds = {row["kind"] for row in rows}
    assert kinds == {"judgment", "error"}
    judgment_row = next(row for row in rows if row["kind"] == "judgment")
    assert judgment_row["contract_change"] == 0
    for row in rows:
        assert set(dict(row).keys()) >= {"id", "ticket_id", "stage_run_id", "plan_item", "plan_said", "agent_did", "why", "kind", "contract_change"}


# an empty deviation set is written as an explicit, canonically hashed empty set (R-S4-2)


def test_a_handback_with_no_deviations_records_the_canonical_empty_set_hash(tmp_path):
    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = _ready_ticket(conn, tmp_path)
    case = next(c for c in HANDBACK_OK_CASES if c["name"] == "handback_empty_deviations")

    outcome = _run_s4(conn, ticket_id, tmp_path, case)

    assert outcome == "pass"
    assert record.get(conn, "ticket", ticket_id)["state"] == "checks"
    assert conn.execute("SELECT COUNT(*) FROM deviation WHERE ticket_id = ?", (ticket_id,)).fetchone()[0] == 0

    check = conn.execute(
        "SELECT * FROM check_result WHERE check_name = 'handback_structure' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert check["result"] == "pass"
    import json
    summary = json.loads(check["summary"])
    assert summary["count"] == 0
    assert summary["deviation_set_hash"] == binding.set_hash([])
    assert summary["deviation_set_hash"] == binding.deviation_set_hash(conn, ticket_id)


# a missing or malformed deviation set is a structural failure (R-S4-2)


@pytest.mark.parametrize("case", HANDBACK_REJECT_CASES, ids=[c["name"] for c in HANDBACK_REJECT_CASES])
def test_a_missing_or_malformed_handback_is_a_structural_failure_that_never_reaches_checks(tmp_path, case):
    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = _ready_ticket(conn, tmp_path)

    outcome = _run_s4(conn, ticket_id, tmp_path, case)

    assert outcome == "fail"
    ticket = record.get(conn, "ticket", ticket_id)
    assert ticket["state"] == "implementing"
    assert conn.execute("SELECT COUNT(*) FROM deviation WHERE ticket_id = ?", (ticket_id,)).fetchone()[0] == 0

    stage_run = conn.execute(
        "SELECT * FROM stage_run WHERE ticket_id = ? AND stage = 'S4' AND parent_run_id IS NULL ORDER BY id DESC LIMIT 1",
        (ticket_id,),
    ).fetchone()
    assert stage_run["outcome"] == "fail"
    assert stage_run["failure_kind"] == "structural"

    # No red_check item, and nothing waivable: the ordinary fresh rerun applies instead.
    red_checks = conn.execute(
        "SELECT COUNT(*) FROM queue_item WHERE ticket_id = ? AND kind = 'red_check'", (ticket_id,)
    ).fetchone()[0]
    assert red_checks == 0


# hand-back never touches pr_url/pr_identity, and creates no external_write (R-S4-2)


def test_handback_never_creates_a_pull_request_or_touches_pr_fields(tmp_path):
    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = _ready_ticket(conn, tmp_path)
    record.update(conn, "ticket", ticket_id, pr_url="https://example.invalid/pr/7", pr_identity="7")

    outcome = _run_s4(conn, ticket_id, tmp_path, next(c for c in HANDBACK_OK_CASES if c["name"] == "handback_ok"))

    assert outcome == "pass"
    after = record.get(conn, "ticket", ticket_id)
    assert after["pr_url"] == "https://example.invalid/pr/7"
    assert after["pr_identity"] == "7"
    assert conn.execute("SELECT COUNT(*) FROM external_write WHERE ticket_id = ?", (ticket_id,)).fetchone()[0] == 0


def test_a_first_cycle_handback_creates_no_pull_request(tmp_path):
    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = _ready_ticket(conn, tmp_path)
    assert record.get(conn, "ticket", ticket_id)["pr_url"] is None

    outcome = _run_s4(conn, ticket_id, tmp_path, next(c for c in HANDBACK_OK_CASES if c["name"] == "handback_ok"))

    assert outcome == "pass"
    after = record.get(conn, "ticket", ticket_id)
    assert after["pr_url"] is None
    assert after["pr_identity"] is None
    assert conn.execute("SELECT COUNT(*) FROM external_write WHERE ticket_id = ?", (ticket_id,)).fetchone()[0] == 0


# `git_trees.commit_worktree` itself: a task that changes nothing leaves HEAD untouched


def test_a_commit_with_no_changes_leaves_head_unchanged(tmp_path):
    """Directly against `commit_worktree`: an unmodified worktree is not an error, and produces no new commit."""
    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = record.insert(conn, "ticket", state="implementing", opened_at=record.now())
    source = _source_repo(tmp_path)
    trees = git_trees.clone_for_ticket(conn, ticket_id, source_checkout=source, target_branch="main", runs_dir=tmp_path)
    before = trees.base_sha
    after = git_trees.commit_worktree(trees.worktree, "no-op hand-back")
    assert after == before
