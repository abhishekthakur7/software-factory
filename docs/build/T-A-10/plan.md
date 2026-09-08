# T-A-10 plan

## Steps

| # | Step | Files touched | Proves |
|---|---|---|---|
| 1 | `set_hash`: canonical hash of the sorted canonical hashes of an iterable of mappings. | `runner/binding.py` | `test_binding.py`'s set-hash tests (criterion 2) |
| 2 | `PlanComponents` (19 fields, one-to-one onto the plan `evidence_tuple` columns) and `ReviewComponents` (the review-only fields plus the seven common hashes), both frozen dataclasses. | `runner/binding.py` | `test_binding.py`'s field-shape tests (criteria 9, 10) |
| 3 | `create_plan_tuple` / `create_review_tuple`: a shared internal helper hashes the full `evidence_tuple` column set (absent columns null, `id`/`content_hash`/`created_at` excluded) and inserts through `record.insert`; every component field is required, checked before the write. | `runner/binding.py` | `test_binding.py`'s row-shape, required-field, and content-hash tests (criteria 1, 9, 10, 11) |
| 4 | `plan_tuple_currency`: compares a stored plan tuple's bound fields against a caller-supplied `PlanComponents`, naming every changed field; never touches the row. | `runner/binding.py` | `test_binding.py`'s currency tests (criteria 2, 5, 8, 11) |
| 5 | `PreflightRefused` and `preflight_review_tuple`: plan-tuple existence and currency, plan quorum via `approvals.evaluate` against the plan tuple's own `content_hash`, actual/effective reviewer-set existence and the `merge_slots` equality check, target-base freshness, head/diff presence, then `create_review_tuple` in one transaction. | `runner/binding.py` | `test_preflight.py` (criterion 6); `test_binding.py`'s quorum/expiry/reviewer-set tests (criteria 3, 4, 5, 7) |
| 6 | Seeded plan- and review-component fixtures: one complete set each, plus the named variants the currency and set-hash tests swap in. | `runner/tests/fixtures/binding/plan_components.yaml`, `runner/tests/fixtures/binding/review_components.yaml` | both test files |
| 7 | This ticket's own brief and plan. | `docs/build/T-A-10/brief.md`, `docs/build/T-A-10/plan.md` | reviewed by the human, not a test |

## Test strategy

`test_binding.py` opens its own `tmp_path` database per test, the same
convention as the rest of the record/schema suite, and loads plan/review
component fixtures from `runner/tests/fixtures/binding/`. For criterion 1
it asserts only what `test_canonical.py` does not already pin: a stored
tuple's `content_hash` equals `canonical.content_hash` recomputed over its
own row with `id`/`content_hash`/`created_at` excluded, and two tuples
differing only in `created_at` share a hash. Criterion 2 swaps one field at
a time (`question_resolution_set_hash`, then `current_assumption_set_hash`)
via `dataclasses.replace` and asserts both the named field and the tuple's
own `content_hash` change. Criterion 5 creates two review tuples differing
only in `effective_reviewer_set_hash` and asserts their `content_hash`
differs while an unrelated plan tuple's does not move. Criterion 8 seeds a
ticket and a plan tuple, then asserts currency holds under an unrelated
change and fails under a changed `base_sha` — see the note below on why the
test does not literally call `record.update` on `ticket.head_sha`.
Criteria 3, 4, 7 exercise `approvals.evaluate` and `reviewer_sets.merge_slots`
through the binding layer (a real plan/review tuple's `content_hash` as
subject) rather than re-testing those modules' own unit behaviour, which
`test_approval_records.py` and `test_reviewer_sets.py` already pin.

`test_preflight.py` covers criterion 6: one success test that reads the
created review tuple back, and one `test_must_reject_...` per refusal —
missing plan tuple, stale plan tuple, no quorum, expired quorum, wrong
approval-set hash, missing reviewer set (planned, actual, and effective),
effective set not the merge, stale target base, and missing head or diff.

## Verification

`uv run pytest -q` — 331 tests pass (301 before this ticket, plus 16 in
`test_binding.py` and 14 in `test_preflight.py`).

## Note on criterion 8's test

`ticket.head_sha` has no mutable/settle-once declaration in
`runner/schema.py`, so a raw `record.update` naming it is refused by the
schema's own append-only trigger (confirmed directly against a real
connection). Since this ticket does not touch `runner/schema.py`,
`test_plan_tuple_currency_ignores_head_advance_but_catches_a_changed_base_sha`
represents the two S4 task commits as `stage_run` rows carrying their
resulting head in `outputs` instead of mutating `ticket.head_sha` in
place, and shows `plan_tuple_currency` is unaffected by them — the
guarantee criterion 8 states holds by construction, since `PlanComponents`
has no `head_sha` field for any stored value to disagree with. See the
brief for the full reasoning.
