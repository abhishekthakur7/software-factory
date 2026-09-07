#!/usr/bin/env python3
"""Capture every screen of a direction, both themes, at the height each screen needs.

Usage: python3 tools/capture.py <dir> [screen ...] [--profile DIR] [--min 1000] [--max 2400] [--html FILE] [--out DIR]
  <dir>     e.g. 02-observatory (reads <dir>/index.html, writes <dir>/captures/NN-<screen>-<theme>.png)
  screen    optional subset, e.g. queue ticket (default: every screen listed in the router)
  --html    capture another file instead, e.g. a preview assembled inside <dir> (assets must resolve)
  --out     write the PNGs elsewhere, e.g. a scratch folder
Runs Chrome one process at a time with a private profile. For each screen it first renders the dark
theme at --max height, finds the bottom of the last drawn element inside the content column (x > 260),
and then captures both themes at that height + 28px (never below --min, rounded up to 10)."""
import sys, os, re, subprocess, tempfile
from PIL import Image
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
d = sys.argv[1].rstrip('/'); args = sys.argv[2:]
def opt(name, default):
    if name in args:
        i = args.index(name); v = args[i + 1]; del args[i:i + 2]; return v
    return default
profile = opt('--profile', os.path.join(tempfile.gettempdir(), 'chrome-capture'))
lo, hi = int(opt('--min', 1000)), int(opt('--max', 2400))
index = os.path.abspath(opt('--html', os.path.join(d, 'index.html')))
outdir = opt('--out', os.path.join(d, 'captures'))
html = open(index).read()
m = re.search(r"screens=\[([^\]]*)\]", html)
order = re.findall(r"'([a-z]+)'", m.group(1))
screens = args or order
os.makedirs(outdir, exist_ok=True)
def shot(screen, theme, h, out, attempt=0):
    url = f'file://{index}?theme={theme}#{screen}'
    prof = profile if attempt == 0 else f'{profile}-{attempt}'
    cmd = [CHROME, '--headless=new', '--disable-gpu', '--hide-scrollbars', '--no-first-run',
           '--timeout=20000', f'--user-data-dir={prof}', f'--window-size=1600,{h}', f'--screenshot={out}', url]
    if os.path.exists(out): os.remove(out)
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=25)
    except subprocess.TimeoutExpired:
        subprocess.run(['pkill', '-9', '-f', prof])
        if os.path.exists(out) and os.path.getsize(out) > 1000:
            return  # Chrome wrote the PNG and then failed to exit; the capture is good
        if attempt < 2:
            print(f'{screen} {theme}: Chrome hung, retrying with a fresh profile', file=sys.stderr)
            return shot(screen, theme, h, out, attempt + 1)
        raise
def content_bottom(path):
    im = Image.open(path).convert('RGB'); w, h = im.size
    bg = im.getpixel((w - 4, h - 4)); px = im.load()
    for y in range(h - 1, 80, -1):
        for x in range(270, w - 6, 6):
            p = px[x, y]
            if max(abs(p[i] - bg[i]) for i in range(3)) > 4: return y
    return lo
for s in screens:
    n = order.index(s) + 1
    probe = os.path.join(tempfile.gettempdir(), f'probe-{s}.png')
    shot(s, 'dark', hi, probe)
    bottom = content_bottom(probe)
    h = max(lo, ((bottom + 28 + 9) // 10) * 10)
    if h >= hi - 20: print(f'{s}: content reaches the {hi}px probe; raise --max', file=sys.stderr)
    for theme in ('dark', 'light'):
        out = os.path.join(outdir, f'{n:02d}-{s}-{theme}.png')
        shot(s, theme, h, out)
        im = Image.open(out); print(f'{out} {im.size[0]}x{im.size[1]} (content bottom {bottom})')
    os.remove(probe)
