"""The transactional outbox: intent creation, guarded dispatch, and reconciliation.

Every test that dispatches or reconciles an intent activates a tmp copy of
the fixture trust profile first, the same `profile_paths`/`_activate`
convention `test_guard.py` uses, so a wrong guard computation would fail
these tests too rather than only its own. `StubDeliverer`'s own state file
lives under a tmp `runs_dir`, one JSON document per route, so two tests
never see each other's fake remote.
"""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from runner import approvals, artefact_registry, cli, git_trees, governance, outbox, owners, publication, queue, record, transitions
from runner.db import connect
from runner.deliverers.stub import Receipt, StubDeliverer
from runner.reviewer_sets import Slot
from runner.trust_profile import DEFAULT_TRUST_PROFILE_PATH, load_trust_profile

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "outbox"
TICKET_FIXTURE = yaml.safe_load((FIXTURES_DIR / "ticket.yaml").read_text())["base"]
QUORUM_FIXTURE = yaml.safe_load((FIXTURES_DIR / "review_quorum.yaml").read_text())
REMOTE_SCENARIOS = yaml.safe_load((FIXTURES_DIR / "remote_scenarios.yaml").read_text())

FAR_FUTURE = "2999-01-01T00:00:00+00:00"


@pytest.fixture
def conn(tmp_path):
    connection = connect(tmp_path / "factory.sqlite")
    yield connection
    connection.close()


@pytest.fixture
def runs_dir(tmp_path):
    return tmp_path / "runs"


@pytest.fixture
def profile_paths(tmp_path):
    """A tmp copy of the fixture trust profile and owners file."""
    profile_path = tmp_path / "trust-profile.yaml"
    owners_path = tmp_path / "owners.yaml"
    shutil.copy(FIXTURES_DIR / "trust-profile.yaml", profile_path)
    shutil.copy(FIXTURES_DIR / "owners.yaml", owners_path)
    return profile_path, owners_path


def _activate(conn, profile_path, owners_path, expires_at=FAR_FUTURE):
    """Satisfy the trust profile's quorum through the real governance decisions."""
    proposal = governance.propose(profile_path, owners_path)
    for role in ("security_approver", "legal_data_governance_approver"):
        governance.decide(
            conn, proposal,
            actor_identity="abhishek", role=role, decision="approve",
            expires_at=expires_at, attestation_version="v1", attestation_hash=f"att-{role}",
            owners_path=owners_path, profile_path=profile_path,
        )
    conn.commit()
    return proposal


def seed_ticket(conn, **overrides) -> int:
    fields = {**TICKET_FIXTURE, **overrides}
    fields.setdefault("opened_at", record.now())
    return record.insert(conn, "ticket", **fields)


def seed_effective_reviewer_set(conn, ticket_id: int, slot: Slot) -> int:
    return record.insert(
        conn, "reviewer_set", ticket_id=ticket_id, kind="effective",
        content_hash=f"effective-set-{ticket_id}-{slot.slot_id}",
        slots=json.dumps([slot.to_json()]),
    )


def seed_review_evidence(conn, ticket_id: int, runs_dir, *, content_hash: str) -> Slot:
    """A review `evidence_tuple` bound to one blocking `check_result`, plus the packet and `pr_body`
    artefacts a real `publication.review_approval_subject` needs -- everything short of the approval
    itself, so a test that wants to seed its own approval row can still build on a real subject."""
    slot = Slot(**QUORUM_FIXTURE["slot"])
    reviewer_set_id = seed_effective_reviewer_set(conn, ticket_id, slot)
    review_tuple_id = record.insert(
        conn, "evidence_tuple", kind="review", ticket_id=ticket_id,
        content_hash=content_hash, effective_reviewer_set_id=reviewer_set_id,
        effective_reviewer_set_hash=f"effective-set-{ticket_id}-{slot.slot_id}", created_at=record.now(),
    )
    stage_run_id = record.insert(conn, "stage_run", ticket_id=ticket_id, stage="S5", attempt=1, outcome="pass")
    record.insert(
        conn, "check_result", stage_run_id=stage_run_id, evidence_tuple_id=review_tuple_id,
        check_name="fixture_check", check_tier="blocking", source="runner", result="pass",
        content_hash=f"check-{content_hash}", canonical_serialization_version=1,
    )
    if artefact_registry.latest(conn, ticket_id, "packet") is None:
        packet_path = runs_dir / "tickets" / str(ticket_id) / "packet.md"
        packet_path.parent.mkdir(parents=True, exist_ok=True)
        packet_path.write_text("fixture packet\n")
        artefact_registry.register(conn, ticket_id=ticket_id, kind="packet", path=packet_path)
    if artefact_registry.latest(conn, ticket_id, "pr_body") is None:
        pr_body_path = runs_dir / "tickets" / str(ticket_id) / "pr_body.md"
        pr_body_path.parent.mkdir(parents=True, exist_ok=True)
        pr_body_path.write_text("fixture pr body\n")
        artefact_registry.register(conn, ticket_id=ticket_id, kind="pr_body", path=pr_body_path)
    return slot


