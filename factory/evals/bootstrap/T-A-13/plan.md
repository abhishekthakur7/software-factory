# T-A-13 plan

## Steps

| # | Step | Files touched | Proves |
|---|---|---|---|
| 1 | `StubDeliverer`: one JSON state document per route (branch heads and pull requests per repository, receipts by key); the four deliverer operations; driving methods; the three reconciliation lookups. `Receipt`, `RemoteRefused`. | `runner/deliverers/stub.py` | criteria 7, 8 |
| 2 | `deliverer_for(route, runs_dir)` and the `Deliverer` protocol. | `runner/deliverers/__init__.py` | criteria 7, 8 (via the outbox tests that call it indirectly) |
| 3 | `ROUTE_FOR_OPERATION`, `InjectedCrash`, `dispatch` (guard the payload, mark `sending`, deliver, guard and store the receipt, mark `reconciled`/`failed`, three named fault points). | `runner/outbox.py` | criteria 1, 9, 10, 11, 19 |
| 4 | `reconcile_pending` and its two private halves: `_reconcile_sending` (receipt-by-key, then by remote identity, else back to `pending`) and `_dispatch_pending` (adopt a matching existing pull request, fail on an unexpected head, else `dispatch`). | `runner/outbox.py` | criteria 4, 5, 12, 14, 15, 16 (unchanged), 17 (unchanged) |
| 5 | `guard_decision_id` keyword on `artefact_registry.register`. | `runner/artefact_registry.py` | criterion 19 |
| 6 | `review_gate`'s real rule: effective-reviewer-set quorum plus a reconciled receipt whose remote head and payload digest match. | `runner/gates.py` | criterion 18 |
| 7 | `reconcile_pending` wired as the first statement of `advance` and `run`. | `runner/cli.py` | criterion 15 |
| 8 | Seeded ticket, quorum, and remote-scenario fixtures. | `runner/tests/fixtures/outbox/*.yaml` | every dispatch/reconciliation test |
| 9 | `test_outbox.py`: one or more tests per criterion, `must_reject` naming on every refusal assertion. | `runner/tests/test_outbox.py` | criteria 1-20 |
| 10 | Updated state-table fixture and loader so the existing `review_gate` scenario still passes under the real rule. | `runner/tests/fixtures/state_table/outbox_receipt.yaml`, `reconciled_receipt.json`, `test_state_table.py`'s `load_scenario` | `test_review_quorum_and_reconciled_receipt_moves_to_pr_opened` |
| 11 | This ticket's own brief and plan. | `docs/build/T-A-13/brief.md`, `docs/build/T-A-13/plan.md` | reviewed by the human, not a test |

## Test strategy

`test_outbox.py` activates a tmp copy of the fixture trust profile
(`profile_paths` + `_activate`, the same convention `test_guard.py` uses)
in every test that dispatches or reconciles, so a wrong guard computation
fails these tests too. `pr_create_intent` seeds a fresh review tuple, an
effective reviewer set with one resolvable slot, and the one approval that
satisfies it, then calls `intent_for_review_quorum` — the same path a real
ticket's quorum completion takes — rather than inserting an
`external_write` row by hand for the tests that exercise the full quorum
path; tests that only need a bare row under a known key (criteria 1, 2,
13, 16, 17) call `create_intent` directly.

Crash injection (criteria 9-11) calls `outbox.dispatch` directly with
`fault=` inside `pytest.raises(outbox.InjectedCrash)`, asserts the row's
state and the deliverer's state file at that exact point, then calls
`reconcile_pending` and asserts the row reconciles to exactly one pull
request in the stub's file — `before_local_commit`'s test is the one that
additionally calls `conn.rollback()` before retrying, since that fault
fires after local writes are issued but before they commit.

Refusal criteria (4's never-overwrite half, 12, 13, 17) are titled
`test_must_reject_...` and assert the refusal itself: an `IntentRefused`
exception, or a row landing in `failed` with the exact `last_error` and an
unmoved ticket field. Criterion 6 gets two tests: one proving the
approval and the intent land together, one (`test_must_reject_by_construction_...`)
proving a rolled-back transaction on a second database leaves neither row
behind at all.

## Verification

`uv run pytest -q`
