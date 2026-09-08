# T-A-07 plan

## Steps

| # | Step | Files touched | Proves |
|---|---|---|---|
| 1 | Seed the trust profile: taxonomy and join/default-deny rules, admitted scopes, secret rules and their bound `rule_set_hash`, one sanitizer pair, the five routes with every required field, evidence references, and the two approval slots; `both_trust_roles_identity` unchanged. | `factory/config/trust-profile.yaml` | `test_trust_profile.py`'s committed-fixture and per-route tests (criteria 1, 18); `test_owners.py`'s rewritten pinned test |
| 2 | `load_trust_profile`, `TrustProfileError`, and every dataclass the profile parses into; `profile_hash`, `rule_set_hash`, `trust_approval_subject`. | `runner/trust_profile.py` | `test_trust_profile.py`'s must-reject field tests (criterion 1); hash tests (criterion 6) |
| 3 | `join`, `resolve_sanitizer`, `approval_slots`, `export_permitted`, `retention_expired`. | `runner/trust_profile.py` | `test_trust_profile.py` (criteria 7, 15, 16, 17); `test_guard.py`'s class-join test (criterion 3) |
| 4 | `governance.propose`: metadata-only `Proposal`, no connection and no payload parameter. | `runner/governance.py` | `test_guard.py`'s structural AST tests and `Proposal` field test (criterion 2) |
| 5 | `governance.decide`: one `approval_record` per acting approver through `approvals.record_approval`, mandatory expiry. | `runner/governance.py` | `test_guard.py` (criteria 5, 19) |
| 6 | `governance.activation`: `approvals.evaluate` over the profile's own slots, `both_trust_roles_identity` as the separation exemption. | `runner/governance.py` | `test_guard.py` (criteria 4, 15) |
| 7 | `guard.Operation`, `guard.Decision`, `guard.CROSSINGS`, `GuardUnavailable`, `GuardRefused`. | `runner/guard.py` | `test_guard.py`'s fixture-driven tests across every crossing |
| 8 | `guard.decide`: the fail-closed decision order ending in one `guard_decision` row per call, whatever the outcome. | `runner/guard.py` | `test_guard.py` (criteria 3, 9, 10, 11, 12, 13, 14, 20) |
| 9 | `guard.pass_through`: re-reads the persisted row; refuses a hand-built, denied, wrong-crossing, or non-`Decision` argument. | `runner/guard.py` | `test_guard.py` (criterion 8) |
| 10 | Seed `runner/tests/fixtures/trust_profile/` (a self-contained profile and owners copy) and `runner/tests/fixtures/guard/` (the same pair, plus one named operation per crossing and per special scenario). | `runner/tests/fixtures/trust_profile/`, `runner/tests/fixtures/guard/` | every test below loads these rather than building fixtures inline |
| 11 | `test_trust_profile.py`. | `runner/tests/test_trust_profile.py` | criteria 1, 6, 7, 15, 16, 17, 18 |
| 12 | `test_guard.py`. | `runner/tests/test_guard.py` | criteria 2, 3, 4, 5, 8, 9, 10, 11, 12, 13, 14, 19, 20 |
| 13 | Rewrite `test_owners.py`'s pinned single-key test to the new invariant. | `runner/tests/test_owners.py` | keeps the pin without asserting a shape this ticket deliberately outgrows |
| 14 | Recompute the manifest entry for the changed trust profile. | `factory/manifest.yaml` | manifest stays a true content index |
| 15 | This ticket's own brief and plan. | `docs/build/T-A-07/brief.md`, `docs/build/T-A-07/plan.md` | reviewed by the human, not a test |

## Test strategy

`test_trust_profile.py` loads the seeded fixture profile
(`runner/tests/fixtures/trust_profile/profile.yaml`) for its structural and
positive-path assertions, then mutates a deep copy field-by-field
(`_without`) for the criterion-1 must-reject sweep — parametrized over
every field the ticket names across the top level, `admitted_scopes`,
`evidence`, `approval_slots`, and one representative route's full field
set, so a validator that skips checking any single one of them fails a
named test case. Criterion 6 copies the fixture profile and owners file
into `tmp_path`, mutates the owners copy, and shows both the raw subject
hash and a real `governance.activation` result move together. Criteria 7,
15, 16, and 17 call `resolve_sanitizer`, `export_permitted`, and
`retention_expired` directly against the loaded fixture profile, each with
a positive and a negative case.

`test_guard.py` never inserts an `approval_record` by hand: every test
needing an active profile calls `governance.propose`/`governance.decide`
against a tmp copy of the fixture profile and owners file first. Criterion
2's AST-based tests parse `runner/governance.py` itself to confirm it
imports none of `runner.guard`, `runner.artefact_registry`, `runner.fs`, or
`runner.stages`, calls no raw `.insert(...)`, and that `propose` takes
neither a connection nor a payload parameter — a structural guarantee no
runtime call could demonstrate as convincingly. `runner/tests/fixtures/
guard/operations.yaml` seeds one named `Operation` per crossing plus five
special scenarios (an absent route, a secret hit inside a plain crossing
and inside an export, an injected widen-instruction, and the digest's
full-text payload); criterion 9 parametrizes over every scenario to prove
`decide` writes exactly one row each time, and criterion 8 parametrizes
`pass_through` over every crossing, plus dedicated must-reject tests for a
mismatched crossing, a denied decision, a hand-built decision never
persisted, and a raw payload in place of a `Decision`.

## Verification

`uv run pytest -q` — 383 tests pass (301 before this ticket, plus 41 in
`test_guard.py` and 41 in `test_trust_profile.py`).
