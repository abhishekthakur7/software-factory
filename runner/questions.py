"""The one write path for `question`, `answer`, and `assumption` rows.

`raise_round` is the pre-queue gate's caller: it validates every candidate
through `runner.checks.question_gate.validate` before writing any row, so
a round is either queued whole or refused whole. `record_answer` is the
one place an `answer` row is written -- `queue.act`'s `answer` and
`accept_default` actions both call it -- and it writes the append-only
`assumption` row a `default_accepted` resolution creates in the same call.
`accept_assumption` is the S3-reviewer path onto the same log for a
question nobody defaulted: `state = assumption_accepted`, one assumption
row naming it. `supersede_assumption` is the only way an assumption's text
changes: the prior row is never touched, a new row names it via
`supersedes`, and `assumption_log_hash` -- the "assumption-log version" --
changes as soon as that new row lands. There is no invalidation column on
any table: a downstream artefact or approval is invalidated exactly when
the log hash it recorded no longer equals `assumption_log_hash`'s current
value, which `dependents_invalidated` checks by comparison rather than by
a flag flipped somewhere.

`question.text` is deliberately not a column: the schema's existing tables
carry every governed field a gate or a rank needs, and the question's full
wording lives in the `question_set` artefact the driver registers, not as
a second copy in the record.
"""
import json
import sqlite3
from pathlib import Path

from runner import artefacts, canonical, queue, record, tags
from runner.checks import question_gate

# Impact x tier-weight x uncertainty, scaled to an integer: placeholder
# weights the owner calibrates once real question outcomes exist.
TIER_WEIGHTS: dict[str, int] = {"light": 1, "standard": 2, "heavy": 3}


class QuestionRejected(ValueError):
    """One or more candidates in this round fail the pre-queue gate; nothing was written."""

    def __init__(self, reasons_by_candidate: dict[int, list[str]]):
        self.reasons_by_candidate = reasons_by_candidate
        detail = "; ".join(f"candidate {index}: {', '.join(reasons)}" for index, reasons in reasons_by_candidate.items())
        super().__init__(f"question gate rejected {len(reasons_by_candidate)} candidate(s): {detail}")


class RoundRefused(ValueError):
    """A new round is refused while a blocking question of the previous round is still open."""


def rank(candidate: dict, tier: str) -> tuple[int, dict]:
    """`(rank, rank_inputs)`: impact times this tier's weight times uncertainty, scaled to an integer.

    Computed and returned even when `candidate["default_option"]` is
    `None` -- a question with no default is ranked exactly like one with
    one -- since nothing here reads `default_option` at all.
    """
    rank_inputs = dict(candidate.get("rank_inputs") or {})
    impact = float(rank_inputs.get("impact", 0))
    uncertainty = float(rank_inputs.get("uncertainty", 0))
    return round(impact * TIER_WEIGHTS[tier] * uncertainty * 100), rank_inputs


def validate(candidate: dict, *, allowed_names: frozenset = frozenset()) -> list[str]:
    """`runner.checks.question_gate.validate`, kept reachable from this module for callers that only import `questions`."""
    return question_gate.validate(candidate, allowed_names=allowed_names)


def _current_round(conn: sqlite3.Connection, ticket_id: int, stage: str) -> int:
    row = conn.execute(
        "SELECT MAX(round) AS max_round FROM question WHERE ticket_id = ? AND stage = ?", (ticket_id, stage)
    ).fetchone()
    return (row["max_round"] or 0) + 1


def _raised_by_answer_reason(conn: sqlite3.Connection, ticket_id: int, raised_by_answer) -> str | None:
    """The one reason `raised_by_answer` is invalid, or `None`: it must name a real `answer` row of this ticket."""
    if raised_by_answer is None:
        return None
    answer = record.get(conn, "answer", raised_by_answer)
    if answer is None:
        return f"raised_by_answer {raised_by_answer} does not name a real answer"
    question = record.get(conn, "question", answer["question_id"])
    if question is None or question["ticket_id"] != ticket_id:
        return f"raised_by_answer {raised_by_answer} does not belong to ticket {ticket_id}"
    return None


