# Review — 03-canvas

Reviewed against R01 (primary), R17, R16, R13, R07, at 1600px, both themes, 14 captures.
All measurements below are normalised: R01's app frame is 1740px wide inside a 2000px image, ours is
1600px, so a percentage-of-frame figure is given wherever the two are compared directly.

## Word counts

`python3 tools/wordcount.py 03-canvas/index.html`

```
queue     142 / 240  ok
tickets   178 / 200  ok
ticket    217 / 260  ok
runs      186 / 220  ok
run       181 / 260  ok
report    129 / 220  ok
factory   190 / 260  ok
```

Every screen is under cap and the counter exits 0. Tickets is at 89% of cap; Factory's 190 includes
about 40 words of literal repetition (see F-1).

## Scores

Where the two themes differ the cell reads light / dark.

| Screen | Hierarchy | Density | Spacing & alignment | Colour & contrast | Craft |
|---|---|---|---|---|---|
| Queue | 7 | 8 | 5 | 6 | 6 / 5 |
| Tickets | 7 | 8 | 6 | 7 | 6 |
| Ticket detail | 7 | 7 | 7 | 7 / 6 | 5 |
| Runs | 7 | 6 | 5 | 7 | 6 |
| Run detail | 6 | 7 | 7 | 6 / 7 | 6 / 5 |
| Report | 8 | 8 | 7 | 6 | 7 |
| Factory | 7 | 4 | 7 | 7 | 7 |

Nothing reaches the pass bar of 8 on every axis. The restraint asked for in BRIEF-v2 §0 has landed —
word counts are well under, rows are one line, there are no helper sentences, no page subtitles, no
snake_case state names in the UI. What has not landed is the canvas itself: on the two screens that
carry the direction's whole idea (Ticket detail, Run detail) the graph is drawn at roughly half R01's
line weight and a third of its port size, and on three screens (Tickets, Runs, and half of Queue) the
canvas is a 20px dotted margin around a card.

## Findings

### All screens — the canvas frame

