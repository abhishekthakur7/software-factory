# Observatory polish: brief v3 (2026-09-07, evening)

Scope: direction `02-observatory` only. The owner chose it ("looks good") and asked for its look and feel to
be refined and polished against seven new references, and for the screen set to match what
`docs/design/milestones.md` requires of a person-facing surface. Everything in BRIEF.md §1, §2, §5 and in
BRIEF-v2.md §2 (density budget) still binds. This file adds the new references, the polish contract per
component and per screen, one new screen, and the working rules for parallel builders on one file.

## 0. What "polish" means here

The rebuild fixed density and structure. What is left is the last 20%: the softness and precision the new
references have and ours does not. In R18 every control is a pill of the same height, every card has the
same radius and the same 1px hairline, numbers sit on one baseline with their delta pill, and the table
rows breathe at 64px with the secondary columns a step lighter. In R23 the cards that matter carry a 1px
coloured border with a faint outer glow, one 3px progress bar and one status line; edges are thin curves
with endpoint dots. In R22 a settings row is a 1px divider, a bold label with one short muted phrase on the
left and one control on the right. Copy those decisions, measured, not the general idea.

Not polish: adding text, adding regions, adding chart types, adding a second accent. Word caps stand.

## 1. The new references (view every one you are assigned with the Read tool)

| id | file | what it is | what we take |
|---|---|---|---|
| R18 | `references/R18.png` | "AI & Queries", light SaaS admin (2000×1500): pastel-washed page, one rounded white frame, icon-only rail with a black active circle, top bar with breadcrumb, 56px search pill with ⌘K keycaps, range pill, download pill, bell, avatar-with-role; title 32 + right actions (ghost pill, black pill); four KPI cards (icon circle top-left, sparkline top-right ending in a ring dot, label, 34px number, tinted delta pill); a table card with title + "8 results", a search pill and three filter dropdown pills, 82px rows, status pills, trailing ⋮ in a circle | Top bar composition; KPI card; table shell (title + count, search, filter dropdowns); row rhythm; pill buttons; the ⋮ circle |
| R19 | `references/R19.png` | "Unique" kanban, light (2000×1500): icon rail + project tree, title with tabs and avatar stack, view toggle, columns with dot + name + count, cards with filled tag pills, 16px title, two-line muted body, checklist rows with circle / check glyphs, avatar row with comment and attachment counts; right rail with a profile and chat | Card anatomy for the queue detail (tags, title, checklist rows, avatars); the tab row; avatar stack |
| R20 | `references/R20.png` | The same kanban in dark, perspective: page #0F0F10, panels #141415, cards #1C1C1E, pastel tag pills with dark text, text #ECECEC / muted #8A8A8F, white underline on the active tab | Dark elevation steps; how pills read on dark |
| R21 | `references/R21.png` | "Story" workflow builder, light (2000×1499): white panel radius 24 on grey; connector library as a 2×4 grid of 150px tiles (32px line icon + label) under group headers with counts; canvas on a dot grid with white node cards 240×80 (icon cell with divider, muted type over 17px name), orange and purple diamond decision nodes, 2px green / orange selected outlines, 1.5px grey orthogonal edges with rounded corners and 22px + / − circles, a dark bottom toolbar (icon groups, "Search on board" white pill, "Quick Add" green pill), a zoom stack, "saved 3 min ago" | Node card anatomy (icon cell, type over name); edge and handle treatment; the dark floating toolbar; zoom stack |
| R22 | `references/R22.png` | Untitled UI settings, light (2000×1500): 300px sidebar with 44px rows and 20px line icons, title 30, tab row with the active tab tinted, section header 18 + muted line + right link, then form rows: 1px dividers, left column 400px (16px bold label, 15px muted phrase, optional link), right column control (image radio cards with a check badge, 48px select), footer Cancel + Save changes | The settings row; the tab row; the section header; the footer pair. The whole Governance screen |
| R23 | `references/R23.png` | "Agentflow Mission Workflow", dark (2000×1205): top nav tabs with icons and one bordered active pill; hero card 28px title with a zoom pill; dotted canvas; Goal card (blue border) → four agent cards 320×120 (1px coloured border + outer glow, filled icon tile, 17px name, 15px muted subtitle, status line, 3–4px gradient progress bar with % right) → AI Decision (purple) → Mission Complete (green); curved edges coloured by source with endpoint dots; Execution Timeline (five dots on a line, done segments coloured, 16px labels with muted times); right rail 380px: Mission Details (label, name, priority pill, progress bar with %, two bordered Started / ETA boxes), Connected Apps (44px icon squares, +4), assistant card with input pill | The stage card, the glow, the progress bar, the flow layout, the timeline, the details rail, the stat boxes. Ticket detail copies it wholesale |
| R24 | `references/R24.png` | "AI Powered" node canvas, light (1784×1266): near-white page with a dot grid, 270px node cards radius 16 with a lavender gradient foot, 20px node titles, 48px input fields, thin purple curved edges with endpoint dots, left rail with caps section labels ("IN PROGRESS 3") and two-line items with a time, floating bottom tool pill | Left-rail item anatomy (title, muted subtitle, time); edge dots; the caps section label with a count |

