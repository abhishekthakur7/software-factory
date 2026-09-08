"""Base freshness: one trusted fetch-and-compare, checked at three boundaries.

`fetch_target_head` is the one place this module reaches the network (or,
in a test, another local repository): it fetches the ticket's own clone
against the project's configured target branch and returns the fetched
tip, never a cached or locally-reasoned value. `check` is the one function
every boundary calls; `boundary` only widens what is compared -- every
boundary requires the fetched head to match the latest plan tuple's
`base_sha` and the ticket's recorded `target_base_sha`, `S5_PREFLIGHT`
additionally requires the worktree's actual HEAD to still be
`ticket.head_sha` and, when it is, that head's diff against the plan
tuple's base to hash to the latest review tuple's `diff_hash` (or, absent
a review tuple yet, simply records the computed hash for the caller to
bind), and `BEFORE_DISPATCH` additionally requires the pending
pull-request intent's branch and subject identity to still match the
ticket and its latest review tuple.

A stale result is never only an in-memory flag: `check` writes one
`check_result` row naming the plan (and, once one exists, review) tuple it
invalidates, so `invalidated_tuples` can later read back exactly which
tuples a gate or preflight must refuse to build on, from the record
itself rather than from a value that only lived in the call that found
the staleness. A fresh result writes nothing -- there is nothing to
invalidate.
"""
import sqlite3
import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml

from runner import canonical, record
from runner.paths import PROJECT_CONFIG, RUNS_DIR

BEFORE_S4 = "before_s4"
S5_PREFLIGHT = "s5_preflight"
BEFORE_DISPATCH = "before_dispatch"

BOUNDARIES: tuple[str, ...] = (BEFORE_S4, S5_PREFLIGHT, BEFORE_DISPATCH)

# The pull-request operations a `BEFORE_DISPATCH` check looks for among the
# ticket's `external_write` rows; mirrors `outbox.PR_OPERATIONS` without
# importing `outbox`, which would make a check module depend on the worker
# that calls it.
_PR_OPERATIONS: tuple[str, ...] = ("pr_create", "pr_update")


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-c", "commit.gpgsign=false", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )


def target_branch(project_path: Path = PROJECT_CONFIG) -> str:
    """The configured target branch every boundary fetches and compares against."""
    return yaml.safe_load(Path(project_path).read_text())["target_branch"]


def fetch_target_head(repo: Path, target_branch: str) -> str:
    """Fetch `target_branch` from `origin` inside the ticket's clone `repo` and return its fetched tip."""
    _git(["fetch", "-q", "origin", target_branch], cwd=repo)
    return _git(["rev-parse", f"origin/{target_branch}"], cwd=repo).stdout.strip()


@dataclass(frozen=True)
class Freshness:
    fresh: bool
    boundary: str
    fetched_target_head: str
    reasons: tuple[str, ...] = ()
    # Only ever set at `S5_PREFLIGHT`, and only when the worktree head still
    # matches: the diff hash the caller can bind onto a new review tuple,
    # computed once here rather than re-diffed by every caller.
    diff_hash: str | None = None
    # The `check_result` row id a stale result wrote, or None on a fresh one.
    check_result_id: int | None = None


def _latest_tuple(conn: sqlite3.Connection, ticket_id: int, kind: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM evidence_tuple WHERE ticket_id = ? AND kind = ? ORDER BY id DESC LIMIT 1",
        (ticket_id, kind),
    ).fetchone()


def _latest_pending_pr_intent(conn: sqlite3.Connection, ticket_id: int) -> sqlite3.Row | None:
    placeholders = ", ".join("?" for _ in _PR_OPERATIONS)
    return conn.execute(
        f"SELECT * FROM external_write WHERE ticket_id = ? AND state = 'pending' "
        f"AND operation IN ({placeholders}) ORDER BY id DESC LIMIT 1",
        (ticket_id, *_PR_OPERATIONS),
    ).fetchone()


def record_failure(
    conn: sqlite3.Connection,
    *,
    check_name: str,
    fetched_target_head: str,
    summary: str,
    plan_tuple_id: int | None = None,
    review_tuple_id: int | None = None,
) -> int:
    """Insert one blocking, failed runner `check_result` for a base-related refusal and return its id.

    The plan and review tuple ids name the evidence the failure
    invalidates; a refusal that invalidates nothing (a rebase conflict)
    leaves both null and is found by its `check_name` alone.
    """
    row = {
        "stage_run_id": None,
        "check_name": check_name,
        "check_tier": "blocking",
        "evidence_tuple_id": review_tuple_id,
        "plan_tuple_id": plan_tuple_id,
        "source": "runner",
        "result": "fail",
        "observed_target_base_sha": fetched_target_head,
        "summary": summary,
        "canonical_serialization_version": canonical.SERIALIZATION_VERSION,
    }
    row["content_hash"] = canonical.content_hash(row)
    return record.insert(conn, "check_result", **row)


