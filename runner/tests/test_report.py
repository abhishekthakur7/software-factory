"""Drives `factory/scripts/tools/report` through its `eval.yaml` fixtures,
plus the report's own rules that a fixture walk alone does not pin: the
forbidden-view list, the only-reader scan, and the objective-rule check
that a context measure can never be selected as primary.
"""
import importlib.machinery
import importlib.util
import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from runner import cli, gates, git_trees, record, schema, transitions
from runner.db import connect
from runner.paths import FACTORY_DIR, REPO_ROOT
from runner.stages import run_stage

SCRIPT = FACTORY_DIR / "scripts" / "tools" / "report"
EVAL_DIR = FACTORY_DIR / "evals" / "scripts" / "tools" / "report"
EVAL_SPEC = yaml.safe_load((EVAL_DIR / "eval.yaml").read_text())

OK_CASES = [c for c in EVAL_SPEC["cases"] if c["expect"] == "ok"]
REJECT_CASES = [c for c in EVAL_SPEC["cases"] if c["expect"] == "reject"]
assert OK_CASES and REJECT_CASES, "eval.yaml must define both an ok and a reject case"


def _load_report_module():
    # The script has no `.py` suffix (like `manifest_hash`), so the loader
    # must be named explicitly rather than guessed from the file extension.
    loader = importlib.machinery.SourceFileLoader("factory_report_script", str(SCRIPT))
    spec = importlib.util.spec_from_file_location("factory_report_script", SCRIPT, loader=loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


REPORT = _load_report_module()


def _apply_seed(conn: sqlite3.Connection, seed_path) -> None:
    for row in yaml.safe_load(seed_path.read_text()) or []:
        record.insert(conn, row["table"], **row.get("fields", {}))
    conn.commit()


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


def _source_repo(tmp_path):
    """A trivial one-file git repository on the real project config's target
    branch, so the freshness checks the walk now passes through (the
    plan-review gate and S5 preflight) find a real, matching target head."""
    repo = tmp_path / "source-repo"
    repo.mkdir()
    _git(["init", "-q"], cwd=repo)
    _git(["checkout", "-q", "-b", "main"], cwd=repo)
    (repo / "README.md").write_text("seed\n")
    # A minimal pom so the now-real S1's impact_scan has something to
    # read, and the one file its `plain_ok` fixture's Flags row names.
    (repo / "pom.xml").write_text(
        "<project>\n  <groupId>com.example</groupId>\n  <artifactId>widget</artifactId>\n  <version>1.0.0</version>\n"
        "  <dependencies>\n    <dependency>\n      <groupId>com.fixturevendor</groupId>\n"
        "      <artifactId>strings</artifactId>\n      <version>1.0.0</version>\n    </dependency>\n  </dependencies>\n"
        "</project>\n"
    )
    src = repo / "src" / "main" / "java" / "com" / "example"
    src.mkdir(parents=True)
    (src / "Handler.java").write_text("package com.example;\n\npublic class Handler {\n}\n")
    _git(["add", "-A"], cwd=repo)
    _git(["commit", "-q", "-m", "init"], cwd=repo, env=_COMMIT_ENV)
    return repo


def _build_completed_walk(db_path, tmp_path) -> None:
    """Walk one ticket S0 through `merged` with the real stub stages and
    transitions (see `test_stub_stages.py`), then layer on the rows the
    stage walk alone does not produce so every measure has something to show.
    """
    conn = connect(db_path)
    ticket_id = record.insert(
        conn, "ticket", state="intake", opened_at=record.now(), tier_final="light",
        # A real pilot-eligible pair, since S0's lookups now reject rather
        # than stub-pass an unresolvable service or ticket type.
        service="fixture-project", ticket_type="small_feature",
    )
    run_stage(conn, ticket_id, "S0", runs_dir=tmp_path)
    record.insert(conn, "queue_item", ticket_id=ticket_id, kind="eligibility", action="granted")
    transitions.apply(conn, ticket_id, gates.intake_gate(conn, record.get(conn, "ticket", ticket_id)))
    # `intake_gate` pins the real manifest hash above; the now-real S1
    # also needs a real worktree to run its impact scan over.
    source = _source_repo(tmp_path)
    trees = git_trees.clone_for_ticket(conn, ticket_id, source_checkout=source, target_branch="main", runs_dir=tmp_path)
    git_trees.record_head(conn, ticket_id, trees.worktree)

    os.environ["FIXTURE_ADAPTER_OUT_DIR"] = str(
        FACTORY_DIR / "evals" / "agents" / "S1" / "fixtures" / "plain_ok" / "out"
    )
    try:
        run_stage(conn, ticket_id, "S1", runs_dir=tmp_path)
    finally:
        del os.environ["FIXTURE_ADAPTER_OUT_DIR"]
    run_stage(conn, ticket_id, "S2", runs_dir=tmp_path)
    run_stage(conn, ticket_id, "S3", runs_dir=tmp_path)

    record.insert(
        conn, "evidence_tuple", kind="plan", ticket_id=ticket_id,
        base_sha=trees.base_sha, target_base_sha=trees.base_sha, content_hash="plan_subject_1",
    )
    record.insert(
        conn, "approval_record", ticket_id=ticket_id, gate="plan", subject_hash="plan_subject_1",
        decision="approve", role="engineer", active_attention_bucket="under_2m",
    )
    ticket = record.get(conn, "ticket", ticket_id)
    transitions.apply(
        conn, ticket_id, gates.plan_review_gate(conn, ticket, runs_dir=tmp_path)
    )

    run_stage(conn, ticket_id, "S4", runs_dir=tmp_path)
    s4_run_id = conn.execute(
        "SELECT id FROM stage_run WHERE ticket_id = ? AND stage = 'S4' ORDER BY id DESC LIMIT 1", (ticket_id,)
    ).fetchone()["id"]

    run_stage(conn, ticket_id, "S5", runs_dir=tmp_path)
    run_stage(conn, ticket_id, "S6", runs_dir=tmp_path)
    ticket = record.get(conn, "ticket", ticket_id)
    transitions.apply(conn, ticket_id, gates.checks_gate(conn, ticket))

    record.insert(
        conn, "evidence_tuple", kind="review", ticket_id=ticket_id, content_hash="review_subject_1",
    )
    record.insert(conn, "external_write", ticket_id=ticket_id, operation="pr_create", state="reconciled")
    record.insert(
        conn, "approval_record", ticket_id=ticket_id, gate="review", subject_hash="review_subject_1",
        decision="approve", role="engineer", active_attention_bucket="5_to_15m",
    )
    # The review gate's own receipt-matching rule is pinned by the outbox
    # tests; this walk only needs the ticket to reach pr_opened.
    transitions.apply(conn, ticket_id, "review_quorum_reconciled")

    record.update(conn, "ticket", ticket_id, factory_completed_at=record.now())
    transitions.apply(conn, ticket_id, "merge_recorded")

    record.insert(conn, "tag", ticket_id=ticket_id, event_kind="revision_after_approval", fm_id="FM-01")
    record.insert(conn, "tag", ticket_id=ticket_id, event_kind="escalation", fm_id="FM-02", ref=f"stage_run:{s4_run_id}")
    question_id = record.insert(conn, "question", ticket_id=ticket_id, stage="S2", round=1, default_option=0)
    record.insert(
        conn, "queue_item", ticket_id=ticket_id, stage="S2", tier="light", kind="question",
        ref=f"question:{question_id}", queued_at="2026-01-01T00:00:00", resolved_at="2026-01-01T00:05:00",
        active_attention_bucket="under_2m",
    )
    record.insert(conn, "answer", question_id=question_id, resolution_kind="default_accepted", answered_at="2026-01-01T00:05:00")
    identity_id = record.insert(
        conn, "generated_test", record_kind="identity", ticket_id=ticket_id,
        stage_run_id=s4_run_id, initial_path="t.py", initial_hash="h1",
    )
    record.insert(conn, "generated_test", record_kind="decision", identity_id=identity_id, decision="kept")
    record.insert(conn, "index_use", stage_run_id=s4_run_id, entry_path="docs/x.md", stale=1)
    record.insert(conn, "tool_call", stage_run_id=s4_run_id, seq=1, tool="grep", result_bytes=2048, inline=1)
    conn.commit()
    conn.close()


def _build_db(case: dict, tmp_path) -> Path:
    db_path = tmp_path / "factory.sqlite"
    fixture_dir = EVAL_DIR / case["fixture"]
    seed_path = fixture_dir / "seed.yaml"
    if case["name"] == "completed_walk":
        _build_completed_walk(db_path, tmp_path)
    elif case["expect"] == "reject":
        # A bare file with no schema at all, so every required view is missing.
        sqlite3.connect(str(db_path)).close()
    else:
        conn = connect(db_path)
        _apply_seed(conn, seed_path)
        conn.close()
    return db_path


def _run(db_path, *extra_args) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--db", str(db_path), *extra_args],
        capture_output=True, text=True,
    )


