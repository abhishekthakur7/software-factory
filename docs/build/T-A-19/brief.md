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
