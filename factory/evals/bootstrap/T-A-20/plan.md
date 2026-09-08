# T-A-20 plan

## Steps

| # | Step | Files touched | Proves |
|---|---|---|---|
| 1 | `service-tiers.yaml` gains `language`/`repositories`; `ticket-types.yaml` rewritten with all five types, `small_feature_max_points`, `eligible_services`, per-type `scrutiny_template`, and the 15-cell `provisional_tier` matrix; `sensitive-paths.yaml` gains `payments`/`secrets` globs. | `factory/config/service-tiers.yaml`, `factory/config/ticket-types.yaml`, `factory/config/sensitive-paths.yaml` | criteria 1, 2, 4, 7 |
| 2 | `exclusions.yaml`: the eight excluded surfaces, each with `path_globs` and `text_patterns`; `sensitive_path`'s globs come from `sensitive-paths.yaml`. | `factory/config/exclusions.yaml` | criteria 5, 15 |
| 3 | `runner/checks/exclusion.py`: `eligible`, `surfaces_in_text`, `surfaces_in_paths`, `decide_at_checks`, `apply_recorded_exclusion`. | `runner/checks/__init__.py`, `runner/checks/exclusion.py` | criteria 14, 15, 16, 17, 18, 19, 20 |
| 4 | `service_tier`/`ticket_type`/`tier_provisional` become one `once="tier_provisional"` group; `tier_final` and `scrutiny_requested` become `mutable=True`; `queue_item.resolved_role` added to the `resolved_at` once-group; `USER_VERSION` bumped. | `runner/schema.py`, `runner/db.py` | criteria 1, 3, 5, 7, 8, 11, 12 |
| 5 | `("intake", "s0_exclusion"): "rejected"` and its `close_reason`. | `runner/state_table.py` | criteria 5, 15 |
| 6 | `S0.py` rewritten: `_lookup`, `sensitivity_match`, `_render_scrutiny`, `governance_valid`, `run` (lookups, sensitive-path candidates, the exclusion gate, the scrutiny fill, in that order). | `runner/stages/S0.py` | criteria 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 14, 15 |
| 7 | `queue.act` gains `tier` and the eligibility governance check; `_override` takes `tier` and refuses a `pilot_excluded` ticket; `_resolve` writes `resolved_role`; `cli.py` gains `--tier`. | `runner/queue.py`, `runner/cli.py` | criteria 9, 10, 11, 12, 13, 20 |
| 8 | The allowlist extended for every new/changed mutability group. | `runner/tests/test_mutable_exceptions.py` | schema-change sweep |
| 9 | `test_s0.py`, `test_exclusion.py`, and their fixtures. | `runner/tests/test_s0.py`, `runner/tests/test_exclusion.py`, `runner/tests/fixtures/s0/owners_engineer2.yaml`, `runner/tests/fixtures/exclusion/*.yaml` | criteria 1-20 |
| 10 | Five collateral fixes: three seed the pilot-eligible service/type pair a real S0 now requires, two activate real governance for an `eligibility` `act` call. | `runner/tests/test_stub_stages.py`, `runner/tests/test_cli_skeleton.py`, `runner/tests/test_report.py`, `runner/tests/test_act.py`, `runner/tests/test_attention_bucket.py` | full-suite green |
| 11 | Manifest hashes recomputed for the three changed config files, an entry added for `exclusions.yaml`, the stale duplicated `content_hash:` line under `trust-profile.yaml` deleted. | `factory/manifest.yaml` | `test_manifest_hash.py` |
| 12 | This ticket's own brief and plan. | `docs/build/T-A-20/brief.md`, `docs/build/T-A-20/plan.md` | reviewed by the human, not a test |

## Test strategy

`test_s0.py` covers criteria 1 through 13. The 15-cell matrix
(criterion 1) and the two lookup-failure cases (criterion 2) call
`S0._lookup` directly against synthetic `service_tiers`/`ticket_types`
dicts, isolating the pure computation from the driver's side effects; a
third test runs the absent-service case through `run_stage` to pin the
full driver's `s0_reject`/structural-failure behaviour. Criteria 3 and 5
share one test, since a sensitive-path candidate both raises `tier_final`
and triggers the same exclusion gate. Criterion 4 calls
`sensitivity_match` directly with `authoritative=True` over a seeded diff
path list, since no live S5 driver exists to produce one. Criterion 6
builds two `Slot`s by hand (a `ticket_engineer` slot and a
`sensitive_path_owner` slot whose `distinct_from` names it) against a
sensitive-paths mapping that gives the matched path an owner distinct
from the shared pilot identity, and exercises `approvals.evaluate`
directly for both the distinct-identity (positive) and same-identity
(negative, `test_must_reject_...`) cases. Criteria 7 and 9 run the full
driver through `run_stage`; criterion 8 calls `S0.run` directly with an
overridden `ticket_types` dict (its `small_feature` template blanked),
since `run_stage` never passes such overrides itself. Criterion 10's
first three governance scenarios (expiry, unauthorised, wrong scope) go
through the full `queue.act` path against a ticket seeded with a real,
then deliberately broken, governance field; the fourth (invalid route)
calls `S0.governance_valid` directly against a deliberately broken tmp
trust-profile file, since only the committed profile can back a real
`act` call. Criteria 11 through 13 run the full driver, then `queue.act`,
asserting `resolved_role`, the override's written tier and provenance,
and the refusal on an S0-excluded ticket in turn.

`test_exclusion.py` covers criteria 5, 14 through 20. Criterion 14 and
its four negative matrix-dimension cases call `exclusion.eligible`
directly. Criteria 5 and 15 are one parametrized test over all eight
excluded surfaces, each seeded as a ticket title chosen to trip that
surface's own text pattern (or, for `sensitive_path`, its path glob),
run through the full driver via `run_stage`. Criteria 16 through 18 each
seed one `check_result` row (`check_name = "exclusion"`, `result =
"fail"`) on a `stage_run` of the stage under test (S1, S3, S5) and call
`apply_recorded_exclusion`, asserting the ticket lands `rejected` with
`close_reason = pilot_excluded`. Criterion 19 reads two seeded fixture
diffs (`accidental_removal.yaml`, `required_by_plan.yaml`) into
`decide_at_checks`, plus one test tying the removal event back to the
real `checks -> implementing` transition. Criterion 20 seeds an
S1-recorded exclusion, applies it, then asserts `queue.act`'s `override`
action refuses on the now-`pilot_excluded` ticket -- the same refusal
criterion 13 exercises against an S0-recorded one.

## Verification

`uv run pytest -q`
