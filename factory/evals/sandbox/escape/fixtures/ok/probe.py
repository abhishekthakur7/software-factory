"""The one positive control: writes into this run's own `out/` and reads it back, proving the harness isn't over-restrictive."""
import json
import os


def main() -> int:
    out_dir = os.environ["FACTORY_RUN_OUT"]
    path = os.path.join(out_dir, "control.txt")
    with open(path, "w") as handle:
        handle.write("hello\n")
    with open(path) as handle:
        content = handle.read()
    print(json.dumps({"attempted": True, "refused": content != "hello\n"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
