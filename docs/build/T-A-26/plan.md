# T-A-26 plan

## Steps

| # | Step | Files touched | Proves |
|---|---|---|---|
| 1 | New `PLAN_TABLES` entries, `PLAN_SUBTABLES`, `Section.subsection(s)`, the closed value sets, and `contract_cell`. | `runner/artefacts.py` | every plan-rubric consumer downstream has one table/parser home |
| 2 | `_check_rollout`, `_check_scope_actions`, `_check_contract_cells`; the new empty-table-allowed set. | `runner/checks/artefact_structure.py` | the new tables are structurally required with exact columns |
| 3 | `plan_rubric.py`: one function per script rubric row, plus the `check` orchestrator and `test_mix_report`. | `runner/checks/plan_rubric.py` | criteria 1, 3, 4, 6, 7, 8, 9, 10, 12, 14, 15, 16, 17, 18, 19, 20, 22, 23 |
| 4 | `S3.py`: `plan_rubric.check` between the structure check and the size gate; `_record_plan_rubric_result`; `_contracts_exclusion_reason` and its `exclusion.apply_recorded_exclusion` call. | `runner/stages/S3.py` | the check lands in order; the public-contract exclusion route fires |
| 5 | `risk_map`'s `--since` -> `--since-as-filter` fix. | `factory/scripts/checks/risk_map` | criterion 25 (a stray old commit no longer zeroes a later candidate's real commit count) |
| 6 | `limits.yaml`: `risk_map.named_places`, `guardrail_metrics.max`, `test_mix`. | `factory/config/limits.yaml` | the rubric's own numbers come from config, not a literal |
| 7 | The real `S3.md` rubric table and its closing paragraph. | `factory/rubrics/S3.md` | `rubrics.load` accepts it; every row/half the ticket names is present |
| 8 | Agent/skill descriptions of the new tables and cell formats. | `factory/agents/S3.md`, `factory/skills/S3.md` | short, matches the fixed columns |
| 9 | Fourteen `plan_rubric_ok`/`plan_rubric_reject` fixture pairs plus `eval.yaml`; six seeded `human_verdict` scenarios. | `factory/evals/rubrics/S3/` | one fixture pair per script rule; one seeded scenario per checklist grader row this ticket owns |
| 10 | `churn_window_cases` (top-decile, no-clear-owner, outside-window) plus a seeded `human_verdict/R-S3-11.yaml`. | `factory/evals/scripts/checks/risk_map/` | criteria 25-29 |
| 11 | Scripted edits: the new tables added to every S3 agent/handoff-ready plan fixture; the `ok` fixture gets real rows clearing every script rule with zero findings. | `factory/evals/agents/S3/fixtures/*/out/plan.md`, `factory/evals/scripts/tools/handoff_ready/fixtures/*/plan.md` | `test_ok_plan_fixture_passes_the_structure_check`, the driver-run tests, still green |
| 12 | `test_s3_rubric.py`: the fourteen eval-fixture pairs, isolated per-clause assertions for the criteria a pair alone can't isolate, the rubric file's own shape, the seeded human_verdict fixtures, and one real `run_stage` proving check order and the exclusion route. | `runner/tests/test_s3_rubric.py` | criteria 1-24 and the two design decisions |
| 13 | `test_risk_map.py`: the churn-window repository, the window-exclusion and named-reason assertions, `risk_map_places`'s floor logic, the seeded human_verdict fixture. | `runner/tests/test_risk_map.py` | criteria 25-29 |
| 14 | Manifest hashes refreshed after every `factory/` change, committed before each test run that goes through a driver. | `factory/manifest.yaml` | `test_manifest_hash.py`; every driver-run test |
| 15 | This ticket's own brief and plan. | `docs/build/T-A-26/brief.md`, `docs/build/T-A-26/plan.md` | reviewed by the human, not a test |

## Test strategy

