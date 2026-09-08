"""The queue: the one channel to a human, and every action taken from it.

`open_item` is the seam a later stage calls to queue a decision; it blocks
the ticket on the new item for every kind except `pr_outcome`, which is
non-blocking by definition. `act` is the sole writer of a queue item's
resolution: it validates the item's kind against `ACTIONS`, resolves the
acting identity and, where the action is an approval decision, the reviewer
slot that identity fills, dispatches the action's own effect through the
same functions any other caller would use (`transitions.apply`,
`approvals.record_approval`, `tags.tag`, `outbox.intent_for_review_quorum`),
and then settles the item's once-only resolution columns in one call. A
control event is the one action that does not resolve the item: the
observation is recorded in addition to whatever else is open, not instead
of it. `abandon` is a ticket-level operation usable with or without a
queued item, since `factory abandon` needs none. `list_queue` and
`latency_seconds` serve `factory queue`'s read side.

Every `active_attention_bucket` written here is either the `bucket`
parameter passed in by the caller or left absent -- never a derived value --
so the rule against any inferred or instrumented source behind this column
holds by construction rather than by a check bolted on afterward.
"""
import json
import sqlite3
from datetime import datetime
from pathlib import Path

from runner import approvals, canonical, outbox, owners, record, tags, transitions
from runner.paths import RUNS_DIR
from runner.reviewer_sets import Slot

# The attestation version `factory act` stamps; a new attestation format
# gets a new version without invalidating rows stamped with this one.
ATTESTATION_VERSION = "queue-act-v1"

# Every action a `queue_item` of each kind accepts, `control_event` aside.
# `pr_outcome` is non-blocking and takes no action here.
ACTIONS: dict[str, frozenset[str]] = {
    "question": frozenset({"answer", "accept_default"}),
    "eligibility": frozenset({"granted", "declined", "edit_scrutiny", "override"}),
    "plan_approval": frozenset({"approve", "redirect", "send_back", "abandon"}),
    "packet_approval": frozenset({"approve", "request_changes", "send_back"}),
    "red_check": frozenset({"send_back", "abandon"}),
    "escalation": frozenset({"resume", "send_back", "abandon"}),
    "manual_pause": frozenset({"resume", "stop", "send_back"}),
    "rubric_inspection": frozenset({"close_inspection"}),
    "pr_outcome": frozenset(),
}

CONTROL_EVENT = "control_event"

# A control event may be observed from any item except `pr_outcome`, in
# addition to whatever `ACTIONS` already permits for that kind.
_NO_CONTROL_EVENT_KINDS = frozenset({"pr_outcome"})

# The plan/packet decisions whose attention bucket is mandatory; every
# other action may carry one but is never refused for omitting it.
_BUCKET_REQUIRED_ACTIONS = frozenset({"approve", "redirect", "request_changes"})

# Actions resolved with no further effect beyond the once-group settlement:
# the decision is recorded on the item and a gate reads it later.
_RESOLVE_ONLY_ACTIONS = frozenset({"granted", "declined", "edit_scrutiny", "close_inspection"})


class ActionRefused(Exception):
    """The named action, actor, or item state does not permit this call."""


def open_item(
    conn: sqlite3.Connection,
    *,
    ticket_id: int,
    kind: str,
    stage: str | None = None,
    tier: str | None = None,
    ref: str | None = None,
    approval_subject_hash: str | None = None,
    reviewer_set_id: int | None = None,
) -> int:
    """Queue one `kind` item for `ticket_id`, blocking the ticket on it unless `kind` is `pr_outcome`."""
    item_id = record.insert(
        conn,
        "queue_item",
        ticket_id=ticket_id,
        stage=stage,
        tier=tier,
        kind=kind,
        ref=ref,
        queued_at=record.now(),
        approval_subject_hash=approval_subject_hash,
        reviewer_set_id=reviewer_set_id,
    )
    if kind != "pr_outcome":
        record.update(conn, "ticket", ticket_id, blocked_on=item_id)
    return item_id


