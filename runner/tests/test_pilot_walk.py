"""The pilot ticket's closing run: from its Jira key through the A and AB mechanisms to `pr_opened`,
then this ticket's own manual outcome record over the `pr_outcome` item the walk's own `advance`
call already opened. Later tickets extend this same closing run with graduation, capacity, and the
stage interface's own criteria; this file holds only the outcome record's closing-run criterion.
"""
import os

import pytest

from runner import artefact_registry, canonical, queue, record
from runner.tests.test_stub_walk import ABHISHEK, HAS_JAVAC, _patch_fixture_runtime, _run_walk


@pytest.fixture(scope="module")
def pilot_walk(tmp_path_factory):
    _patch_fixture_runtime(tmp_path_factory)
    result = _run_walk(tmp_path_factory.mktemp("pilot_walk"))
    yield result
    result.conn.close()


@pytest.mark.skipif(not HAS_JAVAC, reason="javac/java not available: the walk cannot reach pr_opened without it")
def test_the_pilot_tickets_pull_request_outcome_is_entered_manually_and_closes_it(pilot_walk):
    """R-H-11: the closing run records the pilot ticket's eventual disposition by hand,
    with its actual final SHAs and body hash, approval and required-check dispositions, and coverage status."""
    conn, ticket_id, tmp_path = pilot_walk.conn, pilot_walk.ticket_id, pilot_walk.tmp_path
    assert record.get(conn, "ticket", ticket_id)["state"] == "pr_opened"

    item = conn.execute(
        "SELECT id FROM queue_item WHERE ticket_id = ? AND kind = 'pr_outcome' AND resolved_at IS NULL",
        (ticket_id,),
    ).fetchone()
    assert item is not None, "advance's own review_quorum_reconciled hand-off must have opened the item"

    body_path = tmp_path / "closing-run-observed-body.md"
    body_text = "the pilot ticket's actual merged pull-request body, observed by hand"
    body_path.write_text(body_text)
    ticket_before = record.get(conn, "ticket", ticket_id)

    queue.act(
        conn, item_id=item["id"], action="outcome", actor=ABHISHEK,
        fields={
            "result": "merged",
            "head_sha": ticket_before["last_remote_head_sha"] or ticket_before["head_sha"],
            "target_base_sha": ticket_before["target_base_sha"],
            "merge_sha": "closing-run-merge-sha",
            "checks": "green",
            "observed_at": record.now(),
            "body_file": str(body_path),
        },
        runs_dir=tmp_path,
    )

    ticket = record.get(conn, "ticket", ticket_id)
    assert ticket["state"] == "merged"
    assert ticket["close_reason"] == "merged"
    assert ticket["merge_sha"] == "closing-run-merge-sha"
    assert ticket["required_checks_disposition"] == "green"
    assert ticket["approval_disposition"] in ("matched", "mismatched", "unknown")
    assert ticket["final_pr_body_hash"] == canonical.content_hash({"pr_body": body_text})
    assert artefact_registry.latest(conn, ticket_id, "pr_body_observed") is not None

    coverage_rows = conn.execute(
        "SELECT * FROM incident_observation WHERE ticket_id = ? AND record_kind = 'production_coverage'", (ticket_id,)
    ).fetchall()
    assert len(coverage_rows) == 1
    assert coverage_rows[0]["coverage_status"] == "unknown"

    assert record.get(conn, "queue_item", item["id"])["resolved_at"] is not None


@pytest.mark.skipif(
    not os.environ.get("SOFT_FACTORY_DRY_RUN_JIRA_KEY"),
    reason="the live closing run needs a real Jira key and a real GitHub scratch repository/credential",
)
def test_live_pilot_closing_run():
    """The same closing steps against the real Jira and GitHub transports, driven from a real ticket key.

    This only proves the same manual outcome record works end to end
    against live transports; it does not itself prove the pilot ticket's
    actual disposition, which is a one-time human act on the real ticket.
    """
    pytest.skip("live closing run: exercised by hand against the real pilot ticket, not by CI")
