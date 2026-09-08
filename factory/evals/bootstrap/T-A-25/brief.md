# T-A-25 brief: S3 plan artefact, fixed tables, ceilings, traceability,
structure check, size gate, readiness table

## What this delivers

`runner/stages/S3.py` stops being a stub. The real driver runs, in order:
the `risk_map` script over the brief's touched-area candidates against the
ticket's own worktree, attached as an ordinary latest-version input
alongside the brief and criteria; the agent invocation, a child of the
attempt; a parse of the agent's `out/plan.md`; `handoff_ready`, which
derives the plan's readiness table from the criteria, the question and
assumption log, the brief, the risk map, and the plan's own tables --
never from agent prose -- and writes it into the plan in place; the
general structure check (`runner/checks/artefact_structure.py`), now built
generic enough that a later ticket can call it for the `criteria` kind
too; and `size_gate` over the plan's own size estimate. Only a version
that clears both checks is registered as the ticket's `plan`; a
structural failure is a `check_result` fail plus a `fail` outcome with
`failure_kind = "structural"`, never a silent default.

- `runner/checks/artefact_structure.py` (new) -- `check(kind, text, *,
  tier=None, criteria_text=None, catalogue=None, limits=None,
  pending_allowed=False) -> list[Finding]`. Generic over every kind
  `artefacts.SECTIONS` names: fixed sections present, in order, non-empty
  (a `pending answer` section exempt only when `pending_allowed`); every
  fixed table's exact columns, from whichever of `BRIEF_TABLES`/
  `CRITERIA_TABLES`/`PLAN_TABLES` the kind owns, an explicitly empty
  `Dependencies` table the one allowed exception. Plan-only on top of
  that: prose/table-row ceilings and first-page placement (the readiness
  table excluded from the row ceiling, since it is derived rather than
  agent-authored); every task's `validation_recipe` a catalogue id and its
  `validation_args` free of shell syntax; two-way `AC-n` traceability
  between the tasks/test-strategy tables and the criteria artefact; the
  readiness table's own condition keys, and a `blind_spot` row with no
  `waiver_id` treated exactly like `pending`.
- `factory/scripts/checks/size_gate` (new, standalone) -- `--plan --tier`
  reads the plan's own `Size` table; `--plan --tier --diff` counts a
  unified diff's added-plus-removed lines, excluding `project.yaml`'s
  `lockfiles`/`generated_paths` globs, standing in for the real S5 wiring
  a later ticket does. Either mode passes under the tier's `size_gate`
  threshold or when the plan's `Size` table carries a `justification`,
  and prints one JSON line either way.
- `factory/scripts/checks/risk_map` (new, standalone) -- per candidate
  path: commits and top-author share in the churn window (from
  `git log --since`), file size at the checkout's HEAD, and `named` when
  the churn-times-size score falls in the candidate set's own top decile
  or no author holds the configured minimum share. The exact scoring is
  this ticket's wiring; a later ticket deepens the computation itself.