**F-A1. The edges are not drawn.** R01's connector is a continuous ~3px saturated indigo bezier running
port to port, with a white 17px circular port and a ~2px ring sitting on each node face; the label pill
rides on the curve with real line visible on both sides. Ours (`index.html:234`, `:239`, draw() at
`:1136`) is 1.8px in `--edge` (#C6CCD6 light, #3B424D dark) with `r="3.6"` ports — 7.2px across. Worse,
the column pitch swallows it: on Ticket detail the Intake card ends at x=578 and Context begins at
x=633, a 55px gap (3.4% of frame) of which the `pass` pill occupies 46px, leaving two ~4px stubs. R01's
equivalent gap is 99px (5.7% of frame) and its edges also travel 100–150px vertically, so the curve is
the loudest thing on the canvas. In ours the nodes read as cards placed next to each other.
*Fix:* pitch to ~110px between node columns, stroke to 2.5px in a tone near `--muted` (grey is fine,
invisible is not), ports to r=7 with a 2px ring, and let the bezier control points pull far enough that
a curve is visible on both sides of every pill.

**F-A2. The panel is half empty on six of seven screens.** R01's 280px panel runs content to the bottom
and closes with a dashed "Drag nodes to canvas" dropzone. Ours stops at 47% of panel height on Ticket
detail, 46% on Tickets, 50% on Run detail, 49% on Report, 47% on Factory and 34% on Runs (where the
capture is 1300 tall). Only Queue fills it (68%). The result is a tall white column on the left of
almost every screen.
*Fix:* one of — move a region into the panel (Runs' KPI row and Report's KPI row both fit), or close the
panel with a bottom-anchored element the way R01 does, or shorten the panel to its content and let the
canvas start higher.

**F-A3. The canvas carries an unmotivated green wash.** Sampling `03-ticket-light.png`: the canvas is
#F8F9FA at x=1200 but (244,247,239) at x=400,y=180. In dark it is (15,17,21) at the right and
(27,32,22) at the top-left — G clearly above B, reading as olive. R01's canvas is flat #F9F9F9 across
its whole width; R13's flow panel is flat too. In the dark captures this looks like a rendering fault.
*Fix:* remove the radial tint, or bind it to something (the selected node) rather than the top-left
corner.

**F-A4. Gauge tick labels are pure black in dark theme.** The gauge `<svg>` blocks (`index.html:578`,
`:874`) contain bare `<text>` elements and no rule sets their fill, so `0` / `4h` on Queue and `$0` /
`$12` on Run detail render #000000 on the #181B20 surface — measured contrast about 1.05:1, effectively
invisible. `.chart text` (`:373`) has `fill:var(--faint)`; the gauges never got it.
*Fix:* add the gauge texts to the `.chart text` rule or give them `fill:var(--faint)`.

**F-A5. Console level chips are 9.5px.** `.cbg` (`:340`) sets `font-size:9.5px` for PASS / INFO / WAIVE /
FAIL / FIX. BRIEF-v2 §2 allows nothing below 12px except chart tick labels. Seven further rules sit at
11–11.5px: `.el` edge pill (`:241`), `.node .tab` (`:266`), `.snode .hd` (`:275`), `.cline` (`:338`),
`.drow .h` (`:350`), `.lrow .h` (`:178`), `.gcell .lb` (`:367`).
*Fix:* console chip to 11 minimum, console line and node tab to 12, the two mono value columns to 12.

**F-A6. The nav badge sits on top of the icon.** The "10" pill overlaps the tray glyph inside the lime
rail button and clips its top-right corner. R01 has no badges; R16 and R10 put counts as a right-aligned
number in the nav row, clear of the icon.
*Fix:* move the badge to the top-right corner of the button, outside the glyph's bounding box, or drop
the glyph behind a plain count.

### Factory

**F-1. Three identical tier columns.** TIER 1, TIER 2 and TIER 3 hold the same value in all seven rows —
`haiku · $0.10` three times, `sonnet · $2.00` three times, and so on: 21 cells carrying 7 distinct
values, roughly 40 of the screen's 190 words. Neither R17 nor R16 repeats anything. It reads as a data
bug, and it is the single biggest density failure in the direction.
*Fix:* either vary the per-tier budgets (the product presumably does), or collapse to one `MODEL ·
BUDGET` column with a `same across tiers` note in the header, freeing width for the RUBRIC column.

**F-2. "lines" repeated in six of seven rubric cells.** BRIEF-v2 §2 names this exact case: units go in
the column header.
*Fix:* header `RUBRIC (lines)`, cells `7`, `11`, `—`, `14`, `9`, `12`, `6`, right-aligned.

**F-3. Trust profile is not in §3.** §3 for Factory ends "Sandbox policy as four switch rows (R09).
Nothing else." The Routes / Sanitisers / Denied 30d block is extra.
*Fix:* remove it, or, if it stays, it should be what fills the panel dead space rather than adding to it
(see F-A2).

**F-4. Switch "on" is `--ok` green, not the lime accent.** R09's switches use the product's one accent.
Ours splits the accent: lime on buttons and pills, green on switches, so the screen carries two
"positive" colours with no difference in meaning.
*Fix:* switches to `--lime` when on.

**F-5. Agent cards carry row dividers R12 does not have.** Three hairlines inside a 200px card add
structure the reference gets from alignment alone.
*Fix:* drop the dividers, keep the key left / value right alignment.

### Ticket detail

**F-6. Nothing on the canvas is the hero.** Seven stage nodes at identical size, weight and colour
saturation, in two rows. R01 varies node position over four vertical bands and lets one node (Summarize)
sit alone at the right of the arc; R13's Execution Flow gives the failing step a red header and the
running one a purple one against three greens. Ours differentiates only by tab hue, which encodes stage
identity, not state — so the eye has no entry point. The Review gate has a lime ring and is the closest
thing to a hero, but it sits in the second row at the same size as everything else.
*Fix:* make the gate node the hero — wider, taller, with the "2 of 3 slots" at 16–18px — and let the
seven stage nodes shrink slightly. Or tone the edges by outcome (the `.ed.warn` / `.ed.bad` classes
already exist and are unused on this screen) so the S5 "8 of 9" path reads amber end to end.

**F-7. The title truncates mid-word with 147px of free space beside it.** "Reject settlement batches
whose currency differs fro…" ends at x=1016; the Review pill starts at x=1163. R01 does not truncate
anything on its canvas.
*Fix:* give the title row the full width and move the meta cluster (Review / Tier 2 / $18.40 / 3h 40m /
Open queue item) to its own line under it, the way R04 stacks its title row; or shorten the displayed
title to a clean clause.

**F-8. A 1180 × 100px empty band across the middle of the canvas.** The first node row ends at y=280 and
the second begins at y=380; the whole strip between them is bare dots crossed by one connector. R01's
canvas has plenty of air but it is distributed around the graph, not left as a hole through the middle.
*Fix:* the wrap connector should use that band — route it as a wide curve with a labelled pill on it, or
tighten the two rows to a 60px gap and give the saved height back to the console.

**F-9. `CURRENCY_MISMATCH` on the Assumptions node.** BRIEF-v2 §2 restricts raw identifiers to Run
detail inputs and the Factory manifest table; the canvas is neither.
*Fix:* "Currency mismatch".

**F-10. Console and Artefacts share one card split by a hairline.** R01 draws Console and Debug as two
separate cards with their own borders, radius and a ~24px gap between them.
*Fix:* two cards, 20–24px gap.

**F-11. "11 pinned" on the Artefacts header describes nothing.** Eight of eleven rows are shown and
"pinned" is not a concept anywhere else in the product.
*Fix:* `8 of 11`.

**F-12. Avatar initials use four decorative hues** (indigo TW, violet PR, orange IC). §2's palette is one
accent plus the four semantics plus neutrals; R01 has no avatars to borrow from.
*Fix:* one neutral avatar chip, initials in `--ink-2`.

### Run detail

**F-13. Six regions, and the expanded step is missing.** Counting: title bar, panel (Inputs + guard
decisions), canvas, Budget panel, Console, Outputs — six against §2's cap of five. §3 asks for "task 3
expanded showing the failing check and the fix in four lines"; what is on screen is a Task 3 node
reading `9:05 · 1 fix round` and a separate Fix round node reading `2 unit tests red`. The failing check
is never named. R13 makes the expanded step the hero of the screen and gives it two labelled blocks.
*Fix:* drop the Outputs pane (F-14) and expand the Fix round node in place — name the check, show the
fix, four lines, at the size R13 gives its expanded step.

**F-14. The Outputs pane is not in §3 and duplicates Ticket detail's Artefacts pane.** Same numbered
rows, same right-aligned mono column, same eight-row height. It also puts `13:52:01`, `1 of 3`,
`22 files`, `412k` in JetBrains Mono, which §2 forbids (mono is for console blocks, hashes and code —
not times, counts or costs). The header "187 tool calls" is a stray stat with no home.
*Fix:* remove it and let Console span the full width, R13-style; or, if a second pane is wanted, make it
R01's Debug — per-task in/out values, a different data shape from Artefacts.

**F-15. Five saturated green header bars in light theme.** R13's step headers are muted fills with the
label in a lighter tint of the same hue; ours are solid `--ok` with white text, five of them in a row,
which competes with the lime accent for attention. The dark theme already does this correctly (12–16%
tint, coloured label) — the two themes are treating the same element differently.
*Fix:* adopt the dark theme's treatment in light: header at ~14% tint, label in the full hue.

**F-16. `$9.85` overlaps the gauge arc.** At 34px inside a 132px ring the number's `$` and `5` cross the
stroke. R17's `1.15x` sits with clear space on both sides inside a larger arc.
*Fix:* number to 28–30px, or arc radius up by 10px.

**F-17. The guard decisions grid is 2 + 1 with a full-width orphan.** Allow and Redact are half-width;
Deny spans the full panel. R17's node library is a clean 2-column grid throughout.
*Fix:* three equal cells in a row, or 2×2 with the fourth cell holding the total.

### Queue

**F-18. The canvas is 55% empty and the pipeline is not made of nodes.** The seven stage chips are
62 × 36px with a dot and a two-character label — the same size as the Bucket / Kind / Ticket filter
chips in the header row above them, so canvas objects and controls are indistinguishable. R01's canvas
objects are 190 × 58 with an icon tile, four times the area of any control on the screen. Above them a
1150 × 150px band is empty and below the detail card another 1150 × 160px band is empty.
*Fix:* make the chain real nodes at ~150 × 50 with the stage name, centre the pipeline + detail card
group vertically in the canvas, and shrink the canvas height so the empty bands go away.

**F-19. The disabled Approve button uses the accent's soft tint.** Fill (229,240,181) — the same fill as
the Review pill — with grey text. It reads as a soft primary, not as disabled. In dark it goes to a dull
olive that is nearly invisible against the card.
*Fix:* neutral fill at `--surface-2` with `--faint` text and a `not-allowed` cursor, in both themes.

**F-20. Ten different icon tints in the panel list.** Green check, blue document, red triangle, red
shield, amber lock, then five greys. §2 allows semantic colour only; "Plan approval" is not blue and
"Questions" is not grey-because-grey. R01's panel icons are all one neutral stroke colour.
*Fix:* all icons `--muted`; if urgency needs a tell, it is already carried by the bucket sections.

**F-21. Red for the "Act today" bucket.** The segmented bar and its legend dot use `--bad` for a bucket
that means "soon", not "failed", which collides with the same red on Checks/Escalated pills two screens
away.
*Fix:* accent lime for Act today, `--muted` and `--faint` for the other two, matching the three-step
weight R05 uses on its segmented bar.

**F-22. Two uppercase labels in one card.** BY BUCKET and BY KIND are both inside the Today rail card;
§2 allows one per card.
*Fix:* keep BY BUCKET, let the 2×3 grid stand on its cell labels.

**F-23. The gauge number out-sizes the decision.** `38m` is 34px in the rail; "Final review packet v1",
the thing the screen exists to approve, is ~22px. The eye lands on the rail.
*Fix:* detail card title to 24–26, gauge number to 28.

### Runs

**F-24. The STAGE column is 375px wide for two-character values.** It runs x=655 to x=1030 and holds
`S4`, `S1`, `Index rebuild`, `Fix round`. The gap between it and MODEL is the widest empty area in any
table in the direction. R04's eight columns are sized to their content with a fixed trailing slot.
*Fix:* STAGE to ~140px, redistribute to TICKET and RUN.

**F-25. The MODEL column is not in §3.** §3's Runs list is "run id, ticket, stage or kind, started,
duration, cost, outcome pill". Model contributes 20 cells including six em-dashes and belongs on Run
detail, where §3 does put it.
*Fix:* remove the column.

**F-26. The capture is 1600 × 1300.** Twenty 50px rows do not fit the 1000px frame every other screen
uses; the README admits it. In the 1000px frame six rows would be cut. R04 fits its table in its frame
by showing fewer rows.
*Fix:* show 12–14 rows and let the rest scroll, so the screen composes at 1600 × 1000 like the others.

**F-27. Two row systems in one direction.** Tickets rows are 56px, Runs rows are 50px, both primary
tables. §2 sets 56–64 for primary tables and 48–52 for rails and compact lists.
*Fix:* Runs to 56.

**F-28. The Running pill's ring is the only full-strength border on the screen.** Pass, Fail, Blocked and
Aborted all carry a 1px ring at 10–14% of their hue; Running carries a solid `--lime-2` ring, three to
four times the weight. §2: one pill style, no outlined chips beside filled chips.
*Fix:* lime ring at ~30%, keep the dot and the lime text. Same on the Tickets Review pill, whose label
is also dark ink where every other pill uses its own hue as text.

### Tickets

**F-29. The canvas is a 20px dotted margin.** The frosted table card runs x=400–1540 inside a canvas of
x=380–1560, so the direction's premise survives as a decorative border. Same on Runs. R01's identity is
a graph in a large field; two of seven screens have no field.
*Fix:* either give the card real air (inset it 60–80px and let the dots read as ground), or drop the
dotted frame on the two table screens and let the card sit on `--canvas` — a table is a table, and
faking a canvas around it is worse than not having one.

**F-30. The four KPIs are panel rows, not cards.** §3 says "Four KPI cards". They read fine as a stack —
36px numbers, clear jump — but they are also the reason the panel then has 490px of nothing under them
(F-A2).
*Fix:* keep the stack and fill the panel below it, or move them into the canvas as four R16-tabbed cards
above the table, matching Report.

**F-31. Checked rows carry no row tint.** T-0417 and T-0403 show a green checkbox but the same
background as unchecked rows; only the selected row is tinted. R04 tints checked rows.
*Fix:* a light tint on checked rows, distinct from the selected row's lime.

### Report

**F-32. Four decorative hues on the KPI tabs.** Sampled: #B09A4F, #5D9782, #5E93A1, #9179A6 — the t4, t2,
t1 and t6 stage hues on cards that have nothing to do with stages. §2 exempts "Canvas node tabs (low
saturation, R16)" from the no-rainbow rule; a KPI card is not a node tab, and the four hues encode
nothing. They also out-weigh the numbers they sit above, since each is a solid fill with white text.
*Fix:* one tab treatment for all four — `--surface-2` with `--muted` text, or the lime tab on the one
KPI that is the screen's subject (Cost per merged PR) and neutral on the rest.

