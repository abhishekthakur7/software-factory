# 01 Workbench

A light-first operator console built on R04's frame: a dark 254px sidebar, a white content
column with a 32px page title, and a 336px right rail on the Queue. Tables are the primary
surface; the one selected item opens as a floating detail card over the table rather than in a
second pane. One accent (deep green) plus pass / fail / warn semantics; everything else is a
warm neutral ramp.

## Tokens

| Token | Light | Dark | Used for |
|---|---|---|---|
| `--page` | `#EFEFEB` | `#0E1113` | ground behind the app frame |
| `--bg` | `#FFFFFF` | `#1C2023` | content canvas, sticky table head |
| `--s1` | `#FFFFFF` | `#262A2E` | card / panel surface |
| `--s2` | `#FAFAF7` | `#2B3034` | inner fills (stage strip, log, expanded step) |
| `--s3` | `#F3F3EF` | `#353B3F` | selected row, icon chips, segmented track |
| `--s4` | `#EBEBE6` | `#42484C` | gauge track, empty stage dots |
| `--rail` | `#FAFAF8` | `#222629` | Queue right rail |
| `--bd` | `#E5E5DF` | `rgba(255,255,255,.11)` | card and section borders |
| `--hair` | `#F0F0EA` | `rgba(255,255,255,.07)` | row separators |
| `--ctl-bd` | `#DEDED7` | `rgba(255,255,255,.16)` | button / chip borders |
| `--tx` | `#141618` | `#EDEEEE` | primary text, black primary button |
| `--mu` | `#6D7276` | `#A0A6AA` | secondary text |
| `--fa` | `#9AA0A4` | `#868D92` | table head, hashes, uppercase labels |
| `--acc` | `#14684A` | `#54B08A` | selected, running dot, gauge, chart line, bars |
| `--acc-bg` | `#E6F1EB` | `rgba(84,176,138,.16)` | hero KPI tint, stage badge, review gate |
| `--pass` | `#14764F` | `#5CBB8B` | pass pill and tick |
| `--fail` | `#C0392F` | `#E4776C` | fail pill, red stage dot |
| `--warn` | `#9C6511` | `#DDA84E` | blocked / escalated / pending |
| `--nav` | `#101315` | `#07090A` | sidebar (darkest surface in both themes) |
| `--nav-edge` | transparent | `rgba(255,255,255,.09)` | 1px edge that keeps the sidebar readable in dark |
| `--nav-3` | `#262B2E` | `#262C2F` | active nav row |
| `--r1`…`--r4` | `#14684A`→`#CFE3D9` | `#6BC79E`→`#2A6047` | stage cost share ramp (4 steps) |

Shadows: `--sh-card` 1px hairline lift on cards, `--sh-pop` for the floating detail card and
bulk bar, `--sh-app` for the frame (dark adds a 1px white 5% ring so the frame edge reads).

## Type

Plus Jakarta Sans variable (400 / 500 / 600) for everything; Geist Mono only for hashes, the
run event log and the expanded step timestamps. Both are bundled in `assets/`.

| Level | Size / weight |
|---|---|
| Page title | 32 / 600, −0.028em |
| Detail-screen title (`run_7f3a`, ticket title) | 28 / 600 |
| Hero number (one per screen) | 36–38 / 600 tabular — Queue gauge 38, Tickets 12, Runs 43, Report $13.70, Factory 41, Run detail $9.85 at 34 |
| KPI number (non-hero) | 27 / 600 tabular |
| Gauge and donut centre | 38 / 28 / 600 tabular |
| Card title | 16.5 / 600 |
| Stat-strip number | 26 / 600 tabular (hero cell 34) |
| Table cell | 15 / 400; panel row 13.5–14 |
| Nav row, button | 14 / 500, 13.5 / 500 |
| Meta, sub-label | 12.5 / 400 muted |
| Uppercase label | 11 / 600, 0.08em |
| Mono log | 11.5 / 400 |

Row heights: 64px queue table, 58px tickets, 58px runs, 62px stage manifest, 64px run-detail
steps, 76px Factory switch rows, 44–62px panel rows. Card padding 15–24, gaps 20, page gutter 30, radius 14
cards / 10 controls / 999 pills.

## Screen → reference

