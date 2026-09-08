"""The stub walk: one synthetic ticket from `intake` to `pr_opened` through
every stub stage `S0`-`S6`, `cli.advance`, and the human decisions its
gates need -- the milestone's exit test for the stage interface, proven
end to end before any stage becomes real.

`_run_walk` is the one driver every test in this file shares, through a
module-scoped fixture: it is expensive (git clones, subprocesses, a full
state-machine traversal), so it runs once and the short test functions
below assert one criterion each against what it produced, rather than
each replaying the whole walk. Every "kill" during the walk seeds a dead
`stage_run` the same way `test_crash_recovery.py`'s `_open_dead_run`
does -- a monkeypatched `process_identity` for exactly the one call that
opens it -- so every later liveness check in the walk runs the real
function; every "live" run (the stop demonstration) opens with no patch
at all, so its identity is this very test process.
"""
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from runner import cli, git_trees, governance, guard, owners, queue, record, recipes, run_ledger
from runner.db import connect
from runner.paths import FACTORY_DIR, REPO_ROOT
from runner.trust_profile import DEFAULT_TRUST_PROFILE_PATH

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "stub_walk"
TABLES = yaml.safe_load((FIXTURES_DIR / "tables.yaml").read_text())["tables"]
MANIFEST_HASH_SCRIPT = FACTORY_DIR / "scripts" / "tools" / "manifest_hash"

ABHISHEK = "abhishek"
FAR_FUTURE = "2999-01-01T00:00:00+00:00"
_DEAD_PID = os.getpid() + 999983

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
    repo = tmp_path / "source-repo"
    repo.mkdir()
    _git(["init", "-q"], cwd=repo)
    _git(["checkout", "-q", "-b", "main"], cwd=repo)
    (repo / "README.md").write_text("seed\n")
    _git(["add", "-A"], cwd=repo)
    _git(["commit", "-q", "-m", "init"], cwd=repo, env=_COMMIT_ENV)
    return repo


def _activate_default_profile(conn) -> dict:
    """Satisfy the default trust profile's quorum, the same way `factory advance` reads it.

    Returns the ticket fields that bind a ticket to the activated profile
    and to the pilot's admitted source scope, so S0's governance check
    admits the walk's eligibility grant."""
    proposal = governance.propose(DEFAULT_TRUST_PROFILE_PATH, owners.DEFAULT_OWNERS_PATH)
    for role in ("security_approver", "legal_data_governance_approver"):
        governance.decide(
            conn, proposal, actor_identity=ABHISHEK, role=role, decision="approve",
            expires_at=FAR_FUTURE, attestation_version="v1", attestation_hash=f"att-{role}",
            owners_path=owners.DEFAULT_OWNERS_PATH, profile_path=DEFAULT_TRUST_PROFILE_PATH,
        )
    conn.commit()
    activated = governance.activation(conn, proposal)
    return {
        "trust_profile_hash": proposal.profile_hash,
        "trust_approval_set_hash": activated.trust_approval_set_hash,
        "source_kind": "jira",
        "source_ref": "FIX-1",
    }


def _manifest_hash() -> subprocess.CompletedProcess:
    return subprocess.run([str(MANIFEST_HASH_SCRIPT), "--root", str(REPO_ROOT)], capture_output=True, text=True)


def _open_dead_run(conn, **kwargs) -> int:
    """Open a run whose `process_identity` names a pid that does not exist -- a "killed" attempt."""
    fake_identity = f"deadhost:{_DEAD_PID}:Thu Jan  1 00:00:00 1970"
    with patch.object(run_ledger, "process_identity", lambda pid=None: fake_identity):
        return run_ledger.open_stage_run(conn, **kwargs)


def _kill_and_restart(conn, ticket_id, stage, tmp_path):
    """Seed a dead run for `stage`, then let one `factory advance` call expire it and pass a fresh attempt.

    Proves criterion 15 for `stage`: the killed attempt ends
    `infrastructure_failure`/`expired_lease`, and exactly one fresh attempt
    follows it with no duplicate row for the killed attempt.
    """
    dead_id = _open_dead_run(conn, ticket_id=ticket_id, stage=stage, lease_seconds=-1)
    cli.advance(conn, ticket_id, tmp_path)

    dead_row = record.get(conn, "stage_run", dead_id)
    assert dead_row["outcome"] == "infrastructure_failure"
    assert dead_row["failure_kind"] == "expired_lease"
    rows = conn.execute(
        "SELECT outcome FROM stage_run WHERE ticket_id = ? AND stage = ? ORDER BY id", (ticket_id, stage)
    ).fetchall()
    assert rows[-1]["outcome"] == "pass"
    assert sum(1 for row in rows if row["outcome"] == "infrastructure_failure") == 1


