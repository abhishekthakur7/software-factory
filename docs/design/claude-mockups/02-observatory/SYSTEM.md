# Observatory system layer (BRIEF-v3 §3)

Every class here lives in `src/00-head.html`. Copy the shapes below; do not restyle them. Screen-scoped
overrides go in `<style data-screen="…">` in your own partial, every selector prefixed `#s-<id>`.
Prefix screen-scoped classes as well as selectors; shared names like `.rt` and `.ok` leak.

Icon sprite ids: `#i-queue #i-ticket #i-runs #i-report #i-factory #i-shield #i-search #i-sun #i-moon
#i-chevd #i-chevr #i-sel #i-check #i-checkc #i-alert #i-help #i-file #i-list #i-dollar #i-clock #i-branch
#i-pause #i-zap #i-arrowur #i-arrowr #i-back #i-download #i-history #i-plus #i-filter #i-x #i-layers
#i-cpu #i-flow #i-users #i-tag #i-terminal #i-box #i-cal #i-dots #i-ext #i-circle`.

## Surfaces

`.card` radius 15, 1px `--border`; light adds `0 1px 2px rgba(16,24,40,.04)` automatically. `.card-2`/
`.card-3` are tokens, not classes. Inset panels: `.inset` (`--card-2`, radius 12) or `.canvas` (below).
Utilities: `.mut .fnt .ell .r .mono .lbl` (11/600 caps).

## Emphasis border + glow (R23) — running / waiting / failed / selected only

```html
<div class="card is-live">…</div>   <!-- accent + pulse dot: moving now -->
<div class="card is-wait">…</div>   <!-- amber: waiting on a person -->
<div class="card is-fail">…</div>   <!-- red -->
<div class="card is-sel">…</div>    <!-- accent, selected -->
<div class="card is-pass">…</div>   <!-- NO glow: plain --border-2 hairline -->
```
Works on `.card` and `.node`. The four glowing states get a 1px semantic border + `0 0 0 4px @8%,
0 0 24px @18%` (dark); in light the shadow list is `0 1px 2px rgba(16,24,40,.04), 0 0 0 4px @10%` — the
ring is **added to** the plain card's elevation, never replaces it. `.is-pass` is deliberately quiet:
`--border-2` border, no ring, no shadow beyond the plain card's; its full green `.prog` bar and its
dot-plus-word carry the outcome. Running and passed are told apart by the pulse: `.is-live` grows a 9px
accent dot on the top-right corner of its `.node-ic` / `.kpi-ic` (`@keyframes sf-pulse`), and a passed
card has no ring at all. One glowing card per screen is the target; use `.is-wait` for the stage a person
is holding. All five set `--em`, which `.node-ic`, `.prog i` and `.edge` read, so `.is-pass` still paints
green. Table rows keep `.row.is-sel` (background `--sel` + 2px accent bar) — a different, unchanged thing.

## Top bar and sidebar (frame — already built, do not edit)

76px bar: `h1#pgTitle` 28/600, centred 44px `.search` pill ending in `.kbds > .kbd ⌘ / .kbd K`,
then `.range#tbRange` (a `.rangepill` + `.seg` 7d/30d/90d, shown on Report only), the page-action groups,
`.runner`, `.iconbtn` theme circle — all 40px.

**Page actions (R18 puts them on the title row; our title is in the bar).** In `.tb-right`, before
`.runner`, one `<span class="tb-actions" data-for="<screen>">` per screen that has page actions; the
router shows the group whose `data-for` matches the current screen and hides the rest (like `tbRange`).
Built today: `data-for="queue"` — ghost `Export` (`#i-download`) and `History` (`#i-history`);
`data-for="tickets"` — primary `New ticket` (`#i-plus`). A screen must not repeat these in an in-section
action row. `.tb-actions .btn` is 40px so the row keeps one height.

Sidebar 248px, `.nav-i` 44px rows; nav is Queue / Tickets / Runs, then
Report / Factory / **Governance** (`data-nav="governance"`, `href="#governance"`, `#i-shield`).
The router shows `#s-<id>` and reads its `data-title` for the page title.

## Buttons and controls (all pills, radius 999)

```html
<button class="btn pri">Approve profile</button>          <!-- accent fill, 38px -->
<button class="btn">Request changes</button>              <!-- ghost -->
<button class="btn danger">Abandon</button>               <!-- ghost, red text -->
<button class="btn off">Approve</button>                  <!-- disabled, 45% -->
<button class="btn icon"><svg width="16" height="16"><use href="#i-history"/></svg></button>
<span class="fpill">All states <svg width="14" height="14"><use href="#i-chevd"/></svg></span>
```
`.chip` is the same 40px pill (`.chip.on` = active). `.seg` segmented control is pill-shaped.

## Pill (status / tag)

