"""The in-process command functions behind the `factory` verbs that have no module of their own.

`advance`, `run`, `show`, `show_artefact`, `pause`, `resume`, `stop`,
`report`, and `digest_open_items` live here rather than in
`runner/cli.py`, so the command line is only argument parsing over the
one operation surface and a test (or any later API client) calls these
functions directly. Each other verb's function lives in the module that
owns its mechanism (`queue.act`, `tags.tag`, `export.export_ticket`, a
waiver among them -- issued through `queue.act`'s own `waiver` action
rather than a dedicated command function).
"""
import sqlite3
import subprocess
import sys
from pathlib import Path

from runner import (
    capacity, control, digest, export, freshness, gates, guard, outbox, outcome, owners, project, queue, record,
    run_ledger, trust_profile, transitions, waivers,
)
from runner.paths import FACTORY_DIR, RUNS_DIR
from runner.stages import DRIVERS, run_stage
from runner.state_table import STAGE_STATE

REPORT_SCRIPT = FACTORY_DIR / "scripts" / "tools" / "report"

# Stages grouped by the state they run from, in run order (the checks stage before
# human_review in the `checks` state), so `advance` can ask "which stage is due here?".
_STAGES_OF_STATE: dict[str, list[str]] = {}
for _stage, _state in STAGE_STATE.items():
    _STAGES_OF_STATE.setdefault(_state, []).append(_stage)


def _due_stage(conn: sqlite3.Connection, ticket: sqlite3.Row) -> str | None:
    """The first stage of the ticket's state still to run, or None.

    A stage whose pass leaves the state (context gathering to implementation) is always due while the
    ticket sits in that state: being there with a passing run means a
    send-back, so it runs again. A stage whose pass stays in the state (intake,
    checks, human_review) is due only until its latest run has passed; after that the
    state's gate decides. The checks stage is the one exception: a latest run that did
    not pass outright still counts as not due once every blocking result
    it left is validly waived (`runner.waivers.cleared`), since rerunning
    it would write fresh `check_result` rows no waiver names and make the
    ticket's binding stale rather than cleared.
    """
    for stage in _STAGES_OF_STATE.get(ticket["state"], []):
        if DRIVERS[stage].PASS_EVENT is not None:
            return stage
        latest = conn.execute(
            "SELECT id, outcome FROM stage_run WHERE ticket_id = ? AND stage = ? ORDER BY id DESC LIMIT 1",
            (ticket["id"], stage),
        ).fetchone()
        if latest is None:
            return stage
        if latest["outcome"] == "pass":
            continue
        if stage == "checks" and waivers.cleared(conn, latest["id"]):
            continue
        return stage
    return None


def _open_stale_base_item(conn: sqlite3.Connection, ticket_id: int, fresh: freshness.Freshness) -> None:
    """Queue one `red_check` for a stale base, unless the ticket already has an open one."""
    existing = conn.execute(
        "SELECT id FROM queue_item WHERE ticket_id = ? AND kind = 'red_check' AND resolved_at IS NULL",
        (ticket_id,),
    ).fetchone()
    if existing is None:
        queue.open_item(conn, ticket_id=ticket_id, kind="red_check", ref=f"check_result:{fresh.check_result_id}")