def check(
    conn: sqlite3.Connection,
    ticket_id: int,
    *,
    boundary: str,
    target_branch: str,
    runs_dir: Path = RUNS_DIR,
) -> Freshness:
    """The trusted fetch-and-compare at one of `BOUNDARIES`.

    Raises `LookupError` for an unknown ticket and `ValueError` for an
    unknown `boundary`; every other refusal is expressed in the returned
    `Freshness.reasons`, since a stale base is data for the caller to
    route on, not an exceptional condition.
    """
    if boundary not in BOUNDARIES:
        raise ValueError(f"unknown freshness boundary: {boundary!r}")
    ticket = record.get(conn, "ticket", ticket_id)
    if ticket is None:
        raise LookupError(f"no such ticket: {ticket_id}")

    repo = Path(runs_dir) / "tickets" / str(ticket_id) / "repo"
    fetched = fetch_target_head(repo, target_branch)

    plan_tuple = _latest_tuple(conn, ticket_id, "plan")
    review_tuple = _latest_tuple(conn, ticket_id, "review")

    reasons: list[str] = []
    if plan_tuple is None:
        reasons.append("no plan tuple is recorded for this ticket")
    elif fetched != plan_tuple["base_sha"]:
        reasons.append(f"fetched target head {fetched} does not equal plan tuple base_sha {plan_tuple['base_sha']}")
    if fetched != ticket["target_base_sha"]:
        reasons.append(
            f"fetched target head {fetched} does not equal ticket target_base_sha {ticket['target_base_sha']}"
        )

    diff_hash = None
    if boundary == S5_PREFLIGHT:
        worktree = Path(ticket["worktree_path"])
        actual_head = _git(["rev-parse", "HEAD"], cwd=worktree).stdout.strip()
        if actual_head != ticket["head_sha"]:
            reasons.append(f"worktree head {actual_head} has moved past ticket head_sha {ticket['head_sha']}")
        else:
            base_sha = plan_tuple["base_sha"] if plan_tuple is not None else ticket["base_sha"]
            diff_text = _git(["diff", base_sha, actual_head], cwd=worktree).stdout
            diff_hash = canonical.content_hash({"diff": diff_text})
            if review_tuple is not None and diff_hash != review_tuple["diff_hash"]:
                reasons.append(
                    f"candidate diff hash {diff_hash} does not equal bound review tuple diff_hash "
                    f"{review_tuple['diff_hash']}"
                )

    if boundary == BEFORE_DISPATCH:
        intent = _latest_pending_pr_intent(conn, ticket_id)
        if intent is None:
            reasons.append("no pending pull-request intent to check")
        else:
            if intent["head_ref"] != ticket["branch"]:
                reasons.append(f"intent head_ref {intent['head_ref']} does not equal ticket branch {ticket['branch']}")
            if intent["desired_remote_head_sha"] != ticket["head_sha"]:
                reasons.append(
                    f"intent desired_remote_head_sha {intent['desired_remote_head_sha']} "
                    f"does not equal ticket head_sha {ticket['head_sha']}"
                )
            if review_tuple is None or intent["review_approval_subject_hash"] != review_tuple["content_hash"]:
                reasons.append("intent review_approval_subject_hash does not equal the latest review tuple")

    fresh = not reasons
    check_result_id = None
    if not fresh:
        check_result_id = record_failure(
            conn, check_name="freshness", fetched_target_head=fetched, summary="; ".join(reasons),
            plan_tuple_id=plan_tuple["id"] if plan_tuple is not None else None,
            review_tuple_id=review_tuple["id"] if review_tuple is not None else None,
        )

    return Freshness(
        fresh=fresh, boundary=boundary, fetched_target_head=fetched,
        reasons=tuple(reasons), diff_hash=diff_hash, check_result_id=check_result_id,
    )


def invalidated_tuples(conn: sqlite3.Connection, ticket_id: int) -> set[int]:
    """Every plan/review `evidence_tuple` id a recorded freshness failure named for `ticket_id`.

    Joins through `evidence_tuple.ticket_id` rather than reading a
    `ticket_id` off `check_result` itself, since a freshness row names its
    ticket only indirectly, through whichever tuple(s) it invalidates.
    """
    rows = conn.execute(
        "SELECT cr.plan_tuple_id, cr.evidence_tuple_id FROM check_result cr "
        "LEFT JOIN evidence_tuple pt ON pt.id = cr.plan_tuple_id "
        "LEFT JOIN evidence_tuple et ON et.id = cr.evidence_tuple_id "
        "WHERE cr.check_name = 'freshness' AND cr.result = 'fail' AND (pt.ticket_id = ? OR et.ticket_id = ?)",
        (ticket_id, ticket_id),
    ).fetchall()
    ids: set[int] = set()
    for row in rows:
        if row["plan_tuple_id"] is not None:
            ids.add(row["plan_tuple_id"])
        if row["evidence_tuple_id"] is not None:
            ids.add(row["evidence_tuple_id"])
    return ids
