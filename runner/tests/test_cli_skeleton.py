"""The `factory` command: `run`'s refusal path (a missing ticket, an unknown
stage, a stage invoked from the wrong state), `advance`'s walk through a
stage state and a gate state, and `show`, each exercised through
`runner.cli.main` in-process against a tmp_path database.
"""
import pytest

from runner import cli, record, tickets
from runner.db import connect


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "factory.sqlite"


def test_must_reject_run_for_a_ticket_that_does_not_exist(db_path):
    """`factory run` on a nonexistent ticket is rejected before
    any stage_run exists, recorded as a `utility_run` of kind `refused_request`."""
    cli.main(["--db", str(db_path), "run", "404", "S1"])
    conn = connect(db_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM stage_run").fetchone()[0] == 0
        rows = conn.execute("SELECT * FROM utility_run WHERE kind = 'refused_request'").fetchall()
        assert len(rows) == 1
        assert "404" in rows[0]["outputs"]
    finally:
        conn.close()


def test_must_reject_run_for_a_stage_that_does_not_exist(db_path):
    """`factory run` given a stage not valid for the ticket
    (here, one that names no real stage at all) is rejected before any
    stage_run exists, recorded as a `utility_run` of kind `refused_request`."""
    conn = connect(db_path)
    ticket_id = tickets.open_ticket(conn, title="t")
    conn.commit()
    conn.close()

    cli.main(["--db", str(db_path), "run", str(ticket_id), "S9"])

    conn = connect(db_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM stage_run").fetchone()[0] == 0
        rows = conn.execute(
            "SELECT * FROM utility_run WHERE kind = 'refused_request' AND ticket_id = ?", (ticket_id,)
        ).fetchall()
        assert len(rows) == 1
        assert "S9" in rows[0]["outputs"]
    finally:
        conn.close()


def test_must_reject_stage_run_from_the_wrong_state(db_path):
    """a stage invoked for an existing ticket from a state
    other than the one that precedes it is refused and recorded as that
    ticket's own `stage_run` with outcome `refused`, not a `utility_run`."""
    conn = connect(db_path)
    ticket_id = tickets.open_ticket(conn, title="t")  # opens in intake
    conn.commit()
    conn.close()

    # S2 runs from `clarifying`; this ticket is still in `intake`.
    cli.main(["--db", str(db_path), "run", str(ticket_id), "S2"])

    conn = connect(db_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM utility_run").fetchone()[0] == 0
        rows = conn.execute(
            "SELECT * FROM stage_run WHERE ticket_id = ? AND stage = 'S2'", (ticket_id,)
        ).fetchall()
        assert len(rows) == 1
        assert rows[0]["outcome"] == "refused"
        assert record.get(conn, "ticket", ticket_id)["state"] == "intake"
    finally:
        conn.close()


def test_show_prints_ticket_state_and_its_stage_runs(db_path, capsys):
    """`factory show` prints the ticket's state and its stage runs in plain text."""
    conn = connect(db_path)
    ticket_id = tickets.open_ticket(conn, title="t")
    conn.commit()
    conn.close()

    cli.main(["--db", str(db_path), "show", str(ticket_id)])

    out = capsys.readouterr().out
    assert f"ticket {ticket_id}: intake" in out


def test_advance_runs_the_due_stage_then_waits_at_the_gate_then_applies_it(db_path, tmp_path, capsys):
    """`factory advance` runs S0 in intake, then waits on the eligibility
    item, then admits the ticket once it is granted, then runs S1."""
    conn = connect(db_path)
    ticket_id = tickets.open_ticket(conn, title="t")
    conn.commit()
    conn.close()

    cli.main(["--db", str(db_path), "advance", str(ticket_id)])
    cli.main(["--db", str(db_path), "advance", str(ticket_id)])
    out = capsys.readouterr().out
    assert "S0 pass" in out
    assert "waiting on a human at intake" in out

    conn = connect(db_path)
    record.insert(conn, "queue_item", ticket_id=ticket_id, kind="eligibility", action="granted")
    conn.commit()
    conn.close()
    cli.main(["--db", str(db_path), "advance", str(ticket_id)])
    cli.main(["--db", str(db_path), "advance", str(ticket_id)])

    conn = connect(db_path)
    try:
        assert record.get(conn, "ticket", ticket_id)["state"] == "clarifying"
        stages = [row["stage"] for row in conn.execute("SELECT stage FROM stage_run ORDER BY id")]
        assert stages == ["S0", "S1"]
        assert (tmp_path / "tickets" / str(ticket_id)).is_dir()
    finally:
        conn.close()