def seed_review_quorum(conn, ticket_id: int, runs_dir, *, content_hash: str) -> Slot:
    """`seed_review_evidence` plus the one approval, against the real computed subject, that satisfies it."""
    slot = seed_review_evidence(conn, ticket_id, runs_dir, content_hash=content_hash)
    subject = publication.review_approval_subject(conn, ticket_id)
    approvals.record_approval(
        conn, gate="review", subject_hash=subject.hash, slot_id=slot.slot_id,
        actor_identity=QUORUM_FIXTURE["actor"], role=slot.role, decision="approve",
        authority_policy_hash=owners.authority_policy_hash(), membership_snapshot_hash="members-1",
        attestation_version="v1", attestation_hash="att-1",
    )
    return slot


def fixture_pr_body_hash() -> str:
    """The `pr_body_hash` every fixture ticket's intent carries: `seed_review_evidence`'s registered `pr_body` text."""
    from runner import canonical
    return canonical.content_hash({"pr_body": "fixture pr body\n"})


def pr_create_intent(conn, ticket_id, runs_dir, *, content_hash="review-subject-1") -> int:
    seed_review_quorum(conn, ticket_id, runs_dir, content_hash=content_hash)
    intent_id = outbox.intent_for_review_quorum(conn, ticket_id, runs_dir=runs_dir)
    conn.commit()
    return intent_id


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


def give_real_base(conn, runs_dir, ticket_id) -> None:
    """Give `ticket_id` a real, fetchable git base and a matching plan tuple.

    `_dispatch_pending`'s `BEFORE_DISPATCH` freshness check fetches the
    real configured target branch from `runs_dir/tickets/<id>/repo`, so a
    ticket seeded from the fixture's fake SHA strings alone can no longer
    reach `dispatch` on its own. `clone_for_ticket` renames the ticket's
    own branch to its own convention; every test that reads `ticket.branch`
    back expects the fixture's own name, so it is restored immediately
    after -- freshness itself never checks out that branch, only ever
    comparing the recorded name as a plain string.
    """
    source = runs_dir.parent / f"source-repo-{ticket_id}"
    source.mkdir(parents=True)
    _git(["init", "-q"], cwd=source)
    _git(["checkout", "-q", "-b", "main"], cwd=source)
    (source / "README.md").write_text("seed\n")
    _git(["add", "-A"], cwd=source)
    _git(["commit", "-q", "-m", "init"], cwd=source, env=_COMMIT_ENV)

    trees = git_trees.clone_for_ticket(
        conn, ticket_id, source_checkout=source, target_branch="main", runs_dir=runs_dir,
    )
    record.update(conn, "ticket", ticket_id, branch=TICKET_FIXTURE["branch"])
    record.insert(
        conn, "evidence_tuple", kind="plan", ticket_id=ticket_id,
        base_sha=trees.base_sha, target_base_sha=trees.base_sha, content_hash=f"plan-subject-real-base-{ticket_id}",
    )
    conn.commit()



def test_seeded_external_write_row_carries_every_named_field(conn, runs_dir):
    """R-T-11: a seeded row carries id, keys, digests, hashes, refs, state, counters, and timestamps."""
    ticket_id = seed_ticket(conn)
    stage_run_id = record.insert(conn, "stage_run", ticket_id=ticket_id, stage="S6", attempt=1, outcome="pass")
    intent_id = outbox.create_intent(
        conn, ticket_id=ticket_id, operation="pr_create",
        payload={"branch_ref": "feature/x", "head_sha": "h1", "target_ref": "main", "pr_body": "body"},
        runs_dir=runs_dir, stage_run_id=stage_run_id,
        review_tuple_id=None, review_approval_subject_hash="subj-1", review_approval_set_hash="set-1",
        repository="fixture-project", target_ref="main", head_ref="feature/x",
        desired_remote_head_sha="h1", expected_prior_remote_head_sha=None,
    )
    conn.commit()
    row = record.get(conn, "external_write", intent_id)
    for column in (
        "id", "ticket_id", "stage_run_id", "operation", "idempotency_key", "payload_artefact_id",
        "payload_digest", "review_approval_subject_hash", "review_approval_set_hash",
        "publication_target_hash", "repository", "target_ref", "head_ref", "desired_remote_head_sha",
        "pr_body_hash", "revision", "state", "attempt_count", "created_at",
    ):
        assert row[column] is not None, column
    for column in ("guard_decision_id", "remote_pr_identity", "remote_identity", "receipt_artefact_id", "last_error"):
        assert column in row.keys()