- `factory/scripts/tools/handoff_ready` (new, standalone) -- derives and
  writes the seven-row readiness table from the criteria's agreement
  check, the question/assumption exports, the brief's impact and
  linked-sources rows, the attached risk-map JSON, the plan's own `Size`
  table against the tier threshold, and a reviewer-set JSON; `--waiver
  condition=id` is the one explicit input a `blind_spot` row's waiver
  comes from (R-S5-13's own waiver mechanism does not exist yet).
- `runner/stages/S3.py` (rewritten) -- the seven-step order above.
  `assumption_log_hash` is implemented locally (the canonical hash of the
  ticket's non-withdrawn assumption rows) since `runner/questions.py`
  does not exist in this worktree; the reviewer set is a single
  `s3_reviewer` slot built from `owners.yaml`, the real scope-derived set
  being a later ticket's work. Front matter (`assumption_log_hash`,
  `criteria_hash`) is written into the plan text *before* `handoff_ready`
  runs, not after, so the file it edits in place -- and that this driver
  registers unmodified -- already carries it: the registered artefact's
  hash is exactly the file `handoff_ready` produced.
- `factory/config/project.yaml` -- `generated_paths: [target/**]` and a
  new `lockfiles` list (`*.lock`, `package-lock.json`, `uv.lock`,
  `pom.xml.lock`).
- `factory/evals/agents/S3/fixtures/<case>/out/plan.md` (new, eleven
  cases) plus `factory/evals/agents/S3/eval.yaml` extended with matching
  cases under `expect: plan_structural_ok`/`plan_structural_reject` --
  deliberately not `ok`/`reject`, so the existing generic agent-definition
  eval walk in `test_stub_stages.py` (which globs `fixtures/<case>/*.md`
  for the agent's own front matter) leaves them alone.
- `factory/evals/scripts/checks/size_gate/`, `factory/evals/scripts/
  checks/risk_map/`, `factory/evals/scripts/tools/handoff_ready/` (new)
  -- each with its own `eval.yaml` and fixtures; none of these three eval
  roots is walked generically (only `agents`/`skills`/`rubrics` are), so
  each gets its own hand-written test.
- `runner/artefacts.py` -- two small, additive changes, not owned by this
  ticket but touched because the structure check needs them: `Section`
  gains `table_header()` (the first table's column names, present even
  when the table carries zero data rows -- `table()`'s row dicts lose the
  header entirely at zero rows, which the `Dependencies`-empty case needs
  to survive); and `PLAN_TABLES`'s `"Scope"` key is renamed to `"Scope and
  discretion"`, matching the actual section title in `SECTIONS["plan"]` --
  the prior key could never be found by `artefact.section(...)`, a
  pre-existing bug this ticket's own generic table lookup exposed.
- `runner/tests/test_s3_structure.py`, `runner/tests/test_size_gate.py`,
  `runner/tests/fixtures/s3/criteria.md` (new).
- `runner/tests/test_report.py`, `runner/tests/test_stub_stages.py`
  (touched, not owned) -- both built a walk through every stage assuming
  S3's old trivial stub pass; the real driver needs a worktree, a real
  manifest pin, and a brief/criteria to plan against, so both now build
  that and feed the S3 agent invocation the committed `ok` plan fixture
  through `FIXTURE_ADAPTER_OUT_DIR`.
- `factory/manifest.yaml` -- every new/changed file under `factory/`
  added or refreshed.

## Row covered

R-I-12, R-S3-12, R-S3-14, R-S3-18, R-S3-19, R-S3-21
(`docs/prd/04-S3-spec-and-plan.md`); the plan tables, length limits, and
risk-map paragraphs of `docs/prd/08-configuration.md`.

## Owner decisions this ticket follows

Every decision named in the ticket brief: the structure check built
generic from the start, not scoped to `plan`, since a later ticket calls
it for `criteria` too; `pending_allowed` as an explicit keyword rather
than the check re-deriving it; the driver treating an
`aborted_budget`/`infrastructure_failure`/`sandbox_violation` child
outcome as the attempt's own outcome; scripts standalone, shelled out to,
never imported; the single-slot `s3_reviewer` reviewer-set stand-in from
`owners.yaml`; `assumption_log_hash` implemented locally pending
`runner/questions.py`; the S5 real `size_gate` wiring and the risk map's
computed content both explicitly out of scope.

## Decisions this brief did not already settle

- **`stages.invoke_agent`'s `"refused_request"` outcome, mapped to
  `("fail", "infrastructure")` for the attempt's own row.** The brief's
  seam description only says to propagate an `aborted_budget`/
  `infrastructure_failure`/`sandbox_violation` child outcome as the
  attempt's outcome; a manifest-pin refusal returns `"refused_request"`,
  which is not a `stage_run.outcome` value at all (the schema's `OUTCOMES`
  enum has no such member -- only `utility_run` rows use it). Recording it
  as-is would raise an integrity error on the attempt's own `finish` call,
  so this driver special-cases it to `("fail", "infrastructure")`, the
  same failure kind `cursor_sdk._refuse_unavailable_model` uses for the
  analogous "cannot even attempt" situation.
- **Front matter injected before `handoff_ready` runs, not after.** The
  ticket's own criterion 23 needs the registered plan's hash to equal
  the sha256 of the exact file `handoff_ready` produced; adding front
  matter afterward (a natural place to put it) would re-render the file
  and break that byte identity. Prepending
  `assumption_log_hash`/`criteria_hash` as a plain YAML block before the
  agent's own sections, then handing that already-fronted file to
  `handoff_ready --in-place`, means the file it edits and the file this
  driver registers are the same bytes throughout.
- **`handoff_ready`'s reviewer-set `--waiver condition=id` flag.** R-S3-21
  says a `blind_spot` row needs "a waiver id from the input"; since
  R-S5-13's waiver mechanism does not exist as a ticket yet, this reads
  most literally as a script input rather than something read back out of
  agent prose, so it is a repeatable `--waiver` CLI flag the driver does
  not yet call with anything (no code path produces a waiver id today,
  since the brief-side blind-spot acceptance flow is also not built), but
  `handoff_ready`'s own eval fixtures exercise it directly.
- **`size_gate`'s diff mode takes a diff file, not two git refs.** The
  ticket brief's own text allows either ("a fixture diff or two git
  refs"); S5's real wiring (a later ticket) is the caller that would ever
  supply live refs, and this ticket's own diff-mode tests only need a
  seeded fixture diff, so the script takes `--diff <path>` (a unified-diff
  text file) and leaves ref-based invocation to that later ticket.
- **`risk_map`'s "named" rule.** The section 8 text names two conditions
  (top decile of churn-times-size, or no author holding the minimum
  share) without a precise tie-breaking formula. This ticket picks the
  simplest legible one -- rank candidates by `commits * size_bytes`
  descending, name the top `ceil(0.1 * n)` (at least one when the set is
  non-empty) -- and a later ticket, which owns the computation's depth,
  is free to replace it.
- **Collateral fixes to `test_report.py` and `test_stub_stages.py`.**
  Both built a walk through every stage on the assumption that S3, like
  the stub it replaced, always writes a placeholder and passes. The real
  driver refuses without a worktree, a real manifest pin, and a brief/
  criteria carrying real tables; both tests now build that (moving the
  worktree clone ahead of S3, registering a small but real brief and the
  shared criteria fixture, and pointing `FIXTURE_ADAPTER_OUT_DIR` at the
  committed `ok` plan fixture) rather than losing the "every stage really
  runs" coverage either file existed to pin.

## Out of scope

The S3 rubric lines and the risk map's computed content (a later ticket);
the bootstrap checklist, human verdicts, the plan tuple and its approval
(a later ticket); the real S5 wiring of `size_gate` into the ordered
check list (a later ticket); the packet artefact's real fixed-section
content (a later ticket); the real scope-derived reviewer set bound into
the plan tuple (a later ticket).
