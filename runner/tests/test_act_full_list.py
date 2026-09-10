"""Every human action across the nine `queue_item` kinds, the ticket-scoped outcome actions, and every
neighbouring command of the list -- driven once each, seeded per case, each case asserting the effect
the action's own mechanism has rather than a literal the test just passed in.
"""
import json
from pathlib import Path

import pytest

from runner import export, manifest, operations, queue, record, tags, waivers
from runner.db import connect
from runner.tests.test_act import ABHISHEK, _seed_item
from runner.tests.test_freshness import TARGET_BRANCH, _clone_ticket, _commit_all, _load_fixture, _source_repo, _write_files
from runner.tests.test_manifest import OWNERS_PATH as MIGRATION_OWNERS_PATH
from runner.tests.test_manifest import _committed_copy
from runner.tests.test_outcome_revision import seed_pr_opened_ticket, seed_pr_outcome_item
from runner.tests.test_checks_waivers import (
    PLAN_POLICY_ID, REVIEW_POLICY_ID, _owners_yaml, _plan_candidate_blind_spot, _register_evidence,
    _review_tuple_setup, _soon, issue_review_waiver,
)


@pytest.fixture
def conn(tmp_path):
    connection = connect(tmp_path / "factory.sqlite")
    yield connection
    connection.close()


@pytest.mark.parametrize("action", ["granted", "declined", "edit_scrutiny", "override"])
def test_eligibility_actions_are_each_accepted_and_shown_with_the_tickets_data_class(conn, action):
    # Each case gets its own connection: `_governed_ticket_fields` activates
    # the committed trust profile through real `approval_record` rows, and a
    # second activation call on the same connection would fork that
    # decision's own head -- one governed ticket per activation, matching
    # every other governed-eligibility test in this codebase.
    ticket_id, item_id = _seed_item(conn, "eligibility")
    record.update(conn, "ticket", ticket_id, data_class="internal")
    listing_before = queue.list_queue(conn)
    assert "data class to confirm: internal" in listing_before

    kwargs = dict(item_id=item_id, action=action, actor=ABHISHEK)
    if action == "override":
        kwargs["fm_id"] = "question_noise"
        kwargs["note"] = "tier bumped after a closer read"
    queue.act(conn, **kwargs)
    assert record.get(conn, "queue_item", item_id)["resolved_at"] is not None


@pytest.mark.parametrize("action, kwargs", [("answer", {"option": 0}), ("accept_default", {})])
def test_question_answer_and_accept_default_are_each_accepted(conn, action, kwargs):
    _, item_id = _seed_item(conn, "question")
    queue.act(conn, item_id=item_id, action=action, actor=ABHISHEK, self_contained="yes", **kwargs)
    assert record.get(conn, "queue_item", item_id)["resolved_at"] is not None


def test_question_override_corrects_a_flag_records_the_reason_and_leaves_the_item_open(conn):
    """The correction appends a question row superseding the original -- which stays
    readable and unchanged -- with the reason on a `flag_correction` tag; the item itself is
    untouched by it and still answers normally afterward, against the corrected row."""
    from runner import questions

    ticket_id, item_id = _seed_item(conn, "question")
    table, _, raw_id = record.get(conn, "queue_item", item_id)["ref"].partition(":")
    question_id = int(raw_id)
    before = record.get(conn, "question", question_id)
    assert not before["consequential"]

    queue.act(
        conn, item_id=item_id, action="override", actor=ABHISHEK,
        fields={"consequential": "yes"}, note="answering this also changes a public interface", fm_id="question_noise",
    )

    original = record.get(conn, "question", question_id)
    assert original["consequential"] == before["consequential"]
    assert original["state"] == "superseded"

    corrected = questions.current_version(conn, question_id)
    assert corrected["id"] != question_id
    assert corrected["supersedes"] == question_id
    assert corrected["consequential"] == 1
    tag_row = conn.execute(
        "SELECT * FROM tag WHERE ref = ? AND event_kind = 'flag_correction'", (f"question:{corrected['id']}",)
    ).fetchone()
    assert tag_row is not None
    assert tag_row["note"] == "answering this also changes a public interface"
    assert record.get(conn, "queue_item", item_id)["resolved_at"] is None

    queue.act(conn, item_id=item_id, action="answer", actor=ABHISHEK, option=0, self_contained="yes")
    assert record.get(conn, "queue_item", item_id)["resolved_at"] is not None
    assert questions.current_version(conn, question_id)["state"] == "answered"


