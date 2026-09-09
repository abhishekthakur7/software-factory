"""The Cursor SDK runtime adapter: pinned runner code that turns a manifest entry into one governed invocation.

`invoke` is the whole contract of R-I-13: given a resolved manifest
`Entry`, it opens the invocation's own `stage_run` (so a child sub-run
opened with `parent_run_id` is a full row with its own lease, runtime,
model, tokens, cost and wall clock, per R-I-2 criterion 7), checks the
requested model against `runtime.yaml` before anything starts, fetches the
scoped runtime key at the moment of launch when the stage's sandbox admits
one, builds and writes the R-I-15 envelope, launches the worker inside the
enforced sandbox through `runner/launcher.py`, and turns what comes back
into: one `tool_call` row per call, registered `out/` artefacts (skipped
entirely on a resolved-model mismatch -- "no output registered"), a
settled cost group, and a `replayability` verdict. Every field the worker
did not report stays null; nothing here estimates a token count, a
duration, or a per-call usage figure.
"""
import hashlib
import re
import sqlite3
import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml

from runner import artefact_registry, budgets, canonical, credentials, trust_profile
from runner import envelope as envelope_mod
from runner import launcher, record, run_ledger, tool_results
from runner.sandbox import proxy
from runner.fs import write_text
from runner.paths import FACTORY_DIR, RUNS_DIR

RUNTIME_PATH = FACTORY_DIR / "config" / "runtime.yaml"
PRICING_PATH = FACTORY_DIR / "config" / "pricing.yaml"
LIMITS_PATH = FACTORY_DIR / "config" / "limits.yaml"

# This adapter module's own pinned version -- distinct from the SDK
# package version `entry.runtime_version` names -- bumped when this
# module's behavior changes in a way that could affect a run's outcome.
ADAPTER_VERSION = "1"

# `credentials.fetch`'s own default, resolved here rather than baked into
# `invoke`'s keyword default so a test suite can point every invocation at
# a fake Keychain lookup by patching this one module attribute (matching
# how `RUNTIME_PATH` above is resolved at call time, not at import).
CREDENTIAL_RUN = subprocess.run

# A model id carries an immutable build/version suffix when it names a
# concrete pinned revision (an "@digest" pin, or a date-like build stamp
# of six or more digits); a bare model family id like "claude-sonnet-5"
# does not, and replayability is best_effort until the runtime returns one.
_BUILD_SUFFIX_RE = re.compile(r"(@|-\d{6,})")


@dataclass(frozen=True)
class InvocationResult:
    stage_run_id: int
    outcome: str
    failure_kind: str | None
    model_requested: str | None
    model_resolved: str | None
    provider_request_id: str | None
    tokens_in: int | None
    tokens_out: int | None
    wall_clock_seconds: float | None
    cost: float | None
    currency: str | None
    cost_basis: str
    pricing_table_hash: str | None
    reasoning_summary: str | None
    tool_call_ids: tuple[int, ...]
    replayability: str
    replayability_blind_spot: str | None
    envelope_hash: str | None


def _yaml(path: Path) -> dict:
    return yaml.safe_load(Path(path).read_text())


def _run_dir(runs_dir: Path, ticket_id: int, stage_run_id: int) -> Path:
    return Path(runs_dir) / "tickets" / str(ticket_id) / "runs" / str(stage_run_id)


def no_run_result(
    outcome: str, *, failure_kind: str | None = None, model_requested: str | None = None, blind_spot: str | None = None,
) -> InvocationResult:
    """The result of an invocation that never opened a `stage_run`: `stage_run_id` is -1 and nothing is settled.

    Used for a refusal decided before any run exists (an unavailable
    model, a manifest-pin mismatch) and for a script-only stage that has
    no agent to invoke, so every caller of `invoke` handles one shape.
    """
    return InvocationResult(
        stage_run_id=-1, outcome=outcome, failure_kind=failure_kind,
        model_requested=model_requested, model_resolved=None, provider_request_id=None,
        tokens_in=None, tokens_out=None, wall_clock_seconds=None, cost=None, currency=None,
        cost_basis="unavailable", pricing_table_hash=None, reasoning_summary=None, tool_call_ids=(),
        replayability="best_effort", replayability_blind_spot=blind_spot, envelope_hash=None,
    )


