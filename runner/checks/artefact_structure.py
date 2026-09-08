"""The general artefact structure check: fixed sections, fixed table columns, ceilings, and kind-specific rules.

One check function covers every artefact kind `runner.artefacts.SECTIONS`
names: it walks the fixed section list, the fixed table columns for
whichever of `BRIEF_TABLES`/`CRITERIA_TABLES`/`PLAN_TABLES` applies, and,
for the `criteria` kind, the EARS-form, example-concreteness, and
forced-category rules a criteria version carries on top; for the `plan`
kind, the extra rules a plan carries on top -- length ceilings, first-page
placement, typed validation recipes instead of free-form shell, two-way
`AC-n` traceability against the criteria artefact, the `Rollout` section's
five `### ` subsections, `Scope and discretion.action`'s closed value set,
and every `Contracts` field cell parsing to a state. A `Finding`
names the rule that failed and enough detail to find it in the text; an
empty list is a pass. Nothing here writes to the database or the
filesystem -- a caller turns findings into a `check_result` row and an
outcome. `AC-n` id continuity across versions and the split-threshold rule
both need more than one version's text or another artefact's content, so
they stay with the driver that already holds that context rather than
living here.
"""
import re
from typing import NamedTuple

from runner import artefacts

# Tables checked by document kind. `packet` is script-assembled rather
# than agent prose, but its one evidence table still carries a fixed
# column set the structure check enforces like any other; `pr_body` skips
# this since it shares the packet's own script and inputs.
KIND_TABLES: dict[str, dict[str, tuple[str, ...]]] = {
    "brief": artefacts.BRIEF_TABLES,
    "criteria": artefacts.CRITERIA_TABLES,
    "plan": artefacts.PLAN_TABLES,
    "packet": artefacts.PACKET_TABLES,
}

# The fixed tables allowed to carry zero rows: an empty dependency list is
# itself the finding ("nothing changed"), written explicitly rather than
# omitted; an empty agreement check is what a version with no formalised
# or provisional criterion legitimately looks like (every criterion
# unformalisable, restated by no children at all); a plan naming no
# rejected alternative, no non-self-evident code, and no new abstraction
# legitimately leaves those three empty too. `Risk map` is deliberately
# absent from this set: a risk map always names at least one place.
_EMPTY_TABLE_ALLOWED: frozenset[tuple[str, str]] = frozenset({
    ("plan", "Dependencies"), ("plan", "Alternatives"), ("plan", "Archaeology and characterization tests"),
    ("plan", "Abstraction and separate debt"), ("criteria", "Agreement check"),
})

# `Rollout`'s five sub-tables allowed to carry zero rows: a ticket with no
# flag, no ramp, no guardrail, or no log-verification query legitimately
# leaves that sub-table header-only. `Kill trigger` is excluded: a
# rollout always names one, with rollback as its default response.
_ROLLOUT_EMPTY_ALLOWED: frozenset[str] = frozenset({"Flags", "Ramp", "Guardrails", "Log verification"})

# The three sections a reviewer must be able to read without scrolling to
# decide whether to open the rest; `first_page_lines` names how far "the
# first page" reaches.
_FIRST_PAGE_SECTIONS: tuple[str, ...] = ("Intent and scrutiny", "Readiness", "Risk map")

# Shell interpolation and redirection a typed `validation_args` cell must
# never carry -- the same category `runner.recipes` refuses at dispatch,
# checked again here so a plan naming free-form shell fails at S3, before
# any recipe would ever run it.
_SHELL_TOKENS: tuple[str, ...] = (";", "|", "&&", "$(", "`", ">")

_TRUE_STRINGS = frozenset({"yes", "true", "1"})

# `AC-n`, the only id shape the acceptance-criteria table accepts.
_AC_ID_RE = re.compile(r"^AC-\d+$")

# The three literal forms a forced category's resolution cell may take: a
# covering criterion, an explicit not-applicable reason, or left open for
# a question. Anything else is a silent or malformed category, which the
# check refuses rather than guesses at.
_CATEGORY_RESOLUTION_RE = re.compile(r"^(covered by criterion \S.*|not applicable because \S.*|open)$", re.IGNORECASE)

# A Given/When/Then example must use all three words and carry no
# placeholder in place of a real value.
_GWT_WORDS: tuple[str, ...] = ("given", "when", "then")
_PLACEHOLDER_TOKENS: tuple[str, ...] = ("TODO", "X", "foo", "bar", "placeholder")
_PLACEHOLDER_BRACKET_RE = re.compile(r"<[^<>]+>")


