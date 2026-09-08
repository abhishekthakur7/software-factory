"""T-A-02 database isolation test (R-T-1).

R-T-1's own verification clause is phrased as "a stage run started against
a different database path"; T-A-04 is what gives a stage run its driver.
Until then this test drives `connect` directly, since `connect` is exactly
the boundary R-T-1 requires: nothing about the record survives a change of
database path.
"""
from runner.db import connect


def test_fresh_database_path_has_no_prior_rows(tmp_path):
    """T-A-02 criterion 4, R-T-1."""
    db_a = connect(tmp_path / "a.sqlite")
    db_a.execute("INSERT INTO ticket (id, title) VALUES (1, 'seed')")
    db_a.execute("INSERT INTO stage_run (id, ticket_id, stage) VALUES (1, 1, 'S0')")
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
