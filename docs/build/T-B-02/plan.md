# T-B-02 plan

| # | Step | Files touched | Proving test |
|---|---|---|---|
| 1 | Add the batch-verdicts action: `_act_verdicts_batch` reading a YAML tuple list through the existing `_act_verdict` path, `"verdicts"` in `plan_approval`'s action set, and the `file` positional / `verdicts_file` field wiring. | `runner/queue.py`, `runner/cli.py` | `runner/tests/test_act_batch_verdicts.py` |
| 2 | Add the governed-artefact display verb: `operations.show_artefact` (the guard's `display` crossing over `governed_export_display`, the reader-role check, the retention-flag line), `show`'s optional ticket id and new `--artefact`/`--actor` flags. | `runner/operations.py`, `runner/cli.py` | `runner/tests/test_governed_artefact_open.py` |
| 3 | Add the question item's `override` action: `_question_override` over the existing `questions.correct_flag`, `"override"` in `question`'s action set, and the `--consequential`/`--hard-to-reverse` flags. | `runner/queue.py`, `runner/cli.py` | `runner/tests/test_act_full_list.py` |
| 4 | Gate a `plan_approval`/`packet_approval` item's `approve` resolution on `approvals.evaluate`'s own quorum rather than the first slot's record, and refuse a second decision from an actor who already holds a current head for a slot on the same subject. | `runner/queue.py` | `runner/tests/test_act_guards.py`, `test_approval_slot.py` |
| 5 | Add the `waiver` action on `plan_approval`/`red_check` items, calling `waivers.issue` with the item's own ticket and the flags `factory waive` took; delete the `waive` verb and `operations.waive`. | `runner/queue.py`, `runner/cli.py`, `runner/operations.py` | `runner/tests/test_act_full_list.py` |
| 6 | Drive every kind/action pairing and every command of the list once, seeded per case, reusing the existing seeding helpers. | `runner/tests/test_act_full_list.py`, `runner/tests/fixtures/act_full_list/` | itself |
| 7 | Prove the acting identity and role land on every resolution and on an approval's own row. | `runner/tests/test_resolution_role.py` | itself |
| 8 | Prove no response, row, or log line across the whole action list ever contains a credential value. | `runner/tests/test_no_credential_exposure.py` | itself |
| 9 | Record this brief and plan and copy them to the bootstrap fixture tree. | `docs/build/T-B-02/`, `factory/evals/bootstrap/T-B-02/`, `factory/evals/bootstrap/eval.yaml` | `runner/tests/test_bootstrap_fixtures.py` |

## Test strategy

`test_act_full_list.py` seeds a ticket directly in the state each kind's
item needs (matching `test_act.py`'s and `test_state_table.py`'s
convention) and reuses `test_act.py`'s governed-ticket-field helper,
`support.approve_current_plan`, and `test_s5_waivers.issue_review_waiver`
rather than re-deriving them; each case asserts the effect the action's
own mechanism has (a transition, a tag, an approval row, a verdict row,
a waiver row), never a literal the test just passed in. The guard and
approval-slot tests seed a real two-slot reviewer set with a second real
identity (a scratch `owners.yaml` copy, the same pattern
`test_s5_waivers.py` already uses) so the quorum and fork guards are
exercised against two actual actors rather than one identity satisfying
every slot at once. The credential test seeds a secret pattern the trust
profile's own secret rules match into an artefact, a tag note, and an
allowlisted environment name, then drives every action and command the
list carries and asserts none of their return values, the rows they
wrote, or the guard's own stored fields ever carry it.