class Finding(NamedTuple):
    rule: str
    detail: str


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in _TRUE_STRINGS


def _split_ids(cell: str | None) -> list[str]:
    """A comma-separated cell (`AC-n` ids, a `no_behaviour_change` task id) as a list of trimmed tokens."""
    return [part.strip() for part in (cell or "").split(",") if part.strip()]


def _section_line_number(text: str, title: str) -> int | None:
    """The 1-based line on which `## title` appears in `text`, or None when it doesn't."""
    heading = f"## {title}"
    for index, line in enumerate(text.splitlines(), start=1):
        if line.rstrip() == heading:
            return index
    return None


def _check_sections(kind: str, artefact: artefacts.Artefact, *, pending_allowed: bool) -> list[Finding]:
    findings: list[Finding] = []
    fixed = artefacts.SECTIONS[kind]
    present = artefact.titles()

    for name in fixed:
        if name not in present:
            findings.append(Finding("missing_section", name))

    fixed_present_order = [title for title in present if title in fixed]
    expected_order = [name for name in fixed if name in present]
    if fixed_present_order != expected_order:
        findings.append(Finding("section_order", ", ".join(fixed_present_order)))

    for name in fixed:
        section = artefact.section(name)
        if section is None:
            continue  # already reported as missing
        if section.is_pending():
            if not pending_allowed:
                findings.append(Finding("pending_section", name))
            continue  # exempt from every check below while a rerun is owed
        if section.is_empty():
            findings.append(Finding("empty_section", name))
    return findings


def _check_tables(kind: str, artefact: artefacts.Artefact) -> list[Finding]:
    findings: list[Finding] = []
    for section_name, columns in KIND_TABLES.get(kind, {}).items():
        section = artefact.section(section_name)
        if section is None or section.is_pending():
            continue  # missing/pending already reported by _check_sections
        try:
            header = section.table_header()
        except artefacts.ArtefactError as exc:
            findings.append(Finding("malformed_table", f"{section_name}: {exc}"))
            continue
        if header is None:
            findings.append(Finding("missing_table", section_name))
            continue
        if header != columns:
            findings.append(Finding("bad_table_columns", f"{section_name}: {header}"))
        rows = section.table() or []
        if not rows and (kind, section_name) not in _EMPTY_TABLE_ALLOWED:
            findings.append(Finding("empty_table", section_name))
    return findings


def _check_ceilings(artefact: artefacts.Artefact, *, tier: str, limits: dict, text: str) -> list[Finding]:
    findings: list[Finding] = []

    prose_words = sum(artefacts.word_count(section.prose()) for section in artefact.sections)
    prose_ceiling = limits["plan_prose_words"][tier]
    if prose_words > prose_ceiling:
        findings.append(Finding("prose_over_ceiling", f"{prose_words} words over {prose_ceiling}"))

    # The readiness table is derived by `handoff_ready`, never agent
    # prose, so it is excluded from the row ceiling the agent's own tables
    # are judged against.
    total_rows = sum(
        len(artefact.section(name).table() or [])
        for name in artefacts.PLAN_TABLES if name != "Readiness" and artefact.section(name) is not None
    )
    row_ceiling = limits["plan_table_rows"][tier]
    if total_rows > row_ceiling:
        findings.append(Finding("table_rows_over_ceiling", f"{total_rows} rows over {row_ceiling}"))

    first_page = limits["first_page_lines"]
    for name in _FIRST_PAGE_SECTIONS:
        line = _section_line_number(text, name)
        if line is not None and line > first_page:
            findings.append(Finding("section_outside_first_page", f"{name} at line {line}, limit {first_page}"))
    return findings


