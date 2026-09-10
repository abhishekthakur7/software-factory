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

import yaml

from runner import approvals, artefact_registry, binding, canonical, capacity, outbox, owners, publication, record, tags, transitions
from runner.paths import RUNS_DIR
from runner.reviewer_sets import Slot

# The attestation version `factory act` stamps; a new attestation format
# gets a new version without invalidating rows stamped with this one.
ATTESTATION_VERSION = "queue-act-v1"

# `--self-contained` is mandatory on these actions regardless of item kind,
# and additionally on an escalation item's `resume`/`send_back`/`abandon`
# (its own decision is held to the same self-containedness rule through
# its `failure_history` artefact rather than through a dedicated column).
_SELF_CONTAINED_MANDATORY_ACTIONS = frozenset({"approve", "request_changes", "answer", "accept_default"})
_SELF_CONTAINED_MANDATORY_ESCALATION_ACTIONS = frozenset({"resume", "send_back", "abandon"})
_SELF_CONTAINED_VALUES = frozenset({"yes", "no"})

# Every action a `queue_item` of each kind accepts, `control_event` aside.
# `pr_outcome` is non-blocking and takes no action here.
ACTIONS: dict[str, frozenset[str]] = {
    "question": frozenset({"answer", "accept_default", "override"}),
    "eligibility": frozenset({"granted", "declined", "edit_scrutiny", "override"}),
    "plan_approval": frozenset({"approve", "redirect", "send_back", "abandon", "verdict", "verdicts", "waiver"}),
    "packet_approval": frozenset({"approve", "request_changes", "send_back"}),
    "red_check": frozenset({"send_back", "abandon", "waiver"}),
    "escalation": frozenset({"resume", "send_back", "abandon"}),
    "manual_pause": frozenset({"resume", "stop", "send_back"}),
    "rubric_inspection": frozenset({"close_inspection"}),
    "pr_outcome": frozenset({"revision", "outcome"}),
}

# Ticket-scoped actions `act` dispatches with no queue item at all --
# `--ticket <id>` and no `item_id` -- each recording a row in the
# production-coverage or incident series independently of, and any time
# after, the `pr_outcome` item's own `outcome` action.
TICKET_ACTIONS: frozenset[str] = frozenset({"exposure", "coverage", "incident_event", "disposition"})

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

# A `fail` verdict sends the ticket back to the checklist line's own
# stage, keyed by that stage's name.
_CHECKLIST_SEND_BACK_EVENT: dict[str, str] = {
    "context_gathering": "send_back_to_context", "clarification": "send_back_to_clarifying", "planning": "send_back_to_planning",
}


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


def _plan_subject_hash(conn: sqlite3.Connection, ticket_id: int) -> str | None:
    row = conn.execute(
        "SELECT content_hash FROM evidence_tuple WHERE ticket_id = ? AND kind = 'plan' ORDER BY id DESC LIMIT 1",
        (ticket_id,),
    ).fetchone()
    return row["content_hash"] if row is not None else None


def _approval_subject_hash(conn: sqlite3.Connection, item: sqlite3.Row) -> str | None:
    """The subject a decision on `item` binds to.

    Every other item kind carries its own subject on `approval_subject_hash`
    at open time. A `plan_approval` item carries none: its subject is
    whichever `plan` `evidence_tuple` is current for the ticket right now,
    since the bootstrap checklist -- not planning -- is what first creates one,
    and a drift after that can replace it before a human ever approves.
    """
    if item["kind"] != "plan_approval":
        return item["approval_subject_hash"]
    return _plan_subject_hash(conn, item["ticket_id"])


def _review_decision_fields(conn: sqlite3.Connection, item: sqlite3.Row) -> tuple[str, dict]:
    """The review-gate subject hash and the extra `approval_record` fields C11 requires of a final-review record.

    The subject is recomputed fresh right here through
    `publication.review_approval_subject` rather than trusted from the
    item's own `approval_subject_hash` -- the packet, a bound check
    result, a waiver, or the publication target could all have changed
    underneath an item still sitting open -- and compared against it,
    refusing outright on any drift; the same race `_check_plan_approvable`
    guards for the plan gate. The verbatim final-review attestation is
    stamped here rather than the ordinary per-decision one, since every
    required final-review record carries it.
    """
    subject = publication.review_approval_subject(conn, item["ticket_id"])
    if subject.hash != item["approval_subject_hash"]:
        raise ActionRefused(
            f"packet_approval item {item['id']} refused: the review-approval subject changed; "
            f"a fresh subject was created and must be re-approved"
        )
    review_tuple = conn.execute(
        "SELECT * FROM evidence_tuple WHERE ticket_id = ? AND kind = 'review' ORDER BY id DESC LIMIT 1",
        (item["ticket_id"],),
    ).fetchone()
    ticket = record.get(conn, "ticket", item["ticket_id"])
    target = publication.publication_target(conn, ticket)
    fields = {
        "evidence_tuple_id": review_tuple["id"],
        "evidence_tuple_hash": review_tuple["content_hash"],
        "reviewer_set_hash": subject.effective_reviewer_set_hash,
        "publication_target_hash": target.hash,
        "attestation_version": approvals.FINAL_REVIEW_ATTESTATION_VERSION,
        "attestation_hash": canonical.content_hash({"text": approvals.FINAL_REVIEW_ATTESTATION}),
    }
    return subject.hash, fields


