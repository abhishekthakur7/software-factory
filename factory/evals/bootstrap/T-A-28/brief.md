# T-A-28 brief: S4 hand-off and hand-back artefacts, deviation rows

## What this delivers

`runner/stages/S4.py` stops being a stub. Three separate functions, kept
apart because a later ticket turns this single whole-plan invocation into
one run per plan task while reusing the same hand-off and hand-back
shapes:

- `build_handoff` reads the ticket's latest `plan`-kind `evidence_tuple`
  row and its registered `plan`/`criteria` artefacts, derives the task
  list, the scope table, and the plan's blind spots (readiness rows of
  status `blind_spot` plus any `Contracts` field cell marked `unknown`)
  from the plan's own tables, and writes `handoff.json` as canonical JSON
  into the attempt's run directory, registered as artefact kind
  `handoff`. Nothing here reads the S3 transcript or any credential.
- `run` hands off, makes one `stages.invoke_agent` call (a child of the
  attempt), and on a passing invocation calls `record_handback` against
  the child's `out/`.
- `record_handback` reads `out/handback.json`, validates its deviation
  set against the `deviation` schema (`kind` in `judgment`/`error`,
  `contract_change` a bool), and only once that passes: commits the
  ticket worktree under a fixed runner identity (`git_trees.
  commit_worktree`), writes `ticket.branch`/`head_sha`/`worktree_path`,
  inserts one `deviation` row per item, and records a `handback_structure`
  `check_result` whose summary carries the canonical deviation-set hash
  (`binding.deviation_set_hash`, which recomputes from the very rows just
  inserted) and the row count. A missing file, a missing `deviations` key,
  or one row outside the schema returns `("fail", "structural")` before
  any of that -- never a partial hand-back, never a `red_check` item, and
  never waivable; the ordinary fresh rerun applies.

Two small additions elsewhere carry the runner's side of the hand-back
contract: `git_trees.commit_worktree` (the one place S4 makes a git
commit -- the agent never runs git) and `binding.deviation_set_hash` (the
set hash S5 will later bind into the review tuple).

## Files touched (ownership list)

- `runner/stages/S4.py` -- rewritten: `build_handoff`, `record_handback`, `run`.
- `runner/git_trees.py` -- `commit_worktree`.
- `runner/binding.py` -- `deviation_set_hash`.
- `runner/tests/fixtures/adapter/fixture_worker.py`, `sandbox.yaml` -- a
  `FIXTURE_ADAPTER_WORKTREE_DIR` env name the fixture worker uses to stand
  in for the agent's own worktree edits.
- `factory/agents/S4.md` -- short edit naming `out/handback.json` and that
  the runner commits.
- `factory/evals/agents/S4/` -- `ok/out/handback.json`, `ok/worktree/`,
  `empty_deviations/`, `missing_deviations/`, `malformed_deviations/`,
  `no_handback/`, and matching `eval.yaml` cases.
- `factory/manifest.yaml` -- hashes refreshed.
- `runner/tests/test_s4_handoff.py`, `runner/tests/fixtures/s4_handoff/` --
  criteria 1-10.
- `runner/tests/test_s4_handback.py` -- criteria 11-15.
- `runner/tests/test_stub_walk.py`, `runner/tests/fixtures/stub_walk/tables.yaml` --
  the S4 step now runs for real; `deviation` added to the walk's table list.
- `docs/build/T-A-28/brief.md`, `docs/build/T-A-28/plan.md` -- this pair.

## Design decisions the brief left open

- **Blind-spot shape.** `handoff.json`'s `blind_spots` list carries two
  kinds of entry, tagged by `source`: a `readiness` entry (`condition`,
  `waiver_id`, `note`) and a `contract` entry (`unit`, `field`, `note`).
  Neither the ticket nor the PRD row fixes a shape; this one keeps every
  field a reviewer would need to find the row that produced it, and
  nothing else.
- **`validation_args` typing.** Parsed as space-separated `key=value`
  tokens; a value is `true`/`false` as a bool, else an int, else a float,
  else the original string. No richer grammar exists yet at S3's own
  structure-check level (it only forbids shell syntax), so this is the
  simplest typed reading of what that check already guarantees is safe.
- **Deviation-row validation.** A `handback.json` item is accepted only
  when its key set is exactly the six agent-facing fields, `kind` is one
  of `schema.DEVIATION_KINDS`, `contract_change` is a JSON boolean, and
  the four text fields are strings. An extra or missing key is treated as
  malformed rather than tolerated, matching "refuse loudly" over a lax
  default -- the shape is small and fixed, so there is no partial-conformance
  case worth accepting.
- **`plan_tuple_id` reading.** `build_handoff` reads the ticket's latest
  `plan`-kind `evidence_tuple` row directly by SQL, exactly as the common
  brief for this wave directs, rather than through any tuple-selection
  module -- none exists yet in this worktree.
- **Structural pre-flight ownership.** "No plan tuple or no plan artefact"
  is checked in `run`, not `build_handoff`: the latter's contract is a
  plain `-> int`, so a driver-level guard before it runs keeps that
  contract intact and matches where `S3.py` places its own equivalent
  check.
