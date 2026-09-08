"""The `factory` command: `advance`, `run`, `show`.

Each verb is a thin wrapper over an in-process function so tests (and any
later API) can call `advance`/`run`/`show` directly without going through
argument parsing at all.
"""
import argparse
import sqlite3
from pathlib import Path

from runner import gates, outbox, record, transitions
from runner.db import connect
from runner.paths import RUNS_DIR
from runner.stages import DRIVERS, run_stage
from runner.state_table import STAGE_STATE

# Stages grouped by the state they run from, in run order (S5 before S6
# in `checks`), so `advance` can ask "which stage is due here?".
_STAGES_OF_STATE: dict[str, list[str]] = {}
for _stage, _state in STAGE_STATE.items():
    _STAGES_OF_STATE.setdefault(_state, []).append(_stage)


def _due_stage(conn: sqlite3.Connection, ticket: sqlite3.Row) -> str | None:
    """The first stage of the ticket's state still to run, or None.

    A stage whose pass leaves the state (S1 to S4) is always due while the
    ticket sits in that state: being there with a passing run means a
    send-back, so it runs again. A stage whose pass stays in the state (S0,
    S5, S6) is due only until its latest run has passed; after that the
    state's gate decides.
    """
    for stage in _STAGES_OF_STATE.get(ticket["state"], []):
        if DRIVERS[stage].PASS_EVENT is not None:
            return stage
        latest = conn.execute(
            "SELECT outcome FROM stage_run WHERE ticket_id = ? AND stage = ? ORDER BY id DESC LIMIT 1",
            (ticket["id"], stage),
        ).fetchone()
        if latest is None or latest["outcome"] != "pass":
            return stage
    return None


def advance(conn: sqlite3.Connection, ticket_id: int, runs_dir: Path = RUNS_DIR) -> str:
    """Run the stage due in the ticket's state, else evaluate its gate, else report the wait."""
    ticket = record.get(conn, "ticket", ticket_id)
    if ticket is None:
        return f"no such ticket: {ticket_id}"
    outbox.reconcile_pending(conn, ticket_id, runs_dir=runs_dir)
    stage = _due_stage(conn, ticket)
    if stage is not None:
        return f"ticket {ticket_id}: {stage} {run_stage(conn, ticket_id, stage, runs_dir=runs_dir)}"
    gate = gates.GATES.get(ticket["state"])
    event = gate(conn, ticket) if gate is not None else None
    if event is None:
        return f"ticket {ticket_id} is waiting on a human at {ticket['state']}"
    transitions.apply(conn, ticket_id, event)
    return f"ticket {ticket_id}: {event}"


def run(conn: sqlite3.Connection, ticket_id: int, stage: str, runs_dir: Path = RUNS_DIR) -> str:
    """Run the named stage for `ticket_id`; `run_stage` refuses and records a stage its state does not precede."""
    if record.get(conn, "ticket", ticket_id) is not None:
        outbox.reconcile_pending(conn, ticket_id, runs_dir=runs_dir)
    return run_stage(conn, ticket_id, stage, runs_dir=runs_dir)


def show(conn: sqlite3.Connection, ticket_id: int) -> str:
    """The ticket's state and its stage runs (id, stage, attempt, outcome), plain text."""
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
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="factory")
    parser.add_argument("--db", type=Path, default=RUNS_DIR / "factory.sqlite")
    subparsers = parser.add_subparsers(dest="verb", required=True)

    advance_parser = subparsers.add_parser("advance")
    advance_parser.add_argument("ticket_id", type=int)

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("ticket_id", type=int)
    run_parser.add_argument("stage")

    show_parser = subparsers.add_parser("show")
    show_parser.add_argument("ticket_id", type=int)

    args = parser.parse_args(argv)
    # The run tree lives beside the database: one root holds every piece of
    # run state, so pointing `--db` elsewhere moves the artefacts with it.
    runs_dir = args.db.parent
    conn = connect(args.db)
    try:
        if args.verb == "advance":
            print(advance(conn, args.ticket_id, runs_dir))
        elif args.verb == "run":
            print(run(conn, args.ticket_id, args.stage, runs_dir))
        elif args.verb == "show":
            print(show(conn, args.ticket_id))
        conn.commit()
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
