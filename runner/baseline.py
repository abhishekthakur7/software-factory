"""Import and freeze evidence-backed pre-factory baseline cohorts."""
import json
import runpy
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import yaml

from runner import artefact_registry, canonical, guard, record, run_ledger, schema
from runner.paths import FACTORY_DIR
from runner.fs import write_text

BASELINE_ROUTE = "baseline_read"
LIMITS_PATH = FACTORY_DIR / "config" / "limits.yaml"
POST_PLAN_REVISIONS = schema.BASELINE_REVISIONS_MEASURE
_REPORT = runpy.run_path(str(FACTORY_DIR / "scripts" / "tools" / "report"))
REQUESTED_MEASURES = tuple(dict.fromkeys(_REPORT["baseline_measures"]().values()))
MEASURE_DEFINITIONS = {
    POST_PLAN_REVISIONS: {"unit": "count", "rule": "timestamped approved plan or design decision; later attributable revision events"},
    "questions_per_ticket": {"unit": "count", "rule": "retrospective source estimate with immutable locator"},
    "latency_minutes": {"unit": "minutes", "rule": "retrospective source estimate with immutable locator"},
    "attention_minutes": {"unit": "minutes", "rule": "retrospective source estimate with immutable locator"},
}
MEASURE_DEFINITIONS.update({
    measure: {"unit": "unavailable", "rule": "factory lifecycle measure unavailable in a pre-factory baseline"}
    for measure in REQUESTED_MEASURES if measure not in MEASURE_DEFINITIONS
})


class BaselineImportRefused(ValueError):
    """A baseline source or cohort violates the import contract."""


class FrozenCohortError(BaselineImportRefused):
    """The cohort is frozen and can no longer receive baseline evidence."""


def _assert_no_factory_results(conn: sqlite3.Connection) -> None:
    """Baseline evidence ends when the first completed non-baseline factory ticket exists."""
    result = conn.execute(
        "SELECT id FROM ticket WHERE baseline = 0 AND factory_completed_at IS NOT NULL ORDER BY id LIMIT 1"
    ).fetchone()
    if result is not None:
        raise BaselineImportRefused(f"factory result {result['id']} already exists; baseline writes are closed")


def _assert_import_available(conn: sqlite3.Connection) -> None:
    """A cohort is never replayed: one import writes and freezes the whole combined membership."""
    _assert_no_factory_results(conn)
    cohort = conn.execute(
        "SELECT id FROM artefact WHERE kind = 'baseline_selection' ORDER BY id LIMIT 1"
    ).fetchone()
    if cohort is not None:
        raise BaselineImportRefused(f"baseline cohort {cohort['id']} already exists; its membership froze at import")


def guard_baseline_payload(conn, payload: dict, *, source: str, route_id: str = BASELINE_ROUTE, profile_path=None, owners_path=None) -> dict:
    """Pass baseline source content through its sole admitted route before use."""
    if route_id != BASELINE_ROUTE:
        raise BaselineImportRefused(f"baseline reads require route {BASELINE_ROUTE!r}")
    operation = guard.Operation(
        crossing="persistence", route_id=route_id, payload=payload, input_classes=("internal",),
        source_identity=source, destination_identity="factory_baseline",
        content_provenance={"source_identity": source, "destination_identity": "factory_baseline", "crossing": "persistence"},
    )
    kwargs = {k: v for k, v in {"profile_path": profile_path, "owners_path": owners_path}.items() if v is not None}
    decision = guard.decide(conn, operation, **kwargs)
    if decision.decision != "allow":
        reason = "guard redacted an unpermitted baseline field" if decision.decision == "redact" else ",".join(decision.reason_codes)
        raise BaselineImportRefused("baseline guard denied source: " + reason)
    return guard.pass_through(conn, decision, "persistence")


def _measure(value, status: str, reason: str | None = None) -> dict:
    return {"value": float(value) if value is not None else None, "status": status, "unavailable_reason": reason}


def _ticket_id(ticket: dict) -> str:
    """The normalized baseline locator's ticket id, accepting Jira's named field."""
    value = ticket.get("ticket_id", ticket.get("id"))
    if not value:
        raise BaselineImportRefused("baseline ticket has no immutable ticket id")
    return str(value)


def _ticket_type(ticket: dict) -> str | None:
    return ticket.get("ticket_type", ticket.get("issue_type"))


def _instant(value) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed).astimezone(UTC)


def _required_instant(value, label: str) -> datetime:
    """Parse a cohort cutoff, refusing values that cannot order source events."""
    parsed = _instant(value)
    if parsed is None:
        raise BaselineImportRefused(f"{label} must be an ISO-8601 timestamp")
    return parsed


