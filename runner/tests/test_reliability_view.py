"""`stage_reliability_view`: narrowed to the first-attempt rule, over
`stage_run` alone, so no `utility_run` kind can ever appear in it.
"""
import pytest

from runner import record
from runner.db import connect
from runner.schema import UTILITY_KINDS


def _open(tmp_path):
    return connect(tmp_path / "factory.sqlite")


def test_a_first_attempt_task_run_is_counted_eligible_and_passed(tmp_path):
    """A first-attempt, top-level `task` run with a countable outcome
    is grouped by its own manifest, stage and tier, counted eligible and,
    since it passed, counted passed."""
    conn = _open(tmp_path)
    ticket_id = record.insert(conn, "ticket", title="t")
    record.insert(
        conn, "stage_run", ticket_id=ticket_id, stage="implementation", tier="light",
        manifest_hash="m1", attempt=1, run_kind="task", outcome="pass",
    )

    row = conn.execute(
        "SELECT * FROM stage_reliability_view WHERE manifest_hash = 'm1' AND stage = 'implementation' AND tier = 'light'"
    ).fetchone()

    assert row is not None
    assert row["eligible_count"] == 1
    assert row["passed_count"] == 1


@pytest.mark.parametrize(
    "fields",
    [
        pytest.param({"attempt": 2, "run_kind": "task", "outcome": "fail"}, id="retry_attempt"),
        pytest.param({"attempt": 1, "run_kind": "fix_round", "outcome": "fail"}, id="fix_round"),
        pytest.param({"attempt": 1, "run_kind": "validation_only", "outcome": "fail"}, id="validation_only"),
        pytest.param({"attempt": 1, "run_kind": "task", "outcome": "blocked"}, id="blocked"),
        pytest.param({"attempt": 1, "run_kind": "task", "outcome": "refused"}, id="refused"),
        pytest.param({"attempt": 1, "run_kind": "task", "outcome": "aborted_human"}, id="aborted_human"),
    ],
)
def test_a_non_first_attempt_run_is_excluded_from_the_view(tmp_path, fields):
    """A retry, a fix_round/validation_only run, and a blocked,
    refused, or cancelled (aborted_human) outcome each fall outside the
    first-attempt rule and never enter the reliability count."""
    conn = _open(tmp_path)
    ticket_id = record.insert(conn, "ticket", title="t")
    record.insert(
        conn, "stage_run", ticket_id=ticket_id, stage="implementation", tier="light", manifest_hash="m1", **fields
    )

    rows = conn.execute("SELECT * FROM stage_reliability_view").fetchall()

    assert rows == []


def test_a_child_run_is_excluded_from_the_view(tmp_path):
    """A run with a non-null `parent_run_id` is a child (or utility)
    invocation, excluded from the first-attempt measure regardless of its
    own outcome or attempt number."""
    conn = _open(tmp_path)
    ticket_id = record.insert(conn, "ticket", title="t")
    parent_id = record.insert(
        conn, "stage_run", ticket_id=ticket_id, stage="clarification", tier="light",
        manifest_hash="m1", attempt=1, run_kind="task", outcome="pass",
    )
    record.insert(
        conn, "stage_run", ticket_id=ticket_id, stage="clarification", tier="light", manifest_hash="m1",
        attempt=1, run_kind="task", outcome="pass", parent_run_id=parent_id,
    )

    row = conn.execute(
        "SELECT eligible_count FROM stage_reliability_view WHERE stage = 'clarification'"
    ).fetchone()

    assert row["eligible_count"] == 1  # the parent alone, not the child


@pytest.mark.parametrize("kind", sorted(UTILITY_KINDS))
def test_a_seeded_utility_run_of_this_kind_is_excluded_from_the_view(tmp_path, kind):
    """for each utility_run kind, a seeded row of that kind never surfaces in
    stage_reliability_view: the view selects from stage_run alone, so with no
    stage_run seeded the view holds nothing at all."""
    conn = _open(tmp_path)
    record.insert(conn, "utility_run", kind=kind)

    rows = conn.execute("SELECT * FROM stage_reliability_view").fetchall()

    assert rows == []
