"""Pure checks over a parsed `brief` artefact, plus the counts and tier arithmetic the context gathering stage's driver stamps from them.

Every function here takes data the driver already collected -- the parsed
`artefacts.Artefact`, the `impact_scan` payload, the worktree's own path
list, whether a fresh `caller` index entry was read -- and returns a
`Finding` or a plain value; writing a `check_result` row from a `Finding`,
applying an exclusion, and touching the ticket record all stay the
driver's job, the same split `runner/checks/exclusion.py` uses.

Two conventions the brief's tables carry that no column name states
outright: a row's "service" is never a table column, so a service is
identified from an outbound row's `dependency` (a "groupId:artifactId"
key resolved through the registered `impact_scan` payload) or an inbound
row's `dependency` (the caller service's own name, asserted directly);
and an `unknown`-coverage impact row that changes eligibility or names a
new or changed public contract says so in its own `blind_spots` cell,
naming "eligibility" or "public contract", rather than in a column of its
own.
"""
from dataclasses import dataclass

from runner import artefacts

# Live-state words banned everywhere outside "Blind spots" -- a lax first
# pass over the vocabulary a real brief is likely to use; the owner tunes
# this list once real briefs show what else needs catching.
LIVE_STATE_WORDS: tuple[str, ...] = ("SLI", "error budget", "dashboard", "logs show", "in production")

DIRECTIONS: tuple[str, ...] = ("inbound", "outbound")

# blind_spots text naming either of these on an unknown-coverage impact
# row is what marks that row as changing eligibility or a public
# contract, per the module docstring's second convention.
_ELIGIBILITY_BLIND_SPOT_MARKERS: tuple[str, ...] = ("eligibility", "public contract")

_SERVICE_TIER_ORDER: tuple[str, ...] = ("T1", "T2", "T3")
_TICKET_TIER_ORDER: tuple[str, ...] = ("light", "standard", "heavy")


@dataclass(frozen=True)
class Finding:
    check_name: str
    result: str  # "pass" | "fail"
    detail: str


def summary_word_limit(summary_prose: str, *, max_words: int) -> Finding:
    """Whether the ticket summary stays under `tiers.yaml`'s `length_limits.brief_summary_words`."""
    count = artefacts.word_count(summary_prose)
    if count > max_words:
        return Finding("brief_summary_word_limit", "fail", f"ticket summary is {count} words, over the {max_words}-word limit")
    return Finding("brief_summary_word_limit", "pass", f"ticket summary is {count} words")


def flags_are_code_references(flag_rows: list[dict], *, known_paths: frozenset[str]) -> Finding:
    """Whether every `Flags` row names a `path` or `path:line` that exists in the worktree, never a sentence."""
    bad = []
    for row in flag_rows:
        reference = (row.get("reference") or "").strip()
        path = reference.split(":", 1)[0]
        if not path or path not in known_paths:
            bad.append(reference or "<empty>")
    if bad:
        return Finding("brief_flags_code_reference", "fail", f"flag reference(s) not found in the worktree: {bad}")
    return Finding("brief_flags_code_reference", "pass", f"{len(flag_rows)} flag row(s) all reference an existing path")


def live_state_confined_to_blind_spots(artefact: "artefacts.Artefact") -> Finding:
    """Whether none of `LIVE_STATE_WORDS` appears outside the `Blind spots` section."""
    hits = []
    for section in artefact.sections:
        if section.title == "Blind spots":
            continue
        lowered = section.body.lower()
        for word in LIVE_STATE_WORDS:
            if word.lower() in lowered:
                hits.append(f"{section.title!r} names {word!r}")
    if hits:
        return Finding("brief_live_state_confined", "fail", f"live production state asserted outside Blind spots: {hits}")
    return Finding("brief_live_state_confined", "pass", "no live production state asserted outside Blind spots")


def impact_evidence_valid(impact_rows: list[dict], *, impact_scan_dependencies: list[dict], mapping_name: str) -> Finding:
    """Whether every row is well-formed, and an outbound row using `mapping_name` matches `impact_scan`'s own resolution."""
    by_key = {f"{dep['group_id']}:{dep['artifact_id']}": dep for dep in impact_scan_dependencies}
    problems = []
    for row in impact_rows:
        name = row.get("dependency")
        direction, coverage = row.get("direction"), row.get("coverage")
        if direction not in DIRECTIONS:
            problems.append(f"{name!r} has direction {direction!r}, expected one of {DIRECTIONS}")
        if coverage not in artefacts.IMPACT_COVERAGES:
            problems.append(f"{name!r} has coverage {coverage!r}, expected one of {artefacts.IMPACT_COVERAGES}")
        if not (row.get("owner") or "").strip():
            problems.append(f"{name!r} names no owner")
        if row.get("mapping") == mapping_name:
            dep = by_key.get(name)
            if dep is None:
                problems.append(f"{name!r} names mapping {mapping_name!r} but impact_scan found no such dependency")
            elif dep["coverage"] != coverage:
                problems.append(f"{name!r} claims coverage {coverage!r}, impact_scan resolved {dep['coverage']!r}")
    if problems:
        return Finding("brief_impact_evidence_valid", "fail", "; ".join(problems))
    return Finding("brief_impact_evidence_valid", "pass", f"{len(impact_rows)} impact evidence row(s) valid")


