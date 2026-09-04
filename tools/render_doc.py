#!/usr/bin/env python3
"""Render a docs/*.md file to the published HTML page design.

Usage: python3 tools/render_doc.py docs/charter.md out.html [--standfirst "..."]

Stdlib only. Handles the markdown subset the documents use: one H1, an optional
meta table under it, numbered H2 sections, H3 subsections, paragraphs, bullet
and numbered lists, pipe tables, fenced code, bold, inline code, and links.
Content before the first H2 (the PRD part files have no H2) is rendered in
place. Charter and PRD identifiers (P1, FM-01, C3, D20, Q10, QP-5, R-S3-4, S0)
are rendered as chips.
The page is written for the Artifact tool: no doctype, html, head, or body tags.
"""
import html
import re
import sys
from pathlib import Path

ID_RE = re.compile(r"(?<![\w-])(P\d{1,2}|FM-\d{2}|C\d{1,2}|D\d{1,2}|QP-\d+|Q\d{1,2}|R-(?:T|I|H|O|F|S\d)-\d+|S\d)(?![\w-])")
BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")

DEFAULT_STANDFIRST = {
    "charter.md": "The citation root for agent-assisted change to high-stakes, brownfield services. Everything built after this document has to point back to it.",
    "prd.md": "Requirements for the factory the charter describes: precise enough to build and test. Every requirement cites a principle and a failure mode, and the initial version is one page.",
}