```html
<span class="pill pass"><i class="dot"></i>Pass</span>
<span class="pill fail">Fail</span>   <span class="pill warn">Blocked</span>
<span class="pill acc">Running</span> <span class="pill">FM-1</span>
```
24px, 12.5/500, sentence case. Pass = dot + word; filled pill for fail / blocked / aborted / running.

## KPI card (R18) — 168px, four across, one row

```html
<div class="kpis">
  <div class="kpi" style="--tint:var(--accent)">
    <div class="kpi-top">
      <span class="kpi-ic"><svg width="20" height="20"><use href="#i-ticket"/></svg></span>
      <span class="kpi-sp"><svg viewBox="0 0 132 40" preserveAspectRatio="none">
        <path class="sp-a" d="M 0 33 L … L 132 10.6 L 132 40 L 0 40 Z"/>
        <path class="sp-l" d="M 0 33 L … L 132 10.6" vector-effect="non-scaling-stroke"/>
        <ellipse class="sp-dot" cx="132" cy="10.6" rx="3.85" ry="3.18"/></svg></span>
    </div>
    <span class="kpi-l">Open</span>
    <span class="kpi-v"><span class="kpi-n">12</span><span class="kpi-d up">+12.4%</span></span>
  </div>
  …three more…
</div>
```
Icon circle 38px (`--accent-s`, accent icon). Sparkline 120×44 top-right; `cx`/`cy` of `.sp-dot` are the
last point of the `.sp-l` path (7px ring). Label 14.5 muted, number 34/600 tabular (`<small>` for a unit),
delta pill inline: `.kpi-d` neutral, `.kpi-d.up` green, `.kpi-d.dn` red. `--tint` colours line, area and
ring. `.kpi.dim` fades the sparkline, `.kpi.flat` drops the area fill.

**Widths.** `.kpis` is `repeat(4,minmax(0,1fr))` and its children carry `min-width:0`, so a KPI row can
never push its column (the Runs main track) wider than the grid. `.kpi` is `overflow:hidden` so a ring
terminator cannot paint on the neighbouring rail. `.kpi-n` is `clamp(30px,2.27vw,34px)` and never shrinks
in the flex line; `.kpi-d` is the part that gives way (`flex:0 1 auto`, ellipsis) — so keep the delta
phrase short, four or five characters plus a word. Inside `.r-main` (Runs, 300px rail) the card is
~230px: number `clamp(26px,1.88vw,30px)`, 16px side padding, 12px delta.

**Sparklines are smoothed at load** (`smoothSparklines()` in `src/99-tail.html`). Author the `d` as a
plain polyline (`M x y L x y …`, any number of points); on load every `.kpi-sp path` — and any element
marked `data-smooth`, or every `path` inside it — is resampled to 12 points with a gaussian window,
keeping the first and last point, and rewritten as Catmull-Rom → cubic beziers. A closed path (the
`.sp-a` area) keeps its two baseline corners, so line and area stay in sync automatically; `.sp-dot` is
moved to the last point. A path that already contains a curve command is left alone. Result: 0–5
direction changes per card instead of 20 (R18 runs 3–6). A monotone series stays monotone — if you want
the R18 wave, put the wave in the data.

## Stat box (R23 Started / ETA)

```html
<div class="stats">
  <div class="stat"><span class="stat-l">Started</span><b class="stat-v">11:02</b></div>
  <div class="stat acc"><span class="stat-l">Cost</span>
    <b class="stat-v">$9.85 <small>of $12.00</small></b>
    <span class="bar"><i style="width:82%"></i></span></div>
</div>
```
76px, radius 12, 1px `--border-2`; `.stat.pass/.fail/.warn/.acc` for a semantic border. Two to four in a row.

## Table shell (R18)

```html
<div class="card tbl">
  <div class="tbl-h">
    <div class="tbl-t"><h2>Tickets</h2><span>12 results</span></div>
    <div class="tbl-x">
      <span class="tsearch"><svg width="16" height="16"><use href="#i-search"/></svg>
        <span>Search by key or title..</span></span>
      <span class="fpill">All states <svg width="14" height="14"><use href="#i-chevd"/></svg></span>
      <span class="fpill">Tier <svg width="14" height="14"><use href="#i-chevd"/></svg></span>
    </div>
  </div>
  <div class="rows">
    <div class="rowhead xrow"><span>Key</span><span>Title</span><span class="r">Cost</span><span></span></div>
    <div class="row xrow is-sel">…<button class="kebab"><svg width="15" height="15"><use href="#i-dots"/></svg></button></div>
    <div class="row xrow is-hov">…</div>
  </div>
</div>
```
Header 68px (title 17/600 + count 13 muted), search pill and up to three filter pills at 40px. Inside
`.tbl` the header row is 44px and rows are 60px / 14.5. Define your own `.xrow{grid-template-columns:…}`
in your screen block; fixed slots for icon, pill and the trailing 30px `.kebab`. Numbers right and tabular.
`.row.is-sel` = `--sel` + 2px accent bar; `.row.is-hov` = hover. No zebra.

