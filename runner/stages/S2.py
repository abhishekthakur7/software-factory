"""Stub S2 driver: writes the placeholder `criteria` and passes clarifying -> planning."""
import sqlite3
from pathlib import Path

from runner.paths import RUNS_DIR
from runner.stages._common import run_stub

ARTEFACT_KIND = "criteria"
PASS_EVENT = "s2_pass"


def run(conn: sqlite3.Connection, ticket: sqlite3.Row, stage_run_id: int, runs_dir: Path = RUNS_DIR) -> str:
    return run_stub(conn, ticket, "S2", stage_run_id, ARTEFACT_KIND, runs_dir)