| Screen | Copies |
|---|---|
| Queue | R04 whole frame: dark sidebar (rows and switcher from R10), filter chips with the full-bleed rule, 5-column table sized to its content, floating detail card with dark header, drag handle and four footer actions, right rail with R04's four sections (semi-donut gauge, segmented bar, 2-col stat grid, recent-decisions list) running to the frame edge |
| Tickets | R04 table and dark bulk bar, R12 KPI cards (icon circle, label, big number) |
| Ticket detail | R12 agent cards laid in a row of seven stage cards, R04 title row, R04 rail cards as the three panels |
| Runs | R04 table with the R12 KPI row (first card the hero); stage chip per row like R04's avatar slot, trailing `···`, child run indented under its parent |
| Run detail | R13 structure (stat strip, step list with one expanded step, event log block) in R04's light system, in three columns: tasks / inputs + guard decisions / event log |
| Report | R03 KPI row (one tinted hero card) and R03 area chart with dashed median and a callout wired to the circled point, R05 semi-donut with centre total and hatched stacked bars; four regions, chart 2/3 + donut 1/3 |
| Factory | R04 table for the stage manifest (one Model and one Budget column, tier range beside), R12 agent cards with three key/value rows, R09 switch rows (one value control, three toggles), fixture-gate + manifest stat pair as the hero |

## Review pass

`REVIEW.md` scored the seven screens and raised 29 findings. All 29 were acted on; the per-finding
reply is appended to `REVIEW.md`. The three that changed the most:

- **Dead space.** The 482px band through the Runs table is gone (columns evenly slacked, a stage
  chip per row, a trailing `···`, max gutter ~105px). The 475×312 empty right column on Factory is
  gone (stat pair + policy card now stretch to the manifest table's height, agent cards full width
  below). The 82px and 157px holes in the Queue rail are gone (sections size to their content, the
  slack falls at the bottom of the rail, the by-kind grid's last cell spans both columns). The
  710×101 hole under the Ticket-detail stage strip is gone (base advance and review gate are one
  full-width bar split on the stage grid, so the S4 and S6 connectors land on their own segment).
  On Run detail both columns end together — the event log grows into the slack.
- **Dark frame.** Page `#0E1113`, sidebar `#07090A`, content `#1C2023`, rail `#222629`, cards
  `#262A2E`, borders at 11% white — 20+ levels between the sidebar and the content instead of 8,
  plus a 1px white edge on the sidebar. The bulk bar and the floating-card header switch to a
  lighter elevated surface in dark rather than staying black.
- **One hero per screen.** Page titles hold 32; non-hero KPI numbers drop to 27; one number per
  screen goes to 36–38 (Queue gauge 38m, Tickets 12, Runs 43, Report $13.70, Factory 41, Run
  detail $9.85 at 34) and its card carries the single tint. The Factory stage × tier table
  collapses to one Model and one Budget column with the tier range beside — 21 cells of seven
  facts became 21 cells of 21. Primary table rows moved to 58px (R04 is ~61 at our scale).

Also: Tickets folded the checkbox into the Ticket cell (8 columns, R04's own arrangement) and the
bulk bar shifted so it occludes whole cells; running became a ringed accent dot on a neutral pill
so it can no longer be mistaken for pass; state pills reserve green for Merged; the artefact CLASS
column went (one `public` pill instead of eleven cells); approval group labels went to sentence
case; the Inputs badge reads 5, matching its rows; hashes are 4-and-2 everywhere; the Report is
four regions (chart 2/3 + donut 1/3, then bars + a merged tag/model card), its donut tail is
grouped as "Other 12%", its callout is wired to the circled point and the median label moved to the
card header; agent cards carry three key/value rows.

### Spacing pass

A second review re-scored every screen at 8 or above except spacing and alignment, which failed on
six of seven with one defect repeating: short values parked at the far right of a row with the middle
empty. The findings and the measured before/after are appended to `REVIEW.md`; the shape of the fix:

- **Tables and cards are cut to their content, and the space they cannot use goes to a neighbour.**
  The Queue table is 824px wide with five content-sized columns and the rail takes the rest (336 →
  414), so Needs → Age fell from 233px to 55px. The Artefacts card went from 650px to 356px (name →
  version 436 → 85). Run detail became three columns so the Inputs card is 336px (value → hash 405 →
  58). The Factory manifest card went 725 → 560 (Model → Budget 269 → 86) and the fixture-gate and
  policy column took the released width.
- **Fixed-width slots where a row ends.** The Runs outcome pill is an 88px slot and `···` a 40px one,
  so the strip before the trailing dots is constant instead of swinging with the pill's word; the
  seven Runs gutters are now 103–109px each rather than 84 in most places and 156 in one.
- **One baseline per KPI row.** The number sits in a fixed 34px line box, so growing the hero to 36px
  no longer pushes its sub-label 10px below its neighbours; digits are within 2px across every row.
- **Rails and merged cards run to their edges.** The Queue rail carries R04's four sections (the
  fourth is a three-row "Recent decisions" list) and its last ink is 1px from the frame edge, against
  a 304px void before. The Report's merged Tag/Model card top-aligns both halves instead of centring
  the right one.
- Also: the neutral state pill keeps a `--ctl-bd` ring on the selected row (1.02:1 → 1.22:1 at the
  edge) and Duration's colons line up on one x.

Still open after that pass: the Runs gutters are uniform but 103–109px rather than R04's 40–80 (eight
columns of short values in a 1258px table leave 748px of slack, so uniform is the optimum); the
Assumptions rows keep one wide two-field gap; Run detail ends 133px above the frame edge. All three
are recorded with their measurements at the end of `REVIEW.md`.