def test_pr_operation_rows_carry_review_hashes_digest_and_jira_do_not(conn, runs_dir):
    """R-T-11: review-tuple and approval-subject/set hashes are null for `digest`/`jira_feedback`."""
    ticket_id = seed_ticket(conn)
    pr_id = outbox.create_intent(
        conn, ticket_id=ticket_id, operation="pr_create",
        payload={"branch_ref": "feature/x", "head_sha": "h1", "target_ref": "main", "pr_body": ""},
        runs_dir=runs_dir,
        review_approval_subject_hash="subj-1", review_approval_set_hash="set-1",
        repository="fixture-project", target_ref="main", head_ref="feature/x", desired_remote_head_sha="h1",
    )
    digest_id = outbox.create_intent(
        conn, ticket_id=ticket_id, operation="digest",
        payload={"ticket_id": str(ticket_id), "tier": "T2", "item_kind": "send_back", "age": "3d", "command": "x"},
        runs_dir=runs_dir,
    )
    conn.commit()
    pr_row = record.get(conn, "external_write", pr_id)
    digest_row = record.get(conn, "external_write", digest_id)
    assert pr_row["review_approval_subject_hash"] == "subj-1"
    assert pr_row["review_approval_set_hash"] == "set-1"
    assert digest_row["review_approval_subject_hash"] is None
    assert digest_row["review_approval_set_hash"] is None
    assert digest_row["review_tuple_id"] is None



@pytest.mark.parametrize(
    "operation,payload,extra",
    [
        (
            "pr_create",
            {"branch_ref": "feature/x", "head_sha": "h1", "target_ref": "main", "pr_body": ""},
            {"repository": "fixture-project", "target_ref": "main", "head_ref": "feature/x", "desired_remote_head_sha": "h1"},
        ),
        (
            "pr_update",
            {"branch_ref": "feature/x", "head_sha": "h2", "target_ref": "main", "pr_body": ""},
            {
                "repository": "fixture-project", "target_ref": "main", "head_ref": "feature/x",
                "desired_remote_head_sha": "h2", "expected_prior_remote_head_sha": "h1",
                "remote_pr_identity": "fixture-project#1",
            },
        ),
        (
            "digest",
            {"ticket_id": "1", "tier": "T2", "item_kind": "send_back", "age": "3d", "command": "/factory show 1"},
            {},
        ),
        (
            "jira_feedback",
            {"ticket_id": "1", "comment_text": "done", "status_summary": "merged"},
            {},
        ),
    ],
)
def test_each_operation_writes_one_row_under_its_key_rule(conn, runs_dir, operation, payload, extra):
    """R-T-11: creating the same intent twice under one operation returns the same row."""
    ticket_id = seed_ticket(conn)
    first = outbox.create_intent(conn, ticket_id=ticket_id, operation=operation, payload=payload, runs_dir=runs_dir, **extra)
    second = outbox.create_intent(conn, ticket_id=ticket_id, operation=operation, payload=payload, runs_dir=runs_dir, **extra)
    conn.commit()
    assert first == second
    assert record.get(conn, "external_write", first)["operation"] == operation



def test_pending_pr_create_reconciles_an_existing_matching_pull_request_before_creating(conn, runs_dir, profile_paths):
    """R-T-11: an open pull request already matching the desired head and body is adopted, not recreated."""
    profile_path, owners_path = profile_paths
    _activate(conn, profile_path, owners_path)
    ticket_id = seed_ticket(conn)
    intent_id = pr_create_intent(conn, ticket_id, runs_dir)

    scenario = REMOTE_SCENARIOS["existing_pull_request"]
    profile = load_trust_profile(profile_path)
    deliverer = StubDeliverer(runs_dir / "remote" / f"{profile.routes['github_scratch'].id}.json")
    deliverer.seed_pull_request(
        scenario["repository"], scenario["identity"], head_ref=scenario["head_ref"],
        target_ref=scenario["target_ref"], head_sha=scenario["head_sha"], body_hash=fixture_pr_body_hash(),
    )

    acted = outbox.reconcile_pending(conn, ticket_id, runs_dir=runs_dir, profile_path=profile_path, owners_path=owners_path)
    assert acted == [intent_id]
    row = record.get(conn, "external_write", intent_id)
    assert row["state"] == "reconciled"
    assert row["remote_pr_identity"] == scenario["identity"]
    assert deliverer._load()["repositories"][scenario["repository"]]["pull_requests"].keys() == {scenario["identity"]}


def test_must_reject_pr_create_over_an_unexpected_remote_head(conn, runs_dir, profile_paths):
    """R-T-11: a branch already at a head this intent never expected is never overwritten."""
    profile_path, owners_path = profile_paths
    _activate(conn, profile_path, owners_path)
    ticket_id = seed_ticket(conn)
    intent_id = pr_create_intent(conn, ticket_id, runs_dir)

    scenario = REMOTE_SCENARIOS["unexpected_head"]
    profile = load_trust_profile(profile_path)
    deliverer = StubDeliverer(runs_dir / "remote" / f"{profile.routes['github_scratch'].id}.json")
    deliverer.set_branch_head(scenario["repository"], scenario["ref"], scenario["sha"])

    outbox.reconcile_pending(conn, ticket_id, runs_dir=runs_dir, profile_path=profile_path, owners_path=owners_path)
    row = record.get(conn, "external_write", intent_id)
    assert row["state"] == "failed"
    assert row["last_error"] == "unexpected_remote_head"
    assert deliverer.branch_head(scenario["repository"], scenario["ref"]) == scenario["sha"]