CSS = """
  :root{
    --ground:#F5F6F4; --surface:#FFFFFF; --ink:#1B2321; --muted:#5C6763;
    --rule:#D8DDD8; --rule-strong:#B4BDB7;
    --accent:#1E6B5A; --accent-ink:#155245; --accent-soft:#E2EEE9;
    --warn:#A35F14; --warn-soft:#F6EAD9; --code-bg:#ECEFEC;
    --serif:"IBM Plex Serif",Georgia,"Times New Roman",serif;
    --sans:"IBM Plex Sans",-apple-system,"Segoe UI",Helvetica,Arial,sans-serif;
    --mono:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  }
  @media (prefers-color-scheme: dark){
    :root:not([data-theme="light"]){
      --ground:#131816; --surface:#1A201E; --ink:#E4E9E6; --muted:#98A49E;
      --rule:#2A3330; --rule-strong:#3F4B46;
      --accent:#6CC2A9; --accent-ink:#8FD6C1; --accent-soft:#1D332C;
      --warn:#E2A65C; --warn-soft:#3A2A15; --code-bg:#202825;
    }
  }
  :root[data-theme="dark"]{
    --ground:#131816; --surface:#1A201E; --ink:#E4E9E6; --muted:#98A49E;
    --rule:#2A3330; --rule-strong:#3F4B46;
    --accent:#6CC2A9; --accent-ink:#8FD6C1; --accent-soft:#1D332C;
    --warn:#E2A65C; --warn-soft:#3A2A15; --code-bg:#202825;
  }
  html{color-scheme:light dark}
  body{margin:0; background:var(--ground); color:var(--ink); font-family:var(--sans); font-size:16px; line-height:1.6; -webkit-font-smoothing:antialiased}
  *{box-sizing:border-box}
  a{color:var(--accent-ink); text-decoration:none}
  a:hover{text-decoration:underline}
  a:focus-visible{outline:2px solid var(--accent); outline-offset:2px}
  .page{max-width:1240px; margin:0 auto; padding:56px 36px 120px}
  .masthead{border-bottom:1px solid var(--rule-strong); padding-bottom:28px; margin-bottom:40px}
  .eyebrow{font-family:var(--mono); font-size:12px; letter-spacing:.06em; text-transform:uppercase; color:var(--muted); margin:0 0 14px}
  h1{font-family:var(--serif); font-weight:600; font-size:44px; line-height:1.1; letter-spacing:-.01em; margin:0 0 12px; text-wrap:balance}
  .standfirst{font-size:19px; line-height:1.45; max-width:62ch; margin:0 0 28px; color:var(--ink)}
  .meta{display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:16px 24px; border-top:1px solid var(--rule); padding-top:16px; max-width:980px; margin:0}
  .meta div{display:flex; flex-direction:column; gap:2px}
  .meta dt{font-family:var(--mono); font-size:11px; letter-spacing:.07em; text-transform:uppercase; color:var(--muted)}
  .meta dd{margin:0; font-size:14.5px}
  .meta dd code{font-size:.85em}
  .layout{display:grid; grid-template-columns:210px minmax(0,1fr); gap:56px; align-items:start}
  .toc{position:sticky; top:24px}
  .toc .label{font-family:var(--mono); font-size:11px; letter-spacing:.07em; text-transform:uppercase; color:var(--muted); margin:0 0 10px}
  .toc ol{list-style:none; margin:0; padding:0; border-left:1px solid var(--rule); max-width:none}
  .toc li{margin:0}
  .toc a{display:grid; grid-template-columns:22px 1fr; gap:6px; padding:5px 0 5px 12px; margin-left:-1px; border-left:2px solid transparent; font-size:13.5px; line-height:1.35; color:var(--muted)}
  .toc a .n{font-family:var(--mono); font-size:12px; color:var(--muted)}
  .toc a:hover{color:var(--ink); text-decoration:none}
  .toc a.active{color:var(--ink); border-left-color:var(--accent)}
  .toc a.active .n{color:var(--accent-ink)}
  main{min-width:0}
  section{margin:0 0 56px; scroll-margin-top:24px}
  h2{font-family:var(--serif); font-weight:600; font-size:27px; line-height:1.2; margin:0 0 18px; display:flex; align-items:baseline; gap:14px; text-wrap:balance}
  h2 .num{font-family:var(--mono); font-weight:500; font-size:15px; color:var(--accent-ink)}
  h3{font-family:var(--serif); font-weight:600; font-size:19px; line-height:1.3; margin:30px 0 12px; text-wrap:balance; scroll-margin-top:24px}
  p{margin:0 0 14px; max-width:72ch}
  strong{font-weight:600}
  ul,ol{margin:0 0 14px; padding-left:22px; max-width:72ch}
  li{margin:0 0 8px}
  code{font-family:var(--mono); font-size:.9em; background:var(--code-bg); padding:1px 5px; border-radius:2px}
  pre{background:var(--surface); border:1px solid var(--rule); padding:16px 18px; overflow-x:auto; margin:0 0 18px; font-size:13px; line-height:1.5}
  pre code{background:none; padding:0; font-size:inherit}
  .id{font-family:var(--mono); font-size:12px; font-weight:500; letter-spacing:.02em; color:var(--accent-ink); background:var(--accent-soft); padding:1px 5px; border-radius:2px; white-space:nowrap; vertical-align:baseline}
  .tbd{color:var(--muted)}
  .readfirst{border:1px solid var(--rule-strong); background:var(--surface); padding:22px 26px; margin:0 0 40px}
  .readfirst .label{font-family:var(--mono); font-size:11px; letter-spacing:.07em; text-transform:uppercase; color:var(--accent-ink); margin:0 0 10px}
  .readfirst p{max-width:76ch}
  .principles{display:grid; grid-template-columns:auto minmax(0,1fr); gap:0 18px; max-width:80ch; margin:0 0 14px}
  .principles > div{display:contents}
  .principles .id{align-self:start; margin-top:14px; justify-self:start}
  .principles p{padding:12px 0; border-top:1px solid var(--rule); max-width:none; margin:0}
  .principles > div:last-child p{border-bottom:1px solid var(--rule)}
  ul.lead-list{list-style:none; padding:0; max-width:80ch}
  ul.lead-list li{padding:10px 0; border-top:1px solid var(--rule); margin:0}
  ul.lead-list li:last-child{border-bottom:1px solid var(--rule)}
  ul.lead-list .id{margin-right:6px}
  .tablewrap{overflow-x:auto; border:1px solid var(--rule); background:var(--surface); margin:0 0 22px}
  table{border-collapse:collapse; width:100%; font-size:13.5px; line-height:1.5}
  th{font-family:var(--mono); font-size:11px; font-weight:500; text-transform:uppercase; letter-spacing:.07em; color:var(--muted); text-align:left; padding:10px 12px; border-bottom:1px solid var(--rule-strong); white-space:nowrap}
  td{padding:10px 12px; border-bottom:1px solid var(--rule); vertical-align:top}
  tr:last-child td{border-bottom:none}
  table.req td:nth-child(1){white-space:nowrap}
  table.req td:nth-child(2){min-width:34ch}
  table.req td:nth-child(3){min-width:14ch}
  table.req td:nth-child(3) .id{margin-right:3px}
  table.req td:nth-child(4){white-space:nowrap}
  table.fm td:nth-child(1){white-space:nowrap}
  table.fm td:nth-child(2){white-space:nowrap; color:var(--muted)}
  table.plain td:first-child{white-space:nowrap}
  table.plain td:first-child code{white-space:normal}
  td.tbd,td .tbd{color:var(--muted)}
  @media (max-width:900px){
    .page{padding:36px 20px 80px}
    h1{font-size:34px}
    .layout{grid-template-columns:1fr; gap:28px}
    .toc{position:static; border-bottom:1px solid var(--rule); padding-bottom:18px}
    .toc ol{border-left:none; display:flex; flex-wrap:wrap; gap:4px 18px}
    .toc a{display:inline-flex; gap:6px; padding:2px 0; border-left:none; margin:0}
    .meta{grid-template-columns:repeat(2,minmax(0,1fr))}
    table.req td:nth-child(2){min-width:28ch}
  }
  @media print{ .toc{display:none} .layout{grid-template-columns:1fr} body{background:#fff; color:#000} }
  @media (prefers-reduced-motion:no-preference){ html{scroll-behavior:smooth} }
"""

