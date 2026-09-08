# T-A-19 brief, part one: the manifest's full field set, fail-closed resolution, and migration

This brief covers the first of two builders on this ticket. It builds
criteria 1, 2, 3, 4, 5, 9 and 10. Criteria 6, 7, 8 and 11-19 (model checks
against `runtime.yaml`, the resolved-model mismatch, the manifest-hash pin
enforced at every later stage run, and budget abort) belong to a second
builder working on top of this module; `factory/config/runtime.yaml` and
`factory/config/sandbox.yaml` are out of scope here and neither exists yet.

## What this delivers

`factory/manifest.yaml` now names, for every stage `S0` through `S6`, a
`default` entry carrying the ticket's full field set: `agent`, `skill`,
`shared_skills`, `rubric`, `tool_allowlist`, `budget` (a path into
`factory/config/tiers.yaml`, never numbers), `runtime_adapter`,
`runtime_version`, `model_requested`, `grader_model`, `sandbox_policy`,
`toolchain`, and, for `S2` only, `restatement_model`. `S0`, `S5` and `S6`
carry null `agent`, `skill`, `model_requested` and `grader_model`, since
they run no agent; every other field on those three stages stays
populated, since a script-only stage still runs inside the same thin
sandbox and toolchain as an agent-driven one. An optional
`stages.<S>.<tier>` mapping may override any of a stage's default fields
per tier; none exists yet in the real manifest, since none of this
ticket's criteria need one, but `runner/manifest.py` resolves and
validates one wherever a later ticket adds it.

