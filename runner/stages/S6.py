"""Stub S6 driver: writes the placeholder `packet`.

The `checks -> review` move is `gates.checks_gate`'s, gated on both this
run and the latest S5 run having passed, so `PASS_EVENT` is `None` here too.
"""
import sqlite3
from pathlib import Path

from runner.paths import RUNS_DIR
from runner.stages._common import run_stub

ARTEFACT_KIND = "packet"
PASS_EVENT = None


def run(conn: sqlite3.Connection, ticket: sqlite3.Row, stage_run_id: int, runs_dir: Path = RUNS_DIR) -> str:
    return run_stub(conn, ticket, "S6", stage_run_id, ARTEFACT_KIND, runs_dir)
