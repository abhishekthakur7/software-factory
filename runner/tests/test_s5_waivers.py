"""Waivers over a blocking epistemic blind spot, and the non-waivable list (R-S5-13).

A plan-candidate waiver binds a `human_verdict` and enters the plan
tuple's own waiver-set hash; a review-tuple waiver binds a `check_result`
and shares the `red_check` item S5's own failures opened, resolving it
once the run's every blocking result clears. Every seeded fixture under
`fixtures/waivers/never_waivable/` names one `waiver-policy.yaml`
never-waivable check name; the checklist fixture under
`factory/evals/rubrics/S3/fixtures/checklist/` (S1/S2's own real rubrics
plus a small self-contained `contract_unit` line) supplies a real,
committed brief/criteria/plan and an `R-S1-3:grader` instance for the
plan-candidate cases.
"""
import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml

from runner import artefact_registry, binding, checklist, manifest, owners, plan_tuple, queue, record, tags, waivers
from runner.db import connect
from runner.paths import FACTORY_DIR
from runner.tests.support import approve_current_plan

ABHISHEK = "abhishek"

CHECKLIST_FIXTURE_DIR = FACTORY_DIR / "evals" / "rubrics" / "S3" / "fixtures" / "checklist"
S1_RUBRIC = FACTORY_DIR / "rubrics" / "S1.md"
S2_RUBRIC = FACTORY_DIR / "rubrics" / "S2.md"
RUBRIC_OK = CHECKLIST_FIXTURE_DIR / "rubric_ok.md"
OK_RUBRIC_PATHS = (S1_RUBRIC, S2_RUBRIC, RUBRIC_OK)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "waivers"
NEVER_WAIVABLE_FIXTURES = sorted((FIXTURE_DIR / "never_waivable").glob("*.yaml"))

PLAN_POLICY_ID = "impact-blind-spot"
REVIEW_POLICY_ID = "contract-evidence-gap"

PACKET_ASSEMBLE = FACTORY_DIR / "scripts" / "tools" / "packet_assemble"


def _conn(tmp_path):
    return connect(tmp_path / "factory.sqlite")


def _soon() -> str:
    return (datetime.now(UTC) + timedelta(days=1)).isoformat(timespec="seconds")


def _ticket(conn, tmp_path) -> int:
    ticket_id = record.insert(
        conn, "ticket", state="checks", opened_at=record.now(), factory_manifest_hash=manifest.current_hash(),
        trust_profile_hash="trust-1", trust_approval_set_hash="trust-approval-1",
        base_sha="base-1", target_base_sha="base-1",
    )
    for kind in ("brief", "criteria", "plan"):
        artefact_registry.register(conn, ticket_id=ticket_id, kind=kind, path=CHECKLIST_FIXTURE_DIR / f"{kind}.md")
    return ticket_id


def _register_evidence(conn, ticket_id: int, tmp_path: Path) -> int:
    path = tmp_path / f"evidence-{ticket_id}.md"
    path.write_text("manual review notes\n")
    return artefact_registry.register(conn, ticket_id=ticket_id, kind="check_evidence", path=path)


def _plan_candidate_blind_spot(conn, tmp_path):
    """A ticket with a planned reviewer set and a current plan tuple already in place (via
    `approve_current_plan`), then an `R-S1-3:grader` `blind_spot` verdict recorded over it, with
    no waiver yet."""
    ticket_id = _ticket(conn, tmp_path)
    approve_current_plan(conn, ticket_id)
    ticket = record.get(conn, "ticket", ticket_id)
    instances = checklist.expected_instances(conn, ticket, rubric_paths=OK_RUBRIC_PATHS)
    instance = next(i for i in instances if i.rubric_line_id == "R-S1-3:grader")
    item_id = queue.open_item(conn, ticket_id=ticket_id, kind="plan_approval", stage="S3")
    item = record.get(conn, "queue_item", item_id)
    verdict_id = checklist.record_verdict(
        conn, ticket=ticket, item=item, instance=instance, verdict="blind_spot",
        evidence_ids=[], waiver_id=None, reviewer_identity=ABHISHEK, reviewer_role="s3_reviewer",
        note="brief names no owner", rubric_paths=OK_RUBRIC_PATHS,
    )
    return ticket_id, instance, verdict_id


