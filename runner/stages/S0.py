"""S0: the mechanical intake gate -- Jira read, field gate, lookups, sensitive-path detection, exclusion, and scrutiny.

S0 is scripts only, never an agent: every step below reads a section 8
config table or the ticket's own fields and either stamps a ticket column,
applies a transition directly, or opens the one `eligibility` queue item a
human decides. `PASS_EVENT` stays `None` for the same reason the stub it
replaces gave: a plain pass leaves `intake` only through `gates.intake_gate`
once a human grants eligibility, so `run_stage` must not apply anything on
its own. A lookup failure or an exclusion hit is not that kind of wait,
though -- both are mechanical rejections S0 decides for itself, so this
driver applies `s0_reject`/`s0_exclusion` directly rather than leaving
either for a gate that would never fire it.

For a ticket sourced from Jira, the mechanical gate runs before any of
that: `_run_jira_intake` reads the linked issue (or, once one already
carries a `ticket_source` artefact, reuses its own front matter instead
of reading again), runs `runner.checks.intake_fields` over it, and --
only on the first read -- classifies and redacts the payload through the
guard before ever writing it to disk. Every other `source_kind` keeps the
stand-in `run_stub` write this driver always used.
"""
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import yaml

from runner import artefact_registry, governance, guard, owners, queue, record, transitions, trust_profile
from runner.checks import exclusion, intake_fields
from runner.fs import write_text
from runner.paths import FACTORY_DIR, RUNS_DIR
from runner.readers import atlassian
from runner.reviewer_sets import match_sensitive_path
from runner.stages._common import run_stub

ARTEFACT_KIND = "ticket_source"
PASS_EVENT = None

DEFAULT_SERVICE_TIERS_PATH = FACTORY_DIR / "config" / "service-tiers.yaml"
DEFAULT_TICKET_TYPES_PATH = FACTORY_DIR / "config" / "ticket-types.yaml"

# The field gate's mapping when it runs over an already-registered
# `ticket_source` artefact's own front matter rather than a fresh Jira
# payload: the artefact's keys already carry these logical names, so the
# mapping is the identity (`issue_type` alone reads `jira_issue_type`,
# the front matter's own name for it).
_FRONT_MATTER_FIELD_NAMES = {
    "acceptance_criteria": "acceptance_criteria",
    "owner": "owner",
    "parent_link": "parent_link",
    "confluence_link": "confluence_link",
    "issue_type": "jira_issue_type",
}

# S0's Jira read is content-bearing ingress from an outside system, the
# same crossing every other such read is decided and passed through under.
_JIRA_INTAKE_CROSSING = "ingress"

# A path-like token: at least one "/" with the usual filename characters
# either side. The lax scan S0 runs over a ticket's title before any real
# diff exists (see the module docstring on `runner.checks.exclusion`).
_PATH_TOKEN_RE = re.compile(r"[\w][\w./-]*/[\w./-]+")


class S0LookupRefused(Exception):
    """A service, ticket-type, or provisional-tier lookup has no answer in the section 8 tables."""


def load_service_tiers(path: Path = DEFAULT_SERVICE_TIERS_PATH) -> dict:
    """`service-tiers.yaml`'s `services` mapping: service name to `{tier, language, repositories}`."""
    doc = yaml.safe_load(Path(path).read_text()) or {}
    return doc.get("services", {}) or {}


def load_ticket_types(path: Path = DEFAULT_TICKET_TYPES_PATH) -> dict:
    """`ticket-types.yaml`, parsed whole: `small_feature_max_points`, `types`, `provisional_tier`."""
    return yaml.safe_load(Path(path).read_text()) or {}


def _candidate_paths(text: str | None) -> list[str]:
    """Path-like tokens found in `text`, the S0-time stand-in for a real diff's touched paths."""
    return _PATH_TOKEN_RE.findall(text or "")


@dataclass(frozen=True)
class SensitivityMatch:
    """One sensitive-path hit: the governing glob, its configured owner, and whether this check is authoritative.

    `authoritative` is `False` for S0's own candidate detection over ticket
    text and `True` for a later confirmation over an actual diff (S5); the
    matching rule is identical either way -- only the caller's confidence
    in the path list differs.
    """

    glob: str
    owner: str
    authoritative: bool


