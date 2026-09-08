"""Markdown artefacts: fixed section lists and pipe tables, parsed and rendered in exactly one place.

An agent-authored artefact (`brief`, `criteria`, `plan`, `packet`) is one
Markdown file: optional YAML front matter, then `## ` sections in the
fixed order the PRD's "Produces" paragraph for that stage states, with
tables as ordinary pipe tables inside the section that owns them. Every
script that reads an artefact -- the structure check, the size gate,
`handoff_ready`, the traceability check, the stage drivers -- parses it
through this module, so the section names, the table columns and the
parsing rules have one home and a human can read the same file the
scripts read. A section whose whole body is the `pending answer` marker
was left open by a run that ended `blocked`; readers treat it as absent
until the rerun fills it.
"""
import re
from dataclasses import dataclass

import yaml

# The fixed section list per artefact kind, in the order the file must
# carry them. `packet` is a stipulated placeholder until the S6 packet is
# built for real; the structure check applies it as written until then.
SECTIONS: dict[str, tuple[str, ...]] = {
    "brief": (
        "Ticket summary",
        "Linked sources",
        "Touched area candidates",
        "History",
        "Impact evidence",
        "Flags",
        "Blind spots",
        "Unknowns",
        "Index entries used",
        "Final tier",
        "Pilot-exclusion recheck",
        "Blockers",
    ),
    "criteria": (
        "Acceptance criteria",
        "Forced categories",
        "Agreement check",
        "Size estimate",
        "Completeness verdict",
    ),
    "plan": (
        "Intent and scrutiny",
        "Readiness",
        "Risk map",
        "Goals and non-goals",
        "Approach",
        "Alternatives",
        "Scope and discretion",
        "Dependencies",
        "Archaeology and characterization tests",
        "Abstraction and separate debt",
        "Contracts",
        "Semantic-contract checklist",
        "Tasks",
        "Test strategy",
        "Rollout",
        "Size",
        "Impact evidence and blind spots",
        "Assumptions",
        "Unknowns",
        "Required approvers",
    ),
    "packet": (
        "Summary",
        "Evidence",
        "Test summary",
        "Approvers",
    ),
}

# The plan's fixed tables: the section that owns each and its exact
# columns. The readiness table is derived by `handoff_ready` and does not
# count against the row ceiling; every other table is agent-authored.
PLAN_TABLES: dict[str, tuple[str, ...]] = {
    "Readiness": ("condition", "status", "source_artefact", "hash", "waiver_id", "note"),
    "Scope and discretion": ("path", "action", "reason"),
    "Dependencies": ("package", "from_version", "to_version", "kind", "reason"),
    "Contracts": (
        "unit", "kind", "source_declaration", "input", "output", "errors", "side_effects", "invariants",
        "authorization", "ordering_concurrency", "transaction_persistence", "compatibility",
    ),
    "Tasks": (
        "id", "title", "depends_on", "criteria", "files", "validation_recipe", "validation_args",
        "expected_result", "no_behaviour_change",
    ),
    "Test strategy": ("test", "action", "size", "criteria", "proves"),
    "Size": ("estimated_lines", "estimated_files", "basis", "justification"),
}

READINESS_CONDITIONS: tuple[str, ...] = (
    "restatement_agreed", "questions_closed", "impact_evidence", "risk_map", "linked_sources", "size_gate",
    "reviewer_set",
)
READINESS_STATUSES: tuple[str, ...] = ("pass", "blind_spot", "pending")

# The brief's tables, by owning section. Sections not named here are
# prose. `Final tier` is written by the S1 driver from the counts the
# agent reports, never by the agent itself.
BRIEF_TABLES: dict[str, tuple[str, ...]] = {
    "Linked sources": ("source", "date"),
    "Touched area candidates": ("path", "reason"),
    "History": ("path", "classification", "evidence"),
    "Impact evidence": ("direction", "dependency", "method", "source", "mapping", "owner", "coverage", "blind_spots"),
    "Flags": ("flag", "reference"),
    "Blind spots": ("item", "assumption"),
    "Unknowns": ("unknown", "tried"),
    "Index entries used": ("entry", "last_verified", "stale"),
    "Final tier": ("files_touched", "services_touched", "unknowns", "tier_provisional", "tier_final"),
}
HISTORY_CLASSIFICATIONS: tuple[str, ...] = ("explained", "unexplained", "contradictory")
IMPACT_COVERAGES: tuple[str, ...] = ("authoritative", "partial", "unknown")

# The criteria artefact's tables. `Acceptance criteria` holds one row per
# `AC-n`; `state` is `formalised`, `unformalisable` or `provisional`.
CRITERIA_TABLES: dict[str, tuple[str, ...]] = {
    "Acceptance criteria": ("id", "source", "precondition", "trigger", "system", "response", "example", "state"),
    "Forced categories": ("category", "resolution", "reference"),
    "Agreement check": ("id", "samples", "agreed", "note"),
    "Size estimate": ("estimated_lines", "estimated_files", "basis"),
}
CRITERIA_COLUMNS: tuple[str, ...] = CRITERIA_TABLES["Acceptance criteria"]
CRITERION_STATES: tuple[str, ...] = ("formalised", "unformalisable", "provisional")
FORCED_CATEGORIES: tuple[str, ...] = (
    "error paths", "concurrency", "migration", "backward compatibility", "permissions", "observability", "rollback",
    "data retention",
)

PENDING_MARKER = "pending answer"

