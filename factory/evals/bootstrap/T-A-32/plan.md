# T-A-32 plan

## Steps

| # | Step | Files touched | Proves |
|---|---|---|---|
| 1 | `factory/config/waiver-policy.yaml`: the never-waivable list (verbatim from the ticket brief) and two policy entries, `impact-blind-spot` (plan-candidate, any grader line) and `contract-evidence-gap` (review-tuple, `behavior_contract_evidence`/`base_test_diff`). | `factory/config/waiver-policy.yaml` | criterion 10; entry selection for 1-9 |
| 2 | `runner/waivers.py`: `load_policy`, `Policy`/`PolicyEntry`, `subject_hash`, `issue`, deepened `validity`, `recheck`; `blocking_status`/`cleared`/`waiver_for_result`/`effective_result` untouched in signature and shape. | `runner/waivers.py` | criteria 1-9 |
| 3 | `runner/queue.py`: `resolve_by_waiver`, the sole writer of a `red_check` item's `waived` resolution; not reachable through `ACTIONS`. | `runner/queue.py` | criterion 2's shared-item resolution |
| 4 | `runner/checklist.py`: `_waived` asks `waivers.validity` instead of a bare expiry comparison. | `runner/checklist.py` | criterion 1's completeness switch |
| 5 | `runner/gates.py`: `checks_gate` admits `checks -> review` when S5's latest run passed or `waivers.cleared` holds over it. | `runner/gates.py` | criterion 2's downstream gate effect |
| 6 | `runner/cli.py`: `_due_stage` treats a cleared S5 the same way, so a waived run is not rerun; the `waive` subcommand block (kept apart from `tag`). | `runner/cli.py` | criterion 2's downstream due-stage effect; the CLI entry point |
| 7 | `runner/tests/test_s5_waivers.py` and `runner/tests/fixtures/waivers/never_waivable/*.yaml` (twelve fixtures, one per never-waivable check name). | `runner/tests/test_s5_waivers.py`, `runner/tests/fixtures/waivers/` | criteria 1-10 |
| 8 | Two pre-existing raw-inserted `waiver` rows in `test_s3_checklist.py` gain the fields `completeness`'s new `waivers.validity` call now checks (policy id/version/hash, actor role, subject hash, scope, compensating controls) so the "does not block" case stays genuinely valid; the expired case needed no change (expiry alone still blocks). | `runner/tests/test_s3_checklist.py` | no regression in the existing suite |
| 9 | Manifest hashes recomputed for the new and changed files under `factory/`. | `factory/manifest.yaml` | `test_manifest_hash.py` |
| 10 | This ticket's own brief and plan. | `docs/build/T-A-32/brief.md`, `docs/build/T-A-32/plan.md` | reviewed by the human, not a test |

## Test strategy

`test_s5_waivers.py` seeds every scenario directly against the record --
a ticket with the committed S1/S2 rubrics plus the S3 checklist fixture's
own small `contract_unit` rubric line (`factory/evals/rubrics/S3/
fixtures/checklist/`, the same fixture `test_s3_checklist.py` already
uses) for plan-candidate cases, and a hand-seeded S5 `stage_run` plus a
review `evidence_tuple` and one or more `check_result` rows for
review-tuple cases. No git checkout, no stage driver, no fixture-worker
adapter: `waivers.issue` and `waivers.validity` take rows and a
connection, so seeding rows directly is enough to prove every rule.

Criterion coverage: 1 (plan-candidate waiver enters the plan tuple's
`plan_waiver_set_hash`, checklist counts complete) and its `must-reject`
companion (a `fail` verdict is never waivable); 2 (a review-tuple waiver
turns `blocking_status` `waived`, clears the run, and resolves the
shared `red_check` item -- both the "nothing red remains" and "a fail
remains" branches) plus a `must-reject` proof that `queue.act` itself
refuses `waived`; 3 (an actor whose held roles exclude the policy's
`roles` is refused, via a small per-test `owners.yaml` copy with one role
reassigned); 4 (the row records the exact policy id/version/file hash);
5 (a waiver already past `expires_at` -- seeded directly, since `issue`
itself refuses an expiry that is not after the issuing time -- blocks at
`validity` and `cleared`); 6 (`must-reject` for empty compensating
controls and for no evidence ids, each its own test); 7 (the packet's
evidence table names the waiver, scope, and expiry -- `skipif`'d on
`factory/scripts/tools/packet_assemble` existing, built from every key
the parallel ticket's own contract lists); 8 (three independent recheck
blocks: a fresh review tuple superseding the one a waiver bound,
mismatched evidence hashes seeded directly, and an actor demoted out of
the authorising role in a caller-supplied `owners.yaml`, plus one test
proving `recheck` enumerates both a plan- and a review-tuple waiver in
one call); 9 (a bare `policy_exception` tag with no real waiver behind
it changes nothing `cleared` or `blocking_status` reports); 10
(`pytest.mark.parametrize` over all twelve never-waivable fixture
files, each refused by name regardless of which otherwise-valid policy
is named).

`test_s3_checklist.py`'s two pre-existing waiver tests are the one place
this ticket's change to `checklist._waived` could silently regress: the
"unexpired waiver does not block" case now needs a genuinely valid
waiver under `waivers.validity`'s fuller rules, not just an unexpired
`expires_at`, so its seed row gained the policy binding, actor role, and
subject hash `issue` would have written; the "expired" case needed no
change, since expiry alone already blocked it before and after.
