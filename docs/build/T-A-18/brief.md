# T-A-18 brief: Cursor SDK adapter, invocation envelope, thin sandbox, tool-call rows

## What this delivers

The first runtime adapter, the first real invocation boundary, and the
first governed record of what an agent invocation actually received and
returned. Before this ticket, no code path could invoke a model at all;
after it, `runner/adapters/cursor_sdk.py` can turn a resolved manifest
entry into one fresh, sandboxed invocation, recorded as its own
`stage_run` with a reconstructable envelope, one `tool_call` row per call,
and a cost figure carrying honest provenance -- while `S1` to `S4` stay
stubs, since no ticket before this one has built real per-stage agent
content for them to invoke.

- `runner/envelope.py` -- `build(conn, ticket, stage_run_id, entry, *,
  adapter_version=None, sandbox_path=...) -> Envelope`: the ticket's
  latest-version artefacts (ordered by kind, since the manifest does not
  yet name per-stage input kinds -- that lands with its full field set),
  the manifest entry's file hashes, the ticket's pinned trust hashes, the
  recipe-set hash, the sandbox and toolchain digests, base/head SHAs, data
  class, tool allowlist, and the plan-/review-approval subject bound for
  `S3`/`S5`/`S6` alone. `reconstruct(conn, stage_run_id, *, runs_dir=...)
  -> Envelope` rebuilds the same shape from the `stage_run` row, the
  ticket, the artefact rows the run's own `inputs` column names, and (for
  `provider_request_id` alone, unknowable before the invocation runs) the
  run's own `results/stdout.json`. `sandbox_digest`, `toolchain_digest`,
  and `recipe_set_hash` are computed here since both the envelope and the
  `stage_run` row need the identical value.
- `runner/launcher.py` -- `launch(*, run_dir, argv, role, policy, cwd,
  wall_clock_seconds, ...)`: builds the child's whole environment from
  `sandbox.yaml`'s allowlist (starting empty, copying in only allowlisted
  names, injecting the scoped runtime key for the `agent` role and never
  for `build`), starts codegraph as the child's only local server when its
  command resolves on the allowlisted `PATH`, runs the child with a
  timeout, and writes `results/child.pid`, `results/stdout.json`,
  `results/stderr.txt`, `results/exit.json` -- the only writer under
  `results/`. `_check_integrity` compares the child's self-reported
  `environment_names`/`files_written` against what the sandbox actually
  allowed and returns a `SandboxIntegrity` verdict on every launch.
  `terminate_child(run_dir)` kills a still-live child by its recorded pid.
- `runner/adapters/cursor_sdk_worker.py` -- the untrusted `__main__`
  child: reads the envelope path from `argv[1]`, drives one Cursor SDK
  local-runtime agent turn with `setting_sources=[]`, and prints exactly
  one JSON document (`model_resolved`, `provider_request_id`, `status`,
  `tokens_in`/`tokens_out`, `duration_ms`, cost group, `reasoning_summary`,
  `tool_calls`, plus `environment_names`/`files_written` for the sandbox
  check). Never opens the database.
- `runner/adapters/cursor_sdk.py` -- `invoke(conn, *, ticket, stage,
  tier, entry, runs_dir=..., parent_run_id=None, ...) -> InvocationResult`:
  the requested-model check against `runtime.yaml` before anything opens;
  opens its own `stage_run` (so a child invocation under `parent_run_id`
  gets its own row, own lease, own everything); builds and writes the
  envelope; launches the worker; classifies the outcome (sandbox
  violation first, then timeout, then a resolved-model mismatch, then the
  worker's own status); records one `tool_call` row per call, applying the
  `limits.yaml` inline rule; registers `out/`'s files as artefacts, unless
  the run mismatched its model (no output registered); sets
  `replayability`; settles cost under the price-table rule; finishes the
  run.
- `factory/config/limits.yaml`, `factory/config/pricing.yaml`,
  `factory/config/sandbox.yaml`, `factory/config/runtime.yaml`: see
  "Config files" below.
- `factory/evals/adapters/cursor_sdk/` -- `eval.yaml` naming five cases
  (settled, runtime_estimate, price_table, null_cost, silent_fallback) and
  their canned JSON documents under `fixtures/`; `test_adapter.py` walks
  them through the real adapter with the fixture worker.
- `runner/tests/test_adapter.py`, `runner/tests/test_sandbox.py`,
  `runner/tests/fixtures/adapter/` (`fixture_worker.py`, a test copy of
  `runtime.yaml` and `sandbox.yaml`).

## Row covered

R-I-2, R-I-13, R-I-15 (`docs/prd/03-stage-interface.md`): a fresh
invocation receives only the governed artefacts and rubric the manifest
names, nothing from an earlier attempt or user-level configuration; the
adapter returns every available usage/cost/duration/outcome field and one
`tool_call` row per call, with cost basis and price-table hash recorded
honestly; the envelope is reconstructable from the record alone and binds
the governance and execution-boundary identities in force.

## Owner decisions this ticket follows

- Two processes, one JSON contract: the worker never touches the record,
  the parent adapter builds the envelope, launches the sandbox, and writes
  everything under `results/`.
- A model absent from `runtime.yaml`'s list is refused before any
  `stage_run` opens; a resolved model different from the requested one is
  `infrastructure_failure` with no output registered.
- The sandbox digest is the file bytes plus the resolved allowlist; the
  toolchain digest is the toolchain mapping plus the JDK version actually
  found on `PATH`, null (never estimated) when there is none.
- A tool result under `limits.yaml`'s inline bound is recorded by digest
  and byte count alone; over it, the full result and an excerpt sidecar
  land under `results/tool_calls/`, registered as a `tool_result`
  artefact.
- `replayability` is `best_effort`, naming the gap, when the resolved
  model carries no immutable build/version suffix or a tool result could
  not be retained; `exact` only when both hold.
- A child invocation (a restatement sub-run, for instance) is its own
  `stage_run` under `parent_run_id`, with its own runtime, model, tokens,
  cost, and wall clock.
- `control.stop` kills the launcher's child (by the pid `results/child.pid`
  names) before finishing each open run `aborted_human`.