SCRIPT = """
(function(){
  var links = Array.prototype.slice.call(document.querySelectorAll('.toc a[href^="#"]'));
  if (!links.length || !('IntersectionObserver' in window)) return;
  var sections = links.map(function(a){ return document.getElementById(a.getAttribute('href').slice(1)); }).filter(Boolean);
  var current = sections.length ? sections[0].id : null;
  function paint(){ links.forEach(function(a){ a.classList.toggle('active', a.getAttribute('href') === '#' + current); }); }
  var io = new IntersectionObserver(function(entries){ entries.forEach(function(e){ if (e.isIntersecting) current = e.target.id; }); paint(); }, { rootMargin: '-8% 0px -78% 0px', threshold: 0 });
  sections.forEach(function(s){ io.observe(s); }); paint();
})();
"""


def slug(text):
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s or "section"


def inline(text):
    """Escape, then apply inline code, bold, and id chips outside code spans."""
    parts = text.split("`")
    out = []
    for i, part in enumerate(parts):
        esc = html.escape(part, quote=False)
        if i % 2 == 1:
            out.append(f"<code>{esc}</code>")
            continue
        esc = LINK_RE.sub(r'<a href="\2">\1</a>', esc)
        esc = BOLD_RE.sub(r"<strong>\1</strong>", esc)
        esc = ID_RE.sub(r'<span class="id">\1</span>', esc)
        out.append(esc)
    return "".join(out)


def cell(text):
    t = text.strip()
    if t == "TBD":
        return '<td class="tbd">TBD</td>'
    return f"<td>{inline(t)}</td>"


def split_row(line):
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [c.strip() for c in line.split("|")]


def is_sep(line):
    return bool(re.fullmatch(r"\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?", line.strip()))


