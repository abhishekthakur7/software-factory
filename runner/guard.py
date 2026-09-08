"""The single guard seat: the one path for every content-bearing crossing.

`decide` is the sole writer of `guard_decision`, and every call writes
exactly one row -- an allow, a redact, or a deny, never zero and never two
-- so an audit of the table is a complete audit of every crossing attempt.
Deciding is fail-closed at every step: an unreadable policy file, a dead
connection, an unrecognized class, an absent route, a route that will not
admit the joined class, a missing or expired trust-profile activation, or a
secret-rule hit each deny before anything else is even considered, and a
denied secret event's row stores only the rule id and the caller-supplied
safe provenance -- never the payload, the match, or a digest of either that
a search over known secrets could reverse.

`pass_through` is the seat every crossing calls before acting on a
decision's payload: it re-reads the row by id from the database rather than
trusting the in-memory `Decision` object alone, so a hand-built `Decision`
that was never actually persisted, or one whose row denied the operation,
or one bound to a different crossing, is refused rather than honoured.
"""
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

from runner import canonical, governance, owners, record, trust_profile

CROSSINGS = (
    "ingress", "persistence", "display", "sandbox_mount", "logs", "dispatch", "outbox", "export",
)


class GuardUnavailable(Exception):
    """The guard cannot decide right now: the policy is unreadable, or the sink refused the write."""


class GuardRefused(Exception):
    """`pass_through` refuses: no such decision, it did not allow, or it names a different crossing."""


@dataclass(frozen=True)
class Operation:
    crossing: str
    route_id: str
    payload: object  # a str or a Mapping[str, object]
    input_classes: tuple[str, ...]
    source_identity: str
    destination_identity: str
    # Safe metadata only (identities and crossing) -- never content.
    content_provenance: Mapping = field(default_factory=dict)
    ticket_id: int | None = None
    stage_run_id: int | None = None
    sanitizer_rule_hash: str | None = None
    # Echoed back unchanged: ticket/repository text is untrusted instruction
    # and can never widen what the operation is allowed to reach.
    capabilities: Mapping = field(default_factory=dict)


@dataclass(frozen=True)
class Decision:
    id: int
    decision: str  # allow | redact | deny
    reason_codes: tuple[str, ...]
    effective_class: str | None
    payload: object | None  # None whenever decision == "deny"
    capabilities: Mapping


def _project(route: trust_profile.Route, payload: object) -> tuple[object, bool]:
    """The content actually passed, and whether projecting it dropped anything.

    A string payload passes whole (there is no field set to project
    against); a mapping is cut down to the route's declared `fields`
    allowlist, and dropping any key is what turns an `allow` into a
    `redact`.
    """
    if isinstance(payload, Mapping):
        projected = {k: v for k, v in payload.items() if k in route.fields}
        return projected, len(projected) != len(payload)
    return payload, False


def _find_secret(profile: trust_profile.TrustProfile, payload: object) -> str | None:
    if isinstance(payload, Mapping):
        texts = [str(v) for v in payload.values()]
    else:
        texts = [str(payload)]
    for rule in profile.secret_rules:
        if any(rule.compiled.search(text) for text in texts):
            return rule.id
    return None


def _class_admitted(profile: trust_profile.TrustProfile, route: trust_profile.Route, joined: str) -> bool:
    order = profile.classes.order
    return order.index(joined) <= order.index(route.max_class)


