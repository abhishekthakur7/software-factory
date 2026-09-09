"""The trust profile: the one content-addressed governance policy the guard reads.

`load_trust_profile` parses and validates `trust-profile.yaml` -- the
classification taxonomy and its join/default-deny rules, the admitted
scopes, the secret rules and their bound `rule_set_hash`, the permitted
sanitizer pairs, every route's full field set, the evidence references, and
the two governance approval slots -- raising `TrustProfileError` naming the
first field found missing or inconsistent. `profile_hash` hashes the file's
exact bytes for the same reason `owners.authority_policy_hash` does: the
hash a trust approval binds to must catch any change to the committed file,
not just a change a parser would treat as meaningful. `trust_approval_subject`
is the one place the profile hash and the authority-policy hash are joined
into the subject every `trust_profile` approval is decided against; a
change to either file is a change to the subject, which is exactly what
lets a stale approval set stop satisfying quorum without any row having to
change (see `runner.approvals`).

Every hash here calls `runner.canonical.content_hash`; this module adds no
second hashing routine.
"""
import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

import yaml

from runner import canonical, credentials
from runner.paths import FACTORY_DIR
from runner.reviewer_sets import Slot

DEFAULT_TRUST_PROFILE_PATH = FACTORY_DIR / "config" / "trust-profile.yaml"

# The five routes the walk crosses; `routes` must name exactly these.
ROUTE_IDS = ("hosted_model", "governed_export_display", "github_pr", "slack_digest", "jira_feedback")

# Every field a route must carry: the governance terms of the route, the
# admitted source class, and whether its deliverer is live or a stub.
ROUTE_REQUIRED_FIELDS = (
    "purpose", "fields", "provider", "processing_location", "storage_location",
    "logging_terms", "training_reuse_terms", "subprocessors", "residency",
    "reader_roles", "export_rule", "retention_days", "rule_set_hash",
    "max_class", "deliverer",
)

# The route whose deliverer is real; every other route is a stub, since no
# real deliverer for it exists yet.
LIVE_ROUTE = "hosted_model"

DIGEST_ROUTE = "slack_digest"
DIGEST_FIELDS = ("ticket_id", "tier", "item_kind", "age", "command")

TRUST_ROLES = ("security_approver", "legal_data_governance_approver")


class TrustProfileError(ValueError):
    """`trust-profile.yaml` fails validation, naming the first field found missing or wrong."""


def _require(mapping: Mapping, key: str, where: str):
    if not isinstance(mapping, Mapping) or key not in mapping or mapping[key] in (None, ""):
        raise TrustProfileError(f"trust-profile.yaml: {where} is missing {key!r}")
    return mapping[key]


def _require_list(mapping: Mapping, key: str, where: str) -> list:
    value = _require(mapping, key, where)
    if not isinstance(value, list):
        raise TrustProfileError(f"trust-profile.yaml: {where}.{key} must be a list")
    return value


@dataclass(frozen=True)
class JoinException:
    classes: tuple[str, str]
    result: str


@dataclass(frozen=True)
class ClassTaxonomy:
    # Least to most restrictive.
    order: tuple[str, ...]
    exceptions: tuple[JoinException, ...]
    default_deny: bool


@dataclass(frozen=True)
class SecretRule:
    id: str
    pattern: str
    compiled: re.Pattern = field(compare=False, repr=False)

    def __init__(self, id: str, pattern: str):
        object.__setattr__(self, "id", id)
        object.__setattr__(self, "pattern", pattern)
        object.__setattr__(self, "compiled", re.compile(pattern))


@dataclass(frozen=True)
class Sanitizer:
    rule_hash: str
    source_class: str
    target_class: str


@dataclass(frozen=True)
class ExportRule:
    allowed_formats: tuple[str, ...]
    max_class: str
    # Every class dominance-at-or-below max_class, resolved at load time so
    # `export_permitted` never needs the profile's class order to answer.
    admitted_classes: tuple[str, ...]


@dataclass(frozen=True)
class Route:
    id: str
    purpose: str
    fields: tuple[str, ...]
    provider: str
    processing_location: str
    storage_location: str
    logging_terms: str
    training_reuse_terms: str
    subprocessors: tuple[str, ...]
    residency: str
    reader_roles: tuple[str, ...]
    export_rule: ExportRule
    retention_days: int
    rule_set_hash: str
    max_class: str
    deliverer: str
    operations: tuple[str, ...] = ()
    # The credential roles the trusted runner fetches to serve this route;
    # empty for a route that needs none. Written as `credential_role` in
    # the file, one name or a list.
    credential_roles: tuple[str, ...] = ()


