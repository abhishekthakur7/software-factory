# Soft Factory UI mockups, round 2 rebuild: brief v2

This file supersedes BRIEF.md §3, §4, §6 and §7. BRIEF.md §1 (product), §2 (fake data, with the correction
block at its top) and §5 (technical spec: folder layout, hash routing, theme query, fonts, capture command)
still apply unchanged. On any conflict, this file wins.

## 0. Why we are rebuilding

The first build was rated 6/10 by the owner. Beside the reference screenshots the problems are plain:

- Two to four times the text of any reference. Our screens carried 400 to 620 visible words; the Mate orders
  screen (R04) has about 150, the Stealth overview (R11) about 250.
- Every row had two lines of small monospace metadata, every entity showed every field, every page had a
  subtitle and helper sentences. It read like a log viewer.
- Type sizes barely differed between title, body and meta. Nothing was big. Nothing had air around it.
- Six chip colours and monospace snake_case identifiers everywhere the references use one accent and
  sentence-case words.

Root cause: the builders never saw the references (they got text descriptions) and the reviewers audited
data against the brief instead of design against the references. Both are fixed now: the 17 images are in
`references/R01.png` … `references/R17.png`, and the review is a side-by-side.

**The bar:** a screen is done when it could sit in the reference set without looking like the odd one out.
Same air, same hierarchy, same restraint. If a reference shows less, we show less.

## 1. The references (view every one you are assigned with the Read tool; do not work from memory)

| Id  | What it is | Take from it |
|-----|------------|--------------|
| R01 | Light workflow builder: icon rail, node-library panel, dotted canvas, node cards with pill-labelled bezier edges, Console and Debug panels below, lime Run button | Canvas frame, node card, edge pill, console/debug treatment |
| R02 | Dark event-engagement dashboard: five KPI cards with a different mini-chart each, big line chart with callout, heatmap, bar rows | Chart variety, KPI card with chart inside, heatmap with axis labels |
| R03 | Light indigo e-commerce dashboard: three pastel-tinted KPI cards, area chart with dashed comparison and callout, donut with legend | Tinted KPI card, area chart with median line, donut legend layout |
| R04 | "Mate" orders table: dark sidebar, 32px title, filter chips, 8-column table with 60px rows, floating detail card with tabs and four actions, dark bulk bar, right rail with gauge and stat grid | The whole Workbench frame and table system |
| R05 | "ACRU" lime finance dashboard: 40px hero number, hatched inactive bars, segmented colour bar with legend, semi-donut gauge, goal rows | Hero number, segmented bar, hatched bars, semi-donut |
| R06 | Dark magenta/cyan analytics board: sales line with callout, invoice rows with status dots, heatmap, dotted map | Invoice-style rows, heatmap cell scale |
| R07 | Frosted credit-score screen on a tilted monitor: glass cards, huge score, month grid | Glass card treatment only (Canvas), nothing else |
| R08 | Neon learning hub: gradient course cards, gantt schedule, progress rail | Gantt rows only (Canvas Report); ignore the neon |
| R09 | Dark settings panels: segmented theme control, colour swatches, key-cap hotkeys, switch rows, member rows | Setting rows with switches and key-caps (Factory policy) |
| R10 | Synerque sidebar: 56px nav rows, 18px labels, workspace switcher box, collapsed icon rail, workspace list with 64px avatars | Sidebar proportions, switcher, workspace rows |
| R11 | "Stealth" dark agent monitoring: sidebar with grouped nav, three KPI cards with 36px numbers and sparklines, three-series line chart, Top Tools progress rows, Model Split bar, Live Activity rail with two-line rows | The whole Observatory frame, KPI cards, rail, chart |
| R12 | Light agents list: four KPI cards with icon circle, filter tabs, 3×2 agent card grid (name, subtitle, status dot, three key/value rows, Pause/Open buttons) | Agent cards, KPI cards with icon circle, tab filter |
| R13 | Dark "Agent Execution Viewer": four stat cells in a strip, step list with pills and one expanded step, execution flow of five step cards with coloured headers, Raw Output panel | Ticket and Run detail structure (Observatory), step cards |
| R14 | "What it costs" four tinted KPI cards on black, each with icon circle, label, 40px number, delta line, sparkline | KPI card proportions and tint |
| R15 | "Core AI" overview: KPI strip, spend line with callout, donut with centre total and legend, token bar chart, model table with per-row sparkline, recent activity rows | Report layout (Observatory), donut, model table |
| R16 | "Oreflow" node canvas: coloured-tab node cards with real content inside, cyan edges, review-queue node with dot matrices, gantt "Projects Time" | Coloured node tabs, dot matrix, gantt |
| R17 | "ChatDash" frosted voice-agent builder: node library grid, vertical flow with Matched/Fallback branch pills, right property panel with arc gauge, sliders and switches | Gate branch, property panel, node library grid |

