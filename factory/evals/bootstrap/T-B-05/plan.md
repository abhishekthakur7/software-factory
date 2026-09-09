# T-B-05 plan

| # | Step | Files touched | Proving test |
|---|---|---|---|
| 1 | Write the one operation surface: nineteen names, each a thin binding to the function its own module already defines; `run_stage` binds to the wrapper that already refuses a live run and reconciles pending writes before the driver, not the bare dispatcher | `runner/stage_interface.py` | `runner/tests/test_stage_interface_complete.py` |
| 2 | Rewrite the command line so it imports only the stage interface and the paths module, every verb calling one exported name; drop the one verb with no exported name in the Initial catalogue | `runner/cli.py` | `runner/tests/test_stage_interface_complete.py`, `runner/tests/test_cli_skeleton.py` |
| 3 | Update every existing test that reached the record through the command line's own re-exported names to call the operation module or the surface directly | `runner/tests/test_crash_recovery.py`, `runner/tests/test_freshness.py`, `runner/tests/test_outbox.py`, `runner/tests/test_report.py`, `runner/tests/test_stage_interface.py`, `runner/tests/test_stub_stages.py`, `runner/tests/test_stub_walk.py` | the same files, run directly |
| 4 | Write the export-list, outcome-actions-through-`act`, command-line import boundary, and every AST import-graph scan (adapters, forbidden script imports, forbidden script SQL, the one graduation write site, the stage-driver boundary in both directions), plus the non-owner graduation-approval authority test | `runner/tests/test_stage_interface_complete.py`, `runner/tests/fixtures/stage_interface/` | itself |
| 5 | Unify the real-ticket-export redaction review onto four named fields, used both per-case and, new, at the top level of a `tickets/<id>` eval directory the completeness walk now also derives from disk | `runner/evals.py`, `runner/tests/test_manifest_eval_walk.py` | `runner/tests/test_manifest_eval_walk.py`, `runner/tests/test_gate_ab.py` |
| 6 | Write the standalone fixture-building script: copy a governed export directory, write its `eval.yaml` with the owner, target failure modes, and the four-field redaction review carrying the export's own content hash | `factory/scripts/tools/fixture_from_export` | `runner/tests/test_fixture_from_export.py` |
| 7 | Give the script its own eval directory the way every other script under `factory/scripts/tools/` has one | `factory/evals/scripts/tools/fixture_from_export/` | completeness walk |
| 8 | Extend the closing run with the graduation-gate-not-yet-passed, capacity-held-at-one, every-operation-through-the-surface, governed-export-completeness, dispatch-ordering, and redacted-fixture-accepted checks, over the same module-scoped walk fixture the existing outcome-record test already runs once | `runner/tests/test_pilot_walk.py` | itself |
| 9 | Refresh the manifest and write this ticket's own brief and plan | `factory/manifest.yaml`, `docs/build/T-B-05/brief.md`, `docs/build/T-B-05/plan.md` | reviewed by the human, not a test |

## Test strategy

The AST scans parse real source with `ast.walk` rather than grepping, so a
forbidden import or literal split across lines still trips them; every
scan covers `runner/`'s production modules with `runner/tests/` excluded,
the same convention the existing write-barrier scan already uses, since a
test's own fixtures deliberately reach into internal driver modules for
monkeypatching that the shipped surface must never do. The non-owner
graduation-approval test and the closing-run extension both seed real
rows through the record's own write paths -- `approvals.record_approval`,
`artefact_registry.register` against a file actually written to disk,
`run_ledger.open_utility_run` -- and assert on what a real read function
(`capacity.effective_parallel_limit`, `evals.check`, the export the walk
itself produces) returns, never on a value a test only just wrote down.
The closing run's own extension reuses its existing module-scoped fixture
rather than re-running the walk, since the walk itself is the expensive
part and every later check needs only what it already produced.
