"""Reads the host home directory from inside the sandbox; refused when that read fails.

The directory comes from the account record, not from `HOME`: the launcher
points the sandbox's `HOME` at the run's own scratch directory, and the
probe must look at where the host account actually lives.
"""
import json
import os
import pwd


def main() -> int:
    home = pwd.getpwuid(os.getuid()).pw_dir
    try:
        os.listdir(home)
        refused = False
    except OSError:
        refused = True
    print(json.dumps({"attempted": True, "refused": refused}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