@dataclass(frozen=True)
class ApprovalSlotSpec:
    role: str
    min_count: int
    distinct_from: tuple[str, ...]


@dataclass(frozen=True)
class TrustProfile:
    both_trust_roles_identity: str
    classes: ClassTaxonomy
    admitted_scopes: Mapping[str, tuple[str, ...]]
    secret_rules: tuple[SecretRule, ...]
    sanitizers: tuple[Sanitizer, ...]
    routes: Mapping[str, Route]
    evidence: Mapping[str, str]
    approval_slots: Mapping[str, ApprovalSlotSpec]


def _load_classes(doc: Mapping) -> ClassTaxonomy:
    order = _require_list(doc, "classes", "trust-profile.yaml")
    if not all(isinstance(c, str) and c for c in order):
        raise TrustProfileError("trust-profile.yaml: classes must be a list of non-empty names")
    join_rules = _require(doc, "join_rules", "trust-profile.yaml")
    default_deny = _require(join_rules, "default_deny", "join_rules")
    if default_deny is not True:
        raise TrustProfileError("trust-profile.yaml: join_rules.default_deny must be true")
    exceptions_raw = join_rules.get("exceptions", None)
    if exceptions_raw is None:
        raise TrustProfileError("trust-profile.yaml: join_rules is missing 'exceptions'")
    exceptions = []
    for entry in exceptions_raw:
        pair = entry.get("classes")
        result = entry.get("result")
        if not (isinstance(pair, list) and len(pair) == 2 and result):
            raise TrustProfileError(f"trust-profile.yaml: join_rules.exceptions entry is malformed: {entry!r}")
        exceptions.append(JoinException(classes=(pair[0], pair[1]), result=result))
    return ClassTaxonomy(order=tuple(order), exceptions=tuple(exceptions), default_deny=True)


def _load_admitted_scopes(doc: Mapping) -> dict:
    scopes = _require(doc, "admitted_scopes", "trust-profile.yaml")
    result = {}
    for key in ("repositories", "jira_projects", "confluence_spaces"):
        result[key] = tuple(_require_list(scopes, key, "admitted_scopes"))
    return result


def _load_secret_rules(doc: Mapping) -> tuple[SecretRule, ...]:
    entries = _require_list(doc, "secret_rules", "trust-profile.yaml")
    rules = []
    for entry in entries:
        rid = _require(entry, "id", "secret_rules entry")
        pattern = _require(entry, "pattern", "secret_rules entry")
        rules.append(SecretRule(id=rid, pattern=pattern))
    return tuple(rules)


def rule_set_hash(profile: "TrustProfile") -> str:
    """The canonical hash every route's `rule_set_hash` field must equal."""
    return canonical.content_hash(
        {"secret_rules": [{"id": r.id, "pattern": r.pattern} for r in profile.secret_rules]}
    )


def _load_sanitizers(doc: Mapping, order: tuple[str, ...]) -> tuple[Sanitizer, ...]:
    entries = _require_list(doc, "sanitizers", "trust-profile.yaml")
    sanitizers = []
    for entry in entries:
        rule_hash = _require(entry, "rule_hash", "sanitizers entry")
        source_class = _require(entry, "source_class", "sanitizers entry")
        target_class = _require(entry, "target_class", "sanitizers entry")
        if source_class not in order or target_class not in order:
            raise TrustProfileError(
                f"trust-profile.yaml: sanitizers entry names a class outside the taxonomy: {entry!r}"
            )
        sanitizers.append(Sanitizer(rule_hash=rule_hash, source_class=source_class, target_class=target_class))
    return tuple(sanitizers)


def _load_export_rule(raw: Mapping, order: tuple[str, ...], where: str) -> ExportRule:
    if not isinstance(raw, Mapping) or "allowed_formats" not in raw:
        raise TrustProfileError(f"trust-profile.yaml: {where} is missing 'allowed_formats'")
    allowed_formats = raw["allowed_formats"]
    if not isinstance(allowed_formats, list):
        raise TrustProfileError(f"trust-profile.yaml: {where}.allowed_formats must be a list")
    max_class = _require(raw, "max_class", where)
    if max_class not in order:
        raise TrustProfileError(f"trust-profile.yaml: {where}.max_class names an unknown class {max_class!r}")
    ceiling = order.index(max_class)
    admitted_classes = tuple(order[: ceiling + 1])
    return ExportRule(allowed_formats=tuple(allowed_formats), max_class=max_class, admitted_classes=admitted_classes)


