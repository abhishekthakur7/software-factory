"""S5's own preflight, driven end to end: a `PreflightRefused` candidate component and a stale
base each stop the run before any check runs, inventing no result (R-S5-1, R-S5-12).

`test_freshness.py` already pins the stale-base path's own `Freshness`/`check_result` shape in
detail; these tests instead pin what the *driver* does with each refusal: exactly one
`review_tuple_preflight` row from a `PreflightRefused` candidate, no such row (only freshness's
own) from a stale base, and in both cases no `check_evidence` artefact and no other check_result
at all -- the run stops before the ordered check list, or the recipes, ever start.
"""
import os
import subprocess
from pathlib import Path

import pytest

from runner import artefact_registry, git_trees, record
from runner.db import connect
from runner.stages import run_stage

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


def _source_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "source-repo"
    repo.mkdir()
    _git(["init", "-q"], cwd=repo)
    _git(["checkout", "-q", "-b", "main"], cwd=repo)
    (repo / "CODEOWNERS").write_text("* @abhishek\n")
    (repo / "README.md").write_text("seed\n")
    _git(["add", "-A"], cwd=repo)
    _git(["commit", "-q", "-m", "init"], cwd=repo, env=_COMMIT_ENV)
    return repo


@pytest.fixture
def conn(tmp_path):
    connection = connect(tmp_path / "factory.sqlite")
    yield connection
    connection.close()


def _clone_ticket(conn, tmp_path, source):
    ticket_id = record.insert(conn, "ticket", state="checks", opened_at=record.now())
    trees = git_trees.clone_for_ticket(conn, ticket_id, source_checkout=source, target_branch="main", runs_dir=tmp_path)
    git_trees.record_head(conn, ticket_id, trees.worktree)
    return ticket_id, trees


def _s5_check_results(conn, ticket_id):
    return conn.execute(
        "SELECT check_result.* FROM check_result JOIN stage_run ON stage_run.id = check_result.stage_run_id "
        "WHERE stage_run.ticket_id = ? AND stage_run.stage = 'S5' ORDER BY check_result.id",
        (ticket_id,),
    ).fetchall()


def test_a_preflight_refused_candidate_writes_exactly_one_review_tuple_preflight_row(conn, tmp_path):
    """A bare, hand-seeded plan tuple -- fresh enough for `freshness.check` (it names the real,
    unmoved base) but bound to none of the record's other current hashes -- is
    `binding.preflight_review_tuple`'s own currency refusal, reached only once freshness has
    already passed; the driver records it as one `review_tuple_preflight` fail and invents
    nothing else -- no recipe runs, no `CHECK_ORDER` check runs, no artefact."""
    source = _source_repo(tmp_path)
    ticket_id, trees = _clone_ticket(conn, tmp_path, source)
    record.insert(
        conn, "evidence_tuple", kind="plan", ticket_id=ticket_id,
        base_sha=trees.base_sha, target_base_sha=trees.base_sha, content_hash="plan-subject-1",
    )

    outcome = run_stage(conn, ticket_id, "S5", runs_dir=tmp_path)

    assert outcome == "fail"
    stage_run = conn.execute(
        "SELECT * FROM stage_run WHERE ticket_id = ? AND stage = 'S5' ORDER BY id DESC LIMIT 1", (ticket_id,)
    ).fetchone()
    assert stage_run["failure_kind"] == "stale_binding"

    results = _s5_check_results(conn, ticket_id)
    assert len(results) == 1
    assert results[0]["check_name"] == "review_tuple_preflight"
    assert results[0]["result"] == "fail"
    assert results[0]["evidence_tuple_id"] is None

    assert artefact_registry.latest(conn, ticket_id, "check_evidence") is None
    assert conn.execute("SELECT COUNT(*) FROM evidence_tuple WHERE ticket_id = ? AND kind = 'review'", (ticket_id,)).fetchone()[0] == 0


def test_a_stale_base_writes_no_review_tuple_preflight_row_and_no_other_check(conn, tmp_path):
    """A stale target base is caught by `freshness.check` before the driver ever reaches
    `binding.preflight_review_tuple`; the run ends the same `fail`/`stale_binding` way, but the
    only check_result is freshness's own (a different check_name), not a second, redundant
    `review_tuple_preflight` row for the same condition."""
    source = _source_repo(tmp_path)
    ticket_id, trees = _clone_ticket(conn, tmp_path, source)
    record.insert(
        conn, "evidence_tuple", kind="plan", ticket_id=ticket_id,
        base_sha=trees.base_sha, target_base_sha=trees.base_sha, content_hash="plan-subject-1",
    )

    (source / "moved.txt").write_text("the target branch moved after this ticket cloned it\n")
    _git(["add", "-A"], cwd=source)
    _git(["commit", "-q", "-m", "target moves"], cwd=source, env=_COMMIT_ENV)

    outcome = run_stage(conn, ticket_id, "S5", runs_dir=tmp_path)

    assert outcome == "fail"
    stage_run = conn.execute(
        "SELECT * FROM stage_run WHERE ticket_id = ? AND stage = 'S5' ORDER BY id DESC LIMIT 1", (ticket_id,)
    ).fetchone()
    assert stage_run["failure_kind"] == "stale_binding"

    # `freshness.record_failure` writes its own row with no `stage_run_id`
    # (the refusal precedes any run row's own checks), so every
    # check_result in this ticket's isolated database is read directly
    # rather than joined through `stage_run`.
    results = conn.execute("SELECT * FROM check_result ORDER BY id").fetchall()
    assert len(results) == 1
    assert results[0]["check_name"] == "freshness"
    assert results[0]["result"] == "fail"
    assert results[0]["stage_run_id"] is None

    assert artefact_registry.latest(conn, ticket_id, "check_evidence") is None