def _review_tuple_setup(conn, tmp_path, *, extra_results=()):
    """A ticket with an S5 `stage_run`, a review `evidence_tuple`, one `behavior_contract_evidence`
    blind spot bound to it, any `extra_results` (`(check_name, result)` pairs) alongside it, and
    the `red_check` item S5 would open for the run."""
    ticket_id = _ticket(conn, tmp_path)
    stage_run_id = record.insert(conn, "stage_run", ticket_id=ticket_id, stage="S5")
    review_tuple_id = record.insert(
        conn, "evidence_tuple", kind="review", ticket_id=ticket_id,
        content_hash=f"review-tuple-{stage_run_id}", created_at=record.now(),
    )
    check_result_id = record.insert(
        conn, "check_result", stage_run_id=stage_run_id, check_name="behavior_contract_evidence",
        check_tier="blocking", evidence_tuple_id=review_tuple_id, result="blind_spot",
        summary="missing generated-API contract evidence", content_hash=f"cr-{stage_run_id}-bce",
    )
    for index, (name, result) in enumerate(extra_results):
        record.insert(
            conn, "check_result", stage_run_id=stage_run_id, check_name=name, check_tier="blocking",
            evidence_tuple_id=review_tuple_id, result=result, summary=f"{name}: {result}",
            content_hash=f"cr-{stage_run_id}-{index}",
        )
    item_id = queue.open_item(conn, ticket_id=ticket_id, kind="red_check", stage="S5", ref=f"stage_run:{stage_run_id}")
    return ticket_id, stage_run_id, check_result_id, item_id


def issue_review_waiver(conn, tmp_path, *, expires_at: str | None = None) -> dict[str, int]:
    """A ticket whose S5 run's one blind spot is covered by a freshly issued review-tuple waiver.

    Shared with the tag tests: a waiver only `waivers.issue` wrote is the one
    kind `waivers.validity` accepts, so no test seeds a bare `waiver` row and
    calls it valid.
    """
    ticket_id, stage_run_id, check_result_id, item_id = _review_tuple_setup(conn, tmp_path)
    evidence_id = _register_evidence(conn, ticket_id, tmp_path)
    waiver_id = waivers.issue(
        conn, ticket_id=ticket_id, policy_id=REVIEW_POLICY_ID, check_result_id=check_result_id,
        actor=ABHISHEK, reason="known generated-API gap, reviewed by hand",
        scope=f"ticket {ticket_id}: behavior_contract_evidence", compensating_controls="manual diff review",
        evidence_ids=[evidence_id], expires_at=expires_at or _soon(),
    )
    return {
        "ticket_id": ticket_id, "stage_run_id": stage_run_id, "check_result_id": check_result_id,
        "item_id": item_id, "waiver_id": waiver_id,
    }


def _owners_yaml(tmp_path: Path, *, identity: str, role: str) -> Path:
    """A copy of the default `owners.yaml` roles with one `role` reassigned to `identity`."""
    default = owners.load_owners()
    roles = {name: dict(entry) for name, entry in default.roles.items()}
    roles[role] = {"identity": identity, "responsibilities": roles[role]["responsibilities"]}
    path = tmp_path / "owners.yaml"
    path.write_text(yaml.safe_dump({"roles": roles, "shared_identities": []}))
    return path


def test_a_plan_candidate_waiver_permits_the_verdict_and_enters_the_plan_tuple(tmp_path):
    """R-S5-13: an authorised plan-candidate waiver over a `blind_spot` verdict lets the
    checklist count it complete, and enters the plan tuple's own `plan_waiver_set_hash`."""
    conn = _conn(tmp_path)
    ticket_id, instance, verdict_id = _plan_candidate_blind_spot(conn, tmp_path)
    ticket = record.get(conn, "ticket", ticket_id)
    assert checklist.completeness(conn, ticket, [instance]).unwaived_blind_spots == (instance,)

    waiver_id = waivers.issue(
        conn, ticket_id=ticket_id, policy_id=PLAN_POLICY_ID, human_verdict_id=verdict_id,
        actor=ABHISHEK, reason="owner mismatch is understood and accepted",
        scope=f"ticket {ticket_id}: {instance.rubric_line_id}", compensating_controls="factory owner reviewed the brief by hand",
        evidence_ids=[artefact_registry.latest(conn, ticket_id, "plan")["id"]], expires_at=_soon(),
    )

    status = checklist.completeness(conn, ticket, [instance])
    assert status.complete
    assert status.unwaived_blind_spots == ()

    tuple_id = plan_tuple.ensure_current(conn, ticket)
    tuple_row = record.get(conn, "evidence_tuple", tuple_id)
    waiver_set = checklist.waiver_set(conn, ticket_id)
    assert any(row["id"] == waiver_id for row in waiver_set)
    assert tuple_row["plan_waiver_set_hash"] == binding.set_hash(waiver_set)


