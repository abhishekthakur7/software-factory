"""The body every stub stage driver shares: write one stub artefact, register it, pass.

Each `SN.py` is a few lines naming its stage and artefact kind; this is the
one place that touches the filesystem and the artefact registry, so the
per-run directory layout (`runs/tickets/<id>/runs/<run>/out/`) and
the `supersedes` chaining live in exactly one function.
"""
import sqlite3
from pathlib import Path

from runner import artefact_registry
from runner.fs import write_text
from runner.paths import RUNS_DIR


def run_stub(
    conn: sqlite3.Connection,
    ticket: sqlite3.Row,
    stage: str,
    stage_run_id: int,
    kind: str,
    runs_dir: Path = RUNS_DIR,
) -> str:
    """Write `out/<kind>.md`, register it superseding this ticket's prior version, return "pass"."""
    out_dir = runs_dir / "tickets" / str(ticket["id"]) / "runs" / str(stage_run_id) / "out"
    path = out_dir / f"{kind}.md"
    write_text(path, f"stub {kind} artefact for stage {stage}, ticket {ticket['id']}.\n")
    prior = artefact_registry.latest(conn, ticket["id"], kind)
    artefact_registry.register(
        conn,
        ticket_id=ticket["id"],
        kind=kind,
        path=path,
        stage_run_id=stage_run_id,
        supersedes=prior["id"] if prior is not None else None,
    )
    return "pass"
