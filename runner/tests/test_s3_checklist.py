"""The bootstrap checklist: expected instances, duplicate/missing rejection, `human_verdict`
binding, and the fail/blind-spot/waiver rules (R-S3-20).

`factory/rubrics/S3.md` is still a stub while a parallel effort builds its rubric table, so
every test here that needs an S3-stage checklist line reads a small, self-contained rubric file
of its own under `factory/evals/rubrics/S3/fixtures/checklist/` instead of the committed
(stub) file -- `rubric_ok.md` for a clean `contract_unit` line, `rubric_duplicate.md` for one
that deliberately collides with `S2.md`'s own `R-S2-1` row id. The real, committed `S1.md` and
`S2.md` are used as-is, since both already carry their real checklist lines.
"""
import json

import pytest
import yaml

from runner import artefact_registry, checklist, manifest, queue, record, waivers
from runner.db import connect
from runner.paths import FACTORY_DIR

RUBRIC_DIR = FACTORY_DIR / "rubrics"
S1_RUBRIC = RUBRIC_DIR / "S1.md"
S2_RUBRIC = RUBRIC_DIR / "S2.md"

FIXTURE_DIR = FACTORY_DIR / "evals" / "rubrics" / "S3" / "fixtures" / "checklist"
RUBRIC_OK = FIXTURE_DIR / "rubric_ok.md"
RUBRIC_DUPLICATE = FIXTURE_DIR / "rubric_duplicate.md"

OK_RUBRIC_PATHS = (S1_RUBRIC, S2_RUBRIC, RUBRIC_OK)

EXPECTED = json.loads((FIXTURE_DIR / "expected.json").read_text())
VERDICTS = yaml.safe_load((FIXTURE_DIR / "verdicts.yaml").read_text())

ABHISHEK = "abhishek"


def _conn(tmp_path):
    return connect(tmp_path / "factory.sqlite")


def _ticket_with_fixture(conn, tmp_path, *, state="plan_review", n_questions=2) -> int:
    """A ticket with the checklist fixture's brief/criteria/plan registered and `n_questions` open questions.

    The question rows are the very first rows inserted into a fresh
    connection, so their ids are deterministically `1`, `2`, ... --
    exactly the ids `expected.json`/`verdicts.yaml` hardcode.
    """
    ticket_id = record.insert(
        conn, "ticket", state=state, opened_at=record.now(), factory_manifest_hash=manifest.current_hash(),
        trust_profile_hash="trust-1", trust_approval_set_hash="trust-approval-1",
        base_sha="base-1", target_base_sha="base-1",
    )
    for _ in range(n_questions):
        record.insert(
            conn, "question", ticket_id=ticket_id, stage="S2", round=1, rank=1,
            options="[]", state="open", blocking=0,
        )
    for kind in ("brief", "criteria", "plan"):
        artefact_registry.register(conn, ticket_id=ticket_id, kind=kind, path=FIXTURE_DIR / f"{kind}.md")
    return ticket_id


def _pairs(instances) -> set[tuple[str, str]]:
    return {(i.rubric_line_id, i.subject_item_key) for i in instances}




def test_expected_instances_matches_the_fixtures_own_expected_set(tmp_path):
    """R-S3-20: `expected_instances` expands every `checklist: yes` line across the pinned
    rubrics by its own subject, matching the fixture's `expected.json` pair for pair."""
    conn = _conn(tmp_path)
    ticket_id = _ticket_with_fixture(conn, tmp_path)
    instances = checklist.expected_instances(conn, record.get(conn, "ticket", ticket_id), rubric_paths=OK_RUBRIC_PATHS)
    assert _pairs(instances) == {(row["rubric_line_id"], row["subject_item_key"]) for row in EXPECTED}
    assert len(instances) == len(EXPECTED)  # no accidental collapse: every pair is distinct


def test_expected_instances_reflects_the_tickets_current_membership(tmp_path):
    """The expected set is derived fresh each call: a third question adds two more `question`-subject instances."""
    conn = _conn(tmp_path)
    ticket_id = _ticket_with_fixture(conn, tmp_path, n_questions=3)
    instances = checklist.expected_instances(conn, record.get(conn, "ticket", ticket_id), rubric_paths=OK_RUBRIC_PATHS)
    assert len(instances) == len(EXPECTED) + 2  # R-S2-5 and R-S2-14 each gain one more question key




