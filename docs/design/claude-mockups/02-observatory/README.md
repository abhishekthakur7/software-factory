# 02 Observatory

A dark-first monitoring room for the factory: near-black surfaces stepped by elevation, one green
accent carrying running / selected / pass, and one glowing card per screen marking the thing that is
moving or waiting on a person. Eight screens are built from the same parts — a KPI or stat row, one
table or flow, one or two secondary panels, a right rail on Queue, Runs and Ticket detail — so they
read as one product. The light theme is a tuned off-white console (white cards on `#F1F2F4`, a
`#F7F8F9` sidebar, a 1px lift), not an inverted copy of the dark one.

Scores, per-finding history and the residual list: `REVIEW-v3.md`.

## Tokens (`src/00-head.html`)

| Token | Dark (`:root`) | Light (`[data-theme="light"]`) |
|---|---|---|
| `--page` | `#0B0C0E` | `#F1F2F4` |
| `--sidebar` | `#08090B` | `#F7F8F9` |
| `--card` | `#121417` | `#FFFFFF` |
| `--card-2` | `#181B1F` | `#F7F8FA` |
| `--card-3` | `#1F2429` | `#EDEFF2` |
| `--border` | `rgba(255,255,255,.08)` | `#E4E6EA` |
| `--border-2` | `rgba(255,255,255,.14)` | `#D2D7DD` |
| `--text` | `#E7E9EC` | `#14171A` |
| `--muted` | `#9AA1A9` | `#667079` |
| `--faint` | `#5F666E` | `#8B939C` |
| `--accent`, `--pass` (`--accent-ink`) | `#22C55E` (`#052012`) | `#15803D` (`#FFFFFF`) |
| `--fail` | `#EF4444` | `#DC2626` |
| `--warn` | `#F59E0B` | `#B45309` |
| `--accent-s`, `--pass-s`, `--fail-s`, `--warn-s` | hue at 13% | hue at 9–11% |
| `--neutral-s` | `rgba(255,255,255,.07)` | `rgba(20,23,26,.055)` |
| `--grid` / `--dots` / `--hatch` | `.06` / `.10` / `.09` white | `.08` / `.13` / `.11` ink |
| `--hov` / `--sel` / `--glow` | `.035` white / accent `.055` / `.11` | `.032` ink / accent `.045` / `.07` |
| card elevation | none (surface step only) | `0 1px 2px rgba(16,24,40,.04)` |
| `--gv-div` (Governance rows) | `rgba(255,255,255,.045)` | `#F4F5F7` |

One accent. Semantic colour is pass green, fail red, warn amber, plus neutral greys — no blue-for-info
and no per-stage rainbow. Emphasis is a 1px semantic border plus `0 0 0 4px` at 8% and `0 0 24px` at
18% in dark, and `0 1px 2px rgba(16,24,40,.04), 0 0 0 4px` at 10% in light, so an emphasised card
keeps the plain card's elevation. `.is-pass` deliberately has no ring; `.is-live` adds a pulse dot.

## Type scale as built

Geist Regular / Medium / SemiBold and Geist Mono, bundled in `assets/`.

| Role | Size / weight |
|---|---|
| Page title (top bar `h1`) | 28 / 600, −0.03em |
| Screen header title (`.th h2`, `.fhead h2`) | 23–24 / 600 |
| KPI number (`.kpi-n`) | `clamp(30px, 2.27vw, 34px)` / 600 tabular; 26–30 inside the Runs rail grid |
| Donut centre, gauge figure | 25–26 / 600 |
| Stat box value (`.stat-v`) | 20 / 600 |
| Card and section title (`.tbl-t h2`, `.sec-h h2`) | 17 / 600 |
| Settings row label (`.set-l`), node title (`.node-t`) | 15 / 600 |
| Table row, KPI label, tab, list-row title | 14.5 / 400–500 |
| Body | 14 / 400 |
| Meta, second lines, muted phrases | 12.5–13.5 / 400 muted |
| Delta pill (`.kpi-d`), stat label | 12.5 / 500 |
| Status pill (`.pill`) | 12.5 / 500, 24px tall |
| Uppercase label (`.lbl`) | 11 / 600, 0.07em |
| Mono (event log, code, hashes) | 12.5–13 Geist Mono |

Rows 60px in every table and rail list, 44px table headers, 68px table-card headers, 84px Governance
settings rows, 76px stat boxes, 168px KPI cards. Card radius 15, inset 12, node 14, controls 999.
Page gutter 28, card padding 16–22, grid gaps 20.

## Components

Every shared class, its HTML shape and its measured contract are in `SYSTEM.md`: surfaces and the
emphasis border, top bar and per-screen `.tb-actions`, sidebar, buttons and filter pills, status
pill, KPI card (including `smoothSparklines()`), stat box, table shell, rail list row, node/stage
card, canvas and edges, timeline, settings row and section header, tab row, avatars and switch.