## 2. Density budget (hard rules; the reviewer measures these)

Words
- Visible words per screen, counted by `tools/wordcount.py` over each `<section class="screen" id="s-…">`
  (app frame outside the sections is not counted): Queue 240, Tickets 200, Ticket 260, Runs 220, Run 260,
  Report 220, Factory 260. These caps are roughly the reference density plus a little; being well under is
  better than being just under.
- Not allowed anywhere: page subtitles or descriptions under a title; helper or explanatory sentences
  ("a tag is required…", "approve is disabled because…"); attestation quotes; footer status lines under
  tables; "not your role" annotations; version chips in the nav; long hashes (short form `1d9f…e4` only, and
  only in the Ticket header, Run detail and Factory manifest); units repeated in every cell (put the unit in
  the column header); legends that repeat what the chart already labels.
- Identifiers become words. The product's snake_case kinds and states are shown in sentence case:
  Packet approval, Plan approval, Red check, Escalation, Control event, Questions, Eligibility, Rubric
  inspection, PR outcome, Manual pause; Intake, Context, Clarifying, Planning, Plan review, Implementing,
  Checks, Review, PR opened, Merged. Stages read "S3 Spec and plan". The raw identifier may appear only in
  Run detail inputs and the Factory manifest table.
- Monospace is for console/log blocks, hashes and code. Not for ids, chips, times, costs or ages. Ticket keys
  and run ids sit in the UI font, muted, tabular numerals (R04 order numbers, R11 run ids).

Rows and tables
- One line per row. Two-line rows only where the copied reference has them (R11 live rail, R12 card
  header, R10 workspace list), and then the second line is one short muted phrase.
- Row height 56 to 64px in primary tables (R04), 48 to 52 in rails and compact lists. At most eight columns.
  At most one status pill and one icon per row. Trailing "···" only where the reference has it.
- Fixed-width slots for checkbox, icon, pill and trailing action so columns align. Numbers right-aligned.
  Titles truncate with an ellipsis and never wrap.

Type (choose sizes inside these bands; the bands are measured from the references at 1600px)
- Page title 28 to 32 / 600. Card title 16 to 18 / 600. Body 14 to 15 / 400. Meta 12 to 13 muted.
  KPI numbers 32 to 40 / 600 tabular. Uppercase labels 11 to 12 / 500 with 0.06em tracking, used at most
  once per card. Weights 400 / 500 / 600 only. Nothing below 12px except chart tick labels.
- The size jump between levels must be visible in a capture. If a title and its body look the same size at
  50% zoom, the scale is wrong.

Space
- Card padding 20 to 24. Gap between cards 20 to 24. Page gutter 28 to 32. Sidebar 240 to 260 wide with 44 to
  48px nav rows (R04, R10). Radius 14 to 16 on cards, 8 to 10 on controls, 999 on pills.
- Air is allowed. A card may hold one number and one chart. Fewer things, bigger.
- At most five regions on a screen (title bar counts as one). The reference screens have three to five.

Colour
- One accent. Semantic: pass green, fail red, warn amber, plus the accent for running or selected. That is
  the whole palette apart from neutrals. No violet-for-running, no blue-for-info, no per-stage rainbow
  except Canvas node tabs (low saturation, R16).
- Pills: tinted background at 10 to 14% with the semantic colour as text. One pill style for the whole
  direction. No outlined chips next to filled chips in the same row.
- Dark theme is tuned (lighter surfaces for elevation, borders at 8 to 12% white, accents desaturated a
  step), never inverted.

Charts
- One large chart per screen at most, plus sparklines inside KPI cards. Every chart: axes or a baseline,
  three to six tick labels, one callout drawn in (R03, R11, R15). Sparklines have no axes.
- Built from the §2 values. Bars 2px radius max, lines 1.5 to 2px, area fills at 8 to 15% alpha.

## 3. Screens (what appears; anything not listed stays out)

Screen ids in `index.html`: `<section class="screen" id="s-queue">` … `s-factory`. Routing per BRIEF.md §5.
The app frame (sidebar, top bar) is shared: wordmark, workspace switcher "Northwind Payments", nav Queue
(badge 10) / Tickets / Runs / Report / Factory, search, theme toggle, runner pill "runner-01 · running",
Priya Raman at the bottom. Nothing else in the frame.