def test_a_duplicate_rubric_line_and_subject_pairing_is_rejected(tmp_path):
    """must-reject: `rubric_duplicate.md` reuses `S2.md`'s own `R-S2-1` row id for a `criterion`
    line, so combining it assembles the identical `(rubric_line_id, subject_item_key)` pair
    `S2.md`'s real `R-S2-1:grader` line already contributes, once per `AC-n`."""
    conn = _conn(tmp_path)
    ticket_id = _ticket_with_fixture(conn, tmp_path)
    ticket = record.get(conn, "ticket", ticket_id)
    with pytest.raises(checklist.ChecklistError):
        checklist.expected_instances(conn, ticket, rubric_paths=(S1_RUBRIC, S2_RUBRIC, RUBRIC_DUPLICATE))


def test_a_checklist_missing_one_instances_verdict_is_reported_incomplete(tmp_path):
    """must-reject (as an incomplete checklist): every instance but the last in `verdicts.yaml`
    gets a `pass` verdict, and `completeness` names the one left unverdicted as missing."""
    conn = _conn(tmp_path)
    ticket_id = _ticket_with_fixture(conn, tmp_path)
    ticket = record.get(conn, "ticket", ticket_id)
    instances = checklist.expected_instances(conn, ticket, rubric_paths=OK_RUBRIC_PATHS)
    plan_artefact = artefact_registry.latest(conn, ticket_id, "plan")
    item_id = queue.open_item(conn, ticket_id=ticket_id, kind="plan_approval", stage="S3")
    item = record.get(conn, "queue_item", item_id)

    by_pair = {(i.rubric_line_id, i.subject_item_key): i for i in instances}
    for row in VERDICTS[:-1]:
        instance = by_pair[(row["rubric_line_id"], row["subject_item_key"])]
        checklist.record_verdict(
            conn, ticket=ticket, item=item, instance=instance, verdict="pass",
            evidence_ids=[plan_artefact["id"]], waiver_id=None, reviewer_identity=ABHISHEK,
            reviewer_role="s3_reviewer", note=None,
            rubric_paths=OK_RUBRIC_PATHS,
        )

    status = checklist.completeness(conn, ticket, instances)
    assert not status.complete
    last = VERDICTS[-1]
    assert (last["rubric_line_id"], last["subject_item_key"]) == (
        status.missing[0].rubric_line_id, status.missing[0].subject_item_key,
    )


def test_a_fully_verdicted_checklist_is_reported_complete(tmp_path):
    """Every instance in `expected.json` gets a `pass` verdict from `verdicts.yaml`; completeness holds."""
    conn = _conn(tmp_path)
    ticket_id = _ticket_with_fixture(conn, tmp_path)
    ticket = record.get(conn, "ticket", ticket_id)
    instances = checklist.expected_instances(conn, ticket, rubric_paths=OK_RUBRIC_PATHS)
    plan_artefact = artefact_registry.latest(conn, ticket_id, "plan")
    item_id = queue.open_item(conn, ticket_id=ticket_id, kind="plan_approval", stage="S3")
    item = record.get(conn, "queue_item", item_id)

    by_pair = {(i.rubric_line_id, i.subject_item_key): i for i in instances}
    for row in VERDICTS:
        instance = by_pair[(row["rubric_line_id"], row["subject_item_key"])]
        checklist.record_verdict(
            conn, ticket=ticket, item=item, instance=instance, verdict="pass",
            evidence_ids=[plan_artefact["id"]], waiver_id=None, reviewer_identity=ABHISHEK,
            reviewer_role="s3_reviewer", note=None,
            rubric_paths=OK_RUBRIC_PATHS,
        )

    status = checklist.completeness(conn, ticket, instances)
    assert status.complete
    assert not status.missing and not status.unwaived_blind_spots and not status.failed