def sensitivity_match(
    paths: list[str], *, authoritative: bool, sensitive_paths: dict[str, str] | None = None
) -> SensitivityMatch | None:
    """The first `sensitive-paths.yaml` match among `paths`, or `None`."""
    sensitive_paths = sensitive_paths if sensitive_paths is not None else exclusion.load_sensitive_paths()
    for path in paths:
        found = match_sensitive_path(sensitive_paths, path)
        if found is not None:
            glob, owner = found
            return SensitivityMatch(glob=glob, owner=owner, authoritative=authoritative)
    return None


def _ticket_source_front_matter(artefact: sqlite3.Row | None) -> dict:
    """The YAML front matter of a registered `ticket_source` artefact, or `{}` when there is none or it carries none."""
    if artefact is None:
        return {}
    text = Path(artefact["path"]).read_text()
    if not text.startswith("---"):
        return {}
    _, _, rest = text.partition("---\n")
    front_matter_text, marker, _ = rest.partition("\n---")
    if not marker:
        return {}
    try:
        parsed = yaml.safe_load(front_matter_text)
    except yaml.YAMLError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _record_check(conn: sqlite3.Connection, stage_run_id: int, finding: intake_fields.Finding) -> None:
    record.insert(
        conn, "check_result", stage_run_id=stage_run_id, check_name=finding.check_name,
        result=finding.result, summary=finding.detail,
    )


def _atlassian_reader(transport) -> "atlassian.AtlassianReader | None":
    """An `AtlassianReader` over `transport` when one is given (every routine test); otherwise the real endpoint, or `None` when it names none yet."""
    if transport is not None:
        return atlassian.AtlassianReader(transport)
    base_url = atlassian.endpoint()
    if base_url is None:
        return None
    return atlassian.AtlassianReader(atlassian.HttpTransport(base_url))


def _source_repository_class(profile: trust_profile.TrustProfile, service_config: dict) -> str | None:
    """The joined data class of the ticket's service's own repositories, or `None` when none of them resolve one."""
    repositories = service_config.get("repositories") or []
    classes = tuple(
        c for c in (trust_profile.repository_class(profile, r) for r in repositories) if c is not None
    )
    if not classes:
        return None
    return trust_profile.join(profile, classes)


def _label_field(labels) -> str | None:
    """The one label `_ticket_type_from_jira` cares about: `docs` if the issue carries it, else the first label, else `None`."""
    labels = labels or []
    if "docs" in labels:
        return "docs"
    return labels[0] if labels else None


def _ticket_source_front_matter_from_redacted(redacted: dict, *, jira_fields: dict) -> dict:
    """The `ticket_source` artefact's front matter, mapping the guard's redacted (still raw-keyed) payload back to logical names."""
    return {
        "jira_issue_type": redacted.get(jira_fields["issue_type"]),
        "estimate": redacted.get("estimate"),
        "label": _label_field(redacted.get("labels")),
        "owner": redacted.get(jira_fields["owner"]),
        "parent_link": redacted.get(jira_fields["parent_link"]),
        "confluence_link": redacted.get(jira_fields["confluence_link"]),
        "acceptance_criteria": redacted.get(jira_fields["acceptance_criteria"]),
    }


def _write_ticket_source_artefact(
    conn: sqlite3.Connection, ticket: sqlite3.Row, stage_run_id: int, runs_dir: Path,
    front_matter: dict, redacted: dict, *, guard_decision_id: int, prior: sqlite3.Row | None,
) -> None:
    """Register the redacted Jira read as the ticket's `ticket_source` artefact, superseding `prior`."""
    body = (
        f"## Summary\n\n{redacted.get('summary') or ''}\n\n"
        f"## Description\n\n{redacted.get('description') or ''}\n\n"
        f"## Acceptance criteria\n\n{front_matter.get('acceptance_criteria') or ''}\n"
    )
    text = "---\n" + yaml.safe_dump(front_matter, sort_keys=False) + "---\n\n" + body
    out_dir = runs_dir / "tickets" / str(ticket["id"]) / "runs" / str(stage_run_id) / "out"
    path = out_dir / f"{ARTEFACT_KIND}.md"
    write_text(path, text)
    artefact_registry.register(
        conn, ticket_id=ticket["id"], kind=ARTEFACT_KIND, path=path, stage_run_id=stage_run_id,
        supersedes=prior["id"] if prior is not None else None, guard_decision_id=guard_decision_id,
    )