def _refuse_forked_head(conn: sqlite3.Connection, *, gate: str, subject_hash: str, slot: Slot, actor: str) -> None:
    """Refuse a second decision from `actor` on a slot they already hold a current head for on this exact subject.

    `approvals.record_approval` never checks this itself -- a fork is
    something `approvals.evaluate` only detects at quorum time, over rows
    already written -- so this is the one point before the write where a
    second `factory act` decision by the same actor on a still-open item
    is stopped from creating one at all, keeping one immutable row per
    actor and required slot the normal case rather than something a later
    supersession has to repair.
    """
    heads = approvals.current_heads(conn, gate, subject_hash)
    if any(row["slot_id"] == slot.slot_id and row["actor_identity"] == actor for row in heads):
        raise ActionRefused(
            f"actor {actor!r} already recorded a decision for slot {slot.slot_id!r} on this subject; "
            f"a second one would fork the head"
        )


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
    self_contained: str | None = None,
) -> int:
    """Write one `approval_record` for `item`'s subject, from the slot `actor` fills on its reviewer set.

    Returns the new row's id. `self_contained` ("yes"/"no"/`None`) lands
    on `decision_supported_without_transcript`, null when the caller
    supplied none.
    """
    reviewer_set_row = _reviewer_set_for_item(conn, item)
    if reviewer_set_row is None:
        raise ActionRefused(f"queue item {item['id']} names no reviewer set to decide against")
    slot = _resolve_slot(owners_obj, actor, reviewer_set_row)
    if slot is None:
        raise ActionRefused(f"actor {actor!r} fits no slot on this item's reviewer set")

    subject_hash = _approval_subject_hash(conn, item)
    extra_fields: dict = {}
    attestation_version = ATTESTATION_VERSION
    attestation_hash = canonical.content_hash({"item_id": item["id"], "action": action, "note": note})
    if gate == "review":
        subject_hash, review_fields = _review_decision_fields(conn, item)
        attestation_version = review_fields.pop("attestation_version")
        attestation_hash = review_fields.pop("attestation_hash")
        extra_fields = review_fields

    _refuse_forked_head(conn, gate=gate, subject_hash=subject_hash, slot=slot, actor=actor)

    return approvals.record_approval(
        conn,
        gate=gate,
        subject_hash=subject_hash,
        slot_id=slot.slot_id,
        actor_identity=actor,
        role=slot.role or "owner",
        decision=decision,
        authority_policy_hash=owners.authority_policy_hash(owners_path),
        membership_snapshot_hash=canonical.content_hash(owners.identity_snapshot(owners_obj, actor)),
        attestation_version=attestation_version,
        attestation_hash=attestation_hash,
        decision_supported_without_transcript=(
            None if self_contained is None else (1 if self_contained == "yes" else 0)
        ),
        active_attention_bucket=bucket,
        ticket_id=item["ticket_id"],
        reviewer_set_id=reviewer_set_row["id"],
        **extra_fields,
    )


def _answer(
    conn: sqlite3.Connection, item: sqlite3.Row, *, action: str, actor: str, option: int | None, note: str | None,
    self_contained: str | None = None,
) -> int:
    # Deferred import: `questions` imports this module back (for
    # `open_item`), so a top-level import here would cycle.
    from runner import questions

    table, _, raw_id = (item["ref"] or "").partition(":")
    original = record.get(conn, "question", int(raw_id)) if table == "question" and raw_id else None
    if original is None:
        raise ActionRefused(f"question item {item['id']} names no question: {item['ref']!r}")
    # The item's own `ref` is fixed at the id `raise_round` first gave the
    # question: a flag correction landing on it since then appended a
    # replacement rather than editing `ref` in place, so the answer must
    # resolve forward to that replacement -- the current tip -- rather
    # than settling the now-superseded id the item still names.
    question = questions.current_version(conn, original["id"])
    return questions.record_answer(
        conn, question["id"], action=action, actor=actor, option=option, note=note,
        supported_without_transcript=None if self_contained is None else self_contained == "yes",
    )


def _override(
    conn: sqlite3.Connection, item: sqlite3.Row, *, actor: str, note: str | None, fm_id: str | None, tier: str | None,
) -> None:
    ticket = record.get(conn, "ticket", item["ticket_id"])
    # Widening a pilot exclusion is a recorded graduation decision,
    # never a tier override, so an excluded ticket refuses this action
    # outright rather than silently letting a human route around intake.
    if ticket["close_reason"] == "pilot_excluded":
        raise ActionRefused(f"ticket {item['ticket_id']} is excluded under pilot eligibility; override is refused")
    fields = {"tier_override_by": actor, "tier_override_at": record.now(), "tier_override_reason": note}
    if tier is not None:
        fields["tier_final"] = tier
    record.update(conn, "ticket", item["ticket_id"], **fields)
    tags.tag(conn, target=f"ticket:{item['ticket_id']}", kind="override", fm_id=fm_id, actor=actor, note=note)


