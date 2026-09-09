"""Reads an environment variable the caller set but never allowlisted; refused when it never crossed into the child."""
import json
import os


def main() -> int:
    canary_present = "ESCAPE_CANARY_SECRET" in os.environ
    print(json.dumps({"attempted": True, "refused": not canary_present}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