def latency_seconds(item: sqlite3.Row) -> float | None:
    """`resolved_at - queued_at` in seconds, or `None` while either timestamp is missing."""
    queued_at, resolved_at = item["queued_at"], item["resolved_at"]
    if queued_at is None or resolved_at is None:
        return None
    return (datetime.fromisoformat(resolved_at) - datetime.fromisoformat(queued_at)).total_seconds()


def _known_identities(owners_obj: owners.Owners) -> frozenset[str]:
    return frozenset(entry["identity"] for entry in owners_obj.roles.values())


def _actor_role(owners_obj: owners.Owners, actor: str) -> str | None:
    """The lowest-sorted role `actor` holds, for provenance fields that take a single role."""
    held = sorted(role for role, entry in owners_obj.roles.items() if entry["identity"] == actor)
    return held[0] if held else None


def _allowed_actions(kind: str) -> frozenset[str]:
    base = ACTIONS.get(kind, frozenset())
    if kind in _NO_CONTROL_EVENT_KINDS:
        return base
    return base | {CONTROL_EVENT}


def _reviewer_set_for_item(conn: sqlite3.Connection, item: sqlite3.Row) -> sqlite3.Row | None:
    """The item's own reviewer set, else the ticket's latest planned (plan) or effective (packet) set."""
    if item["reviewer_set_id"] is not None:
        return record.get(conn, "reviewer_set", item["reviewer_set_id"])
    kind = "planned" if item["kind"] == "plan_approval" else "effective"
    return conn.execute(
        "SELECT * FROM reviewer_set WHERE ticket_id = ? AND kind = ? ORDER BY id DESC LIMIT 1",
        (item["ticket_id"], kind),
    ).fetchone()


def _resolve_slot(owners_obj: owners.Owners, actor: str, reviewer_set_row: sqlite3.Row) -> Slot | None:
    """The first slot whose role `actor` holds, or whose owner is `actor`."""
    slots = [Slot.from_json(entry) for entry in json.loads(reviewer_set_row["slots"] or "[]")]
    for slot in slots:
        if slot.role is not None and owners_obj.roles.get(slot.role, {}).get("identity") == actor:
            return slot
        if slot.owner == actor:
            return slot
    return None


def _record_decision(
    conn: sqlite3.Connection,
    item: sqlite3.Row,
    *,
    actor: str,
    owners_obj: owners.Owners,
    owners_path: Path,
    gate: str,
    decision: str,
    action: str,
    bucket: str | None,
    note: str | None,
) -> None:
    """Write one `approval_record` for `item`'s subject, from the slot `actor` fills on its reviewer set."""
    reviewer_set_row = _reviewer_set_for_item(conn, item)
    if reviewer_set_row is None:
        raise ActionRefused(f"queue item {item['id']} names no reviewer set to decide against")
    slot = _resolve_slot(owners_obj, actor, reviewer_set_row)
    if slot is None:
        raise ActionRefused(f"actor {actor!r} fits no slot on this item's reviewer set")
    approvals.record_approval(
        conn,
        gate=gate,
        subject_hash=item["approval_subject_hash"],
        slot_id=slot.slot_id,
        actor_identity=actor,
        role=slot.role or "owner",
        decision=decision,
        authority_policy_hash=owners.authority_policy_hash(owners_path),
        membership_snapshot_hash=canonical.content_hash(owners.identity_snapshot(owners_obj, actor)),
        attestation_version=ATTESTATION_VERSION,
        attestation_hash=canonical.content_hash({"item_id": item["id"], "action": action, "note": note}),
        active_attention_bucket=bucket,
        ticket_id=item["ticket_id"],
        reviewer_set_id=reviewer_set_row["id"],
    )


