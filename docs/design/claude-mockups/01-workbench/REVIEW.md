# 01 Workbench — review against the references

Reviewed at 1600 wide against R04 (primary), R10, R12, R03, R05, R09. All fourteen captures were
composed side by side with the reference each screen copies and inspected on their own.

Measurement basis: the R04 app frame is 1812px wide inside its 2000px image; ours is 1574px inside a
1600px capture. Reference pixels are therefore multiplied by **0.869** to compare with ours.

## Word counts

`python3 tools/wordcount.py 01-workbench/index.html`

```
queue     169 / 240  ok
tickets   161 / 200  ok
ticket    176 / 260  ok
runs      191 / 220  ok
run       144 / 260  ok
report    112 / 220  ok
factory   169 / 260  ok
```

All seven under cap. Density is no longer a word-count problem; where density is marked down below it
is repeated cells and unlisted columns, not volume of prose.

## Scores

Light / dark where they differ.

| Screen | Hierarchy | Density | Spacing & alignment | Colour & contrast | Craft |
|---|---|---|---|---|---|
| Queue | 8 | 8 | 6 | 8 / **5** | 7 |
| Tickets | 6 | 7 | 6 | 7 / **5** | 7 |
| Ticket detail | 7 | 6 | 6 | 8 / 7 | 6 |
| Runs | 6 | 7 | **4** | 7 / 6 | 7 |
| Run detail | 7 | 8 | 7 | 8 | 7 |
| Report | 6 | 6 | 6 | 5 | 6 |
| Factory | 5 | **4** | 5 | 8 | 6 |

29 findings. Nothing on the direction is broken; the gap to the reference set is dead space, a frame
that disappears in dark, and duplicated cells.

## Findings

### Runs

**R1. A 482px empty band runs down the middle of all twenty rows.** Measured on
`04-runs-light.png`: text stops at x=687 (end of the Stage column) and resumes at x=1169 (Started).
That is 38% of the table width with nothing in it, repeated twenty times. R04's widest gutter in the
same measurement is 72px at its scale, 62px at ours. Fix: pull Started / Duration / Cost / Outcome
left so the largest gutter is under 80px, and let Stage take the slack, or right-align the numeric
group against the Outcome column at x≈1250 rather than the table edge.

**R2. Rows are 50px where R04's are ~61px at our scale.** R04's order rows have a 70px pitch in a
1812px frame, i.e. 60.8px in ours; §2's floor for a primary table is 56. Runs is at 50, Tickets at
52. Both tables read tighter than anything in the reference set. Fix: 58px in both.

**R3. The Export action in the title row is not in BRIEF-v2 §3.** §3 for Runs lists "Title. Four KPI
cards. Filters." and no action. Drop it or move it into the filter row.

### Factory

**F1. The three tier columns repeat the same model and budget verbatim.** Twenty-one cells carrying
seven distinct facts: "claude-haiku-4-5 $0.10" three times, "claude-opus-5 $12.00" three times, and
so on for all seven stages. BRIEF.md §2.7 does not list per-tier values — the tier field there is a
range ("all", "1–3"), so the table is inventing 14 duplicate cells. This is the single densest thing
in the direction and nothing in R04 or R12 repeats a value across columns. Fix: one Model column and
one Budget column, with the tier range as a third narrow column ("all" / "1–3").

**F2. The right column is empty below y=399.** The Sandbox policy card ends at 395 and the column is
uniform white to the bottom of the frame: a 475×198 void, then the agent-card row, then another
475×114. Roughly a fifth of the content area. Fix: put the manifest table full width, then a row of
five agent cards, then the four switch rows as a full-width four-column band (R09's rows are ~76px at
our scale against our 62, so they will take the slack).

**F3. Agent cards carry four key/value rows where §3 lists three.** Runs 30d, Pass rate, Last run,
Fixtures. R12's cards carry exactly three (Runs, Hits, Approval). Drop Fixtures — the Fixtures button
below already points at it.