def _grant_plan_approval(conn, ticket_id, tmp_path, *, content_hash):
    slots = json.dumps(
        [{"source_rule": "plan:1", "role": "s3_reviewer", "min_count": 1, "distinct_from": [], "resolved": True}]
    )
    reviewer_set_id = record.insert(
        conn, "reviewer_set", ticket_id=ticket_id, kind="planned", content_hash=f"planned-{ticket_id}", slots=slots,
    )
    item_id = queue.open_item(
        conn, ticket_id=ticket_id, kind="plan_approval", reviewer_set_id=reviewer_set_id, approval_subject_hash=content_hash,
    )
    queue.act(conn, item_id=item_id, action="approve", actor=ABHISHEK, bucket="under_2m", runs_dir=tmp_path)


def _grant_packet_approval(conn, ticket_id, tmp_path, *, content_hash):
    """Seed a review evidence tuple and effective reviewer set, then approve it -- which itself
    authors the ticket's `pr_create` outbox intent once its quorum is satisfied."""
    slots = json.dumps(
        [{"source_rule": "review:1", "role": "s6_reviewer", "min_count": 1, "distinct_from": [], "resolved": True}]
    )
    reviewer_set_id = record.insert(
        conn, "reviewer_set", ticket_id=ticket_id, kind="effective", content_hash=f"effective-{ticket_id}", slots=slots,
    )
    record.insert(
        conn, "evidence_tuple", kind="review", ticket_id=ticket_id,
        content_hash=content_hash, effective_reviewer_set_id=reviewer_set_id, created_at=record.now(),
    )
    item_id = queue.open_item(
        conn, ticket_id=ticket_id, kind="packet_approval", reviewer_set_id=reviewer_set_id, approval_subject_hash=content_hash,
    )
    queue.act(conn, item_id=item_id, action="approve", actor=ABHISHEK, bucket="under_2m", runs_dir=tmp_path)
    conn.commit()  # `create_intent` never commits; the caller owns the transaction.


@dataclass(frozen=True)
class WalkResult:
    conn: object
    ticket_id: int
    tmp_path: Path
    wrong_state_stage_run_id: int
    stopped_stage_run_id: int
    manifest_hash_before: subprocess.CompletedProcess
    manifest_hash_after: subprocess.CompletedProcess