## Screen → reference

| # | Screen | Copies |
|---|---|---|
| 1 | Queue | R11 frame and rail; R18 table shell (title + count, search, Bucket / Kind / Ticket dropdowns, 60px rows, ⋮ circle); R19 card anatomy for the decision card (two pills, title, meta, checklist slot rows); R23 details rail |
| 2 | Tickets | R18 throughout — KPI cards, shell with State / Tier / Class, 60px rows, ⋮; R04 bulk bar |
| 3 | Ticket detail | R23 wholesale — goal card, stage cards with icon tile and progress bar, curved edges with endpoint dots, execution timeline, 380px details rail with progress and stat boxes; R13 step list for Approvals |
| 4 | Runs | R18 KPI cards and table shell; R11 live-activity rail (60px two-line rows) |
| 5 | Run detail | R13 structure (step list, inputs and guard panels, event log); R23 stat boxes, the Cost box carrying the budget bar |
| 6 | Report | R18 KPI cards and panel headers; R15 layout, donut and model rows; R02 heatmap with hatched no-data cells |
| 7 | Factory | R18 manifest table; R23 agent cards; R22 sandbox-policy settings rows |
| 8 | Governance | R22 wholesale — tab row, section header with external link, settings rows, footer pair; R20 for the dark surface steps |

Outcomes follow R06 everywhere: pass is a dot plus the plain word, and the filled pill is kept for
fail, blocked, aborted and running.

## Word counts

`python3 tools/wordcount.py 02-observatory/index.html runs=260`

```
queue       216 / 240  ok      run         154 / 260  ok
tickets     185 / 200  ok      report      137 / 220  ok
ticket      232 / 260  ok      factory     180 / 260  ok
runs        259 / 260  ok      governance  154 / 240  ok
```

The tool still defaults Runs to 220; pass `runs=260` or it reports OVER.

## Working on it

- Edit the partials in `src/`, never `index.html`. `src/00-head.html` holds the head, tokens, the
  shared CSS, the icon sprite, the sidebar and the top bar; `src/01-queue.html` … `src/08-governance.html`
  are one `<section class="screen">` each; `src/99-tail.html` is the router and `smoothSparklines()`.
- `python3 tools/assemble.py 02-observatory` rebuilds `index.html` from the partials in filename
  order, hoisting each `<style data-screen="…">` block into the head. `--out` writes a preview
  elsewhere inside the folder so `assets/` still resolves.
- Screen-scoped CSS lives in `<style data-screen="<id>">` inside its own partial and **every selector
  and every new class name starts with `#s-<id>` / a screen prefix** — shared names like `.rt` and
  `.ok` leak. Override shared components under that prefix rather than editing `00-head.html`.
- `python3 tools/capture.py 02-observatory [screen …] --profile <dir>` captures both themes at the
  height each screen needs (it probes the content bottom first) into `captures/`. One Chrome at a
  time; if it writes the PNG and hangs, wait 25s, kill it, and use the PNG.
- `python3 tools/gallery.py observatory 02-observatory "02 Observatory"` regenerates the direction's
  blocks in the top-level `index.html`; `python3 tools/sidebyside.py references/RNN.png
  captures/<file> out.png` stacks a reference over a capture for review.

## Unfinished and deliberately traded off

- **Report carries eight regions and four chart types** (line, donut, stacked bars, heatmap) plus
  progress rows and row sparklines, against the one-large-chart rule. BRIEF-v3 §4.6 fixes the panel
  set, so this needs a brief change. It is the only place the review scores below 8.
- **Two tables draw a bar for a range the data cannot fill**: the Factory pass rates (97 → 79) and
  the Report tag leaderboard (5 / 4 / 2 / 2 / 1).
- **Factory's agent cards are 243px**, under §3's 300–320, because §4.7 asks for five across in a
  1310px column. Four across at 320 would satisfy both numbers.
- **Run detail puts its panel counts to the right of the title** where every other screen puts them
  underneath, and its Guard-decision figures sit at the same 14px digit height as the stat strip.
- **Tickets and Runs keep the neutral delta pill** beside the KPI number; Report dropped the chrome
  for a plain muted phrase. §2 supplies no real deltas, so neither can be coloured.
- **Two of four Tickets sparklines are monotone ramps.** The smoother keeps a monotone series
  monotone on purpose; the wave would have to come from the data.
- **Governance's Owners tab is inert** (§4.8 asks for the tab row and for both sections stacked), its
  header/label ratio is 1.18 against R22's 1.36 because §3 sets 17 and 15, and it builds its own
  `.gv-*` settings row instead of the shared `.set` / `.sec` that Factory uses.
- **The dark card step is a 1.061 contrast ratio** against R20's 1.087; deepening it is a token
  change that moves all eight screens. In light, the heatmap's lightest step clears its panel by
  ΔE 16.4 — legible, but light is the weaker theme for that one panel.
