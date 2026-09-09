"""Base freshness at three boundaries, and `refresh_base`.

Every git repository here is real (mirroring `test_fixture_project.py`'s
`_bare_git_project` convention -- a plain repository, no JDK needed), so
`freshness.fetch_target_head`'s own `git fetch`/`git rev-parse` calls are
exercised for real rather than stubbed: "target movement" is a fresh
commit on the source repository's target branch made after
`git_trees.clone_for_ticket` has already cloned it.
"""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from runner import (
    approvals, artefact_registry, artefacts, binding, canonical, cli, freshness, gates, git_trees, manifest, outbox,
    owners, plan_tuple, publication, record, refresh_base, transitions,
)
from runner.db import connect
from runner.deliverers.stub import StubDeliverer
from runner.reviewer_sets import Slot
from runner.stages import run_stage
from runner.trust_profile import load_trust_profile

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "freshness"
OUTBOX_FIXTURES_DIR = Path(__file__).parent / "fixtures" / "outbox"

TARGET_BRANCH = "main"

_COMMIT_ENV = {
    "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@example.invalid",
}


def _git(args, cwd, env=None, check=True):
    full_env = {**os.environ, **env} if env else None
    return subprocess.run(
        ["git", "-c", "commit.gpgsign=false", *args], cwd=cwd, env=full_env,
        capture_output=True, text=True, check=check,
    )


def _write_files(root: Path, files: dict) -> None:
    for name, content in files.items():
        (root / name).write_text(content)


def _commit_all(repo: Path, message: str) -> None:
    _git(["add", "-A"], cwd=repo)
    _git(["commit", "-q", "-m", message], cwd=repo, env=_COMMIT_ENV)


def _load_fixture(name: str) -> dict:
    return yaml.safe_load((FIXTURES_DIR / f"{name}.yaml").read_text())


def _source_repo(tmp_path: Path, seed_files: dict) -> Path:
    repo = tmp_path / "source-repo"
    repo.mkdir()
    _git(["init", "-q"], cwd=repo)
    _git(["checkout", "-q", "-b", TARGET_BRANCH], cwd=repo)
    _write_files(repo, seed_files)
    _commit_all(repo, "seed")
    return repo


@pytest.fixture
def conn(tmp_path):
    connection = connect(tmp_path / "factory.sqlite")
    yield connection
    connection.close()


def _clone_ticket(conn, tmp_path, source, *, state, **ticket_fields):
    """`ticket_fields` are set at insert time -- `trust_profile_hash` and `trust_approval_set_hash`
    are append-only columns, so a caller that needs them set must pass them here rather than
    through a later `record.update`."""
    runs_dir = tmp_path / "runs"
    ticket_id = record.insert(conn, "ticket", state="intake", opened_at=record.now(), **ticket_fields)
    trees = git_trees.clone_for_ticket(
        conn, ticket_id, source_checkout=source, target_branch=TARGET_BRANCH, runs_dir=runs_dir,
    )
    git_trees.record_head(conn, ticket_id, trees.worktree)
    record.update(conn, "ticket", ticket_id, state=state)
    return ticket_id, trees, runs_dir


def _plan_tuple(conn, ticket_id, base_sha, content_hash="plan-1") -> int:
    return record.insert(
        conn, "evidence_tuple", kind="plan", ticket_id=ticket_id,
        base_sha=base_sha, target_base_sha=base_sha, content_hash=content_hash,
    )


def _approve_plan(conn, ticket_id, content_hash) -> None:
    record.insert(
        conn, "approval_record", ticket_id=ticket_id, gate="plan", decision="approve", subject_hash=content_hash,
    )


def test_before_s4_detects_target_movement_against_the_plan_tuple_and_ticket(conn, tmp_path):
    """R-S5-12"""
    fixture = _load_fixture("target_movement")
    source = _source_repo(tmp_path, fixture["seed"])
    ticket_id, trees, runs_dir = _clone_ticket(conn, tmp_path, source, state="implementing")
    _plan_tuple(conn, ticket_id, trees.base_sha)

    _write_files(source, fixture["target_commit"]["files"])
    _commit_all(source, fixture["target_commit"]["message"])

    fresh = freshness.check(conn, ticket_id, boundary=freshness.BEFORE_S4, target_branch=TARGET_BRANCH, runs_dir=runs_dir)

    assert not fresh.fresh
    assert fresh.reasons
    assert fresh.fetched_target_head != trees.base_sha
    assert fresh.check_result_id is not None