**F4. No hero.** Nothing on the screen is larger than the 16.5px card titles except the page title.
R12 puts a KPI strip with 20px numbers above the card grid; R05 puts one 40px number at the top left.
Factory has 21 cells of 14px text and five cards of 14px rows. Fix: promote "41 fixtures pass" and the
manifest version into a stat pair at 28–32px under the title, or let the agent cards' pass rates be
the number.

**F5. All four sandbox switches are on.** R09's switch rows mix states and add key-caps; four
identical green toggles read as a placeholder. Fix: turn one off (the loopback proxy allowlist is the
natural one to show as off in a tier-1 profile) so the off state is designed.

**F6. Two hash formats in one direction.** §2 sanctions `1d9f…e4` (4 characters, ellipsis, 2). The
Factory header uses `9c1e42…8af2` (6 and 4) and the Sandbox policy card `c8a0…42` (4 and 2), while
Ticket detail and Run detail use the 4-and-2 form. Fix: 4-and-2 everywhere.

### Report

**P1. The KPI tints carry no meaning.** Sampled at y=110: card 1 `rgb(230,241,235)` and card 2
`rgb(228,242,234)` are the same green to within two levels, card 3 is amber, card 4 is neutral
`rgb(243,243,239)`. So two cards share a tint, one is warned and one is not tinted at all — the row
reads as an accident. R03's three cards each take a distinct pastel. In dark it inverts: card 4 is
`rgb(42,46,48)`, the *lightest* of the four, against `rgb(24,34,32)` for the others. Fix: one tinted
card (the hero) and three neutral, in both themes, or four distinct tints per R03.

**P2. The hero plot is a 4.4:1 ribbon.** The plot area is roughly 1220×280. R03's revenue chart is
about 470×230 inside its card, near 2:1, which is why its curve has shape. At 4.4:1 our 31-day line
flattens into noise. Fix: raise the plot to ~380px tall, or split the card so the chart takes two
thirds of the width with the median and range facts beside it.

**P3. The callout is detached from its point.** The "26 Aug · $28.70" box ends at x=1053; the circled
data point is at x=1103, with nothing joining them. R03 sits its callout directly above the circled
point. Fix: centre the box over the point or draw a 1px leader.

**P4. No hero number.** Four KPI numbers at 34px and a 32px page title, so five things are the same
size. R05 gives one number 40px cap against a 16px nav and 24px section titles — a 2.5:1 step. Fix:
drop three KPI numbers to 26 and keep "Cost per merged PR $13.70" at 34, or keep all four at 26 and
let the chart be the hero.

**P5. Seven regions and three charts against §2's five and one.** Title, KPI row + baseline line,
hero chart, Runs by outcome, Stage cost share, Tag leaderboard, Model spend. §3 asks for all of this
content, so this is a rule conflict rather than a builder error, but the page is visibly busier than
R03. Fix: merge Tag leaderboard and Model spend into one two-column card (five regions), and give the
outcome bars a y axis so the second chart earns its place.

**P6. The donut legend's last three tints are indistinguishable.** S6 6%, S2 4%, S5 2% sit at the
pale end of a six-step green ramp and their dots read as the same colour at 100%. Fix: five steps
with the tail grouped as "Other 12%", or label the arcs instead of using a dot legend.

**P7. The "median $13.70" label sits inside the plot at the right edge**, overlapping the plot frame
and passing within ~12px of the curve. R03 leaves its dashed comparison series unlabelled. Fix: move
the label to the left end of the dashed line where the curve is 40px clear, or into the card header.

### Tickets

**T1. The page title and the KPI numbers are the same size.** Measured caps: title "Tickets" 24px,
KPI digit "12" 23px — a 1.04 ratio. R12's title cap is 18.6px at our scale against a 14px KPI digit,
1.33. Nothing on our screen is the hero. Same defect on Runs. Fix: KPI numbers to 26–28 and hold the
title at 32.

**T2. Nine columns.** Checkbox, Ticket, Title, Repo, Tier, State, Stages, Cost, Age. §2 caps a table
at eight; R04 runs checkbox plus seven. Fix: fold Tier into the state cell or drop Repo (it is
already implied by the ticket key on every other screen).

