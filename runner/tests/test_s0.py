"""S0 for real: lookups, provisional tier, sensitive paths, scrutiny, eligibility, exclusion.

`_governed_ticket_fields` gives a ticket a real, currently active
governance state -- the trust-profile and approval-set hashes S0's own
`governance_valid` checks -- through the committed trust profile and
owners file, the same default-path activation `test_outbox.py`'s
reconcile-first test uses (`governance.propose()`/`decide()` with no
override paths).
"""
import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from runner import artefact_registry, credentials, gates, governance, manifest, queue, record, run_ledger, transitions
from runner.db import connect
from runner.readers import atlassian
from runner.reviewer_sets import Slot
from runner.stages import S0
from runner.stages import run_stage
from runner.tests.fakes.atlassian_transport import FakeAtlassianTransport

ABHISHEK = "abhishek"
FAR_FUTURE = "2999-01-01T00:00:00+00:00"

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "s0"


@pytest.fixture
def conn(tmp_path):
    connection = connect(tmp_path / "factory.sqlite")
    yield connection
    connection.close()


def _governed_ticket_fields(conn, *, expires_at: str = FAR_FUTURE) -> dict:
    """Ticket fields that satisfy `S0.governance_valid` against the committed trust profile and owners file."""
    proposal = governance.propose()
    for role in ("security_approver", "legal_data_governance_approver"):
        governance.decide(
            conn, proposal, actor_identity=ABHISHEK, role=role, decision="approve",
            expires_at=expires_at, attestation_version="v1", attestation_hash=f"att-{role}",
        )
    activated = governance.activation(conn, proposal)
    return {
        "trust_profile_hash": proposal.profile_hash,
        "trust_approval_set_hash": activated.trust_approval_set_hash,
        "service": "fixture-project",
        "source_kind": "jira",
        "source_ref": "FIX-1",
    }


def _seed_ticket_source(conn, ticket_id: int, tmp_path: Path, **front_matter_overrides) -> int:
    """A `ticket_source` artefact that already clears the intake field gate, so `S0.run` skips the Jira read.

    Every `_governed_ticket_fields` ticket carries `source_kind: "jira"`
    for the governance-scope checks below, which means `S0.run` now takes
    the Jira intake leg; without a registered source already on file it
    would try a real read against a server this suite never reaches, so
    every test that drives such a ticket through `run_stage`/`S0.run`
    seeds one first.
    """
    front_matter = {
        "jira_issue_type": "Story", "estimate": 2, "label": None, "owner": ABHISHEK,
        "parent_link": "FIX-0", "confluence_link": None,
        "acceptance_criteria": "Given a user opens the export dialog, when they click export, then a file downloads.",
        **front_matter_overrides,
    }
    text = "---\n" + yaml.safe_dump(front_matter, sort_keys=False) + "---\n\nSummary body.\n"
    path = tmp_path / f"ticket_source_{ticket_id}.md"
    path.write_text(text)
    return artefact_registry.register(conn, ticket_id=ticket_id, kind="ticket_source", path=path)


# --- criterion 1: the 15-cell provisional tier matrix (R-S0-2) ---

_MATRIX_CASES = [
    ("T1", "bug", "heavy"), ("T1", "small_feature", "heavy"), ("T1", "feature", "heavy"),
    ("T1", "refactor", "heavy"), ("T1", "config_or_docs", "standard"),
    ("T2", "bug", "standard"), ("T2", "small_feature", "standard"), ("T2", "feature", "heavy"),
    ("T2", "refactor", "standard"), ("T2", "config_or_docs", "light"),
    ("T3", "bug", "light"), ("T3", "small_feature", "light"), ("T3", "feature", "standard"),
    ("T3", "refactor", "standard"), ("T3", "config_or_docs", "light"),
]


