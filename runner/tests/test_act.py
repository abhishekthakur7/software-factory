"""`factory act`, `factory abandon`, and `factory tag`: the day-one
kind-to-action mapping, the once-only resolution, queue latency, the
human-transition tags a send-back/abandon/override writes, and the
control-event action every open kind but `pr_outcome` accepts.

Each seeded ticket is placed directly in the state its item's action needs
(`record.insert(..., state=...)`, never `tickets.open_ticket`, which always
opens in `intake`) rather than replaying the stages that would normally
reach it -- the same convention `test_state_table.py` uses. `escalated` is
the one state the mapping and the state table disagree about: `escalated`
carries no generic `send_back_to_*` row (its own routes are named
`escalation_verification_resolved_to_*`), so the escalation/send_back
combination is exercised against a ticket seeded in `checks` instead, the
same way a plan, packet, or manual-pause send-back is. `request_changes`
also carries a failure-mode id here even though it names no `--fm`
requirement of its own: the `revision_after_approval` tag its own effect
writes has the same required `fm_id` every other tag does, so the id is
supplied for the same reason a redirect or send-back needs one.

An `eligibility` item's every action now runs behind S0's own governance
validity check, so every ticket seeded in `intake` for one carries a real,
currently active governance state: `_governed_ticket_fields` activates the
committed trust profile the same default-path way `test_outbox.py`'s
reconcile-first test does, and stamps the resulting hashes and admitted
source/service onto the ticket at creation, since `trust_profile_hash` and
`trust_approval_set_hash` are themselves append-only.
"""
import json
import tempfile
from pathlib import Path

import pytest

from runner import artefact_registry, artefacts, checklist, cli, governance, manifest, owners, queue, record, tags, tickets
from runner.db import connect
from runner.reviewer_sets import Slot
from runner.tests.test_s5_waivers import issue_review_waiver

ABHISHEK = "abhishek"
FAR_FUTURE = "2999-01-01T00:00:00+00:00"


def _governed_ticket_fields(conn) -> dict:
    """Ticket fields that satisfy `S0.governance_valid` against the committed trust profile and owners file."""
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

# The ticket state each kind's own item is naturally opened from, used by
# `_seed_item` for every accepted-pairing and refused-pairing test.
_KIND_STATE = {
    "question": "clarifying",
    "eligibility": "intake",
    "plan_approval": "plan_review",
    "packet_approval": "review",
    "red_check": "checks",
    "escalation": "escalated",
    "manual_pause": "implementing",
    "rubric_inspection": "planning",
    "pr_outcome": "pr_opened",
}


@pytest.fixture
def conn(tmp_path):
    connection = connect(tmp_path / "factory.sqlite")
    yield connection
    connection.close()


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "factory.sqlite"


def _reviewer_set(conn, ticket_id, *, kind, role, subject_hash):
    slots = json.dumps([
        {"source_rule": f"{kind}:1", "role": role, "min_count": 1, "distinct_from": [], "resolved": True}
    ])
    return record.insert(conn, "reviewer_set", ticket_id=ticket_id, kind=kind, subject_hash=subject_hash, slots=slots)


def _seed_plan_approval_item(conn, ticket_id: int) -> int:
    """A `plan_approval` item whose bootstrap checklist is already fully satisfied with `pass` verdicts.

    A `plan_approval` item carries no `approval_subject_hash` of its own
    -- its subject is the ticket's plan tuple, which only exists once the
    checklist completes -- so every generic `plan_approval` pairing this
    file exercises (`approve` included, which additionally refuses an
    incomplete checklist) needs real registered artefacts and a verdict
    on every expected instance, not just a bare reviewer set.
    """
    record.update(
        conn, "ticket", ticket_id, factory_manifest_hash=manifest.current_hash(),
        base_sha="base-1", target_base_sha="base-1",
    )
    stub_dir = Path(tempfile.mkdtemp())
    for artefact_kind in ("brief", "criteria", "plan"):
        path = stub_dir / f"{artefact_kind}.md"
        path.write_text(f"## {artefacts.SECTIONS[artefact_kind][0]}\n\nstub\n")
        artefact_registry.register(conn, ticket_id=ticket_id, kind=artefact_kind, path=path)
    identity = owners.load_owners().roles["s3_reviewer"]["identity"]
    slot = Slot(source_rule="s3_reviewer_role", role="s3_reviewer", owner=identity, min_count=1)
    reviewer_set_id = record.insert(
        conn, "reviewer_set", ticket_id=ticket_id, kind="planned", content_hash="planned-subj",
        slots=json.dumps([slot.to_json()]),
    )
    item_id = queue.open_item(conn, ticket_id=ticket_id, kind="plan_approval", reviewer_set_id=reviewer_set_id)
    ticket = record.get(conn, "ticket", ticket_id)
    plan_artefact = artefact_registry.latest(conn, ticket_id, "plan")
    for instance in checklist.expected_instances(conn, ticket):
        queue.act(
            conn, item_id=item_id, action="verdict", actor=identity, line=instance.rubric_line_id,
            key=instance.subject_item_key, verdict="pass", evidence=[plan_artefact["id"]], runs_dir=stub_dir,
        )
    return item_id