## Word counts

`python3 tools/wordcount.py 01-workbench/index.html`

```
queue     180 / 240  ok
tickets   161 / 200  ok
ticket    165 / 260  ok
runs      192 / 220  ok
run       144 / 260  ok
report    110 / 220  ok
factory   137 / 260  ok
```

## Verified

14 captures at 1600 wide, headless Chrome, scale 1, one profile per shot: Queue / Tickets / Ticket /
Run at 1000 tall, Factory at 950, Report at 1130 and Runs at 1560 because those screens differ from
the viewport. Gutters measured pixel by pixel in the captures (see the Spacing pass in `REVIEW.md`).
Checked each capture on its own and side by side against R04 (Queue, Tickets), R12 (Factory),
R03 and R05 (Report). Also rendered at 1280 and 1440 wide: the frame holds, the queue table
scrolls inside its own region. Fonts confirmed rendering from `assets/` (Plus Jakarta's rounded
`a` and single-storey `g` are visible in every capture).

## Deviations and unfinished

- Queue rows show a trailing `···` instead of a per-row bucket dot; the bucket is a group header
  row (dot + label) above each block. BRIEF-v2 §3 asks for a per-row dot, but with the rail
  already carrying the by-bucket legend a third repetition of the same fact per row was the kind
  of redundancy §2 rules out. Same information, one place per block.
- Long titles are truncated in the HTML with a real ellipsis rather than by CSS overflow, so the
  word counter sees what a reader sees. Full titles live in BRIEF.md §2.
- The stage manifest now shows one Model and one Budget column with the tier range beside the
  stage, because §2.7 carries no per-tier values. BRIEF-v2 §3 says "7 stages × 3 tiers"; the
  three columns were 14 duplicate cells, so the table states the range instead.
- Started / Duration / Cost are left-aligned on Runs (tabular figures, column-aligned). §2 asks
  for right-aligned numbers, but a right-aligned number after a left-aligned text column doubles
  the gutter at that junction, which is what produced the 482px band. R04 left-aligns its own
  Total and Date columns. Tickets keeps Cost and Age right-aligned at the table edge.
- The Factory hero is a stat pair (fixture gate 41, manifest v14) directly under the title rather
  than a thin header row. Same facts §3 lists in the header, rendered as the screen's one hero.
- One sandbox row carries a value control ("per stage") instead of a fourth identical toggle, so
  the control set varies the way R09's does without asserting a policy the data does not state.
- Tabs on the Queue detail card (Evidence, Slots) and every filter chip are static; only the
  theme toggle and hash nav are wired.
- Tickets shows 11 of its 12 rows at 1000 tall now that rows are 58px; the table runs off the
  bottom edge the way R04's does.
- Even at the tuned column widths the Runs table carries a 103–109px gutter per column against
  R04's 32–74px: 20 rows of seven short values simply carry less ink than R04's rows. The gutters
  are equal and constant, which is what stops them reading as a hole.
- The Queue rail is 414px against R04's 349 at our scale, and the Queue table 824px against R04's
  1040. R04 runs eight columns where §3 allows us five, so the split between table and rail moves
  rather than the columns spreading.
- Run detail is three columns (tasks | inputs + guard | event log) rather than two. It matches §3's
  own division and keeps the Inputs card at a width its three short fields can fill; the cost is
  that the screen ends 133px above the frame edge.
