# T-A-12 brief: queue items, `factory queue` and `factory act`

## What this delivers

The queue as the one channel to a human, and the one place every human
decision on it is recorded:

- `runner/queue.py` -- `ACTIONS`, the day-one `queue_item.kind` to action
  mapping as a module constant; `open_item`, the seam a later stage calls to
  queue a decision (blocking the ticket on it for every kind except
  `pr_outcome`, which is non-blocking by construction); `act`, the sole
  writer of a queue item's resolution, which validates the kind/action
  pairing, resolves the acting identity and, for a plan or packet decision,
  the reviewer slot that identity fills, dispatches the action's own effect
  through the same functions any other caller would use
  (`transitions.apply`, `approvals.record_approval`, `tags.tag`,
  `outbox.intent_for_review_quorum`), and settles the item's once-only
  resolution columns; `abandon`, the ticket-level operation `factory
  abandon` and `act`'s own `abandon` action both call; `list_queue`, the
  read side `factory queue` prints; and `latency_seconds`.
- `runner/tags.py` -- `tag`, the one function every human-transition tag in
  this ticket (`send_back`, `abandoned`, `override`, `revision_after_approval`,
  `control_defect`) writes through, validating the target shape against the
  record before insert and deriving the tag's own `ticket_id` from the
  target row rather than taking it on faith.
- Four new `runner/cli.py` subparsers -- `queue`, `act`, `abandon`, `tag` --
  each a thin wrapper printing its in-process function's return value; every
  other line of the file is unchanged.
- `runner/tests/test_queue.py`, `runner/tests/test_act.py`,
  `runner/tests/test_attention_bucket.py`, and seeded fixtures under
  `runner/tests/fixtures/queue/`.

## Rows covered

R-H-1 (`docs/prd/05-human-interaction.md`): one queue holds every human item
kind, records queue latency, and shows the minimum governed context;
`pr_outcome` is non-blocking and excluded from attention/touchpoint
measures, and queue latency is never labelled active attention.

R-H-12: every plan and packet `approval_record`, including a redirect or
reject decision, requires the acting human's coarse `active_attention_bucket`
from the six values including `unknown`; a non-approval queue action may
record one optionally; the factory collects no keystroke, focus-event,
editor-telemetry, or inferred individual-attention signal.

R-H-4 (`docs/prd/05-human-interaction.md`), so far as this ticket's day-one
action vocabulary reaches it: the local queue takes eligibility, question/
default, plan and packet approval/redirect/request-changes, send-back,
pause/resume/stop, escalation, rubric inspection, incident/control event,
and abandon actions, each recording canonical actor and role.

## Owner decisions this ticket follows

- `queue_item.kind` to `action` mapping, `ACTIONS: dict[str, frozenset[str]]`,
  exactly as specified; `control_event` is accepted on every kind but
  `pr_outcome`, in addition to the mapping.
- What a human passes to `factory act` -- item id, action, `--actor`,
  `--bucket` (required only for `approve`/`redirect`/`request_changes`),
  `--note`, `--to`, `--fm`, `--category`/`--severity`, `--option` -- and how
  everything else is derived: the approval's slot and role from the item's
  reviewer set matched against the actor's roles in `owners.yaml`;
  `authority_policy_hash` from `owners.authority_policy_hash()`;
  `membership_snapshot_hash` from `canonical.content_hash(owners.identity_snapshot(...))`;
  `attestation_version` the literal `"queue-act-v1"`; `attestation_hash` the
  canonical hash of `{item_id, action, note}`.
- Per-action effects exactly as specified: `answer`/`accept_default` write an
  `answer` row and mark the question `answered` with no state transition;
  `granted`/`declined` only resolve the item, leaving `gates.intake_gate` to
  derive the transition on the next `factory advance`; `override` writes the
  ticket's tier-override fields and an `override` tag; `approve` on a plan
  item records the approval and lets `gates.plan_review_gate` decide
  advancement; `approve` on a packet item records the approval and calls
  `outbox.intent_for_review_quorum` in the same transaction; `redirect` records
  a `redirect` decision plus send-back semantics; `request_changes` records a
  `reject` decision, transitions, and tags; `send_back` transitions and tags;
  `abandon` is the one shared function; `resume` on an escalation item picks
  its transition from the failed stage the item's `ref` names; `resume` on a
  manual pause clears the pause fields with no transition; `stop` applies
  `escalate`; `close_inspection` only resolves; `control_event` inserts an
  `incident_observation` row and its tag without resolving the item.
- Resolution is one `record.update` of the once-group
  (`resolved_at`, `resolved_by`, `action`, `note`, `active_attention_bucket`);
  `ticket.blocked_on` clears when the resolved item was the blocking one;
  queue latency is `latency_seconds(item) -> float | None`.