def render_table(lines, first_table):
    header = split_row(lines[0])
    rows = [split_row(l) for l in lines[2:]]
    if first_table and all(h == "" for h in header):
        items = "".join(
            f"<div><dt>{inline(r[0])}</dt><dd>{inline(r[1])}</dd></div>" for r in rows if len(r) >= 2
        )
        return f'<dl class="meta">{items}</dl>', True
    h0 = header[0].lower()
    if h0 in ("#", "failure mode"):
        cls = "req"
    elif h0 == "id" and len(header) > 1 and header[1].lower() == "stage":
        cls = "fm"
    else:
        cls = "plain"
    thead = "".join(f"<th>{inline(h)}</th>" for h in header)
    body = []
    for r in rows:
        r = r + [""] * (len(header) - len(r))
        body.append("<tr>" + "".join(cell(c) for c in r[: len(header)]) + "</tr>")
    return (
        f'<div class="tablewrap"><table class="{cls}"><thead><tr>{thead}</tr></thead>'
        f'<tbody>{"".join(body)}</tbody></table></div>',
        False,
    )


LEAD_ID_TITLE = re.compile(r"^\*\*((?:P|C|D|Q|QP-|FM-)\d+)\.\s+(.+?)\*\*\s*(.*)$", re.S)
LEAD_ID_ONLY = re.compile(r"^\*\*((?:P|C|D|Q|QP-|FM-)\d+)\.\*\*\s*(.*)$", re.S)


def render_lead_item(text):
    m = LEAD_ID_TITLE.match(text)
    if m:
        return f'<li><span class="id">{m.group(1)}</span> <strong>{inline(m.group(2))}.</strong> {inline(m.group(3))}</li>'
    m = LEAD_ID_ONLY.match(text)
    if m:
        return f'<li><span class="id">{m.group(1)}</span> {inline(m.group(2))}</li>'
    return f"<li>{inline(text)}</li>"


def render_list(items, ordered, lead):
    if ordered:
        return "<ol>" + "".join(f"<li>{inline(i)}</li>" for i in items) + "</ol>"
    if lead:
        return '<ul class="lead-list">' + "".join(render_lead_item(i) for i in items) + "</ul>"
    return "<ul>" + "".join(f"<li>{inline(i)}</li>" for i in items) + "</ul>"


def render_principles(paras):
    out = ['<div class="principles">']
    for p in paras:
        m = LEAD_ID_TITLE.match(p)
        out.append(
            f'<div><span class="id">{m.group(1)}</span><p><strong>{inline(m.group(2))}.</strong> {inline(m.group(3))}</p></div>'
        )
    out.append("</div>")
    return "".join(out)


def parse_blocks(lines):
    """Yield (kind, payload) blocks from markdown lines."""
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if line.startswith("```"):
            j = i + 1
            buf = []
            while j < n and not lines[j].startswith("```"):
                buf.append(lines[j])
                j += 1
            yield ("code", "\n".join(buf))
            i = j + 1
            continue
        if line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            yield ("h%d" % level, line[level:].strip())
            i += 1
            continue
        if line.lstrip().startswith("|") and i + 1 < n and is_sep(lines[i + 1]):
            j = i
            buf = []
            while j < n and lines[j].lstrip().startswith("|"):
                buf.append(lines[j])
                j += 1
            yield ("table", buf)
            i = j
            continue
        m = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", line)
        if m:
            ordered = m.group(2)[0].isdigit()
            items = []
            j = i
            while j < n:
                mm = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", lines[j])
                if mm and mm.group(2)[0].isdigit() == ordered:
                    items.append(mm.group(3))
                    j += 1
                elif lines[j].startswith("  ") and items and lines[j].strip():
                    items[-1] += " " + lines[j].strip()
                    j += 1
                else:
                    break
            yield ("list", (items, ordered))
            i = j
            continue
        buf = [line.strip()]
        j = i + 1
        while j < n and lines[j].strip() and not lines[j].startswith(("#", "|", "```", "- ", "* ")) and not re.match(r"^\d+\.\s", lines[j]):
            buf.append(lines[j].strip())
            j += 1
        yield ("p", " ".join(buf))
        i = j


def block_html(kind, payload):
    """Render one non-table block: h3, paragraph, fenced code, or list."""
    if kind == "h3":
        return f'<h3 id="{slug(payload)}">{inline(payload)}</h3>'
    if kind == "p":
        return f"<p>{inline(payload)}</p>"
    if kind == "code":
        return f"<pre><code>{html.escape(payload, quote=False)}</code></pre>"
    if kind == "list":
        items, ordered = payload
        lead = (not ordered) and all(i.startswith("**") for i in items)
        return render_list(items, ordered, lead)
    return ""


