"""The bootstrap checklist: the expected human-verdict instance set, and the one write path for a verdict.

Until calibrated graders exist, every grader-only rubric line marked
`checklist: yes` across the pinned rubric files stands in for a human
judgment. `expected_instances` expands each such line by its own
`subject` into one or more `(rubric_line_id, subject_item_key)` pairs --
one for the stage's own artefact, one per acceptance criterion, one per
question, or one per contracts-table unit -- reading every subject item's
current membership fresh from the record each call, so the expected set
always matches what the ticket's artefacts and questions actually hold
right now. `record_verdict` is the sole writer of `human_verdict`;
`completeness` is the one place "is the checklist satisfied" is decided,
over the newest verdict per instance and the `waiver` rows that name one.

A rubric line's own stage decides which artefact kind its verdicts bind
to (`STAGE_ARTEFACT_KIND`): every instance a line expands to, whatever its
`subject`, verdicts against that stage's own latest artefact, since a
criterion or a contracts unit is read from that same artefact.
"""
import hashlib
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from runner import artefact_registry, artefacts, binding, canonical, definitions, record, rubrics, waivers
from runner.paths import FACTORY_DIR

# The three rubric files this ticket's checklist code reads by default;
# every real caller uses exactly this set, a test may pass its own.
DEFAULT_RUBRIC_PATHS: tuple[Path, ...] = (
    FACTORY_DIR / "rubrics" / "S1.md",
    FACTORY_DIR / "rubrics" / "S2.md",
    FACTORY_DIR / "rubrics" / "S3.md",
)

# The artefact kind an `artefact`-subject checklist line in a given
# stage's rubric names -- also the artefact every instance from that
# stage's rubric verdicts against, whatever its own subject kind.
STAGE_ARTEFACT_KIND: dict[str, str] = {"S1": "brief", "S2": "criteria", "S3": "plan"}

# human_verdict.verdict's closed set; the table carries no CHECK
# constraint of its own, so this module is the one place that enforces it.
VERDICTS: tuple[str, ...] = ("pass", "fail", "blind_spot")


class ChecklistError(ValueError):
    """The pinned rubrics assemble an inconsistent expected set: the same instance twice."""


@dataclass(frozen=True)
class Instance:
    rubric_line_id: str
    subject_item_key: str
    rubric_file: str
    rubric_hash: str


def _file_hash(path: Path) -> str:
    """sha256 of `path`'s exact bytes.

    The same algorithm `factory/manifest.yaml` records for a committed
    file, computed directly against the file rather than looked up in the
    manifest, so a caller can pin a rubric file the committed manifest
    never registered -- a test's own fixture under `tmp_path`.
    """
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stage_of(rubric_file: str) -> str:
    """The `stage` a rubric file's own front matter names."""
    return definitions.load_definition(Path(rubric_file))["stage"]


def _criterion_keys(conn: sqlite3.Connection, ticket: sqlite3.Row) -> list[str]:
    row = artefact_registry.latest(conn, ticket["id"], "criteria")
    if row is None:
        return []
    section = artefacts.parse(Path(row["path"]).read_text()).section("Acceptance criteria")
    table = section.table() if section is not None else None
    return [r["id"] for r in (table or []) if r.get("id")]


def _question_keys(conn: sqlite3.Connection, ticket: sqlite3.Row) -> list[str]:
    rows = conn.execute("SELECT id FROM question WHERE ticket_id = ? ORDER BY id", (ticket["id"],)).fetchall()
    return [str(row["id"]) for row in rows]


def _contract_unit_keys(conn: sqlite3.Connection, ticket: sqlite3.Row) -> list[str]:
    row = artefact_registry.latest(conn, ticket["id"], "plan")
    if row is None:
        return []
    section = artefacts.parse(Path(row["path"]).read_text()).section("Contracts")
    table = section.table() if section is not None else None
    return [r["unit"] for r in (table or []) if r.get("unit")]


