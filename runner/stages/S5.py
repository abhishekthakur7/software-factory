"""Stub S5 driver: writes the placeholder `check_evidence`.

Real S5 never leaves `checks` on its own pass (the S6 assembly pass does,
and only once S5 has also passed -- see `gates.checks_gate`), so
`PASS_EVENT` is `None`.
"""
import sqlite3
from pathlib import Path

from runner.paths import RUNS_DIR
from runner.stages._common import run_stub

ARTEFACT_KIND = "check_evidence"
PASS_EVENT = None


def run(conn: sqlite3.Connection, ticket: sqlite3.Row, stage_run_id: int, runs_dir: Path = RUNS_DIR) -> str:
    return run_stub(conn, ticket, "S5", stage_run_id, ARTEFACT_KIND, runs_dir)