def advance(conn: sqlite3.Connection, ticket_id: int, runs_dir: Path = RUNS_DIR) -> str:
    """Reconcile the outbox, expire dead leases, then run the stage due in the ticket's state, else evaluate its gate, else report the wait.

    A ticket with a live run refuses every command but `factory stop`,
    `advance` included, before touching anything else. Outbox
    reconciliation runs before lease expiry, and both run before any
    due-stage or gate logic: a restart must never advance ticket state on
    evidence a crashed attempt left ambiguous or a dead run still holds a
    lease over. Immediately before it would start a due stage or evaluate
    a gate -- the two recorded boundaries -- `advance` checks the durable
    pause flag; a pending pause consumes the boundary instead, so nothing
    below it runs this call. Before ever starting implementation, the runner fetches
    the configured target branch and refuses to start it on a stale
    result: no stage runs, one `red_check` item is queued (unless the
    ticket already has one open), and the ticket stays where it is. The
    same freshness check backs `plan_review`'s own gate, so a moved target
    withholds `plan_quorum_fresh` too. A ticket still in `intake` is
    checked against the parallel-ticket limit before either boundary --
    starting its `intake` run or applying the intake gate's admitting event --
    so a ticket at capacity starts no run and moves nowhere, and the wait
    is reported instead.
    """
    ticket = record.get(conn, "ticket", ticket_id)
    if ticket is None:
        return f"no such ticket: {ticket_id}"
    if control.live_run(conn, ticket_id) is not None:
        return control.live_run_refusal(ticket_id)
    outbox.reconcile_pending(conn, ticket_id, runs_dir=runs_dir)
    run_ledger.expire_dead_runs(conn, ticket_id)
    if ticket["state"] == "intake":
        wait_line = capacity.wait(conn, ticket, capacity.effective_parallel_limit(conn))
        if wait_line is not None:
            return f"ticket {ticket_id}: {wait_line}"
    stage = _due_stage(conn, ticket)
    if stage is not None:
        if control.pause_pending(conn, ticket_id):
            return f"ticket {ticket_id}: paused at {ticket['state']}"
        if stage == "implementation":
            fresh = freshness.check(
                conn, ticket_id, boundary=freshness.BEFORE_IMPLEMENTATION, target_branch=freshness.target_branch(), runs_dir=runs_dir,
            )
            if not fresh.fresh:
                _open_stale_base_item(conn, ticket_id, fresh)
                return f"ticket {ticket_id}: base is stale ({'; '.join(fresh.reasons)})"
        return f"ticket {ticket_id}: {stage} {run_stage(conn, ticket_id, stage, runs_dir=runs_dir)}"
    gate = gates.GATES.get(ticket["state"])
    if gate is not None and control.pause_pending(conn, ticket_id):
        return f"ticket {ticket_id}: paused at {ticket['state']}"
    event = gate(conn, ticket, runs_dir=runs_dir) if gate is not None else None
    if event is None:
        return f"ticket {ticket_id} is waiting on a human at {ticket['state']}"
    transitions.apply(conn, ticket_id, event)
    if event == "review_quorum_reconciled":
        # Non-blocking: the ticket is already in `pr_opened` and stays
        # there whether or not the item opens, so a caller has no reason
        # to see this queueing fail `advance` itself.
        outcome.open_pr_outcome_item(conn, ticket_id)
    return f"ticket {ticket_id}: {event}"


def run(conn: sqlite3.Connection, ticket_id: int, stage: str, runs_dir: Path = RUNS_DIR) -> str:
    """Run the named stage for `ticket_id`; `run_stage` refuses and records a stage its state does not precede.

    A ticket with a live run refuses this call too, before `run_stage`
    ever sees it: only `factory stop` may act on a ticket while one of its
    stages is actually running.
    """
    if record.get(conn, "ticket", ticket_id) is not None:
        if control.live_run(conn, ticket_id) is not None:
            return control.live_run_refusal(ticket_id)
        outbox.reconcile_pending(conn, ticket_id, runs_dir=runs_dir)
    return run_stage(conn, ticket_id, stage, runs_dir=runs_dir)


def show(conn: sqlite3.Connection, ticket_id: int) -> str:
    """The ticket's state, its stage runs (id, stage, attempt, outcome), and its current control status, plain text."""
    ticket = record.get(conn, "ticket", ticket_id)
    if ticket is None:
        return f"no such ticket: {ticket_id}"
    lines = [f"ticket {ticket_id}: {ticket['state']}"]
    for stage_run in conn.execute(
        "SELECT id, stage, attempt, outcome FROM stage_run WHERE ticket_id = ? ORDER BY id",
        (ticket_id,),
    ):
        lines.append(
            f"  stage_run {stage_run['id']}: {stage_run['stage']} "
            f"attempt {stage_run['attempt']} outcome {stage_run['outcome']}"
        )
    info = control.status(conn, ticket_id)
    lines.append(f"  pause pending: {info['pause_pending']}")
    if info["stage"] is not None:
        lines.append(
            f"  current: {info['stage']} attempt {info['attempt']}, elapsed {info['elapsed_seconds']:.1f}s"
        )
        remaining = info["budget_remaining"]
        lines.append(
            f"  budget remaining: tokens {remaining['tokens']}, wall_clock_seconds {remaining['wall_clock_seconds']}"
        )
        for output in info["outputs"]:
            lines.append(f"    output: artefact {output['id']} {output['kind']} {output['path']}")
    wait_line = capacity.wait(conn, ticket, capacity.effective_parallel_limit(conn))
    if wait_line is not None:
        lines.append(f"  {wait_line}")
    return "\n".join(lines)


def pause(conn: sqlite3.Connection, ticket_id: int) -> str:
    """Request a pause for `ticket_id`; `advance` honours it at the next recorded boundary."""
    return control.pause(conn, ticket_id)


