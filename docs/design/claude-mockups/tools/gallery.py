#!/usr/bin/env python3
"""Regenerate one direction's Screens and Captures blocks in the gallery (index.html) from its captures/.

Usage: python3 tools/gallery.py <section-id> <folder> <label>
  e.g. python3 tools/gallery.py observatory 02-observatory "02 Observatory"
Screens come from the folder's router (the screens array) and their data-title; sizes from the PNGs."""
import sys, re, os
from PIL import Image
sec_id, folder, label = sys.argv[1:4]
gal = 'index.html'; g = open(gal).read()
html = open(os.path.join(folder, 'index.html')).read()
order = re.findall(r"'([a-z]+)'", re.search(r"screens=\[([^\]]*)\]", html).group(1))
titles = dict(re.findall(r'id="s-([a-z]+)" data-title="([^"]+)"', html))
titles = {k: ('Ticket detail' if k == 'ticket' else 'Run detail' if k == 'run' else v) for k, v in titles.items()}
links = ['<div class="links">']
for s in order:
    links.append(f'<div>\n<div class="name">{titles[s]}</div>\n<div class="hash mono">#{s}</div>\n'
                 f'<div class="pair"><a href="{folder}/index.html?theme=light#{s}">light</a><span>/</span>'
                 f'<a href="{folder}/index.html?theme=dark#{s}">dark</a></div>\n</div>')
links.append('</div>')
shots = ['<div class="shots">']
for i, s in enumerate(order, 1):
    figs = []
    for theme in ('light', 'dark'):
        p = f'{folder}/captures/{i:02d}-{s}-{theme}.png'
        w, h = Image.open(p).size
        figs.append(f'<figure>\n<a class="shot" style="aspect-ratio: {w} / {h}" href="{p}" target="_blank" rel="noopener">\n'
                    f'<img src="{p}" alt="{label} — {titles[s]}, {theme} theme" loading="lazy" decoding="async">\n</a>\n'
                    f'<figcaption><span>{titles[s]}</span><span class="theme">{theme}</span></figcaption>\n</figure>')
    shots.append(f'<div class="shotpair">\n<div class="pair-title"><span class="idx mono">{i:02d}</span><span>{titles[s]}</span>'
                 f'<span class="hash mono">#{s}</span></div>\n<div class="two">\n' + '\n'.join(figs) + '\n</div>\n</div>')
shots.append('</div>')
a = g.index(f'<section class="dir" id="{sec_id}">'); b = g.index('</section>', a)
sec = g[a:b]
sec = re.sub(r'<div class="links">.*?\n</div>\n</div>\n(?=<div class="section-label">Captures)', '\n'.join(links) + '\n', sec, count=1, flags=re.S)
sec = sec[:sec.index('<div class="shots">')] + '\n'.join(shots) + '\n</div>'  # the trailing </div> closes .wrap
g = g[:a] + sec + g[b:]
open(gal, 'w').write(g)
print(f'{sec_id}: {len(order)} screens, {2*len(order)} captures')