@pytest.mark.parametrize("case", OK_CASES, ids=[c["name"] for c in OK_CASES])
def test_report_produces_the_expected_text_for_conformance_case(tmp_path, case):
    db_path = _build_db(case, tmp_path)
    result = _run(db_path)
    assert result.returncode == 0, result.stderr

    expect_path = EVAL_DIR / case["fixture"] / "expect.txt"
    for line in expect_path.read_text().splitlines():
        assert line in result.stdout, f"missing expected line {line!r} in:\n{result.stdout}"


@pytest.mark.parametrize("case", REJECT_CASES, ids=[c["name"] for c in REJECT_CASES])
def test_must_reject_report_conformance_case(tmp_path, case):
    db_path = _build_db(case, tmp_path)
    result = _run(db_path)
    assert result.returncode == 1
    assert result.stdout.strip() == ""
    assert result.stderr.strip() != ""


def test_factory_report_runs_the_script_and_prints_its_output(tmp_path, capsys):
    """`factory report` shells out to the script and prints exactly its
    stdout, matching A's exit test (a completed walk's report)."""
    case = next(c for c in OK_CASES if c["name"] == "completed_walk")
    db_path = _build_db(case, tmp_path)

    text = cli.report(db_path, window_days=7, until="2026-02-01T00:00:00+00:00")
    assert "primary measures (unranked)" in text

    cli.main(["--db", str(db_path), "report", "--window-days", "7", "--until", "2026-02-01T00:00:00+00:00"])
    captured = capsys.readouterr()
    assert captured.out == text


