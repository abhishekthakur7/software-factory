"""The trust profile: schema validation, class join, sanitizer resolution,
export permission, retention, and the route field set the walk crosses.

`_profile_doc`/`_without` build a mutable copy of the seeded fixture
profile so the missing-field tests each break exactly one field, rather
than committing a whole fixture file per scenario -- the same pattern
`test_owners.py` uses for `owners.yaml`.
"""
import copy
import shutil
from pathlib import Path

import pytest
import yaml

from runner import governance, owners, trust_profile
from runner.db import connect

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "trust_profile"


def _profile_doc() -> dict:
    return copy.deepcopy(yaml.safe_load((FIXTURES_DIR / "profile.yaml").read_text()))


def _without(doc: dict, path: str) -> dict:
    """`doc` with the field at dotted `path` removed."""
    doc = copy.deepcopy(doc)
    node = doc
    parts = path.split(".")
    for part in parts[:-1]:
        node = node[part]
    del node[parts[-1]]
    return doc


def _write(tmp_path: Path, doc: dict, name: str = "trust-profile.yaml") -> Path:
    path = tmp_path / name
    path.write_text(yaml.safe_dump(doc))
    return path


# Every field a route must carry, plus the admitted-source-class and
# deliverer fields the routes section also carries, so a file missing any
# one of them is proven to fail rather than silently passing.
REQUIRED_FIELD_PATHS = [
    "both_trust_roles_identity",
    "classes",
    "join_rules.default_deny",
    "join_rules.exceptions",
    "admitted_scopes.repositories",
    "admitted_scopes.jira_projects",
    "admitted_scopes.confluence_spaces",
    "secret_rules",
    "sanitizers",
    "evidence.provider_terms_dpa_ref",
    "evidence.security_assessment_ref",
    "approval_slots.security_approver",
    "approval_slots.legal_data_governance_approver",
] + [f"routes.hosted_model.{field}" for field in trust_profile.ROUTE_REQUIRED_FIELDS]


def test_committed_fixture_profile_validates_against_the_schema():
    """the seeded fixture profile loads clean through the real validator,
    naming every route, class and slot the ticket requires."""
    profile = trust_profile.load_trust_profile(FIXTURES_DIR / "profile.yaml")
    assert profile.both_trust_roles_identity == "abhishek"
    assert profile.classes.order == ("public", "internal", "confidential", "restricted")
    assert profile.classes.default_deny is True
    assert profile.admitted_scopes["repositories"] == ("fixture-project",)
    assert profile.admitted_scopes["jira_projects"] == ("FIX",)
    assert profile.admitted_scopes["confluence_spaces"] == ("FIX",)
    assert set(profile.routes) == set(trust_profile.ROUTE_IDS)


@pytest.mark.parametrize("field_path", REQUIRED_FIELD_PATHS, ids=REQUIRED_FIELD_PATHS)
def test_must_reject_trust_profile_missing_a_required_field(tmp_path, field_path):
    doc = _without(_profile_doc(), field_path)
    path = _write(tmp_path, doc)
    with pytest.raises(trust_profile.TrustProfileError):
        trust_profile.load_trust_profile(path)


def test_must_reject_route_rule_set_hash_that_does_not_match_the_secret_rules(tmp_path):
    doc = _profile_doc()
    doc["routes"]["hosted_model"]["rule_set_hash"] = "0" * 64
    path = _write(tmp_path, doc)
    with pytest.raises(trust_profile.TrustProfileError):
        trust_profile.load_trust_profile(path)


def test_must_reject_digest_route_fields_wider_than_the_five_declared(tmp_path):
    doc = _profile_doc()
    doc["routes"]["slack_digest"]["fields"] = list(trust_profile.DIGEST_FIELDS) + ["ticket_text"]
    path = _write(tmp_path, doc)
    with pytest.raises(trust_profile.TrustProfileError):
        trust_profile.load_trust_profile(path)