@pytest.mark.parametrize("service_tier, ticket_type, expected_tier", _MATRIX_CASES)
def test_provisional_tier_matrix_cell(conn, service_tier, ticket_type, expected_tier):
    """R-S0-2: each of the 15 service_tier/ticket_type cells yields the matching provisional tier."""
    ticket_id = record.insert(conn, "ticket", state="intake", opened_at=record.now(), service="svc", ticket_type=ticket_type)
    ticket = record.get(conn, "ticket", ticket_id)
    service_tiers = {"svc": {"tier": service_tier, "language": "java", "repositories": ["svc"]}}
    _, _, tier_provisional = S0._lookup(
        conn, ticket, service_tiers=service_tiers, ticket_types=S0.load_ticket_types(), prior_source_artefact=None,
    )
    assert tier_provisional == expected_tier


# --- criterion 2: a service absent from service-tiers.yaml, and an Epic issue type (R-S0-2) ---

def test_must_reject_lookup_for_a_service_absent_from_service_tiers(conn):
    ticket_id = record.insert(
        conn, "ticket", state="intake", opened_at=record.now(), service="not-a-real-service", ticket_type="bug",
    )
    ticket = record.get(conn, "ticket", ticket_id)
    with pytest.raises(S0.S0LookupRefused, match="service not tiered"):
        S0._lookup(
            conn, ticket, service_tiers=S0.load_service_tiers(), ticket_types=S0.load_ticket_types(),
            prior_source_artefact=None,
        )


def test_must_reject_lookup_for_an_epic_jira_issue_type(conn, tmp_path):
    ticket_id = record.insert(conn, "ticket", state="intake", opened_at=record.now(), service="fixture-project")
    source_path = tmp_path / "ticket_source.md"
    source_path.write_text("---\njira_issue_type: Epic\n---\nbody\n")
    artefact_id = artefact_registry.register(conn, ticket_id=ticket_id, kind="ticket_source", path=source_path)
    artefact = record.get(conn, "artefact", artefact_id)
    ticket = record.get(conn, "ticket", ticket_id)
    with pytest.raises(S0.S0LookupRefused, match="needs child tickets"):
        S0._lookup(
            conn, ticket, service_tiers=S0.load_service_tiers(), ticket_types=S0.load_ticket_types(),
            prior_source_artefact=artefact,
        )


def test_must_reject_a_lookup_failure_through_run_stage_rejects_the_ticket(conn, tmp_path):
    """the absent-service case, run through the full driver: `s0_reject` fires with a structural failure_kind."""
    ticket_id = record.insert(
        conn, "ticket", state="intake", opened_at=record.now(), service="not-a-real-service", ticket_type="bug",
    )
    outcome = run_stage(conn, ticket_id, "S0", runs_dir=tmp_path)
    assert outcome == "fail"
    stage_run = conn.execute(
        "SELECT failure_kind FROM stage_run WHERE ticket_id = ? AND stage = 'S0'", (ticket_id,)
    ).fetchone()
    assert stage_run["failure_kind"] == "structural"
    ticket = record.get(conn, "ticket", ticket_id)
    assert ticket["state"] == "rejected"
    assert ticket["close_reason"] == "rejected_at_s0"


# --- criteria 3 and 5: a sensitive-path candidate raises tier_final and R-S0-8 excludes it (R-S0-5) ---

def test_sensitive_path_candidate_raises_tier_final_to_heavy_and_excludes_the_ticket(conn, tmp_path):
    ticket_id = record.insert(
        conn, "ticket", state="intake", opened_at=record.now(),
        title="Rework src/main/java/com/fixture/auth/LoginController.java",
        service="fixture-project", ticket_type="small_feature",
    )
    outcome = run_stage(conn, ticket_id, "S0", runs_dir=tmp_path)
    assert outcome == "fail"
    ticket = record.get(conn, "ticket", ticket_id)
    assert ticket["tier_final"] == "heavy"
    assert ticket["state"] == "rejected"
    assert ticket["close_reason"] == "pilot_excluded"


# --- criterion 4: an authoritative match over an actual diff (R-S0-5) ---

def test_authoritative_sensitivity_match_over_an_actual_diff_confirms_heavy(conn):
    diff_paths = ["src/main/java/com/fixture/payments/ChargeService.java"]
    match = S0.sensitivity_match(diff_paths, authoritative=True)
    assert match is not None
    assert match.authoritative is True
    assert match.glob == "src/main/java/com/fixture/payments/**"
    assert match.owner == "abhishek"


