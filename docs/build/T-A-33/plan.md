# T-A-33 plan

## Steps

| # | Step | Files touched | Proves |
|---|---|---|---|
| 1 | `factory/catalogue/failure-modes.md`: front matter, the 25-row `Failure modes` table verbatim from the charter (id/stage/failure/consequence), and a `Tag schema` section listing the tag columns and every event kind's `tagged_by`/severity shape. | `factory/catalogue/failure-modes.md` | criteria 1-8 (fm_id catalogue check) |
| 2 | `factory/catalogue/decisions.md`: the catalogue's own decision log, seeded with the row recording the charter mirror. | `factory/catalogue/decisions.md` | — |
| 3 | `factory/rubrics/checklists/send-back-grounds.md`: the six grounds in a `ground \| description` table. | `factory/rubrics/checklists/send-back-grounds.md` | criterion 3 |
| 4 | `runner/tags.py`: `failure_modes`/`send_back_grounds` parsers; `fm_id` catalogue check; `MECHANICAL_ACTOR`/`MECHANICAL_KINDS` actor gate; `send_back` note-format check; `waiver` added to `_TARGET_TABLES` and `policy_exception`'s target-and-validity check; `packet_defect`'s fixed `FM-10`; the resolution-chain check (`resolves_tag_id`/`resolution_evidence_ref`). | `runner/tags.py` | criteria 1-8 |
| 5 | `runner/cli.py`: `factory tag` gains `--resolves`/`--resolution-evidence`. | `runner/cli.py` (tag block only) | criterion 8 |
| 6 | Seed-value fixes in existing tests that now hit the new refusals (catalogue `fm_id`, send-back note format, mechanical-actor gate). | `runner/tests/test_act.py`, `test_stage_interface.py`, `test_s3_checklist.py`, `test_stub_walk.py` | full-suite green |
| 7 | `runner/tests/test_tags.py` and its fixtures: one test per acceptance criterion, plus the catalogue-fm_id and parser checks. | `runner/tests/test_tags.py`, `runner/tests/fixtures/tags/` | criteria 1-8 |
| 8 | Manifest refresh; remove `factory/catalogue/.gitkeep`. | `factory/manifest.yaml` | `test_manifest_hash.py` |
| 9 | This brief and plan. | `docs/build/T-A-33/brief.md`, `docs/build/T-A-33/plan.md` | reviewed by the human, not a test |

## Test strategy

`test_tags.py` groups by acceptance criterion. Criterion 1 and 7 share
one seeding helper (`_seed_item`, mirroring `test_act.py`'s own) over
`red_check`/`eligibility` items and go through `queue.act` so the tag
write is exercised exactly as a human would trigger it, including the
`must_reject` case of an act with no `fm_id`. Criterion 2 goes through
`tags.tag` directly against a seeded `approval_record`/`question`
("decision record" fixture), since the live route through `queue.act` is
next ticket's. Criterion 3 parametrizes over the six grounds (accepted)
plus three `must_reject` shapes: no ground prefix, `other` with no text,
`wrong_brief_or_criteria` with no stage named. Criterion 4 reuses
`test_exclusion.py`'s own S1-exclusion seeding shape to reach a
`pilot_excluded` ticket and asserts zero `tag` rows. Criterion 5
parametrizes the three mechanical kinds against both actors, adds a
direct `incident` tag test (a human kind carrying attribution+severity),
and a `must_reject` for the queue's `control_event` action's now-refused
human-actor `control_defect` write. Criterion 6 seeds a valid and an
expired waiver (`waivers.yaml` fixture); the "grants nothing" test seeds
an unrelated blocking `check_result` and checks `waivers.blocking_status`
still reports it un-waived after the `policy_exception` tag lands.
Criterion 8 builds a resolution chain via two `packet_defect` tags, reads
the original row back unchanged, and asserts a raw `UPDATE` on it still
hits the pre-existing append-only trigger (`sqlite3.IntegrityError`),
plus three `must_reject` shapes (one of the pair missing, wrong ticket,
resolved row not a `packet_defect`). A closing pair of tests parse the
catalogue/checklist files directly and exercise `factory tag`'s new
`--resolves`/`--resolution-evidence` flags end to end through `cli.main`.
