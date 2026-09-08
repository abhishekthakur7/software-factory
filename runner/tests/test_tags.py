"""The `tag` write path: the catalogue-checked `fm_id`, the human-versus-mechanical
`tagged_by` split, the six send-back grounds, packet_defect's fixed failure mode,
policy_exception's waiver binding, and resolution chains over a `packet_defect` row.

`load_scenario` inserts one fixture family's rows through `record.insert`, resolving a
bare `$name` value to a previously inserted row's id, the same convention
`test_queue.py`'s own loader uses.
"""
from pathlib import Path

import pytest
import sqlite3
import yaml

from runner import governance, queue, record, tags, waivers
from runner.tests.test_s5_waivers import issue_review_waiver
from runner.db import connect

ABHISHEK = "abhishek"
FAR_FUTURE = "2999-01-01T00:00:00+00:00"

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "tags"


@pytest.fixture
def conn(tmp_path):
    connection = connect(tmp_path / "factory.sqlite")
    yield connection
    connection.close()


def load_scenario(conn, family: str, scenario: str) -> dict[str, int]:
    data = yaml.safe_load((FIXTURES_DIR / f"{family}.yaml").read_text())[scenario]
    refs: dict[str, int] = {}

    def resolve(value):
        if isinstance(value, str) and value.startswith("$") and value[1:] in refs:
            return refs[value[1:]]
        if isinstance(value, str) and "$" in value:
            for name, row_id in refs.items():
                value = value.replace(f"${name}", str(row_id))
        return value

    for table, rows in data.items():
        for row in rows:
            row = dict(row)
            name = row.pop("as", None)
            row_id = record.insert(conn, table, **{k: resolve(v) for k, v in row.items()})
            if name:
                refs[name] = row_id
    return refs


def _governed_ticket_fields(conn) -> dict:
    """Ticket fields that satisfy `S0.governance_valid`, the committed trust profile's default-path activation."""
    proposal = governance.propose()
    for role in ("security_approver", "legal_data_governance_approver"):
        governance.decide(
            conn, proposal, actor_identity=ABHISHEK, role=role, decision="approve",
            expires_at=FAR_FUTURE, attestation_version="v1", attestation_hash=f"att-{role}",
        )
    activated = governance.activation(conn, proposal)
    return {
        "trust_profile_hash": proposal.profile_hash,
        "trust_approval_set_hash": activated.trust_approval_set_hash,
        "service": "fixture-project",
        "source_kind": "jira",
        "source_ref": "FIX-1",
    }


def _seed_item(conn, kind: str, *, state: str = "checks", **ticket_fields) -> tuple[int, int]:
    ticket_id = record.insert(conn, "ticket", state=state, opened_at=record.now(), **ticket_fields)
    item_id = queue.open_item(conn, ticket_id=ticket_id, kind=kind)
    return ticket_id, item_id


def test_override_commits_only_with_a_human_tagged_tag(conn, tmp_path):
    ticket_id, item_id = _seed_item(conn, "eligibility", state="intake", **_governed_ticket_fields(conn))

    queue.act(conn, item_id=item_id, action="override", actor=ABHISHEK, tier="heavy", fm_id="FM-05", runs_dir=tmp_path)

    tag_rows = conn.execute("SELECT * FROM tag WHERE ticket_id = ?", (ticket_id,)).fetchall()
    assert [row["event_kind"] for row in tag_rows] == ["override"]
    assert tag_rows[0]["tagged_by"] == ABHISHEK


def test_send_back_commits_only_with_a_human_tagged_tag(conn, tmp_path):
    ticket_id, item_id = _seed_item(conn, "red_check")

    queue.act(
        conn, item_id=item_id, action="send_back", actor=ABHISHEK, to="context", fm_id="FM-07",
        note="duplicates_existing_work: already covered elsewhere", runs_dir=tmp_path,
    )

    tag_rows = conn.execute("SELECT * FROM tag WHERE ticket_id = ?", (ticket_id,)).fetchall()
    assert [row["event_kind"] for row in tag_rows] == ["send_back"]
    assert tag_rows[0]["tagged_by"] == ABHISHEK


def test_abandoned_commits_only_with_a_human_tagged_tag(conn, tmp_path):
    ticket_id, item_id = _seed_item(conn, "red_check")

    queue.act(conn, item_id=item_id, action="abandon", actor=ABHISHEK, fm_id="FM-19", runs_dir=tmp_path)

    tag_rows = conn.execute("SELECT * FROM tag WHERE ticket_id = ?", (ticket_id,)).fetchall()
    assert [row["event_kind"] for row in tag_rows] == ["abandoned"]
    assert tag_rows[0]["tagged_by"] == ABHISHEK