def _question_override(
    conn: sqlite3.Connection, item: sqlite3.Row, *, actor: str, note: str | None, fm_id: str | None, fields: dict,
) -> None:
    """Correct a question's `consequential`, `hard_to_reverse`, and/or `blocking` flag (`fields`) through `questions.correct_flag`.

    Distinct from `_override` above (an eligibility item's tier
    correction): this writes no ticket field and resolves no item -- a
    question stays open for its own `answer`/`accept_default` regardless
    of a flag correction landing on it, since the two are independent
    decisions about the same question. `raw_id` is passed through as
    given, not resolved to a tip here: `correct_flag` resolves it itself,
    so a second override on an already-corrected question still lands on
    the live row, and correcting `blocking` to false is what lets
    `advance` move a ticket the flag alone was holding in `clarifying`
    past the question gate.
    """
    from runner import questions

    table, _, raw_id = (item["ref"] or "").partition(":")
    if table != "question" or not raw_id:
        raise ActionRefused(f"question item {item['id']} names no question: {item['ref']!r}")
    consequential, hard_to_reverse, blocking = (
        fields.get("consequential"), fields.get("hard_to_reverse"), fields.get("blocking"),
    )
    if consequential is None and hard_to_reverse is None and blocking is None:
        raise ActionRefused("override requires --consequential, --hard-to-reverse, and/or --blocking")
    if not note:
        raise ActionRefused("override requires --note naming the recorded reason")
    if not fm_id:
        raise ActionRefused("override requires --fm")
    questions.correct_flag(
        conn, int(raw_id), actor=actor, fm_id=fm_id, reason=note,
        consequential=None if consequential is None else consequential == "yes",
        hard_to_reverse=None if hard_to_reverse is None else hard_to_reverse == "yes",
        blocking=None if blocking is None else blocking == "yes",
    )


def _instance_keys(instances) -> list[tuple[str, str]]:
    return [(instance.rubric_line_id, instance.subject_item_key) for instance in instances]


def _check_plan_approvable(conn: sqlite3.Connection, item: sqlite3.Row) -> None:
    """Refuse a `plan_approval` item's `approve` while its checklist is incomplete or its subject just drifted.

    The race guard: `plan_tuple.ensure_current` is called again right
    here, immediately before the decision is recorded, so a change that
    landed after the checklist completed but before the human clicked
    approve is caught the same way a change that landed earlier is --
    the ticket's plan subject is never approved stale.
    """
    from runner import checklist, plan_tuple

    ticket = record.get(conn, "ticket", item["ticket_id"])
    expected = checklist.expected_instances(conn, ticket)
    status = checklist.completeness(conn, ticket, expected)
    if not status.complete:
        raise ActionRefused(
            f"plan_approval item {item['id']} checklist is incomplete: "
            f"missing={_instance_keys(status.missing)} "
            f"unwaived_blind_spots={_instance_keys(status.unwaived_blind_spots)} "
            f"failed={_instance_keys(status.failed)}"
        )

    latest = conn.execute(
        "SELECT * FROM evidence_tuple WHERE ticket_id = ? AND kind = 'plan' ORDER BY id DESC LIMIT 1",
        (item["ticket_id"],),
    ).fetchone()
    components = plan_tuple.derive_components(conn, ticket)
    currency = binding.plan_tuple_currency(conn, latest["id"], components) if latest is not None else None
    plan_tuple.ensure_current(conn, ticket)
    if latest is None or not currency.current:
        changed = currency.changed if currency is not None else ("no_prior_plan_subject",)
        raise ActionRefused(
            f"plan_approval item {item['id']} refused: the plan subject changed ({', '.join(changed)}); "
            f"a fresh subject was created and must be re-approved"
        )


def _approve(
    conn: sqlite3.Connection, item: sqlite3.Row, *, actor: str, owners_obj: owners.Owners,
    owners_path: Path, bucket: str | None, note: str | None, runs_dir: Path, self_contained: str | None = None,
) -> int:
    kind = item["kind"]
    gate = "plan" if kind == "plan_approval" else "review"
    if kind == "plan_approval":
        _check_plan_approvable(conn, item)
    approval_id = _record_decision(
        conn, item, actor=actor, owners_obj=owners_obj, owners_path=owners_path,
        gate=gate, decision="approve", action="approve", bucket=bucket, note=note, self_contained=self_contained,
    )
    if kind == "packet_approval":
        outbox.intent_for_review_quorum(conn, item["ticket_id"], runs_dir=runs_dir)
    return approval_id


def _approve_quorum_satisfied(conn: sqlite3.Connection, item: sqlite3.Row) -> bool:
    """Whether every slot on the item's own reviewer set now holds a satisfying decision on this approval's subject.

    A `plan_approval` or `packet_approval` item stays open across more
    than one `approve` call when its reviewer set names more than one
    slot: the item resolves only once `approvals.evaluate` finds quorum,
    not on the first slot's own record, so a decision meant to need
    several reviewers actually waits on all of them rather than closing
    on the first.
    """
    reviewer_set_row = _reviewer_set_for_item(conn, item)
    if reviewer_set_row is None:
        return True
    slots = [Slot.from_json(entry) for entry in json.loads(reviewer_set_row["slots"] or "[]")]
    gate = "plan" if item["kind"] == "plan_approval" else "review"
    subject_hash = _approval_subject_hash(conn, item)
    return approvals.evaluate(conn, gate=gate, subject_hash=subject_hash, slots=slots).satisfied