_HEADING = re.compile(r"^## (.+?)\s*$")
_TABLE_SEPARATOR = re.compile(r"^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$")


class ArtefactError(ValueError):
    """The text is not an artefact this module can read: malformed front matter or an unreadable table."""


@dataclass(frozen=True)
class Section:
    title: str
    body: str

    def is_pending(self) -> bool:
        """True when the section holds only the `pending answer` marker a blocked run left behind."""
        return self.body.strip().lower() == PENDING_MARKER

    def is_empty(self) -> bool:
        return not self.body.strip()

    def _table_blocks(self) -> list[list[str]]:
        blocks: list[list[str]] = []
        block: list[str] = []
        for line in [*self.body.splitlines(), ""]:
            if line.lstrip().startswith("|"):
                block.append(line)
                continue
            if block:
                blocks.append(block)
                block = []
        return blocks

    def tables(self) -> list[list[dict[str, str]]]:
        """Every pipe table in the section, each as a list of row dicts keyed by its header cells."""
        return [parse_table(block) for block in self._table_blocks()]

    def table(self) -> list[dict[str, str]] | None:
        """The section's first table, or None when it carries none."""
        tables = self.tables()
        return tables[0] if tables else None

    def table_header(self) -> tuple[str, ...] | None:
        """The section's first table's column names, or None when it carries no table.

        `table()`'s row dicts lose the header entirely when a table has zero
        data rows (an explicitly empty table, allowed for a handful of
        fixed tables) -- a structure check that must still validate that
        table's exact columns needs the header on its own, independent of
        row count.
        """
        blocks = self._table_blocks()
        if not blocks:
            return None
        rows = [line for line in blocks[0] if line.strip()]
        if len(rows) < 2 or not _TABLE_SEPARATOR.match(rows[1]):
            raise ArtefactError("a pipe table needs a header row and a separator row")
        return tuple(_split_cells(rows[0]))

    def prose(self) -> str:
        """The section body with every table line removed."""
        return "\n".join(line for line in self.body.splitlines() if not line.lstrip().startswith("|")).strip()


@dataclass(frozen=True)
class Artefact:
    front_matter: dict
    sections: tuple[Section, ...]

    def titles(self) -> tuple[str, ...]:
        return tuple(section.title for section in self.sections)

    def section(self, title: str) -> Section | None:
        for section in self.sections:
            if section.title == title:
                return section
        return None


def _split_cells(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|") and not stripped.endswith("\\|"):
        stripped = stripped[:-1]
    # An escaped pipe is a literal cell character, not a column break.
    parts = re.split(r"(?<!\\)\|", stripped)
    return [part.replace("\\|", "|").strip() for part in parts]


def parse_table(lines: list[str]) -> list[dict[str, str]]:
    """Rows of one pipe table as dicts keyed by header cell; a short row is padded, a long row is an error."""
    rows = [line for line in lines if line.strip()]
    if len(rows) < 2 or not _TABLE_SEPARATOR.match(rows[1]):
        raise ArtefactError("a pipe table needs a header row and a separator row")
    columns = _split_cells(rows[0])
    parsed = []
    for line in rows[2:]:
        cells = _split_cells(line)
        if len(cells) > len(columns):
            raise ArtefactError(f"table row has {len(cells)} cells for {len(columns)} columns: {line.strip()!r}")
        cells += [""] * (len(columns) - len(cells))
        parsed.append(dict(zip(columns, cells)))
    return parsed


def _front_matter(text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end == -1:
        raise ArtefactError("unterminated front matter")
    try:
        parsed = yaml.safe_load(text[4:end])
    except yaml.YAMLError as exc:
        raise ArtefactError(f"invalid YAML front matter: {exc}") from exc
    if parsed is not None and not isinstance(parsed, dict):
        raise ArtefactError("front matter is not a mapping")
    return parsed or {}, text[end + len("\n---"):].lstrip("\n")


def parse(text: str) -> Artefact:
    """Split `text` into its front matter and `## ` sections; text before the first section heading is dropped."""
    front_matter, body = _front_matter(text)
    sections: list[Section] = []
    title: str | None = None
    lines: list[str] = []
    for line in body.splitlines():
        match = _HEADING.match(line)
        if match:
            if title is not None:
                sections.append(Section(title, "\n".join(lines).strip("\n")))
            title, lines = match.group(1), []
        elif title is not None:
            lines.append(line)
    if title is not None:
        sections.append(Section(title, "\n".join(lines).strip("\n")))
    return Artefact(front_matter=front_matter, sections=tuple(sections))


def render_table(columns, rows) -> str:
    """One pipe table from `columns` and row dicts; a missing cell renders empty, a pipe in a cell is escaped."""
    def cell(value) -> str:
        return "" if value is None else str(value).replace("|", "\\|")

    header = "| " + " | ".join(columns) + " |"
    separator = "|" + "|".join("---" for _ in columns) + "|"
    body = ["| " + " | ".join(cell(row.get(column)) for column in columns) + " |" for row in rows]
    return "\n".join([header, separator, *body])


def render(sections, *, front_matter: dict | None = None) -> str:
    """One artefact text from `(title, body)` pairs, with optional front matter first."""
    parts: list[str] = []
    if front_matter:
        parts.append("---\n" + yaml.safe_dump(front_matter, sort_keys=False).strip() + "\n---\n")
    for title, body in sections:
        parts.append(f"## {title}\n\n{body.rstrip()}\n")
    return "\n".join(parts)


def word_count(text: str) -> int:
    return len(text.split())