def test_a_recorded_verdict_binds_the_stage_appropriate_subject_artefact_and_evidence(tmp_path):
    """R-S3-20: an S1-stage instance binds the `brief` artefact, an S2-stage instance the
    `criteria` artefact, and the fixture's own S3-stage instance the `plan` artefact -- each
    verdict's `evidence_hashes` matches the cited artefact's own registered hash."""
    conn = _conn(tmp_path)
    ticket_id = _ticket_with_fixture(conn, tmp_path)
    ticket = record.get(conn, "ticket", ticket_id)
    instances = checklist.expected_instances(conn, ticket, rubric_paths=OK_RUBRIC_PATHS)
    by_line = {i.rubric_line_id: i for i in instances}
    brief_artefact = artefact_registry.latest(conn, ticket_id, "brief")
    criteria_artefact = artefact_registry.latest(conn, ticket_id, "criteria")
    plan_artefact = artefact_registry.latest(conn, ticket_id, "plan")
    item_id = queue.open_item(conn, ticket_id=ticket_id, kind="plan_approval", stage="S3")
    item = record.get(conn, "queue_item", item_id)

    cases = [
        ("R-S1-2:grader", brief_artefact),
        ("R-S2-1:grader", criteria_artefact),
        ("R-CK-1:grader", plan_artefact),
    ]
    for line_id, subject_artefact in cases:
        instance = by_line[line_id]
        verdict_id = checklist.record_verdict(
            conn, ticket=ticket, item=item, instance=instance, verdict="pass",
            evidence_ids=[subject_artefact["id"]], waiver_id=None, reviewer_identity=ABHISHEK,
            reviewer_role="s3_reviewer", note="binding check",
            rubric_paths=OK_RUBRIC_PATHS,
        )
        row = record.get(conn, "human_verdict", verdict_id)
        assert row["subject_artefact_id"] == subject_artefact["id"]
        assert row["subject_artefact_hash"] == subject_artefact["hash"]
        assert row["rubric_line_id"] == instance.rubric_line_id
        assert row["rubric_hash"] == instance.rubric_hash
        assert json.loads(row["evidence_hashes"]) == [subject_artefact["hash"]]
        assert row["reviewer_identity"] == ABHISHEK
        assert row["reviewer_role"] == "s3_reviewer"
        assert row["created_at"] is not None


def test_a_correction_verdict_is_a_newer_row_and_the_newest_one_wins(tmp_path):
    """A second verdict on the same instance is a correction, not a duplicate error: both rows
    persist, and `completeness`/`verdict_set` read the newest one."""
    conn = _conn(tmp_path)
    ticket_id = _ticket_with_fixture(conn, tmp_path)
    ticket = record.get(conn, "ticket", ticket_id)
    instances = checklist.expected_instances(conn, ticket, rubric_paths=OK_RUBRIC_PATHS)
    instance = next(i for i in instances if i.rubric_line_id == "R-CK-1:grader")
    plan_artefact = artefact_registry.latest(conn, ticket_id, "plan")
    item_id = queue.open_item(conn, ticket_id=ticket_id, kind="plan_approval", stage="S3")
    item = record.get(conn, "queue_item", item_id)

    first_id = checklist.record_verdict(
        conn, ticket=ticket, item=item, instance=instance, verdict="blind_spot",
        evidence_ids=[], waiver_id=None, reviewer_identity=ABHISHEK, reviewer_role="s3_reviewer", note=None,
        rubric_paths=OK_RUBRIC_PATHS,
    )
    second_id = checklist.record_verdict(
        conn, ticket=ticket, item=item, instance=instance, verdict="pass",
        evidence_ids=[plan_artefact["id"]], waiver_id=None, reviewer_identity=ABHISHEK,
        reviewer_role="s3_reviewer", note="corrected after review",
        rubric_paths=OK_RUBRIC_PATHS,
    )
    assert second_id != first_id
    rows = conn.execute("SELECT * FROM human_verdict WHERE ticket_id = ?", (ticket_id,)).fetchall()
    assert len(rows) == 2

    verdict_set = checklist.verdict_set(conn, ticket_id)
    assert len(verdict_set) == 1
    assert verdict_set[0]["id"] == second_id
    assert verdict_set[0]["verdict"] == "pass"




