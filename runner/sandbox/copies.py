"""Copy-on-write base/head checkouts a build step writes into, never the immutable checkouts themselves.

`provision` clones each of `git_trees.plain_checkout`'s immutable
checkouts with `cp -c -R` -- an APFS clonefile, roughly constant time
regardless of tree size -- into this stage run's own `copies/<id>/`
directory, with the disposable build/scratch/cache directories created
empty alongside. `dispose` removes that whole directory; `provisioned`
disposes on every exit path, including a caller that raises mid-run, so a
crashed build step never leaves a stale copy behind.
"""
import subprocess
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from runner import fs
from runner.paths import RUNS_DIR

DEFAULT_DISPOSABLE: tuple[str, ...] = ("target", "scratch", "cache")


class CopyError(Exception):
    """An APFS clone could not be made."""


@dataclass(frozen=True)
class Copies:
    root: Path
    base: Path
    head: Path
    disposable: tuple[str, ...]


def _clone(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(["cp", "-c", "-R", str(src), str(dst)], capture_output=True, text=True)
    if result.returncode != 0:
        raise CopyError(f"cp -c -R {src} {dst} failed: {result.stderr.strip()}")


def provision(
    *, ticket_id: int, stage_run_id: int, base_checkout: Path, head_checkout: Path,
    runs_dir: Path = RUNS_DIR, disposable: tuple[str, ...] = DEFAULT_DISPOSABLE,
) -> Copies:
    """Clone `base_checkout` and `head_checkout` into this run's own copies directory, with empty disposables."""
    root = Path(runs_dir) / "tickets" / str(ticket_id) / "copies" / str(stage_run_id)
    base = root / "base"
    head = root / "head"
    if root.exists():
        fs.remove_tree(root)
    try:
        _clone(Path(base_checkout), base)
        _clone(Path(head_checkout), head)
        for checkout_dir in (base, head):
            for name in disposable:
                (checkout_dir / name).mkdir(parents=True)
    except Exception:
        # A failed second clone can leave a writable first copy. Remove the
        # whole run-local root before reporting failure so it cannot be reused.
        if root.exists():
            fs.remove_tree(root)
        raise
    return Copies(root=root, base=base, head=head, disposable=tuple(disposable))


def dispose(copies: Copies) -> None:
    """Remove the whole `copies/<stage_run_id>` directory; a no-op when it is already gone."""
    if copies.root.exists():
        fs.remove_tree(copies.root)


def recheck(checkout: Path, expected_sha: str) -> bool:
    """Whether `checkout` is still exactly `expected_sha` with no uncommitted change -- false on either drift."""
    checkout = Path(checkout)
    rev = subprocess.run(["git", "rev-parse", "HEAD"], cwd=checkout, capture_output=True, text=True)
    if rev.returncode != 0 or rev.stdout.strip() != expected_sha:
        return False
    status = subprocess.run(["git", "status", "--porcelain"], cwd=checkout, capture_output=True, text=True)
    return status.returncode == 0 and not status.stdout.strip()


@contextmanager
def provisioned(
    *, ticket_id: int, stage_run_id: int, base_checkout: Path, head_checkout: Path,
    runs_dir: Path = RUNS_DIR, disposable: tuple[str, ...] = DEFAULT_DISPOSABLE,
) -> Iterator[Copies]:
    """`provision`, yield the result, `dispose` it in `finally` -- including when the caller raises mid-run."""
    copies = provision(
        ticket_id=ticket_id, stage_run_id=stage_run_id, base_checkout=base_checkout, head_checkout=head_checkout,
        runs_dir=runs_dir, disposable=disposable,
    )
    try:
        yield copies
    finally:
        dispose(copies)