Older references that still apply to Observatory: R11 (frame, KPI row, live rail), R13 (step list, stat
strip, raw output), R14 (KPI tint), R15 (donut, model rows), R02 (heatmap), R06 (dot-plus-word outcomes).

## 2. Screens required by the milestones

`docs/design/milestones.md` names every place a person meets the factory. Mapping, so the set is complete:

| milestone surface | block | screen |
|---|---|---|
| The queue: one item per thing needing a person, its list view and act contract | 12 Queue item and decision; 18 Stage interface (`queue`, `act`) | Queue |
| Ticket and its state; runs, artefacts, approvals, assumptions (`show`) | 9, 10, 11, 13, 14 | Tickets, Ticket detail, Runs, Run detail |
| The record's measures as views; the report; export and import | 17 Record (`report`, `export`, `import`) | Report |
| The factory tree: manifest, agents, skills, rubrics, recipes, sandbox policy, change control | 1–5, 7, 8, 20, 21 | Factory |
| The governance view: the proposed trust profile and the owners file shown to the security and legal approvers, a metadata-only approval with expiry | 6 Trust profile; 14 Approval and quorum (R-T-9, R-F-13) | **Governance (new, screen 8)** |
| The Slack digest; GitHub pull requests | 24 External access (X8) | Not ours to draw |
| The `factory` command | 18 Stage interface | Not a screen |

So the set becomes eight screens: the seven of BRIEF-v2 §3 plus Governance. Nothing else is added.

## 3. Component contract (the system layer; `src/00-head.html`)

Measured at 1600px. The system agent implements these as shared classes and documents each with its HTML
shape in `02-observatory/SYSTEM.md`; screen builders use them and do not restyle them.

- **Surfaces.** Page, sidebar, card, card-2, card-3 as today. Cards radius 16, 1px `--border`. Light cards
  add `0 1px 2px rgba(16,24,40,.04)` (R18, R22); dark cards get no shadow, elevation is the surface step
  (R20). Inset panels (log, code, canvas) are `--card-2` with radius 12.
- **Emphasis border.** `.card.is-live` / `.is-pass` / `.is-fail` / `.is-sel`: 1px semantic border plus an
  outer glow `0 0 0 4px <hue at 8%>, 0 0 24px <hue at 18%>` in dark, `0 0 0 4px <hue at 10%>` in light (R23).
  Used on: the running stage card, the selected queue item card, the running run row's card, the agent card
  whose stage is running. Nowhere else.
- **Top bar (R18, R11).** 76px. Title 28/600 left. Search pill centred, 44px tall, radius 999, `--card-2`,
  with two 22px keycaps `⌘` `K` at the right end (R18). Right: the Report range pill (calendar icon,
  "30 Days", chevron; the 7d/30d/90d segmented control stays), runner pill, theme circle. All the same 40px
  height. The user card stays in the sidebar foot (R22), not in the top bar.
- **Sidebar (R11, R22).** 248px, 44px nav rows, 18px icons, active row = filled `--card-3` pill with the
  2px accent bar (unchanged). Add "Governance" under Record. Section labels 11/600 caps as today.
- **Buttons.** All pills, radius 999. Primary: accent fill, 38px, 14/500. Ghost: 1px `--border-2`,
  transparent. Danger stays ghost with `--fail` text. Disabled: 45% opacity, no border change. Icon
  button 38px circle. Heights identical in a row (R18: the ghost and the black pill are the same height).
