"""The `outcome` action's observed-PR-body sourcing: a governed file, an immutable remote locator, or neither."""
import json
from pathlib import Path

from runner import artefact_registry, canonical, outbox, queue, record
from runner.deliverers.github import GitHubDeliverer
from runner.tests.fakes.github_transport import FakeGitHubTransport
from runner.tests.test_outcome_revision import conn, seed_pr_opened_ticket, seed_pr_outcome_item, ABHISHEK

_REQUIRED_OUTCOME_FIELDS = {
    "result": "merged", "head_sha": "final-head", "target_base_sha": "final-base",
    "checks": "green", "observed_at": "2025-01-01T00:00:00+00:00",
}


def test_a_body_file_is_copied_into_the_run_tree_and_registered_and_hashed(conn, tmp_path):
    """R-H-11: `--body-file` becomes a registered `pr_body_observed` artefact and `final_pr_body_hash`."""
    ticket_id = seed_pr_opened_ticket(conn)
    item_id = seed_pr_outcome_item(conn, ticket_id)
    body_path = tmp_path / "observed-body.md"
    body_path.write_text("the actual merged pull-request body")

    queue.act(
        conn, item_id=item_id, action="outcome", actor=ABHISHEK,
        fields={**_REQUIRED_OUTCOME_FIELDS, "body_file": str(body_path)}, runs_dir=tmp_path,
    )

    artefact = artefact_registry.latest(conn, ticket_id, "pr_body_observed")
    assert artefact is not None
    ticket = record.get(conn, "ticket", ticket_id)
    assert ticket["final_pr_body_hash"] == canonical.content_hash({"pr_body": "the actual merged pull-request body"})


def test_a_locator_read_registers_the_remote_body_and_carries_the_locator_in_its_metadata(conn, tmp_path, monkeypatch):
    """R-H-11: `--pr-identity`/`--observed-head-sha` performs one narrowly scoped GitHub read."""
    ticket_id = seed_pr_opened_ticket(conn)
    item_id = seed_pr_outcome_item(conn, ticket_id)

    remote = FakeGitHubTransport()
    remote.pull_requests[("fixture-project", "7")] = {
        "identity": "7", "head_sha": "remote-head-7", "body": "the remote pull request's own body",
        "body_hash": canonical.content_hash({"pr_body": "the remote pull request's own body"}),
        "state": "open", "target_ref": "main",
    }
    monkeypatch.setattr(outbox, "route_and_deliverer", lambda *args, **kwargs: (None, GitHubDeliverer(remote)))

    queue.act(
        conn, item_id=item_id, action="outcome", actor=ABHISHEK,
        fields={**_REQUIRED_OUTCOME_FIELDS, "pr_identity": "7", "observed_head_sha": "remote-head-7"},
        runs_dir=tmp_path,
    )

    assert [call[0] for call in remote.calls] == ["pull_request_body"]
    artefact = artefact_registry.latest(conn, ticket_id, "pr_body_observed")
    assert artefact is not None
    stored = json.loads(Path(artefact["path"]).read_text())
    assert stored["source"] == "locator"
    assert stored["pr_identity"] == "7"
    assert stored["observed_head_sha"] == "remote-head-7"
    ticket = record.get(conn, "ticket", ticket_id)
    assert ticket["final_pr_body_hash"] == canonical.content_hash({"pr_body": "the remote pull request's own body"})


def test_neither_body_source_leaves_the_final_pr_body_hash_null(conn, tmp_path):
    """R-H-11: given neither `--body-file` nor `--pr-identity`, `final_pr_body_hash` stays null."""
    ticket_id = seed_pr_opened_ticket(conn)
    item_id = seed_pr_outcome_item(conn, ticket_id)

    queue.act(conn, item_id=item_id, action="outcome", actor=ABHISHEK, fields=dict(_REQUIRED_OUTCOME_FIELDS), runs_dir=tmp_path)

    ticket = record.get(conn, "ticket", ticket_id)
    assert ticket["final_pr_body_hash"] is None
    assert artefact_registry.latest(conn, ticket_id, "pr_body_observed") is None