1. **Queue** `#queue`. Title "Queue", actions (Export, History). Filter chips (Bucket, Kind, Ticket, All
   filters). Right rail: median latency 38m gauge, by-bucket segmented bar with three legend rows, by-kind
   2×3 grid. The 10 items (BRIEF.md §2.2) as rows: kind with icon, ticket key, title, age, bucket dot. Item 1
   selected, its detail as the direction's card: title, "T-0412 · Packet approval · 58m", three slot rows
   (initials, name, role, approved 14:12 / approved 14:19 / open), one evidence line "9 checks · 8 pass ·
   1 waived" with a link, four actions (Approve disabled, Request changes, Send back, Abandon). Tabs
   Packet / Evidence / Slots with Packet active; the other tabs are not rendered.
2. **Tickets** `#tickets`. Title, New ticket action. Four KPI cards (Open 12, In queue 10, Merged 30d 31,
   Cost 30d $430.40). Filter chips (State, Tier, Class, Repo). Table of 12: checkbox, key, title, repo, tier,
   state pill, S0–S6 as seven dots, cost, age. T-0412 selected, one row hovered, three checked with the dark
   bulk bar (Selected: 3 · Export · Send back · Abandon).
3. **Ticket detail** `#ticket`. Header: key, title, state pill, tier, cost $18.40, elapsed 3h 40m, one
   action (Open queue item). Hero: the S0–S6 stages as seven cards in a row (stage, run id, duration, cost,
   outcome), base advance as a small node under S4, review gate after S6 with "2 of 3 slots". Three panels
   below: Artefacts (11 rows: name, version, short hash), Approvals (5 rows: who, role, time or pending),
   Assumptions (3 rows). Nothing else.
4. **Runs** `#runs`. Title. Four KPI cards (Runs today 43, Pass 35, Fail 5, Settled $72.90). Filters
   (Outcome, Stage, Ticket). Table of 20 (BRIEF.md §2.5): run id, ticket, stage or kind, started, duration,
   cost, outcome pill. run_d204 running with a pulse, run_7f3a selected. Child runs get an indent, no
   "child of" text. Observatory adds the live rail (R11).
5. **Run detail** `#run`. Header: run id, ticket, "S4 Implementation", outcome pill, model, runtime. Stat
   strip (Tasks 6, Fix rounds 1, Duration 31:05, Cost $9.85 of $12.00 with a bar). Left: the six tasks as a
   step list, task 3 expanded showing the failing check and the fix in four lines. Right: inputs by hash
   (5 rows), guard decisions as three numbers, event log as one monospace block of at most ten lines.
6. **Report** `#report`. Title, range control 7d / 30d / 90d. Four KPI cards (Cost per merged PR $13.70 median,
   Merged 31 of 38 closed, First-pass check rate 71%, Median queue latency 38m). The baseline row from §2.6
   is one muted line under the KPI row with its exact label. Hero: the
   31-day cost line with median line and the 26 Aug callout. Two secondary panels: runs by outcome as
   stacked daily bars, stage cost share as a donut with legend. One list: tag leaderboard, five rows. Model
   spend as three rows. "Not yet measurable" is one muted cell, not a paragraph.
7. **Factory** `#factory`. Header: manifest v14, short hash, fixture gate pass, one action (Open PR).
   Stage × tier table (7 stages × 3 tiers: model and budget). Five agent cards (R12: name, model, status dot,
   three key/value rows, two buttons). Sandbox policy as four switch rows (R09). Nothing else.

## 4. Directions

Each direction keeps its palette and fonts from BRIEF.md §7 unless stated. What changes is the layout
source: every screen copies a named reference's structure and proportions.

### 4.1 Workbench (`01-workbench`), light-first. References: R04 R10 R12 R03 R05 R09
- Frame: R04 exactly (dark sidebar, white content, 32px title, Import/Export style buttons top right).
  Sidebar rows and switcher from R10.
- Queue: R04. The table, the floating detail card (drag handle, open and close icons, tabs, four buttons),
  the right rail (gauge, status bar, 2×3 stats).
- Tickets, Runs: R04 table with R12 KPI cards above and the R04 bulk bar.
- Ticket detail: header like R04's title row; stage cards like R12's agent cards laid in a row; the three
  panels as R04's rail cards.
