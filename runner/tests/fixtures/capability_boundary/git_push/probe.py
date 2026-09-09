"""Attempts `git push` from inside a sandbox; refused when the push does not exit cleanly."""
import json
import subprocess
import sys


def main() -> int:
    repo_dir = sys.argv[1]
    # A build sandbox's process-exec grant never includes `git` at all, so
    # the exec itself can fail before a push is ever attempted -- refusal
    # just as real as a push that runs and is rejected by the disabled
    # remote or the missing network route.
    try:
        result = subprocess.run(
            ["git", "-c", "commit.gpgsign=false", "push"], cwd=repo_dir, capture_output=True, text=True,
        )
        refused = result.returncode != 0
    except OSError:
        refused = True
    print(json.dumps({"attempted": True, "refused": refused}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
