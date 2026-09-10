"""The pilot ticket's closing run: from its Jira key through the A and AB mechanisms to `pr_opened`,
then this ticket's own manual outcome record over the `pr_outcome` item the walk's own `advance`
call already opened, the graduation gate evaluated fresh over that same record, the parallel-limit
read, the governed export, and the redacted fixture the export becomes. Every check below runs
on the fake-driven walk's own synthetic ticket, the fakes under `runner/tests/fakes/` and the
fixture project standing in for the pilot host; only the escape suite's `credentials` category and
the live GitHub view need the real pilot ticket on the real pilot host, so those stay in the
skipping-loudly live test at the bottom of this file.
"""
import ast
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

from runner import artefact_registry, canonical, capacity, evals, outbox, queue, record, stage_interface
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


def _measure_block(report_text: str, title_prefix: str) -> list[str]:
    """The indented lines the report printed under the one measure whose title starts with `title_prefix`.

    Raises when no measure matches, so a measure the report stopped
    printing at all fails the reading test rather than reading as empty.
    """
    lines = report_text.splitlines()
    start = next(index for index, line in enumerate(lines) if line.startswith(title_prefix))
    block: list[str] = []
    for line in lines[start + 1:]:
        if not line.startswith("  "):
            break
        block.append(line.strip())
    return block