def _act_verdict(
    conn: sqlite3.Connection,
    item: sqlite3.Row,
    *,
    actor: str,
    owners_obj: owners.Owners,
    line: str | None,
    key: str | None,
    verdict: str | None,
    evidence: list[int] | None,
    waiver: int | None,
    fm_id: str | None,
    note: str | None,
) -> bool:
    """Record one `human_verdict` for `item`; return whether the item itself resolves.

    Only a `fail` verdict resolves the item, by sending the ticket back to
    the failing line's own stage -- `context` for the context-gathering stage, `clarifying`
    for the clarification stage, `planning` for the planning stage -- and tagging the send-back (`fm_id` is therefore
    required for a `fail`). A `pass` or `blind_spot` verdict leaves the
    item open: the checklist may still have other instances outstanding,
    and even a complete checklist still waits on the separate `approve`
    action. When this verdict completes the checklist with no fail and no
    unwaived blind spot, a fresh plan tuple is created in the same
    transaction, so `approve`'s own race guard always finds a current
    subject to check against.
    """
    from runner import checklist, plan_tuple

    if line is None or key is None:
        raise ActionRefused("verdict requires --line and --key")
    if verdict not in checklist.VERDICTS:
        raise ActionRefused(f"verdict must be one of {sorted(checklist.VERDICTS)}")

    ticket = record.get(conn, "ticket", item["ticket_id"])
    expected = checklist.expected_instances(conn, ticket)
    instance = next((i for i in expected if i.rubric_line_id == line and i.subject_item_key == key), None)
    if instance is None:
        raise ActionRefused(f"no expected checklist instance for line {line!r} key {key!r}")

    reviewer_set_row = _reviewer_set_for_item(conn, item)
    if reviewer_set_row is None:
        raise ActionRefused(f"queue item {item['id']} names no reviewer set to verdict against")
    slot = _resolve_slot(owners_obj, actor, reviewer_set_row)
    if slot is None:
        raise ActionRefused(f"actor {actor!r} fits no slot on this item's reviewer set")

    checklist.record_verdict(
        conn, ticket=ticket, item=item, instance=instance, verdict=verdict,
        evidence_ids=list(evidence or []), waiver_id=waiver, reviewer_identity=actor,
        reviewer_role=slot.role or "owner", note=note,
    )

    if verdict == "fail":
        if not fm_id:
            raise ActionRefused("a fail verdict requires --fm-id")
        stage = checklist.stage_of(instance.rubric_file)
        transitions.apply(conn, item["ticket_id"], _CHECKLIST_SEND_BACK_EVENT[stage])
        tags.tag(conn, target=f"queue_item:{item['id']}", kind="send_back", fm_id=fm_id, actor=actor, note=note)
        return True

    if checklist.completeness(conn, ticket, expected).complete:
        plan_tuple.ensure_current(conn, ticket)
    return False


def _act_verdicts_batch(
    conn: sqlite3.Connection, item: sqlite3.Row, *, actor: str, owners_obj: owners.Owners,
    verdicts_file: str | None, fm_id: str | None,
) -> bool:
    """Apply every `(rubric_line_id, subject_item_key, verdict, evidence)` tuple `verdicts_file` names, through `_act_verdict`.

    Each tuple writes its own `human_verdict` row through the same path a
    single `verdict` action uses, one call per tuple; a `fail` anywhere in
    the list sends the ticket back exactly as a lone `fail` would and the
    batch stops there, the remaining tuples never applied. `fm_id` is the
    batch's one flag, since every tuple in a file shares whichever
    send-back a `fail` among them causes.
    """
    if not verdicts_file:
        raise ActionRefused("verdicts requires a file path")
    entries = yaml.safe_load(Path(verdicts_file).read_text()) or []
    if not entries:
        raise ActionRefused(f"{verdicts_file} names no verdict tuples")
    for entry in entries:
        resolves = _act_verdict(
            conn, item, actor=actor, owners_obj=owners_obj,
            line=entry.get("rubric_line_id"), key=entry.get("subject_item_key"), verdict=entry.get("verdict"),
            evidence=entry.get("evidence"), waiver=entry.get("waiver"), fm_id=fm_id, note=entry.get("note"),
        )
        if resolves:
            return True
    return False


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
    owners_path: Path, bucket: str | None, fm_id: str | None, note: str | None, self_contained: str | None = None,
) -> int:
    approval_id = _record_decision(
        conn, item, actor=actor, owners_obj=owners_obj, owners_path=owners_path,
        gate="review", decision="reject", action="request_changes", bucket=bucket, note=note,
        self_contained=self_contained,
    )
    transitions.apply(conn, item["ticket_id"], "request_changes")
    tags.tag(
        conn, target=f"ticket:{item['ticket_id']}", kind="revision_after_approval",
        fm_id=fm_id, actor=actor, note=note,
    )
    return approval_id


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


def _escalation_defect_target(conn: sqlite3.Connection, item: sqlite3.Row) -> str:
    """`artefact:<failure_history id>` for the `failure_history` artefact `item`'s stage run registered.

    An escalation's own decision has no dedicated column for the
    self-containedness rule -- it is held to it through this artefact
    instead -- so a false answer on it is refused outright rather than
    silently accepted when the run behind the item registered none (only
    a verification-exhaustion escalation ever does).
    """
    ref = item["ref"] or ""
    stage_run = record.get(conn, "stage_run", int(ref.split(":", 1)[1])) if ref.startswith("stage_run:") else None
    history = artefact_registry.latest(conn, stage_run["ticket_id"], "failure_history") if stage_run is not None else None
    if history is None:
        raise ActionRefused(f"escalation item {item['id']} names no failure_history artefact to bind a defect to")
    return f"artefact:{history['id']}"