def _answer(conn: sqlite3.Connection, item: sqlite3.Row, *, action: str, actor: str, option: int | None, note: str | None) -> None:
    # Deferred import: `questions` imports this module back (for
    # `open_item`), so a top-level import here would cycle.
    from runner import questions

    table, _, raw_id = (item["ref"] or "").partition(":")
    question = record.get(conn, "question", int(raw_id)) if table == "question" and raw_id else None
    if question is None:
        raise ActionRefused(f"question item {item['id']} names no question: {item['ref']!r}")
    questions.record_answer(conn, question["id"], action=action, actor=actor, option=option, note=note)


def _override(
    conn: sqlite3.Connection, item: sqlite3.Row, *, actor: str, note: str | None, fm_id: str | None, tier: str | None,
) -> None:
    ticket = record.get(conn, "ticket", item["ticket_id"])
    # R-S0-8: widening a pilot exclusion is a recorded graduation decision,
    # never a tier override, so an excluded ticket refuses this action
    # outright rather than silently letting a human route around S0.
    if ticket["close_reason"] == "pilot_excluded":
        raise ActionRefused(f"ticket {item['ticket_id']} is excluded under pilot eligibility; override is refused")
    fields = {"tier_override_by": actor, "tier_override_at": record.now(), "tier_override_reason": note}
    if tier is not None:
        fields["tier_final"] = tier
    record.update(conn, "ticket", item["ticket_id"], **fields)
    tags.tag(conn, target=f"ticket:{item['ticket_id']}", kind="override", fm_id=fm_id, actor=actor, note=note)


def _approve(
    conn: sqlite3.Connection, item: sqlite3.Row, *, actor: str, owners_obj: owners.Owners,
    owners_path: Path, bucket: str | None, note: str | None, runs_dir: Path,
) -> None:
    kind = item["kind"]
    gate = "plan" if kind == "plan_approval" else "review"
    _record_decision(
        conn, item, actor=actor, owners_obj=owners_obj, owners_path=owners_path,
        gate=gate, decision="approve", action="approve", bucket=bucket, note=note,
    )
    if kind == "packet_approval":
        outbox.intent_for_review_quorum(conn, item["ticket_id"], runs_dir=runs_dir)


def _redirect(
    conn: sqlite3.Connection, item: sqlite3.Row, *, actor: str, owners_obj: owners.Owners,
    owners_path: Path, bucket: str | None, to: str | None, fm_id: str | None, note: str | None,
) -> None:
    if to is None:
        raise ActionRefused("redirect requires --to")
    _record_decision(
        conn, item, actor=actor, owners_obj=owners_obj, owners_path=owners_path,
        gate="plan", decision="redirect", action="redirect", bucket=bucket, note=note,
    )
    transitions.apply(conn, item["ticket_id"], f"send_back_to_{to}")
    tags.tag(conn, target=f"queue_item:{item['id']}", kind="send_back", fm_id=fm_id, actor=actor, note=note)


def _request_changes(
    conn: sqlite3.Connection, item: sqlite3.Row, *, actor: str, owners_obj: owners.Owners,
    owners_path: Path, bucket: str | None, fm_id: str | None, note: str | None,
) -> None:
    _record_decision(
        conn, item, actor=actor, owners_obj=owners_obj, owners_path=owners_path,
        gate="review", decision="reject", action="request_changes", bucket=bucket, note=note,
    )
    transitions.apply(conn, item["ticket_id"], "request_changes")
    tags.tag(
        conn, target=f"ticket:{item['ticket_id']}", kind="revision_after_approval",
        fm_id=fm_id, actor=actor, note=note,
    )


def _send_back(conn: sqlite3.Connection, item: sqlite3.Row, *, actor: str, to: str | None, fm_id: str | None, note: str | None) -> None:
    if to is None:
        raise ActionRefused("send_back requires --to")
    transitions.apply(conn, item["ticket_id"], f"send_back_to_{to}")
    tags.tag(conn, target=f"queue_item:{item['id']}", kind="send_back", fm_id=fm_id, actor=actor, note=note)


