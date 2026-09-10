"""`outcome`'s own production-coverage rows, and the ticket-scoped `exposure`/`coverage` series that extends them."""
import pytest

from runner import queue, record
from runner.tests.test_outcome_revision import conn, seed_pr_opened_ticket, seed_pr_outcome_item, ABHISHEK

_MERGED_FIELDS = {
    "result": "merged", "head_sha": "final-head", "target_base_sha": "final-base",
    "checks": "green", "observed_at": "2025-01-01T00:00:00+00:00",
}


def _merge(conn, tmp_path, ticket_id: int) -> None:
    item_id = seed_pr_outcome_item(conn, ticket_id)
    queue.act(conn, item_id=item_id, action="outcome", actor=ABHISHEK, fields=dict(_MERGED_FIELDS), runs_dir=tmp_path)


def _abandon(conn, tmp_path, ticket_id: int) -> None:
    item_id = seed_pr_outcome_item(conn, ticket_id)
    queue.act(
        conn, item_id=item_id, action="outcome", actor=ABHISHEK,
        fields={**_MERGED_FIELDS, "result": "abandoned", "fm_id": "question_noise"}, runs_dir=tmp_path,
    )


def _coverage_rows(conn, ticket_id: int):
    return conn.execute(
        "SELECT * FROM incident_observation WHERE ticket_id = ? AND record_kind = 'production_coverage' ORDER BY id",
        (ticket_id,),
    ).fetchall()


def test_an_abandoned_outcome_appends_a_not_deployed_coverage_row(conn, tmp_path):
    ticket_id = seed_pr_opened_ticket(conn)
    _abandon(conn, tmp_path, ticket_id)
    rows = _coverage_rows(conn, ticket_id)
    assert len(rows) == 1
    assert rows[0]["coverage_status"] == "not_deployed"


def test_a_merged_outcome_appends_an_unknown_coverage_row_with_no_exposure_fields(conn, tmp_path):
    ticket_id = seed_pr_opened_ticket(conn)
    _merge(conn, tmp_path, ticket_id)
    rows = _coverage_rows(conn, ticket_id)
    assert len(rows) == 1
    assert rows[0]["coverage_status"] == "unknown"
    assert rows[0]["exposure_start"] is None
    assert rows[0]["exposure_source"] is None


def test_exposure_appends_an_unknown_status_row_superseding_the_earlier_coverage_row(conn, tmp_path):
    ticket_id = seed_pr_opened_ticket(conn)
    _merge(conn, tmp_path, ticket_id)
    earlier = _coverage_rows(conn, ticket_id)[0]

    queue.act(
        conn, ticket_id=ticket_id, action="exposure", actor=ABHISHEK,
        fields={"start": "2025-02-01T00:00:00+00:00", "source": "deploy log"},
    )

    rows = _coverage_rows(conn, ticket_id)
    assert len(rows) == 2
    assert rows[1]["coverage_status"] == "unknown"
    assert rows[1]["exposure_start"] == "2025-02-01T00:00:00+00:00"
    assert rows[1]["exposure_source"] == "deploy log"
    assert rows[1]["supersedes"] == earlier["id"]


def test_coverage_appends_a_none_observed_row_superseding_within_the_series(conn, tmp_path):
    ticket_id = seed_pr_opened_ticket(conn)
    _merge(conn, tmp_path, ticket_id)
    queue.act(
        conn, ticket_id=ticket_id, action="exposure", actor=ABHISHEK,
        fields={"start": "2025-02-01T00:00:00+00:00", "source": "deploy log"},
    )
    exposure_row = _coverage_rows(conn, ticket_id)[-1]

    queue.act(conn, ticket_id=ticket_id, action="coverage", actor=ABHISHEK, fields={"through": "2025-03-01T00:00:00+00:00"})

    rows = _coverage_rows(conn, ticket_id)
    assert rows[-1]["coverage_status"] == "none_observed"
    assert rows[-1]["observed_through"] == "2025-03-01T00:00:00+00:00"
    assert rows[-1]["supersedes"] == exposure_row["id"]


def test_must_reject_coverage_whose_current_row_carries_no_exposure_start_and_source(conn, tmp_path):
    """The freshly merged `unknown` row carries no exposure fields yet."""
    ticket_id = seed_pr_opened_ticket(conn)
    _merge(conn, tmp_path, ticket_id)
    with pytest.raises(queue.ActionRefused):
        queue.act(conn, ticket_id=ticket_id, action="coverage", actor=ABHISHEK, fields={"through": "2025-03-01T00:00:00+00:00"})


def test_must_reject_coverage_naming_a_production_incident_event_root(conn, tmp_path):
    ticket_id = seed_pr_opened_ticket(conn)
    _merge(conn, tmp_path, ticket_id)
    queue.act(
        conn, ticket_id=ticket_id, action="incident_event", actor=ABHISHEK,
        fields={"severity": "sev3", "occurred_at": "2025-02-01T00:00:00+00:00", "fm_id": "question_noise", "note": "a real incident"},
    )
    event_row = conn.execute(
        "SELECT id FROM incident_observation WHERE ticket_id = ? AND record_kind = 'production_incident_event'", (ticket_id,)
    ).fetchone()
    with pytest.raises(queue.ActionRefused):
        queue.act(
            conn, ticket_id=ticket_id, action="coverage", actor=ABHISHEK,
            fields={"through": "2025-03-01T00:00:00+00:00", "root": str(event_row["id"])},
        )


def test_must_reject_exposure_naming_a_coverage_root_of_a_different_ticket(conn, tmp_path):
    ticket_id = seed_pr_opened_ticket(conn)
    _merge(conn, tmp_path, ticket_id)
    other_ticket_id = seed_pr_opened_ticket(conn)
    _merge(conn, tmp_path, other_ticket_id)
    other_root = _coverage_rows(conn, other_ticket_id)[0]

    with pytest.raises(queue.ActionRefused):
        queue.act(
            conn, ticket_id=ticket_id, action="exposure", actor=ABHISHEK,
            fields={"start": "2025-02-01T00:00:00+00:00", "source": "deploy log", "root": str(other_root["id"])},
        )