def test_before_s4_is_fresh_when_the_target_has_not_moved(conn, tmp_path):
    """R-S5-12"""
    fixture = _load_fixture("target_movement")
    source = _source_repo(tmp_path, fixture["seed"])
    ticket_id, trees, runs_dir = _clone_ticket(conn, tmp_path, source, state="implementing")
    _plan_tuple(conn, ticket_id, trees.base_sha)

    fresh = freshness.check(conn, ticket_id, boundary=freshness.BEFORE_S4, target_branch=TARGET_BRANCH, runs_dir=runs_dir)

    assert fresh.fresh
    assert fresh.reasons == ()
    assert fresh.check_result_id is None


def test_advance_refuses_s4_on_a_stale_base_and_queues_exactly_one_red_check(conn, tmp_path, monkeypatch):
    """R-S5-12: the due-stage boundary in `cli.advance`."""
    fixture = _load_fixture("target_movement")
    source = _source_repo(tmp_path, fixture["seed"])
    ticket_id, trees, runs_dir = _clone_ticket(conn, tmp_path, source, state="implementing")
    _plan_tuple(conn, ticket_id, trees.base_sha)

    # `advance` reads the project's real target branch from the committed
    # `factory/config/project.yaml` ("main"), which the fixture's source
    # repository already uses -- no monkeypatch of that config is needed.
    monkeypatch.setattr(cli, "_due_stage", lambda conn, ticket: "S4")

    _write_files(source, fixture["target_commit"]["files"])
    _commit_all(source, fixture["target_commit"]["message"])

    message = cli.advance(conn, ticket_id, runs_dir=runs_dir)
    assert "stale" in message
    assert record.get(conn, "ticket", ticket_id)["state"] == "implementing"
    red_checks = conn.execute(
        "SELECT * FROM queue_item WHERE ticket_id = ? AND kind = 'red_check'", (ticket_id,)
    ).fetchall()
    assert len(red_checks) == 1
    assert red_checks[0]["ref"].startswith("check_result:")

    # a second advance call finds the same open red_check and queues no second one
    cli.advance(conn, ticket_id, runs_dir=runs_dir)
    red_checks = conn.execute(
        "SELECT * FROM queue_item WHERE ticket_id = ? AND kind = 'red_check'", (ticket_id,)
    ).fetchall()
    assert len(red_checks) == 1


def _real_plan_quorum(conn, tmp_path, ticket_id) -> int:
    """Build a real, currently-current plan tuple and a satisfying `plan` approval on it; return the tuple's id.

    `gates.plan_review_gate` now derives quorum from `approvals.evaluate`
    against the ticket's own latest plan tuple and refuses when
    `plan_tuple.derive_components` no longer matches it, so the bare stub
    row `_plan_tuple`/`_approve_plan` above seed (fine for the freshness
    boundary tests, which never call this gate) cannot stand in here:
    this ticket needs real registered artefacts, a real planned reviewer
    set, and a plan tuple built the same way the checklist would build
    one, before a real `approval_record` against its exact subject hash
    can satisfy quorum. The caller must have inserted the ticket with
    `trust_profile_hash`/`trust_approval_set_hash` already set (see
    `_clone_ticket`'s `ticket_fields`) -- both are append-only columns.
    """
    record.update(conn, "ticket", ticket_id, factory_manifest_hash=manifest.current_hash())
    for kind in ("brief", "criteria", "plan"):
        path = tmp_path / f"{kind}.md"
        path.write_text(f"## {artefacts.SECTIONS[kind][0]}\n\nstub\n")
        artefact_registry.register(conn, ticket_id=ticket_id, kind=kind, path=path)

    identity = owners.load_owners().roles["s3_reviewer"]["identity"]
    slot = Slot(source_rule="s3_reviewer_role", role="s3_reviewer", owner=identity, min_count=1)
    record.insert(
        conn, "reviewer_set", ticket_id=ticket_id, kind="planned", content_hash="planned-1",
        slots=json.dumps([slot.to_json()]),
    )

    ticket = record.get(conn, "ticket", ticket_id)
    tuple_id = plan_tuple.ensure_current(conn, ticket)
    subject_hash = record.get(conn, "evidence_tuple", tuple_id)["content_hash"]
    approvals.record_approval(
        conn, gate="plan", subject_hash=subject_hash, slot_id=slot.slot_id, actor_identity=identity,
        role="s3_reviewer", decision="approve", authority_policy_hash="authority-1",
        membership_snapshot_hash="membership-1", attestation_version="v1", attestation_hash="att-1",
        ticket_id=ticket_id,
    )
    return tuple_id