def _referenced_stage(conn: sqlite3.Connection, ref: str | None) -> str:
    if ref is None or not ref.startswith("stage_run:"):
        raise ActionRefused(f"escalation item ref is not a stage_run reference: {ref!r}")
    stage_run = record.get(conn, "stage_run", int(ref.split(":", 1)[1]))
    if stage_run is None:
        raise ActionRefused(f"escalation item references a missing stage_run: {ref!r}")
    return stage_run["stage"]


def _resume(conn: sqlite3.Connection, item: sqlite3.Row) -> None:
    if item["kind"] == "escalation":
        stage = _referenced_stage(conn, item["ref"])
        if stage == "S4":
            event = "escalation_resume_implementing"
        elif stage in ("S5", "S6"):
            event = "escalation_resume_checks"
        else:
            raise ActionRefused(f"cannot resume an escalation whose failed stage was {stage!r}")
        transitions.apply(conn, item["ticket_id"], event)
    else:
        record.update(conn, "ticket", item["ticket_id"], pause_requested=0, paused_at=None)


def _record_control_event(
    conn: sqlite3.Connection, item: sqlite3.Row, *, actor: str, owners_obj: owners.Owners,
    category: str | None, severity: str | None, fm_id: str | None, note: str | None,
) -> None:
    if not category:
        raise ActionRefused("control_event requires --category")
    if not severity:
        raise ActionRefused("control_event requires --severity")
    record.insert(
        conn,
        "incident_observation",
        ticket_id=item["ticket_id"],
        record_kind="control_defect_event",
        control_category=category,
        recorder_identity=actor,
        recorder_role=_actor_role(owners_obj, actor),
        occurred_at=record.now(),
        severity=severity,
        note=note,
        created_at=record.now(),
    )
    tags.tag(
        conn, target=f"queue_item:{item['id']}", kind="control_defect",
        fm_id=fm_id, actor=actor, note=note, severity=severity,
    )


def _clear_blocked_on(conn: sqlite3.Connection, item: sqlite3.Row) -> None:
    ticket = record.get(conn, "ticket", item["ticket_id"])
    if ticket is not None and ticket["blocked_on"] == item["id"]:
        record.update(conn, "ticket", item["ticket_id"], blocked_on=None)


def _resolve(
    conn: sqlite3.Connection, item: sqlite3.Row, *, actor: str, action: str, note: str | None,
    bucket: str | None, owners_obj: owners.Owners,
) -> None:
    """Settle the item's once-only resolution columns and clear `ticket.blocked_on` if it named this item."""
    record.update(
        conn,
        "queue_item",
        item["id"],
        resolved_at=record.now(),
        resolved_by=actor,
        action=action,
        note=note,
        active_attention_bucket=bucket,
        resolved_role=_actor_role(owners_obj, actor),
    )
    _clear_blocked_on(conn, item)