def test_pending_pr_update_requires_the_previously_reconciled_head_and_updates_the_same_pr(conn, runs_dir, profile_paths):
    """R-T-11: `pr_update` applies compare-and-set against the ticket's last reconciled head and never opens a replacement."""
    profile_path, owners_path = profile_paths
    _activate(conn, profile_path, owners_path)
    ticket_id = seed_ticket(conn)
    give_real_base(conn, runs_dir, ticket_id)
    create_id = pr_create_intent(conn, ticket_id, runs_dir, content_hash="review-subject-create")
    outbox.reconcile_pending(conn, ticket_id, runs_dir=runs_dir, profile_path=profile_path, owners_path=owners_path)
    assert record.get(conn, "external_write", create_id)["state"] == "reconciled"
    pr_identity = record.get(conn, "ticket", ticket_id)["pr_identity"]

    record.update(conn, "ticket", ticket_id, head_sha="head-sha-2")
    update_id = pr_create_intent(conn, ticket_id, runs_dir, content_hash="review-subject-update")
    assert record.get(conn, "external_write", update_id)["operation"] == "pr_update"

    outbox.reconcile_pending(conn, ticket_id, runs_dir=runs_dir, profile_path=profile_path, owners_path=owners_path)
    row = record.get(conn, "external_write", update_id)
    assert row["state"] == "reconciled"
    assert row["remote_pr_identity"] == pr_identity

    profile = load_trust_profile(profile_path)
    deliverer = StubDeliverer(runs_dir / "remote" / f"{profile.routes['github_scratch'].id}.json")
    pull_requests = deliverer._load()["repositories"]["fixture-project"]["pull_requests"]
    assert pull_requests.keys() == {pr_identity}
    assert pull_requests[pr_identity]["head_sha"] == "head-sha-2"


def test_must_reject_pr_update_race_on_unexpected_remote_head(conn, runs_dir, profile_paths):
    """R-T-11: a `pr_update` intent dispatched against a head other than the expected prior head is refused."""
    profile_path, owners_path = profile_paths
    _activate(conn, profile_path, owners_path)
    ticket_id = seed_ticket(conn)
    give_real_base(conn, runs_dir, ticket_id)
    create_id = pr_create_intent(conn, ticket_id, runs_dir, content_hash="review-subject-create")
    outbox.reconcile_pending(conn, ticket_id, runs_dir=runs_dir, profile_path=profile_path, owners_path=owners_path)
    assert record.get(conn, "external_write", create_id)["state"] == "reconciled"
    stored_head = record.get(conn, "ticket", ticket_id)["last_remote_head_sha"]

    profile = load_trust_profile(profile_path)
    deliverer = StubDeliverer(runs_dir / "remote" / f"{profile.routes['github_scratch'].id}.json")
    deliverer.set_branch_head("fixture-project", "feature/fixture-outbox", "raced-away-commit")

    record.update(conn, "ticket", ticket_id, head_sha="head-sha-2")
    update_id = pr_create_intent(conn, ticket_id, runs_dir, content_hash="review-subject-update")

    outbox.reconcile_pending(conn, ticket_id, runs_dir=runs_dir, profile_path=profile_path, owners_path=owners_path)
    row = record.get(conn, "external_write", update_id)
    assert row["state"] == "failed"
    assert row["last_error"] == "unexpected_remote_head"
    assert record.get(conn, "ticket", ticket_id)["last_remote_head_sha"] == stored_head


def test_pr_update_against_a_pull_request_from_a_driven_create_reconciles_without_a_replacement(conn, runs_dir, profile_paths):
    """R-T-11: a `pr_update` dispatched while the stub already holds an open PR from a driven create reconciles to it."""
    profile_path, owners_path = profile_paths
    _activate(conn, profile_path, owners_path)
    ticket_id = seed_ticket(conn)
    give_real_base(conn, runs_dir, ticket_id)

    profile = load_trust_profile(profile_path)
    deliverer = StubDeliverer(runs_dir / "remote" / f"{profile.routes['github_scratch'].id}.json")
    driven_identity = "fixture-project#driven-2"
    deliverer.set_branch_head("fixture-project", "feature/fixture-outbox", "head-sha-1")
    deliverer.seed_pull_request(
        "fixture-project", driven_identity, head_ref="feature/fixture-outbox", target_ref="main",
        head_sha="head-sha-1", body_hash=fixture_pr_body_hash(),
    )

    record.update(conn, "ticket", ticket_id, pr_identity=driven_identity, last_remote_head_sha="head-sha-1")
    record.update(conn, "ticket", ticket_id, head_sha="head-sha-2")
    update_id = pr_create_intent(conn, ticket_id, runs_dir, content_hash="review-subject-driven")
    assert record.get(conn, "external_write", update_id)["operation"] == "pr_update"

    outbox.reconcile_pending(conn, ticket_id, runs_dir=runs_dir, profile_path=profile_path, owners_path=owners_path)
    row = record.get(conn, "external_write", update_id)
    assert row["state"] == "reconciled"
    assert row["remote_pr_identity"] == driven_identity
    pull_requests = deliverer._load()["repositories"]["fixture-project"]["pull_requests"]
    assert pull_requests.keys() == {driven_identity}



