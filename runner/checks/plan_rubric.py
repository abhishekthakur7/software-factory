"""The plan rubric's script-half findings: one function per plan-rubric row, over an already-parsed plan.

`artefact_structure.check` gates the plan's shape -- fixed sections, fixed
table columns, every `Contracts` cell parsing to a state; this module gates
what those tables *say*, the deterministic half of each rubric row that
carries one (the grader half is a human judgment the bootstrap checklist
carries until a calibrated grader exists). A `Finding` never reports
`"pass"`: an empty list from `check` is a pass, `"fail"` blocks the plan
the same way a structural finding does, and `"blind_spot"` records
something a human must explicitly accept -- a mixed no-behaviour-change
task list, an `unknown` contract field -- without blocking the run by
itself. Every function here takes already-parsed `artefacts.Artefact`
values and plain data (question rows, the recipe catalogue, the project's
enabled recipe ids, `limits.yaml`'s mapping); nothing here touches a
database connection or the filesystem, so the driver assembles those
inputs and turns the result into one `check_result` row.
"""
import re
from typing import NamedTuple

from runner import artefacts

# `Test strategy.size` maps onto the project's three test-level recipes
# one for one; a `large` row needs a registered `end_to_end` recipe before
# it may be planned at all.
SIZE_TO_LEVEL: dict[str, str] = {"small": "unit", "medium": "integration", "large": "end_to_end"}

_TRUE_STRINGS = frozenset({"yes", "true", "1"})
_PUNCT_RE = re.compile(r"[^\w\s]")


class Finding(NamedTuple):
    rule: str
    detail: str
    result: str  # "fail" | "blind_spot"


def _truthy(value) -> bool:
    return str(value or "").strip().lower() in _TRUE_STRINGS


def _split_ids(cell: str | None) -> list[str]:
    return [part.strip() for part in (cell or "").split(",") if part.strip()]


def _normalise(text: str) -> list[str]:
    """Lowercased, punctuation-stripped words, so `rejected_because` restating `alternative` reads as equal."""
    return _PUNCT_RE.sub("", text or "").lower().split()


def _rows(artefact: artefacts.Artefact, section_title: str) -> list[dict[str, str]]:
    section = artefact.section(section_title)
    return (section.table() if section is not None else None) or []


def rejected_alternative_reason(plan: artefacts.Artefact) -> list[Finding]:
    """Every `Alternatives` row names both what it was and why, and the reason is not the name restated."""
    findings: list[Finding] = []
    for row in _rows(plan, "Alternatives"):
        alternative = (row.get("alternative") or "").strip()
        reason = (row.get("rejected_because") or "").strip()
        if not alternative or not reason:
            findings.append(
                Finding("rejected_alternative_reason", f"{alternative or '<empty>'}: missing alternative or reason", "fail")
            )
            continue
        if _normalise(reason) == _normalise(alternative):
            findings.append(Finding("rejected_alternative_reason", f"{alternative}: reason restates the alternative", "fail"))
    return findings


def shared_abstraction_cited(plan: artefacts.Artefact) -> list[Finding]:
    """A new abstraction cites its search before it is proposed."""
    findings: list[Finding] = []
    for row in _rows(plan, "Abstraction and separate debt"):
        kind = (row.get("kind") or "").strip()
        unit = row.get("unit") or "<unknown unit>"
        existing = _split_ids(row.get("existing"))
        reason = (row.get("reason") or "").strip()
        if kind == "new_shared_abstraction":
            if len(existing) < 3 and not reason:
                findings.append(
                    Finding("shared_abstraction_cited", f"{unit}: fewer than three existing near-duplicates and no risk named", "fail")
                )
        elif kind == "widened_shared_function":
            if not reason:
                findings.append(Finding("shared_abstraction_cited", f"{unit}: no reason inlining was rejected", "fail"))
        elif kind == "new_utility":
            if not existing or not reason:
                findings.append(Finding("shared_abstraction_cited", f"{unit}: no recorded search or no reason", "fail"))
        elif kind:
            findings.append(Finding("shared_abstraction_cited", f"{unit}: kind {kind!r} not in {artefacts.ABSTRACTION_KINDS}", "fail"))
    return findings


