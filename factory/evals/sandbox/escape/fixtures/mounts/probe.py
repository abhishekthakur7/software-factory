"""Reads a sibling checkout the caller never registered as this run's input; refused when the read itself fails."""
import json
import sys


def main() -> int:
    sibling_path = sys.argv[1]
    try:
        with open(sibling_path) as handle:
            handle.read()
        refused = False
    except OSError:
        refused = True
    print(json.dumps({"attempted": True, "refused": refused}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
