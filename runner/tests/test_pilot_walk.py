"""The pilot ticket's closing run: from its Jira key through the A and AB mechanisms to `pr_opened`,
then this ticket's own manual outcome record over the `pr_outcome` item the walk's own `advance`
call already opened, the graduation gate evaluated fresh over that same record, the parallel-limit
read, the governed export, and the redacted fixture the export becomes. Every check below runs
on the fake-driven walk's own synthetic ticket, the fakes under `runner/tests/fakes/` and the
fixture project standing in for the pilot host; only the escape suite's `credentials` category and
the live GitHub view need the real pilot ticket on the real pilot host, so those stay in the
skipping-loudly live test at the bottom of this file.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from runner import artefact_registry, canonical, capacity, evals, queue, record, stage_interface
from runner.paths import FACTORY_DIR
from runner.tests.test_stub_walk import ABHISHEK, HAS_JAVAC, _patch_fixture_runtime, _run_walk

FIXTURE_FROM_EXPORT_SCRIPT = FACTORY_DIR / "scripts" / "tools" / "fixture_from_export"

# The operations `_run_walk` itself issues to move the pilot ticket to
# `pr_opened`, mapped to the name `stage_interface.__all__` exports for
# each: `waive` is issued too (over a seeded security blind spot), but it
# is not part of the Initial operation catalogue this ticket's interface
# exports -- see `stage_interface.__all__`, which carries no `waive` --
# so it names no expected export here.
_WALK_VERBS_IN_CATALOGUE = {"advance": "advance", "run": "run_stage", "pause": "pause", "resume": "resume", "stop": "stop", "act": "act"}

_SKIP_NO_JAVAC = pytest.mark.skipif(not HAS_JAVAC, reason="javac/java not available: the walk cannot reach pr_opened without it")


@pytest.fixture(scope="module")
def pilot_walk(tmp_path_factory):
    _patch_fixture_runtime(tmp_path_factory)
    result = _run_walk(tmp_path_factory.mktemp("pilot_walk"))
    yield result
    result.conn.close()


@pytest.fixture(scope="module")
def pilot_export(pilot_walk):
    """The pilot ticket's own governed export, built once through `stage_interface.export`
    and shared by every check below that reads it, rather than re-exporting per test."""
    conn, ticket_id, tmp_path = pilot_walk.conn, pilot_walk.ticket_id, pilot_walk.tmp_path
    if record.get(conn, "ticket", ticket_id)["data_class"] is None:
        record.update(conn, "ticket", ticket_id, data_class="internal")
        conn.commit()
    result = stage_interface.export(conn, ticket_id, runs_dir=tmp_path / "closing-run-export")
    return Path(result["export_dir"])


@_SKIP_NO_JAVAC
def test_the_graduation_gate_evaluates_not_passed_over_the_walk_s_own_record(pilot_walk):
    """R-O-13: the graduation gate evaluated fresh, through `stage_interface.graduate_evaluate`,
    over the closing run's own record has not passed -- one ticket never clears the window's
    minimum-outcomes clause on its own -- and no approval has been recorded against it."""
    conn = pilot_walk.conn
    before_approvals = conn.execute(
        "SELECT COUNT(*) AS n FROM approval_record WHERE gate = 'graduation'"
    ).fetchone()["n"]

    report_artefact_id = stage_interface.graduate_evaluate(conn, cutoff=record.now())
    conn.commit()

    report_artefact = record.get(conn, "artefact", report_artefact_id)
    report = json.loads(Path(report_artefact["path"]).read_text())
    assert report["passed"] is False
    failing_clauses = sorted(name for name, clause in report["clauses"].items() if not clause["passed"])
    assert "window" in failing_clauses

    after_approving = conn.execute(
        "SELECT COUNT(*) AS n FROM approval_record WHERE gate = 'graduation' AND decision = 'approve'"
    ).fetchone()["n"]
    assert before_approvals == 0
    assert after_approving == 0


@_SKIP_NO_JAVAC
def test_the_parallel_limit_stays_one_and_the_ticket_shows_no_capacity_wait_line(pilot_walk):
    """R-I-10: with no graduation approval on record, `capacity.effective_parallel_limit`
    still returns one, and `stage_interface.show` over the pilot ticket -- long past `intake`
    -- carries no capacity-wait line."""
    conn, ticket_id = pilot_walk.conn, pilot_walk.ticket_id

    limit = capacity.effective_parallel_limit(conn)
    output = stage_interface.show(conn, ticket_id)

    assert limit.limit == 1
    assert "capacity wait" not in output


@_SKIP_NO_JAVAC
def test_the_export_list_covers_every_stage_interface_verb_the_walk_used(pilot_walk):
    """R-I-1: `stage_interface.__all__` exports a name for every operation verb the walk
    itself issued to reach `pr_opened`, and the surface itself -- not `operations`/`queue`
    directly -- is what these closing-run checks call."""
    for exported_name in _WALK_VERBS_IN_CATALOGUE.values():
        assert exported_name in stage_interface.__all__

    conn, ticket_id = pilot_walk.conn, pilot_walk.ticket_id
    assert f"ticket {ticket_id}: pr_opened" in stage_interface.show(conn, ticket_id)
    assert isinstance(stage_interface.queue(conn), str)


@_SKIP_NO_JAVAC
def test_the_governed_export_lists_every_run_tool_result_guard_decision_approval_and_external_write(pilot_walk, pilot_export):
    """R-I-15, R-I-16: the pilot ticket's governed export carries a row for every `stage_run`,
    `tool_call`, `guard_decision`, `approval_record`, and `external_write` the walk wrote for
    it -- the record and the export never disagree about what happened."""
    conn, ticket_id = pilot_walk.conn, pilot_walk.ticket_id
    export_dir = pilot_export

    stage_run_ids = {
        row["id"] for row in conn.execute("SELECT id FROM stage_run WHERE ticket_id = ?", (ticket_id,)).fetchall()
    }
    tool_call_ids: set[int] = set()
    if stage_run_ids:
        placeholders = ",".join("?" for _ in stage_run_ids)
        tool_call_ids = {
            row["id"] for row in conn.execute(
                f"SELECT id FROM tool_call WHERE stage_run_id IN ({placeholders})", list(stage_run_ids)
            ).fetchall()
        }
    guard_decision_ids = {
        row["id"] for row in conn.execute("SELECT id FROM guard_decision WHERE ticket_id = ?", (ticket_id,)).fetchall()
    }
    approval_ids = {
        row["id"] for row in conn.execute("SELECT id FROM approval_record WHERE ticket_id = ?", (ticket_id,)).fetchall()
    }
    external_write_ids = {
        row["id"] for row in conn.execute("SELECT id FROM external_write WHERE ticket_id = ?", (ticket_id,)).fetchall()
    }

    for table, expected_ids in (
        ("stage_run", stage_run_ids),
        ("tool_call", tool_call_ids),
        ("guard_decision", guard_decision_ids),
        ("approval_record", approval_ids),
        ("external_write", external_write_ids),
    ):
        envelopes = json.loads((export_dir / "rows" / f"{table}.json").read_text())
        exported_ids = {envelope["row"]["id"] for envelope in envelopes}
        assert exported_ids == expected_ids, f"{table}: exported {sorted(exported_ids)} != record {sorted(expected_ids)}"


@_SKIP_NO_JAVAC
def test_the_pr_create_external_write_dispatches_no_earlier_than_the_quorum_completing_review_approval(pilot_walk):
    """R-I-1: the `pr_create` external write the walk dispatched to open the pull request was
    created no earlier than the `review`-gate approval that completed its quorum -- publication
    never precedes the decision that authorises it."""
    conn, ticket_id = pilot_walk.conn, pilot_walk.ticket_id

    external_write = conn.execute(
        "SELECT * FROM external_write WHERE ticket_id = ? AND operation = 'pr_create' ORDER BY id DESC LIMIT 1",
        (ticket_id,),
    ).fetchone()
    assert external_write is not None

    quorum_approval = conn.execute(
        "SELECT * FROM approval_record WHERE ticket_id = ? AND gate = 'review' AND decision = 'approve' "
        "ORDER BY decided_at DESC, id DESC LIMIT 1",
        (ticket_id,),
    ).fetchone()
    assert quorum_approval is not None
    assert external_write["created_at"] >= quorum_approval["decided_at"]


@_SKIP_NO_JAVAC
def test_fixture_from_export_over_the_walk_s_own_export_produces_a_directory_the_completeness_walk_accepts(pilot_walk, pilot_export, tmp_path):
    """R-I-1, R-F-2: `factory/scripts/tools/fixture_from_export` run over the pilot ticket's own
    governed export produces a `factory/evals/tickets/<id>/` directory under a temporary fixture
    root -- never the real `factory/` -- that the completeness walk accepts."""
    ticket_id = pilot_walk.ticket_id
    export_dir = pilot_export
    fixture_root = tmp_path / "fixture-root"

    result = subprocess.run(
        [
            sys.executable, str(FIXTURE_FROM_EXPORT_SCRIPT), str(export_dir), str(ticket_id),
            "--reviewer", ABHISHEK, "--redacted-fields", "", "--root", str(fixture_root),
        ],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr

    ticket_eval_dir = fixture_root / "factory" / "evals" / "tickets" / str(ticket_id)
    evals.check(ticket_eval_dir)  # raises on failure; no exception is the assertion
    assert ticket_eval_dir in evals.expected_eval_dirs(fixture_root / "factory")


@_SKIP_NO_JAVAC
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

    stage_interface.act(
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

    Everything the fake-driven walk above proves -- the graduation
    verdict, the parallel limit, the export's completeness, the dispatch
    ordering, and the redacted fixture -- applies unchanged against the
    real record once this runs for real; the two checks that need a
    genuine external system rather than this repository's own fakes are
    the escape suite's `credentials` category re-run against the pilot
    ticket's real agent sandbox, and the native GitHub view of the
    resulting draft pull request carrying the diff of the approved
    narrative. Neither can be exercised honestly from this worktree --
    there is no real Jira key, GitHub scratch repository, or scoped
    runtime credential here -- so this test stays a hand-run script
    against the real pilot host rather than fabricated integration code
    this session cannot itself verify.
    """
    pytest.skip("live closing run: exercised by hand against the real pilot ticket, not by CI")
