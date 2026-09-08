# T-A-25 plan

## Steps

| # | Step | Files touched | Proves |
|---|---|---|---|
| 1 | `Section.table_header()` added; `PLAN_TABLES["Scope"]` renamed to `PLAN_TABLES["Scope and discretion"]` to match the real section title. | `runner/artefacts.py` | the generic table check can find and validate every plan table, including one with zero rows |
| 2 | `artefact_structure.check(kind, text, ...)`: fixed sections in order and non-empty (pending-exempt), fixed table columns per kind, plan-only ceilings/first-page order/recipe typing/traceability/readiness rules. | `runner/checks/artefact_structure.py` | criteria 1-4, 9-21 |
| 3 | `size_gate`: plan-estimate mode and diff mode, both against the tier threshold and the plan's own justification. | `factory/scripts/checks/size_gate` | criteria 5-8 |
| 4 | `risk_map`: per-candidate commits, top-author share, size, and the named/top-decile rule. | `factory/scripts/checks/risk_map` | attaches as an S3 input; computation depth is a later ticket's |
| 5 | `handoff_ready`: the seven readiness conditions, each read from exactly one source, never agent prose. | `factory/scripts/tools/handoff_ready` | criterion 19, and feeds criteria 20-24 |
| 6 | `project.yaml` gains `lockfiles` and a real `generated_paths` entry. | `factory/config/project.yaml` | `size_gate`'s diff-mode exclusion |
| 7 | `S3.py` rewritten: risk map, agent invocation, plan parse, front-matter injection, `handoff_ready`, structure check, size gate, registration. | `runner/stages/S3.py` | the seven-step order; criteria 19, 22, 23 through a real run |
| 8 | Eleven plan-content fixtures (one ok, ten deliberate defects) plus matching `eval.yaml` cases. | `factory/evals/agents/S3/fixtures/*/out/plan.md`, `factory/evals/agents/S3/eval.yaml` | the structure check's own rules, one fixture per rule |
| 9 | Size-gate and risk-map eval fixtures. | `factory/evals/scripts/checks/size_gate/`, `factory/evals/scripts/checks/risk_map/` | criteria 5-8; the risk-map script's attachment |
| 10 | Handoff-ready eval fixtures: all-pass, all-pending, and a blind-spot case. | `factory/evals/scripts/tools/handoff_ready/` | criterion 19 across every status a condition can take |
| 11 | Shared criteria fixture the plan fixtures cite. | `runner/tests/fixtures/s3/criteria.md` | traceability tests have a real criteria artefact to check against |
| 12 | `test_s3_structure.py`: the structure check driven directly and through eval fixtures, plus two full-driver integration tests. | `runner/tests/test_s3_structure.py` | criteria 1-4, 9-24 |
| 13 | `test_size_gate.py`: the four size-gate criteria through its eval fixtures. | `runner/tests/test_size_gate.py` | criteria 5-8 |
| 14 | Two collateral fixes: both built a stage-walk on the old S3 stub's trivial pass; both now set up a worktree, a real manifest pin, and a brief/criteria before calling the real driver. | `runner/tests/test_report.py`, `runner/tests/test_stub_stages.py` | full-suite green |
| 15 | Manifest hashes recomputed for every changed file, entries added for every new one. | `factory/manifest.yaml` | `test_manifest_hash.py` |
| 16 | This ticket's own brief and plan. | `docs/build/T-A-25/brief.md`, `docs/build/T-A-25/plan.md` | reviewed by the human, not a test |

## Test strategy

`test_s3_structure.py` covers the structure check two ways. Section- and
kind-generality (missing sections for `brief`/`criteria`/`plan`, the
`packet` placeholder, the pending-answer exemption) are hand-built small
texts, since they need no full plan. Every plan-only rule (table columns,
both ceilings, first-page order, typed recipes, traceability, unflagged
tasks) is one data-driven test parametrized over
`factory/evals/agents/S3/eval.yaml`'s `plan_structural_reject` cases,
asserting the named rule fires and nothing else is needed to prove it;
the matching `plan_structural_ok` case proves the same "ok" fixture used
throughout carries none of them. The readiness-specific rules (a missing
table, a pending row, a `blind_spot` row with no waiver) are hand-edited
copies of the "ok" fixture's own readiness table, changing exactly one
cell. `handoff_ready` itself is driven through its own eval fixtures
(all-pass, all-pending, one blind-spot case with a waiver), asserting
every one of the seven condition rows lands the expected status and
carries a real hash. The two rules only a live run can pin --
`handoff_ready` running strictly after the agent's own child invocation,
and the registered plan's hash being exactly the file it produced with
every readiness hash bound to its own source artefact -- go through a
real `run_stage("S3")` call against a ticket with a real worktree,
manifest pin, and brief/criteria, served by the committed "ok" fixture
through `FIXTURE_ADAPTER_OUT_DIR`; ordering is proven by the raw child
output still holding the fixture's placeholder hashes while the
registered version holds the real ones `handoff_ready` computed on top of
it, not by comparing ids across the `artefact`/`stage_run` tables (an
earlier draft tried that; two independent autoincrement sequences carry
no ordering guarantee against each other).

`test_size_gate.py` drives the script through its own eval fixtures
(`over_threshold`, `justified`), each carrying both a `plan.md` (for
plan-estimate mode) and a `diff.txt` (for diff mode) so one fixture pair
serves all four criteria; a dedicated test confirms the diff fixture's
lockfile hunk (`uv.lock`) never counts toward the total, and another
confirms plan mode reads the `Size` table's `estimated_lines` rather than
computing anything itself.

## Verification

`uv run pytest -q`
