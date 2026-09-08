"""Filesystem roots shared by every runner module.

`factory/` is versioned and read-only at run time (R-F-5); `runs/` is the
unversioned run state. Both are fixed relative to this repository (PRD 7).
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FACTORY_DIR = REPO_ROOT / "factory"
RUNS_DIR = REPO_ROOT / "runs"
