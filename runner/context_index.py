"""The context index: `factory/index/*.md` entries, their staleness at read time, and the record of every read.

An entry is a Markdown file with front matter carrying the six required
keys. Staleness is never stored on the entry: it is computed each time a
stage reads the index, from `last_verified` against today and against
the base branch's commits touching the entry's `paths`, so a fresh commit
makes an entry stale with no edit to the index. `record_reads` is the one
writer of `index_use` and of the `stale_index` tag a stale read earns, so
a stage driver records what it read in one call and the tag's failure
mode lives in exactly one place. An empty index is a valid index: the
reading stage records no rows and says "no entries".
"""
import sqlite3
import subprocess
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

import yaml

from runner import record, tags
from runner.definitions import DefinitionError, front_matter
from runner.paths import FACTORY_DIR

INDEX_DIR = FACTORY_DIR / "index"
LIMITS_PATH = FACTORY_DIR / "config" / "limits.yaml"
REQUIRED_KEYS: tuple[str, ...] = ("kind", "source", "owner", "last_verified", "staleness_rule", "paths")
STALE_INDEX_FM = "memory_rot"


class ContextIndexError(ValueError):
    """An entry is missing a required front-matter key or carries one of the wrong shape."""


@dataclass(frozen=True)
class Entry:
    path: Path
    kind: str
    source: str
    owner: str
    last_verified: str | None
    staleness_rule: object
    paths: tuple[str, ...]
    body: str


@dataclass(frozen=True)
class Read:
    entry: Entry
    stale_reason: str | None

    @property
    def stale(self) -> bool:
        return self.stale_reason is not None


def _entry(path: Path) -> Entry:
    try:
        meta, body = front_matter(path.read_text(), path=path)
    except DefinitionError as exc:
        raise ContextIndexError(str(exc)) from exc
    missing = [key for key in REQUIRED_KEYS if key not in meta]
    if missing:
        raise ContextIndexError(f"{path}: front matter missing {missing}")
    paths = meta["paths"]
    if not isinstance(paths, list) or not all(isinstance(item, str) for item in paths):
        raise ContextIndexError(f"{path}: paths must be a list of strings")
    last_verified = meta["last_verified"]
    if isinstance(last_verified, (date, datetime)):
        last_verified = last_verified.isoformat()
    return Entry(
        path=path, kind=str(meta["kind"]), source=str(meta["source"]), owner=str(meta["owner"]),
        last_verified=str(last_verified) if last_verified is not None else None,
        staleness_rule=meta["staleness_rule"], paths=tuple(paths), body=body,
    )


def load_entries(index_dir: Path = INDEX_DIR) -> tuple[Entry, ...]:
    """Every entry under `index_dir`, sorted by file name; a missing or empty directory holds none."""
    if not Path(index_dir).is_dir():
        return ()
    return tuple(_entry(path) for path in sorted(Path(index_dir).glob("*.md")))


def default_max_days(limits_path: Path = LIMITS_PATH) -> int:
    return int(yaml.safe_load(Path(limits_path).read_text())["index_staleness"]["days"])


def _parse_date(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def _commits_touching(checkout: Path, branch: str, since: str, paths: tuple[str, ...]) -> list[str]:
    if not paths:
        return []
    result = subprocess.run(
        ["git", "log", f"--since={since}", "--format=%H", branch, "--", *paths],
        cwd=checkout, capture_output=True, text=True,
    )
    if result.returncode != 0:
        return []
    return [line for line in result.stdout.splitlines() if line.strip()]


def stale_reason(
    entry: Entry, *, now: str | None = None, checkout: Path | None = None, target_branch: str | None = None,
    max_days: int | None = None,
) -> str | None:
    """Why `entry` is stale at read time, or None while it is fresh.

    The rule is the section-8 default -- `max_days` since `last_verified`,
    or any commit on `target_branch` touching the entry's `paths` since
    then -- unless the entry's own `staleness_rule` is a mapping carrying
    `days`, which replaces the day count alone. An entry with no
    `last_verified` is stale whatever its rule says, since there is no
    date to measure from. The commit check runs only when a checkout and
    branch are given; a caller without one gets the date rule alone.
    """
    if entry.last_verified is None:
        return "no last_verified"
    limit = max_days if max_days is not None else default_max_days()
    if isinstance(entry.staleness_rule, dict) and "days" in entry.staleness_rule:
        limit = int(entry.staleness_rule["days"])
    verified_at = _parse_date(entry.last_verified)
    current = _parse_date(now) if now is not None else datetime.now(timezone.utc)
    age = (current - verified_at).days
    if age > limit:
        return f"{age} days since last_verified, over the {limit}-day rule"
    if checkout is not None and target_branch is not None:
        commits = _commits_touching(Path(checkout), target_branch, entry.last_verified, entry.paths)
        if commits:
            return f"base branch commit {commits[0][:12]} touched {', '.join(entry.paths)} since last_verified"
    return None


def record_reads(
    conn: sqlite3.Connection, *, stage_run_id: int, entries, now: str | None = None, checkout: Path | None = None,
    target_branch: str | None = None, actor: str = tags.MECHANICAL_ACTOR,
) -> tuple[Read, ...]:
    """Write one `index_use` row per entry read by `stage_run_id`, tagging each stale read `stale_index`."""
    reads: list[Read] = []
    for entry in entries:
        reason = stale_reason(entry, now=now, checkout=checkout, target_branch=target_branch)
        record.insert(
            conn, "index_use", stage_run_id=stage_run_id, entry_path=str(entry.path),
            entry_last_verified=entry.last_verified, stale=1 if reason else 0,
        )
        if reason:
            tags.tag(
                conn, target=f"stage_run:{stage_run_id}", kind="stale_index", fm_id=STALE_INDEX_FM, actor=actor,
                note=f"{entry.path.name}: {reason}",
            )
        reads.append(Read(entry=entry, stale_reason=reason))
    return tuple(reads)