def raise_round(
    conn: sqlite3.Connection, *, ticket_id: int, stage: str, candidates: list[dict], tier: str,
    allowed_names: frozenset = frozenset(),
) -> list[int]:
    """Validate every candidate, then insert and queue the whole round; `[]` in, `[]` out, no round consumed.

    `round` is `1 +` the ticket's highest existing round at this stage.
    A new round is refused outright -- before any candidate is even
    looked at -- while a blocking question of the previous round is still
    `open`, so an agent cannot outrun a human who has not yet answered.
    Every candidate is checked before any row is written: one bad
    candidate rejects the whole round rather than partially queueing it.
    """
    if not candidates:
        return []

    new_round = _current_round(conn, ticket_id, stage)
    if new_round > 1:
        open_blocking = conn.execute(
            "SELECT id FROM question WHERE ticket_id = ? AND stage = ? AND round = ? AND blocking = 1 AND state = 'open'",
            (ticket_id, stage, new_round - 1),
        ).fetchone()
        if open_blocking is not None:
            raise RoundRefused(
                f"round {new_round - 1} of ticket {ticket_id} still has an open blocking question; "
                f"round {new_round} is refused"
            )

    reasons_by_candidate: dict[int, list[str]] = {}
    for index, candidate in enumerate(candidates):
        reasons = question_gate.validate(candidate, allowed_names=allowed_names)
        answer_reason = _raised_by_answer_reason(conn, ticket_id, candidate.get("raised_by_answer"))
        if answer_reason is not None:
            reasons = [*reasons, answer_reason]
        if reasons:
            reasons_by_candidate[index] = reasons
    if reasons_by_candidate:
        raise QuestionRejected(reasons_by_candidate)

    ids: list[int] = []
    for candidate in candidates:
        rank_value, rank_inputs = rank(candidate, tier)
        sensitive = bool(candidate.get("sensitive"))
        consequential = bool(candidate.get("consequential")) or sensitive
        consequential_reason = candidate.get("consequential_reason")
        if sensitive:
            consequential_reason = f"sensitive decision: {consequential_reason}" if consequential_reason else "sensitive decision"
        question_id = record.insert(
            conn, "question",
            ticket_id=ticket_id, stage=stage, round=new_round, rank=rank_value,
            text=candidate["text"], affects=candidate["affects"], reasoning=candidate["reasoning"],
            options=canonical.canonical_json(candidate["options"]).decode(),
            default_option=candidate.get("default_option"),
            consequential=1 if consequential else 0,
            consequential_reason=consequential_reason,
            hard_to_reverse=1 if candidate.get("hard_to_reverse") else 0,
            hard_to_reverse_reason=candidate.get("hard_to_reverse_reason"),
            blocking=1 if candidate.get("blocking") else 0,
            rank_inputs=canonical.canonical_json(rank_inputs).decode(),
            raised_by_answer=candidate.get("raised_by_answer"),
            state="open",
        )
        queue.open_item(conn, ticket_id=ticket_id, kind="question", stage=stage, tier=tier, ref=f"question:{question_id}")
        ids.append(question_id)
    return ids


def record_answer(
    conn: sqlite3.Connection, question_id: int, *, action: str, actor: str, option: int | None = None,
    note: str | None = None,
) -> int:
    """Write one `answer` row for `question_id`, settle its `state`, and return the answer id.

    `action == "answer"` records the chosen option (or, absent one, the
    question's own default); any other action records `default_accepted`
    against the question's default and, since nobody answered, appends
    one `assumption` row naming it -- the one path an `answer` row creates
    an `assumption` on its own.
    """
    question = record.get(conn, "question", question_id)
    if question is None:
        raise LookupError(f"no such question: {question_id}")
    if action == "answer":
        resolution_kind, chosen = "chosen_option", option if option is not None else question["default_option"]
    else:
        resolution_kind, chosen = "default_accepted", question["default_option"]
    answer_id = record.insert(
        conn, "answer",
        question_id=question_id, resolution_kind=resolution_kind,
        chosen_option=str(chosen) if chosen is not None else None,
        free_text=note, answered_by=actor, answered_at=record.now(),
    )
    record.update(conn, "question", question_id, state="answered" if resolution_kind == "chosen_option" else "default_accepted")
    if resolution_kind == "default_accepted":
        options = json.loads(question["options"] or "[]")
        text = options[chosen]["consequence"] if chosen is not None and 0 <= chosen < len(options) else None
        record.insert(
            conn, "assumption",
            ticket_id=question["ticket_id"], text=text or f"default accepted for question {question_id}",
            origin=str(question_id), supersedes=None, withdrawn=0, withdrawal_reason=None, created_at=record.now(),
        )
    return answer_id


def accept_assumption(conn: sqlite3.Connection, question_id: int, *, actor: str, text: str) -> int:
    """The S3-reviewer path: mark `question_id` `assumption_accepted` and write one assumption row naming it.

    `actor` is not stored on the `assumption` row -- the table carries no
    reviewer-identity column -- but is accepted for symmetry with every
    other write path here and for a caller that wants to tag the
    acceptance itself.
    """
    question = record.get(conn, "question", question_id)
    if question is None:
        raise LookupError(f"no such question: {question_id}")
    record.update(conn, "question", question_id, state="assumption_accepted")
    return record.insert(
        conn, "assumption",
        ticket_id=question["ticket_id"], text=text, origin=str(question_id),
        supersedes=None, withdrawn=0, withdrawal_reason=None, created_at=record.now(),
    )


