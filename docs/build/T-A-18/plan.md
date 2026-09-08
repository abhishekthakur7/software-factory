# T-A-18 plan

## Steps

| # | Step | Files touched | Proves |
|---|---|---|---|
| 1 | `stage_run.envelope_hash`, `replayability`, `replayability_blind_spot` added; every field a runtime adapter learns after the row opens marked `mutable=True`. `USER_VERSION` bumped. | `runner/schema.py`, `runner/db.py` | criteria 6, 22, 24, 26, 27 |
| 2 | `run_ledger.record_invocation`: the one write path for those fields. | `runner/run_ledger.py` | criteria 7, 8-15, 22, 24-28 |
| 3 | Mutable-exception allowlist extended for `stage_run`. | `runner/tests/test_mutable_exceptions.py` | criterion 22 (allowlist sweep) |
| 4 | `envelope.py`: `Envelope`, `build`, `reconstruct`, `content_hash`, `sandbox_digest`, `toolchain_digest`, `recipe_set_hash`. | `runner/envelope.py` | criteria 2, 3, 6, 24-28 |
| 5 | `launcher.py`: `launch`, the allowlist-only child environment, per-role credential injection, codegraph start, `out/`/`results/`, sandbox-integrity check, `terminate_child`. | `runner/launcher.py` | criteria 18-23 |
| 6 | `factory/config/{limits,pricing,sandbox,runtime}.yaml`. | `factory/config/*.yaml` | criteria 8-11, 17, 18, 20, 21 |
| 7 | `adapters/cursor_sdk_worker.py`: the untrusted child, one JSON document, `setting_sources=[]`. | `runner/adapters/cursor_sdk_worker.py` | criteria 1, 4 |
| 8 | `adapters/cursor_sdk.py`: `invoke`, the model checks, tool-call recording, output registration, replayability, cost settlement. | `runner/adapters/cursor_sdk.py` | criteria 1, 5, 7-17, 24-28 |
| 9 | `control.stop` kills the launcher's child before finishing each open run. | `runner/control.py` | owner decision, not a numbered criterion |
| 10 | The seam: `stages.invoke_agent`. | `runner/stages/__init__.py` | owner decision ("Wiring"), not a numbered criterion |
| 11 | Fixture worker, test copies of `runtime.yaml`/`sandbox.yaml`. | `runner/tests/fixtures/adapter/**` | every criterion below |
| 12 | `test_adapter.py`: criteria 1-17, 24-28. | `runner/tests/test_adapter.py` | criteria 1-17, 24-28 |
| 13 | `test_sandbox.py`: criteria 18-23. | `runner/tests/test_sandbox.py` | criteria 18-23 |
| 14 | Adoption-gate eval directory. | `factory/evals/adapters/cursor_sdk/**` | criteria 1, 13, 16 |
| 15 | `cursor-sdk` dependency added, pinned. | `pyproject.toml`, `uv.lock` | package availability |
| 16 | New files appended to `factory/manifest.yaml`'s `files:` list. | `factory/manifest.yaml` | manifest hash validity |
| 17 | This ticket's own brief and plan. | `docs/build/T-A-18/brief.md`, `docs/build/T-A-18/plan.md` | reviewed by the human, not a test |

## Test strategy

`test_adapter.py` and `test_sandbox.py` both drive
`adapters.cursor_sdk.invoke`/`runner.launcher.launch` against the fixture
worker under `runner/tests/fixtures/adapter/fixture_worker.py`, chosen by
`FIXTURE_ADAPTER_CASE` (or, for the eval-directory walk,
`FIXTURE_ADAPTER_PAYLOAD_PATH` naming a canned JSON file directly) --
never the real Cursor SDK, so the suite runs no network. Every case's
`model_resolved` matches its entry's bare `model_requested` exactly except
two built to differ on purpose (`silent_fallback`: a different model
family; `error`: no model at all) and one (`settled_pinned_build`) whose
resolved id carries an immutable build suffix while its own test's
`model_requested` matches it exactly, isolating "exact" replayability from
the mismatch check.

Cost-basis criteria (8-11) are four direct tests reading `stage_run.cost*`
after one `invoke` call each. Tool-call criteria (14, 17) use a fixture
with one small and one 500-line result, asserting `inline`/
`result_artefact` on each row and that the large one's excerpt file names
its first and last lines. Governance-binding (25) seeds a `plan`-kind
`evidence_tuple` and asserts the written envelope's `approval_subject_hash`
for `S3`, and asserts it null for `S1`. Replayability (26) has two direct
cases: a bare model id (no build suffix) and a fixture-declared
`retention_blind_spot`. Reconstruct-equality (6, 24) invokes once, then
calls `envelope.reconstruct` on the same `stage_run_id` and asserts every
hash/version field the row stored matches what `reconstruct` recovers.
Sandbox criteria (18-23) assert `LaunchResult.integrity`'s reported
`environment_names`/`codegraph_started` directly, plus one full-adapter
test tying a reported violation to `stage_run.outcome`/`failure_kind`.
`test_must_reject_unavailable_model_before_any_run_is_opened` asserts zero
`stage_run` rows exist after a refused invocation.

## Verification

`uv run pytest -q --deselect runner/tests/test_manifest_hash.py`
(deselected because the committed-bytes check in that file fails against
an uncommitted `factory/manifest.yaml` edit in this worktree; rerun
without the deselect after committing to confirm it passes against the
committed bytes).