def test_a_provisional_candidate_match_is_not_marked_authoritative(conn):
    candidates = ["src/main/java/com/fixture/auth/Login.java"]
    match = S0.sensitivity_match(candidates, authoritative=False)
    assert match is not None
    assert match.authoritative is False


# --- criterion 6: the path-owner slot's distinct_from rejects the ticket engineer's own identity (R-S0-5) ---

def test_sensitive_path_owner_slot_rejects_the_ticket_engineers_own_identity(conn):
    """the fixture sensitive-paths mapping gives the auth path a different
    owner (`priya`) than the pilot's shared identity, so the negative case
    (same identity approving both slots) has something real to reject."""
    from runner import approvals

    sensitive_paths = {"src/main/java/com/fixture/auth/**": "priya"}
    match = S0.sensitivity_match(
        ["src/main/java/com/fixture/auth/Login.java"], authoritative=False, sensitive_paths=sensitive_paths,
    )
    engineer_slot = Slot(source_rule="trust-profile", role="ticket_engineer")
    owner_slot = Slot(
        source_rule=f"sensitive_paths:{match.glob}", role="sensitive_path_owner", owner=match.owner,
        distinct_from=(engineer_slot.slot_id,),
    )
    slots = [engineer_slot, owner_slot]

    def _approve(actor, slot, subject):
        approvals.record_approval(
            conn, gate="plan", subject_hash=subject, slot_id=slot.slot_id, actor_identity=actor,
            role=slot.role, decision="approve", authority_policy_hash="h", membership_snapshot_hash="m",
            attestation_version="v1", attestation_hash=f"{slot.slot_id}-{actor}",
        )

    _approve("engineer", engineer_slot, "subj-distinct")
    _approve("priya", owner_slot, "subj-distinct")
    conn.commit()
    quorum = approvals.evaluate(conn, gate="plan", subject_hash="subj-distinct", slots=slots)
    assert quorum.satisfied


def test_must_reject_when_the_ticket_engineer_also_holds_the_sensitive_path_owner_slot(conn):
    """the negative case: the same identity fills both slots, so the
    owner slot's `distinct_from` constraint refuses quorum."""
    from runner import approvals

    sensitive_paths = {"src/main/java/com/fixture/auth/**": "priya"}
    match = S0.sensitivity_match(
        ["src/main/java/com/fixture/auth/Login.java"], authoritative=False, sensitive_paths=sensitive_paths,
    )
    engineer_slot = Slot(source_rule="trust-profile", role="ticket_engineer")
    owner_slot = Slot(
        source_rule=f"sensitive_paths:{match.glob}", role="sensitive_path_owner", owner=match.owner,
        distinct_from=(engineer_slot.slot_id,),
    )
    slots = [engineer_slot, owner_slot]

    def _approve(actor, slot, subject):
        approvals.record_approval(
            conn, gate="plan", subject_hash=subject, slot_id=slot.slot_id, actor_identity=actor,
            role=slot.role, decision="approve", authority_policy_hash="h", membership_snapshot_hash="m",
            attestation_version="v1", attestation_hash=f"{slot.slot_id}-{actor}",
        )

    _approve("priya", engineer_slot, "subj-same")
    _approve("priya", owner_slot, "subj-same")
    conn.commit()
    quorum = approvals.evaluate(conn, gate="plan", subject_hash="subj-same", slots=slots)
    assert not quorum.satisfied
    assert any(reason.startswith("separation:") for reason in quorum.reasons)


# --- criterion 7: the scrutiny template fill (R-S0-6) ---

