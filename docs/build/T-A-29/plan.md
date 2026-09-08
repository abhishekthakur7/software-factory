# T-A-29 plan

## Steps

| # | Step | Files touched | Proves |
|---|---|---|---|
| 1 | `red_route.classify`: `RecipeOutcome`/`CheckOutcome`/`Route`, the eligibility rule per red recipe, the cap check first. | `runner/checks/red_route.py` | criteria 14-17, 20 |
| 2 | `limits.yaml` gains `verification.max_attempts: 3`. | `factory/config/limits.yaml` | the escalation threshold reads from config, never a literal |
| 3 | `_revalidate`/`_record_stale_binding`: the `BEFORE_S4` freshness check, a `fail`/`stale_binding` run with no verification attempt, one `red_check` item unless one is already open. | `runner/stages/S4.py` | criterion 1 |
| 4 | The per-task loop: `_topological_order`, `_task_passed`, `_verification_attempt_number`, `_run_task`, `run_next`'s task branch; `run`/`build_handoff` grow an optional `task`. | `runner/stages/S4.py` | criteria 2, 5, 6, 7, 8 |
| 5 | Validation and control defects: `_validate_task` (approved-recipe check, then `recipes.run`), `_control_defect` (tag, `incident_observation`, escalate, one item), `_consecutive_infrastructure_failures`. | `runner/stages/S4.py` | criteria 3, 4 |
| 6 | Verification exhaustion: `_failure_history_payload`, `_escalate_verification_exhausted`, `_escalate`. | `runner/stages/S4.py` | criteria 9, 13 |
| 7 | Fix rounds: `_fix_round_routed`, `_check_fix_round_diff` (test-only refusal, base-test authorization, deviation recording), `_run_all_task_validations`/`_run_task_validations_only`, `_execute_fix_round`, `_run_fix_round`, the cap refusal. | `runner/stages/S4.py` | criteria 14 (S4-level), 18, 19, 20 (S4-level), 21-24 |
| 8 | `queue._resume` reads the escalation's cause; `_control_defect_remediated`; `escalation_context` gains `failure_history_artefact_id`. | `runner/queue.py` | criteria 11, 12, 13 |
| 9 | Fix-round paragraph. | `factory/agents/S4.md` | agent-facing behaviour matches the driver |
| 10 | Task-loop fixtures and tests: stale binding, three-in-a-row verification numbering, infra retry then escalation, unapproved recipe, fresh-invocation registration, green pass, plan-tuple reset, retained skip. | `runner/tests/test_s4_task_loop.py`, `runner/tests/fixtures/s4_task_loop/` | criteria 1-8 |
| 11 | Escalation fixtures and tests: verification exhaustion plus its artefact, both sandbox-integrity fixture cases, all three resume routes, a budget abort. | `runner/tests/test_s4_escalation.py`, `runner/tests/fixtures/s4_escalation/` | criteria 9-13 |
| 12 | `red_route` unit tests plus fix-round fixtures (authorized/unauthorized base-test change, test-only diff, out-of-scope diff, a broken post-hand-back validation, a budget-busting round, the cap) and their tests. | `runner/tests/test_s4_fix_round.py`, `runner/tests/fixtures/s4_fix_round/`, `factory/evals/agents/S4/fixtures/fix_round_*` | criteria 14-24 |
| 13 | Collateral: point three pre-existing S4 smoke tests at a one-task plan so a single `run_stage` call still finishes what they assert; add a real, dependency-free `Widget.java` where no agent invocation would otherwise supply one. | `runner/tests/test_s4_handback.py`, `runner/tests/test_state_table.py`, `runner/tests/test_stub_stages.py` | full-suite green under the new per-task loop |
| 14 | Manifest hashes refreshed, new fixture files added. | `factory/manifest.yaml` | `manifest.current_hash()` matches HEAD |
| 15 | This ticket's own brief and plan. | `docs/build/T-A-29/brief.md`, `docs/build/T-A-29/plan.md` | reviewed by the human, not a test |

## Test strategy

`test_s4_task_loop.py` and `test_s4_escalation.py` both drive the real
driver through `run_stage`, never `run_next` directly, so every test
also proves `stages.run_stage`'s own delegation and state-guard behaviour
along the way. A small, hand-written, dependency-free source tree
(`Widget.java`, no imports) stands in for the fixture project throughout,
compiling with an empty `vendor_classpath` -- real `fixture_compile`
runs, no `setup.materialise` pass needed. Verification failures are
driven with a genuinely broken `Widget.java` committed at the ticket's
base (so no agent edit is needed to keep the validation red across
retries); the "ok" and `empty_deviations` hand-back fixtures already on
main serve every case that just needs a structurally valid, deviation-
free hand-back. `red_route.classify` is tested with plain dataclass
literals, no ticket, no database, one test per named reason plus the
cap-first ordering. Fix-round criteria that need a routed ticket seed
the exact marker T-A-30's real S5 driver will leave (`check_result`
`fix_round_route` = `pass` on the ticket's latest S5 run) rather than
waiting on that driver to exist; a two-task plan stands in for "S5
already found this ticket's task loop complete" wherever a test needs
the ticket to stay `implementing` after one task's own pass. The three
resume routes in `test_s4_escalation.py` seed a `path_violation` or a
verification-exhausted run directly against `queue.act`, since those are
`queue.py` behaviours this ticket also owns, not S4's own; the remediated
path seeds a `control_disposition` and a `gate` `utility_run` by hand,
the smallest real satisfaction of `_control_defect_remediated`'s two-part
condition.

## Verification

`uv run pytest -q`