def _run_jira_intake(
    conn: sqlite3.Connection, ticket: sqlite3.Row, stage_run_id: int, runs_dir: Path, *,
    ticket_types: dict, service_tiers: dict, prior_source_artefact: sqlite3.Row | None, transport,
) -> tuple[str, str] | None:
    """The Jira intake leg for a `source_kind == 'jira'` ticket, or `None` to fall through to the ordinary lookup flow.

    A ticket that already carries a `ticket_source` artefact was already
    read and redacted once; this call re-runs only the field gate, over
    that artefact's own front matter, so a second `S0.run` (a retried
    attempt, or the seeded-fixture path the routine suite drives) never
    reaches the network. A ticket with no artefact yet does the real read:
    the field gate first, over the raw payload, then the guard's classify-
    and-redact, and only then the artefact is written -- so a gate
    rejection or a guard denial never leaves a `ticket_source` behind.
    """
    ticket_id = ticket["id"]
    if prior_source_artefact is not None:
        front_matter = _ticket_source_front_matter(prior_source_artefact)
        finding = intake_fields.check(front_matter, field_names=_FRONT_MATTER_FIELD_NAMES)
        _record_check(conn, stage_run_id, finding)
        if finding.result == "fail":
            transitions.apply(conn, ticket_id, "s0_reject")
            return ("fail", "structural")
        return None

    reader = _atlassian_reader(transport)
    if reader is None:
        _record_check(
            conn, stage_run_id,
            intake_fields.Finding("atlassian_read", "fail", "sandbox.yaml names no atlassian_read endpoint yet"),
        )
        # An unreachable source is the host's problem, not the ticket's: the
        # ticket stays in intake for a retry once the endpoint exists.
        return ("fail", "infrastructure")

    issue = reader.read_issue(ticket["source_ref"])
    finding = intake_fields.check(issue, field_names=ticket_types["jira_fields"])
    _record_check(conn, stage_run_id, finding)
    if finding.result == "fail":
        transitions.apply(conn, ticket_id, "s0_reject")
        return ("fail", "structural")

    profile = trust_profile.load_trust_profile()
    service_config = service_tiers.get(ticket["service"]) or {}
    source_class = _source_repository_class(profile, service_config)
    if source_class is None:
        _record_check(
            conn, stage_run_id,
            intake_fields.Finding("ticket_source_guard", "fail", "no configured data class for the ticket's repositories"),
        )
        transitions.apply(conn, ticket_id, "s0_reject")
        return ("fail", "structural")

    decision = guard.decide(conn, guard.Operation(
        crossing=_JIRA_INTAKE_CROSSING, route_id="atlassian_read", payload=issue, input_classes=(source_class,),
        source_identity="atlassian", destination_identity="factory_s0", ticket_id=ticket_id,
        stage_run_id=stage_run_id,
        content_provenance={
            "source_identity": "atlassian", "destination_identity": "factory_s0", "crossing": _JIRA_INTAKE_CROSSING,
        },
    ))
    if decision.decision == "deny":
        _record_check(
            conn, stage_run_id,
            intake_fields.Finding(
                "ticket_source_guard", "fail", "guard denied the Jira read: " + ",".join(decision.reason_codes),
            ),
        )
        transitions.apply(conn, ticket_id, "s0_reject")
        return ("fail", "structural")
    redacted = guard.pass_through(conn, decision, _JIRA_INTAKE_CROSSING)

    record.update(conn, "ticket", ticket_id, data_class=decision.effective_class)

    front_matter = _ticket_source_front_matter_from_redacted(redacted, jira_fields=ticket_types["jira_fields"])
    _write_ticket_source_artefact(
        conn, ticket, stage_run_id, runs_dir, front_matter, redacted,
        guard_decision_id=decision.id, prior=prior_source_artefact,
    )
    return None


def _ticket_type_from_jira(front_matter: dict, *, max_points: int) -> str:
    """Bug -> `bug`; Story -> `small_feature` at or under `max_points`, else `feature`; Task -> `config_or_docs`/`refactor` by label; Epic refuses."""
    issue_type = front_matter.get("jira_issue_type")
    if issue_type == "Bug":
        return "bug"
    if issue_type == "Story":
        estimate = front_matter.get("estimate")
        if estimate is not None and estimate <= max_points:
            return "small_feature"
        return "feature"
    if issue_type == "Task":
        return "config_or_docs" if front_matter.get("label") == "docs" else "refactor"
    if issue_type == "Epic":
        raise S0LookupRefused("needs child tickets")
    raise S0LookupRefused("no ticket type available")


