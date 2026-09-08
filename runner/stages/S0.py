"""Stub S0 driver: the mechanical intake gate.

Real S0 is scripts only (no agent) and never leaves `intake` on its own --
the eligibility decision does (`gates.intake_gate`). `PASS_EVENT` is
`None` for that reason: `run_stage` records this run's outcome and stops,
leaving the state change to the gate.
"""
import sqlite3
from pathlib import Path

from runner.paths import RUNS_DIR
from runner.stages._common import run_stub

ARTEFACT_KIND = "ticket_source"
PASS_EVENT = None


def run(conn: sqlite3.Connection, ticket: sqlite3.Row, stage_run_id: int, runs_dir: Path = RUNS_DIR) -> str:
    return run_stub(conn, ticket, "S0", stage_run_id, ARTEFACT_KIND, runs_dir)
