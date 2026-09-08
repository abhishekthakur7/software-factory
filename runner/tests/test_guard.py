"""The governance console and the single guard seat.

Every test that needs an active trust profile builds one through
`governance.propose`/`governance.decide` against a tmp copy of the fixture
profile and owners files, never by inserting `approval_record` rows by
hand -- so a wrong quorum computation in `runner.approvals` would fail
these tests too, not just a hand-written row shape.
"""
import ast
import hashlib
import json
import shutil
from pathlib import Path

import pytest
import yaml

from runner import governance, guard, record
from runner.db import connect
from runner.paths import REPO_ROOT

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "guard"
OPERATIONS = yaml.safe_load((FIXTURES_DIR / "operations.yaml").read_text())
FAR_FUTURE = "2999-01-01T00:00:00+00:00"


@pytest.fixture
def conn(tmp_path):
    connection = connect(tmp_path / "factory.sqlite")
    yield connection
    connection.close()


@pytest.fixture
def profile_paths(tmp_path):
    """A tmp copy of the fixture trust profile and owners file."""
    profile_path = tmp_path / "trust-profile.yaml"
    owners_path = tmp_path / "owners.yaml"
    shutil.copy(FIXTURES_DIR / "trust-profile.yaml", profile_path)
    shutil.copy(FIXTURES_DIR / "owners.yaml", owners_path)
    return profile_path, owners_path


def _activate(conn, profile_path, owners_path, expires_at=FAR_FUTURE):
    """Satisfy the trust profile's quorum through the real governance decisions."""
    proposal = governance.propose(profile_path, owners_path)
    for role in ("security_approver", "legal_data_governance_approver"):
        governance.decide(
            conn, proposal,
            actor_identity="abhishek", role=role, decision="approve",
            expires_at=expires_at, attestation_version="v1", attestation_hash=f"att-{role}",
            owners_path=owners_path, profile_path=profile_path,
        )
    conn.commit()
    return proposal


def _operation(name, **overrides):
    data = dict(OPERATIONS[name])
    data["input_classes"] = tuple(data["input_classes"])
    data.update(overrides)
    return guard.Operation(**data)


# ---------------------------------------------------------------------------
# the governance-only console cannot read, persist, or dispatch
# production content.
# ---------------------------------------------------------------------------

GOVERNANCE_PATH = REPO_ROOT / "runner" / "governance.py"
FORBIDDEN_MODULES = {"runner.guard", "runner.artefact_registry", "runner.fs", "runner.stages"}


def test_governance_console_imports_none_of_the_content_bearing_modules():
    """`propose`/`decide`/`activation` have no way to reach a stage, the
    artefact registry, the filesystem write path, or the guard itself."""
    tree = ast.parse(GOVERNANCE_PATH.read_text(), filename=str(GOVERNANCE_PATH))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert not (imported & FORBIDDEN_MODULES), imported & FORBIDDEN_MODULES


def test_must_reject_a_governance_module_that_calls_insert_directly():
    """every write governance.py makes goes through
    `approvals.record_approval`; a raw `....insert(...)` call anywhere in
    the module would be a second, ungoverned write path."""
    tree = ast.parse(GOVERNANCE_PATH.read_text(), filename=str(GOVERNANCE_PATH))
    direct_inserts = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "insert"
    ]
    assert direct_inserts == []


def test_propose_takes_no_connection_and_no_payload_parameter():
    """`propose` cannot dispatch or persist because it never receives a
    database connection or a payload to act on in the first place."""
    tree = ast.parse(GOVERNANCE_PATH.read_text(), filename=str(GOVERNANCE_PATH))
    propose_def = next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "propose"
    )
    names = {a.arg for a in propose_def.args.args} | {a.arg for a in propose_def.args.kwonlyargs}
    assert "conn" not in names
    assert "payload" not in names