def test_must_reject_question_override_with_neither_flag_named(conn):
    _, item_id = _seed_item(conn, "question")
    with pytest.raises(queue.ActionRefused):
        queue.act(conn, item_id=item_id, action="override", actor=ABHISHEK, note="a reason", fm_id="question_noise")


def test_question_override_forwards_a_blocking_correction(conn):
    """the queue action carries `--blocking` through to `questions.correct_flag` exactly like
    `--consequential` and `--hard-to-reverse` above."""
    from runner import questions

    ticket_id, _ = _seed_item(conn, "question")
    # `_seed_item` leaves `blocking` unset, and the column is append-only
    # -- it cannot be set after the fact -- so a fresh row carries it
    # from the insert instead.
    blocking_question_id = record.insert(
        conn, "question", ticket_id=ticket_id, stage="clarification", round=1, rank=1,
        options='[{"label": "A", "consequence": "does A"}]', default_option=0, state="open", blocking=1,
    )
    blocking_item_id = queue.open_item(
        conn, ticket_id=ticket_id, kind="question", ref=f"question:{blocking_question_id}",
    )

    queue.act(
        conn, item_id=blocking_item_id, action="override", actor=ABHISHEK,
        fields={"blocking": "no"}, note="downgraded after review", fm_id="question_noise",
    )

    tip = questions.current_version(conn, blocking_question_id)
    assert tip["blocking"] == 0
    assert tip["supersedes"] == blocking_question_id


def test_plan_approval_decision_actions_are_each_accepted_only_approve_reading_a_verdict_row(conn, tmp_path):
    for action in ("redirect", "send_back", "abandon"):
        ticket_id, item_id = _seed_item(conn, "plan_approval")
        before = conn.execute("SELECT COUNT(*) FROM human_verdict WHERE ticket_id = ?", (ticket_id,)).fetchone()[0]
        kwargs = dict(item_id=item_id, action=action, actor=ABHISHEK, fm_id="question_noise", runs_dir=tmp_path)
        if action in ("redirect", "send_back"):
            kwargs["to"] = "context"
            kwargs["note"] = "duplicates_existing_work: already built on another ticket"
        if action == "redirect":
            kwargs["bucket"] = "under_2m"
        queue.act(conn, **kwargs)
        after = conn.execute("SELECT COUNT(*) FROM human_verdict WHERE ticket_id = ?", (ticket_id,)).fetchone()[0]
        assert after == before, f"{action} must record no verdict row of its own"
        assert record.get(conn, "queue_item", item_id)["resolved_at"] is not None

    ticket_id, item_id = _seed_item(conn, "plan_approval")
    queue.act(
        conn, item_id=item_id, action="approve", actor=ABHISHEK, bucket="under_2m",
        self_contained="yes", runs_dir=tmp_path,
    )
    assert record.get(conn, "queue_item", item_id)["resolved_at"] is not None
    approvals = conn.execute(
        "SELECT * FROM approval_record WHERE gate = 'plan' AND actor_identity = ? AND ticket_id = ?",
        (ABHISHEK, ticket_id),
    ).fetchall()
    assert len(approvals) == 1 and approvals[0]["decision"] == "approve"


@pytest.mark.parametrize("action", ["approve", "request_changes", "send_back"])
def test_packet_approval_actions_are_each_accepted(conn, tmp_path, action):
    # Its own connection per action: `_seed_packet_approval_item`'s fixture
    # packet/pr_body content, review-tuple hash and reviewer-set hash are
    # all fixed literals, so two tickets seeded on the same connection
    # derive the identical review subject -- a second `approve`/
    # `request_changes` on that same subject by the same actor is exactly
    # the fork the forked-head guard now refuses.
    ticket_id, item_id = _seed_item(conn, "packet_approval", tmp_path)
    kwargs = dict(item_id=item_id, action=action, actor=ABHISHEK, fm_id="question_noise", runs_dir=tmp_path)
    if action in ("approve", "request_changes"):
        kwargs["bucket"] = "under_2m"
        kwargs["self_contained"] = "yes"
    if action == "send_back":
        kwargs["to"] = "context"
        kwargs["note"] = "duplicates_existing_work: already covered elsewhere"
    queue.act(conn, **kwargs)
    assert record.get(conn, "queue_item", item_id)["resolved_at"] is not None


