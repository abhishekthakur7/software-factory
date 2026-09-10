"""The run ledger: the one write path for `stage_run` and `utility_run` rows,
the closed value sets the schema now enforces on them, and the budgets and
lease length `tiers.yaml` carries.

Every test opens its own `tmp_path` database, matching the rest of the
record/schema test suite.
"""
import sqlite3

import pytest

from runner import record, run_ledger
from runner.db import connect


def _open(tmp_path):
    return connect(tmp_path / "factory.sqlite")


def _ticket(conn, **fields):
    return record.insert(conn, "ticket", title="t", **fields)



def test_must_reject_a_stage_run_with_a_null_ticket_id(tmp_path):
    """creating a stage_run row with no ticket_id is rejected by the schema."""
    conn = _open(tmp_path)
    with pytest.raises(sqlite3.IntegrityError):
        record.insert(conn, "stage_run", stage="context_gathering")


def test_must_reject_a_stage_run_with_a_stage_outside_intake_to_merge(tmp_path):
    """creating a stage_run row with a stage value outside intake to merge is
    rejected by the schema."""
    conn = _open(tmp_path)
    ticket_id = _ticket(conn)
    with pytest.raises(sqlite3.IntegrityError):
        record.insert(conn, "stage_run", ticket_id=ticket_id, stage="S8")


def test_must_reject_a_stage_run_with_an_unknown_run_kind(tmp_path):
    conn = _open(tmp_path)
    ticket_id = _ticket(conn)
    with pytest.raises(sqlite3.IntegrityError):
        record.insert(conn, "stage_run", ticket_id=ticket_id, stage="context_gathering", run_kind="made_up")


def test_must_reject_a_stage_run_with_an_unknown_outcome(tmp_path):
    conn = _open(tmp_path)
    ticket_id = _ticket(conn)
    with pytest.raises(sqlite3.IntegrityError):
        record.insert(conn, "stage_run", ticket_id=ticket_id, stage="context_gathering", outcome="made_up")


def test_must_reject_a_stage_run_with_an_unknown_failure_kind(tmp_path):
    conn = _open(tmp_path)
    ticket_id = _ticket(conn)
    with pytest.raises(sqlite3.IntegrityError):
        record.insert(conn, "stage_run", ticket_id=ticket_id, stage="context_gathering", failure_kind="made_up")


def test_must_reject_a_stage_run_with_an_unknown_cost_basis(tmp_path):
    conn = _open(tmp_path)
    ticket_id = _ticket(conn)
    with pytest.raises(sqlite3.IntegrityError):
        record.insert(conn, "stage_run", ticket_id=ticket_id, stage="context_gathering", cost_basis="made_up")


def test_must_reject_a_utility_run_with_an_unknown_kind(tmp_path):
    conn = _open(tmp_path)
    with pytest.raises(sqlite3.IntegrityError):
        record.insert(conn, "utility_run", kind="made_up")


def test_must_reject_a_utility_run_with_an_unknown_cost_basis(tmp_path):
    conn = _open(tmp_path)
    with pytest.raises(sqlite3.IntegrityError):
        record.insert(conn, "utility_run", kind="setup", cost_basis="made_up")



def test_a_child_stage_run_carries_its_parent_run_id(tmp_path):
    """A child stage_run created during a parent's execution, such as a clarification
    restatement, carries parent_run_id pointing at the parent run."""
    conn = _open(tmp_path)
    ticket_id = _ticket(conn, state="clarifying")
    parent_id = run_ledger.open_stage_run(conn, ticket_id=ticket_id, stage="clarification")

    child_id = run_ledger.open_stage_run(
        conn, ticket_id=ticket_id, stage="clarification", parent_run_id=parent_id
    )

    assert record.get(conn, "stage_run", child_id)["parent_run_id"] == parent_id


def test_attempt_counts_prior_runs_of_the_same_ticket_and_stage_plus_one(tmp_path):
    conn = _open(tmp_path)
    ticket_id = _ticket(conn, state="implementing")

    first = run_ledger.open_stage_run(conn, ticket_id=ticket_id, stage="implementation")
    second = run_ledger.open_stage_run(conn, ticket_id=ticket_id, stage="implementation", run_kind="fix_round")
    other_stage = run_ledger.open_stage_run(conn, ticket_id=ticket_id, stage="context_gathering")
    other_ticket = run_ledger.open_stage_run(
        conn, ticket_id=_ticket(conn, state="implementing"), stage="implementation"
    )

    assert record.get(conn, "stage_run", first)["attempt"] == 1
    assert record.get(conn, "stage_run", second)["attempt"] == 2
    assert record.get(conn, "stage_run", other_stage)["attempt"] == 1
    assert record.get(conn, "stage_run", other_ticket)["attempt"] == 1



