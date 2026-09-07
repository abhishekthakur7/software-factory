#!/usr/bin/env python3
"""Stack a reference image and one of our captures at the same width.

Usage: python3 tools/sidebyside.py references/R04.png 01-workbench/captures/01-queue-light.png out.png [--h]
Default stacks vertically (reference on top) so proportions, row heights and
type sizes compare directly. --h places them side by side."""
import sys
from PIL import Image, ImageDraw

ref_p, cap_p, out_p = sys.argv[1:4]
horizontal = '--h' in sys.argv
W = 1400
def fit(p):
    im = Image.open(p).convert('RGB')
    h = round(im.height * W / im.width)
    return im.resize((W, h), Image.LANCZOS)
ref, cap = fit(ref_p), fit(cap_p)
label_h = 36
if horizontal:
    out = Image.new('RGB', (W * 2 + 24, max(ref.height, cap.height) + label_h), '#202020')
    out.paste(ref, (0, label_h)); out.paste(cap, (W + 24, label_h))
    pos = [(12, 8), (W + 36, 8)]
else:
    out = Image.new('RGB', (W, ref.height + cap.height + label_h * 2 + 24), '#202020')
    out.paste(ref, (0, label_h)); out.paste(cap, (0, ref.height + label_h * 2 + 24))
    pos = [(12, 8), (12, ref.height + label_h + 32)]
d = ImageDraw.Draw(out)
d.text(pos[0], f'REFERENCE  {ref_p}', fill='#ffffff')
d.text(pos[1], f'OURS       {cap_p}', fill='#ffffff')
out.save(out_p)
print(out_p, out.size)
