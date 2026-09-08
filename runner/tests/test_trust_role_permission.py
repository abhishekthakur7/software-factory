"""One identity filling both trust roles is a policy exception, not a
default: it is accepted only when `trust-profile.yaml` names that identity,
and refused whenever the key is unset, null, or names someone else.
"""
import pytest
import yaml

from runner.owners import REQUIRED_ROLES, OwnersError, load_owners


def _owners_doc(security_identity, legal_identity):
    roles = {role: {"identity": "abhishek", "responsibilities": ["approvals"]} for role in REQUIRED_ROLES}
    roles["security_approver"]["identity"] = security_identity
    roles["legal_data_governance_approver"]["identity"] = legal_identity
    return {"roles": roles, "shared_identities": []}


def _write_owners(tmp_path, security_identity, legal_identity):
    path = tmp_path / "owners.yaml"
    path.write_text(yaml.safe_dump(_owners_doc(security_identity, legal_identity)))
    return path


def _write_trust_profile(tmp_path, doc):
    path = tmp_path / "trust-profile.yaml"
    path.write_text(yaml.safe_dump(doc))
    return path


def test_shared_trust_role_identity_is_accepted_when_the_profile_names_it(tmp_path):
    owners_path = _write_owners(tmp_path, "abhishek", "abhishek")
    profile_path = _write_trust_profile(tmp_path, {"both_trust_roles_identity": "abhishek"})
    owners = load_owners(owners_path, profile_path)
    assert owners.roles["security_approver"]["identity"] == "abhishek"
    assert owners.roles["legal_data_governance_approver"]["identity"] == "abhishek"


def test_must_reject_shared_trust_role_identity_when_the_profile_key_is_absent(tmp_path):
    owners_path = _write_owners(tmp_path, "abhishek", "abhishek")
    profile_path = _write_trust_profile(tmp_path, {})
    with pytest.raises(OwnersError):
        load_owners(owners_path, profile_path)


def test_must_reject_shared_trust_role_identity_when_the_profile_file_is_missing(tmp_path):
    owners_path = _write_owners(tmp_path, "abhishek", "abhishek")
    missing_profile_path = tmp_path / "no-such-trust-profile.yaml"
    with pytest.raises(OwnersError):
        load_owners(owners_path, missing_profile_path)


def test_must_reject_shared_trust_role_identity_when_the_profile_key_is_null(tmp_path):
    owners_path = _write_owners(tmp_path, "abhishek", "abhishek")
    profile_path = _write_trust_profile(tmp_path, {"both_trust_roles_identity": None})
    with pytest.raises(OwnersError):
        load_owners(owners_path, profile_path)


def test_must_reject_shared_trust_role_identity_when_the_profile_names_someone_else(tmp_path):
    owners_path = _write_owners(tmp_path, "abhishek", "abhishek")
    profile_path = _write_trust_profile(tmp_path, {"both_trust_roles_identity": "someone_else"})
    with pytest.raises(OwnersError):
        load_owners(owners_path, profile_path)


def test_distinct_trust_role_identities_need_no_profile_exemption(tmp_path):
    """the profile gate only fires when one identity fills both trust
    roles; distinct identities load without any trust-profile file at all."""
    owners_path = _write_owners(tmp_path, "abhishek", "someone_else")
    missing_profile_path = tmp_path / "no-such-trust-profile.yaml"
    owners = load_owners(owners_path, missing_profile_path)
    assert owners.roles["security_approver"]["identity"] == "abhishek"
    assert owners.roles["legal_data_governance_approver"]["identity"] == "someone_else"
