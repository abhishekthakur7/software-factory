# Milestone AB build tickets: boundary and connection

| | |
|---|---|
| Status | Draft v0.1 |
| Date | 2026-09-08 |
| Owner | Abhishek Thakur |
| Cites | `docs/design/milestones.md` v0.7 (section 3 "AB, boundary and connection", Appendix A); `docs/prd/prd.md` v0.18 and its parts; `docs/charter.md` v0.14; `docs/design/hld/README.md` v0.3; `docs/design/tickets/A.md` |
| Milestone | AB: the enforced execution boundary, the pilot repository's trust routes, the credentials, the real reads and writes, and the pilot service's configuration content, 13 requirement rows, each proven without a real ticket advanced past S1 |

## How to read

One ticket per section, in build order. A ticket depends only on tickets above it in this file or on Milestone A tickets in `A.md`, so the file order is a topological order. Every ticket names its milestone, its blocks by number from `milestones.md` section 1, its components by id from the HLD register, the tickets it depends on, the PRD rows it covers, what it builds and why, its scope in and out, numbered acceptance criteria that each restate one verification clause of one row as a test that passes or fails, and the test files and fixtures it adds. A row sits in exactly one ticket. `tools/tickets_check.py` enforces the format, the coverage of Appendix A, the placement, the dependency order and the citation of a row id on every criterion.

Three phases, fixed by `milestones.md` section 3. Phase 1, the boundary (T-AB-01 to T-AB-03): the OS policy, the loopback proxy, the copy-on-write base and head copies, the results subpath read-only from inside, the escape suite on the pilot host, the boundary tests for hidden capabilities and unregistered files, and tool results through the proxy. Phase 2, the connections (T-AB-04 to T-AB-07): the pilot's trust profile with its real routes and credentials by role, the pilot and scratch repositories, the pilot's configuration content, S0 intake over Jira, S1 archaeology through the Atlassian server with the dry-run walk to `clarifying`, the outbox worker with push authority, and the digest. Phase 3, the pilot's checks, the baseline and the gate (T-AB-08 to T-AB-11): the pilot's recipes with dependency verification under the registry policy, the full S5 order in the copies with the security recipes, the frozen baseline, and the adoption gate complete. Under PRD decision 39, each ticket's builder hand-writes `docs/build/<ticket-id>/brief.md` and `plan.md` before building that ticket, the rule T-A-01 states. Names no source document fixes are stated in the ticket that first uses them and hold for every ticket after it: the pilot host is macOS, the OS policy is a Seatbelt profile under `factory/config/sandbox/`, the sandbox code is the package `runner/sandbox/`, credentials are fetched by role name from the host credential store by `runner/credentials.py`, trusted-side readers live under `runner/readers/` and real deliverers under `runner/deliverers/`.

## T-AB-01: Sandbox: OS policy, loopback proxy, results subpath read-only from inside, copy-on-write base and head copies with disposal and recheck, credential roles in the sandbox policy, the escape suite on the pilot host

| | |
|---|---|
| Milestone | AB |
| Blocks | 20 Sandbox; 4 Manifest |
| HLD components | G2, G3, F2, R2 |
| Depends on | T-A-08, T-A-18, T-A-19 |
| Rows covered | R-I-14 |

### Description

Every agent invocation and repository or build recipe must run inside an OS-enforced sandbox identified by an immutable policy digest, satisfying charter C10's isolation requirement from the first production-capable pilot (R-I-14). This ticket builds the Seatbelt OS policy as two profiles, agent and build, launched through `sandbox-exec` from T-A-18's launcher, and adds a loopback allowlisting proxy that becomes the runtime key's only path to the hosted-inference endpoint. It provisions and disposes of S5's copy-on-write base and head copies of the immutable checkouts, with disposable build, scratch and cache layers and a post-disposal recheck of the underlying commits and diff. The per-run directory's `results/` subpath becomes read-only from inside the sandbox, writable only by the trusted runner. It names the credential roles the manifest's sandbox-policy entry admits per stage and fetches the runtime key from the Keychain by role. It proves every mechanism with an escape suite on the pilot host over eleven categories, from paths and symlinks to credentials, run against T-A-08's fixture project and T-A-19's manifest.

### Scope

**In:** `factory/config/sandbox/agent-profile.sb`, `factory/config/sandbox/build-profile.sb`; `factory/config/sandbox.yaml` (T-A-18), extended with `os_profile` digests, `proxy_allowlist`, and the disposable-copy location; `factory/manifest.yaml` (T-A-19), extended with a sandbox-policy entry naming the OS profile, the proxy allowlist and the credential roles admitted per stage; `runner/sandbox/os_policy.py`; `runner/sandbox/proxy.py`; `runner/sandbox/copies.py`; `runner/credentials.py`; `factory/config/runtime.yaml` (T-A-18), extended with the runtime key's rotation field; `stage_run.sandbox_digest`, recomputed content; `runner/tests/test_sandbox.py` (T-A-18), extended with the OS policy, proxy allowlist, credential-role and digest assertions; `runner/tests/test_escape_suite.py` (new); `factory/evals/sandbox/escape/eval.yaml`, `factory/evals/sandbox/escape/fixtures/paths/`, `.../symlinks/`, `.../subprocesses/`, `.../environment/`, `.../sockets/`, `.../network/`, `.../mounts/`, `.../base-head-isolation/`, `.../source-immutability/`, `.../copy-disposal/`, `.../credentials/`.

**Out:** the manifest and sandbox tests over undeclared tools, source writes, path and symlink escape, arbitrary shell, ambient credentials and push, and the unregistered-file probe (T-AB-02); the proxy's tool-result capture into the results subpath (T-AB-03); the pilot repository's own recipes, the security recipes, and the `atlassian_read`, `github_publish` and `slack_digest` credential roles and routes (T-AB-04, T-AB-06, T-AB-07, T-AB-08, T-AB-09); the full S5 order run inside these copies (T-AB-09); registering the escape suite and the copy-disposal run among the adoption gate's required checks (T-AB-11).

### Acceptance criteria

