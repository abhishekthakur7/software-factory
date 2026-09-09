"""The adoption-gate entry point: `python3 -m runner.gate`.

Three steps, each printing one line and, on its own failure, making the
whole run exit non-zero: the adoption record (the manifest hash `factory/`
is pinned to right now, and the last commit that touched it -- both read
from this repository's own local git history, with no outside network
call of any kind); the eval-directory completeness walk; and the
`runner/tests/` suite itself, including the required sandbox and history
fixtures even when a caller selects fewer tests. A change under `factory/` that does not pass this
gate is not an adopted change, whatever branch protection the repository
does or does not enforce.
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from runner.fs import write_text
from runner import evals, manifest, record
from runner.paths import REPO_ROOT


def _last_factory_commit(root: Path) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(root), "log", "-1", "--format=%H", "--", "factory/"],
        capture_output=True, text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return result.stdout.strip()


def check_fixture_changes(root: Path) -> None:
    """Require each versioned mechanism change since fixture introduction to carry its fixture update.

    Inspecting each commit prevents an unrelated follow-up commit from hiding
    an earlier mechanism change that omitted its regression fixture.
    """
    introduction = subprocess.run(
        ["git", "-C", str(root), "log", "--diff-filter=A", "--format=%H", "--", "factory/evals/sandbox/copy-disposal/eval.yaml"],
        capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    result = subprocess.run(
        ["git", "-C", str(root), "log", "--first-parent", "--format=commit:%H", "--name-only"],
        capture_output=True, text=True, check=True,
    )
    mechanisms = {
        "sandbox/escape": ("runner/sandbox/os_policy.py", "runner/sandbox/proxy.py", "runner/launcher.py", "factory/config/sandbox/"),
        "sandbox/copy-disposal": ("runner/sandbox/copies.py", "runner/recipes.py", "runner/adoption.py", "factory/config/command-recipes.yaml"),
        "record/incident-history": ("runner/record.py", "runner/schema.py"),
        "record/control-history": ("runner/record.py", "runner/schema.py", "runner/tags.py"),
        "record/coverage-history": ("runner/record.py", "runner/schema.py", "runner/tags.py"),
    }
    for commit in result.stdout.split("commit:")[1:]:
        lines = commit.splitlines()
        changed = set(lines[1:])
        for name, paths in mechanisms.items():
            if not any(path.startswith(prefix) for path in changed for prefix in paths):
                continue
            directory = f"factory/evals/{name}"
            if f"{directory}/eval.yaml" not in changed or not any(
                path.startswith(f"{directory}/fixtures/") for path in changed
            ):
                raise evals.EvalDirectoryError(f"{name}: mechanism change {lines[0]} requires eval.yaml and a matching fixture update")
        if not introduction or lines[0] == introduction[-1]:
            break


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="runner.gate")
    parser.add_argument("--tests", default=str(REPO_ROOT / "runner" / "tests"))
    parser.add_argument("--root", default=str(REPO_ROOT))
    parser.add_argument("--close", action="store_true", help="record local adoption only after every required check passes")
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
        check_fixture_changes(root)
        print("eval directories: ok")
    except evals.EvalDirectoryError as exc:
        print(f"eval directories: FAIL ({exc})")
        failed = True

    required = [REPO_ROOT / "runner/tests" / name for name in ("test_escape_suite.py", "test_adoption_fixtures.py")]
    selected = Path(args.tests).resolve()
    extra = [str(path) for path in required if path != selected and selected not in path.parents]
    # A fresh process prevents module caching across gate invocations from
    # making a selected factory tree reuse another tree's fixture definitions.
    test_rc = subprocess.run(
        [sys.executable, "-m", "pytest", args.tests, *extra, "-q"],
        env={**os.environ, "FACTORY_GATE_ROOT": str(root.resolve())}, cwd=REPO_ROOT,
    ).returncode
    print(f"tests: {'ok' if test_rc == 0 else f'FAIL (exit code {test_rc})'}")
    if test_rc != 0:
        failed = True

    if args.close and not failed:
        receipt = root / "runs/adoption" / f"{current_hash}.json"
        receipt.parent.mkdir(parents=True, exist_ok=True)
        write_text(receipt, json.dumps({
            "manifest_hash": current_hash, "factory_commit": last_commit, "checked_at": record.now(),
            "result": "pass", "required_mechanics": list(evals.REQUIRED_MECHANICS),
        }, sort_keys=True) + "\n")
        print(f"adoption closed: {receipt}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
