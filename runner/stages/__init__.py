"""`run_stage`: the one path from "run this ticket's next stage" to a recorded `stage_run`.

implementation is the one stage whose run rows the driver opens itself (see
`implementation.run_next`); `run_stage` still owns every refusal for it.

Refusal comes before anything else: a missing ticket
or an unknown stage name is refused before any `stage_run` exists, as a
`utility_run` of kind `refused_request`; a known stage invoked from the
wrong state is refused as that ticket's own `stage_run` with outcome
`refused`, since the ticket and stage both exist and the refusal belongs
to its run history. Otherwise the driver runs, its outcome and `ended_at`
are recorded, and -- unless this is a `validation_only` run or the
driver has no `PASS_EVENT` (intake, checks, human_review: their exits are gates, not an
automatic stage pass) -- a `pass` outcome applies that event. Every
`stage_run`/`utility_run` write goes through `run_ledger`, never a direct
`record.insert`/`record.update`, so attempt numbering and lease bookkeeping
live in exactly one place.

A driver's `run` ordinarily returns a plain outcome string. A driver may
instead return `(outcome, failure_kind)` when the outcome itself needs a
`failure_kind` on the `stage_run` -- the checks stage's stale-binding preflight refusal
is the one case today -- so `run_ledger.finish` records it; every other
driver keeps returning a bare string, which carries no `failure_kind`.
"""
import dataclasses
import sqlite3
from pathlib import Path

from runner import manifest, record, run_ledger, transitions
from runner.adapters import cursor_sdk
from runner.paths import RUNS_DIR
from runner.stages import intake, context_gathering, clarification, planning, implementation, checks, human_review
from runner.state_table import STAGE_STATE

DRIVERS = {"intake": intake, "context_gathering": context_gathering, "clarification": clarification, "planning": planning, "implementation": implementation, "checks": checks, "human_review": human_review}


def run_stage(
    conn: sqlite3.Connection,
    ticket_id: int,
    stage: str,
    *,
    validation_only: bool = False,
    runs_dir: Path = RUNS_DIR,
) -> str:
    """Run `stage` for `ticket_id` and return its outcome ("pass", "refused", or "refused_request")."""
    ticket = record.get(conn, "ticket", ticket_id)
    if ticket is None:
        run_id = run_ledger.open_utility_run(
            conn, kind="refused_request", outputs=f"no such ticket: {ticket_id}"
        )
        run_ledger.finish(conn, run_id, "refused_request", table="utility_run")
        return "refused_request"
    if stage not in DRIVERS:
        run_id = run_ledger.open_utility_run(
            conn, kind="refused_request", ticket_id=ticket_id, outputs=f"no such stage: {stage}"
        )
        run_ledger.finish(conn, run_id, "refused_request", table="utility_run")
        return "refused_request"

    run_kind = "validation_only" if validation_only else "task"

    if ticket["state"] != STAGE_STATE[stage]:
        stage_run_id = run_ledger.open_stage_run(
            conn, ticket_id=ticket_id, stage=stage, run_kind=run_kind
        )
        run_ledger.finish(conn, stage_run_id, "refused")
        return "refused"

    # implementation opens its own rows: its unit of execution is the plan task, and
    # the columns that name one (`plan_item`, `plan_tuple_id`,
    # `verification_attempt`) are written at insert, so only the driver that
    # knows which task is next can open the row.
    if stage == "implementation":
        return implementation.run_next(conn, ticket, runs_dir=runs_dir, validation_only=validation_only)

    stage_run_id = run_ledger.open_stage_run(conn, ticket_id=ticket_id, stage=stage, run_kind=run_kind)
    driver = DRIVERS[stage]
    result = driver.run(conn, ticket, stage_run_id, runs_dir)
    outcome, failure_kind = result if isinstance(result, tuple) else (result, None)
    run_ledger.finish(conn, stage_run_id, outcome, failure_kind=failure_kind)
    if outcome == "pass" and not validation_only and driver.PASS_EVENT is not None:
        transitions.apply(conn, ticket_id, driver.PASS_EVENT)
    return outcome


def invoke_agent(
    conn: sqlite3.Connection, ticket: sqlite3.Row, stage: str, *, tier: str | None = None, runs_dir: Path = RUNS_DIR,
    manifest_path: Path = manifest.MANIFEST_PATH, parent_run_id: int | None = None, input_artefact_ids=None,
    model_override: str | None = None,
) -> cursor_sdk.InvocationResult:
    """The seam a real stage driver calls once it has agent content: resolve the manifest entry, invoke if agent-bearing.

    A real stage runs as two kinds of `stage_run` row. The row `run_stage`
    opened is the stage attempt: it holds the lease, and its outcome
    (pass, blocked, fail) is what the state table reads. Every agent
    invocation the driver makes is a child of that attempt, opened by
    `adapters.cursor_sdk.invoke` with `parent_run_id` set, carrying its own
    envelope, model, tokens, cost and replayability; a restatement child
    is a sibling of the main invocation under the same attempt. Budgets
    sum over the attempt's whole family and the first-attempt measure
    excludes children, so the split costs nothing either way. A driver
    therefore passes its own `stage_run_id` as `parent_run_id`; a stage
    whose resolved manifest entry names no agent (a script-only stage)
    gets a `pass` result with no run opened.

    `model_override` names a model other than the entry's `model_requested`
    for one invocation -- the manifest's `restatement_model` for clarification's
    agreement-check children -- and is checked against the runtime's
    approved models exactly like the entry's own.

    Every stage but `intake` first compares the ticket's `factory_manifest_hash`
    pin against this resolution's own manifest hash: a missing pin, or one
    that no longer matches, is refused as a `utility_run` of kind
    `refused_request` before anything else runs, so no `stage_run` is ever
    opened for it. `intake` is exempt since the pin is not written until
    eligibility is granted (see `gates.intake_gate`), by which point the
    ticket has already left `intake`.
    """
    tier = tier or ticket["tier_final"] or ticket["tier_provisional"] or "standard"
    entry = manifest.resolve(manifest.load(manifest_path), stage, tier)
    if stage != "intake":
        pinned = ticket["factory_manifest_hash"]
        if pinned is None or pinned != entry.manifest_hash:
            reason = (
                f"ticket {ticket['id']} carries no manifest pin for stage {stage}" if pinned is None
                else f"ticket {ticket['id']} manifest pin {pinned!r} no longer matches the resolved "
                     f"manifest hash {entry.manifest_hash!r} for stage {stage}"
            )
            run_id = run_ledger.open_utility_run(conn, kind="refused_request", ticket_id=ticket["id"], outputs=reason)
            run_ledger.finish(conn, run_id, "refused_request", table="utility_run")
            return cursor_sdk.no_run_result("refused_request", blind_spot=reason)
    if entry.agent is None:
        return cursor_sdk.no_run_result("pass", blind_spot="script-only stage: no agent invoked")
    if model_override is not None:
        entry = dataclasses.replace(entry, model_requested=model_override)
    return cursor_sdk.invoke(
        conn, ticket=ticket, stage=stage, tier=tier, entry=entry, runs_dir=runs_dir,
        parent_run_id=parent_run_id, input_artefact_ids=input_artefact_ids,
    )