def test_must_reject_a_pass_verdict_with_no_evidence(tmp_path):
    conn = _conn(tmp_path)
    ticket_id = _ticket_with_fixture(conn, tmp_path)
    ticket = record.get(conn, "ticket", ticket_id)
    instances = checklist.expected_instances(conn, ticket, rubric_paths=OK_RUBRIC_PATHS)
    instance = instances[0]
    item_id = queue.open_item(conn, ticket_id=ticket_id, kind="plan_approval", stage="S3")
    item = record.get(conn, "queue_item", item_id)
    with pytest.raises(ValueError, match="evidence"):
        checklist.record_verdict(
            conn, ticket=ticket, item=item, instance=instance, verdict="pass",
            evidence_ids=[], waiver_id=None, reviewer_identity=ABHISHEK, reviewer_role="s3_reviewer", note=None,
            rubric_paths=OK_RUBRIC_PATHS,
        )


def test_must_reject_an_evidence_id_that_is_not_this_tickets_artefact(tmp_path):
    conn = _conn(tmp_path)
    ticket_id = _ticket_with_fixture(conn, tmp_path)
    other_ticket_id = _ticket_with_fixture(conn, tmp_path)
    ticket = record.get(conn, "ticket", ticket_id)
    instances = checklist.expected_instances(conn, ticket, rubric_paths=OK_RUBRIC_PATHS)
    instance = instances[0]
    item_id = queue.open_item(conn, ticket_id=ticket_id, kind="plan_approval", stage="S3")
    item = record.get(conn, "queue_item", item_id)
    other_plan = artefact_registry.latest(conn, other_ticket_id, "plan")
    with pytest.raises(ValueError, match="not an artefact"):
        checklist.record_verdict(
            conn, ticket=ticket, item=item, instance=instance, verdict="pass",
            evidence_ids=[other_plan["id"]], waiver_id=None, reviewer_identity=ABHISHEK,
            reviewer_role="s3_reviewer", note=None,
            rubric_paths=OK_RUBRIC_PATHS,
        )


def test_must_reject_an_instance_outside_the_expected_set(tmp_path):
    conn = _conn(tmp_path)
    ticket_id = _ticket_with_fixture(conn, tmp_path)
    ticket = record.get(conn, "ticket", ticket_id)
    item_id = queue.open_item(conn, ticket_id=ticket_id, kind="plan_approval", stage="S3")
    item = record.get(conn, "queue_item", item_id)
    bogus = checklist.Instance(
        rubric_line_id="R-NOPE:grader", subject_item_key="brief", rubric_file=str(S1_RUBRIC), rubric_hash="deadbeef",
    )
    with pytest.raises(ValueError, match="outside"):
        checklist.record_verdict(
            conn, ticket=ticket, item=item, instance=bogus, verdict="blind_spot",
            evidence_ids=[], waiver_id=None, reviewer_identity=ABHISHEK, reviewer_role="s3_reviewer", note=None,
            rubric_paths=OK_RUBRIC_PATHS,
        )




@pytest.mark.parametrize(
    "rubric_line_id, expected_state",
    [("R-S1-2:grader", "context"), ("R-S2-1:grader", "clarifying"), ("R-S3-2:grader", "planning")],
)
def test_a_fail_verdict_sends_the_ticket_back_to_the_lines_own_stage(tmp_path, rubric_line_id, expected_state):
    """R-S3-20: a `fail` verdict on an S1/S2/S3-stage line returns the ticket to that stage's
    own state -- `context`, `clarifying`, or `planning` respectively -- and resolves the item."""
    conn = _conn(tmp_path)
    ticket_id = _ticket_with_fixture(conn, tmp_path, state="plan_review")
    ticket = record.get(conn, "ticket", ticket_id)
    instances = checklist.expected_instances(conn, ticket)
    instance = next(i for i in instances if i.rubric_line_id == rubric_line_id)
    identity = "abhishek"
    slot = json.dumps([{"source_rule": "s3_reviewer_role", "role": "s3_reviewer", "owner": identity, "min_count": 1, "distinct_from": [], "resolved": True}])
    reviewer_set_id = record.insert(conn, "reviewer_set", ticket_id=ticket_id, kind="planned", content_hash="planned-1", slots=slot)
    item_id = queue.open_item(conn, ticket_id=ticket_id, kind="plan_approval", stage="S3", reviewer_set_id=reviewer_set_id)

    queue.act(
        conn, item_id=item_id, action="verdict", actor=identity, line=instance.rubric_line_id,
        key=instance.subject_item_key, verdict="fail", fm_id="FM-15",
        note="technically_unsound: does not hold", runs_dir=tmp_path,
    )

    assert record.get(conn, "ticket", ticket_id)["state"] == expected_state
    assert record.get(conn, "queue_item", item_id)["resolved_at"] is not None
    send_back = conn.execute(
        "SELECT * FROM tag WHERE ticket_id = ? AND event_kind = 'send_back'", (ticket_id,)
    ).fetchall()
    assert len(send_back) == 1