def act(
    conn: sqlite3.Connection,
    *,
    item_id: int,
    action: str,
    actor: str,
    bucket: str | None = None,
    note: str | None = None,
    to: str | None = None,
    fm_id: str | None = None,
    category: str | None = None,
    severity: str | None = None,
    option: int | None = None,
    tier: str | None = None,
    owners_path: Path = owners.DEFAULT_OWNERS_PATH,
    runs_dir: Path = RUNS_DIR,
) -> str:
    """Record a human decision on `item_id` and, where the action permits it, apply its effect.

    Raises `LookupError` for an unknown item and `ActionRefused` for every
    other refusal: an already-resolved item, an action not in this kind's
    mapping, an actor `owners_path` does not name, a missing mandatory
    bucket, an approval action whose actor fits no reviewer slot, or --
    for an `eligibility` item -- an invalid governance state. A
    `control_event` is recorded and returns without resolving the item;
    every other action settles the item's resolution columns before
    returning.
    """
    item = record.get(conn, "queue_item", item_id)
    if item is None:
        raise LookupError(f"no such queue item: {item_id}")
    if item["resolved_at"] is not None:
        raise ActionRefused(f"queue item {item_id} is already resolved")
    if item["ticket_id"] is not None:
        # Deferred import: `control` imports this module for `resume`'s own
        # `queue.act` call, so importing it back at module scope would cycle.
        from runner import control
        if control.live_run(conn, item["ticket_id"]) is not None:
            raise ActionRefused(control.live_run_refusal(item["ticket_id"]))
        outbox.reconcile_pending(conn, item["ticket_id"], runs_dir=runs_dir)

    kind = item["kind"]
    if action not in _allowed_actions(kind):
        raise ActionRefused(f"action {action!r} is not valid for queue item kind {kind!r}")

    if kind == "eligibility":
        # Imported here, not at module scope: S0 itself opens this item
        # through `queue.open_item`, so a top-level import in either
        # direction would be circular.
        from runner.stages import S0

        ticket = record.get(conn, "ticket", item["ticket_id"])
        reasons = S0.governance_valid(conn, ticket)
        if reasons:
            raise ActionRefused(f"eligibility item {item_id} fails governance validity: {', '.join(reasons)}")

    owners_obj = owners.load_owners(owners_path)
    if actor not in _known_identities(owners_obj):
        raise ActionRefused(f"unknown actor identity: {actor!r}")

    if action in _BUCKET_REQUIRED_ACTIONS and bucket is None:
        raise ActionRefused(f"action {action!r} requires --bucket")

    if action == CONTROL_EVENT:
        _record_control_event(
            conn, item, actor=actor, owners_obj=owners_obj, category=category,
            severity=severity, fm_id=fm_id, note=note,
        )
        return f"queue item {item_id}: control event recorded"

    if action in ("answer", "accept_default"):
        _answer(conn, item, action=action, actor=actor, option=option, note=note)
    elif action in _RESOLVE_ONLY_ACTIONS:
        pass
    elif action == "override":
        _override(conn, item, actor=actor, note=note, fm_id=fm_id, tier=tier)
    elif action == "approve":
        _approve(conn, item, actor=actor, owners_obj=owners_obj, owners_path=owners_path, bucket=bucket, note=note, runs_dir=runs_dir)
    elif action == "redirect":
        _redirect(conn, item, actor=actor, owners_obj=owners_obj, owners_path=owners_path, bucket=bucket, to=to, fm_id=fm_id, note=note)
    elif action == "send_back":
        _send_back(conn, item, actor=actor, to=to, fm_id=fm_id, note=note)
    elif action == "abandon":
        abandon(conn, item["ticket_id"], actor=actor, fm_id=fm_id, note=note, runs_dir=runs_dir)
    elif action == "request_changes":
        _request_changes(conn, item, actor=actor, owners_obj=owners_obj, owners_path=owners_path, bucket=bucket, fm_id=fm_id, note=note)
    elif action == "resume":
        _resume(conn, item)
    elif action == "stop":
        transitions.apply(conn, item["ticket_id"], "escalate")
    else:
        raise ActionRefused(f"unhandled action: {action!r}")

    _resolve(conn, item, actor=actor, action=action, note=note, bucket=bucket, owners_obj=owners_obj)
    return f"queue item {item_id}: resolved with {action}"


def abandon(
    conn: sqlite3.Connection, ticket_id: int, *, actor: str, fm_id: str, note: str | None = None,
    runs_dir: Path = RUNS_DIR,
) -> str:
    """Abandon `ticket_id`: a state transition, an `abandoned` tag, and a `not_deployed` coverage record.

    Used both by `factory abandon`, which names no queued item, and by
    `act`'s own `abandon` action, which resolves the item separately.
    Pending external writes reconcile first, as before every other
    state-advancing command.
    """
    outbox.reconcile_pending(conn, ticket_id, runs_dir=runs_dir)
    transitions.apply(conn, ticket_id, "abandon")
    tags.tag(conn, target=f"ticket:{ticket_id}", kind="abandoned", fm_id=fm_id, actor=actor, note=note)
    record.insert(
        conn,
        "incident_observation",
        ticket_id=ticket_id,
        record_kind="production_coverage",
        coverage_status="not_deployed",
        recorder_identity=actor,
        created_at=record.now(),
    )
    return f"ticket {ticket_id}: abandoned"