def test_a_fail_verdict_is_never_waivable(tmp_path):
    """must-reject: a `fail` is a defect, not an epistemic gap, and `issue` says so."""
    conn = _conn(tmp_path)
    ticket_id = _ticket(conn, tmp_path)
    ticket = record.get(conn, "ticket", ticket_id)
    instances = checklist.expected_instances(conn, ticket, rubric_paths=OK_RUBRIC_PATHS)
    instance = next(i for i in instances if i.rubric_line_id == "R-S1-3:grader")
    item_id = queue.open_item(conn, ticket_id=ticket_id, kind="plan_approval", stage="S3")
    item = record.get(conn, "queue_item", item_id)
    verdict_id = checklist.record_verdict(
        conn, ticket=ticket, item=item, instance=instance, verdict="fail",
        evidence_ids=[artefact_registry.latest(conn, ticket_id, "plan")["id"]], waiver_id=None,
        reviewer_identity=ABHISHEK, reviewer_role="s3_reviewer", note="wrong owner named",
        rubric_paths=OK_RUBRIC_PATHS,
    )
    with pytest.raises(waivers.WaiverRefused, match="fail"):
        waivers.issue(
            conn, ticket_id=ticket_id, policy_id=PLAN_POLICY_ID, human_verdict_id=verdict_id,
            actor=ABHISHEK, reason="x", scope="x", compensating_controls="x",
            evidence_ids=[artefact_registry.latest(conn, ticket_id, "plan")["id"]], expires_at=_soon(),
        )


def test_a_review_tuple_waiver_clears_the_run_and_resolves_the_shared_red_check_item(tmp_path):
    """R-S5-13: waiving the run's only blind spot turns its `blocking_status` entry
    `waived`, clears the run, and resolves the `red_check` item S5's own failures opened."""
    conn = _conn(tmp_path)
    ticket_id, stage_run_id, check_result_id, item_id = _review_tuple_setup(conn, tmp_path)
    evidence_id = _register_evidence(conn, ticket_id, tmp_path)

    waiver_id = waivers.issue(
        conn, ticket_id=ticket_id, policy_id=REVIEW_POLICY_ID, check_result_id=check_result_id,
        actor=ABHISHEK, reason="known generated-API gap, reviewed by hand",
        scope=f"ticket {ticket_id}: behavior_contract_evidence", compensating_controls="manual diff review",
        evidence_ids=[evidence_id], expires_at=_soon(),
    )

    entry = next(e for e in waivers.blocking_status(conn, stage_run_id) if e["id"] == check_result_id)
    assert entry["status"] == "waived"
    assert entry["waiver_id"] == waiver_id
    assert waivers.cleared(conn, stage_run_id)

    item = record.get(conn, "queue_item", item_id)
    assert item["resolved_at"] is not None
    assert item["action"] == "waived"
    assert item["resolved_by"] == ABHISHEK


def test_a_review_tuple_waiver_leaves_the_shared_red_check_item_open_while_a_fail_remains(tmp_path):
    """R-S5-13: a `fail` alongside the waived blind spot keeps the run uncleared and the item open."""
    conn = _conn(tmp_path)
    ticket_id, stage_run_id, check_result_id, item_id = _review_tuple_setup(
        conn, tmp_path, extra_results=[("size_gate", "fail")],
    )
    evidence_id = _register_evidence(conn, ticket_id, tmp_path)

    waivers.issue(
        conn, ticket_id=ticket_id, policy_id=REVIEW_POLICY_ID, check_result_id=check_result_id,
        actor=ABHISHEK, reason="known generated-API gap, reviewed by hand",
        scope=f"ticket {ticket_id}: behavior_contract_evidence", compensating_controls="manual diff review",
        evidence_ids=[evidence_id], expires_at=_soon(),
    )

    assert not waivers.cleared(conn, stage_run_id)
    item = record.get(conn, "queue_item", item_id)
    assert item["resolved_at"] is None