def supersede_assumption(
    conn: sqlite3.Connection, assumption_id: int, *, text: str | None = None, withdraw: bool = False,
    reason: str, actor: str,
) -> int:
    """Append a new row that supersedes `assumption_id`; the prior row is never touched.

    `withdraw=True` marks the new row withdrawn and carries `reason` as
    the assumption table's own `withdrawal_reason` -- its only
    reason-carrying column, so a plain text replacement's `reason` lands
    there too, `withdrawn` being the one field that tells the two kinds
    of supersession apart. `actor` is accepted for symmetry with the
    other write paths; the table carries no per-row author column.
    """
    old = record.get(conn, "assumption", assumption_id)
    if old is None:
        raise LookupError(f"no such assumption: {assumption_id}")
    if not withdraw and text is None:
        raise ValueError("supersede_assumption requires text unless withdraw=True")
    return record.insert(
        conn, "assumption",
        ticket_id=old["ticket_id"], text=old["text"] if withdraw else text, origin=old["origin"],
        supersedes=assumption_id, withdrawn=1 if withdraw else 0, withdrawal_reason=reason, created_at=record.now(),
    )


def correct_flag(
    conn: sqlite3.Connection, question_id: int, *, consequential: bool | None = None,
    hard_to_reverse: bool | None = None, reason: str, actor: str, fm_id: str,
) -> None:
    """A human correcting `consequential` and/or `hard_to_reverse` in place, with the reason recorded as a tag.

    The two flag columns are mutable in place (a human correction), but
    their `_reason` columns are not -- those hold the agent's own
    original reasoning -- so the correction's reason lands as a
    `flag_correction` tag on `question:<id>` instead of overwriting it.
    """
    if consequential is None and hard_to_reverse is None:
        raise ValueError("correct_flag requires consequential or hard_to_reverse")
    fields = {}
    if consequential is not None:
        fields["consequential"] = 1 if consequential else 0
    if hard_to_reverse is not None:
        fields["hard_to_reverse"] = 1 if hard_to_reverse else 0
    record.update(conn, "question", question_id, **fields)
    tags.tag(conn, target=f"question:{question_id}", kind="flag_correction", fm_id=fm_id, actor=actor, note=reason)


def assumption_log_hash(conn: sqlite3.Connection, ticket_id: int) -> str:
    """The canonical hash of the ticket's current assumption set: every non-withdrawn row at the tip of its lineage.

    A row is "current" when nothing supersedes it (it is not named by
    another row's `supersedes`) and it is not itself a withdrawal. This
    is the assumption-log version a downstream artefact records; a
    supersession or withdrawal always changes it, since it always adds a
    new tip row.
    """
    rows = conn.execute("SELECT * FROM assumption WHERE ticket_id = ? ORDER BY id", (ticket_id,)).fetchall()
    superseded_ids = {row["supersedes"] for row in rows if row["supersedes"] is not None}
    current = [row for row in rows if row["id"] not in superseded_ids and not row["withdrawn"]]
    subject = [{"id": row["id"], "text": row["text"], "origin": row["origin"]} for row in current]
    return canonical.content_hash({"assumptions": subject})


def dependents_invalidated(conn: sqlite3.Connection, ticket_id: int) -> list[dict]:
    """Every already-recorded artefact, evidence tuple, and approval whose recorded assumption-log hash is now stale.

    "Invalidated" means exactly one thing in this code: the hash a row
    recorded when it was built no longer equals `assumption_log_hash`'s
    current value. An artefact records it in its own front matter
    (`assumption_log_hash`); an `evidence_tuple` records it in
    `current_assumption_set_hash`; an `approval_record` inherits it
    through the `evidence_tuple` it approved. Nothing here flips a flag
    anywhere -- the mismatch itself is the invalidation, so a consumer
    that never compares hashes is not protected by this function alone.
    """
    current = assumption_log_hash(conn, ticket_id)
    stale: list[dict] = []

    for kind in ("plan", "criteria", "packet", "handoff"):
        row = conn.execute(
            "SELECT * FROM artefact WHERE ticket_id = ? AND kind = ? ORDER BY version DESC, id DESC LIMIT 1",
            (ticket_id, kind),
        ).fetchone()
        if row is None:
            continue
        try:
            parsed = artefacts.parse(Path(row["path"]).read_text())
        except (artefacts.ArtefactError, OSError):
            continue
        recorded = parsed.front_matter.get("assumption_log_hash")
        if recorded is not None and recorded != current:
            stale.append({"type": "artefact", "id": row["id"], "kind": kind, "recorded_hash": recorded})

    for tuple_row in conn.execute("SELECT * FROM evidence_tuple WHERE ticket_id = ?", (ticket_id,)).fetchall():
        recorded = tuple_row["current_assumption_set_hash"]
        if recorded is None or recorded == current:
            continue
        stale.append({"type": "evidence_tuple", "id": tuple_row["id"], "kind": tuple_row["kind"], "recorded_hash": recorded})
        for approval in conn.execute(
            "SELECT id FROM approval_record WHERE evidence_tuple_id = ?", (tuple_row["id"],)
        ).fetchall():
            stale.append({"type": "approval_record", "id": approval["id"], "recorded_hash": recorded})

    return stale