def test_plan_review_gate_withholds_plan_quorum_fresh_on_a_stale_base(conn, tmp_path):
    """R-S5-12: the plan-approval commit boundary."""
    fixture = _load_fixture("target_movement")
    source = _source_repo(tmp_path, fixture["seed"])
    ticket_id, trees, runs_dir = _clone_ticket(
        conn, tmp_path, source, state="plan_review",
        trust_profile_hash="trust-1", trust_approval_set_hash="trust-approval-1",
    )
    _real_plan_quorum(conn, tmp_path, ticket_id)

    ticket = record.get(conn, "ticket", ticket_id)
    assert gates.plan_review_gate(conn, ticket, runs_dir=runs_dir) == "plan_quorum_fresh"

    _write_files(source, fixture["target_commit"]["files"])
    _commit_all(source, fixture["target_commit"]["message"])

    ticket = record.get(conn, "ticket", ticket_id)
    assert gates.plan_review_gate(conn, ticket, runs_dir=runs_dir) is None


def test_s5_preflight_detects_target_movement(conn, tmp_path):
    """R-S5-12: the S5 preflight boundary."""
    fixture = _load_fixture("target_movement")
    source = _source_repo(tmp_path, fixture["seed"])
    ticket_id, trees, runs_dir = _clone_ticket(conn, tmp_path, source, state="checks")
    _plan_tuple(conn, ticket_id, trees.base_sha)

    _write_files(source, fixture["target_commit"]["files"])
    _commit_all(source, fixture["target_commit"]["message"])

    fresh = freshness.check(
        conn, ticket_id, boundary=freshness.S5_PREFLIGHT, target_branch=TARGET_BRANCH, runs_dir=runs_dir,
    )
    assert not fresh.fresh


def test_stage_s5_driver_fails_stale_binding_on_a_stale_base(conn, tmp_path):
    """R-S5-12: the real stub S5 driver runs the preflight before writing any artefact."""
    fixture = _load_fixture("target_movement")
    source = _source_repo(tmp_path, fixture["seed"])
    ticket_id, trees, runs_dir = _clone_ticket(conn, tmp_path, source, state="checks")
    _plan_tuple(conn, ticket_id, trees.base_sha)

    _write_files(source, fixture["target_commit"]["files"])
    _commit_all(source, fixture["target_commit"]["message"])

    outcome = run_stage(conn, ticket_id, "S5", runs_dir=runs_dir)
    assert outcome == "fail"
    stage_run = conn.execute(
        "SELECT * FROM stage_run WHERE ticket_id = ? AND stage = 'S5' ORDER BY id DESC LIMIT 1", (ticket_id,)
    ).fetchone()
    assert stage_run["failure_kind"] == "stale_binding"
    assert artefact_registry.latest(conn, ticket_id, "check_evidence") is None


def test_s5_preflight_binds_a_diff_hash_when_no_review_tuple_exists_yet(conn, tmp_path):
    """R-S5-12"""
    fixture = _load_fixture("target_movement")
    source = _source_repo(tmp_path, fixture["seed"])
    ticket_id, trees, runs_dir = _clone_ticket(conn, tmp_path, source, state="checks")
    _plan_tuple(conn, ticket_id, trees.base_sha)

    fresh = freshness.check(
        conn, ticket_id, boundary=freshness.S5_PREFLIGHT, target_branch=TARGET_BRANCH, runs_dir=runs_dir,
    )
    assert fresh.fresh
    assert fresh.diff_hash == canonical.content_hash({"diff": ""})


def test_s5_preflight_requires_the_diff_to_match_the_bound_review_tuple(conn, tmp_path):
    """R-S5-12"""
    fixture = _load_fixture("target_movement")
    source = _source_repo(tmp_path, fixture["seed"])
    ticket_id, trees, runs_dir = _clone_ticket(conn, tmp_path, source, state="checks")
    _plan_tuple(conn, ticket_id, trees.base_sha)
    record.insert(
        conn, "evidence_tuple", kind="review", ticket_id=ticket_id,
        content_hash="review-1", diff_hash="a-diff-hash-that-does-not-match",
    )

    fresh = freshness.check(
        conn, ticket_id, boundary=freshness.S5_PREFLIGHT, target_branch=TARGET_BRANCH, runs_dir=runs_dir,
    )
    assert not fresh.fresh
    assert any("diff" in reason for reason in fresh.reasons)