def test_proposal_carries_metadata_only(profile_paths):
    """the object shown to an approver is hashes, identities and route
    ids -- never a field that could hold ticket or repository content."""
    profile_path, owners_path = profile_paths
    proposal = governance.propose(profile_path, owners_path)
    field_names = {f.name for f in __import__("dataclasses").fields(proposal)}
    assert field_names == {
        "profile_hash", "authority_policy_hash", "subject_hash",
        "trust_role_identities", "route_ids", "both_trust_roles_identity",
    }
    assert proposal.trust_role_identities == {
        "security_approver": "abhishek", "legal_data_governance_approver": "abhishek",
    }
    assert set(proposal.route_ids) == {
        "hosted_model", "governed_export_display", "github_pr", "slack_digest", "jira_feedback",
    }


# ---------------------------------------------------------------------------
# no valid class join denies.
# ---------------------------------------------------------------------------

def test_must_reject_operation_whose_input_classes_have_no_valid_join(conn, profile_paths):
    profile_path, owners_path = profile_paths
    _activate(conn, profile_path, owners_path)
    op = _operation("dispatch", input_classes=("internal", "top_secret"))
    decision = guard.decide(conn, op, profile_path=profile_path, owners_path=owners_path)
    assert decision.decision == "deny"
    assert decision.reason_codes == ("no_valid_join",)


# ---------------------------------------------------------------------------
# activation needs the configured slots and separation rule,
# with the both_trust_roles_identity as the one exemption.
# ---------------------------------------------------------------------------

def test_activation_fails_until_both_configured_slots_are_satisfied(conn, profile_paths):
    profile_path, owners_path = profile_paths
    proposal = governance.propose(profile_path, owners_path)

    assert not governance.activation(conn, proposal, profile_path=profile_path).active

    governance.decide(
        conn, proposal, actor_identity="abhishek", role="security_approver", decision="approve",
        expires_at=FAR_FUTURE, attestation_version="v1", attestation_hash="a1",
        owners_path=owners_path, profile_path=profile_path,
    )
    conn.commit()
    assert not governance.activation(conn, proposal, profile_path=profile_path).active


def test_activation_succeeds_only_because_both_trust_roles_identity_permits_the_shared_actor(conn, profile_paths):
    """the fixture owners file names `abhishek` for both trust roles;
    activation succeeds only because the profile's
    `both_trust_roles_identity` names that same identity as the
    separation exemption."""
    profile_path, owners_path = profile_paths
    proposal = governance.propose(profile_path, owners_path)
    assert proposal.both_trust_roles_identity == "abhishek"
    assert proposal.trust_role_identities["security_approver"] == "abhishek"
    assert proposal.trust_role_identities["legal_data_governance_approver"] == "abhishek"

    for role in ("security_approver", "legal_data_governance_approver"):
        governance.decide(
            conn, proposal, actor_identity="abhishek", role=role, decision="approve",
            expires_at=FAR_FUTURE, attestation_version="v1", attestation_hash=role,
            owners_path=owners_path, profile_path=profile_path,
        )
    conn.commit()
    activated = governance.activation(conn, proposal, profile_path=profile_path)
    assert activated.active
    assert activated.trust_approval_set_hash


# ---------------------------------------------------------------------------
# mandatory expiry, and one approval_record row per acting
# approver.
# ---------------------------------------------------------------------------

def test_must_reject_trust_profile_decision_without_an_expiry(conn, profile_paths):
    profile_path, owners_path = profile_paths
    proposal = governance.propose(profile_path, owners_path)
    with pytest.raises(ValueError):
        governance.decide(
            conn, proposal, actor_identity="abhishek", role="security_approver", decision="approve",
            expires_at=None, attestation_version="v1", attestation_hash="h",
            owners_path=owners_path, profile_path=profile_path,
        )


def test_expired_trust_profile_approval_no_longer_satisfies_activation(conn, profile_paths):
    profile_path, owners_path = profile_paths
    proposal = governance.propose(profile_path, owners_path)
    for role in ("security_approver", "legal_data_governance_approver"):
        governance.decide(
            conn, proposal, actor_identity="abhishek", role=role, decision="approve",
            expires_at="2000-01-01T00:00:00+00:00", attestation_version="v1", attestation_hash=role,
            owners_path=owners_path, profile_path=profile_path,
        )
    conn.commit()
    activated = governance.activation(conn, proposal, now="2026-01-01T00:00:00+00:00", profile_path=profile_path)
    assert not activated.active


