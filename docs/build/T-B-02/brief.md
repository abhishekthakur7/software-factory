# T-B-02 brief: the list view complete

## What this delivers

Every human action across the nine queue-item kinds, plus the ticket-scoped
outcome actions the manual outcome record adds, now runs through one
`factory act` call surface. This ticket closes the three gaps left once
every earlier building ticket's own mechanism is wired in:

- The batch form of `factory act <plan_approval item> verdicts <file>`:
  a YAML list of `(rubric_line_id, subject_item_key, verdict, evidence)`
  tuples, each written as one `human_verdict` row through the existing
  single-verdict path, stopping the batch at the first `fail` exactly as a
  lone `fail` already does, and resolving the item once every expected
  instance has a row.
- `factory show --artefact <artefact id>`: evaluates the guard against
  `trust-profile.yaml`'s `governed_export_display` route, the same route
  export scans every file through, but over the `display` crossing. The
  acting reader must hold at least one role the route names, checked
  before the guard is ever consulted; a later refusal (an unadmitted data
  class, an inactive trust profile, a secret in the content) is the
  guard's own decision. An artefact whose `retention_until` has passed is
  still shown, prefixed with a line flagging it as subject to deletion.
- `factory act <question item> override`: corrects `question.consequential`
  and/or `question.hard_to_reverse` in place through the existing
  `questions.correct_flag`, which already records the reason as a tag on
  the question and leaves the item open for its own later `answer`.

Two guards close gaps the day-one mapping left open once a `plan_approval`
or `packet_approval` item's reviewer set can name more than one slot:
`approve` now resolves the item only once `approvals.evaluate` finds
quorum on its subject, not on the first slot's own record, and a second
decision by an actor who already holds a current head for a slot on the
same subject is refused before it can ever fork one. A `waiver` action on
a `plan_approval` or `red_check` item calls the existing `waivers.issue`
with the item's own ticket, taking the same flags `factory waive` took;
that standalone verb and its operations wrapper are gone, replaced
entirely by this one path.

Every other action in the list -- eligibility, plan and packet approvals,
red-check and escalation resolution, pause/resume/stop, base refresh,
manifest migration, export/import/purge, and the outcome/exposure/
coverage/incident/control-event actions -- reuses the mechanism its own
building ticket already tests; nothing about those mechanisms changes
here, only that they are proven once more, together, from one seeded
fixture set per kind.

Row covered: R-H-4.

## Design decisions

- The question item's `override` reuses `questions.correct_flag` (and its
  existing `flag_correction` tag) rather than inventing a second write
  path for the same two columns; `queue.act` only adds the CLI-facing
  dispatch and flag parsing on top of it.
- A waiver issued through `factory act` never resolves the queue item
  itself: `waivers.issue` already resolves a `red_check` through
  `queue.resolve_by_waiver` once every blocking result clears, and a
  `plan_approval` item is expected to stay open for its own later
  `approve`.
- The forked-head guard sits in `queue._record_decision`, the one write
  path `approve`/`redirect`/`request_changes` all share, rather than in
  each action separately: a second decision by the same actor on the same
  slot and subject is refused there before any row is written, so
  `approvals.evaluate`'s own fork detection stays a defence over rows this
  path never creates in the normal course of things.
- `factory show`'s ticket-id argument becomes optional and `--artefact`
  is added beside it, rather than a separate subcommand, since both read
  the one `show` verb and differ only in which id they take.

## Explicitly out

Each action's own mechanism (already built by the tickets it names in its
own description), the graduation approval's own quorum and report
mechanism, the capacity-wait line at `intake`, and exporting every action
through `runner/stage_interface.py`.
