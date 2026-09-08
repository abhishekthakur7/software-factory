"""The governance-only console: metadata about the trust profile, never its content.

`propose` reads only file metadata -- hashes and role identities -- and
takes no database connection and no payload, so there is structurally
nothing here that could read, persist, or dispatch production content: it
imports neither `runner.guard`, `runner.artefact_registry`, `runner.fs`,
nor `runner.stages`, and it never calls `record.insert` itself (every write
below goes through `runner.approvals.record_approval`, the one place an
`approval_record` row is built). `decide` writes one such row per acting
approver, gated with a mandatory expiry since `trust_profile` is one of
`approvals.MANDATORY_EXPIRY_GATES`. `activation` answers whether the
current approval records satisfy the profile's own slots and separation
rule -- it is the only place that question is asked, so a stage or seat
never has to recompute quorum by hand.
"""
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from runner import approvals, canonical, owners, trust_profile
from runner.reviewer_sets import Slot


@dataclass(frozen=True)
class Proposal:
    """Metadata-only view of a trust profile awaiting activation."""

    profile_hash: str
    authority_policy_hash: str
    subject_hash: str
    # role -> the identity currently holding it, read from owners.yaml.
    trust_role_identities: dict
    route_ids: tuple[str, ...]
    both_trust_roles_identity: str


def propose(
    profile_path: Path = trust_profile.DEFAULT_TRUST_PROFILE_PATH,
    owners_path: Path = owners.DEFAULT_OWNERS_PATH,
) -> Proposal:
    """Build a `Proposal` from the two policy files' metadata alone.

    No database connection and no payload parameter exist on this
    function; there is nothing here it could read, persist, or dispatch
    beyond the two file paths it is given.
    """
    profile = trust_profile.load_trust_profile(profile_path)
    owners_doc = owners.load_owners(owners_path, profile_path)
    profile_hash_value = trust_profile.profile_hash(profile_path)
    authority_hash = owners.authority_policy_hash(owners_path)
    subject_hash = trust_profile.trust_approval_subject(profile_hash_value, authority_hash)
    trust_role_identities = {
        role: owners_doc.roles[role]["identity"] for role in trust_profile.TRUST_ROLES
    }
    return Proposal(
        profile_hash=profile_hash_value,
        authority_policy_hash=authority_hash,
        subject_hash=subject_hash,
        trust_role_identities=trust_role_identities,
        route_ids=tuple(sorted(profile.routes)),
        both_trust_roles_identity=profile.both_trust_roles_identity,
    )


def decide(
    conn: sqlite3.Connection,
    proposal: Proposal,
    *,
    actor_identity: str,
    role: str,
    decision: str,
    expires_at: str,
    attestation_version: str,
    attestation_hash: str,
    owners_path: Path = owners.DEFAULT_OWNERS_PATH,
    profile_path: Path = trust_profile.DEFAULT_TRUST_PROFILE_PATH,
) -> int:
    """Write one `approval_record` for `actor_identity` deciding `proposal`'s subject.

    "Signed" here means the row's own canonical content hash under the
    actor's identity and the given attestation hash -- no cryptographic
    signature exists yet. `owners_path`/`profile_path` let a test decide
    against a tmp copy of the committed files rather than the real ones;
    both default to the committed paths `propose` also defaults to.
    `authority_policy_hash` is recomputed here rather than reused from
    `proposal` so a decision always binds to the owners file as it reads
    right now, and `membership_snapshot_hash` is taken fresh at this call
    (via `owners.identity_snapshot`), independent of that hash, so a role
    assignment and the person holding it at decision time are never
    conflated into one hash.
    """
    owners_doc = owners.load_owners(owners_path, profile_path)
    authority_hash = owners.authority_policy_hash(owners_path)
    snapshot_hash = canonical.content_hash(owners.identity_snapshot(owners_doc, actor_identity))
    slot_id = Slot(source_rule="trust-profile", role=role).slot_id
    return approvals.record_approval(
        conn,
        gate="trust_profile",
        subject_hash=proposal.subject_hash,
        slot_id=slot_id,
        actor_identity=actor_identity,
        role=role,
        decision=decision,
        authority_policy_hash=authority_hash,
        membership_snapshot_hash=snapshot_hash,
        attestation_version=attestation_version,
        attestation_hash=attestation_hash,
        expires_at=expires_at,
        scope=proposal.profile_hash,
    )


@dataclass(frozen=True)
class Activation:
    active: bool
    # The current trust-approval-set hash when active, else None.
    trust_approval_set_hash: str | None
    reasons: tuple[str, ...]


def activation(
    conn: sqlite3.Connection,
    proposal: Proposal,
    now: str | None = None,
    *,
    profile_path: Path = trust_profile.DEFAULT_TRUST_PROFILE_PATH,
) -> Activation:
    """Whether `proposal`'s subject currently has quorum over the profile's own slots.

    The `both_trust_roles_identity` from the proposal is the sole
    separation exemption: it is the only identity permitted to satisfy
    both the security and legal/data-governance slots at once.
    """
    profile = trust_profile.load_trust_profile(profile_path)
    slots = trust_profile.approval_slots(profile)
    quorum = approvals.evaluate(
        conn,
        gate="trust_profile",
        subject_hash=proposal.subject_hash,
        slots=slots,
        now=now,
        separation_exempt_identities=frozenset({proposal.both_trust_roles_identity}),
    )
    return Activation(
        active=quorum.satisfied,
        trust_approval_set_hash=quorum.approval_set_hash,
        reasons=quorum.reasons,
    )
