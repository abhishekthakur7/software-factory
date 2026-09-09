"""The parallel-ticket limit: how many tickets may be past `intake` at once, and the wait line for one held there.

`effective_parallel_limit` reads the configured limit and, above one,
looks for a current `approval_record` on the `graduation` gate that raises
it: the record must come from the `factory_owner` identity, be unexpired,
and name the exact configuration file the limit came from. Even then the
raise only holds while both the bound configuration hash still matches the
file's current bytes and the bound report still reports a pass under the
current manifest hash -- an editor who bumps the number by hand, or whose
approved report has gone stale under either kind of drift, gets the same
refusal as never having asked at all, just with a reason attached instead
of silence. `in_flight` and `wait` are the read side `factory advance`,
`factory queue` and `factory show` share, so the three surfaces can never
disagree about who is waiting or why.
"""
import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import yaml

from runner import manifest, owners, record
from runner.paths import FACTORY_DIR

LIMITS_PATH = FACTORY_DIR / "config" / "limits.yaml"

# The states a ticket occupies while it holds a slot: every state between
# `intake` and a pull request being opened, plus `escalated` since an
# escalation is still open work, not a wait. `intake`, `pr_opened`, and
# every terminal state hold no slot.
COUNTED_STATES = (
    "context",
    "clarifying",
    "planning",
    "plan_review",
    "implementing",
    "checks",
    "review",
    "escalated",
)

UNSIGNED_EDIT = "unsigned_edit"
STALE_REPORT = "stale_report"

# The literal path a graduation approval's `scope` names to bind it to
# this configuration file, independent of where a caller's own
# `limits_path` argument happens to point (a test's temporary copy, for
# instance): the bound path is what the approval is *about*, the hash
# beside it is what makes that binding stale or current.
CONFIG_PATH = "factory/config/limits.yaml"


@dataclass(frozen=True)
class Limit:
    limit: int
    reason: str | None = None


def _latest_graduation_approval(
    conn: sqlite3.Connection, *, owner_identity: str, now: str,
) -> sqlite3.Row | None:
    """The most recent unexpired `approval_record` naming this configuration, from the factory owner -- else None."""
    rows = conn.execute(
        "SELECT * FROM approval_record WHERE gate = 'graduation' AND decision = 'approve' "
        "AND role = 'factory_owner' AND actor_identity = ? ORDER BY id DESC",
        (owner_identity,),
    ).fetchall()
    for row in rows:
        if row["expires_at"] is not None and row["expires_at"] <= now:
            continue
        scope = json.loads(row["scope"] or "{}")
        if scope.get("config_path") != CONFIG_PATH:
            continue
        return row
    return None


def effective_parallel_limit(
    conn: sqlite3.Connection,
    *,
    limits_path: Path = LIMITS_PATH,
    manifest_hash: str | None = None,
    now: str | None = None,
    owners_path: Path = owners.DEFAULT_OWNERS_PATH,
) -> Limit:
    """The parallel-ticket limit in force right now, paired with why it is held at one, if it is."""
    configured = int((yaml.safe_load(Path(limits_path).read_text()) or {}).get("parallel_tickets", 1))
    if configured <= 1:
        return Limit(1, None)

    owner_identity = owners.load_owners(owners_path).roles["factory_owner"]["identity"]
    approval = _latest_graduation_approval(conn, owner_identity=owner_identity, now=now or record.now())
    if approval is None:
        return Limit(1, UNSIGNED_EDIT)

    scope = json.loads(approval["scope"])
    current_config_hash = hashlib.sha256(Path(limits_path).read_bytes()).hexdigest()
    if scope.get("config_hash") != current_config_hash:
        return Limit(1, STALE_REPORT)

    evidence_ids = json.loads(approval["evidence_ids"] or "[]")
    report_artefact = record.get(conn, "artefact", evidence_ids[0]) if evidence_ids else None
    if report_artefact is None:
        return Limit(1, STALE_REPORT)
    report = json.loads(Path(report_artefact["path"]).read_text())

    current_manifest_hash = manifest_hash if manifest_hash is not None else manifest.current_hash()
    if report.get("passed") is not True or report.get("manifest_hash") != current_manifest_hash:
        return Limit(1, STALE_REPORT)

    return Limit(configured, None)


def in_flight(conn: sqlite3.Connection, *, excluding: int | None = None) -> int:
    """How many tickets currently hold a slot (see `COUNTED_STATES`), a pre-factory baseline ticket never among them."""
    placeholders = ", ".join("?" for _ in COUNTED_STATES)
    query = f"SELECT COUNT(*) AS n FROM ticket WHERE state IN ({placeholders}) AND baseline IS NOT 1"
    params: list = list(COUNTED_STATES)
    if excluding is not None:
        query += " AND id != ?"
        params.append(excluding)
    return conn.execute(query, params).fetchone()["n"]


def wait(conn: sqlite3.Connection, ticket: sqlite3.Row, limit: Limit) -> str | None:
    """The capacity-wait line for `ticket`, or None when it is not a held-at-`intake` ticket or there is room.

    Only a ticket actually sitting at `intake` with nothing else already
    blocking it (`blocked_on` null) can be held here -- a ticket blocked on
    a queue item is already accounted for by that item, and one already
    past `intake` no longer needs a slot to be checked for.
    """
    if ticket["state"] != "intake" or ticket["blocked_on"] is not None:
        return None
    count = in_flight(conn, excluding=ticket["id"])
    if count < limit.limit:
        return None
    line = f"capacity wait: {count} of {limit.limit} tickets in flight"
    if limit.reason is not None:
        line += f" (limit held at 1: {limit.reason})"
    return line
