"""Build the scheduled attention digest and queue it through the outbox."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta, tzinfo
from pathlib import Path
from typing import Mapping

from runner import canonical, outbox, record
from runner.paths import RUNS_DIR

WEEKDAY_NAMES: tuple[str, ...] = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
DEFAULT_TIMES: tuple[str, ...] = ("10:00", "15:00")
DEFAULT_WEEKDAYS: tuple[str, ...] = WEEKDAY_NAMES[:5]

_SLOT_FORMAT = "%Y-%m-%dT%H:%M"


class DigestConfigurationError(ValueError):
    """The digest channel is missing, or the configured schedule is empty or malformed."""


def _parse_time(value: object) -> tuple[int, int]:
    if not isinstance(value, str) or len(value) != 5 or value[2] != ":":
        raise DigestConfigurationError(f"digest time must be an 'HH:MM' string, found {value!r}")
    try:
        parsed = time.fromisoformat(value)
    except ValueError as exc:
        raise DigestConfigurationError(f"digest time {value!r} is not a time of day") from exc
    return parsed.hour, parsed.minute


def _parse_weekday(value: object) -> int:
    """The index of a configured weekday name, counting Monday as 0.

    Weekdays are named, never numbered: every numbering in reach counts
    from a different day (Python from Monday, launchd and Slack from
    Sunday), so a bare number in the file would be ambiguous to whoever
    edits it next.
    """
    if not isinstance(value, str) or value.strip().lower() not in WEEKDAY_NAMES:
        raise DigestConfigurationError(f"digest weekday must be one of {', '.join(WEEKDAY_NAMES)}, found {value!r}")
    return WEEKDAY_NAMES.index(value.strip().lower())


@dataclass(frozen=True)
class Schedule:
    """The occurrences a digest run serves: times of day on weekdays, read in one local zone.

    `times` holds `(hour, minute)` pairs and `weekdays` holds indices
    counting Monday as 0, both ascending and without duplicates so the
    same configuration always produces the same occurrence order. `zone`
    of `None` means this host's own zone, which is the zone the installed
    scheduler entry fires against.
    """

    times: tuple[tuple[int, int], ...]
    weekdays: tuple[int, ...]
    zone: tzinfo | None = None

    @classmethod
    def from_config(cls, config: Mapping | None, *, zone: tzinfo | None = None) -> "Schedule":
        """The schedule under a `digest` configuration mapping, defaulting to twice a working day.

        An absent or null `times`/`weekdays` takes the default; an empty
        list is refused rather than defaulted, because an engineer who
        wrote `times: []` asked for no digest at all and the scheduler
        must not silently install one anyway.
        """
        settings = config or {}
        raw_times = settings.get("times")
        raw_weekdays = settings.get("weekdays")
        raw_times = DEFAULT_TIMES if raw_times is None else raw_times
        raw_weekdays = DEFAULT_WEEKDAYS if raw_weekdays is None else raw_weekdays
        for name, raw in (("times", raw_times), ("weekdays", raw_weekdays)):
            if not isinstance(raw, (list, tuple)) or not raw:
                raise DigestConfigurationError(f"digest {name} must be a non-empty list, found {raw!r}")
        return cls(
            times=tuple(sorted({_parse_time(value) for value in raw_times})),
            weekdays=tuple(sorted({_parse_weekday(value) for value in raw_weekdays})),
            zone=zone,
        )

    def occurrence(self, now: datetime) -> datetime:
        """The most recent scheduled occurrence at or before `now`, as an instant.

        The configured times are wall-clock times in the engineer's own
        day, so the search runs against `now` converted to the schedule's
        zone and compares calendar fields rather than instants: that way
        a daylight-saving shift moves the occurrence's instant without
        moving which occurrence a run is serving.
        """
        local = now.astimezone(self.zone).replace(tzinfo=None)
        for days_back in range(8):
            day = (local - timedelta(days=days_back)).date()
            if day.weekday() not in self.weekdays:
                continue
            for hour, minute in reversed(self.times):
                candidate = datetime.combine(day, time(hour, minute))
                if candidate <= local:
                    # A naive local time converts through the host's own
                    # zone when the schedule names none.
                    return candidate.replace(tzinfo=self.zone) if self.zone else candidate.astimezone()
        # Unreachable while `weekdays` is non-empty, which parsing guarantees:
        # eight days back always covers a full week, and every time of day on a
        # day before today lies in the past. It fails closed rather than
        # inventing a slot, so a future parsing change cannot silently produce
        # digests under a key that names no scheduled occurrence.
        raise DigestConfigurationError("digest schedule names no occurrence in the week before this run")

    @staticmethod
    def slot_id(occurrence: datetime) -> str:
        """The identifier of one occurrence, whose stability makes a retry within it idempotent.

        Naming the occurrence by its local date and time, not by the
        instant, keeps two runs of one occurrence on a single key even
        when they fall either side of a UTC date boundary.
        """
        return occurrence.strftime(_SLOT_FORMAT)


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
    schedule: Schedule,
    now: datetime | None = None,
    runs_dir: Path = RUNS_DIR,
    dispatch: bool = True,
) -> int | None:
    """Record one digest utility run and, when there is work, create and dispatch its one outbox intent.

    The run serves the scheduled occurrence `now` falls in, and every age
    it reports is measured from that occurrence rather than from the
    moment of the run, so a retry inside one occurrence rebuilds the same
    item list under the same key instead of a second intent.
    """
    instant = now or datetime.now(UTC)
    occurrence = schedule.occurrence(instant)
    slot = Schedule.slot_id(occurrence)
    items = open_items(conn, now=occurrence)
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
        "schedule_slot": slot,
        "items": items,
        "item_list_hash": canonical.content_hash({"items": items}),
        "text": _text(items),
    }
    intent_id = outbox.create_intent(
        conn, ticket_id=None, operation="digest", payload=payload, runs_dir=runs_dir,
        digest_channel=channel, schedule_slot=slot,
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