# ---------------------------------------------------------------------------
# an owners.yaml content-hash change changes the trust-approval
# subject, and a previously satisfying approval set stops satisfying it.
# ---------------------------------------------------------------------------

def _seed_pair(tmp_path):
    profile_path = tmp_path / "trust-profile.yaml"
    owners_path = tmp_path / "owners.yaml"
    shutil.copy(FIXTURES_DIR / "profile.yaml", profile_path)
    shutil.copy(FIXTURES_DIR / "owners.yaml", owners_path)
    return profile_path, owners_path


def test_owners_content_hash_change_produces_a_new_trust_approval_subject(tmp_path):
    profile_path, owners_path = _seed_pair(tmp_path)
    profile_hash = trust_profile.profile_hash(profile_path)
    old_authority_hash = owners.authority_policy_hash(owners_path)
    old_subject = trust_profile.trust_approval_subject(profile_hash, old_authority_hash)

    doc = yaml.safe_load(owners_path.read_text())
    doc["roles"]["factory_owner"]["responsibilities"].append("waivers")
    owners_path.write_text(yaml.safe_dump(doc))

    new_authority_hash = owners.authority_policy_hash(owners_path)
    new_subject = trust_profile.trust_approval_subject(profile_hash, new_authority_hash)

    assert new_authority_hash != old_authority_hash
    assert new_subject != old_subject


def test_owners_content_hash_change_invalidates_a_previously_satisfying_approval_set(tmp_path):
    profile_path, owners_path = _seed_pair(tmp_path)
    conn = connect(tmp_path / "factory.sqlite")
    try:
        proposal = governance.propose(profile_path, owners_path)
        for role in ("security_approver", "legal_data_governance_approver"):
            governance.decide(
                conn, proposal, actor_identity="abhishek", role=role, decision="approve",
                expires_at="2999-01-01T00:00:00+00:00", attestation_version="v1", attestation_hash=role,
                owners_path=owners_path, profile_path=profile_path,
            )
        conn.commit()
        assert governance.activation(conn, proposal, profile_path=profile_path).active

        doc = yaml.safe_load(owners_path.read_text())
        doc["roles"]["factory_owner"]["responsibilities"].append("waivers")
        owners_path.write_text(yaml.safe_dump(doc))

        new_proposal = governance.propose(profile_path, owners_path)
        assert new_proposal.subject_hash != proposal.subject_hash
        assert not governance.activation(conn, new_proposal, profile_path=profile_path).active
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# a sanitizer rule hash is permitted only for its named pair.
# ---------------------------------------------------------------------------

def test_sanitizer_records_the_permitted_downgrade_for_its_named_pair():
    profile = trust_profile.load_trust_profile(FIXTURES_DIR / "profile.yaml")
    sanitizer = profile.sanitizers[0]
    resolved = trust_profile.resolve_sanitizer(
        profile, sanitizer.rule_hash, sanitizer.source_class, sanitizer.target_class
    )
    assert resolved == sanitizer.target_class


def test_must_reject_sanitizer_rule_hash_invoked_outside_its_permitted_pair():
    profile = trust_profile.load_trust_profile(FIXTURES_DIR / "profile.yaml")
    sanitizer = profile.sanitizers[0]
    # right rule hash, wrong target
    assert trust_profile.resolve_sanitizer(profile, sanitizer.rule_hash, sanitizer.source_class, "restricted") is None
    # right rule hash, wrong source
    assert trust_profile.resolve_sanitizer(profile, sanitizer.rule_hash, "public", sanitizer.target_class) is None
    # a rule hash that names no sanitizer at all
    assert trust_profile.resolve_sanitizer(profile, "not-a-registered-rule", "confidential", "internal") is None


# ---------------------------------------------------------------------------
# both_trust_roles_identity names one identity, and activation
# depends on that exact field.
# ---------------------------------------------------------------------------