def _refuse_unavailable_model(model_requested: str | None) -> InvocationResult:
    """No `stage_run` at all: R-I-4's unavailable-model check runs before any run is opened."""
    return no_run_result(
        "infrastructure_failure", failure_kind="infrastructure", model_requested=model_requested,
        blind_spot="model unavailable before invocation started",
    )


def _has_immutable_build(model_resolved: str | None) -> bool:
    return model_resolved is not None and bool(_BUILD_SUFFIX_RE.search(model_resolved))


def _record_tool_calls(
    conn: sqlite3.Connection, *, ticket_id: int, stage_run_id: int, tool_calls: list[dict],
    run_dir: Path, inline_rule: dict,
) -> tuple[int, ...]:
    """One governed `tool_call` row per call; a result over the inline limit lands as a `tool_result` artefact.

    Every result the worker reports already reached the agent as text (a
    string, or a value this function serializes to its canonical JSON), so
    shaping always runs with `media_type="text/plain"` -- `tool_results.shape`'s
    non-text case belongs to the proxy's raw-bytes calls, never a direct
    call's. A result within the limit is recorded by digest and byte count
    alone (`inline = 1`) -- it already reached the agent's own context
    transiently through the runtime, so the ledger's job is proving it was
    small and unmodified, not storing a second copy. A result over the
    limit is written whole to `results/tool_calls/<seq>.txt`, registered as
    a `tool_result` artefact, and given a sidecar excerpt file at
    `<seq>.excerpt.txt` next to it when the shaping produced one --
    discoverable by that naming convention rather than by an extra column.
    """
    ids: list[int] = []
    # Proxy-routed calls were numbered as they happened, during the run;
    # the worker's own numbering starts at 1, so it continues after them.
    seq_base = proxy.next_seq(conn, stage_run_id) - 1
    for call in tool_calls:
        seq = seq_base + call["seq"] if call.get("seq") is not None else None
        args = call.get("args")
        result = call.get("result")
        args_text = canonical.canonical_json(args).decode() if args is not None else None
        result_text = (
            result if isinstance(result, str) else (canonical.canonical_json(result).decode() if result is not None else None)
        )
        args_digest = hashlib.sha256(args_text.encode()).hexdigest() if args_text is not None else None
        result_digest = hashlib.sha256(result_text.encode()).hexdigest() if result_text is not None else None
        result_artefact_id = None
        shaped = None
        if result_text is not None:
            shaped = tool_results.shape(result_text.encode(), media_type="text/plain", rule=inline_rule)
            if not shaped.inline:
                full_path = run_dir / "results" / "tool_calls" / f"{seq}.txt"
                write_text(full_path, result_text)
                if shaped.excerpt is not None:
                    write_text(run_dir / "results" / "tool_calls" / f"{seq}.excerpt.txt", shaped.excerpt)
                result_artefact_id = artefact_registry.register(
                    conn, ticket_id=ticket_id, kind="tool_result", path=full_path, stage_run_id=stage_run_id,
                )
        row_id = record.insert(
            conn, "tool_call",
            stage_run_id=stage_run_id, seq=seq, tool=call.get("tool"), tool_version=call.get("tool_version"),
            args_digest=args_digest, result_digest=result_digest, result_artefact=result_artefact_id,
            duration_ms=call.get("duration_ms"), tokens=call.get("tokens"),
            result_bytes=shaped.result_bytes if shaped is not None else None,
            inline=1 if (shaped is None or shaped.inline) else 0,
        )
        ids.append(row_id)
    return tuple(ids)