def decide(
    conn: sqlite3.Connection,
    operation: Operation,
    *,
    profile_path: Path = trust_profile.DEFAULT_TRUST_PROFILE_PATH,
    owners_path: Path = owners.DEFAULT_OWNERS_PATH,
    now: str | None = None,
) -> Decision:
    now = now or record.now()
    try:
        profile = trust_profile.load_trust_profile(profile_path)
        proposal = governance.propose(profile_path, owners_path)
        conn.execute("SELECT 1")
    except (trust_profile.TrustProfileError, owners.OwnersError, sqlite3.Error, OSError) as exc:
        raise GuardUnavailable(f"guard cannot decide: {exc}") from exc

    reason_codes: list[str] = []
    decision = "deny"
    effective_class: str | None = None
    sanitizer_rule_id: str | None = None
    passed_payload: object | None = None
    allowed_digest: str | None = None
    trust_approval_set_hash: str | None = None

    joined = trust_profile.join(profile, operation.input_classes)
    route = profile.routes.get(operation.route_id)

    if joined is None:
        reason_codes.append("no_valid_join")
    elif route is None:
        reason_codes.append("absent_route")
    elif not _class_admitted(profile, route, joined):
        reason_codes.append("class_not_admitted")
    else:
        activated = governance.activation(conn, proposal, now=now, profile_path=profile_path)
        trust_approval_set_hash = activated.trust_approval_set_hash
        if not activated.active:
            reason_codes.append("inactive_trust_profile")
        else:
            secret_hit = _find_secret(profile, operation.payload)
            if secret_hit is not None:
                reason_codes.append(f"secret:{secret_hit}")
            else:
                effective_class = joined
                if operation.sanitizer_rule_hash is not None:
                    target = trust_profile.resolve_sanitizer(profile, operation.sanitizer_rule_hash, joined)
                    if target is None:
                        reason_codes.append("sanitizer_not_permitted")
                    else:
                        effective_class = target
                        sanitizer_rule_id = operation.sanitizer_rule_hash
                if not reason_codes:
                    passed_payload, dropped = _project(route, operation.payload)
                    decision = "redact" if dropped else "allow"
                    allowed_digest = canonical.content_hash({"content": passed_payload})

    # A secret hit never stores the match, the payload, or any digest of
    # either -- only the rule id above and the caller-supplied provenance,
    # which by the Operation's own contract carries identities and the
    # crossing name and nothing else.
    row = {
        "ticket_id": operation.ticket_id,
        "stage_run_id": operation.stage_run_id,
        "operation": operation.crossing,
        "route_id": operation.route_id,
        "source_identity": operation.source_identity,
        "destination_identity": operation.destination_identity,
        "content_provenance": canonical.canonical_json(dict(operation.content_provenance)).decode(),
        "input_data_class": canonical.canonical_json(list(operation.input_classes)).decode(),
        "effective_data_class": effective_class,
        "trust_profile_hash": proposal.profile_hash,
        "trust_approval_set_hash": trust_approval_set_hash,
        "rule_set_hash": trust_profile.rule_set_hash(profile),
        "allowed_content_digest": allowed_digest,
        "sanitizer_rule_id": sanitizer_rule_id,
        "decision": decision,
        "reason_codes": canonical.canonical_json(reason_codes).decode(),
        "redacted_artefact_id": None,
        "created_at": now,
        "canonical_serialization_version": canonical.SERIALIZATION_VERSION,
    }
    row["content_hash"] = canonical.content_hash(row)
    try:
        row_id = record.insert(conn, "guard_decision", **row)
        conn.commit()
    except sqlite3.Error as exc:
        raise GuardUnavailable(f"guard decision sink refused the write: {exc}") from exc

    return Decision(
        id=row_id,
        decision=row["decision"],
        reason_codes=tuple(reason_codes),
        effective_class=effective_class,
        payload=passed_payload if row["decision"] != "deny" else None,
        capabilities=operation.capabilities,
    )


def pass_through(conn: sqlite3.Connection, decision: Decision, crossing: str) -> object:
    """The content `decision` allowed to pass `crossing`, or `GuardRefused`.

    Re-reads the persisted row rather than trusting `decision` alone: a
    `Decision` built by hand instead of returned from `decide`, one bound
    to a different crossing, or one that denied, is refused exactly the
    same way.
    """
    if not isinstance(decision, Decision):
        raise GuardRefused("pass_through requires a guard Decision, not a raw payload")
    row = record.get(conn, "guard_decision", decision.id)
    if row is None or row["decision"] not in ("allow", "redact") or row["operation"] != crossing:
        raise GuardRefused(f"guard decision {decision.id} does not permit the {crossing!r} crossing")
    return decision.payload
