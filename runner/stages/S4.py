"""Stub S4 driver: writes the placeholder `handoff` and passes implementing -> checks.

`run_stage` applies `PASS_EVENT` only when it is not called with
`validation_only=True`, which is how a `validation_only` run stays an S4
run from `implementing` with no state change.
"""
import sqlite3
from pathlib import Path

from runner.paths import RUNS_DIR
from runner.stages._common import run_stub

ARTEFACT_KIND = "handoff"
PASS_EVENT = "s4_pass"


def run(conn: sqlite3.Connection, ticket: sqlite3.Row, stage_run_id: int, runs_dir: Path = RUNS_DIR) -> str:
    return run_stub(conn, ticket, "S4", stage_run_id, ARTEFACT_KIND, runs_dir)