def _register_outputs(conn: sqlite3.Connection, *, ticket_id: int, stage_run_id: int, out_dir: Path) -> tuple[int, ...]:
    ids = []
    for path in sorted(out_dir.rglob("*")):
        if path.is_file():
            ids.append(
                artefact_registry.register(conn, ticket_id=ticket_id, kind="agent_output", path=path, stage_run_id=stage_run_id)
            )
    return tuple(ids)


def _replayability(*, model_resolved: str | None, retention_blind_spot: str | None) -> tuple[str, str | None]:
    """`exact` only when the resolved model names an immutable build and every tool result was retainable.

    `retention_blind_spot` is the worker's own report that some tool
    result could not lawfully be retained (a non-text or otherwise
    unretainable result, per R-I-17); when present it names the gap
    directly rather than this function re-deriving it from tool_calls it
    has no lawful copy of.
    """
    if retention_blind_spot is not None:
        return "best_effort", retention_blind_spot
    if not _has_immutable_build(model_resolved):
        return "best_effort", f"model_resolved {model_resolved!r} carries no immutable build/version suffix"
    return "exact", None


def _aborted_budget_result(
    *, stage_run_id: int, model_requested: str | None, wall_clock_seconds: float | None, envelope_hash: str,
    blind_spot: str,
) -> InvocationResult:
    """The result `abort` leaves behind: a real, now-finished run with nothing else settled."""
    return InvocationResult(
        stage_run_id=stage_run_id, outcome="aborted_budget", failure_kind=None,
        model_requested=model_requested, model_resolved=None, provider_request_id=None,
        tokens_in=None, tokens_out=None, wall_clock_seconds=wall_clock_seconds, cost=None, currency=None,
        cost_basis="unavailable", pricing_table_hash=None, reasoning_summary=None, tool_call_ids=(),
        replayability="best_effort", replayability_blind_spot=blind_spot, envelope_hash=envelope_hash,
    )


def _credential_unavailable_result(
    *, stage_run_id: int, model_requested: str | None, envelope_hash: str, blind_spot: str,
) -> InvocationResult:
    """The result a `CredentialUnavailable` fetch leaves behind: a real, finished run, never a crash."""
    return InvocationResult(
        stage_run_id=stage_run_id, outcome="infrastructure_failure", failure_kind="infrastructure",
        model_requested=model_requested, model_resolved=None, provider_request_id=None,
        tokens_in=None, tokens_out=None, wall_clock_seconds=None, cost=None, currency=None,
        cost_basis="unavailable", pricing_table_hash=None, reasoning_summary=None, tool_call_ids=(),
        replayability="best_effort", replayability_blind_spot=blind_spot, envelope_hash=envelope_hash,
    )


def _classify(
    *, launch_result: launcher.LaunchResult, model_requested: str | None, model_resolved: str | None,
) -> tuple[str, str | None]:
    """The run's outcome and failure_kind, given its launch result and any model mismatch.

    Never called on a timed-out launch: wall clock is a budget dimension,
    so a launcher timeout is handled by `budgets.abort` before this
    function ever runs, not classified as an ordinary infrastructure
    failure.
    """
    if not launch_result.integrity.ok:
        return "sandbox_violation", "sandbox_integrity"
    if model_resolved is not None and model_requested is not None and model_resolved != model_requested:
        return "infrastructure_failure", "infrastructure"
    payload = launch_result.stdout_json or {}
    status = payload.get("status")
    if launch_result.exit_code != 0 or status in (None, "error"):
        return "infrastructure_failure", "infrastructure"
    return "pass", None