def test_governance_decide_writes_one_approval_record_per_acting_approver(conn, profile_paths):
    profile_path, owners_path = profile_paths
    proposal = governance.propose(profile_path, owners_path)
    row_ids = [
        governance.decide(
            conn, proposal, actor_identity="abhishek", role=role, decision="approve",
            expires_at=FAR_FUTURE, attestation_version="v1", attestation_hash=role,
            owners_path=owners_path, profile_path=profile_path,
        )
        for role in ("security_approver", "legal_data_governance_approver")
    ]
    conn.commit()
    assert len(set(row_ids)) == 2
    for row_id in row_ids:
        row = record.get(conn, "approval_record", row_id)
        assert row["gate"] == "trust_profile"
        assert row["subject_hash"] == proposal.subject_hash
        assert row["expires_at"] == FAR_FUTURE


# ---------------------------------------------------------------------------
# every decide() call writes exactly one guard_decision row.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("scenario", sorted(OPERATIONS))
def test_every_guard_decide_call_writes_exactly_one_row(conn, profile_paths, scenario):
    profile_path, owners_path = profile_paths
    _activate(conn, profile_path, owners_path)
    before = conn.execute("SELECT COUNT(*) FROM guard_decision").fetchone()[0]
    guard.decide(conn, _operation(scenario), profile_path=profile_path, owners_path=owners_path)
    after = conn.execute("SELECT COUNT(*) FROM guard_decision").fetchone()[0]
    assert after - before == 1


# ---------------------------------------------------------------------------
# pass_through is the seat every crossing must go through.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("crossing", guard.CROSSINGS)
def test_pass_through_returns_the_payload_of_its_own_matching_decision(conn, profile_paths, crossing):
    profile_path, owners_path = profile_paths
    _activate(conn, profile_path, owners_path)
    decision = guard.decide(conn, _operation(crossing), profile_path=profile_path, owners_path=owners_path)
    assert decision.decision in ("allow", "redact")
    assert guard.pass_through(conn, decision, crossing) == decision.payload


def test_must_reject_pass_through_for_a_mismatched_crossing(conn, profile_paths):
    profile_path, owners_path = profile_paths
    _activate(conn, profile_path, owners_path)
    decision = guard.decide(conn, _operation("dispatch"), profile_path=profile_path, owners_path=owners_path)
    with pytest.raises(guard.GuardRefused):
        guard.pass_through(conn, decision, "ingress")


def test_must_reject_pass_through_for_a_denied_decision(conn, profile_paths):
    profile_path, owners_path = profile_paths
    _activate(conn, profile_path, owners_path)
    decision = guard.decide(conn, _operation("absent_route"), profile_path=profile_path, owners_path=owners_path)
    assert decision.decision == "deny"
    with pytest.raises(guard.GuardRefused):
        guard.pass_through(conn, decision, "dispatch")


def test_must_reject_pass_through_for_a_hand_built_decision_never_persisted(conn):
    fake = guard.Decision(
        id=999_999, decision="allow", reason_codes=(), effective_class="internal",
        payload="never actually written", capabilities={},
    )
    with pytest.raises(guard.GuardRefused):
        guard.pass_through(conn, fake, "dispatch")


def test_must_reject_pass_through_given_a_raw_payload_instead_of_a_decision(conn):
    with pytest.raises(guard.GuardRefused):
        guard.pass_through(conn, "a raw payload, not a Decision", "dispatch")


# ---------------------------------------------------------------------------
# ticket/repository text cannot widen an operation's own
# capabilities.
# ---------------------------------------------------------------------------