## List row for a rail (R11, R24)

```html
<div class="lrow">
  <span><span class="lrow-a">run_d204</span><span class="lrow-b">S4 Implementation · T-0412</span></span>
  <span class="lrow-v">14:32</span>
</div>
```
60px, two lines: 14.5 title, 13 muted phrase, time right in muted tabular.

## Node / stage card (R23) — 300–320 wide

```html
<div class="node is-live">
  <div class="node-h">
    <span class="node-ic"><svg width="18" height="18"><use href="#i-cpu"/></svg></span>
    <span class="ell"><span class="node-t">S4 Implementation</span>
      <span class="node-s">run_d204 · 31:05</span></span>
  </div>
  <div class="node-st">Running 62% <b>$9.85</b></div>
  <span class="prog"><i style="width:62%"></i></span>
</div>
```
Icon tile 34px radius 9 at the hue 14%; title 15/600; subtitle 13 muted; status line 13 (word left, cost
right); 3px progress bar — full for done, partial for running, empty for pending. The hue comes from
`.is-live/.is-pass/.is-wait/.is-fail` (or set `--em` inline).

**Width.** `.node` is `width:auto; min-width:0` with `max-width:312px` and `flex:0 1 312px` — it fills
(and can shrink inside) a grid track, and only in flow layouts does it default to 312. Never hard-code a
width on `.node` itself; set the track (Factory's five across) or a screen-scoped width on your own
class (`#s-ticket .td-n{width:300px}`).

## Canvas and edges (R23, R21)

```html
<div class="canvas" style="min-height:420px">
  <svg class="edges" viewBox="0 0 900 420" preserveAspectRatio="none">
    <path class="edge" style="--em:var(--pass)" d="M 300 90 C 380 90 380 210 460 210"/>
    <circle class="edge-d" style="--em:var(--pass)" cx="300" cy="90" r="3"/>
    <circle class="edge-d" style="--em:var(--pass)" cx="460" cy="210" r="3"/>
  </svg>
  <div class="node" style="position:relative">…</div>
</div>
```
`.canvas` is `--card-2`, radius 12, dot grid at an 18px pitch. `.edges` fills it and sits behind the cards
(give each node `position:relative`). `.edge` is a 1.5px cubic with horizontal tangents at the source hue
60%; `.edge-d` are the 6px endpoint dots (r 3).

## Timeline (R23)

```html
<div class="tl">
  <div class="tl-i done"><span class="tl-t">Intake</span><span class="tl-m">11:02</span></div>
  <div class="tl-i now"><span class="tl-t">Implementing</span><span class="tl-m">In progress</span></div>
  <div class="tl-i"><span class="tl-t">Review</span><span class="tl-m">Pending</span></div>
</div>
```
One 2px line, 12px dots; `.done` segments accent, the rest `--border-2`; `.now` adds an accent halo.
Label 14.5/600, time 13 muted. Five to six items, evenly spaced.

## Settings row and section header (R22)

```html
<div class="sec">
<div class="sec-h">
  <div><h2>Trust profile</h2><p>4ab7d0…c19d · approved 3 Sep 2026</p></div>
  <a class="sec-link">config/trust-profile.yaml <svg width="14" height="14"><use href="#i-ext"/></svg></a>
</div>
<div class="set">
  <div><span class="set-l">Admitted scope</span><span class="set-p">Repository and fixture</span></div>
  <div class="set-c"><span class="set-v">Northwind Payments</span><span class="pill">Fixture</span></div>
</div>
</div><!-- /.sec -->
<div class="set-f"><button class="btn">Cancel</button><button class="btn pri">Approve profile</button></div>
```
Grid `380px 1fr`, 1px `--border` top divider, 22px padding and a **72px minimum row height** — every row
in the panel keeps the same rhythm whatever its control. Left label 15/600 plus one muted phrase of at
most six words; right one control (`.switch`, `.set-v` text, pills, or a `.fpill`). Wrap each section's
header and rows in `.sec`: it closes the section with a divider (so the last row is ruled off), spaces
the next section 26px below it, and drops its own rule when it is the last section before `.set-f`.

## Tab row (R22, R19)

```html
<div class="tabs">
  <button class="tab on">Trust profile</button>
  <button class="tab">Owners <span class="pill">9</span></button>
</div>
```
40px tabs, 14.5/500; active tinted `--card-3`. Count pill only where the screen contract gives one.

## Avatars (R19) and switch (R22)

```html
<span class="av">IC</span>
<span class="avs"><span class="av">IC</span><span class="av">ML</span><span class="av">PR</span></span>
<span class="switch on"><i></i></span>   <!-- 44×24, accent when on -->
```
28px initials circles, `--card-3` with a 1px `--border-2`, stacked at −8px with a ring in the card colour.
