"""R-S6-3: GitHub dispatch uses the outbox crash and escalation paths, not an adapter-only substitute."""
import pytest
import shutil
from pathlib import Path

from runner import canonical, outbox, record, trust_profile
from runner.db import connect
from runner.deliverers.github import GitHubDeliverer, GitHubNonRetryable
from runner.tests.fakes.github_transport import FakeGitHubTransport
from runner.tests import test_outbox as harness


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
    profile_path, owners_path = tmp_path / "trust-profile.yaml", tmp_path / "owners.yaml"
    shutil.copy(harness.FIXTURES_DIR / "trust-profile.yaml", profile_path)
    shutil.copy(harness.FIXTURES_DIR / "owners.yaml", owners_path)
    return profile_path, owners_path


def test_r_s6_3_retry_reconciles_the_existing_github_pull_request_by_its_branch_and_approved_body():
    remote = FakeGitHubTransport()
    intent = {
        "repository": "soft-factory-scratch", "expected_prior_remote_head_sha": None,
        "pr_body_hash": canonical.content_hash({"pr_body": "approved body"}), "payload_digest": "payload", "idempotency_key": "key",
    }
    payload = {"branch_ref": "scratch/ticket-1", "head_sha": "head-1", "target_ref": "main", "pr_body": "approved body"}
    receipt = GitHubDeliverer(remote).pr_create(intent, payload)
    recovered = GitHubDeliverer(remote).open_pull_request("soft-factory-scratch", "scratch/ticket-1")
    assert recovered is not None
    assert recovered[0] == receipt.remote_pr_identity
    assert recovered[1]["head_sha"] == receipt.remote_head_sha
    assert recovered[1]["body_hash"] == receipt.body_hash


def _github_intent(conn, runs_dir):
    ticket_id = harness.seed_ticket(conn, state="review")
    intent_id = outbox.create_intent(
        conn, ticket_id=ticket_id, operation="pr_create",
        payload={"branch_ref": "scratch/ticket-1", "head_sha": "head-1", "target_ref": "main", "pr_body": "approved body"},
        runs_dir=runs_dir, repository="soft-factory-scratch", target_ref="main", head_ref="scratch/ticket-1",
        desired_remote_head_sha="head-1", expected_prior_remote_head_sha=None, review_approval_subject_hash="subject", review_approval_set_hash="set",
    )
    conn.commit()
    return ticket_id, intent_id


def test_r_s6_3_after_remote_success_crash_reconciles_one_github_pull_request(conn, runs_dir, profile_paths, monkeypatch):
    profile_path, owners_path = profile_paths
    harness._activate(conn, profile_path, owners_path)
    ticket_id, intent_id = _github_intent(conn, runs_dir)
    remote = FakeGitHubTransport()
    route = trust_profile.load_trust_profile(profile_path).routes["github_scratch"]
    monkeypatch.setattr(outbox, "_route_and_deliverer", lambda *args, **kwargs: (route, GitHubDeliverer(remote)))
    with pytest.raises(outbox.InjectedCrash, match="after_remote_success"):
        outbox.dispatch(conn, intent_id, fault="after_remote_success", runs_dir=runs_dir, profile_path=profile_path, owners_path=owners_path)
    assert record.get(conn, "external_write", intent_id)["state"] == "sending"
    outbox._reconcile_sending(conn, record.get(conn, "external_write", intent_id), runs_dir=runs_dir, profile_path=profile_path, owners_path=owners_path, now=None)
    assert record.get(conn, "external_write", intent_id)["state"] == "reconciled"
    assert len(remote.pull_requests) == 1


def test_r_s6_3_nonretryable_pre_dispatch_github_control_failure_escalates(conn, runs_dir, profile_paths, monkeypatch):
    profile_path, owners_path = profile_paths
    harness._activate(conn, profile_path, owners_path)
    ticket_id, intent_id = _github_intent(conn, runs_dir)

    class RefusingDeliverer(GitHubDeliverer):
        def open_pull_request(self, repository, head_ref):
            raise GitHubNonRetryable("GitHub GET was not authorised")

    route = trust_profile.load_trust_profile(profile_path).routes["github_scratch"]
    monkeypatch.setattr(outbox, "_route_and_deliverer", lambda *args, **kwargs: (route, RefusingDeliverer(FakeGitHubTransport())))
    outbox._dispatch_pending(conn, record.get(conn, "external_write", intent_id), runs_dir=runs_dir, profile_path=profile_path, owners_path=owners_path, now=None)
    assert record.get(conn, "external_write", intent_id)["state"] == "failed"
    assert record.get(conn, "ticket", ticket_id)["state"] == "escalated"


def test_r_s6_3_before_send_crash_retries_once_against_the_github_transport(conn, runs_dir, profile_paths, monkeypatch):
    profile_path, owners_path = profile_paths
    harness._activate(conn, profile_path, owners_path)
    _, intent_id = _github_intent(conn, runs_dir)
    remote = FakeGitHubTransport()
    route = trust_profile.load_trust_profile(profile_path).routes["github_scratch"]
    monkeypatch.setattr(outbox, "_route_and_deliverer", lambda *args, **kwargs: (route, GitHubDeliverer(remote)))
    with pytest.raises(outbox.InjectedCrash, match="before_send"):
        outbox.dispatch(conn, intent_id, fault="before_send", runs_dir=runs_dir, profile_path=profile_path, owners_path=owners_path)
    assert record.get(conn, "external_write", intent_id)["state"] == "pending"
    assert remote.calls == []
    outbox.dispatch(conn, intent_id, runs_dir=runs_dir, profile_path=profile_path, owners_path=owners_path)
    assert record.get(conn, "external_write", intent_id)["state"] == "reconciled"
    assert len(remote.pull_requests) == 1


def test_must_reject_r_s6_3_redispatch_while_github_success_is_ambiguous(conn, runs_dir, profile_paths, monkeypatch):
    from runner.deliverers.github import GitHubRemoteRefused

    profile_path, owners_path = profile_paths
    harness._activate(conn, profile_path, owners_path)
    ticket_id, intent_id = _github_intent(conn, runs_dir)
    record.update(conn, "external_write", intent_id, state="sending")
    conn.commit()
    remote = FakeGitHubTransport()
    def unreadable(*args):
        raise GitHubRemoteRefused("remote state cannot be observed")
    monkeypatch.setattr(remote, "open_pull_request", unreadable)
    route = trust_profile.load_trust_profile(profile_path).routes["github_scratch"]
    monkeypatch.setattr(outbox, "_route_and_deliverer", lambda *args, **kwargs: (route, GitHubDeliverer(remote)))
    with pytest.raises(GitHubRemoteRefused, match="cannot be observed"):
        outbox.reconcile_pending(conn, ticket_id, runs_dir=runs_dir, profile_path=profile_path, owners_path=owners_path)
    assert record.get(conn, "external_write", intent_id)["state"] == "sending"
    assert record.get(conn, "ticket", ticket_id)["state"] == "review"
    assert remote.calls == []