def test_injected_widen_instruction_leaves_capabilities_unchanged(conn, profile_paths):
    profile_path, owners_path = profile_paths
    _activate(conn, profile_path, owners_path)
    op = _operation("injected_instruction")
    decision = guard.decide(conn, op, profile_path=profile_path, owners_path=owners_path)
    assert decision.capabilities == op.capabilities
    assert decision.capabilities["credentials"] == []
    assert decision.capabilities["tools"] == ["lint"]


# ---------------------------------------------------------------------------
# a secret hit denies and never stores the match, the raw
# payload, or a reversible digest of either.
# ---------------------------------------------------------------------------

def _assert_row_has_no_secret_trace(row, *secrets):
    row_text = json.dumps(dict(row))
    for secret in secrets:
        assert secret not in row_text
        assert hashlib.sha256(secret.encode()).hexdigest() not in row_text


def test_must_reject_secret_hit_and_the_row_stores_no_match_or_raw_payload(conn, profile_paths):
    profile_path, owners_path = profile_paths
    _activate(conn, profile_path, owners_path)
    op = _operation("secret_hit")
    decision = guard.decide(conn, op, profile_path=profile_path, owners_path=owners_path)
    assert decision.decision == "deny"
    assert decision.reason_codes == ("secret:aws_access_key_id",)
    row = record.get(conn, "guard_decision", decision.id)
    _assert_row_has_no_secret_trace(row, "AKIAABCDEFGHIJKLMNOP", op.payload)


def test_must_reject_secret_in_an_export_payload_matching_the_exit_test(conn, profile_paths):
    """the same non-retention rule applies to the governed export route,
    which is the milestone's own exit test."""
    profile_path, owners_path = profile_paths
    _activate(conn, profile_path, owners_path)
    op = _operation("export_secret_hit")
    decision = guard.decide(conn, op, profile_path=profile_path, owners_path=owners_path)
    assert decision.decision == "deny"
    assert decision.reason_codes == ("secret:github_token",)
    row = record.get(conn, "guard_decision", decision.id)
    _assert_row_has_no_secret_trace(row, "ghp_abcdefghijklmnopqrstuvwxyz0123456789")


# ---------------------------------------------------------------------------
# an operation naming an absent route denies.
# ---------------------------------------------------------------------------

def test_must_reject_operation_naming_a_route_absent_from_the_trust_profile(conn, profile_paths):
    profile_path, owners_path = profile_paths
    _activate(conn, profile_path, owners_path)
    decision = guard.decide(conn, _operation("absent_route"), profile_path=profile_path, owners_path=owners_path)
    assert decision.decision == "deny"
    assert decision.reason_codes == ("absent_route",)


# ---------------------------------------------------------------------------
# guard unavailable denies, whatever makes it unavailable.
# ---------------------------------------------------------------------------

def test_must_reject_operation_when_the_trust_profile_is_unreadable(conn, profile_paths, tmp_path):
    _, owners_path = profile_paths
    with pytest.raises(guard.GuardUnavailable):
        guard.decide(
            conn, _operation("dispatch"),
            profile_path=tmp_path / "no-such-trust-profile.yaml", owners_path=owners_path,
        )


def test_must_reject_operation_when_the_guard_sink_connection_is_closed(profile_paths, tmp_path):
    profile_path, owners_path = profile_paths
    closed_conn = connect(tmp_path / "closed.sqlite")
    closed_conn.close()
    with pytest.raises(guard.GuardUnavailable):
        guard.decide(closed_conn, _operation("dispatch"), profile_path=profile_path, owners_path=owners_path)


# ---------------------------------------------------------------------------
# the digest route lets only its five declared fields through.
# ---------------------------------------------------------------------------

def test_digest_payload_passes_only_the_five_declared_fields(conn, profile_paths):
    profile_path, owners_path = profile_paths
    _activate(conn, profile_path, owners_path)
    decision = guard.decide(conn, _operation("outbox"), profile_path=profile_path, owners_path=owners_path)
    assert decision.decision == "redact"
    assert set(decision.payload) == {"ticket_id", "tier", "item_kind", "age", "command"}
    assert "ticket_text" not in decision.payload
    assert "question_options" not in decision.payload