def test_a_human_action_cannot_resolve_a_red_check_item_as_waived(tmp_path):
    """must-reject: `waived` is not one of `red_check`'s `ACTIONS`, so a human can never reach it through `act`."""
    conn = _conn(tmp_path)
    ticket_id, stage_run_id, check_result_id, item_id = _review_tuple_setup(conn, tmp_path)
    with pytest.raises(queue.ActionRefused):
        queue.act(conn, item_id=item_id, action="waived", actor=ABHISHEK)


def test_an_actor_whose_role_the_policy_does_not_authorise_is_refused(tmp_path):
    """R-S5-13: an actor holding no role the policy lists is refused."""
    conn = _conn(tmp_path)
    ticket_id, stage_run_id, check_result_id, item_id = _review_tuple_setup(conn, tmp_path)
    evidence_id = _register_evidence(conn, ticket_id, tmp_path)
    # "camille" holds only `ticket_engineer`, which neither this policy's
    # `s6_reviewer` nor `factory_owner` role names.
    unauthorised_owners = _owners_yaml(tmp_path, identity="camille", role="ticket_engineer")

    with pytest.raises(waivers.WaiverRefused, match="role"):
        waivers.issue(
            conn, ticket_id=ticket_id, policy_id=REVIEW_POLICY_ID, check_result_id=check_result_id,
            actor="camille", reason="x", scope="x", compensating_controls="x",
            evidence_ids=[evidence_id], expires_at=_soon(), owners_path=unauthorised_owners,
        )


def test_a_waiver_records_the_exact_policy_id_version_and_hash(tmp_path):
    """R-S5-13."""
    conn = _conn(tmp_path)
    ticket_id, stage_run_id, check_result_id, item_id = _review_tuple_setup(conn, tmp_path)
    evidence_id = _register_evidence(conn, ticket_id, tmp_path)

    waiver_id = waivers.issue(
        conn, ticket_id=ticket_id, policy_id=REVIEW_POLICY_ID, check_result_id=check_result_id,
        actor=ABHISHEK, reason="x", scope="x", compensating_controls="x",
        evidence_ids=[evidence_id], expires_at=_soon(),
    )

    row = record.get(conn, "waiver", waiver_id)
    policy = waivers.load_policy()
    entry = policy.entry(REVIEW_POLICY_ID)
    assert row["policy_id"] == entry.id
    assert row["policy_version"] == entry.version
    assert row["policy_hash"] == policy.policy_hash


def test_an_expired_waiver_no_longer_permits_advancement(tmp_path):
    """R-S5-13: a waiver past its mandatory expiry no longer covers its result.

    `issue` itself refuses an expiry that is not after the issuing time, so
    this seeds the row directly the way the record would hold one that has
    since aged past its own `expires_at`.
    """
    conn = _conn(tmp_path)
    ticket_id, stage_run_id, check_result_id, item_id = _review_tuple_setup(conn, tmp_path)
    subj = waivers.subject_hash(conn, check_result=record.get(conn, "check_result", check_result_id))
    waiver_id = record.insert(
        conn, "waiver", ticket_id=ticket_id, policy_id=REVIEW_POLICY_ID, policy_version="1",
        policy_hash=waivers.load_policy().policy_hash, waived_check_result_id=check_result_id,
        subject_kind="review_tuple", subject_hash=subj, actor_identity=ABHISHEK, actor_role="s6_reviewer",
        reason="x", scope="x", compensating_controls="x", evidence_ids="[]", evidence_hashes="[]",
        issued_at="2000-01-01T00:00:00+00:00", expires_at="2000-02-01T00:00:00+00:00",
    )
    result = waivers.validity(conn, waiver_id)
    assert not result.valid
    assert "expired" in result.reasons
    assert not waivers.cleared(conn, stage_run_id)


