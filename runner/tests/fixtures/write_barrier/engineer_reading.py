"""Stand-in for the engineer's own reading trying to write into factory/ at runtime.

Write-barrier fixture: the scanner in test_write_barrier.py
must flag this raw write the same way it flags real runner/ modules.
"""
import shutil

from runner.paths import FACTORY_DIR


def copy_reading_note(src: str) -> None:
    shutil.copy(src, FACTORY_DIR / "catalogue" / "reading_note.md")