def test_scrutiny_template_fill_writes_a_nonempty_paragraph_naming_type_tier_and_match(conn, tmp_path):
    ticket_id = record.insert(
        conn, "ticket", state="intake", opened_at=record.now(), title="Add an export button",
        service="fixture-project", ticket_type="small_feature",
    )
    outcome = run_stage(conn, ticket_id, "S0", runs_dir=tmp_path)
    assert outcome == "pass"
    ticket = record.get(conn, "ticket", ticket_id)
    assert ticket["tier_provisional"] == "standard"
    assert ticket["scrutiny_requested"]
    assert "small_feature" in ticket["scrutiny_requested"]
    assert "standard" in ticket["scrutiny_requested"]
    assert "none" in ticket["scrutiny_requested"]
    item = conn.execute(
        "SELECT * FROM queue_item WHERE ticket_id = ? AND kind = 'eligibility'", (ticket_id,)
    ).fetchone()
    assert item is not None
    assert item["tier"] == "standard"


# --- criterion 8: an empty rendered template holds the ticket at intake (R-S0-6) ---

def test_empty_rendered_scrutiny_leaves_the_ticket_in_intake_with_no_item(conn, tmp_path):
    ticket_id = record.insert(
        conn, "ticket", state="intake", opened_at=record.now(), title="Tweak the copy",
        service="fixture-project", ticket_type="small_feature",
    )
    ticket_types = S0.load_ticket_types()
    ticket_types["types"]["small_feature"]["scrutiny_template"] = ""
    stage_run_id = run_ledger.open_stage_run(conn, ticket_id=ticket_id, stage="S0")
    ticket = record.get(conn, "ticket", ticket_id)

    outcome = S0.run(conn, ticket, stage_run_id, tmp_path, ticket_types=ticket_types)

    assert outcome == "pass"
    ticket = record.get(conn, "ticket", ticket_id)
    assert ticket["state"] == "intake"
    assert ticket["scrutiny_requested"] is None
    count = conn.execute("SELECT COUNT(*) FROM queue_item WHERE ticket_id = ?", (ticket_id,)).fetchone()[0]
    assert count == 0


# --- criterion 9: the eligibility item shows governance state; granted admits (R-S0-7) ---

def test_a_granted_eligibility_decision_moves_intake_to_context(conn, tmp_path):
    fields = _governed_ticket_fields(conn)
    ticket_id = record.insert(
        conn, "ticket", state="intake", opened_at=record.now(), title="Add an export button",
        ticket_type="small_feature", **fields,
    )
    _seed_ticket_source(conn, ticket_id, tmp_path)
    outcome = run_stage(conn, ticket_id, "S0", runs_dir=tmp_path)
    assert outcome == "pass"
    item = conn.execute(
        "SELECT * FROM queue_item WHERE ticket_id = ? AND kind = 'eligibility'", (ticket_id,)
    ).fetchone()
    assert item is not None

    listing = queue.list_queue(conn)
    assert f"trust profile hash: {fields['trust_profile_hash']}" in listing
    assert "satisfying trust approval set" in listing
    assert "planned RACI roles" in listing

    queue.act(conn, item_id=item["id"], action="granted", actor=ABHISHEK, runs_dir=tmp_path)
    ticket = record.get(conn, "ticket", ticket_id)
    assert ticket["state"] == "intake"  # act() alone doesn't move it
    event = gates.intake_gate(conn, ticket)
    assert transitions.apply(conn, ticket_id, event) == "context"


# --- criterion 10: expired, unauthorised, wrong-scope, and invalid-route governance states refuse act (R-S0-7) ---

def test_must_reject_act_when_the_governance_approval_set_has_expired(conn, tmp_path):
    fields = _governed_ticket_fields(conn, expires_at="2000-01-01T00:00:00+00:00")
    ticket_id = record.insert(conn, "ticket", state="intake", opened_at=record.now(), **fields)
    item_id = queue.open_item(conn, ticket_id=ticket_id, kind="eligibility")
    with pytest.raises(queue.ActionRefused):
        queue.act(conn, item_id=item_id, action="granted", actor=ABHISHEK, runs_dir=tmp_path)
    assert record.get(conn, "ticket", ticket_id)["state"] == "intake"


