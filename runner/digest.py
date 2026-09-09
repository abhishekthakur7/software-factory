"""Build the configured cadence's minimal attention digest and queue it through the outbox."""
from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from runner import canonical, outbox, record
from runner.paths import RUNS_DIR


class DigestConfigurationError(ValueError):
    """The configured digest cadence is missing or unsupported."""


def cadence_slot(cadence: str, now: datetime) -> str:
    """The UTC slot identifier whose stability makes a scheduled retry idempotent."""
    instant = now.astimezone(UTC)
    if cadence == "hourly":
        return instant.strftime("%Y-%m-%dT%H")
    if cadence == "daily":
        return instant.strftime("%Y-%m-%d")
    if cadence == "weekly":
        year, week, _day = instant.isocalendar()
        return f"{year}-W{week:02d}"
    raise DigestConfigurationError(f"unsupported digest cadence {cadence!r}")


def _slot_start(cadence: str, now: datetime) -> datetime:
    instant = now.astimezone(UTC)
    if cadence == "hourly":
        return instant.replace(minute=0, second=0, microsecond=0)
    if cadence == "daily":
        return instant.replace(hour=0, minute=0, second=0, microsecond=0)
    if cadence == "weekly":
        return instant.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=instant.weekday())
    raise DigestConfigurationError(f"unsupported digest cadence {cadence!r}")


def _age(queued_at: str | None, now: datetime) -> str:
    if not queued_at:
        return "unknown"
    try:
        started = datetime.fromisoformat(queued_at.replace("Z", "+00:00"))
    except ValueError:
        return "unknown"
    seconds = max(0, int((now - started.astimezone(UTC)).total_seconds()))
    if seconds < 3600:
        return f"{seconds // 60}m"
    if seconds < 86400:
        return f"{seconds // 3600}h"
    return f"{seconds // 86400}d"


def open_items(conn: sqlite3.Connection, *, now: datetime) -> list[dict]:
    """The narrow, deterministic projection that is permitted to leave the factory."""
    rows = conn.execute(
        "SELECT qi.id, qi.ticket_id, qi.tier, qi.kind, qi.queued_at, t.state "
        "FROM queue_item qi LEFT JOIN ticket t ON t.id = qi.ticket_id "
        "WHERE qi.resolved_at IS NULL ORDER BY qi.ticket_id, qi.id"
    ).fetchall()
    return [
        {
            "ticket_id": str(row["ticket_id"]),
            "tier": row["tier"] or "unknown",
            "item_kind": row["kind"],
            "age": _age(row["queued_at"], now),
            "command": f"factory act {row['id']} inspect --actor <identity>",
        }
        for row in rows
    ]


def _text(items: list[dict]) -> str:
    return "\n".join(
        f"{item['ticket_id']} | {item['tier']} | {item['item_kind']} | {item['age']} | {item['command']}"
        for item in items
    )


def run(
    conn: sqlite3.Connection,
    *,
    channel: str | None,
    cadence: str,
    now: datetime | None = None,
    runs_dir: Path = RUNS_DIR,
    dispatch: bool = True,
) -> int | None:
    """Record one digest utility run and, when there is work, create and dispatch its one outbox intent."""
    instant = now or datetime.now(UTC)
    slot = cadence_slot(cadence, instant)
    items = open_items(conn, now=_slot_start(cadence, instant))
    if not items:
        record.insert(
            conn, "utility_run", kind="digest", inputs=json.dumps({"open_item_count": 0}, sort_keys=True),
            outputs=json.dumps({"intent_id": None}), process_identity="factory digest", outcome="pass",
            started_at=record.now(), ended_at=record.now(),
        )
        conn.commit()
        return None
    if not channel:
        record.insert(
            conn, "utility_run", kind="digest", inputs=json.dumps({"open_item_count": len(items)}, sort_keys=True),
            outputs=json.dumps({"intent_id": None}), process_identity="factory digest", outcome="fail",
            started_at=record.now(), ended_at=record.now(),
        )
        conn.commit()
        raise DigestConfigurationError("digest channel is not configured")

    payload = {
        "channel": channel,
        "cadence_slot": slot,
        "items": items,
        "item_list_hash": canonical.content_hash({"items": items}),
        "text": _text(items),
    }
    intent_id = outbox.create_intent(
        conn, ticket_id=None, operation="digest", payload=payload, runs_dir=runs_dir,
        digest_channel=channel, cadence_slot=slot,
    )
    record.insert(
        conn, "utility_run", kind="digest", inputs=json.dumps({"open_item_count": len(items)}, sort_keys=True),
        outputs=json.dumps({"intent_id": intent_id}), process_identity="factory digest", outcome="pass",
        started_at=record.now(), ended_at=record.now(),
    )
    conn.commit()
    if dispatch and record.get(conn, "external_write", intent_id)["state"] == "pending":
        outbox.dispatch(conn, intent_id, runs_dir=runs_dir)
    return intent_id
