Observatory polish review

## Baseline (before polish)

Scores 1–10 per axis, `dark / light`. Measured from side-by-sides of
`02-observatory/captures/*` against the BRIEF-v3 §4 reference for each screen, at 1600px.
Reference figures quoted at their native width are converted to 1600 (R18/R19/R22 ×0.8, R23 ×0.8,
R13 ×0.8).

| Screen | Hierarchy | Density | Spacing & alignment | Colour & contrast | Craft |
|---|---|---|---|---|---|
| Queue (R18 + R19 + R23) | 6 / 6 | 7 / 7 | 7 / 7 | 7 / 6 | 6 / 6 |
| Tickets (R18) | 6 / 6 | 6 / 6 | 7 / 7 | 7 / 6 | 6 / 6 |
| Ticket detail (R23) | 4 / 4 | 5 / 5 | 5 / 5 | 5 / 5 | 3 / 3 |
| Runs (R18) | 6 / 6 | 6 / 6 | 7 / 7 | 7 / 6 | 6 / 6 |
| Run detail (R13 + R23) | — / 7 | — / 6 | — / 7 | — / 7 | — / 6 |
| Report (R18 KPI) | 5 / 5 | 6 / 6 | 7 / 7 | 6 / 6 | 6 / 6 |
| Factory (R18 + R23 + R22) | 6 / 6 | 6 / 6 | 7 / 7 | 7 / 6 | 5 / 5 |

`02-observatory/captures/05-run-dark.png` does not show the Run detail screen — it is a capture of
the mockups index page ("Soft Factory mockups, round 2", direction cards and capture thumbnails).
Run detail dark is therefore unscored; it must be recaptured before the polish pass is judged.

Two defects are shared by every screen and are counted once in each screen's Colour and Craft cells,
not repeated below:

- **No light card shadow.** BRIEF-v3 §3 gives light cards `0 1px 2px rgba(16,24,40,.04)` (R18, R22).
  Sampling straight down through a card edge in `02-tickets-light.png` at x=450 gives
  y319 `#F7F8FA` (card) → y320 `#E4E6EA` (border) → y321 `#F4F5F7` (page): border straight to page,
  no shadow band. R18's cards lift off the page; ours are drawn on it. Light page is `#F4F5F7` and
  the sidebar is `#FFFFFF`, where §3 asks for page `#F1F2F4` and sidebar `#F7F8F9` — so the only
  separation between a white card and the page is an 11-value step plus a hairline.
- **Search pill has no keycaps.** The pill is 44px tall (y32→y76) as §3 asks, but scanning
  x860–1020 across its right end finds no glyphs. R18 puts two 22px `⌘` `K` keycaps there
  (at 2000: two ~28px rounded squares inside the pill's right inset).

---

### Queue

Reference: R18 rows, R19 detail card, R23 rail.

1. **Rows are 10px short.** R18's table rows run at an 82px pitch at 2000 (text bands at
   861 / 943 / 1025 / 1107 / 1188 / 1271 / 1352) = 66px at 1600. Ours run at 56px
   (`01-queue-light.png`, bands 310–332, 366–388, 422–444, 478–500 …). §3 Table shell says 60px.
   Take the rows to 60 and the ten items still fit above the detail card.
2. **No table shell header.** §3 wants a 68px card header: title 17/600 + "10 items" 13 muted on the
   left, a 40px search pill and up to three 40px filter dropdowns on the right. We have a bare
   "Open items" title and the filters live outside the card as four ghost chips
   (Bucket / Kind / Ticket / All filters). §4.1 explicitly replaces those chips with
   Bucket / Kind / Ticket dropdowns inside the shell.
3. **The act card carries no emphasis.** §3 puts `.is-sel` (1px semantic border + `0 0 0 4px` at 8%
   and `0 0 24px` at 18% in dark, `0 0 0 4px` at 10% in light) on the selected queue item card, as
   R23 does on every live node. Ours has the same 1px `--border` as the neutral cards around it, so
   the one surface a person acts on is the least marked thing on the screen.
4. **No R19 card head.** §4.1 asks for two pills (kind, bucket) above the title. Ours goes straight
   from a tab row to the 17/600 title; the kind and bucket only appear as words in the meta line.
5. **The evidence figure outranks the title.** The "9" in the evidence line is set at KPI scale
   (~26px digit height, the same as the Tickets KPI numbers) at the card's bottom-left, so the
   largest glyph inside the decision card is a check count, not the subject. R19 keeps one 16px
   title as the card's only large type.
6. **The rail is not R23's details rail.** §4.1 asks for label / value / stat boxes. "By kind" is a
   2×3 grid of hairline-ruled cells, each holding one digit and a word (2, 1, 1, 1, 1, 4) over
   ~360px of height — a table drawn for six single-digit counts. R23's rail packs the same weight
   into two 66px bordered boxes.
7. **No trailing ⋮.** R18 closes every row with a ⋮ in a circle (30px at 1600). Our rows end on the
   bucket dot, so the row has no affordance and the last column is ragged against the card edge.
8. **Type row rhythm inside the slot rows is right but the tab row is doing two jobs** — Packet /
   Evidence / Slots on the left and four action pills on the right share one line. R19 keeps the tab
   row and the action row separate; the four pills at 1600 crowd to within 8px of the card edge.

**Keep:** page gutter 28px (card border x276 against the sidebar edge x248) and sidebar 248px, both
per §3; the median-latency gauge (one number, one arc, one p90 line); the three slot rows with 28px
initials avatars and a green "Approved 14:12" / amber "Open" ending; one accent with bucket dots as
the only second hue; word count 194 / 240.

---

### Tickets

Reference: R18.

1. **KPI card is 30% too tall.** R18's card is 211px at 2000 (top y322, bottom y533) = 169px at 1600;
   §3 says 168. Ours is 220px (`02-tickets-light.png`, top y100, bottom y320). The extra 51px is a
   full-bleed sparkline band, and it pushes the table 50px down the page on every screen that uses
   the card.
2. **KPI anatomy is not R18's.** R18: 38px icon circle top-left, 110×40 sparkline top-right ending in
   a 7px ring dot, label at y≈94 from the card top, number 34/600 with the delta pill **on the same
   baseline**. Ours: a 44×44 rounded square icon with the label set beside it at the same y, number
   under it (26px digit height, y147–172, i.e. 35px from the card top against R18's 145), a muted
   phrase under that, then the sparkline. Four stacked lines where R18 has two rows.
3. **Sparkline bleeds to the card edge.** R18's is inset 137×50 at 2000 (x483–619, y355–404) =
   110×40 at 1600, top-right, with a ring dot terminator. Ours is ~305×100 flush to the card's left,
   right and bottom edges, so the card's radius is cut and the chart reads as a footer band.
4. **No delta pill.** R18 pairs every number with a 36px-at-2000 (29px at 1600) tinted pill
   ("+12.4%"). §3 allows a muted "vs 30d" phrase instead, and we use one, but as a third line rather
   than beside the number — so nothing sits on the number's baseline.
5. **No table shell header.** Same as Queue finding 2: no title, no "12 results", no search pill, no
   State / Tier / Class dropdowns inside the card. R18 carries all four in an 85px-at-2000 (68px)
   header band.
6. **Rows 56px against R18's 66px** (bands 438–459, 494–517, 550–573, 606–629; pitch 56). §3 asks 60.
7. **No trailing ⋮ circle** — R18 has one on all eight rows.
8. **Two state systems in one column.** Review / Plan review / Escalated / PR opened / Merged /
   Rejected are tinted pills; Implementing / Checks / Clarifying / Intake / Abandoned / Context are
   bare muted text in the same column. BRIEF-v2 §2 allows one pill style per direction and forbids
   mixing pill and non-pill treatments in a row; the R06 dot-plus-word form is the fix for the
   unfilled half.

**Keep:** card width 305px and gap 24px — R18's card is 380 at 2000 = 304, so the KPI grid geometry
is already right; the seven S0–S6 stage dots; the selected row's 2px accent bar plus tint; the dark
bulk bar; word count 179 / 200.

---

### Ticket detail

Reference: R23, copied wholesale per §4.3. This is the largest gap in the set.

1. **No right rail.** R23 devotes a 380px column to Mission Details (name, priority pill, progress
   bar with %, two bordered stat boxes), Connected Apps and the assistant card. §4.3 asks for the
   same column: "Ticket" details card with a "5 of 7 stages" progress bar and Started / Elapsed stat
   boxes, "Links", and Approvals as an R13 step list. We have no rail; Approvals is a panel below,
   and there is no progress bar anywhere on the screen.
2. **Stage cards are less than half the reference.** R23's agent card is 320×120 at 2000 = 256×96 at
   1600, §3 says 300–320 wide. Ours measures 138×80 (`03-ticket-light.png`: card x318→456,
   y367→447) — eight of them abreast. At that width nothing but "Implementation" and "31:05 · $9.85"
   fits, which is why the card has no icon tile and no status line.
3. **No progress bar on any stage card.** R23 gives every card a 3–4px gradient bar with the % at its
   right (67%, 78%, 62%) — it is what makes the flow readable at a glance. §3 requires it: full for
   done, partial for running, empty for pending.
4. **No icon tile.** §3: 34px tile at radius 9, filled with the card's hue at 14% (R23 uses 56px at
   2000 = 45px). Ours opens on a text "✓ S0" and a run id.