def _run_walk(tmp_path) -> WalkResult:
    conn = connect(tmp_path / "factory.sqlite")
    manifest_hash_before = _manifest_hash()
    governed = _activate_default_profile(conn)

    # A pilot-eligible service and type, since the real S0 rejects anything else.
    ticket_id = record.insert(
        conn, "ticket", state="intake", opened_at=record.now(),
        service="fixture-project", ticket_type="small_feature", **governed,
    )

    # criterion 14: a stage invoked from a state the transition table does not permit is refused and recorded.
    wrong_state_outcome = cli.run(conn, ticket_id, "S4", runs_dir=tmp_path)
    assert wrong_state_outcome == "refused"
    wrong_state_row = conn.execute(
        "SELECT id FROM stage_run WHERE ticket_id = ? AND stage = 'S4' ORDER BY id LIMIT 1", (ticket_id,)
    ).fetchone()
    assert record.get(conn, "stage_run", wrong_state_row["id"])["outcome"] == "refused"

    # S0, kill and restart, then eligibility admits to `context`.
    _kill_and_restart(conn, ticket_id, "S0", tmp_path)
    eligibility_item = conn.execute(
        "SELECT id FROM queue_item WHERE ticket_id = ? AND kind = 'eligibility' AND resolved_at IS NULL",
        (ticket_id,),
    ).fetchone()
    queue.act(conn, item_id=eligibility_item["id"], action="granted", actor=ABHISHEK, runs_dir=tmp_path)
    cli.advance(conn, ticket_id, tmp_path)
    assert record.get(conn, "ticket", ticket_id)["state"] == "context"

    # S1, S2, S3: each always due while its state holds, killed and restarted once.
    _kill_and_restart(conn, ticket_id, "S1", tmp_path)
    assert record.get(conn, "ticket", ticket_id)["state"] == "clarifying"
    _kill_and_restart(conn, ticket_id, "S2", tmp_path)
    assert record.get(conn, "ticket", ticket_id)["state"] == "planning"
    _kill_and_restart(conn, ticket_id, "S3", tmp_path)
    assert record.get(conn, "ticket", ticket_id)["state"] == "plan_review"

    # A real, fetchable base: S4's freshness preflight and the plan-review
    # gate's own freshness check both fetch the configured target branch
    # from the ticket's own clone.
    source = _source_repo(tmp_path)
    trees = git_trees.clone_for_ticket(conn, ticket_id, source_checkout=source, target_branch="main", runs_dir=tmp_path)
    git_trees.record_head(conn, ticket_id, trees.worktree)
    record.insert(
        conn, "evidence_tuple", kind="plan", ticket_id=ticket_id,
        base_sha=trees.base_sha, target_base_sha=trees.base_sha, content_hash="plan-subject-1",
    )
    _grant_plan_approval(conn, ticket_id, tmp_path, content_hash="plan-subject-1")
    cli.advance(conn, ticket_id, tmp_path)
    assert record.get(conn, "ticket", ticket_id)["state"] == "implementing"

    # criterion 16 (stop half): a live S4 run stopped ends `aborted_human`
    # and escalates; resuming the escalation returns the ticket to `implementing`.
    stopped_run_id = run_ledger.open_stage_run(conn, ticket_id=ticket_id, stage="S4")
    cli.stop(conn, ticket_id, actor=ABHISHEK, fm_id="FM-07", note="paused for a manual look")
    assert record.get(conn, "stage_run", stopped_run_id)["outcome"] == "aborted_human"
    assert record.get(conn, "ticket", ticket_id)["state"] == "escalated"
    escalation_item = conn.execute(
        "SELECT id FROM queue_item WHERE ticket_id = ? AND kind = 'escalation' ORDER BY id DESC LIMIT 1", (ticket_id,)
    ).fetchone()
    queue.act(conn, item_id=escalation_item["id"], action="resume", actor=ABHISHEK, runs_dir=tmp_path)
    assert record.get(conn, "ticket", ticket_id)["state"] == "implementing"

    _kill_and_restart(conn, ticket_id, "S4", tmp_path)
    assert record.get(conn, "ticket", ticket_id)["state"] == "checks"

    # criterion 16 (pause half), 6, 8, 12: a pending pause takes effect at
    # the next boundary, before S5 ever starts, and repeating the same
    # boundary opens no duplicate `manual_pause` item.
    cli.pause(conn, ticket_id)
    paused_result = cli.advance(conn, ticket_id, tmp_path)
    assert paused_result == f"ticket {ticket_id}: paused at checks"
    cli.advance(conn, ticket_id, tmp_path)
    manual_pause_items = conn.execute(
        "SELECT id FROM queue_item WHERE ticket_id = ? AND kind = 'manual_pause'", (ticket_id,)
    ).fetchall()
    assert len(manual_pause_items) == 1
    assert conn.execute("SELECT COUNT(*) FROM stage_run WHERE ticket_id = ? AND stage = 'S5'", (ticket_id,)).fetchone()[0] == 0
    cli.resume(conn, ticket_id, actor=ABHISHEK)

    _kill_and_restart(conn, ticket_id, "S5", tmp_path)
    assert record.get(conn, "ticket", ticket_id)["state"] == "checks"
    _kill_and_restart(conn, ticket_id, "S6", tmp_path)
    assert record.get(conn, "ticket", ticket_id)["state"] == "checks"

    cli.advance(conn, ticket_id, tmp_path)  # checks_gate: both S5 and S6 passed
    assert record.get(conn, "ticket", ticket_id)["state"] == "review"

    _grant_packet_approval(conn, ticket_id, tmp_path, content_hash="review-subject-1")
    cli.advance(conn, ticket_id, tmp_path)  # reconciles the pr_create intent, then review_quorum_reconciled

    manifest_hash_after = _manifest_hash()

    return WalkResult(
        conn=conn, ticket_id=ticket_id, tmp_path=tmp_path,
        wrong_state_stage_run_id=wrong_state_row["id"], stopped_stage_run_id=stopped_run_id,
        manifest_hash_before=manifest_hash_before, manifest_hash_after=manifest_hash_after,
    )


@pytest.fixture(scope="module")
def walk(tmp_path_factory):
    result = _run_walk(tmp_path_factory.mktemp("stub_walk"))
    yield result
    result.conn.close()