def _settle_cost(
    conn: sqlite3.Connection, stage_run_id: int, *, payload: dict, model_resolved: str | None,
    model_requested: str | None, pricing_path: Path,
) -> tuple[float | None, str | None, str, str | None]:
    cost, currency, basis = payload.get("cost"), payload.get("currency"), payload.get("cost_basis")
    if basis in ("provider_settled", "runtime_estimate") and cost is not None and currency is not None:
        run_ledger.settle_cost(conn, stage_run_id, cost=cost, currency=currency, cost_basis=basis)
        return cost, currency, basis, None

    tokens_in, tokens_out = payload.get("tokens_in"), payload.get("tokens_out")
    if tokens_in is not None and tokens_out is not None:
        pricing_doc = _yaml(pricing_path)
        # Priced by the approved requested model family, not the resolved
        # build: pricing.yaml is maintained against the model an operator
        # chose, and a resolved id may carry a build suffix the table was
        # never meant to be keyed by.
        model_prices = pricing_doc.get("models", {}).get(model_requested or model_resolved)
        if model_prices is not None:
            computed = (
                tokens_in * model_prices["input_per_million"] + tokens_out * model_prices["output_per_million"]
            ) / 1_000_000
            table_hash = hashlib.sha256(Path(pricing_path).read_bytes()).hexdigest()
            run_ledger.settle_cost(
                conn, stage_run_id, cost=computed, currency=pricing_doc["currency"],
                cost_basis="price_table_estimate", pricing_table_hash=table_hash,
            )
            return computed, pricing_doc["currency"], "price_table_estimate", table_hash

    run_ledger.settle_cost(conn, stage_run_id, cost=None, currency=None, cost_basis="unavailable")
    return None, None, "unavailable", None


def _route_service(
    conn: sqlite3.Connection, *, ticket_id: int, stage_run_id: int, stage: str, run_dir: Path, inline_rule: dict,
) -> proxy.RouteService | None:
    """The proxy's route dispatch table for this run, or None on a database with no file behind it (an in-memory test)."""
    db_path = conn.execute("PRAGMA database_list").fetchone()[2]
    if not db_path:
        return None
    return proxy.RouteService(
        db_path=Path(db_path), ticket_id=ticket_id, stage_run_id=stage_run_id, stage=stage, run_dir=run_dir,
        routes=trust_profile.load_trust_profile().routes, inline_rule=inline_rule, relay=proxy.live_relay,
    )


