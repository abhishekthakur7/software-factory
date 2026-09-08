"""Approval records and quorum: the one place a gate's approvals are written and counted.

`record_approval` is the sole writer of `approval_record`: it stamps the
canonical serialisation version and content hash, and refuses a
`trust_profile` approval without an expiry, since that gate's approvals
are mandatory-expiry by contract. `evaluate` answers whether a subject has
quorum right now: for every slot it counts distinct current, unexpired,
approving actors on the identical subject, applies the slot's minimum count
and `distinct_from` separation, and refuses outright when any
`(gate, subject, slot, actor)` has more than one unsuperseded head. Validity
is never stored on a row; it is derived here at each call from the rows and
the clock, so an expired or superseded approval confers nothing without any
row having to change.
"""
import sqlite3
from dataclasses import dataclass, field

from runner import canonical, record, schema
from runner.reviewer_sets import Slot

MANDATORY_EXPIRY_GATES = frozenset({"trust_profile"})


def record_approval(
    conn: sqlite3.Connection,
    *,
    gate: str,
    subject_hash: str,
    slot_id: str,
    actor_identity: str,
    role: str,
    decision: str,
    authority_policy_hash: str,
    membership_snapshot_hash: str,
    attestation_version: str,
    attestation_hash: str,
    decided_at: str | None = None,
    expires_at: str | None = None,
    **fields,
) -> int:
    """Insert one immutable `approval_record` row and return its id.

    `fields` carries the optional columns (`ticket_id`, `scope`,
    `evidence_tuple_id`, `supersedes`, ...); an unknown column name raises
    `ValueError`, as does a gate in `MANDATORY_EXPIRY_GATES` with no
    `expires_at`. The content hash is taken over the full column set, an
    absent optional column hashed as null, so the hash stored on the row is
    recomputable from the row alone.
    """
    if gate in MANDATORY_EXPIRY_GATES and expires_at is None:
        raise ValueError(f"an approval on gate {gate!r} must carry an expiry")
    columns = {column.name for column in schema.table("approval_record").columns}
    unknown = set(fields) - columns
    if unknown:
        raise ValueError(f"approval_record has no column(s) {sorted(unknown)}")
    row = {
        **{name: None for name in columns},
        **fields,
        "gate": gate,
        "subject_hash": subject_hash,
        "slot_id": slot_id,
        "actor_identity": actor_identity,
        "role": role,
        "decision": decision,
        "authority_policy_hash": authority_policy_hash,
        "membership_snapshot_hash": membership_snapshot_hash,
        "attestation_version": attestation_version,
        "attestation_hash": attestation_hash,
        "decided_at": decided_at or record.now(),
        "expires_at": expires_at,
        "canonical_serialization_version": canonical.SERIALIZATION_VERSION,
    }
    row.pop("id")
    row["content_hash"] = canonical.content_hash(row)
    return record.insert(conn, "approval_record", **row)


def current_heads(conn: sqlite3.Connection, gate: str, subject_hash: str) -> list[sqlite3.Row]:
    """Every unsuperseded `approval_record` row on `(gate, subject_hash)`, oldest first."""
    return conn.execute(
        "SELECT * FROM approval_record WHERE gate = ? AND subject_hash = ? "
        "AND id NOT IN (SELECT supersedes FROM approval_record WHERE supersedes IS NOT NULL) "
        "ORDER BY id",
        (gate, subject_hash),
    ).fetchall()


def forked_heads(heads: list[sqlite3.Row]) -> list[tuple[str, str]]:
    """The `(slot_id, actor_identity)` pairs holding more than one unsuperseded head."""
    seen: dict[tuple[str, str], int] = {}
    for row in heads:
        pair = (row["slot_id"], row["actor_identity"])
        seen[pair] = seen.get(pair, 0) + 1
    return sorted(pair for pair, count in seen.items() if count > 1)


def approval_set_hash(rows: list[sqlite3.Row]) -> str:
    """The canonical ordered hash of the qualifying rows' content hashes."""
    return canonical.content_hash({"approvals": sorted(row["content_hash"] for row in rows)})


@dataclass(frozen=True)
class Quorum:
    satisfied: bool
    reasons: tuple[str, ...]
    # The hash of the qualifying rows when satisfied, else None.
    approval_set_hash: str | None
    # slot_id -> the distinct approving actors counted for it.
    actors: dict[str, tuple[str, ...]] = field(default_factory=dict)


def evaluate(
    conn: sqlite3.Connection,
    *,
    gate: str,
    subject_hash: str,
    slots: list[Slot],
    now: str | None = None,
    separation_exempt_identities: frozenset[str] = frozenset(),
) -> Quorum:
    """Whether `slots` all have quorum on `(gate, subject_hash)` at `now`.

    An identity in `separation_exempt_identities` may satisfy two slots
    that `distinct_from` each other; the trust profile's named
    both-trust-roles identity is the one such case. A forked head anywhere
    on the subject refuses quorum for every slot, since a fork means the
    record no longer says which decision is the actor's.
    """
    now = now or record.now()
    heads = current_heads(conn, gate, subject_hash)
    forks = forked_heads(heads)
    if forks:
        return Quorum(False, tuple(f"forked_head:{slot}:{actor}" for slot, actor in forks), None)

    qualifying: list[sqlite3.Row] = []
    actors: dict[str, tuple[str, ...]] = {}
    reasons: list[str] = []
    for slot in slots:
        if not slot.resolved:
            reasons.append(f"unresolved_slot:{slot.slot_id}")
            continue
        slot_rows = [
            row for row in heads
            if row["slot_id"] == slot.slot_id
            and row["decision"] == "approve"
            and (row["expires_at"] is None or row["expires_at"] > now)
        ]
        # One row per distinct actor: a repeated approval by one actor counts once.
        by_actor: dict[str, sqlite3.Row] = {}
        for row in slot_rows:
            by_actor.setdefault(row["actor_identity"], row)
        actors[slot.slot_id] = tuple(sorted(by_actor))
        qualifying.extend(by_actor.values())
        if len(by_actor) < slot.min_count:
            reasons.append(f"insufficient:{slot.slot_id}:{len(by_actor)}<{slot.min_count}")

    for slot in slots:
        for other_id in slot.distinct_from:
            shared = set(actors.get(slot.slot_id, ())) & set(actors.get(other_id, ()))
            shared -= separation_exempt_identities
            if shared:
                reasons.append(f"separation:{slot.slot_id}:{other_id}:{','.join(sorted(shared))}")

    if reasons:
        return Quorum(False, tuple(reasons), None, actors)
    return Quorum(True, (), approval_set_hash(qualifying), actors)
