"""Crash recovery: a killed run's lease and process identity both dead,
restart through `factory advance`, outbox-first reconciliation, and the
reasoning-summary cap `tiers.yaml` sets.

Every test opens its own `tmp_path` database, matching the rest of the
record/schema test suite. A "killed" run is seeded exactly as a ticket's
restart path expects to find one: an open `stage_run`/`utility_run` row
(no `outcome` yet) whose `process_identity` names a process that is gone.
`_open_dead_run` gets that identity onto the row by monkeypatching
`run_ledger.process_identity` for the one call that opens it, then
undoing the patch immediately so every later liveness check in the same
test runs the real function.
"""
import os
from pathlib import Path

import pytest
import yaml

from runner import artefact_registry, cli, governance, outbox, owners, record, run_ledger
from runner.db import connect
from runner.trust_profile import DEFAULT_TRUST_PROFILE_PATH

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "crash_recovery"
PER_STAGE = yaml.safe_load((FIXTURES_DIR / "per_stage.yaml").read_text())["stages"]
OUTBOX_FIRST = yaml.safe_load((FIXTURES_DIR / "outbox_first.yaml").read_text())

FAR_FUTURE = "2999-01-01T00:00:00+00:00"
# Well before any lease a test opens with a positive `lease_seconds`, and
# after none: a fixed past timestamp for a deliberately lapsed lease.
PAST = "2000-01-01T00:00:00+00:00"
# A pid this test process almost certainly is not and does not share a
# start time with, so the real `process_identity`/`process_alive` pair
# reports it as gone without ever touching another real process.
_DEAD_PID = os.getpid() + 999983


@pytest.fixture
def conn(tmp_path):
    connection = connect(tmp_path / "factory.sqlite")
    yield connection
    connection.close()


def _ticket_in(conn, state, **fields):
    return record.insert(conn, "ticket", state=state, opened_at=record.now(), **fields)


def _open_dead_run(monkeypatch, conn, *, table="stage_run", **kwargs):
    """Open a run whose `process_identity` names a pid that does not exist."""
    fake_identity = f"deadhost:{_DEAD_PID}:Thu Jan  1 00:00:00 1970"
    monkeypatch.setattr(run_ledger, "process_identity", lambda pid=None: fake_identity)
    try:
        if table == "stage_run":
            return run_ledger.open_stage_run(conn, **kwargs)
        return run_ledger.open_utility_run(conn, **kwargs)
    finally:
        monkeypatch.undo()


def _activate_default_profile(conn):
    """Satisfy the default trust profile's quorum, the same way `factory advance` reads it."""
    proposal = governance.propose(DEFAULT_TRUST_PROFILE_PATH, owners.DEFAULT_OWNERS_PATH)
    for role in ("security_approver", "legal_data_governance_approver"):
        governance.decide(
            conn, proposal, actor_identity="abhishek", role=role, decision="approve",
            expires_at=FAR_FUTURE, attestation_version="v1", attestation_hash=f"att-{role}",
            owners_path=owners.DEFAULT_OWNERS_PATH, profile_path=DEFAULT_TRUST_PROFILE_PATH,
        )
    conn.commit()


def test_killed_stage_run_restarted_produces_no_duplicate_row_for_the_attempt(conn, tmp_path, monkeypatch):
    """R-O-1: a stage_run killed mid-execution restarts through `factory advance`
    as `infrastructure_failure`/`expired_lease`, with a fresh attempt + 1 and
    no second row for the killed attempt."""
    ticket_id = _ticket_in(conn, "context")
    dead_id = _open_dead_run(monkeypatch, conn, ticket_id=ticket_id, stage="S1", lease_seconds=-1)
    conn.commit()

    cli.advance(conn, ticket_id, tmp_path)

    dead_row = record.get(conn, "stage_run", dead_id)
    assert dead_row["outcome"] == "infrastructure_failure"
    assert dead_row["failure_kind"] == "expired_lease"

    rows = conn.execute(
        "SELECT id, attempt FROM stage_run WHERE ticket_id = ? AND stage = 'S1' ORDER BY attempt", (ticket_id,)
    ).fetchall()
    assert [row["attempt"] for row in rows] == [1, 2]
    fresh = rows[1]
    assert record.get(conn, "stage_run", fresh["id"])["attempt"] == dead_row["attempt"] + 1