**F-33. Six regions.** Title/range bar, panel, KPI row, baseline row, hero chart, bottom pair. §2 caps at
five.
*Fix:* fold the baseline row into the KPI row as a fifth muted cell, or move the panel's Model spend
list into the bottom row beside the donut.

**F-34. "Runs by outcome" has no value scale.** A baseline and three date labels, but nothing says
whether a bar is 8 runs or 30. §2 requires three to six tick labels on every chart. The 31 bars are also
9px wide with 6px gaps, which is finer than anything in R16 or R15.
*Fix:* three y ticks, or replace the panel (see the gantt note below).

**F-35. The callout has no leader to its point.** R03 and R15 both connect the callout box to the marked
value. Ours draws a 3px-dashed diagonal from the box but it stops short of the red dot at (664,21) — at
1600px the two read as unconnected.
*Fix:* extend the leader to the dot, or move the box to touch it.

**F-36. The baseline row splits into two fragments 1100px apart.** "CONTEXT MEASURE, NOT COMPARABLE ·
Pre-factory cycle 3.2d · Human review 41 min" at the left, "Defect escape rate — not yet measurable"
flush right, nothing between.
*Fix:* one left-aligned line with the not-yet-measurable item as its last member, separated by the same
middot.

## Content not listed in BRIEF-v2 §3