@pytest.mark.parametrize(
    "action, kwargs",
    [
        ("send_back", {"to": "context", "note": "duplicates_existing_work: dup"}),
        ("abandon", {}),
        ("override", {"tier": "heavy"}),
    ],
)
def test_must_reject_send_back_abandon_or_override_with_no_failure_mode_id(conn, tmp_path, action, kwargs):
    """R-T-6: none of these decisions can commit without the tag that carries the human's chosen fm_id."""
    if action == "override":
        ticket_id, item_id = _seed_item(conn, "eligibility", state="intake", **_governed_ticket_fields(conn))
    else:
        ticket_id, item_id = _seed_item(conn, "red_check")

    with pytest.raises(tags.TagRefused):
        queue.act(conn, item_id=item_id, action=action, actor=ABHISHEK, runs_dir=tmp_path, **kwargs)
    assert conn.execute("SELECT COUNT(*) FROM tag WHERE ticket_id = ?", (ticket_id,)).fetchone()[0] == 0


def test_revision_after_approval_targets_a_seeded_approval_record(conn):
    refs = load_scenario(conn, "decision_records", "packet_defect_target")

    tag_id = tags.tag(
        conn, target=f"approval_record:{refs['decision1']}", kind="revision_after_approval",
        fm_id="FM-06", actor=ABHISHEK, note="the approved plan missed a case",
    )

    row = record.get(conn, "tag", tag_id)
    assert row["event_kind"] == "revision_after_approval"
    assert row["ticket_id"] == refs["ticket1"]
    assert row["tagged_by"] == ABHISHEK


def test_packet_defect_targets_a_seeded_approval_record_or_question_and_is_always_fm_10(conn):
    refs = load_scenario(conn, "decision_records", "packet_defect_target")

    on_decision = tags.tag(
        conn, target=f"approval_record:{refs['decision1']}", kind="packet_defect",
        fm_id="FM-10", actor=ABHISHEK, note="the packet omits the narrative",
    )
    on_question = tags.tag(
        conn, target=f"question:{refs['question1']}", kind="packet_defect",
        fm_id="FM-10", actor=ABHISHEK, note="this question version is stale",
    )

    assert record.get(conn, "tag", on_decision)["ref"] == f"approval_record:{refs['decision1']}"
    assert record.get(conn, "tag", on_question)["ref"] == f"question:{refs['question1']}"


def test_must_reject_a_packet_defect_tag_with_a_failure_mode_id_other_than_fm_10(conn):
    refs = load_scenario(conn, "decision_records", "packet_defect_target")

    with pytest.raises(tags.TagRefused):
        tags.tag(
            conn, target=f"approval_record:{refs['decision1']}", kind="packet_defect",
            fm_id="FM-06", actor=ABHISHEK, note="wrong fm id",
        )


@pytest.mark.parametrize(
    "ground, text",
    [
        ("duplicates_existing_work", "already built on another ticket"),
        ("technically_unsound", "the approach does not hold"),
        ("missing_compatibility_analysis", "no migration analysis was written"),
        ("contradicts_non_goal", "the plan's own non-goal rules this out"),
        ("wrong_brief_or_criteria", "the criteria were wrong; send back to S2"),
        ("other", "a reason none of the above names"),
    ],
)
def test_a_send_back_note_naming_each_checklist_ground_is_accepted(conn, tmp_path, ground, text):
    ticket_id, item_id = _seed_item(conn, "red_check")

    queue.act(
        conn, item_id=item_id, action="send_back", actor=ABHISHEK, to="context", fm_id="FM-07",
        note=f"{ground}: {text}", runs_dir=tmp_path,
    )

    tag_row = conn.execute("SELECT * FROM tag WHERE ticket_id = ?", (ticket_id,)).fetchone()
    assert tag_row["note"] == f"{ground}: {text}"


def test_must_reject_a_send_back_note_with_no_ground_id(conn, tmp_path):
    ticket_id, item_id = _seed_item(conn, "red_check")

    with pytest.raises(tags.TagRefused):
        queue.act(
            conn, item_id=item_id, action="send_back", actor=ABHISHEK, to="context", fm_id="FM-07",
            note="just a free-text reason", runs_dir=tmp_path,
        )
    assert conn.execute("SELECT COUNT(*) FROM tag WHERE ticket_id = ?", (ticket_id,)).fetchone()[0] == 0


