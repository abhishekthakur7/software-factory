# 02 Observatory — dark-first monitoring room

Observatory treats the factory as something you watch: near-black surfaces stepped by elevation, one green
accent carrying "running / selected / pass", and numbers set large enough that a screen reads from across a
desk. Every screen is built from the same four parts — a KPI or stat row, one large panel, one or two
secondary panels, and (on Queue and Runs) a right rail — so the seven screens feel like one product rather
than seven layouts. The light theme is a tuned off-white console — white cards on a `#F1F2F4` page with a
`#F7F8F9` sidebar, so the nav column, the page and the cards are three distinct surfaces — not an inverted
copy of the dark one.

## Tokens

| Token | Dark (default) | Light |
|---|---|---|
| `--page` | `#0B0C0E` | `#F1F2F4` |
| `--sidebar` | `#08090B` | `#F7F8F9` |
| `--card` | `#121417` | `#FFFFFF` |
| `--card-2` | `#181B1F` | `#F1F3F6` |
| `--card-3` | `#1F2429` | `#E7EAEE` |
| `--border` | `rgba(255,255,255,.08)` | `#E1E4E8` |
| `--border-2` | `rgba(255,255,255,.14)` | `#CDD3DA` |
| `--text` | `#E7E9EC` | `#14171A` |
| `--muted` | `#9AA1A9` | `#667079` |
| `--faint` | `#5F666E` | `#8B939C` |
| `--accent` / `--pass` | `#22C55E` | `#15803D` |
| `--fail` | `#EF4444` | `#DC2626` |
| `--warn` | `#F59E0B` | `#B45309` |
| pill tints | semantic hue at 13% | semantic hue at 9–11% |
| `--grid` | `rgba(255,255,255,.06)` | `rgba(20,23,26,.08)` |
| `--dots` (flow canvas) | `rgba(255,255,255,.10)` | `rgba(20,23,26,.13)` |
| `--dots` (flow canvas) | `rgba(255,255,255,.10)` | `rgba(20,23,26,.13)` |
| `--glow` (KPI card) | `.11` | `.07` |

There is one accent. Semantic colour is pass green, fail red, warn amber, plus neutral greys. Running uses
the accent with a static ring, not violet; there is no blue-for-info and no per-stage rainbow. The donut and
all progress bars are a single-hue accent ramp, floored at 34% so the small segments stay visible on white
(100 / 78 / 62 / 50 / 42 / 34%). Outcomes follow R06: pass is a dot plus the plain word, and the filled pill
is reserved for fail, blocked, aborted and running.

## Type scale

Geist Regular / Medium / SemiBold and Geist Mono, bundled in `assets/` (single-storey `g` visible in every
capture; mono confirmed in the event log and hashes).

| Role | Size / weight |
|---|---|
| Page title (top bar) | 28 / 600, −0.03em |
| Screen header title (Ticket, Run, Factory) | 23–24 / 600 |
| KPI number | 36 / 600 tabular |
| Stat-strip number | 32 / 600 tabular |
| Agent pass rate, gauge, evidence count | 30–34 / 600 |
| Donut centre total | 25 / 600 |
| Card title | 16.5 / 600 |
| Step / row title | 14.5–15.5 / 500 |
| Body, table cell | 14 / 400 |
| Meta, second line | 12.5–13 / 400 muted |
| Uppercase label (`.lbl`) | 11 / 600, 0.07em |
| Mono (event log, code, hashes) | 13 / 400 Geist Mono |
| Chart tick labels | 11 |

Rows: 56px in the Queue list and the Tickets/Runs tables, 60px in the Runs live rail, 46–54px in panels,
52px in the queue slot rows, 64px in the Run step list. Card padding 18–22, gaps 20, page gutter 24/28, radius 15 on cards, 9–10 on controls, 999 on pills.

## Screen → reference