def test_review_quorum_approval_and_intent_land_in_one_transaction(conn, runs_dir):
    """R-T-11: the quorum-completing approval and the intent it authorises never land separately."""
    ticket_id = seed_ticket(conn)
    slot = seed_review_evidence(conn, ticket_id, runs_dir, content_hash="review-subject-atomic")
    subject = publication.review_approval_subject(conn, ticket_id)
    approvals.record_approval(
        conn, gate="review", subject_hash=subject.hash, slot_id=slot.slot_id,
        actor_identity=QUORUM_FIXTURE["actor"], role=slot.role, decision="approve",
        authority_policy_hash=owners.authority_policy_hash(), membership_snapshot_hash="members-1",
        attestation_version="v1", attestation_hash="att-1",
    )
    intent_id = outbox.intent_for_review_quorum(conn, ticket_id, runs_dir=runs_dir)
    assert intent_id is not None
    conn.commit()
    assert record.get(conn, "approval_record", 1) is not None
    assert record.get(conn, "external_write", intent_id) is not None


def test_must_reject_by_construction_a_rolled_back_transaction_leaves_neither_row(tmp_path):
    """R-T-11: rolling back before the shared commit leaves neither the approval nor the intent behind."""
    db_path = tmp_path / "atomic.sqlite"
    conn = connect(db_path)
    try:
        ticket_id = seed_ticket(conn)
        slot = seed_review_evidence(conn, ticket_id, tmp_path / "runs", content_hash="review-subject-rollback")
        subject = publication.review_approval_subject(conn, ticket_id)
        approvals.record_approval(
            conn, gate="review", subject_hash=subject.hash, slot_id=slot.slot_id,
            actor_identity=QUORUM_FIXTURE["actor"], role=slot.role, decision="approve",
            authority_policy_hash=owners.authority_policy_hash(), membership_snapshot_hash="members-1",
            attestation_version="v1", attestation_hash="att-1",
        )
        intent_id = outbox.intent_for_review_quorum(conn, ticket_id, runs_dir=tmp_path / "runs")
        assert intent_id is not None
        conn.rollback()
    finally:
        conn.close()

    fresh = connect(db_path)
    try:
        assert fresh.execute("SELECT COUNT(*) FROM approval_record").fetchone()[0] == 0
        assert fresh.execute("SELECT COUNT(*) FROM external_write").fetchone()[0] == 0
    finally:
        fresh.close()



def test_stub_deliverer_holds_remote_state_across_calls(tmp_path):
    """R-T-11: branch head, pull-request identity, and body hash persist across separate `StubDeliverer` instances."""
    state_path = tmp_path / "remote" / "github_scratch.json"
    first = StubDeliverer(state_path)
    first.set_branch_head("fixture-project", "feature/x", "sha-1")
    first.seed_pull_request(
        "fixture-project", "fixture-project#1", head_ref="feature/x", target_ref="main",
        head_sha="sha-1", body_hash="body-hash-1",
    )

    second = StubDeliverer(state_path)
    assert second.branch_head("fixture-project", "feature/x") == "sha-1"
    identity, pr = second.open_pull_request("fixture-project", "feature/x")
    assert identity == "fixture-project#1"
    assert pr["body_hash"] == "body-hash-1"



def test_stub_driven_to_a_duplicate_key_returns_the_stored_receipt_not_a_second_object(conn, runs_dir, profile_paths):
    """R-T-11: a stub driven to already hold a receipt for an intent's key returns it instead of dispatching twice."""
    profile_path, owners_path = profile_paths
    _activate(conn, profile_path, owners_path)
    ticket_id = seed_ticket(conn)
    give_real_base(conn, runs_dir, ticket_id)
    intent_id = pr_create_intent(conn, ticket_id, runs_dir)
    key = record.get(conn, "external_write", intent_id)["idempotency_key"]

    profile = load_trust_profile(profile_path)
    deliverer = StubDeliverer(runs_dir / "remote" / f"{profile.routes['github_scratch'].id}.json")
    seeded = Receipt(
        remote_identity="fixture-project#seeded", remote_pr_identity="fixture-project#seeded",
        remote_head_sha="head-sha-1", body_hash=fixture_pr_body_hash(), payload_digest=record.get(conn, "external_write", intent_id)["payload_digest"],
        idempotency_key=key, created_at=record.now(),
    )
    deliverer.seed_receipt(key, seeded)

    outbox.reconcile_pending(conn, ticket_id, runs_dir=runs_dir, profile_path=profile_path, owners_path=owners_path)
    row = record.get(conn, "external_write", intent_id)
    assert row["state"] == "reconciled"
    assert row["remote_pr_identity"] == "fixture-project#seeded"
    assert deliverer._load()["repositories"] == {}



