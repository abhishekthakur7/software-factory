"""Stand-in for a repeated `grader_failure` trying to patch factory/ at runtime.

Fixture for T-A-01 criterion 8 (R-F-5): the scanner in test_write_barrier.py
must flag this raw write the same way it flags real runner/ modules.
"""
from runner.paths import FACTORY_DIR


def patch_rubric(rubric_path: str, body: bytes) -> None:
    with open(FACTORY_DIR / "rubrics" / rubric_path, "wb") as f:
        f.write(body)