def _seed_item(conn, kind: str) -> tuple[int, int]:
    """A ticket in `kind`'s natural state, plus one open item of that kind."""
    extra = _governed_ticket_fields(conn) if kind == "eligibility" else {}
    if kind == "plan_approval":
        # Append-only columns: must be set at insert time, since the
        # bootstrap checklist's own plan tuple requires both non-null.
        extra = {"trust_profile_hash": "trust-1", "trust_approval_set_hash": "trust-approval-1"}
    ticket_id = record.insert(conn, "ticket", state=_KIND_STATE[kind], opened_at=record.now(), **extra)
    kwargs: dict = {"ticket_id": ticket_id, "kind": kind}
    if kind == "question":
        question_id = record.insert(
            conn, "question", ticket_id=ticket_id, stage="S2", round=1, rank=1,
            options='[{"label": "A", "consequence": "does A"}]', default_option=0, state="open",
        )
        kwargs["ref"] = f"question:{question_id}"
    elif kind == "escalation":
        stage_run_id = record.insert(conn, "stage_run", ticket_id=ticket_id, stage="S4", attempt=1, outcome="fail")
        kwargs["ref"] = f"stage_run:{stage_run_id}"
    elif kind == "plan_approval":
        return ticket_id, _seed_plan_approval_item(conn, ticket_id)
    elif kind == "packet_approval":
        kwargs["reviewer_set_id"] = _reviewer_set(conn, ticket_id, kind="effective", role="s6_reviewer", subject_hash="review-subj")
        kwargs["approval_subject_hash"] = "review-subj"
    item_id = queue.open_item(conn, **kwargs)
    return ticket_id, item_id


_ACCEPTED_PAIRS = [
    ("question", "answer"),
    ("question", "accept_default"),
    ("eligibility", "granted"),
    ("eligibility", "declined"),
    ("eligibility", "edit_scrutiny"),
    ("eligibility", "override"),
    ("plan_approval", "approve"),
    ("plan_approval", "redirect"),
    ("plan_approval", "send_back"),
    ("plan_approval", "abandon"),
    ("packet_approval", "approve"),
    ("packet_approval", "request_changes"),
    ("packet_approval", "send_back"),
    ("red_check", "send_back"),
    ("red_check", "abandon"),
    ("escalation", "resume"),
    ("escalation", "abandon"),
    ("manual_pause", "resume"),
    ("manual_pause", "stop"),
    ("manual_pause", "send_back"),
    ("rubric_inspection", "close_inspection"),
]


@pytest.mark.parametrize("kind, action", _ACCEPTED_PAIRS)
def test_each_valid_kind_action_pairing_from_the_day_one_mapping_is_accepted(conn, tmp_path, kind, action):
    """R-H-1: every pairing `queue.ACTIONS` lists for a kind
    is accepted, and resolves the item, when seeded with what that action needs."""
    ticket_id, item_id = _seed_item(conn, kind)
    kwargs = dict(item_id=item_id, action=action, actor=ABHISHEK, runs_dir=tmp_path)
    if action in ("approve", "redirect", "request_changes"):
        kwargs["bucket"] = "under_2m"
    if action in ("redirect", "send_back"):
        kwargs["to"] = "context"
        kwargs["note"] = "duplicates_existing_work: already built on another ticket"
    if action in ("redirect", "send_back", "abandon", "override", "request_changes"):
        kwargs["fm_id"] = "FM-07"
    queue.act(conn, **kwargs)
    assert record.get(conn, "queue_item", item_id)["resolved_at"] is not None


def test_escalation_send_back_uses_the_generic_send_back_transition(conn, tmp_path):
    """`escalated` has no `send_back_to_*` row of its own, so this pairing
    is exercised on a ticket seeded in `checks`, exactly as a red-check
    send-back would be -- the mapping permits the pairing regardless of
    which open state the ticket happens to carry it from."""
    ticket_id = record.insert(conn, "ticket", state="checks", opened_at=record.now())
    stage_run_id = record.insert(conn, "stage_run", ticket_id=ticket_id, stage="S4", attempt=1, outcome="fail")
    item_id = queue.open_item(conn, ticket_id=ticket_id, kind="escalation", ref=f"stage_run:{stage_run_id}")
    queue.act(
        conn, item_id=item_id, action="send_back", actor=ABHISHEK, to="context", fm_id="FM-07",
        note="technically_unsound: the approach does not hold", runs_dir=tmp_path,
    )
    assert record.get(conn, "ticket", ticket_id)["state"] == "context"
    assert record.get(conn, "queue_item", item_id)["resolved_at"] is not None


