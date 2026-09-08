# T-A-21 plan

## Steps

| # | Step | Files touched | Proves |
|---|---|---|---|
| 1 | Three real context-index entries with the six required front-matter keys and short factual bodies; the stub `.gitkeep` deleted. | `factory/index/conventions.md`, `factory/index/sensitive-paths.md`, `factory/index/callers.md`; `factory/index/.gitkeep` removed | criteria 1, 4 |
| 2 | `runner/tests/test_context_index.py`: front-matter presence, the day-and-commit staleness rule, no-`last_verified` staleness, the three-entry count, `index_use` rows on a real stage run, stale listing, the `stale_index` tag, and the empty-index "no entries" contract. | `runner/tests/test_context_index.py`, `runner/tests/fixtures/context_index/*` | criteria 1, 2, 3, 4, 5, 6, 7, 8 |
| 3 | Real agent files for S1..S4: what each reads, the exact output section list, the PRD rules for that stage, what's forbidden. | `factory/agents/S1.md`, `factory/agents/S2.md`, `factory/agents/S3.md`, `factory/agents/S4.md` | criterion 9 |
| 4 | Real skill files for S1..S4: the ordered procedure each stage follows. | `factory/skills/S1.md`, `factory/skills/S2.md`, `factory/skills/S3.md`, `factory/skills/S4.md` | criterion 9 |
| 5 | The shared `codegraph-lookup` skill: when and how to query the codegraph before grepping or proposing something new; the stub `.gitkeep` deleted. | `factory/skills/shared/codegraph-lookup.md`; `factory/skills/shared/.gitkeep` removed | criterion 10 |
| 6 | Manifest: `shared_skills` set on the S1, S3, S4 default entries only; a `files` entry for every new file; every changed file's hash refreshed. | `factory/manifest.yaml` | criterion 11 |
| 7 | Every stub's `eval.yaml` gains `owner`; the `ok` fixture becomes a copy of the real (now real-content) file; `missing_front_matter` stays as the generic reject case. New `eval.yaml` and fixtures for the shared skill. | `factory/evals/agents/S1..S4/eval.yaml`, `factory/evals/skills/S1..S4/eval.yaml`, `factory/evals/agents/S1..S4/fixtures/ok/*`, `factory/evals/skills/S1..S4/fixtures/ok/*`, `factory/evals/skills/shared/codegraph-lookup/eval.yaml`, `factory/evals/skills/shared/codegraph-lookup/fixtures/*` | criterion 12 |
| 8 | `runner/tests/test_agent_skill_files.py`: line-limit test over all nine files, the manifest-attachment test for the shared skill (S1/S3/S4 carry it, S2 does not, never by path alone), the nine-eval-directory ok/owner/non-empty-fixture walk plus its negative case, and the "no stray file under `factory/agents/` or `factory/skills/`" walk. | `runner/tests/test_agent_skill_files.py` | criteria 9, 10, 11, 12, 13 |
| 9 | This ticket's own brief and plan. | `docs/build/T-A-21/brief.md`, `docs/build/T-A-21/plan.md` | reviewed by the human, not a test |

## Test strategy

`test_context_index.py` covers criteria 1 through 8. Criterion 1 and 4 read
the three real committed entries through `load_entries` and assert their
front-matter keys, kinds, and count directly — these three are the only
places a real committed entry's exact content is pinned, so the test reads
them rather than a copy. Criteria 2 and 3 build synthetic `Entry` fixtures
(a fresh one, a day-stale one, a base-branch-stale one via a throwaway git
checkout built the way `test_stub_walk.py`'s `_git` helper does, and one
with no `last_verified`) and call `stale_reason` directly with a fixed
`now`, so the assertions never depend on the wall-clock date the test
happens to run on. Criteria 5 through 7 open a `stage_run` with
`run_ledger.open_stage_run` and call `record_reads` directly against a
fresh entry and a stale one, asserting the `index_use` row's fields, the
`Read.stale` flag, and the `stale_index` tag's `fm_id`. Criterion 8 asserts
`load_entries` on a missing and on an empty directory both return `()`, and
that `record_reads(conn, stage_run_id=..., entries=())` writes no row and
raises nothing — the empty-index contract a driver relies on to write "no
entries".

`test_agent_skill_files.py` covers criteria 9 through 13. Criterion 9
parametrizes over the eight stage files (agents and skills, S1-S4) plus the
shared skill for criterion 10, asserting each is under
`tiers.yaml`'s `length_limits.instruction_file_lines` — never the literal
300. Criterion 11 loads the real manifest through `manifest.load()` and
asserts `shared_skills` on the S1, S3, and S4 default entries names the
shared skill's path and that S2's entry does not, so the attachment is
proven through the manifest the runtime actually reads, not a directory
listing. Criterion 12 walks the nine eval directories, asserting each
`eval.yaml` carries a non-empty `owner` and at least one case whose fixture
directory exists and is non-empty, plus a `must_reject` test over a
`tmp_path` copy with an empty fixture directory and one with `owner`
deleted. Criterion 13 walks `factory/agents/` and `factory/skills/` and
asserts the only files present are the eight stage files and the one
shared skill under `skills/shared/`.

## Verification

`uv run pytest -q`
