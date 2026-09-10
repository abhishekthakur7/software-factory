"""GitHub delivery mutates only a leased branch and its one draft pull request."""
import os
import subprocess

import pytest

from runner import canonical, project
from runner.deliverers import github
from runner.deliverers.github import GitHubDeliverer, GitHubRemoteRefused, GitHubRestClient
from runner.tests.fakes.github_transport import FakeGitHubTransport


def _intent(operation="pr_create", *, expected=None, remote_pr_identity=None):
    return {
        "operation": operation, "repository": "soft-factory-scratch", "expected_prior_remote_head_sha": expected,
        "remote_pr_identity": remote_pr_identity, "pr_body_hash": canonical.content_hash({"pr_body": "approved body"}),
        "payload_digest": "payload", "idempotency_key": "key",
    }


def _payload(head="head-1"):
    return {"branch_ref": "scratch/ticket-1", "head_sha": head, "target_ref": "main", "pr_body": "approved body"}


def test_create_pushes_the_ticket_branch_then_opens_one_draft_pull_request():
    remote = FakeGitHubTransport()
    receipt = GitHubDeliverer(remote).pr_create(_intent(), _payload())
    assert remote.branches[("soft-factory-scratch", "scratch/ticket-1")] == "head-1"
    assert receipt.remote_pr_identity == "1"
    assert [name for name, _ in remote.calls] == ["branch_head", "push_branch", "create_pull_request"]


def test_must_reject_create_when_the_remote_head_is_not_the_expected_head():
    remote = FakeGitHubTransport()
    remote.branches[("soft-factory-scratch", "scratch/ticket-1")] = "outside-change"
    with pytest.raises(GitHubRemoteRefused, match="unexpected remote head"):
        GitHubDeliverer(remote).pr_create(_intent(expected="known-head"), _payload())
    assert len(remote.pull_requests) == 0


def test_update_keeps_the_same_pull_request_under_a_force_with_lease_compare():
    remote = FakeGitHubTransport()
    deliverer = GitHubDeliverer(remote)
    deliverer.pr_create(_intent(), _payload("head-1"))
    receipt = deliverer.pr_update(_intent("pr_update", expected="head-1", remote_pr_identity="1"), _payload("head-2"))
    assert receipt.remote_pr_identity == "1"
    assert remote.pull_requests[("soft-factory-scratch", "scratch/ticket-1")]["head_sha"] == "head-2"


def test_must_reject_update_of_a_closed_pull_request_without_a_replacement():
    remote = FakeGitHubTransport()
    deliverer = GitHubDeliverer(remote)
    deliverer.pr_create(_intent(), _payload())
    remote.pull_requests[("soft-factory-scratch", "scratch/ticket-1")]["state"] = "closed"
    with pytest.raises(GitHubRemoteRefused, match="closed or merged"):
        deliverer.pr_update(_intent("pr_update", expected="head-1", remote_pr_identity="1"), _payload("head-2"))
    assert len(remote.pull_requests) == 1


def test_live_push_uses_the_configured_remote_and_a_full_ref_lease(monkeypatch, tmp_path):
    observed = {}

    def fake_run(argv, **kwargs):
        observed["argv"] = argv
        observed["env"] = kwargs["env"]
        observed["timeout"] = kwargs["timeout"]
        return type("Completed", (), {"returncode": 0})()

    monkeypatch.setattr("runner.deliverers.github.subprocess.run", fake_run)
    monkeypatch.setenv("AMBIENT_CREDENTIAL", "must-not-reach-git")
    client = GitHubRestClient("not-recorded", remote_url="https://github.com/owner/scratch.git", checkout=tmp_path)
    client.push_branch("soft-factory-scratch", "scratch/ticket-1", "head-2", "head-1")
    assert observed["argv"] == [
        "git", "-c", "credential.helper=", "-c", "core.hooksPath=/dev/null", "push", "https://github.com/owner/scratch.git", "head-2:refs/heads/scratch/ticket-1",
        "--force-with-lease=refs/heads/scratch/ticket-1:head-1",
    ]
    assert "not-recorded" not in " ".join(observed["argv"])
    assert observed["env"]["GIT_CONFIG_NOSYSTEM"] == "1"
    assert observed["env"]["GIT_CONFIG_GLOBAL"] == os.devnull
    assert observed["env"]["GIT_TERMINAL_PROMPT"] == "0"
    assert observed["env"]["SOFT_FACTORY_GITHUB_TOKEN"] == "not-recorded"
    assert "AMBIENT_CREDENTIAL" not in observed["env"]
    assert observed["timeout"] == 30


def test_askpass_helper_runs_from_an_unrelated_working_directory(tmp_path):
    helper_dir = tmp_path / "helper"
    helper_dir.mkdir()
    unrelated_cwd = tmp_path / "checkout"
    unrelated_cwd.mkdir()
    helper = github._write_askpass_helper(helper_dir)

    completed = subprocess.run(
        [str(helper), "Password for https://github.com:"], cwd=unrelated_cwd,
        env={"PATH": "/usr/bin:/bin", "SOFT_FACTORY_GITHUB_TOKEN": "test-token"}, capture_output=True, text=True, check=True,
    )

    assert completed.stdout == "test-token\n"


@pytest.mark.parametrize(
    ("remote", "error"),
    [(None, "not configured"), ("https://github.com/owner/other.git", "canonical GitHub HTTPS")],
)
def test_must_reject_an_unusable_live_remote_before_fetching_a_credential(monkeypatch, tmp_path, remote, error):
    fetched = False

    def fetch(_role):
        nonlocal fetched
        fetched = True
        return "never-used"

    monkeypatch.setattr(project, "load", lambda: {"scratch_repository": {"name": "owner/scratch", "remote": remote}})
    monkeypatch.setattr("runner.deliverers.github.credentials.fetch", fetch)

    with pytest.raises(GitHubRemoteRefused, match=error):
        GitHubDeliverer(client_factory=lambda _token: FakeGitHubTransport(), runs_dir=tmp_path).branch_head("owner/scratch", "scratch/ticket-1")

    assert not fetched


def test_open_pull_request_lists_owner_qualified_head_refs(monkeypatch):
    observed = {}
    client = GitHubRestClient("token", remote_url="https://github.com/owner/scratch.git")

    def request(method, path, body=None):
        observed.update(method=method, path=path, body=body)
        return []

    monkeypatch.setattr(client, "_request", request)
    assert client.open_pull_request("owner/scratch", "scratch/ticket-1") is None
    assert observed == {
        "method": "GET", "path": "/repos/owner/scratch/pulls?state=all&head=owner%3Ascratch%2Fticket-1&per_page=100", "body": None,
    }


def test_must_reject_a_branch_outside_the_configured_scratch_prefix():
    with pytest.raises(GitHubRemoteRefused, match="scratch prefix"):
        GitHubDeliverer(FakeGitHubTransport()).pr_create(_intent(), {**_payload(), "branch_ref": "feature/ticket-1"})


@pytest.mark.parametrize("route_id", ["github_scratch", "slack_digest"])
def test_must_reject_incomplete_live_configuration_without_fixture_receipt(tmp_path, monkeypatch, route_id):
    from dataclasses import replace
    from runner import outbox, project, trust_profile
    from runner.deliverers.stub import RemoteRefused

    route = replace(trust_profile.load_trust_profile().routes[route_id], deliverer="live")
    monkeypatch.setattr(project, "load", lambda: {"scratch_repository": {}, "digest": {}})
    with pytest.raises(RemoteRefused, match="not configured"):
        outbox.deliverer_for(route, tmp_path)
    assert not (tmp_path / "remote").exists()
