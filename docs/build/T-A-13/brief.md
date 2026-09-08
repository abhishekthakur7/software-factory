# T-A-13 brief: the transactional outbox, stub deliverers, and reconciliation

## What this delivers

The worker half of the outbox the record schema and the seam already
describe: everything between a satisfied review quorum and a pull request
that actually exists on the fake remote, with no crash or race ever
producing two remote objects for one ticket action.

- `runner/outbox.py` (extended) — `dispatch`, which performs exactly one
  `external_write` intent: guards its payload, hands the payload to the
  operation's deliverer, guards the receipt the deliverer returns, and
  stores both the receipt artefact and the row's new state (`reconciled`,
  or `failed` with `last_error` on a guard deny or a refused remote call).
  `reconcile_pending`, the one call every state-advancing command makes
  first: it resolves the ticket's `sending` rows (ask the deliverer what
  it already knows; adopt the receipt or fall back to `pending`) before
  ever touching a `pending` row, and a `pending` `pr_create`/`pr_update`
  reconciles against the remote branch and any open pull request before
  `dispatch` is ever called. `ROUTE_FOR_OPERATION`, the fixed operation-
  to-route map. `InjectedCrash`, raised by `dispatch`'s three named fault
  points for a test to prove reconciliation recovers from each.
  `create_intent` and `intent_for_review_quorum` are unchanged in name and
  keyword signature, since the queue module being built in parallel calls
  the latter directly.
- `runner/deliverers/__init__.py` — `deliverer_for(route, runs_dir)`,
  reading a route's `deliverer` field (`stub` to a `StubDeliverer`, `live`
  to `NotImplementedError` naming the route); the `Deliverer` protocol
  both present.
- `runner/deliverers/stub.py` — `StubDeliverer`, one JSON document per
  route under `runs_dir/remote/`, holding branch heads and pull requests
  per repository and receipts by idempotency key; `pr_create`, `pr_update`,
  `digest`, `jira_feedback` (the four deliverer operations); the driving
  methods a test uses to seed an unexpected head, an existing pull
  request, or a duplicate-key receipt (`set_branch_head`,
  `seed_pull_request`, `seed_receipt`); and the lookups reconciliation
  needs (`receipt_for_key`, `open_pull_request`, `branch_head`). `Receipt`,
  a frozen dataclass serialisable to the receipt artefact's JSON.
- `runner/gates.py` — `review_gate` now fires `review_quorum_reconciled`
  only from the ticket's latest `external_write` row in state `reconciled`
  whose remote identity is set and whose stored receipt's remote head and
  payload digest match the row's own desired values, with review quorum
  evaluated over the review tuple's effective reviewer set exactly as
  `outbox.intent_for_review_quorum` evaluates it. A `superseded` latest
  row still routes to `checks`.
- `runner/cli.py` — `advance` and `run` each call
  `outbox.reconcile_pending` as their first statement after the
  ticket-exists check.
- `runner/artefact_registry.py` — `register` takes an optional
  `guard_decision_id` keyword, for the one caller (the receipt artefact)
  whose content is itself a governed crossing rather than internal run
  bookkeeping.
- `runner/tests/test_outbox.py` and seeded fixtures under
  `runner/tests/fixtures/outbox/`.
- `runner/tests/fixtures/state_table/outbox_receipt.yaml` and its new
  `reconciled_receipt.json`, updated so the existing `review_gate` state-
  table test still exercises a real reviewer-set quorum and a receipt that
  actually matches, now that the gate does real work instead of a stored
  equality check.

## Row covered

R-T-11 (`docs/prd/02-1-ticket-record.md` line 21; the `external_write`
paragraph of `docs/prd/02-2-entities.md`; the `review` and `pr_opened` rows
of `docs/prd/02-3-ticket-states.md`): every external write goes through one
transactional outbox; the last quorum-completing approval and the intent
it authorises commit together; a worker performs the intent, stores the
receipt, and reconciles by idempotency key and remote identity before
retry after ambiguity; `pr_create` and `pr_update`'s exact keying,
reconciliation, and never-overwrite rules; one key never carrying two
payloads; a stale pending intent becoming `superseded`; an ambiguous
`sending` intent reconciling before another is created under its key; and
ticket state advancing only from a receipt whose desired remote head and
payload hash match.

## Owner decisions this ticket follows

- Guard timing: the payload guard runs at dispatch, never inside the
  approval-plus-intent transaction, since `guard.decide` commits its own
  row. Each dispatch attempt guards the payload once (stamping
  `external_write.guard_decision_id`) and the deliverer's receipt once
  more (re-stamping the same column), both against the operation's fixed
  route (`ROUTE_FOR_OPERATION`).