def expected_instances(
    conn: sqlite3.Connection, ticket: sqlite3.Row, *, rubric_paths: tuple[Path, ...] = DEFAULT_RUBRIC_PATHS,
) -> tuple[Instance, ...]:
    """Every checklist instance the pinned rubrics assemble for `ticket`, read fresh from the record.

    Each `checklist: yes` grader line in `rubric_paths` expands by its own
    `subject`: `artefact` gives one instance keyed by its stage's artefact
    kind; `criterion` one per `AC-n` row of the latest criteria artefact;
    `question` one per question row of the ticket; `contract_unit` one
    per `Contracts` row of the latest plan. Raises `ChecklistError` when
    two lines assemble the identical `(rubric_line_id, subject_item_key)`
    pair, since the expected set is meant to be exactly that -- a set with
    no duplicate member.
    """
    criterion_keys = _criterion_keys(conn, ticket)
    question_keys = _question_keys(conn, ticket)
    contract_unit_keys = _contract_unit_keys(conn, ticket)
    subject_keys = {
        "criterion": criterion_keys,
        "question": question_keys,
        "contract_unit": contract_unit_keys,
    }

    instances: list[Instance] = []
    seen: set[tuple[str, str]] = set()
    for path in rubric_paths:
        stage = stage_of(str(path))
        rubric_file = str(path)
        rubric_hash = _file_hash(path)
        for line in rubrics.checklist_lines(rubrics.load(path)):
            keys = [STAGE_ARTEFACT_KIND[stage]] if line.subject == "artefact" else subject_keys[line.subject]
            for key in keys:
                pair = (line.id, key)
                if pair in seen:
                    raise ChecklistError(f"duplicate checklist instance {pair!r} from {path}")
                seen.add(pair)
                instances.append(
                    Instance(rubric_line_id=line.id, subject_item_key=key, rubric_file=rubric_file, rubric_hash=rubric_hash)
                )
    return tuple(instances)


def checklist_hash(instances: tuple[Instance, ...]) -> str:
    """The canonical set hash of `instances`, order-independent."""
    return binding.set_hash(
        {
            "rubric_line_id": instance.rubric_line_id,
            "subject_item_key": instance.subject_item_key,
            "rubric_file": instance.rubric_file,
            "rubric_hash": instance.rubric_hash,
        }
        for instance in instances
    )


def record_verdict(
    conn: sqlite3.Connection,
    *,
    ticket: sqlite3.Row,
    item: sqlite3.Row,
    instance: Instance,
    verdict: str,
    evidence_ids: list[int],
    waiver_id: int | None,
    reviewer_identity: str,
    reviewer_role: str,
    note: str | None,
    rubric_paths: tuple[Path, ...] = DEFAULT_RUBRIC_PATHS,
) -> int:
    """Insert one immutable `human_verdict` row for `instance` and return its id.

    A second verdict recorded later against the same instance is a
    correction, not an error: nothing here refuses it, the row is simply
    appended, and `completeness`/`verdict_set` always read the newest row
    per instance -- a duplicate *within one call* never arises, since one
    call names exactly one instance. Refuses an `instance` outside the
    ticket's currently expected set, a `pass` verdict with no evidence, and
    an evidence id that does not name one of this ticket's own artefacts.
    `waiver_id`, when given, is checked only for existence: a waiver row
    can never name this verdict before this call returns and its id is
    known, so linking one (`waiver.waived_human_verdict_id`) is always a
    separate, later write, and validating it against policy content is a
    later ticket's job -- this call only catches an obviously wrong id.
    """
    if verdict not in VERDICTS:
        raise ValueError(f"verdict must be one of {VERDICTS}, got {verdict!r}")
    expected = expected_instances(conn, ticket, rubric_paths=rubric_paths)
    if instance not in expected:
        raise ValueError(f"instance {instance!r} is outside ticket {ticket['id']}'s expected checklist")
    if verdict == "pass" and not evidence_ids:
        raise ValueError("a pass verdict requires at least one evidence id")
    if waiver_id is not None and record.get(conn, "waiver", waiver_id) is None:
        raise ValueError(f"no such waiver: {waiver_id}")

    artefact_kind = STAGE_ARTEFACT_KIND[stage_of(instance.rubric_file)]
    subject_artefact = artefact_registry.latest(conn, ticket["id"], artefact_kind)
    if subject_artefact is None:
        raise ValueError(f"ticket {ticket['id']} carries no {artefact_kind} artefact to verdict against")

    evidence_hashes: list[str] = []
    for evidence_id in evidence_ids:
        artefact_row = record.get(conn, "artefact", evidence_id)
        if artefact_row is None or artefact_row["ticket_id"] != ticket["id"]:
            raise ValueError(f"evidence id {evidence_id} is not an artefact of ticket {ticket['id']}")
        evidence_hashes.append(artefact_row["hash"])

    row = {
        "ticket_id": ticket["id"],
        "queue_item_id": item["id"],
        "rubric_line_id": instance.rubric_line_id,
        "subject_item_key": instance.subject_item_key,
        "rubric_file": instance.rubric_file,
        "rubric_hash": instance.rubric_hash,
        "subject_artefact_id": subject_artefact["id"],
        "subject_artefact_hash": subject_artefact["hash"],
        "verdict": verdict,
        "evidence_ids": canonical.canonical_json(list(evidence_ids)).decode(),
        "evidence_hashes": canonical.canonical_json(evidence_hashes).decode(),
        "note": note,
        "reviewer_identity": reviewer_identity,
        "reviewer_role": reviewer_role,
        "created_at": record.now(),
        "canonical_serialization_version": canonical.SERIALIZATION_VERSION,
    }
    row["content_hash"] = canonical.content_hash(row)
    return record.insert(conn, "human_verdict", **row)


