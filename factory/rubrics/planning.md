---
name: spec-and-plan-rubric
kind: rubric
stage: planning
---

The spec-and-plan stage's rubric: one line per row and half, over the
plan's rejected-alternative, abstraction, archaeology, no-behaviour-change,
contracts, test-strategy, rollout and risk-map sections. A script half's
judgment is the sentence `runner.checks.plan_rubric` enforces
mechanically; a grader half marked `checklist: yes` stands in for a
calibrated grader until one exists, so a human applies its judgment
sentence directly against the checked plan. contracts_table's `contract_unit`
subject makes every touched unit's ten contract fields its own checklist
instance, one per unit the plan's `Contracts` table carries.

| line | row | half | subject | checklist | judgment |
|---|---|---|---|---|---|
| rejected_alternatives:script | rejected_alternatives | script | artefact | no | fail when a rejected alternative's `alternative` or `rejected_because` cell is empty, or the reason restates the alternative itself rather than naming a fact about cost, risk, or capability |
| rejected_alternatives:grader | rejected_alternatives | grader | artefact | yes | fail when a rejected alternative's stated reason restates the alternative itself rather than naming a fact about cost, risk, or capability |
| shared_abstraction:script | shared_abstraction | script | artefact | no | fail when a `new_shared_abstraction` row cites fewer than three existing near-duplicates and names no pre-abstraction risk, or a `widened_shared_function` row names no reason inlining was rejected |
| shared_abstraction:grader | shared_abstraction | grader | artefact | yes | fail when a shared-path abstraction cites fewer than three existing near-duplicates and names no pre-abstraction risk |
| archaeology_carry_over:script | archaeology_carry_over | script | artefact | no | fail when a brief history row classified `unexplained` or `contradictory` is not carried into the plan's archaeology table with the same classification, is missing a `characterization_task` naming a `Tasks` id, or is marked `alters_captured_behaviour` without being named in the plan's Unknowns |
| no_behaviour_change_tasks:script | no_behaviour_change_tasks | script | artefact | no | fail when a task flagged `no_behaviour_change` has no behaviour-preserving test-strategy row naming it; a plan mixing flagged and unflagged tasks is a blind spot naming the exception the human must approve |
| no_behaviour_change_tasks:grader | no_behaviour_change_tasks | grader | artefact | yes | fail when a task flagged `no_behaviour_change` describes a change that in fact alters behaviour |
| new_utility_search:script | new_utility_search | script | artefact | no | fail when a `new_utility` abstraction row records no existing candidate or no reason each was rejected |
| new_utility_search:grader | new_utility_search | grader | artefact | yes | fail when a recorded utility search names no context-index entry and no component-catalogue entry checked before proposing the new utility |
| contracts_table:script | contracts_table | script | contract_unit | no | fail when a contracts row's field cell does not parse to `unchanged`, `changed`, or `unknown`, a `changed` field carries no evidence and the ticket names no consequential question, or an `unknown` field is not recorded as an accepted blind spot |
| contracts_table:grader | contracts_table | grader | contract_unit | yes | fail when a contract field's declared state does not match the unit's actual behaviour before and after the change |
| test_strategy:script | test_strategy | script | artefact | no | fail when a test-strategy row's `size` or `action` is not one of the fixed values, a `change` or `remove` row names no `AC-n` criterion and no `no_behaviour_change` task, or a `large` row is planned with no registered end-to-end recipe |
| test_strategy:grader | test_strategy | grader | artefact | yes | fail when a planned test's stated `proves` value names no `AC-n` criterion and no specific assertion the test's action checks |
| rollout_section:script | rollout_section | script | artefact | no | fail when a `Flags` row omits any of its five cells, guardrail metrics exceed the section 8 limit or a row omits its `query` or `critical_threshold`, no `Kill trigger` row names rollback as the default response, or a `Log verification` row omits its pass or fail pattern |
| rollout_section:grader | rollout_section | grader | artefact | yes | fail when a rollout section's guardrail metrics carry no critical threshold, or its kill trigger names no rollback as the default response |
| risk_map:script | risk_map | script | artefact | no | fail when the risk map names fewer places than the section 8 floor, or fewer than one per computed candidate when the computed risk map names fewer candidates, or a named place carries no `why` |
| risk_map:grader | risk_map | grader | artefact | yes | fail when a risk-map section reuses boilerplate language with no candidate-specific reasoning |

The grader lines marked `checklist: yes` above join the context-gathering and
clarification stages' own checklist lines into the one bootstrap checklist
the runner assembles at the planning stage, standing in for a calibrated
grader until one exists.