5. **No edges.** R23 draws 1.5px curves coloured by the source card's hue with 6px endpoint dots
   from the Goal card into each agent and out into the decision node. We draw one bare 1px vertical
   line from S4 down to the Base advance node and nothing else, so the eight cards read as a strip,
   not a flow.
6. **No emphasis border anywhere.** §3 puts `.is-live` on the running stage card. All eight of our
   cards carry the same neutral 1px border; only "Gate / waiting" is tinted.
7. **No timeline.** §4.3 asks for the R23 Execution Timeline under the hero (one 2px line, 12px dots,
   done segments in `--accent`, label 14.5/600 above and time 13 muted below, five to six
   milestones). It is absent.
8. **The canvas is mostly empty and the stat strip outranks the hero.** The dot canvas runs
   1300×~230 with the 80px card strip at its top and ~120px of empty grid below it, while the four
   stat cells above ($18.40, 3h 40m, 4, 11) carry the page's largest numbers. R23 inverts this: the
   flow is the hero and the rail's numbers are 20/600 inside 66px boxes.

**Keep:** the header line (key · ticket · tier over a 24/600 title, state pill and one primary pill)
is already R23's hero-card shape; the dot canvas itself; the Artefacts panel's superseded row drawn
with a strikethrough; short hashes in mono, everything else in the UI font; word count 185 / 260.

---

### Runs

Reference: R18.

1. **Rows 56px against R18's 66px** (bands 436–459, 492–515, 548–571; pitch 56). §3 asks 60.
2. **No table shell header** — no title, no "20 runs", no search pill, no Outcome / Stage / Ticket
   dropdowns in the card; the three filters sit outside as ghost chips.
3. **A second graphic on every row.** Each of the 20 rows carries a ~200px grey duration bar between
   Stage and Duration — roughly 15% of the table width — while the exact duration is printed two
   columns to its right. BRIEF-v2 §2 allows one status pill and one icon per row; R18's rows carry a
   pill and nothing else. The bars form a grey block that reads louder than the outcome column.
