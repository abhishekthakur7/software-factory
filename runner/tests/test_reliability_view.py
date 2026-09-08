"""`stage_reliability_view`: a view over `stage_run` alone, so no `utility_run`
kind can ever appear in it.
"""
import pytest

from runner import record
from runner.db import connect
from runner.schema import UTILITY_KINDS


def _open(tmp_path):
    return connect(tmp_path / "factory.sqlite")


def test_a_seeded_stage_run_appears_in_the_view_with_its_own_fields(tmp_path):
    conn = _open(tmp_path)
    ticket_id = record.insert(conn, "ticket", title="t")
    stage_run_id = record.insert(
        conn, "stage_run", ticket_id=ticket_id, stage="S4",
        attempt=2, verification_attempt=1, run_kind="fix_round", outcome="pass",
    )

    row = conn.execute(
        "SELECT * FROM stage_reliability_view WHERE id = ?", (stage_run_id,)
    ).fetchone()

    assert row is not None
    assert row["ticket_id"] == ticket_id
    assert row["stage"] == "S4"
    assert row["attempt"] == 2
    assert row["verification_attempt"] == 1
    assert row["run_kind"] == "fix_round"
    assert row["outcome"] == "pass"


@pytest.mark.parametrize("kind", sorted(UTILITY_KINDS))
def test_a_seeded_utility_run_of_this_kind_is_excluded_from_the_view(tmp_path, kind):
    """for each utility_run kind, a seeded row of that kind never surfaces in
    stage_reliability_view: the view selects from stage_run alone, so with no
    stage_run seeded the view holds nothing at all."""
    conn = _open(tmp_path)
    record.insert(conn, "utility_run", kind=kind)

    rows = conn.execute("SELECT * FROM stage_reliability_view").fetchall()

    assert rows == []