def test_must_reject_s5_preflight_when_the_worktree_head_moved_past_ticket_head_sha(conn, tmp_path):
    """R-S5-12"""
    fixture = _load_fixture("target_movement")
    source = _source_repo(tmp_path, fixture["seed"])
    ticket_id, trees, runs_dir = _clone_ticket(conn, tmp_path, source, state="checks")
    _plan_tuple(conn, ticket_id, trees.base_sha)

    (trees.worktree / "drift.txt").write_text("an uncommitted-to-the-record advance\n")
    _commit_all(trees.worktree, "worktree head moves without updating ticket.head_sha")

    fresh = freshness.check(
        conn, ticket_id, boundary=freshness.S5_PREFLIGHT, target_branch=TARGET_BRANCH, runs_dir=runs_dir,
    )
    assert not fresh.fresh
    assert any("head_sha" in reason for reason in fresh.reasons)
    assert fresh.diff_hash is None


def test_a_stale_result_invalidates_the_plan_and_review_tuples_it_named(conn, tmp_path):
    """R-S5-12"""
    fixture = _load_fixture("target_movement")
    source = _source_repo(tmp_path, fixture["seed"])
    ticket_id, trees, runs_dir = _clone_ticket(conn, tmp_path, source, state="checks")
    plan_tuple_id = _plan_tuple(conn, ticket_id, trees.base_sha)
    review_tuple_id = record.insert(
        conn, "evidence_tuple", kind="review", ticket_id=ticket_id, content_hash="review-1",
    )

    _write_files(source, fixture["target_commit"]["files"])
    _commit_all(source, fixture["target_commit"]["message"])

    assert freshness.invalidated_tuples(conn, ticket_id) == set()

    fresh = freshness.check(
        conn, ticket_id, boundary=freshness.S5_PREFLIGHT, target_branch=TARGET_BRANCH, runs_dir=runs_dir,
    )
    assert not fresh.fresh

    invalidated = freshness.invalidated_tuples(conn, ticket_id)
    assert invalidated == {plan_tuple_id, review_tuple_id}

    check_result = record.get(conn, "check_result", fresh.check_result_id)
    assert check_result["check_name"] == "freshness"
    assert check_result["check_tier"] == "blocking"
    assert check_result["result"] == "fail"
    assert check_result["plan_tuple_id"] == plan_tuple_id
    assert check_result["evidence_tuple_id"] == review_tuple_id


def test_a_fresh_result_writes_no_check_result_row(conn, tmp_path):
    """R-S5-12"""
    fixture = _load_fixture("target_movement")
    source = _source_repo(tmp_path, fixture["seed"])
    ticket_id, trees, runs_dir = _clone_ticket(conn, tmp_path, source, state="checks")
    _plan_tuple(conn, ticket_id, trees.base_sha)

    freshness.check(conn, ticket_id, boundary=freshness.BEFORE_S4, target_branch=TARGET_BRANCH, runs_dir=runs_dir)

    assert conn.execute("SELECT COUNT(*) FROM check_result").fetchone()[0] == 0


def test_refresh_base_preserves_a_dirty_build_and_records_the_new_base_and_head(conn, tmp_path):
    """R-S5-12"""
    fixture = _load_fixture("clean_rebase")
    source = _source_repo(tmp_path, fixture["seed"])
    ticket_id, trees, runs_dir = _clone_ticket(conn, tmp_path, source, state="implementing")
    _plan_tuple(conn, ticket_id, trees.base_sha)

    _write_files(trees.worktree, fixture["ticket_commit"]["files"])
    _commit_all(trees.worktree, fixture["ticket_commit"]["message"])
    git_trees.record_head(conn, ticket_id, trees.worktree)

    _write_files(source, fixture["target_commit"]["files"])
    _commit_all(source, fixture["target_commit"]["message"])
    new_target_head = _git(["rev-parse", TARGET_BRANCH], cwd=source).stdout.strip()

    message = refresh_base.refresh_base(
        conn, ticket_id, actor="engineer-1", target_branch=TARGET_BRANCH, runs_dir=runs_dir,
    )

    assert "escalat" not in message
    ticket = record.get(conn, "ticket", ticket_id)
    assert ticket["state"] == "context"
    assert ticket["base_sha"] == new_target_head
    assert ticket["target_base_sha"] == new_target_head
    new_head_sha = _git(["rev-parse", "HEAD"], cwd=trees.worktree).stdout.strip()
    assert ticket["head_sha"] == new_head_sha
    assert new_head_sha != new_target_head, "the dirty build's own commit survives on top of the new base"

    for name, content in fixture["ticket_commit"]["files"].items():
        assert (trees.worktree / name).read_text() == content
    for name, content in fixture["target_commit"]["files"].items():
        assert (trees.worktree / name).read_text() == content