def test_crash_before_send_leaves_the_row_pending_and_retry_produces_one_object(conn, runs_dir, profile_paths):
    """R-T-11: a `pr_create` killed before the deliverer is called leaves the row `pending`; retry produces one object."""
    profile_path, owners_path = profile_paths
    _activate(conn, profile_path, owners_path)
    ticket_id = seed_ticket(conn)
    give_real_base(conn, runs_dir, ticket_id)
    intent_id = pr_create_intent(conn, ticket_id, runs_dir)

    with pytest.raises(outbox.InjectedCrash):
        outbox.dispatch(conn, intent_id, fault="before_send", runs_dir=runs_dir, profile_path=profile_path, owners_path=owners_path)
    assert record.get(conn, "external_write", intent_id)["state"] == "pending"

    outbox.reconcile_pending(conn, ticket_id, runs_dir=runs_dir, profile_path=profile_path, owners_path=owners_path)
    row = record.get(conn, "external_write", intent_id)
    assert row["state"] == "reconciled"
    profile = load_trust_profile(profile_path)
    deliverer = StubDeliverer(runs_dir / "remote" / f"{profile.routes['github_scratch'].id}.json")
    assert len(deliverer._load()["repositories"]["fixture-project"]["pull_requests"]) == 1


def test_crash_after_remote_success_reconciles_to_the_same_object_on_retry(conn, runs_dir, profile_paths):
    """R-T-11: killed after the stub records success but before the receipt is stored, retry reconciles to that object."""
    profile_path, owners_path = profile_paths
    _activate(conn, profile_path, owners_path)
    ticket_id = seed_ticket(conn)
    intent_id = pr_create_intent(conn, ticket_id, runs_dir)

    with pytest.raises(outbox.InjectedCrash):
        outbox.dispatch(conn, intent_id, fault="after_remote_success", runs_dir=runs_dir, profile_path=profile_path, owners_path=owners_path)
    row = record.get(conn, "external_write", intent_id)
    assert row["state"] == "sending"
    assert row["receipt_artefact_id"] is None

    outbox.reconcile_pending(conn, ticket_id, runs_dir=runs_dir, profile_path=profile_path, owners_path=owners_path)
    row = record.get(conn, "external_write", intent_id)
    assert row["state"] == "reconciled"
    profile = load_trust_profile(profile_path)
    deliverer = StubDeliverer(runs_dir / "remote" / f"{profile.routes['github_scratch'].id}.json")
    assert len(deliverer._load()["repositories"]["fixture-project"]["pull_requests"]) == 1


def test_crash_before_local_commit_reconciles_by_remote_identity_on_retry(conn, runs_dir, profile_paths):
    """R-T-11: killed after the receipt is returned but before the commit, a rolled-back retry reconciles by identity."""
    profile_path, owners_path = profile_paths
    _activate(conn, profile_path, owners_path)
    ticket_id = seed_ticket(conn)
    intent_id = pr_create_intent(conn, ticket_id, runs_dir)

    with pytest.raises(outbox.InjectedCrash):
        outbox.dispatch(conn, intent_id, fault="before_local_commit", runs_dir=runs_dir, profile_path=profile_path, owners_path=owners_path)
    conn.rollback()
    assert record.get(conn, "external_write", intent_id)["state"] == "sending"

    outbox.reconcile_pending(conn, ticket_id, runs_dir=runs_dir, profile_path=profile_path, owners_path=owners_path)
    row = record.get(conn, "external_write", intent_id)
    assert row["state"] == "reconciled"
    profile = load_trust_profile(profile_path)
    deliverer = StubDeliverer(runs_dir / "remote" / f"{profile.routes['github_scratch'].id}.json")
    assert len(deliverer._load()["repositories"]["fixture-project"]["pull_requests"]) == 1



