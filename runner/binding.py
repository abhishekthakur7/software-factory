"""Bindings: canonical subject hashes and the plan/review evidence tuples they hash into.

A binding fixes exactly what a decision refers to: hash the tuple's bound
fields, and any later drift away from those fields is a different subject,
never the same one silently reinterpreted. `set_hash` is the one routine
for hashing an unordered collection into one subject hash — the
question-resolution set, the current-assumption set, the human-verdict
set, the plan-waiver set, and the deviation set all use it, so a new
answer or a superseding assumption changes a set hash the same way any
other member change does. `PlanComponents` and `ReviewComponents` name
every field the plan and review `evidence_tuple` rows bind;
`create_plan_tuple` and `create_review_tuple` write them through
`record.insert`, hashing the full row exactly as
`approvals.record_approval` hashes an approval record, so the stored
`content_hash` is always recomputable from the row alone and never carries
meaning the row itself does not. `plan_tuple_currency` compares a stored
plan tuple against a caller-supplied current `PlanComponents` without ever
reading `ticket` or any config file itself: every bound hash and SHA this
module touches arrives as an argument, so a later change to
how a hash is derived, or adds a real trust profile or recipe catalogue,
never changes this module. `preflight_review_tuple` is the S5 preflight:
it constructs a review tuple only after checking, in order, that the plan
tuple is current, plan quorum holds against its exact content hash, the
actual and effective reviewer sets are the ones the approval subject
expects, the target base is current, and head/diff are present — any
failure raises before the single write that creates the row.
"""
import json
import sqlite3
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from runner import approvals, canonical, record, schema
from runner.reviewer_sets import Slot, merge_slots


def set_hash(items: Iterable[Mapping]) -> str:
    """The canonical hash of the sorted canonical hashes of `items`.

    Sorting the member hashes before hashing the set makes the result
    independent of insertion order, so a set behaves like a set: two scans
    that recorded the same members in a different order hash the same,
    while adding, removing, or superseding one member always changes it.
    """
    member_hashes = sorted(canonical.content_hash(item) for item in items)
    return canonical.content_hash({"members": member_hashes})


def deviation_set_hash(conn: sqlite3.Connection, ticket_id: int) -> str:
    """`set_hash` over `ticket_id`'s `deviation` rows, `id` and `stage_run_id` excluded.

    `id` drops out through `content_hash`'s own default exclusion;
    `stage_run_id` is dropped here because it names which attempt wrote
    the row, not what the row means -- an S5 review tuple binds this hash
    to compare deviation sets across attempts, so two otherwise-identical
    rows written by different attempts must hash as the same member. The
    empty set (no deviation rows) hashes just like any other set, which is
    exactly the explicit, canonical hash a deviation-free hand-back
    records.
    """
    rows = conn.execute("SELECT * FROM deviation WHERE ticket_id = ? ORDER BY id", (ticket_id,)).fetchall()
    items = [{k: v for k, v in dict(row).items() if k != "stage_run_id"} for row in rows]
    return set_hash(items)


# One-to-one onto the plan `evidence_tuple` columns (common columns plus
# the plan-only columns); order matches the ticket-record's field list.
PLAN_COMPONENT_FIELDS: tuple[str, ...] = (
    "ticket_source_hash",
    "brief_hash",
    "criteria_hash",
    "plan_hash",
    "question_resolution_set_hash",
    "current_assumption_set_hash",
    "base_sha",
    "target_base_sha",
    "manifest_hash",
    "project_config_hash",
    "trust_profile_hash",
    "trust_approval_set_hash",
    "recipe_hash",
    "sandbox_digest",
    "toolchain_digest",
    "planned_reviewer_set_hash",
    "semantic_checklist_hash",
    "human_verdict_set_hash",
    "plan_waiver_set_hash",
)