**T3. The bulk bar slices the "Context" pill in half.** The bar's right edge lands at x=1170 and the
T-0411 state pill starts at x=1174, so half a green pill sticks out from behind the bar. R04's bar
covers a name and an avatar, which read as occluded content rather than as clipping. Fix: shift the
bar 60px left so both its edges fall on empty cells, or dim the row it covers.

**T4. Running and Pass are the same green.** `--acc` `#14684A` and `--pass` `#14764F` are eight levels
apart, so the "Running" and "Pass" pills on Runs are indistinguishable, and "Review" on Tickets reads
as a pass. §2 allows the accent for running, but then the accent must not also be the pass colour.
Fix: keep green for pass and move running to the accent as a hollow ring or a pulsing dot with
neutral pill text.

### Queue

**Q1. Two voids in the right rail.** Measured on `01-queue-light.png`: 82px of uniform ground between
"50 decisions today" and the first divider, and 157px between "When convenient 2" and the second.
R04's four rail sections hug their content with roughly equal 24px padding top and bottom and let the
leftover space fall at the bottom of the rail. Fix: size each section to its content and put the
slack below "BY KIND".

**Q2. Dark theme: the frame disappears.** Sampled: sidebar `rgb(10,12,13)`, content `rgb(18,20,22)`,
rail `rgb(22,25,26)`, page behind the frame `rgb(6,7,8)`. Eight levels separate the sidebar from the
content and four separate the page from the sidebar, so R04's defining move — a dark rail against a
light canvas — reads as one flat black field. Fix: raise the content surface to about `#1A1D20` and
the rail to `#1E2224`, keep the sidebar at `#0A0C0D`, and add a 1px `rgba(255,255,255,.08)` edge on
the sidebar's right. Same fix applies to every screen in dark.

