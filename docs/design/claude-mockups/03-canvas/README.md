# 03-canvas

A light-first node-graph direction: the factory's pipeline is drawn on a dotted canvas, and every screen
sits in the same R01 frame of icon rail, 280px panel, canvas and two console panes. Stages, tasks and gates
are node cards with one title line and one meta line; the state of a run is carried by the edge pills between
them, by low-saturation coloured node tabs and by one lime accent. The dotted canvas runs edge to edge under
the whole content area, and the panel, the tables, the charts and the console are frosted cards floating on
it, so the direction reads as one surface rather than seven pages.

Files: `index.html` (all CSS and JS inline), `assets/` (Outfit-Variable.woff2, JetBrainsMono-Variable.woff2),
`captures/` (14 PNGs). Hash routes `#queue #tickets #ticket #runs #run #report #factory`, `?theme=light|dark`
(light default, query wins over the toggle), works from `file://` with no network.

## Tokens

| Token | Light | Dark |
|---|---|---|
| `--page` (behind the app) | `#E9ECEF` | `#08090B` |
| `--app` | `#FFFFFF` | `#121418` |
| `--canvas` (the ground, runs under everything) | `#EFF1F5` | `#0B0D10` |
| `--dot` (grid, 22px pitch) | `rgba(20,26,40,.11)` | `rgba(255,255,255,.075)` |
| `--surface` / `--surface-2` | `#FFFFFF` / `#F4F6F8` | `#181B20` / `#1E2128` |
| `--frost` (panels, blur 22px) | `rgba(255,255,255,.84)` | `rgba(26,29,35,.80)` |
| `--frost-brd` | `rgba(20,26,40,.08)` | `rgba(255,255,255,.11)` |
| `--line` / `--line-2` | `#E7E9ED` / `#D9DDE3` | `rgba(255,255,255,.09)` / `.15` |
| `--ink` / `--ink-2` | `#111419` / `#3C434E` | `#F1F3F6` / `#C4CAD3` |
| `--muted` / `--faint` | `#79818E` / `#868E9C` | `#8A929F` / `#6B7481` |
| `--lime` (accent) / `--lime-2` | `#B8D832` / `#A8C824` | `#B6D64C` / `#C7E464` |
| `--lime-ink` (text on lime) | `#26320A` | `#161D04` |
| `--ok` pass | `#1B8F5E` | `#54BE8B` |
| `--bad` fail | `#C9403C` | `#E97B77` |
| `--warn` waived / blocked | `#A0700F` | `#D9A94A` |
| `--edge` (connectors, 2.5px) | `#8AA32B` | `#9FBB46` |
| `--port` (connector port fill) | `#FFFFFF` | `#20242B` |

Stage hues, used only on node tabs and the stage chips (low saturation, R16). Light → dark:
`--t0` `#7B8FAF`→`#8296B4`, `--t1` `#5E93A1`→`#699DAA`, `--t2` `#5D9782`→`#68A08C`, `--t3` `#7E9B5C`→`#8AA668`,
`--t4` `#B09A4F`→`#B8A25B`, `--t5` `#B5836A`→`#BD8D74`, `--t6` `#9179A6`→`#9C85AF`.
In light a tab is the solid hue with white text; in dark it is the hue at 26% with the hue as text
(`color-mix`), so nothing is a bright block on a dark ground. R13 step-card headers use the hue at 15% with
the hue as the label in both themes. Pills are the semantic colour at 10–14% with the colour as text — one
pill style everywhere, including the accent pill (Review, Running, Act today).

## Type scale (Outfit; JetBrains Mono only for console lines and hashes)

| Role | Size / weight |
|---|---|
| Page title (`h1`) | 28 / 600, −0.03em |
| KPI number | 36 / 600, tabular |
| Hero node title (review gate) | 18 / 600 |
| Queue decision card title | 25 / 600 |
| Gauge number | 28–29 / 600 |
| Card title, panel title | 16 / 600 |
| Node title | 14.5 / 600 (step cards 14–15 / 600) |
| Body, table cell | 13.5–14 / 400–500 |
| Meta, node meta | 12–12.5 muted |
| Uppercase label | 11 / 500, 0.07em (once per card) |
| Node tab, step header, edge pill | 12 |
| Console line, hash (mono) | 12 |
| Chart and gauge tick | 11 |

Nothing is below 12px except chart and gauge ticks (11) and uppercase micro-labels (11).
Rows: 56px in every primary table (Tickets, Runs, Factory manifest), 48–52px in panel lists, 26px console
lines. Cards 16px radius, controls 8–10px, pills 999. Card padding 16–18, gutter 20, panel 280, icon rail 60.
Node pitch on the two graph screens is 110px, so every edge has real line on both sides of its pill.

## Screen → reference