def _measure_rows(report_text: str, title_prefix: str) -> list[dict]:
    """The `key=value` lines of one measure's block as dicts; a status/reason block has none."""
    return [
        {key: ast.literal_eval(value) for key, value in (field.split("=", 1) for field in line.split(", "))}
        for line in _measure_block(report_text, title_prefix) if "=" in line
    ]


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
    """The graduation gate evaluated fresh, through `stage_interface.graduate_evaluate`,
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
    """With no graduation approval on record, `capacity.effective_parallel_limit`
    still returns one, and `stage_interface.show` over the pilot ticket -- long past `intake`
    -- carries no capacity-wait line."""
    conn, ticket_id = pilot_walk.conn, pilot_walk.ticket_id

    limit = capacity.effective_parallel_limit(conn)
    output = stage_interface.show(conn, ticket_id)

    assert limit.limit == 1
    assert "capacity wait" not in output


@_SKIP_NO_JAVAC
def test_the_export_list_covers_every_stage_interface_verb_the_walk_used(pilot_walk):
    """`stage_interface.__all__` exports a name for every operation verb the walk
    itself issued to reach `pr_opened`, and the surface itself -- not `operations`/`queue`
    directly -- is what these closing-run checks call."""
    for exported_name in _WALK_VERBS_IN_CATALOGUE.values():
        assert exported_name in stage_interface.__all__

    conn, ticket_id = pilot_walk.conn, pilot_walk.ticket_id
    assert f"ticket {ticket_id}: pr_opened" in stage_interface.show(conn, ticket_id)
    assert isinstance(stage_interface.queue(conn), str)


@_SKIP_NO_JAVAC
def test_the_governed_export_lists_every_run_tool_result_guard_decision_approval_and_external_write(pilot_walk, pilot_export):
    """The pilot ticket's governed export carries a row for every `stage_run`,
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
    # The export's own scans write guard decisions while it runs, after
    # its row snapshot was taken; those are named by its manifest rather
    # than carried inside it, so the record it must match is every
    # decision that preceded the export's own overall decision.
    export_manifest = json.loads((export_dir / "manifest.json").read_text())
    guard_decision_ids = {
        row["id"] for row in conn.execute(
            "SELECT id FROM guard_decision WHERE ticket_id = ? AND id < ?",
            (ticket_id, export_manifest["guard_decision_id"]),
        ).fetchall()
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
    """The `pr_create` external write the walk dispatched to open the pull request was
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
def test_the_dispatched_pull_request_intent_carries_the_subjects_both_gates_approved(pilot_walk):
    """The pre-dispatch recheck let the pull request through on subjects that were still
    the current ones: the dispatched intent's review subject is the one every `review`-gate
    approval bound and the one the review packet was opened on, its review tuple is the ticket's
    latest and stands at the ticket's own final head, the plan tuple that review tuple references
    is the one the `plan`-gate approvals bound, and no write the walk left behind records a
    pre-dispatch mismatch."""
    conn, ticket_id = pilot_walk.conn, pilot_walk.ticket_id

    external_write = conn.execute(
        "SELECT * FROM external_write WHERE ticket_id = ? AND operation = 'pr_create' ORDER BY id DESC LIMIT 1",
        (ticket_id,),
    ).fetchone()
    ticket = record.get(conn, "ticket", ticket_id)
    review_tuple = record.get(conn, "evidence_tuple", external_write["review_tuple_id"])
    plan_tuple = record.get(conn, "evidence_tuple", review_tuple["plan_tuple_id"])
    latest_review_tuple_id = conn.execute(
        "SELECT MAX(id) AS id FROM evidence_tuple WHERE ticket_id = ? AND kind = 'review'", (ticket_id,)
    ).fetchone()["id"]
    packet_item = conn.execute(
        "SELECT approval_subject_hash FROM queue_item WHERE ticket_id = ? AND kind = 'packet_approval' "
        "ORDER BY id DESC LIMIT 1",
        (ticket_id,),
    ).fetchone()

    assert external_write["state"] == "reconciled"
    assert review_tuple["id"] == latest_review_tuple_id
    assert review_tuple["head_sha"] == ticket["head_sha"]
    assert review_tuple["target_base_sha"] == ticket["target_base_sha"]

    review_subject_hashes = {
        row["subject_hash"] for row in conn.execute(
            "SELECT subject_hash FROM approval_record WHERE ticket_id = ? AND gate = 'review' AND decision = 'approve'",
            (ticket_id,),
        )
    }
    plan_subject_hashes = {
        row["subject_hash"] for row in conn.execute(
            "SELECT subject_hash FROM approval_record WHERE ticket_id = ? AND gate = 'plan' AND decision = 'approve'",
            (ticket_id,),
        )
    }
    assert review_subject_hashes == {external_write["review_approval_subject_hash"]}
    assert packet_item["approval_subject_hash"] == external_write["review_approval_subject_hash"]
    assert plan_subject_hashes == {plan_tuple["content_hash"]}

    for row in conn.execute("SELECT last_error FROM external_write WHERE ticket_id = ?", (ticket_id,)):
        assert not (row["last_error"] or "").startswith(outbox.PREDISPATCH_MISMATCH_PREFIX)


@_SKIP_NO_JAVAC
def test_fixture_from_export_over_the_walk_s_own_export_produces_a_directory_the_completeness_walk_accepts(pilot_walk, pilot_export, tmp_path):
    """`factory/scripts/tools/fixture_from_export` run over the pilot ticket's own
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
def test_the_measure_report_over_the_walk_s_record_separates_reliability_latency_attention_and_what_it_cannot_supply(pilot_walk):
    """`stage_interface.report` over the closing run's own database tells four different
    things apart. First-attempt reliability counts exactly one attempt for each stage the walk
    killed before it ever ran, and none of them passed on that attempt: the killed run is the
    first, the passing restart is a later attempt, and the child runs under it and the
    implementation invocation the transition table refused are no first-attempt result at all.
    Queue latency is the wait on the plan-approval item, in seconds off that item's own queued and
    resolved instants, and covers only the item kinds the measure names -- the eligibility and
    red-check items the walk also resolved are not waits on a decision. Active attention comes
    from what each approver recorded and nothing else: at both gates one approval came through
    the queue with a bucket and one was recorded directly with none, so an unrecorded bucket
    is its own group rather than a zero or a latency stand-in. And a measure this fixture never
    fed -- no generated test was ever judged -- reads as unavailable with a reason, never as a
    zero share and never dropped from the panel."""
    conn, ticket_id, tmp_path = pilot_walk.conn, pilot_walk.ticket_id, pilot_walk.tmp_path
    # The report runs as its own process against the database file, so
    # anything still open in this connection's transaction would be
    # invisible to it.
    conn.commit()

    report_text = stage_interface.report(tmp_path / "factory.sqlite")

    reliability = {
        row["stage"]: (row["eligible_count"], row["passed_count"])
        for row in _measure_rows(report_text, "share of stage runs passing on the first attempt")
    }
    assert reliability == {
        stage: (1, 0)
        for stage in ("intake", "context_gathering", "clarification", "planning", "checks", "human_review")
    }

    plan_approval_item = conn.execute(
        "SELECT queued_at, resolved_at FROM queue_item WHERE ticket_id = ? AND kind = 'plan_approval' "
        "ORDER BY id DESC LIMIT 1",
        (ticket_id,),
    ).fetchone()
    waited_seconds = (
        datetime.fromisoformat(plan_approval_item["resolved_at"])
        - datetime.fromisoformat(plan_approval_item["queued_at"])
    ).total_seconds()
    latency_rows = _measure_rows(report_text, "queue latency at clarification, planning, human review")
    assert [(row["stage"], row["tier"], row["item_count"]) for row in latency_rows] == [("planning", "standard", 1)]
    assert latency_rows[0]["queue_latency_seconds"] == pytest.approx(waited_seconds, abs=0.001)

    attention_rows = _measure_rows(report_text, "active attention at planning and human review")
    assert {(row["stage"], row["tier"], row["decision"], row["bucket"]): row["record_count"] for row in attention_rows} == {
        ("planning", "standard", "approve", "under_2m"): 1,
        ("planning", "standard", "approve", None): 1,
        ("human_review", "standard", "approve", "under_2m"): 1,
        ("human_review", "standard", "approve", None): 1,
    }

    generated_tests_block = _measure_block(report_text, "share of generated tests kept after review")
    assert len(generated_tests_block) == 2
    assert generated_tests_block[0] == "status: unavailable"
    assert generated_tests_block[1].startswith("reason: ")


@_SKIP_NO_JAVAC
def test_the_pilot_tickets_pull_request_outcome_is_entered_manually_and_closes_it(pilot_walk):
    """The closing run records the pilot ticket's eventual disposition by hand,
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