def inbound_coverage_matches_caller_freshness(impact_rows: list[dict], *, any_fresh_caller_entry: bool) -> Finding:
    """Whether an inbound row claims non-`unknown` coverage only when a fresh `caller` index entry backs it."""
    if any_fresh_caller_entry:
        return Finding("brief_inbound_caller_freshness", "pass", "a fresh caller index entry backs inbound coverage")
    asserted = [
        row.get("dependency") for row in impact_rows
        if row.get("direction") == "inbound" and row.get("coverage") != "unknown"
    ]
    if asserted:
        return Finding(
            "brief_inbound_caller_freshness", "fail",
            f"inbound row(s) {asserted} assert non-unknown coverage with no fresh caller index entry",
        )
    return Finding("brief_inbound_caller_freshness", "pass", "no fresh caller entry; every inbound row is unknown")


def discovers_excluded_scope(
    impact_rows: list[dict], *, target_service: str | None, impact_scan_dependencies: list[dict],
) -> str | None:
    """The reason this brief re-triggers the exclusion gate, or `None` when it doesn't.

    Either impact_scan itself resolved a dependency onto a service other
    than the ticket's own target (a second service discovered), or an
    `unknown`-coverage row's own `blind_spots` names an eligibility or
    public-contract concern -- the two clauses the design leaves for a
    later stage's own discovery rather than intake's pre-diff scan.
    """
    for dep in impact_scan_dependencies:
        if dep.get("service") and dep["service"] != target_service:
            return (
                f"impact_scan discovered dependency {dep['group_id']}:{dep['artifact_id']} mapped to "
                f"service {dep['service']!r}, outside the ticket's own service {target_service!r}"
            )
    for row in impact_rows:
        if row.get("coverage") != "unknown":
            continue
        blind_spots = (row.get("blind_spots") or "").lower()
        for marker in _ELIGIBILITY_BLIND_SPOT_MARKERS:
            if marker in blind_spots:
                return f"impact evidence row {row.get('dependency')!r} is unknown and names {marker!r} in its blind spots"
    return None


def count_files_touched(touched_rows: list[dict]) -> int:
    return len({row.get("path") for row in touched_rows if row.get("path")})


def touched_services(
    impact_rows: list[dict], *, target_service: str | None, impact_scan_dependencies: list[dict],
) -> frozenset[str]:
    """Every service the brief's impact evidence names, plus the ticket's own target.

    An outbound row's service comes from `impact_scan`'s own resolution
    (matched by the row's `dependency` key); an inbound row names its
    caller service directly in `dependency`, per the module docstring.
    """
    services = {target_service} if target_service else set()
    for dep in impact_scan_dependencies:
        if dep.get("service"):
            services.add(dep["service"])
    for row in impact_rows:
        if row.get("direction") == "inbound" and row.get("dependency"):
            services.add(row["dependency"])
    return frozenset(services)


def count_unknowns(unknown_rows: list[dict], impact_rows: list[dict]) -> int:
    return len(unknown_rows) + sum(1 for row in impact_rows if row.get("coverage") == "unknown")


def _never_lower(candidate: str, floor: str) -> str:
    return candidate if _TICKET_TIER_ORDER.index(candidate) >= _TICKET_TIER_ORDER.index(floor) else floor


def final_tier_rule(
    *, files_touched: int, services_touched: int, unknowns: int, tier_provisional: str, tier_so_far: str, rule: dict,
) -> str:
    """Raise `tier_provisional` one level when any of `rule`'s three thresholds is met; never lowered."""
    triggered = (
        services_touched >= rule["services_touched_at_least"]
        or files_touched > rule["files_touched_over"]
        or unknowns >= rule["unknowns_at_least"]
    )
    if triggered:
        index = _TICKET_TIER_ORDER.index(tier_provisional)
        candidate = _TICKET_TIER_ORDER[min(index + 1, len(_TICKET_TIER_ORDER) - 1)]
    else:
        candidate = tier_provisional
    return _never_lower(_never_lower(candidate, tier_provisional), tier_so_far)


def impact_derived_tier(
    *, impacted_services: frozenset[str], service_tiers: dict, ticket_type: str,
    provisional_tier_matrix: dict, tier_so_far: str,
) -> tuple[str, bool]:
    """`(tier, unknown_impact)` from the highest known criticality among `impacted_services`, by ticket type.

    `unknown_impact` is `True` whenever any of `impacted_services` is
    absent from `service-tiers.yaml` -- an explicit flag on its own,
    never inferred from how much of a scan happened to complete.
    """
    known_tiers = []
    unknown_impact = False
    for name in impacted_services:
        config = service_tiers.get(name)
        if config is None:
            unknown_impact = True
            continue
        known_tiers.append(config["tier"])
    if not known_tiers:
        return tier_so_far, unknown_impact
    highest = min(known_tiers, key=_SERVICE_TIER_ORDER.index)
    mapped = (provisional_tier_matrix.get(highest) or {}).get(ticket_type)
    if mapped is None:
        return tier_so_far, unknown_impact
    return _never_lower(mapped, tier_so_far), unknown_impact
