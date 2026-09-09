# T-AB-01 plan

| # | Step | Files touched | Proving test |
|---|---|---|---|
| 1 | Agent and build Seatbelt profiles: mount/writability/egress rules, `(import "system.sb")` for the host's process-exec crash, a `literal` `REPO_ROOT` grant for the editable-install `.pth`. | `factory/config/sandbox/agent-profile.sb`, `factory/config/sandbox/build-profile.sb` | `runner/tests/test_sandbox.py`, `runner/tests/test_escape_suite.py` |
| 2 | `factory/config/sandbox.yaml` rewritten under the `enforced` policy name: `os_profiles` (path + digest), `endpoints`, `proxy_allowlist` per stage, `copies.location`. | `factory/config/sandbox.yaml` | `runner/tests/test_sandbox.py` |
| 3 | `runner/sandbox/os_policy.py`: `profile_for`, `digest`, `wrap`, `available`. | `runner/sandbox/os_policy.py` | `runner/tests/test_sandbox.py` |
| 4 | `runner/sandbox/proxy.py`: one `CONNECT`-tunnelling HTTP server per run, `POST /routes/<id>` reserved (404 for now). | `runner/sandbox/proxy.py` | `runner/tests/test_sandbox.py` |
| 5 | `runner/sandbox/copies.py`: `provision`, `dispose`, `recheck`, `provisioned`. | `runner/sandbox/copies.py` | `runner/tests/test_sandbox.py`, `runner/tests/test_escape_suite.py` |
| 6 | `runner/launcher.py` rewritten: applies `os_policy.wrap`, starts/stops the proxy, records `os_policy` in `exit.json`, the `runtime_key` env name literal, `stage`/`ticket_dir`/`worktree_path`/copy-path parameters. | `runner/launcher.py` | `runner/tests/test_sandbox.py`, `runner/tests/test_escape_suite.py`, `runner/tests/test_adapter.py` |
| 7 | `runner/envelope.sandbox_digest` rewritten to take `stage`/`runs_dir` and hash the OS profiles, resolved proxy allowlist, and runs-directory location together; `envelope.build` threads `runs_dir` through. | `runner/envelope.py` | `runner/tests/test_sandbox.py`, `runner/tests/test_adapter.py` |
| 8 | `cursor_sdk.invoke`: fetch `runtime_key` via `credentials.fetch` at the moment of launch when admitted, `CREDENTIAL_RUN` module constant, `_credential_unavailable_result`, launcher call gains `stage`/`ticket_dir`/`worktree_path`. | `runner/adapters/cursor_sdk.py` | `runner/tests/test_sandbox.py` |
| 9 | `runtime.yaml`'s `runtime_key` entry (`role`, `scope`, `spend_cap`, `rotation`). | `factory/config/runtime.yaml` | `runner/tests/test_sandbox.py` |
| 10 | Rename `sandbox_policy` from `thin` to `enforced` everywhere: manifest stage entries, manifest test fixtures, the adapter test-sandbox fixture, `plan_tuple.py`, docstrings. | `factory/manifest.yaml`, `runner/tests/fixtures/manifest/*/factory/manifest.yaml`, `runner/tests/fixtures/adapter/sandbox.yaml`, `runner/plan_tuple.py`, `runner/adapters/cursor_sdk.py`, `runner/adapters/cursor_sdk_worker.py`, `runner/launcher.py` | full suite |
| 11 | `runner/evals.py`: `expected_eval_dirs` gains `evals/sandbox/escape` when `config/sandbox/` holds profiles. | `runner/evals.py` | `runner/tests/test_manifest_eval_walk.py` (the real-tree case) |
| 12 | The escape suite: `eval.yaml` (eleven categories, `expect: reject`, plus one `ok` control) and one standalone `probe.py` per category. | `factory/evals/sandbox/escape/eval.yaml`, `factory/evals/sandbox/escape/fixtures/*/probe.py` | `runner/tests/test_escape_suite.py` |
| 13 | `runner/tests/test_escape_suite.py`: fails at collection when `os_policy.available()` is false; one test per category launched through the real profiles; a coverage test naming every category. | `runner/tests/test_escape_suite.py` | itself |
| 14 | `runner/tests/test_sandbox.py` rewritten for the enforced policy: profile shape, digests, proxy allowlist resolution, copy location, `os_policy` applied/recorded, digest-differs-from-before, manifest sandbox-policy shape and credential admission, credential-value-never-stored, `runtime.yaml`/`trust-profile.yaml` assertions, proxy start/allowlist/routing, copies provision/dispose/recheck, read-only registered inputs, `results/` read-only, `factory/`/`runs/factory.sqlite` unreachable. | `runner/tests/test_sandbox.py` | itself |
| 15 | A frozen pre-enforcement `sandbox.yaml` fixture, comment stripped of any row id, for the digest-differs test. | `runner/tests/fixtures/sandbox/thin_before/sandbox.yaml` | `runner/tests/test_sandbox.py` |
| 16 | Mechanical fix for the shared execution-boundary seam's already-broken `Entry` construction, outside this ticket's ownership but blocking the whole suite. | `runner/tests/test_adapter.py`, `runner/tests/test_budgets.py` | those files' own existing tests, now green |
| 17 | `runner/tests/conftest.py`: patch `cursor_sdk.CREDENTIAL_RUN` to a fake, successful Keychain lookup for the whole suite. | `runner/tests/conftest.py` | every test that reaches `stages.invoke_agent` for an agent stage |
| 18 | This ticket's own brief and plan. | `docs/build/T-AB-01/brief.md`, `docs/build/T-AB-01/plan.md` | reviewed by the human, not a test |
| 19 | Bootstrap fixture sync and manifest refresh. | `factory/evals/bootstrap/T-AB-01/`, `factory/evals/bootstrap/eval.yaml`, `factory/manifest.yaml` | `runner/tests/test_bootstrap_fixtures.py`, `runner/tests/test_manifest_hash.py` |

