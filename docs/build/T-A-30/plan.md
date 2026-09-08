# T-A-30 plan, part one

## Steps

| # | Step | Files touched | Proves |
|---|---|---|---|
| 1 | `scope_diff`: diff-touched paths minus the plan's scope-table paths minus its discretion globs; no `subprocess`/network import, no checkout argument. | `factory/scripts/checks/scope_diff` | criteria 1-3 |
| 2 | Eval fixtures: every file in scope, one file outside scope and discretion, one file matched only by a discretion glob. | `factory/evals/scripts/checks/scope_diff/` | criteria 1-2 |
| 3 | `source_declaration_diff`: regex extractor for public/protected Java declarations, base-vs-head matching by kind/owner/bare-name, `unplanned` and `unchanged_but_changed` detection against the plan's `Contracts` table. | `factory/scripts/checks/source_declaration_diff` | criteria 4-6 |
| 4 | Eval fixtures: declaration added and unnamed, declaration removed and unnamed, a parameter-list change on a declaration the plan calls unchanged, and a fixture where the plan names everything. | `factory/evals/scripts/checks/source_declaration_diff/` | criteria 4-6 |
| 5 | `behavior_contract_evidence`: per-field-cell and per-verdict evidence resolution against `--tests-head` identities and characterization tasks, plus the six lax blind-spot detections. | `factory/scripts/checks/behavior_contract_evidence` | criteria 7-8 |
| 6 | Eval fixtures: every field and verdict carrying resolvable evidence (pass, no blind spots); one fixture seeding all six named blind spots at once. | `factory/evals/scripts/checks/behavior_contract_evidence/` | criteria 7-8 |
| 7 | `base_test_diff`: base/head glob matching (with optional `--globs-base`), changed-file reasons (`edited`/`deleted`/`excluded`), missing-identity detection, and `Test strategy`-row matching. | `factory/scripts/checks/base_test_diff` | R-S4-10's four detections |
| 8 | Eval fixtures: one per detection (edited, deleted, renamed, excluded-through-configuration) plus a planned-change pass case. | `factory/evals/scripts/checks/base_test_diff/` | R-S4-10's four detections |
| 9 | `regression_only.py`: `compare_diagnostics`, `compare_tests`, `governs`, and the `GOVERNED_KINDS` constant. | `runner/checks/regression_only.py` | criteria 10-13, 15 |
| 10 | `test_s5_scope_diff.py`: conformance over the eval fixtures, the out-of-scope listing, and a static no-network/no-subprocess/no-checkout-argument check. | `runner/tests/test_s5_scope_diff.py` | criteria 1-3 |
| 11 | `test_s5_declaration_diff.py`: conformance for both `source_declaration_diff` and `behavior_contract_evidence` over their eval fixtures, plus targeted assertions on the added/removed/changed listings and the six blind-spot reasons. | `runner/tests/test_s5_declaration_diff.py` | criteria 4-8 |
| 12 | `test_s5_regression_only.py`: `compare_diagnostics`/`compare_tests` on seeded texts, a real walk of `factory/lints/` against `S5.CHECK_ORDER` and `GOVERNED_KINDS`, and `governs` over every named kind. | `runner/tests/test_s5_regression_only.py` | criteria 10-15 |
| 13 | `test_s5_base_test_diff.py`: conformance over the five eval fixtures plus targeted assertions on each detection's shape. | `runner/tests/test_s5_base_test_diff.py` | R-S4-10's four detections |
| 14 | Manifest hashes recomputed for every new file under `factory/`. | `factory/manifest.yaml` | `test_manifest_hash.py` |
| 15 | This part's own brief and plan. | `docs/build/T-A-30/brief.md`, `docs/build/T-A-30/plan.md` | reviewed by the human, not a test |

## Test strategy

Each script gets one eval directory (`eval.yaml` with `subject`,
`owner: abhishek`, `cases`) and a matching pytest file that runs the
script as a subprocess per case, asserting `result` against `expect` and
`returncode == 0` always (a failed check is still a clean run under this
wave's exit-code convention). Every fixture is a small, hand-built
directory tree or Markdown/JSON file -- no git repository, no fixture
project checkout -- since these scripts take plain directories and files,
never a checkout the driver hands them later.

`test_s5_scope_diff.py` adds a static AST check over the script's own
source (no `subprocess`/`socket`/`requests`/`urllib`/`http`/`runner`
import, no `--base`/`--head`/`--checkout` argument in the text) so
criterion 3's "no model, no network, no git" claim is something a
regression could actually trip, not just prose.

`test_s5_declaration_diff.py` covers both scripts in one file, per the
common brief's file list. For `source_declaration_diff`: an added
declaration and a removed declaration each unnamed by any `Contracts`
row fail and list exactly that declaration; a parameter-list change on
an existing method produces one `changed`/`unchanged_but_changed` entry
keyed by method identity, proving the base-name-only matching avoids a
spurious remove-plus-add pair; the `limitations` list always carries the
fixed source-text-extractor disclaimer. For `behavior_contract_evidence`:
the pass fixture (every field and verdict resolves) has zero blind
spots; the six-blind-spot fixture's `reasons` set contains a match for
each of the six named detections and the result is `blind_spot`, not
`fail`, proving blind spots alone never fail the check on their own.

`test_s5_regression_only.py` seeds diagnostic and test-identity text by
hand: a diagnostic absent at base blocks; the same diagnostic twice at
head and once at base blocks entirely (not split into a partial
inherited count); a diagnostic unchanged between base and head is
`inherited`, never `new_or_worse`; the same shape for `compare_tests`
over base/head-failed identities. The `factory/lints/` test walks the
directory for real (`rglob`, skip `.gitkeep`) and asserts no file there
declares a blocking rule under a name `S5.CHECK_ORDER` or
`GOVERNED_KINDS` already reserves -- a real assertion over the
directory's actual contents, honest about the fact that the directory
holds nothing today, not a vacuous pass hard-coded around that fact.
`governs` is checked against every kind the ticket brief names on both
sides of the exception, plus one call with a different `check_name` to
pin that the exception belongs to `regression_only` alone.

`test_s5_base_test_diff.py` checks each of R-S4-10's four detections
individually (edited's `changed_files` reason, deleted's, a rename's
`missing_identities` entry, and an excluded file's `changed_files` reason
under a narrower head glob via `--globs-base`), plus one pass case
proving a `Test strategy` row naming the test with a non-empty `criteria`
cell keeps it out of `unplanned` and shows up in `planned` with the
row's own action and criteria names.