def resume(conn: sqlite3.Connection, ticket_id: int, *, actor: str, runs_dir: Path = RUNS_DIR) -> str:
    """Resume `ticket_id` from its held pause boundary."""
    return control.resume(conn, ticket_id, actor=actor, runs_dir=runs_dir)


def stop(conn: sqlite3.Connection, ticket_id: int, *, actor: str, fm_id: str, note: str | None = None) -> str:
    """Terminate `ticket_id`'s running stage(s) and escalate the ticket."""
    return control.stop(conn, ticket_id, actor=actor, fm_id=fm_id, note=note)


def report(
    db_path: Path,
    *,
    manifest_hash: str | None = None,
    window_days: int = 30,
    until: str | None = None,
) -> str:
    """Run the report script over `db_path` and return its stdout as text."""
    argv = [sys.executable, str(REPORT_SCRIPT), "--db", str(db_path), "--window-days", str(window_days)]
    if manifest_hash is not None:
        argv += ["--manifest-hash", manifest_hash]
    if until is not None:
        argv += ["--until", until]
    result = subprocess.run(argv, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "report script failed")
    return result.stdout


def show_artefact(
    conn: sqlite3.Connection,
    artefact_id: int,
    *,
    actor: str,
    owners_path: Path = owners.DEFAULT_OWNERS_PATH,
    profile_path: Path = trust_profile.DEFAULT_TRUST_PROFILE_PATH,
) -> str:
    """Print a governed artefact's content once the display route's guard allows it for `actor`'s reader role(s).

    Evaluates `runner.guard.decide` the same way `runner.export._scan`
    does -- against `trust-profile.yaml`'s `governed_export_display`
    route, over the artefact's own file content -- but for the `display`
    crossing rather than `export`. `actor` must hold at least one role
    the route names as a reader in `owners.yaml`; an actor with none is
    refused before the guard is ever consulted, since nothing about the
    artefact was actually evaluated for a reader it never authorised. A
    later refusal (an unadmitted data class, an inactive trust profile, a
    secret found in the content) is the guard's own decision, printed
    from its reason codes. An artefact whose `retention_until` has
    passed is still shown, prefixed with a line flagging it as subject to
    deletion, since retention governs cleanup, not readability.
    """
    artefact_row = record.get(conn, "artefact", artefact_id)
    if artefact_row is None:
        raise LookupError(f"no such artefact: {artefact_id}")

    route = trust_profile.load_trust_profile(profile_path).routes[export.ROUTE_ID]
    owners_obj = owners.load_owners(owners_path)
    reader_roles = sorted(
        role for role, entry in owners_obj.roles.items()
        if entry["identity"] == actor and role in route.reader_roles
    )
    if not reader_roles:
        raise queue.ActionRefused(f"actor {actor!r} holds no role {export.ROUTE_ID!r} names as a reader")

    source_path = Path(artefact_row["path"]) if artefact_row["path"] else None
    if source_path is None or not source_path.is_file():
        raise queue.ActionRefused(f"artefact {artefact_id} names no readable file")
    content = source_path.read_text()

    ticket_row = record.get(conn, "ticket", artefact_row["ticket_id"]) if artefact_row["ticket_id"] is not None else None
    data_class = artefact_row["data_class"] or (ticket_row["data_class"] if ticket_row is not None else None)
    operation = guard.Operation(
        crossing="display",
        route_id=export.ROUTE_ID,
        payload=content,
        input_classes=(data_class,),
        source_identity="ticket_record",
        destination_identity=f"reader:{'+'.join(reader_roles)}",
        content_provenance={"artefact_id": artefact_id, "actor": actor},
        ticket_id=artefact_row["ticket_id"],
    )
    decision = guard.decide(conn, operation, profile_path=profile_path, owners_path=owners_path)
    if decision.decision != "allow":
        raise queue.ActionRefused(f"artefact {artefact_id} display refused: {list(decision.reason_codes)}")

    lines: list[str] = []
    retention_until = artefact_row["retention_until"]
    if retention_until is not None and retention_until < record.now():
        lines.append(f"subject to deletion: retention_until {retention_until} has passed")
    lines.append(decision.payload)
    return "\n".join(lines)


def digest_open_items(conn: sqlite3.Connection, runs_dir: Path = RUNS_DIR) -> str:
    """Build and dispatch the configured cadence's digest through the transactional outbox."""
    config = project.load().get("digest") or {}
    intent_id = digest.run(conn, channel=config.get("channel"), cadence=config.get("cadence", "daily"), runs_dir=runs_dir)
    return "digest: no open items" if intent_id is None else f"digest: intent {intent_id}"
