"""Human control over a running ticket: pause, resume, stop, and the data `factory show` reports.

`live_run` is the one predicate every command but `stop` checks before
touching a ticket: an open (`outcome IS NULL`) `stage_run` whose process is
still alive blocks `pause`, `resume`, `factory run`, `advance`, and `act`
on the ticket's open item, since only `stop` may act on a running stage.
`pause_pending` is the boundary check `advance` calls immediately before
starting a due stage or evaluating a state's gate, so a pause request in
flight always lands there rather than mid-invocation: the boundary either
has not yet been crossed (this call sees the flag and stops first) or it
already has (the flag was not yet set when this call ran, and nothing here
retroactively undoes work already begun). Neither `pause` nor `stop` ever
touches a stage's registered inputs, prompt, or artefacts -- both act only
on `stage_run`, `ticket`, `tag`, and `queue_item` rows.
"""
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from runner import launcher, queue, record, run_ledger, tags, transitions
from runner.paths import RUNS_DIR


def live_run(conn: sqlite3.Connection, ticket_id: int) -> sqlite3.Row | None:
    """The ticket's one open `stage_run` whose process is still alive, or None.

    A lapsed lease whose process has also died is not live -- that is
    `run_ledger.expire_dead_runs`'s job, which `advance` runs before this
    predicate is ever asked about the ticket again, so a merely slow but
    genuinely live run is never mistaken for a crashed one here.
    """
    for row in conn.execute(
        "SELECT * FROM stage_run WHERE ticket_id = ? AND outcome IS NULL", (ticket_id,)
    ).fetchall():
        if run_ledger.process_alive(row["process_identity"]):
            return row
    return None


def live_run_refusal(ticket_id: int) -> str:
    """The message every command but `stop` returns while the ticket has a live run."""
    return f"ticket {ticket_id}: a live run is in progress; only 'factory stop' is permitted"


def pause(conn: sqlite3.Connection, ticket_id: int) -> str:
    """Set the durable pause flag; `advance` honours it at the ticket's next recorded boundary."""
    ticket = record.get(conn, "ticket", ticket_id)
    if ticket is None:
        return f"no such ticket: {ticket_id}"
    if live_run(conn, ticket_id) is not None:
        return live_run_refusal(ticket_id)
    record.update(conn, "ticket", ticket_id, pause_requested=1)
    return f"ticket {ticket_id}: pause requested"


def pause_pending(conn: sqlite3.Connection, ticket_id: int) -> bool:
    """Whether the pause flag is set; if so, stamp `paused_at` once and open one `manual_pause` item.

    `advance` calls this immediately before it would otherwise start a due
    stage or evaluate a state's gate -- the two recorded boundaries -- so
    a request that arrives at the same instant as either one resolves to
    pausing there, never mid-invocation. Repeated calls while still paused
    leave `paused_at` and the open item alone: only the first call after
    the flag is set does either write.
    """
    ticket = record.get(conn, "ticket", ticket_id)
    if ticket is None or not ticket["pause_requested"]:
        return False
    if ticket["paused_at"] is None:
        record.update(conn, "ticket", ticket_id, paused_at=record.now())
    existing = conn.execute(
        "SELECT id FROM queue_item WHERE ticket_id = ? AND kind = 'manual_pause' AND resolved_at IS NULL",
        (ticket_id,),
    ).fetchone()
    if existing is None:
        queue.open_item(conn, ticket_id=ticket_id, kind="manual_pause")
    return True


def resume(conn: sqlite3.Connection, ticket_id: int, *, actor: str, runs_dir: Path = RUNS_DIR) -> str:
    """Resolve the ticket's open `manual_pause` item with `resume`, continuing it from its held boundary."""
    ticket = record.get(conn, "ticket", ticket_id)
    if ticket is None:
        return f"no such ticket: {ticket_id}"
    if live_run(conn, ticket_id) is not None:
        return live_run_refusal(ticket_id)
    item = conn.execute(
        "SELECT id FROM queue_item WHERE ticket_id = ? AND kind = 'manual_pause' AND resolved_at IS NULL "
        "ORDER BY id DESC LIMIT 1",
        (ticket_id,),
    ).fetchone()
    if item is None:
        return f"ticket {ticket_id}: no open pause to resume"
    return queue.act(conn, item_id=item["id"], action="resume", actor=actor, runs_dir=runs_dir)


