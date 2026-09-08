"""The ticket's isolated git trees: clone, worktree, plain checkouts, copies.

Every write here is a git or filesystem-copy subprocess/call, not a Python
`open()`, so none of it needs to route through `runner/fs.py`; the sole
`record` interaction is the pair of `record.update` calls that pin
`base_sha`/`target_base_sha`/`branch`/`worktree_path` and, later,
`head_sha` onto the ticket row.

A cloned repository's push URL is set to an unusable literal rather than
left pointing at the source checkout: the sandbox that runs inside the
ticket worktree must have no way to push, even if it somehow obtained
network access, so the refusal is baked into the git remote configuration
itself rather than relying only on the OS network policy.
"""
import os
import sqlite3
import subprocess
from dataclasses import dataclass
from pathlib import Path

from runner import fs, record
from runner.paths import RUNS_DIR

# Not a resolvable transport: git refuses any push through it, whatever the
# sandbox's network policy does or doesn't allow.
DISABLED_PUSH_URL = "no-push://ticket-clone-disabled"

# The hand-back commit's fixed identity: the trusted runner made this
# commit, not any individual agent invocation or human, so it never
# carries an actor's own name.
_COMMIT_AUTHOR_NAME = "soft-factory runner"
_COMMIT_AUTHOR_EMAIL = "runner@soft-factory.invalid"


def _git(args: list[str], cwd: Path, env: dict | None = None) -> subprocess.CompletedProcess:
    full_env = {**os.environ, **env} if env else None
    return subprocess.run(
        ["git", "-c", "commit.gpgsign=false", *args],
        cwd=cwd,
        env=full_env,
        capture_output=True,
        text=True,
        check=True,
    )


def _rev_parse(cwd: Path, ref: str = "HEAD") -> str:
    return _git(["rev-parse", ref], cwd=cwd).stdout.strip()


@dataclass(frozen=True)
class TicketTrees:
    repo: Path
    worktree: Path
    branch: str
    base_sha: str


def clone_for_ticket(
    conn: sqlite3.Connection,
    ticket_id: int,
    *,
    source_checkout: Path,
    target_branch: str,
    runs_dir: Path = RUNS_DIR,
) -> TicketTrees:
    """Clone `source_checkout` and give the ticket its own branch and worktree.

    The clone lives at `runs/tickets/<id>/repo`; the worktree for the
    ticket's own branch, checked out from that clone's `target_branch` tip,
    lives at `runs/tickets/<id>/worktree`. `base_sha` and `target_base_sha`
    are recorded as the same value: the tip this ticket branched from.
    """
    ticket_root = Path(runs_dir) / "tickets" / str(ticket_id)
    repo_dir = ticket_root / "repo"
    worktree_dir = ticket_root / "worktree"
    branch = f"ticket/{ticket_id}"

    ticket_root.mkdir(parents=True, exist_ok=True)
    _git(["clone", "-q", str(source_checkout), str(repo_dir)], cwd=ticket_root)
    _git(["checkout", "-q", target_branch], cwd=repo_dir)
    _git(["remote", "set-url", "--push", "origin", DISABLED_PUSH_URL], cwd=repo_dir)
    base_sha = _rev_parse(repo_dir, target_branch)

    _git(["worktree", "add", "-q", "-b", branch, str(worktree_dir), base_sha], cwd=repo_dir)

    record.update(
        conn,
        "ticket",
        ticket_id,
        base_sha=base_sha,
        target_base_sha=base_sha,
        branch=branch,
        worktree_path=str(worktree_dir),
    )
    return TicketTrees(repo=repo_dir, worktree=worktree_dir, branch=branch, base_sha=base_sha)


def record_head(conn: sqlite3.Connection, ticket_id: int, worktree: Path) -> str:
    """Read `worktree`'s current HEAD into `ticket.head_sha` and return it."""
    head_sha = _rev_parse(Path(worktree))
    record.update(conn, "ticket", ticket_id, head_sha=head_sha)
    return head_sha


def commit_worktree(worktree: Path, message: str) -> str:
    """Commit every change in `worktree` under the runner's fixed identity; return the resulting HEAD.

    The agent that ran inside the ticket worktree never runs git itself --
    the hand-off contract leaves committing to the trusted runner, under
    an identity that names the runner rather than whichever invocation or
    human produced the edits. A task may legitimately change nothing (its
    deviation set says so), so an empty status is not an error: `HEAD`
    stays exactly where it was and is returned unchanged.
    """
    worktree = Path(worktree)
    _git(["add", "-A"], cwd=worktree)
    status = _git(["status", "--porcelain"], cwd=worktree)
    if not status.stdout.strip():
        return _rev_parse(worktree)
    commit_env = {
        "GIT_AUTHOR_NAME": _COMMIT_AUTHOR_NAME, "GIT_AUTHOR_EMAIL": _COMMIT_AUTHOR_EMAIL,
        "GIT_COMMITTER_NAME": _COMMIT_AUTHOR_NAME, "GIT_COMMITTER_EMAIL": _COMMIT_AUTHOR_EMAIL,
    }
    _git(["commit", "-q", "-m", message], cwd=worktree, env=commit_env)
    return _rev_parse(worktree)


def plain_checkout(source_checkout: Path, sha: str, dest: Path) -> Path:
    """An independent checkout of `sha`, usable without the ticket worktree.

    A full clone rather than a linked `git worktree`: the base and head
    checkouts must stay usable, and safely deletable, after the ticket
    worktree and its clone are gone, so they cannot share object storage
    with either.
    """
    Path(dest).parent.mkdir(parents=True, exist_ok=True)
    _git(["clone", "-q", str(source_checkout), str(dest)], cwd=Path(dest).parent)
    _git(["checkout", "-q", sha], cwd=dest)
    return Path(dest)


def throwaway_copy(checkout: Path, dest: Path) -> Path:
    """A filesystem copy of `checkout` a check may freely write into."""
    fs.copy_tree(Path(checkout), Path(dest))
    return Path(dest)