def _load_credential_roles(raw: Mapping, where: str) -> tuple[str, ...]:
    value = raw.get("credential_role")
    roles = () if value is None else (value,) if isinstance(value, str) else tuple(value)
    unknown = [role for role in roles if role not in credentials.ROLES]
    if unknown:
        raise TrustProfileError(f"trust-profile.yaml: {where}.credential_role names unknown role(s) {unknown}")
    return roles


def _load_routes(doc: Mapping, order: tuple[str, ...], expected_rule_set_hash: str) -> dict:
    routes_raw = _require(doc, "routes", "trust-profile.yaml")
    missing_routes = [r for r in ROUTE_IDS if r not in routes_raw]
    if missing_routes:
        raise TrustProfileError(f"trust-profile.yaml: routes is missing {missing_routes}")
    routes = {}
    for route_id, raw in routes_raw.items():
        where = f"routes.{route_id}"
        for field_name in ROUTE_REQUIRED_FIELDS:
            _require(raw, field_name, where)
        if raw["max_class"] not in order:
            raise TrustProfileError(f"trust-profile.yaml: {where}.max_class names an unknown class")
        if raw["rule_set_hash"] != expected_rule_set_hash:
            raise TrustProfileError(
                f"trust-profile.yaml: {where}.rule_set_hash does not match the canonical hash of secret_rules"
            )
        expected_deliverer = "live" if route_id == LIVE_ROUTE else "stub"
        if raw["deliverer"] != expected_deliverer:
            raise TrustProfileError(
                f"trust-profile.yaml: {where}.deliverer must be {expected_deliverer!r} for this route"
            )
        if route_id == "github_pr":
            operations = tuple(raw.get("operations", ()))
            if operations != ("pr_create", "pr_update"):
                raise TrustProfileError(
                    "trust-profile.yaml: routes.github_pr.operations must be [pr_create, pr_update]"
                )
        else:
            operations = ()
        if route_id == DIGEST_ROUTE and tuple(raw["fields"]) != DIGEST_FIELDS:
            raise TrustProfileError(
                f"trust-profile.yaml: routes.{DIGEST_ROUTE}.fields must be exactly {list(DIGEST_FIELDS)}"
            )
        routes[route_id] = Route(
            id=route_id,
            purpose=raw["purpose"],
            fields=tuple(raw["fields"]),
            provider=raw["provider"],
            processing_location=raw["processing_location"],
            storage_location=raw["storage_location"],
            logging_terms=raw["logging_terms"],
            training_reuse_terms=raw["training_reuse_terms"],
            subprocessors=tuple(raw["subprocessors"]),
            residency=raw["residency"],
            reader_roles=tuple(raw["reader_roles"]),
            export_rule=_load_export_rule(raw["export_rule"], order, f"{where}.export_rule"),
            retention_days=raw["retention_days"],
            rule_set_hash=raw["rule_set_hash"],
            max_class=raw["max_class"],
            deliverer=raw["deliverer"],
            operations=operations,
            credential_roles=_load_credential_roles(raw, where),
        )
    return routes


def _load_evidence(doc: Mapping) -> dict:
    evidence = _require(doc, "evidence", "trust-profile.yaml")
    return {
        "provider_terms_dpa_ref": _require(evidence, "provider_terms_dpa_ref", "evidence"),
        "security_assessment_ref": _require(evidence, "security_assessment_ref", "evidence"),
    }


def _load_approval_slots(doc: Mapping) -> dict:
    slots_raw = _require(doc, "approval_slots", "trust-profile.yaml")
    missing = [role for role in TRUST_ROLES if role not in slots_raw]
    if missing:
        raise TrustProfileError(f"trust-profile.yaml: approval_slots is missing {missing}")
    slots = {}
    for role in TRUST_ROLES:
        raw = slots_raw[role]
        min_count = _require(raw, "min_count", f"approval_slots.{role}")
        distinct_from = _require_list(raw, "distinct_from", f"approval_slots.{role}")
        slots[role] = ApprovalSlotSpec(role=role, min_count=min_count, distinct_from=tuple(distinct_from))
    return slots