## Config files

- `factory/config/limits.yaml`: `tool_result_inline` (200 lines / 8 KB,
  40/20-line excerpt truncated to 4 KB per end), matching section 8.
- `factory/config/pricing.yaml`: dated, `claude-sonnet-5` priced per
  million input/output tokens, used only under the price-table rule.
- `factory/config/sandbox.yaml`: the `thin` policy -- environment
  allowlist, per-role credential rule (`agent` gets the named runtime key,
  `build` gets none), and the codegraph command.
- `factory/config/runtime.yaml`: the `cursor_sdk` adapter's package,
  version, worker command, approved model list, and key role name.

## Decisions this brief did not already settle

- **The invocation's identity is written at insert; only its result
  settles in place.** The envelope is built before the run's row opens
  (its content never depends on the run id), so `run_ledger.open_stage_run`
  takes the identity fields an adapter knows before dispatch -- runtime and
  versions, requested model, agent/skill/rubric refs, manifest and trust
  hashes, tool allowlist, digests, ordered inputs, `envelope_hash` -- as
  insert-time keywords and those columns stay immutable. The seven fields
  a run learns only after it ends (`model_resolved`, `outputs`,
  `tokens_in`, `tokens_out`, `wall_clock_seconds`, `replayability`,
  `replayability_blind_spot`) are the only new mutable columns, written by
  the one new ledger function `run_ledger.record_invocation_result`, the
  same way `reasoning_summary` already settles. COMMON.md's seam rule
  (every `stage_run` write goes through `run_ledger`) is why the function
  lives there rather than in adapter code; keeping the identity immutable
  is why the split exists instead of one uniform write-after-open rule.
  `runner/tests/test_mutable_exceptions.py`'s hand-written allowlist is
  extended by exactly those seven; `USER_VERSION` moves with the schema
  change.
- **`envelope.build`'s "inputs"** are every one of the ticket's
  latest-version artefacts, ordered by kind, rather than a per-stage
  subset. The manifest does not yet name, per stage, which artefact kinds
  a stage reads -- that field set lands with T-A-19 -- so a stage-specific
  filter would mean inventing PRD content this ticket was not asked to
  write. This is a real, temporary narrowing: every stub stage before S1
  in a fresh ticket contributes no prior artefact anyway, so the two
  behaviours coincide until real per-stage content exists to tell them
  apart.
- **`reconstruct`'s `shared_skill_hashes` is always empty.** `stage_run`
  carries single `agent_ref`/`skill_ref`/`rubric_ref` columns but no
  column for a list of shared-skill hashes, and this ticket's shared,
  minimal schema edit is `envelope_hash`/`replayability`/
  `replayability_blind_spot` alone. Every entry this ticket's own tests
  and fixtures exercise sets `shared_skills: []`, so the gap is invisible
  today; a later ticket that gives a stage real shared skills is the one
  that should decide where that list is recorded.
- **No `args_artefact` is ever registered for a tool call.** The PRD
  entity table allows it null "when the data is derivable from another
  registered input or declared unavailable"; T-A-18's own acceptance
  criteria never name it, only the result-side inline rule (criterion 17),
  so args stay digested (`args_digest`) but not separately persisted.
- **A sandbox-integrity result is recorded through `outcome`/
  `failure_kind` alone**, not a new column: every launch computes a
  `SandboxIntegrity` verdict, and a violation becomes
  `sandbox_violation`/`sandbox_integrity` on the `stage_run`; a passing
  check has no dedicated row of its own, since no schema addition for one
  was in scope.
- **`__CF_USER_TEXT_ENCODING` and `LC_CTYPE`** are excluded from the
  sandbox-integrity check's allowlist comparison: macOS's own
  process-spawning runtime injects them into a child's environment
  regardless of what `env=` names, so counting either as a leak would
  make every launch on this host a false-positive violation. Documented
  in `runner/launcher.py` where the exclusion lives.
- **`invoke`'s "seam" in `runner/stages/__init__.py` (`invoke_agent`)
  always opens its own `stage_run`,** matching "the adapter's entry point
  takes `parent_run_id`" literally: no stub driver calls it yet, so how it
  composes with `run_stage`'s own generic open/finish wrapping for a real
  future agent stage is left to the ticket that wires real content, named
  explicitly in the function's own docstring.

## Out of scope

The manifest's full field set, fail-closed resolution, and per-stage
input-kind list (T-A-19); real per-stage agent, skill, and rubric content
for `S1` to `S4` (T-A-21 onward); the OS policy, copy-on-write copies, the
loopback proxy, and the escape suite (absent at Milestone A); budget abort
and the per-ticket S4 budget (T-A-19); dedicated unavailable-model and
resolved-model-mismatch fixtures beyond the silent-fallback case this
ticket's own criteria name (T-A-19 owns those fixtures, though the
mechanism they will exercise is built and lightly tested here).
