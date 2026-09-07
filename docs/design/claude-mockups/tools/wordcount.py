#!/usr/bin/env python3
"""Count visible words per screen in a mockup index.html.

Usage: python3 tools/wordcount.py 01-workbench/index.html [screen=cap ...]
Counts text inside each <section class="screen" id="..."> (ids may be
s-queue, screen-queue or queue). Scripts, styles and SVG <text> are stripped.
Exits 1 when a screen exceeds its cap (BRIEF-v2 §3)."""
import re, sys, html

CAPS = {'queue': 240, 'tickets': 200, 'ticket': 260, 'runs': 220,
        'run': 260, 'report': 220, 'factory': 260, 'governance': 240}

path = sys.argv[1]
if '02-observatory' in path: CAPS['runs'] = 260  # Observatory carries the R11 live rail on Runs (BRIEF-v2 §4.2)
# optional overrides, e.g. runs=260 (Observatory carries the R11 live rail on Runs)
for arg in sys.argv[2:]:
    k, v = arg.split('=')
    CAPS[k] = int(v)
s = open(path, encoding='utf-8').read()
s = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', s, flags=re.S)
s = re.sub(r'<!--.*?-->', '', s, flags=re.S)
starts = [(m.start(), m.group(1)) for m in
          re.finditer(r'<section[^>]*\bid="(?:s-|screen-)?([a-z]+)"', s)]
bad = False
for i, (pos, name) in enumerate(starts):
    if name not in CAPS:
        continue
    end = starts[i + 1][0] if i + 1 < len(starts) else len(s)
    chunk = s[pos:end]
    chunk = re.sub(r'<text[^>]*>.*?</text>', ' ', chunk, flags=re.S)  # chart tick labels
    text = html.unescape(re.sub(r'<[^>]+>', ' ', chunk))
    n = len(text.split())
    flag = 'OVER' if n > CAPS[name] else 'ok'
    bad |= n > CAPS[name]
    print(f'{name:8s} {n:4d} / {CAPS[name]}  {flag}')
sys.exit(1 if bad else 0)
