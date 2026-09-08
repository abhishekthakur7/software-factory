# T-A-19 plan, part one: the manifest's full field set, fail-closed resolution, and migration

Covers criteria 1, 2, 3, 4, 5, 9, 10. Criteria 6-8 and 11-19 are marked
"second builder" below and left untouched by this plan.

## Steps

| # | Step | Files touched | Proves |
|---|---|---|---|
| 1 | `Manifest`/`Entry` dataclasses; `load(path)` parses `files` and every stage's `default`/tier entries: known-field check, required-field check on `default`, field-type check, referenced-file-in-`files` check, the null/non-null invariant, and the `tiers.yaml` budget-key sweep. | `runner/manifest.py` | criteria 1, 2, 3, 4, 5 |
| 2 | `resolve(manifest, stage, tier)`: merges `default` with a tier override, re-checks the null invariant, re-hashes every referenced file against `files`, reads the live budget dict, and calls `current_hash` for `Entry.manifest_hash`. Takes no `conn`. | `runner/manifest.py` | criteria 2, 5 |
| 3 | `current_hash(root)`: subprocess call to `factory/scripts/tools/manifest_hash --root`, its stdout/stderr passed straight through as the result or the `ManifestError`. | `runner/manifest.py` | supports criteria 2, 9 |
| 4 | `migrate(conn, *, actor, note, root, owners_path)`: records one `manifest`-gate approval (`approve` iff `actor` holds `factory_owner` in `owners.yaml`, else `reject`), evaluates the lone-slot quorum, and on success walks every non-terminal ticket whose hash differs, writing one `manifest_migration` `check_result` naming its `S1`-onward artefact ids, applying `migrate_manifest`, and re-pinning the hash. | `runner/manifest.py` | criteria 9, 10 |
| 5 | `"manifest"` added to `APPROVAL_GATES`; `USER_VERSION` bumped. | `runner/schema.py`, `runner/db.py` | criterion 10 (schema support) |
| 6 | `migrate-manifest` verb: `--actor` required, `--note` optional, thin wrapper over `manifest.migrate`. | `runner/cli.py` | criterion 10 (the one verb) |
| 7 | Full per-stage field set for `S0`-`S6` in the real manifest; the stale duplicated `content_hash:` line under `trust-profile.yaml` deleted. | `factory/manifest.yaml` | criteria 1, 4 |
| 8 | Six self-contained fixture trees plus a shared `owners.yaml`. | `runner/tests/fixtures/manifest/**` | criteria 1, 2, 3, 4, 5, 9, 10 |
| 9 | `test_manifest.py`: one or more tests per criterion, `must_reject` naming on every negative fixture and the non-quorum migration path. | `runner/tests/test_manifest.py` | criteria 1, 2, 3, 4, 5, 9, 10 |
| 10 | This ticket's brief and plan (both note the second builder's share). | `docs/build/T-A-19/brief.md`, `docs/build/T-A-19/plan.md` | reviewed by the human, not a test |

## Test strategy

Every fixture directory under `fixtures/manifest/` is copied into
`tmp_path` and, wherever a test needs `resolve` or `current_hash`
(neither of which will run over an uncommitted tree, by design), given a
fresh `git init`/`add`/`commit` -- the same `_committed_copy` helper
`test_manifest_hash.py`'s own `_build_repo` inspired. `load`-only tests
skip the git step entirely, since `load` never shells out.

Criterion 1 loads the real committed manifest and walks every stage's
`default` entry for the full required-field set, plus `S2`'s
`restatement_model` and its absence everywhere else. Criterion 5 pairs a
`must_reject` load of `missing_required_field` (asserting the exact
"missing field" message) with a second test proving the same failure
leaves `stage_run` at zero rows in a real database -- the closest a
`conn`-free module can come to demonstrating "no stage run opens on a
resolution failure" directly. Criterion 2 resolves the `valid` fixture and
checks `Entry`'s file hashes and `manifest_hash` against the manifest's
own `files` map and `current_hash`, then separately proves a tampered
on-disk file and a range-shaped `runtime_version` each fail closed.
Criterion 3 loads the real manifest (proving its live `tiers.yaml` budget
keys are clean) and rejects `invalid_budget_key`'s injected
`requests_per_minute` key. Criterion 4 asserts the null/non-null split
both ways on the real manifest and rejects `non_null_agent_on_s5`.

Criteria 9 and 10 share `migration_seed`: a ticket in `implementing` with
one `S0`, one `S1`, and one `S2` stage run, each with a registered
artefact. `migrate(actor="abhishek", ...)` (the identity `owners.yaml`
gives `factory_owner`) moves the ticket to `context`, re-pins its hash,
and writes a `check_result` whose summary names exactly the `S1` and `S2`
artefact ids, in id order -- never the `S0` one. A second test calls
`migrate` with an actor `owners.yaml` does not name as `factory_owner`,
naming it `test_must_reject_...`: the ticket's state and hash are
untouched, and the recorded `approval_record` carries `decision =
"reject"`. A third test proves a terminal ticket (`abandoned`) is never
touched by a migration even when its hash differs, closing the
"non-terminal" half of criterion 9's "every open ticket" language that
the quorum test alone does not cover.

## Verification

`uv run pytest -q` -- `runner/tests/test_manifest_hash.py`'s
committed-bytes check is expected to fail until `factory/manifest.yaml`
is committed; rerun it alone after committing to confirm. The second
builder adds `runner/tests/test_budgets.py` on top of this module and is
not part of this plan's verification.

# T-A-19 plan, part two: model checks, the S0 pin, and budget abort