def test_must_reject_a_send_back_note_grounded_other_with_no_text_after_the_colon(conn, tmp_path):
    ticket_id, item_id = _seed_item(conn, "red_check")

    with pytest.raises(tags.TagRefused):
        queue.act(
            conn, item_id=item_id, action="send_back", actor=ABHISHEK, to="context", fm_id="FM-07",
            note="other:", runs_dir=tmp_path,
        )


def test_must_reject_a_send_back_note_grounded_wrong_brief_or_criteria_with_no_stage_named(conn, tmp_path):
    ticket_id, item_id = _seed_item(conn, "red_check")

    with pytest.raises(tags.TagRefused):
        queue.act(
            conn, item_id=item_id, action="send_back", actor=ABHISHEK, to="context", fm_id="FM-07",
            note="wrong_brief_or_criteria: the criteria were wrong", runs_dir=tmp_path,
        )


def test_a_ticket_closed_pilot_excluded_carries_the_recorded_rule_and_writes_no_human_tag(conn):
    from runner.checks import exclusion

    ticket_id = record.insert(conn, "ticket", state="context", opened_at=record.now())
    stage_run_id = record.insert(conn, "stage_run", ticket_id=ticket_id, stage="S1", attempt=1)
    record.insert(
        conn, "check_result", stage_run_id=stage_run_id, check_name="exclusion", result="fail",
        summary="auth_or_permission surface discovered in the touched files",
    )

    exclusion.apply_recorded_exclusion(conn, ticket_id)

    ticket = record.get(conn, "ticket", ticket_id)
    assert ticket["close_reason"] == "pilot_excluded"
    check = conn.execute(
        "SELECT summary FROM check_result WHERE stage_run_id = ? AND check_name = 'exclusion'", (stage_run_id,)
    ).fetchone()
    assert "auth_or_permission" in check["summary"]
    assert conn.execute("SELECT COUNT(*) FROM tag WHERE ticket_id = ?", (ticket_id,)).fetchone()[0] == 0


@pytest.mark.parametrize("kind, fm_id", [("stale_index", "FM-17"), ("escalation", "FM-19")])
def test_mechanical_kinds_refuse_a_human_actor_and_accept_the_runner(conn, kind, fm_id):
    ticket_id = record.insert(conn, "ticket", state="checks", opened_at=record.now())
    stage_run_id = record.insert(conn, "stage_run", ticket_id=ticket_id, stage="S4", attempt=1)

    with pytest.raises(tags.TagRefused):
        tags.tag(conn, target=f"stage_run:{stage_run_id}", kind=kind, fm_id=fm_id, actor=ABHISHEK)

    tag_id = tags.tag(conn, target=f"stage_run:{stage_run_id}", kind=kind, fm_id=fm_id, actor=tags.MECHANICAL_ACTOR)
    assert record.get(conn, "tag", tag_id)["tagged_by"] == tags.MECHANICAL_ACTOR


@pytest.mark.parametrize("actor", [ABHISHEK, tags.MECHANICAL_ACTOR])
def test_a_control_defect_tag_is_written_by_the_runner_when_detected_and_by_a_reviewer_when_observed(conn, actor):
    """R-T-6: only a mechanically detected control defect is a mechanical tag; an incident
    reviewer's own observation carries their identity."""
    ticket_id = record.insert(conn, "ticket", state="checks", opened_at=record.now())
    stage_run_id = record.insert(conn, "stage_run", ticket_id=ticket_id, stage="S4", attempt=1)

    tag_id = tags.tag(conn, target=f"stage_run:{stage_run_id}", kind="control_defect", fm_id="FM-23", actor=actor, severity="sev2")

    assert record.get(conn, "tag", tag_id)["tagged_by"] == actor


def test_must_reject_a_human_kind_tagged_by_the_mechanical_actor(conn):
    ticket_id = record.insert(conn, "ticket", state="checks", opened_at=record.now())

    with pytest.raises(tags.TagRefused):
        tags.tag(conn, target=f"ticket:{ticket_id}", kind="abandoned", fm_id="FM-19", actor=tags.MECHANICAL_ACTOR)


def test_an_incident_reviewer_writes_an_incident_tag_with_attribution_and_a_severity(conn):
    ticket_id = record.insert(conn, "ticket", state="checks", opened_at=record.now())

    tag_id = tags.tag(
        conn, target=f"ticket:{ticket_id}", kind="incident", fm_id="FM-23", actor=ABHISHEK,
        severity="sev1", note="production incident under review",
    )

    row = record.get(conn, "tag", tag_id)
    assert row["tagged_by"] == ABHISHEK
    assert row["severity"] == "sev1"