4. **KPI cards inherit all four Tickets findings** (220px tall against 168; icon square with the
   label beside it; full-bleed sparkline; no delta pill on the number's baseline).
5. **No trailing ⋮ circle.**
6. **The child run's indent has no anchor.** `run_7f3b` is indented under `run_7f3a` with an 18px
   offset and no rule or glyph, so at 56px rows the relationship is only visible if you notice the
   left edge.
7. **The running row is marked twice and the selected row once.** `run_d204` gets a pulse dot and
   `run_7f3a` gets the 2px accent bar plus tint — correct per §4.4 — but the two treatments sit
   nine rows apart with nothing tying them to the "1 running" figure in the KPI card.
8. **Word count 253.** Under BRIEF-v3 §4.4's cap of 260, but `tools/wordcount.py` defaults Runs to
   220 (BRIEF-v2) and reports OVER; run it as `wordcount.py … runs=260` or the pass check will
   mis-fire.

**Keep:** the live rail's 60px two-line rows (bands at 276, 336, 396, 456, 516, 576, 636, 696 —
exactly §3's list row) with the time right-aligned in muted tabular figures; the R06 outcome
treatment (dot + word for Pass, filled pill for Running / Aborted / Blocked / Fail); the pulse dot;
the child-run indent without a "child of" label.

---

### Run detail

Reference: R13 structure with R23 stat boxes. Light only — see the note above the table.

1. **Stat strip is R13's, not R23's.** §4.5 asks for four R23 stat boxes: 1px border, radius 12,
   label 12.5 muted, value 20/600, 76px tall (R23's Started / ETA boxes measure ~82px at 2000 = 66px
   at 1600, each separately bordered). Ours is one 112px card spanning x247→1563 with three hairline
   dividers (x930, x966 …) and no per-box border or radius.
2. **The budget bar is in the wrong place.** §4.5 puts the 3px budget bar inside the Cost box. Ours
   runs along the bottom edge of the whole strip card under the Cost cell, so it reads as a card
   underline rather than as Cost's own meter.
3. **Step rows are 43% too tall.** R13's step rows run at a 57px pitch at 2000 = 65px at 1600. Ours
   run at 93px (`05-run-light.png`, step circles at y411, 504, 926, 1019, 1113). §4.5 asks for 60px.
   At 93px the six tasks plus the expanded third fill the whole column.
4. **Step rows carry no status pill.** R13 ends each step with Success / Warning / Error / Running as
   a tinted pill and a time. Ours ends on a bare green check glyph, so a red or amber step would have
   nowhere to show.
5. **The dark capture is the wrong screen** (see above) — `05-run-dark.png` is the mockups index
   page, so no dark evidence exists for any of these findings.
6. **KPI-scale numbers in Guard decisions.** 214 / 3 / 0 are set at roughly the stat-strip scale
   inside a secondary panel, so a routine counter competes with the Cost and Duration figures at
   the top of the page.

**Keep:** the R13 skeleton is right and should not be redrawn — uppercase stat labels with a line
icon, the expanded task 3 with FAILING CHECK and FIX ROUND 1 as inset mono blocks, the five-row
Inputs panel with the short hash right-aligned, and the event log as a single mono block with one
red line. Header (key line, run id 24/600, model · runtime, Pass pill) matches §4.5. Word count
163 / 260.

---

### Report

Reference: R18 KPI cards, R15 layout.

1. **No hero.** Six panels of equal height sit in two rows of three, each ~355px wide, so the 31-day
   cost line — the screen's subject — is the same size as the donut and the stacked bars. R15 gives
   its spend chart roughly twice the width of its neighbours; BRIEF-v2 §2 allows one large chart per
   screen plus sparklines. We have four charts (line, donut, stacked bars, heatmap) plus five
   progress rows and three row sparklines.
2. **Eight regions.** Title bar, KPI row, baseline line, and six panels. BRIEF-v2 §2 caps a screen at
   five regions, and the references sit at three to five.
3. **Panel headers are not the table shell header.** §4.6 asks for the R18 form: title 17/600 with a
   muted second line (R18: "Query log" over "8 results"). Ours puts the title and a right-aligned
   value on one line with no second line, so the panels have less head than the reference and the
   period is never stated.
4. **The donut is one hue in six steps.** S4 58%, S3 21%, S1 9%, S6 6%, S2 4%, S5 2% are rendered as
   six lightness steps of the accent, and the four small slices differ by only a few percent of
   lightness — in dark the S1 / S6 / S2 / S5 legend dots are effectively the same colour, so the
   legend cannot be mapped back to the ring. R15 solves the same six-way split with distinct hues;
   the alternative inside our one-accent rule is to label the slices directly and drop the legend
   dots.
5. **The heatmap's low end vanishes in dark.** The lightest occupied cell sits within a few levels of
   the panel surface, so "Faster" cells and empty cells read alike; R02's cell scale keeps its
   lightest step clearly above the panel.
6. **KPI cards inherit the Tickets findings** (220px tall, icon square with the label beside it,
   full-bleed sparkline, no delta pill).
7. **The tag leaderboard's bars restate the numbers.** Five rows, each with a full-width progress bar
   and the count at the right; the counts are 5, 4, 2, 2, 1, so the bars encode a range of four.

**Keep:** the unit suffix set smaller than the figure ("71%", "38m") — that is exactly R18's
treatment of "8.4 M" in R11 and should survive; the "26 Aug · $28.70 / T-0403 escalation" callout
drawn into the line chart with a dashed median; the baseline row as one muted line; "not yet
measurable" as a single muted cell; word count 118 / 220, the most restrained screen in the set.

---

### Factory

Reference: R18 table, R23 agent cards, R22 settings rows.

1. **Agent cards are R12's, not R23's.** §4.7 asks for R23 stage cards five across with the pass rate
   as the progress bar. Ours are R12 cards: a 34px "97%" with "Pass rate 30d" under it, two
   key/value rows (Fixtures 6, Runs 30d 61) and two buttons (Fixtures ghost, Open filled). R23's
   card is an icon tile, a 17/600 name over a 15 muted subtitle, one status line and a 3–4px bar —
   no buttons, no key/value rows.
2. **No `.is-live` on s4-implementer.** §4.7 names it explicitly. It gets a "Running" pill; the card
   itself carries the same neutral border as the four idle cards, so the one live agent is marked
   at 24px pill scale instead of by the card.
3. **Sandbox policy is not R22.** §4.7 asks for four R22 settings rows: grid `380px 1fr`, 1px
   divider, 22px padding, a 15/600 label with one muted phrase of at most six words on the left and
   the switch on the right. Ours is a single 4-column strip of icon + label + switch, ~330px per
   column, divided vertically, with no muted phrase and no horizontal dividers — four controls in
   one 90px band instead of four rows.
4. **Manifest table has a half header.** "Stages" plus a right-aligned muted "budget per stage" is
   closer than the other tables, but §4.7 asks for the R18 shell with the count — "7 stages" — as
   the muted second line under the title.
5. **The budget bar eats the table.** Each of the seven rows carries a bar from x517 to x1213 —
   about 55% of the table's width — restating the $ figure printed at its right edge. Same defect as
   the Runs duration bar, and at seven rows it turns the manifest into a bar chart with labels.
6. **The action is weaker than the status.** "Fixture gate · 41 fixtures" is a filled tinted pill;
   "Open PR" beside it is a ghost pill. §4.7 wants the gate as a dot-plus-word (R06) and "Open PR" as
   the one primary pill, so the button reads as the action.
7. **Five 34px percentages in a row.** 97 / 93 / 91 / 88 / 79 set at KPI scale across the agent row
   are the loudest thing on the page, above the "Manifest v14" title — five numbers spanning 18
   points do not need KPI weight. As a 3px bar (finding 1) they would carry the same information at
   a tenth of the ink.
8. **No stage-level emphasis in the manifest.** The running stage (S4 Implementation) is not marked
   in the table even though its agent card is the live one, so the two halves of the screen do not
   agree.

**Keep:** the header line (Manifest v14 with the short hash in mono at 13, R18-style) and the manifest
row content — stage, model, tier, budget — at seven rows; the "Push URL" switch drawn off, so the
switch has two visible states; sentence-case stage names ("S3 Spec and plan"); word count 136 / 260.

## Round 1 (after polish, two reviewers)

### Reviewer A: Queue, Tickets, Ticket detail, Runs

# Observatory polish — round 1, reviewer A

Screens: Queue, Tickets, Ticket detail, Runs. Measured from side-by-sides at 1600px against the
BRIEF-v3 §4 reference for each screen; reference figures converted to 1600 (R18/R19 ×0.8, R23 ×0.8).
Cells are `dark / light`.

| Screen | Hierarchy | Density | Spacing & alignment | Colour & contrast | Craft |
|---|---|---|---|---|---|
| Queue (R18 + R19 + R23) | 7 / 7 | 8 / 8 | 7 / 7 | 8 / 8 | 7 / 7 |
| Tickets (R18) | 8 / 8 | 8 / 8 | 7 / 7 | 8 / 8 | 7 / 7 |
| Ticket detail (R23) | 7 / 7 | 8 / 8 | 8 / 8 | 6 / 6 | 7 / 7 |
| Runs (R18 + R11) | 7 / 7 | 6 / 6 | 6 / 6 | 7 / 7 | 6 / 6 |

Big picture: the structural gap in the baseline is closed. KPI cards are now 168px with R18's anatomy
(`02-tickets-light.png`: card top y158, page resumes y327 → 168px; §3 says 168, R18 is 169). Table
rows are 60px on all three tables (queue-light dividers 268 / 328 / 388 / 448 / 508 …). The shell
header, the search pill with ⌘ K keycaps, the 30px trailing ⋮ circle (border x1521→x1550) and the
light card shadow are all in. What is left is a colour problem (everything is the accent green), a
chart problem (sawtooth sparklines), one layout break on Runs, and three counting inconsistencies.

---

### Queue

1. **The page action row is an orphan.** `Export` and `History` sit alone on a 60px band above the
   card, right-aligned at x1199–1415 of a 1440 frame, leaving 923px (64% of the content width) empty
   because the title lives in the top bar. R18 fills that row: title 32/600 at the left, ghost pill
   + black pill at the right, one 76px band. Runs has no such row at all, so sibling screens start
   their content 60px apart. Fix (§3 top bar / §4): either move Export + History into the table shell
   header beside the filter dropdowns, or put the screen title back on this row and reduce the top
   bar to search + runner + theme.
2. **The decision card has four ghost pills and no primary.** `Approve`, `Request changes`,
   `Send back`, `Abandon` are all `--border-2` ghosts at the same height; `Approve` is only dimmed.
   §3 Buttons: "Primary: accent fill, 38px" and "Disabled: 45% opacity, **no border change**" — so
   Approve should be an accent-filled pill at 45%, not a ghost. As drawn, the one action the screen
   exists for is the least marked thing in the card.
3. **The bucket dot has no column and no word.** Rows end `58m ●` with the dot in the Age column
   (dot at x≈1146, age right-aligned at x≈1128) under a header that reads only "Age". R18 gives the
   status its own labelled column and a pill; BRIEF-v2 §2's R06 form is dot **plus word**. Ten rows
   carry zero pills where R18 carries one per row. Fix: give the dot its own 68px column headed
   "Bucket", or drop it and colour the age.
4. **"By kind" is six stat boxes for six single digits.** 2×3 grid, ~250px of rail height for the
   values 2 / 1 / 1 / 1 / 1 / 4. §3 Stat box says "two to four in a row"; R23's whole details rail
   spends 330px on name + priority + progress + two boxes. Fix: fold the six kinds into one two-box
   row (e.g. "Approvals 2 · Other 8") or a bucket-bar-style list.
5. **Rail is 740px of height for three numbers.** Median latency card ~250px (one number, one arc),
   By bucket ~240px, By kind ~250px. R23's rail at the same width carries Mission Details (330) +
   Connected Apps (200) + assistant. Fix: merge the gauge and the bucket bar into one card so the
   detail card and the rail end on the same baseline.

**Keep:** the table shell (title + "10 items", search pill, Bucket / Kind / Ticket dropdowns) — this
is R18's header, done; 60px rows and the 30px ⋮ circle; the `.is-sel` treatment on the detail card
(light: 1px `#6EB087` at x276 then a 4px `#DAE6E1` ring then page `#F1F2F4` — exactly §3's `0 0 0 4px`
at 10%); the two kind/bucket pills over the 17/600 title and the meta line (R19 card head); the three
slot rows with 28px initials avatars; the evidence line now at body size, not KPI size; 199/240 words.

---

### Tickets

1. **Sparklines are sawtooth, not R18's curve.** See answer (a). All four paths are polylines: the
   Open card is `M 0 33.2 L 5.5 29.4 L 11 37 L 16.5 25.7 …`, 24 `L` segments alternating direction
   over a 132-unit viewBox. R18's is one smooth bezier with two inflections across 137px at 2000.
   Worse, card 3 (Merged 30d) is a monotone ramp (`L 5.5 35.9 L 11 34.8 L 16.5 34.8 …`), so one row
   holds two different chart characters. Fix (§3 KPI card): resample to 6–8 points and draw a smooth
   cubic, keep the 1.5px stroke, the 10–12% area and the 7px ring dot.
2. **Page action row is an orphan** — as Queue finding 1. `New ticket` sits alone at x1284–1412 of
   1440 with the rest of the band empty.
3. **The bulk bar is 3× R04's and cannot be dismissed.** Ours spans the full table card width
   (x272→x1580 = 1308px, height 53px). R04's is 530px at 2000 = 424px at 1600, a floating pill, with a
   separate square **X** button at its left and text actions divided by 1px rules. Ours opens on a
   filled green check glyph (no dismiss) and closes on three ghost pills. At 1440 it also covers the
   LED-2261 and SET-104 rows. Fix: shrink to ~440px, centre it over the table, lead with an X.
4. **Delta pills are neutral grey.** "8 active", "5 act today", "of 38 closed", "$412 this week" are
   `--card-3` pills. R18 pairs every number with a tinted pill (`+12.4%` green on `#E8F5EE`,
   `-5.2%` red). §3 allows a muted phrase, but a grey blob at 24px beside a 34px number reads as a
   second object rather than as the number's annotation. Fix: drop the pill chrome for the phrase
   form (muted text on the number's baseline) and keep the pill only where there is a real delta.

**Keep:** the KPI card is now R18's — 168px tall, 38px accent icon circle top-left, 120×44 sparkline
top-right ending in a ring dot, label, then 34/600 number and the delta on one baseline; the shell
header with search + All states / Tier / Class; 60px rows; the seven S0–S6 stage dots; the selected
row's 2px accent bar plus tint; 187/200 words.

---

### Ticket detail

1. **Six of eight nodes glow.** S1–S4 carry `.is-pass` green (1px `--pass` 62% + `0 0 0 4px` at 8% +
   `0 0 24px` at 18%), S5 carries it too, S6 carries the amber variant. Only S0 and the PR card are
   plain. §3 says the emphasis border is for "the running stage card, the selected queue item card,
   the running run row's card, the agent card whose stage is running. **Nowhere else.**" R23 glows
   every node too, but with five different hues (green / blue / cyan / orange / purple), so the glow
   separates nodes; here one hue on six nodes only raises the whole canvas's luminance. See (b).
   Fix: glow the one node that is live or blocking (S6) and let S1–S5 keep the plain 1px border with
   the green progress bar and the "Pass" dot doing the work.
2. **"5 of 7 stages · 71%" contradicts the flow and the timeline.** The flow shows six passed stages
   (S0 Intake, S1, S2, S3, S4 each with a green "Pass" line, and S5 Checks with a green border and
   "8 pass · 1 waived"), S6 amber, PR pending → 6 of 7 = 86%. The timeline shows five green
   milestones + amber Review, and marks **Packet** green while the S6 Packet card is amber. Three
   surfaces, three counts. Fix: derive all three from one number; if S5 counts as passed the rail
   reads "6 of 7 · 86%" and the timeline's Packet dot must go amber.
3. **The rail progress bar leaves a 90px dead gap.** Light capture: track x63→x283 inside a 380px
   card, "71%" set at x372–400 — 89px of nothing between the track end and its own label. R23 runs
   the track to within 15px of the % (bar x1625→1895, "68%" at 1910 of a 380 card at 2000). Fix:
   `grid-template-columns: minmax(0,1fr) auto` with a 10px gap.
4. **A semantic border on a non-semantic box.** The "Elapsed 3h 40m" stat box has a green 1px border
   while "Started 11:24" beside it has `--border-2`. §3 allows "1px semantic **or** `--border-2`";
   green here says "pass" about an elapsed time. R23 tints its ETA box orange because the ETA is the
   risk. Fix: both boxes neutral, or tint only when the value is over budget.
5. **The S0 goal card is 160px against R23's 192.** Capture x≈420→580; R23's Goal card is 240 at 2000
   = 192 at 1600 and is the visual anchor of the fan. Ours is the smallest card on the canvas while
   being the origin of eight edges. Fix: 200–220px wide, matching the stage cards' 90px height.

**Keep:** the whole R23 skeleton — hero flow on the dot canvas, 300px stage cards (x556→x856) with a
34px icon tile, 15/600 name, run id · duration subtitle, status line with the cost right and a 3px
progress bar; the 1.5px cubic edges with 6px endpoint dots at the fan origin (measured ~6px at 1600
against R23's ~7px); the timeline under the hero; the complete right rail (Ticket details + stat
boxes, Links icon squares, Approvals as an R13 step list); the header line and 24/600 title;
230/260 words.

---

### Runs

1. **It breaks at 1440.** The fourth KPI card ("Settled $72.90") is painted over the Live activity
   rail: "Live activity" is clipped to "e activity", `run_d204` to `_d204`, `T-0409` to `409`. Cause:
   `.kpis{grid-template-columns:repeat(4,1fr)}` (00-head.html:150) with `.kpi-n{white-space:nowrap;
   font-size:34px}` (:517) — the auto min-content of "$72.90" plus its pill exceeds the track, so the
   grid overflows `.r-main` inside `.r-grid{minmax(0,1fr) 300px}` (:299). Fix:
   `repeat(4,minmax(0,1fr))` and let the delta pill wrap or shrink below 1540.
2. **The sparkline's ring dot draws outside its card.** `.kpi{overflow:visible}` (:508) plus
   `.kpi-sp svg{overflow:visible}` (:513) and `<ellipse cx="132">` on a 132-wide viewBox put half the
   terminator past the card edge; at 1440 a stray green dot sits on the rail at (1135,184) with no
   line attached. Fix: inset the last point by `rx`, or clip the sparkline box.
3. **Every row still carries a duration bar.** 20 rows, each with a 5px track ~285px wide (light
   capture x600→x885 of a 1000px crop = 22% of the table width), with the exact duration printed two
   columns to its right. BRIEF-v2 §2: one status pill and one icon per row; R18's rows carry a pill
   and nothing else. Unchanged from the baseline. Fix: delete the column; keep the bar only inside
   the selected row if it earns its place.
4. **The bar column has no header.** The header row reads Run · Ticket · Stage · (blank ~330px) ·
   Duration · Cost · Outcome. R18 labels all seven of its columns. Fix follows from 3.
5. **No search pill in the shell header.** Runs has only Outcome / Stage / Ticket dropdowns; Queue
   and Tickets both carry the 40px search. §3 Table shell puts a search pill *and* up to three
   dropdowns in the 68px header, and R18 shows both. Fix: add "Search by run or ticket..".
6. **Sparklines** — same sawtooth defect as Tickets finding 1; the Fail card's red sawtooth reads as
   noise rather than as a trend.
7. **`wordcount.py` reports Runs OVER.** 256 words against the tool's default 220; BRIEF-v3 §4.4
   raises the cap to 260. Fix the tool default or pass `runs=260`, or the pass check mis-fires.

**Keep:** the live rail's 60px two-line rows with the time right in muted tabular and the outcome pill
on line 2 (R11 exactly); the R06 outcome treatment (dot + word for Pass, filled pill for Running /
Aborted / Blocked / Fail); the pulse dot on `run_d204`; the child-run elbow glyph on `run_7f3b`, which
now reads without a label; the 60px rows, 30px ⋮ circle and the R18 KPI anatomy.

---

## Answers

**(a) Do the KPI sparklines read as R18's smooth curve or as a zigzag? — Zigzag.**
Every sparkline in the set is a polyline of 24 `L` segments alternating up and down every 5.5 viewBox
units (e.g. Runs today: `M 0 37 L 5.5 29.9 L 11 34.2 L 16.5 22.8 L 22 27.1 …`). R18's is a single
smooth bezier with two inflections and no area fill. Two of the four Tickets cards (Merged 30d, and
partly Cost 30d) are instead near-monotone ramps, so the row is not even internally consistent. The
7px ring terminator and the 120×44 box are right; only the path is wrong.

**(b) Do four green S1–S4 cards plus a glowing S5 read as R23's emphasis or as noise? — Noise.**
R23 glows five nodes in five hues, so the glow encodes *which agent*; ours glows six nodes in one
hue, so it encodes nothing and the canvas simply gets brighter. It also breaks §3's "Nowhere else"
list, which names only the running card. The rail's "5 of 7 stages · 71%" is **not** consistent with
the flow: the flow shows S0–S5 passed (six stages, 86%) and the timeline marks Packet green while
the S6 Packet card is amber "2 of 3 slots". Three numbers for one fact.

**(c) Is a running card distinguishable from a passed card anywhere? — No.**
`00-head.html:19-20` sets `--accent:#22C55E` and `--pass:#22C55E` (light: both `#15803D`), and
`:468` maps `.is-live{--em:var(--accent)}` and `.is-pass{--em:var(--pass)}` to the same value, so a
running card and a passed card render pixel-identical borders and glows. The only devices that
separate them are the pulse dot on the Runs row and the word in the status line — neither of which
appears on a stage card in the Ticket flow or on a Factory agent card. Fix: give running its own
treatment (the pulse ring on the icon tile plus a partial progress bar) or desaturate pass to a
quieter green and reserve full accent for live.

**(d) Does the page-level action row sit well with the title in the top bar? — No.**
On Queue and Tickets it is a 60px band whose left 64% is empty (Export/History at x1199–1415 of a
1440 frame; New ticket at x1284–1412). R18 uses the same band for title 32/600 **plus** the two
right-hand pills, so nothing is orphaned. Runs and Ticket detail have no such row, so content starts
60px higher there — the four screens do not share a vertical rhythm. Either give the row its title
back or move the actions into the table shell header.

**(e) In light theme, do emphasised cards keep the same elevation as plain cards? — No, they lose it.**
`[data-theme="light"] .card{box-shadow:0 1px 2px rgba(16,24,40,.04)}` (:462-463) is replaced, not
extended, by `[data-theme="light"] .card.is-sel{box-shadow:0 0 0 4px …}` (:474-478). Measured down a
plain rail card's bottom edge in `01-queue-light.png` at x1400: `#FFFFFF` → border `#E4E6EA` (y1320)
→ `#EAEBEE` → `#EFF0F2` → page `#F1F2F4` — a two-step drop shadow. Down the emphasised detail card at
x700: `#FFFFFF` → `#6EB087` (y1321) → four flat rows of `#DAE6E1` → page. The ring is uniform on all
four sides, so the emphasised card reads *flatter* than the plain cards around it. Fix: comma the two
shadows together — `0 1px 2px rgba(16,24,40,.04), 0 0 0 4px <hue at 10%>`.

**(f) At what width does each screen break?** Captured at 1440×1000 headless.
- **Queue — holds.** Subjects truncate with an ellipsis, the 300px rail stays, rows stay 60px.
- **Tickets — holds.** KPI row compresses cleanly; the bulk bar does overlay the last two rows, but
  that is the bar's width (finding 3), not a reflow break.
- **Ticket detail — holds, with a soft break.** Nothing collides, but the stage cards fall to ~250px,
  below §3's 300–320 minimum, and the fan of edges bunches to ~40px of clearance between the S1–S4
  column and the S5/S6 column.
- **Runs — breaks.** KPI card 4 overlaps the Live activity rail and clips its heading and its first
  two rows; the sparkline terminator lands on the rail. See findings 1 and 2.

### Reviewer B: Run detail, Report, Factory, Governance

# Observatory polish, round 1 — Reviewer B

Screens: Run detail, Report, Factory, Governance. Measured at 1600px from
`02-observatory/captures/*` against the BRIEF-v3 §4 reference for each, side-by-sides in
`<scratch>/r1b-*.png`. Reference figures quoted at native width are converted to 1600
(R13/R15/R18/R22 ×0.8, R23 ×0.8, R02 ×0.8).

## Scores (dark / light)

| Screen | Hierarchy | Density | Spacing & alignment | Colour & contrast | Craft |
|---|---|---|---|---|---|
| Run detail (R13 + R23) | 8 / 8 | 9 / 9 | 7 / 7 | 9 / 9 | 8 / 8 |
| Report (R18 + R15 + R02) | 7 / 7 | 6 / 6 | 8 / 8 | 7 / 7 | 7 / 7 |
| Factory (R18 + R23 + R22) | 8 / 8 | 9 / 9 | 6 / 6 | 9 / 9 | 8 / 8 |
| Governance (R22; dark vs R20) | 7 / 7 | 9 / 9 | 6 / 6 | 7 / 7 | 8 / 8 |

Word counts (all mine under cap): run 154/260, report 129/220, factory 127/260,
governance 142/240. **Not mine but visible from `tools/wordcount.py`: `runs` is 256/220, OVER.**

Two baseline defects are fixed across the set and are not repeated below: light cards now carry a
shadow (sampling down through a card edge in `05-run-light.png` at x=600 gives y1005 `#FFFFFF` →
y1006 `#E4E6EA` border → y1007 `#EAEBEE` → y1008 `#EFF0F2` → y1009 page), and the light tokens are
now exactly §3's (page `#F1F2F4`, sidebar `#F7F8F9`, cards white). The search pill has its ⌘ K keycaps.

---

### Run detail

Reference R13 (structure) + R23 (stat boxes). Both themes captured and correct — the baseline's
wrong-screen dark capture is fixed.

1. **The two columns end 122px apart.** Left column's last card bottom is y1005, right column's
   y1127 (`05-run-light.png`, scanning for the last white pixel at x=600 and x=1260). In R13 the
   step list ends y1341 and the Raw Output block y1361 at 2000 — a 16px rag at 1600. Ours is 7.6×
   that, and because the left column is the page's subject the rag reads as an unfinished column,
   not as R13's balance. Fix: R13 shares one bottom edge because both columns sit inside one framed
   panel; here, stretch the Tasks card in the two-column grid so both columns close on y1127.
2. **Two panel-header forms on one screen.** Tasks and Inputs put their count to the *right* of the
   title ("6 validated" at x848, "9 hashes verified" at x1449). §3's table shell and §4.6 put the
   count as a 13 muted second line under the title — which is what Report ("Cost per merged PR" /
   "7 Aug – 6 Sep") and Factory ("Manifest" / "7 stages") both do. Run detail is the only screen
   using the other form, so the shared component reads two ways across the set.
3. **The step list has no state gradient.** All six rows are an identical green check + name + time
   + chevron at a 60px pitch (circles at y397, 457, 526, 845, 905, 965 — pitch exactly §4.5's 60px).
   R13 ends every step with a Success / Warning / Error / Running pill, so its one warning and one
   error are the loudest thing in the column. Ours signals the only interesting row (task 3, one fix
   round) with 13px amber text at x781. §3's R06 rule (dot + word for pass, filled pill for
   fail/running) would carry state without R13's four-colour pill set.
4. **Guard decisions sits at stat-strip scale.** "214 / 3 / 0" measure a 14px digit height —
   identical to the stat boxes' "31:05" and "$9.85" (also 14px). A rail counter and the page's
   headline figures are the same size, so §2's "the size jump between levels must be visible" is
   not met between region 2 and region 5.

**Keep.** The four R23 stat boxes: 75px tall (y192→267) against §3's 76, radius 12, 1px border,
with the Cost box carrying the semantic border *and* the 3px budget bar inside it — both baseline
findings 1 and 2 are properly fixed. The 60px step pitch. The expanded task 3 with FAILING CHECK
and FIX ROUND 1 as inset mono blocks. The five-row Inputs panel with short hashes right-aligned.
The event log as one mono block with one red line. It is the most robust screen in the set at
narrow widths (see (f)).

---

### Report

Reference R18 (KPI cards, panel header) + R15 (layout, donut, model rows) + R02 (heatmap).

1. **Three of four KPI sparklines are zigzags, not R18's curve.** Tracing the line and counting
   direction changes: ours = 13, 3, 26, 21 over a 125px width; R18's four = 3, 6, 3, 5 over 66–101px.
   Amplitude matches (ours 34–38px, R18 27–31px), so the fault is point count, not scale — we plot
   ~30 daily values raw. Fix: 8–12 points with a monotone cubic, per §3's "1.5px line … ends in a
   7px ring dot" (the ring dot itself is correct on all four). R18 also carries no area fill; our
   ~10% fill (allowed by §3) turns card 3's sawtooth into a solid block with a serrated top.
2. **Still no hero, still eight regions.** Six panels of equal width in two rows of three (row 1
   y320→617, row 2 y639→1037), plus title bar, KPI row and the baseline line. BRIEF-v2 §2 caps a
   screen at five regions and one large chart plus sparklines; we run four charts (line, donut,
   stacked bars, heatmap) plus five progress rows plus three row sparklines. §4.6 says "panels
   unchanged in content", so this is inherited, but it is the reason density cannot score 8.
3. **The donut's four small slices are within ΔE 10.5.** Legend dots, dark: `#22C55E`, `#1F9E4E`,
   `#1B8142`, `#1A6D3A`, `#185E34`, `#17502F`; adjacent ΔE76 = 18.5, 14.3, 10.5, 8.1, 8.1. Light:
   15.6, 12.5, 9.3, 6.2, 5.9. Everything clears the panel (see (b)), so nothing vanishes, but S1 9%
   / S6 6% / S2 4% / S5 2% are four adjacent thin wedges separated by ≤8 ΔE — the legend cannot be
   mapped back to the ring. Fix inside the one-accent rule: label those four on the ring and drop
   their dots, or collapse them into one "Other 21%" wedge.
4. **The tag leaderboard's bars still encode a range of four.** Five rows, counts 5 / 4 / 2 / 2 / 1,
   each with a full-width bar (x300→x671) and the number printed at its right edge. Two of the five
   bars are identical. Same defect as the baseline; R15's model rows use the sparkline (a shape the
   number cannot show) in that slot instead.
5. **The four KPI phrase pills read as a status-pill row.** "median", "of 38 closed", "6 send-backs",
   "p90 3h 10m" are neutral tinted pills beside each number. §3 asks for a *tinted delta pill* or a
   *muted phrase* when §2 gives no delta — as four grey pills in a row they take R18's delta slot
   without R18's green/red meaning, so the row's most colourful element carries no signal.

**Keep.** The panel headers are now exactly §4.6's form — title 17/600 over a 13 muted second line
on all six panels (baseline finding 3 fixed). The 168px KPI card (y100→268) with the 38px icon
circle, sparkline top-right and 34/600 number. The "26 Aug · $28.70 / T-0403 escalation" callout with
the dashed median. The baseline row as one muted line. "not yet measurable" as one muted cell.
The unit suffix set smaller than the figure ("71%", "38m"). 129/220 words — still the most
restrained screen in the set.

---

### Factory

Reference R18 (manifest table) + R23 (agent cards) + R22 (policy rows). The biggest improvement in
my four: baseline findings 1, 2, 3, 4, 6 and 7 are all fixed.

1. **A 634px dead band runs through every manifest row.** See (a). At 51–57% of the table's width
   it is 3.9× the next-largest gap in the same row and 3.6× R18's worst intra-row gap in proportion.
2. **The five agent cards are 243px, against §3's 300–320.** Card edges at y780 give x276→519 = 243px.
   This is not the builder's choice: §4.7's "five across" at a 1310px content width forces it. The
   consequence is (f) — the screen breaks 60px below its design width. Either §3's width or §4.7's
   count has to give; four across at 320 would satisfy both.
3. **The middle band has no head.** Manifest and Sandbox policy are both titled cards with a muted
   second line; the five agent cards float between them with no label, so a reader must infer that
   the band is "Agents". The page's three regions do not head the same way.
4. **The pass-rate bars encode a 9-point range.** 97 / 93 / 91 / 88 on the four idle cards, drawn on
   a ~190px bar — a 17px difference end to end, next to the same numbers printed in text. R23's four
   bars span 62 / 67 / 78 / 100, a range the bar can actually show. The one bar that earns its place
   is s4-implementer's at 79%.

**Keep.** The `.is-live` treatment on s4-implementer is textbook §3: sampling across the card's left
edge at y780 gives a 1px `#1B8142` border at x1329, a 4px ring `#0E2618` at x1325–1328, and a soft
glow decaying from x1305 — `0 0 0 4px` + `0 0 24px` exactly. The R22 settings rows (four rows at an
88px pitch, 405px label track, 1px dividers, a 15/600 label over one muted phrase, switch right,
"Push URL" drawn off). The switch itself: 46×22 track, 18.5px knob, both states clean at 4× zoom.
The header line (Manifest v14 + short hash mono 13, "Gate pass · 41 fixtures" as a dot-word, "Open
PR" as the one filled pill). R23 card anatomy: 34px icon tile, 15/600 name over 13 muted model,
status line, 3px bar. 127/260 words.

---

### Governance

Reference R22 wholesale; dark against R20. A strong first draft of the new screen.

1. **Two row rhythms in one panel.** Trust profile rows sit at an 84px pitch (dividers y259, 343,
   427); Owners rows at 57px (dividers y1059, 1116, 1173, 1230, 1287, 1344). §3's settings row is
   "padding 22px 0", which with a 28px avatar is a 72px minimum — the Owners rows run 56px between
   dividers, so their padding is ~14px, 36% under contract. R22 never goes below 96px at 2000 (77px
   at 1600). The two halves of the panel do not belong to the same component.
2. **The Trust profile section is never closed.** Dividers run at y259/343/427/658/742/826, then
   nothing until the Owners heading at y994. The Approvals row is the only row in the panel with no
   closing rule, so the section's last item bleeds into the next section's header across 168px of
   blank card. R22 closes its last row with the footer divider.
3. **Owners' right half is a hole, not R22's air.** See (d).
4. **Dividers are 2.8× R22's weight.** Ours `#E4E6EA` on white = contrast ratio 1.25; R22's is
   `#F5F5F5` on white = 1.09 (sampled at x1500, y430–432 and y534–537). Ours is the same token as
   the card *border*, so the rows read as a grid of cells rather than as R22's rhythm. Fix: a
   lighter divider token inside the settings card, ~10 levels off the surface.
5. **The header/label size ratio is compressed.** Section header cap 13px ("Owners" O, y994→1006)
   against row-label cap 11px ("Data classes" D, y369→379) = 1.18. R22 runs 17 / 12.5 at 2000 =
   1.36. Both sizes are inside §3's bands (17/600 and 15/600), but at 1.18 the labels read almost as
   loud as the header, so nine rows and one header compete.
6. **The tab row promises a switch the page does not make.** "Trust profile" is the active tinted
   tab and "Owners" the muted one, yet both sections are rendered stacked in the same panel — so
   the Owners tab is inert and the Owners content is already on screen. §4.8 asks for both, so this
   is a brief-level contradiction, not a builder error; the honest resolutions are to drop the tab
   row or to mark the tabs as in-page anchors.
7. **The dark card barely lifts.** Page `#0B0C0E`, card `#121417` — a contrast ratio of 1.061.
   R20's equivalent step (board `#151718` → card `#1D1F20`) is 1.087. On a screen that is one large
   card on an empty page, a step that shallow leaves the card edge doing all the work.

**Keep.** The footer pair is right (see (d)). The section header form — 17/600 title, muted phrase
under it, right-aligned `config/trust-profile.yaml` with an external icon on the title's baseline —
is R22 exactly. The Routes mini-table as an inset with caps column heads. The Approvals rows with
28px initials avatars, role, dot-plus-word "Approved" and the expiry right-aligned. The active tab
as a tinted `--card-3` pill (y119→155, 36px). Sentence-case everything; two hashes only, both
short. 142/240 words.

---

## Specific questions

**(a) The Factory manifest's Tier→Budget band.** 634px on the S0 row (last ink of the Tier value at
x780, budget bar starts x1413), 625px on S3, 718px in the header row (x788→1505). The table's inner
width is 1252px (x300→1552), so the band is **50–57% of the table**, and the next-largest gap in the
same row is 163px — the dead band is 3.9× it. R18's worst intra-row gap is 211px on a 1465px table
at 2000 = **14%**. Both R18 and R15 fill that space with columns rather than leaving it: R18 runs
seven columns at a ~168px pitch (at 1600) with the ⋮ circle pinned right; R15's model table runs
seven columns ending in a per-row trend sparkline pinned right. Two fixes inside §3: add the R15
trend sparkline (and, if wanted, "Runs 30d") as trailing columns — a sparkline costs no words
against the 260 cap and Factory is at 127 — or cap the four column tracks so they occupy ~700px
with Budget right-aligned there and §3's trailing ⋮ circle taking the right edge.

**(b) Report sparklines and donut.** Sparklines: **zigzag, not R18's curve** — direction changes
per sparkline are 13 / 3 / 26 / 21 (ours, 125px wide) against R18's 3 / 6 / 3 / 5 (66–101px). Only
card 2 (Merged) reads as R18. Amplitude is not the problem (34–38px vs 27–31px); point count is.
Donut: **legible in both themes, unreliable at the low end.** Every step clears its panel — dark
ΔE76 vs `#121417` = 98.5 / 80.1 / 65.9 / 55.5 / 47.5 / 39.4; light vs white = 74.7 / 59.7 / 47.3 /
37.9 / 31.7 / 25.8 — so nothing disappears, which is a real fix on the baseline. But adjacent steps
fall to ΔE 8.1 (dark) and 5.9 (light) across the four small slices, and those four are adjacent thin
wedges on the ring, so arc→legend mapping is guesswork.

**(c) Heatmap low end in dark: yes, it survives.** Five steps `#143022`, `#174C2D`, `#1A6D3A`,
`#1E934A`, `#22C55E`. The lowest is ΔE 20.1 from the panel (`#121417`) and ΔE 18.7 from a hatched
"no data" cell (`#181B1F`); adjacent steps are 17.2 / 18.4 / 19.2 / 24.0 apart. R02's requirement —
lightest step clearly above the panel — is met, and the 4× crop confirms it by eye. **Light is now
the weaker theme:** its lowest step `#D9EBE0` is only ΔE 12.1 from the white panel and ΔE 10.9 from
the "no data" cell `#F7F8FA`, so in light the fastest cells and the empty cells are told apart by
the hatch, not by the fill.

**(d) Governance Owners, and the footer.** The empty right half reads as **a hole**, not R22's air.
The dividers run x300→x1552 (1252px); the longest ink in any of the six Owners rows ends at x836,
leaving 716px — **57% of every divider** — unoccupied, for six consecutive rows over 348px of
height. R22 does have rows with that much trailing air (Brand color's hex input ends at 58% of the
content width), but never two consecutively without a row whose control reaches ~88% (the
image-radio rows span x890→1640 of a x496→1825 track). Our Trust profile section passes that test —
Routes reaches x1338, Approvals x1354 — and Owners fails it because nothing in the section anchors
the right edge. Fix: give the Owners rows the right-hand column §4.8 already gives Approvals (the
"changed by PR #4802" now buried in the section subtitle would do at no word cost), or cap the
Owners rows' `1fr` track so the divider stops where the content does. **The footer pair is right:**
ghost "Cancel" then filled "Approve profile", both 38px tall (y1430→1468), right-aligned under a
full-width divider at y1409 — R22's Cancel / Save changes at 44px/2000 = 35px/1600, same order,
same alignment.

**(e) Run detail's 120px rag: a gap, not balance.** Left column ends y1005, right y1127 = 122px.
R13's two columns end at y1341 and y1361 at 2000 — a 16px rag at 1600, i.e. flush. Ours is 7.6×
that. R13 gets flushness free because both columns live inside one framed panel with a shared
bottom edge; here the cheapest equivalent is to stretch the Tasks card in the grid.

**(f) Break widths** (headless Chrome, `#<screen>`, 1000px height, one run at a time):

| Screen | Holds | Breaks | First symptom |
|---|---|---|---|
| Run detail | 1440, 1280, **1152** | none found ≥1152 | — |
| Factory | 1560 | **~1540** (fails at 1520) | s4-implementer's status line wraps to two lines ("79% pass · 49 / runs"), so the five bars lose their common baseline and the live card grows taller than its neighbours; at 1440 all five wrap |
| Report | 1520 | **~1500** (fails at 1480) | Model spend ellipsises the model name — the row's subject — as "claude-sonnet…", "claude-haiku-…"; at 1440 a second break, the "Runs by outcome" title runs into its Pass / Fail / Other pills |
| Governance | 1440 | **~1330** (fails at 1280) | the Routes mini-table's Route column ellipsises "Hosted model inferen…" |

Factory is the concern: it survives only 60px below its 1600 design width, and the cause is §4.7's
"five across" fighting §3's 300–320 card width (finding Factory-2). Run detail is the most robust
screen in the whole direction.

## Final pass

One reviewer, fresh context, from the sixteen captures in `02-observatory/captures/` (all 1600 wide,
both themes) composed side by side against the BRIEF-v3 §4 reference for each screen, with pixel
probes on the captures themselves. Reference figures quoted at native width are converted to 1600
(R18/R19/R22 ×0.8, R23 ×0.8, R13 ×0.8).

### Scores (dark / light)

| Screen | Hierarchy | Density | Spacing & alignment | Colour & contrast | Craft |
|---|---|---|---|---|---|
| Queue (R18 + R19 + R23) | 8 / 8 | 8 / 8 | 8 / 8 | 8 / 8 | 8 / 8 |
| Tickets (R18) | 9 / 9 | 9 / 9 | 9 / 9 | 8 / 8 | 8 / 8 |
| Ticket detail (R23) | 9 / 9 | 8 / 8 | 9 / 9 | 9 / 9 | 9 / 9 |
| Runs (R18 + R11) | 8 / 8 | 8 / 8 | 8 / 8 | 8 / 8 | 8 / 8 |
| Run detail (R13 + R23) | 8 / 8 | 9 / 9 | 9 / 9 | 9 / 9 | 8 / 8 |
| Report (R18 + R15 + R02) | 8 / 8 | **7 / 7** | 8 / 8 | 8 / 8 | 8 / 8 |
| Factory (R18 + R23 + R22) | 9 / 9 | 9 / 9 | 9 / 9 | 9 / 9 | 8 / 8 |
| Governance (R22; dark vs R20) | 8 / 8 | 9 / 9 | 9 / 9 | 8 / 8 | 9 / 9 |

Two cells below 8, both the same one: Report density. Everything else clears the bar.

Word counts (`python3 tools/wordcount.py 02-observatory/index.html runs=260`): queue 216/240,
tickets 185/200, ticket 232/260, runs 259/260, run 154/260, report 137/220, factory 180/260,
governance 154/240 — all ok. Sixteen captures, all current.

Three things fixed across the whole set and not repeated per screen:

- **The page-action row is gone.** Queue's `Export` / `History` and Tickets' `New ticket` now sit in
  the top bar as `.tb-actions` groups the router shows per screen. First ink below the 76px bar is
  y=100 on seven of the eight screens (Factory starts at y=158 because §4.7 gives it its own
  `Manifest v14` header line). Round-1 answer (d) closed.
- **Light emphasis keeps the plain card's elevation.** `00-head.html:484` now commas the two
  shadows. Down the Queue detail card's bottom edge at x=700: white → `#6EB087` border (y1265) →
  ring `#D4DFDB`→`#DAE6E1` (y1266–1269, the near rows darkened by the 1px/2px shadow underneath) →
  page `#F1F2F4`. A plain card at the same x reads `#E4E6EA` (y821) → `#EAEBEE` → `#EFF0F2` → page.
  Round-1 answer (e) closed.
- **Running and passed are no longer the same card.** `.is-pass` drops the ring entirely
  (`00-head.html:485`) and `.is-live` grows a 9px pulse dot on its icon tile (`:489-496`), so the two
  states differ by treatment, not only by a word. Round-1 answer (c) closed.

---

### Queue

**Closed.** (1) Orphan action row — the actions are in the top bar; content starts at y=100, level
with Tickets, Runs and Ticket detail. (2) No primary in the decision card — `Approve` is now the
accent-filled pill at 45% opacity, the other three stay ghosts, as §3 Buttons asks. (3) Bucket dot
with no column — the rows carry a labelled **Bucket** column with a tinted pill on all ten rows
(`Act today` / `This week` / `When convenient`), so the table has R18's one-pill-per-row.
(4) "By kind" as six stat boxes — folded into a five-row list (Approvals 2, Checks 1, Escalations 1,
Questions 1, Other 5) in the R11 Top-Tools form. (5) Rail 740px for three numbers — the gauge and
the bucket bar are now one card (y231→800) with By kind under it (y821→1265); the main column ends
at y1269 and the rail at y1266, a **3px rag** against round 1's unbalanced pair.

**Open.** None.

Measured: rows 60px (dividers 452 / 512 / 572 / 632 …), 30px ⋮ circle on every row, `.card.is-sel`
on the one decision card, 216/240 words.

---

### Tickets

**Closed.** (1) Sawtooth sparklines — direction changes per card are now **3 / 1 / 0 / 0** over a
125px box, against 24 alternating segments in round 1; R18's first card measures 3 by the same
trace. (2) Orphan action row — `New ticket` is in the top bar. (3) Bulk bar — now **445 × 52px**,
centred over the table (x701→1146 against a content column centred on x928) and led by a square X;
R04's is 424px at 1600. Round 1 was 1308px full-bleed with no dismiss.

**Open.** (4) **Delta pills are still neutral grey chrome.** "8 active", "5 act today", "of 38
closed", "$412 this week" remain `.kpi-d` pills on `--neutral-s`. They are on the number's baseline,
which §3 requires, but Report solved the same problem by dropping the pill and setting the phrase as
plain muted text — so the shared KPI card now reads two ways across the set.

Also open, as a shape rather than a defect: two of the four sparklines are monotone ramps (0
direction changes), so one row still holds two chart characters. `smoothSparklines()` keeps a
monotone series monotone by design; the fix would be in the data, not the code.

---

### Ticket detail

**Closed.** (1) Six of eight nodes glowing — the partial now carries six `.is-pass` (no ring) and
exactly **one** `.is-wait`, the S6 Review card. (2) "5 of 7 stages · 71%" contradicting the flow and
the timeline — the rail reads **6 of 7 stages · 86%**, the flow shows S0–S5 each with a green "Pass"
line and S6 amber, and the timeline runs five green milestones (Intake 11:24, Plan approved 12:51,
Implementation 13:52, Checks 14:03, Packet 14:06) closing on an amber `Review — Waiting`; the hero
header carries the same "Waiting on review" pill. Three surfaces, one number. (3) Rail progress bar
dead gap — the track runs x1213→1510 with the 86% fill ending at x1468 and "86%" starting at x1522:
a **12px** gap, against 89px in round 1 and ~15px in R23. (4) Semantic border on a non-semantic box
— `Started` and `Elapsed` both sample `#D2D7DD` (`--border-2`) at their edges. (5) S0 goal card
160px — now **204px** (x313→519) against R23's 192.

**Open.** None. Stage cards measure ~296px (x578→874) against §3's 300–320.

232/260 words.

---

### Runs

**Closed.** (1) Break at 1440 — recaptured at 1440×1000: the four KPI cards sit at 276→504 / 525→753
/ 774→1002 / 1023→1251 with the rail beginning at x1272; "Live activity", `run_d204` and `T-0409`
are all intact. `.kpis` is `repeat(4,minmax(0,1fr))` and `.kpi` is `min-width:0; overflow:hidden`.
(2) Ring dot outside its card — the only saturated pixels between x1230 and x1320 in the KPI band
are inside card 4 (ends x1251) and inside the rail card's own header dot; nothing lands on the rail.
(3) A duration bar on every row — the column is gone. (4) The bar column had no header — the table
now runs six labelled columns (Run · Ticket · Stage · Duration · Cost · Outcome) plus the ⋮ slot.
(5) No search pill — "Search by run.." sits in the 68px shell header beside Outcome / Stage / Ticket.
(6) Sparklines — **2 / 2 / 3 / 2** direction changes.

**Open.** (7) `tools/wordcount.py` still defaults Runs to 220, so the check must be run as
`wordcount.py 02-observatory/index.html runs=260`; Runs measures 259, one word under the cap
BRIEF-v3 §4.4 grants.

The Settled card reads `$72.90` with `$1.70 avg` **in full** at 1600. At 1440 the phrase ellipsises
to `$1.70 …` — the documented give-way (`.kpi-d{flex:0 1 auto}`), not a break.

---

### Run detail

**Closed.** (1) The 122px rag — both columns now end on **y1119** in `05-run-light.png` (last non-page
pixel at x=600 and at x=1300): a 0px rag against R13's 16px.

**Open.** (2) **Two panel-header forms on one screen.** Tasks still puts "6 validated" to the right
of its title and Inputs "9 hashes verified" to the right of its own, while Report and Factory set
the count as a 13px muted second line. Unchanged from round 1. (3) **The step list has no state
gradient** — six identical green check glyphs at a 60px pitch, with 13px amber "1 fix round" on task
3 as the only signal. §4.5 asks for R19 checklist glyphs, so this is contract-compliant, but a red
or amber step still has nowhere to show. (4) **Guard decisions sits at stat-strip scale** — "214"
measures a 14px digit height (y693–706), identical to the stat boxes' values (y232–245). Unchanged.

The four R23 stat boxes, the Cost box's semantic border with the 3px budget bar inside it, the
expanded task 3 and the event log all hold. 154/260 words.

---

### Report

**Closed.** (1) Zigzag sparklines — **8 / 0 / 5 / 3** direction changes against round 1's 13 / 3 / 26
/ 21; R18 runs 3–6. Card 1 at 8 is the busiest in the set and card 2 is flat. (3) The donut's four
small slices within ΔE 10.5 — the ring is now three wedges (S4 58% $249.60, S3 21% $90.40, Other 21%
$90.40) with three legend rows, and the four small stages are one muted line under the legend
("S1 9% · S6 6% · S2 4% · S5 2%"), so every dot maps to an arc. (5) Four grey phrase pills — the
pill chrome is gone; "median", "of 38 closed", "6 send-backs", "p90 3h 10m" are plain muted text on
the number's baseline.

**Partly closed.** The light heatmap's low end: the lightest filled step is now `#CCE3D4`, **ΔE 16.4**
from the white panel and **ΔE 15.2** from a `#F7F8FA` no-data cell, against 12.1 / 10.9 in round 1.
Legible, but light is still the weaker theme of the two.

**Open.** (2) **No hero, eight regions, four chart types.** Six equal panels in two rows of three
(unchanged), plus the title bar, the KPI row and the baseline line. §4.6 fixes the panel set
("panels unchanged in content"), so this is inherited from the brief — and it is the only reason a
cell in this table is below 8. (4) **The tag leaderboard's bars still encode a range of four** —
five rows, counts 5 / 4 / 2 / 2 / 1, each with a full-width bar beside the printed number; two of
the five bars are identical.

137/220 words, still the most restrained screen.

---

### Factory

**Closed.** (1) The 634px dead band — the manifest now runs seven columns (Stage · Agent · Model ·
Tier · Rubric · Tools · Budget). Largest intra-row gap on a data row is **171px on a 1250px inner
table = 13.7%**, and 202px = 16.2% in the header row; R18's worst is 14%. Round 1 was 50–57%.
(3) The middle band had no head — it is headed "Agents / 5 definitions · 30-day pass rate", so all
three regions head the same way. Also closed: the ~1540 break — recaptured at 1440, the five status
lines stay on one line and the five bars keep a common baseline.

**Open.** (2) **The agent cards are 243px** (x277→518 at y840), against §3's 300–320. §4.7's "five
across" at a 1310px content width cannot produce a 300px card; one of the two numbers has to give.
(4) **The pass-rate bars encode a 9-point range** — 97 / 93 / 91 / 88 on the four idle cards, next
to the same figures in text; only s4-implementer's 79% is a length the bar can show.

`.is-live` on the s4-implementer card and `.row.is-sel` on the S4 manifest row mean the two halves
of the screen now agree. 180/260 words.

---

### Governance

**Closed.** (1) Two row rhythms — every row in the panel is now 84px (dividers at 259 / 343 / 427 …
and, in Owners, 1058 / 1142 / 1226 / 1310 / 1394 / 1478), one pitch throughout, above §3's 72px
minimum and level with R22's 77px. (2) The Trust profile section never closed — a closing rule runs
at y957 after Approvals, with the Owners header 41px below it. (3) Owners' right half a hole — every
Owners row now carries a right-aligned scope (All stages / Trust profile / Trust profile / Spec and
plan / Human review / Record), so the content reaches the divider's right end. (4) Dividers 2.8×
R22's weight — the panel uses its own `--gv-div` token (`#F4F5F7` light, `rgba(255,255,255,.045)`
dark), measuring a **1.10** contrast ratio against the card surface in both themes; R22's is 1.09
and round 1's was 1.25.

