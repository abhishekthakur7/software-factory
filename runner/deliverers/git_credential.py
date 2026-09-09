"""The one-process Git askpass helper for a trusted GitHub publication call."""
import os
import sys


def main() -> int:
    prompt = sys.argv[1] if len(sys.argv) > 1 else ""
    if "username" in prompt.lower():
        print("x-access-token")
        return 0
    token = os.environ.get("SOFT_FACTORY_GITHUB_TOKEN")
    if not token:
        return 1
    print(token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