def test_red_check_actions_are_each_accepted(conn, tmp_path):
    for action in ("send_back", "abandon"):
        _, item_id = _seed_item(conn, "red_check")
        kwargs = dict(item_id=item_id, action=action, actor=ABHISHEK, fm_id="question_noise", runs_dir=tmp_path)
        if action == "send_back":
            kwargs["to"] = "context"
            kwargs["note"] = "duplicates_existing_work: already covered elsewhere"
        queue.act(conn, **kwargs)
        assert record.get(conn, "queue_item", item_id)["resolved_at"] is not None


def test_escalation_actions_are_each_accepted(conn, tmp_path):
    for action in ("resume", "abandon"):
        _, item_id = _seed_item(conn, "escalation")
        kwargs = dict(item_id=item_id, action=action, actor=ABHISHEK, self_contained="yes", runs_dir=tmp_path)
        if action == "abandon":
            kwargs["fm_id"] = "question_noise"
        queue.act(conn, **kwargs)
        assert record.get(conn, "queue_item", item_id)["resolved_at"] is not None

    _, item_id = _seed_item(conn, "escalation", tmp_path)
    queue.act(
        conn, item_id=item_id, action="send_back", actor=ABHISHEK, to="context", fm_id="question_noise",
        note="duplicates_existing_work: already covered elsewhere", self_contained="yes", runs_dir=tmp_path,
    )
    assert record.get(conn, "queue_item", item_id)["resolved_at"] is not None


def test_manual_pause_actions_are_each_accepted(conn, tmp_path):
    for action in ("resume", "stop", "send_back"):
        _, item_id = _seed_item(conn, "manual_pause")
        kwargs = dict(item_id=item_id, action=action, actor=ABHISHEK, runs_dir=tmp_path)
        if action == "send_back":
            kwargs["to"] = "context"
            kwargs["fm_id"] = "question_noise"
            kwargs["note"] = "duplicates_existing_work: already covered elsewhere"
        queue.act(conn, **kwargs)
        assert record.get(conn, "queue_item", item_id)["resolved_at"] is not None


def test_rubric_inspection_close_inspection_is_accepted(conn):
    _, item_id = _seed_item(conn, "rubric_inspection")
    queue.act(conn, item_id=item_id, action="close_inspection", actor=ABHISHEK)
    assert record.get(conn, "queue_item", item_id)["resolved_at"] is not None


def test_pr_outcome_actions_are_each_accepted(conn, tmp_path):
    ticket_id = seed_pr_opened_ticket(conn)
    item_id = seed_pr_outcome_item(conn, ticket_id)
    queue.act(
        conn, item_id=item_id, action="revision", actor=ABHISHEK,
        fields={"to": "implementing", "fm_id": "question_noise", "note": "one more pass needed"}, runs_dir=tmp_path,
    )
    assert record.get(conn, "queue_item", item_id)["resolved_at"] is not None
    assert record.get(conn, "ticket", ticket_id)["state"] == "implementing"

    ticket_id2 = seed_pr_opened_ticket(conn)
    item_id2 = seed_pr_outcome_item(conn, ticket_id2)
    queue.act(
        conn, item_id=item_id2, action="outcome", actor=ABHISHEK,
        fields={
            "result": "merged", "head_sha": "final-head", "target_base_sha": "final-base",
            "checks": "green", "observed_at": "2025-01-01T00:00:00+00:00",
        },
        runs_dir=tmp_path,
    )
    assert record.get(conn, "queue_item", item_id2)["resolved_at"] is not None
    assert record.get(conn, "ticket", ticket_id2)["state"] == "merged"


def test_ticket_scoped_exposure_and_coverage_are_each_accepted(conn):
    ticket_id = seed_pr_opened_ticket(conn)
    queue.act(
        conn, ticket_id=ticket_id, action="exposure", actor=ABHISHEK,
        fields={"start": "2025-02-01T00:00:00+00:00", "source": "deploy log"},
    )
    queue.act(conn, ticket_id=ticket_id, action="coverage", actor=ABHISHEK, fields={"through": "2025-03-01T00:00:00+00:00"})
    rows = conn.execute(
        "SELECT coverage_status FROM incident_observation WHERE ticket_id = ? AND record_kind = 'production_coverage' "
        "ORDER BY id",
        (ticket_id,),
    ).fetchall()
    assert [row["coverage_status"] for row in rows] == ["unknown", "none_observed"]


