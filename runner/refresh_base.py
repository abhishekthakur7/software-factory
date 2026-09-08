"""`refresh_base`: the human action that rebases a ticket's branch onto a freshly fetched target head.

A ticket a freshness boundary found stale can only move again through this
function, a send-back, or an abandon -- never automatically -- so this is
the one place a moved target branch is actually absorbed. On a clean
rebase, the new base and head are recorded and the ticket returns to
`context` through the `refresh_base` transition, which by itself makes a
new context pass, plan approval, S4 validation and S5 all required again:
nothing here has to enforce that separately. On a conflict the rebase is
aborted rather than resolved -- resolving a conflict is exactly the
judgment call this function must never make on a human's behalf -- and the
ticket escalates instead, carrying the conflicting paths as evidence.
"""
import sqlite3
import subprocess
from pathlib import Path

from runner import freshness, outbox, queue, record, transitions
from runner.paths import RUNS_DIR
from runner.state_table import TABLE


def _git(args: list[str], cwd: Path, *, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-c", "commit.gpgsign=false", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=check,
    )


def _conflicting_paths(worktree: Path) -> list[str]:
    """Paths still unmerged in `worktree`'s interrupted rebase, read before the abort discards that state."""
    result = _git(["diff", "--name-only", "--diff-filter=U"], cwd=worktree)
    return [line for line in result.stdout.splitlines() if line]


def refresh_base(
    conn: sqlite3.Connection,
    ticket_id: int,
    *,
    actor: str,
    note: str | None = None,
    target_branch: str,
    runs_dir: Path = RUNS_DIR,
) -> str:
    """Fetch `target_branch`, rebase the ticket branch onto it, and record or escalate the result.

    Reconciles the ticket's pending external writes first, like every
    other state-advancing command. Refuses before any git call when the
    ticket's current state carries no `refresh_base` row in
    `state_table.TABLE` (`plan_review`, `implementing`, `checks`):
    checking the same table `transitions.apply` would consult anyway, but
    before mutating the worktree, means a call from the wrong state never
    leaves a rebase behind for the exception to strand. `escalate` is a
    valid event from all three of those states, so the conflict path below
    always reaches `escalated` however `refresh_base` was reached.
    """
    outbox.reconcile_pending(conn, ticket_id, runs_dir=runs_dir)
    ticket = record.get(conn, "ticket", ticket_id)
    if ticket is None:
        raise LookupError(f"no such ticket: {ticket_id}")
    if (ticket["state"], "refresh_base") not in TABLE:
        raise transitions.TransitionRefused(
            f"ticket {ticket_id}: no transition for event 'refresh_base' from state {ticket['state']!r}"
        )

    repo = Path(runs_dir) / "tickets" / str(ticket_id) / "repo"
    worktree = Path(ticket["worktree_path"])
    fetched_head = freshness.fetch_target_head(repo, target_branch)

    rebase = _git(["rebase", f"origin/{target_branch}"], cwd=worktree, check=False)
    if rebase.returncode != 0:
        conflicting = _conflicting_paths(worktree)
        _git(["rebase", "--abort"], cwd=worktree)
        summary = f"refresh_base by {actor} conflicts on: {', '.join(conflicting)}"
        if note:
            summary += f" ({note})"
        check_result_id = freshness.record_failure(
            conn, check_name="refresh_base", fetched_target_head=fetched_head, summary=summary,
        )
        transitions.apply(conn, ticket_id, "escalate")
        queue.open_item(conn, ticket_id=ticket_id, kind="escalation", ref=f"check_result:{check_result_id}")
        return f"ticket {ticket_id}: refresh_base conflicts on {', '.join(conflicting)}; escalated"

    new_head = _git(["rev-parse", "HEAD"], cwd=worktree).stdout.strip()
    record.update(
        conn, "ticket", ticket_id,
        base_sha=fetched_head, target_base_sha=fetched_head, head_sha=new_head,
    )
    transitions.apply(conn, ticket_id, "refresh_base")
    return f"ticket {ticket_id}: refresh_base rebased onto {fetched_head}, new head {new_head}"