def test_an_incident_reviewer_supplies_attribution_and_disposition_on_a_control_defect_through_the_queue(conn, tmp_path):
    """R-T-6: the queue's `control_event` records the reviewer's observation with its
    category and severity and tags the item under the reviewer's own identity."""
    ticket_id, item_id = _seed_item(conn, "red_check")

    queue.act(
        conn, item_id=item_id, action="control_event", actor=ABHISHEK,
        category="execution_boundary", severity="sev2", fm_id="FM-23", note="observed drift",
        runs_dir=tmp_path,
    )

    incident = conn.execute(
        "SELECT * FROM incident_observation WHERE ticket_id = ? AND record_kind = 'control_defect_event'",
        (ticket_id,),
    ).fetchone()
    assert (incident["recorder_identity"], incident["control_category"], incident["severity"]) == (ABHISHEK, "execution_boundary", "sev2")
    tag_row = conn.execute("SELECT * FROM tag WHERE ticket_id = ? AND event_kind = 'control_defect'", (ticket_id,)).fetchone()
    assert (tag_row["tagged_by"], tag_row["severity"]) == (ABHISHEK, "sev2")


def test_must_reject_a_policy_exception_tag_with_no_valid_waiver(conn):
    refs = load_scenario(conn, "waivers", "expired_only")

    with pytest.raises(tags.TagRefused):
        tags.tag(
            conn, target=f"waiver:{refs['expired_waiver']}", kind="policy_exception",
            fm_id="FM-25", actor=ABHISHEK, severity="sev3",
        )


def test_a_policy_exception_tag_on_a_valid_waiver_classifies_it_and_grants_nothing(conn, tmp_path):
    refs = issue_review_waiver(conn, tmp_path)
    other_check_result_id = record.insert(
        conn, "check_result", stage_run_id=refs["stage_run_id"], check_name="dep_verify",
        check_tier="blocking", result="blind_spot",
    )

    tag_id = tags.tag(
        conn, target=f"waiver:{refs['waiver_id']}", kind="policy_exception",
        fm_id="FM-25", actor=ABHISHEK, severity="sev3",
    )

    assert record.get(conn, "tag", tag_id)["event_kind"] == "policy_exception"
    # the tag classifies the waiver; it never substitutes for one. A check
    # result the waiver does not name stays `blind_spot`, not `waived`.
    entries = waivers.blocking_status(conn, refs["stage_run_id"])
    entry = next(entry for entry in entries if entry["id"] == other_check_result_id)
    assert entry["status"] == "blind_spot"


def test_must_reject_a_policy_exception_tag_that_does_not_target_a_waiver(conn):
    ticket_id = record.insert(conn, "ticket", state="checks", opened_at=record.now())

    with pytest.raises(tags.TagRefused):
        tags.tag(conn, target=f"ticket:{ticket_id}", kind="policy_exception", fm_id="FM-25", actor=ABHISHEK, severity="sev3")


@pytest.mark.parametrize("action, kwargs", [("send_back", {"to": "context"}), ("abandon", {})])
def test_must_reject_send_back_or_abandon_leaves_no_tag_and_no_resolution(conn, tmp_path, action, kwargs):
    ticket_id, item_id = _seed_item(conn, "red_check")

    with pytest.raises(tags.TagRefused):
        queue.act(conn, item_id=item_id, action=action, actor=ABHISHEK, runs_dir=tmp_path, **kwargs)

    assert record.get(conn, "queue_item", item_id)["resolved_at"] is None
    assert conn.execute("SELECT COUNT(*) FROM tag WHERE ticket_id = ?", (ticket_id,)).fetchone()[0] == 0


def test_a_resolution_tag_points_at_the_original_packet_defect_row_which_stays_untouched(conn):
    refs = load_scenario(conn, "decision_records", "packet_defect_target")
    original_id = tags.tag(
        conn, target=f"approval_record:{refs['decision1']}", kind="packet_defect",
        fm_id="FM-10", actor=ABHISHEK, note="the packet omits the narrative",
    )
    before = dict(record.get(conn, "tag", original_id))

    resolution_id = tags.tag(
        conn, target=f"approval_record:{refs['decision1']}", kind="packet_defect", fm_id="FM-10",
        actor=ABHISHEK, note="a corrected packet was published",
        resolves_tag_id=original_id, resolution_evidence_ref="artefact:42",
    )

    resolution = record.get(conn, "tag", resolution_id)
    assert resolution["resolves_tag_id"] == original_id
    assert resolution["resolution_evidence_ref"] == "artefact:42"
    after = dict(record.get(conn, "tag", original_id))
    assert after == before
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE tag SET note = ? WHERE id = ?", ("tampered", original_id))