def test_refresh_base_escalates_a_conflicting_rebase_without_resolving_it(conn, tmp_path):
    """R-S5-12"""
    fixture = _load_fixture("conflicting_rebase")
    source = _source_repo(tmp_path, fixture["seed"])
    ticket_id, trees, runs_dir = _clone_ticket(conn, tmp_path, source, state="implementing")
    _plan_tuple(conn, ticket_id, trees.base_sha)

    _write_files(trees.worktree, fixture["ticket_commit"]["files"])
    _commit_all(trees.worktree, fixture["ticket_commit"]["message"])
    git_trees.record_head(conn, ticket_id, trees.worktree)
    pre_conflict_head = record.get(conn, "ticket", ticket_id)["head_sha"]

    _write_files(source, fixture["target_commit"]["files"])
    _commit_all(source, fixture["target_commit"]["message"])

    message = refresh_base.refresh_base(
        conn, ticket_id, actor="engineer-1", note="attempted refresh", target_branch=TARGET_BRANCH, runs_dir=runs_dir,
    )

    assert "escalat" in message
    assert "shared.txt" in message

    ticket = record.get(conn, "ticket", ticket_id)
    assert ticket["state"] == "escalated"
    # nothing about the ticket's own recorded head moved: the conflict was
    # never resolved, so the pre-conflict head is still what is recorded.
    assert ticket["head_sha"] == pre_conflict_head

    status = _git(["status", "--porcelain"], cwd=trees.worktree).stdout
    assert status == "", "the aborted rebase must leave the worktree clean"
    branch = _git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=trees.worktree).stdout.strip()
    assert branch == trees.branch, "an aborted rebase returns to the ticket's own branch, not a detached HEAD"

    escalations = conn.execute(
        "SELECT * FROM queue_item WHERE ticket_id = ? AND kind = 'escalation'", (ticket_id,)
    ).fetchall()
    assert len(escalations) == 1
    assert escalations[0]["resolved_at"] is None
    check_result_id = int(escalations[0]["ref"].split(":", 1)[1])
    check_result = record.get(conn, "check_result", check_result_id)
    assert check_result["check_name"] == "refresh_base"
    assert check_result["result"] == "fail"
    assert "shared.txt" in check_result["summary"]


def test_must_reject_refresh_base_from_a_state_with_no_refresh_base_transition(conn, tmp_path):
    """R-S5-12"""
    fixture = _load_fixture("target_movement")
    source = _source_repo(tmp_path, fixture["seed"])
    ticket_id, trees, runs_dir = _clone_ticket(conn, tmp_path, source, state="review")
    _plan_tuple(conn, ticket_id, trees.base_sha)

    with pytest.raises(transitions.TransitionRefused):
        refresh_base.refresh_base(conn, ticket_id, actor="engineer-1", target_branch=TARGET_BRANCH, runs_dir=runs_dir)

    # refused before any git call: the worktree is untouched, still on the ticket's own branch.
    branch = _git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=trees.worktree).stdout.strip()
    assert branch == trees.branch