1. `factory/config/sandbox/agent-profile.sb` is a Seatbelt profile that mounts the worktree, permits writes to `out/`, denies writes to `results/`, and admits only loopback egress (R-I-14)
2. `factory/config/sandbox/build-profile.sb` is a Seatbelt profile that permits writes only to the copy and its disposable build, scratch and cache directories, supplies no credential, and admits loopback only to recipe-declared registry endpoints (R-I-14)
3. `sandbox.yaml`'s `os_profile` digests equal the content hash of `agent-profile.sb` and `build-profile.sb` respectively (R-I-14)
4. `sandbox.yaml` gains a `proxy_allowlist` field naming the route id, host and port admitted per stage (R-I-14)
5. `sandbox.yaml` names the disposable-copy location under `runs/tickets/<id>/copies/<stage_run_id>/{base,head}/` (R-I-14)
6. `runner/launcher.py` starts a stage's sandbox through `runner/sandbox/os_policy.py`, which selects the agent or build profile for the stage and launches it with `sandbox-exec` (R-I-14)
7. `stage_run.sandbox_digest` records a digest computed over the OS profile, the proxy allowlist and the runtime's sandbox configuration together, differing from the digest a run recorded before this ticket (R-I-14)
8. `factory/manifest.yaml`'s sandbox-policy entry names the OS profile, the proxy allowlist and the credential roles admitted per stage (R-I-14)
9. The manifest's sandbox-policy entry admits `runtime_key` for an agent stage and no credential role for a build sandbox, `S0`, an `S5` script, or `S6` (R-I-14)
10. `runner/credentials.py` fetches the `runtime_key` value from the macOS Keychain through the `security` command at the moment of use and never returns it into a row, an artefact, a log, or a build sandbox's environment (R-I-14)
11. `runtime.yaml` records the runtime key's role, scope, spend cap and rotation by role name, never its value (R-I-14)
12. `runner/sandbox/proxy.py` starts one process per run on `127.0.0.1`, on a port `runner/launcher.py` passes into the sandbox environment (R-I-14)
13. The proxy admits only the `(host, port)` pairs `sandbox.yaml`'s `proxy_allowlist` names for the stage: the hosted-inference endpoint for an agent sandbox and a recipe-declared registry endpoint for a build sandbox at S5 (R-I-14)
14. Inside an agent sandbox, the scoped runtime key reaches the hosted-inference endpoint only through the loopback proxy (R-I-14)
15. `runner/sandbox/copies.py` creates the S5 base and head copies as APFS clones by `cp -c` of the immutable checkouts, each with empty recipe-declared build-output, scratch and cache directories (R-I-14)
16. Nothing written into a copy's disposable directories is present in the immutable checkout it was cloned from, after the run ends (R-I-14)
17. `runner/sandbox/copies.py` destroys the base and head copies after governed evidence capture, and on the crash path (R-I-14)
18. After copy disposal, the runner rechecks the underlying commits and diff of the immutable checkouts and finds them unchanged (R-I-14)
19. Every registered input other than S4's worktree mount and S5's copies stays read-only inside the sandbox for the run's duration (R-I-14)
20. The per-run directory's `results/` subpath is read-only from inside the sandbox; only the trusted runner outside the boundary writes into it (R-I-14)
21. The per-run directory's filesystem location is hashed into the sandbox digest, and the directory is destroyed with the run's other disposable state (R-I-14)
22. `factory/` and `runs/factory.sqlite` are absent from every mount the sandbox receives (R-I-14)
23. The `paths` probe reads the host home directory from inside the sandbox and is refused (R-I-14)
24. The `symlinks` probe follows a symlink placed inside a mount that targets a path outside the sandbox's declared mounts and is refused (R-I-14)
25. The `subprocesses` probe spawns a process other than a declared recipe executable and is refused (R-I-14)
26. The `environment` probe reads an environment variable outside the R-I-16 environment-name allowlist and observes it absent (R-I-14)
27. The `sockets` probe opens the host's Docker socket and is refused (R-I-14)
28. The `network` probe connects to a host and port outside `proxy_allowlist` and is refused (R-I-14)
29. The `mounts` probe reads a sibling checkout not registered as an input and is refused (R-I-14)
30. The `base-head-isolation` probe writes a file into the base copy and finds it absent from the head copy (R-I-14)
31. The `source-immutability` probe writes into the immutable checkout underlying a copy and is refused (R-I-14)
32. The `copy-disposal` probe confirms neither the base nor the head copy directory exists after disposal (R-I-14)
33. The `credentials` probe reads the host Keychain, an SSH agent socket, or an ambient credential and is refused (R-I-14)
34. `runner/tests/test_escape_suite.py` fails, never skips, when the OS policy is unavailable on the host running it (R-I-14)
35. The escape suite passes on the pilot host over every category R-I-14 names (R-I-14)

### Verification

`runner/tests/test_sandbox.py`: criteria 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22
`runner/tests/test_escape_suite.py`: criteria 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35
`factory/evals/sandbox/escape/eval.yaml`, `factory/evals/sandbox/escape/fixtures/paths/`, `.../symlinks/`, `.../subprocesses/`, `.../environment/`, `.../sockets/`, `.../network/`, `.../mounts/`, `.../base-head-isolation/`, `.../source-immutability/`, `.../copy-disposal/`, `.../credentials/`: criteria 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33

## T-AB-02: Boundary tests: undeclared inherited tools, source writes, path and symlink escape, arbitrary shell, ambient credentials and push denied; forbidden capabilities across manifest, inherited configuration, recipes, mounts, environment and credentials; an unregistered file absent from the sandbox

| | |
|---|---|
| Milestone | AB |
| Blocks | 4 Manifest; 11 Artefact; 20 Sandbox |
| HLD components | F2, G2, G3, R2 |
| Depends on | T-A-03, T-A-17, T-A-18, T-A-19, T-AB-01 |
| Rows covered | R-I-3, R-I-11, R-T-2 |

### Description

Each stage run must attach only the manifest's declared MCP servers and tools, and a capability the manifest does not name must be denied across the manifest, the inherited runtime configuration, a recipe, a mount, the environment and a credential together (R-I-3, R-I-11). An unregistered file must stay invisible to the next stage and absent from its sandbox, since a stage reads artefacts only through the table (R-T-2). This ticket builds no new mechanism: it tests T-AB-01's OS policy and proxy and T-A-19's manifest resolution, injecting an undeclared tool, a source write outside S4, a path or symlink escape, an arbitrary shell string, an ambient credential read, and a push attempt, then probing each capability R-I-11 forbids. It reruns T-A-17's stub walk with a hidden capability at each of six surfaces, and places an unregistered file in the per-ticket directory to prove T-A-03's artefact registry gates the next stage's sandbox mounts.

### Scope