def _eligibility_context(conn: sqlite3.Connection, ticket: sqlite3.Row, owners_obj: owners.Owners) -> list[str]:
    lines = [
        f"  trust profile hash: {ticket['trust_profile_hash']}",
        f"  trust approval-set hash: {ticket['trust_approval_set_hash']}",
        "  satisfying trust approval set:",
    ]
    satisfying = conn.execute(
        "SELECT slot_id, actor_identity, content_hash FROM approval_record "
        "WHERE gate = 'trust_profile' AND subject_hash = ? ORDER BY id",
        (ticket["trust_profile_hash"],),
    ).fetchall()
    for row in satisfying:
        lines.append(f"    slot {row['slot_id']}: {row['actor_identity']} ({row['content_hash']})")
    lines.append("  planned RACI roles:")
    for role, entry in sorted(owners_obj.roles.items()):
        lines.append(f"    {role}: {entry['identity']} ({', '.join(entry['responsibilities'])})")
    lines.append(f"  ticket type to confirm: {ticket['ticket_type']}")
    lines.append(f"  data class to confirm: {ticket['data_class']}")
    lines.append(f"  scrutiny: {ticket['scrutiny_requested']}")
    return lines


def _question_context(conn: sqlite3.Connection, item: sqlite3.Row) -> list[str]:
    """The question's wording, its options with their consequences, and which option is the default, for a human to answer from."""
    table, _, raw_id = (item["ref"] or "").partition(":")
    question = record.get(conn, "question", int(raw_id)) if table == "question" and raw_id else None
    if question is None:
        return []
    lines = [f"  question: {question['text']}", f"  affects: {question['affects']}"]
    options = json.loads(question["options"] or "[]")
    for index, option in enumerate(options):
        marker = " (default)" if question["default_option"] == index else ""
        lines.append(f"  option {index}{marker}: {option.get('text')} -- {option.get('consequence')}")
    lines.append(f"  blocking: {bool(question['blocking'])}; consequential: {bool(question['consequential'])}; hard to reverse: {bool(question['hard_to_reverse'])}")
    return lines


def _approval_context(conn: sqlite3.Connection, item: sqlite3.Row) -> list[str]:
    lines = ["  approval records:"]
    rows = conn.execute(
        "SELECT actor_identity, decision, active_attention_bucket FROM approval_record "
        "WHERE subject_hash = ? ORDER BY id",
        (item["approval_subject_hash"],),
    ).fetchall()
    for row in rows:
        lines.append(
            f"    {row['actor_identity']}: {row['decision']} "
            f"(active_attention_bucket: {row['active_attention_bucket']})"
        )
    return lines


def _item_block(conn: sqlite3.Connection, item: sqlite3.Row, owners_obj: owners.Owners) -> list[str]:
    ticket = record.get(conn, "ticket", item["ticket_id"])
    lines = [
        f"queue_item {item['id']}: {item['kind']}",
        f"  ticket {item['ticket_id']}: {ticket['title'] if ticket else None}",
        f"  stage: {item['stage']}",
        f"  tier: {item['tier']}",
        f"  queued_at: {item['queued_at']}",
    ]
    if item["kind"] in ("plan_approval", "packet_approval"):
        lines.extend(_approval_context(conn, item))
    if item["resolved_at"] is not None:
        lines.append(f"  queue latency: {latency_seconds(item)}s")
        lines.append(f"  outcome: {item['action']}")
    if item["kind"] == "eligibility" and ticket is not None:
        lines.extend(_eligibility_context(conn, ticket, owners_obj))
    if item["kind"] == "question":
        lines.extend(_question_context(conn, item))
    if item["kind"] == "escalation":
        lines.extend(f"  {key}: {value}" for key, value in escalation_context(conn, item).items())
    return lines