**Open.** (5) **The header/label size ratio is still 1.18** (cap 13px on "Owners" against 11px on
"Data classes"); R22 runs 1.36. §3 prescribes 17/600 and 15/600, so the ratio is fixed by the
contract, not by the builder. (6) **The tab row still promises a switch the page does not make** —
"Trust profile" is the active tinted tab, "Owners" is muted, and both sections are rendered stacked.
§4.8 asks for both, so this is a brief-level contradiction. (7) **The dark card barely lifts** —
page `#0B0C0E` against card `#121417` is a **1.061** contrast ratio; R20's equivalent step is 1.087.
Unchanged, and token-level: it is the whole direction's dark surface step, not this screen's.

154/240 words.

---

### Residual

What is still below 8 or is a knowing trade-off, with the reason.

- **Report density 7 / 7 — the only cells under the bar.** Eight regions and four chart types (line,
  donut, stacked bars, heatmap) plus five progress rows and three row sparklines, where BRIEF-v2 §2
  allows one large chart plus sparklines. §4.6's "panels unchanged in content" fixes the panel set,
  so closing this needs a brief change, not an edit.
- **The tag leaderboard's bars** restate counts of 5 / 4 / 2 / 2 / 1. Same class of defect as the
  Factory pass-rate bars: the data has no range for a bar to show.