def test_ticket_scoped_incident_and_disposition_and_an_open_items_control_event_are_each_accepted(conn, tmp_path):
    ticket_id = seed_pr_opened_ticket(conn)
    queue.act(
        conn, ticket_id=ticket_id, action="incident_event", actor=ABHISHEK,
        fields={"severity": "sev3", "occurred_at": "2025-02-01T00:00:00+00:00", "fm_id": "question_noise", "note": "a real incident"},
    )
    event = conn.execute(
        "SELECT id FROM incident_observation WHERE ticket_id = ? AND record_kind = 'production_incident_event'",
        (ticket_id,),
    ).fetchone()
    queue.act(
        conn, ticket_id=ticket_id, action="disposition", actor=ABHISHEK,
        fields={"event": str(event["id"]), "attribution": "undetermined", "disposition": "open"},
    )
    assert conn.execute(
        "SELECT COUNT(*) FROM incident_observation WHERE ticket_id = ? AND record_kind = 'production_disposition'",
        (ticket_id,),
    ).fetchone()[0] == 1

    _, item_id = _seed_item(conn, "red_check")
    result = queue.act(
        conn, item_id=item_id, action="control_event", actor=ABHISHEK, category="execution_boundary",
        severity="sev2", fm_id="parallel_fatigue", note="observed drift", runs_dir=tmp_path,
    )
    assert "control event recorded" in result
    assert record.get(conn, "queue_item", item_id)["resolved_at"] is None


def test_a_policy_permitted_waiver_is_accepted_through_act(conn, tmp_path):
    ticket_id, instance, verdict_id = _plan_candidate_blind_spot(conn, tmp_path)
    item_id = conn.execute(
        "SELECT id FROM queue_item WHERE ticket_id = ? AND kind = 'plan_approval' ORDER BY id DESC LIMIT 1",
        (ticket_id,),
    ).fetchone()["id"]
    from runner import artefact_registry
    evidence_id = artefact_registry.latest(conn, ticket_id, "plan")["id"]

    result = queue.act(
        conn, item_id=item_id, action="waiver", actor=ABHISHEK, verdict=str(verdict_id), evidence=[evidence_id],
        fields={
            "policy_id": PLAN_POLICY_ID, "reason": "owner mismatch is understood and accepted",
            "scope": f"ticket {ticket_id}: {instance.rubric_line_id}",
            "controls": "factory owner reviewed the brief by hand", "expires_at": _soon(),
        },
    )
    assert "waiver" in result and "issued" in result
    assert record.get(conn, "queue_item", item_id)["resolved_at"] is None
    assert conn.execute("SELECT COUNT(*) FROM waiver WHERE ticket_id = ?", (ticket_id,)).fetchone()[0] == 1


def test_must_reject_a_waiver_from_an_actor_the_exact_policy_does_not_authorise(conn, tmp_path):
    ticket_id, stage_run_id, check_result_id, item_id = _review_tuple_setup(conn, tmp_path)
    evidence_id = _register_evidence(conn, ticket_id, tmp_path)
    owners_path = _owners_yaml(tmp_path, identity="not_a_reviewer", role="ticket_engineer")

    with pytest.raises(waivers.WaiverRefused):
        queue.act(
            conn, item_id=item_id, action="waiver", actor="not_a_reviewer", owners_path=owners_path,
            evidence=[evidence_id],
            fields={
                "policy_id": REVIEW_POLICY_ID, "check_result_id": check_result_id,
                "reason": "known generated-API gap, reviewed by hand",
                "scope": f"ticket {ticket_id}: behavior_contract_evidence",
                "controls": "manual diff review", "expires_at": _soon(),
            },
        )
    assert conn.execute("SELECT COUNT(*) FROM waiver WHERE ticket_id = ?", (ticket_id,)).fetchone()[0] == 0


