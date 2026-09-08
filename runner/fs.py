"""The only module in `runner/` allowed to open a path for writing.

Every other module must go through `write_text`/`write_bytes`/`copy_tree`
here, which refuse a target resolving inside `FACTORY_DIR`.
`test_write_barrier.py` enforces the "only module" half by scanning every
other module under `runner/` for a raw write primitive; this module is the
one place that scan skips.
"""
import shutil
from pathlib import Path

from runner.paths import FACTORY_DIR


class FactoryWriteRefused(Exception):
    """Raised when a write target resolves inside the read-only factory/ tree."""


def _check(path: Path) -> Path:
    resolved = Path(path).resolve()
    # FACTORY_DIR may not exist yet in a fresh checkout; resolve() still
    # normalizes it, and is_relative_to needs no filesystem access either way.
    if resolved.is_relative_to(FACTORY_DIR.resolve()):
        raise FactoryWriteRefused(f"refusing to write inside factory/: {resolved}")
    return resolved


def write_text(path: Path, text: str) -> None:
    resolved = _check(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(text)


def write_bytes(path: Path, data: bytes) -> None:
    resolved = _check(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_bytes(data)


def copy_tree(src: Path, dst: Path) -> None:
    """Copy the directory tree `src` to `dst`, refusing a `dst` inside `factory/`.

    `dst` must not already exist -- `shutil.copytree`'s own rule -- so a
    caller that wants to replace a prior copy removes it first rather than
    relying on this function to merge into a live tree.
    """
    resolved = _check(dst)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, resolved)


def remove_tree(path: Path) -> None:
    """Delete the directory `path` and everything under it; refuses a target inside `factory/`."""
    shutil.rmtree(_check(path))