def test_must_reject_expiring_a_lease_whose_process_is_still_alive(conn):
    """R-O-1: a lapsed lease whose process is still alive is left open, not expired."""
    ticket_id = _ticket_in(conn, "implementing")
    run_id = run_ledger.open_stage_run(conn, ticket_id=ticket_id, stage="S4", lease_seconds=-1)
    conn.commit()

    expired = run_ledger.expire_dead_runs(conn, ticket_id)

    assert expired == []
    row = record.get(conn, "stage_run", run_id)
    assert row["outcome"] is None
    assert row["failure_kind"] is None


def test_an_open_run_whose_lease_has_not_lapsed_is_left_alone(conn, monkeypatch):
    """R-O-1: a dead process whose lease has not yet lapsed is left open."""
    ticket_id = _ticket_in(conn, "implementing")
    dead_id = _open_dead_run(monkeypatch, conn, ticket_id=ticket_id, stage="S4", lease_seconds=3600)
    conn.commit()

    expired = run_ledger.expire_dead_runs(conn, ticket_id)

    assert expired == []
    assert record.get(conn, "stage_run", dead_id)["outcome"] is None


def test_expiring_a_dead_run_preserves_artefacts_and_worktree_path(conn, monkeypatch):
    """R-O-1: expiring a dead run touches only its own row -- registered artefacts
    and the ticket's worktree_path are untouched."""
    ticket_id = _ticket_in(conn, "implementing", worktree_path="runs/tickets/1/worktree")
    dead_id = _open_dead_run(monkeypatch, conn, ticket_id=ticket_id, stage="S4", lease_seconds=-1)
    artefact_id = record.insert(
        conn, "artefact", ticket_id=ticket_id, stage_run_id=dead_id, kind="handoff",
        path="runs/tickets/1/runs/1/out/handoff.md", created_at=record.now(),
    )
    conn.commit()

    run_ledger.expire_dead_runs(conn, ticket_id)

    artefact = record.get(conn, "artefact", artefact_id)
    assert artefact["path"] == "runs/tickets/1/runs/1/out/handoff.md"
    assert artefact["stage_run_id"] == dead_id
    assert record.get(conn, "ticket", ticket_id)["worktree_path"] == "runs/tickets/1/worktree"


def test_expiring_a_dead_utility_run_carries_no_failure_kind(conn, monkeypatch):
    """R-O-1: a dead utility_run also expires to infrastructure_failure; the table has no failure_kind column."""
    ticket_id = _ticket_in(conn, "context")
    dead_id = _open_dead_run(
        monkeypatch, conn, table="utility_run", kind="digest", ticket_id=ticket_id, lease_seconds=-1
    )
    conn.commit()

    expired = run_ledger.expire_dead_runs(conn, ticket_id)

    assert expired == [dead_id]
    row = record.get(conn, "utility_run", dead_id)
    assert row["outcome"] == "infrastructure_failure"
    assert "failure_kind" not in row.keys()


