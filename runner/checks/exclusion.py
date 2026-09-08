"""The exclusion gate: pilot-eligibility matrix violations and excluded surfaces, as pure functions over data.

Every function here takes already-loaded configuration or already-known
ticket fields and returns data -- reasons, surface names, or the one event
name a caller applies -- so the mechanical exclusion decision itself never
touches the database. `apply_recorded_exclusion` is the one exception: it
reads back a `check_result` another stage already wrote and applies the one
transition event that stage's own state permits.
"""
import re
import sqlite3
from pathlib import Path

import yaml

from runner import transitions
from runner.paths import FACTORY_DIR
from runner.reviewer_sets import match_sensitive_path

DEFAULT_SENSITIVE_PATHS_PATH = FACTORY_DIR / "config" / "sensitive-paths.yaml"
DEFAULT_EXCLUSIONS_PATH = FACTORY_DIR / "config" / "exclusions.yaml"

# The pilot eligibility matrix (R-S0-8): exactly one T2, Java service and
# the one admitted ticket type, one repository and one target service.
_PILOT_SERVICE_TIER = "T2"
_PILOT_LANGUAGE = "java"
_PILOT_TICKET_TYPE = "small_feature"

# The transition event a recorded exclusion applies, keyed by the
# stage_run.stage that discovered it; S5's proof reuses the checks-stage
# event the state table already carries for a required sensitive path.
_STAGE_EVENTS: dict[str, str] = {
    "S1": "s1_exclusion",
    "S3": "s3_exclusion",
    "S5": "checks_sensitive_path_required",
}


def load_sensitive_paths(path: Path = DEFAULT_SENSITIVE_PATHS_PATH) -> dict[str, str]:
    """`sensitive-paths.yaml`'s glob-to-owner mapping."""
    doc = yaml.safe_load(Path(path).read_text()) or {}
    return doc.get("paths", {}) or {}


def load_exclusions(path: Path = DEFAULT_EXCLUSIONS_PATH) -> dict[str, dict]:
    """`exclusions.yaml`'s surface-to-`{path_globs, text_patterns}` mapping."""
    doc = yaml.safe_load(Path(path).read_text()) or {}
    return doc.get("surfaces", {}) or {}


def eligible(ticket_fields: dict, service_config: dict) -> list[str]:
    """The pilot eligibility matrix's own violations for this ticket, or `[]` when it passes.

    Every dimension is checked independently rather than short-circuiting
    on the first miss, so a caller sees every reason a ticket falls
    outside the Initial pilot matrix, not just the first one found.
    """
    reasons = []
    if (service_config or {}).get("tier") != _PILOT_SERVICE_TIER:
        reasons.append("service tier not T2")
    if (service_config or {}).get("language") != _PILOT_LANGUAGE:
        reasons.append("language not java")
    if ticket_fields.get("ticket_type") != _PILOT_TICKET_TYPE:
        reasons.append("type not eligible")
    if ticket_fields.get("repository_count", 1) > 1 or ticket_fields.get("service_count", 1) > 1:
        reasons.append("more than one repository or service")
    return reasons


def surfaces_in_text(text: str, *, exclusions: dict | None = None) -> set[str]:
    """Every excluded surface whose `text_patterns` matches somewhere (case-insensitively) in `text`."""
    exclusions = exclusions if exclusions is not None else load_exclusions()
    hits: set[str] = set()
    for surface, config in exclusions.items():
        for pattern in config.get("text_patterns", ()) or ():
            if re.search(pattern, text or "", re.IGNORECASE):
                hits.add(surface)
                break
    return hits


def _surface_globs(surface: str, config: dict, sensitive_paths: dict[str, str]) -> dict[str, str]:
    """`config`'s own `path_globs`, plus `sensitive-paths.yaml`'s globs for the `sensitive_path` surface.

    The `sensitive_path` surface's globs are `sensitive-paths.yaml`'s own
    keys, read from there rather than duplicated in `exclusions.yaml`.
    """
    globs = {glob: surface for glob in config.get("path_globs", ()) or ()}
    if surface == "sensitive_path":
        globs.update({glob: surface for glob in sensitive_paths})
    return globs


def surfaces_in_paths(
    paths: list[str], *, exclusions: dict | None = None, sensitive_paths: dict[str, str] | None = None
) -> set[str]:
    """Every excluded surface whose `path_globs` (or, for `sensitive_path`, `sensitive-paths.yaml`) matches one of `paths`."""
    exclusions = exclusions if exclusions is not None else load_exclusions()
    sensitive_paths = sensitive_paths if sensitive_paths is not None else load_sensitive_paths()
    hits: set[str] = set()
    for surface, config in exclusions.items():
        globs = _surface_globs(surface, config, sensitive_paths)
        for path in paths:
            if match_sensitive_path(globs, path) is not None:
                hits.add(surface)
                break
    return hits


def decide_at_checks(
    *,
    plan_paths: list[str],
    diff_paths: list[str],
    exclusions: dict | None = None,
    sensitive_paths: dict[str, str] | None = None,
) -> str:
    """The event to apply for an excluded path found in the actual diff.

    `checks_removal_return` when some excluded diff path is not among the
    plan's own paths -- an accidental touch S4 must remove before S5 can
    pass; `checks_sensitive_path_required` only when every excluded diff
    path the diff touches is one the plan itself already named in scope.
    Raises `ValueError` when `diff_paths` names no excluded path at all,
    since a caller only reaches this decision after a check has already
    found one.
    """
    exclusions = exclusions if exclusions is not None else load_exclusions()
    sensitive_paths = sensitive_paths if sensitive_paths is not None else load_sensitive_paths()
    excluded = [
        path for path in diff_paths
        if surfaces_in_paths([path], exclusions=exclusions, sensitive_paths=sensitive_paths)
    ]
    if not excluded:
        raise ValueError("no excluded path found in diff_paths")
    if any(path not in plan_paths for path in excluded):
        return "checks_removal_return"
    return "checks_sensitive_path_required"


def apply_recorded_exclusion(conn: sqlite3.Connection, ticket_id: int) -> str:
    """Apply the transition `ticket_id`'s latest recorded exclusion `check_result` names, by the stage that found it.

    Reads the latest `check_result` row of `check_name = 'exclusion'` and
    `result = 'fail'` for `ticket_id`, through the `stage_run` it belongs
    to, and applies `s1_exclusion`, `s3_exclusion`, or
    `checks_sensitive_path_required` by that run's own stage;
    `transitions.apply` itself refuses when the ticket is not in the state
    that stage runs from, so this function adds no state check of its own.
    """
    row = conn.execute(
        "SELECT stage_run.stage AS stage FROM check_result "
        "JOIN stage_run ON stage_run.id = check_result.stage_run_id "
        "WHERE stage_run.ticket_id = ? AND check_result.check_name = 'exclusion' AND check_result.result = 'fail' "
        "ORDER BY check_result.id DESC LIMIT 1",
        (ticket_id,),
    ).fetchone()
    if row is None:
        raise LookupError(f"no recorded exclusion check_result for ticket {ticket_id}")
    event = _STAGE_EVENTS.get(row["stage"])
    if event is None:
        raise ValueError(f"exclusion check_result recorded from an unsupported stage: {row['stage']!r}")
    return transitions.apply(conn, ticket_id, event)