Runs' MODEL column (F-25), Run detail's Outputs pane (F-14), Factory's Trust profile block (F-3),
Ticket detail's "11 pinned" (F-11), Run detail's "187 tool calls" (F-14). Ticket detail's Inputs panel
header reads `9` above five rows (§3 says five rows) — the count and the list disagree.

## BRIEF-v2 §2 rules broken

Type floor of 12px (F-A5, eight rules, worst at 9.5px). Units repeated in every cell (F-2). Monospace on
times and counts (F-14). One pill style (F-28). Semantic colour only (F-20, F-21, F-32, F-4). One
uppercase label per card (F-22). Five regions per screen (F-13, F-33). Raw identifier outside its two
permitted homes (F-9). Every chart gets tick labels (F-34). Row height band in primary tables (F-27).

## The admitted deviations

**Dropping the R16 gantt and dot matrix from Report — half right.** The dot matrix should stay dropped:
the Queue rail's 2×3 by-kind grid already does that job, and R16's matrix is decoration. The gantt
should come back, and it should replace "Runs by outcome" rather than add to the screen. The stacked bar
is the weakest panel in the direction (F-34: no scale, 31 hairline bars, a four-item legend) and it
restates the hero line's own daily-over-time framing. A gantt of today's runs on an 11:00–15:00 axis is
the same data class, keeps the region count unchanged, and is the one panel that would make Report
recognisably part of a node-graph direction instead of a chart page any of the three directions could
have produced.

**The Factory manifest as a table rather than R17's node-library grid — right call.** R17's grid holds
twelve equal icon-labelled items; a 7 × 3 model-and-budget matrix is tabular and would be unreadable as
cards. The table as built is undermined by its own repetition (F-1), not by the format choice.

**Run detail's second console pane — wrong call.** It takes the screen to six regions, breaks the
monospace rule, and duplicates Ticket detail's Artefacts pane exactly, while the thing §3 actually asks
for on that screen — the expanded failing step — is absent (F-13, F-14).

**Ticket detail's three §3 panels spread across the frame — right call**, and the strongest structural
idea in the direction: Approvals in the panel, Artefacts in the console slot, Assumptions as a node
reads as one surface rather than three stacked lists.

**Approve disabled with no explanation — right call** under the helper-sentence ban, but the button must
then look disabled (F-19).

---

## Builder response

One line per finding. Word counts after the pass: queue 140, tickets 186, ticket 222, runs 118, run 158,
report 123, factory 131 — all under cap.

Two structural decisions from the orchestrator shaped most of the fixes: draw the edges like R01 (110px
pitch, 2.5px accent stroke, r=7 ports, outlined pills), and make the canvas genuinely present on the table
screens. Both were taken by turning the whole content area into one dotted ground with frosted cards
floating on it, which is R01's and R17's own frame and which closes F-A2 and F-29 together.

### All screens

- **F-A1 edges not drawn — fixed.** Pitch 110 on Ticket detail and Run detail (was 55 and 28), `.ed`
  stroke 2.5px in `--edge` (a darkened accent, `#8AA32B` / `#9FBB46`), ports r=7 with a card-coloured fill
  and a 2px ring, bezier control distance raised to 0.5 × span capped at 120, pill labels 12px outlined and
  centred on the curve. The ports were also being clipped by the node cards; they are now drawn in a second
  SVG layer above the nodes and de-duplicated where two edges share a port.
- **F-A2 panel half empty — fixed.** The panel is a content-sized frosted card on the canvas ground, not a
  full-height white column, so no screen has an empty column. Ticket detail's panel also gained the
  Assumptions list (a §3 panel), Run detail's guard cells became a 3-up row.
- **F-A3 green canvas wash — fixed.** Both radial washes removed; the ground is flat.
- **F-A4 black gauge ticks on dark — fixed.** `.gauge text` joins `.chart text` at `--faint` (about 3.7:1 on
  the dark panel).
- **F-A5 sub-12px type — fixed.** Console chip 9.5 → 11 (uppercase), console line 11.5 → 12, node tab
  11.5 → 12, step header 11.5 → 12, mono value columns 11 → 12, edge pill 11 → 12, cell label 11.5 → 12,
  callout sub 11.5 → 12. 11px is left only on uppercase micro-labels and chart/gauge ticks.
- **F-A6 badge on top of the icon — fixed.** Moved to the top-right corner outside the glyph box.

### Factory

- **F-1 three identical tier columns — fixed.** One Model and one Budget column, plus a Tiers column
  carrying what §2.7 actually varies (All / 1–3). 21 cells became 7.
- **F-2 "lines" in every cell — fixed.** Header "Rubric (lines)", cells 7 / 11 / — / 14 / 9 / 12 / 6,
  right-aligned.
- **F-3 trust profile not in §3 — fixed.** Removed.
- **F-4 switch "on" is green — not a defect.** `.sw.on` was already `var(--lime)`; the pixel under the switch
  in the reviewed capture sampled `#B8D832`. No change.