def test_both_trust_roles_identity_names_one_identity():
    profile = trust_profile.load_trust_profile(FIXTURES_DIR / "profile.yaml")
    assert profile.both_trust_roles_identity == "abhishek"


def test_must_reject_proposal_when_the_profile_names_a_different_shared_trust_role_identity(tmp_path):
    """the fixture owners file gives both trust roles to `abhishek`; that is
    only ever permitted because the profile's `both_trust_roles_identity`
    names `abhishek` too -- naming anyone else breaks the whole proposal,
    not just quorum."""
    profile_path, owners_path = _seed_pair(tmp_path)
    doc = yaml.safe_load(profile_path.read_text())
    doc["both_trust_roles_identity"] = "someone_else"
    profile_path.write_text(yaml.safe_dump(doc))
    with pytest.raises(owners.OwnersError):
        governance.propose(profile_path, owners_path)


# ---------------------------------------------------------------------------
# export requests are evaluated against the route's own rule.
# ---------------------------------------------------------------------------

def test_export_request_within_the_route_rule_is_permitted():
    profile = trust_profile.load_trust_profile(FIXTURES_DIR / "profile.yaml")
    route = profile.routes["governed_export_display"]
    assert trust_profile.export_permitted(route, {"format": "directory_export", "class": "confidential"})


def test_must_reject_export_request_outside_the_route_rule():
    profile = trust_profile.load_trust_profile(FIXTURES_DIR / "profile.yaml")
    route = profile.routes["governed_export_display"]
    assert not trust_profile.export_permitted(route, {"format": "directory_export", "class": "restricted"})
    assert not trust_profile.export_permitted(route, {"format": "zip_archive", "class": "confidential"})


# ---------------------------------------------------------------------------
# retention/deletion is a distinct flag from "still current".
# ---------------------------------------------------------------------------

def test_artefact_past_retention_is_flagged_distinct_from_one_still_inside_the_window():
    profile = trust_profile.load_trust_profile(FIXTURES_DIR / "profile.yaml")
    route = profile.routes["governed_export_display"]  # retention_days: 90
    created_at = "2026-01-01T00:00:00+00:00"
    assert trust_profile.retention_expired(route, created_at, now="2026-06-01T00:00:00+00:00")
    assert not trust_profile.retention_expired(route, created_at, now="2026-01-10T00:00:00+00:00")


# ---------------------------------------------------------------------------
# every route the walk crosses names its provider, reader
# roles, and deliverer kind.
# ---------------------------------------------------------------------------

def test_every_route_the_walk_crosses_names_its_provider_reader_roles_and_deliverer():
    profile = trust_profile.load_trust_profile(FIXTURES_DIR / "profile.yaml")
    assert set(profile.routes) == set(trust_profile.ROUTE_IDS)
    for route_id, route in profile.routes.items():
        assert route.provider
        assert route.reader_roles
        expected_deliverer = (
            "stub" if route_id in ("github_scratch", "slack_digest") and not route.credential_roles
            else "live" if route_id in trust_profile.LIVE_ROUTES else "stub"
        )
        assert route.deliverer == expected_deliverer
    for route_id in trust_profile.GITHUB_ROUTE_IDS:
        assert profile.routes[route_id].operations == ("pr_create", "pr_update")


# ---------------------------------------------------------------------------
# a repository's own configured classes join the same way any other
# class set does.
# ---------------------------------------------------------------------------

def test_repository_class_joins_a_repositorys_configured_classes():
    profile = trust_profile.load_trust_profile(trust_profile.DEFAULT_TRUST_PROFILE_PATH)
    assert profile.repository_data_classes["fixture-project"] == ("internal", "confidential")
    assert trust_profile.repository_class(profile, "fixture-project") == "confidential"


def test_repository_class_is_none_for_a_repository_the_profile_names_no_classes_for():
    profile = trust_profile.load_trust_profile(FIXTURES_DIR / "profile.yaml")
    assert trust_profile.repository_class(profile, "fixture-project") is None