| Screen | Copies |
|---|---|
| Queue | R11 frame (sidebar, grouped nav, centred search, green button, right rail); R11 Top Tools panel for the item list; R13 card/segmented-tab treatment for the selected-item detail; R05-style semi-donut for the median-latency gauge, sized to fill its card with the p90 under it. The three rail sections size to content and the lower two take the slack, so the rail runs to the frame edge as R11's does |
| Tickets | R15 model table (row sparkline replaced by the S0–S6 dots), R14/R15 KPI cards, R04 dark bulk bar |
| Ticket detail | R13 header-plus-stat-strip card, R13 Execution Flow on a dotted inset canvas (stage cards with tinted header strips carrying the run id, a sub-node under S4), R13 step-list proportions for the two panel columns |
| Runs | R11 KPI cards and full-height Live Activity rail (22 rows at 60px, top-aligned with the KPI row), R15 table with a per-row duration bar in place of R15's trend sparkline, R06 status-dot outcomes |
| Run detail | R13 in full: four-cell stat strip, step list with step 3 expanded, inputs/guard panels, Raw-output block with a segmented tab |
| Report | R15 layout: date range and 7d/30d/90d control in the top bar, R14 KPI cards, then two rows of three panels — spend line with median line and a drawn callout, donut with the 30-day total in the centre, stacked daily outcome bars; then the tag leaderboard (R11 Top Tools rows), an R02 hour × weekday latency heatmap on a five-step scale, its no-data cells hatched as R02 hatches its empty cells, with a legend that covers every state, and R15 model rows with per-row sparklines |
| Factory | R15 table for the manifest (Stage / Model / Tier / Budget, with a per-row budget bar in R15's trend slot), R12 agent cards with the pass rate as the card's one large figure and Open as the primary action, R09 switch rows for sandbox policy as a full-width four-up band |

## Word counts (`python3 tools/wordcount.py 02-observatory/index.html`)

```
queue     194 / 240  ok
tickets   179 / 200  ok
ticket    185 / 260  ok
runs      253 / 260  ok   (cap raised to 260 for this direction: R11 itself carries the rail)
run       163 / 260  ok
report    118 / 220  ok
factory   136 / 260  ok
```

`tools/wordcount.py` still prints `OVER` for Runs because its table holds the shared 220 cap; 253 is under
the 260 the orchestrator granted this direction for the live rail.

## Captures

14 PNGs in `captures/`, headless Chrome at 1600 wide, scale 1, both themes, one Chrome profile per shot.
Heights vary by screen because several screens are taller than 1000: queue 1270, tickets 1170, ticket 1210,
runs 1545, run 1205, report 1045, factory 1130 — each a little over the measured document height. Checked at 1440 and 1280: the Runs KPI icons drop out below
1540 so the KPI numbers never clip, and card headers clip their legend rather than overflowing.

## Review pass

Applied against `REVIEW.md` (34 findings) plus the orchestrator's five decisions. Per-finding notes are
appended to `REVIEW.md`; the structural changes are:

- **Runs (R1, R2, R3).** The live rail is now the right column of a grid that starts at the KPI row and ends
  with the table: 22 rows at 60px against R11's 13 at ~56px, so the column no longer leaves 648px of bare
  page. The table's `Started` column paid for it — the rail is now the only place the clock times live, the
  table is the ledger (duration, cost, outcome), and three rail rows (`run_c6f2`, `run_9d0e`) are runs the
  table does not carry. Outcomes use R06: a green dot plus "Pass", with the filled pill kept for Running,
  Blocked, Aborted and Fail.
- **KPI cards (T1).** Tickets and Runs cards carry Report's third line ("8 active", "of 38 closed",
  "1 running", "$38.52 shown"), so the 43px hole between number and sparkline is gone. Sparklines are one
  accent (the Fail card stays red, where red means something).
- **Ragged bottoms (K1, F3, P5).** Ticket detail is two panel columns — Artefacts left, Approvals over
  Assumptions right — which end within a few pixels of each other. Factory is one card per row (manifest
  table, agent cards, a full-width policy band). Report is two rows of three panels, each row stretched to a
  common height.
- **Report (P1–P7, decision d).** Range control moved into the top bar (four regions now). Donut centre is
  the $430.40 total, its ramp floored at 34%. The amber latency sparkline is now a neutral accent line with
  no fill. Model spend moved beside the leaderboard and an R02 heatmap — queue latency by hour × weekday,
  derived from the §2.6 latency histogram, with a labelled faster→slower scale — fills the third slot.
  "Not yet measurable" is one muted cell under the model rows.
- **Ticket detail (K2–K6).** Header and a four-cell stat strip are one R13 card ($18.40, 3h 40m, 4 of 5,
  11), the flow sits on a dotted inset canvas so the space around the cards reads as canvas, stage cards are
  down to two body lines with the run id in the tinted strip, "Plan v1" is struck through, and the light
  nesting is fixed by putting white cards on the page-coloured canvas.
