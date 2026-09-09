"""Reads the host home directory from inside the sandbox; refused when that read fails."""
import json
import os


def main() -> int:
    home = os.path.expanduser("~")
    try:
        os.listdir(home)
        refused = False
    except OSError:
        refused = True
    print(json.dumps({"attempted": True, "refused": refused}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
