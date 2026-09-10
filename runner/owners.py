"""The authority policy: who holds which role, and what a role may decide.

`owners.yaml` is the one file every trust and ticket approval binds against.
Its exact bytes hash to the authority-policy hash carried on an
`approval_record` row (`authority_policy_hash`), so any edit to the file,
even one that reorders lines without changing meaning, changes that hash --
deliberately, since the hash exists to let a later audit tell "the policy in
force at decision time" apart from "the policy today" without re-parsing
either file. Who a role's current identity actually is, and which roles that
identity holds, is a separate question answered fresh at each decision by
`identity_snapshot` and hashed independently
(`approval_record.membership_snapshot_hash`): a role assignment and the
person behind it at decision time must never collapse into one hash, or a
role rename would silently invalidate every past approval and a personnel
change would silently validate one.

`trust-profile.yaml` carries the one gate this module enforces on top of the
role list: the pilot's two trust roles, security and legal/data-governance
approval, may be held by the same identity only when that file names the
identity explicitly. Everything else in that file belongs to a later ticket.
"""
import hashlib
from dataclasses import dataclass
from pathlib import Path

import yaml

from runner import record
from runner.paths import FACTORY_DIR

REQUIRED_ROLES = (
    "factory_owner",
    "security_approver",
    "legal_data_governance_approver",
    "service_owner",
    "sensitive_path_owner",
    "ticket_engineer",
    "plan_reviewer",
    "packet_reviewer",
    "outcome_recorder",
    "incident_reviewer",
)

TRUST_ROLES = ("security_approver", "legal_data_governance_approver")

RESPONSIBILITY_CATEGORIES = frozenset({
    "tiers",
    "topology",
    "trust_policy",
    "sandbox_recipes",
    "manifests_rubrics",
    "waivers",
    "approvals",
    "incident_attribution_disposition",
})

DEFAULT_OWNERS_PATH = FACTORY_DIR / "config" / "owners.yaml"
DEFAULT_TRUST_PROFILE_PATH = FACTORY_DIR / "config" / "trust-profile.yaml"


class OwnersError(ValueError):
    """The owners file, or the trust-profile gate on it, fails validation."""


def _load_yaml_mapping(path: Path, error_prefix: str) -> dict:
    try:
        text = Path(path).read_text()
    except OSError as exc:
        raise OwnersError(f"{error_prefix}: cannot read {path}: {exc}") from exc
    try:
        parsed = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise OwnersError(f"{error_prefix}: invalid YAML in {path}: {exc}") from exc
    if not isinstance(parsed, dict):
        raise OwnersError(f"{error_prefix}: {path} is not a mapping")
    return parsed


def _validate_role_entry(role: str, entry: object) -> None:
    if not isinstance(entry, dict):
        raise OwnersError(f"owners.yaml: role {role!r} is not a mapping")
    identity = entry.get("identity")
    if not isinstance(identity, str) or not identity:
        raise OwnersError(f"owners.yaml: role {role!r} has no identity")
    responsibilities = entry.get("responsibilities")
    if not isinstance(responsibilities, list) or not responsibilities:
        raise OwnersError(f"owners.yaml: role {role!r} has an empty responsibilities list")
    unknown = [c for c in responsibilities if c not in RESPONSIBILITY_CATEGORIES]
    if unknown:
        raise OwnersError(f"owners.yaml: role {role!r} names unknown responsibilities {unknown}")


def _validate_shared_identities(shared_identities: object, roles: dict) -> None:
    if not isinstance(shared_identities, list):
        raise OwnersError("owners.yaml: shared_identities must be a list")
    for entry in shared_identities:
        if not isinstance(entry, dict):
            raise OwnersError("owners.yaml: shared_identities entry is not a mapping")
        identity = entry.get("identity")
        held_roles = entry.get("roles")
        note = entry.get("note")
        if not isinstance(identity, str) or not identity:
            raise OwnersError("owners.yaml: shared_identities entry has no identity")
        if not isinstance(held_roles, list) or not held_roles:
            raise OwnersError(f"owners.yaml: shared_identities entry for {identity!r} names no roles")
        if not isinstance(note, str) or not note:
            raise OwnersError(f"owners.yaml: shared_identities entry for {identity!r} has no note")
        for role in held_roles:
            if role not in roles:
                raise OwnersError(f"owners.yaml: shared_identities names unknown role {role!r}")
            if roles[role]["identity"] != identity:
                raise OwnersError(
                    f"owners.yaml: shared_identities says {identity!r} holds {role!r}, "
                    f"but that role's identity is {roles[role]['identity']!r}"
                )


def _validate_trust_roles(roles: dict, trust_profile_path: Path) -> None:
    identities = {roles[role]["identity"] for role in TRUST_ROLES}
    if len(identities) > 1:
        return  # distinct identities in the two trust roles need no exemption
    shared_identity = next(iter(identities))
    profile = {}
    if Path(trust_profile_path).is_file():
        profile = _load_yaml_mapping(trust_profile_path, "trust-profile.yaml")
    permitted = profile.get("both_trust_roles_identity")
    if permitted != shared_identity:
        raise OwnersError(
            f"owners.yaml: {TRUST_ROLES[0]!r} and {TRUST_ROLES[1]!r} are both held by "
            f"{shared_identity!r}, but trust-profile.yaml's both_trust_roles_identity "
            f"does not name that identity"
        )


@dataclass(frozen=True)
class Owners:
    """The validated authority policy: `roles[role] == {"identity", "responsibilities"}`."""

    roles: dict
    shared_identities: list


def load_owners(
    path: Path = DEFAULT_OWNERS_PATH,
    trust_profile_path: Path = DEFAULT_TRUST_PROFILE_PATH,
) -> Owners:
    """Parse and validate `path`, raising `OwnersError` on the first problem found."""
    doc = _load_yaml_mapping(path, "owners.yaml")
    roles = doc.get("roles")
    if not isinstance(roles, dict):
        raise OwnersError("owners.yaml: missing roles mapping")
    missing = [role for role in REQUIRED_ROLES if role not in roles]
    if missing:
        raise OwnersError(f"owners.yaml: missing required role(s) {missing}")
    for role in REQUIRED_ROLES:
        _validate_role_entry(role, roles[role])
    _validate_shared_identities(doc.get("shared_identities", []), roles)
    _validate_trust_roles(roles, trust_profile_path)
    return Owners(roles=roles, shared_identities=doc.get("shared_identities", []))


def authority_policy_hash(path: Path = DEFAULT_OWNERS_PATH) -> str:
    """SHA-256 hex digest of the owners file's exact committed bytes.

    Hashing the raw bytes rather than the parsed structure means any change
    to the file -- including one a parser would treat as equivalent, such as
    key order or comment text -- changes the hash a decision is bound to.
    """
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def identity_snapshot(owners: Owners, identity: str) -> dict:
    """The roles `identity` holds in `owners`, as of now.

    Hash the returned dict with `runner.canonical.content_hash` to get
    `approval_record.membership_snapshot_hash`; that call is left to the
    caller so a snapshot can be taken, and hashed, at the moment a decision
    is made, independently of when the policy file itself last changed.
    """
    held = sorted(role for role, entry in owners.roles.items() if entry["identity"] == identity)
    return {"identity": identity, "roles": held, "taken_at": record.now()}
