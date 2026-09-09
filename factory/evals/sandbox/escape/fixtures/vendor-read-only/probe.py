"""The declared vendor input is readable, while writes and removal remain forbidden."""
import json
import sys
from pathlib import Path


target = Path(sys.argv[1])
readable = target.read_text() == "pinned dependency\n"
try:
    target.write_text("substituted dependency\n")
    write_refused = False
except OSError:
    write_refused = True
try:
    target.unlink()
    unlink_refused = False
except OSError:
    unlink_refused = True
print(json.dumps({"attempted": True, "readable": readable, "refused": write_refused and unlink_refused}))
