# T-A-35 plan

| # | Step | Files touched | Proving test |
|---|---|---|---|
| 1 | `expected_eval_dirs`, `check`, `walk`, `EvalDirectoryError`, `eval_dir_for_file`, `eval_dir_for_adapter`. | `runner/evals.py` | `runner/tests/test_manifest_eval_walk.py` |
| 2 | Move the nine-directory owner/fixture check into `runner.evals`; the existing test file imports it instead of defining its own. | `runner/tests/test_agent_skill_files.py` | `runner/tests/test_agent_skill_files.py` (unchanged assertions) |
| 3 | The manifest's own completeness check: every stage-and-tier entry's agent, skill, shared skills, rubric, and runtime adapter must resolve to a complete eval directory, checked only over the real project manifest. | `runner/manifest.py` | `runner/tests/test_manifest_eval_walk.py`; `runner/tests/test_manifest.py` and `test_manifest_hash.py` unaffected |
| 4 | `java_compile`, `java_lint`, `java_test` eval directories: `eval.yaml` plus a real two-file Java source tree each. | `factory/evals/scripts/checks/java_compile/`, `factory/evals/scripts/checks/java_lint/`, `factory/evals/scripts/checks/java_test/` | `runner/tests/test_recipe_wrappers.py` |
| 5 | A conformance test for the three wrappers, skipping loudly without a JDK. | `runner/tests/test_recipe_wrappers.py` | itself |
| 6 | `owner: abhishek` added to every eval.yaml that lacked one -- the four rubric directories the ticket brief names, plus the `cursor_sdk` adapter and six script directories the completeness walk over the real tree also needs owned. | `factory/evals/rubrics/S0/eval.yaml`, `S4/eval.yaml`, `S5/eval.yaml`, `S6/eval.yaml`, `factory/evals/adapters/cursor_sdk/eval.yaml`, `factory/evals/scripts/checks/impact_scan/eval.yaml`, `factory/evals/scripts/tools/export/eval.yaml`, `import/eval.yaml`, `manifest_hash/eval.yaml`, `purge/eval.yaml`, `report/eval.yaml` | `runner/tests/test_manifest_eval_walk.py` ("the real tree passes") |
| 7 | `tools/bootstrap_fixtures.py`: sync `docs/build/<ticket-id>/` pairs into `factory/evals/bootstrap/<ticket-id>/`, compute the ticket -> eval-directory mapping from each plan's own file list, write `factory/evals/bootstrap/eval.yaml`. | `tools/bootstrap_fixtures.py` | `runner/tests/test_bootstrap_fixtures.py` |
| 8 | Move the scratchpad manifest-refresh helper to its permanent home, unchanged in behaviour. | `tools/refresh_manifest.py` | manual: `python3 tools/refresh_manifest.py` regenerates `factory/manifest.yaml`'s `files:` list |
| 9 | Run the bootstrap sync and commit its output: every ticket's brief/plan pair under `factory/evals/bootstrap/`, and the computed mapping. | `factory/evals/bootstrap/**` | `runner/tests/test_bootstrap_fixtures.py` |
| 10 | The real three-step gate: adoption record (manifest hash, last `factory/` commit, no network), the eval-directory walk, then the test suite; non-zero exit on any step's failure. | `runner/gate.py` | `runner/tests/test_gate.py` |
| 11 | `test_manifest_eval_walk.py`: a temp `factory/` tree with one directory removed, one emptied, one carrying an unreviewed real-ticket case, one unowned -- each rejected; the real tree passes; a referenced stage rubric with an emptied case list fails `manifest.load`. | `runner/tests/test_manifest_eval_walk.py` | itself |
| 12 | `test_bootstrap_fixtures.py`: every docs/build pair has a byte-identical bootstrap copy; every mapped eval directory is real; `fixture-project/` sits outside `expected_eval_dirs`; a targeted check of the plan-text-to-eval-dir derivation; re-running the sync over the committed tree changes nothing. | `runner/tests/test_bootstrap_fixtures.py` | itself |
| 13 | `test_gate.py`: a temp git repo with a copied `factory/` and committed manifest -- editing one file and recommitting with a refreshed manifest changes `current_hash`; a failing temp test directory makes the gate exit non-zero; a dirty (uncommitted) `factory/` edit makes the gate exit non-zero; no `fetch`/`remote` in the module's source, and a monkeypatched `subprocess.run` that refuses any git verb but `log` still lets the gate complete. | `runner/tests/test_gate.py` | itself |
| 14 | This ticket's own brief and plan. | `docs/build/T-A-35/brief.md`, `docs/build/T-A-35/plan.md` | reviewed by the human, not a test |
| 15 | Manifest hashes recomputed for every new or changed file under `factory/`. | `factory/manifest.yaml` | `runner/tests/test_manifest_hash.py` |

## Test strategy

`test_manifest_eval_walk.py` builds a small synthetic `factory/` tree
(one agent, one skill, one rubric, one adapter, one script, matching
`runtime.yaml`) under `tmp_path` so each rejection case can mutate exactly
one directory without touching the real tree: deleting a directory,
emptying its `cases:` list, adding a `source: real_ticket_export` case
with no `redaction_review`, and deleting its `owner` line each raise
`EvalDirectoryError` naming that directory; the untouched synthetic tree
and the real `factory/` tree both pass `evals.walk`. The manifest half
seeds a tiny manifest naming the synthetic tree's own files, empties one
referenced rubric's case list, and asserts `manifest.load` raises rather
than the eval-directory check silently passing a manifest it should
refuse.

`test_recipe_wrappers.py` runs each wrapper as a real subprocess over its
own fixture: `java_compile` and `java_lint` assert a clean exit and (for
lint) empty stderr; `java_test` asserts the exact `ran` identity on its
final JSON line; one `must_reject` case proves a source root with no
`.java` files fails loudly rather than passing on an empty diff. All four
skip loudly, via `pytest.mark.skipif`, when `javac`/`java` are not on
`PATH`.

`test_bootstrap_fixtures.py` treats the committed `factory/evals/bootstrap/`
tree as the thing under test, not the tool's internals: every real
`docs/build/<id>/{brief.md,plan.md}` byte-compares equal to its bootstrap
copy; every relative path `eval.yaml`'s `tickets:` mapping names is asserted
to exist as a real directory; `fixture-project/` is asserted absent from
`evals.expected_eval_dirs()`. One direct test of
`bootstrap_fixtures.eval_dirs_exercised` on a synthetic plan text (a rubric
path, a script path, and an unrelated config path in the same string) pins
that only the two real ones are kept. A final test calls
`bootstrap_fixtures.sync` over the real repository root and asserts it
returns no changes -- the committed tree already is what the tool would
produce, so a plan edited after its ticket's build without re-running the
sync would fail this test rather than silently drifting.

`test_gate.py` never runs the gate over the real `runner/tests/` directory;
every case passes `--tests` at a small temp directory it builds itself.
The manifest-hash-changes case copies `factory/` into a temp git repo,
edits one file (a skill body), reruns `tools/refresh_manifest.py` equivalent
logic inline, commits, and asserts `main`'s printed hash differs from the
pre-edit run. The no-network case asserts the string `fetch` and `remote`
are absent from `runner/gate.py`'s source, then monkeypatches
`subprocess.run` to raise on any `git` invocation whose subcommand is not
`log`, running the gate over a clean temp repo and asserting it still
completes -- proving the only git call the gate itself makes is the
read-only log lookup its adoption-record line prints.
