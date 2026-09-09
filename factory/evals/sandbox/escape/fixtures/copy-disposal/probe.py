"""Writes a marker into the base copy so the caller can prove it is gone once `copies.dispose` runs.

`expect: ok` for this case: the write itself must succeed (the build
profile permits writes to the copy) -- the disposal assertion this
category is named for runs afterward, outside the sandbox, in the test
itself.
"""
import json
import os
import sys


def main() -> int:
    copy_dir = sys.argv[1]
    with open(os.path.join(copy_dir, "copy_disposal_marker.txt"), "w") as handle:
        handle.write("present before disposal\n")
    print(json.dumps({"attempted": True, "refused": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