def _control_defect_remediated(conn: sqlite3.Connection, ticket_id: int) -> bool:
    """Whether the ticket's latest `control_defect_event` carries a `remediated` disposition and a newer passing gate run.

    Both conditions must hold on the same event: a disposition alone is a
    human's word that the underlying defect is fixed, and a gate run
    alone proves nothing about which incident it clears, so resuming
    needs the pair, in that order, against the one event this escalation
    named.
    """
    event = conn.execute(
        "SELECT id, created_at FROM incident_observation WHERE ticket_id = ? AND record_kind = 'control_defect_event' "
        "ORDER BY id DESC LIMIT 1",
        (ticket_id,),
    ).fetchone()
    if event is None:
        return False
    disposition = conn.execute(
        "SELECT id FROM incident_observation WHERE ticket_id = ? AND record_kind = 'control_disposition' "
        "AND event_id = ? AND disposition = 'remediated' ORDER BY id DESC LIMIT 1",
        (ticket_id, event["id"]),
    ).fetchone()
    if disposition is None:
        return False
    # `>=`, not `>`: `record.now()` carries second precision, so a gate run
    # started in the same second as the event it clears is still at least
    # as new as it -- the ordering this guards against is a stale gate run
    # from *before* the event, not one merely tied with it.
    gate = conn.execute(
        "SELECT id FROM utility_run WHERE ticket_id = ? AND kind = 'gate' AND outcome = 'pass' AND started_at >= ? "
        "ORDER BY id DESC LIMIT 1",
        (ticket_id, event["created_at"]),
    ).fetchone()
    return gate is not None


def _resume(conn: sqlite3.Connection, item: sqlite3.Row) -> None:
    """Route a plain `resume` by the escalation's own cause, read from the run its `ref` names.

    Verification exhaustion never resumes this way at all -- the only
    route is `send_back --to planning`, a new plan-item version and a
    fresh planning approval. A control defect (a sandbox-integrity or an
    invalid recipe-policy-binding failure) resumes only once its event
    carries a `remediated` disposition and a newer passing `gate` run,
    and then through `escalation_control_defect_remediated`, never the
    plain resume events below. Every other cause -- an infrastructure
    failure or a human stop -- resumes the same item with its quota
    preserved, exactly as before this function grew cause-awareness.
    """
    if item["kind"] != "escalation":
        record.update(conn, "ticket", item["ticket_id"], pause_requested=0, paused_at=None)
        return

    stage = _referenced_stage(conn, item["ref"])
    run = record.get(conn, "stage_run", int(item["ref"].split(":", 1)[1]))

    if run["failure_kind"] == "verification":
        raise ActionRefused(
            "a verification-exhaustion escalation resumes only through 'send_back --to planning' (a new "
            "plan-item version and a fresh planning approval), never through resume"
        )
    if run["failure_kind"] in ("sandbox_integrity", "recipe_binding"):
        if not _control_defect_remediated(conn, item["ticket_id"]):
            raise ActionRefused(
                "a control-defect escalation resumes only once its event carries a 'remediated' disposition and a "
                "utility_run of kind 'gate' with outcome 'pass' newer than the event"
            )
        transitions.apply(conn, item["ticket_id"], "escalation_control_defect_remediated")
        return

    if stage == "implementation":
        event = "escalation_resume_implementing"
    elif stage in ("checks", "human_review"):
        event = "escalation_resume_checks"
    else:
        raise ActionRefused(f"cannot resume an escalation whose failed stage was {stage!r}")
    transitions.apply(conn, item["ticket_id"], event)


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


def _self_contained_required(kind: str, action: str) -> bool:
    if action in _SELF_CONTAINED_MANDATORY_ACTIONS:
        return True
    return kind == "escalation" and action in _SELF_CONTAINED_MANDATORY_ESCALATION_ACTIONS


def _write_packet_defect(conn: sqlite3.Connection, *, target: str, actor: str, note: str | None) -> None:
    tags.tag(conn, target=target, kind="packet_defect", fm_id=tags.PACKET_DEFECT_FM_ID, actor=actor, note=note)


def _issue_waiver(
    conn: sqlite3.Connection, item: sqlite3.Row, *, actor: str, human_verdict_id: str | None,
    evidence: list[int] | None, fields: dict,
) -> int:
    """Issue a waiver over `item`'s ticket through `waivers.issue`, the one policy-checked write a waiver ever takes.

    `fields` carries the waiver's own flags (`policy_id`, `check_result_id`,
    `reason`, `scope`, `controls`, `expires_at`); the covered human verdict
    and the evidence list arrive through the `--verdict` and `--evidence`
    flags every verdict action already has.

    Never resolves `item`: `waivers.issue` already resolves a `red_check`
    itself, through `queue.resolve_by_waiver`, once every blocking result
    the run shares clears, and a `plan_approval` item stays open for its
    later `approve` regardless of which blind spot a waiver just covered.
    """
    from runner import waivers

    missing = [name for name in ("policy_id", "reason", "scope", "controls", "expires_at") if not fields.get(name)]
    if missing:
        raise ActionRefused(f"waiver requires {', '.join('--' + name.replace('_id', '').replace('_', '-') for name in missing)}")
    return waivers.issue(
        conn, ticket_id=item["ticket_id"], policy_id=fields["policy_id"], check_result_id=fields.get("check_result_id"),
        human_verdict_id=int(human_verdict_id) if human_verdict_id is not None else None,
        actor=actor, reason=fields["reason"], scope=fields["scope"], compensating_controls=fields["controls"],
        evidence_ids=evidence or [], expires_at=fields["expires_at"],
    )