def test_open_stage_run_starts_its_own_lease(tmp_path):
    conn = _open(tmp_path)
    ticket_id = _ticket(conn, state="context")

    run_id = run_ledger.open_stage_run(conn, ticket_id=ticket_id, stage="context_gathering", lease_seconds=60)

    row = record.get(conn, "stage_run", run_id)
    assert row["started_at"] is not None
    assert row["heartbeat_at"] == row["started_at"]
    assert row["lease_expires_at"] > row["heartbeat_at"]


def test_heartbeat_renews_a_stage_runs_lease(tmp_path):
    """heartbeat moves heartbeat_at and lease_expires_at forward from what the run opened with."""
    conn = _open(tmp_path)
    ticket_id = _ticket(conn, state="implementing")
    run_id = run_ledger.open_stage_run(conn, ticket_id=ticket_id, stage="implementation", lease_seconds=1)
    opened = record.get(conn, "stage_run", run_id)

    run_ledger.heartbeat(conn, run_id, lease_seconds=3600)

    renewed = record.get(conn, "stage_run", run_id)
    assert renewed["heartbeat_at"] >= opened["heartbeat_at"]
    assert renewed["lease_expires_at"] > opened["lease_expires_at"]


def test_heartbeat_renews_a_utility_runs_lease_via_the_table_argument(tmp_path):
    conn = _open(tmp_path)
    run_id = run_ledger.open_utility_run(conn, kind="digest", lease_seconds=1)
    opened = record.get(conn, "utility_run", run_id)

    run_ledger.heartbeat(conn, run_id, table="utility_run", lease_seconds=3600)

    renewed = record.get(conn, "utility_run", run_id)
    assert renewed["lease_expires_at"] > opened["lease_expires_at"]


def test_finish_stamps_outcome_and_ended_at_on_a_stage_run(tmp_path):
    conn = _open(tmp_path)
    ticket_id = _ticket(conn, state="context")
    run_id = run_ledger.open_stage_run(conn, ticket_id=ticket_id, stage="context_gathering")
    assert record.get(conn, "stage_run", run_id)["ended_at"] is None

    run_ledger.finish(conn, run_id, "fail", failure_kind="implementation")

    row = record.get(conn, "stage_run", run_id)
    assert row["outcome"] == "fail"
    assert row["failure_kind"] == "implementation"
    assert row["ended_at"] is not None


def test_finish_stamps_outcome_and_ended_at_on_a_utility_run(tmp_path):
    conn = _open(tmp_path)
    run_id = run_ledger.open_utility_run(conn, kind="setup")
    assert record.get(conn, "utility_run", run_id)["ended_at"] is None

    run_ledger.finish(conn, run_id, "pass", table="utility_run")

    row = record.get(conn, "utility_run", run_id)
    assert row["outcome"] == "pass"
    assert row["ended_at"] is not None



def test_settle_cost_writes_the_cost_group_once(tmp_path):
    conn = _open(tmp_path)
    ticket_id = _ticket(conn, state="context")
    run_id = run_ledger.open_stage_run(conn, ticket_id=ticket_id, stage="context_gathering")

    run_ledger.settle_cost(conn, run_id, cost=1.25, currency="USD", cost_basis="provider_settled")

    row = record.get(conn, "stage_run", run_id)
    assert row["cost"] == 1.25
    assert row["currency"] == "USD"
    assert row["cost_basis"] == "provider_settled"
    assert row["cost_settled_at"] is not None


def test_settle_cost_accepts_a_price_table_estimate_with_its_hash(tmp_path):
    conn = _open(tmp_path)
    ticket_id = _ticket(conn, state="context")
    run_id = run_ledger.open_stage_run(conn, ticket_id=ticket_id, stage="context_gathering")

    run_ledger.settle_cost(
        conn, run_id, cost=2.0, currency="USD",
        cost_basis="price_table_estimate", pricing_table_hash="deadbeef",
    )

    row = record.get(conn, "stage_run", run_id)
    assert row["cost_basis"] == "price_table_estimate"
    assert row["pricing_table_hash"] == "deadbeef"


