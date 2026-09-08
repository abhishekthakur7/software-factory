"""`run_stage`: the one path from "run this ticket's next stage" to a recorded `stage_run`.

Refusal comes before anything else: a missing ticket
or an unknown stage name is refused before any `stage_run` exists, as a
`utility_run` of kind `refused_request`; a known stage invoked from the
wrong state is refused as that ticket's own `stage_run` with outcome
`refused`, since the ticket and stage both exist and the refusal belongs
to its run history. Otherwise the driver runs, its outcome and `ended_at`
are recorded, and -- unless this is a `validation_only` run or the
driver has no `PASS_EVENT` (S0, S5, S6: their exits are gates, not an
automatic stage pass) -- a `pass` outcome applies that event.
"""
import sqlite3
from pathlib import Path

from runner import record, transitions
from runner.paths import RUNS_DIR
from runner.stages import S0, S1, S2, S3, S4, S5, S6
from runner.state_table import STAGE_STATE

DRIVERS = {"S0": S0, "S1": S1, "S2": S2, "S3": S3, "S4": S4, "S5": S5, "S6": S6}


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
        record.insert(
            conn,
            "utility_run",
            kind="refused_request",
            outputs=f"no such ticket: {ticket_id}",
            started_at=record.now(),
            ended_at=record.now(),
        )
        return "refused_request"
    if stage not in DRIVERS:
        record.insert(
            conn,
            "utility_run",
            ticket_id=ticket_id,
            kind="refused_request",
            outputs=f"no such stage: {stage}",
            started_at=record.now(),
            ended_at=record.now(),
        )
        return "refused_request"

    prior_attempts = conn.execute(
        "SELECT COUNT(*) FROM stage_run WHERE ticket_id = ? AND stage = ?", (ticket_id, stage)
    ).fetchone()[0]
    attempt = prior_attempts + 1
    run_kind = "validation_only" if validation_only else "task"

    if ticket["state"] != STAGE_STATE[stage]:
        record.insert(
            conn,
            "stage_run",
            ticket_id=ticket_id,
            stage=stage,
            attempt=attempt,
            run_kind=run_kind,
            outcome="refused",
            started_at=record.now(),
            ended_at=record.now(),
        )
        return "refused"

    stage_run_id = record.insert(
        conn,
        "stage_run",
        ticket_id=ticket_id,
        stage=stage,
        attempt=attempt,
        run_kind=run_kind,
        started_at=record.now(),
    )
    driver = DRIVERS[stage]
    outcome = driver.run(conn, ticket, stage_run_id, runs_dir)
    record.update(conn, "stage_run", stage_run_id, outcome=outcome, ended_at=record.now())
    if outcome == "pass" and not validation_only and driver.PASS_EVENT is not None:
        transitions.apply(conn, ticket_id, driver.PASS_EVENT)
    return outcome