def _check_tasks_and_traceability(
    artefact: artefacts.Artefact, *, criteria_text: str | None, catalogue: dict | None,
) -> list[Finding]:
    findings: list[Finding] = []
    tasks_section = artefact.section("Tasks")
    tests_section = artefact.section("Test strategy")
    tasks = tasks_section.table() if tasks_section is not None else None
    tests = tests_section.table() if tests_section is not None else None
    if tasks is None:
        tasks = []
    if tests is None:
        tests = []

    for row in tasks:
        recipe_id = (row.get("validation_recipe") or "").strip()
        if catalogue is not None and recipe_id not in catalogue:
            findings.append(Finding("unregistered_recipe", f"task {row.get('id')}: {recipe_id!r}"))
        args = row.get("validation_args") or ""
        if any(token in args for token in _SHELL_TOKENS):
            findings.append(Finding("shell_in_validation_args", f"task {row.get('id')}: {args!r}"))
        criteria_ids = _split_ids(row.get("criteria"))
        if not criteria_ids and not _truthy(row.get("no_behaviour_change")):
            findings.append(Finding("unflagged_task", str(row.get("id"))))

    if criteria_text is not None:
        try:
            known_ids = {
                row["id"] for row in artefacts.parse(criteria_text).section("Acceptance criteria").table() or []
            }
        except (artefacts.ArtefactError, AttributeError):
            known_ids = set()

        cited_ids: set[str] = set()
        for row in tasks:
            for ac_id in _split_ids(row.get("criteria")):
                cited_ids.add(ac_id)
                if ac_id.startswith("AC-") and ac_id not in known_ids:
                    findings.append(Finding("dangling_ac_id", f"task {row.get('id')} cites {ac_id}"))

        test_served_ids: set[str] = set()
        for row in tests:
            for ac_id in _split_ids(row.get("criteria")):
                test_served_ids.add(ac_id)
                if ac_id.startswith("AC-") and ac_id not in known_ids:
                    findings.append(Finding("dangling_ac_id", f"test {row.get('test')} cites {ac_id}"))

        for ac_id in sorted(known_ids):
            if ac_id not in cited_ids:
                findings.append(Finding("unserved_criterion", f"{ac_id}: no task row"))
            if ac_id not in test_served_ids:
                findings.append(Finding("unserved_criterion", f"{ac_id}: no test row"))
    return findings


def _example_is_concrete(example: str) -> bool:
    """A Given/When/Then example naming every clause, with no bracketed or listed placeholder in place of a real value."""
    lowered = example.lower()
    if not all(word in lowered for word in _GWT_WORDS):
        return False
    if _PLACEHOLDER_BRACKET_RE.search(example):
        return False
    return not any(re.search(rf"(?<![\w-]){re.escape(token)}(?![\w-])", example) for token in _PLACEHOLDER_TOKENS)


def _check_criteria(artefact: artefacts.Artefact) -> list[Finding]:
    findings: list[Finding] = []
    ac_section = artefact.section("Acceptance criteria")
    if ac_section is not None and not ac_section.is_pending():
        for row in ac_section.table() or []:
            ac_id, state = row.get("id") or "", row.get("state")
            if not _AC_ID_RE.match(ac_id):
                findings.append(Finding("bad_ac_id", ac_id))
            if state not in artefacts.CRITERION_STATES:
                findings.append(Finding("bad_criterion_state", f"{ac_id}: {state!r}"))
                continue
            if state == "unformalisable":
                continue  # no EARS form or example is expected: the row becomes a question instead
            if not (row.get("system") or "").strip() or not (row.get("response") or "").strip():
                findings.append(Finding("incomplete_ears_form", ac_id))
            if not _example_is_concrete(row.get("example") or ""):
                findings.append(Finding("example_not_concrete", ac_id))

    fc_section = artefact.section("Forced categories")
    if fc_section is not None and not fc_section.is_pending():
        by_category = {row.get("category"): row for row in (fc_section.table() or [])}
        for category in artefacts.FORCED_CATEGORIES:
            row = by_category.get(category)
            if row is None:
                findings.append(Finding("missing_forced_category", category))
                continue
            resolution = (row.get("resolution") or "").strip()
            if not _CATEGORY_RESOLUTION_RE.match(resolution):
                findings.append(Finding("bad_category_resolution", f"{category}: {resolution!r}"))
    return findings