def invoke(
    conn: sqlite3.Connection,
    *,
    ticket: sqlite3.Row,
    stage: str,
    tier: str | None,
    entry,  # manifest.Entry
    runs_dir: Path = RUNS_DIR,
    parent_run_id: int | None = None,
    input_artefact_ids=None,
    runtime_path: Path | None = None,
    pricing_path: Path | None = None,
    limits_path: Path | None = None,
    sandbox_path: Path | None = None,
    credential_run=None,
    env_source: dict[str, str] | None = None,
) -> InvocationResult:
    """Run one fresh, governed agent invocation for `entry`, opening (and finishing) its own `stage_run`.

    `parent_run_id` set makes this a child invocation (an R-S2-3
    restatement, for instance): the child gets its own run, its own
    envelope, and its own everything below, separate from the parent's.
    `input_artefact_ids` fixes the invocation's input set (see
    `envelope.build`). The four config paths resolve to this module's
    defaults at call time, not at import, so a test suite can point every
    driver in the runner at a fixture runtime by patching the module
    constants once. `credential_run` overrides `CREDENTIAL_RUN` for one
    call, the way the config paths override their own module constants.
    """
    runtime_path = runtime_path if runtime_path is not None else RUNTIME_PATH
    pricing_path = pricing_path if pricing_path is not None else PRICING_PATH
    limits_path = limits_path if limits_path is not None else LIMITS_PATH
    sandbox_path = sandbox_path if sandbox_path is not None else launcher.SANDBOX_PATH
    runtime_doc = _yaml(runtime_path)
    adapter_cfg = runtime_doc.get("adapters", {}).get(entry.runtime_adapter)
    models = adapter_cfg["models"] if adapter_cfg is not None else ()
    if adapter_cfg is None or entry.model_requested not in models:
        return _refuse_unavailable_model(entry.model_requested)

    env = envelope_mod.build(
        conn, ticket, entry, adapter_version=ADAPTER_VERSION, sandbox_path=sandbox_path,
        input_artefact_ids=input_artefact_ids, runs_dir=runs_dir,
    )
    env_hash = envelope_mod.content_hash(env)
    stage_run_id = run_ledger.open_stage_run(
        conn, ticket_id=ticket["id"], stage=stage, parent_run_id=parent_run_id, tier=tier,
        runtime=entry.runtime_adapter, runtime_version=entry.runtime_version, adapter_version=ADAPTER_VERSION,
        model_requested=entry.model_requested, agent_ref=env.agent_hash, skill_ref=env.skill_hash,
        rubric_ref=env.rubric_hash, manifest_hash=env.manifest_hash, trust_profile_hash=env.trust_profile_hash,
        trust_approval_set_hash=env.trust_approval_set_hash,
        tool_allowlist=canonical.canonical_json(list(env.tool_allowlist)).decode(),
        sandbox_digest=env.sandbox_digest, toolchain_digest=env.toolchain_digest,
        recipe_set_hash=env.recipe_set_hash,
        inputs=canonical.canonical_json([item.artefact_id for item in env.inputs]).decode(),
        envelope_hash=env_hash,
    )

    # Tokens are checked at each invocation boundary: settled usage from
    # every earlier sibling in this family (and, for S4, the ticket's
    # whole S4 history) is compared to budget before this invocation does
    # any real work at all.
    budget_reason = budgets.check_before_invocation(conn, ticket, stage, tier, parent_run_id=parent_run_id)
    if budget_reason is not None:
        budgets.abort(conn, ticket, stage_run_id, reason=budget_reason)
        return _aborted_budget_result(
            stage_run_id=stage_run_id, model_requested=entry.model_requested,
            wall_clock_seconds=None, envelope_hash=env_hash, blind_spot="budget exceeded before invocation started",
        )

    # Fetched at the moment of launch, handed to this one call, and never
    # written to a row, an artefact, or a log: `credential_run` only exists
    # so a test can inject a fake Keychain lookup instead of monkeypatching
    # `credentials.fetch` itself, which would also hide a real failure path
    # this function must classify as `infrastructure_failure`, not a crash.
    runtime_key_value = None
    if "runtime_key" in entry.credential_roles:
        try:
            runtime_key_value = credentials.fetch(
                "runtime_key", run=credential_run if credential_run is not None else CREDENTIAL_RUN,
            )
        except credentials.CredentialUnavailable as exc:
            run_ledger.finish(conn, stage_run_id, "infrastructure_failure", failure_kind="infrastructure")
            return _credential_unavailable_result(
                stage_run_id=stage_run_id, model_requested=entry.model_requested, envelope_hash=env_hash,
                blind_spot=f"runtime_key unavailable: {exc}",
            )

    run_dir = _run_dir(runs_dir, ticket["id"], stage_run_id)
    envelope_path = run_dir / "envelope.json"
    write_text(envelope_path, canonical.canonical_json(envelope_mod.to_dict(env)).decode())
    # The worker's second argument: where to find what the envelope names
    # by hash. Unhashed on purpose (see `envelope.locations`).
    locations_path = run_dir / "locations.json"
    staged_locations = launcher.stage_inputs(run_dir, envelope_mod.locations(conn, ticket, entry, env))
    write_text(locations_path, canonical.canonical_json(staged_locations).decode())

    limits_doc = _yaml(limits_path)
    inline_rule = limits_doc["tool_result_inline"]
    # The proxy records routed tool calls from its own thread through its
    # own connection to the same file, so everything this connection has
    # written so far is committed before the child can make a call.
    conn.commit()
    launch_result = launcher.launch(
        run_dir=run_dir, argv=[*adapter_cfg["command"], str(envelope_path), str(locations_path)], role="agent",
        policy=entry.sandbox_policy, cwd=Path(ticket["worktree_path"]) if ticket["worktree_path"] else run_dir,
        wall_clock_seconds=entry.budget.get("wall_clock_seconds"), env_source=env_source,
        runtime_key_value=runtime_key_value, runtime_key_env_name=adapter_cfg["key_role"],
        envelope_path=envelope_path, sandbox_path=sandbox_path, stage=stage, ticket_dir=Path(runs_dir) / "tickets" / str(ticket["id"]),
        worktree_path=Path(ticket["worktree_path"]) if ticket["worktree_path"] else None,
        routes=_route_service(conn, ticket_id=ticket["id"], stage_run_id=stage_run_id, stage=stage, run_dir=run_dir, inline_rule=inline_rule),
    )
    if launch_result.timed_out:
        # Wall clock is enforced live by the launcher's own timeout, not by
        # a post-hoc token comparison: a timed-out child is a budget abort
        # outright, never classified as an ordinary infrastructure failure.
        budgets.abort(conn, ticket, stage_run_id, reason=f"wall clock budget of {entry.budget.get('wall_clock_seconds')}s exceeded")
        return _aborted_budget_result(
            stage_run_id=stage_run_id, model_requested=entry.model_requested,
            wall_clock_seconds=entry.budget.get("wall_clock_seconds"), envelope_hash=env_hash,
            blind_spot="wall clock budget exceeded",
        )
    payload = launch_result.stdout_json or {}
    model_resolved = payload.get("model_resolved")
    outcome, failure_kind = _classify(
        launch_result=launch_result, model_requested=entry.model_requested, model_resolved=model_resolved,
    )
    mismatch = model_resolved is not None and entry.model_requested is not None and model_resolved != entry.model_requested

    tool_call_ids = _record_tool_calls(
        conn, ticket_id=ticket["id"], stage_run_id=stage_run_id, tool_calls=payload.get("tool_calls") or [],
        run_dir=run_dir, inline_rule=inline_rule,
    )

    output_ids: tuple[int, ...] = ()
    if not mismatch and outcome == "pass":
        output_ids = _register_outputs(conn, ticket_id=ticket["id"], stage_run_id=stage_run_id, out_dir=launch_result.out_dir)

    replayability, blind_spot = _replayability(
        model_resolved=model_resolved, retention_blind_spot=payload.get("retention_blind_spot"),
    )

    reasoning_summary = None
    if payload.get("reasoning_summary"):
        reasoning_summary = run_ledger.record_reasoning_summary(conn, stage_run_id, payload["reasoning_summary"])

    duration_ms = payload.get("duration_ms")
    run_ledger.record_invocation_result(
        conn, stage_run_id,
        model_resolved=model_resolved, tokens_in=payload.get("tokens_in"), tokens_out=payload.get("tokens_out"),
        wall_clock_seconds=(duration_ms / 1000 if duration_ms is not None else None),
        outputs=canonical.canonical_json(list(output_ids)).decode(),
        replayability=replayability, replayability_blind_spot=blind_spot,
    )

    cost, currency, cost_basis, pricing_table_hash = _settle_cost(
        conn, stage_run_id, payload=payload, model_resolved=model_resolved, model_requested=entry.model_requested,
        pricing_path=pricing_path,
    )

    run_ledger.finish(conn, stage_run_id, outcome, failure_kind=failure_kind)

    return InvocationResult(
        stage_run_id=stage_run_id, outcome=outcome, failure_kind=failure_kind,
        model_requested=entry.model_requested, model_resolved=model_resolved,
        provider_request_id=payload.get("provider_request_id"),
        tokens_in=payload.get("tokens_in"), tokens_out=payload.get("tokens_out"),
        wall_clock_seconds=(duration_ms / 1000 if duration_ms is not None else None),
        cost=cost, currency=currency, cost_basis=cost_basis, pricing_table_hash=pricing_table_hash,
        reasoning_summary=reasoning_summary, tool_call_ids=tool_call_ids,
        replayability=replayability, replayability_blind_spot=blind_spot, envelope_hash=env_hash,
    )
