"""Stub S1 driver: writes the placeholder `brief` and passes context -> clarifying."""
import sqlite3
from pathlib import Path

from runner.paths import RUNS_DIR
from runner.stages._common import run_stub

ARTEFACT_KIND = "brief"
PASS_EVENT = "s1_pass"


def run(conn: sqlite3.Connection, ticket: sqlite3.Row, stage_run_id: int, runs_dir: Path = RUNS_DIR) -> str:
    return run_stub(conn, ticket, "S1", stage_run_id, ARTEFACT_KIND, runs_dir)