def test_must_reject_act_when_the_trust_profile_hash_is_unauthorised(conn, tmp_path):
    fields = _governed_ticket_fields(conn)
    fields["trust_profile_hash"] = "not-the-real-profile-hash"
    ticket_id = record.insert(conn, "ticket", state="intake", opened_at=record.now(), **fields)
    item_id = queue.open_item(conn, ticket_id=ticket_id, kind="eligibility")
    with pytest.raises(queue.ActionRefused):
        queue.act(conn, item_id=item_id, action="granted", actor=ABHISHEK, runs_dir=tmp_path)
    assert record.get(conn, "ticket", ticket_id)["state"] == "intake"


def test_must_reject_act_when_the_source_ref_is_outside_the_admitted_scope(conn, tmp_path):
    fields = _governed_ticket_fields(conn)
    fields["source_ref"] = "OTHER-9"
    ticket_id = record.insert(conn, "ticket", state="intake", opened_at=record.now(), **fields)
    item_id = queue.open_item(conn, ticket_id=ticket_id, kind="eligibility")
    with pytest.raises(queue.ActionRefused):
        queue.act(conn, item_id=item_id, action="granted", actor=ABHISHEK, runs_dir=tmp_path)
    assert record.get(conn, "ticket", ticket_id)["state"] == "intake"


def test_must_reject_governance_validity_when_the_trust_profile_fails_to_load(conn, tmp_path):
    """the invalid-route case: a broken profile file fails to load, so
    `governance_valid` refuses rather than raising."""
    broken_path = tmp_path / "trust-profile.yaml"
    broken_path.write_text("both_trust_roles_identity: abhishek\n")
    ticket_id = record.insert(conn, "ticket", state="intake", opened_at=record.now())
    ticket = record.get(conn, "ticket", ticket_id)
    reasons = S0.governance_valid(conn, ticket, profile_path=broken_path)
    assert "invalid route" in reasons


# --- criterion 11: the acting role is recorded (R-S0-7) ---

def test_resolved_role_records_the_deciding_identitys_role(conn, tmp_path):
    owners_path = FIXTURES_DIR / "owners_engineer2.yaml"
    fields = _governed_ticket_fields(conn)
    ticket_id = record.insert(
        conn, "ticket", state="intake", opened_at=record.now(), title="Add an export button",
        ticket_type="small_feature", **fields,
    )
    _seed_ticket_source(conn, ticket_id, tmp_path)
    run_stage(conn, ticket_id, "S0", runs_dir=tmp_path)
    item = conn.execute(
        "SELECT * FROM queue_item WHERE ticket_id = ? AND kind = 'eligibility'", (ticket_id,)
    ).fetchone()

    queue.act(conn, item_id=item["id"], action="granted", actor="engineer2", owners_path=owners_path, runs_dir=tmp_path)

    resolved = record.get(conn, "queue_item", item["id"])
    assert resolved["resolved_by"] == "engineer2"
    assert resolved["resolved_role"] == "ticket_engineer"


# --- criterion 12: override writes the tier and its provenance (R-S0-7) ---

def test_override_writes_tier_final_and_override_provenance_and_tag(conn, tmp_path):
    fields = _governed_ticket_fields(conn)
    ticket_id = record.insert(
        conn, "ticket", state="intake", opened_at=record.now(), title="Add an export button",
        ticket_type="small_feature", **fields,
    )
    _seed_ticket_source(conn, ticket_id, tmp_path)
    run_stage(conn, ticket_id, "S0", runs_dir=tmp_path)
    item = conn.execute(
        "SELECT * FROM queue_item WHERE ticket_id = ? AND kind = 'eligibility'", (ticket_id,)
    ).fetchone()

    queue.act(
        conn, item_id=item["id"], action="override", actor=ABHISHEK, tier="heavy",
        fm_id="FM-05", note="raise for safety", runs_dir=tmp_path,
    )

    ticket = record.get(conn, "ticket", ticket_id)
    assert ticket["tier_final"] == "heavy"
    assert ticket["tier_override_by"] == ABHISHEK
    assert ticket["tier_override_reason"] == "raise for safety"
    tag_rows = conn.execute(
        "SELECT * FROM tag WHERE ticket_id = ? AND event_kind = 'override'", (ticket_id,)
    ).fetchall()
    assert len(tag_rows) == 1