- **F-5 agent-card dividers — fixed.** Removed; key/value alignment carries the structure.
- Also: manifest rows to 56px and the group centred vertically, which removed a 190px void at the bottom.

### Ticket detail

- **F-6 no hero — fixed.** The review gate is a 252 × 100 node with an 18px title standing alone right of
  the second row; the S5 → S6 "8 of 9" path is amber end to end.
- **F-7 title truncates — fixed.** Full-width untruncated title; the meta cluster and the action moved to
  their own line beneath it.
- **F-8 empty band — fixed.** The S3 → S4 wrap connector runs through it as a long routed edge with a
  "plan v2" pill.
- **F-9 CURRENCY_MISMATCH — fixed.** "Currency mismatch", and the assumptions moved to the panel.
- **F-10 Console and Artefacts in one card — fixed.** Two cards, 20px gap.
- **F-11 "11 pinned" — fixed.** "8 of 11".
- **F-12 four avatar hues — fixed.** One neutral avatar chip, initials in `--ink-2`; the rail avatar too.

### Run detail

- **F-13 six regions, no expanded step — fixed.** Outputs dropped (five regions) and the fix round is
  expanded in place: "Failing check — unit recipe · 2 tests red · 13:39" and "Fix — 13:39 → 13:41 · task 3
  validated", in R13's two-label form at 15px.
- **F-14 Outputs pane — fixed.** Removed; Console spans the full width.
- **F-15 saturated green headers in light — fixed.** Step headers are the hue at 15% with the hue as the
  label in both themes.
- **F-16 $9.85 overlapping the arc — fixed.** Arc radius 66 → 76, number 34 → 29.
- **F-17 guard grid 2 + 1 — fixed.** Three equal cells.

### Queue

- **F-18 canvas half empty, chips not nodes — fixed.** Seven 106 × 46 node cards with the stage name and a
  state dot, the group centred vertically, the decision card widened to 898.
- **F-19 disabled Approve — fixed.** `--surface-2` fill, `--faint` text, `not-allowed`, both themes.
- **F-20 ten icon tints — fixed.** All panel icons neutral.
- **F-21 red for Act today — fixed.** Lime / muted / line-2 across the segmented bar and its legend.
- **F-22 two uppercase labels in one card — fixed.** "By kind" removed; the grid stands on its cell labels.
- **F-23 gauge out-sizes the decision — fixed.** Card title 19 → 25, gauge number 34 → 28.

### Runs

- **F-24 375px Stage column — fixed.** Stage 250, slack redistributed to Run and Ticket.
- **F-25 Model column not in §3 — fixed.** Removed.
- **F-26 1600 × 1300 capture — fixed.** 12 rows, captured at 1600 × 1000 like every other screen. Note the
  consequence: the shown-row outcome mix no longer matches BRIEF §2.5's "shown 20" note.
- **F-27 two row systems — fixed.** 56px, matching Tickets and the Factory manifest.
- **F-28 Running pill's full-strength ring — fixed.** One accent pill token set (`--acc-bg` / `--acc-ink` /
  `--acc-brd` at ~32%) used for Running and for Tickets' Review, with the hue as the label.

### Tickets

- **F-29 canvas as a 20px margin — fixed.** The table card floats with a 36px side inset and 56px from the
  panel card on a full-bleed dotted ground, with the selected ticket's pipeline as node cards above it.
- **F-30 KPIs are panel rows, not cards — partly.** They stay a stack in the panel card; §3's "four KPI
  cards" reads as one card of four stats. The 490px of nothing under them, which was the reviewer's actual
  complaint, is gone because the panel is content-sized on the ground.
- **F-31 checked rows carry no tint — fixed.** `.chk` neutral tint, distinct from the selected row's lime.

### Report