def test_settle_cost_accepts_a_null_cost_with_the_unavailable_basis(tmp_path):
    conn = _open(tmp_path)
    ticket_id = _ticket(conn, state="context")
    run_id = run_ledger.open_stage_run(conn, ticket_id=ticket_id, stage="context_gathering")

    run_ledger.settle_cost(conn, run_id, cost=None, currency=None, cost_basis="unavailable")

    row = record.get(conn, "stage_run", run_id)
    assert row["cost"] is None
    assert row["cost_basis"] == "unavailable"


def test_must_reject_settle_cost_with_an_unknown_cost_basis(tmp_path):
    conn = _open(tmp_path)
    ticket_id = _ticket(conn, state="context")
    run_id = run_ledger.open_stage_run(conn, ticket_id=ticket_id, stage="context_gathering")

    with pytest.raises(ValueError):
        run_ledger.settle_cost(conn, run_id, cost=1.0, currency="USD", cost_basis="made_up")


def test_must_reject_settle_cost_with_a_nonnull_cost_and_no_currency(tmp_path):
    conn = _open(tmp_path)
    ticket_id = _ticket(conn, state="context")
    run_id = run_ledger.open_stage_run(conn, ticket_id=ticket_id, stage="context_gathering")

    with pytest.raises(ValueError):
        run_ledger.settle_cost(conn, run_id, cost=1.0, currency=None, cost_basis="runtime_estimate")


def test_must_reject_settle_cost_price_table_estimate_without_its_hash(tmp_path):
    conn = _open(tmp_path)
    ticket_id = _ticket(conn, state="context")
    run_id = run_ledger.open_stage_run(conn, ticket_id=ticket_id, stage="context_gathering")

    with pytest.raises(ValueError):
        run_ledger.settle_cost(
            conn, run_id, cost=1.0, currency="USD", cost_basis="price_table_estimate"
        )


def test_must_reject_settle_cost_pricing_table_hash_outside_a_price_table_estimate(tmp_path):
    conn = _open(tmp_path)
    ticket_id = _ticket(conn, state="context")
    run_id = run_ledger.open_stage_run(conn, ticket_id=ticket_id, stage="context_gathering")

    with pytest.raises(ValueError):
        run_ledger.settle_cost(
            conn, run_id, cost=1.0, currency="USD",
            cost_basis="provider_settled", pricing_table_hash="deadbeef",
        )


def test_must_reject_a_second_cost_settlement_of_the_same_run(tmp_path):
    conn = _open(tmp_path)
    ticket_id = _ticket(conn, state="context")
    run_id = run_ledger.open_stage_run(conn, ticket_id=ticket_id, stage="context_gathering")
    run_ledger.settle_cost(conn, run_id, cost=1.0, currency="USD", cost_basis="provider_settled")

    with pytest.raises(sqlite3.IntegrityError):
        run_ledger.settle_cost(conn, run_id, cost=2.0, currency="USD", cost_basis="provider_settled")



def test_budget_reads_the_per_tier_figures_tiers_yaml_holds():
    assert run_ledger.budget("context_gathering", "light") == {"tokens": 400000, "wall_clock_seconds": 1200}
    assert run_ledger.budget("clarification", "standard") == {"tokens": 800000, "wall_clock_seconds": 2400}
    assert run_ledger.budget("planning", "heavy") == {"tokens": 1500000, "wall_clock_seconds": 3600}


def test_budget_gives_checks_no_wall_clock_budget_at_any_tier():
    """The checks stage carries no wall-clock budget at any tier: its build commands carry their own timeout."""
    for tier in ("light", "standard", "heavy"):
        assert run_ledger.budget("checks", tier)["wall_clock_seconds"] is None


def test_implementation_per_ticket_budget_reads_the_cumulative_figures():
    assert run_ledger.implementation_per_ticket_budget("light") == {
        "tokens": 1000000, "wall_clock_seconds": 2700,
    }
    assert run_ledger.implementation_per_ticket_budget("heavy") == {
        "tokens": 4000000, "wall_clock_seconds": 9000,
    }