@dataclass(frozen=True)
class PlanComponents:
    """Every field a `plan` `evidence_tuple` row binds; its `content_hash` is the plan-approval subject.

    Sandbox and toolchain digests are seeded placeholder inputs for now —
    their real values arrive once something actually derives them — but
    this module treats every field alike: an opaque string it hashes and
    compares, never derives.
    """

    ticket_source_hash: str
    brief_hash: str
    criteria_hash: str
    plan_hash: str
    question_resolution_set_hash: str
    current_assumption_set_hash: str
    base_sha: str
    target_base_sha: str
    manifest_hash: str
    project_config_hash: str
    trust_profile_hash: str
    trust_approval_set_hash: str
    recipe_hash: str
    sandbox_digest: str
    toolchain_digest: str
    planned_reviewer_set_hash: str
    semantic_checklist_hash: str
    human_verdict_set_hash: str
    plan_waiver_set_hash: str


# One-to-one onto the review `evidence_tuple` columns (the review-only
# columns plus the seven hashes it shares with the plan tuple).
REVIEW_COMPONENT_FIELDS: tuple[str, ...] = (
    "plan_tuple_id",
    "plan_approval_set_hash",
    "head_sha",
    "diff_hash",
    "deviation_set_hash",
    "target_base_sha",
    "actual_reviewer_set_id",
    "actual_reviewer_set_hash",
    "effective_reviewer_set_id",
    "effective_reviewer_set_hash",
    "manifest_hash",
    "project_config_hash",
    "trust_profile_hash",
    "trust_approval_set_hash",
    "recipe_hash",
    "sandbox_digest",
    "toolchain_digest",
)


@dataclass(frozen=True)
class ReviewComponents:
    """Every field a `review` `evidence_tuple` row binds beyond the plan tuple it references."""

    plan_tuple_id: int
    plan_approval_set_hash: str
    head_sha: str
    diff_hash: str
    deviation_set_hash: str
    target_base_sha: str
    actual_reviewer_set_id: int
    actual_reviewer_set_hash: str
    effective_reviewer_set_id: int
    effective_reviewer_set_hash: str
    manifest_hash: str
    project_config_hash: str
    trust_profile_hash: str
    trust_approval_set_hash: str
    recipe_hash: str
    sandbox_digest: str
    toolchain_digest: str


def _require_present(component_fields: tuple[str, ...], components) -> None:
    """Raise before any write when a bound component is missing (`None`)."""
    missing = [name for name in component_fields if getattr(components, name) is None]
    if missing:
        raise ValueError(f"missing required component(s): {', '.join(missing)}")


def _create_tuple(
    conn: sqlite3.Connection,
    *,
    kind: str,
    ticket_id: int,
    components,
    component_fields: tuple[str, ...],
) -> int:
    _require_present(component_fields, components)
    columns = {column.name for column in schema.table("evidence_tuple").columns}
    row = {name: None for name in columns}
    row.update({name: getattr(components, name) for name in component_fields})
    row["kind"] = kind
    row["ticket_id"] = ticket_id
    row["created_at"] = record.now()
    row["canonical_serialization_version"] = canonical.SERIALIZATION_VERSION
    row.pop("id")
    row["content_hash"] = canonical.content_hash(row)
    return record.insert(conn, "evidence_tuple", **row)


def create_plan_tuple(conn: sqlite3.Connection, ticket_id: int, components: PlanComponents) -> int:
    """Insert one `plan` `evidence_tuple` row; its `content_hash` is exactly the plan-approval subject."""
    return _create_tuple(
        conn, kind="plan", ticket_id=ticket_id, components=components,
        component_fields=PLAN_COMPONENT_FIELDS,
    )


def create_review_tuple(conn: sqlite3.Connection, ticket_id: int, components: ReviewComponents) -> int:
    """Insert one `review` `evidence_tuple` row referencing its plan tuple."""
    return _create_tuple(
        conn, kind="review", ticket_id=ticket_id, components=components,
        component_fields=REVIEW_COMPONENT_FIELDS,
    )


@dataclass(frozen=True)
class Currency:
    current: bool
    # The bound field names whose stored value differs from `current`'s.
    changed: tuple[str, ...]