def test_must_reject_two_intents_sharing_a_key_with_different_payloads(conn, runs_dir):
    """R-T-11: one idempotency key can never carry two different payload digests.

    `pr_create`'s key binds `pr_body`'s hash, not the rest of the payload,
    so two payloads that agree on every keyed field (including `pr_body`)
    but disagree on an unkeyed one (`branch_ref` here, which the operation
    otherwise gets from the explicit `head_ref` argument) hash the same key
    to two different payload digests -- exactly the collision the key rule
    exists to refuse.
    """
    ticket_id = seed_ticket(conn)
    outbox.create_intent(
        conn, ticket_id=ticket_id, operation="pr_create",
        payload={"branch_ref": "feature/x", "head_sha": "h1", "target_ref": "main", "pr_body": "same"},
        runs_dir=runs_dir, review_approval_subject_hash="subj-shared",
        repository="fixture-project", target_ref="main", head_ref="feature/x", desired_remote_head_sha="h1",
    )
    conn.commit()
    with pytest.raises(outbox.IntentRefused):
        outbox.create_intent(
            conn, ticket_id=ticket_id, operation="pr_create",
            payload={"branch_ref": "feature/y", "head_sha": "h1", "target_ref": "main", "pr_body": "same"},
            runs_dir=runs_dir, review_approval_subject_hash="subj-shared",
            repository="fixture-project", target_ref="main", head_ref="feature/x", desired_remote_head_sha="h1",
        )



@pytest.mark.parametrize("call", ["advance", "run", "act", "abandon"])
def test_every_state_advancing_command_reconciles_pending_rows_first(conn, runs_dir, call):
    """R-T-11: `factory advance`, `run`, `act` and `abandon` reconcile pending `external_write` rows before doing anything else."""
    # `cli.advance`/`cli.run` reconcile through the default (committed) trust
    # profile and owners file, since neither takes a profile/owners override --
    # activated here directly rather than through a tmp copy.
    _activate(conn, DEFAULT_TRUST_PROFILE_PATH, owners.DEFAULT_OWNERS_PATH)
    ticket_id = seed_ticket(conn, state="review")
    outbox.create_intent(
        conn, ticket_id=ticket_id, operation="digest",
        payload={"ticket_id": str(ticket_id), "tier": "T2", "item_kind": "send_back", "age": "3d", "command": "x"},
        runs_dir=runs_dir,
    )
    conn.commit()

    if call == "advance":
        cli.advance(conn, ticket_id, runs_dir)
    elif call == "run":
        cli.run(conn, ticket_id, "S5", runs_dir)
    elif call == "act":
        item_id = queue.open_item(conn, ticket_id=ticket_id, kind="rubric_inspection")
        queue.act(conn, item_id=item_id, action="close_inspection", actor="abhishek", runs_dir=runs_dir)
    else:
        queue.abandon(conn, ticket_id, actor="abhishek", fm_id="FM-19", runs_dir=runs_dir)

    rows = conn.execute("SELECT state FROM external_write WHERE ticket_id = ?", (ticket_id,)).fetchall()
    assert [row["state"] for row in rows] == ["reconciled"]



def test_stale_pending_intent_becomes_superseded_on_a_newer_one(conn, runs_dir):
    """R-T-11: a newer intent for the same ticket and operation supersedes an older pending one."""
    ticket_id = seed_ticket(conn)
    first_id = outbox.create_intent(
        conn, ticket_id=ticket_id, operation="pr_create",
        payload={"branch_ref": "feature/x", "head_sha": "h1", "target_ref": "main", "pr_body": "one"},
        runs_dir=runs_dir, repository="fixture-project", target_ref="main", head_ref="feature/x",
        desired_remote_head_sha="h1",
    )
    conn.commit()
    second_id = outbox.create_intent(
        conn, ticket_id=ticket_id, operation="pr_create",
        payload={"branch_ref": "feature/x", "head_sha": "h2", "target_ref": "main", "pr_body": "two"},
        runs_dir=runs_dir, repository="fixture-project", target_ref="main", head_ref="feature/x",
        desired_remote_head_sha="h2",
    )
    conn.commit()
    assert first_id != second_id
    assert record.get(conn, "external_write", first_id)["state"] == "superseded"
    assert record.get(conn, "external_write", second_id)["state"] == "pending"



def test_must_reject_creating_under_a_key_still_sending(conn, runs_dir):
    """R-T-11: a row still `sending` under a key must reconcile before another intent under that key is created."""
    ticket_id = seed_ticket(conn)
    payload = {"branch_ref": "feature/x", "head_sha": "h1", "target_ref": "main", "pr_body": ""}
    intent_id = outbox.create_intent(
        conn, ticket_id=ticket_id, operation="pr_create", payload=payload, runs_dir=runs_dir,
        repository="fixture-project", target_ref="main", head_ref="feature/x", desired_remote_head_sha="h1",
    )
    record.update(conn, "external_write", intent_id, state="sending")
    conn.commit()

    with pytest.raises(outbox.IntentRefused):
        outbox.create_intent(
            conn, ticket_id=ticket_id, operation="pr_create", payload=payload, runs_dir=runs_dir,
            repository="fixture-project", target_ref="main", head_ref="feature/x", desired_remote_head_sha="h1",
        )

    record.update(conn, "external_write", intent_id, state="reconciled")
    conn.commit()
    resolved = outbox.create_intent(
        conn, ticket_id=ticket_id, operation="pr_create", payload=payload, runs_dir=runs_dir,
        repository="fixture-project", target_ref="main", head_ref="feature/x", desired_remote_head_sha="h1",
    )
    assert resolved == intent_id