def test_a_waiver_with_no_compensating_controls_is_refused(tmp_path):
    """must-reject: R-S5-13."""
    conn = _conn(tmp_path)
    ticket_id, stage_run_id, check_result_id, item_id = _review_tuple_setup(conn, tmp_path)
    evidence_id = _register_evidence(conn, ticket_id, tmp_path)
    with pytest.raises(waivers.WaiverRefused, match="compensating controls"):
        waivers.issue(
            conn, ticket_id=ticket_id, policy_id=REVIEW_POLICY_ID, check_result_id=check_result_id,
            actor=ABHISHEK, reason="x", scope="x", compensating_controls="",
            evidence_ids=[evidence_id], expires_at=_soon(),
        )


def test_a_waiver_with_no_evidence_is_refused(tmp_path):
    """must-reject: R-S5-13."""
    conn = _conn(tmp_path)
    ticket_id, stage_run_id, check_result_id, item_id = _review_tuple_setup(conn, tmp_path)
    with pytest.raises(waivers.WaiverRefused, match="evidence"):
        waivers.issue(
            conn, ticket_id=ticket_id, policy_id=REVIEW_POLICY_ID, check_result_id=check_result_id,
            actor=ABHISHEK, reason="x", scope="x", compensating_controls="x",
            evidence_ids=[], expires_at=_soon(),
        )