def test_refresh_base_returns_to_context_and_requires_a_new_plan_approval(conn, tmp_path):
    """R-S5-12"""
    fixture = _load_fixture("target_movement")
    source = _source_repo(tmp_path, fixture["seed"])
    ticket_id, trees, runs_dir = _clone_ticket(
        conn, tmp_path, source, state="plan_review",
        trust_profile_hash="trust-1", trust_approval_set_hash="trust-approval-1",
    )
    old_plan_tuple_id = _real_plan_quorum(conn, tmp_path, ticket_id)

    _write_files(source, fixture["target_commit"]["files"])
    _commit_all(source, fixture["target_commit"]["message"])

    refresh_base.refresh_base(conn, ticket_id, actor="engineer-1", target_branch=TARGET_BRANCH, runs_dir=runs_dir)
    ticket = record.get(conn, "ticket", ticket_id)
    assert ticket["state"] == "context"

    # The old plan tuple and its quorum are still on the ticket, but its
    # own (unmoved) target_base_sha is now stale against the refreshed
    # ticket -- plan_review_gate's own currency check catches this before
    # ever reaching the live freshness fetch, so advancing again requires
    # a new plan tuple (over the ticket's now-current target_base_sha) and
    # a fresh approval on it.
    record.update(conn, "ticket", ticket_id, state="plan_review")
    ticket = record.get(conn, "ticket", ticket_id)
    assert gates.plan_review_gate(conn, ticket, runs_dir=runs_dir) is None
    currency = binding.plan_tuple_currency(conn, old_plan_tuple_id, plan_tuple.derive_components(conn, ticket))
    assert not currency.current
    assert "target_base_sha" in currency.changed


@pytest.fixture
def profile_paths(tmp_path):
    profile_path = tmp_path / "trust-profile.yaml"
    owners_path = tmp_path / "owners.yaml"
    shutil.copy(OUTBOX_FIXTURES_DIR / "trust-profile.yaml", profile_path)
    shutil.copy(OUTBOX_FIXTURES_DIR / "owners.yaml", owners_path)
    return profile_path, owners_path


def test_before_dispatch_supersedes_a_stale_pending_intent_and_sends_nothing(conn, tmp_path, profile_paths):
    """R-S5-12"""
    profile_path, owners_path = profile_paths
    fixture = _load_fixture("target_movement")
    source = _source_repo(tmp_path, fixture["seed"])
    ticket_id, trees, runs_dir = _clone_ticket(conn, tmp_path, source, state="review")
    _plan_tuple(conn, ticket_id, trees.base_sha)

    slot = Slot(source_rule="owners", role="s6_reviewer")
    reviewer_set_id = record.insert(
        conn, "reviewer_set", ticket_id=ticket_id, kind="effective",
        content_hash="effective-set-1", slots=json.dumps([slot.to_json()]),
    )
    review_tuple_id = record.insert(
        conn, "evidence_tuple", kind="review", ticket_id=ticket_id,
        content_hash="review-subject-1", effective_reviewer_set_id=reviewer_set_id,
        effective_reviewer_set_hash="effective-set-1",
    )
    # `publication.review_approval_subject` -- the real subject an
    # `approval_record` for this gate now binds -- also needs one bound
    # blocking check result and packet/`pr_body` artefacts on record; a
    # bare review tuple is no longer enough to compute it.
    stage_run_id = record.insert(conn, "stage_run", ticket_id=ticket_id, stage="S5", attempt=1, outcome="pass")
    record.insert(
        conn, "check_result", stage_run_id=stage_run_id, evidence_tuple_id=review_tuple_id,
        check_name="fixture_check", check_tier="blocking", source="runner", result="pass",
        content_hash="check-1", canonical_serialization_version=1,
    )
    for kind, text in (("packet", "fixture packet\n"), ("pr_body", "fixture pr body\n")):
        path = runs_dir / f"{kind}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        artefact_registry.register(conn, ticket_id=ticket_id, kind=kind, path=path)
    subject = publication.review_approval_subject(conn, ticket_id)
    approvals.record_approval(
        conn, gate="review", subject_hash=subject.hash, slot_id=slot.slot_id,
        actor_identity="abhishek", role=slot.role, decision="approve",
        authority_policy_hash=owners.authority_policy_hash(), membership_snapshot_hash="members-1",
        attestation_version="v1", attestation_hash="att-1",
    )
    intent_id = outbox.intent_for_review_quorum(conn, ticket_id, runs_dir=runs_dir)
    conn.commit()
    assert intent_id is not None
    assert record.get(conn, "external_write", intent_id)["state"] == "pending"

    _write_files(source, fixture["target_commit"]["files"])
    _commit_all(source, fixture["target_commit"]["message"])

    outbox.reconcile_pending(conn, ticket_id, runs_dir=runs_dir, profile_path=profile_path, owners_path=owners_path)

    row = record.get(conn, "external_write", intent_id)
    assert row["state"] == "superseded"
    assert row["last_error"]

    profile = load_trust_profile(profile_path)
    deliverer = StubDeliverer(runs_dir / "remote" / f"{profile.routes['github_scratch'].id}.json")
    assert deliverer._load()["repositories"] == {}