def test_outbox_reconciles_before_a_fresh_attempt_opens(conn, tmp_path, monkeypatch):
    """R-O-1: restart reconciles pending external_write rows before expiring a
    dead lease or opening the fresh attempt it leads to."""
    _activate_default_profile(conn)
    ticket_id = _ticket_in(conn, **OUTBOX_FIRST["ticket"])
    outbox.create_intent(
        conn, ticket_id=ticket_id, operation="digest",
        payload={"ticket_id": str(ticket_id), **OUTBOX_FIRST["digest_payload"]},
        runs_dir=tmp_path,
    )
    dead_id = _open_dead_run(monkeypatch, conn, ticket_id=ticket_id, stage="S5", lease_seconds=-1)
    conn.commit()

    cli.advance(conn, ticket_id, tmp_path)

    intent = conn.execute(
        "SELECT * FROM external_write WHERE ticket_id = ?", (ticket_id,)
    ).fetchone()
    assert intent["state"] == "reconciled"
    assert intent["receipt_artefact_id"] is not None

    assert record.get(conn, "stage_run", dead_id)["outcome"] == "infrastructure_failure"
    fresh = conn.execute(
        "SELECT id FROM stage_run WHERE ticket_id = ? AND stage = 'S5' AND attempt = 2", (ticket_id,)
    ).fetchone()
    assert fresh is not None
    # Both the receipt and the fresh attempt's own check_evidence artefact
    # land in the same `artefact` table, so their row ids are directly
    # comparable: the receipt's lower id proves reconciliation's artefact
    # was written before the fresh attempt's.
    fresh_artefact = artefact_registry.latest(conn, ticket_id, "check_evidence")
    assert fresh_artefact["stage_run_id"] == fresh["id"]
    assert intent["receipt_artefact_id"] < fresh_artefact["id"]


def test_must_reject_a_reasoning_summary_over_the_cap(conn):
    """R-O-1: a summary longer than tiers.yaml's max_words is stored truncated to exactly that many words."""
    ticket_id = _ticket_in(conn, "implementing")
    run_id = run_ledger.open_stage_run(conn, ticket_id=ticket_id, stage="S4")
    max_words = run_ledger._tiers_config()["reasoning_summary"]["max_words"]
    long_summary = " ".join(f"word{i}" for i in range(max_words + 50))

    stored = run_ledger.record_reasoning_summary(conn, run_id, long_summary)

    assert len(stored.split()) == max_words
    assert record.get(conn, "stage_run", run_id)["reasoning_summary"] == stored


def test_reasoning_summary_under_the_cap_is_stored_unchanged(conn):
    """a summary within the cap is stored verbatim, word for word."""
    ticket_id = _ticket_in(conn, "implementing")
    run_id = run_ledger.open_stage_run(conn, ticket_id=ticket_id, stage="S4")

    stored = run_ledger.record_reasoning_summary(conn, run_id, "short summary of the run")

    assert stored == "short summary of the run"
    assert record.get(conn, "stage_run", run_id)["reasoning_summary"] == "short summary of the run"


@pytest.mark.parametrize("stage", sorted(PER_STAGE))
def test_per_stage_kill_and_restart_leaves_no_duplicate_row(conn, tmp_path, monkeypatch, stage):
    """R-O-1: for every stage S0 to S6, killing its run and rerunning `factory
    advance` completes with no duplicate stage_run row for the killed attempt."""
    spec = PER_STAGE[stage]
    ticket_id = _ticket_in(conn, spec["state"])
    for prior_stage in spec.get("prior_passes", []):
        prior_id = run_ledger.open_stage_run(conn, ticket_id=ticket_id, stage=prior_stage)
        run_ledger.finish(conn, prior_id, "pass")
    conn.commit()

    dead_id = _open_dead_run(monkeypatch, conn, ticket_id=ticket_id, stage=stage, lease_seconds=-1)
    conn.commit()

    cli.advance(conn, ticket_id, tmp_path)

    dead_row = record.get(conn, "stage_run", dead_id)
    assert dead_row["outcome"] == "infrastructure_failure"
    assert dead_row["failure_kind"] == "expired_lease"

    rows = conn.execute(
        "SELECT attempt FROM stage_run WHERE ticket_id = ? AND stage = ? ORDER BY attempt", (ticket_id, stage)
    ).fetchall()
    assert [row["attempt"] for row in rows] == [1, 2]
