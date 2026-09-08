"""Stand-in for a `stale_index_entry` event trying to write into factory/ at runtime.

Fixture for T-A-01 criterion 8 (R-F-5): the scanner in test_write_barrier.py
must flag this raw write the same way it flags real runner/ modules.
"""
from pathlib import Path

from runner.paths import FACTORY_DIR


def refresh_entry(entry_name: str, body: str) -> None:
    Path(FACTORY_DIR / "index" / entry_name).write_text(body)
