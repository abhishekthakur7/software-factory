# 02 Observatory — review against the references

Reviewed against R11 (frame, KPI cards, live rail, chart), R13 (stat strip, step list, execution flow, raw
output), R14 (KPI card proportions), R15 (report layout, donut, model table, activity rows), R02 (heatmap,
KPI card with a chart inside), R06 (rows with status dots). Fourteen captures, both themes, each composed
side by side with the reference its screen copies and each viewed on its own. Measurements below are taken
from the PNGs; reference figures are normalised to our 1600px width (R11's app frame is 1870px inside a
2000px image, so reference pixels are multiplied by 0.855; R13's by 0.93).

## Word counts

```
queue     195 / 240  ok
tickets   181 / 200  ok
ticket    183 / 260  ok
runs      220 / 220  ok
run       169 / 260  ok
report    118 / 220  ok
factory   153 / 260  ok
```

All under cap. Runs is exactly at cap and is also the emptiest-looking screen in the set; see R1.

## Scores

| Screen | Hierarchy | Density | Spacing / alignment | Colour / contrast | Craft |
|---|---|---|---|---|---|
| Queue | 6 | 7 | 7 | 7 dark / 6 light | 7 |
| Tickets | 7 | 7 | 7 | 6 | 7 |
| Ticket detail | 5 | 7 | 4 | 7 dark / 6 light | 6 |
| Runs | 7 | 6 | 3 | 7 | 6 |
| Run detail | 8 | 9 | 8 | 8 dark / 7 light | 8 |
| Report | 7 | 7 | 7 | 6 | 7 |
| Factory | 6 | 6 | 7 | 8 | 7 |

Nothing passes on every axis. Run detail is one axis short (light-theme contrast). Every other screen has at
least two axes below 8.

## What is right, so the fixes do not undo it

KPI number size is correct and does not need changing: our Tickets and Runs numbers measure 26px of digit
height, R11's "12,438" measures 31px in a 2000px image, which is 26.5px at our width. Run detail's stat
numbers measure 22px against R13's 18.6px normalised. Table rows are 56px, inside the 56–64 band. Sidebar
248px, nav rows 44px, page gutter 28, card radius 15. Run ids and ticket keys are in Geist, not mono, with
tabular numerals, which is what §2 asks for — they read monospaced in the captures only because of the
underscore. Mono is confined to hashes and the two log blocks.

---

## Runs — the largest problem in the direction

**R1. The live rail is 521px tall beside a 1169px table, leaving 648px of bare page in the right column.**
Measured on `04-runs-dark.png`: rail card 340→861, table 340→1509. That is 55% of the table's height showing
nothing, and it is the first thing the eye lands on in both themes. Three separate causes:
- Seven rows against R11's thirteen.
- Our rail rows are 64px; R11's are 65.5px in a 2000px image, i.e. 56px at our width. We are 14% looser than
  the reference while holding half its rows.
- R11's Live Activity card is top-aligned with the KPI cards and occupies the right quarter for the full
  content height. Ours starts below both the KPI row and the filter row, so it forfeits ~200px before it
  starts.

Fix, and the answer to the question the README raises: **yes, fill the rail to R11's density, and take the
words from the table.** The rail is the signature element of the frame this direction copies; a seven-row
rail with 648px of nothing under it is worse than any word count. Concretely: tighten rows to 56px, run the
rail from the top of the KPI row to the bottom of the table (that is 19 rows at 56px, or 13 rows plus a soft
fade at the bottom edge if 19 rows of fake data is too much), and pay for it by deleting the table's
`Started` column — 20 time values, 21 words, and every rail row already carries a timestamp on its second
line. R15's model table has no time column either. If that still leaves you over 220, the cap is the thing
that is wrong, not the rail: BRIEF-v2 §1 puts R11 itself at about 250 visible words, and 13 two-line rail
rows are roughly 65 of them.

**R2. Every one of the seven rail rows is also a table row.** run_d204, run_u020, run_77d2, run_f0c9,
run_e1a2, run_44e8 and run_9d11 appear twice on the screen, at the same times, with the same durations and
costs. R11's rail is a stream the rest of the screen does not contain. When the rail is lengthened, make its
lower rows events the table does not show (run started / inputs verified / fix round opened), or accept the
overlap only for the top three.

**R3. Fourteen identical green "Pass" pills in a twenty-row table.** R15's Recent Activity marks success with
a small check glyph and a word, not a filled pill, and R06 — a listed reference for this direction that is
used nowhere in the build — marks invoice rows with a coloured dot plus plain text. Use R06's treatment:
a status dot plus the word for pass, and reserve the filled pill for Running, Fail, Blocked and Aborted.
That removes fourteen chips of visual weight and makes the five exceptions findable.

---

## Ticket detail

**K1. Two of the three lower panels stop less than half way down.** Artefacts runs 465→1059 (594px),
Approvals 465→771 (306px), Assumptions 465→736 (271px). That is 288px of empty page under Approvals and
323px under Assumptions — the bottom half of two-thirds of the screen. R13 fills its frame: the step list on
the left and the flow-plus-output stack on the right both reach the bottom edge. Fix: give the row a common
height and let Artefacts scroll inside its card at eleven rows, or restack as two columns (Artefacts left at
full height; Approvals above Assumptions right).

**K2. Nothing on the screen is larger than the 24px title, and there is no number at all.** R13 opens with a
four-cell stat strip whose numbers measure 18.6px of digit height at our width; ours has cost and elapsed
time set at 12.5px in a meta line under the title. §3 gives you the material — cost $18.40, elapsed 3h 40m,
5 approvals, 11 artefacts. Promote them into an R13 stat strip above the stage row and the screen gains a
focal band without a word of new content.

**K3. The stage cards carry three body lines where R13's carry two.** Ours: title, run id, `0:41 · $0.02`.
R13's: title, `12ms`. Merge the run id into the meta line (`run_2b1c · 0:41 · $0.02`) and the card loses a
line and gains air; at 145px column width that line still fits at 12.5px.

**K4. The flow area around the Base advance node is a 90px empty band with no canvas treatment.** R13 draws
its Execution Flow on a dotted grid inside an inset panel, which is why the space around its five cards
reads as canvas rather than as a gap. Ours is flat card fill, so the same emptiness reads as a layout
mistake. Add R13's dot grid to the stage panel, and thicken the S4→Base advance connector: at 1px it
disappears in both themes.

**K5. The greyed "Plan v1" row reads as a rendering fault.** It sits between "Risk map" and "Plan v2" at
about 40% opacity with no other signal. Either strike it through, or move v1 behind a "v1" chip on the v2
row, or drop it.

**K6. In light the nested stage cards do not separate.** Page #F4F5F7, panel #FFFFFF, stage card #F7F8FA —
a 3-unit step from the page and an 8-unit step from the panel they sit in. In dark the same nesting is
#0B0C0E → #121417 → #181B1F, two clear 6–7 unit steps. Push the light nested surface to about #EEF0F3 or
give it the border only and drop the fill.

---

## Report

**P1. The loudest element on the page is the amber sparkline in the fourth KPI card, and it means nothing.**
Median queue latency is not a warning; it is a neutral measure. §2 allows semantic colour only for meaning.
In light the orange fill under the zigzag makes that card the visual hero of a screen whose hero is supposed
to be the cost line. Make it the accent or a neutral, and drop the fill under it.

**P2. The donut centre shows the largest segment, not the total.** Ours reads "58% / S4". R15's reads
"$97.61 / Total", and §4.2 asks for "donut with centre total". Put the 30-day stage cost there with "Total"
beneath, and let the legend carry the per-stage shares it already carries.

**P3. The donut's small segments vanish in light.** S2 at 4% and S5 at 2% are two steps of a six-step green
ramp at 27% and 18% opacity; on white they and their legend dots are close to invisible. Either floor the
ramp at about 35%, or collapse S1/S2/S5 into one "Other 15%" segment as R15 does with
"Other/Unclassified 2.0%".

**P4. Six regions against §2's five.** Title bar, range control, KPI row, baseline line, chart row, panel
row. Fold the range control into the title bar — R15 puts its date range and "Last 30 days" control in the
top bar next to the title — and the count is five.

**P5. Model spend is 132px shorter than the panel beside it, and it is the weakest panel on the screen.**
Measured: Model spend 673→926, Tag leaderboard 673→1058. Three rows, three near-identical green sparklines,
and it restates the cost story the donut already tells. **This is where the R02 heatmap belongs.** Latency by
hour, R02's cell scale, six or seven tick labels, in place of the three model rows — it fills the ragged
column, adds the only chart type on the screen that is neither a line nor a bar nor a donut, and costs about
fifteen words against a 118/220 budget. R02 is a listed reference for this direction and currently appears
nowhere. The model rows can move into the Tag leaderboard column as three lines under the leaderboard, or be
dropped with the owner's sign-off, since §3 does name them.

**P6. A leaderboard bar is heavier than the hero chart.** FM-4's progress bar is a full-width solid accent
fill; the hero cost line is a 1.5px stroke. R11's Top Tools rows put a thin accent fill on a grey track and
never let a row bar outweigh the chart above it. Halve the bar height and set the track to `--card-3`.

**P7. "Not yet measurable" is absent.** §3 asks for it as one muted cell. Minor, but it is listed.

---

## Queue

**Q1. The largest thing on the screen is a rail card.** "38m" in the median-latency gauge is the only number
above 14px anywhere; the main column — the list and the decision card, which are what the screen is for —
contains no number and no chart. R11's main column carries three 36px numbers and a three-series chart, and
its rail is the quiet column. The builder is right that §3 does not list a KPI row here, but the gauge, the
bucket bar and the by-kind grid can move to the top as a compact stat band and let the list and the detail
card own the width; or the detail card's "9 checks · 8 pass · 1 waived" can be set as a number-led block so
the decision surface has one large figure.

**Q2. The three approval slots are rendered as a four-card grid, where both §3 and §4.2 ask for rows.**
§3: "three slot rows (initials, name, role, approved 14:12 / approved 14:19 / open), one evidence line".
§4.2: "detail as an R13 step list". Ours is four bordered boxes, each three lines deep, in a component style
that appears nowhere else in the direction. Three 52px rows with a fixed avatar slot, a name, a muted role
and a right-aligned status — R11's Recent Changes rows, or R13's collapsed step rows — plus one evidence
line with the link, would cut the card's height by about a third and stop it reading as a second design.

**Q3. The number 10 appears three times.** Nav badge, the chip on the Open items header, and the "10 Open"
cell in the by-kind grid. Keep the nav badge, drop the header chip, and make the sixth grid cell a kind
rather than a total.

**Q4. The strongest green on the screen is a disabled button.** Approve is a filled accent button at 60%
opacity next to three outline buttons. The eye reads fill before opacity. Make the disabled Approve an
outline button like its neighbours and keep the filled accent for a live primary action, as R11 does with
its single "New Agent" button.

**Q5. Column header and cell content do not align, and the rail stops short.** The "Kind" header sits at
x=333 over the label, while each row's icon starts at x=309, so the icons hang outside their column. Give
the icon a fixed slot inside the Kind column and start the header at the icon's left edge. Separately, the
rail ends at y=954 against a main column ending at y=1126: 172px. Less serious than Runs, same cause.

**Q6. In light the sidebar is the same white as the cards.** Sidebar #FFFFFF, card #FFFFFF, page #F4F5F7.
The nav column has no surface identity — only a hairline border separates it from content that is also
white. Dark gets this right (#08090B against #0B0C0E against #121417). Tint the light sidebar to about
#FAFBFC and darken the page a step, or put the sidebar on the page colour and keep cards white.

---

## Tickets

**T1. Eight KPI cards across Tickets and Runs have a 43px hole in them.** Measured on `02-tickets-dark.png`:
card 100→262 (162px tall), icon/label/number band ends at y=172, sparkline starts at y=215. That is 27% of
the card height as empty band. R14 and R15's cards of the same proportion carry four bands — label, number,
delta line, sparkline — and R11's puts the sparkline beside the number with the delta line beneath it. The
fix already exists in this file: Report's KPI card is the same 162px and has three bands with no hole
(number ends 234, third line 246–254, sparkline 274). Give Tickets and Runs the same third line ("12 open
now", "of 43 today", "5 of 43", "$430.40 month"), or move the sparkline to the card's right half as R11 does.

**T2. Four sparklines, four hues, no meaning.** Open green, In queue amber, Merged 30d green, Cost 30d grey.
Amber has no warning sense here and the grey line is close to invisible in both themes (dark grey on
near-black, light grey on white). One accent for all four, or accent for the three counts and the accent at
lower opacity for cost.

**T3. Nine columns.** Checkbox, Ticket, Title, Repo, Tier, State, Stages, Cost, Age. §2 caps at eight. Repo
is the one that carries least — nine of twelve rows say "ledger-core" — and it can move into the title row
as a muted suffix or go entirely.

**T4. Six identical neutral pills stacked in one column.** Implementing, Checks, Clarifying, Intake,
Abandoned, Context all render as the same grey chip. R04 and R15 set unremarkable states as plain muted text
and pill only what is notable. Pill Review, Plan review, Escalated, Rejected, PR opened and Merged; set the
rest as text.

---

## Run detail

The strongest screen; three things keep it off 8 everywhere.

**N1. In light the code blocks barely read as blocks.** Card #FFFFFF, block #EDEFF2 — a 7-unit step, against
dark's #121417 to #1F2429 which is a clear 9–11 units on a much darker base and reads as a real inset. R13's
raw-output block is a distinct step down from its card. Take the light block to about #E8EAEE and add the
1px border it already has in dark.

**N2. Six identical Pass pills and six chevrons down the task list.** R13's step list varies (Success,
Success, Warning, Error, Running), which is what gives it rhythm. Ours cannot vary — the data is all pass —
so drop the pill on passing steps to a small check glyph and keep the chevron only on the expandable step.

**N3. The two columns end 90px apart** (Tasks card to y≈1060, Event log to y≈1150). Minor next to Ticket
detail, but the same habit.

---

## Factory

**F1. Fourteen of the twenty-one matrix cells are exact duplicates of the cell beside them.** Every row
repeats the same model and the same budget under Tier 1, Tier 2 and Tier 3. The widest panel on the screen
carries seven facts in twenty-one slots, and a reader's first reaction is that the table is broken. Restructure
to Stage | Model | T1 | T2 | T3 with only the budget in the three tier columns, right-aligned: the model is
named once, the three numbers align, the table drops from six data columns to four, and if the budgets ever
differ the matrix still works.

**F2. No focal point.** Manifest v14 at 24px is the largest thing; the rest is three flat lists. R12's card
grid is flat too, so this is partly reference-consistent, but the fixture gate (41 fixtures) and the five
agents' pass rates are the numbers the screen exists to show and they are all set at 12–14px. Promote the
fixture gate to a number, or set the five pass rates as the card's one large figure with Fixtures and Runs
30d as its meta line, which is exactly R12's agent card.

**F3. 190px of empty page under Sandbox policy.** Policy panel 160→467, stages table 160→657. Four switch
rows will not fill 497px; either move the policy panel down beside the agent cards, or split the stage table
into two panels so the right column has two stacked cards.

**F4. Both agent-card buttons have the same weight.** R12 pairs a secondary (Pause) with a primary (Open).
Ours gives Fixtures and Open identical outline treatment, so the card has no default action.

**F5. A second hash sits in the Sandbox policy header** (`c8a0…42`), unlabelled. §2 permits short hashes in
the Factory manifest; the policy panel is not the manifest. Either label it or drop it.

---

## Rules and content

- **§2 broken:** at most eight columns (Tickets has nine, T3); semantic colour only for meaning (Tickets'
  amber sparkline T2, Report's amber KPI sparkline P1); at most five regions (Report has six, P4); two-line
  rows only where the reference has them (Ticket detail's Assumptions rows carry three data points, K3's
  sibling — acceptable if the third is dropped).
- **§2 vs §3 conflict, resolved in §3's favour and correctly:** the eleven short hashes in the Ticket
  detail Artefacts panel. §2 restricts short hashes to the Ticket header, Run detail and the Factory
  manifest; §3 explicitly specifies "11 rows: name, version, short hash". Keep them, keep them at `--faint`.
- **Content not in §3:** "10 decisions today" under the Queue gauge; the "10 Open" cell in the by-kind grid
  (a total, not a kind); "7 Aug – 6 Sep 2026" beside the Report range control (reasonable, but it is extra).
- **Content §3 lists and the build omits:** Report's "Not yet measurable" muted cell (P7).
- **Reference listed for the direction and used nowhere:** R02 (heatmap — see P5) and R06 (status-dot rows —
  see R3). Both have an obvious home.

## Priority

1. R1 — fill the Runs rail to R11's density and top-align it. 648px of dead column is the one thing that
   would stop a reviewer at a glance.
2. T1 — give the eight Tickets and Runs KPI cards the third line that Report's cards already have.
3. K1, F3, P5 — equalise panel bottoms across Ticket detail (288px and 323px), Factory (190px) and Report
   (132px). The ragged-bottom habit is what most separates these screens from R11, R13 and R15, all of which
   fill their frames.

Then K2 and F2 (no large number on two of seven screens), P1 and P2 (Report's colour and donut centre), Q2
(slot rows), R3 and T4 (pill walls).

---

# Builder response

Re-built against these findings plus the orchestrator's decisions (a) fill the Runs rail and drop the
table's `Started` column, cap raised to 260; (b) three-line KPI cards on Tickets and Runs; (c) equal panel
bottoms on Ticket detail, Factory and Report; (d) Report's bottom row is leaderboard + R02 heatmap + model
spend, five regions max; (e) R06 dot-plus-word for pass rows. One line per finding.

## Runs

- **R1 — fixed.** The rail is the right column of a grid that starts at the KPI row and ends with the table:
  22 rows at 60px (R11 has 13 at ~56px), so the 648px of bare page is gone and both columns end level.
- **R2 — partly fixed.** The rail now carries the clock times the table lost, and `run_c6f2` / `run_9d0e`
  are runs the table cannot show; the rest still overlaps, because a longer stream of events the table lacks
  would mean inventing timings that BRIEF.md §2 does not give.
- **R3 — fixed.** Pass rows are an R06 dot plus the plain word; the filled pill is kept for Running, Fail,
  Blocked and Aborted, in the table and in the rail.

## Ticket detail

- **K1 — fixed.** Two panel columns: Artefacts left at full height, Approvals over Assumptions right; the
  columns end within a few pixels of each other.
- **K2 — fixed.** Header and an R13 four-cell stat strip are one card: Cost $18.40, Elapsed 3h 40m,
  Approvals 4 of 5, Artefacts 11, at 32px.
- **K3 — fixed.** Stage cards are two body lines (title, `0:41 · $0.02`); the run id moved into the tinted
  header strip at 12px.
- **K4 — fixed.** The flow sits on an inset dotted canvas (page colour, `--dots` at 10/13%) and the S4 →
  base-advance connector is 2px.
- **K5 — fixed.** "Plan v1" is struck through rather than only dimmed.
- **K6 — fixed.** Nesting inverted: white / `#121417` stage cards on the page-coloured canvas, so both
  themes show two clear steps.

## Report

- **P1 — fixed.** The median-latency card is a neutral accent line at 55% with no area fill.
- **P2 — fixed.** The donut centre reads `$430.40 / Total`; the legend keeps the per-stage shares.
- **P3 — fixed.** The ramp is floored at 34% (100 / 78 / 62 / 50 / 42 / 34).
- **P4 — fixed.** The date range and 7d/30d/90d control moved into the top bar; the screen is four regions.
- **P5 — fixed.** The bottom row is Tag leaderboard, an R02 hour × weekday latency heatmap with a labelled
  faster→slower scale, and Model spend; all three stretch to a common height.
- **P6 — fixed.** Leaderboard bars are 4px at 85% on the `--card-3` track.
- **P7 — fixed.** "Defect escape rate — not yet measurable" is one muted cell under the model rows.

## Queue

- **Q1 — partly fixed.** The gauge dropped to 34px and the decision card's evidence block is number-led at
  30px, so the rail no longer owns the only large number; the list and detail card still carry no chart.
  Moving the three rail cards into a top stat band would finish it but costs this screen its R11 rail.
- **Q2 — fixed.** Three 52px slot rows (avatar, name, role, right-aligned status) plus one evidence row,
  replacing the four bordered boxes.
- **Q3 — fixed.** The header chip is gone and the sixth by-kind cell is a kind (Control 1, Other 4).
- **Q4 — fixed.** The disabled Approve is an outline button; no filled accent button on this screen.
- **Q5 — fixed.** The icon lives inside the Kind column, so header and cells share an edge; the rail cards
  stretch to the main column's height.
- **Q6 — fixed.** Light sidebar `#F7F8F9` on a `#F1F2F4` page with white cards: three distinct surfaces.

## Tickets

- **T1 — fixed.** Both KPI rows carry Report's third line, so the 43px hole is gone.
- **T2 — fixed.** One accent for the counts, accent at 55% for cost; the Runs Fail card keeps red, where red
  carries meaning.
- **T3 — fixed.** Repo dropped (the ticket key prefix already encodes it); eight columns.
- **T4 — fixed.** Implementing, Checks, Clarifying, Intake, Abandoned and Context are plain muted text;
  pills are kept for Review, Plan review, Escalated, Rejected, PR opened and Merged.

## Run detail

- **N1 — fixed.** Both blocks use `--card-3` (`#E7EAEE` light, `#1F2429` dark) with their border.
- **N2 — fixed.** Passing steps show a small check glyph; the chevron is only on the expandable step.
- **N3 — fixed.** The two columns stretch to a common height and the step list distributes its rows.

## Factory

- **F1 — partly fixed.** Restructured to Stage / Model / Tier 1–3, so the model is named once and the three
  budgets align right; the budgets themselves are still identical because §2's data does not vary by tier.
- **F2 — fixed.** Each agent card leads with its pass rate at 32px over "Pass rate 30d", with Fixtures and
  Runs 30d as key/value rows.
- **F3 — fixed.** One card per row: manifest table, agent cards, and a full-width four-up policy band.
- **F4 — fixed.** Open is the primary button, Fixtures the secondary.
- **F5 — fixed.** The unlabelled policy hash is gone.

## Rules and content

- Eight columns on Tickets, five regions or fewer on every screen, semantic colour only where it means
  something, and no content added beyond BRIEF-v2 §3 plus the decisions. "10 decisions today" (not in §3)
  was removed from the Queue gauge. The Report date range stays, next to the range control in the top bar,
  as in R15.
- Word counts: queue 191, tickets 179, ticket 185, runs 253 (cap 260 for this direction), run 163,
  report 118, factory 147.

---

# Re-score (second pass, fresh reviewer)

Fourteen captures re-viewed alone and side by side with the reference each screen copies (R11 Queue/Runs,
R13 Ticket/Run detail, R15 Tickets/Report/Factory), plus R14, R02 and R06 for the elements that cite them.
Reference figures are normalised to our 1600px content width: R11's frame is 1870px inside a 2000px image,
so R11 pixels are multiplied by 0.855; R15 and R02 are measured inside their own 2000px frames and quoted
as ratios rather than pixels.

Word counts with the raised Runs cap — all pass:

```
queue 191/240 · tickets 179/200 · ticket 185/260 · runs 253/260 · run 163/260 · report 118/220 · factory 147/260
```

## Scores

| Screen | Hierarchy | Density | Spacing / alignment | Colour / contrast | Craft |
|---|---|---|---|---|---|
| Queue | 8 | **7** | 8 | 8 | 8 |
| Tickets | 9 | 9 | 8 | 8 | 9 |
| Ticket detail | 9 | 8 | 9 | 8 | 8 |
| Runs | 8 | 8 | **7** | 8 | 8 |
| Run detail | 9 | 9 | 8 | 8 | 9 |
| Report | 9 | 9 | 9 | **7** | 8 |
| Factory | 8 | **7** | **7** | 8 | 8 |

**Does not pass.** Five cells below 8 across four screens, down from twenty-two cells and seven screens.
Tickets, Ticket detail and Run detail now clear the bar on every axis. Every remaining finding is a
localised layout or scale fix; none requires a screen to be rebuilt.

## Ruling: the two rail rows that are not in the table

**Keep them, and they are not "plausible fill".** `run_c6f2` and `run_9d0e` are named verbatim in BRIEF.md
§2.5: "run_c7a0, run_c7a1 and run_9d11 have parents outside today's list … (T-0417 S4 parent **run_c6f2 at
12:05**, T-0403 S4 parent **run_9d0e at 09:12**)". The rail renders both with the exact ticket, stage and
clock time §2 gives them. They are not invented entities, and they do a job nothing else on the screen can:
§3 removed the "child of" text from the indented rows, so the parent identity had no home until the rail
took it. This is the best pair of rows in the rail — keep them and, if the rail is ever re-cut, keep them
first.

## Per-finding verdicts

| | Verdict | Evidence |
|---|---|---|
| R1 rail 648px short | **fixed** | Rail and table are one grid: both columns run 100→1509 on `04-runs-dark.png`, bottoms level to the pixel. 22 rail rows at a measured 60px pitch against R11's 65.5px raw (56px normalised) — 7% looser, inside tolerance. |
| R2 rail duplicates the table | **partly, accepted** | 20 of 22 rail rows are still table rows. The division of labour is real (rail = clock times the table dropped; table = duration, cost, outcome) and the alternative is inventing timings. Not scored against. |
| R3 fourteen Pass pills | **fixed** | R06 treatment: green dot + plain "Pass"; filled pill kept for Running, Aborted, Blocked, Fail, in both table and rail. |
| K1 panel bottoms | **fixed** | Artefacts, Approvals and Assumptions columns all end at y=1170 on `03-ticket-dark.png`. |
| K2 no number on the screen | **fixed** | R13 stat strip; $18.40 measures 29px of digit height against R13's 18.6px normalised. |
| K3 three body lines | **fixed** | Two lines; run id moved into the tinted header strip. |
| K4 flow band with no canvas | **fixed** | Dotted inset canvas, 2px S4→base-advance connector. |
| K5 greyed Plan v1 | **fixed** | Struck through. |
| K6 light nesting | **fixed** | White cards on a page-coloured canvas inside a white panel — two clear steps in both themes. |
| P1 amber latency sparkline | **fixed** | Neutral accent line, no fill. |
| P2 donut centre | **fixed** | `$430.40 / Total`. |
| P3 donut segments vanish | **fixed** | Ramp floored; S2 and S5 legible on white. |
| P4 six regions | **fixed** | Range control in the top bar; five regions. |
| P5 heatmap replaces model rows | **fixed, with a new defect** | R02 heatmap present with a labelled Faster→Slower scale; see finding 3 for the off-scale cells it introduced. |
| P6 leaderboard bar heavier than the chart | **fixed** | 4px bars on a `--card-3` track. |
| P7 "not yet measurable" | **fixed** | One muted cell. |
| Q1 largest thing is a rail card | **partly** | Gauge "38m" 26px of digit height, main-column "9" 23px — a 3px difference, effectively level. The main column still carries no chart, which §3 does not give it. Not scored against. |
| Q2 slots as four boxes | **fixed** | Three 52px rows, avatar / name / role / right-aligned status. |
| Q3 the number 10 three times | **fixed** | Header chip gone; sixth grid cell is a kind. |
| Q4 disabled Approve is the strongest green | **fixed** | Outline; no filled accent button on the screen. |
| Q5 Kind column misalignment / rail stops short | **fixed, with a new defect** | Icon inside the Kind column, header and cells share x=298; rail ends at y=1233 with the main column. Stretching the cards to reach it created the voids in finding 4. |
| Q6 light sidebar same white as cards | **fixed** | Sidebar #F7F8F9, page #F1F2F4, cards #FFFFFF — three sampled surfaces. |
| T1 43px hole in eight KPI cards | **fixed** | Tickets card 1 bands measure 123–171 / 187–195 / 219–259; largest gap 24px. Identical structure on Runs and Report. |
| T2 four sparkline hues | **fixed** | One accent; red kept only on the Runs Fail card. |
| T3 nine columns | **fixed** | Eight. |
| T4 six identical grey pills | **fixed** | Six states set as plain muted text; pills only where the state is notable. |
| N1 light code blocks | **fixed** | `--card-3` with border; reads as an inset on white. |
| N2 six Pass pills, six chevrons | **fixed** | Check glyph on passing steps, chevron on the expandable one. |
| N3 columns 90px apart | **fixed** | Both end at y=1170. |
| F1 duplicate matrix cells | **not fixed** | See finding 2 — restructured, but 14 of 21 tier cells still repeat their neighbour. |
| F2 no focal point | **fixed** | Pass rate leads each agent card at 32px. |
| F3 190px under Sandbox policy | **fixed** | One card per row; full-width four-up policy band. |
| F4 two equal buttons | **fixed** | Open primary, Fixtures secondary. |
| F5 unlabelled policy hash | **fixed** | Gone. |

Fixed 29, partly 3 (R2, Q1 — both accepted), not fixed 1 (F1), plus three defects the fix pass introduced,
folded into the findings below.

## Remaining findings

**1. Runs and Factory: 44–45% of every table row is dead space in the middle. (Runs spacing 7, Factory spacing 7)**
On `04-runs-light.png` the Stage cell ends at x=558 and the Duration figure starts at x=984 — a **426px gap
in a 975px table**, in all twenty rows. On `07-factory-light.png` the Model cell ends at x=636 and the
Tier 1 figure starts at x=1215 — a **579px gap in a 1295px table**, in all seven rows. R15's model table,
the named reference for both, runs its seven columns from x=306 to x=1022 with a largest inter-column gap
of 66px — **9% of the table width against our 44%**. Dropping the `Started` column (the right fix for R1)
is what opened the Runs gap; nothing moved to fill it. *Fix:* set explicit column widths so no
inter-column gap exceeds ~80px — on Runs, push Duration/Cost/Outcome left to start around x=760 and let
Run/Ticket/Stage take the width; on Factory, close it with finding 2.

**2. Factory: the three tier columns still repeat every value, and the header asserts a variation the data
does not have. (Factory density 7)**
Seven rows × three tier cells = 21 slots carrying 7 facts; 14 cells are exact duplicates of the cell beside
them, unchanged in count from the first review. §2.7's manifest has **one budget per stage** and a tier
column reading "all" or "1–3" — there is no per-tier budget in the data at all, so "budget by tier" in the
card header is asserting something §2 does not say. *Fix:* one right-aligned Budget column plus a Tier
column carrying §2's own "all" / "1–3" values. That removes the 14 duplicate cells, makes the header true,
and gives the row two real columns where the 579px gap of finding 1 currently is.

**3. Report: the heatmap has a sixth cell state that is not on its own scale, and in dark it reads
backwards. (Report colour 7)**
Nine of 42 cells are neutral grey — `#E7EAEE` light, `#1F2429` dark — while the legend runs a six-step
green ramp from `#D9EBE0` to `#15803D`. Nothing says what grey means. In dark it is worse than unlabelled:
the grey cells sample at mean luminance 31 while the palest green step samples at 20, so the cells with no
value read as **busier than the fastest hours**. R02, the reference this panel copies, hatches its empty
cells so they can never be mistaken for a value. *Fix:* hatch the grey cells as R02 does and add "no data"
to the Faster→Slower scale, or fold them onto the scale's lightest step and drop the sixth state.

**4. Queue: two of the three rail cards are half air. (Queue density 7)**
Median latency runs 158→502 (344px) and holds content only from 182–196 and 313–414 — **205px empty, 60% of
the card**. By bucket runs 523→868 (345px) with content at 547–561, 640–649 and 676–774 — **173px empty,
50%**, as a 79px gap between the title and the bar and a 94px gap under the last legend row. Both come from
centring the content block in a card that was stretched to reach the main column's bottom edge (the Q5 fix).
R11's three rail panels — Top Tools, Model Split, Recent Changes — are packed to their edges with rows.
The By kind grid, third in our own rail, is packed and proves the pattern works. *Fix:* top-align the
content in both cards and distribute the slack into row height rather than into two gaps, or move the by-kind
counts into By bucket so all three rail cards carry rows.

## Notes, not scored against

- **Runs rail rhythm.** Rows with an outcome stack the time over the pill; rows without carry the time
  alone, so the right edge alternates between one and two lines. R11 replaces the whole two-line right
  stack with the pill (Retry 1/3, Tool Error). One line of CSS.
- **Tickets light bulk bar.** §3 asks for R04's dark bulk bar; in light it renders as another white card
  with no emphasis against the white table above it. Dark theme is correct.
- **Factory accent spend.** Five filled green Open buttons in one row, plus five status pills and the
  fixture-gate pill, make the bottom third of the screen the loudest part while the manifest table — the
  screen's declared subject — is grey. This follows F4 as written, so it is not scored, but R11 spends its
  filled accent on exactly one button per screen.
- **Ticket detail canvas fill.** The dotted panel is about 50% occupied (cards 350–440 and the base-advance
  node in a 310–570 panel) against R13's ~70% across two card rows. Reads as canvas now, which was K4's
  point; only worth revisiting if the panel is ever re-proportioned.
- **Run detail step pitch.** Collapsed steps sit 93px apart against R13's 88px raw (82px normalised) — 13%
  looser, from distributing six rows to a stretched column. Visible only in measurement.
- **Cross-screen keys.** Tickets shows LED-2291 / SET-118 / MP-77 while every other screen shows T-0412.
  Both are §2 columns and the Ticket detail header carries "T-0412 · LED-2291", so the mapping is
  discoverable; flagged only so it stays deliberate.

---

# Final pass (builder, after the re-score)

Scope: the four remaining findings only. All fourteen captures were retaken before the work (the set in
`captures/` was stale) and again after it. Gutters are the ink-to-ink distance between neighbouring cells,
measured on every row in the live document and re-checked in the light captures against the card ground;
card voids are the largest run of card height that carries nothing.

| Finding | Measured before | Measured after |
|---|---|---|
| **1. Table dead bands** | Runs **423px** between the Stage text and the Duration figure in a 974px table — `Stage` sat in a 374px `1fr` track holding 17px of text. Factory **585px** between Model and Tier 1 in a 1294px table. | Largest gap on any row, measured in the light captures against the card ground: Runs **89px**, Factory **92px**. Runs columns are 92 / 52 / 1fr / 52 / 48 / 78 at a 44px gap; the Stage cell holds a fixed 92px label plus a duration bar that takes the slack. Factory is 124 / 110 / 34 / 1fr at 22px; the last cell holds a budget bar and the figure. Both bars are the slot R15 gives its Trend column and R11 gives its Top Tools rows. |
| **2. Factory tier columns** | 21 tier cells carrying 7 facts, **14 exact duplicates**; the card header claimed "budget by tier". | One `Tier` column carrying §2.7's own `all` / `1–3` and one `Budget` column: **0 duplicate cells**, header now "budget per stage". Factory drops 147 → **136 words**. |
| **3. Heatmap sixth state** | 7 of 42 cells filled `--card-3`, off the six-step ramp. In dark they sampled lighter than the palest green, so no-data read as busier than the fastest hours. | No-data cells hatched at 45° on `--card-2` with a `--hatch` stroke, as R02 does. In dark they now sample **(24, 27, 31)** against **(20, 48, 34)** for the palest filled step, so no-data is the quietest state in both themes. The ramp is folded to five steps (.16 / .32 / .50 / .72 / 1.00) and the legend carries the five swatches **plus a hatched "No data" key**. |
| **4. Queue rail voids** | Three cards stretched to an equal 345px: Median latency **205px void (60%)**, By bucket **173px (50%)**. | Cards size to content and the lower two absorb the slack: **320 / 302 / 408px**, largest voids **47px (15%) / 63px (21%) / 23px (6%)**. The gauge is 278px wide (was 176) with the figure centred on the arc and `p90 3h 10m` under it; the legend rows and the by-kind cells grow, no gap does. The rail still ends level with the main column at 1076px. |

Word counts after (`python3 tools/wordcount.py 02-observatory/index.html runs=260`):

```
queue 194/240 · tickets 179/200 · ticket 185/260 · runs 253/260 · run 163/260 · report 118/220 · factory 136/260
```

## Not done, and why

- **The Factory policy card was not moved beside the manifest table.** Pairing them is the right R15 move on
  width, but not on height: the Stages card is 492px tall and four R09 switch rows are 319px, so the policy
  card would either leave a 173px hole beside the table — the F3 defect again — or stretch its four rows to
  107px each. Arithmetic settles it: a row of four short columns carries about 300px of ink, so at any width
  above ~600px some gap must exceed 100px unless something is drawn in the slack. The budget bar is that
  something, and it leaves §3's contents untouched.
- **The Runs Stage column still varies by 69px of ink** (`S4` 17px against `Index rebuild` 86px). That
  variance inside a fixed 92px label track is the whole of the remaining 89px gap; it is inherent to §2's
  stage names at this table width.
- **Both bar tracks are drawn at `--border-2`**, so a gutter measured with an absolute darkness threshold
  will read the empty part of a track as blank. Measured against the card ground — which is what the eye
  does — the bar column is continuous ink from the label to the figure.
