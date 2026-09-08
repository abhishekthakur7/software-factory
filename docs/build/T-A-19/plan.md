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
