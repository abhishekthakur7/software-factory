"""The one write path for `stage_run` and `utility_run` rows.

`run_stage` and every other caller open, heartbeat, finish, and cost-settle a
run through this module instead of calling `record.insert`/`record.update`
directly, so attempt numbering, lease bookkeeping, and the cost-provenance
contract each have exactly one implementation. Budgets and the default lease
length live in `factory/config/tiers.yaml`, read fresh on every call: it is
versioned config an engineer edits by hand, not a value worth caching against
the risk of serving a stale copy after an edit.
"""
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml

from runner import record
from runner.paths import FACTORY_DIR
from runner.schema import COST_BASES

TIERS_PATH = FACTORY_DIR / "config" / "tiers.yaml"


def _tiers_config() -> dict:
    return yaml.safe_load(Path(TIERS_PATH).read_text())


def _default_lease_seconds() -> int:
    return _tiers_config()["leases"]["seconds"]


def _lease_fields(lease_seconds: int | None) -> tuple[str, str]:
    """(heartbeat_at, lease_expires_at) for a run opened or renewed now."""
    if lease_seconds is None:
        lease_seconds = _default_lease_seconds()
    now = datetime.now(UTC)
    heartbeat_at = now.isoformat(timespec="seconds")
    lease_expires_at = (now + timedelta(seconds=lease_seconds)).isoformat(timespec="seconds")
    return heartbeat_at, lease_expires_at


def _next_attempt(conn: sqlite3.Connection, ticket_id: int, stage: str) -> int:
    """The count of this ticket's prior `stage_run` rows for `stage`, plus one."""
    prior = conn.execute(
        "SELECT COUNT(*) FROM stage_run WHERE ticket_id = ? AND stage = ?", (ticket_id, stage)
    ).fetchone()[0]
    return prior + 1


def open_stage_run(
    conn: sqlite3.Connection,
    *,
    ticket_id: int,
    stage: str,
    run_kind: str = "task",
    parent_run_id: int | None = None,
    tier: str | None = None,
    lease_seconds: int | None = None,
) -> int:
    """Insert a new `stage_run` row and return its id: attempt computed, lease and heartbeat started now."""
    heartbeat_at, lease_expires_at = _lease_fields(lease_seconds)
    return record.insert(
        conn,
        "stage_run",
        ticket_id=ticket_id,
        stage=stage,
        attempt=_next_attempt(conn, ticket_id, stage),
        run_kind=run_kind,
        parent_run_id=parent_run_id,
        tier=tier,
        started_at=heartbeat_at,
        heartbeat_at=heartbeat_at,
        lease_expires_at=lease_expires_at,
    )


def open_utility_run(
    conn: sqlite3.Connection,
    *,
    kind: str,
    ticket_id: int | None = None,
    inputs: str | None = None,
    outputs: str | None = None,
    lease_seconds: int | None = None,
) -> int:
    """Insert a new `utility_run` row and return its id: lease and heartbeat started now."""
    heartbeat_at, lease_expires_at = _lease_fields(lease_seconds)
    return record.insert(
        conn,
        "utility_run",
        ticket_id=ticket_id,
        kind=kind,
        inputs=inputs,
        outputs=outputs,
        started_at=heartbeat_at,
        heartbeat_at=heartbeat_at,
        lease_expires_at=lease_expires_at,
    )


def heartbeat(
    conn: sqlite3.Connection, run_id: int, *, table: str = "stage_run", lease_seconds: int | None = None
) -> None:
    """Refresh `heartbeat_at`/`lease_expires_at` on a live `stage_run` or `utility_run`, renewing its lease."""
    heartbeat_at, lease_expires_at = _lease_fields(lease_seconds)
    record.update(conn, table, run_id, heartbeat_at=heartbeat_at, lease_expires_at=lease_expires_at)


def finish(
    conn: sqlite3.Connection,
    run_id: int,
    outcome: str,
    *,
    failure_kind: str | None = None,
    table: str = "stage_run",
) -> None:
    """Stamp `outcome` and `ended_at`; `failure_kind` is meaningful only on a `stage_run`."""
    fields = {"outcome": outcome, "ended_at": record.now()}
    if table == "stage_run":
        fields["failure_kind"] = failure_kind
    record.update(conn, table, run_id, **fields)


def settle_cost(
    conn: sqlite3.Connection,
    run_id: int,
    *,
    cost: float | None,
    currency: str | None,
    cost_basis: str,
    pricing_table_hash: str | None = None,
) -> None:
    """Write a `stage_run`'s once-only cost group, enforcing the PRD's provenance contract.

    Raises `ValueError` before touching the database for a `cost_basis`
    outside the closed set, a non-null `cost` with no `currency`, a
    `price_table_estimate` basis with no `pricing_table_hash`, or a
    `pricing_table_hash` given under any other basis. The schema's
    settle-once trigger separately rejects a second settlement of the same
    run.
    """
    if cost_basis not in COST_BASES:
        raise ValueError(f"unknown cost_basis: {cost_basis!r}")
    if cost is not None and currency is None:
        raise ValueError("currency is required when cost is not null")
    if cost_basis == "price_table_estimate" and pricing_table_hash is None:
        raise ValueError("pricing_table_hash is required for a price_table_estimate")
    if cost_basis != "price_table_estimate" and pricing_table_hash is not None:
        raise ValueError("pricing_table_hash only applies to a price_table_estimate")
    record.update(
        conn,
        "stage_run",
        run_id,
        cost=cost,
        currency=currency,
        cost_basis=cost_basis,
        pricing_table_hash=pricing_table_hash,
        cost_settled_at=record.now(),
    )


def budget(stage: str, tier: str) -> dict:
    """The `{tokens, wall_clock_seconds}` budget for one run of `stage` at `tier`.

    `wall_clock_seconds` is `None` where `tiers.yaml` overrides it for the
    stage (S5's build commands carry their own timeout), read as data rather
    than special-cased here.
    """
    budgets = _tiers_config()["budgets"]
    resolved = dict(budgets["by_tier"][tier])
    resolved.update(budgets.get("overrides", {}).get(stage, {}))
    return resolved


def s4_per_ticket_budget(tier: str) -> dict:
    """The cumulative `{tokens, wall_clock_seconds}` budget across one ticket's S4 task invocations."""
    return dict(_tiers_config()["s4_per_ticket"][tier])
