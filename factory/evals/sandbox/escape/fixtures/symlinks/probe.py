"""Follows a symlink the caller placed inside an allowed mount, targeting a path outside every declared mount."""
import json
import sys


def main() -> int:
    link_path = sys.argv[1]
    try:
        with open(link_path) as handle:
            handle.read()
        refused = False
    except OSError:
        refused = True
    print(json.dumps({"attempted": True, "refused": refused}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
