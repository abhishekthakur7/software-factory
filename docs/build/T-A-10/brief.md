# T-A-10 brief: binding — canonical subject hashes, plan and review tuples, preflight construction

## What this delivers

The one module that turns already-computed hashes into the plan and review
`evidence_tuple` rows the rest of the record binds decisions against:

- `runner/binding.py` — `set_hash` (the canonical hash of the sorted
  canonical hashes of a collection, used for every set-shaped binding: the
  question-resolution set, the current-assumption set, the human-verdict
  set, the plan-waiver set, and the deviation set); `PlanComponents` and
  `ReviewComponents`, frozen dataclasses naming exactly the fields the plan
  and review `evidence_tuple` columns bind; `create_plan_tuple` and
  `create_review_tuple`, which insert one row each through `record.insert`,
  hashing the full column set the same way `approvals.record_approval`
  hashes an approval record so the stored `content_hash` is always
  recomputable from the row alone; `plan_tuple_currency`, which compares a
  stored plan tuple against a caller-supplied current `PlanComponents`
  without ever reading the `ticket` table or any config itself; and
  `preflight_review_tuple`, the S5 preflight as an in-process function,
  which verifies the plan tuple, plan quorum, the actual/effective reviewer
  sets, and target-base/head/diff freshness, in order, before creating the
  review tuple in one transaction.
- `runner/tests/test_binding.py`, `runner/tests/test_preflight.py`, and
  seeded component fixtures under `runner/tests/fixtures/binding/`.

This module reads no config file and no git repository. Every bound hash
and SHA arrives as an argument, so the trust profile, the recipe catalogue,
and reviewer-set derivation can each change independently later without
this module changing. At this milestone the sandbox and toolchain digests
are seeded placeholder strings — opaque values this module hashes and
compares like any other bound field, never derives — pending the sandbox
and toolchain tickets that will produce their real values.

## Row covered

R-T-10 (`docs/prd/02-1-ticket-record.md` line 20; the `evidence_tuple`,
`approval_record`, and `reviewer_set` paragraphs of
`docs/prd/02-2-entities.md`; R-S5-1's preflight sentence in
`docs/prd/04-S5-cleanup-pass.md`): canonical serialisation and content
hashing for the plan and review evidence tuples; a plan tuple's
question-resolution and current-assumption set hashes changing on a new
answer or a superseding assumption; the plan/review reviewer-slot merge
rule; approval expiry invalidating a satisfying set and requiring fresh
quorum against the same subject; the review tuple's actual/effective
reviewer-set hashes distinct from the plan tuple's planned hash; S5
preflight refusing tuple creation on any missing or stale component; an S4
head advance with `base_sha` unchanged never invalidating the plan tuple;
and tuples never being updated in place.

## Owner decisions this ticket follows

- One hashing routine (`canonical.content_hash`), one quorum routine
  (`approvals.evaluate`), one slot-merge routine (`reviewer_sets.merge_slots`),
  one write path (`record.insert`) — `binding.py` calls each exactly once
  per row/decision and never reimplements any of them.
- `evidence_tuple` rows are one table for both kinds; a plan tuple's
  review-only columns and a review tuple's plan-only columns are always
  null, so the same "hash the full row" routine as
  `approvals.record_approval` produces a stable, recomputable hash for
  either kind without a kind-specific hashing path.
- `plan_tuple_currency` takes "current" state as an argument rather than
  deriving it, so a field this module does not bind (`head_sha` is not a
  `PlanComponents` field) can never appear in `changed` — the S4
  head-advance guarantee (criterion 8) falls out of the field list itself,
  not out of special-case logic.
- `preflight_review_tuple` treats plan-quorum expiry, missing quorum, and
  a wrong approval-set hash as three separate, individually testable
  refusals, all routed through the one call to `approvals.evaluate` against
  the plan tuple's own `content_hash` as subject.

## Decisions this brief did not already settle

- **`ticket.head_sha` cannot be updated in place under the current schema,
  and this ticket does not touch `runner/schema.py`.** `head_sha` (like
  `base_sha` and `target_base_sha`) has neither `mutable=True` nor a
  `once=` group, so the schema's own append-only trigger aborts any
  `record.update` naming it — confirmed directly: `record.update(conn,
  "ticket", id, head_sha=...)` raises `sqlite3.IntegrityError`. There is
  also no `updated_at` column pairing it, so the same call would fail on
  "no such column" even before reaching that trigger. Criterion 8's test
  therefore does not literally call `record.update` on `ticket.head_sha`;
  instead it records the two S4 task commits as two `stage_run` rows
  (`stage="S4"`, `run_kind="task"`) each carrying its resulting head in
  `outputs` — the same free-form place `check_result.observed_head_sha`
  already models a per-run head — and shows `plan_tuple_currency` is
  unaffected by them. This is not a workaround for the assertion itself:
  `PlanComponents` has no `head_sha` field at all, so no call this module
  makes could ever compare against one; the test demonstrates that
  guarantee by construction rather than by mutating a column the schema
  does not allow moved. If a future ticket wants `ticket.head_sha` itself
  to advance in place, that is a `runner/schema.py` change (adding
  `mutable=True` or a settle group) outside this ticket's scope.
- `set_hash` hashes `{"members": sorted(hashes)}`, mirroring
  `approvals.approval_set_hash`'s `{"approvals": sorted(...)}` shape, so
  every "hash of a set of hashes" in the record follows the same pattern
  rather than each call site inventing its own wrapper key.
- `create_plan_tuple` / `create_review_tuple` share one internal helper
  that (1) checks every named component field is non-`None`, raising
  `ValueError` before touching the database, then (2) builds the full
  `evidence_tuple` column set with absent columns null and hashes it,
  exactly mirroring `approvals.record_approval`'s row-then-hash shape.
- The planned `reviewer_set` row `preflight_review_tuple` checks against
  is looked up by `(ticket_id, kind="planned", content_hash)`, not by id —
  the plan tuple only binds the planned set's *hash*
  (`planned_reviewer_set_hash`), never a row id, since reviewer-set
  derivation and id-tracking belong to a sibling ticket. `ReviewComponents`,
  by contrast, does carry `actual_reviewer_set_id`/`effective_reviewer_set_id`
  per the ticket's own field list, so those two are looked up by id and
  cross-checked against their expected hash.
- The effective-set-is-the-merge check in preflight compares slots as a
  `{key: slot}` mapping rather than list equality, since slot order is not
  a stated invariant of R-T-10 — only slot content and the key set are.
- `PreflightRefused.reason` is a short, colon-joined identifier (e.g.
  `"stale_plan_tuple:base_sha,target_base_sha"`, `"missing_reviewer_set:actual"`)
  rather than an opaque code, so a test can assert on the specific failure
  without a second lookup table translating codes to meanings.

## Out of scope

The freshness boundaries that invalidate a tuple's target-base SHA and
`refresh-base` (T-A-14); waivers bound into the plan or review tuple
(T-A-32); the S6 publication-target and review-approval subject added to
the review tuple (T-A-34); actual reviewer-set derivation from CODEOWNERS
and the unresolved-owner block result (T-A-09); the real sandbox and
toolchain digests (T-A-18, T-A-19); `runner/schema.py`, `runner/db.py`,
`runner/approvals.py`, `runner/reviewer_sets.py`, `runner/canonical.py`,
`runner/gates.py`, `runner/state_table.py`, `runner/owners.py`, and
everything under `factory/`, all untouched by this ticket.