def test_a_baseline_only_database_never_prints_the_baseline_tickets_tag(tmp_path):
    """R-O-4: with only a baseline ticket seeded, the tag it carries never
    surfaces on the report -- the measure shows unavailable instead."""
    case = next(c for c in OK_CASES if c["name"] == "baseline_excluded")
    db_path = _build_db(case, tmp_path)
    result = _run(db_path)

    assert result.returncode == 0, result.stderr
    assert "FM-01" not in result.stdout


FORBIDDEN_PERSON_COLUMNS = (
    "resolved_by", "actor_identity", "tagged_by", "entered_by",
    "reviewer_identity", "recorder_identity", "answered_by", "tier_override_by",
)


def test_no_view_selects_a_forbidden_person_identifying_column():
    """R-O-5: no view exposes a per-person breakdown."""
    for name, sql in schema.VIEWS:
        for column in FORBIDDEN_PERSON_COLUMNS:
            assert column not in sql, f"{name} references forbidden column {column}"


def test_no_view_computes_pull_request_share_savings_or_cost_per_pull_request():
    """R-O-5: no view for agent-attributed PR share, estimated savings over
    human work, or cost per pull request distinct from cost per ticket."""
    names = {name for name, _ in schema.VIEWS}
    forbidden_fragments = ("pull_request", "per_pr", "saving", "pr_share", "pr_cost")
    for name in names:
        for fragment in forbidden_fragments:
            assert fragment not in name, f"{name} looks like a forbidden PR/savings measure"