- **Pill.** 24px, 12.5/500, padding 0 10px, tinted 12% (dark) / 10% (light), sentence case; the R06 rule
  stands (pass = dot + word; filled pill for fail, blocked, aborted, running). One style; tags (FM-1 …) use
  the neutral tint. No pastel-filled pills (R19's) in this direction: one accent.
- **KPI card (R18 with R14 tint).** 168px tall. Icon circle 38px top-left (`--accent-s`, accent icon).
  Sparkline 120×44 top-right, 1.5px line, 10–12% area, ends in a 7px ring dot (R18). Label 14.5 muted at
  y≈96, number 34/600 tabular at the baseline with the delta pill beside it (green tint + "+12.4%" style,
  or a muted "vs 30d" phrase when §2 gives no delta). Four across; one row only.
- **Stat box (R23 Started / ETA).** For the stat strip on Run detail and the Ticket rail: 1px semantic or
  `--border-2` border, radius 12, label 12.5 muted, value 20/600, 76px tall. Two to four in a row.
- **Table shell (R18).** Card header 68px: title 17/600 + count "12 results" 13 muted on the left; right:
  search pill 40px ("Search by key or title..") and up to three filter dropdown pills 40px with a chevron
  ("All states ▾"). Header row 44px, 13.5/500 muted. Rows 60px, 14.5/400, secondary columns `--muted`,
  numbers right and tabular, one pill per row, trailing ⋮ in a 30px circle where §3 names it. Hover
  `--hov`, selected `--sel` with a 2px accent bar at the left edge. No zebra.
- **List row (R11 rail, R24 rail).** 60px two-line rows for the live rail: 14.5 title, 13 muted phrase,
  time right in muted tabular.
- **Node / stage card (R23).** 1px border, radius 14, padding 16; icon tile 34px radius 9 filled with the
  hue at 14%; title 15/600; subtitle 13 muted (run id · duration); status line 13 (outcome word or "Running
  62%" left, cost right); 3px progress bar, full for done, partial for running, empty for pending. Widths
  300–320.
- **Edges.** 1.5px curves (cubic, horizontal tangents), coloured by the source card's hue at 60%, 6px
  endpoint dots (R23). Canvas is a dot grid (`--dots`, 18px pitch) inset in `--card-2`.
- **Timeline (R23).** One 2px line, 12px dots, done segments in `--accent`, pending in `--border-2`, label
  14.5/600 above, time 13 muted below, five to six milestones evenly spaced.
- **Settings row (R22).** Grid `380px 1fr`, 1px divider, padding 22px 0. Left: label 15/600 and one muted
  phrase of at most six words. Right: the control (switch 44×24, value text, pills, or a 48px select).
  Section header above the rows: 17/600 title, one muted phrase, a right-aligned link with an external
  icon.
- **Tab row (R22, R19).** 40px tabs, 14.5/500, active tab tinted `--card-3` with `--text`, inactive muted;
  a count pill on a tab only where §3 gives one.
- **Avatars.** 28px initials circles, `--card-3` with a 1px `--border-2`, stacked at −8px (R19).
- **Switch.** 44×24, accent when on (R22 has none; R09 shape).

Light theme: page `#F1F2F4`, sidebar `#F7F8F9`, cards white, the 1px shadow above; dark theme: unchanged
tokens, emphasis by border + glow. Type scale and fonts (Geist, Geist Mono) unchanged.

## 4. Per-screen contract

Word caps are BRIEF-v2 §2's, plus Governance 240. Every screen keeps BRIEF-v2 §3's contents; the list
below says what changes shape and which reference each part copies now.

1. **Queue** (cap 240; keep R11 layout). List rows in the R18 table shell (title "Queue" + "10 items", one
   search pill, filter dropdowns Bucket / Kind / Ticket replace the chips). Detail card copies R19's card:
   two pills (kind, bucket), title 17/600, meta line "T-0412 · 58m", the three slot rows as R19 checklist
   rows (28px avatar, name, role, then a filled green check for approved with the time, an empty circle for
   open), the evidence line, four pill buttons. The card carries `.is-sel`. Rail: the gauge card, the bucket
   bar and the by-kind grid styled as R23's details rail (label, value, stat boxes).
2. **Tickets** (cap 200). R18: KPI cards, table shell with search + State / Tier / Class dropdowns, 60px
   rows, ⋮ circle. Bulk bar stays (R04). S0–S6 dots stay.
3. **Ticket detail** (cap 260; copies R23 wholesale). Header: key + title 24/600, state pill, tier, cost,
   elapsed, one primary pill "Open queue item". Hero card "Execution flow" on the dot canvas: S0 intake as
   the Goal card at the left (blue-less: neutral border, ticket icon, key and title); S1–S4 as four stage
   cards stacked in one column with curved edges from S0 (base advance as a small node under S4); S5 checks
   as the decision card; S6 packet as the completion card with "2 of 3 slots"; a final "PR" card, pending.
   Under it the R23 timeline with the stage times from BRIEF.md §2.3. Right rail (R23): "Ticket" details
   card (progress bar "5 of 7 stages", Started / Elapsed stat boxes), "Links" (Jira, GitHub, Slack icon
   squares), Approvals as the R13 step list (5 rows). Below the hero: Artefacts (11 rows) and Assumptions
   (3 rows). If the cap binds, drop the Links card first.
4. **Runs** (cap 260 for Observatory). R18 KPI cards and table shell (Outcome / Stage / Ticket dropdowns),
   60px rows; the running row's card treatment is the pulse dot, not a glow. Live rail: 60px list rows.
5. **Run detail** (cap 260; R13 structure). Stat strip as four R23 stat boxes (Cost box carries the 3px
   budget bar). Step list rows 60px with R19 checklist glyphs; task 3 expanded. Inputs and guard panels,
   event log as the inset mono block. No timeline (the step list is the timeline).
6. **Report** (cap 220). R18 KPI cards. Panels unchanged in content; panel headers as the table shell
   header (title + period). The baseline line stays one muted line.
7. **Factory** (cap 260). Header: manifest v14, short hash, "Gate pass" dot-word, one primary pill "Open
   PR". Manifest table in the R18 shell (title + "7 stages"). Agent cards as R23 stage cards, five across,
   pass rate as the progress bar, `.is-live` on s4-implementer. Sandbox policy as four R22 settings rows
   with switches.
8. **Governance** (new; cap 240; `src/08-governance.html`, `id="s-governance"`, hash `#governance`, nav
   under Record, captures `08-governance-light.png` / `-dark.png`). Copies R22 wholesale. Title in the top
   bar "Governance". Tab row: Trust profile (active), Owners. Section header: "Trust profile" 17/600,
   muted phrase "4ab7d0…c19d · approved 3 Sep 2026", right link "config/trust-profile.yaml" with an
   external icon. Settings rows: Admitted scope → "Northwind Payments" + pill "fixture"; Data classes →
   pills "internal" "public" and the phrase "default deny"; Routes → a four-row mini table (route, provider,
   reader role, retention): hosted model inference · Anthropic API · agent · 0 d; export and display ·
   local · owner · 90 d; digest · Slack, stub · team · 30 d; pull request · GitHub, stub · reviewer · repo;
   Sanitisers → "3 identities"; Guard, 30 days → "6,412 allow · 88 redact · 2 deny"; Approvals → two rows
   with avatars: Ines Carvalho · Security · approved, expires 30 Nov; Mei Lin · Legal · approved, expires
   30 Nov. Second section "Owners" 17/600, muted phrase "config/owners.yaml · 9 roles": rows Factory owner
   → Priya Raman; Security approver → Ines Carvalho; Legal approver → Mei Lin; S3 reviewer, S6 reviewer,
   Outcome recorder → names from BRIEF.md §2.2 / §2.3 slot rows (use only people who already appear
   there). Footer: ghost "Cancel", primary "Approve profile". The two hashes here are the exception to
   BRIEF-v2 §2's hash rule (the trust-approval subject is the profile hash plus the owners hash).

## 5. Working rules (parallel builders on one file)

The file is split. `src/00-head.html` (head, CSS, icon sprite, sidebar, top bar), `src/01-queue.html` …
`src/08-governance.html` (one `<section class="screen">` each), `src/99-tail.html` (router script). 
`python3 tools/assemble.py 02-observatory` writes `02-observatory/index.html`; it hoists any
`<style data-screen="…">` block found in a screen partial into the head.

- You own only the files your prompt names. Edit with the Edit tool; never Write over `index.html` and
  never assemble to `index.html` (the assembler agent does that). Preview with
  `python3 tools/assemble.py 02-observatory --out 02-observatory/_preview-<you>.html`, capture that, and
  delete it when you finish.
- Screen-scoped CSS goes in `<style data-screen="<id>">` inside your partial; every selector starts with
  `#s-<id>`, so an override can only touch your screen. All CSS in `00-head.html` (shared components and
  the older per-screen blocks) belongs to the system agent; override it under your `#s-<id>` prefix rather
  than editing it, and if a shared component itself is wrong, say so in your report.
- Record the md5 of each file you own when you start; if it changes under you, stop and report.
- Captures: `python3 tools/capture.py 02-observatory <screen> --profile <scratch>/chrome-<you>` captures
  one screen in both themes at the height the screen needs (it probes the content bottom first) into
  `02-observatory/captures/`; for a preview file, run headless Chrome per BRIEF.md §5 by hand with
  `--timeout=20000` and your own `--user-data-dir`, one run at a time. Chrome on this machine often writes
  the PNG and then never exits: wait 25s, kill it, and use the PNG it wrote. Never two runs at once.
- Word count: `python3 tools/wordcount.py 02-observatory/_preview-<you>.html` (the caps include
  `governance=240`). Under cap before you report.
- Side-by-side: `python3 tools/sidebyside.py references/R18.png <capture> <scratch>/sbs.png`, then look at
  it with the Read tool. For each screen you own, at least one side-by-side per theme before you report.
- When you have reported, you are done. Do not act on later notifications.

Reviewers (fresh context) score each screen 1–10 on hierarchy, density, spacing and alignment, colour and
contrast, craft, from side-by-sides against the reference named in §4, citing measurements; findings go
to `02-observatory/REVIEW-v3.md`. Pass: every cell ≥ 8, every count under cap, 16 captures.
