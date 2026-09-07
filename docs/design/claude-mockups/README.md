# Soft Factory UI mockups, round 2

Three design directions for the Soft Factory app, each one a single self-contained `index.html` that
renders the same seven screens from the same fixed fake data, in light and dark. Every direction also
ships 14 captures (7 screens × 2 themes) under its own `captures/`.

`index.html` in this folder is the gallery: the three directions side by side, with links into every
screen and thumbnails of all 42 captures.

## The three directions

| direction | character | fonts | open |
|---|---|---|---|
| 01 Workbench | A clean operations workbench: dark charcoal sidebar, white content area, dense tables, floating layers where a person acts. Light-first. | Plus Jakarta Sans, Geist Mono | [01-workbench/index.html](01-workbench/index.html) |
| 02 Observatory | A monitoring room: near-black surfaces, hairline cards, tabular numerals, sparklines and a live activity rail. Dark-first. | Geist, Geist Mono | [02-observatory/index.html](02-observatory/index.html) |
| 03 Canvas | The factory as a node canvas: the S0→S6 walk as node cards with labelled edges, a console and debug panel beneath. Light-first. | Outfit, JetBrains Mono | [03-canvas/index.html](03-canvas/index.html) |

Each direction's own `README.md` has its token table, type scale, what it borrows from which reference,
and what its author verified or left unfinished.

## The seven screens

Every direction renders all seven as sections of one file; the nav switches between them without a reload.
`index.html` honours `location.hash` on load (default `#queue`) and `?theme=light|dark` (the query wins
over the direction's default). Query before hash: `index.html?theme=dark#report`.

| # | screen | hash | capture prefix |
|---|---|---|---|
| 1 | Queue | `#queue` | `01-queue` |
| 2 | Tickets | `#tickets` | `02-tickets` |
| 3 | Ticket detail | `#ticket` | `03-ticket` |
| 4 | Runs | `#runs` | `04-runs` |
| 5 | Run detail | `#run` | `05-run` |
| 6 | Report | `#report` | `06-report` |
| 7 | Factory | `#factory` | `07-factory` |
| 8 | Governance (Observatory only) | `#governance` | `08-governance` |

Governance was added to Observatory in the polish round: `docs/design/milestones.md` (block 6, Trust
profile) names a governance view where the security and legal approvers see the proposed trust profile and
the owners file and record a metadata-only approval; none of the seven screens showed it.

## The brief, the references, and the rebuild

The first build (7 Sep 2026) was rated 6/10 by the owner: two to four times the text of the references,
two-line monospace rows, subtitles and helper sentences, a flat type scale. It was rebuilt the same day.

- [BRIEF.md](BRIEF.md) §1 describes the product, §2 fixes the fake data verbatim (Northwind Payments,
  12 tickets, 10 queue items, the latest 20 runs, ticket T-0412, run run_7f3a, a 30-day report, the
  factory manifest), §5 is the technical spec. Its §3, §4, §6 and §7 are superseded.
- [BRIEF-v2.md](BRIEF-v2.md) is the contract for the rebuild: what each screen shows and nothing more, a
  density budget (word caps per screen, one line per row, sentence-case kinds, mono only for logs and
  hashes, type bands measured from the references), and the screen-to-reference map per direction.
- `references/R01.png` … `R17.png` are the owner's 17 reference screenshots. Every builder and reviewer
  looked at them directly; the review is a side-by-side against the named reference.
- `tools/wordcount.py <dir>/index.html` counts visible words per screen against the caps;
  `tools/sidebyside.py <reference> <capture> <out.png>` stacks a reference and a capture at the same width.
- Each direction's `REVIEW.md` holds the side-by-side review: scores per screen on five axes (hierarchy,
  density, spacing and alignment, colour and contrast, craft), the findings with reference measurements,
  the builder's response, the re-score, and the final pass.
- `_previous/` keeps the first build's `index.html` and `README.md` per direction for comparison. Their
  captures were overwritten. `_previous/02-observatory-v2/` is the Observatory rebuild as it stood before
  the polish round, with its captures.

## The Observatory polish (evening of 7 Sep 2026)

The owner chose Observatory and attached seven more references (`references/R18.png` … `R24.png`: a light
SaaS admin with KPI cards and a query table, a kanban in light and dark, a workflow builder, a settings
page, a dark agent-mission canvas, a node canvas). [BRIEF-v3.md](BRIEF-v3.md) is the contract for that
round: what polish means here (§0), the new references and what each lends (§1), the milestone-to-screen
map that adds Governance (§2), a measured component contract (§3), the per-screen contract (§4) and the
working rules for parallel builders on one file (§5).

- `02-observatory/src/` holds the file as partials: `00-head.html` (CSS, icon sprite, sidebar, top bar),
  `01-queue.html` … `08-governance.html` (one screen each, with its screen-scoped `<style data-screen>`),
  `99-tail.html` (the router). `python3 tools/assemble.py 02-observatory` writes `02-observatory/index.html`
  from them; edit the partials, not the assembled file.
- `02-observatory/SYSTEM.md` documents the shared components (KPI card, table shell, node card, edges,
  timeline, stat box, settings row, tab row, avatars, emphasis states) with their markup.
- `tools/capture.py 02-observatory [screen …]` captures every screen in both themes at the height the
  screen needs; `tools/gallery.py observatory 02-observatory "02 Observatory"` regenerates this gallery's
  Observatory block from the captures.
- `02-observatory/REVIEW-v3.md` holds the baseline review against the new references, the round-1
  side-by-side review after the polish, and the final pass.

Nothing is invented per direction, so the same ticket, run and cost numbers appear on every screen and in
every direction.

## How to open

Double-click `index.html` in this folder — everything works from `file://`, with no network and no build
step. Fonts are bundled under each direction's `assets/`.

If you prefer a server:

```
python3 -m http.server 4175 --directory docs/design/claude-mockups
```

then open <http://localhost:4175/>.

## How to regenerate captures

One PNG per screen per theme, headless Chrome, named `NN-screen-theme.png`, at scale 1 (the template from
BRIEF.md §5):

```
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu \
  --hide-scrollbars --window-size=1600,1000 --screenshot="captures/01-queue-light.png" \
  "file:///ABSOLUTE/PATH/index.html?theme=light#queue"
```

Use a taller window (`--window-size=1600,1400` or more) for screens longer than the viewport, so the
capture shows the whole screen. `--force-device-scale-factor=2` is useful for a close-up polish check, but
the shipped captures stay at scale 1. The gallery reads capture heights from the files themselves, so a
re-shot capture at a different height does not break its layout.

## Not to be confused with

`docs/design/mockups/` is an earlier, separate round with different fake data. This folder does not extend
it; the two sets are not meant to be compared screen by screen.