def act(
    conn: sqlite3.Connection,
    *,
    item_id: int | None = None,
    ticket_id: int | None = None,
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
    line: str | None = None,
    key: str | None = None,
    verdict: str | None = None,
    evidence: list[int] | None = None,
    waiver: int | None = None,
    self_contained: str | None = None,
    fields: dict | None = None,
    owners_path: Path = owners.DEFAULT_OWNERS_PATH,
    runs_dir: Path = RUNS_DIR,
) -> str:
    """Record a human decision on `item_id`, or a ticket-scoped observation on `ticket_id`, and apply its effect.

    Raises `LookupError` for an unknown item and `ActionRefused` for every
    other refusal: an already-resolved item, an action not in this kind's
    mapping, an actor `owners_path` does not name, a missing mandatory
    bucket, a missing mandatory `self_contained` (`approve`,
    `request_changes`, `answer`, `accept_default`, and an escalation
    item's `resume`/`send_back`/`abandon`), an approval action whose actor
    fits no reviewer slot, or -- for an `eligibility` item -- an invalid
    governance state. A `control_event`, a `waiver`, and a `question`
    item's `override` are each recorded and return without resolving the
    item; every other action settles the item's resolution columns
    before returning, except `approve` on a `plan_approval` or
    `packet_approval` item, whose resolution additionally waits on the
    reviewer set's own quorum -- one slot's record leaves the item open
    for the next. `self_contained == "no"` writes, in the same
    transaction as the decision itself, a `packet_defect` tag bound to the
    exact `approval_record` (a plan or review decision), `question` (an
    answer), or `failure_history` artefact (an escalation) the false
    self-containedness answer was about.

    With `item_id` omitted and `ticket_id` given, `action` must be one of
    `TICKET_ACTIONS`: the production-coverage and incident series a ticket
    may extend at any time after its outcome is recorded, with no queue
    item involved and nothing to resolve.
    """
    if item_id is None:
        if ticket_id is None:
            raise ActionRefused("act requires either item_id or ticket_id")
        if action not in TICKET_ACTIONS:
            raise ActionRefused(f"action {action!r} is not a ticket-scoped action; must be one of {sorted(TICKET_ACTIONS)}")
        owners_obj = owners.load_owners(owners_path)
        if actor not in _known_identities(owners_obj):
            raise ActionRefused(f"unknown actor identity: {actor!r}")
        # Deferred import: `outcome` imports this module at its own top
        # level for `queue.ActionRefused` and `queue.abandon`, so importing
        # it back here at module scope would cycle -- the same shape as
        # the `control` import above.
        from runner import outcome
        getattr(outcome, action)(conn, ticket_id=ticket_id, actor=actor, owners_obj=owners_obj, fields=fields or {})
        return f"ticket {ticket_id}: {action} recorded"

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
        # Imported here, not at module scope: intake itself opens this item
        # through `queue.open_item`, so a top-level import in either
        # direction would be circular.
        from runner.stages import intake

        ticket = record.get(conn, "ticket", item["ticket_id"])
        reasons = intake.governance_valid(conn, ticket)
        if reasons:
            raise ActionRefused(f"eligibility item {item_id} fails governance validity: {', '.join(reasons)}")

    owners_obj = owners.load_owners(owners_path)
    if actor not in _known_identities(owners_obj):
        raise ActionRefused(f"unknown actor identity: {actor!r}")

    if action in _BUCKET_REQUIRED_ACTIONS and bucket is None:
        raise ActionRefused(f"action {action!r} requires --bucket")

    if self_contained is not None and self_contained not in _SELF_CONTAINED_VALUES:
        raise ActionRefused(f"--self-contained must be one of {sorted(_SELF_CONTAINED_VALUES)}, got {self_contained!r}")
    if _self_contained_required(kind, action) and self_contained is None:
        raise ActionRefused(f"action {action!r} requires --self-contained yes|no")

    if action == CONTROL_EVENT:
        from runner import outcome
        outcome.control_event(
            conn, item, actor=actor, owners_obj=owners_obj,
            fields={"category": category, "severity": severity, "fm_id": fm_id, "note": note},
        )
        return f"queue item {item_id}: control event recorded"

    if action == "waiver":
        waiver_id = _issue_waiver(
            conn, item, actor=actor, human_verdict_id=verdict, evidence=evidence, fields=fields or {},
        )
        return f"queue item {item_id}: waiver {waiver_id} issued"

    if kind == "question" and action == "override":
        _question_override(conn, item, actor=actor, note=note, fm_id=fm_id, fields=fields or {})
        return f"queue item {item_id}: override recorded"

    if kind == "pr_outcome" and action in ("revision", "outcome"):
        from runner import outcome
        getattr(outcome, action)(
            conn, ticket_id=item["ticket_id"], actor=actor, owners_obj=owners_obj,
            fields=fields or {}, runs_dir=runs_dir,
        )
        _resolve(conn, item, actor=actor, action=action, note=note, bucket=bucket, owners_obj=owners_obj)
        return f"queue item {item_id}: resolved with {action}"

    if action == "verdict":
        # A verdict resolves the item only on a `fail` (a send-back); a
        # `pass` or `blind_spot` records the row and returns without
        # touching the item's own resolution columns, since the checklist
        # may still have other instances outstanding.
        resolves = _act_verdict(
            conn, item, actor=actor, owners_obj=owners_obj, line=line, key=key, verdict=verdict,
            evidence=evidence, waiver=waiver, fm_id=fm_id, note=note,
        )
        if not resolves:
            return f"queue item {item_id}: verdict recorded"
        _resolve(conn, item, actor=actor, action=action, note=note, bucket=bucket, owners_obj=owners_obj)
        return f"queue item {item_id}: resolved with {action}"

    if action == "verdicts":
        resolves = _act_verdicts_batch(
            conn, item, actor=actor, owners_obj=owners_obj,
            verdicts_file=(fields or {}).get("verdicts_file"), fm_id=fm_id,
        )
        if not resolves:
            return f"queue item {item_id}: verdicts recorded"
        _resolve(conn, item, actor=actor, action=action, note=note, bucket=bucket, owners_obj=owners_obj)
        return f"queue item {item_id}: resolved with {action}"

    if action in ("answer", "accept_default"):
        _answer(conn, item, action=action, actor=actor, option=option, note=note, self_contained=self_contained)
        if self_contained == "no":
            _write_packet_defect(conn, target=item["ref"], actor=actor, note=note)
    elif action in _RESOLVE_ONLY_ACTIONS:
        pass
    elif action == "override":
        _override(conn, item, actor=actor, note=note, fm_id=fm_id, tier=tier)
    elif action == "approve":
        approval_id = _approve(
            conn, item, actor=actor, owners_obj=owners_obj, owners_path=owners_path, bucket=bucket, note=note,
            runs_dir=runs_dir, self_contained=self_contained,
        )
        if self_contained == "no":
            _write_packet_defect(conn, target=f"approval_record:{approval_id}", actor=actor, note=note)
        if not _approve_quorum_satisfied(conn, item):
            return f"queue item {item_id}: approval recorded"
    elif action == "redirect":
        _redirect(conn, item, actor=actor, owners_obj=owners_obj, owners_path=owners_path, bucket=bucket, to=to, fm_id=fm_id, note=note)
    elif action == "send_back":
        _send_back(conn, item, actor=actor, to=to, fm_id=fm_id, note=note)
        if kind == "escalation" and self_contained == "no":
            _write_packet_defect(conn, target=_escalation_defect_target(conn, item), actor=actor, note=note)
    elif action == "abandon":
        abandon(conn, item["ticket_id"], actor=actor, fm_id=fm_id, note=note, runs_dir=runs_dir)
        if kind == "escalation" and self_contained == "no":
            _write_packet_defect(conn, target=_escalation_defect_target(conn, item), actor=actor, note=note)
    elif action == "request_changes":
        approval_id = _request_changes(
            conn, item, actor=actor, owners_obj=owners_obj, owners_path=owners_path, bucket=bucket, fm_id=fm_id,
            note=note, self_contained=self_contained,
        )
        if self_contained == "no":
            _write_packet_defect(conn, target=f"approval_record:{approval_id}", actor=actor, note=note)
    elif action == "resume":
        _resume(conn, item)
        if kind == "escalation" and self_contained == "no":
            _write_packet_defect(conn, target=_escalation_defect_target(conn, item), actor=actor, note=note)
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