## Test strategy

`test_sandbox.py` proves the structural pieces once each: the profile
files exist and are valid Seatbelt profiles (`os_policy.available()`),
`sandbox.yaml`'s digests equal the profiles' own content hash, the proxy
allowlist resolves route/host/port per stage, the disposable-copy location
string, the launcher records `os_policy` true/false correctly for a
policy that does/doesn't name `os_profiles`, the sandbox digest changes
both from its pre-enforcement value and with the stage/runs-directory
inputs, the manifest's `sandbox_policy` shape and per-stage credential
admission, a credential value's absence from every row/artefact/file the
whole invocation touches (a fake `security` call returns a known secret,
then the test scans the database and every file under the run directory
for it), a `CredentialUnavailable` fetch landing as
`infrastructure_failure`/`infrastructure` rather than a crash, the proxy
starting on `127.0.0.1` with its port reaching the sandbox via
`HTTPS_PROXY`, the proxy admitting only its own allowlist (a real
loopback listener the test opens itself, allowed and refused ports both
attempted), `copies.provision`/`dispose`/`recheck`/`provisioned`
(including the crash path), registered-input read-only-ness, and
`factory/`/`runs/factory.sqlite` unreachability from both roles. Several
of these run a tiny inline Python probe script through the real,
committed profiles via `launcher.launch` -- not a stand-in profile --
since criteria 1, 2, 6, 20-23 are claims about what the real profile
actually enforces.

`test_escape_suite.py` is the exhaustive per-category proof the ticket's
own acceptance criteria demand: `os_policy.available()` gates the whole
module at import time (`pytest.fail`, not a skip) so a host where
`sandbox-exec` cannot run the agent profile fails loudly rather than
silently passing nothing. Every probe is copied out of its eval-directory
fixture into the run's own `tmp/` (the one path both profiles grant read
access to without granting it to `factory/` itself) and launched for
real. `base-head-isolation`'s probe writes into the base copy under a
build-role sandbox scoped only to that copy, then tries to read the same
relative path under the head copy -- refused proves the sandbox itself
never mounts the sibling copy, not merely that two APFS clones happen to
be independent files. `copy-disposal`'s probe only proves the write
succeeds (`expect: ok`); the test's own assertions, run outside the
sandbox after `copies.dispose`, prove both copy directories are gone.
`credentials`' probe checks three signals together (`SSH_AUTH_SOCK`
absence, `~/.aws/credentials` unreadability, and `security
find-generic-password`'s stdout carrying no value) since this host has no
real Keychain item under the `soft-factory` service and the probe cannot
distinguish "denied by the sandbox" from "simply not found" through the
legacy Keychain CLI's own exit behaviour -- documented in the probe's own
docstring rather than claimed as more than it proves.

## Known simplifications

- The build profile's registry endpoint (`pypi.org:443`) and the agent
  profile's hosted-inference endpoint (`api.cursor.sh:443`) are both
  explicit placeholder choices (see the brief's owner-decisions section),
  not values read from a live route negotiation -- correcting either
  later is a one-line change to `sandbox.yaml`'s `endpoints` block, since
  every stage's proxy allowlist resolves through it rather than naming a
  host directly.
- Criterion 22's "the directory is destroyed with the run's other
  disposable state" is only proven for the digest-binding half (the runs
  directory's resolved location changes the digest, per
  `test_sandbox_digest_changes_with_the_stage_and_with_the_runs_directory`);
  nothing in this ticket's ownership list actually deletes a finished
  run's `run_dir` -- no file under `runner/` outside `runner/sandbox/` and
  `runner/launcher.py` is this ticket's to change, and none of those
  currently disposes of `runs/tickets/<id>/runs/<stage_run_id>/` on a
  successful run.
