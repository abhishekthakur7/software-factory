# 14. Rubric row and failure-mode keys

Part of the [Software Factory PRD](prd.md). The index holds the version, the reading rules, and the map from section numbers to files.

The factory tree names each rubric row by what it judges, never by a requirement id, because the code and everything a user sees carry no document ids (`AGENTS.md`, Names). A rubric line is `<row key>:script` or `<row key>:grader`, stored under that name in `human_verdict.rubric_line_id` and in the check results. These tables are the only place the two vocabularies meet; a retired id in section 13 resolves to its carrying row first.

| Row key | Rubric file | Requirement |
|---|---|---|
| `ticket_summary` | `rubrics/context_gathering.md` | R-S1-2 |
| `impact_evidence` | `rubrics/context_gathering.md` | R-S1-3 |
| `history_classification` | `rubrics/context_gathering.md` | R-S1-4 |
| `reference_grounding` | `rubrics/context_gathering.md` | R-S1-6 |
| `context_index_use` | `rubrics/context_gathering.md` | R-S1-7 |
| `final_tier` | `rubrics/context_gathering.md` | R-S1-8 |
| `impact_tiering` | `rubrics/context_gathering.md` | R-S1-11 |
| `criterion_restatement` | `rubrics/clarification.md` | R-S2-1 |
| `given_when_then_example` | `rubrics/clarification.md` | R-S2-2 |
| `agreement_check` | `rubrics/clarification.md` | R-S2-3 |
| `forced_categories` | `rubrics/clarification.md` | R-S2-4 |
| `question_reasoning` | `rubrics/clarification.md` | R-S2-5 |
| `question_ranking` | `rubrics/clarification.md` | R-S2-6 |
| `default_option` | `rubrics/clarification.md` | R-S2-7 |
| `question_flags` | `rubrics/clarification.md` | R-S2-8 |
| `follow_up_rounds` | `rubrics/clarification.md` | R-S2-9 |
| `vertical_slice_size` | `rubrics/clarification.md` | R-S2-10 |
| `default_accepted_assumption` | `rubrics/clarification.md` | R-S2-11 |
| `pass_completeness` | `rubrics/clarification.md` | R-S2-12 |
| `self_contained_question` | `rubrics/clarification.md` | R-S2-14 |
| `rejected_alternatives` | `rubrics/planning.md` | R-S3-2 |
| `shared_abstraction` | `rubrics/planning.md` | R-S3-3 |
| `archaeology_carry_over` | `rubrics/planning.md` | R-S3-4 |
| `no_behaviour_change_tasks` | `rubrics/planning.md` | R-S3-5 |
| `new_utility_search` | `rubrics/planning.md` | R-S3-6 |
| `contracts_table` | `rubrics/planning.md` | R-S3-7 |
| `test_strategy` | `rubrics/planning.md` | R-S3-9 |
| `rollout_section` | `rubrics/planning.md` | R-S3-10 |
| `risk_map` | `rubrics/planning.md` | R-S3-11 |
| `diff_size` | `rubrics/checks.md` | R-S3-12 |
| `scope_confinement` | `rubrics/checks.md` | R-S5-4 |
| `declaration_contracts` | `rubrics/checks.md` | R-S5-5 |
| `contract_evidence` | `rubrics/checks.md` | R-S5-5, evidence half |
| `regression_only` | `rubrics/checks.md` | R-S5-10 |

The stage files of section 4 keep naming rubric lines by requirement id; read the row key off this table when looking for the line in the tree, a verdict, or a check result.

## Failure-mode keys

The charter's failure-mode table keeps its FM ids. The catalogue the factory tree carries (`factory/catalogue/failure-modes.md`), every `tag.fm_id`, every eval's `failure_modes` list and the runner's own constants use the key.

| Key | Charter id |
|---|---|
| `unjustified_abstraction` | FM-01 |
| `load_bearing_hack` | FM-02 |
| `pattern_ignored` | FM-03 |
| `tech_debt_mixing` | FM-04 |
| `scope_creep` | FM-05 |
| `jumps_to_implementation` | FM-06 |
| `question_noise` | FM-07 |
| `missing_scenarios` | FM-08 |
| `parallel_fatigue` | FM-09 |
| `unreviewable_diff` | FM-10 |
| `filler_tests` | FM-11 |
| `filler_comments` | FM-12 |
| `missing_comments` | FM-13 |
| `unknown_impact` | FM-14 |
| `contract_drift` | FM-15 |
| `false_rigor` | FM-16 |
| `memory_rot` | FM-17 |
| `agent_only_review` | FM-18 |
| `slow_failure` | FM-19 |
| `hallucinated_dependency` | FM-20 |
| `state_loss` | FM-21 |
| `loop_drift` | FM-22 |
| `unsafe_execution` | FM-23 |
| `data_boundary_breach` | FM-24 |
| `stale_approval` | FM-25 |
