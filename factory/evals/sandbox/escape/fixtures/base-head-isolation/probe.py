"""Writes a marker into the base copy, then tries to read that same relative path under the head copy.

Run under the build profile scoped to the base copy alone: `refused` true
means the head copy is neither mounted nor written by a base-scoped run,
which is the isolation this category exists to prove -- not merely that
two `cp -c` clones happen to be independent files on disk.
"""
import json
import os
import sys


def main() -> int:
    copy_dir, head_dir = sys.argv[1], sys.argv[2]
    marker_name = "escape_marker.txt"
    with open(os.path.join(copy_dir, marker_name), "w") as handle:
        handle.write("base-only\n")
    try:
        with open(os.path.join(head_dir, marker_name)) as handle:
            handle.read()
        refused = False
    except OSError:
        refused = True
    print(json.dumps({"attempted": True, "refused": refused}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