# The S4 run kinds that are an actual execution attempt; `validation_only`
# is the runner's script-only verification pass after one, so on its own
# it stands for "a verification ran".
_S4_EXECUTION_KINDS = frozenset({"task", "fix_round"})
_S4_VERIFICATION_KIND = "validation_only"


def _s4_progress(conn: sqlite3.Connection, ticket_id: int) -> dict:
    """The highest passing S4 task attempt, the execution count and the verification count of the ticket's S4 history."""
    rows = conn.execute(
        "SELECT attempt, run_kind, outcome FROM stage_run WHERE ticket_id = ? AND stage = 'S4' ORDER BY id",
        (ticket_id,),
    ).fetchall()
    completed = [row["attempt"] for row in rows if row["run_kind"] in _S4_EXECUTION_KINDS and row["outcome"] == "pass"]
    return {
        "last_completed_task": completed[-1] if completed else None,
        "execution_count": sum(1 for row in rows if row["run_kind"] in _S4_EXECUTION_KINDS),
        "verification_count": sum(1 for row in rows if row["run_kind"] == _S4_VERIFICATION_KIND),
    }


def escalation_context(conn: sqlite3.Connection, item: sqlite3.Row) -> dict:
    """What an `escalation` item carries, derived from the record its `ref` points at.

    The stage run's reason (the latest failed runner check recorded on
    it), its own reasoning summary, the artefacts registered under it,
    the ticket's current binding (latest evidence tuple) if one exists,
    the stage's prior-attempt failure history, and for S4 the last
    completed task, execution count and verification count. An item
    whose `ref` names no stage run yields an empty mapping.
    """
    ref = item["ref"] or ""
    if not ref.startswith("stage_run:"):
        return {}
    stage_run = record.get(conn, "stage_run", int(ref.split(":", 1)[1]))
    if stage_run is None:
        return {}
    reason = conn.execute(
        "SELECT summary FROM check_result WHERE stage_run_id = ? AND source = 'runner' AND result = 'fail' "
        "ORDER BY id DESC LIMIT 1",
        (stage_run["id"],),
    ).fetchone()
    binding = conn.execute(
        "SELECT id FROM evidence_tuple WHERE ticket_id = ? ORDER BY id DESC LIMIT 1", (stage_run["ticket_id"],)
    ).fetchone()
    context = {
        "reason": reason["summary"] if reason is not None else None,
        "reasoning_summary": stage_run["reasoning_summary"],
        "registered_outputs": [
            row["id"] for row in conn.execute(
                "SELECT id FROM artefact WHERE stage_run_id = ? ORDER BY id", (stage_run["id"],)
            ).fetchall()
        ],
        "binding_evidence_tuple_id": binding["id"] if binding is not None else None,
        "failure_history": [
            {"attempt": row["attempt"], "outcome": row["outcome"], "failure_kind": row["failure_kind"]}
            for row in conn.execute(
                "SELECT attempt, outcome, failure_kind FROM stage_run "
                "WHERE ticket_id = ? AND stage = ? AND id < ? ORDER BY id",
                (stage_run["ticket_id"], stage_run["stage"], stage_run["id"]),
            ).fetchall()
        ],
    }
    if stage_run["stage"] == "S4":
        context.update(_s4_progress(conn, stage_run["ticket_id"]))
    return context


def list_queue(
    conn: sqlite3.Connection, *, include_resolved: bool = False, owners_path: Path = owners.DEFAULT_OWNERS_PATH,
) -> str:
    """One text block per open item (every item, resolved included, with `include_resolved`)."""
    owners_obj = owners.load_owners(owners_path)
    query = "SELECT * FROM queue_item"
    if not include_resolved:
        query += " WHERE resolved_at IS NULL"
    query += " ORDER BY id"
    blocks: list[str] = []
    for item in conn.execute(query).fetchall():
        blocks.extend(_item_block(conn, item, owners_obj))
        blocks.append("")
    return "\n".join(blocks).rstrip("\n")
