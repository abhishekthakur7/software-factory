"""Stub S5 driver: the freshness preflight, then the placeholder `check_evidence`.

Real S5 never leaves `checks` on its own pass (the S6 assembly pass does,
and only once S5 has also passed -- see `gates.checks_gate`), so
`PASS_EVENT` is `None`. The preflight runs before the stub artefact is
ever written: a stale candidate must never reach even a placeholder S5
result, since a later pass over a stale binding would otherwise look like
real evidence.
"""
import sqlite3
from pathlib import Path

from runner import freshness
from runner.paths import RUNS_DIR
from runner.stages._common import run_stub

ARTEFACT_KIND = "check_evidence"
PASS_EVENT = None

# The blocking-tier checks S5 runs at this milestone, in the order they
# run after the preflight and the project's own recipes at base and head.
# The S4 hand-off names this list as the check policies the implementer
# will face, so the two never disagree about what S5 enforces.
CHECK_ORDER: tuple[str, ...] = (
    "size_gate",
    "scope_diff",
    "source_declaration_diff",
    "behavior_contract_evidence",
    "regression_only",
    "base_test_diff",
)


def run(
    conn: sqlite3.Connection, ticket: sqlite3.Row, stage_run_id: int, runs_dir: Path = RUNS_DIR,
) -> str | tuple[str, str]:
    fresh = freshness.check(
        conn, ticket["id"], boundary=freshness.S5_PREFLIGHT, target_branch=freshness.target_branch(), runs_dir=runs_dir,
    )
    if not fresh.fresh:
        return "fail", "stale_binding"
    return run_stub(conn, ticket, "S5", stage_run_id, ARTEFACT_KIND, runs_dir)