def resolve_by_waiver(conn: sqlite3.Connection, item: sqlite3.Row, waiver_id: int) -> None:
    """Resolve a `red_check` item as `waived`, on behalf of the covering waiver's own actor.

    `waived` names no entry in `ACTIONS`, so `act` never accepts it from a
    human; this is the only path that writes it, called by
    `runner.waivers.issue` immediately after a review-tuple waiver leaves
    its stage run's every blocking result `pass` or validly waived. The
    resolving actor is the waiver's own `actor_identity`, not a
    separately supplied one, since it is the waiver -- not a person
    acting on the queue -- that resolves the item.
    """
    waiver = record.get(conn, "waiver", waiver_id)
    if waiver is None:
        raise ActionRefused(f"no such waiver: {waiver_id}")
    owners_obj = owners.load_owners()
    _resolve(
        conn, item, actor=waiver["actor_identity"], action="waived", note=f"waiver:{waiver_id}",
        bucket=None, owners_obj=owners_obj,
    )


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
    """The question's wording, its options with their consequences, and which option is the default, for a human to answer from.

    Reads the lineage's current tip, not the id `item["ref"]` names: a
    flag correction leaves `ref` pointing at the now-superseded original,
    and a human deciding from this listing needs the corrected flags, not
    the ones the agent first wrote.
    """
    from runner import questions

    table, _, raw_id = (item["ref"] or "").partition(":")
    original = record.get(conn, "question", int(raw_id)) if table == "question" and raw_id else None
    question = questions.current_version(conn, original["id"]) if original is not None else None
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
    subject_hash = _approval_subject_hash(conn, item)
    lines = [f"  subject: {subject_hash}"]
    if item["kind"] == "packet_approval":
        # `queue_item` carries no column for the publication-target hash:
        # this is the one place it is shown to the human deciding, always
        # recomputed fresh rather than read back from anywhere stored.
        ticket = record.get(conn, "ticket", item["ticket_id"])
        if ticket is not None:
            lines.append(f"  publication target: {publication.publication_target(conn, ticket).hash}")
    lines.append("  approval records:")
    rows = conn.execute(
        "SELECT actor_identity, decision, active_attention_bucket FROM approval_record "
        "WHERE subject_hash = ? ORDER BY id",
        (subject_hash,),
    ).fetchall()
    for row in rows:
        lines.append(
            f"    {row['actor_identity']}: {row['decision']} "
            f"(active_attention_bucket: {row['active_attention_bucket']})"
        )
    return lines