def plan_tuple_currency(conn: sqlite3.Connection, plan_tuple_id: int, current: PlanComponents) -> Currency:
    """Compare the stored plan tuple's bound fields against `current`; the row is never touched.

    `current` is supplied by the caller, never read from `ticket` or any
    config here — a field this module does not bind (`head_sha` is not a
    `PlanComponents` field) can therefore never appear in `changed`, which
    is what makes an S4 hand-back that only advances `head_sha` leave a
    plan tuple current: there is no bound field for it to disagree on.
    """
    row = record.get(conn, "evidence_tuple", plan_tuple_id)
    if row is None:
        raise LookupError(f"no evidence_tuple {plan_tuple_id}")
    changed = tuple(
        name for name in PLAN_COMPONENT_FIELDS if row[name] != getattr(current, name)
    )
    return Currency(current=not changed, changed=changed)


class PreflightRefused(Exception):
    """S5 preflight found a missing or stale candidate component; no review tuple was created."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _slots_of(row: sqlite3.Row) -> list[Slot]:
    return [Slot.from_json(item) for item in json.loads(row["slots"] or "[]")]


def _reviewer_set_by_id(
    conn: sqlite3.Connection, reviewer_set_id: int | None, ticket_id: int, kind: str, expected_hash: str,
) -> sqlite3.Row:
    row = record.get(conn, "reviewer_set", reviewer_set_id) if reviewer_set_id is not None else None
    if row is None or row["ticket_id"] != ticket_id or row["kind"] != kind or row["content_hash"] != expected_hash:
        raise PreflightRefused(f"missing_reviewer_set:{kind}")
    return row


def _reviewer_set_by_hash(conn: sqlite3.Connection, ticket_id: int, kind: str, expected_hash: str) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM reviewer_set WHERE ticket_id = ? AND kind = ? AND content_hash = ?",
        (ticket_id, kind, expected_hash),
    ).fetchone()
    if row is None:
        raise PreflightRefused(f"missing_reviewer_set:{kind}")
    return row


def preflight_review_tuple(
    conn: sqlite3.Connection,
    ticket_id: int,
    *,
    plan_tuple_id: int,
    plan_slots: list[Slot],
    components: ReviewComponents,
    current_plan: PlanComponents,
    now: str | None = None,
) -> int:
    """The S5 preflight, in process: verify every candidate component, then create the review tuple.

    Every check below raises `PreflightRefused` before any write; the
    final `create_review_tuple` call is the only write this function
    performs, so a refusal never leaves a partial row behind.
    """
    plan_row = record.get(conn, "evidence_tuple", plan_tuple_id)
    if plan_row is None or plan_row["kind"] != "plan" or plan_row["ticket_id"] != ticket_id:
        raise PreflightRefused("missing_plan_tuple")

    currency = plan_tuple_currency(conn, plan_tuple_id, current_plan)
    if not currency.current:
        raise PreflightRefused(f"stale_plan_tuple:{','.join(currency.changed)}")

    quorum = approvals.evaluate(
        conn, gate="plan", subject_hash=plan_row["content_hash"], slots=plan_slots, now=now,
    )
    if not quorum.satisfied:
        raise PreflightRefused(f"no_plan_quorum:{','.join(quorum.reasons)}")
    if components.plan_approval_set_hash != quorum.approval_set_hash:
        raise PreflightRefused("wrong_approval_set_hash")

    planned_row = _reviewer_set_by_hash(conn, ticket_id, "planned", plan_row["planned_reviewer_set_hash"])
    actual_row = _reviewer_set_by_id(
        conn, components.actual_reviewer_set_id, ticket_id, "actual", components.actual_reviewer_set_hash,
    )
    effective_row = _reviewer_set_by_id(
        conn, components.effective_reviewer_set_id, ticket_id, "effective", components.effective_reviewer_set_hash,
    )
    merged = {slot.key: slot for slot in merge_slots(_slots_of(planned_row), _slots_of(actual_row))}
    effective = {slot.key: slot for slot in _slots_of(effective_row)}
    if merged != effective:
        raise PreflightRefused("effective_reviewer_set_not_merge")

    ticket = record.get(conn, "ticket", ticket_id)
    if ticket is None or components.target_base_sha != ticket["target_base_sha"]:
        raise PreflightRefused("stale_target_base")

    if not components.head_sha or not components.diff_hash:
        raise PreflightRefused("missing_head_or_diff")

    return create_review_tuple(conn, ticket_id, components)
