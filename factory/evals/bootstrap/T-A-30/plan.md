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

# T-A-30 plan, part two

## Steps

| # | Step | Files touched | Proves |
|---|---|---|---|
| 1 | The preflight: `freshness.check` at `S5_PREFLIGHT`, then `binding.preflight_review_tuple` over a `ReviewComponents` built from the record; exactly one `review_tuple_preflight` refusal, or one review tuple, with no other write. | `runner/stages/S5.py` | criterion 16's preflight half; the preflight-driver tests |
| 2 | Plain base/head checkouts of the ticket's clone, one throwaway copy of each, every project recipe run at both through `recipes.run`, each recorded as a `check_result` and (when kept) a `check_evidence` artefact. | `runner/stages/S5.py` | criterion 16 |
| 3 | The four scripts plus `size_gate` and `regression_only`'s own aggregate verdict, in `CHECK_ORDER`, each bound to the review tuple; the approval-binding recheck. | `runner/stages/S5.py` | criteria 1-15 (through the driver), 16 |
| 4 | Criterion 9's routing: a `behavior_contract_evidence` "binary compatibility" blind spot through `exclusion.decide_at_checks` and, only on `checks_sensitive_path_required`, `exclusion.apply_recorded_exclusion`. | `runner/stages/S5.py` | criterion 9 |
| 5 | Aggregation: every non-`pass` blocking result builds `RecipeOutcome`/`CheckOutcome` inputs for `runner.checks.red_route.classify` (T-A-29's own module, imported locally); `fix_round` applies `checks_fix_round`, otherwise one `red_check` item opens. | `runner/stages/S5.py` | the ownership list's aggregation bullet (no numbered criterion of its own) |
| 6 | `regression_only.governs` simplifies to one argument; `recipe_governed_kind` maps a catalogue recipe onto it. | `runner/checks/regression_only.py`, `runner/tests/test_s5_regression_only.py` | part one's own noted follow-up |
| 7 | `fixture_lint`/`fixture_compile`'s `output_retention` switches to `keep` so `regression_only` has real diagnostic text to compare. | `factory/config/command-recipes.yaml` | criteria 10-11 through a live driver run |
| 8 | `factory/rubrics/S5.md`'s script-only lines for R-S5-4, R-S5-5 (two lines), R-S5-10, R-S3-12 at S5. | `factory/rubrics/S5.md` | reviewed by the human, not a test |
| 9 | `test_s5_preflight_driver.py`: a `PreflightRefused` candidate and a stale base each write exactly one refusal and nothing else. | `runner/tests/test_s5_preflight_driver.py` | the preflight half of criterion 16; no result invented |
| 10 | `test_s5_order.py`: a real base/head diff over a small fixture repository (a pre-existing `Widget.compute` gaining a guard clause, its own unit test carrying the plan's `Contracts` evidence) runs every `CHECK_ORDER` check after the project's recipes, bound to one review tuple, with plain checkouts and copies only for recipes; criterion 9's exclusion route, both the triggering and the two non-triggering cases. | `runner/tests/test_s5_order.py` | criteria 9, 16 |
| 11 | `runner/tests/test_stub_walk.py` and its neighbours (`test_stub_stages.py`, `test_crash_recovery.py`, `test_report.py`) updated for a real S5: CODEOWNERS, a passing unit test, a real plan tuple/quorum, and (for the walk itself) a local plan copy whose `Contracts` evidence resolves against a real test identity, plus a javac skip guard. | see "test fixture updates outside this ticket's ownership" below | keeps the shared exit tests honest about a real S5 rather than crashing or silently limping past it |
| 12 | Manifest hashes recomputed for every changed file under `factory/`. | `factory/manifest.yaml` | `test_manifest_hash.py` |
| 13 | This part's own brief and plan additions. | `docs/build/T-A-30/brief.md`, `docs/build/T-A-30/plan.md` | reviewed by the human, not a test |

## Test fixture updates outside this ticket's ownership

None of these files are in T-A-30's ownership list; each is flagged here
and in the final report. All were broken or gave a false pass once S5
became a real driver, not a stub:

- `runner/tests/test_crash_recovery.py`: `_give_real_base`'s source
  repository gains a CODEOWNERS file (S5's real reviewer-set derivation
  raises without one) and a trivial passing unit test (an ungoverned
  recipe absent entirely would fail on its own); a new
  `_give_s5_ready_preflight` helper gives the one test that reaches a
  real S5 run a genuine, current plan tuple and quorum.
- `runner/tests/test_stub_stages.py`: `_source_repo` gains the same
  CODEOWNERS file and passing unit test; `_checks_ticket_with_fresh_base`
  gains a real plan tuple, planned reviewer set, and quorum so its own
  `s5_outcome == "pass"` assertion still holds against a real driver.
- `runner/tests/test_report.py`: `_source_repo` gains the same two
  fixtures; `_grant_plan_approval` now records every reviewer-set slot
  the approving actor fills (not only the first `queue.act` itself
  resolves), since a real CODEOWNERS rule and `s3_reviewer_role` can now
  name the same person as two distinct slots; the walk no longer assumes
  `checks_gate` fires on its own (a real S5 pass here needs evidence the
  shared "ok" plan fixture cannot supply, "test fixture updates" above
  explains why), forcing `checks_pass_to_review` when the gate withholds
  it, since this walk's own purpose is populating rows for the `report`
  script, not re-proving `checks_gate`'s correctness.
- `runner/tests/test_stub_walk.py`: the same CODEOWNERS/unit-test/quorum
  fixes, plus a **local** copy of the S3 "ok" plan fixture
  (`runner/tests/fixtures/stub_walk/s3_ok/out/plan.md`) whose `Contracts`
  row evidence resolves against this walk's own `WidgetUnitTest` identity
  -- the shared `factory/evals/agents/S3/fixtures/ok/out/plan.md`'s own
  evidence text (`"Widget.java:42"`) resolves nowhere real, which
  `behavior_contract_evidence` now correctly calls a blind spot on every
  one of its ten `Contracts` field cells; copied rather than edited in
  place since `test_s3_rubric.py` asserts against that file's exact
  committed text. A `HAS_JAVAC` guard skips the walk loudly, before S5
  ever runs, when no JDK is available, since everything from S5 onward
  (S6, `checks_gate`, review, `pr_opened`) builds on a real recipe pass.

## Test strategy

`test_s5_preflight_driver.py` seeds two ticket states directly (no
S1-S4): one with a bare, hand-crafted plan tuple that is fresh enough for
`freshness.check` (it names the ticket's real, unmoved base) but stale by
`plan_tuple_currency`'s own comparison, proving `binding.
preflight_review_tuple`'s refusal path; one where the target branch
itself moves after cloning, proving `freshness.check`'s own refusal
short-circuits before the driver's preflight ever runs. Both assert the
`stage_run` ends `fail`/`stale_binding`, no `check_evidence` artefact
exists, and (the distinguishing assertion) exactly one `check_result`
exists in the whole per-test database -- `review_tuple_preflight` for the
first, `freshness` (a row with no `stage_run_id` of its own) for the
second, never both.

`test_s5_order.py` builds one ticket directly against a small, real git
repository (no S1-S4): a `Widget.java` with an unguarded `compute` at
base, a private-to-the-diff `WidgetUnitTest` proving the guarded
behaviour at head, and a plan whose `Contracts` row and Scope table match
exactly, so the real S5 driver clears every blocking check with no blind
spot. Skips loudly without a JDK. Asserts every `CHECK_ORDER` check_name
passed exactly once, in order, after the recipe results; that the
ungoverned unit-test recipe's own head result also passed, while the
governed recipes' base-side and empty-tree (integration/end-to-end)
results are left unchecked since they never decide blocking on their
own; that every check_result binds the one review tuple this attempt
created; that no `check_name` mentions a security recipe; and that the
recipes' own build output lands only under the throwaway copies, never
the plain checkouts. Criterion 9 is proven directly against
`S5._handle_compatibility_exclusion` with a synthetic
`behavior_contract_evidence` payload: the triggering case (the blind
spot's file is both an excluded surface and plan-declared), and two
non-triggering cases (the same file but not plan-declared; a file no
excluded surface covers at all) -- proving the driver only ever
auto-excludes on `exclusion.decide_at_checks`'s own confirmed route,
never a guess.