def archaeology_carried(plan: artefacts.Artefact, *, brief: artefacts.Artefact) -> list[Finding]:
    """The brief's classification survives into the plan; unexplained/contradictory code gets a characterization test."""
    findings: list[Finding] = []
    plan_rows = _rows(plan, "Archaeology and characterization tests")
    by_path = {row.get("path"): row for row in plan_rows if row.get("path")}
    task_ids = {row.get("id") for row in _rows(plan, "Tasks")}
    unknowns_section = plan.section("Unknowns")
    unknowns_prose = unknowns_section.prose() if unknowns_section is not None else ""

    for history_row in _rows(brief, "History"):
        path = history_row.get("path")
        classification = history_row.get("classification")
        carried = by_path.get(path)
        if carried is None or carried.get("classification") != classification:
            findings.append(Finding("archaeology_carried", f"{path}: brief classification {classification!r} not carried into the plan", "fail"))

    for row in plan_rows:
        path = row.get("path")
        classification = row.get("classification")
        if classification in ("unexplained", "contradictory"):
            task_id = (row.get("characterization_task") or "").strip()
            if not task_id or task_id not in task_ids:
                findings.append(Finding("archaeology_carried", f"{path}: no characterization_task naming a Tasks id", "fail"))
        if _truthy(row.get("alters_captured_behaviour")) and (not path or path not in unknowns_prose):
            findings.append(Finding("archaeology_carried", f"{path}: alters captured behaviour but is not named in Unknowns", "fail"))
    return findings


def no_behaviour_change_isolated(plan: artefacts.Artefact) -> list[Finding]:
    """A flagged task is its own tested task; a plan mixing flagged and unflagged tasks needs the human's named exception."""
    findings: list[Finding] = []
    tasks = _rows(plan, "Tasks")
    tests = _rows(plan, "Test strategy")
    flagged = [row for row in tasks if _truthy(row.get("no_behaviour_change"))]
    unflagged = [row for row in tasks if not _truthy(row.get("no_behaviour_change"))]

    for row in flagged:
        task_id = row.get("id")
        if not any(task_id in _split_ids(test.get("criteria")) for test in tests):
            findings.append(Finding("no_behaviour_change_isolated", f"{task_id}: no behaviour-preserving test-strategy row", "fail"))

    if flagged and unflagged:
        findings.append(
            Finding("no_behaviour_change_isolated", "plan mixes no_behaviour_change and ordinary tasks: named exception needed", "blind_spot")
        )
    return findings


def contracts_declared(plan: artefacts.Artefact, *, questions: list[dict]) -> list[Finding]:
    """Every field parses to a state; `changed` needs evidence or a consequential question; `unknown` is an accepted blind spot."""
    findings: list[Finding] = []
    any_consequential_question = any(_truthy(q.get("consequential")) for q in questions)
    for row in _rows(plan, "Contracts"):
        unit = row.get("unit") or "<unknown unit>"
        for field in artefacts.CONTRACT_FIELDS:
            cell = row.get(field)
            try:
                state, evidence = artefacts.contract_cell(cell)
            except artefacts.ArtefactError:
                findings.append(Finding("contracts_declared", f"{unit}.{field}: {cell!r} does not parse to a state", "fail"))
                continue
            if state == "changed" and not evidence and not any_consequential_question:
                findings.append(Finding("contracts_declared", f"{unit}.{field}: changed with no evidence and no consequential question", "fail"))
            elif state == "unknown":
                findings.append(Finding("contracts_declared", f"{unit}.{field}", "blind_spot"))
    return findings


def test_strategy_typed(
    plan: artefacts.Artefact, *, criteria_text: str | None, catalogue: dict, project_recipes: list[str],
) -> list[Finding]:
    """Typed size/action, a `change`/`remove` row names its authority, a `large` row needs a registered end-to-end recipe."""
    findings: list[Finding] = []
    no_behaviour_change_ids = {row.get("id") for row in _rows(plan, "Tasks") if _truthy(row.get("no_behaviour_change"))}
    known_ac_ids: set[str] = set()
    if criteria_text:
        try:
            criteria_artefact = artefacts.parse(criteria_text)
        except artefacts.ArtefactError:
            criteria_artefact = None
        if criteria_artefact is not None:
            known_ac_ids = {row["id"] for row in _rows(criteria_artefact, "Acceptance criteria")}

    end_to_end_registered = any(
        (recipe_id in catalogue and catalogue[recipe_id].level == "end_to_end") for recipe_id in project_recipes
    )

    for row in _rows(plan, "Test strategy"):
        test, size, action = row.get("test") or "<unnamed test>", (row.get("size") or "").strip(), (row.get("action") or "").strip()
        if size not in artefacts.TEST_SIZES:
            findings.append(Finding("test_strategy_typed", f"{test}: size {size!r} not in {artefacts.TEST_SIZES}", "fail"))
        if action not in artefacts.TEST_ACTIONS:
            findings.append(Finding("test_strategy_typed", f"{test}: action {action!r} not in {artefacts.TEST_ACTIONS}", "fail"))
        if action in ("change", "remove"):
            ids = _split_ids(row.get("criteria"))
            authorised = any(i in known_ac_ids or i in no_behaviour_change_ids for i in ids)
            if not authorised:
                findings.append(Finding("test_strategy_typed", f"{test}: {action} row names no AC-n or no_behaviour_change task", "fail"))
        if size == "large" and not end_to_end_registered:
            findings.append(Finding("test_strategy_typed", f"{test}: large test planned with no registered end-to-end recipe", "fail"))
    return findings


