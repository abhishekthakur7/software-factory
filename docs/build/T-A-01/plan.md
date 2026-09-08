# T-A-01 plan

| # | Step | Files touched | Proving test |
|---|---|---|---|
| 1 | Create the `factory/` tree of PRD 7, with `.gitkeep` in every directory this ticket leaves empty | `factory/agents/.gitkeep`, `factory/skills/shared/.gitkeep`, `factory/rubrics/checklists/.gitkeep`, `factory/scripts/checks/.gitkeep`, `factory/lints/.gitkeep`, `factory/benchmarks/.gitkeep`, `factory/index/.gitkeep`, `factory/config/.gitkeep`, `factory/catalogue/.gitkeep` | `runner/tests/test_tree_layout.py` |
| 2 | Write `manifest_hash`: load and structurally validate the manifest, diff on-disk bytes against `git show HEAD:factory/manifest.yaml`, print the SHA-256 of the committed bytes | `factory/scripts/tools/manifest_hash` | `runner/tests/test_manifest_hash.py` |
| 3 | Write the eval directory: `eval.yaml` naming four conformance cases (`valid`, `path_outside_factory`, `parent_traversal`, `missing_content_hash`) and one fixture `factory/manifest.yaml` per case | `factory/evals/scripts/tools/manifest_hash/eval.yaml`, `factory/evals/scripts/tools/manifest_hash/fixtures/*/factory/manifest.yaml` | `runner/tests/test_manifest_hash.py` (reads `eval.yaml` and drives each fixture through a temp git repo) |
| 4 | Write `factory/manifest.yaml` itself, listing every non-`.gitkeep` file this ticket adds with a real `shasum -a 256` hash | `factory/manifest.yaml` | `runner/tests/test_manifest_hash.py`, `runner/tests/test_tree_layout.py` |
| 5 | Write the write barrier: `runner/fs.py` (`write_text`, `write_bytes`, `FactoryWriteRefused`) and the AST scanner that finds raw write primitives in every other `runner/` module | `runner/fs.py`, `runner/tests/test_write_barrier.py` | `runner/tests/test_write_barrier.py` |
| 6 | Write the four synthetic write-attempt fixtures, one per event kind | `runner/tests/fixtures/write_barrier/tag.py`, `stale_index_entry.py`, `grader_failure.py`, `engineer_reading.py` | `runner/tests/test_write_barrier.py` (`must_reject` cases) |
| 7 | Write the fence: `state_table.py` (`STATES`, `TRANSITIONS`) and `anti_goals.py` (`ANTI_GOALS`), both outside `factory/` and unreferenced by the manifest | `runner/state_table.py`, `runner/anti_goals.py`, `runner/tests/test_fence.py` | `runner/tests/test_fence.py` |
| 8 | Write the gate entry point | `runner/gate.py` | manual: `python3 -m runner.gate` exits 0 |
| 9 | Write this ticket's own brief and plan (PRD decision 39) | `docs/build/T-A-01/brief.md`, `docs/build/T-A-01/plan.md` | reviewed by the human, not a test |

## Test strategy

Every criterion gets a test that can fail against a wrong implementation:
the manifest-hash tests build a real temporary git repository per fixture
and assert on the script's actual exit code and stdout rather than on
values the test itself supplies; the write-barrier test parses real source
with `ast` and would catch a write call added anywhere outside `fs.py`; the
fence test asserts on the module's file location and content shape, and
that the manifest's own file list excludes both fence modules by name. The
one exception is step 9, which has no automated proof by design -- a
hand-written brief and plan are read, not executed.