def stop(
    conn: sqlite3.Connection, ticket_id: int, *, actor: str, fm_id: str, note: str | None = None,
    runs_dir: Path = RUNS_DIR,
) -> str:
    """Finish every open stage run `aborted_human`, escalate the ticket, and open one `escalation` item.

    Unlike every other command here, `stop` never checks `live_run`: it is
    the one command a live run does not refuse, since it is what ends one.
    The escalation item's `ref` names the last run stopped, so a human
    resuming it lands back on the stage that was interrupted. Before each
    run finishes, this kills the launcher's child process named at
    `runs/tickets/<id>/runs/<run>/results/child.pid`, if one is still
    alive -- a run with no such file (a script-only stub, or one that
    never reached the launcher) has nothing to kill, which is not an
    error.
    """
    ticket = record.get(conn, "ticket", ticket_id)
    if ticket is None:
        return f"no such ticket: {ticket_id}"
    open_runs = conn.execute(
        "SELECT id, reasoning_summary FROM stage_run WHERE ticket_id = ? AND outcome IS NULL ORDER BY id",
        (ticket_id,),
    ).fetchall()
    if not open_runs:
        return f"ticket {ticket_id}: no open stage run to stop"
    for row in open_runs:
        if row["reasoning_summary"] is None and note is not None:
            run_ledger.record_reasoning_summary(conn, row["id"], note)
        run_dir = runs_dir / "tickets" / str(ticket_id) / "runs" / str(row["id"])
        launcher.terminate_child(run_dir)
        run_ledger.finish(conn, row["id"], "aborted_human")
    transitions.apply(conn, ticket_id, "escalate")
    # The escalation is the factory's own tag on the interrupted run; the
    # human who stopped it is named in the note, never as `tagged_by`.
    stop_note = f"stopped by {actor}" + (f": {note}" if note else "")
    tags.tag(conn, target=f"ticket:{ticket_id}", kind="escalation", fm_id=fm_id, actor=tags.MECHANICAL_ACTOR, note=stop_note)
    queue.open_item(conn, ticket_id=ticket_id, kind="escalation", ref=f"stage_run:{open_runs[-1]['id']}")
    return f"ticket {ticket_id}: stopped and escalated"


def status(conn: sqlite3.Connection, ticket_id: int) -> dict:
    """The data `factory show` reports: state, the open-or-latest run's stage/attempt/elapsed/budget/outputs, and pause-pending.

    Reads the ticket's open `stage_run` if one exists, else its latest one;
    a ticket with no `stage_run` yet reports every run-scoped field as
    `None`/empty. Token budget remaining is the tier's `tiers.yaml` figure
    minus `tokens_in + tokens_out` recorded on the run so far; wall-clock
    remaining is that figure minus the run's elapsed time computed from its
    timestamps, or `None` where `tiers.yaml` carries no wall-clock budget
    for the stage.
    """
    ticket = record.get(conn, "ticket", ticket_id)
    if ticket is None:
        raise LookupError(f"no such ticket: {ticket_id}")
    run = conn.execute(
        "SELECT * FROM stage_run WHERE ticket_id = ? ORDER BY (outcome IS NULL) DESC, id DESC LIMIT 1",
        (ticket_id,),
    ).fetchone()
    result = {
        "state": ticket["state"],
        "pause_pending": bool(ticket["pause_requested"]),
        "stage": None,
        "attempt": None,
        "elapsed_seconds": None,
        "budget_remaining": None,
        "outputs": [],
    }
    if run is None:
        return result
    result["stage"] = run["stage"]
    result["attempt"] = run["attempt"]
    started = datetime.fromisoformat(run["started_at"])
    ended = datetime.fromisoformat(run["ended_at"]) if run["ended_at"] else datetime.now(UTC)
    elapsed = (ended - started).total_seconds()
    result["elapsed_seconds"] = elapsed

    tier = ticket["tier_final"] or ticket["tier_provisional"] or "standard"
    budget = run_ledger.budget(run["stage"], tier)
    tokens_used = (run["tokens_in"] or 0) + (run["tokens_out"] or 0)
    result["budget_remaining"] = {
        "tokens": budget["tokens"] - tokens_used,
        "wall_clock_seconds": (
            budget["wall_clock_seconds"] - elapsed if budget["wall_clock_seconds"] is not None else None
        ),
    }
    result["outputs"] = [
        {"id": row["id"], "kind": row["kind"], "path": row["path"]}
        for row in conn.execute(
            "SELECT id, kind, path FROM artefact WHERE stage_run_id = ? ORDER BY id", (run["id"],)
        ).fetchall()
    ]
    return result
