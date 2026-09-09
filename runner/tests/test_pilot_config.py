"""The pilot's committed configuration content: structure and resolution over the real files, not literals (R-S0-1)."""
from pathlib import Path

import yaml

from runner import credentials, envelope, governance, owners, project, record, trust_profile
from runner.db import connect
from runner.paths import FACTORY_DIR, REPO_ROOT
from runner.stages import S0

ABHISHEK = "abhishek"
FAR_FUTURE = "2999-01-01T00:00:00+00:00"

TRUST_PROFILE = trust_profile.load_trust_profile()
PROJECT_DOC = project.load()
PILOT = project.pilot()


# --- service-tiers.yaml, ticket-types.yaml, sensitive-paths.yaml carry the pilot's rows ---

def test_service_tiers_carries_a_row_for_the_pilot_service():
    tiers = yaml.safe_load((FACTORY_DIR / "config" / "service-tiers.yaml").read_text())
    service = tiers["services"][PILOT["name"]]
    assert service["tier"]
    assert PILOT["name"] in service["repositories"]


def test_ticket_types_names_the_pilots_jira_field_keys():
    ticket_types = S0.load_ticket_types()
    jira_fields = ticket_types["jira_fields"]
    assert set(jira_fields) == {"acceptance_criteria", "owner", "parent_link", "confluence_link", "issue_type"}
    assert all(isinstance(v, str) and v for v in jira_fields.values())
    # the atlassian_read route must actually admit every one of these
    # keys, or the field gate could pass over a payload the guard would
    # then redact right back out.
    assert set(jira_fields.values()) <= set(TRUST_PROFILE.routes["atlassian_read"].fields)


def test_sensitive_paths_entries_each_carry_an_owner():
    sensitive_paths = yaml.safe_load((FACTORY_DIR / "config" / "sensitive-paths.yaml").read_text())["paths"]
    assert sensitive_paths
    assert all(isinstance(owner, str) and owner for owner in sensitive_paths.values())


# --- factory/index/ carries the pilot's entries, fresh at seeding ---

def test_index_conventions_and_sensitive_paths_entries_carry_last_verified():
    from runner import context_index
    entries = {entry.path.stem: entry for entry in context_index.load_entries()}
    assert entries["conventions"].kind == "convention"
    assert entries["conventions"].last_verified is not None
    assert entries["sensitive-paths"].kind == "sensitive_paths"
    assert entries["sensitive-paths"].last_verified is not None


def test_index_carries_a_caller_entry_for_the_pilots_known_caller():
    from runner import context_index
    callers = [e for e in context_index.load_entries() if e.kind == "caller"]
    assert callers
    assert all(entry.last_verified is not None for entry in callers)


# --- project.yaml: the pilot's checkout, target branch, recipes, toolchain; the scratch repository ---

def test_pilot_checkout_resolves_outside_the_repository():
    checkout = (REPO_ROOT / PILOT["checkout"]).resolve()
    assert not str(checkout).startswith(str(FACTORY_DIR.resolve()))
    assert not checkout.is_relative_to(REPO_ROOT / "factory")


def test_pilot_names_a_target_branch_recipe_ids_and_a_resolvable_toolchain_digest():
    assert PILOT["target_branch"]
    assert PILOT["recipes"]
    digest = envelope.toolchain_digest(PILOT["toolchain"])
    assert digest


def test_scratch_repository_names_a_branch_prefix_for_a_repository_the_owner_creates_by_hand():
    scratch = PROJECT_DOC["scratch_repository"]
    assert scratch["name"]
    assert scratch["branch_prefix"]
    # `remote` stays null until the owner creates the GitHub repository by
    # hand -- a non-null value here would mean this config was never
    # actually reviewed against the real state of the world.
    assert scratch.get("remote") is None


def test_pilot_loader_refuses_a_file_naming_more_than_one_project(tmp_path):
    path = tmp_path / "project.yaml"
    path.write_text(yaml.safe_dump({"projects": [{"name": "a"}, {"name": "b"}]}))
    try:
        project.pilot(path=path)
    except project.ProjectConfigError as exc:
        assert "expected exactly one project" in str(exc)
    else:
        raise AssertionError("expected ProjectConfigError")


# --- trust-profile.yaml: admitted scopes, routes, credential roles, and the repository data-class join ---

def test_admitted_scopes_carries_both_the_pilot_and_the_scratch_repository():
    scratch_name = PROJECT_DOC["scratch_repository"]["name"]
    assert PILOT["name"] in TRUST_PROFILE.admitted_scopes["repositories"]
    assert scratch_name in TRUST_PROFILE.admitted_scopes["repositories"]


def test_every_routes_credential_role_is_a_real_role():
    for route_id, route in TRUST_PROFILE.routes.items():
        assert set(route.credential_roles) <= set(credentials.ROLES), route_id


def test_named_routes_carry_the_credential_roles_the_ticket_specifies():
    assert TRUST_PROFILE.routes["atlassian_read"].credential_roles == ("atlassian_read",)
    assert TRUST_PROFILE.routes["github_pilot"].credential_roles == ("github_publish",)
    assert TRUST_PROFILE.routes["github_scratch"].credential_roles == ("github_publish",)
    assert TRUST_PROFILE.routes["slack_digest"].credential_roles == ("slack_digest",)
    assert set(TRUST_PROFILE.routes["baseline_read"].credential_roles) == {"atlassian_read", "github_publish"}
    assert TRUST_PROFILE.routes["registry"].credential_roles == ()
    assert TRUST_PROFILE.routes["vulnerability_feed"].credential_roles == ()


def test_pilot_repository_data_class_joins_to_confidential():
    assert trust_profile.repository_class(TRUST_PROFILE, PILOT["name"]) == "confidential"


# --- every service's repositories fall inside the admitted scope ---

def test_every_service_tiers_repository_is_inside_the_admitted_scope():
    tiers = yaml.safe_load((FACTORY_DIR / "config" / "service-tiers.yaml").read_text())
    for service, config in tiers["services"].items():
        for repository in config["repositories"]:
            assert repository in TRUST_PROFILE.admitted_scopes["repositories"], (service, repository)


# --- the committed profile is governance-approved and pinned before eligibility, the same activation path S0 uses ---

def test_pilot_profile_is_approved_and_pinned_before_a_fresh_tickets_eligibility(tmp_path):
    conn = connect(tmp_path / "factory.sqlite")
    try:
        proposal = governance.propose()
        for role in ("security_approver", "legal_data_governance_approver"):
            governance.decide(
                conn, proposal, actor_identity=ABHISHEK, role=role, decision="approve",
                expires_at=FAR_FUTURE, attestation_version="v1", attestation_hash=f"att-{role}",
            )
        activated = governance.activation(conn, proposal)
        assert activated.active

        ticket_id = record.insert(
            conn, "ticket", state="intake", opened_at=record.now(),
            trust_profile_hash=proposal.profile_hash, trust_approval_set_hash=activated.trust_approval_set_hash,
            service=PILOT["name"], source_kind="jira", source_ref="FIX-1",
        )
        ticket = record.get(conn, "ticket", ticket_id)
        assert S0.governance_valid(conn, ticket) == []
    finally:
        conn.close()
