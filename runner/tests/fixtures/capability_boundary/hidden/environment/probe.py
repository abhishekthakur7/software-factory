"""Reads an environment name the launching process set but the sandbox policy never allowlisted."""
import json
import os


def main() -> int:
    leaked = "HIDDEN_CAPABILITY_ENV_CANARY" in os.environ
    print(json.dumps({"attempted": True, "refused": not leaked}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