# --- criterion 13: override refuses on a ticket S0 already excluded (R-S0-7) ---

def test_must_reject_override_on_a_ticket_s0_excluded(conn, tmp_path):
    fields = _governed_ticket_fields(conn)
    ticket_id = record.insert(
        conn, "ticket", state="intake", opened_at=record.now(),
        title="Rework src/main/java/com/fixture/auth/Login.java",
        ticket_type="small_feature", **fields,
    )
    _seed_ticket_source(conn, ticket_id, tmp_path)
    run_stage(conn, ticket_id, "S0", runs_dir=tmp_path)
    ticket = record.get(conn, "ticket", ticket_id)
    assert ticket["state"] == "rejected"
    assert ticket["close_reason"] == "pilot_excluded"

    item_id = queue.open_item(conn, ticket_id=ticket_id, kind="eligibility")
    with pytest.raises(queue.ActionRefused):
        queue.act(conn, item_id=item_id, action="override", actor=ABHISHEK, tier="heavy", fm_id="FM-05", runs_dir=tmp_path)
    assert record.get(conn, "ticket", ticket_id)["tier_override_by"] is None


# --- Jira intake: a fresh read's field gate, guard redaction, and credential discipline (R-S0-1) ---

def _redaction_fixture_issue() -> dict:
    return yaml.safe_load((FIXTURES_DIR / "redaction_issue.yaml").read_text())


def test_guard_redacts_a_fresh_jira_read_into_a_faithful_ticket_source_and_sets_data_class(conn, tmp_path):
    """the guard classifies and redacts the permitted source fields of a
    freshly read Jira payload into `ticket_source` and sets
    `ticket.data_class`; a field the route does not admit (`reporter`)
    never survives, so the result is faithful to the permitted fields,
    never an unfiltered copy of the Jira payload (R-S0-1)."""
    fields = _governed_ticket_fields(conn)
    ticket_id = record.insert(
        conn, "ticket", state="intake", opened_at=record.now(), title="Add an export button", **fields,
    )
    transport = FakeAtlassianTransport({"FIX-1": _redaction_fixture_issue()})
    stage_run_id = run_ledger.open_stage_run(conn, ticket_id=ticket_id, stage="S0")
    ticket = record.get(conn, "ticket", ticket_id)

    outcome = S0.run(conn, ticket, stage_run_id, tmp_path, transport=transport)

    assert outcome == "pass"
    assert transport.calls == [("read_issue", {"key": "FIX-1"})]
    artefact = artefact_registry.latest(conn, ticket_id, "ticket_source")
    assert artefact is not None
    text = Path(artefact["path"]).read_text()
    assert "someone-else" not in text
    assert "export" in text
    front_matter = S0._ticket_source_front_matter(artefact)
    assert front_matter["owner"] == "abhishek"
    assert front_matter["parent_link"] == "FIX-0"
    ticket = record.get(conn, "ticket", ticket_id)
    assert ticket["data_class"] == "confidential"


_SECRET_TOKEN = "ghp_" + "a" * 36


def test_must_reject_when_the_jira_payload_contains_a_secret(conn, tmp_path):
    """a secret-rule hit denies the guard crossing outright: no
    `ticket_source` is ever written, and the ticket is rejected the same
    way a field-gate failure is (R-S0-1)."""
    fields = _governed_ticket_fields(conn)
    ticket_id = record.insert(
        conn, "ticket", state="intake", opened_at=record.now(), title="Add an export button", **fields,
    )
    issue = {**_redaction_fixture_issue(), "description": f"leaked token {_SECRET_TOKEN}"}
    transport = FakeAtlassianTransport({"FIX-1": issue})
    stage_run_id = run_ledger.open_stage_run(conn, ticket_id=ticket_id, stage="S0")
    ticket = record.get(conn, "ticket", ticket_id)

    outcome = S0.run(conn, ticket, stage_run_id, tmp_path, transport=transport)

    assert outcome == ("fail", "structural")
    check_result = conn.execute(
        "SELECT * FROM check_result WHERE stage_run_id = ? AND check_name = 'ticket_source_guard'", (stage_run_id,)
    ).fetchone()
    assert check_result is not None
    assert check_result["result"] == "fail"
    assert artefact_registry.latest(conn, ticket_id, "ticket_source") is None
    assert record.get(conn, "ticket", ticket_id)["state"] == "rejected"


