# T-AB-01 brief: the OS-enforced sandbox, the loopback proxy, copy-on-write copies, credential roles, the escape suite

## What this delivers

Every agent invocation and every build recipe now runs inside a real,
OS-enforced Seatbelt boundary rather than the launcher-built environment
allowlist alone. Two profiles, `factory/config/sandbox/agent-profile.sb`
and `build-profile.sb`, are applied through `sandbox-exec` from
`runner/launcher.py` via the new `runner/sandbox/os_policy.py`: the agent
profile mounts the ticket's registered inputs and (only at S4) its
worktree, writes only to the run's own `out/`, and admits only loopback
network; the build profile writes only to a copy and its disposable
build/scratch/cache directories, execs only the project's own recipe
scripts and the interpreter/JDK they shell out to, and carries no
credential. `factory/` and `runs/factory.sqlite` are unreachable from
inside either.

A loopback proxy (`runner/sandbox/proxy.py`) is the sandboxed child's only
path to the network: one `CONNECT`-tunnelling HTTP server per run, bound
to an OS-chosen port on `127.0.0.1`, admitting only the host-and-port
pairs `sandbox.yaml`'s `proxy_allowlist` names for the run's stage. The
launcher starts and stops it around every launch and injects
`HTTPS_PROXY`/`HTTP_PROXY`/`FACTORY_PROXY_PORT` into the child's
environment.

`runner/sandbox/copies.py` provisions S5's base and head checkouts as
APFS clones (`cp -c -R`) of the immutable checkouts, each with empty
`target`/`scratch`/`cache` directories a recipe may write into; `dispose`
removes the whole per-run copies directory (via a `provisioned` context
manager that disposes on the crash path too); `recheck` proves the
immutable checkout underneath is still exactly the commit and diff it
was.

`runner/adapters/cursor_sdk.py`'s `invoke` now fetches the scoped runtime
key through `credentials.fetch("runtime_key")` at the moment of launch,
only when the resolved entry's `credential_roles` admits it, and hands it
straight to `launcher.launch`; a Keychain miss is recorded as an
`infrastructure_failure`/`infrastructure` outcome on a real, finished
`stage_run`, never a crash. `runtime.yaml` gains a `runtime_key` entry
(`role`, `scope`, `spend_cap`, `rotation` -- never a `value`); the
`hosted_model` route in `trust-profile.yaml` already carried
`credential_role: runtime_key` from the shared execution-boundary seam,
so this ticket only writes the test that proves it.

`runner/envelope.sandbox_digest` now hashes, in one payload, both OS
profile files, the stage's resolved proxy allowlist (route/host/port
triples), `sandbox.yaml`'s own bytes, the resolved environment allowlist,
and the runs directory's resolved location -- a value that provably
differs from what the same function produced over the pre-enforcement
`sandbox.yaml`.

The escape suite (`runner/tests/test_escape_suite.py`,
`factory/evals/sandbox/escape/`) proves all of this for real on this host,
never through a fake: eleven categories (paths, symlinks, subprocesses,
environment, sockets, network, mounts, base-head-isolation,
source-immutability, copy-disposal, credentials) plus one positive control,
each launched through the real, committed profiles via `launcher.launch`.
The suite fails outright at collection, rather than skipping, when
`os_policy.available()` is false on the host running it.

Row covered: R-I-14.

## Owner decisions this ticket made

- **`(import "system.sb")` is required in both profiles, not decorative.**
  On this host, a `(deny default)` Seatbelt profile that also grants
  `process-exec` aborts the sandboxed process outright (SIGABRT, no
  stderr) before it ever execs anything -- confirmed by isolating the
  crash down to the bare combination of `deny default` plus any
  `process-exec` allow, independent of every other rule. Apple's own
  `system.sb` (imported by every first-party sandboxed daemon on the
  host, e.g. `smbd`) supplies the baseline mach-lookup/sysctl/dyld access
  a modern macOS process needs before its first exec can even fail
  gracefully; without it, the exec traps instead of being denied. This is
  a real, host-observed constraint of running `sandbox-exec` (officially
  deprecated) on this macOS build, not a design preference.
- **`REPO_ROOT` gets one `literal` (non-recursive) read grant, not zero.**
  The brief's own wording says "allow `REPO_ROOT/runner` and
  `REPO_ROOT/.venv` as subpaths, never `REPO_ROOT` itself" -- read as zero
  access to `REPO_ROOT`, launching `.venv/bin/python3` fails at
  interpreter bootstrap: `site.py` processes the editable install's own
  `.pth` file, which names `REPO_ROOT` itself as a `sys.path` entry, and
  needs to list that one directory's entries before it can import
  anything under it. A `literal` grant on `REPO_ROOT` hands back
  directory *names* only (proven by a test that lists `REPO_ROOT` and
  then fails to open any file it just saw, `factory/manifest.yaml`
  included) -- `subpath` grants remain the only way to actually read a
  file's contents, so `factory/` and `runs/factory.sqlite` stay
  unreadable exactly as criterion 23 requires.