def test_mix_report(plan: artefacts.Artefact, *, limits: dict) -> str:
    """The plan's `add`-row test counts against `limits.yaml`'s `test_mix` target, as one information line -- never a finding."""
    add_rows = [row for row in _rows(plan, "Test strategy") if (row.get("action") or "").strip() == "add"]
    counts = {size: sum(1 for row in add_rows if (row.get("size") or "").strip() == size) for size in artefacts.TEST_SIZES}
    total = sum(counts.values())
    target = limits.get("test_mix", {})
    parts = [
        f"{size} {counts[size]}/{total} (target {target.get(size, '?')})" if total else f"{size} 0 (target {target.get(size, '?')})"
        for size in artefacts.TEST_SIZES
    ]
    return f"test mix over {total} add row(s): " + ", ".join(parts)


def rollout_structured(plan: artefacts.Artefact, *, limits: dict) -> list[Finding]:
    """Every flag's five cells, guardrails within the section 8 limit, one rollback kill trigger, both log patterns."""
    findings: list[Finding] = []
    section = plan.section("Rollout")
    if section is None:
        return findings  # already reported by artefact_structure

    flags = section.subsection("Flags")
    for row in (flags.table() if flags is not None else None) or []:
        missing = [column for column in artefacts.PLAN_SUBTABLES["Rollout"]["Flags"] if not (row.get(column) or "").strip()]
        if missing:
            findings.append(Finding("rollout_structured", f"flag {row.get('flag')}: missing {missing}", "fail"))

    guardrails = section.subsection("Guardrails")
    guardrail_rows = (guardrails.table() if guardrails is not None else None) or []
    max_metrics = limits["guardrail_metrics"]["max"]
    if len(guardrail_rows) > max_metrics:
        findings.append(Finding("rollout_structured", f"{len(guardrail_rows)} guardrail metrics over the {max_metrics} limit", "fail"))
    for row in guardrail_rows:
        if not (row.get("query") or "").strip() or not (row.get("critical_threshold") or "").strip():
            findings.append(Finding("rollout_structured", f"{row.get('metric')}: missing query or critical_threshold", "fail"))

    kill_trigger = section.subsection("Kill trigger")
    kill_rows = (kill_trigger.table() if kill_trigger is not None else None) or []
    if not any((row.get("default_response") or "").strip().lower().startswith("rollback") for row in kill_rows):
        findings.append(Finding("rollout_structured", "no kill trigger row names rollback as the default response", "fail"))

    log_verification = section.subsection("Log verification")
    for row in (log_verification.table() if log_verification is not None else None) or []:
        if not (row.get("pass_pattern") or "").strip() or not (row.get("fail_pattern") or "").strip():
            findings.append(Finding("rollout_structured", f"{row.get('query')}: missing pass_pattern or fail_pattern", "fail"))
    return findings


def risk_map_places(plan: artefacts.Artefact, *, limits: dict, risk_map_candidate_count: int) -> list[Finding]:
    """At least the section 8 named-places floor, or one per computed candidate when the risk map names fewer; every `why` filled."""
    findings: list[Finding] = []
    rows = _rows(plan, "Risk map")
    configured = limits["risk_map"]["named_places"]
    floor = configured if risk_map_candidate_count >= configured else risk_map_candidate_count
    if len(rows) < floor:
        findings.append(Finding("risk_map_places", f"{len(rows)} place(s) named, floor is {floor}", "fail"))
    for row in rows:
        if not (row.get("why") or "").strip():
            findings.append(Finding("risk_map_places", f"{row.get('place')}: empty why", "fail"))
    return findings


def check(
    plan_text: str, *, brief_text: str, criteria_text: str, catalogue: dict, project_recipes: list[str],
    questions: list[dict], limits: dict, risk_map_candidate_count: int = 0,
) -> list[Finding]:
    """Every script-half rubric finding over `plan_text`; an empty list is a pass.

    `catalogue` is `recipes.load_catalogue()`; `project_recipes` is
    `project.yaml`'s enabled recipe ids; `questions` is the ticket's
    question rows as dicts; `limits` is `limits.yaml`'s parsed mapping;
    `risk_map_candidate_count` is the attached risk-map artefact's own
    named-candidate count, computed by the driver before this runs.
    """
    plan = artefacts.parse(plan_text)
    brief = artefacts.parse(brief_text)
    findings: list[Finding] = []
    findings += rejected_alternative_reason(plan)
    findings += shared_abstraction_cited(plan)
    findings += archaeology_carried(plan, brief=brief)
    findings += no_behaviour_change_isolated(plan)
    findings += contracts_declared(plan, questions=questions)
    findings += test_strategy_typed(plan, criteria_text=criteria_text, catalogue=catalogue, project_recipes=project_recipes)
    findings += rollout_structured(plan, limits=limits)
    findings += risk_map_places(plan, limits=limits, risk_map_candidate_count=risk_map_candidate_count)
    return findings