- **Queue (Q1–Q6).** Slots are three 52px rows, not four boxes; the evidence line is number-led ("9 checks");
  the rail cards reached the main column's height (re-cut in the final pass below); the icon sits inside the Kind column so header and
  cells align; the disabled Approve is an outline button; the sixth by-kind cell is a kind (Control 1,
  Other 4), and the duplicate "10" chip is gone.
- **Light theme.** Page `#F1F2F4`, sidebar `#F7F8F9`, cards white, code blocks `#E7EAEE` — the sidebar, page
  and cards are now three surfaces and the Run detail blocks read as insets.

### Final pass (four remaining findings)

- **Table dead bands (Runs, Factory).** The Runs table put its slack in a `1fr` Stage column holding two
  characters, leaving a 423px hole in a 974px table; Factory left 585px. Both tables now size their columns
  to content and draw the slack: the Runs Stage cell carries a fixed 92px label plus a duration bar, and the
  Factory Budget cell carries a budget bar plus the figure — the slot R15 gives its trend column and R11
  gives its Top Tools rows. Largest gap on any row, measured in the captures: Runs 89px, Factory 92px.
- **Factory tier columns.** Three identical tier columns (14 of 21 cells repeated) become one Tier column
  carrying §2.7's own `all` / `1–3` and one Budget column; the card header reads "budget per stage", which is
  what the data says. Factory drops from 147 to 136 words.
- **Report heatmap.** The no-data cells are hatched on `--card-2` as R02 hatches its empty cells instead of
  sitting off the ramp as a sixth grey state, the ramp is folded to five steps, and the legend gained a
  hatched "No data" key. In dark, no-data now samples darker than the palest filled step rather than lighter.
- **Queue rail.** The three rail cards no longer stretch to a common height with their content centred
  (which left 205px and 173px of air). They size to content and the lower two absorb the slack into row
  height: 320 / 302 / 408px with largest voids of 47 / 63 / 23px (15% / 21% / 6%). The gauge fills its card at 278px wide
  with the figure centred on the arc and `p90 3h 10m` under it.
- **Not done:** the manifest table was not paired with the policy card. Four short columns carry about 300px
  of ink, so no width above ~600px avoids a 100px gap without something drawn in the slack; and pairing
  would leave the policy card 173px shorter than the table, which is the ragged bottom F3 removed.

### What is not fixed

- **R2 (rail / table overlap).** The rail is a stream of the same runs, differentiated by carrying the clock
  times the table dropped and two runs the table cannot show. Making every rail row an event the table lacks
  would mean inventing timings that BRIEF.md §2 does not contain.
- **Q1 (no large number in the Queue main column).** Softened rather than solved: the gauge dropped to 34px
  and the evidence block is set at 30px, so the rail no longer owns the only big number, but the list and
  the decision card still hold no chart. Moving the three rail cards into a top stat band would fix it and
  would cost the direction its R11 rail on this screen.

## Deviations and unfinished

- **Queue keeps §3's contents** (head row, list, detail card, three rail cards) and adds nothing from §4.2.
- **Report carries four chart types** (line, donut, stacked bars, heatmap) against the "one large chart"
  rule, because §3 names both secondary panels and decision (d) adds the heatmap.
- **Stage names are split across the R13 card** — the tinted strip carries `S3` and the run id, the body
  carries `Spec and plan`. At 144px per column the full string wrapped and broke the strip alignment.
- **Hashes appear in the Ticket detail Artefacts panel** (11 rows), which §3 requires, although §2 restricts
  short hashes to the ticket header, Run detail and the Factory manifest. They appear nowhere else.
- **Two tables carry a bar drawn from a column they already show** — a duration bar on Runs and a budget bar
  on Factory, both in the slot R15 gives its trend column. They exist because four to six short columns
  cannot fill a 974px or 1294px table without leaving a gap larger than any reference has; no new data.
- **The heatmap grid is derived, not given.** §2.6 supplies a queue-latency histogram over 50 decisions; the
  hour × weekday cells are a plausible distribution of those bands (fast midday weekdays, slow evenings and
  weekends), consistent with the stated 38m median and 3h 10m p90.
- **Runs is the one screen with real air left inside a card**: the Tickets/Run panels distribute their rows
  rather than leaving a hole, which reads as deliberate spacing at 1600 but is looser than the references at
  1280.
