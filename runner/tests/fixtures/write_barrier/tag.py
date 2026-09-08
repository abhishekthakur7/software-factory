"""Stand-in for a `tag` event trying to write into factory/ at runtime.

Fixture for T-A-01 criterion 8 (R-F-5): the scanner in test_write_barrier.py
must flag this raw write the same way it flags real runner/ modules.
"""
from runner.paths import FACTORY_DIR


def apply_tag(body: str) -> None:
    with open(FACTORY_DIR / "catalogue" / "tags.md", "w") as f:
        f.write(body)
