"""Database isolation.

The requirement's own verification clause is phrased as "a stage run started against
a different database path"; until a stage driver exists this test drives `connect` directly, since `connect` is exactly
the boundary the requirement names: nothing about the record survives a change of
database path.
"""
from runner.db import connect


def test_fresh_database_path_has_no_prior_rows(tmp_path):
    """a fresh database path holds no prior ticket, stage run or artefact rows."""
    db_a = connect(tmp_path / "a.sqlite")
    db_a.execute("INSERT INTO ticket (id, title) VALUES (1, 'seed')")
    db_a.execute("INSERT INTO stage_run (id, ticket_id, stage) VALUES (1, 1, 'intake')")
    db_a.execute(
        "INSERT INTO artefact (id, ticket_id, kind, path) VALUES (1, 1, 'brief', 'x')"
    )
    db_a.commit()

    db_b = connect(tmp_path / "b.sqlite")

    for table in ("ticket", "stage_run", "artefact"):
        assert db_b.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0

    # Database A's own rows must not have been disturbed by opening B.
    for table in ("ticket", "stage_run", "artefact"):
        assert db_a.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 1