def test_only_the_report_script_references_the_measure_view_names():
    """R-O-5: the report is the only reader of the views -- no other module
    under `runner/` (besides the schema itself) or script under
    `factory/scripts/` names one."""
    view_names = [name for name, _ in schema.VIEWS]
    pattern = re.compile("|".join(re.escape(name) for name in view_names))

    offenders = []
    runner_dir = REPO_ROOT / "runner"
    for path in runner_dir.rglob("*.py"):
        relative = path.relative_to(runner_dir)
        if path.name == "schema.py" or relative.parts[0] == "tests":
            continue
        if pattern.search(path.read_text()):
            offenders.append(path)

    scripts_dir = REPO_ROOT / "factory" / "scripts"
    for path in scripts_dir.rglob("*"):
        if not path.is_file() or path == SCRIPT or "__pycache__" in path.parts:
            continue
        if pattern.search(path.read_text(errors="ignore")):
            offenders.append(path)

    assert offenders == []
    assert pattern.search(SCRIPT.read_text()), "the report script itself should reference the views"


def test_every_measure_block_states_its_own_window(tmp_path):
    """R-O-5: every growth figure states its window, and the primary panel
    says unranked."""
    conn = connect(tmp_path / "factory.sqlite")
    output = REPORT.generate(conn, db_path=tmp_path / "factory.sqlite", manifest_hash=None, window_days=7, until="2026-02-01T00:00:00+00:00")

    assert "primary measures (unranked)" in output
    for title, _view, _cols in REPORT.PRIMARY_MEASURES:
        block_header = next(line for line in output.splitlines() if line.startswith(title))
        assert "window:" in block_header


def test_context_measures_sit_in_their_own_labelled_block_separate_from_primary(tmp_path):
    """R-O-5 / R-O-12: context measures are in their own block, each line
    labelled context, and none of their titles appear in the primary panel."""
    conn = connect(tmp_path / "factory.sqlite")
    output = REPORT.generate(conn, db_path=tmp_path / "factory.sqlite", manifest_hash=None, window_days=7, until=None)

    primary_start = output.index("primary measures (unranked)")
    context_start = output.index("context (not a primary measure or rubric-line score)")
    assert context_start > primary_start

    primary_text = output[primary_start:context_start]
    context_text = output[context_start:]
    for title, _view, _cols in REPORT.CONTEXT_MEASURES:
        assert title not in primary_text
        block_lines = [line for line in context_text.splitlines() if title in line or "context" in line]
    for line in context_text.splitlines():
        if line.strip() and line.strip() != "context (not a primary measure or rubric-line score)" and "proposal schema" not in line:
            assert line.startswith("[context]"), f"unlabelled context line: {line!r}"


def test_the_report_states_the_proposal_schema_is_absent(tmp_path):
    """R-O-12: the report ends by stating the proposal schema's absence
    rather than the schema stubbing an early table."""
    assert "proposal" not in {t.name for t in schema.TABLES}
    assert "proposal" in schema.LATER_TABLES

    conn = connect(tmp_path / "factory.sqlite")
    output = REPORT.generate(conn, db_path=tmp_path / "factory.sqlite", manifest_hash=None, window_days=7, until=None)
    assert "the proposal schema is absent in this version" in output


def test_cost_per_ticket_cannot_be_selected_as_a_primary_measure_or_rubric_line():
    """R-O-12: the objective rule reads only `primary_measures()`; a context
    measure such as cost per ticket is not in that data at all."""
    primary_views = {view for _title, view, _cols in REPORT.primary_measures()}
    context_views = {view for _title, view, _cols in REPORT.context_measures()}

    assert "v_ctx_cost_per_ticket" not in primary_views
    assert "v_ctx_cost_per_ticket" in context_views
    # every context view carries the same guarantee, not only cost.
    assert primary_views.isdisjoint(context_views)
