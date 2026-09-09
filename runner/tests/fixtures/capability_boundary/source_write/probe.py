"""Writes a new file into a source-tree path (the ticket worktree, or a build copy's worktree-shaped path)."""
import json
import os
import sys


def main() -> int:
    target_dir = sys.argv[1]
    try:
        with open(os.path.join(target_dir, "escape_write.txt"), "w") as handle:
            handle.write("written from inside the sandbox\n")
        refused = False
    except OSError:
        refused = True
    print(json.dumps({"attempted": True, "refused": refused}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