def measures(history: dict, pull_requests: list[dict]) -> dict[str, dict]:
    """Measure only attributable history; absent evidence stays visible as unavailable."""
    decisions = [(event, _instant(event.get("at"))) for event in history.get("decisions", []) if isinstance(event, dict) and event.get("kind") in {"approved_plan", "design_decision"}]
    decisions = [(event, at) for event, at in decisions if at is not None]
    if not decisions or not history.get("source_locator") or not history.get("pull_request_locator"):
        revisions = _measure(None, "unavailable", "no timestamped approved plan or design decision")
    else:
        plan_at = min(at for _event, at in decisions)
        parsed_events = [(event, _instant(event.get("at"))) for event in pull_requests if isinstance(event, dict)]
        if any(event.get("kind") != "revision" or at is None for event, at in parsed_events):
            revisions = _measure(None, "unavailable", "pull-request history is malformed or not attributable")
        else:
            revisions = _measure(sum(at > plan_at for _event, at in parsed_events), "observed")

    result = {POST_PLAN_REVISIONS: revisions}
    for measure_name, field in (("questions_per_ticket", "questions"), ("latency_minutes", "latency_minutes"), ("attention_minutes", "attention_minutes")):
        value = history.get(field)
        result[measure_name] = _measure(value, "approximate") if isinstance(value, (int, float)) and history.get("source_locator") else _measure(None, "unavailable", f"no attributable {field} evidence")
    for measure_name in REQUESTED_MEASURES:
        result.setdefault(measure_name, _measure(None, "unavailable", "factory lifecycle measure has no pre-factory source"))
    return result


def assert_cohort_open(conn: sqlite3.Connection, cohort_id: int) -> None:
    cohort = record.get(conn, "artefact", cohort_id)
    if cohort is None or cohort["kind"] != "baseline_selection":
        raise BaselineImportRefused(f"unknown baseline cohort {cohort_id}")
    _assert_no_factory_results(conn)
    if cohort["frozen_at"] is not None:
        raise FrozenCohortError(f"baseline cohort {cohort_id} is frozen")


def add_ticket(conn: sqlite3.Connection, cohort_id: int, ticket: dict) -> int:
    """Append a baseline ticket with no factory state or lifecycle bindings."""
    assert_cohort_open(conn, cohort_id)
    return record.insert(
        conn, "ticket", baseline=1, baseline_cohort_id=cohort_id, source_kind="jira",
        source_ref=_ticket_id(ticket), title=ticket.get("title"), service=ticket.get("service"), ticket_type=_ticket_type(ticket),
    )


def add_measure(conn: sqlite3.Connection, cohort_id: int, ticket_id: int, *, measure_name: str, definition_hash: str, ticket: dict, result: dict) -> int:
    """Append one declared measure, preserving unavailable evidence as a row."""
    assert_cohort_open(conn, cohort_id)
    return record.insert(
        conn, "baseline_measure", ticket_id=ticket_id, baseline_cohort_id=cohort_id, measure=measure_name,
        measure_definition_hash=definition_hash, service=ticket.get("service"), ticket_type=ticket.get("ticket_type"),
        value=result["value"], status=result["status"], source_kind="baseline_read", source_ref=ticket.get("source_locator"),
        source_observed_at=ticket.get("completed_at"), entered_by="baseline_import", entered_at=record.now(),
        unavailable_reason=result["unavailable_reason"],
    )


def _comparable_target(limits_path: Path) -> int:
    """The supplemental cohort exists to reach the count the graduation gate needs comparable,
    so both read the one configured value rather than each carrying its own."""
    return int(yaml.safe_load(Path(limits_path).read_text())["graduation"]["baseline_min_comparable"])