def test_must_reject_a_fail_verdict_with_no_failure_mode_id(tmp_path):
    conn = _conn(tmp_path)
    ticket_id = _ticket_with_fixture(conn, tmp_path, state="plan_review")
    ticket = record.get(conn, "ticket", ticket_id)
    instances = checklist.expected_instances(conn, ticket)
    instance = instances[0]
    identity = "abhishek"
    slot = json.dumps([{"source_rule": "s3_reviewer_role", "role": "s3_reviewer", "owner": identity, "min_count": 1, "distinct_from": [], "resolved": True}])
    reviewer_set_id = record.insert(conn, "reviewer_set", ticket_id=ticket_id, kind="planned", content_hash="planned-1", slots=slot)
    item_id = queue.open_item(conn, ticket_id=ticket_id, kind="plan_approval", stage="S3", reviewer_set_id=reviewer_set_id)
    with pytest.raises(queue.ActionRefused):
        queue.act(
            conn, item_id=item_id, action="verdict", actor=identity, line=instance.rubric_line_id,
            key=instance.subject_item_key, verdict="fail", runs_dir=tmp_path,
        )




def test_an_unwaived_blind_spot_blocks_completeness(tmp_path):
    conn = _conn(tmp_path)
    ticket_id = _ticket_with_fixture(conn, tmp_path)
    ticket = record.get(conn, "ticket", ticket_id)
    instances = checklist.expected_instances(conn, ticket, rubric_paths=OK_RUBRIC_PATHS)
    instance = next(i for i in instances if i.rubric_line_id == "R-CK-1:grader")
    item_id = queue.open_item(conn, ticket_id=ticket_id, kind="plan_approval", stage="S3")
    item = record.get(conn, "queue_item", item_id)

    checklist.record_verdict(
        conn, ticket=ticket, item=item, instance=instance, verdict="blind_spot",
        evidence_ids=[], waiver_id=None, reviewer_identity=ABHISHEK, reviewer_role="s3_reviewer", note="no evidence available",
        rubric_paths=OK_RUBRIC_PATHS,
    )
    status = checklist.completeness(conn, ticket, [instance])
    assert not status.complete
    assert status.unwaived_blind_spots == (instance,)


def test_a_blind_spot_naming_a_seeded_unexpired_waiver_does_not_block(tmp_path):
    conn = _conn(tmp_path)
    ticket_id = _ticket_with_fixture(conn, tmp_path)
    ticket = record.get(conn, "ticket", ticket_id)
    instances = checklist.expected_instances(conn, ticket, rubric_paths=OK_RUBRIC_PATHS)
    instance = next(i for i in instances if i.rubric_line_id == "R-CK-1:grader")
    item_id = queue.open_item(conn, ticket_id=ticket_id, kind="plan_approval", stage="S3")
    item = record.get(conn, "queue_item", item_id)

    verdict_id = checklist.record_verdict(
        conn, ticket=ticket, item=item, instance=instance, verdict="blind_spot",
        evidence_ids=[], waiver_id=None, reviewer_identity=ABHISHEK, reviewer_role="s3_reviewer", note="no evidence available",
        rubric_paths=OK_RUBRIC_PATHS,
    )
    # A real, policy-backed waiver: `completeness` now asks
    # `runner.waivers.validity`, which checks the policy binding and actor
    # authority alongside expiry, not expiry alone.
    verdict = record.get(conn, "human_verdict", verdict_id)
    policy = waivers.load_policy()
    record.insert(
        conn, "waiver", ticket_id=ticket_id, waived_human_verdict_id=verdict_id, actor_identity=ABHISHEK,
        actor_role="s3_reviewer", policy_id="impact-blind-spot", policy_version="1", policy_hash=policy.policy_hash,
        subject_kind="plan_candidate", subject_hash=waivers.subject_hash(conn, human_verdict=verdict),
        reason="accepted risk", scope="ticket: R-CK-1:grader", compensating_controls="manual review",
        evidence_ids="[]", evidence_hashes="[]", issued_at=record.now(), expires_at="2999-01-01T00:00:00+00:00",
    )
    status = checklist.completeness(conn, ticket, [instance])
    assert status.complete
    assert status.unwaived_blind_spots == ()