`test_s3_rubric.py` drives `plan_rubric.check` two ways: directly against
the fourteen eval fixtures (one conforming/defective pair per script
rule), and through eleven hand-built inline-text assertions for the
criteria a single ok/reject pair can't isolate on its own -- the
`widened_shared_function`/`new_utility` abstraction clauses, the
characterization-task and altered-behaviour archaeology clauses split
from the classification-carry clause the fixture pair already covers, the
no-behaviour-change mixing exception landing as `blind_spot` not `fail`,
the consequential-question exception and the `unknown`-field blind spot
on `Contracts`, the size-to-recipe mapping, a `change` row citing neither
authority, a `large` row with no registered end-to-end recipe, guardrail
metrics over the section 8 limit, and a `Log verification` row missing a
pattern. The rubric file itself is checked through `rubrics.load`: every
grader line the ticket dictates a judgment sentence for is marked a
bootstrap-checklist line carrying that sentence verbatim, `R-S3-4` carries
a script line with no grader half, `R-S3-7`'s grader names
`contract_unit` as its subject, every row has a script line, and the six
seeded `human_verdict` fixtures name their rubric line and a fail verdict.
One real `run_stage("S3")` call, against a ticket with a real worktree and
manifest pin, proves the `plan_rubric` check_result lands strictly
between `artefact_structure` and `size_gate` in call order, and a second
proves a public unit's `unknown` compatibility field moves the ticket to
`rejected` with `close_reason = pilot_excluded` through the same route
`exclusion.apply_recorded_exclusion` gives S1.

`test_risk_map.py` builds one repository with four files, each set up to
hit exactly one named-entry rule at once: a single-author file with the
highest churn-times-size score (top decile), a three-author file no one
holds 40 percent of (no clear owner), a file whose one commit sits
outside the twelve-month window -- proving `--since-as-filter` excludes
it from the count entirely rather than merely from the top-decile
ranking, which plain `--since` does not -- and a quiet file named for
neither reason. The expected JSON is pinned as a seeded fixture, read
through a `churn_window_cases` key kept separate from the `cases` key
`test_s3_structure.py` already parametrizes over its own smaller,
unrelated repository, so extending this eval file for the new scenario
never touches that test. `risk_map_places`'s floor logic (the configured
named-places count, or the computed candidate count when that is fewer)
and its `why`-emptiness check are driven directly, and the seeded
`human_verdict/R-S3-11.yaml` fixture is asserted to name its rubric line
and a fail verdict.

## Deviations and design decisions the ticket left open

- **`risk_map`'s `--since` replaced with `--since-as-filter`.** Building
  the churn-window test repository surfaced a real defect: `git log
  --since=<date>` stops walking a branch's history at the first commit
  older than the cutoff, so one old-dated commit anywhere earlier in the
  branch (a rebase, an import, a preserved original author date) silently
  zeroes the commit count for every candidate whose real commits sit
  behind it in the chain, even though each individually falls inside the
  window. `--since-as-filter` (git >= 2.35) filters the whole walk
  instead. Confirmed against the existing `churn` eval case: identical
  output, since it has no out-of-order commit to expose the bug.
- **R-S3-7's grader judgment sentence.** The ticket names verbatim grader
  sentences for R-S3-2, R-S3-3, R-S3-5, R-S3-6, R-S3-9, R-S3-10, R-S3-11
  but not R-S3-7; this ticket writes one consistent with the row's own
  PRD text ("a changed field is a named decision... unknown is a blind
  spot explicitly accepted at S3") and the `Semantic-contract checklist`
  section every touched unit already carries.
  Judgment: "fail when a contract field's declared state does not match
  the unit's actual behaviour before and after the change."
- **The public-unit exclusion check reads "public" from either the
  `Contracts.kind` cell or the free-form `source_declaration` text**,
  since the table's `kind` column values (function, module, endpoint,
  event, serialized shape) carry no dedicated visibility column of their
  own, and the design decision names both cells as acceptable evidence.
- **`risk_map_places`'s floor**: the configured `risk_map.named_places`,
  or the risk map's own computed named-candidate count when that is
  fewer -- read literally from "at least N rows, or one per candidate
  when the attached risk map names fewer."
- **`test_mix_report`** is a separate function from `check`'s finding
  list, called by the driver only for the `plan_rubric` check_result's
  summary text, since the ticket says the mix is "reported... as
  information, never a fail" -- never a `Finding`, which only carries
  `fail`/`blind_spot`.
- **`factory/evals/scripts/checks/size_gate/fixtures/*/plan.md`** were
  left untouched: each carries only a `Size` section, and the script
  reads only that section by name, never parsing the file as a whole
  plan, so there is no new table for it to have "nothing to say" about.
- **`docs/build/T-A-26/`** was written after implementation, not before,
  given the ticket's size; its content reflects what was actually built.

## Verification

`uv run pytest -q`