def load_trust_profile(path: Path = DEFAULT_TRUST_PROFILE_PATH) -> TrustProfile:
    """Parse and validate `path`, raising `TrustProfileError` naming the first problem found."""
    try:
        text = Path(path).read_text()
    except OSError as exc:
        raise TrustProfileError(f"trust-profile.yaml: cannot read {path}: {exc}") from exc
    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise TrustProfileError(f"trust-profile.yaml: invalid YAML in {path}: {exc}") from exc
    if not isinstance(doc, dict):
        raise TrustProfileError(f"trust-profile.yaml: {path} is not a mapping")

    identity = _require(doc, "both_trust_roles_identity", "trust-profile.yaml")
    classes = _load_classes(doc)
    admitted_scopes = _load_admitted_scopes(doc)
    secret_rules = _load_secret_rules(doc)
    sanitizers = _load_sanitizers(doc, classes.order)
    evidence = _load_evidence(doc)
    approval_slots = _load_approval_slots(doc)

    profile_without_routes = TrustProfile(
        both_trust_roles_identity=identity,
        classes=classes,
        admitted_scopes=admitted_scopes,
        secret_rules=secret_rules,
        sanitizers=sanitizers,
        routes={},
        evidence=evidence,
        approval_slots=approval_slots,
    )
    expected_rule_set_hash = rule_set_hash(profile_without_routes)
    routes = _load_routes(doc, classes.order, expected_rule_set_hash)

    return TrustProfile(
        both_trust_roles_identity=identity,
        classes=classes,
        admitted_scopes=admitted_scopes,
        secret_rules=secret_rules,
        sanitizers=sanitizers,
        routes=routes,
        evidence=evidence,
        approval_slots=approval_slots,
    )


def profile_hash(path: Path = DEFAULT_TRUST_PROFILE_PATH) -> str:
    """SHA-256 hex digest of the trust profile's exact committed bytes.

    Same rationale as `owners.authority_policy_hash`: the hash a trust
    approval binds to must catch any change to the committed file, not
    only a change a parser would treat as meaningful.
    """
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def trust_approval_subject(profile_hash_value: str, authority_policy_hash: str) -> str:
    """The canonical hash every `trust_profile` approval is decided against.

    Binding both hashes into one subject means a change to either file --
    the profile or the owners file it depends on -- creates a new subject,
    so a previously satisfying approval set stops satisfying this one
    without any row needing to change.
    """
    return canonical.content_hash({"trust_profile_hash": profile_hash_value, "authority_policy_hash": authority_policy_hash})


def join(profile: TrustProfile, classes: tuple[str, ...]) -> str | None:
    """The joined class of `classes`, or `None` when the rules cannot derive one.

    An unrecognized class denies outright (`default_deny`). Two classes
    matching a named exception resolve to its result; otherwise the join is
    the most dominant (highest-index) class among the inputs.
    """
    if not classes:
        return None
    order = profile.classes.order
    if any(c not in order for c in classes):
        return None
    if len(classes) == 2:
        for exc in profile.classes.exceptions:
            if frozenset(exc.classes) == frozenset(classes):
                return exc.result
    return max(classes, key=order.index)


def resolve_sanitizer(
    profile: TrustProfile, rule_hash: str, source_class: str, target_class: str | None = None
) -> str | None:
    """The permitted target class for `rule_hash` from `source_class`, or `None`.

    With `target_class` given, this confirms that exact triple is a
    registered pair. Left as
    `None`, it looks up whichever target the rule is registered for from
    `source_class` -- the form the guard uses, since an `Operation` names
    only the sanitizer it invoked and the class it is downgrading from,
    never the target it expects.
    """
    matches = [
        s for s in profile.sanitizers
        if s.rule_hash == rule_hash and s.source_class == source_class
        and (target_class is None or s.target_class == target_class)
    ]
    if len(matches) != 1:
        return None
    return matches[0].target_class


def approval_slots(profile: TrustProfile) -> list[Slot]:
    """The two governance requirement slots, built for `approvals.evaluate`."""
    specs = [profile.approval_slots[role] for role in TRUST_ROLES]
    bare = [Slot(source_rule="trust-profile", role=spec.role, min_count=spec.min_count) for spec in specs]
    slot_id_by_role = {slot.role: slot.slot_id for slot in bare}
    return [
        Slot(
            source_rule="trust-profile",
            role=slot.role,
            min_count=slot.min_count,
            distinct_from=tuple(slot_id_by_role[role] for role in spec.distinct_from),
        )
        for slot, spec in zip(bare, specs)
    ]


def export_permitted(route: Route, request: Mapping) -> bool:
    """Whether `request` (`{"format": ..., "class": ...}`) satisfies `route.export_rule`."""
    rule = route.export_rule
    return request.get("format") in rule.allowed_formats and request.get("class") in rule.admitted_classes


def retention_expired(route: Route, created_at: str, now: str) -> bool:
    """Whether `created_at` is past `route.retention_days` as of `now`.

    Both timestamps are the record's ISO-8601 UTC format
    (`runner.record.now`); comparing them as strings would break across a
    change in fractional-second precision, so they are parsed instead.
    """
    from datetime import datetime, timedelta

    created = datetime.fromisoformat(created_at)
    current = datetime.fromisoformat(now)
    return current >= created + timedelta(days=route.retention_days)
