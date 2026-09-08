"""Filesystem roots shared by every runner module.

`factory/` is versioned and read-only at run time; `runs/` is the
unversioned run state. Both are fixed relative to this repository.
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FACTORY_DIR = REPO_ROOT / "factory"
RUNS_DIR = REPO_ROOT / "runs"
PROJECT_CONFIG = FACTORY_DIR / "config" / "project.yaml"