def test_refresh_base_is_accepted(conn, tmp_path):
    from runner import refresh_base

    fixture = _load_fixture("clean_rebase")
    source = _source_repo(tmp_path, fixture["seed"])
    ticket_id, trees, runs_dir = _clone_ticket(conn, tmp_path, source, state="implementing")
    record.insert(conn, "evidence_tuple", kind="plan", ticket_id=ticket_id, base_sha=trees.base_sha, target_base_sha=trees.base_sha, content_hash="plan-1")

    _write_files(source, fixture["target_commit"]["files"])
    _commit_all(source, fixture["target_commit"]["message"])

    message = refresh_base.refresh_base(conn, ticket_id, actor=ABHISHEK, target_branch=TARGET_BRANCH, runs_dir=runs_dir)
    assert "escalat" not in message
    assert record.get(conn, "ticket", ticket_id)["state"] == "context"


def test_migrate_manifest_is_accepted(conn, tmp_path):
    repo = _committed_copy(tmp_path, "migration_seed")
    message = manifest.migrate(conn, actor=ABHISHEK, root=repo, owners_path=MIGRATION_OWNERS_PATH)
    assert "waiting" not in message
    approval = conn.execute("SELECT * FROM approval_record WHERE gate = 'manifest' ORDER BY id DESC LIMIT 1").fetchone()
    assert approval["decision"] == "approve"


def test_pause_resume_and_stop_are_each_accepted(conn, tmp_path):
    from runner import control

    ticket_id = record.insert(conn, "ticket", state="implementing", opened_at=record.now())
    operations.pause(conn, ticket_id)
    assert record.get(conn, "ticket", ticket_id)["pause_requested"] == 1
    control.pause_pending(conn, ticket_id)  # stamps paused_at and opens the manual_pause item, as `advance` would

    result = operations.resume(conn, ticket_id, actor=ABHISHEK, runs_dir=tmp_path)
    assert "resolved with resume" in result
    assert record.get(conn, "ticket", ticket_id)["pause_requested"] == 0

    ticket_id2 = record.insert(conn, "ticket", state="implementing", opened_at=record.now())
    record.insert(conn, "stage_run", ticket_id=ticket_id2, stage="implementation", attempt=1)
    result2 = operations.stop(conn, ticket_id2, actor=ABHISHEK, fm_id="question_noise")
    assert "stopped" in result2
    assert record.get(conn, "ticket", ticket_id2)["state"] == "escalated"


def test_packet_defect_and_policy_exception_tags_and_their_resolution_chain_are_accepted(conn, tmp_path):
    ticket_id = record.insert(conn, "ticket", state="checks", opened_at=record.now())
    defect_id = tags.tag(
        conn, target=f"ticket:{ticket_id}", kind="packet_defect", fm_id=tags.PACKET_DEFECT_FM_ID,
        actor=ABHISHEK, note="missing narrative for the risk section",
    )
    resolution_id = tags.tag(
        conn, target=f"ticket:{ticket_id}", kind="packet_defect", fm_id=tags.PACKET_DEFECT_FM_ID,
        actor=ABHISHEK, note="narrative added in the next packet",
        resolves_tag_id=defect_id, resolution_evidence_ref="artefact:packet-v2",
    )
    resolution = record.get(conn, "tag", resolution_id)
    assert resolution["resolves_tag_id"] == defect_id
    assert resolution["resolution_evidence_ref"] == "artefact:packet-v2"

    refs = issue_review_waiver(conn, tmp_path)
    exception_id = tags.tag(
        conn, target=f"waiver:{refs['waiver_id']}", kind="policy_exception", fm_id=waivers.POLICY_EXCEPTION_FM_ID,
        actor=ABHISHEK, severity="sev3", note="classified as a known epistemic gap",
    )
    assert record.get(conn, "tag", exception_id)["event_kind"] == "policy_exception"


def test_abandon_and_purge_are_each_accepted(conn, tmp_path):
    ticket_id = record.insert(conn, "ticket", state="implementing", opened_at=record.now())
    result = queue.abandon(conn, ticket_id, actor=ABHISHEK, fm_id="question_noise")
    assert "abandoned" in result
    assert record.get(conn, "ticket", ticket_id)["state"] == "abandoned"

    export_dir = tmp_path / "export"
    (export_dir / "rows").mkdir(parents=True)
    (export_dir / "manifest.json").write_text(json.dumps({"retention_until": "2000-01-01T00:00:00+00:00"}))
    result2 = export.purge_export(conn, export_dir)
    assert "purged" in result2
    assert not export_dir.exists()
