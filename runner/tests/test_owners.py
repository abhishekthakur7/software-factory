"""The authority policy: role/identity/responsibility validation, the
authority-policy hash bound into an approval decision, and the identity
snapshot taken independently of it.

`_owners_doc` builds a minimal valid structure as a Python dict so each test
mutates exactly the piece it wants broken, rather than committing a whole
fixture file per scenario.
"""
import hashlib

import pytest
import yaml

from runner import canonical, record
from runner.db import connect
from runner.owners import (
    REQUIRED_ROLES,
    OwnersError,
    authority_policy_hash,
    identity_snapshot,
    load_owners,
)
from runner.paths import FACTORY_DIR

OWNERS_PATH = FACTORY_DIR / "config" / "owners.yaml"
TRUST_PROFILE_PATH = FACTORY_DIR / "config" / "trust-profile.yaml"


def _owners_doc():
    return {
        "roles": {role: {"identity": "abhishek", "responsibilities": ["approvals"]} for role in REQUIRED_ROLES},
        "shared_identities": [
            {
                "identity": "abhishek",
                "roles": ["factory_owner", "service_owner"],
                "note": "the pilot has one person holding both roles.",
            }
        ],
    }


def _write(tmp_path, doc, name="owners.yaml"):
    path = tmp_path / name
    path.write_text(yaml.safe_dump(doc))
    return path


def _write_trust_profile(tmp_path, identity="abhishek"):
    path = tmp_path / "trust-profile.yaml"
    path.write_text(yaml.safe_dump({"both_trust_roles_identity": identity}))
    return path


def test_committed_owners_file_names_every_required_role_with_an_identity():
    """every required role has a non-empty identity in the committed file,
    loaded through the real validator rather than read as raw YAML."""
    owners = load_owners()
    for role in REQUIRED_ROLES:
        assert owners.roles[role]["identity"]


def test_committed_sensitive_path_owner_and_ticket_engineer_are_distinct_role_entries():
    """the sensitive-path-owner and ticket-engineer roles are recorded as two
    separate role entries, not one entry doing double duty."""
    owners = load_owners()
    assert "sensitive_path_owner" in owners.roles
    assert "ticket_engineer" in owners.roles
    assert owners.roles["sensitive_path_owner"] is not owners.roles["ticket_engineer"]


def test_committed_shared_identities_records_the_pilot_note():
    """the seeded pilot identity holding several non-sensitive roles is
    recorded as data, with a note explaining why, not left implicit."""
    owners = load_owners()
    assert owners.shared_identities
    entry = owners.shared_identities[0]
    assert entry["identity"] == "abhishek"
    assert len(entry["roles"]) >= 2
    assert entry["note"]


def test_committed_trust_profile_carries_only_the_one_key():
    """trust-profile.yaml, as built by this ticket, carries only
    both_trust_roles_identity and nothing else."""
    doc = yaml.safe_load(TRUST_PROFILE_PATH.read_text())
    assert set(doc.keys()) == {"both_trust_roles_identity"}
    assert doc["both_trust_roles_identity"] == "abhishek"


def test_must_reject_role_with_empty_responsibilities_list(tmp_path):
    doc = _owners_doc()
    doc["roles"]["factory_owner"]["responsibilities"] = []
    path = _write(tmp_path, doc)
    with pytest.raises(OwnersError):
        load_owners(path, _write_trust_profile(tmp_path))


def test_must_reject_role_with_unknown_responsibility_category(tmp_path):
    doc = _owners_doc()
    doc["roles"]["factory_owner"]["responsibilities"] = ["not_a_real_category"]
    path = _write(tmp_path, doc)
    with pytest.raises(OwnersError):
        load_owners(path, _write_trust_profile(tmp_path))


def test_must_reject_missing_required_role(tmp_path):
    doc = _owners_doc()
    del doc["roles"]["incident_reviewer"]
    path = _write(tmp_path, doc)
    with pytest.raises(OwnersError):
        load_owners(path, _write_trust_profile(tmp_path))


def test_must_reject_role_with_no_identity(tmp_path):
    doc = _owners_doc()
    doc["roles"]["ticket_engineer"]["identity"] = ""
    path = _write(tmp_path, doc)
    with pytest.raises(OwnersError):
        load_owners(path, _write_trust_profile(tmp_path))


