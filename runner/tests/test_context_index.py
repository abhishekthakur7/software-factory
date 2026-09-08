"""The context index: front matter, the staleness rule, and `index_use`/`stale_index` recording.

`stale_reason` tests pass an explicit `now` so the assertions never depend
on the wall-clock date the suite happens to run on; only the tests that pin
the three real committed entries' own content read `factory/index/`
directly.
"""
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from runner import context_index, record, run_ledger
from runner.db import connect
from runner.paths import FACTORY_DIR

REAL_INDEX_DIR = FACTORY_DIR / "index"
FIXTURES_DIR = Path(__file__).parent / "fixtures" / "context_index"

_COMMIT_ENV = {
    "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@example.invalid",
}


def _git(args, cwd, env=None):
    full_env = {**os.environ, **env} if env else None
    return subprocess.run(
        ["git", "-c", "commit.gpgsign=false", *args], cwd=cwd, env=full_env,
        capture_output=True, text=True, check=True,
    )


def _commit(repo, *, message, date, touch=None):
    if touch:
        (repo / touch).write_text(f"{message}\n")
    _git(["add", "-A"], cwd=repo)
    env = {**_COMMIT_ENV, "GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date}
    _git(["commit", "-q", "-m", message, "--allow-empty"], cwd=repo, env=env)


@pytest.fixture
def conn(tmp_path):
    connection = connect(tmp_path / "factory.sqlite")
    yield connection
    connection.close()


# the three real committed entries


def test_the_conventions_entry_carries_the_six_required_front_matter_keys():
    """R-F-6: every entry's front matter carries kind, source, owner,
    last_verified, staleness_rule, paths."""
    entries = {e.path.stem: e for e in context_index.load_entries(REAL_INDEX_DIR)}
    conventions = entries["conventions"]
    assert conventions.kind == "convention"
    assert conventions.source and conventions.owner
    assert conventions.last_verified == "2026-09-08"
    assert conventions.staleness_rule == "default"
    assert conventions.paths


def test_the_index_carries_exactly_three_hand_written_entries_at_this_stage():
    """R-F-6: conventions, sensitive-paths, and one caller entry -- no more, no fewer."""
    entries = context_index.load_entries(REAL_INDEX_DIR)
    assert {e.path.stem for e in entries} == {"conventions", "sensitive-paths", "callers"}
    kinds = {e.path.stem: e.kind for e in entries}
    assert kinds == {"conventions": "convention", "sensitive-paths": "sensitive_paths", "callers": "caller"}


# the staleness rule


def test_an_entry_within_the_default_window_is_fresh():
    entry = context_index.load_entries(FIXTURES_DIR / "fresh")[0]
    assert context_index.stale_reason(entry, now="2026-09-08T00:00:00+00:00") is None


def test_an_entry_past_the_default_day_window_is_stale():
    """R-F-6: more than the section 8 day count since `last_verified` is stale."""
    entry = context_index.load_entries(FIXTURES_DIR / "stale_by_days")[0]
    limit = context_index.default_max_days()
    now = datetime(2026, 9, 8, tzinfo=timezone.utc)
    verified_at = datetime.fromisoformat(entry.last_verified).replace(tzinfo=timezone.utc)
    assert (now - verified_at).days > limit  # the fixture is only meaningful if it actually crosses the limit
    reason = context_index.stale_reason(entry, now="2026-09-08T00:00:00+00:00")
    assert reason is not None and "last_verified" in reason


def test_must_reject_an_entry_with_no_last_verified_key_at_all():
    """A required front-matter key still missing entirely is a load-time error, distinct from
    the key being present with a null value (which is R-F-6's own "always stale" case)."""
    with pytest.raises(context_index.ContextIndexError):
        context_index.load_entries(FIXTURES_DIR / "missing_front_matter_key")


def test_an_entry_with_last_verified_present_but_null_is_always_stale():
    """R-F-6: no `last_verified` value marks the entry stale whatever the staleness rule says."""
    entry = context_index.load_entries(FIXTURES_DIR / "no_last_verified")[0]
    assert entry.last_verified is None
    assert context_index.stale_reason(entry, now="2026-09-08T00:00:00+00:00") == "no last_verified"


def test_a_day_fresh_entry_is_stale_when_a_base_branch_commit_touches_its_paths(tmp_path):
    """R-F-6: the commit clause makes an entry stale even when the day rule alone would not."""
    entry = context_index.load_entries(FIXTURES_DIR / "base_branch_touched")[0]
    repo = tmp_path / "checkout"
    repo.mkdir()
    _git(["init", "-q"], cwd=repo)
    _git(["checkout", "-q", "-b", "main"], cwd=repo)
    _commit(repo, message="seed", date="2026-08-01T00:00:00", touch="watched.txt")
    _commit(repo, message="touch watched path", date="2026-09-05T00:00:00", touch="watched.txt")

    # the day rule alone (entry verified 2026-09-01, now 2026-09-08) would call this fresh
    day_only = context_index.stale_reason(entry, now="2026-09-08T00:00:00+00:00")
    assert day_only is None

    with_commits = context_index.stale_reason(
        entry, now="2026-09-08T00:00:00+00:00", checkout=repo, target_branch="main",
    )
    assert with_commits is not None and "watched.txt" in with_commits


def test_a_day_fresh_entry_survives_a_base_branch_commit_that_does_not_touch_its_paths(tmp_path):
    entry = context_index.load_entries(FIXTURES_DIR / "base_branch_touched")[0]
    repo = tmp_path / "checkout"
    repo.mkdir()
    _git(["init", "-q"], cwd=repo)
    _git(["checkout", "-q", "-b", "main"], cwd=repo)
    _commit(repo, message="seed", date="2026-08-01T00:00:00", touch="watched.txt")
    _commit(repo, message="unrelated change", date="2026-09-05T00:00:00", touch="other.txt")

    reason = context_index.stale_reason(entry, now="2026-09-08T00:00:00+00:00", checkout=repo, target_branch="main")
    assert reason is None


# index_use rows and the stale_index tag


def _stage_run(conn) -> int:
    ticket_id = record.insert(conn, "ticket", state="context", opened_at=record.now())
    return run_ledger.open_stage_run(conn, ticket_id=ticket_id, stage="S1")


def test_a_read_stage_run_writes_one_index_use_row_per_entry_with_its_last_verified_date(conn):
    """R-S1-7: every context index entry read is recorded in `index_use` with its last-verified date."""
    stage_run_id = _stage_run(conn)
    entry = context_index.load_entries(FIXTURES_DIR / "fresh")[0]

    context_index.record_reads(conn, stage_run_id=stage_run_id, entries=[entry], now="2026-09-08T00:00:00+00:00")

    rows = conn.execute("SELECT * FROM index_use WHERE stage_run_id = ?", (stage_run_id,)).fetchall()
    assert len(rows) == 1
    assert rows[0]["entry_path"] == str(entry.path)
    assert rows[0]["entry_last_verified"] == entry.last_verified
    assert rows[0]["stale"] == 0


def test_a_stale_read_is_listed_stale_in_the_returned_reads(conn):
    """R-S1-7: an entry past its staleness rule is listed as stale to the reading stage."""
    stage_run_id = _stage_run(conn)
    entry = context_index.load_entries(FIXTURES_DIR / "stale_by_days")[0]

    reads = context_index.record_reads(conn, stage_run_id=stage_run_id, entries=[entry], now="2026-09-08T00:00:00+00:00")

    assert len(reads) == 1
    assert reads[0].stale is True
    assert reads[0].stale_reason is not None

    row = conn.execute("SELECT * FROM index_use WHERE stage_run_id = ?", (stage_run_id,)).fetchone()
    assert row["stale"] == 1


def test_a_stale_read_writes_a_stale_index_tag_with_fm_17(conn):
    """R-S1-7: a stale read writes a `tag` row with `event_kind = stale_index` and `fm_id = FM-17`."""
    stage_run_id = _stage_run(conn)
    entry = context_index.load_entries(FIXTURES_DIR / "stale_by_days")[0]

    context_index.record_reads(conn, stage_run_id=stage_run_id, entries=[entry], now="2026-09-08T00:00:00+00:00")

    tags = conn.execute(
        "SELECT * FROM tag WHERE ref = ? AND event_kind = 'stale_index'", (f"stage_run:{stage_run_id}",)
    ).fetchall()
    assert len(tags) == 1
    assert tags[0]["fm_id"] == "FM-17"


def test_a_fresh_read_writes_no_stale_index_tag(conn):
    stage_run_id = _stage_run(conn)
    entry = context_index.load_entries(FIXTURES_DIR / "fresh")[0]

    context_index.record_reads(conn, stage_run_id=stage_run_id, entries=[entry], now="2026-09-08T00:00:00+00:00")

    tags = conn.execute("SELECT * FROM tag WHERE ref = ?", (f"stage_run:{stage_run_id}",)).fetchall()
    assert tags == []


# an empty index is valid


def test_a_missing_index_directory_loads_as_no_entries(tmp_path):
    assert context_index.load_entries(tmp_path / "does-not-exist") == ()


def test_an_existing_but_empty_index_directory_loads_as_no_entries(tmp_path):
    empty = tmp_path / "empty-index"
    empty.mkdir()
    assert context_index.load_entries(empty) == ()


def test_recording_reads_over_no_entries_writes_nothing_and_raises_nothing(conn):
    """R-S1-7: an empty index is allowed; the reading stage records "no entries" rather than
    failing, which starts from `record_reads` writing zero rows and raising nothing over `()`."""
    stage_run_id = _stage_run(conn)

    reads = context_index.record_reads(conn, stage_run_id=stage_run_id, entries=(), now="2026-09-08T00:00:00+00:00")

    assert reads == ()
    assert conn.execute("SELECT * FROM index_use WHERE stage_run_id = ?", (stage_run_id,)).fetchall() == []