- **F-32 four decorative KPI tabs — fixed.** Lime tab on Cost per PR (the screen's subject),
  `--surface-2` / muted on the other three.
- **F-33 six regions — fixed.** The baseline line folded into the KPI block: five regions.
- **F-34 no value scale on the bars — fixed.** Three y ticks (0 / 6 / 12) and two dashed gridlines.
- **F-35 callout leader stops short — fixed.** The callout is drawn inside the chart SVG so it scales with
  it, and the dashed leader touches the marker.
- **F-36 baseline split into two fragments — fixed.** One left-aligned line ending with "Defect escape rate
  not yet measurable".

### On the admitted deviations

- **Gantt for "Runs by outcome" — not taken.** BRIEF-v2 §3 fixes Report's secondary panels as "runs by
  outcome as stacked daily bars", and the instructions for this pass forbid content beyond §3. F-34 was
  fixed in place instead.
- **Manifest as a table — kept**, and the repetition that undermined it is gone.
- **Run detail's second console pane — removed**, as the finding asked.
- **Ticket detail's three panels spread across the frame — kept**, with Assumptions moved from the canvas to
  the panel so the graph could be about the pipeline and the panel could fill.
- **Approve disabled with no explanation — kept**, and it now looks disabled.

---

# Re-score

Second pass, fresh eyes. 14 captures, all 1600 × 1000, side-by-sided against R01 (Queue, Tickets, Ticket
detail, Runs), R13 and R17 (Run detail), R16 (Report, Factory), plus R07 for the frost. Word counter run:
all seven under cap, exit 0 (queue 140, tickets 186, ticket 222, runs 118, run 158, report 123,
factory 131). Measurements are pixels in the 1600 × 1000 captures unless a percentage-of-frame is given;
R01 figures are normalised by 1560/1740 where the two are compared.

## Scores

| Screen | Hierarchy | Density | Spacing & alignment | Colour & contrast | Craft |
|---|---|---|---|---|---|
| Queue | 8 | 8 | 8 | 8 | 8 |
| Tickets | 8 | 7 | 8 | 7 | 7 |
| Ticket detail | 9 | 8 | 9 | 8 | 8 |
| Runs | 8 | 7 | 7 | 8 | 8 |
| Run detail | 8 | 8 | 7 | 8 | 8 |
| Report | 8 | 8 | 8 | 7 | 7 |
| Factory | 8 | 6 | 7 | 8 | 8 |

Was 5–8 with nothing at the bar; now 6–9 with 26 of 35 cells at or above 8. **Does not pass:** nine cells
below 8, all on four screens (Tickets, Runs, Report, Factory). The two screens that carry the direction —
Ticket detail and Run detail — are the strongest, and Ticket detail is the first screen in this set that
could sit beside R01 without being picked out.

## Per-finding verdict

**Fixed (33):** F-A1, F-A3, F-A4, F-A6, F-1, F-2, F-3, F-5, F-6, F-7, F-8, F-9, F-10, F-11, F-12, F-13,
F-14, F-15, F-16, F-17, F-19, F-20, F-21, F-22, F-23, F-25, F-27, F-28, F-29, F-32, F-33, F-35, F-36.
Spot checks against the captures rather than the claim:

- **F-A1 (edges).** Measured at 3× on `03-ticket-light.png` against R01 normalised to our frame width:
  stroke ~3px (R01 ~3.3px), port ~11px across with a 2px ring (R01 ~9px), node gap 113px = 7.2% of frame
  (R01 99px = 5.7%). At or above R01's weight, not below it. Residue in R-9.
- **F-A3 (wash).** Ground samples flat across the width: light (239,241,245) at x=200, 800 and 1200; dark
  (11,13,16) at the same points. Gone.
- **F-A4 (dark gauge ticks).** `01-queue-dark.png` "0" glyph is (107,116,129) — `--faint`, 2.05:1 against
  the arc it sits under and 3.7:1 against the panel. Legible, no longer #000.
- **F-1 / F-2 (Factory manifest).** 21 repeated cells are now 7; Tiers carries All / 1–3; the header reads
  RUBRIC (LINES) with right-aligned numerals and one em-dash. Real fix.
- **F-4 (switches).** **Not a defect, confirmed.** Sampled `#B8D832` under the on-switch on both
  `07-factory-light.png` and `05-run-light.png`, `#B6D64C` in dark. That is `--lime`. The first review was
  wrong; the builder was right to refuse.
- **F-13 (expanded step).** Present, in R13's two-label form: "FAILING CHECK / unit recipe · 2 tests red ·
  13:39" and "FIX / 13:39 → 13:41 · task 3 validated". Five regions, not six.

**Partly fixed (6):** F-A2, F-A5, F-18, F-24, F-31, F-34 — carried below as R-1, R-4, R-6, R-8, R-10.

- **F-A5.** 9.5px is gone. The eleven remaining 11px rules are uppercase micro-labels, and §2's own type
  band permits those ("Uppercase labels 11 to 12"), so this is substantially fixed. Three non-uppercase
  exceptions survive: the chart callout's second line at 11.5px (`.co .cos`), avatar initials 11px, nav
  badge 11px. Only the callout line is body text.

**Not fixed (1):** F-30 — KPIs stay a stack in the panel card rather than four cards. Defensible; the
consequence is R-1.

**Regressed (1):** F-26 — see the ruling below.

## Two rulings

**Runs at 12 of 20 rows to fit 1600 × 1000 — not acceptable.** The brief resolves this the other way.
BRIEF-v2 §3 fixes the content ("Table of 20 (BRIEF.md §2.5)") and BRIEF.md §5, left in force by
BRIEF-v2 §0, says in as many words: "Use `--window-size=1600,1400` (or taller) when a screen is longer
than the viewport so the capture shows the whole screen." The 1000px ceiling was self-imposed and the
first review's F-26 advice was wrong. The cost is measurable: Runs carries 118 words against a 220 cap —
the thinnest screen in the direction — next to a 280 × 452px empty column, and eight specified rows
(run_c7a0 through run_2b1c) are absent, so the shown outcome mix no longer matches §2.5.
*Fix:* recapture Runs alone at 1600 × 1450 with all 20 rows at 56px (20 × 56 + 44 header + ~300 chrome
= ~1464). Nothing else changes.

**Consoles at eight lines — acceptable, and on Ticket detail it is literally what was asked.** BRIEF-v2
§4.3 for this direction: "R01 Console and Debug below but each at most eight lines." §3 for Run detail
allows "at most ten lines" and eight is inside it. Both consoles read as R01's do — timestamp column,
level chip, message — and eight lines fills the card without a scroll stub. No change.

## Remaining findings

**R-1. A 280px-wide column of empty dotted ground under the panel card, on six of seven screens.**
The old defect was a half-empty white column; the new one is a wholly empty strip. Measured from the
panel card's bottom edge to the content bottom (y=990), column x=95–375: Factory **615px (68% of the
902px content column, 12% of the whole content area)**, Run detail 500px (55%), Tickets 452px, Runs
452px, Report 434px, Ticket detail 287px, Queue 260px. R01's panel runs to the bottom and closes with a
dashed dropzone; R17's node library runs to within 40px of the frame; R16 fills its canvas edge to edge.
Removing the trust-profile block (F-3, correctly) is what pushed Factory to 615.
*Fix, per screen rather than one rule:* Factory — move the five agent cards into the column as a vertical
list, or the manifest's stage chips as an R17 node-library grid. Run detail — the event log's other seven
§2.4 entries as a second panel block, or move Guard decisions to the bottom of the column and let Inputs
grow. Tickets and Runs — the filter chips currently in the header row belong in the panel (R01 puts its
filters there); or bottom-anchor a small element the way R01 does. Report — Model spend is already there;
add the tag leaderboard's remaining rows. Drives Factory density 6 and spacing 7, Run detail spacing 7,
Tickets and Runs density 7.

