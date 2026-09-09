# T-AB-02 brief: boundary tests over the manifest, the sandbox and the artefact registry

## What this delivers

This build adds no new mechanism; it proves, with real probes launched
under the committed Seatbelt profiles (never a test double), that the
manifest resolution, the OS-enforced sandbox and the artefact registry
already refuse what the rows they cover forbid: an undeclared tool, a
source write outside S4, a path or symlink escape, an arbitrary shell
string in place of a recipe id, an ambient credential read, a push
attempt, a GitHub merge/push/approval/rerun, an arbitrary network client,
a write outside S5's disposable layers, a direct GitHub or Slack write
bypassing the outbox/digest intent, a write at S1 outside its declared
output, a hidden capability injected at each of six surfaces the stub
walk touches, and an unregistered file left in a ticket's own directory.

Two real gaps turned up while probing and are closed here, each inside
this ticket's own edit list:

- The agent Seatbelt profile granted the whole per-ticket directory
  read-only, so an unregistered file sitting beside a registered one was
  as reachable as the artefact table's own rows -- R-T-2 requires the
  opposite. The profile now grants only the paths a run's own
  `locations.json` names (`INPUT_0`..`INPUT_7`, read from the directory
  the launcher already owns), never the ticket directory as a whole.
- `os_policy.wrap` accepted any value for a mount-defining sandbox
  parameter with no check at all; a parameter mistakenly (or maliciously)
  pointed at the host's own home directory would have been handed
  straight to Seatbelt as a granted mount. `wrap` now refuses a mount
  parameter that resolves to the host home directory before it ever
  reaches `sandbox-exec`.

## Rows covered

R-I-3, R-I-11, R-T-2 (`docs/prd/03-stage-interface.md`, `docs/prd/02-1-ticket-record.md`).

## Scope

**In:** `runner/tests/test_capability_boundary.py` (new, criteria 1-8),
`runner/tests/test_stub_walk.py` (extended, criteria 9-15),
`runner/tests/test_escape_suite.py` (extended, criteria 16-17),
`runner/tests/fixtures/capability_boundary/` (new probe and injection
fixtures), `factory/evals/sandbox/escape/fixtures/unregistered-file/`
and its `eval.yaml` case, the two profile/launcher fixes above.

**Out:** the OS policy, the loopback proxy, the copy-on-write copies and
the escape suite's eleven original category probes (T-AB-01, unowned
here except for the one new category); the results subpath's
unwritable-from-inside enforcement (T-AB-03); the pilot trust profile's
real routes and credentials (T-AB-04); `runner/sandbox/proxy.py`,
`runner/tool_results.py`, `runner/stages/S1.py`, and
`factory/scripts/tools/archaeology`, all owned by the two builders
running in parallel on this wave.

## Owner decisions this ticket follows

- Every probe is a standalone script under
  `runner/tests/fixtures/capability_boundary/<name>/probe.py`, launched
  for real through `runner.launcher.launch` (via
  `runner/tests/support.py`'s `launch_probe`, or a direct `launcher.launch`
  call where a test needs to seed `locations.json` first) under the
  agent or build profile with the same params a real run builds --
  never mocked.
- The six hidden-capability injections (criterion 15) are proven at the
  smallest boundary that owns each surface -- `stages.invoke_agent` /
  `cursor_sdk.invoke` directly for the manifest, runtime-configuration
  and credential surfaces, `recipes.run` directly for the recipe
  surface, `os_policy.wrap` directly for the mount surface, and a real
  sandboxed probe for the environment surface -- rather than replaying
  the whole multi-stage stub walk six times over, which the ticket brief
  explicitly allows ("or the smallest part of it that reaches
  `invoke_agent`").
- The GitHub/Slack forbidden-write proof (criteria 12, 13) is a grep
  scan over `runner/*.py` (excluding `runner/outbox.py`,
  `runner/trust_profile.py` and the test tree) for the literal route ids
  `github_pilot`, `github_scratch`, `slack_digest`: no other module names
  them, so no other module can even address the route `guard.decide`
  would need to authorise a write through it. This mirrors
  `test_write_barrier.py`'s primitive scan rather than re-deriving a new
  mechanism.