def test_an_expired_waiver_leaves_the_blind_spot_unwaived(tmp_path):
    conn = _conn(tmp_path)
    ticket_id = _ticket_with_fixture(conn, tmp_path)
    ticket = record.get(conn, "ticket", ticket_id)
    instances = checklist.expected_instances(conn, ticket, rubric_paths=OK_RUBRIC_PATHS)
    instance = next(i for i in instances if i.rubric_line_id == "R-CK-1:grader")
    item_id = queue.open_item(conn, ticket_id=ticket_id, kind="plan_approval", stage="S3")
    item = record.get(conn, "queue_item", item_id)

    verdict_id = checklist.record_verdict(
        conn, ticket=ticket, item=item, instance=instance, verdict="blind_spot",
        evidence_ids=[], waiver_id=None, reviewer_identity=ABHISHEK, reviewer_role="s3_reviewer", note="no evidence available",
        rubric_paths=OK_RUBRIC_PATHS,
    )
    record.insert(
        conn, "waiver", ticket_id=ticket_id, waived_human_verdict_id=verdict_id, actor_identity=ABHISHEK,
        reason="accepted risk", issued_at="2000-01-01T00:00:00+00:00", expires_at="2000-02-01T00:00:00+00:00",
    )
    status = checklist.completeness(conn, ticket, [instance])
    assert not status.complete
    assert status.unwaived_blind_spots == (instance,)




def test_checklist_hash_changes_with_the_expected_set_and_verdict_set_changes_with_a_correction(tmp_path):
    """R-S3-20: `semantic_checklist_hash` (over `expected_instances`) and `human_verdict_set_hash`
    (over `verdict_set`, through `binding.set_hash`) are independent, order-free hashes that
    change exactly when their own member set changes -- the two inputs the plan tuple binds
    separately so a rubric/artefact change and a verdict correction are each visible on their own."""
    from runner import binding

    conn = _conn(tmp_path)
    ticket_id = _ticket_with_fixture(conn, tmp_path)
    ticket = record.get(conn, "ticket", ticket_id)
    instances = checklist.expected_instances(conn, ticket, rubric_paths=OK_RUBRIC_PATHS)
    checklist_hash_before = checklist.checklist_hash(instances)

    more_instances = checklist.expected_instances(
        conn, record.get(conn, "ticket", _ticket_with_fixture(conn, tmp_path, n_questions=3)),
        rubric_paths=OK_RUBRIC_PATHS,
    )
    assert checklist.checklist_hash(more_instances) != checklist_hash_before

    verdict_set_before = binding.set_hash(checklist.verdict_set(conn, ticket_id))
    instance = next(i for i in instances if i.rubric_line_id == "R-CK-1:grader")
    plan_artefact = artefact_registry.latest(conn, ticket_id, "plan")
    item_id = queue.open_item(conn, ticket_id=ticket_id, kind="plan_approval", stage="S3")
    item = record.get(conn, "queue_item", item_id)
    checklist.record_verdict(
        conn, ticket=ticket, item=item, instance=instance, verdict="pass",
        evidence_ids=[plan_artefact["id"]], waiver_id=None, reviewer_identity=ABHISHEK,
        reviewer_role="s3_reviewer", note=None,
        rubric_paths=OK_RUBRIC_PATHS,
    )
    assert binding.set_hash(checklist.verdict_set(conn, ticket_id)) != verdict_set_before