def _plan_checklist_context(conn: sqlite3.Connection, item: sqlite3.Row) -> list[str]:
    """`factory queue`'s own view of a `plan_approval` item: every expected instance and its newest verdict, or `missing`."""
    from runner import checklist

    ticket = record.get(conn, "ticket", item["ticket_id"])
    if ticket is None:
        return []
    expected = checklist.expected_instances(conn, ticket)
    status = checklist.completeness(conn, ticket, expected)
    missing_keys = {(i.rubric_line_id, i.subject_item_key) for i in status.missing}
    verdicts = {
        (row["rubric_line_id"], row["subject_item_key"]): row["verdict"]
        for row in checklist.verdict_set(conn, item["ticket_id"])
    }
    lines = ["  checklist:"]
    for instance in expected:
        pair = (instance.rubric_line_id, instance.subject_item_key)
        state = "missing" if pair in missing_keys else verdicts.get(pair, "missing")
        lines.append(f"    {instance.rubric_line_id} / {instance.subject_item_key}: {state}")
    if status.unwaived_blind_spots:
        lines.append(f"  unwaived blind spots: {_instance_keys(status.unwaived_blind_spots)}")
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
    if item["kind"] == "plan_approval":
        lines.extend(_plan_checklist_context(conn, item))
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


# The implementation run kinds that are an actual execution attempt; `validation_only`
# is the runner's script-only verification pass after one, so on its own
# it stands for "a verification ran".
_IMPLEMENTATION_EXECUTION_KINDS = frozenset({"task", "fix_round"})
_IMPLEMENTATION_VERIFICATION_KIND = "validation_only"


def _implementation_progress(conn: sqlite3.Connection, ticket_id: int) -> dict:
    """The highest passing implementation task attempt, the execution count and the verification count of the ticket's implementation history."""
    rows = conn.execute(
        "SELECT attempt, run_kind, outcome FROM stage_run WHERE ticket_id = ? AND stage = 'implementation' ORDER BY id",
        (ticket_id,),
    ).fetchall()
    completed = [row["attempt"] for row in rows if row["run_kind"] in _IMPLEMENTATION_EXECUTION_KINDS and row["outcome"] == "pass"]
    return {
        "last_completed_task": completed[-1] if completed else None,
        "execution_count": sum(1 for row in rows if row["run_kind"] in _IMPLEMENTATION_EXECUTION_KINDS),
        "verification_count": sum(1 for row in rows if row["run_kind"] == _IMPLEMENTATION_VERIFICATION_KIND),
    }


def escalation_context(conn: sqlite3.Connection, item: sqlite3.Row) -> dict:
    """What an `escalation` item carries, derived from the record its `ref` points at.

    The stage run's reason (the latest failed runner check recorded on
    it), its own reasoning summary, the artefacts registered under it,
    the ticket's current binding (latest evidence tuple) if one exists,
    the stage's prior-attempt failure history, and for implementation the last
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
    if stage_run["stage"] == "implementation":
        context.update(_implementation_progress(conn, stage_run["ticket_id"]))
        # The registered `failure_history` JSON artefact a verification-
        # exhaustion escalation writes, distinct from the `failure_history`
        # list above (this stage's own prior-attempt summary): `None` for
        # any other escalation cause, which writes no such artefact.
        history = artefact_registry.latest(conn, stage_run["ticket_id"], "failure_history")
        context["failure_history_artefact_id"] = history["id"] if history is not None else None
    return context


def list_queue(
    conn: sqlite3.Connection, *, include_resolved: bool = False, owners_path: Path = owners.DEFAULT_OWNERS_PATH,
) -> str:
    """One text block per open item (every item, resolved included, with `include_resolved`), plus one line per ticket held at `intake` by capacity.

    A ticket capacity holds at `intake` has no queue item of its own -- the
    wait is derived from its state and the configured limit, not queued --
    so this is the only place the queue's own listing can show it.
    """
    owners_obj = owners.load_owners(owners_path)
    query = "SELECT * FROM queue_item"
    if not include_resolved:
        query += " WHERE resolved_at IS NULL"
    query += " ORDER BY id"
    blocks: list[str] = []
    for item in conn.execute(query).fetchall():
        blocks.extend(_item_block(conn, item, owners_obj))
        blocks.append("")
    limit = capacity.effective_parallel_limit(conn)
    for ticket in conn.execute("SELECT * FROM ticket WHERE state = 'intake' ORDER BY id").fetchall():
        wait_line = capacity.wait(conn, ticket, limit)
        if wait_line is not None:
            blocks.append(f"ticket {ticket['id']}: {wait_line}")
    return "\n".join(blocks).rstrip("\n")
