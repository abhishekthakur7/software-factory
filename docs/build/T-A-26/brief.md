# T-A-26 brief: S3 plan rubric lines and the risk-map line

## What this delivers

`factory/rubrics/S3.md` stops being a stub: it carries the real rubric
table for R-S3-2, R-S3-3, R-S3-4, R-S3-5, R-S3-6, R-S3-7, R-S3-9, R-S3-10,
R-S3-11, one script line per row and a grader line wherever the ticket
dictates a judgment sentence. `runner/checks/plan_rubric.py` (new) is the
script half's implementation: `check(plan_text, *, brief_text,
criteria_text, catalogue, project_recipes, questions, limits,
risk_map_candidate_count) -> list[Finding]`, one function per rubric row's
behaviour, each `Finding` a `fail` (blocks the plan) or a `blind_spot`
(recorded, never blocking by itself). `runner/stages/S3.py` runs it
between the structure check and the size gate, records one `plan_rubric`
check_result, and applies the same pilot-exclusion route S1 uses for a
discovered excluded scope when a `Contracts` row's `compatibility` field
is `unknown` on a public unit.

The plan's new tables and cell formats live in one home,
`runner/artefacts.py`: `PLAN_TABLES` gains `Risk map`, `Alternatives`,
`Archaeology and characterization tests`, `Abstraction and separate
debt`; `PLAN_SUBTABLES["Rollout"]` names the five `### ` subsections
(`Flags`, `Ramp`, `Guardrails`, `Kill trigger`, `Log verification`) a
new `Section.subsection`/`subsections` pair reads; `SCOPE_ACTIONS`,
`CONTRACT_FIELDS`, `CONTRACT_STATES`, `ABSTRACTION_KINDS`, `TEST_SIZES`,
`TEST_ACTIONS` are the closed value sets; `contract_cell(cell) ->
(state, evidence)` parses a `<state>` or `<state>: <evidence>` cell.
`runner/checks/artefact_structure.py` gained the matching structural
rules: the `Rollout` subsections (header-only allowed except `Kill
trigger`), `Scope and discretion.action` in the closed set, and every
`Contracts` field cell parsing to a state.

- `runner/artefacts.py` -- the table/subtable additions above, plus
  `Section.subsections()`/`subsection(title)` (mirrors the top-level
  `## ` parse at `### ` depth) and `contract_cell`.
- `runner/checks/artefact_structure.py` -- `_check_rollout`,
  `_check_scope_actions`, `_check_contract_cells`; `Alternatives`,
  `Archaeology and characterization tests`, `Abstraction and separate
  debt` join `Dependencies` in the empty-table-allowed set; `Risk map`
  does not, so it always needs at least one row.
- `runner/checks/plan_rubric.py` (new) -- `rejected_alternative_reason`,
  `shared_abstraction_cited`, `archaeology_carried`,
  `no_behaviour_change_isolated`, `contracts_declared`,
  `test_strategy_typed`, `test_mix_report` (an information line, never a
  finding), `rollout_structured`, `risk_map_places`, and the `check`
  orchestrator.
- `runner/stages/S3.py` -- one added step: `plan_rubric.check` runs
  against the version the structure check just cleared, using the
  brief/criteria text, the recipe catalogue, `project.yaml`'s recipe
  ids, the ticket's question rows (for the `consequential`-question
  exception), `limits.yaml`, and the risk-map artefact's own named-
  candidate count; `_record_plan_rubric_result` writes one `plan_rubric`
  check_result (`fail`/`blind_spot`/`pass`); `_contracts_exclusion_reason`
  scans the same version for an `unknown` `compatibility` field on a
  public unit and, when found, records an `exclusion` check_result and
  calls `exclusion.apply_recorded_exclusion` before the rubric's own
  fail/pass verdict is even consulted.
- `factory/scripts/checks/risk_map` -- one-line fix: `--since` became
  `--since-as-filter` (see "Decisions this brief did not already
  settle").
- `factory/config/limits.yaml` -- `risk_map.named_places: 3`,
  `guardrail_metrics.max: 12`, `test_mix` (80/15/5).
- `factory/rubrics/S3.md`, `factory/agents/S3.md`, `factory/skills/S3.md`
  -- the real rubric table and the agent/skill descriptions of the new
  tables and cell formats.
- `factory/evals/rubrics/S3/` -- fourteen `plan_rubric_ok`/
  `plan_rubric_reject` fixture pairs (one per script rule) plus six
  seeded `human_verdict/R-S3-N.yaml` scenarios, mirroring S1's pattern.
- `factory/evals/scripts/checks/risk_map/` -- a `churn_window_cases` key
  (kept separate from the `cases` key `test_s3_structure.py` already
  parametrizes over its own smaller repo) covering top-decile
  churn-times-size, no clear owner, and a commit outside the window, plus
  a seeded `human_verdict/R-S3-11.yaml`.
- `factory/evals/agents/S3/fixtures/*/out/plan.md` (all eleven that carry
  one), `factory/evals/scripts/tools/handoff_ready/fixtures/*/plan.md` --
  scripted edits adding the new tables (header-only where the fixture has
  nothing to say; the `ok` fixture carries real rows, including a `Kill
  trigger` row and `Contracts` cells in both `state` and `state: evidence`
  form, so it clears `plan_rubric.check` with zero findings).
- `runner/tests/test_s3_rubric.py` (new), `runner/tests/test_risk_map.py`
  (new); `runner/tests/test_s3_structure.py` untouched beyond what the
  new fixtures already exercise through its existing parametrized walks.
- `factory/manifest.yaml` refreshed after every `factory/` change.

## Rows covered

R-S3-2, R-S3-3, R-S3-4, R-S3-5, R-S3-6, R-S3-7, R-S3-9, R-S3-10, R-S3-11
(`docs/prd/04-S3-spec-and-plan.md`); the plan-table, test-mix, guardrail,
and risk-map paragraphs of `docs/prd/08-configuration.md`.

## Owner decisions this ticket follows

Tables, not prose, for every section a script reads, with columns coming
from `artefacts.py` only; an `unknown` contract field is an explicitly
accepted blind spot that can trigger the pilot exclusion, via the same
route S1 uses; `plan_rubric.check` takes text and plain data, never a
connection; rubric line ids are `<row>:<half>` with the check's rule
names chosen for behaviour, not row id; KISS/YAGNI, lax initially (the
test-mix target is reported, never enforced).

## Out of scope

The bootstrap checklist, human verdicts, the plan tuple and its approval
(T-A-27); the S4 hand-off/hand-back (T-A-28); the S5 check order's own
driver (a later wave); `runner/stages/S3.py`'s reviewer-set derivation
(T-A-27, the file's other half).
