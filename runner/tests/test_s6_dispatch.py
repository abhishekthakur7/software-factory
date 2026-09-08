"""Full review quorum drives one `pr_create`/`pr_update` intent through the stub deliverer.

Reuses `test_s6_publication_subjects.py`'s ticket/review-tuple/approval
helpers, and the outbox fixture's trust-profile/owners pair and
`_activate` convention `test_outbox.py` established, so the guard and the
stub deliverer behave exactly as they do for every other dispatch test.
"""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from runner import governance, git_trees, outbox, publication, record
from runner.deliverers.stub import StubDeliverer
from runner.reviewer_sets import Slot
from runner.tests.test_s6_publication_subjects import S6_REVIEWER_IDENTITY, TICKET_FIXTURE, approve, conn, seed_review_tuple, seed_ticket
from runner.trust_profile import load_trust_profile

OUTBOX_FIXTURES_DIR = Path(__file__).parent / "fixtures" / "outbox"

FAR_FUTURE = "2999-01-01T00:00:00+00:00"

_COMMIT_ENV = {
    "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@example.invalid",
}

__all__ = ["conn"]  # re-exported fixture; keeps the import above from looking unused


@pytest.fixture
def runs_dir(tmp_path):
    return tmp_path / "runs"


@pytest.fixture
def profile_paths(tmp_path):
    profile_path = tmp_path / "trust-profile.yaml"
    owners_path = tmp_path / "owners.yaml"
    shutil.copy(OUTBOX_FIXTURES_DIR / "trust-profile.yaml", profile_path)
    shutil.copy(OUTBOX_FIXTURES_DIR / "owners.yaml", owners_path)
    return profile_path, owners_path


def _activate(conn, profile_path, owners_path, expires_at=FAR_FUTURE):
    proposal = governance.propose(profile_path, owners_path)
    for role in ("security_approver", "legal_data_governance_approver"):
        governance.decide(
            conn, proposal, actor_identity=S6_REVIEWER_IDENTITY, role=role, decision="approve",
            expires_at=expires_at, attestation_version="v1", attestation_hash=f"att-{role}",
            owners_path=owners_path, profile_path=profile_path,
        )
    conn.commit()


def _git(args, cwd, env=None):
    full_env = {**os.environ, **env} if env else None
    return subprocess.run(
        ["git", "-c", "commit.gpgsign=false", *args], cwd=cwd, env=full_env, capture_output=True, text=True, check=True,
    )


def give_real_base(conn, runs_dir, ticket_id) -> None:
    """A real, fetchable git base: `BEFORE_DISPATCH` freshness fetches it before ever calling the deliverer."""
    source = runs_dir.parent / f"source-repo-{ticket_id}"
    source.mkdir(parents=True)
    _git(["init", "-q"], cwd=source)
    _git(["checkout", "-q", "-b", "main"], cwd=source)
    (source / "README.md").write_text("seed\n")
    _git(["add", "-A"], cwd=source)
    _git(["commit", "-q", "-m", "init"], cwd=source, env=_COMMIT_ENV)
    trees = git_trees.clone_for_ticket(conn, ticket_id, source_checkout=source, target_branch="main", runs_dir=runs_dir)
    record.update(conn, "ticket", ticket_id, branch=TICKET_FIXTURE["branch"])
    record.insert(
        conn, "evidence_tuple", kind="plan", ticket_id=ticket_id,
        base_sha=trees.base_sha, target_base_sha=trees.base_sha, content_hash=f"plan-subject-{ticket_id}",
    )
    conn.commit()