| Screen | Copies |
|---|---|
| Frame (all) | R01: icon rail, dotted canvas, top-bar tab, lime primary button, Console and Debug as two separate cards; the 280px panel is a frosted card floating on the ground, R17 / R07 |
| Queue | R01 panel list and canvas; R17 property-panel treatment for the frosted detail card and the right rail; R16 for the mini pipeline chain |
| Tickets | R04 row system (checkbox, key, title, pill, stages, right-aligned numbers) and dark bulk bar, in a frosted card inset 36px on the dotted ground, with the selected ticket's pipeline as node cards above it; R01 panel holds the four counts and the filters |
| Ticket detail | R16 coloured-tab node cards for S0–S6 and the assumptions card; R01 edge pills, Console and Debug panes; R17 gate branch (Approved / Send back pills into ghost nodes) |
| Runs | Same frosted table card on the ground, all 20 runs at 56px rows, child runs indented, stage name with its colour square in the Stage column, with the selected run and its base-advance child as two nodes above it; R01 panel holds the filters and a by-outcome summary |
| Run detail | R13 step cards with coloured headers for the six tasks and the fix round; R17 property panel (arc gauge, three numbers, two switches) and branch pills; R01 console |
| Report | R16 coloured-tab KPI cards; R03 / R15 line chart with median line and drawn callout; stacked daily bars; donut with centre total and legend |
| Factory | R17 node-library tile grid of the seven stages in the panel; R16 tabbed cards for the five agents; R09 switch rows for sandbox policy; one manifest row per stage (tiers, model, budget, rubric) |

## Word counts (`python3 tools/wordcount.py 03-canvas/index.html`)

```
queue     140 / 240  ok
tickets   187 / 200  ok
ticket    222 / 260  ok
runs      205 / 220  ok
run       187 / 260  ok
report    140 / 220  ok
factory   150 / 260  ok
```

## Review pass

Applied against `REVIEW.md` (42 findings). Per-finding answers are in that file's Builder response section.

Fixed, in order of weight:

- **The canvas is now the ground.** The dotted field runs edge to edge under the whole content area; the
  left panel, the tables, the charts, the console and the property panels are frosted cards floating on it.
  This removed the tall half-empty white panel column on six screens (F-A2) and the 20px decorative dotted
  border on Tickets and Runs (F-29) in one move.
- **The edges are drawn like R01.** Node pitch 110px on Ticket detail and Run detail (was 55 and 28),
  stroke 2.5px in a darkened accent, circular ports r=7 with a card-coloured fill and a 2px ring, drawn in a
  layer above the node cards so they are no longer clipped by them, and outlined 12px pill labels centred on
  the curve. Pass paths carry the accent; only warn and fail paths are toned (F-A1, F-6).
- **Ticket detail has a hero.** The review gate is a 252 × 100 node standing alone to the right of the second
  row, the title row is full width and no longer truncates, the meta cluster moved to its own line, the
  S3 → S4 wrap connector fills the dead band with a labelled edge, and the assumptions moved into the panel
  (F-6 – F-12).
- **Run detail shows the expanded step §3 asks for.** The Outputs pane is gone (five regions, not six) and
  the fix round names the failing check and the fix in four lines at R13's size (F-13 – F-17).
- **Factory's manifest stopped repeating itself.** Three identical tier columns collapsed to a Tiers column
  carrying what §2.7 varies (All / 1–3) plus one Model and one Budget column; "lines" moved into the column
  header (F-1, F-2). Trust profile removed, agent-card dividers removed (F-3, F-5).
- **Type floor.** Nothing below 12px except chart and gauge ticks and uppercase micro-labels (F-A5).
- **Colour.** The unmotivated canvas wash is gone (F-A3); gauge ticks are legible on dark (F-A4); panel icons,
  avatars and the Act today bucket are neutral or the accent instead of five decorative hues (F-12, F-20,
  F-21, F-32); one accent pill style with the hue as its own label (F-28); the disabled Approve reads
  disabled (F-19).
- **Runs** dropped the Model column and keeps 56px rows (F-24, F-25, F-27). The row count and the Stage
  column were revisited in the final pass below.
- **Report** folded the baseline into the KPI block (five regions), put three y ticks on the outcome bars,
  and moved the callout inside the chart SVG so its leader reaches the marker (F-33 – F-36).

Not done:

- **F-4 (switches green rather than lime)** — not a defect. `.sw.on` was already `var(--lime)`; the pixel
  under the switch in the reviewed capture is `#B8D832`. No change made.
- **The R16 gantt replacing "Runs by outcome"** — the reviewer recommends it, but BRIEF-v2 §3 fixes Report's
  secondary panels as "runs by outcome as stacked daily bars" and the brief forbids content beyond §3. The
  panel was fixed in place instead (value scale, gridlines).
