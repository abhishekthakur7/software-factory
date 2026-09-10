"""Tags: the one place any `tag` row is written.

Every event recorded against a human transition -- a send-back, an
abandonment, a tier override, a request for changes, a control-defect
observation -- goes through `tag`, so the target-shape and required-field
rules below are enforced exactly once rather than re-checked at each call
site. `target` is validated against the record before insert: an unknown
target kind or a target row that does not exist fails before anything is
written, and the tag's own `ticket_id` is derived from that row rather than
taken on faith from the caller. `fm_id` must name a real catalogue entry,
and the acting identity must match the kind's own human-or-mechanical
shape, so neither a fabricated failure mode nor a misattributed actor ever
reaches the row.
"""
import sqlite3
from pathlib import Path

from runner import artefacts, record, waivers
from runner.paths import FACTORY_DIR
from runner.schema import STAGES, TAG_EVENT_KINDS

DEFAULT_CATALOGUE_PATH = FACTORY_DIR / "catalogue" / "failure-modes.md"
DEFAULT_SEND_BACK_GROUNDS_PATH = FACTORY_DIR / "rubrics" / "checklists" / "send-back-grounds.md"

# event kinds the entity definition marks severity-required; every other
# kind leaves severity null.
SEVERITY_REQUIRED_KINDS = frozenset({"incident", "control_defect", "policy_exception"})

# The target shapes `tag` accepts: `<table>:<id>` for these tables, each of
# whose rows carries `ticket_id` (or, for `ticket`, is the ticket).
_TARGET_TABLES: frozenset[str] = frozenset(
    {"ticket", "stage_run", "approval_record", "queue_item", "artefact", "question", "waiver"}
)

# The one identity the factory itself writes tags under; a human identity
# never matches this string (see `MECHANICAL_KINDS` below).
MECHANICAL_ACTOR = "runner"

# Event kinds only the factory writes -- the entity definition's exception
# to "tagged_by is a human". A `control_defect` is in neither set: the
# factory writes one it detects mechanically and an incident reviewer
# writes one they observe, so that kind accepts either actor. Every other
# kind is a decision a human made against the factory's output and refuses
# the mechanical actor, so provenance can never be spoofed either way.
MECHANICAL_KINDS: frozenset[str] = frozenset({"stale_index", "escalation"})
EITHER_ACTOR_KINDS: frozenset[str] = frozenset({"control_defect"})

# `packet_defect` names one fixed failure mode: the review-narrative gap
# the entity definition and catalogue both call unreviewable_diff.
PACKET_DEFECT_FM_ID = "unreviewable_diff"

# send_back grounds whose note carries an extra requirement beyond naming
# a real ground id.
_OTHER_GROUND = "other"
_WRONG_STAGE_GROUND = "wrong_brief_or_criteria"


class TagRefused(ValueError):
    """The target, kind, fm_id, actor, note, or resolution fails validation before any row is written."""


def failure_modes(path: Path = DEFAULT_CATALOGUE_PATH) -> dict[str, dict]:
    """The catalogue's `id -> row` mapping, parsed from `failure-modes.md`'s `Failure modes` table."""
    parsed = artefacts.parse(path.read_text())
    section = parsed.section("Failure modes")
    rows = section.table() if section is not None else None
    return {row["id"]: row for row in (rows or [])}


def send_back_grounds(path: Path = DEFAULT_SEND_BACK_GROUNDS_PATH) -> dict[str, dict]:
    """The checklist's `ground -> row` mapping, parsed from `send-back-grounds.md`'s `Grounds` table."""
    parsed = artefacts.parse(path.read_text())
    section = parsed.section("Grounds")
    rows = section.table() if section is not None else None
    return {row["ground"]: row for row in (rows or [])}


def _resolve_target(conn: sqlite3.Connection, target: str) -> tuple[str, int, int]:
    """`(table, target_id, ticket_id)` for `target`, after checking it names a real row."""
    table, _, raw_id = target.partition(":")
    if table not in _TARGET_TABLES or not raw_id:
        raise TagRefused(f"tag target must be one of {sorted(_TARGET_TABLES)}, got {target!r}")
    try:
        target_id = int(raw_id)
    except ValueError as exc:
        raise TagRefused(f"tag target id is not an integer: {target!r}") from exc
    row = record.get(conn, table, target_id)
    if row is None:
        raise TagRefused(f"no such {table}: {target_id}")
    ticket_id = target_id if table == "ticket" else row["ticket_id"]
    return table, target_id, ticket_id


