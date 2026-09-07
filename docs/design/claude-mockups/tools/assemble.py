#!/usr/bin/env python3
"""Assemble a direction's index.html from its src/ partials.

Usage: python3 tools/assemble.py <dir> [--out PATH]
  <dir>   e.g. 02-observatory (contains src/00-head.html, src/NN-<screen>.html, src/99-tail.html)
  --out   write elsewhere (default <dir>/index.html). A preview must sit inside <dir> so assets/ resolves.

Partials concatenate in filename order. Any <style data-screen="…">…</style> block inside a screen
partial is hoisted into the head, just before </head>, so screen-scoped CSS can live next to its markup."""
import sys, os, re, glob
d = sys.argv[1].rstrip('/')
out = os.path.join(d, 'index.html')
if '--out' in sys.argv: out = sys.argv[sys.argv.index('--out') + 1]
parts = sorted(glob.glob(os.path.join(d, 'src', '*.html')))
head = open(parts[0]).read(); tail = open(parts[-1]).read()
body, hoisted = [], []
pat = re.compile(r'<style data-screen="[^"]*">.*?</style>\s*', re.S)
for p in parts[1:-1]:
    s = open(p).read()
    hoisted += pat.findall(s)
    body.append(pat.sub('', s))
if hoisted:
    head = head.replace('</head>', ''.join(h.rstrip() + '\n' for h in hoisted) + '</head>', 1)
open(out, 'w').write(head + ''.join(body) + tail)
print(out, os.path.getsize(out), 'bytes from', len(parts), 'partials')
