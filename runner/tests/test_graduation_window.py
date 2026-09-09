"""The graduation window: candidate tickets, the window start, and the severe-incident reset."""
from runner import graduation, record
from runner.db import connect
from runner.tests.fixtures.graduation import seed

CUTOFF = "2026-02-01T00:00:00"


def _conn(tmp_path):
    return connect(tmp_path / "factory.sqlite")


def _limits(**overrides):
    return {
        "window_min_outcomes": 1, "stage_min_first_attempts": 1, "stage_min_pass_share": 0.5,
        "baseline_min_comparable": 1, "severe_severities": ["sev1", "sev2"], **overrides,
    }


def test_window_candidates_are_non_baseline_merged_or_abandoned_tickets_closed_in_range(tmp_path):
    """A candidate ticket has `baseline = 0`, `close_reason` `merged`/`abandoned`, and `closed_at` inside `[start, cutoff]`."""
    conn = _conn(tmp_path)
    merged_id = seed.seed_window_ticket(conn, closed_at="2026-01-10T00:00:00", close_reason="merged")
    abandoned_id = seed.seed_window_ticket(conn, closed_at="2026-01-11T00:00:00", close_reason="abandoned")
    baseline_id = seed.seed_ticket(conn, closed_at="2026-01-10T00:00:00", close_reason="merged", baseline=1)
    open_id = seed.seed_ticket(conn, closed_at=None, close_reason=None)
    after_cutoff_id = seed.seed_window_ticket(conn, closed_at="2026-03-01T00:00:00", close_reason="merged")
    conn.commit()

    result = graduation.window(conn, _limits(), cutoff=CUTOFF)

    assert set(result["inputs"]["ticket_ids"]) == {merged_id, abandoned_id}
    assert baseline_id not in result["inputs"]["ticket_ids"]
    assert open_id not in result["inputs"]["ticket_ids"]
    assert after_cutoff_id not in result["inputs"]["ticket_ids"]


def test_window_start_is_the_later_of_the_prior_approval_and_the_latest_remediation(tmp_path):
    """`start` is the later of the prior graduation-approve `decided_at` and the newest severe-attributable remediation."""
    conn = _conn(tmp_path)
    record.insert(
        conn, "approval_record", gate="graduation", decision="approve", decided_at="2026-01-05T00:00:00",
        subject_hash="s1", slot_id="factory_owner|", actor_identity="abhishek", role="factory_owner",
    )
    ticket_id = seed.seed_window_ticket(conn, closed_at="2026-01-20T00:00:00")
    event_id = seed.seed_incident_event(conn, ticket_id, severity="sev1")
    seed.seed_disposition(
        conn, event_id, ticket_id, attribution="attributable", disposition="remediated", created_at="2026-01-08T00:00:00",
    )
    conn.commit()

    result = graduation.window(conn, _limits(), cutoff=CUTOFF)

    assert result["inputs"]["start"] == "2026-01-08T00:00:00"


def test_a_prior_graduation_approval_excludes_a_ticket_closed_before_its_decision_time(tmp_path):
    """The fresh-window test: a ticket closed before the prior approval's `decided_at` falls outside the new window."""
    conn = _conn(tmp_path)
    record.insert(
        conn, "approval_record", gate="graduation", decision="approve", decided_at="2026-01-15T00:00:00",
        subject_hash="s1", slot_id="factory_owner|", actor_identity="abhishek", role="factory_owner",
    )
    stale_id = seed.seed_window_ticket(conn, closed_at="2026-01-10T00:00:00")
    fresh_id = seed.seed_window_ticket(conn, closed_at="2026-01-20T00:00:00")
    conn.commit()

    result = graduation.window(conn, _limits(), cutoff=CUTOFF)

    assert stale_id not in result["inputs"]["ticket_ids"]
    assert fresh_id in result["inputs"]["ticket_ids"]


def test_a_remediated_severe_attributable_incident_opens_the_window_at_its_disposition_time(tmp_path):
    """A remediated severe, attributable incident sets `start` to that disposition's own timestamp."""
    conn = _conn(tmp_path)
    ticket_id = seed.seed_window_ticket(conn, closed_at="2026-01-20T00:00:00")
    event_id = seed.seed_incident_event(conn, ticket_id, severity="sev2")
    seed.seed_disposition(
        conn, event_id, ticket_id, attribution="attributable", disposition="remediated", created_at="2026-01-12T00:00:00",
    )
    conn.commit()

    result = graduation.window(conn, _limits(), cutoff=CUTOFF)

    assert result["inputs"]["start"] == "2026-01-12T00:00:00"
    assert result["inputs"]["reset_pending"] is False


def test_an_unremediated_severe_attributable_incident_leaves_the_window_empty(tmp_path):
    """The incident-reset test: an open severe, attributable incident sets `reset_pending` and an empty window."""
    conn = _conn(tmp_path)
    ticket_id = seed.seed_window_ticket(conn, closed_at="2026-01-20T00:00:00")
    event_id = seed.seed_incident_event(conn, ticket_id, severity="sev1")
    seed.seed_disposition(conn, event_id, ticket_id, attribution="attributable", disposition="open")
    conn.commit()

    result = graduation.window(conn, _limits(), cutoff=CUTOFF)

    assert result["inputs"]["reset_pending"] is True
    assert result["inputs"]["ticket_ids"] == []
    assert result["passed"] is False


def test_a_non_attributable_severe_incident_never_triggers_a_reset(tmp_path):
    """An incident whose latest disposition is not attributable is not a graduation reset trigger, even at severe severity."""
    conn = _conn(tmp_path)
    ticket_id = seed.seed_window_ticket(conn, closed_at="2026-01-20T00:00:00")
    event_id = seed.seed_incident_event(conn, ticket_id, severity="sev1")
    seed.seed_disposition(conn, event_id, ticket_id, attribution="not_attributable", disposition="open")
    conn.commit()

    result = graduation.window(conn, _limits(), cutoff=CUTOFF)

    assert result["inputs"]["reset_pending"] is False
    assert ticket_id in result["inputs"]["ticket_ids"]


def test_must_fail_the_window_clause_with_fewer_than_window_min_outcomes_tickets(tmp_path):
    """The window-size test: fewer than `window_min_outcomes` eligible tickets fails the clause."""
    conn = _conn(tmp_path)
    seed.seed_window_ticket(conn, closed_at="2026-01-10T00:00:00")
    conn.commit()

    result = graduation.window(conn, _limits(window_min_outcomes=2), cutoff=CUTOFF)

    assert result["passed"] is False
    assert any("insufficient_outcomes" in reason for reason in result["reasons"])