def test_must_reject_shared_identities_entry_naming_a_role_it_does_not_hold(tmp_path):
    """shared_identities is checked against the roles it claims to summarize,
    not accepted as an unverified label."""
    doc = _owners_doc()
    doc["roles"]["service_owner"]["identity"] = "someone_else"
    path = _write(tmp_path, doc)
    with pytest.raises(OwnersError):
        load_owners(path, _write_trust_profile(tmp_path))


def test_owners_with_shared_trust_roles_loads_when_the_trust_profile_permits_it(tmp_path):
    doc = _owners_doc()
    doc["roles"]["security_approver"]["identity"] = "abhishek"
    doc["roles"]["legal_data_governance_approver"]["identity"] = "abhishek"
    path = _write(tmp_path, doc)
    owners = load_owners(path, _write_trust_profile(tmp_path, "abhishek"))
    assert owners.roles["security_approver"]["identity"] == "abhishek"


def test_authority_policy_hash_matches_a_hash_recomputed_over_the_file_bytes(tmp_path):
    doc = _owners_doc()
    path = _write(tmp_path, doc)
    expected = hashlib.sha256(path.read_bytes()).hexdigest()
    assert authority_policy_hash(path) == expected


def test_authority_policy_hash_changes_when_the_file_bytes_change(tmp_path):
    doc = _owners_doc()
    path = _write(tmp_path, doc)
    before = authority_policy_hash(path)
    doc["roles"]["factory_owner"]["responsibilities"].append("waivers")
    path.write_text(yaml.safe_dump(doc))
    after = authority_policy_hash(path)
    assert before != after


def test_identity_snapshots_for_two_decisions_differ_from_each_other_and_from_the_policy_hash(tmp_path):
    doc = _owners_doc()
    doc["roles"]["s3_reviewer"]["identity"] = "someone_else"
    path = _write(tmp_path, doc)
    owners = load_owners(path, _write_trust_profile(tmp_path))
    policy_hash = authority_policy_hash(path)

    snapshot_a = canonical.content_hash(identity_snapshot(owners, "abhishek"))
    snapshot_b = canonical.content_hash(identity_snapshot(owners, "someone_else"))

    assert snapshot_a != snapshot_b
    assert snapshot_a != policy_hash
    assert snapshot_b != policy_hash


def test_rewriting_the_owners_file_changes_the_policy_hash_but_not_a_snapshot_already_taken(tmp_path):
    doc = _owners_doc()
    path = _write(tmp_path, doc)
    owners = load_owners(path, _write_trust_profile(tmp_path))
    snapshot_before_rewrite = identity_snapshot(owners, "abhishek")
    snapshot_hash_before_rewrite = canonical.content_hash(snapshot_before_rewrite)
    policy_hash_before = authority_policy_hash(path)

    doc["roles"]["outcome_recorder"]["responsibilities"].append("incident_attribution_disposition")
    path.write_text(yaml.safe_dump(doc))
    policy_hash_after = authority_policy_hash(path)

    assert policy_hash_after != policy_hash_before
    # a snapshot already taken (and its hash) is frozen data, unaffected by
    # a later rewrite of the file it was taken from.
    assert canonical.content_hash(snapshot_before_rewrite) == snapshot_hash_before_rewrite


def test_approval_record_row_carries_the_policy_hash_and_a_fresh_membership_snapshot_hash(tmp_path):
    """the two hashes land on the same approval_record row through the
    ordinary record.insert path, and read back exactly as written."""
    doc = _owners_doc()
    path = _write(tmp_path, doc)
    owners = load_owners(path, _write_trust_profile(tmp_path))

    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = record.insert(conn, "ticket", title="t")

    policy_hash = authority_policy_hash(path)
    snapshot = identity_snapshot(owners, "abhishek")
    snapshot_hash = canonical.content_hash(snapshot)

    approval_id = record.insert(
        conn,
        "approval_record",
        ticket_id=ticket_id,
        gate="trust_profile",
        actor_identity="abhishek",
        authority_policy_hash=policy_hash,
        membership_snapshot_hash=snapshot_hash,
        decided_at=record.now(),
    )
    conn.commit()

    row = record.get(conn, "approval_record", approval_id)
    assert row["authority_policy_hash"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert row["membership_snapshot_hash"] == snapshot_hash
    conn.close()