- Run detail: R13 structure rendered in R04's light system (stat strip, step list, output block).
- Report: R03 tinted KPI cards, R03 area chart with dashed median, R05 hatched stacked bars and semi-donut.
- Factory: R12 agent cards, R09 switch rows, R04 table.
- Type: Plus Jakarta Sans (already in `assets/`), Geist Mono only for the Run detail log and hashes.

### 4.2 Observatory (`02-observatory`), dark-first. References: R11 R13 R14 R15 R02 R06
- Frame: R11 exactly (grouped nav, search in the top bar, green primary button, Live Activity rail).
- Queue: R11 layout: KPI row, the item list as R11's Top Tools panel style, detail as an R13 step list, the
  live rail on the right.
- Tickets: R15's model table (row sparkline replaced by the S0–S6 dots).
- Ticket detail: R13's Execution Flow as the hero (stage cards with coloured header strips), R13's step
  list for approvals, artefacts as R11's Recent Changes rows.
- Runs: R11 KPI cards above an R15 table, live rail right.
- Run detail: R13 in full (stat strip, step list with one expanded, Raw Output block).
- Report: R15 layout: R14 KPI cards, spend line with callout, donut with centre total, R02 heatmap for
  latency by hour, R15 model table with per-row sparkline.
- Factory: R15 table for agents, R11 Recent Changes for change control, R09 rows for policy.
- Type: Geist (already in `assets/`), Geist Mono for the output block and hashes. Body 14, not 12.

### 4.3 Canvas (`03-canvas`), light-first. References: R01 R17 R16 R13 R07
- Frame: R01 exactly (icon rail, 280px panel, canvas with dotted grid, top bar with tab, Save / Share /
  Run in lime). Panels frosted per R07/R17 at 70% white.
- Ticket detail: R01 canvas with seven stage nodes (R16 coloured tabs, one line of content each) and labelled
  edges, R17's gate branch (approved / send back pills), R01 Console and Debug below but each at most eight
  lines.
- Run detail: six task nodes with R17's branch for the fix round, R17's property panel (arc gauge, three
  numbers, two switches), console below.
- Queue: R01 panel holds the list; the canvas holds one frosted detail card (R17 property panel treatment)
  and the ticket's mini pipeline.
- Tickets, Runs: one frosted card holding the table; R01's rounded type.
- Report: R16 gantt for today's runs on an 11:00–15:00 axis, R16 coloured-tab cards for the KPIs, hero line
  in a frosted card, R16 dot matrix for queue by bucket.
- Factory: R17 node library grid for the manifest, R16 cards for agents, R09 rows for policy.
- Type: Outfit (already in `assets/`), JetBrains Mono for console and hashes.

## 5. Process (builders and reviewers)

Builder
1. Read this file, BRIEF.md §1, §2 and §5. View every reference image assigned to your direction with the
   Read tool. Then view the old capture set in `_previous/` only if you want to see what not to do.
2. Start `index.html` from a blank file. You may copy the `@font-face` block, the token skeleton and the
   hash router from `_previous/<dir>/index.html`. Nothing else.
3. Build all seven screens, both themes. Capture per BRIEF.md §5 with the same filenames as before
   (`captures/01-queue-light.png` … `07-factory-dark.png`); the gallery links to those paths.
4. Run `python3 tools/wordcount.py <dir>/index.html`; every screen must be under cap.
5. For at least four screens make a side-by-side against the reference you copied:
   `python3 tools/sidebyside.py references/R04.png <dir>/captures/01-queue-light.png <scratch>/sbs-queue.png`
   and look at it with the Read tool. Fix what differs in proportion, size, air and restraint. Do at
   least two full capture-and-fix passes.
6. Write README.md: three sentences on the direction, the token table, type scale, the screen → reference
   map, the word counts, and anything unfinished. No self-praise.

Reviewer (separate agent, fresh context)
1. Read this file. View the direction's references. Run the word counter.
2. For every screen, in both themes, compose the side-by-side against the reference the builder named and
   look at it. Score each screen 1 to 10 on five axes: hierarchy, density, spacing and alignment, colour and
   contrast, craft (charts, icons, pills, states). Every score below 8 needs a finding that cites the
   reference measurement ("R04 rows are ~60px, ours ~44") and the fix.
3. Write the findings to `<dir>/REVIEW.md` and return the per-screen scores. The orchestrator sends the
   findings to the builder, who fixes and recaptures; the reviewer re-scores once.

Pass: every screen at or above 8 on every axis, every word count under cap, both themes captured.