def _lookup(
    conn: sqlite3.Connection,
    ticket: sqlite3.Row,
    *,
    service_tiers: dict,
    ticket_types: dict,
    prior_source_artefact: sqlite3.Row | None,
) -> tuple[str, str, str]:
    """`(service_tier, ticket_type, tier_provisional)`, raising `S0LookupRefused` naming the first failure."""
    service_config = service_tiers.get(ticket["service"]) if ticket["service"] else None
    if service_config is None:
        raise S0LookupRefused("service not tiered")
    service_tier = service_config["tier"]

    ticket_type = ticket["ticket_type"]
    if ticket_type is None:
        front_matter = _ticket_source_front_matter(prior_source_artefact)
        max_points = ticket_types.get("small_feature_max_points", 3)
        ticket_type = _ticket_type_from_jira(front_matter, max_points=max_points)

    matrix = ticket_types.get("provisional_tier", {})
    tier_provisional = (matrix.get(service_tier) or {}).get(ticket_type)
    if tier_provisional is None:
        raise S0LookupRefused(f"no provisional tier for service tier {service_tier!r} and ticket type {ticket_type!r}")

    return service_tier, ticket_type, tier_provisional


def _render_scrutiny(ticket: sqlite3.Row, match: SensitivityMatch | None, *, ticket_types: dict) -> str:
    """The rendered scrutiny paragraph for `ticket`'s type, or `""` when the type is unmapped or its template is empty."""
    type_config = (ticket_types.get("types") or {}).get(ticket["ticket_type"])
    if type_config is None:
        return ""
    template = type_config.get("scrutiny_template") or ""
    if not template.strip():
        return ""
    sensitive_match = "none" if match is None else f"{match.glob} (owner {match.owner})"
    return template.format(
        title=ticket["title"] or "",
        ticket_type=ticket["ticket_type"],
        tier=ticket["tier_provisional"],
        sensitive_match=sensitive_match,
    ).strip()


def governance_valid(
    conn: sqlite3.Connection,
    ticket: sqlite3.Row,
    *,
    now: str | None = None,
    profile_path: Path = trust_profile.DEFAULT_TRUST_PROFILE_PATH,
    owners_path: Path = owners.DEFAULT_OWNERS_PATH,
) -> list[str]:
    """The reasons `ticket`'s current governance state fails to authorise an eligibility decision, or `[]` when valid.

    Every reason is checked independently and fail-closed: the ticket's
    stamped `trust_profile_hash` must equal the committed profile's current
    hash (`unauthorised`), the profile's own approval quorum must be active
    as of `now` (`expiry`), the ticket's source must fall inside the
    profile's admitted scopes (`wrong source scope`), and the profile must
    both load and still name the `hosted_model` route the walk depends on
    (`invalid route`) -- a profile that fails to load is caught here rather
    than raised, since a broken policy file is exactly the situation an
    eligibility decision must refuse against, not crash on. `profile_path`/
    `owners_path` default to the committed files, the same as every other
    governance call in this codebase, and exist so a test can exercise a
    deliberately broken profile without touching the committed one.
    """
    try:
        proposal = governance.propose(profile_path, owners_path)
        profile = trust_profile.load_trust_profile(profile_path)
    except (trust_profile.TrustProfileError, owners.OwnersError):
        return ["invalid route"]

    reasons: list[str] = []
    if "hosted_model" not in profile.routes:
        reasons.append("invalid route")
    if ticket["trust_profile_hash"] != proposal.profile_hash:
        reasons.append("unauthorised")
    if not governance.activation(conn, proposal, now=now, profile_path=profile_path).active:
        reasons.append("expiry")
    if not _source_in_scope(ticket, profile.admitted_scopes):
        reasons.append("wrong source scope")
    return reasons


def _source_in_scope(ticket: sqlite3.Row, admitted_scopes) -> bool:
    """Whether `ticket`'s Jira project and target repositories all fall inside the trust profile's `admitted_scopes`."""
    if ticket["source_kind"] == "jira":
        project = (ticket["source_ref"] or "").split("-")[0]
        if project not in admitted_scopes["jira_projects"]:
            return False
    if ticket["service"] is not None:
        service_config = load_service_tiers().get(ticket["service"], {})
        repositories = service_config.get("repositories", [])
        if any(repository not in admitted_scopes["repositories"] for repository in repositories):
            return False
    return True