@pytest.mark.skipif(not PACKET_ASSEMBLE.exists(), reason="packet_assemble is built by a parallel ticket")
def test_a_review_tuple_waiver_appears_in_the_packets_evidence_table(tmp_path):
    """R-S5-13: the packet's evidence table names the waiver's id, exact scope, and expiry."""
    conn = _conn(tmp_path)
    ticket_id, stage_run_id, check_result_id, item_id = _review_tuple_setup(conn, tmp_path)
    evidence_id = _register_evidence(conn, ticket_id, tmp_path)
    expires_at = _soon()
    scope = f"ticket {ticket_id}: behavior_contract_evidence"

    waiver_id = waivers.issue(
        conn, ticket_id=ticket_id, policy_id=REVIEW_POLICY_ID, check_result_id=check_result_id,
        actor=ABHISHEK, reason="known generated-API gap, reviewed by hand",
        scope=scope, compensating_controls="manual diff review",
        evidence_ids=[evidence_id], expires_at=expires_at,
    )
    waiver_row = record.get(conn, "waiver", waiver_id)

    diff_path = tmp_path / "diff.patch"
    diff_path.write_text("")
    inputs = {
        "ticket": {"id": ticket_id, "title": "t", "service": "svc", "ticket_type": "feature", "tier": "standard"},
        "identity": {
            "review_tuple_id": None, "review_tuple_hash": "review-tuple-1", "plan_tuple_id": None,
            "plan_tuple_hash": None, "base_sha": "base-1", "head_sha": "head-1", "target_base_sha": "base-1",
            "manifest_hash": "manifest-1", "diff_hash": "diff-1", "deviation_set_hash": "dev-1",
            "effective_reviewer_set_hash": "eff-1",
        },
        "freshness": {"fresh": True, "boundary": "before_dispatch", "target_head_sha": "base-1", "checked_at": record.now(), "reasons": []},
        "artefacts": {},
        "checks": [],
        "fix_rounds": [],
        "base_test_changes": [],
        "readiness": [],
        "approvals": [],
        "waivers": [{
            "id": waiver_id, "policy_id": waiver_row["policy_id"], "policy_version": waiver_row["policy_version"],
            "subject_kind": waiver_row["subject_kind"], "scope": waiver_row["scope"], "expires_at": waiver_row["expires_at"],
            "waived_check_result_id": waiver_row["waived_check_result_id"], "waived_human_verdict_id": waiver_row["waived_human_verdict_id"],
            "content_hash": waiver_row["content_hash"],
        }],
        "deviations": [],
        "assumptions": [],
        "blind_spots": [],
        "test_summary": {"strategy_rows": [], "diff_test_files": []},
        "plan_sections": {
            "intent": "", "scrutiny": "", "alternatives": [], "contracts_changed": [], "non_goals": [],
            "scope_rows": [], "risk_map": [], "checklist_verdicts": [],
        },
        "diff_path": str(diff_path),
    }
    inputs_path = tmp_path / "packet_inputs.json"
    inputs_path.write_text(json.dumps(inputs))
    out_path = tmp_path / "packet.md"

    result = subprocess.run(
        [sys.executable, str(PACKET_ASSEMBLE), "--inputs", str(inputs_path), "--out", str(out_path)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    text = out_path.read_text()
    assert f"waiver {waiver_id}" in text
    assert f"policy {waiver_row['policy_id']}@{waiver_row['policy_version']}" in text
    assert f"scope: {scope}" in text
    assert f"expires: {expires_at}" in text


def test_a_review_tuple_waiver_blocks_once_a_fresh_review_tuple_supersedes_it(tmp_path):
    """R-S5-13: a fresh review tuple (a later fix round's preflight) changes the
    subject an S5 waiver bound; its own recomputed subject hash no longer matches the one it
    was issued against, and it blocks."""
    conn = _conn(tmp_path)
    ticket_id, stage_run_id, check_result_id, item_id = _review_tuple_setup(conn, tmp_path)
    evidence_id = _register_evidence(conn, ticket_id, tmp_path)
    waiver_id = waivers.issue(
        conn, ticket_id=ticket_id, policy_id=REVIEW_POLICY_ID, check_result_id=check_result_id,
        actor=ABHISHEK, reason="x", scope="x", compensating_controls="x",
        evidence_ids=[evidence_id], expires_at=_soon(),
    )
    assert waivers.validity(conn, waiver_id).valid

    record.insert(
        conn, "evidence_tuple", kind="review", ticket_id=ticket_id,
        content_hash="review-tuple-fresh", created_at=record.now(),
    )

    result = waivers.validity(conn, waiver_id)
    assert not result.valid
    assert "subject_changed" in result.reasons


def test_recheck_finds_every_currently_bound_plan_and_review_waiver(tmp_path):
    """R-S5-13: `recheck` enumerates the plan-candidate waiver bound through the
    checklist and the review-tuple waiver bound through the S5 run's check results, in one call."""
    conn = _conn(tmp_path)
    plan_ticket_id, instance, verdict_id = _plan_candidate_blind_spot(conn, tmp_path)
    plan_waiver_id = waivers.issue(
        conn, ticket_id=plan_ticket_id, policy_id=PLAN_POLICY_ID, human_verdict_id=verdict_id,
        actor=ABHISHEK, reason="x", scope="x", compensating_controls="x",
        evidence_ids=[artefact_registry.latest(conn, plan_ticket_id, "plan")["id"]], expires_at=_soon(),
    )
    plan_results = waivers.recheck(conn, plan_ticket_id)
    assert plan_waiver_id in plan_results
    assert plan_results[plan_waiver_id].valid

    ticket_id, stage_run_id, check_result_id, item_id = _review_tuple_setup(conn, tmp_path)
    evidence_id = _register_evidence(conn, ticket_id, tmp_path)
    review_waiver_id = waivers.issue(
        conn, ticket_id=ticket_id, policy_id=REVIEW_POLICY_ID, check_result_id=check_result_id,
        actor=ABHISHEK, reason="x", scope="x", compensating_controls="x",
        evidence_ids=[evidence_id], expires_at=_soon(),
    )
    review_results = waivers.recheck(conn, ticket_id)
    assert review_waiver_id in review_results
    assert review_results[review_waiver_id].valid


def test_recheck_blocks_on_changed_evidence(tmp_path):
    """R-S5-13: an evidence artefact whose recorded hash no longer matches blocks."""
    conn = _conn(tmp_path)
    ticket_id, stage_run_id, check_result_id, item_id = _review_tuple_setup(conn, tmp_path)
    evidence_id = _register_evidence(conn, ticket_id, tmp_path)
    subj = waivers.subject_hash(conn, check_result=record.get(conn, "check_result", check_result_id))
    policy = waivers.load_policy()
    waiver_id = record.insert(
        conn, "waiver", ticket_id=ticket_id, policy_id=REVIEW_POLICY_ID, policy_version="1",
        policy_hash=policy.policy_hash, waived_check_result_id=check_result_id,
        subject_kind="review_tuple", subject_hash=subj, actor_identity=ABHISHEK, actor_role="s6_reviewer",
        reason="x", scope="x", compensating_controls="x",
        evidence_ids=json.dumps([evidence_id]), evidence_hashes=json.dumps(["deliberately-wrong-hash"]),
        issued_at=record.now(), expires_at=_soon(),
    )
    result = waivers.validity(conn, waiver_id)
    assert not result.valid
    assert "evidence_changed" in result.reasons


def test_recheck_blocks_on_lost_authority(tmp_path):
    """R-S5-13: an actor who no longer holds the authorising role blocks at recheck,
    even though the waiver was validly issued while they held it."""
    conn = _conn(tmp_path)
    ticket_id, stage_run_id, check_result_id, item_id = _review_tuple_setup(conn, tmp_path)
    evidence_id = _register_evidence(conn, ticket_id, tmp_path)
    waiver_id = waivers.issue(
        conn, ticket_id=ticket_id, policy_id=REVIEW_POLICY_ID, check_result_id=check_result_id,
        actor=ABHISHEK, reason="x", scope="x", compensating_controls="x",
        evidence_ids=[evidence_id], expires_at=_soon(),
    )
    row = record.get(conn, "waiver", waiver_id)
    demoted_owners = _owners_yaml(tmp_path, identity="someone-else", role=row["actor_role"])

    result = waivers.validity(conn, waiver_id, owners_path=demoted_owners)
    assert not result.valid
    assert "lost_authority" in result.reasons


def test_a_policy_exception_tag_alone_grants_no_authority(tmp_path):
    """R-S5-13: the `policy_exception` tag issued with a waiver outlives the waiver's own
    validity, and `cleared` follows the waiver, never the tag."""
    conn = _conn(tmp_path)
    refs = issue_review_waiver(conn, tmp_path)
    after_expiry = (datetime.now(UTC) + timedelta(days=2)).isoformat(timespec="seconds")

    tag_rows = conn.execute(
        "SELECT * FROM tag WHERE event_kind = 'policy_exception' AND ref = ?", (f"waiver:{refs['waiver_id']}",)
    ).fetchall()
    assert len(tag_rows) == 1
    assert waivers.cleared(conn, refs["stage_run_id"])
    assert not waivers.cleared(conn, refs["stage_run_id"], now=after_expiry)
    entry = next(e for e in waivers.blocking_status(conn, refs["stage_run_id"], now=after_expiry) if e["id"] == refs["check_result_id"])
    assert entry["status"] == "blind_spot"


@pytest.mark.parametrize("fixture_path", NEVER_WAIVABLE_FIXTURES, ids=lambda p: p.stem)
def test_a_never_waivable_condition_is_refused_regardless_of_policy(tmp_path, fixture_path):
    """must-reject: R-S5-13 -- every check name `waiver-policy.yaml` names as
    never-waivable is refused by name, before any policy is even consulted."""
    check_name = yaml.safe_load(fixture_path.read_text())["check_name"]
    conn = _conn(tmp_path)
    ticket_id = _ticket(conn, tmp_path)
    stage_run_id = record.insert(conn, "stage_run", ticket_id=ticket_id, stage="S5")
    review_tuple_id = record.insert(
        conn, "evidence_tuple", kind="review", ticket_id=ticket_id,
        content_hash=f"review-{stage_run_id}", created_at=record.now(),
    )
    check_result_id = record.insert(
        conn, "check_result", stage_run_id=stage_run_id, check_name=check_name, check_tier="blocking",
        evidence_tuple_id=review_tuple_id, result="blind_spot", summary=f"{check_name} gap",
        content_hash=f"cr-{stage_run_id}",
    )
    evidence_id = _register_evidence(conn, ticket_id, tmp_path)

    with pytest.raises(waivers.WaiverRefused, match="never waivable"):
        waivers.issue(
            conn, ticket_id=ticket_id, policy_id=REVIEW_POLICY_ID, check_result_id=check_result_id,
            actor=ABHISHEK, reason="x", scope="x", compensating_controls="x",
            evidence_ids=[evidence_id], expires_at=_soon(),
        )
