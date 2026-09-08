# T-A-21 brief: context index entries, staleness, index-use rows; agent and skill files capped

## What this delivers

The context index stops being an empty directory: three hand-written
entries (`conventions`, `sensitive-paths`, `callers`) describe the fixture
project for real, each with the front matter the staleness rule reads.
`runner/context_index.py` already carries the loader, the staleness rule,
and `record_reads` (the `index_use` writer and `stale_index` tagger); this
ticket only tests that seam against the three real entries and a handful of
synthetic ones, since the real reading stage (S1's driver) is a later
ticket's work.

The stub agent and skill files for S1 through S4, plus the shared
`codegraph-lookup` skill, get their real content: what each stage reads,
what it writes (the exact section list and table columns from
`runner/artefacts.py`), and the rules its PRD row states, each file well
under the section 8 instruction-file line limit. The shared skill attaches
to S1, S3, and S4 through the manifest's `shared_skills` field, never by
directory convention, and S2 does not carry it. Every stub's own eval
directory keeps its `ok`/`missing_front_matter` shape and gains an `owner`
key.

## Rows covered

R-F-6, R-S1-7 (`docs/prd/04-S1-context-gathering.md`, `docs/prd/07-factory-as-code.md`),
R-F-7 (`docs/prd/07-factory-as-code.md`).

## What was built

- `factory/index/conventions.md`, `factory/index/sensitive-paths.md`,
  `factory/index/callers.md` — real front matter and short factual bodies;
  `factory/index/.gitkeep` deleted.
- `factory/agents/S1.md` .. `S4.md`, `factory/skills/S1.md` .. `S4.md`,
  `factory/skills/shared/codegraph-lookup.md` — real content;
  `factory/skills/shared/.gitkeep` deleted. Each file states what it reads,
  the exact output shape, and the PRD rules for that stage; none of them
  crosses 100 lines, well under the 300-line cap.
- `factory/manifest.yaml` — `shared_skills: [factory/skills/shared/codegraph-lookup.md]`
  added to the S1, S3, and S4 default entries only; file entries for every
  new file; hashes refreshed for every changed file.
- `factory/evals/agents/S1..S4/`, `factory/evals/skills/S1..S4/`,
  `factory/evals/skills/shared/codegraph-lookup/` — each `eval.yaml` gains
  an `owner` key; the `ok` case's fixture is a byte-for-byte copy of the
  real file; `missing_front_matter` is unchanged.
- `runner/context_index.py` — untouched; the existing loader, staleness
  rule, and `record_reads` already cover every criterion.
- `runner/tests/test_context_index.py` (new), `runner/tests/test_agent_skill_files.py`
  (new), fixtures under `runner/tests/fixtures/context_index/`.
- `runner/tests/test_stub_stages.py` — untouched; its eval-directory walk
  only descends into a directory that itself carries `eval.yaml`, so the
  nested `factory/evals/skills/shared/codegraph-lookup/` directory was
  never in its scope and the new `owner` key doesn't change what it reads.

## Decisions this brief did not already settle

- **Caller entry's invented consumer.** `checkout-web`, tier T1, reaches the
  fixture project through `com.fixture.Greeter#greet` (the fixture
  project's one public class) rather than an HTTP route, since the fixture
  project itself has no HTTP layer — inventing one would misdescribe the
  checkout it actually is. `paths` names the one file backing that call, so
  a commit touching it is what makes the entry stale on the base-branch
  clause.
- **Context-index entries' `source` field never names a ticket.** Each
  entry's `source` points at the artefact it describes
  (`factory/evals/fixture-project`, `factory/config/sensitive-paths.yaml`,
  or, for the invented caller, "hand-recorded" since no live service
  registry exists at this scale) rather than the document that produced it,
  keeping the index itself ticket-agnostic the way the rest of `factory/`
  is.
- **Agent files carry rules and invariants; skill files carry the
  procedure.** The PRD calls the agent file "the runtime's rules file" and
  the skill "the stage prompt" without drawing the line further. This build
  puts what must always hold (section list, table columns, what's
  forbidden) in the agent file and the ordered walkthrough in the skill
  file, so a stage's two files complement rather than duplicate each other;
  some restatement is unavoidable (e.g., the fixed section list appears in
  both, since the skill's last step needs it as a checklist) and is exactly
  the "same policy restated at each site it governs" AGENTS.md allows.
- **The shared skill's own `stage` front-matter value is `shared`.**
  `runner/definitions.py` requires the key but never validates its value
  against a closed set, and the skill is attached to three different stages
  through the manifest, so no single real stage code fits; `shared` says
  plainly that it isn't stage-specific.
- **Criterion 8 ("no entries") is proven at the `context_index` module
  level, not through a stage driver.** No real S1 driver exists yet (a
  later ticket's work); the test calls `load_entries` on an empty directory
  and `record_reads` with the resulting empty tuple, asserting neither
  raises and no `index_use` row is written — the same contract a real
  driver will rely on to write "no entries" into the brief.
- **Test fixtures for staleness use a synthetic index directory, not the
  three real committed entries, for every case except criterion 1 and 4.**
  The real entries are fixed at `last_verified: 2026-09-08`; ordinary test
  runs happen on later dates, so a test asserting freshness against the
  real entries would silently start failing as they age. Synthetic fixture
  entries under `runner/tests/fixtures/context_index/` carry `now` values
  the test also controls.

## Out of scope

The real S1 driver that calls `context_index.record_reads` for a live run
and writes "index entries used" into the brief (a later ticket); the brief
artefact's own content (a later ticket); `scripts/tools/reindex` (a later
ticket).