def run(
    conn: sqlite3.Connection,
    ticket: sqlite3.Row,
    stage_run_id: int,
    runs_dir: Path = RUNS_DIR,
    *,
    service_tiers: dict | None = None,
    ticket_types: dict | None = None,
    sensitive_paths: dict[str, str] | None = None,
    exclusions: dict | None = None,
    transport=None,
) -> str | tuple[str, str]:
    """Run S0's Jira intake, lookups, sensitive-path check, exclusion gate, and scrutiny fill for `ticket`, in that order.

    A `source_kind == "jira"` ticket runs `_run_jira_intake` first: a
    field-gate or guard-denial failure there rejects the ticket
    (`s0_reject`) and returns immediately, the same exit a lookup failure
    takes below. Every other `source_kind` gets the stand-in `run_stub`
    write it always got. A lookup failure rejects the ticket (`s0_reject`)
    and returns `("fail", "structural")`; a sensitive-path candidate
    raises `tier_final` to `heavy` before the exclusion gate runs, so a
    sensitive-path exclusion and a matrix-eligibility exclusion are both
    decided by the same check; either kind of exclusion applies
    `s0_exclusion` and returns `"fail"`. A ticket that clears both gets
    its scrutiny paragraph filled and one `eligibility` item opened, unless
    the rendered paragraph is empty, in which case it stays in `intake`
    with nothing queued. The keyword-only config parameters default to
    the committed files; `run_stage` never passes them, so they exist only
    for a test that needs a config a real run would never see. `transport`
    is the Jira reader's own injectable transport, real in production and
    a fake in the routine suite.
    """
    ticket_id = ticket["id"]
    # Read before either branch below writes a new one: a pre-registered
    # ticket_source carries the Jira front matter this run's lookup and
    # (for a jira ticket) intake gate both need, and a fresh write would
    # otherwise already have replaced it.
    prior_source_artefact = artefact_registry.latest(conn, ticket_id, ARTEFACT_KIND)

    service_tiers = service_tiers if service_tiers is not None else load_service_tiers()
    ticket_types = ticket_types if ticket_types is not None else load_ticket_types()
    sensitive_paths = sensitive_paths if sensitive_paths is not None else exclusion.load_sensitive_paths()
    exclusions = exclusions if exclusions is not None else exclusion.load_exclusions()

    if ticket["source_kind"] == "jira":
        jira_failure = _run_jira_intake(
            conn, ticket, stage_run_id, runs_dir, ticket_types=ticket_types, service_tiers=service_tiers,
            prior_source_artefact=prior_source_artefact, transport=transport,
        )
        if jira_failure is not None:
            return jira_failure
        ticket = record.get(conn, "ticket", ticket_id)
        prior_source_artefact = artefact_registry.latest(conn, ticket_id, ARTEFACT_KIND)
    else:
        run_stub(conn, ticket, "S0", stage_run_id, ARTEFACT_KIND, runs_dir)

    try:
        service_tier, ticket_type, tier_provisional = _lookup(
            conn, ticket, service_tiers=service_tiers, ticket_types=ticket_types,
            prior_source_artefact=prior_source_artefact,
        )
    except S0LookupRefused:
        transitions.apply(conn, ticket_id, "s0_reject")
        return ("fail", "structural")

    stamped = {}
    if ticket["service_tier"] is None:
        stamped["service_tier"] = service_tier
    if ticket["ticket_type"] is None:
        stamped["ticket_type"] = ticket_type
    if ticket["tier_provisional"] is None:
        stamped["tier_provisional"] = tier_provisional
    if stamped:
        record.update(conn, "ticket", ticket_id, **stamped)
        ticket = record.get(conn, "ticket", ticket_id)

    candidates = _candidate_paths(ticket["title"])
    match = sensitivity_match(candidates, authoritative=False, sensitive_paths=sensitive_paths)
    if match is not None:
        record.update(conn, "ticket", ticket_id, tier_final="heavy")
        ticket = record.get(conn, "ticket", ticket_id)

    service_config = service_tiers.get(ticket["service"], {})
    matrix_reasons = exclusion.eligible(
        {"ticket_type": ticket["ticket_type"], "repository_count": 1, "service_count": 1}, service_config,
    )
    surfaces = exclusion.surfaces_in_text(ticket["title"] or "", exclusions=exclusions)
    surfaces |= exclusion.surfaces_in_paths(candidates, exclusions=exclusions, sensitive_paths=sensitive_paths)

    if match is not None or matrix_reasons or surfaces:
        transitions.apply(conn, ticket_id, "s0_exclusion")
        return "fail"

    scrutiny = _render_scrutiny(ticket, match, ticket_types=ticket_types)
    if scrutiny:
        record.update(conn, "ticket", ticket_id, scrutiny_requested=scrutiny)
        queue.open_item(conn, ticket_id=ticket_id, kind="eligibility", stage="S0", tier=ticket["tier_provisional"])
    return "pass"