- `runner/manifest.py` (new) -- `load(path) -> Manifest` parses and fully
  validates a manifest: every `files` entry is path plus hash and stays
  inside `factory/`; every stage's `default` entry carries every required
  field (and `S2`'s `restatement_model`); every field a `default` or tier
  entry names as a file path is a key in `files`; every budget key the
  manifest's `budget` path resolves to, across `tiers.yaml`'s `by_tier`,
  `overrides`, and `s4_per_ticket`, is exactly `tokens` or
  `wall_clock_seconds`; `runtime_version` is a plain dotted version, never
  a range; and the null/non-null split on `agent`/`skill`/
  `model_requested`/`grader_model` holds exactly on `S0`, `S5`, `S6`
  versus every other stage. `resolve(manifest, stage, tier) -> Entry`
  merges the stage's `default` with its tier override (if any), re-checks
  the same null invariant on the merged result, then re-hashes every file
  the merged entry names against the manifest's declared hash for it --
  an entry whose backing file has moved since the manifest was written
  fails resolution even though it already passed `load`. Neither
  function takes a database connection, so a resolution failure is
  structurally incapable of opening a stage run: criterion 5's "before
  the stage it names is invoked" holds because there is nothing in this
  module that could invoke one. `current_hash(root)` shells out to
  `factory/scripts/tools/manifest_hash` rather than re-deriving its
  hashing rule, so the two can never quietly drift apart; it fails the
  same way the script does on an uncommitted edit or a tree with no git
  history. `migrate(conn, *, actor, note=None, root=REPO_ROOT,
  owners_path=...)` is `factory migrate-manifest`'s function: it always
  records one `approval_record` on the new `manifest` gate, decided
  `approve` when `actor` currently holds `factory_owner` in
  `owners.yaml` and `reject` otherwise, so an unauthorised call is
  audited but can never itself satisfy the lone-`factory_owner`-slot
  quorum `approvals.evaluate` checks next. Once quorum holds, every
  ticket outside `state_table.TERMINAL_STATES` whose `factory_manifest_hash`
  differs from the new hash is migrated: one `check_result` row (
  `check_name = "manifest_migration"`) names the ids of that ticket's
  artefacts registered by stage runs of `S1` onward (an `S0` artefact is
  never named, since eligibility is not re-litigated by a manifest
  change), `transitions.apply(..., "migrate_manifest")` returns the
  ticket to `context` (the state table already carried this event's row,
  built by an earlier ticket), and `factory_manifest_hash` is re-pinned.
  Without quorum, only the approval row is written.
- `runner/cli.py` -- the `migrate-manifest` verb, `--actor` required,
  `--note` optional, wired straight to `manifest.migrate`.
- `runner/schema.py` -- `"manifest"` added to `APPROVAL_GATES`.
- `runner/db.py` -- `USER_VERSION` bumped for the new gate value.
- `factory/manifest.yaml` -- the full `stages` field set described above,
  and the stale duplicated `content_hash:` line under
  `factory/config/trust-profile.yaml` deleted (the file's real hash is
  the first of the two lines; `shasum -a 256` confirms it).
- `runner/tests/test_manifest.py` and `runner/tests/fixtures/manifest/`
  (`valid`, `missing_required_field`, `non_null_agent_on_s5`,
  `invalid_budget_key`, `missing_referenced_file`, `migration_seed`, each
  a small self-contained `factory/` tree; `owners.yaml`, a copy of the
  real committed file's shape, isolates the migration tests from
  `factory/config/owners.yaml`).

## Row covered

R-I-4 (`docs/prd/03-stage-interface.md` line 10): the manifest's full
per-stage-and-tier field set, files as path plus hash, script-only stages
carrying null agent/model fields, and a human-approved migration that
invalidates `S1` onward and returns a ticket to `context`. This builder
covers R-I-4's manifest-shape and migration clauses; the model-check and
pin-enforcement clauses of the same row belong to the second builder.

## Owner decisions this brief follows

- The manifest field set, its per-stage null/non-null split, and the
  `runner/manifest.py` function signatures (`load`, `resolve`,
  `current_hash`) are exactly as named in the ticket brief.
- One placeholder model name, `claude-sonnet-5`, stands in for
  `model_requested`, `grader_model` and `S2`'s `restatement_model` across
  every agent-driven stage in the real manifest. **The owner must confirm
  this name (or replace it) before the first real run** -- it is a
  placeholder chosen only so the manifest's required fields are non-null,
  not a model selection.
- `runtime_adapter: cursor_sdk` and `runtime_version: "1.0.31"` are
  likewise placeholders pending the adapter ticket; `sandbox_policy:
  thin` and `toolchain: {jdk: "17"}` match the sandbox and fixture
  project already committed by earlier tickets.
- `tool_allowlist: [read_file, write_file, run_command]` for the
  agent-driven stages is a placeholder tool-name set: no runtime adapter
  exists yet to define the real vocabulary. Script-only stages carry an
  empty list, as the ticket text requires.

## Decisions this brief did not already settle

- **The null/non-null field-presence check runs at both `load` (on every
  stage's `default` entry) and `resolve` (on the tier-merged entry)**,
  through one shared helper, rather than only once. A tier override is
  optional and, today, none exists in the real manifest, but a future one
  could set `agent` on `S5`'s `light` tier without touching `S5`'s
  `default` at all; checking only at `load` time would miss that.
- **`current_hash` shells out to the `manifest_hash` script** rather than
  lifting its hashing rule into a shared pure function. The script must
  stay import-free of `runner` by design (its own docstring: "the trusted
  control plane never has to load agent-reachable code to check its own
  manifest"), and a subprocess call is the only sharing option that adds
  no import in either direction.
- **`migrate`'s quorum path turns on the approval's `decision`, not on a
  membership check before recording.** Recording `reject` for an actor
  who does not currently hold `factory_owner` reuses
  `approvals.evaluate`'s existing "does this slot have quorum" question
  unchanged (the slot's `min_count` is 1, so any accepted `approve` row
  alone would otherwise always satisfy it) and keeps every migration
  attempt -- authorised or not -- in the same audited table, matching how
  `governance.decide` already records a trust-profile decision under
  whatever role the caller names, without a separate authorisation gate
  in front of it.
- **The `check_result` row naming invalidated artefacts carries no
  `ticket_id` column**, because `check_result` has none; it is tied to
  the migration only through its `summary` text and its position in the
  table, the same way `freshness.record_failure` names a stale check's
  reasons in `summary` rather than a dedicated column when no evidence
  tuple id fits. A caller who needs "every migration `check_result` for
  ticket N" reads `summary` or, more simply, already knows N from having
  called `migrate` itself.
- **The manifest's `budget` field is the path to `tiers.yaml`; `resolve`'s
  `Entry.budget` is the actual `{tokens, wall_clock_seconds}` dict**,
  read live through `run_ledger.budget(stage, tier)` against the real
  `factory/config/tiers.yaml` (never the resolving manifest's own tree) --
  budgets are versioned, hand-edited operational config `run_ledger.py`
  already reads fresh on every call, not a value a manifest fixture could
  meaningfully override. `Entry.budget_source` keeps the declared path
  itself, so both the source and the resolved numbers are visible on one
  `Entry`.
- **Fixture files are shared byte-for-byte across every `fixtures/manifest/`
  case** (`agent.md`, `skill.md`, `rubric.md`, `tiers.yaml`, each stage's
  `agent`/`skill`/`rubric` field pointing at the same one file) rather
  than one real-looking file per stage, since nothing in `resolve` or
  `load` requires distinct paths per stage and a minimal fixture is
  easier to read against the assertion it backs.

## Out of scope

`factory/config/runtime.yaml`, `factory/config/sandbox.yaml`, the
pre-invocation requested-model check and the post-invocation
resolved-model mismatch (criteria 6, 7), pinning
`ticket.factory_manifest_hash` at S0 eligibility and enforcing it on every
later stage run (criterion 8), and every budget-abort criterion (11-19,
`runner/tests/test_budgets.py`) -- all left to the second builder working
on top of `runner/manifest.py`. `runner/stages/**`, `runner/queue.py`,
`runner/control.py`, `runner/export.py`, and `runner/checks/**` are
untouched.

# T-A-19 brief, part two: model checks, the S0 pin, and budget abort

This brief covers the second builder, working on top of the first
builder's `runner/manifest.py`. It builds criteria 6, 7, 8 and 11-19.

## What this delivers

- **Model checks (criteria 6, 7)** already exist in
  `runner/adapters/cursor_sdk.py::invoke`, built by the adapter ticket:
  the requested-model-unavailable refusal (`_refuse_unavailable_model`,
  no `stage_run` opened at all) and the resolved-model-mismatch
  classification (`_classify`, `infrastructure_failure` with no output
  registered) were already in place before this ticket started. This
  builder adds the R-I-4 proof that the *manifest-resolved* path reaches
  the same two refusals, not just a hand-built `Entry`: two new tests in
  `runner/tests/test_manifest.py` resolve the shared `valid` fixture
  manifest into a real `Entry`, then drive `cursor_sdk.invoke` against two
  new `runtime.yaml` fixtures under `runner/tests/fixtures/manifest/model_check/`
  (`unavailable_runtime.yaml` names no model the manifest's `light`/`S1`
  entry requests; `mismatch_runtime.yaml` accepts that model but points
  at the adapter suite's own `fixture_worker.py`, reused rather than
  duplicated, running its `silent_fallback` case).
- **The manifest-hash pin (criterion 8)** is two small pieces, exactly
  where the ticket brief named them:
  - `runner/gates.py::intake_gate` pins `ticket.factory_manifest_hash` to
    `manifest.current_hash()` the moment it is about to return
    `eligibility_granted`, but only when the ticket carries no pin yet.
    This is the second write exception in this module (after
    `plan_review_gate`), documented the same way.
  - `runner/stages/__init__.py::invoke_agent` -- the one seam that
    resolves a manifest entry for a real agent invocation, still unused
    by every stub driver today -- now compares the ticket's pin against
    the resolution's own `Entry.manifest_hash` before doing anything
    else, for every stage but `S0` (whose pin does not exist yet, by
    construction, until eligibility is granted). A missing or
    mismatched pin is refused as a `utility_run` of kind
    `refused_request`, naming the mismatch in `outputs`; no `stage_run`
    is ever opened for it. `invoke_agent` gained one new keyword
    parameter, `manifest_path`, defaulting to the real committed
    manifest, purely so a test can point it at a fixture tree instead.

  This placement deliberately does **not** touch `runner/stages/run_stage`
  itself: `run_stage` opens the *stub* drivers' own outer `stage_run` for
  every stage from `intake` through `checks`, and every existing test in
  `test_stub_stages.py`, `test_state_table.py`, `test_stage_interface.py`,
  `test_crash_recovery.py`, `test_report.py`, `test_outbox.py`, and
  `test_stub_walk.py` seeds tickets directly into `context` and later
  states with no pin at all, since none of them exercise a real agent
  invocation. `invoke_agent` is the one place a manifest is actually
  resolved for real work today (S1-S4 stay stubs; nothing calls it yet),
  so enforcing the pin there satisfies criterion 8's "every later stage
  run" against the one call path capable of doing agent-governed work,
  without rewriting the stub-stage suite's ticket fixtures across eight
  files for an invariant no stub stage's own behaviour depends on.
- **`runner/budgets.py`** (new) -- `check_before_invocation(conn, ticket,
  stage, tier, *, parent_run_id=None)` sums the settled tokens and
  wall-clock seconds already recorded against the invocation family about
  to grow (the run named by `parent_run_id`, if any, plus every run
  recorded under it at any depth) and compares the total to
  `run_ledger.budget(stage, tier)`; for `S4` it separately compares the
  ticket's whole `S4` history (every `stage_run` with `stage = 'S4'`,
  family boundaries aside) to `run_ledger.s4_per_ticket_budget(tier)`.
  `abort(conn, ticket, stage_run_id, *, reason)` finishes an
  already-open `stage_run` `aborted_budget`, writes one JSON escalation
  note (reasoning summary, registered outputs, the ticket's latest
  `evidence_tuple` id if one exists, the stage's prior-attempt failure
  history, and, for `S4`, `last_completed_task`/`execution_count`/
  `verification_count`) onto that run's own `reasoning_summary` --
  `queue_item.note` is a one-time field only a human resolving the item
  can set, so the escalation item's `ref` (`stage_run:<id>`) is the only
  place left for the runner's own note -- then applies `escalate` and
  opens one `escalation` queue item, the same shape `control.stop` and
  `refresh_base`'s conflict path already use.
- **`runner/adapters/cursor_sdk.py`** calls `budgets.check_before_invocation`
  immediately after opening its own `stage_run` and before building the
  envelope or launching anything; a non-`None` reason calls `budgets.abort`
  on that same run and returns an `aborted_budget` result with nothing
  else settled. A launcher timeout (`LaunchResult.timed_out`) is handled
  the same way, in place of the old `_classify` branch that used to
  report it as an ordinary `infrastructure_failure` -- wall clock is a
  budget dimension now, not a generic infrastructure fault.

## Row covered

R-I-4's model-check and pin clauses (criteria 6-8) and R-I-6 in full
(criteria 11-19), both in `docs/prd/03-stage-interface.md`.

## Owner decisions this brief follows

- **The pin check lives in `invoke_agent`, not `run_stage`.** See "What
  this delivers" above for the full reasoning; the short version is that
  `run_stage` is the stub-stage skeleton every existing test seeds
  tickets against with no pin, while `invoke_agent` is the actual,
  currently-unused seam a real agent invocation would go through.
- **The pin write lives in `intake_gate`, not `queue.act`'s `granted`
  handling.** The ticket brief names "the eligibility_granted path", and
  `intake_gate` is the one function that decides whether that event
  fires at all (`queue.act`'s `granted` action alone is not enough
  without a passing `S0` run too) -- pinning where the event is decided
  keeps the write and the decision inseparable.
- **The escalation note is JSON on the aborted run's own
  `reasoning_summary`**, not `queue_item.note`: `queue_item`'s one-time
  resolution columns (`note` included) are written exactly once, by a
  human resolving the item through `queue.act`, and a budget abort is the
  runner escalating on its own, before any human has looked at it. The
  `escalation` item's `ref` already points a reader at `stage_run:<id>`,
  so the note lands exactly where that pointer leads.
- **No `tags.tag` call on budget abort.** `refresh_base`'s own conflict
  path -- the codebase's other system-triggered escalation -- opens its
  `escalation` item and applies `escalate` with no tag at all; every
  `tags.tag(kind="escalation", ...)` call site elsewhere takes a human's
  `--fm`/`--actor` pair from `factory stop` or `factory act`. Budget
  abort has neither, so it follows `refresh_base`'s precedent rather than
  inventing a synthetic actor identity or a PRD-reference fm_id.
- **`S4`'s `last_completed_task`/`execution_count`/`verification_count`**
  are derived from `stage_run.run_kind` and `outcome` alone, since no
  dedicated task-tracking column exists yet (the real `S4` loop is a
  later ticket): `execution_count` counts every `task`/`fix_round` row,
  `verification_count` counts every `validation_only` row, and
  `last_completed_task` is the highest `attempt` among `task`/`fix_round`
  rows whose `outcome` is `pass`.
- **`check_before_invocation`'s family walk is a `parent_run_id` BFS at
  any depth**, not a single-level lookup, so a grandchild invocation (if
  one is ever opened) still counts toward the same family total as its
  grandparent; today's only real caller (`invoke_agent`'s eventual S2
  restatement) is one level deep, but nothing in the budget module
  assumes that.

## Decisions this brief did not already settle

- **`budgets.py` reads `run_ledger.TIERS_PATH` through `run_ledger.budget`/
  `run_ledger.s4_per_ticket_budget` rather than taking a `tiers.yaml` path
  of its own**, matching the same "live, hand-edited config" reasoning
  the first builder's brief already gave for `Entry.budget`. Tests that
  need a small, deterministic budget monkeypatch `run_ledger.TIERS_PATH`,
  the same idiom `test_crash_recovery.py` already uses for
  `run_ledger.process_identity`.
- **A budget-exceeded pre-check still opens the invocation's own
  `stage_run` before aborting it**, unlike the unavailable-model refusal,
  which opens none at all. The escalation item's `ref` names
  `stage_run:<id>`, and `control.stop`'s own end-a-run pattern always
  operates on a real, already-open row -- an abort with nowhere to point
  the escalation item would leave criterion 16's "the current binding...
  and failure history" with no row to hang off of.
- **`>` (strictly exceeds), not `>=`, decides a budget refusal.** A
  family sitting exactly at its budget with zero usage yet from the
  invocation about to start is not yet over it; the next boundary check,
  after that invocation's own usage settles, is what would catch it if it
  pushes the family over.

## Out of scope

The real `S4` execution loop and its task/fix-round/validation-only
lifecycle (a later ticket); a second, post-invocation budget check inside
one already-running invocation (tokens are only knowable once an
invocation's JSON comes back, so enforcement is necessarily at the
boundary between invocations, per R-I-6's own text); wiring
`check_before_invocation`/`abort` into any stub `S1`-`S4` driver, since
none of them call `invoke_agent` yet.