- `open_item(conn, *, ticket_id, kind, stage=None, tier=None, ref=None, approval_subject_hash=None, reviewer_set_id=None) -> int`
  sets `queued_at` and blocks the ticket on the new item for every kind
  except `pr_outcome`.
- `factory queue` lists open items (`--all` for resolved too) as plain text,
  one block per item, with an eligibility item additionally showing the
  exact trust profile and trust approval-set hashes, the satisfying
  `trust_profile` approval set by slot and actor, the planned RACI roles
  from `owners.yaml`, the ticket type and data class to confirm, and the
  scrutiny paragraph; a plan or packet item shows each recorded
  `approval_record` for its subject by actor, decision, and
  `active_attention_bucket`, separate from the queue-latency line and the
  decision outcome.
- `runner/tags.py`'s `tag(conn, *, target, kind, fm_id, actor, note=None, severity=None) -> int`,
  validating `target` against the record and requiring severity for
  `incident`, `control_defect`, and `policy_exception` kinds.
- The forbidden-telemetry scan (a token scan over `factory/manifest.yaml`,
  every file under `factory/config/`, and every non-test `.py` under
  `runner/`) and the AST check that every `active_attention_bucket`
  assignment or keyword argument in `runner/` is a plain name or the literal
  `"unknown"`.

## Decisions this brief did not already settle

- **`--fm` is also required for `redirect` and `request_changes`**, even
  though the owner's flag-requirement list names only `send_back`,
  `abandon`, `override`, and `control_event`. Both actions write a tag
  (`send_back` for redirect's send-back semantics, `revision_after_approval`
  for request-changes) through `tags.tag`, and the `tag` table's `fm_id`
  column is `nullable=False` regardless of which action produced the row.
  `tags.tag` itself raises a clear `TagRefused` when `fm_id` is absent,
  rather than letting a missing id surface as a raw `NOT NULL` constraint
  failure three calls down.
- **`escalation`'s `send_back` pairing has no matching state-table row when
  the ticket is actually `escalated`.** The state table gives `escalated`
  its own named routes (`escalation_verification_resolved_to_*`,
  `escalation_resume_*`) and no generic `send_back_to_*` row; a real
  escalation's send-back is out of this ticket's scope (only `resume`,
  `send_back`, and `abandon` are asked for, and the state table itself only
  wires up two of the three from `escalated`). `act`'s `send_back` dispatch
  is uniform across every kind that lists it -- it applies
  `send_back_to_<to>` and writes the tag, exactly as the owner's per-action
  description states -- and correctly refuses when the ticket's current
  state carries no such row, per "refuse if the transition table has no row
  rather than guessing." `test_act.py` proves the pairing succeeds against a
  ticket seeded in a state that does carry the row (`checks`), the same way
  a red-check send-back is exercised, and documents the gap in its own
  docstring rather than silently special-casing `escalation` inside
  `queue.py`.
- **An actor must be a known identity in `owners.yaml`** (an identity held
  by at least one role) for every `act` call, not only an approval decision;
  an approval action additionally requires that identity to fill a slot on
  the item's reviewer set. This reads the owner's "an actor who fits no
  slot, or an unknown identity, is refused before anything is written" as
  two separate checks -- one for every call, one only where a slot exists to
  fit -- rather than gating every action behind slot resolution.
  `_actor_role` (used by `control_event`'s `recorder_role`) picks the
  lowest-sorted role the actor holds when more than one applies, since the
  pilot's single identity holds every role and a stable, deterministic
  choice is needed regardless.
- **`control_event`'s tag points at the queue item**
  (`queue_item:<item_id>`), not the `incident_observation` row it also
  writes: `tag`'s target shapes are `ticket`, `stage_run`, `approval_record`,
  `queue_item`, and `artefact` only, per this ticket's own specification of
  `runner/tags.py`; `incident_observation` is not one of them, so the
  observable target the tag names is the item the control event was raised
  against.
- **`factory queue`'s eligibility block reads the satisfying trust approval
  set by `subject_hash = ticket.trust_profile_hash`**, not by `ticket_id`,
  since a `trust_profile` gate's approval rows bind to the profile subject
  itself (`entities.md`'s `approval_record` paragraph) and need not carry a
  ticket id at all.
- **`_resolve_slot` returns the first slot whose role the actor holds, or
  whose owner is the actor**, in the reviewer set's own slot order; the
  pilot's fixtures never need a second match, so no tie-break beyond
  encounter order is specified or tested.

## Out of scope

The full tag catalogue and its kinds beyond the five this ticket writes
(later ticket); the control-defect category enum and disposition path
(later ticket); `pr_outcome`'s own actions (Later); the views/report agent's
work on `runner/schema.py` `VIEWS` and `factory report`; the outbox worker's
dispatch and reconciliation (`runner/outbox.py`, `runner/deliverers/*`,
`gates.review_gate`) beyond the one `intent_for_review_quorum` call this
ticket already makes; anything under `factory/`.
