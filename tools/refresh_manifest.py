#!/usr/bin/env python3
"""Regenerate the `files:` section of factory/manifest.yaml from disk; keep `stages:` verbatim.

Usage: python3 tools/refresh_manifest.py [repo-root]
Lists every regular file under factory/ (skipping __pycache__, *.pyc, .DS_Store)
sorted by path with its sha256, then re-appends the existing `stages:` block
unchanged. Run it after adding, editing or deleting any file under factory/,
then commit the manifest together with the change. This is the maintainer's
command -- neither the gate nor any test calls it.
"""
import hashlib
import re
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd().resolve()
manifest_path = root / "factory" / "manifest.yaml"
text = manifest_path.read_text()
match = re.search(r"^stages:\s*$", text, re.MULTILINE)
if not match:
    raise SystemExit("manifest.yaml has no `stages:` block")
stages_block = text[match.start():]

skip_names = {".DS_Store"}
entries = []
for path in sorted((root / "factory").rglob("*")):
    if not path.is_file():
        continue
    if "__pycache__" in path.parts or path.suffix == ".pyc" or path.name in skip_names:
        continue
    if path == manifest_path:
        continue
    rel = path.relative_to(root).as_posix()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    entries.append((rel, digest))

lines = ["version: 1", "files:"]
for rel, digest in entries:
    lines.append(f"  - path: {rel}")
    lines.append(f"    content_hash: {digest}")
manifest_path.write_text("\n".join(lines) + "\n" + stages_block)
print(f"{len(entries)} entries written to {manifest_path}")
