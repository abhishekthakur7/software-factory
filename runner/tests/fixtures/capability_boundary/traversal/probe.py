"""Reads the host home directory through a relative `../..` traversal computed from an allowed mount.

The home directory comes from the account record, not `HOME`, which the
launcher points at the run's own scratch directory.
"""
import json
import os
import pwd
import sys


def main() -> int:
    mount = sys.argv[1]
    home = pwd.getpwuid(os.getuid()).pw_dir
    traversed = os.path.join(mount, os.path.relpath(home, start=mount))
    try:
        os.listdir(traversed)
        refused = False
    except OSError:
        refused = True
    print(json.dumps({"attempted": True, "refused": refused}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