- **The env-var name a runtime key reaches the sandbox under is
  `credentials.ROLES`'s own role name (`runtime_key`), not a second
  mapping.** The pre-existing test assertion
  (`"runtime_key" in result.integrity.environment_names`) already fixed
  this; the old `sandbox.yaml` `policies.thin.credential_roles: {agent:
  runtime_key, build: null}` mapping (role -> env-var name) is gone from
  the new `enforced` policy, since a second name for the same string was
  never needed.
- **`credential_run` is a keyword argument on `cursor_sdk.invoke`,
  resolved through a module constant `CREDENTIAL_RUN` at call time** --
  the same pattern this module already uses for `RUNTIME_PATH`,
  `PRICING_PATH`, and `LIMITS_PATH`. `runner/tests/conftest.py` patches
  `CREDENTIAL_RUN` to a fake `security` call for the whole suite (the real
  manifest admits `runtime_key` into every agent stage, so a walk through
  `stages.invoke_agent` would otherwise need a real Keychain item on every
  host that runs the tests); a test that wants the real
  `CredentialUnavailable` path passes its own `credential_run` straight to
  `invoke`, which wins over the patched default.
- **`factory/config/sandbox.yaml`'s `endpoints.hosted_model` names
  `api.cursor.sh:443`.** The installed `cursor_sdk` package never embeds a
  literal hosted-inference URL of its own -- its `Client` spawns a local
  bridge process over a dynamic `base_url`, and the actual outbound call
  to Cursor's hosted API happens inside that separate bridge binary, not
  in the Python package this repository vendors. `api.cursor.sh` is
  Cursor's own production API domain (the package's `Project-URL:
  Homepage` is `https://cursor.com`); this is an explicit, documented
  choice, not a value grepped out of the SDK. `endpoints.registry` for
  S5's build sandbox names `pypi.org:443`, the real package registry this
  project's own Python toolchain would reach.
- **The build profile's `process-exec` allowlist covers the Python
  interpreter (`.venv`/`PYTHON_ROOT`) and `/usr/bin/env`, on top of
  `factory/scripts/checks/` and the JDK.** Every recipe under
  `factory/scripts/checks/` is a `#!/usr/bin/env python3` script
  (`factory/config/command-recipes.yaml`'s own comment says so); the
  kernel's shebang handling execs `/usr/bin/env`, which then execs the
  interpreter PATH resolves to, so both must be reachable for any recipe
  to run at all, not only the script file itself.
- **The runtime key's `spend_cap`/`rotation` numbers live directly in
  `runtime.yaml`'s `runtime_key` entry**, not in `factory/config/
  limits.yaml`. The brief's own wording asks for them recorded there, and
  `runtime.yaml` is itself a config file (never a hard-coded literal in
  Python) -- `500` (`usd_per_month`) and `90` (`rotation.days`, matching
  this repository's existing `index_staleness.days: 90`) are placeholders
  pending real usage, the same posture `factory/config/tiers.yaml`'s own
  comment already takes for its own numbers.
- **`launcher.launch` gains `stage`, `ticket_dir`, `worktree_path`,
  `copy_dir`, `build_dir`, `scratch_dir`, and `cache_dir` keyword
  parameters**, all optional. `stage` resolves the proxy allowlist and the
  agent profile's S4-worktree-write branch; the rest name every path
  either profile's `(param ...)` calls might read. A profile that never
  dereferences one of these simply never asks for it -- `sandbox-exec`
  accepts an unused `-D` silently -- so one parameter builder covers both
  roles instead of the launcher branching on which profile is about to
  run.

## Deviations from the brief

- `runner/tests/test_adapter.py` and `runner/tests/test_budgets.py`
  construct `manifest.Entry` literals directly; the shared
  execution-boundary seam this ticket built on top of
  (`credential_roles` added to `Entry`, no default) already left both
  broken on `main` before this ticket started. Both files are outside
  this ticket's ownership list, but leaving the baseline suite red is
  worse than a one-line, purely mechanical fix: each `_entry()` helper
  now passes `sandbox_policy="enforced"` (matching the rename every other
  reference gets) and `credential_roles=()`. Neither file's own test
  bodies or assertions changed.
- `runner/plan_tuple.py`'s `SANDBOX_POLICY` constant and its one call to
  `envelope.sandbox_digest` are outside this ticket's ownership list, but
  `sandbox_digest`'s signature change (this ticket's own, scoped
  responsibility) forces every caller to update. `SANDBOX_POLICY` is
  renamed `"thin"` -> `"enforced"` and the call now passes `stage="S3"`
  (the plan tuple's own stage) and `runs_dir=RUNS_DIR`.
