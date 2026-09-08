"""Rubric files: one table of rubric lines per stage, parsed here for every reader.

A stage's rubric (`factory/rubrics/S<n>.md`) is hand-written: front matter
(`name`, `kind: rubric`, `stage`) and one pipe table with the columns in
`COLUMNS`, one row per rubric line. A PRD requirement row that is both a
script check and a grader judgment appears as two lines, one per half,
so a line id is `<row>:<half>` and is stable for as long as the row id is
(retired ids are never reused). `checklist` marks a grader line that the
bootstrap checklist stands in for until calibrated graders exist; its
`judgment` is the pass-or-fail sentence a human reviewer applies. The
line id set derived here is what the checklist assembler expects every
`human_verdict` to cover, so a rubric edit changes that expected set
through this one parser rather than through a second copy of the table.
"""
from dataclasses import dataclass
from pathlib import Path

from runner import artefacts, definitions

COLUMNS: tuple[str, ...] = ("line", "row", "half", "checklist", "judgment")
HALVES: tuple[str, ...] = ("script", "grader")


class RubricError(ValueError):
    """The rubric file's table is missing, misshapen, or names an inconsistent line."""


@dataclass(frozen=True)
class Line:
    id: str
    row: str
    half: str
    checklist: bool
    judgment: str


def _to_bool(value: str, *, path: Path, line_id: str) -> bool:
    if value in ("yes", "true"):
        return True
    if value in ("no", "false", ""):
        return False
    raise RubricError(f"{path}: line {line_id!r} has checklist {value!r}, expected yes or no")


def load(path: Path) -> tuple[Line, ...]:
    """Every rubric line in `path`, in file order; a file with front matter but no table has none."""
    definition = definitions.load_definition(path)
    if definition["kind"] != "rubric":
        raise RubricError(f"{path}: kind is {definition['kind']!r}, not a rubric")
    table_lines = [line for line in definition["body"].splitlines() if line.lstrip().startswith("|")]
    if not table_lines:
        return ()
    try:
        rows = artefacts.parse_table(table_lines)
    except artefacts.ArtefactError as exc:
        raise RubricError(f"{path}: {exc}") from exc
    if rows and tuple(rows[0].keys()) != COLUMNS:
        raise RubricError(f"{path}: rubric table columns are {tuple(rows[0].keys())}, expected {COLUMNS}")
    lines: list[Line] = []
    seen: set[str] = set()
    for row in rows:
        line_id, row_id, half = row["line"], row["row"], row["half"]
        if half not in HALVES:
            raise RubricError(f"{path}: line {line_id!r} has half {half!r}, expected one of {HALVES}")
        if line_id != f"{row_id}:{half}":
            raise RubricError(f"{path}: line id {line_id!r} must be {row_id}:{half}")
        if line_id in seen:
            raise RubricError(f"{path}: duplicate rubric line {line_id!r}")
        if not row["judgment"]:
            raise RubricError(f"{path}: line {line_id!r} has no judgment")
        seen.add(line_id)
        checklist = _to_bool(row["checklist"], path=path, line_id=line_id)
        if checklist and half != "grader":
            raise RubricError(f"{path}: line {line_id!r} is a script line and cannot be a checklist line")
        lines.append(Line(id=line_id, row=row_id, half=half, checklist=checklist, judgment=row["judgment"]))
    return tuple(lines)


def line(lines, row: str, half: str) -> Line | None:
    """The line for `row` and `half`, or None."""
    for item in lines:
        if item.row == row and item.half == half:
            return item
    return None


def checklist_lines(lines) -> tuple[Line, ...]:
    """The grader lines the bootstrap checklist stands in for."""
    return tuple(item for item in lines if item.checklist)