**In:** `runner/tests/test_capability_boundary.py` (new: R-I-3's undeclared-tool, source-write, path-escape, symlink-escape, arbitrary-shell, ambient-credential and push probes, and the resolved-set-write check); `runner/tests/test_stub_walk.py` (T-A-17), extended with R-I-11's forbidden-capability probes and a hidden-capability injection case for each of the manifest, the inherited runtime configuration, a recipe, a mount, the environment, and a credential; `runner/tests/test_escape_suite.py` (T-AB-01), extended with a probe for an unregistered file placed in the per-ticket directory; `runner/tests/fixtures/capability_boundary/` (undeclared-tool, source-write, path-escape, symlink-escape, shell-string, ambient-credential, push, per-surface hidden-capability, and unregistered-file fixtures).

**Out:** the OS policy, the loopback proxy, the copy-on-write copies and the escape suite's eleven category probes (T-AB-01); the results subpath's unwritable-from-inside enforcement (T-AB-03); the pilot trust profile's real routes and credentials (T-AB-04).

### Acceptance criteria

1. A stage run started with a workspace-level MCP server not named in the manifest's per-stage-tier tool list does not have that server among its attached tools (R-I-3)
2. A recipe invocation at a stage other than S4 attempting to write into the ticket worktree is refused (R-I-3)
3. A probe reading a path outside the sandbox's declared mounts through a relative traversal is refused (R-I-3)
4. A probe following a symlink placed inside a mount that targets a path outside the sandbox's declared mounts is refused (R-I-3)
5. An agent-issued shell string given in place of a typed recipe id is refused before dispatch (R-I-3)
6. A probe inside a stage sandbox other than an S4 or agent stage reading an ambient credential from the Keychain, an SSH agent socket, or an environment variable outside the allowlist finds none present (R-I-3)
7. A probe attempting `git push` from inside any stage's sandbox is refused, since no stage sandbox holds a push-capable remote (R-I-3)
8. The resolved set of MCP servers and tools attached for a stage run is written to the record before the stage starts (R-I-3)
9. For each of a GitHub merge, a default-branch push, a pull-request approval, an Actions rerun, an arbitrary network client, and an arbitrary shell, a probe attempting it from inside any stage's sandbox is refused (R-I-11)
10. Source-tree write succeeds only at S4's worktree mount; a probe at S1, S2, S3, S5, or S6 attempting a source-tree write is refused (R-I-11)
11. At S5, a probe attempting to write outside its disposable build, scratch or cache layers, or outside governed evidence, is refused (R-I-11)
12. A GitHub branch or pull-request write succeeds only through the trusted `pr_create`/`pr_update` outbox worker; a probe from inside any sandbox attempting one directly is refused (R-I-11)
13. A Slack post succeeds only through the digest intent; a probe from inside any sandbox attempting one directly is refused (R-I-11)
14. S1 grants no write capability; a probe at S1 attempting a write outside its declared brief output is refused (R-I-11)
15. For each of a hidden capability injected into the manifest, the inherited runtime configuration, a recipe, a mount, the environment, and a credential, rerunning T-A-17's stub walk with that injection fails the walk (R-I-11)
16. Given an unregistered file placed in the ticket's per-ticket directory, the artefact-lookup path the next stage driver calls does not return it as a registered input (R-T-2)
17. Given the same unregistered file, a probe inside the next stage's sandbox on the pilot host finds it absent from every declared mount (R-T-2)

### Verification

`runner/tests/test_capability_boundary.py`: criteria 1, 2, 3, 4, 5, 6, 7, 8
`runner/tests/test_stub_walk.py`: criteria 9, 10, 11, 12, 13, 14, 15
`runner/tests/test_escape_suite.py`: criteria 16, 17
`runner/tests/fixtures/capability_boundary/`: criteria 1, 2, 3, 4, 5, 6, 7, 9, 10, 11, 12, 13, 14, 15, 16, 17

## T-AB-03: Tool results through the proxy into the results subpath

| | |
|---|---|
| Milestone | AB |
| Blocks | 19 Invocation and runtime adapter; 20 Sandbox |
| HLD components | G1, G2, R2 |
| Depends on | T-A-18, T-AB-01 |
| Rows covered | R-I-17 |

### Description

Tool results stay out of the context window unless small, whether a call reaches the agent through the adapter or the stage-approved MCP proxy R-I-14 builds (R-I-17). This ticket extends T-AB-01's proxy so every MCP-routed tool result is written by the trusted runner as a governed `tool_result` artefact in the results subpath of the per-run directory. It re-proves the four size cases T-A-18 already proved for the adapter's direct calls, now through the proxy: a large result excerpted with a complete artefact, a one-line oversized and a non-text result with no inline payload, and a small result returned inline as well. It sets `tool_call.result_bytes` and `tool_call.inline` for every proxy-routed call and never truncates the stored result. It proves the results subpath stays unwritable from inside the sandbox, so only the trusted runner writes governed evidence there. It depends on T-A-18's adapter, whose result-shaping rules it reuses, and T-AB-01's proxy, whose allowlisted routes it now instruments.

### Scope

**In:** `runner/sandbox/proxy.py` (T-AB-01), extended to record every MCP-route tool result into the run's `results/` subpath as a governed `tool_result` artefact and to write the `tool_call` row for that call; `runner/tests/test_proxy_results.py` (new); `runner/tests/fixtures/proxy_results/` (large, one-line-oversized, non-text, and small result fixtures).

**Out:** the OS policy, the copy-on-write copies, and the escape suite (T-AB-01); the manifest and sandbox capability tests (T-AB-02); the adapter's direct-call result handling, tested at T-A-18 and not restated here.

### Acceptance criteria

1. An MCP tool call from inside a stage's sandbox to a route on `sandbox.yaml`'s `proxy_allowlist` is dispatched through `runner/sandbox/proxy.py` rather than returned to the agent directly (R-I-17)
2. A large MCP tool result delivered through the proxy is written as a governed `tool_result` artefact in the run's `results/` subpath, and the agent's context receives the artefact's path, size, exit status, and a head-and-tail excerpt bounded by `limits.yaml`'s inline limit (R-I-17)
3. A one-line oversized MCP tool result delivered through the proxy is written as a governed `tool_result` artefact and returns no inline payload to the agent's context (R-I-17)
4. A non-text MCP tool result delivered through the proxy is represented in the agent's context by size, media type, and digest only, with no inline payload (R-I-17)
5. A small MCP tool result delivered through the proxy, under `limits.yaml`'s inline limit, is returned inline as well as written to the results subpath (R-I-17)
6. `tool_call.result_bytes` and `tool_call.inline` are set for a call the proxy routes, matching the delivered result's size and inline status (R-I-17)
7. `runner/sandbox/proxy.py` writes the `tool_call` row for the MCP route it serves and never truncates the stored `tool_result` artefact regardless of the result's size (R-I-17)
8. After receiving the bounded excerpt, the agent reads a further slice of a proxy-delivered result with an ordinary file read against the artefact's path in `results/` (R-I-17)
9. A probe inside an agent sandbox attempting to write into the `results/` subpath of its own per-run directory is refused (R-I-17)
10. A tool result delivered through the proxy lands as a governed file in the results subpath of the per-run directory, which the sandbox cannot write (R-I-17)

### Verification

`runner/tests/test_proxy_results.py`: criteria 1, 2, 3, 4, 5, 6, 7, 8, 9, 10
`runner/tests/fixtures/proxy_results/`: criteria 2, 3, 4, 5

## T-AB-04: Pilot trust profile and credentials by role; pilot and scratch repositories; pilot configuration content; S0 intake over Jira with the field gate

| | |
|---|---|
| Milestone | AB |
| Blocks | 24 External access; 6 Trust profile; 9 Ticket and its state; 22 Check; 25 Git trees |
| HLD components | C7, F6, C5, H4, C9, R3, E1, E5 |
| Depends on | T-A-07, T-A-08, T-A-20, T-A-21, T-AB-01 |
| Rows covered | R-S0-1 |

### Description

S0 runs no agent, but its mechanical gate and its Jira read now cross the trust boundary charter C9 requires. This ticket adds `runner/checks/intake_fields.py`, the mechanical gate over `ticket-types.yaml`'s Jira field names that rejects a missing item or an epic with the reason named, called by T-A-20's `runner/stages/S0.py` before classification. `runner/readers/atlassian.py` reads the ticket through the Atlassian MCP server with the `atlassian_read` role, fetched by T-AB-01's `runner/credentials.py` from the trusted runner process, never mounted into an agent sandbox. T-A-07's guard classifies and redacts the permitted source fields into `ticket_source` before storage or inference, so verbatim means faithful after governed redaction. This ticket also carries the pilot trust profile's admitted scopes, the pilot and scratch repositories in `project.yaml`, the pilot's configuration content in `service-tiers.yaml`, `ticket-types.yaml`, `sensitive-paths.yaml` and the context index, and the Atlassian-read, GitHub-publication, Slack-digest, baseline-read and registry routes later tickets use. Each route is governance-approved and pinned by hash on T-A-07's trust profile. It sits on T-A-08's git-tree mechanics for the pilot repository's checkout, T-A-20's S0 driver, T-A-21's context index, and T-AB-01's sandbox boundary for the credential path.

### Scope

**In:** `runner/checks/intake_fields.py`; `runner/readers/atlassian.py`; `runner/stages/S0.py` (calls `intake_fields.py` before classification and `atlassian.py` for the pilot service, invokes T-A-07's guard to classify and redact into `ticket_source`); the `atlassian_read` role's use of T-AB-01's `runner/credentials.py`; `factory/config/ticket-types.yaml` (pilot Jira field names for acceptance criteria, owner, parent link, Confluence link); `factory/config/service-tiers.yaml` (pilot row); `factory/config/sensitive-paths.yaml` (pilot entries with owners); `factory/index/` (pilot `conventions` and `sensitive-paths` entries, `caller` entries); `factory/config/project.yaml` (`projects` list gains the pilot repository, `scratch_repository` key); `factory/config/trust-profile.yaml` (admits the pilot and scratch repositories as scopes; adds the Atlassian-read, GitHub-publication to the pilot and scratch repositories, Slack-digest, baseline-read, recipe-declared-registry, and vulnerability-database-feed routes, each with a `credential_role` key); `runner/tests/test_intake_fields.py`; `runner/tests/test_s0.py`; `runner/tests/test_pilot_config.py`; `runner/tests/fixtures/intake_fields/`; `runner/tests/fixtures/s0/`; `runner/tests/fixtures/pilot_config/`.

**Out:** the credential-fetch mechanism itself and the loopback proxy (T-AB-01); the Atlassian route's agent-side S1 leg (T-AB-05); the outbox worker's use of the GitHub-publication route (T-AB-06); the digest's use of the Slack route (T-AB-07); the pilot repository's recipes and the registry route's use (T-AB-08, T-AB-09); the baseline's use of the Atlassian and GitHub-publication routes (T-AB-10).

### Acceptance criteria

1. Given a seeded source ticket with empty acceptance criteria, `runner/checks/intake_fields.py` rejects it with the reason named (R-S0-1)
2. Given a seeded source ticket with no named owner, `runner/checks/intake_fields.py` rejects it with the reason named (R-S0-1)
3. Given a seeded source ticket with neither a linked parent nor a linked Confluence page, `runner/checks/intake_fields.py` rejects it with the reason named (R-S0-1)
4. Given a seeded source ticket of Jira issue type `Epic`, `runner/checks/intake_fields.py` rejects it with the reason `needs child tickets` (R-S0-1)
5. `runner/checks/intake_fields.py` reads the acceptance-criteria, owner, parent-link and Confluence-link field names from `ticket-types.yaml`, is called by `runner/stages/S0.py` before classification, and writes one `check_result` row with `check = 'intake_fields'` (R-S0-1)
6. Before storage or inference, T-A-07's guard classifies and redacts the permitted source fields of a seeded Jira payload into a `ticket_source` artefact and sets `ticket.data_class` (R-S0-1)
7. A seeded redaction fixture shows `ticket_source`'s retained fields faithful to the source Jira payload after governed redaction, never an unfiltered copy of the Jira payload (R-S0-1)
8. On the dry-run ticket created from one real Jira key of the pilot service, `runner/readers/atlassian.py` reads the ticket through the Atlassian MCP server, and S0 writes the resulting classified `ticket_source` artefact (R-S0-1)
9. `runner/credentials.py` fetches the `atlassian_read` credential value from the macOS Keychain through the `security` command, on the trusted runner side, at the moment S0 reads the ticket (R-S0-1)
10. The manifest's sandbox-policy entry names no credential role admitted into an S0 sandbox, since S0 runs no agent and the credential is fetched by the runner process directly (R-S0-1)
11. The `atlassian_read` credential value never appears in a `ticket_source` row, an artefact, or a log across the dry-run read (R-S0-1)
12. On the dry-run ticket, `ticket.trust_profile_hash` and `ticket.trust_approval_set_hash` are pinned at eligibility to `trust-profile.yaml`'s exact hash and its satisfying security and legal/data-governance approval set (R-S0-1)
13. `factory/config/service-tiers.yaml` carries a row for the pilot service, `factory/config/ticket-types.yaml` names the pilot's Jira field names for acceptance criteria, owner, parent link and Confluence link, and `factory/config/sensitive-paths.yaml` carries the pilot's entries with owners, each filled by one reviewed pull request (R-S0-1)
14. `factory/index/` carries the pilot service's `conventions` and `sensitive-paths` entries with `last_verified` set at seeding, and its `caller` entries where the pilot's callers are known (R-S0-1)
15. `factory/config/project.yaml`'s `projects` list carries the pilot repository's entry with its checkout path outside this repository, target branch, recipe ids and toolchain digest, and its `scratch_repository` key names a throwaway branch prefix for a GitHub repository the owner creates by hand (R-S0-1)
16. `trust-profile.yaml` admits the pilot repository and the scratch repository as scopes, each governance-approved and pinned by hash, before the dry-run ticket's S0 read (R-S0-1)

### Verification

`runner/tests/test_intake_fields.py`: criteria 1, 2, 3, 4, 5
`runner/tests/test_s0.py`: criteria 6, 7, 8, 9, 10, 11, 12
`runner/tests/test_pilot_config.py`: criteria 13, 14, 15, 16
`runner/tests/fixtures/intake_fields/`: missing-acceptance-criteria, missing-owner, missing-link, and epic fixtures for criteria 1, 2, 3, 4
`runner/tests/fixtures/s0/`: redaction, dry-run Jira read, and credential fixtures for criteria 6, 7, 8, 9, 10, 11, 12
`runner/tests/fixtures/pilot_config/`: pilot service-tiers, ticket-types, sensitive-paths, index, project.yaml, and trust-profile route fixtures for criteria 13, 14, 15, 16

## T-AB-05: S1 archaeology through the Atlassian server and the dry-run walk to `clarifying`

| | |
|---|---|
| Milestone | AB |
| Blocks | 24 External access; 3 Rubric |
| HLD components | C7, C6, F4, G3, E1 |
| Depends on | T-A-22, T-A-27, T-AB-03, T-AB-04 |
| Rows covered | R-S1-4 |

### Description

S1's brief needs real archaeology once the pilot repository's history can be read, not the fixture repository's issue-less commits that satisfied R-S1-4's coverage line trivially at A. This ticket builds `factory/scripts/tools/archaeology`, which runs `git blame` inside the S1 sandbox on every candidate file or function that is not self-evident, then reads the issues named in the commit messages through the Atlassian route on the loopback proxy, reached with T-AB-04's `atlassian_read` role. Each candidate is classified `explained`, `unexplained`, or `contradictory` in T-A-22's brief history section, and a candidate whose history names no issue is `unexplained`. On the dry-run ticket, S1 resolves one blame-linked issue of the pilot repository and passes the ticket into `clarifying`, where `factory abandon` writes the ticket's `abandoned` tag and `not_deployed` coverage record so no S2 or later stage runs. Since no real ticket reaches S3 at AB, the bootstrap-checklist archaeology-coverage line T-A-27 built is exercised over a seeded brief from the dry run instead of a live S3 approval. It sits on T-A-22's brief driver, T-A-27's checklist, T-AB-03's proxy-delivered tool results, and T-AB-04's Atlassian route and credential role.

### Scope

**In:** `factory/scripts/tools/archaeology`; `sandbox.yaml`'s `proxy_allowlist` gaining the Atlassian route entry for S1; `runner/stages/S1.py` (calls `archaeology`, records classification into the brief's history section); `runner/tests/test_s1_archaeology.py`; `factory/evals/scripts/tools/archaeology/` (eval.yaml, fixtures); `runner/tests/fixtures/s1_archaeology/`.

**Out:** the loopback proxy itself and the results-subpath capture of proxy-delivered tool results (T-AB-01, T-AB-03); the brief artefact's fixed sections other than history (T-A-22); the bootstrap checklist's other rubric lines (T-A-27); the pull-request chain via the GitHub read attachment (Later); the credential-fetch mechanism and its S0 leg (T-AB-01, T-AB-04).

### Acceptance criteria

1. Given the dry-run ticket at S1, `factory/scripts/tools/archaeology` runs `git blame` inside the S1 sandbox on a candidate file or function of the pilot repository that is not self-evident (R-S1-4)
2. `factory/scripts/tools/archaeology` reads the issues named in the commit messages `blame` surfaces through the Atlassian route on the loopback proxy (R-S1-4)
3. `sandbox.yaml`'s `proxy_allowlist` names the Atlassian server's endpoint for S1 only, and the proxy fetches the `atlassian_read` credential through `runner/credentials.py` to relay the call, never mounting the credential into the S1 sandbox (R-S1-4)
4. The `atlassian_read` credential value never appears in a `tool_call` row, an artefact, or a log across the S1 Atlassian read (R-S1-4)
5. For each of `explained`, `unexplained`, and `contradictory`, a seeded candidate whose blame-linked commit-message history matches that pattern is classified accordingly in the brief's history section (R-S1-4)
6. A candidate whose commit-message history names no issue is classified `unexplained` in the brief's history section (R-S1-4)
7. On the dry-run ticket, S1 resolves one blame-linked issue of the pilot repository through the Atlassian server, and the brief's history section records that classification (R-S1-4)
8. The dry-run ticket moves from `context` to `clarifying` on S1's pass (R-S1-4)
9. `factory abandon` on the dry-run ticket in `clarifying` writes an `abandoned` tag and a `not_deployed` production-coverage record, and no `stage_run` for S2 or a later stage is recorded on that ticket (R-S1-4)
10. On a seeded brief from the dry run, T-A-27's bootstrap-checklist archaeology-coverage line of `rubrics/S3.md` records a `human_verdict` row over the pilot brief's history section (R-S1-4)

### Verification

`runner/tests/test_s1_archaeology.py`: criteria 1, 2, 3, 4, 5, 6, 7, 8, 9
`runner/tests/fixtures/s1_archaeology/`: blame, commit-message, and classification fixtures for criteria 1, 2, 5, 6
`factory/evals/scripts/tools/archaeology/`: eval.yaml, fixtures for criteria 1, 2, 3
`runner/tests/test_s3_checklist.py`: criterion 10
`factory/evals/rubrics/S3/fixtures/`: seeded dry-run brief fixture for criterion 10

## T-AB-06: Outbox worker with push authority: `pr_create` and `pr_update` on the scratch repository

| | |
|---|---|
| Milestone | AB |
| Blocks | 24 External access; 15 Binding |
| HLD components | C7, C4, E2, E5 |
| Depends on | T-A-13, T-A-15, T-A-34, T-AB-04 |
| Rows covered | R-S6-3 |

### Description

Publication only gets push authority once the outbox worker can reach a real remote, so this ticket replaces T-A-13's stub deliverer with `runner/deliverers/github.py` for `pr_create` and `pr_update` on the scratch repository. The worker pushes only the ticket branch with the `github_publish` role, rechecks T-A-34's publication-target and review-approval subjects, T-A-14's freshness boundary, every approval slot and waiver, and the trust identity immediately before dispatch, and never overwrites an unexpected remote head. On the first cycle no branch or diff is pushed before full review quorum; on a revision cycle the branch and pull request stay unchanged until reapproval, and the last quorum-completing approval commits together with the intent it authorises. `pr_update` requires the previously reconciled remote head and applies compare-and-set and `--force-with-lease` semantics, never opening a replacement pull request. A non-retryable permission or control failure escalates the ticket, and an already closed or merged remote pull request raises the `pr_outcome` item instead of dispatching, its actions arriving at B. It sits on T-A-13's outbox contract and crash recovery, T-A-15's restart path, T-A-34's publication subjects, and T-AB-04's scratch repository, credential role and route.

### Scope

**In:** `runner/deliverers/github.py`; the `github_publish` role's use of T-AB-01's `runner/credentials.py` and a credential helper on the trusted side; `runner/outbox.py` (change, T-A-13: dispatch calls `runner/deliverers/github.py` for `pr_create` and `pr_update` instead of the stub deliverer); the `pr_outcome` queue item raised for an already closed or merged remote pull request; `runner/tests/test_deliverer_github.py`; `runner/tests/test_outbox_crash_github.py`; `runner/tests/fixtures/deliverer_github/`; `runner/tests/fixtures/outbox_crash_github/`.

**Out:** the pilot and scratch repositories' configuration and trust-profile scopes (T-AB-04); the credential-fetch mechanism itself (T-AB-01); the `pr_outcome` item's own actions and the manual outcome record (B); the digest's Slack deliverer (T-AB-07); the S6 driver's assembly run and publication-subject hashing (T-A-31, T-A-34).

### Acceptance criteria

1. On the first cycle, no branch or diff is pushed to the scratch repository before full review quorum is reached (R-S6-3)
2. The last quorum-completing `approval_record` and the `pr_create` intent it authorises commit together in one transaction (R-S6-3)
3. Given a ticket with full quorum and no PR identity, the outbox selects `pr_create` (R-S6-3)
4. `pr_create` pushes only the ticket branch to the scratch repository and opens one draft pull request carrying the approved `pr_body` (R-S6-3)
5. On a revision cycle, the existing remote branch and pull request on the scratch repository remain unchanged until reapproval (R-S6-3)
6. Given a ticket already at `pr_opened` with full quorum on a new revision, the outbox selects `pr_update` (R-S6-3)
7. `pr_update` requires the previously reconciled remote head and updates the same branch and body under compare-and-set and `--force-with-lease=<branch>:<expected head>` semantics (R-S6-3)
8. Before dispatch, `runner/deliverers/github.py` rechecks the canonical review-approval subject, the `publication_target` hash, every required approval slot and waiver, the target, base, head and diff, and the trust identity (R-S6-3)
9. A pre-dispatch mismatch on any of those rechecked values supersedes the intent and routes the ticket to `checks`, `planning`, or `context` as the mismatch affects (R-S6-3)
10. `pr_create` never overwrites an unexpected remote head on the scratch repository's branch (R-S6-3)
11. `pr_update` never overwrites an unexpected commit and never opens a replacement pull request (R-S6-3)
12. A non-retryable permission or control failure from `runner/deliverers/github.py` escalates the ticket (R-S6-3)
13. Given a scratch-repository pull request already closed or merged outside the factory, the worker raises the `pr_outcome` queue item instead of dispatching (R-S6-3)
14. A matching receipt from the scratch repository records the remote pull-request identity, head, and body hash, and moves the ticket to `pr_opened` (R-S6-3)
15. Crash injection before send on a `pr_create` intent against `runner/deliverers/github.py` leaves one `external_write` row `pending`, and the retried command produces exactly one remote pull request on the scratch repository (R-S6-3)
16. Crash injection after remote success but before the receipt is stored reconciles on retry to the same remote pull request, with no duplicate (R-S6-3)
17. Two `external_write` rows sharing one `idempotency_key` for the scratch-repository dispatch, with different payload hashes, are refused (R-S6-3)
18. An ambiguous `sending` `external_write` row against the scratch repository's deliverer remains in `review` until reconciled, with no second dispatch (R-S6-3)
19. Publication runs only as trusted outbox work: it is not an agent invocation, an S6 `stage_run`, or a reliability attempt (R-S6-3)
20. `runner/deliverers/github.py` pushes with the `github_publish` role fetched through a credential helper on the trusted side, and the credential value never appears in a row, artefact, or log across the create-then-update sequence (R-S6-3)
21. The push targets only the scratch repository named under `scratch_repository` in `project.yaml`, on its configured throwaway branch prefix (R-S6-3)
22. On the closing run, the outbox worker creates one draft pull request on the scratch repository's throwaway branch and then updates that same pull request (R-S6-3)

### Verification

`runner/tests/test_deliverer_github.py`: criteria 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 19, 20, 21, 22
`runner/tests/fixtures/deliverer_github/`: quorum, revision, pre-dispatch-mismatch, unexpected-head, permission-failure, closed-merged-PR, and receipt fixtures for criteria 1 through 14, 19 through 22
`runner/tests/test_outbox_crash_github.py`: criteria 15, 16, 17, 18
`runner/tests/fixtures/outbox_crash_github/`: crash-before-send, crash-after-success, duplicate-key, and ambiguous-sending fixtures for criteria 15, 16, 17, 18

## T-AB-07: `factory digest`: the Slack post and the scheduler entry

| | |
|---|---|
| Milestone | AB |
| Blocks | 24 External access; 12 Queue item and decision |
| HLD components | C7, C1, H2, E3, E5 |
| Depends on | T-A-12, T-A-13, T-AB-04 |
| Rows covered | R-H-3 |

### Description

The factory never interrupts, so the digest groups T-A-12's open `queue_item` rows by ticket and age and posts them through T-A-13's transactional outbox on a configured cadence instead of any live notification. This ticket builds `factory/scripts/tools/digest`, run by `factory digest` as a `utility_run` with `kind = 'digest'`, which sends nothing for an empty queue and otherwise creates one `external_write` intent keyed by the channel, the cadence slot, and the canonical hash of the item list. Under T-A-07's guard the payload carries only ticket identifier, tier, item kind, age, and local command/link, never ticket text, code, question options, artefact content, or a secret. `runner/deliverers/slack.py` posts it through the official Slack MCP server with the `slack_digest` role, the only Slack write the factory makes. `runner/setup.py` installs the scheduler entry from `project.yaml`'s `digest` key. It sits on T-A-12's queue, T-A-13's outbox, and T-AB-04's Slack route and credential role.

### Scope

**In:** `factory/scripts/tools/digest`; `factory digest` command in `runner/cli.py`; `runner/deliverers/slack.py`; the `slack_digest` role's use of T-AB-01's `runner/credentials.py`; `runner/setup.py` (change: writes the launchd scheduler entry from `project.yaml`'s `digest` key); `factory/config/project.yaml`'s `digest` key (channel, cadence); `runner/tests/test_digest.py`; `factory/evals/scripts/tools/digest/` (eval.yaml, fixtures); `runner/tests/fixtures/digest/`.

**Out:** the Slack route's entry in the trust profile and the `slack_digest` credential role's definition (T-AB-04, T-AB-01); the queue items the digest groups (T-A-12); the outbox's general intent and dispatch mechanism (T-A-13).

### Acceptance criteria

1. Given a seeded set of open `queue_item` rows, `factory digest` in `runner/cli.py` runs `factory/scripts/tools/digest` as a `utility_run` with `kind = 'digest'` (R-H-3)
2. `factory/scripts/tools/digest` groups the seeded open items by ticket and by age (R-H-3)
3. `factory/scripts/tools/digest` run over an empty open-item set creates no `external_write` intent and sends nothing (R-H-3)
4. `factory/scripts/tools/digest` creates one `external_write` row with `operation = 'digest'` and an `idempotency_key` composed of the channel, the cadence slot, and the canonical hash of the item list (R-H-3)
5. A seeded digest payload carrying full ticket text, code, question options, or artefact content is denied by T-A-07's guard before dispatch, and only ticket identifier, tier, item kind, age, and local command/link reach the configured Slack channel (R-H-3)
6. A seeded digest payload carrying a secret is denied by the guard before dispatch (R-H-3)
7. `runner/deliverers/slack.py` posts the digest through the official Slack MCP server's one post tool with the `slack_digest` role, and no other code path posts to Slack (R-H-3)
8. `runner/setup.py` writes a launchd scheduler entry from `project.yaml`'s `digest` key, naming the configured cadence and channel (R-H-3)
9. A second `factory digest` invocation in the same cadence slot over the same open-item set reuses the existing intent's `idempotency_key` and posts nothing a second time (R-H-3)
10. The `slack_digest` credential value never appears in a `queue_item` row, an `external_write` row, an artefact, or a log across the digest post (R-H-3)
11. On the closing run, `factory digest` posts once to the configured Slack channel (R-H-3)

### Verification

`runner/tests/test_digest.py`: criteria 1, 2, 3, 4, 5, 6, 7, 9, 10, 11
`runner/tests/fixtures/digest/`: seeded queue-item, empty-queue, payload-redaction, secret, and duplicate-post fixtures for criteria 1, 2, 3, 4, 5, 6, 9, 10, 11
`runner/tests/test_setup.py`: criterion 8
`factory/evals/scripts/tools/digest/`: eval.yaml, fixtures for criteria 1, 4, 7

## T-AB-08: Pilot recipes, registry policy and dependency verification at base and head in the copies

| | |
|---|---|
| Milestone | AB |
| Blocks | 22 Check; 21 Recipe |
| HLD components | C9, G2, G3, F7, E6 |
| Depends on | T-A-08, T-A-25, T-AB-01, T-AB-04 |
| Rows covered | R-S5-2 |

### Description

Dependency verification runs the pilot repository's pinned resolved-dependency recipe at base and head in clean sandboxes, under the same declared registry and cache policy. It compares the result with the plan, guarding against a fabricated import, an undeclared package, a mutable resolution, or a network source outside the recipe allowlist (FM-05, FM-14, FM-20). This ticket adds the pilot repository's own recipes to `command-recipes.yaml` and builds `factory/scripts/checks/dep_verify`. The proxy admits only recipe-declared registry endpoints for the build sandbox. Its four fixtures run over T-AB-01's copies, standalone from the full ordered check list T-AB-09 assembles. It sits on T-A-08's recipe catalogue, T-A-25's plan Dependencies table, T-AB-01's copies and proxy, and T-AB-04's pilot repository.

### Scope

**In:** `factory/config/command-recipes.yaml` (the pilot repository's recipes, its resolved-dependency recipe among them); `factory/scripts/checks/dep_verify`; `factory/evals/scripts/checks/dep_verify/` (`eval.yaml`, `fixtures/`); `factory/config/sandbox.yaml`'s `proxy_allowlist` entry for the build-sandbox stage at S5, naming the recipe-declared registry endpoints; `runner/tests/test_dep_verify.py`.

**Out:** the full S5 ordered check list and binding `dep_verify`'s result to the review tuple (T-AB-09); the security recipes and `security-checks.yaml` content (T-AB-09); the base and head copy-on-write copies themselves (T-AB-01); the pilot repository and its trust-profile route (T-AB-04).

### Acceptance criteria

1. `factory/config/command-recipes.yaml` gains the pilot repository's recipes, including a pinned resolved-dependency recipe with its declared registry and cache policy (R-S5-2)
2. `dep_verify` runs that resolved-dependency recipe at base inside a clean build sandbox over T-AB-01's base copy, under the recipe's declared registry and cache policy (R-S5-2)
3. `dep_verify` runs the same recipe at head inside a clean build sandbox over T-AB-01's head copy, under the identical declared registry and cache policy (R-S5-2)
4. `dep_verify` compares the base and head resolved-dependency results with the approved plan's Dependencies table `package`, `from_version`, `to_version` and `kind` values (R-S5-2)
5. A seeded fixture with a fabricated import unresolvable at head: `dep_verify` writes `check_result.result = 'fail'` naming the unresolvable import (R-S5-2)
6. A seeded fixture with an undeclared package or version change absent from the plan's Dependencies table: `dep_verify` writes `check_result.result = 'fail'` naming the undeclared change (R-S5-2)
7. A seeded fixture with a mutable or unpinned dependency resolution the pilot repository's project policy forbids: `dep_verify` writes `check_result.result = 'fail'` naming the forbidden resolution (R-S5-2)
8. A seeded fixture with a required network source outside the recipe's declared allowlist: `dep_verify` writes `check_result.result = 'fail'`, and the loopback proxy refuses the connection and logs its route id (R-S5-2)
9. `sandbox.yaml`'s `proxy_allowlist` for the build-sandbox stage at S5 admits only the recipe-declared registry endpoints the pilot repository's resolved-dependency recipe names (R-S5-2)
10. A `dep_verify` pass reports resolved-dependency results only and asserts no service-impact completeness claim, matching R-S1-3's package-versus-impact distinction (R-S5-2)

### Verification

`runner/tests/test_dep_verify.py`: criteria 1, 2, 3, 4, 9, 10
`factory/evals/scripts/checks/dep_verify/eval.yaml`, `factory/evals/scripts/checks/dep_verify/fixtures/`: fabricated-import, undeclared-package, mutable-resolution, and network-policy fixtures for criteria 5, 6, 7, 8

## T-AB-09: S5 full order inside the base and head copies with the security recipes

| | |
|---|---|
| Milestone | AB |
| Blocks | 22 Check; 20 Sandbox |
| HLD components | C9, G2, G3, F6, F7, E6 |
| Depends on | T-A-29, T-A-30, T-A-32, T-AB-01, T-AB-08 |
| Rows covered | R-S5-1 |

### Description

The blocking tier at AB moves from A's plain checkouts into T-AB-01's copy-on-write base and head views. The ordered check list grows to the security recipes `security-checks.yaml` pins and T-AB-08's dependency verification, so untrusted execution never escapes its bounds (C9, C10, FM-05, FM-15, FM-20, FM-23). Preflight still verifies plan approval, identity and digests before any copy is provisioned, and only its success creates the review tuple T-A-10 built. Every result binds that one tuple. A red result inside lint, compile-type, unit-test or integration-test recipes first takes T-A-29's fix rounds; an end-to-end red never does. The rest aggregate into one `red_check` item under T-A-32's waiver policy. It sits on T-A-29's fix-round routing, T-A-30's ordered-check driver, T-A-32's waivers, T-AB-01's copies, and T-AB-08's dependency verification.

### Scope

**In:** `runner/stages/S5.py` moved from plain checkouts into T-AB-01's base and head copies, wired to the full ordered list: the pilot repository's lint, compile/type, unit-test, integration-test and end-to-end recipes, `base_test_diff` and R-S4-10's planned-change runs, `security_checks`, T-AB-08's `dep_verify`, `size_gate`, `scope_diff`, `source_declaration_diff`, `behavior_contract_evidence`, and approval-binding; `factory/scripts/checks/security_checks`; `factory/config/security-checks.yaml` (real content for the pilot repository: tool or image, ruleset and vulnerability-database digests, severity thresholds, owned expiring suppressions, unavailable-feed behaviour, `waiver-policy.yaml` references); `factory/evals/scripts/checks/security_checks/` (`eval.yaml`, `fixtures/`); `runner/tests/test_s5_ab_order.py`, `test_s5_ab_blind_spot.py`, `test_s5_ab_fix_routing.py`.

**Out:** R-S5-13's waiver mechanism itself, already built (T-A-32); the base and head copies and the loopback proxy themselves (T-AB-01); `dep_verify`'s own script and its four fixtures (T-AB-08); the dry run of every pilot recipe for the adoption gate's copy-disposal fixture (T-AB-11).

### Acceptance criteria

1. Preflight verifies current plan approval and quorum before repository execution starts (R-S5-1)
2. Preflight verifies target, base, head, diff and deviation identity before repository execution starts (R-S5-1)
3. Preflight verifies trust and execution digests before repository execution starts (R-S5-1)
4. Preflight verifies R-S6-6's final reviewer ownership before repository execution starts (R-S5-1)
5. Only a preflight success creates the review tuple; a failed preflight creates none (R-S5-1)
6. A construction failure records exactly one `review_tuple_preflight` check_result and stops, inventing no result for an unrun check (R-S5-1)
7. On preflight success, T-AB-01's build sandbox provisions separate clean base and head copy-on-write views over the pilot repository's immutable checkouts, each with isolated empty build-output, scratch and cache directories (R-S5-1)
8. The S5 driver runs, in order, the pilot repository's lint, compile or type, unit-test and integration-test recipes, and its end-to-end recipe where the repository registers one (R-S5-1)
9. The ordered list continues with the `base_test_diff` and planned-change runs of R-S4-10 (R-S5-1)
10. The ordered list continues with the mandatory secret-scanning, static-analysis, dependency-vulnerability and licence-policy recipes `security-checks.yaml` declares (R-S5-1)
11. The ordered list continues with T-AB-08's dependency verification (R-S5-1)
12. The ordered list continues with size, scope, source-declaration comparison, behavioural-contract evidence and final approval-binding (R-S5-1)
13. Every recipe in the ordered list runs inside the build sandbox (R-S5-1)
14. The size, scope, source-declaration, behavioural-contract, dependency-verification and approval-binding scripts run on the trusted side over that evidence and the immutable checkouts, never inside a sandbox (R-S5-1)
15. `security-checks.yaml` pins each security recipe's tool or image digest, ruleset digest, vulnerability-database digest, severity threshold, owned and expiring suppressions, and unavailable-feed behaviour for the pilot repository (R-S5-1)
16. `security-checks.yaml` names its specific `waiver-policy.yaml` references for a security-recipe blind spot (R-S5-1)
17. Every result the ordered list produces binds the same review tuple (R-S5-1)
18. Except for a tuple-construction or sandbox-integrity failure, the ordered list continues running after a red result instead of stopping (R-S5-1)
19. A seeded test recipe whose declared network policy or dependencies the build sandbox cannot satisfy does not run, and records one `blind_spot` naming the unmet dependency, waivable under R-S5-13 and listed in the evidence table (R-S5-1)
20. A red result confined to the pilot repository's lint, compile or type, unit-test and integration-test recipes first takes the fix rounds of R-S4-9 before forming a `red_check` item (R-S5-1)
21. A red end-to-end result never takes the fix-round route and instead forms a `red_check` item directly (R-S5-1)
22. Every failure and waivable blind spot outside the fix-round route aggregates into one `red_check` item that advances only under an R-S5-13 waiver (R-S5-1)
23. Every control in the ordered list runs locally inside the sandbox or on the trusted side, with no substitution by an external CI check (R-S5-1)
24. A's fixture ticket walks S5 again inside the base and head copies with the security recipes and dependency verification, every result bound to one review tuple, one red result routed through R-S5-13 with one blind spot waived, and the copies disposed of (R-S5-1)

### Verification

`runner/tests/test_s5_ab_order.py`: criteria 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 17, 18, 23, 24
`factory/evals/scripts/checks/security_checks/eval.yaml`, `factory/evals/scripts/checks/security_checks/fixtures/`: criteria 10, 15, 16
`runner/tests/test_s5_ab_blind_spot.py`: criterion 19
`runner/tests/test_s5_ab_fix_routing.py`: criteria 20, 21, 22

## T-AB-10: Baseline: retrospective and supplemental cohorts read, measured, frozen

| | |
|---|---|
| Milestone | AB |
| Blocks | 17 Record; 24 External access |
| HLD components | R5, R1, C7, E1, E2 |
| Depends on | T-A-05, T-A-11, T-AB-04 |
| Rows covered | R-O-6 |

### Description

Before the first real factory ticket enters Milestone B, the runner selects the ten most recent completed, agent-assisted tickets matching the pilot service and an admitted ticket type. It reads their Jira, Confluence and GitHub history to build a retrospective baseline the graduation gate of R-O-13 later compares against (P1, P7, FM-09, FM-10). `factory/scripts/tools/baseline_import` runs as a `utility_run`, writing `baseline = true` `ticket` rows and `baseline_measure` rows. A value the history cannot supply is marked `approximate` or `unavailable`, never invented or omitted. A supplemental prospective cohort completes the count when the retrospective one yields fewer than ten comparable revision values. The combined cohort is frozen before Milestone B, after which the write path refuses any further baseline row. This ticket sits on T-A-05's `utility_run` kind, T-A-11's dedicated baseline views, and T-AB-04's Atlassian reader and pilot repository.

### Scope

**In:** `factory/scripts/tools/baseline_import`; `factory/evals/scripts/tools/baseline_import/` (`eval.yaml`, `fixtures/`); `runner/readers/github.py` (GitHub REST API pull-request-history reads, `github_publish` role, baseline only); the baseline read added to `runner/readers/atlassian.py`; `baseline_measure` rows for the retrospective and supplemental cohorts; `ticket` rows with `baseline = true`; the selection artefact's `frozen_at` field and the frozen write-path refusal on `baseline_measure` and baseline `ticket` writes; `runner/tests/test_baseline_import.py`.

**Out:** the graduation gate's clause-by-clause comparison against the baseline (B, R-O-13); the manual outcome record the baseline eventually compares against (B); the dedicated baseline SQL views themselves, already built at T-A-11; the pilot repository's Atlassian route and credential fetch (T-AB-04).

### Acceptance criteria

1. `factory/scripts/tools/baseline_import`, run as a `utility_run` with `kind = 'baseline_import'`, selects the ten most recent completed, agent-assisted tickets matching the pilot service and an admitted ticket type before a recorded cutoff (R-O-6)
2. The selection query, cutoff, included and excluded ticket ids, and immutable source locators are registered as one governed artefact the `utility_run` creates (R-O-6)
3. `baseline_import` reads the retrospective cohort's Jira and Confluence history through `runner/readers/atlassian.py` with the `atlassian_read` role (R-O-6)
4. `baseline_import` reads the retrospective cohort's pull-request history through `runner/readers/github.py` with the `github_publish` role (R-O-6)
5. `baseline_import` writes one `ticket` row with `baseline = true` for each selected retrospective ticket, with factory bindings, state and lifecycle timestamps null (R-O-6)
6. `baseline_import` writes one `baseline_measure` row per selected ticket for post-plan revisions, the measure R-O-13's graduation gate compares (R-O-6)
7. `baseline_import` writes one further `baseline_measure` row per selected ticket for each additional measure `scripts/tools/report` requests (R-O-6)
8. A `baseline_measure` row whose value the retrospective history cannot supply carries `status = 'approximate'` or `status = 'unavailable'`, never an omitted row (R-O-6)
9. A revision counts toward post-plan revisions only when a timestamped approved plan or an equivalent recorded design decision exists for that ticket (R-O-6)
10. A seeded ticket whose only evidence is a PR opening or a first review, with no timestamped approved plan or equivalent design decision, records `status = 'unavailable'` for post-plan revisions (R-O-6)
11. A retrospective ticket's question, latency, or attention `baseline_measure` values carry `status = 'approximate'` (R-O-6)
12. A `baseline_measure` value with missing, mismatched, or non-attributable source evidence carries `status = 'unavailable'`, never `0` (R-O-6)
13. A seeded retrospective selection yielding fewer than ten comparable `observed` revision values triggers a supplemental cohort of prospectively observed, current-workflow, non-factory tickets on the identical endpoint (R-O-6)
14. The supplemental cohort's cutoff is recorded separately from the retrospective cohort's cutoff (R-O-6)
15. The supplemental cohort's `baseline_measure` rows carry the same `measure_definition_hash` as the retrospective cohort's rows for the same measure (R-O-6)
16. `baseline_import`'s freeze writes a `frozen_at` field on the selection artefact's record once the combined retrospective and supplemental cohort is complete (R-O-6)
17. After `frozen_at` is set, the write path refuses a new `baseline_measure` or baseline `ticket` row for that cohort (R-O-6)
18. A seeded attempt to add a baseline row after real factory results exist is refused by the frozen write path (R-O-6)
19. The combined cohort is frozen before any real ticket enters Milestone B (R-O-6)
20. T-A-11's dedicated baseline views read the seeded `baseline_measure` rows this ticket writes without requiring a pre-factory manifest (R-O-6)
21. No credential value `runner/readers/atlassian.py` or `runner/readers/github.py` uses during the baseline read appears in the `utility_run` row, the selection artefact, or any log (R-O-6)
22. The baseline cohort is read from the pilot service's real pre-factory Jira, Confluence and GitHub history, its retrospective and supplemental endpoints checked as equivalent, frozen once and never backfilled (R-O-6)

### Verification

`runner/tests/test_baseline_import.py`: criteria 1, 2, 3, 4, 5, 6, 7, 11, 14, 15, 19, 20, 21
`factory/evals/scripts/tools/baseline_import/eval.yaml`, `factory/evals/scripts/tools/baseline_import/fixtures/`: retrospective-cohort, supplemental-cohort, unavailable-value, and frozen-write fixtures for criteria 8, 9, 10, 12, 13, 16, 17, 18, 22

## T-AB-11: Adoption gate complete: escape, copy-disposal and history fixtures, the dry run of every pilot recipe, the required check

| | |
|---|---|
| Milestone | AB |
| Blocks | 7 Fixtures and evals; 8 Factory tree and change control |
| HLD components | F8, F1 |
| Depends on | T-A-35, T-AB-01, T-AB-02, T-AB-03, T-AB-04, T-AB-05, T-AB-06, T-AB-07, T-AB-08, T-AB-09, T-AB-10 |
| Rows covered | R-F-14 |

### Description

The Initial adoption gate proves mechanics, not subjective output quality, over deterministic fixtures naming a target failure mode (C6, P2, P10). T-A-35 completed the gate's walk over every fixture that exists without the OS sandbox. This ticket adds the sandbox-escape and copy-disposal fixtures the sandbox now makes possible, and the incident, control and coverage history fixtures over seeded rows the record already holds from A. It runs a dry run of every recipe on the pilot repository's current base, in a base and head copy, records results, and disposes of both copies. That dry run is the copy-disposal fixture on the real repository. `runner/gate.py` becomes the required check of R-F-4's reviewed-change path and of the milestone-closing run. It sits on T-A-35's gate and every other AB ticket whose mechanism it exercises.

### Scope

**In:** `factory/evals/sandbox/copy-disposal/` (`eval.yaml`, `fixtures/`); `factory/evals/record/incident-history/`, `factory/evals/record/control-history/`, `factory/evals/record/coverage-history/` (each `eval.yaml`, `fixtures/`); the dry run of every pilot recipe on the pilot repository's current base in a base and head copy, recorded and disposed of; the AB eval-kind walk added to `runner/gate.py`; `runner/gate.py`'s required-check wiring into R-F-4's reviewed-change path and the milestone-closing run; `runner/tests/test_gate_ab.py`.

**Out:** the escape suite's own eleven-category fixtures and `runner/tests/test_escape_suite.py` (T-AB-01); branch protection making the gate enforced at the repository level (Later, R-F-9); calibrated quality and holdout grading (Later, R-F-3, R-F-8).

### Acceptance criteria

1. `factory/evals/sandbox/escape/` (`eval.yaml`, the eleven-category `fixtures/` T-AB-01 builds) is registered in the gate's fixture list, naming its target failure-mode ids (R-F-14)
2. `factory/evals/sandbox/copy-disposal/` (`eval.yaml`, `fixtures/`) is registered in the gate's fixture list, naming its target failure-mode ids (R-F-14)
3. A dry run of every recipe `command-recipes.yaml` names for the pilot repository's current base runs in a base and a head copy-on-write copy T-AB-01's `runner/sandbox/copies.py` provisions, and records one result per recipe (R-F-14)
4. The dry run disposes of both copies afterward, and its recorded results and disposal are `factory/evals/sandbox/copy-disposal/`'s fixture on the real pilot repository (R-F-14)
5. `factory/evals/record/incident-history/` (`eval.yaml`, `fixtures/`) holds a seeded fixture of `incident_observation` rows the record already holds from A, naming its target failure-mode ids (R-F-14)
6. `factory/evals/record/control-history/` (`eval.yaml`, `fixtures/`) holds a seeded fixture of `incident_observation` rows with `record_kind = 'control_defect_event'` the record already holds from A, naming its target failure-mode ids (R-F-14)
7. `factory/evals/record/coverage-history/` (`eval.yaml`, `fixtures/`) holds a seeded fixture of coverage `check_result` and `tag` rows the record already holds from A, naming its target failure-mode ids (R-F-14)
8. `runner/gate.py` walks `factory/evals/sandbox/escape/`, `sandbox/copy-disposal/`, `record/incident-history/`, `record/control-history/`, and `record/coverage-history/` alongside the directories T-A-35 already walks, and fails when any is missing, empty, unredacted, or unowned (R-F-14)
9. `runner/gate.py` is the required check of R-F-4's reviewed-change path over `factory/`, so a change failing it is not an adopted change (R-F-14)
10. `runner/gate.py` is the required check of the milestone-closing run, so a failing fixture stops that run (R-F-14)
11. A versioned change to a mechanism this ticket's five eval directories cover names its target failure-mode id in the changed `eval.yaml` (R-F-14)
12. A versioned change to a mechanism this ticket's five eval directories cover, whose behaviour changes, adds or updates a fixture in the matching directory before `runner/gate.py` passes it (R-F-14)
13. `runner/gate.py` reports pass or fail over the escape, copy-disposal, and three history fixtures as mechanics, with no subjective-quality score (R-F-14)
14. For each of the escape-suite, copy-disposal, incident-history, control-history, and coverage-history fixtures, a seeded failing fixture makes `runner/gate.py` exit non-zero when run as `python3 -m runner.gate` (R-F-14)

### Verification

`runner/tests/test_gate_ab.py`: criteria 1, 2, 8, 9, 10, 11, 12, 13, 14
`factory/evals/sandbox/copy-disposal/eval.yaml`, `factory/evals/sandbox/copy-disposal/fixtures/`: criteria 2, 3, 4
`factory/evals/record/incident-history/eval.yaml`, `factory/evals/record/incident-history/fixtures/`: criterion 5
`factory/evals/record/control-history/eval.yaml`, `factory/evals/record/control-history/fixtures/`: criterion 6
`factory/evals/record/coverage-history/eval.yaml`, `factory/evals/record/coverage-history/fixtures/`: criterion 7
