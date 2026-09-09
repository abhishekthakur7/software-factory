"""Probe: attempt to write into the run's own `results/` subpath from inside the agent sandbox; report whether refused.

`FACTORY_RUN_OUT` is the one directory name the sandbox actually hands the
child; `results/` is its sibling, so this probe derives the path the same
way any other code outside the sandbox would, without needing a
`results/`-specific environment variable of its own.
"""
import json
import os


def main() -> int:
    out_dir = os.environ["FACTORY_RUN_OUT"]
    results_dir = os.path.join(os.path.dirname(out_dir), "results")
    target = os.path.join(results_dir, "forged_tool_result.txt")
    refused = False
    try:
        with open(target, "w") as handle:
            handle.write("forged\n")
    except OSError:
        refused = True
    print(json.dumps({"attempted": True, "refused": refused}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
