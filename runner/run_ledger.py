"""The one write path for `stage_run` and `utility_run` rows.

`run_stage` and every other caller open, heartbeat, finish, and cost-settle a
run through this module instead of calling `record.insert`/`record.update`
directly, so attempt numbering, lease bookkeeping, and the cost-provenance
contract each have exactly one implementation. Budgets and the default lease
length live in `factory/config/tiers.yaml`, read fresh on every call: it is
versioned config an engineer edits by hand, not a value worth caching against
the risk of serving a stale copy after an edit.
"""
import os
import socket
import sqlite3
import subprocess
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


def process_identity(pid: int | None = None) -> str:
    """`host:pid:start` for `pid` (this process by default), or `None` for a pid that is gone.

    The start time is part of the identity so a recycled pid on the same
    host can never be mistaken for the process that took the lease: the
    liveness check compares the whole string, not the pid alone.
    """
    pid = os.getpid() if pid is None else pid
    started = subprocess.run(
        ["ps", "-o", "lstart=", "-p", str(pid)], capture_output=True, text=True
    ).stdout.strip()
    if not started:
        return None
    return f"{socket.gethostname()}:{pid}:{started}"


def process_alive(identity: str | None) -> bool:
    """Whether the process `identity` names still exists with the same start time."""
    if not identity:
        return False
    pid = int(identity.split(":", 2)[1])
    return process_identity(pid) == identity


def expire_dead_runs(conn: sqlite3.Connection, ticket_id: int, *, now: str | None = None) -> list[int]:
    """Finish every still-open `stage_run`/`utility_run` of `ticket_id` whose lease has lapsed and process is gone.

    A row is left alone unless both conditions hold: its lease expired
    before `now` (a live run whose lease has simply not renewed yet stays
    open) and `process_alive` says the process that opened or last
    renewed it no longer exists (a slow but live run is never expired out
    from under itself). Every match finishes as `infrastructure_failure`;
    `finish` itself already applies `failure_kind` only to a `stage_run`,
    so one call site covers both tables. Registered artefacts and the
    ticket's own fields are never touched here -- expiry only closes the
    dead run's own row.
    """
    now = now or record.now()
    expired: list[int] = []
    for table in ("stage_run", "utility_run"):
        rows = conn.execute(
            f"SELECT id, process_identity FROM {table} "
            "WHERE ticket_id = ? AND outcome IS NULL AND lease_expires_at < ?",
            (ticket_id, now),
        ).fetchall()
        for row in rows:
            if process_alive(row["process_identity"]):
                continue
            finish(conn, row["id"], "infrastructure_failure", failure_kind="expired_lease", table=table)
            expired.append(row["id"])
    return expired


def record_reasoning_summary(conn: sqlite3.Connection, run_id: int, text: str) -> str:
    """Store at most `tiers.yaml`'s `reasoning_summary.max_words` words of `text` on the run, and return them.

    Words are whitespace-split and rejoined with single spaces, so the cap
    is on word count, not character count; an agent's self-report is
    truncated rather than refused, since the point is a bounded record,
    not a rejected run.
    """
    max_words = _tiers_config()["reasoning_summary"]["max_words"]
    capped = " ".join(text.split()[:max_words])
    record.update(conn, "stage_run", run_id, reasoning_summary=capped)
    return capped


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
    **identity,
) -> int:
    """Insert a new `stage_run` row and return its id: attempt computed, lease and heartbeat started now.

    `identity` carries the invocation's fixed identity an adapter knows
    before dispatch (runtime, versions, requested model, agent/skill/rubric
    refs, manifest and trust hashes, tool allowlist, digests, ordered
    inputs, envelope hash), written once at insert so those columns stay
    immutable; what the run learns only after it ends goes through
    `record_invocation_result`.
    """
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
        process_identity=process_identity(),
        started_at=heartbeat_at,
        heartbeat_at=heartbeat_at,
        lease_expires_at=lease_expires_at,
        **identity,
    )


def open_utility_run(
    conn: sqlite3.Connection,
    *,
    kind: str,
    ticket_id: int | None = None,
    inputs: str | None = None,
    outputs: str | None = None,
    manifest_hash: str | None = None,
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
        manifest_hash=manifest_hash,
        process_identity=process_identity(),
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


def record_invocation_result(
    conn: sqlite3.Connection,
    run_id: int,
    *,
    model_resolved: str | None = None,
    outputs: str | None = None,
    tokens_in: int | None = None,
    tokens_out: int | None = None,
    wall_clock_seconds: float | None = None,
    replayability: str | None = None,
    replayability_blind_spot: str | None = None,
) -> None:
    """Write what a `stage_run` learns only once its invocation has ended.

    These seven columns are the ones an adapter cannot know when the row
    opens -- the row exists, with its lease, before a possibly long
    invocation runs -- so they settle in place afterwards, the same way
    `reasoning_summary` does. Everything fixed before dispatch is written
    at insert by `open_stage_run`; attempt, lease, outcome and cost keep
    their own functions. Only fields actually passed are written.
    """
    fields = {
        "model_resolved": model_resolved,
        "outputs": outputs,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "wall_clock_seconds": wall_clock_seconds,
        "replayability": replayability,
        "replayability_blind_spot": replayability_blind_spot,
    }
    given = {name: value for name, value in fields.items() if value is not None}
    if given:
        record.update(conn, "stage_run", run_id, **given)


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