def test_the_walk_reaches_pr_opened_and_every_touched_table_carries_rows(walk):
    """R-I-8, R-H-13, criterion 13: the synthetic ticket reaches `pr_opened`
    through every stub stage `S0`-`S6`, and every table the walk touches
    (named in the fixture) carries at least one row."""
    assert record.get(walk.conn, "ticket", walk.ticket_id)["state"] == "pr_opened"
    for table in TABLES:
        count = walk.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        assert count > 0, f"expected at least one {table} row"


def test_a_wrong_state_stage_invocation_is_refused_and_recorded(walk):
    """criterion 14: `S4` invoked from `intake` -- a state the transition
    table does not permit for it -- is refused and its own `stage_run`
    records the refusal."""
    row = record.get(walk.conn, "stage_run", walk.wrong_state_stage_run_id)
    assert row["stage"] == "S4"
    assert row["outcome"] == "refused"


def test_a_kill_at_every_stage_leaves_no_duplicate_attempt(walk):
    """criterion 15: across the whole walk, every stage `S0`-`S6` was
    killed once and restarted with exactly one fresh, passing attempt --
    proven inline by `_kill_and_restart` during the walk itself; this test
    pins that every stage was actually exercised that way."""
    for stage in ("S0", "S1", "S2", "S3", "S4", "S5", "S6"):
        rows = walk.conn.execute(
            "SELECT outcome FROM stage_run WHERE ticket_id = ? AND stage = ?", (walk.ticket_id, stage)
        ).fetchall()
        outcomes = [row["outcome"] for row in rows]
        assert outcomes.count("infrastructure_failure") == 1, stage
        assert outcomes.count("pass") == 1, stage


def test_the_stop_demonstration_ended_the_run_aborted_human(walk):
    """criterion 16 (stop half): the stage run stopped mid-walk carries
    `aborted_human`, distinct from every killed attempt's `infrastructure_failure`."""
    assert record.get(walk.conn, "stage_run", walk.stopped_stage_run_id)["outcome"] == "aborted_human"


def test_an_in_place_edit_on_an_append_only_row_is_refused(walk):
    """criterion 17: an attempted in-place edit of an append-only `stage_run`
    column raises `sqlite3.IntegrityError`, refused by the schema's own trigger."""
    import sqlite3

    row = walk.conn.execute(
        "SELECT id FROM stage_run WHERE ticket_id = ? AND stage = 'S0' LIMIT 1", (walk.ticket_id,)
    ).fetchone()
    with pytest.raises(sqlite3.IntegrityError):
        record.update(walk.conn, "stage_run", row["id"], stage="S1")


def test_must_reject_a_recipe_given_a_shell_string(walk):
    """criterion 18: a recipe catalogue entry whose literal argument carries
    shell command substitution is refused by `recipes.load_catalogue`
    before any recipe from it could ever be dispatched."""
    with pytest.raises(recipes.RecipeError):
        recipes.load_catalogue(FIXTURES_DIR / "shell_recipe.yaml")


def test_the_manifest_hash_validates_identically_before_and_after_the_walk(walk):
    """criterion 19: the manifest hash script validates the real repository
    both before and after the stub walk, and reports the identical hash --
    the walk, which only ever writes to a tmp database and tmp run tree,
    changes nothing under `factory/`."""
    assert walk.manifest_hash_before.returncode == 0, walk.manifest_hash_before.stderr
    assert walk.manifest_hash_after.returncode == 0, walk.manifest_hash_after.stderr
    assert walk.manifest_hash_before.stdout == walk.manifest_hash_after.stdout


def test_one_guard_decision_row_per_content_bearing_crossing(walk):
    """criterion 20: the walk's one `pr_create` dispatch performs exactly
    two content-bearing crossings through the guard -- the outbound
    payload and the inbound receipt -- and each writes exactly one
    `guard_decision` row, neither denied."""
    rows = walk.conn.execute("SELECT decision, operation FROM guard_decision ORDER BY id").fetchall()
    assert len(rows) == 2
    assert all(row["operation"] == "outbox" for row in rows)
    assert all(row["decision"] in ("allow", "redact") for row in rows)


def test_must_reject_a_crossing_that_bypasses_the_guard(tmp_path):
    """criterion 21: `guard.pass_through` refuses a hand-built `Decision`
    that was never actually persisted through `guard.decide`."""
    conn = connect(tmp_path / "factory.sqlite")
    fake = guard.Decision(id=999999, decision="allow", reason_codes=(), effective_class="internal", payload="x", capabilities={})
    with pytest.raises(guard.GuardRefused):
        guard.pass_through(conn, fake, "outbox")
    conn.close()
