"""Writes into the immutable checkout underlying a copy; refused when the write itself fails."""
import json
import os
import sys


def main() -> int:
    checkout_path = sys.argv[1]
    target = os.path.join(checkout_path, "escape_write.txt")
    try:
        with open(target, "w") as handle:
            handle.write("should not land\n")
        refused = False
    except OSError:
        refused = True
    print(json.dumps({"attempted": True, "refused": refused}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
