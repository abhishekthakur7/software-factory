"""The general artefact structure check: fixed sections, fixed table columns, ceilings, and plan-specific rules.

One check function covers every artefact kind `runner.artefacts.SECTIONS`
names: it walks the fixed section list, the fixed table columns for
whichever of `BRIEF_TABLES`/`CRITERIA_TABLES`/`PLAN_TABLES` applies, and,
for the `plan` kind only, the extra rules a plan carries on top -- length
ceilings, first-page placement, typed validation recipes instead of
free-form shell, and two-way `AC-n` traceability against the criteria
artefact. A `Finding` names the rule that failed and enough detail to find
it in the text; an empty list is a pass. Nothing here writes to the
database or the filesystem -- a caller turns findings into a `check_result`
row and an outcome.
"""
from typing import NamedTuple

from runner import artefacts

# Tables checked by document kind: only a kind an agent actually files
# tables under gets one; `packet` carries none yet (its real fixed content
# is a later ticket's placeholder is a plain prose kind for now).
KIND_TABLES: dict[str, dict[str, tuple[str, ...]]] = {
    "brief": artefacts.BRIEF_TABLES,
    "criteria": artefacts.CRITERIA_TABLES,
    "plan": artefacts.PLAN_TABLES,
}

# The one fixed table allowed to carry zero rows: an empty dependency list
# is itself the finding ("nothing changed"), written explicitly rather than
# omitted.
_EMPTY_TABLE_ALLOWED: frozenset[tuple[str, str]] = frozenset({("plan", "Dependencies")})

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

    if kind == "plan":
        if tier is not None and limits is not None:
            findings += _check_ceilings(artefact, tier=tier, limits=limits, text=text)
        findings += _check_tasks_and_traceability(artefact, criteria_text=criteria_text, catalogue=catalogue)
        findings += _check_readiness(artefact)
    return findings