- The three crash-injection points are exactly the one-line
  `if fault == ...: raise InjectedCrash(fault)` checks the ticket names,
  placed after the real side effect that precedes each: nothing sent
  before `before_send`; the deliverer already holding the object before
  `after_remote_success`; the receipt already returned, with local writes
  issued but not yet committed, before `before_local_commit`.
- `reconcile_pending` processes every `sending` row for the ticket before
  any `pending` one, oldest first within each state, and re-reads a row
  immediately before acting on it — resolving an earlier row (a supersede,
  or the ticket fields a reconciled `pr_create` moves) can change what a
  later one should do.
- A `pending` `pr_create`/`pr_update` is reconciled against the remote in
  `reconcile_pending`'s own pre-checks, never inside `dispatch` itself:
  `dispatch` performs an intent unconditionally once called, so a caller
  that already knows an intent should be sent (a test driving `dispatch`
  directly for crash injection) never has that decision re-litigated
  underneath it.

## Decisions this brief did not already settle

- **The stub's state-file path is one file per route, not one per
  repository.** `deliverer_for(route, runs_dir)` receives no repository —
  only a route and a run root — so the state file is
  `runs_dir/remote/<route_id>.json`, and the document itself nests branch
  heads and pull requests under a `repositories` key so more than one
  repository could share the file if the project ever named more than
  one. Receipts are keyed by idempotency key alone, not nested under a
  repository, since a key is already globally unique per intent and two of
  the four operations (`digest`, `jira_feedback`) have no repository at
  all.
- **The receipt guard call does not gate what gets stored.** `github_pr`'s
  field allowlist (`branch_ref`, `head_sha`, `pr_body`, `target_ref`)
  describes an *outbound* payload; a receipt's field names (`remote_identity`,
  `remote_head_sha`, ...) share none of them, so projecting a receipt
  through that allowlist the way an outbound payload is projected would
  redact it to nothing. The guard call on a receipt is therefore
  fail-closed enforcement only — a deny stops the write and is recorded —
  and the receipt artefact stores the receipt's actual content, with the
  guard decision's id attached as the authorising decision rather than as
  a content filter.
- **`intent_for_review_quorum`'s current signature took no `profile_path`/
  `owners_path`.** Creating an intent never invokes the guard (payload
  guarding is a dispatch-time concern per the timing decision above), so
  this ticket added no such keywords to it; `dispatch` and
  `reconcile_pending` are the two functions a test points at a tmp trust
  profile.
- **`review_gate`'s stricter rule required updating one existing
  state-table fixture.** `test_state_table.py`'s `outbox_receipt.yaml`
  "reconciled" scenario previously seeded only a bare `state: reconciled`
  row and a subject-matched `approval_record`, which the old thin-equality
  gate accepted. The real rule needs an effective reviewer set with a
  resolvable slot, an approval bound to that slot's id, and a receipt
  artefact whose content actually matches the row's desired head and
  payload digest — so the fixture (and `load_scenario`'s loader, which
  gained a `fixture:<name>` path-resolving prefix for the artefact row's
  `path`) now seeds all of that. No other scenario in that file exercises
  the `reconciled` branch, so nothing else needed to change.
- **Criterion 20's "revision" scenario is exercised without walking the
  full `pr_opened` → `implementing` → `checks` → `review` state path.**
  `intent_for_review_quorum` only ever reads the latest review tuple, its
  effective reviewer set, and `ticket.pr_identity` — it does not read
  `ticket.state` at all — so a test proves the same functional claim (one
  `pr_create`, then one `pr_update`, each with a receipt) by seeding a
  second review tuple and quorum directly and advancing `ticket.head_sha`,
  without also reconstructing the state transitions a real revision would
  pass through first.
- `_dispatch_pending` and `dispatch` share one rule for "does an existing
  open pull request already say what I want to publish": exact equality
  of `head_sha` and `pr_body_hash` against the row's `desired_remote_head_sha`/
  `pr_body_hash`. Anything else falls through to the branch-head check and
  then, absent a mismatch, an ordinary `dispatch` — including the case of
  a stale open pull request that does not match while the branch is still
  at the expected prior head, which the acceptance text does not name as
  a separate case and this ticket does not special-case either.

## Out of scope

The worker's pre-dispatch freshness recheck of target, branch and subject
equality beyond what reconciliation itself needs; S6's automatic dispatch
of `pr_create`/`pr_update` after quorum and the packet/PR-body content it
sends; a live deliverer for any route (`deliverer_for` raises
`NotImplementedError` for one); `runner/schema.py`, `runner/queue.py`,
`runner/tags.py`, `runner/run_ledger.py`, `runner/stages/*`,
`runner/transitions.py`, `runner/state_table.py`, `runner/approvals.py`,
`runner/guard.py`, `runner/governance.py`, `runner/trust_profile.py`, and
everything under `factory/`, all untouched by this ticket.
