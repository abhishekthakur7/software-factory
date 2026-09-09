"""Reads a file placed in the ticket directory that no invocation ever registered as an input; refused when the read fails."""
import json
import sys


def main() -> int:
    unregistered_path = sys.argv[1]
    try:
        with open(unregistered_path) as handle:
            handle.read()
        refused = False
    except OSError:
        refused = True
    print(json.dumps({"attempted": True, "refused": refused}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
