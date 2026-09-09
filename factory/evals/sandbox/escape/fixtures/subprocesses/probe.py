"""Spawns a process outside the build profile's recipe-executable allowlist; refused when the exec itself fails."""
import json
import subprocess


def main() -> int:
    try:
        subprocess.run(["/bin/ls", "/"], capture_output=True)
        refused = False
    except OSError:
        refused = True
    print(json.dumps({"attempted": True, "refused": refused}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