def test_review_to_pr_opened_advances_only_from_a_matching_reconciled_receipt(conn, runs_dir, profile_paths):
    """R-T-11: the transition fires only once the reconciled receipt's head and payload digest match the desired ones."""
    from runner import gates

    profile_path, owners_path = profile_paths
    _activate(conn, profile_path, owners_path)
    ticket_id = seed_ticket(conn)
    give_real_base(conn, runs_dir, ticket_id)
    pr_create_intent(conn, ticket_id, runs_dir)
    ticket = record.get(conn, "ticket", ticket_id)
    assert gates.review_gate(conn, ticket) is None, "quorum satisfied, but nothing reconciled yet"

    outbox.reconcile_pending(conn, ticket_id, runs_dir=runs_dir, profile_path=profile_path, owners_path=owners_path)
    ticket = record.get(conn, "ticket", ticket_id)
    event = gates.review_gate(conn, ticket)
    assert event == "review_quorum_reconciled"
    assert transitions.apply(conn, ticket_id, event) == "pr_opened"



def test_every_dispatched_intent_guards_its_payload_and_its_receipt(conn, runs_dir, profile_paths):
    """R-T-11: a dispatched intent leaves a guard decision for its outbound payload and for the receipt it stores.

    The payload's fields are exactly the route's allowlist, so its
    decision is `allow`; the receipt's field names share none of that
    allowlist, so projecting it drops everything and its decision is
    `redact` -- both are the guard actually passing the content, neither
    is `deny`, which is what "passes the guard" actually requires here.
    """
    profile_path, owners_path = profile_paths
    _activate(conn, profile_path, owners_path)
    ticket_id = seed_ticket(conn)
    give_real_base(conn, runs_dir, ticket_id)
    intent_id = pr_create_intent(conn, ticket_id, runs_dir)

    outbox.reconcile_pending(conn, ticket_id, runs_dir=runs_dir, profile_path=profile_path, owners_path=owners_path)
    row = record.get(conn, "external_write", intent_id)
    assert row["state"] == "reconciled"

    decisions = conn.execute(
        "SELECT * FROM guard_decision WHERE ticket_id = ? AND operation = 'outbox' ORDER BY id", (ticket_id,)
    ).fetchall()
    assert len(decisions) == 2
    assert all(d["decision"] in ("allow", "redact") for d in decisions)
    assert row["guard_decision_id"] == decisions[-1]["id"]

    receipt_artefact = record.get(conn, "artefact", row["receipt_artefact_id"])
    assert receipt_artefact["guard_decision_id"] == decisions[-1]["id"]



def test_full_quorum_produces_one_pr_create_then_a_revision_produces_one_pr_update(conn, runs_dir, profile_paths):
    """R-T-11: full review quorum yields one `pr_create` intent; a later revision yields one `pr_update`, each with a receipt."""
    profile_path, owners_path = profile_paths
    _activate(conn, profile_path, owners_path)
    ticket_id = seed_ticket(conn)
    give_real_base(conn, runs_dir, ticket_id)

    create_id = pr_create_intent(conn, ticket_id, runs_dir, content_hash="review-subject-r1")
    outbox.reconcile_pending(conn, ticket_id, runs_dir=runs_dir, profile_path=profile_path, owners_path=owners_path)
    create_row = record.get(conn, "external_write", create_id)
    assert create_row["operation"] == "pr_create"
    assert create_row["state"] == "reconciled"
    assert create_row["receipt_artefact_id"] is not None
    assert record.get(conn, "ticket", ticket_id)["factory_completed_at"] is not None

    record.update(conn, "ticket", ticket_id, head_sha="head-sha-revised")
    update_id = pr_create_intent(conn, ticket_id, runs_dir, content_hash="review-subject-r2")
    outbox.reconcile_pending(conn, ticket_id, runs_dir=runs_dir, profile_path=profile_path, owners_path=owners_path)
    update_row = record.get(conn, "external_write", update_id)
    assert update_row["operation"] == "pr_update"
    assert update_row["state"] == "reconciled"
    assert update_row["receipt_artefact_id"] is not None
    assert update_row["revision"] == 2

    profile = load_trust_profile(profile_path)
    deliverer = StubDeliverer(runs_dir / "remote" / f"{profile.routes['github_scratch'].id}.json")
    pull_requests = deliverer._load()["repositories"]["fixture-project"]["pull_requests"]
    assert len(pull_requests) == 1
    assert list(pull_requests.values())[0]["head_sha"] == "head-sha-revised"