**Q3. The BY KIND grid leaves an empty sixth cell, and the per-row bucket dot §3 asks for is gone.**
The 2×3 grid holds five values with a hole bottom right; R04's Overview grid fills all six. The
builder replaced the per-row dot with three group-header rows ("ACT TODAY", "THIS WEEK", "WHEN
CONVENIENT"), which §3 does not list. The substitution reads well, but it should be recorded as a §3
deviation for the owner to accept or reject. Fix for the grid: six cells, or a 2×2 grid with the tail
grouped.

### Ticket detail

**K1. A 710×101px void under the left half of the stage strip.** The stage cards end at y=258 and the
base-advance node and review gate occupy only x=1025–1555 at y=285–335, leaving x=300–1010 empty for
101px. Fix: reduce the strip-to-panel gap to 28px and hang the base-advance node from S4 with a short
16px connector, or run the review gate full width under the strip.

**K2. The seven stage cards are identical.** Every card carries the same pale-green S badge and the
same green tick; no card marks the current stage, and the ticket is in Review. R12's six agent cards
show five different statuses with different button pairs, which is what stops that grid reading as a
template. Fix: give S6 the accent border and a "current" dot, and drop the tick from a card that
carries a duration and a cost already.

**K3. The Artefacts panel has an unlisted CLASS column.** §3 lists "name, version, short hash". The
column holds "internal" ten times and "public" once — eleven cells for one bit of information. Fix:
drop the column and mark the one public artefact with a small pill on its name.

**K4. The Approvals card carries two uppercase group labels.** "PLAN V2" and "PACKET V1". §2 allows
one uppercase label per card. Fix: keep one as the card's own label and separate the two groups with
a hairline and a sentence-case row, or split them into two cards.

### Run detail

**N1. The Inputs badge reads 9 over five rows.** The count badge on every other panel matches the
visible rows (Tasks "6 of 6", Artefacts "11"). Nine is the hash count from the event log. A badge that
contradicts the list beneath it reads as a bug. Fix: "5", or move the hash count into the panel's
subtitle position as "9 hashes".

**N2. A 605×150px void below the event log.** The log card ends at y=825 and the right column is
empty to y=985 while the left column runs to 918. Fix: let the event log grow to the column's full
height (§3 caps it at ten lines, so add padding rather than lines) or move Guard decisions into the
right column under Inputs so the two columns end together.

## What was checked and is right

Row height on Queue (64px against R04's 61 at our scale), sidebar width (254 against R04's 260),
body size (11px cap against R04's 11.3), the floating detail card's structure, run ids and ticket keys
in the UI font rather than mono, monospace confined to the event log and hashes, one pill style, the
child-run indent, the pulse on the running row, sentence-case kinds and states throughout, and all
seven word counts under cap.

## Builder response

Applied at 1600 wide, three capture-and-fix passes, all 14 PNGs re-shot. One line per finding.

### Runs
- **R1 fixed.** Columns re-slacked evenly (Run 203 / Ticket 159 / Stage 276 / Started 148 /
  Duration 152 / Cost 124 / Outcome 181 / `···` 48), cells at 15px, a 28px stage chip added to the
  Stage cell and a trailing `···` column added (R04 has both). Widest gutter is now ~105px, not
  482. Started, Duration and Cost are left-aligned: right-aligning a number after a left-aligned
  text column stacks two gutters at that junction, which is what made the band. R04 left-aligns its
  own Total and Date columns. Recorded in README under Deviations.
- **R2 fixed.** Runs and Tickets rows both at 58px.
- **R3 fixed.** The Export action is gone from the Runs title row.

### Factory
- **F1 fixed.** One Model column, one Budget column (right-aligned), tier range in a narrow column
  ("all" / "1–3"). 14 duplicate cells removed.
- **F2 fixed.** The manifest table and the right column (stat pair + sandbox policy at 76px rows)
  now stretch to the same height; the five agent cards run full width beneath. No empty column.
- **F3 fixed.** Fixtures dropped; three key/value rows per card, as R12.
- **F4 fixed.** A stat pair under the title: fixture gate **41** at 36px (the screen's hero, above
  the 32px title) and manifest **v14** at 24px with its hash. Both facts were already the §3 header.
- **F5 partly fixed.** The fourth row is a "per stage" value control instead of a fourth identical
  toggle, so the control set varies the way R09's does. Not turned off: §2.7 states the loopback
  proxy allowlist is part of the digest, and an off toggle would assert a policy the data denies.
- **F6 fixed.** 4-and-2 everywhere: `9c1e…f2`, `c8a0…42`, `1d9f…e4`.

### Report
- **P1 fixed.** One tinted card (the hero) and three neutral, in both themes, on every KPI row in
  the direction — Report, Tickets and Runs now share the treatment.
- **P2 fixed.** The chart card is two thirds of the row with the donut beside it; the plot is
  ~730×310 (2.4:1) instead of 1220×280 (4.4:1).
- **P3 fixed.** The callout sits at the point's own y, with a 16px leader into the circle.
- **P4 fixed.** $13.70 at 40→36px against 27px for the other three; nothing else on the screen is
  larger. The donut centre total was cut to ~28px so it cannot compete.
- **P5 fixed.** Four regions plus the title: KPI row + baseline, chart + donut, outcome bars +
  a merged Tag leaderboard / Model spend card. The outcome bars gained a y axis (0 / 6 / 12).
- **P6 fixed.** The ramp is four steps; the tail is one row, "Other 12%".
- **P7 fixed.** The in-plot label is gone; "— median $13.70" is a dashed swatch in the card header.

### Tickets
- **T1 fixed.** Title 32, KPI numbers 27, hero "Open 12" at 36. Same on Runs.
- **T2 fixed.** Eight columns: the checkbox folded into the Ticket cell, as R04 does with Order.
- **T3 fixed.** The bar now falls on whole cells; nothing is sliced.
- **T4 fixed.** Running is a ringed accent dot on a neutral pill. Green is reserved for pass and
  for Merged; Review and PR opened are neutral pills.

### Queue
- **Q1 fixed.** Rail sections size to their content and the last one takes the slack, so the
  leftover space falls at the bottom of the rail, as in R04.
- **Q2 fixed.** Dark surfaces separated: page `#0E1113`, sidebar `#07090A`, content `#1C2023`,
  rail `#222629`, cards `#262A2E`, borders 11% white, hairlines 7%, plus a 1px white edge on the
  sidebar and an elevated surface for the bulk bar and the floating-card header.
- **Q3 half fixed.** The by-kind grid has no hole: "Other 5" spans both columns. The per-row bucket
  dot stays replaced by a bucket group-header row; the deviation is recorded in the README for the
  owner to accept or reject.

### Ticket detail
- **K1 fixed.** Base advance and review gate are a single full-width bar split on the seven-column
  stage grid (1–5 / 6–7), so the S4 and S6 connectors each land on their own segment and no empty
  band is left.
- **K2 fixed.** S6 carries the accent border, a filled accent badge, a tinted footer and a ringed
  current dot; the other six keep their pass tick, which §3 asks for as the stage outcome.
- **K3 fixed.** CLASS column dropped; PR body carries a `public` pill on its name.
- **K4 fixed.** "Plan v2" and "Packet v1" are sentence-case muted rows; the card keeps no
  uppercase label of its own.

### Run detail
- **N1 fixed.** The Inputs badge reads 5.
- **N2 fixed.** The grid stretches and the event log panel grows into the slack, so both columns
  end on the same line.

---

# Re-score

Fresh pass, second reviewer. All 14 captures viewed alone and composed side by side with the
reference each screen copies (R04 for Queue / Tickets / Runs / Run detail, R12 for Ticket detail and
Factory, R03 + R05 for Report). Word counts re-run: queue 169, tickets 161, ticket 165, runs 192,
run 144, report 110, factory 137 — all under cap.

Scale basis unchanged: the R04 frame is ~1821px inside a 2000px image, ours ~1567px inside 1600, so
reference pixels are multiplied by **0.86**. R04's widest inter-column gutter, measured across two
rows, is 94px raw = **81px at our scale**; its largest rail void is 51px.

## Scores

| Screen | Hierarchy | Density | Spacing & alignment | Colour & contrast | Craft |
|---|---|---|---|---|---|
| Queue | 8 | 8 | **6** | 8 | 8 |
| Tickets | 8 | 8 | 8 | 8 | 8 |
| Ticket detail | 8 | 8 | **6** | 8 | 8 |
| Runs | 8 | 8 | **7** | 8 | 8 |
| Run detail | 8 | 8 | **7** | 8 | 8 |
| Report | 8 | 8 | **7** | 8 | 8 |
| Factory | 8 | 8 | **7** | 8 | 8 |

Does not pass. Hierarchy, density, colour and craft clear the bar on every screen; **spacing and
alignment fails on six of seven**, and six of those six are one defect repeating: when a row holds
two or three short values, the value columns are parked at the far right and the middle of the row
is empty. The fix pass removed that hole from the two places the first review named it (Runs, the
Factory tier columns) and left it everywhere it was not named.

Measured hierarchy, for the record: page title cap 24px on every screen; the one hero number per
screen cap 27; non-hero KPI numbers cap 20; card titles cap 17; table cells cap 11. Dark surfaces
are now sidebar `rgb(7,9,10)` / content `rgb(28,32,35)` / rail `rgb(34,38,41)` / cards
`rgb(38,42,46)` — 21 levels between sidebar and content against 8 before.

## Per-finding verdict

| # | Verdict | Evidence in the capture |
|---|---|---|
| R1 | **partly** | The 482px band is gone. Widest gutter on `04-runs-light` is now 196px (Stage → Started on short stage names), and a constant 156px strip sits between the Outcome pill and the `···` on all 20 rows. R04's widest is 81px at our scale. |
| R2 | fixed | Hairline pitch measured at 58px on Runs and Tickets. |
| R3 | fixed | No Export in the Runs title row. |
| F1 | fixed | One Model column, one Budget column, tier range beside the stage. |
| F2 | fixed | Manifest table and the right column both end at y=618; five agent cards run full width below. No empty column. |
| F3 | fixed | Three key/value rows per agent card. |
| F4 | fixed | "41 fixtures pass" cap 27 against the title's cap 24 — the screen has a hero. |
| F5 | partly | The fourth row is a "per stage" value control, so the control set varies as R09's does; no off toggle. Builder's reason (the allowlist is in the digest) is sound. Accept. |
| F6 | fixed | `9c1e…f2`, `c8a0…42`, `1d9f…e4`, `a11f…3c` — 4-and-2 everywhere. |
| P1 | fixed | Card 1 `rgb(230,241,235)`, cards 2–4 `rgb(255,255,255)`. One tint. |
| P2 | fixed | Plot area 715×280 = 2.55:1, against 4.4:1 before. |
| P3 | fixed | Callout sits at the point's own y with a leader into the circle. |
| P4 | fixed | Hero digits cap 27, the other three cap 20, title cap 24. |
| P5 | fixed | Four regions plus the title; outcome bars carry a 0 / 6 / 12 axis. |
| P6 | fixed | Four ramp steps, tail grouped as "Other 12%". |
| P7 | fixed | "— median $13.70" is a dashed swatch in the card header; nothing sits inside the plot. |
| T1 | fixed | Title cap 24, hero "12" cap 27, the other three cap 20. |
| T2 | fixed | Eight columns; checkbox folded into the Ticket cell. |
| T3 | fixed | Bar right edge x=1172, next ink x=1210. Nothing sliced. |
| T4 | fixed | Running is a neutral pill with a ringed accent dot `rgb(89,91,91)` ground; Pass is a green tint `rgb(159,201,183)`. Unmistakable in both themes. |
| Q1 | **partly** | The 82px and 157px mid-rail holes are gone and sections hug their content, but the slack is now one **304px void** at the bottom of the rail (y=678 to the frame edge), 32% of the rail's height. R04's rail runs content to the frame edge and its largest void is 51px. |
| Q2 | fixed | See the surface ladder above; the 1px white sidebar edge is present. |
| Q3 | partly | The by-kind grid has no hole ("Other 5" spans both columns). The per-row bucket dot is still a group-header row — a live §3 deviation for the owner, not a defect. |
| K1 | fixed | Base advance and Review gate are one full-width bar split on the stage grid; no band under the strip. |
| K2 | fixed | S6 carries the accent border, a filled badge, a tinted footer and a ringed current dot. |
| K3 | fixed | CLASS column gone; one `public` pill on PR body. |
| K4 | fixed | "Plan v2" / "Packet v1" are sentence-case muted rows. |
| N1 | fixed | Inputs badge reads 5 over five rows. |
| N2 | fixed | Both columns end at y≈935. |

25 fixed, 4 partly, 0 not fixed, 0 reverted.

## Regression introduced by the fix pass

**G1. Growing one KPI number per row broke the row's baseline.** On `06-report-light` the four KPI
cards share a label baseline (y=128) and top-align their numbers (147–149), but the hero is 36px and
the others 27px, so the hero's sub-label "median" lands at y=190 while "of 38 closed",
"send-backs 6" and "p90 3h 10m" all land at y=180 — a 10px step across four otherwise identical
cards. Same cause on Tickets and Runs, where the hero digit's baseline sits 9px below its three
neighbours (208 against 199). R03's and R12's KPI rows keep one type size across the row and get a
hero from tint and position instead. Fix: baseline-align the numbers (or bottom-align the card's
content block) so the sub-label row is common, and keep the size step to the tint plus one card.

## Remaining findings, most important first

**A1. The mid-row hole survives on the three screens the first review did not name.** Same defect as
R1/F1, same measurement method:

- `01-queue-light`, every row: text stops where the Needs value ends and nothing resumes until Age —
  **419px** on "PR outcome", 355px on "Manual pause", 233px on "Control event". That is 27% of the
  1030px table width, repeated ten times, in a table with only four data columns where R04 runs seven.
- `03-ticket-light`, Artefacts panel, all 11 rows: **436px** between the artefact name and the
  VERSION column, inside a 650px card, with VERSION and HASH crammed into the right 150px behind a
  45px margin.
- `05-run-light`, Inputs panel, all 5 rows: **405px** between the value and the hash column inside a
  600px card.

R04's widest gutter is 81px at our scale and its rail cards set the value hard against the card's
right edge with the label at the left, no third parked column. Fix: on Queue give the table the
columns it is short of (bucket, or the trailing action moved in) or shrink Needs and pull Age left so
the largest gutter is under 120px; in the Artefacts and Inputs cards, right-align the hash to the
card edge and set VERSION / value immediately left of it so the row is label-left, values-right with
one gutter, not two.

**A2. The Queue rail's bottom 304px is empty.** Measured on both themes at x=1265–1580: last ink at
y=678, rail runs to y=982. R04 fills its rail with four sections (Receipt of goods, Orders status,
Overview, Top sellers) and clips the last one at the frame edge; ours carries three and stops a third
of the way up. The screen reads emptier than its reference beside it. Fix: add the fourth section
R04's rail implies — the oldest-item or send-back count, or the by-kind grid re-laid as three rows —
or let the by-kind grid's cells grow so the three sections divide the rail evenly.

**A3. Runs still carries a fixed 156px dead strip and a 196px gutter.** `04-runs-light`: between the
Outcome pill's right edge (x=1408) and the `···` (x=1564) there is nothing, on all 20 rows; R04's
Date → `···` gap is 35px raw, 30px at our scale. The Stage → Started gutter reaches 196px on
short stage names. Fix: right-align the Outcome pill against the `···` slot, and let Started move
left by ~80px so the numeric group sits closer to Stage.

**A4. The Factory stage manifest spreads four short columns across 725px.** Measured on
`07-factory-light`: 201px between "S0 Intake" and the Tier value, 269px between "scripts" and the
Budget figure on S6. Seven rows of four values in a card wider than R04's whole table region. Fix:
narrow the card to about two thirds and put the fixture-gate stat pair beside it, or add the column
the table is missing (runtime, or the per-stage agent name that the cards below already carry).

**A5. The two halves of the Report's merged card do not share a row grid.** Tag leaderboard rows sit
at y=813 / 861 / 908 / 956 / 1005; Model spend rows at 859 / 907 / 955. The right half is centred
against the left half's five rows, so it opens 46px low and closes 95px high, and the divider between
them runs past empty ground at both ends. Fix: top-align both lists to the same first-row baseline
and let the shorter one end short, as R15's stacked panels do.

**A6. The neutral state pill disappears on the selected row.** `02-tickets-light`: the "Review" pill
fill is `rgb(240,240,235)` on a selected-row ground of `rgb(243,243,239)` — 1.02:1, so the chip has
no shape and T-0412's state reads as bare text while every other row shows a chip. Fix: give the
neutral pill a 1px `--ctl-bd` ring, or darken the pill one step on `[aria-selected]` rows.

**A7. Duration is left-aligned, so its colons do not line up.** `04-runs-light`: "31:05", "3:44" and
"22:10" all start at x=1096, so the minute field wanders by a digit down the column. The Cost column
survives left alignment because every value is `$N.NN`; Duration does not. Fix: right-align Duration
only, or pad to `mm:ss`.

---

# Spacing pass

Targeted pass on the one axis still below 8. Scope: A1–A5, G1 and the two minor findings above;
nothing else was touched. All 14 PNGs re-shot at 1600 wide, sequentially, one Chrome profile per
shot. Gutters are measured in the capture as the pixels between the end of a column's **longest**
value and the start of the next column's value; where a short value widens the gap the second
number is given. R04's own widest inter-column gutter is 81px at our scale.

| # | Before | After | What changed |
|---|---|---|---|
| **A1 Queue** | 419px on "PR outcome", 233px on the longest Needs value | **55px** longest, 251px on "PR outcome" | The 5-column table is now sized to its content (Kind 196 / Ticket 104 / Needs 356 / Age 108 / `···` 80 = 824px) and the rail takes the width the table cannot carry (336 → 414). Age is left-aligned, so a right-aligned number no longer stacks a second gutter on the text column's own slack. Kind → Ticket 47, Ticket → Needs 54, Age → `···` 83. |
| **A1 Ticket, Artefacts** | 436px between the name and VERSION inside a 650px card | **85px** name → version, **73px** version → hash | Card narrowed to its content (652 → 356, R04's rail-card measure); the hash is right-aligned to the card edge with VERSION immediately left of it. The Approvals card beside it splits into its two groups (Plan v2 / Packet v1) over a hairline so its rows stay tight at the wider measure: name → role 271 → **97px**. |
| **A1 Run, Inputs** | 405px between the value and the hash inside a 600px card | **48px** label → value, **58px** value → hash | Run detail is three columns (Tasks 452 / Inputs + Guard 336 / Event log 430) instead of two, so the Inputs card is 336 wide. Guard decisions moved to the middle column, which is also what §3 asks for (left = tasks, right = inputs, guard, log). |
| **A2 Queue rail** | 304px empty at the bottom, last ink y=678 | **last ink y=984 against a frame edge at y=985** | Four sections as in R04: median-latency gauge (enlarged to a 150px arc), by-bucket, by-kind, and a new "Recent decisions" list of three rows. Sections size to their content and share the leftover equally instead of piling it at the bottom. |
| **A3 Runs** | constant 156px strip between the Outcome pill and `···`; 196px Stage → Started | **107px, constant**; **105px** Stage → Started (175px on "Intake") | The outcome pill is a fixed 88px slot (§2's "fixed-width slots for pill and trailing action"), so the gap no longer swings 45px with the word length; `···` is a 40px slot at the row's end. Column widths re-cut so every one of the seven gutters is 103–109px, i.e. one rhythm rather than one hole. **Not under 100:** eight columns of short values in a 1258px table leave 748px of slack; spread evenly that is 107px per gutter, and any concentration (including giving the slack to Stage, as the finding suggests) makes one gutter worse. Under 80 would need the table inset to ~1170px, which breaks the 30px page gutter. |
| **A4 Factory** | four short columns over 725px; 201px Stage → Tier, 269px Model → Budget | **68px** Stage → Tier, **62px** Tier → Model, **86px** Model → Budget | Manifest card narrowed to its content (725 → 560; Stage 198 / Tier 86 / Model 184 / Budget 90). The fixtures-and-policy column takes the released width (480 → 678). Both columns still end level. |
| **A5 Report** | right half opened 46px low and closed 95px high | **first rows aligned to 1px** (left 804, right 803) | `.twinb`'s second half no longer centres its rows; both halves start on the same baseline and the shorter list ends short, as R15's stacked panels do. |
| **G1 KPI baseline** | hero sub-label 10px below its neighbours; hero digits 9px low on Tickets and Runs | **sub-labels level (182 across all four); digits 0px on Tickets, 1px on Runs, 1–2px on Report** | The number line is a fixed 34px box with a fixed line-height, so the sub-label row is common; the hero is larger by font size only, with a 2px optical correction that does not move the row below it. |
| **minor, pill** | neutral pill 1.02:1 on the selected row | **1px `--ctl-bd` ring, 1.22:1 at the edge** | Ring applied only to neutral pills on `.r-sel` rows, so pass / fail / warn pills keep the one pill style. |
| **minor, Duration** | colons wander a digit down the column | **colons on one x** | Tabular numerals plus a `1ch` left pad on one-digit-minute values. Right-alignment was not used: with 14 of 20 values carrying a one-digit minute it would have moved the colon on more rows than it fixed, and it would have doubled the gutter at the Started → Duration junction. |

## Still open after this pass

- **Runs gutters sit at 103–109px**, not in R04's 40–80 band. Arithmetic, not layout: the table
  carries 593px of ink in 1258px. Uniform is the optimum; the numbers above are the best achievable
  without insetting the table.
- **Ticket detail, Assumptions**: 465px between the assumption and its `S2 · default` stamp. That is
  a two-field row with the value hard against the card's right edge — the R04 rail-card pattern this
  review sanctioned — and pulling the card narrower would leave the right column 108px short of the
  Artefacts card beside it. Left as is.
- **Run detail** now ends at y=852 against a frame edge at 985 (133px), where the two-column version
  ended at 935. The three columns end level with each other; the page simply carries less height than
  the viewport. Filling it would put the void inside the Tasks card instead.
- Queue rows still carry a group-header row rather than a per-row bucket dot (the §3 deviation
  recorded in the README); the rail is 414px against R04's 349 at our scale, because five short
  columns cannot spend 982px.
