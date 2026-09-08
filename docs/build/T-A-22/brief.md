# T-A-22 brief: S1 for real -- brief rubric, impact evidence, final tier, impact-derived tiering

## What this delivers

S1 stops being a stub: it reindexes the ticket's worktree, runs the
Maven/Gradle impact scan over its `pom.xml`, reads the context index and
records what it read, invokes the context-gathering agent, then checks
the brief it wrote before letting it stand. The checked brief -- never
the agent's raw output -- is what gets registered and what everything
downstream reads. `Final tier` is never trusted from the agent: the
driver counts files/services/unknowns from the brief's own other tables
and the registered impact-scan payload, applies the files/services/
unknowns threshold rule, then impact-derived tiering (the highest known
criticality among the target and impacted services, with an explicit
unknown-impact flag), and overwrites the section with its own numbers.
A brief that discovers scope outside the ticket's own repository and
target service, or an `unknown` row that says so in its own blind spots,
re-triggers the exclusion gate instead of proceeding; every other
content problem -- an over-length summary, a flag with no code
reference, a live-state assertion outside blind spots, an impact row the
impact scan itself contradicts -- fails the attempt as a verification
problem, so a rerun can fix the content without the ticket leaving its
current state.

- `runner/stages/S1.py` (rewritten) -- reindex as a `utility_run`
  (non-fatal); `impact_scan` run over the worktree's `pom.xml` and
  registered as artefact kind `impact_scan`; context-index reads recorded
  and registered as artefact kind `index_reads`; the agent invoked
  through `stages.invoke_agent` with both as its fixed input set; the raw
  `out/brief.md` parsed and structurally validated; the tier numbers
  computed and the `Final tier` section overwritten before the checked
  brief is registered, superseding the ticket's prior version; the
  brief's own content checks run and recorded; an exclusion or a content
  check failure returns before the driver ever applies a plain pass.
- `runner/checks/brief.py` (new) -- pure functions over already-collected
  evidence: `summary_word_limit`, `flags_are_code_references`,
  `live_state_confined_to_blind_spots`, `impact_evidence_valid`,
  `inbound_coverage_matches_caller_freshness`, `discovers_excluded_scope`,
  plus the counting and tier helpers `count_files_touched`,
  `touched_services`, `count_unknowns`, `final_tier_rule`,
  `impact_derived_tier`. Two conventions the brief's tables carry that no
  column states outright, both documented in the module docstring: a
  row's service comes from an outbound row's `dependency` (a
  `groupId:artifactId` key resolved through the registered `impact_scan`
  payload) or an inbound row's `dependency` (the caller service's own
  name, asserted directly); an `unknown`-coverage row that changes
  eligibility or names a public contract says so in its own `blind_spots`
  cell, naming "eligibility" or "public contract".
- `factory/scripts/tools/reindex` (new) -- a standalone script: `codegraph
  index <worktree>`, one JSON line `{"ok": bool, "reason": ...}`, exit 0
  on success, 1 when the binary is absent or the index itself fails.
- `factory/rubrics/S1.md` (rewritten) -- a real ten-line table: script
  and grader halves for the summary, impact-evidence, and flags/live-state
  rows, script-only for the index-reads row (nothing in the acceptance
  criteria dictates a grader sentence for it), script-only for the
  final-tier row for the same reason, and script and grader halves for
  the impact-derived-tiering row -- the grader halves' `judgment` text is
  copied verbatim from the acceptance criteria that dictate it.
- `factory/evals/rubrics/S1/` -- `eval.yaml` gains `owner: abhishek`; a
  fact-only-summary fixture; four seeded `human_verdict` scenario
  documents (one per row needing a grader judgment), each naming the
  rubric line it exercises, a subject, a verdict, and why.
- `factory/evals/agents/S1/fixtures/` -- eight new `out/brief.md`
  fixtures (HTTP, messaging, config, stale-catalogue, unmapped-package,
  authoritative-build-graph, eligibility-triggering-unknown, plain-ok),
  and a new `driver_cases` key in `eval.yaml` naming them -- kept
  separate from the existing `cases` key, which the generic
  definition-conformance walk still reads for `factory/agents/S1.md`
  itself and is untouched.
- `factory/manifest.yaml` -- `factory/rubrics/S1.md`'s hash refreshed;
  new entries for every file this ticket adds under `factory/`.
- `runner/tests/test_s1.py` (new) -- drives every acceptance criterion.

## Deviations and open decisions

See the final report for the full list; the two structural ones are:
the driver-fixture cases live under a new `driver_cases` key in
`factory/evals/agents/S1/eval.yaml` rather than the existing `cases` key
(which the generic stub-definition conformance walk reads and would
otherwise try to `load_definition` a `brief.md`), and the rubric's
`R-S1-8` (final tier) row is script-only, since no acceptance criterion
dictates a grader judgment sentence for it.
