"""T-A-01 criterion 1, R-F-1: the committed factory/ tree matches PRD 7's layout."""
import subprocess

from runner.paths import FACTORY_DIR, REPO_ROOT

REQUIRED_DIRS = (
    "agents",
    "skills",
    "skills/shared",
    "rubrics",
    "rubrics/checklists",
    "scripts/checks",
    "scripts/tools",
    "lints",
    "evals",
    "benchmarks",
    "index",
    "config",
    "catalogue",
)


def test_every_prd_7_directory_exists_under_factory():
    for rel in REQUIRED_DIRS:
        assert (FACTORY_DIR / rel).is_dir(), f"missing factory/{rel}"


def test_manifest_file_exists():
    assert (FACTORY_DIR / "manifest.yaml").is_file()


def test_runs_directory_is_gitignored():
    # trailing slash lets git match the "runs/" gitignore pattern as a
    # directory even when runs/ hasn't been created on disk yet (it is
    # created lazily at run time and never committed).
    result = subprocess.run(
        ["git", "check-ignore", "-q", "runs/"], cwd=REPO_ROOT
    )
    assert result.returncode == 0