def _check_rollout(artefact: artefacts.Artefact) -> list[Finding]:
    """`Rollout` carries no table of its own -- each of its five `### ` subsections does.

    A `Rollout` section with no `### ` subsection at all is prose-only,
    the same `missing_table` finding a flat table's absence would be.
    """
    findings: list[Finding] = []
    section = artefact.section("Rollout")
    if section is None or section.is_pending():
        return findings  # already reported by _check_sections
    subsections = {sub.title: sub for sub in section.subsections()}
    if not subsections:
        findings.append(Finding("missing_table", "Rollout"))
        return findings
    for name, columns in artefacts.PLAN_SUBTABLES["Rollout"].items():
        sub = subsections.get(name)
        if sub is None:
            findings.append(Finding("missing_table", f"Rollout.{name}"))
            continue
        try:
            header = sub.table_header()
        except artefacts.ArtefactError as exc:
            findings.append(Finding("malformed_table", f"Rollout.{name}: {exc}"))
            continue
        if header is None:
            findings.append(Finding("missing_table", f"Rollout.{name}"))
            continue
        if header != columns:
            findings.append(Finding("bad_table_columns", f"Rollout.{name}: {header}"))
        rows = sub.table() or []
        if not rows and name not in _ROLLOUT_EMPTY_ALLOWED:
            findings.append(Finding("empty_table", f"Rollout.{name}"))
    return findings


def _check_scope_actions(artefact: artefacts.Artefact) -> list[Finding]:
    findings: list[Finding] = []
    section = artefact.section("Scope and discretion")
    if section is None or section.is_pending():
        return findings
    for row in section.table() or []:
        action = (row.get("action") or "").strip()
        if action not in artefacts.SCOPE_ACTIONS:
            findings.append(Finding("bad_scope_action", f"{row.get('path')}: {action!r}"))
    return findings


def _check_contract_cells(artefact: artefacts.Artefact) -> list[Finding]:
    """Every `Contracts` field cell parses to one of the three states; semantic completeness is `plan_rubric`'s."""
    findings: list[Finding] = []
    section = artefact.section("Contracts")
    if section is None or section.is_pending():
        return findings
    for row in section.table() or []:
        for field in artefacts.CONTRACT_FIELDS:
            try:
                artefacts.contract_cell(row.get(field))
            except artefacts.ArtefactError:
                findings.append(Finding("bad_contract_cell", f"{row.get('unit')}.{field}: {row.get(field)!r}"))
    return findings


def _check_readiness(artefact: artefacts.Artefact) -> list[Finding]:
    findings: list[Finding] = []
    section = artefact.section("Readiness")
    if section is None or section.is_pending():
        return findings  # already reported by _check_sections
    rows = section.table() or []
    by_condition = {row.get("condition"): row for row in rows}
    for condition in artefacts.READINESS_CONDITIONS:
        row = by_condition.get(condition)
        if row is None:
            findings.append(Finding("missing_readiness_condition", condition))
            continue
        status = row.get("status")
        if status == "pending":
            findings.append(Finding("pending_readiness_row", condition))
        elif status == "blind_spot" and not (row.get("waiver_id") or "").strip():
            findings.append(Finding("pending_readiness_row", f"{condition}: blind_spot with no waiver_id"))
    return findings


def check(
    kind: str,
    text: str,
    *,
    tier: str | None = None,
    criteria_text: str | None = None,
    catalogue: dict | None = None,
    limits: dict | None = None,
    pending_allowed: bool = False,
) -> list[Finding]:
    """Every structural finding against `text` as an artefact of `kind`; an empty list is a pass.

    `tier`/`limits` (the tier's `length_limits` mapping from `tiers.yaml`)
    drive the plan-only ceiling rules; `catalogue` (`recipes.load_catalogue()`)
    and `criteria_text` drive the plan-only recipe and traceability rules.
    Any of the four left `None` skips just the rules that need it, so a
    caller checking a `brief` or `criteria` version never has to supply
    plan-only inputs. `pending_allowed` exempts a `pending answer` section
    left by a run that ended `blocked`, until the fresh rerun fills it.
    """
    if kind not in artefacts.SECTIONS:
        return [Finding("unknown_kind", kind)]
    try:
        artefact = artefacts.parse(text)
    except artefacts.ArtefactError as exc:
        return [Finding("parse_error", str(exc))]

    findings = _check_sections(kind, artefact, pending_allowed=pending_allowed)
    findings += _check_tables(kind, artefact)

    if kind == "criteria":
        findings += _check_criteria(artefact)

    if kind == "plan":
        if tier is not None and limits is not None:
            findings += _check_ceilings(artefact, tier=tier, limits=limits, text=text)
        findings += _check_tasks_and_traceability(artefact, criteria_text=criteria_text, catalogue=catalogue)
        findings += _check_readiness(artefact)
        findings += _check_rollout(artefact)
        findings += _check_scope_actions(artefact)
        findings += _check_contract_cells(artefact)
    return findings