def render(md_text, rel_path, standfirst):
    lines = md_text.splitlines()
    blocks = list(parse_blocks(lines))
    title = next((p for k, p in blocks if k == "h1"), rel_path)
    meta_html = ""
    sections = []  # dicts: id, num, title, body(list of html), aside(bool)
    cur = None
    first_table = True
    principles_buf = []

    def flush_principles():
        nonlocal principles_buf
        if principles_buf and cur is not None:
            cur["body"].append(render_principles(principles_buf))
            principles_buf = []

    for kind, payload in blocks:
        if kind == "h1":
            continue
        if kind == "h2":
            flush_principles()
            m = re.match(r"^(\d+)\.\s+(.*)$", payload)
            if m:
                num, text = m.group(1), m.group(2)
            else:
                num, text = ("R" if payload.lower().startswith("revision") else ""), payload
            aside = payload.lower().startswith("how to use")
            cur = {"id": ("s" + num) if num.isdigit() else slug(text), "num": num, "title": text, "body": [], "aside": aside}
            sections.append(cur)
            continue
        if cur is None:
            # content before the first h2: the meta table, then anything else in place
            if kind == "table":
                h, was_meta = render_table(payload, first_table)
                first_table = False
                if was_meta:
                    meta_html = h
                    continue
            else:
                h = block_html(kind, payload)
            sections.append({"id": "front", "num": "", "title": "", "body": [h], "aside": False})
            continue
        if kind == "p" and "principles" in cur["title"].lower() and LEAD_ID_TITLE.match(payload):
            principles_buf.append(payload)
            continue
        flush_principles()
        if kind == "table":
            h, was_meta = render_table(payload, first_table)
            first_table = False
            cur["body"].append(h)
        else:
            cur["body"].append(block_html(kind, payload))
    flush_principles()

    toc = []
    main = []
    for s in sections:
        if s["id"] == "front":
            main.extend(s["body"])
            continue
        if s["aside"]:
            main.append(f'<aside class="readfirst"><p class="label">{inline(s["title"])}</p>{"".join(s["body"])}</aside>')
            continue
        toc.append(f'<li><a href="#{s["id"]}"><span class="n">{s["num"]}</span><span>{inline(s["title"])}</span></a></li>')
        num_html = f'<span class="num">{s["num"]}</span>' if s["num"].isdigit() else ""
        main.append(f'<section id="{s["id"]}"><h2>{num_html}{inline(s["title"])}</h2>{"".join(s["body"])}</section>')

    fonts = "https://fonts.googleapis.com/css2?family=IBM+Plex+Serif:wght@400;600&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap"
    return f"""<title>{html.escape(title)}</title>
<link rel="stylesheet" href="{fonts}">
<style>{CSS}</style>
<div class="page">
  <header class="masthead">
    <p class="eyebrow">soft-factory &nbsp;/&nbsp; {html.escape(rel_path)}</p>
    <h1>{html.escape(title)}</h1>
    <p class="standfirst">{html.escape(standfirst)}</p>
    {meta_html}
  </header>
  <div class="layout">
    <nav class="toc" aria-label="Sections"><p class="label">Contents</p><ol>{"".join(toc)}</ol></nav>
    <main>{"".join(main)}</main>
  </div>
</div>
<script>{SCRIPT}</script>
"""


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    src, dst = Path(argv[1]), Path(argv[2])
    standfirst = None
    if "--standfirst" in argv:
        standfirst = argv[argv.index("--standfirst") + 1]
    if standfirst is None:
        standfirst = DEFAULT_STANDFIRST.get(src.name, "")
    rel = str(src)
    for root in ("docs/",):
        idx = rel.find(root)
        if idx >= 0:
            rel = rel[idx:]
    dst.write_text(render(src.read_text(encoding="utf-8"), rel, standfirst), encoding="utf-8")
    print(f"wrote {dst} ({dst.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