def test_must_reject_resolves_tag_id_given_without_resolution_evidence_ref(conn):
    refs = load_scenario(conn, "decision_records", "packet_defect_target")
    original_id = tags.tag(
        conn, target=f"approval_record:{refs['decision1']}", kind="packet_defect",
        fm_id="FM-10", actor=ABHISHEK, note="the packet omits the narrative",
    )

    with pytest.raises(tags.TagRefused):
        tags.tag(
            conn, target=f"approval_record:{refs['decision1']}", kind="packet_defect", fm_id="FM-10",
            actor=ABHISHEK, note="missing the evidence ref", resolves_tag_id=original_id,
        )


def test_must_reject_a_resolution_tag_pointing_at_a_tag_from_a_different_ticket(conn):
    refs = load_scenario(conn, "decision_records", "packet_defect_target")
    original_id = tags.tag(
        conn, target=f"approval_record:{refs['decision1']}", kind="packet_defect",
        fm_id="FM-10", actor=ABHISHEK, note="the packet omits the narrative",
    )
    other_ticket_id = record.insert(conn, "ticket", state="checks", opened_at=record.now())

    with pytest.raises(tags.TagRefused):
        tags.tag(
            conn, target=f"ticket:{other_ticket_id}", kind="abandoned", fm_id="FM-10",
            actor=ABHISHEK, resolves_tag_id=original_id, resolution_evidence_ref="artefact:1",
        )


def test_must_reject_a_resolution_tag_pointing_at_a_tag_that_is_not_a_packet_defect(conn):
    ticket_id = record.insert(conn, "ticket", state="checks", opened_at=record.now())
    override_id = tags.tag(conn, target=f"ticket:{ticket_id}", kind="abandoned", fm_id="FM-19", actor=ABHISHEK)

    with pytest.raises(tags.TagRefused):
        tags.tag(
            conn, target=f"ticket:{ticket_id}", kind="abandoned", fm_id="FM-19", actor=ABHISHEK,
            resolves_tag_id=override_id, resolution_evidence_ref="artefact:1",
        )


# --- fm_id must name a real catalogue entry ---


def test_must_reject_an_fm_id_the_catalogue_does_not_list(conn):
    ticket_id = record.insert(conn, "ticket", state="checks", opened_at=record.now())

    with pytest.raises(tags.TagRefused):
        tags.tag(conn, target=f"ticket:{ticket_id}", kind="abandoned", fm_id="FM-99", actor=ABHISHEK)


def test_failure_modes_and_send_back_grounds_parse_the_catalogue_files():
    assert set(tags.failure_modes()) == {f"FM-{i:02d}" for i in range(1, 26)}
    assert set(tags.send_back_grounds()) == {
        "duplicates_existing_work", "technically_unsound", "missing_compatibility_analysis",
        "contradicts_non_goal", "wrong_brief_or_criteria", "other",
    }


# --- `factory tag` carries a resolution chain end to end ---


def test_factory_tag_cli_accepts_resolves_and_resolution_evidence(tmp_path):
    from runner import cli

    db_path = tmp_path / "factory.sqlite"
    setup = connect(db_path)
    ticket_id = record.insert(setup, "ticket", state="checks", opened_at=record.now())
    decision_id = record.insert(setup, "approval_record", ticket_id=ticket_id, gate="review", decision="approve")
    setup.commit()
    setup.close()

    cli.main([
        "--db", str(db_path), "tag", f"approval_record:{decision_id}", "packet_defect",
        "--fm", "FM-10", "--actor", ABHISHEK, "--note", "first packet defect",
    ])
    check = connect(db_path)
    try:
        original_id = check.execute("SELECT id FROM tag WHERE ticket_id = ?", (ticket_id,)).fetchone()["id"]
    finally:
        check.close()

    cli.main([
        "--db", str(db_path), "tag", f"approval_record:{decision_id}", "packet_defect",
        "--fm", "FM-10", "--actor", ABHISHEK, "--note", "corrected",
        "--resolves", str(original_id), "--resolution-evidence", "artefact:9",
    ])

    verify = connect(db_path)
    try:
        rows = verify.execute("SELECT * FROM tag WHERE ticket_id = ? ORDER BY id", (ticket_id,)).fetchall()
        assert len(rows) == 2
        assert rows[1]["resolves_tag_id"] == original_id
        assert rows[1]["resolution_evidence_ref"] == "artefact:9"
    finally:
        verify.close()