- **Factory agent cards at 243px** against §3's 300–320. §4.7's "five across" at 1310px forces it;
  four across at 320 would satisfy both numbers and lose a card from the row.
- **Factory pass-rate bars** span 97 → 79, a 17px difference end to end on a ~190px track.
- **Run detail's panel headers** put their count to the right of the title while Report, Factory and
  every table shell put it underneath — the shared header form reads two ways across the set.
- **Run detail's Guard decisions** are set at the same 14px digit height as the page's headline
  figures, so region 5 does not step down from region 2.
- **Tickets and Runs keep the neutral delta pill**; Report dropped it for the plain muted phrase.
  §2's data supplies no real deltas, so colouring them would mean inventing numbers — but the two
  treatments should not both be in the set.
- **Two of four Tickets sparklines are monotone ramps** (0 direction changes). The smoother keeps a
  monotone series monotone on purpose; the wave would have to come from the data.
- **Governance's 1.18 header/label ratio** and the **inert Owners tab** are both fixed by BRIEF-v3
  §3 and §4.8 respectively.
- **The dark card step is 1.061** (R20: 1.087). Deepening it is a token change that would move all
  eight screens and both themes.
- **Governance builds its own `.gv-*` settings row** (84px, `--gv-div`) instead of the shared
  `.set` / `.sec` that Factory uses, so a later change to the shared component will not reach it.
- **The light heatmap's lightest step** clears its panel by ΔE 16.4 and a no-data cell by ΔE 15.2 —
  legible, but light remains the weaker theme for that panel.
- **`tools/wordcount.py` still defaults Runs to 220.** Run it as `… runs=260`, or Runs (259) reports
  OVER.