def _selection_path(runs_dir: Path, run_id: int) -> Path:
    path = runs_dir / "baseline" / str(run_id) / "selection.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def import_baseline(conn: sqlite3.Connection, *, atlassian, github, service: str, admitted_types: set[str], retrospective_cutoff: str,
                    supplemental: list[dict] | None = None, supplemental_cutoff: str | None = None, repository: str = "", runs_dir: Path,
                    limits_path: Path = LIMITS_PATH, profile_path=None, owners_path=None) -> int:
    """Read, measure, and freeze one retrospective plus optional supplemental cohort."""
    _assert_import_available(conn)
    comparable_target = _comparable_target(limits_path)
    run_id = run_ledger.open_utility_run(conn, kind="baseline_import", inputs=json.dumps({"service": service, "cutoff": retrospective_cutoff}))
    selection_path = None
    savepoint_open = False
    try:
        retrospective_cutoff_at = _required_instant(retrospective_cutoff, "retrospective cutoff")
        candidates = atlassian.list_completed_baseline_tickets(service, retrospective_cutoff)
        selected, excluded = [], []
        for raw in candidates:
            ticket = guard_baseline_payload(conn, raw, source="atlassian", profile_path=profile_path, owners_path=owners_path)
            completed_at = _instant(ticket.get("completed_at"))
            if (ticket.get("service") == service and _ticket_type(ticket) in admitted_types and ticket.get("status") in {"Done", "Resolved", "Closed"}
                    and ticket.get("agent_assisted") is True and completed_at is not None and completed_at <= retrospective_cutoff_at):
                selected.append((ticket, completed_at))
            else:
                excluded.append(_ticket_id(ticket))
        selected.sort(key=lambda item: item[1], reverse=True)
        retrospective = [ticket for ticket, _completed_at in selected[:10]]
        guarded_supplemental = [
            guard_baseline_payload(conn, item, source="atlassian", profile_path=profile_path, owners_path=owners_path)
            for item in (supplemental or [])
        ]
        if guarded_supplemental and supplemental_cutoff is None:
            raise BaselineImportRefused("supplemental cohort requires its own cutoff")
        supplemental_cutoff_at = _required_instant(supplemental_cutoff, "supplemental cutoff") if guarded_supplemental else None
        cohort_ids = {_ticket_id(ticket) for ticket in retrospective}
        for ticket in guarded_supplemental:
            completed_at = _instant(ticket.get("completed_at"))
            ticket_id = _ticket_id(ticket)
            if ticket.get("service") != service:
                raise BaselineImportRefused("supplemental cohort endpoint differs from retrospective cohort")
            if ticket_id in cohort_ids or completed_at is None or completed_at > supplemental_cutoff_at:
                raise BaselineImportRefused("supplemental cohort is duplicate or outside its cutoff")
            cohort_ids.add(ticket_id)
        selection = {"service": service, "retrospective_cutoff": retrospective_cutoff, "supplemental_cutoff": supplemental_cutoff,
                     "query": {"completed": True, "agent_assisted": True, "admitted_types": sorted(admitted_types)},
                     "included": [{"id": _ticket_id(item), "source_locator": item.get("source_locator")} for item in retrospective],
                     "supplemental_included": [{"id": _ticket_id(item), "source_locator": item.get("source_locator")} for item in guarded_supplemental],
                     "excluded": excluded + [_ticket_id(item) for item, _completed_at in selected[10:]]}
        definition_hashes = {name: canonical.content_hash({"measure": name, **MEASURE_DEFINITIONS[name]}) for name in REQUESTED_MEASURES}

        def read_member(ticket):
            source_id = _ticket_id(ticket)
            history = guard_baseline_payload(conn, {"history": atlassian.read_baseline_history(source_id)}, source="atlassian", profile_path=profile_path, owners_path=owners_path).get("history", {})
            confluence_locator = history.get("confluence_locator")
            if confluence_locator:
                confluence = guard_baseline_payload(conn, {"history": atlassian.read_baseline_confluence_history(confluence_locator)}, source="atlassian", profile_path=profile_path, owners_path=owners_path).get("history", {})
                history = {**history, "decisions": [*(history.get("decisions") or []), *(confluence.get("decisions") or [])], "source_locator": confluence.get("source_locator", history.get("source_locator"))}
            locator = history.get("pull_request_locator")
            pulls = guard_baseline_payload(conn, {"pull_request_history": github.read_pull_request_history(repository, locator)}, source="github", profile_path=profile_path, owners_path=owners_path).get("pull_request_history", []) if locator else []
            return ticket, measures(history, pulls)

        prepared_retrospective = [read_member(ticket) for ticket in retrospective]
        observed = sum(results[POST_PLAN_REVISIONS]["status"] == "observed" for _ticket, results in prepared_retrospective)
        prepared_supplemental = [read_member(ticket) for ticket in guarded_supplemental] if observed < comparable_target else []

        conn.execute("SAVEPOINT baseline_import_cohort")
        savepoint_open = True
        selection_path = _selection_path(runs_dir, run_id)
        write_text(selection_path, canonical.canonical_json(selection).decode())
        cohort_id = artefact_registry.register(conn, ticket_id=None, utility_run_id=run_id, kind="baseline_selection", path=selection_path)

        def write_member(ticket, results):
            ticket_id = add_ticket(conn, cohort_id, ticket)
            for name, outcome in results.items():
                add_measure(conn, cohort_id, ticket_id, measure_name=name, definition_hash=definition_hashes[name], ticket=ticket, result=outcome)

        for ticket, results in (*prepared_retrospective, *prepared_supplemental):
            write_member(ticket, results)
        # Membership freezes whatever the history could supply: the cohort has to be fixed
        # before any factory result exists, and a cohort too short to compare is the
        # graduation gate's own verdict to report, not a reason to leave it open and
        # backfillable once results are known.
        record.update(conn, "artefact", cohort_id, frozen_at=record.now())
        run_ledger.finish(conn, run_id, "pass", table="utility_run")
        conn.execute("RELEASE SAVEPOINT baseline_import_cohort")
        savepoint_open = False
        conn.commit()
        return cohort_id
    except Exception:
        if savepoint_open:
            conn.execute("ROLLBACK TO SAVEPOINT baseline_import_cohort")
            conn.execute("RELEASE SAVEPOINT baseline_import_cohort")
        if selection_path is not None:
            selection_path.unlink(missing_ok=True)
        run_ledger.finish(conn, run_id, "refused", table="utility_run")
        conn.commit()
        raise