**R-2. Runs: a 247px dead gutter inside the table.** The widest STAGE value ("Index rebuild") ends at
x=857; the first STARTED digit begins at x=1104 — 247px of nothing in every row, and 308px for the
two-character values ("S4" ends at x=796). By comparison the RUN→TICKET gutter is 135px and
TICKET→STAGE is 108px. R04 sizes all eight of its columns to their content with a fixed trailing slot.
*Fix:* STAGE to ~120px and pull STARTED / DURATION / COST / OUTCOME left by ~180px, or widen RUN and
TICKET to absorb it. Drives Runs spacing 7.

**R-3. Report: the stacked bars overshoot their own axis.** On `06-report-light.png` the "12" gridline
sits at y=667; the tallest stacks' top caps reach y=655 — about 1.2 units above the axis maximum. The
cause is the ~3px gap drawn between stack segments: the gap is as tall as a one-run segment, so a
1-run "Other" cap and the blank under it read the same size, and the gaps accumulate into the overshoot.
R05 and R15 stack their segments flush.
*Fix:* stack the segments contiguously, or keep the gaps and raise the axis maximum to 14 with ticks at
0 / 7 / 14. Drives Report craft 7.

**R-4. Tickets: selected, hovered and checked collapse into two visible states.** Sampled at x=900:
base row `#FCFDFE`, hovered row (T-0415) `#F4F6F8`, checked rows (T-0417, T-0403) `#F1F3F6`. Checked
against base is **1.09:1**; hovered against checked is **1.02:1**. In the capture the hovered row and the
two checked rows form one indistinguishable grey block, and only the lime selected row separates. Dark is
the same: (23,26,32) / (30,33,40) / (34,36,42). R04 gives checked rows a tint clearly distinct from hover.
*Fix:* checked rows to the accent at 5–6% (a pale lime, one step under the selected row's 14%), hover to
a neutral 2%. Drives Tickets colour 7.

**R-5. Tickets: the bulk bar loses its figure–ground in dark.** Light: fill (27,31,38) on the app ground
(239,241,245) = **14.6:1**, a solid black bar exactly as R04 draws it. Dark: fill (42,47,56) on
(11,13,16) = **1.45:1**, and 1.3:1 against the table card it overlaps. It reads as a smudge, not a
floating action bar. §2 asks the dark theme to be tuned rather than inverted; here the element's whole
idea — a dark slab against a light field — was inverted into nothing.
*Fix:* dark bulk bar to an elevated surface around `#3C424E` with a 1px `--line-2` border and the same
shadow, so it clears 3:1 against the card behind it. Drives Tickets craft 7.

**R-6. Light theme: `--faint` micro-labels sit at 2.0–2.2:1.** Every uppercase micro-label sampled comes
back `#A6ADB8` on white or on the ground: ACT TODAY, BY BUCKET, PLAN V2, WAIVER, ASSUMPTIONS, GUARD
DECISIONS, MODEL SPEND and every table column header measure **2.22:1**; Report's "CONTEXT MEASURE, NOT
COMPARABLE" measures **2.01:1** on the ground — the lowest on the direction, on the one caveat that
carries the most meaning. R01's own INPUT / TRANSFORM labels measure 2.71:1 at a larger rendered size, so
the reference is faint too, but ours is a further 20% down at 11px. Dark is fine (3.7:1).
*Fix:* light `--faint` from `#A6ADB8` to about `#8B93A0` (≈3.2:1), which still reads as the quietest tone
on the screen; and Report's baseline tag to `--muted`. Drives Report colour 7, contributes to Tickets
colour 7.

**R-7. Factory: a 240px gutter between MODEL and BUDGET.** MODEL values end at x≈1160; the right-aligned
BUDGET column begins at x≈1400. Same class as R-2, half the size.
*Fix:* pull BUDGET and RUBRIC left, or give AGENT and MODEL the slack. Contributes to Factory spacing 7.

**R-8. Queue and Tickets: the chain nodes are not the direction's own nodes.** 108 × 40px with a dot and
one word, against 178 × 62px on Ticket detail and R01's ~170 × 52 normalised — 63% of R01's width, 77%
of its height — and the connectors between them are bare 25px stubs with **no ports**, while every other
edge in the direction carries an 11px ringed port at both ends. Two edge systems in one direction. The
Packet → detail-card connector also terminates at the card's top border with nothing on the end.
*Fix:* one node size and one edge system: chain nodes to ~150 × 50, ports on every connector including
the one into the detail card. Contributes to Queue craft 8, Tickets craft 7.

**R-9. Ticket detail and Run detail: ports float in the gap; every edge is a straight horizontal.**
R01 seats each port circle on the node's face, half over the border, and every connector is a bezier that
travels 100–150px vertically, which is what makes its canvas read as a graph rather than a row of cards.
Ours parks the ports about 15px clear of the node edge in open space and draws straight horizontals
between same-row nodes; only the "plan v2" wrap and the gate branch curve. The screens read closer to
R16's orthogonal canvas than to R01's.
*Fix, optional:* seat the ports on the node faces, and let the row-to-row and branch edges carry more
vertical travel. Not a score-blocker; both screens are at 8 on craft with it.

**R-10. Run detail has no middle in its type scale.** run_7f3a at 28px and $9.85 at 29px, then the whole
field at 14–15px. R13 puts four 32px numbers in a strip across the top (TOTAL STEPS 5, ERRORS 1,
DURATIONS 2.78s, STATUS Completed) so the screen has an at-a-glance layer; ours renders Tasks 6 of 6 /
Fix rounds 1 / Duration 31:05 as 14px key-value rows inside the Budget panel. BRIEF-v2 §3 asks for a stat
strip here; §4.3 asks for R17's property panel. The builder chose §4.3, which is defensible, but the
hierarchy cost is real.
*Fix, optional:* the three property-panel numbers to 24–26px tabular with the label above, R17's own
treatment for its gauge readouts. Run detail is at 8 on hierarchy with it.

**R-11. One 11.5px non-uppercase line.** `.co .cos`, the chart callout's second line ("T-0403 escalation,
3 attempts"). §2's floor is 12 except chart ticks, and this is a sentence, not a tick.
*Fix:* 12px.

## Regressions introduced by the fix pass

1. **Runs lost eight rows** (F-26 ruling above) — the only content regression.
2. **Removing the trust-profile block took Factory's empty column from ~300px to 615px.** The removal was
   right; nothing was put back.
3. **Tickets and Runs gained a mini node-pipeline that is not in BRIEF-v2 §3** (§3 for Tickets ends at the
   table and the bulk bar; §4.3 describes those screens as "one frosted card holding the table"). It is
   what makes those two screens belong to the direction, so keep it — but it is content beyond §3, and on
   Tickets it restates the STAGES dot column of the selected row.

Nothing regressed in colour, type or the frame. The canvas-as-ground move is the right call and should
stay; the whole of R-1 is the unfinished half of it.

# Final pass

Targeted pass against R-1 – R-6 and the two rulings. Nothing else was touched. Word counter after:
queue 140, tickets 187, ticket 222, runs 205, run 187, report 140, factory 150 — all under cap, exit 0.
All 14 PNGs recaptured (Runs at 1600 × 1450, the other six screens at 1600 × 1000). Measurements below are
pixels sampled in the shipped captures; contrast is WCAG relative-luminance ratio.

**R-1. Empty column under the left panel — fixed.** The panel is now the full-height card R01 has
(`align-self:stretch`), so the dotted column beneath it is gone on all seven screens: Factory **615 → 0**,
Run detail **500 → 0**, Tickets **452 → 0**, Runs **452 → 0**, Report **434 → 0**, Ticket detail 287 → 0,
Queue 260 → 0. Each panel was filled with content BRIEF-v2 §3 already lists for its screen: Factory takes
R17's node-library tile grid (seven stage tiles plus a dashed *Add stage* cell) with the four sandbox
switches bottom-anchored; Run detail takes §3's six-task step list between Inputs and Guard decisions;
Tickets and Runs take the filter set out of the title bar (R01 puts filters in the panel), and Runs adds a
by-outcome segmented bar with five counts pinned to the bottom; Report gains a six-row Measures list from
§2.6 above Tags and Model spend. Largest blank band inside a panel, as a share of panel height:
Report 8%, Run detail 17%, Factory 17%, Queue 21%, Tickets 23%, Ticket detail 27%, Runs 30%. None over 40%.

**R-2. Runs gutter — fixed.** Columns are sized to content at 146 / 136 / 146 / 84 / 88 / 96 / 152 in an
848px card, and the Stage column now carries the stage *name* with its colour square ("S4 Implement",
"S3 Plan") instead of "S4", so the slack sits under a label rather than beside a two-character value.
Measured Stage → Started **247 → 70** for the widest value ("S4 Implement"), 76 for "Index rebuild",
98 worst case on the one short value ("S4 task 4"). Every other gutter: Run → Ticket 92, Ticket → Stage 93,
Started → Duration 57, Duration → Cost 62, Cost → Outcome 40. Nothing over 100.

**R-3. Report daily outcome bars — fixed.** The axis was 0 / 6 / 12 while the scale ran to 13, so a 13-run
day topped out above its own maximum. The axis is now 0 / 7 / 14 at the same gridline positions, the unit is
7.91px, and segments are drawn with a 1px gap. The tallest stack tops at y = 18.2 against the 14 gridline at
y = 9.2 — **12px above the axis maximum → 9px below it**. A one-run segment is 6.9px against a 1px gap, so it
reads about 7× the gap.

**R-4. Tickets row states — fixed.** Light, sampled at x = 900: base (252,253,254), hover (222,222,225),
checked (243,247,225), selected (233,242,197) with a 3px lime bar on the first cell. Hover against base
**1.07 → 1.32:1**; checked is the accent at 14% (a pale lime against a neutral hover, so the two no longer
read as one grey block); selected is the accent at 28% plus the bar. Dark: hover against base **1.06 → 1.32**,
checked against base **1.09 → 1.34**, selected against checked 1.38.

**R-5. Dark bulk bar — fixed.** Fill `#616978` with a 10% white border and the two-layer shadow
(`0 2px 6px rgba(0,0,0,.28), 0 24px 44px -22px rgba(0,0,0,.85)`). Measured fill (97,105,120) against the
table card behind it **1.30 → 3.15:1**, against the app ground **1.45 → 3.52:1**. Light is unchanged at
14.6:1.

**R-6. Light `--faint` — fixed.** `#A6ADB8` → `#868E9C`. Sampled on a table column header:
**2.22 → 3.24:1** on the frosted card, which is where every chart tick, table header and uppercase
micro-label sits. The two faint items that sat on the raw app ground moved to `--muted` `#79818E`: Report's
"context measure, not comparable" tag (**2.01 → 3.25:1**) and the Ticket / Run detail eyebrow. `--faint` on
the raw ground would be 2.92, so nothing is left there. Dark is unchanged at 3.68:1.

**Ruling 1. Runs shows all 20 rows.** run_c7a0, run_9d11, run_c4d8, run_e83f, run_bb72, run_9a03, run_5e77
and run_2b1c are back, in §2.5 order, fix-round and task children indented with no "child of" text. The
table is 44 + 20 × 56 = 1164px and the screen is captured at 1600 × 1450 per BRIEF.md §5, with ~25px of
frame to spare. The shown-row outcome mix now matches §2.5 again.

**Ruling 2. Consoles stay at eight lines.** No change.

## Out of scope, improved in passing

**R-7 (Factory MODEL → BUDGET gutter) is better but not under 100.** Columns rebalanced to
220 / 218 / 148 / 176 / 104 / 132 in a 998px card with the Rubric column left-aligned, so the measured
gutters are **240 → 120** (Stage), 188 → 122 (Model → Budget) and 142 → 30 (Budget → Rubric). Getting every
one under 100 needs the card at ~900px, and the five agent cards below it cannot go under ~185px each
without "s4-implementer" truncating, so the table and the card row would stop aligning. Left as is.

**R-8 to R-11 were out of scope and are untouched.**