@dataclass(frozen=True)
class Completeness:
    complete: bool
    missing: tuple[Instance, ...]
    unwaived_blind_spots: tuple[Instance, ...]
    failed: tuple[Instance, ...]


def _waived(conn: sqlite3.Connection, verdict_row: sqlite3.Row, *, now: str) -> bool:
    """Whether any `waiver` naming `verdict_row` is currently valid, not merely unexpired.

    Delegates to `runner.waivers.validity` -- the one place expiry, policy
    drift, lost actor authority, a changed subject, and changed evidence
    are all checked -- rather than re-testing expiry alone here.
    """
    rows = conn.execute(
        "SELECT id FROM waiver WHERE waived_human_verdict_id = ? ORDER BY id DESC", (verdict_row["id"],)
    ).fetchall()
    return any(waivers.validity(conn, row["id"], now=now).valid for row in rows)


def completeness(
    conn: sqlite3.Connection, ticket: sqlite3.Row, instances: tuple[Instance, ...],
) -> Completeness:
    """Whether every instance in `instances` has a satisfying newest verdict.

    "Newest" is decided per instance by row id, since `human_verdict` rows
    are append-only and a correction is always a later row. A `blind_spot`
    verdict counts against completeness unless an unexpired `waiver` row
    names that exact verdict row -- a correction's fresh row is therefore
    unwaived again until a fresh waiver names it in turn.
    """
    now = record.now()
    latest_by_key: dict[tuple[str, str], sqlite3.Row] = {}
    for row in conn.execute(
        "SELECT * FROM human_verdict WHERE ticket_id = ? ORDER BY id", (ticket["id"],)
    ).fetchall():
        latest_by_key[(row["rubric_line_id"], row["subject_item_key"])] = row

    missing: list[Instance] = []
    unwaived_blind_spots: list[Instance] = []
    failed: list[Instance] = []
    for instance in instances:
        row = latest_by_key.get((instance.rubric_line_id, instance.subject_item_key))
        if row is None:
            missing.append(instance)
        elif row["verdict"] == "fail":
            failed.append(instance)
        elif row["verdict"] == "blind_spot" and not _waived(conn, row, now=now):
            unwaived_blind_spots.append(instance)

    complete = not missing and not unwaived_blind_spots and not failed
    return Completeness(complete, tuple(missing), tuple(unwaived_blind_spots), tuple(failed))


def verdict_set(conn: sqlite3.Connection, ticket_id: int) -> list[dict]:
    """The newest `human_verdict` row per `(rubric_line_id, subject_item_key)` instance, as dicts."""
    latest: dict[tuple[str, str], dict] = {}
    for row in conn.execute(
        "SELECT * FROM human_verdict WHERE ticket_id = ? ORDER BY id", (ticket_id,)
    ).fetchall():
        latest[(row["rubric_line_id"], row["subject_item_key"])] = dict(row)
    return list(latest.values())


def waiver_set(conn: sqlite3.Connection, ticket_id: int) -> list[dict]:
    """Every `waiver` row naming one of `ticket_id`'s `human_verdict` rows, as dicts."""
    rows = conn.execute(
        "SELECT waiver.* FROM waiver JOIN human_verdict ON human_verdict.id = waiver.waived_human_verdict_id "
        "WHERE human_verdict.ticket_id = ?",
        (ticket_id,),
    ).fetchall()
    return [dict(row) for row in rows]