def _validate_actor(kind: str, actor: str) -> None:
    if kind in MECHANICAL_KINDS:
        if actor != MECHANICAL_ACTOR:
            raise TagRefused(f"a {kind!r} tag is written mechanically; actor must be {MECHANICAL_ACTOR!r}, got {actor!r}")
    elif actor == MECHANICAL_ACTOR and kind not in EITHER_ACTOR_KINDS:
        raise TagRefused(f"a {kind!r} tag is a human decision; actor may not be {MECHANICAL_ACTOR!r}")


def _validate_send_back_note(note: str | None) -> None:
    """The note must open `<ground>: <text>` naming a real ground; `other` and the wrong-stage ground add their own rule."""
    ground_id, sep, rest = (note or "").partition(":")
    ground_id = ground_id.strip()
    if not sep or ground_id not in send_back_grounds():
        raise TagRefused(f"send_back note must open with one of the checklist's ground ids: {note!r}")
    rest = rest.strip()
    if ground_id == _OTHER_GROUND and not rest:
        raise TagRefused("a send_back tag grounded 'other' requires text after the colon")
    if ground_id == _WRONG_STAGE_GROUND and not any(stage in rest for stage in STAGES):
        raise TagRefused("a send_back tag grounded 'wrong_brief_or_criteria' must name the target stage in its note")


def _validate_policy_exception(conn: sqlite3.Connection, table: str, target_id: int) -> None:
    """A policy exception classifies a valid waiver; it never grants one -- callers still ask `waivers` for authority."""
    if table != "waiver":
        raise TagRefused("a policy_exception tag must target a waiver: <id>")
    validity = waivers.validity(conn, target_id)
    if not validity.valid:
        raise TagRefused(f"policy_exception tag references an invalid waiver: {', '.join(validity.reasons)}")


def _validate_resolution(
    conn: sqlite3.Connection, resolves_tag_id: int | None, resolution_evidence_ref: str | None, ticket_id: int,
) -> None:
    if (resolves_tag_id is None) != (resolution_evidence_ref is None):
        raise TagRefused("resolves_tag_id and resolution_evidence_ref must both be given or both omitted")
    if resolves_tag_id is None:
        return
    resolved = record.get(conn, "tag", resolves_tag_id)
    if resolved is None:
        raise TagRefused(f"no such tag to resolve: {resolves_tag_id}")
    if resolved["ticket_id"] != ticket_id:
        raise TagRefused("a resolution tag must belong to the same ticket as the tag it resolves")
    if resolved["event_kind"] != "packet_defect":
        raise TagRefused("a resolution tag may only resolve a packet_defect tag")


def tag(
    conn: sqlite3.Connection,
    *,
    target: str,
    kind: str,
    fm_id: str,
    actor: str,
    note: str | None = None,
    severity: str | None = None,
    resolves_tag_id: int | None = None,
    resolution_evidence_ref: str | None = None,
) -> int:
    """Insert one immutable `tag` row naming `target`'s event and return its id."""
    if kind not in TAG_EVENT_KINDS:
        raise TagRefused(f"unknown tag kind: {kind!r}")
    if not fm_id:
        raise TagRefused(f"a {kind!r} tag requires a failure-mode id")
    if fm_id not in failure_modes():
        raise TagRefused(f"fm_id does not name a catalogue failure mode: {fm_id!r}")
    if kind == "packet_defect" and fm_id != PACKET_DEFECT_FM_ID:
        raise TagRefused(f"a packet_defect tag is always {PACKET_DEFECT_FM_ID!r}, got {fm_id!r}")
    if kind in SEVERITY_REQUIRED_KINDS and not severity:
        raise TagRefused(f"a {kind!r} tag requires a severity")
    _validate_actor(kind, actor)
    if kind == "send_back":
        _validate_send_back_note(note)
    table, target_id, ticket_id = _resolve_target(conn, target)
    if kind == "policy_exception":
        _validate_policy_exception(conn, table, target_id)
    _validate_resolution(conn, resolves_tag_id, resolution_evidence_ref, ticket_id)
    return record.insert(
        conn,
        "tag",
        ticket_id=ticket_id,
        event_kind=kind,
        fm_id=fm_id,
        ref=target,
        severity=severity,
        note=note,
        tagged_by=actor,
        tagged_at=record.now(),
        resolves_tag_id=resolves_tag_id,
        resolution_evidence_ref=resolution_evidence_ref,
    )