def test_full_quorum_on_a_ticket_with_no_pr_identity_creates_one_pr_create_intent_with_a_receipt(conn, runs_dir, profile_paths):
    """R-S6-10: full quorum on a ticket with no PR identity creates one `pr_create` intent through the stub deliverer."""
    profile_path, owners_path = profile_paths
    _activate(conn, profile_path, owners_path)
    ticket_id = seed_ticket(conn)
    give_real_base(conn, runs_dir, ticket_id)
    slot = Slot(source_rule="owners", role="s6_reviewer", min_count=1)
    seed_review_tuple(conn, ticket_id, runs_dir, slots=[slot], content_hash="review-dispatch-create")
    subject = publication.review_approval_subject(conn, ticket_id)
    approve(conn, subject_hash=subject.hash, slot=slot, ticket_id=ticket_id)

    intent_id = outbox.intent_for_review_quorum(conn, ticket_id, runs_dir=runs_dir)
    assert intent_id is not None
    conn.commit()
    assert record.get(conn, "external_write", intent_id)["operation"] == "pr_create"

    outbox.reconcile_pending(conn, ticket_id, runs_dir=runs_dir, profile_path=profile_path, owners_path=owners_path)
    row = record.get(conn, "external_write", intent_id)
    assert row["state"] == "reconciled"
    assert row["receipt_artefact_id"] is not None
    assert record.get(conn, "ticket", ticket_id)["pr_identity"] is not None

    profile = load_trust_profile(profile_path)
    deliverer = StubDeliverer(runs_dir / "remote" / f"{profile.routes['github_pr'].id}.json")
    assert len(deliverer._load()["repositories"]["fixture-project"]["pull_requests"]) == 1


def test_a_second_quorum_after_a_recorded_revision_creates_one_pr_update_intent_with_a_receipt(conn, runs_dir, profile_paths):
    """R-S6-10: a ticket seeded at `pr_opened` with a recorded revision gets one `pr_update` intent on a second quorum."""
    profile_path, owners_path = profile_paths
    _activate(conn, profile_path, owners_path)
    ticket_id = seed_ticket(conn)
    give_real_base(conn, runs_dir, ticket_id)
    slot = Slot(source_rule="owners", role="s6_reviewer", min_count=1)
    seed_review_tuple(conn, ticket_id, runs_dir, slots=[slot], content_hash="review-dispatch-r1")
    subject = publication.review_approval_subject(conn, ticket_id)
    approve(conn, subject_hash=subject.hash, slot=slot, ticket_id=ticket_id)
    create_id = outbox.intent_for_review_quorum(conn, ticket_id, runs_dir=runs_dir)
    conn.commit()
    outbox.reconcile_pending(conn, ticket_id, runs_dir=runs_dir, profile_path=profile_path, owners_path=owners_path)
    assert record.get(conn, "external_write", create_id)["state"] == "reconciled"
    record.update(conn, "ticket", ticket_id, state="pr_opened")
    assert record.get(conn, "ticket", ticket_id)["pr_identity"] is not None

    # The recorded revision: a new head, a fresh review tuple bound to it,
    # and a fresh quorum against the new subject that revision creates.
    record.update(conn, "ticket", ticket_id, head_sha="head-sha-revised")
    seed_review_tuple(conn, ticket_id, runs_dir, slots=[slot], content_hash="review-dispatch-r2")
    subject2 = publication.review_approval_subject(conn, ticket_id)
    approve(conn, subject_hash=subject2.hash, slot=slot, ticket_id=ticket_id)

    update_id = outbox.intent_for_review_quorum(conn, ticket_id, runs_dir=runs_dir)
    assert update_id is not None
    conn.commit()
    assert record.get(conn, "external_write", update_id)["operation"] == "pr_update"

    outbox.reconcile_pending(conn, ticket_id, runs_dir=runs_dir, profile_path=profile_path, owners_path=owners_path)
    row = record.get(conn, "external_write", update_id)
    assert row["state"] == "reconciled"
    assert row["receipt_artefact_id"] is not None

    profile = load_trust_profile(profile_path)
    deliverer = StubDeliverer(runs_dir / "remote" / f"{profile.routes['github_pr'].id}.json")
    pull_requests = deliverer._load()["repositories"]["fixture-project"]["pull_requests"]
    assert len(pull_requests) == 1
    assert list(pull_requests.values())[0]["head_sha"] == "head-sha-revised"
