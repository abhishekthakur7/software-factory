# T-AB-02 plan

| # | Step | Files touched | Proving test |
|---|---|---|---|
| 1 | `os_policy.wrap` refuses a mount-parameter value that resolves to the host home directory, before it ever builds a `sandbox-exec` argv. | `runner/sandbox/os_policy.py` | `runner/tests/test_capability_boundary.py` (criterion 15, mount surface) |
| 2 | The agent profile's `TICKET_DIR` grant is replaced with eight named `INPUT_n` slots, each a single registered artefact path read from the run's own `locations.json`; unused slots default to the already-writable `TMPDIR` placeholder. `sandbox.yaml`'s agent digest is recomputed. | `factory/config/sandbox/agent-profile.sb`, `factory/config/sandbox.yaml` | `runner/tests/test_escape_suite.py` (criteria 16, 17); `runner/tests/test_sandbox.py` (unowned, digest-equality test) stays green |
| 3 | `launcher.py`: `_registered_input_params` reads `<run_dir>/locations.json` if present and builds the eight `INPUT_n` params; wired into `_sandbox_params`. | `runner/launcher.py` | `runner/tests/test_escape_suite.py` |
| 4 | The `unregistered-file` escape category: a probe that reads a file placed beside a registered artefact under the ticket directory, plus its `eval.yaml` case. | `factory/evals/sandbox/escape/fixtures/unregistered-file/probe.py`, `factory/evals/sandbox/escape/eval.yaml` | `runner/tests/test_escape_suite.py` |
| 5 | `test_capability_boundary.py`: criteria 1-8 -- undeclared tool (DB-level and sandbox-level), source write refused outside S4 and allowed at S4, build-profile worktree write refused, path traversal and symlink escape, the S4 hand-back's shell-string `validation_recipe` refused before dispatch, ambient credential absence under a non-agent sandbox, `git push` refused from inside a sandbox, and `stage_run.tool_allowlist` set before `launcher.launch` is ever called. | `runner/tests/test_capability_boundary.py`, `runner/tests/fixtures/capability_boundary/*` | itself |
| 6 | `test_stub_walk.py`: criteria 9-14 -- the forbidden-capability set (GitHub merge/push/approval/rerun via the route-id grep, arbitrary shell and arbitrary network client via real probes), source-tree write only at S4 (shared probes with step 5), S5's disposable-layer boundary, the GitHub/Slack route-id grep test, and S1's no-write boundary. | `runner/tests/test_stub_walk.py`, `runner/tests/fixtures/capability_boundary/*` | itself |
| 7 | `test_stub_walk.py`: criterion 15 -- six hidden-capability injections (manifest, runtime configuration, recipe, mount, environment, credential), each at the smallest real boundary that owns it. | `runner/tests/test_stub_walk.py`, `runner/tests/fixtures/capability_boundary/hidden/*` | itself |
| 8 | Manifest refresh for every new file under `factory/` and the two edited profile/policy files. | `factory/manifest.yaml` | `runner/tests/test_manifest_hash.py`, `runner/tests/test_manifest.py` (unowned, stay green) |
| 9 | This ticket's own brief and plan. | `docs/build/T-AB-02/brief.md`, `docs/build/T-AB-02/plan.md` | reviewed by the human, not a test |

## Test strategy

`test_capability_boundary.py` launches every probe for real through
`runner.launcher.launch`, most via `runner/tests/support.py`'s
`launch_probe`; the two tests that need a run-specific `locations.json`
on disk before the child starts (the unregistered-file proof lives in
`test_escape_suite.py`, but the `stage_run.tool_allowlist`-before-launch
proof needs the real `cursor_sdk.invoke` call graph) build their own
`run_dir` layout or patch `launcher.launch` directly rather than
extending the shared helper's signature. Every probe prints one JSON
line `{"attempted": ..., "refused": ...}`; a probe that succeeds where it
must be refused fails the test with that line in the message, never
silently.

`test_stub_walk.py`'s six hidden-capability tests each build the
smallest real setup that reaches the boundary owning that surface: a
committed two-hash manifest pair for the manifest surface (mirroring
`test_manifest.py`'s own `_committed_copy` convention, but under this
ticket's own fixture directory), a tampered `runtime.yaml` adapter
command run through the real fixture worker for the runtime-configuration
surface, a tampered `command-recipes.yaml` entry for the recipe surface,
a `$HOME`-pointing mount parameter for the mount surface, a real
sandboxed probe for the environment surface, and a resolved `Entry` with
an empty `credential_roles` set for the credential surface, driven
through `cursor_sdk.invoke` with a `credential_run` stand-in that raises
if it is ever called at all.

`test_escape_suite.py`'s `unregistered-file` case places two files in a
ticket directory, registers only one through `artefact_registry.register`,
writes the resulting `locations.json` a real invocation would produce,
and launches a probe under the agent profile that can read the
registered file back but is refused on the unregistered one -- proving
both `artefact_registry.latest` (a database-level check) and the
sandbox's own mount (an OS-level check) agree that an unregistered file
never becomes a registered input.
