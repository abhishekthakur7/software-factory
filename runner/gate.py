"""The adoption-gate entry point: `python3 -m runner.gate`.

Three steps, each printing one line and, on its own failure, making the
whole run exit non-zero: the adoption record (the manifest hash `factory/`
is pinned to right now, and the last commit that touched it -- both read
from this repository's own local git history, with no outside network
call of any kind); the eval-directory completeness walk; and the
`runner/tests/` suite itself, over the subset of fixtures that exists
without the OS sandbox. A change under `factory/` that does not pass this
gate is not an adopted change, whatever branch protection the repository
does or does not enforce.
"""
import argparse
import subprocess
from pathlib import Path

import pytest

from runner import evals, manifest
from runner.paths import REPO_ROOT


def _last_factory_commit(root: Path) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(root), "log", "-1", "--format=%H", "--", "factory/"],
        capture_output=True, text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return result.stdout.strip()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="runner.gate")
    parser.add_argument("--tests", default=str(REPO_ROOT / "runner" / "tests"))
    parser.add_argument("--root", default=str(REPO_ROOT))
    args = parser.parse_args(argv)
    root = Path(args.root)

    failed = False

    try:
        current_hash = manifest.current_hash(root)
        last_commit = _last_factory_commit(root)
        print(f"adoption record: manifest {current_hash}, last factory/ commit {last_commit}")
    except manifest.ManifestError as exc:
        print(f"adoption record: FAIL ({exc})")
        failed = True

    try:
        evals.walk(root=root / "factory")
        print("eval directories: ok")
    except evals.EvalDirectoryError as exc:
        print(f"eval directories: FAIL ({exc})")
        failed = True

    test_rc = pytest.main([args.tests, "-q"])
    print(f"tests: {'ok' if test_rc == 0 else f'FAIL (exit code {test_rc})'}")
    if test_rc != 0:
        failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
