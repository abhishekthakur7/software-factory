"""The batch verdict form: `factory act <plan_approval item> verdicts <file>`.

Reuses `test_act.py`'s governed plan-approval setup (a ticket in
`plan_review` with real registered brief/criteria/plan artefacts and a
planned `s3_reviewer` slot) up to the point its checklist is expected, but
seeds no verdicts itself -- the whole point of this file is driving every
expected instance through the batch form instead of one `verdict` call
per instance.
"""
import json

import pytest
import yaml

from runner import artefact_registry, artefacts, checklist, manifest, owners, queue, record
from runner.db import connect
from runner.reviewer_sets import Slot
from runner.tests.test_act import ABHISHEK

STAGES = ("brief", "criteria", "plan")


@pytest.fixture
def conn(tmp_path):
    connection = connect(tmp_path / "factory.sqlite")
    yield connection
    connection.close()


def _open_plan_approval_item(conn, tmp_path) -> tuple[int, int]:
    """A `plan_approval` item with a real, single-slot reviewer set and every artefact its checklist expects,
    with no verdict recorded against any instance yet."""
    ticket_id = record.insert(
        conn, "ticket", state="plan_review", opened_at=record.now(),
        trust_profile_hash="trust-1", trust_approval_set_hash="trust-approval-1",
        factory_manifest_hash=manifest.current_hash(), base_sha="base-1", target_base_sha="base-1",
    )
    for artefact_kind in STAGES:
        path = tmp_path / f"{artefact_kind}.md"
        path.write_text(f"## {artefacts.SECTIONS[artefact_kind][0]}\n\nstub\n")
        artefact_registry.register(conn, ticket_id=ticket_id, kind=artefact_kind, path=path)
    identity = owners.load_owners().roles["s3_reviewer"]["identity"]
    slot = Slot(source_rule="s3_reviewer_role", role="s3_reviewer", owner=identity, min_count=1)
    reviewer_set_id = record.insert(
        conn, "reviewer_set", ticket_id=ticket_id, kind="planned", content_hash="planned-subj-batch",
        slots=json.dumps([slot.to_json()]),
    )
    item_id = queue.open_item(conn, ticket_id=ticket_id, kind="plan_approval", reviewer_set_id=reviewer_set_id)
    return ticket_id, item_id


def _expected_instances(conn, ticket_id):
    ticket = record.get(conn, "ticket", ticket_id)
    return checklist.expected_instances(conn, ticket)


def test_a_batch_of_pass_tuples_writes_one_verdict_row_each_and_completes_the_checklist(conn, tmp_path):
    """R-H-4: each tuple's `(rubric_line_id, subject_item_key, verdict, evidence)` writes one `human_verdict`
    row through the same path a single `verdict` action uses. Completing the checklist this way leaves the
    item itself open for its own later `approve`, exactly as completing it one `verdict` call at a time does
    -- a `pass` never resolves a `plan_approval` item on its own, batched or not."""
    ticket_id, item_id = _open_plan_approval_item(conn, tmp_path)
    instances = _expected_instances(conn, ticket_id)
    assert len(instances) >= 2, "the fixture must expect more than one instance for a batch to be meaningful"
    plan_artefact = artefact_registry.latest(conn, ticket_id, "plan")

    entries = [
        {
            "rubric_line_id": instance.rubric_line_id, "subject_item_key": instance.subject_item_key,
            "verdict": "pass", "evidence": [plan_artefact["id"]],
        }
        for instance in instances
    ]
    verdicts_file = tmp_path / "verdicts.yaml"
    verdicts_file.write_text(yaml.safe_dump(entries))

    queue.act(
        conn, item_id=item_id, action="verdicts", actor=ABHISHEK, fields={"verdicts_file": str(verdicts_file)},
        runs_dir=tmp_path,
    )

    rows = conn.execute(
        "SELECT rubric_line_id, subject_item_key, verdict FROM human_verdict WHERE ticket_id = ? ORDER BY id",
        (ticket_id,),
    ).fetchall()
    assert len(rows) == len(instances)
    assert all(row["verdict"] == "pass" for row in rows)
    ticket = record.get(conn, "ticket", ticket_id)
    assert checklist.completeness(conn, ticket, instances).complete
    assert record.get(conn, "queue_item", item_id)["resolved_at"] is None

    # The checklist's completion is exactly what `approve`'s own race guard
    # needs; the same still-open item now accepts it.
    queue.act(
        conn, item_id=item_id, action="approve", actor=ABHISHEK, bucket="under_2m",
        self_contained="yes", runs_dir=tmp_path,
    )
    assert record.get(conn, "queue_item", item_id)["resolved_at"] is not None


def test_a_fail_tuple_stops_the_batch_there_and_sends_the_ticket_back(conn, tmp_path):
    """R-H-4: a `fail` in the batch sends the ticket back exactly as a lone `fail` would, and no tuple after it
    in the file is ever applied."""
    ticket_id, item_id = _open_plan_approval_item(conn, tmp_path)
    instances = _expected_instances(conn, ticket_id)
    assert len(instances) >= 2
    plan_artefact = artefact_registry.latest(conn, ticket_id, "plan")

    entries = [
        {
            "rubric_line_id": instances[0].rubric_line_id, "subject_item_key": instances[0].subject_item_key,
            "verdict": "fail", "evidence": [], "note": "technically_unsound: the approach does not hold",
        },
        {
            "rubric_line_id": instances[1].rubric_line_id, "subject_item_key": instances[1].subject_item_key,
            "verdict": "pass", "evidence": [plan_artefact["id"]],
        },
    ]
    verdicts_file = tmp_path / "verdicts.yaml"
    verdicts_file.write_text(yaml.safe_dump(entries))

    queue.act(
        conn, item_id=item_id, action="verdicts", actor=ABHISHEK, fm_id="FM-07",
        fields={"verdicts_file": str(verdicts_file)}, runs_dir=tmp_path,
    )

    rows = conn.execute(
        "SELECT rubric_line_id, verdict FROM human_verdict WHERE ticket_id = ? ORDER BY id", (ticket_id,)
    ).fetchall()
    assert [row["rubric_line_id"] for row in rows] == [instances[0].rubric_line_id]
    assert rows[0]["verdict"] == "fail"
    assert record.get(conn, "ticket", ticket_id)["state"] in ("context", "clarifying", "planning")
    assert record.get(conn, "queue_item", item_id)["resolved_at"] is not None


def test_must_reject_verdicts_with_no_file(conn, tmp_path):
    ticket_id, item_id = _open_plan_approval_item(conn, tmp_path)
    with pytest.raises(queue.ActionRefused):
        queue.act(conn, item_id=item_id, action="verdicts", actor=ABHISHEK, fields={}, runs_dir=tmp_path)