- **F-30 (KPIs as panel rows rather than four cards)** — the four stats stay a stack inside the panel card on
  Tickets and Runs. The reason the reviewer objected, 490px of nothing under them, is gone: the final pass
  put the filter set and, on Runs, a by-outcome summary in the same panel.

Still open, by choice:

- Console and Artefacts are eight lines each on Ticket detail, and the Run detail console is eight of the
  fifteen §2.4 event-log entries — BRIEF-v2 §4.3 caps this direction's consoles at eight.

## Final pass

A second, targeted pass against the re-score findings R-1 to R-6 and its two rulings (`REVIEW.md`,
"Final pass" section, carries the measured before and after for each).

- **The left panel is R01's full-height card on every screen.** The dotted column under it — 615px on
  Factory, 500 on Run detail, 452 on Tickets and Runs, 434 on Report — is gone, and each panel was filled
  with content §3 already lists for its screen: Factory takes R17's node-library tile grid of the seven
  stages with the sandbox switches bottom-anchored; Run detail takes the six-task step list; Tickets and
  Runs take the filter set out of the title bar, and Runs adds a by-outcome bar with five counts pinned to
  the bottom; Report gains a Measures list from §2.6. Largest blank band inside any panel is now 30%.
- **Runs shows all 20 rows** of BRIEF §2.5 and is captured at 1600 × 1450 (BRIEF.md §5 allows a taller
  window for a longer screen); the other six screens stay at 1600 × 1000. The Stage column carries the
  stage name and its colour square, columns are sized to content in an 848px card, and no gutter exceeds
  100px (Stage → Started 247 → 70).
- **The Report outcome bars fit their axis.** Ticks are 0 / 7 / 14 and segments have a 1px gap, so a
  one-run segment reads about seven times the gap and the tallest stack sits below the top tick.
- **Table row states separate.** Hover is a neutral tint at 1.32:1 against the base row in both themes,
  checked is the accent at 14%, selected is the accent at 28% with a 3px lime bar.
- **The dark bulk bar floats.** `#616978` with a 10% white border and a two-layer shadow: 3.15:1 against
  the card behind it, up from 1.30.
- **Light `--faint` is `#868E9C`** (was `#A6ADB8`), 3.24:1 on a frosted card. The two faint items that sat
  on the raw ground — Report's baseline tag and the Ticket / Run eyebrow — are `--muted`.

Not fixed: the Factory manifest table's gutters are 120–128px rather than under 100 (R-7, out of scope).
The table's content is about 455px in a 998px card; taking the card to ~900px would stop it aligning with
the five agent cards below, which cannot go under ~185px each without truncating "s4-implementer".

## Verified

All 14 captures are headless Chrome, one Chrome per screen with its own `--user-data-dir`, run
sequentially (parallel runs sharing a profile produced stale renders; a reused profile caches the `file://`
document, so each run also gets a fresh profile and a cache-busting query). `--window-size=1600,1000` for
six screens and `1600,1450` for Runs, which is longer than the viewport. Fonts render from `assets/` under
`file://`. Every canvas reports 100% zoom at 1600. Four capture-and-fix passes were done, with side-by-sides
against R01 (Ticket detail, Queue, Tickets, Runs), R17 (Run detail, Factory) and R16 (Report), plus a
per-capture read of all 14 in both themes. Panel fill, table gutters and light and dark contrast were
measured from the pixels of the shipped captures, not from the CSS.

## Deviations and unfinished

- **R16 gantt and dot matrix are not used.** BRIEF-v2 §4.3 suggests them for Report, but §3 fixes Report's
  content and §2 caps a screen at five regions. R16 shows up instead as the coloured tabs on the agent cards
  and the stage nodes.
- **The Factory manifest is a table; R17's node-library grid is the left panel.** A model-and-budget matrix
  is tabular, so the seven stages appear as R17 tiles in the panel and the manifest stays a table beside it.
- **Ticket detail spreads §3's three panels** across the frame: Approvals and Assumptions in the left panel,
  Artefacts in the right console pane. Eight of the eleven artefacts are listed, with the count in the pane
  header.
- **Model spend shows three rows** as §3 asks, so the grader row (`claude-sonnet-5 $19.70`) is not on screen.
- **Ticket titles are shortened in the Tickets table's markup**, not only clipped by CSS, because the counter
  measures the DOM: T-0412 reads "Reject settlement batches whose currency…" there. The full title is on
  Ticket detail.
- **Approve is disabled with no explanation** (helper sentences are banned), so the screen does not say that
  Priya does not hold the security slot.
- The canvases are laid out for 1600. Below roughly 1500px the fit() helper scales a canvas down and the zoom
  readout drops under 100%; at 1440 and 1280 the screens are correct but the node graphs are scaled.
- No hover, focus or drag states beyond the single hovered table row and the selected rows; nothing is
  interactive except the nav, the theme toggle and hash routing.
