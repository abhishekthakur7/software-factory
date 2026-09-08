# T-A-33 brief: tags -- catalogue, human tags, mechanical tags, policy exception, resolution chains

## What this delivers

The catalogue `tag.fm_id` must resolve against (`factory/catalogue/
failure-modes.md`, mirroring the charter's twenty-five failure modes,
plus its own decision log and the checklist's send-back grounds), and
every remaining rule the `tag` write path (`runner/tags.py`) enforces on
top of the target-shape check that already existed: an `fm_id` must name
a real catalogue entry; the acting identity must match the kind's own
human-or-mechanical shape (`stale_index`, `escalation`, `control_defect`
are written only by the runner, every other kind only by a human);
`send_back`'s note must open with one of the checklist's six ground ids,
with `other` and `wrong_brief_or_criteria` carrying their own extra
requirement; `policy_exception` must target a waiver that is valid right
now, and classifies it without granting anything; `packet_defect` is
always failure mode FM-10; and a resolution tag (`resolves_tag_id` +
`resolution_evidence_ref`) may only point at a `packet_defect` row on the
same ticket, appending rather than touching it.

## Rows covered

R-T-6 (`docs/prd/02-1-ticket-record.md`); the `tag` entity paragraph
(`docs/prd/02-2-entities.md`); the charter's failure-mode catalogue
(`docs/charter.md` section 4).

## Owner decisions this ticket follows

`tags.tag` stays the one write path every caller goes through; catalogue
and checklist files are parsed with `runner.artefacts.parse` rather than
a second ad hoc reader; a schema change is not needed since `tag`'s
columns, `_TARGET_TABLES`, and `TAG_EVENT_KINDS` already covered every
shape this ticket adds (the `waiver` target and the resolution columns
were already there, unused).

## Decisions this brief did not already settle

- **`MECHANICAL_KINDS` is enforced as a hard, symmetric rule inside
  `tag()` itself: `stale_index`, `escalation`, and `control_defect`
  refuse every actor but `"runner"`, and every other kind refuses
  `"runner"` itself.** This is what the brief specifies and what the
  entity paragraph states ("tagged_by is a human except stale_index,
  escalation, and mechanically detected control defects"). Two existing,
  out-of-scope call sites write one of these kinds with a human actor:
  `runner/control.py`'s `stop` (a human-initiated abort tags its own
  `escalation`) and `runner/queue.py`'s `_record_control_event` (the
  `control_event` action tags `control_defect` under whichever actor
  called `factory act`). Both are outside this ticket's ownership and
  are left as written; the tests that exercised them are adjusted (see
  below) rather than the production code, since neither module is
  ticket-owned here. This means `factory stop`'s escalation tag is now
  always attributed to the runner regardless of who typed the command,
  and a human `factory act <item> control_event` on any item kind is now
  always refused -- both flagged here for the merge, since a future
  ticket may want `control.py` to stop threading a human actor into a
  tag this rule now requires to be mechanical, or `queue.py`'s
  `control_event` to record a human's attribution and disposition
  through `incident_observation` alone rather than through a second,
  now-impossible tag write.
- **The catalogue's `Failure modes` table drops the charter's
  `Frequency` column.** The brief asks for `id | stage | failure |
  consequence`; frequency (like cost) is computed from tag rows, not
  reproduced as a static catalogue value, and the charter's own column
  is `TBD` at every row today regardless.
- **`send_back`'s note format is checked as `<ground>: <text>`,
  `ground` matched against the checklist's `Grounds` table after
  stripping surrounding whitespace.** `other` additionally requires
  non-empty `text`; `wrong_brief_or_criteria` additionally requires one
  of `runner.schema.STAGES` (`S0`..`S7`) to appear in `text`, which is
  the only mechanical way to check "names the target stage" without
  hand-rolling a second stage list.
- **`packet_defect`'s target stays whatever the caller passes**
  (`approval_record:<id>` or `question:<id>`, both already accepted
  target tables); only its `fm_id` is pinned to `FM-10`. The exact
  binding rule for the live request-changes route is explicitly the next
  ticket's (T-A-34); this one only supports the write path.
- **A resolution tag's own `event_kind` is not constrained** -- only the
  row it resolves must be a `packet_defect` on the same ticket. The test
  suite exercises the natural case (a second `packet_defect` tag
  resolving the first, standing in for "a later corrected packet"),
  since the brief does not require the resolving tag to carry any
  particular kind of its own.

## Existing tests adjusted

Every adjustment below is either a `note`/`fm_id`/target seed-value fix
(a call that used to write an arbitrary or free-text tag and now must
satisfy the catalogue/note-format rules) or a consequence of the
`MECHANICAL_KINDS` rule above:

- `runner/tests/test_act.py`: parametrized send-back/redirect cases and
  two direct `send_back` calls gain a ground-prefixed `note`;
  `test_factory_tag_records_one_human_tag_on_the_named_target` now
  targets a seeded `waiver` (a `policy_exception` tag can no longer
  target a bare `ticket`); `test_control_event_records_an_incident_
  observation_and_leaves_the_item_open` now asserts the human-actor
  `control_defect` write is refused, while the `incident_observation`
  row it writes first still lands.
- `runner/tests/test_stage_interface.py`: the four `factory stop` calls
  pass `tags.MECHANICAL_ACTOR` instead of the human identity (the
  `escalation` tag they write is now mechanical-only; no test here
  asserted `tagged_by`, so no assertion changed); its own `send_back`
  call gains a ground-prefixed note.
- `runner/tests/test_s3_checklist.py`: the fail-verdict test's note
  gains a `technically_unsound:` prefix.
- `runner/tests/test_stub_walk.py`: the same `factory stop` actor fix as
  above, committed on its own since another builder owns this file this
  wave.

## Out of scope

The live request-changes and self-containedness decisions, including
`packet_defect`'s exact `approval_record` binding (T-A-34). Changing
`runner/control.py` or `runner/queue.py` themselves.