_REFUSED_PAIRS = [
    ("question", "approve"),
    ("eligibility", "resume"),
    ("plan_approval", "close_inspection"),
    ("packet_approval", "resume"),
    ("red_check", "approve"),
    ("escalation", "approve"),
    ("manual_pause", "abandon"),
    ("rubric_inspection", "approve"),
    ("pr_outcome", "answer"),
    ("pr_outcome", "control_event"),
]


@pytest.mark.parametrize("kind, action", _REFUSED_PAIRS)
def test_must_reject_a_kind_action_pairing_outside_the_day_one_mapping(conn, kind, action):
    """R-H-1: `pr_outcome` accepts none of these actions, `control_event`
    included, and every other kind refuses an action not in its own list."""
    _, item_id = _seed_item(conn, kind)
    with pytest.raises(queue.ActionRefused):
        queue.act(conn, item_id=item_id, action=action, actor=ABHISHEK, bucket="under_2m", to="context", fm_id="FM-07")



def test_must_reject_second_act_call_against_an_already_resolved_item(conn):
    _, item_id = _seed_item(conn, "eligibility")
    queue.act(conn, item_id=item_id, action="granted", actor=ABHISHEK)
    with pytest.raises(queue.ActionRefused):
        queue.act(conn, item_id=item_id, action="declined", actor=ABHISHEK)



def test_queue_latency_is_resolved_at_minus_queued_at_in_seconds(conn):
    item_id = record.insert(
        conn, "queue_item", kind="rubric_inspection",
        queued_at="2024-01-01T00:00:00+00:00", resolved_at="2024-01-01T00:05:30+00:00",
        resolved_by=ABHISHEK, action="close_inspection",
    )
    assert queue.latency_seconds(record.get(conn, "queue_item", item_id)) == 330.0


def test_queue_latency_is_none_while_the_item_is_still_open(conn):
    _, item_id = _seed_item(conn, "rubric_inspection")
    assert queue.latency_seconds(record.get(conn, "queue_item", item_id)) is None



def test_send_back_abandon_and_override_each_write_one_tag_naming_the_transition(conn, tmp_path):
    ticket_id, item_id = _seed_item(conn, "red_check")
    queue.act(
        conn, item_id=item_id, action="send_back", actor=ABHISHEK, to="context", fm_id="FM-07",
        note="duplicates_existing_work: already covered elsewhere", runs_dir=tmp_path,
    )
    send_back_tags = conn.execute("SELECT * FROM tag WHERE ticket_id = ?", (ticket_id,)).fetchall()
    assert [row["event_kind"] for row in send_back_tags] == ["send_back"]

    ticket_id2, item_id2 = _seed_item(conn, "red_check")
    queue.act(conn, item_id=item_id2, action="abandon", actor=ABHISHEK, fm_id="FM-07", runs_dir=tmp_path)
    abandon_tags = conn.execute("SELECT * FROM tag WHERE ticket_id = ?", (ticket_id2,)).fetchall()
    assert [row["event_kind"] for row in abandon_tags] == ["abandoned"]

    ticket_id3, item_id3 = _seed_item(conn, "eligibility")
    queue.act(conn, item_id=item_id3, action="override", actor=ABHISHEK, fm_id="FM-07", note="tier bumped")
    override_tags = conn.execute("SELECT * FROM tag WHERE ticket_id = ?", (ticket_id3,)).fetchall()
    assert [row["event_kind"] for row in override_tags] == ["override"]
    assert record.get(conn, "ticket", ticket_id3)["tier_override_reason"] == "tier bumped"



def test_control_event_records_an_incident_observation_and_leaves_the_item_open(conn, tmp_path):
    """A control event a human observes records the observation and a `control_defect`
    tag under that human, without resolving the item: an incident reviewer's own tag is
    the one control-defect tag the factory does not write mechanically."""
    ticket_id, item_id = _seed_item(conn, "red_check")
    result = queue.act(
        conn, item_id=item_id, action="control_event", actor=ABHISHEK,
        category="execution_boundary", severity="sev2", fm_id="FM-09", note="observed drift",
        runs_dir=tmp_path,
    )
    assert "control event recorded" in result
    assert record.get(conn, "queue_item", item_id)["resolved_at"] is None
    incidents = conn.execute(
        "SELECT * FROM incident_observation WHERE ticket_id = ? AND record_kind = 'control_defect_event'",
        (ticket_id,),
    ).fetchall()
    assert len(incidents) == 1
    assert incidents[0]["recorder_identity"] == ABHISHEK
    assert incidents[0]["severity"] == "sev2"
    tag_rows = conn.execute("SELECT * FROM tag WHERE event_kind = 'control_defect'").fetchall()
    assert [(row["tagged_by"], row["ref"]) for row in tag_rows] == [(ABHISHEK, f"queue_item:{item_id}")]