Covers criteria 6, 7, 8, 11-19.

## Steps

| # | Step | Files touched | Proves |
|---|---|---|---|
| 1 | Two new `runtime.yaml` fixtures (`unavailable_runtime.yaml`, `mismatch_runtime.yaml`) naming no model and a mismatching model respectively, reusing the adapter suite's `fixture_worker.py`. | `runner/tests/fixtures/manifest/model_check/**` | criteria 6, 7 |
| 2 | Two tests resolving the shared `valid` manifest fixture into a real `Entry`, then driving `cursor_sdk.invoke` against each new runtime fixture. | `runner/tests/test_manifest.py` | criteria 6, 7 |
| 3 | `gates.intake_gate` pins `ticket.factory_manifest_hash` to `manifest.current_hash()` the first time it is about to return `eligibility_granted`. | `runner/gates.py` | criterion 8 (pin write) |
| 4 | `stages.invoke_agent` gains a `manifest_path` parameter and, for every stage but `S0`, refuses (one `refused_request` `utility_run`, no `stage_run`) when the ticket's pin is missing or no longer matches the resolution's own `Entry.manifest_hash`. | `runner/stages/__init__.py` | criterion 8 (pin enforcement) |
| 5 | Five tests: no pin, a stale pin, a matching pin (a script-only stage, so no adapter setup is needed), `S0`'s own exemption, and `intake_gate`'s pin write itself. | `runner/tests/test_manifest.py` | criterion 8 |
| 6 | `runner/budgets.py`: `check_before_invocation` (family walk over `parent_run_id` plus, for `S4`, the ticket's whole `S4` history) and `abort` (finish `aborted_budget`, write the JSON escalation note onto `reasoning_summary`, `escalate`, open one `escalation` item). | `runner/budgets.py` | criteria 11, 12, 14, 15, 16, 17, 18 |
| 7 | `cursor_sdk.invoke` calls `check_before_invocation` right after opening its own `stage_run` and before building the envelope; a launcher timeout calls `abort` in place of the old `_classify` infrastructure-failure branch. | `runner/adapters/cursor_sdk.py` | criteria 11, 12, 13, 14 |
| 8 | A tiny fixture `tiers.yaml`, monkeypatched over `run_ledger.TIERS_PATH`, so a family can be pushed over budget with a handful of tokens. | `runner/tests/fixtures/budgets/tiers.yaml` | test determinism for criteria 11, 12, 15 |
| 9 | Direct `check_before_invocation` tests (family-over-budget, family-under-budget, S4-cumulative-over, S4-cumulative-under, child-counts-toward-parent) plus two `cursor_sdk.invoke` integration tests (a real launcher timeout, an S4 pre-check abort before any launch). | `runner/tests/test_budgets.py` | criteria 11, 12, 13, 14, 15 |
| 10 | `abort` tests: the escalation note's every field (outputs, binding, failure history, S4 progress), worktree isolation, and proof that no new `stage_run` opens and `verification_attempt` is untouched. | `runner/tests/test_budgets.py` | criteria 16, 17, 18 |
| 11 | A `reapproval` fixture (a copy of `valid`); a test that edits `tiers.yaml`'s S4 budget and its manifest-declared hash, commits, and proves `invoke_agent` refuses the old pin until `manifest.migrate` re-pins it. | `runner/tests/fixtures/manifest/reapproval/**`, `runner/tests/test_budgets.py` | criterion 19 |
| 12 | This ticket's brief and plan, part two. | `docs/build/T-A-19/brief.md`, `docs/build/T-A-19/plan.md` | reviewed by the human, not a test |

## Test strategy

Criteria 6 and 7 reuse the first builder's `valid` fixture manifest for
the `Entry`, varying only a `runtime.yaml` the two new fixtures name --
proving the manifest-resolution path reaches the same refusals
`test_adapter.py` already pins with a hand-built `Entry`, without
duplicating the fixture worker script that plays the runtime.

Criterion 8's tests all drive `stages.invoke_agent` directly against a
`manifest_path` pointed at the committed `valid` fixture copy, using `S5`
(a script-only stage) for the matching-pin and `S0`-exemption cases so no
adapter/runtime setup is needed to prove the pin logic alone; the
mismatch and missing-pin cases assert zero `stage_run` rows exist
afterward, the same "no stage_run" proof `test_resolution_failure_opens_no_stage_run`
already uses for `manifest.load`.

Criteria 11-18 split into direct unit tests of `budgets.check_before_invocation`/
`abort` (fast, deterministic, seeded `stage_run` rows and a monkeypatched
`TIERS_PATH`) and two integration tests through `cursor_sdk.invoke` proving
the actual wiring: a real launcher timeout (fixture worker's `timeout`
case, a one-second budget so the test stays fast) and an S4 pre-check
abort that never reaches the launcher at all (asserted by zero `tool_call`/
`artefact` rows). Criterion 15's child-counts-toward-parent case seeds a
parent and a `parent_run_id`-linked child directly, since no real driver
opens a child run yet. Criterion 19 edits a fixture `tiers.yaml`'s S4
budget and updates only its own `content_hash` entry inside
`manifest.yaml` ("recompute nothing else"), so `current_hash()`'s hash of
the committed `manifest.yaml` file changes for exactly the reason the
criterion describes, then proves the old pin is refused and a fresh
`manifest.migrate` re-pins it into a passing state.

## Verification

`uv run pytest -q` -- 784 passed, 1 skipped (baseline 765 passed, 1
skipped, plus 7 new tests in `test_manifest.py` and 12 new tests in
`test_budgets.py`).