def test_http_transport_requests_the_credential_inside_the_call_and_never_holds_it():
    """`HttpTransport` fetches the `atlassian_read` credential at the
    moment of the request, not at construction, and never stores it on
    itself afterward (R-S0-1)."""
    calls = []

    def fake_fetch(role):
        calls.append(role)
        return "secret-token-value"

    transport = atlassian.HttpTransport("https://jira.example.invalid", fetch=fake_fetch)
    assert calls == []

    response = MagicMock()
    response.read.return_value = json.dumps({"key": "FIX-1"}).encode()
    response.__enter__.return_value = response
    response.__exit__.return_value = False
    with patch("runner.readers.atlassian.urllib.request.urlopen", return_value=response) as mock_urlopen:
        result = transport("read_issue", {"key": "FIX-1"})

    assert calls == ["atlassian_read"]
    assert result == {"key": "FIX-1"}
    assert "secret-token-value" not in vars(transport).values()
    sent_request = mock_urlopen.call_args[0][0]
    assert sent_request.get_header("Authorization") == "Bearer secret-token-value"


def test_manifest_sandbox_policy_admits_no_credential_role_into_s0():
    """S0 runs no agent, so its sandbox admits no credential role: the
    `atlassian_read` credential is fetched by the trusted runner process
    directly, never mounted into a sandbox (R-S0-1)."""
    assert manifest.load().sandbox_policy["credential_roles"]["S0"] == ()


def test_dry_run_ticket_reads_the_real_atlassian_server_and_pins_governance(conn, tmp_path):
    """on the dry-run ticket, `runner.readers.atlassian` reads the real
    Atlassian server, the `atlassian_read` credential value never
    reaches a row, artefact or check-result summary, and
    `ticket.trust_profile_hash`/`trust_approval_set_hash` are pinned to
    the committed profile's hash and its satisfying approval set (R-S0-1).

    Skipped loudly wherever the pilot's Jira key, Keychain item, or
    sandbox endpoint don't exist on this host -- the owner has confirmed
    none of the three exist yet, so this test always skips today."""
    if not credentials.available("atlassian_read"):
        pytest.skip("no atlassian_read Keychain item on this host: the dry-run ticket cannot reach a real Jira")
    if atlassian.endpoint() is None:
        pytest.skip("sandbox.yaml names no atlassian_read endpoint yet: a later ticket wires the loopback proxy's allowlist")
    dry_run_key = os.environ.get("SOFT_FACTORY_DRY_RUN_JIRA_KEY")
    if not dry_run_key:
        pytest.skip("no dry-run Jira key configured: SOFT_FACTORY_DRY_RUN_JIRA_KEY is unset")

    fields = _governed_ticket_fields(conn)
    fields["source_ref"] = dry_run_key
    ticket_id = record.insert(conn, "ticket", state="intake", opened_at=record.now(), **fields)

    outcome = run_stage(conn, ticket_id, "S0", runs_dir=tmp_path)

    ticket = record.get(conn, "ticket", ticket_id)
    assert ticket["trust_profile_hash"] == fields["trust_profile_hash"]
    assert ticket["trust_approval_set_hash"] == fields["trust_approval_set_hash"]
    if outcome == "pass":
        artefact = artefact_registry.latest(conn, ticket_id, "ticket_source")
        assert artefact is not None
        token = credentials.fetch("atlassian_read")
        assert token not in Path(artefact["path"]).read_text()
        rows = conn.execute(
            "SELECT summary FROM check_result WHERE stage_run_id IN "
            "(SELECT id FROM stage_run WHERE ticket_id = ?)", (ticket_id,),
        ).fetchall()
        assert all(token not in (row["summary"] or "") for row in rows)