def test_factory_act_resolves_the_item_and_resumes_only_when_the_action_permits_it(db_path):
    """`granted` alone leaves the ticket where it was -- the intake gate
    applies `eligibility_granted` only on a later `factory advance` -- while
    `send_back` applies its transition immediately, as part of `act` itself."""
    conn = connect(db_path)
    ticket_id = tickets.open_ticket(conn, title="t", **_governed_ticket_fields(conn))
    item_id = queue.open_item(conn, ticket_id=ticket_id, kind="eligibility")
    conn.commit()
    conn.close()

    cli.main(["--db", str(db_path), "act", str(item_id), "granted", "--actor", ABHISHEK])

    conn = connect(db_path)
    try:
        item = record.get(conn, "queue_item", item_id)
        assert item["resolved_at"] is not None and item["action"] == "granted"
        assert record.get(conn, "ticket", ticket_id)["state"] == "intake"
    finally:
        conn.close()

    conn = connect(db_path)
    ticket_id2 = record.insert(conn, "ticket", state="checks", opened_at=record.now())
    item_id2 = queue.open_item(conn, ticket_id=ticket_id2, kind="red_check")
    conn.commit()
    conn.close()

    cli.main([
        "--db", str(db_path), "act", str(item_id2), "send_back", "--actor", ABHISHEK, "--to", "context",
        "--fm", "FM-07", "--note", "duplicates_existing_work: already handled",
    ])

    conn = connect(db_path)
    try:
        assert record.get(conn, "ticket", ticket_id2)["state"] == "context"
    finally:
        conn.close()


def test_factory_queue_is_a_thin_wrapper_over_list_queue(db_path, capsys):
    conn = connect(db_path)
    ticket_id = tickets.open_ticket(conn, title="t")
    queue.open_item(conn, ticket_id=ticket_id, kind="eligibility")
    conn.commit()
    conn.close()

    cli.main(["--db", str(db_path), "queue"])
    out = capsys.readouterr().out

    conn = connect(db_path)
    try:
        expected = queue.list_queue(conn)
    finally:
        conn.close()
    assert out.strip() == expected.strip()


def test_factory_abandon_records_a_tag_and_coverage_without_a_queued_item(db_path):
    conn = connect(db_path)
    ticket_id = tickets.open_ticket(conn, title="t")
    conn.commit()
    conn.close()

    cli.main(["--db", str(db_path), "abandon", str(ticket_id), "--actor", ABHISHEK, "--fm", "FM-07"])

    conn = connect(db_path)
    try:
        assert record.get(conn, "ticket", ticket_id)["state"] == "abandoned"
        abandoned_tags = conn.execute(
            "SELECT * FROM tag WHERE ticket_id = ? AND event_kind = 'abandoned'", (ticket_id,)
        ).fetchall()
        assert len(abandoned_tags) == 1
        coverage = conn.execute(
            "SELECT * FROM incident_observation WHERE ticket_id = ? AND coverage_status = 'not_deployed'",
            (ticket_id,),
        ).fetchall()
        assert len(coverage) == 1
        assert conn.execute("SELECT COUNT(*) FROM queue_item WHERE ticket_id = ?", (ticket_id,)).fetchone()[0] == 0
    finally:
        conn.close()


def test_factory_tag_records_one_human_tag_on_the_named_target(db_path):
    conn = connect(db_path)
    refs = issue_review_waiver(conn, db_path.parent)
    conn.commit()
    before = conn.execute("SELECT COUNT(*) FROM tag WHERE ticket_id = ?", (refs["ticket_id"],)).fetchone()[0]
    conn.close()

    cli.main([
        "--db", str(db_path), "tag", f"waiver:{refs['waiver_id']}", "policy_exception",
        "--fm", "FM-10", "--actor", ABHISHEK, "--severity", "sev3",
    ])

    conn = connect(db_path)
    try:
        rows = conn.execute("SELECT * FROM tag WHERE ticket_id = ? ORDER BY id", (refs["ticket_id"],)).fetchall()
        assert len(rows) == before + 1
        assert (rows[-1]["event_kind"], rows[-1]["severity"], rows[-1]["tagged_by"]) == ("policy_exception", "sev3", ABHISHEK)
    finally:
        conn.close()
