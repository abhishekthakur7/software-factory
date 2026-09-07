# Soft Factory UI mockups, round 2: shared brief

> **Data corrections after the first build (apply these when reviewing; the numbers below are now the
> truth everywhere in §2):** the Runs table was re-timed so one runner never overlaps (new start times, one
> new row run_1e05, the 09:00 digest dropped from the latest 20); header counts are now 43 runs today /
> 35 pass / 5 fail / 1 blocked / 1 aborted_human / 1 running / $72.90 settled, with the shown 20 rows at
> 14 pass / 3 fail / $38.52 settled; S6 run_f0c9 starts 14:05 (after S5 ends 14:00:44) and the packet
> approvals moved to Tomasz 14:12 and Priya 14:19; the blind_spot waiver is at 14:03; ticket ages changed
> for T-0409 3h 59m, T-0415 4h 14m, T-0417 5h 34m, T-0418 4h 40m, T-0420 30m, T-0411 29m; queue item ages
> changed for #1 58m, #2 2h 54m, #3 1h 51m, #4 2h 18m, #6 1h 46m, #7 30m, #8 3h 08m, #10 26m; agents'
> last runs are s0-intake run_1e05 14:35 and s3-planner run_c4d8. Item numbering and list order are unchanged.

Three directions, same seven screens, same fake data, each direction fully realised in light and dark.
One Opus agent builds one direction. Read this whole file before writing a line of HTML. The direction
sections at the end (§7) are the only part that differs between agents.

Owner's bar, verbatim: "at least the same level of fidelity and premium-ness as the references; no AI slop
tendencies; fake data on every screen so the mockup is complete across screens; light and dark for each."

Bar in practice: a screenshot of any screen, in either theme, should pass as a shipped product page from a
well-funded ops tool (Linear, Vercel, Warp, Raycast level). If a screen looks like a template with the labels
swapped, it is not done.

## 1. The product in 30 seconds

Soft Factory is a governed software factory. A ticket (from Jira) walks through stages run by agents:
S0 intake, S1 context, S2 clarify, S3 spec and plan, S4 implementation, S5 checks, S6 packet and human
review, then a PR is opened. People are reached only through the queue: one queue item per thing that
needs a person, resolved by one recorded decision. Every run records model, cost, duration, lease, and the
hashes of everything it used. Approvals bind to hashes. Everything lands in one append-only local record.
One person, one machine, one ticket at a time; the runner is local, model inference is not.

Vocabulary (use these exact tokens in chips and labels, lowercase with underscores as shown):

- Ticket states: intake, context, clarifying, planning, plan_review, implementing, checks, review,
  pr_opened, merged, abandoned, rejected, escalated.
- Stages: S0 intake, S1 context, S2 clarify, S3 plan, S4 implement, S5 checks, S6 packet.
- Run kinds: stage, task, child, fix_round, base_advance, utility.
- Run outcomes: pass, fail, blocked, refused, aborted_human, infrastructure_failure, running.
- Queue item kinds: packet_approval, plan_approval, red_check, escalation, question_round, eligibility,
  rubric_inspection, pr_outcome, control_event, manual_pause.
- Attention buckets: act today, this week, when convenient.
- Tags (failure modes): FM-1 wrong scope, FM-4 stale context, FM-7 scope creep, FM-10 packet defect,
  FM-12 flaky check.
- Data classes: internal, public. Tiers: 1, 2, 3.
- Act controls: Approve, Request changes, Send back, Waive, Abandon, Resume, Stop, Record outcome.

## 2. Fixed fake data (use verbatim; trim rows on small surfaces, never invent new entities)

Product: Soft Factory. Org / workspace: Northwind Payments. Signed-in user: Priya Raman (Owner),
priya@northwind.dev. Runner: runner-01 (local, Cursor SDK). Manifest v14, hash 9c1e42…8af2. Trust profile
hash 4ab7d0…c19d. Today: Sun 6 Sep 2026, 15:04.

Repos: northwind/ledger-core (Java), northwind/settlement-api (Java), northwind/merchant-portal (TypeScript).
Ticket key prefixes map to repos: LED-* ledger-core, SET-* settlement-api, MP-* merchant-portal.

People (initials avatars, deterministic colours, no stock photos): Priya Raman (owner, PR), Tomasz
Wierzbicki (reviewer, TW), Ines Carvalho (security, IC), Daniel Okafor (platform, DO), Mei Lin (product, ML).

### 2.1 Tickets (12)

| id | key | title | repo | tier | class | state | cost | age | queue |
|---|---|---|---|---|---|---|---|---|---|
| T-0412 | LED-2291 | Reject settlement batches whose currency differs from the merchant account | ledger-core | 2 | internal | review | $18.40 | 3h 40m | packet_approval |
| T-0409 | LED-2287 | Add idempotency key to refund POST | ledger-core | 1 | internal | implementing | $9.12 | 3h 59m | rubric_inspection |
| T-0415 | LED-2302 | Backfill merchant timezone on legacy accounts | ledger-core | 2 | internal | plan_review | $6.75 | 4h 14m | plan_approval |
| T-0417 | SET-118 | Retry settlement webhook with exponential backoff | settlement-api | 1 | internal | checks | $11.30 | 5h 34m | red_check |
| T-0403 | LED-2270 | Rename ledger_entry.amount_cents to minor_units | ledger-core | 3 | internal | escalated | $27.60 | 6h 15m | escalation |
| T-0418 | MP-77 | Show settlement ETA on merchant dashboard | merchant-portal | 1 | public | clarifying | $2.10 | 4h 40m | question_round |
| T-0420 | LED-2310 | Remove deprecated v1 export endpoint | ledger-core | 2 | internal | intake | $0.30 | 30m | eligibility |
| T-0398 | LED-2261 | Fix rounding drift in FX conversion | ledger-core | 2 | internal | pr_opened | $14.90 | 2d | pr_outcome |
| T-0391 | SET-104 | Add merchant_id to settlement audit log | settlement-api | 1 | internal | merged | $7.40 | 4d | — |
| T-0387 | LED-2244 | Migrate batch runner to virtual threads | ledger-core | 3 | internal | rejected | $1.05 | 5d | — |
| T-0395 | MP-62 | Export statements as CSV | merchant-portal | 1 | public | abandoned | $5.20 | 6d | — |
| T-0411 | LED-2289 | Validate IBAN checksum at intake | ledger-core | 1 | internal | context | $0.85 | 29m | manual_pause |

Stage progress per ticket (for S0…S6 mini-progress indicators): T-0412 S0–S6 done, waiting at review;
T-0409 S0–S3 done, S4 running; T-0415 S0–S3 done, plan_review; T-0417 S0–S4 done, S5 red; T-0403 S0–S3
done, S4 escalated at task 4/7; T-0418 S0–S1 done, S2 waiting on answers; T-0420 S0 done; T-0398 all
done, PR #4821 open; T-0391 all done, merged PR #4790; T-0387 rejected at S0; T-0395 abandoned at S3;
T-0411 S0 done, paused at S1 boundary.

Counts by state for the Tickets header: 12 total; active 8 (intake 1, context 1, clarifying 1, plan_review 1,
implementing 1, checks 1, review 1, escalated 1); pr_opened 1; closed 3 (merged 1, rejected 1, abandoned 1).

### 2.2 Queue items (10; the human inbox, grouped by bucket; keep this order)

| # | kind | ticket | age | bucket | what is needed (one line in the list; full text in the detail pane) |
|---|---|---|---|---|---|
| 1 | packet_approval | T-0412 | 58m | act today | Final review packet v1. Slots: reviewer Tomasz ✓, owner Priya ✓, security Ines (open). Subject hash 1d9f…e4. |
| 2 | plan_approval | T-0415 | 2h 54m | act today | Plan v2: 6 tasks, 3 acceptance criteria, base 7c2a19f. Owner slot open. |
| 3 | red_check | T-0417 | 1h 51m | act today | integration-test recipe red at head, green at base. Fix rounds 2 of 2 used. Options: send back, waiver, abandon. |
| 4 | escalation | T-0403 | 2h 18m | act today | Third verification failure on task 4 of 7 (rename touches 212 files). Options: superseding plan, abandon. |
| 5 | control_event | (none) | 6h | act today | Sandbox integrity: egress attempt to 34.12.8.9:443 denied by guard. Category execution_boundary. Disposition open. |
| 6 | question_round | T-0418 | 1h 46m | this week | Round 1, 3 questions ranked. Q1 "Which timezone for ETA?" default: merchant account tz. Q2 "Show ETA when batch is pending?" default: yes. Q3 "Round to hour or minute?" default: hour. |
| 7 | eligibility | T-0420 | 30m | this week | S0 scripts pass. Provisional tier 2, class internal, CODEOWNERS: ledger-core/api. Decide eligibility. |
| 8 | rubric_inspection | T-0409 | 3h 08m | this week | Grader-only line S3-L4 "plan names every touched service" needs a human verdict. |
| 9 | pr_outcome | T-0398 | 2d | when convenient | PR #4821 open on ledger-core. Record merge, abandon, or revision. |
| 10 | manual_pause | T-0411 | 26m | when convenient | Paused by Priya at the S1 boundary. Note: "waiting on index rebuild". Resume or stop. |

Header counts: 10 open; act today 5, this week 3, when convenient 2. By kind: approvals 2, checks 1,
escalations 1, questions 1, other 5. Median queue latency today 38m.

Selected item on the Queue screen is #1 (packet_approval, T-0412). Its detail pane shows:

- Packet summary: "Rejects batches whose currency differs from the merchant account at intake; adds
  CurrencyMismatch handling to BatchIntake; 6 tasks, 1 fix round, 2 deviations, 9 checks (8 pass, 1 waived)."
- Slots: reviewer Tomasz Wierzbicki, approved 14:12; owner Priya Raman, approved 14:19; security Ines
  Carvalho, open (yours if you hold the role; Priya does not).
- Evidence table, 9 checks: lint pass 0:12; compile pass 1:04; unit (142 tests) pass 2:31; integration
  (18) pass 3:12; migration-dry-run pass 0:40; secrets-scan pass 0:08; size-and-scope pass (14 files,
  +312 −48); dependency-diff pass (no change); blind_spot: "no test covers multi-currency refunds" waived by
  Priya, expires 14 Sep, tag FM-12 not applied.
- Subject hash 1d9f…e4 (packet v1 + PR body v1 + head 3f8d0aa). Freshness: current.
- Attestation text: "I have read the packet at hash 1d9f…e4 and approve it for the review slot 'reviewer'."
- Act controls: Approve (primary), Request changes, Send back ▾ (to context / clarifying / planning; requires
  a tag), Abandon (requires a tag). Show the tag picker as a small secondary control with the five tags.

### 2.3 Ticket T-0412 (Ticket detail screen)

Header: LED-2291 · T-0412 · "Reject settlement batches whose currency differs from the merchant account" ·
tier 2 · class internal · state `review` · repo northwind/ledger-core · branch factory/T-0412 · base 9e40b21 ·
head 3f8d0aa · target main · manifest 9c1e42…8af2 (v14) · trust 4ab7d0…c19d · cost to date $18.40 ·
opened Sun 11:24 · 3h 40m elapsed · Jira LED-2291 (link).

Stage timeline (the hero of this screen):

| stage | run | duration | cost | outcome | note |
|---|---|---|---|---|---|
| S0 intake | run_2b1c | 0:41 | $0.02 | pass | scripts pass, eligibility granted by Priya |
| S1 context | run_5e77 | 6:12 | $1.14 | pass | 2 index entries read, 1 flagged stale (FM-4) |
| S2 clarify | run_9a03 | 4:58 | $0.92 | pass | 1 round, 3 questions, 2 answered, 1 default accepted |
| S3 spec and plan | run_c4d8 | 14:37 | $4.60 | pass | plan v2 approved (2 slots), 3 criteria, 6 tasks |
| S4 implementation | run_7f3a | 31:05 | $9.85 | pass | 6/6 tasks validated, 1 fix round, 2 deviations |
| S4 base advance | run_7f3b | 0:09 | $0.00 | pass | disjoint advance 7c2a19f → 9e40b21 (minor row) |
| S5 checks | run_e1a2 | 7:44 | $0.41 | pass | 9 checks: 8 pass, 1 blind_spot waived by Priya 14:03 (expires 14 Sep) |
| S6 packet | run_f0c9 | 1:20 | $1.46 | pass | packet v1 + PR body assembled, packet_approval queued 14:06 |

Current position: after S6, waiting on the queue item (review). Next: pr_opened.

Artefacts (kind, version, hash, class): brief v1 a3e1…07 internal; criteria v1 5c9d…b2 internal; question
set v1 8d10…4e internal; risk map v1 f27a…91 internal; plan v1 (superseded) 41b0…c3; plan v2 0b3d…f9
internal; handoff v1 6e8c…2a internal; deviation list v1 9f44…d8 internal; readiness table v1 b7c2…15
internal; packet v1 1d9f…e4 internal; PR body v1 e02b…6c public.

Approvals: plan v2: reviewer Tomasz 12:48, owner Priya 12:51. Packet v1: reviewer Tomasz 14:12, owner
Priya 14:19, security Ines pending. Waivers: blind_spot "no test covers multi-currency refunds", granted by
Priya 14:03, expires 14 Sep.

Assumption log: (1) accepted default "reject at intake, not at settlement" (S2, Q2); (2) accepted default
"error code CURRENCY_MISMATCH" (S2, Q3); (3) agent-declared "merchant account currency is immutable after
onboarding" (S3, unverified, flagged for reviewer).

Tags: FM-4 stale context on run_5e77 (index entry "settlement-flow.md" last verified 2 Jul), resolved by
re-read. Questions: 3 asked, 2 answered by Mei Lin, 1 default accepted.

### 2.4 Run run_7f3a (Run detail screen)

Header: run_7f3a · T-0412 LED-2291 · S4 implementation · kind stage · attempt 1 of 3 · outcome pass ·
started 13:21:08 · ended 13:52:13 · 31:05 · lease runner-01.

- Model and runtime: runtime Cursor SDK (local); requested claude-opus-5, resolved claude-opus-5; model
  check pass; fallback models disabled; grader claude-sonnet-5.
- Cost and usage: budget $12.00, settled $9.85 (82%); tokens input 412k, output 38k, cached 1.1M;
  cost_settled_at 13:52:40.
- Lease and heartbeat: runner-01, heartbeat 12s ago (at the time of capture: show "last heartbeat 13:52:01"),
  lease expired normally at 13:52:13.
- Tool calls 187: read 94, edit 41, recipe 22, codegraph 30.
- Guard decisions: 214 allow, 3 redact, 0 deny. Sandbox integrity: pass.
- Inputs by hash: agent s4-implementer a11f…3c; skill s4-implement.md 77c0…b8; shared skill
  repo-conventions 5d2e…01; rubric S4 e9b1…77; plan v2 0b3d…f9; manifest 9c1e…8af2; trust 4ab7…c19d;
  sandbox policy c8a0…42; context index 3e77…a0.
- Outputs: handoff v1 6e8c…2a; deviation list v1 9f44…d8 with 2 deviations: "used existing
  CurrencyMismatchException instead of new type" and "skipped migration test, covered by integration
  recipe"; 22 tool-result files (recipe outputs).
- Tasks: 1 add CurrencyValidator (pass, 4:12); 2 wire into BatchIntake (pass, 6:40); 3 unit tests (pass after
  fix round, 9:05); 4 integration test (pass, 5:31); 5 error message copy (pass, 1:48); 6 changelog (pass,
  0:52).
- Recipes run: lint ×4 (all pass), compile ×6 (5 pass, 1 fail), unit ×8 (7 pass, 1 fail), integration ×4
  (all pass).
- Event log: 13:21:08 run started, lease acquired runner-01; 13:21:11 inputs verified (9 hashes);
  13:21:40 task 1 started; 13:25:52 task 1 validated; 13:32:32 task 2 validated; 13:39:04 task 3 unit
  recipe fail (2 tests red); 13:39:20 fix round 1 started; 13:41:37 task 3 validated; 13:47:08 task 4
  validated; 13:48:56 task 5 validated; 13:49:48 task 6 validated; 13:50:30 handoff v1 written; 13:51:02
  deviation list v1 written; 13:52:13 run ended pass; 13:52:40 cost settled $9.85.

### 2.5 Runs (Runs list screen; the latest 20 of today's runs, newest first)

| run | ticket | kind | stage | attempt | model | started | duration | cost | outcome | lease |
|---|---|---|---|---|---|---|---|---|---|---|
| run_d204 | T-0409 | stage | S4 | 1/3 | claude-opus-5 | 14:42 | 22:10 (running) | $3.52 so far | running | runner-01, heartbeat 4s |
| run_u020 | — | utility | index rebuild | 1/1 | — | 14:38 | 3:44 | $0.00 | pass | released |
| run_77d2 | T-0411 | stage | S1 | 1/3 | claude-sonnet-5 | 14:36 | 2:10 | $0.31 | aborted_human | released |
| run_1e05 | T-0411 | stage | S0 | 1/1 | claude-haiku-4-5 | 14:35 | 0:24 | $0.02 | pass | released |
| run_0c3e | T-0420 | stage | S0 | 1/1 | claude-haiku-4-5 | 14:34 | 0:36 | $0.02 | pass | released |
| run_f0c9 | T-0412 | stage | S6 | 1/1 | — | 14:05 | 1:20 | $1.46 | pass | released |
| run_e1a2 | T-0412 | stage | S5 | 1/1 | — | 13:53 | 7:44 | $0.41 | pass | released |
| run_7f3b | T-0412 | base_advance | S4 | 1/1 | — | 13:52 | 0:09 | $0.00 | pass | released |
| run_7f3a | T-0412 | stage | S4 | 1/3 | claude-opus-5 | 13:21 | 31:05 | $9.85 | pass | released |
| run_51a7 | T-0418 | stage | S2 | 1/3 | claude-sonnet-5 | 13:14 | 4:15 | $0.80 | blocked | released |
| run_44e8 | T-0417 | stage | S5 | 1/1 | — | 13:06 | 6:51 | $0.38 | fail | released |
| run_c7a1 | T-0417 | fix_round | S4 | 2/2 | claude-opus-5 | 12:56 | 9:02 | $2.31 | fail | released |
| run_c7a0 | T-0417 | fix_round | S4 | 1/2 | claude-opus-5 | 12:47 | 8:14 | $2.05 | pass | released |
| run_9d11 | T-0403 | task | S4 task 4 | 3/3 | claude-opus-5 | 12:28 | 18:20 | $6.12 | fail | released |
| run_c4d8 | T-0412 | stage | S3 | 1/3 | claude-opus-5 | 12:12 | 14:37 | $4.60 | pass | released |
| run_e83f | T-0415 | stage | S3 | 1/3 | claude-opus-5 | 11:57 | 13:02 | $4.21 | pass | released |
| run_bb72 | T-0409 | stage | S3 | 1/3 | claude-opus-5 | 11:44 | 11:58 | $3.90 | pass | released |
| run_9a03 | T-0412 | stage | S2 | 1/3 | claude-sonnet-5 | 11:38 | 4:58 | $0.92 | pass | released |
| run_5e77 | T-0412 | stage | S1 | 1/3 | claude-sonnet-5 | 11:31 | 6:12 | $1.14 | pass | released |
| run_2b1c | T-0412 | stage | S0 | 1/1 | claude-haiku-4-5 | 11:24 | 0:41 | $0.02 | pass | released |

One runner, so runs never overlap: each row starts after the previous one ended (the 09:00 digest run_u019
and the earlier runs of T-0409, T-0415, T-0417, T-0403 and T-0418 fall outside the latest 20). The index
rebuild run_u020 is the one Priya paused T-0411 for.

Runs header counts (today): 43 runs, 1 running, 35 pass, 5 fail, 1 blocked, 1 aborted_human; $72.90 settled
today. The table shows the latest 20 (14 pass, 3 fail, 1 blocked, 1 aborted_human, 1 running; $38.52 settled in
the shown rows, run_d204's $3.52 unsettled). Filters: ticket, stage, kind, outcome, model. The selected/expanded row is run_7f3a. Where a
direction nests child rows, nest run_7f3b under run_7f3a; run_c7a0, run_c7a1 and run_9d11 have parents outside
today's list, so show them flat with a "child of run_…" note (T-0417 S4 parent run_c6f2 at 12:05, T-0403 S4 parent run_9d0e at 09:12).

### 2.6 Report (last 30 days, "7 Aug – 6 Sep 2026", range control 7d / 30d / 90d with 30d active)

Tiles: tickets closed 38; merged 31 (82%); abandoned 4; rejected 3; median cycle time intake→pr_opened
4h 12m; cost per merged PR $13.70 median, $412 this week; human minutes per ticket 9.5 median; queue
latency median 38m, p90 3h 10m; first-pass check pass rate 71%; send-backs 6; escalations 3.

Hero chart, cost per merged PR by day (31 values, 7 Aug → 6 Sep, weekends dip):
14.2, 8.1, 6.4, 12.9, 15.6, 18.3, 13.1, 16.8, 7.2, 6.0, 11.4, 14.7, 21.9, 17.2, 12.6, 8.8, 6.9, 13.5, 19.4,
28.7, 16.1, 14.0, 7.5, 6.3, 12.2, 15.9, 13.8, 22.4, 14.6, 11.7, 13.7. Show the median line at $13.70 and a
callout on 26 Aug ($28.70, "T-0403 escalation, 3 attempts").

Runs by outcome (30 days): pass 212, fail 23, blocked 9, refused 2, aborted_human 3, infrastructure_failure 4.
Daily stacked bars: weekdays 7–12 runs, weekends 1–3; distribute the failures across weekdays, with a cluster
of 4 fails on 26 Aug.

Stage cost share: S4 58%, S3 21%, S1 9%, S6 6%, S2 4%, S5 2%.

Queue latency histogram (50 decisions): <15m 9, 15–30m 14, 30m–1h 11, 1–2h 7, 2–4h 5, 4–8h 3, >8h 1.

Tag leaderboard: FM-4 stale context 5, FM-7 scope creep 4, FM-10 packet defect 2, FM-12 flaky check 2,
FM-1 wrong scope 1.

Baseline row, labelled exactly "context measure, not comparable": pre-factory cycle time 3.2d, human review
minutes per ticket 41. Unavailable measures show "not yet measurable" (e.g. "defect escape rate", "PRs
merged without revision").

Model spend (30 days): claude-opus-5 $318.40 (74%), claude-sonnet-5 $88.10 (20%), claude-haiku-4-5 $4.20
(1%), grader claude-sonnet-5 $19.70 (5%). Tokens 30d: 41.2M input, 3.1M output, 96M cached.

### 2.7 Factory (Factory config screen, includes Agents)

Manifest v14, hash 9c1e42…8af2, migrated 3 Sep 2026, approved by Priya (re-approval on migration).
Fixture gate: 41 fixtures, last pass 6 Sep 14:22 (smoke 12, conformance 29). Factory tree: 63 files pinned by
hash. Change control: reviewed PR only; last change PR #4802 "raise S3 budget to $6" merged 3 Sep.

Stage × tier manifest:

| stage | tier | agent | model | skill | shared skills | rubric | budget | tools |
|---|---|---|---|---|---|---|---|---|
| S0 intake | all | s0-intake | claude-haiku-4-5 | s0-intake.md | question-format | rubric-s0 (7 lines) | $0.10 | read |
| S1 context | 1–3 | s1-context | claude-sonnet-5 | s1-context.md | repo-conventions | rubric-s1 (11) | $2.00 | read, codegraph |
| S2 clarify | 1–3 | s2-clarify | claude-sonnet-5 | s2-clarify.md | question-format | rubric-s2 + checklists | $1.50 | read |
| S3 plan | 1–3 | s3-planner | claude-opus-5 | s3-plan.md | repo-conventions | rubric-s3 (14) | $6.00 | read, codegraph |
| S4 implement | 1–3 | s4-implementer | claude-opus-5 | s4-implement.md | repo-conventions | rubric-s4 (9) | $12.00 | read, edit, recipe, codegraph |
| S5 checks | all | (scripts) | — | — | — | rubric-s5 (12) | $1.00 | recipe |
| S6 packet | all | (scripts) | — | — | — | rubric-s6 (6) | $2.00 | — |

Agents (5 cards or rows): s0-intake (haiku, hash 2f9a…c1, 6 fixtures, last run run_1e05 14:35, 30d runs 61,
pass 97%); s1-context (sonnet, 8be0…7d, 8 fixtures, last run run_77d2, 30d runs 58, pass 93%); s2-clarify
(sonnet, c41d…09, 7 fixtures, last run run_51a7, 30d runs 54, pass 91%); s3-planner (opus, 0ab7…e5,
9 fixtures, last run run_c4d8, 30d runs 52, pass 88%); s4-implementer (opus, a11f…3c, 11 fixtures, last run
run_d204 running, 30d runs 49, pass 79%). Grader model: claude-sonnet-5. S2 restatement model:
claude-haiku-4-5.

Shared skills: repo-conventions 5d2e…01 (S1, S3, S4), question-format 91c3…4b (S0, S2).

Recipe catalogue: lint (30s, exit 0/1), compile (5m, 0/1), unit (10m, 0/1/2), integration (15m, 0/1/2),
e2e (25m, 0/1/2, tier 3 only), migration-dry-run (5m), secrets-scan (1m), size-and-scope (10s),
dependency-diff (1m).

Sandbox policy digest c8a0…42: copy-on-write worktree mount; allowlisted env; no push URL; scoped runtime
key; loopback proxy allowlist per stage (S0/S1 atlassian read, S1/S3/S4 codegraph, S6 none).

Trust profile 4ab7d0…c19d: 4 routes (hosted model inference, export and display, digest stub, PR stub);
approvals security Ines Carvalho (expires 30 Nov), legal Mei Lin (expires 30 Nov); classes internal, public;
sanitiser identities 3; guard decisions 30d: 6,412 allow, 88 redact, 2 deny.

## 3. The seven screens

Every screen keeps the direction's app frame: left nav (Queue with count badge 10, Tickets, Runs, Report,
Factory; a Northwind Payments workspace switcher at the top; Priya Raman at the bottom), a top bar with
search (⌘K), a theme toggle, and a small runner status ("runner-01 · leased to run_d204" or idle). Screen
IDs in parentheses are the URL hashes the file must honour (§5).

1. **Queue** (`#queue`). Header counts by bucket and kind. The 10 items as a list: kind chip, ticket key +
   title, one-line need, age, bucket. Item 1 selected with its detail pane open (§2.2): packet summary,
   slots, evidence table, subject hash and freshness, attestation text, act controls, tag picker.
2. **Tickets** (`#tickets`). Filter chips (state, tier, class, repo, "has queue item"), counts by state,
   the 12 tickets as a table: key, title, repo, tier, class, state chip, S0–S6 mini progress, cost, age,
   queue kind. One row hovered, one selected (T-0412). Bulk-action affordance where the direction has one.
3. **Ticket detail** (`#ticket`). §2.3. The S0→S6 stage timeline is the hero. Then artefacts, approvals and
   waivers, assumption log, tags, questions, and a link to the queue item.
4. **Runs** (`#runs`). §2.5. Header counts, filters, the 20 runs with run_7f3a expanded or selected. One
   running row with a live indicator (heartbeat).
5. **Run detail** (`#run`). §2.4. Header, model and runtime, cost and usage (budget bar), lease and heartbeat,
   tool calls, guard decisions, inputs by hash, outputs with the deviation list expanded, task table, recipe
   runs, event log.
6. **Report** (`#report`). §2.6. Tiles, hero chart, runs by outcome, stage cost share, queue latency
   histogram, tag leaderboard, model spend, baseline row with its exact label, "not yet measurable" cells.
7. **Factory** (`#factory`). §2.7. Manifest header and fixture gate, stage × tier table, agents (5), shared
   skills, recipe catalogue, sandbox policy, trust profile routes and approvals with expiry.

## 4. Quality bar and anti-slop rules (hard requirements)

Typography
- One UI family and one monospace family, bundled as woff2/ttf under `assets/` with `@font-face` and a real
  fallback stack. Sizes: 11/12/13/14/16/20/28 (or your own 6-step scale), consistent line heights, weight
  400/500/600 only. `font-variant-numeric: tabular-nums` on every number column. Uppercase section labels get
  +0.04em tracking and 11–12px. No faux bold, no text shadows, no letter-spaced body text.
- Titles are the product's words. No "Welcome back", no "Let's analyze your stats", no marketing copy,
  no "AI-powered", no sparkle glyphs.

Colour and theme
- A token set on `:root` (surfaces 0–3, border, border-strong, text, text-muted, text-faint, accent,
  accent-fg, and the semantic set: pass/green, fail/red, warn/amber, info/blue, running/violet) redefined
  under `[data-theme="dark"]`. Dark is tuned, not inverted: elevation by lighter surfaces, borders at
  ~8–12% white, no black-on-black, desaturated accents where the light accent would glow.
- One accent colour per direction. Semantic colours are used only for meaning (outcomes, states, buckets)
  and consistently across all seven screens. Contrast ≥ 4.5:1 body, ≥ 3:1 secondary and chart labels, in both
  themes.
- No purple→blue gradient backgrounds, no neon glow on everything, no glassmorphism except where a direction
  explicitly asks for it, no 3D blobs, no decorative orbs.

Layout and density
- 8px grid, 4px sub-grid. Cards radius 10–14, controls 6–8, chips 999. Hairline borders (1px) over shadows;
  shadows only on floating layers (popovers, drawers, bulk bars), and then two-layer soft shadows.
- Tables: header row with muted uppercase or sentence-case labels, 40–52px rows, fixed-width slots
  (`flex: 0 0 Npx`) for checkboxes, icons, chips and trailing actions so columns align across rows; right-align
  numbers; truncate titles with ellipsis. Show one hover row and one selected row.
- No empty grey boxes, no "chart goes here", no lorem, no identical three-card grids of nothing, no centred
  hero text in an app screen, no giant whitespace between sections.

Icons and imagery
- Inline SVG icons, 16 or 20px, single stroke width (1.5), one visual family throughout (Lucide-style is fine,
  hand-write the paths). Never emoji, never mixed icon sets. Avatars are initials on deterministic colours.
  No stock photos, no illustrations, no logos you do not own (a plain wordmark "Soft Factory" is fine).

Charts (real, from the data in §2)
- Inline SVG built from the actual values, with axes, gridlines, tick labels, legend, and one hover callout
  drawn in (the references all show one). Line charts use a 1.5–2px stroke and optional low-alpha area fill.
  Bars have 2px radius max. Donuts show the total in the centre. Heatmaps have a labelled scale. Sparklines
  in KPI cards are drawn from a plausible 14–30 point series. Colours come from the token set.

States and interaction
- Nav switches screens without reload; the theme toggle works; hover styles on rows, buttons, chips; the
  running run pulses gently (CSS only); disabled buttons look disabled. Nothing needs to actually do anything
  else. Keep JS under ~150 lines, vanilla, no framework, no CDN.
- Data consistency: the same ticket/run/cost numbers on every screen. Cross-check before you finish.

Fidelity check before you report done
- Take the captures (§5), open every PNG with the Read tool and look at it. Fix clipping, overlap, orphan
  elements, misaligned columns, unreadable contrast, chart labels colliding, uneven paddings, and any place
  where a component reads as "template". Do at least two full capture-and-fix passes. If something is still
  wrong at the end, say so in README.md.

## 5. Technical spec (identical for all directions)

- Folder: `docs/design/claude-mockups/<NN-name>/` with `index.html` (one file, all CSS and JS inline),
  `assets/` (fonts only), `captures/` (14 PNGs), `README.md`. Touch nothing outside your folder.
- `index.html` renders all seven screens as sections; the nav shows one at a time. On load, honour
  `location.hash` (`#queue #tickets #ticket #runs #run #report #factory`; default `#queue`) and the query
  `?theme=light|dark` (default light; a direction may default to dark, but the query must win). The theme
  toggle sets `data-theme` on `<html>`.
- Designed for a 1600×1000 viewport; must still be correct at 1440 wide and not break at 1280. The page may
  scroll vertically inside the content area; screens are desktop only.
- Works from `file://` with no network. Fonts: copy from `docs/design/mockups/01-atelier/assets/`
  (Geist Regular/Medium/SemiBold, Geist Mono) or `docs/design/mockups/03-studio/assets/`
  (Plus Jakarta Sans variable), or download woff2 from Google Fonts (request the CSS with a desktop
  user-agent to get woff2 URLs, then fetch the files). Verify in a capture that the bundled font actually
  rendered (compare a glyph you know, e.g. Geist's single-storey g, Plus Jakarta's rounded a).
- Captures: headless Chrome, one PNG per screen per theme, named `NN-screen-theme.png`
  (e.g. `01-queue-light.png` … `07-factory-dark.png`). Command template (query before hash):

```
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu \
  --hide-scrollbars --window-size=1600,1000 --screenshot="captures/01-queue-light.png" \
  "file:///ABSOLUTE/PATH/index.html?theme=light#queue"
```

  Use `--window-size=1600,1400` (or taller) when a screen is longer than the viewport so the capture shows
  the whole screen. Add `--force-device-scale-factor=2` for a close-up polish check, but keep the shipped
  captures at scale 1.
- README.md (short, plain, no self-praise): the direction in three sentences; the token table (light and
  dark values for the main tokens); type scale; what each screen borrows from which reference; which fonts
  are bundled; what you verified and how; anything unfinished or uncertain.

Available skills you may load with the Skill tool before designing: `high-end-visual-design`,
`emil-design-eng`, `design-taste-frontend`, `dataviz`. They are optional; this brief wins on any conflict.

## 6. Reference catalogue (the owner's 17 images, described because you cannot see them)

R1 Workflow builder, light. White chrome, 72px icon rail + 300px panel "Search" and grouped node library
(INPUT: File, Text Content, Sheets, Example Data, Webhook, Schedule; TRANSFORM: Filter, Merge, Group, Sort,
Javascript, Geocode, Colorize; AI & ACTIONS collapsed), dashed "Drag nodes to canvas" drop zone. Top bar: tab
"◇ Untitled" + "+", centre undo/redo and a "Social media" name field, right Save / Share / gear / lime "▷ Run".
Dotted canvas with white rounded node cards (icon in a tinted circle, title, muted subtitle: "Data Source /
Webhook trigger", "AI Processor / GPT-4 Analysis", "Format Output / JSON Transform", "Generate Report / PDF
Export", "Send Notification / Email & Slack", "Summarize / Content summary"), indigo bezier edges with small
outlined pill labels on them ("raw data", "Analysis", "Report", "Formatted", "status"). Zoom control
"− 100% + | Reset". Bottom split panel: "Console" with timestamped lines "12:43:01 INFO Workflow started",
"SUCCESS Data Source → Connected successfully" and indented JSON blocks; "Debug" with per-node cards
"1 ● Data Source DONE 0.17s", key/value in/out summaries, "WARN" amber for a node. Rounded geometric sans.

R2 Event engagement dashboard, dark. Charcoal #16171B page over a blurred olive backdrop, cards #1C1D22
radius 16. Top: search "⌘K", three date stat pills, "● Live Data". Five KPI tiles, each with a different
micro-chart: area line, step line with an annotation pill "245%", red step bars with pill "75%", square-wave
line, a dot-matrix. Big "Engagements per attendee 312%" three-line chart with a vertical cursor and callout
"312% Actions", y-axis labels 70K…00K, x-axis Day 1–5. "Mobile vs web engagement %" curves with month pills
(Apr active). "Chat messages per session" horizontal stacked bars by weekday. "Peak engagement time"
heatmap grid with hatched empty cells. Lavender accent ~#A99BF5, lime for one series, white text, thin icon
rail with a colour legend of dots.

R3 E-commerce dashboard, light indigo. White cards, three pastel KPI cards (blue/teal/orange tint):
label, big number, "Total visits today 7% ↗", a slider-like progress with a knob, "View Detail" link.
"Revenue" area chart with indigo gradient fill, dashed orange comparison line, callout "$180 / 21 August
2018" on a point. "Profit" ring gauge in three colours with a legend of rows (Current $500 ↗ 37%). Segmented
text "Day Week Month ···". Sidebar with indigo active pill and a badge "5" on Mail.

R4 Orders (Mate), light with dark sidebar. Sidebar #1B1F22: wordmark, search "⌘F", nav rows (Dashboard,
Orders active, Inventory, Payments, Customers; Notifications with red badge 7; Help; Settings), user at
bottom. Content: "Orders" H1, "↓ Import" (black) and "↑ Export" buttons. Filter chips: "Type 3 ▾" (active,
black), "Status ▾", "Order date ▾", "All filters ▾". Table: checkbox, "#192541" with a comment icon, initials
avatar + name, type, status "✓ Paid" green / "↺ Refunded" / "✕ Cancelled" red, product thumbnails, total,
date, "···". Selected rows tinted grey with checked boxes. A floating "Order #4567" card over the table:
drag handle, open and close icons, contact rows, tabs "Order items / Delivery / Docs", line items, total,
buttons Export / Duplicate / Print. Right rail (white, 1px separators): "RECEIPT OF GOODS" semicircle gauge
"$2.2m 242 orders" plus two stats; "ORDERS STATUS Active ▾" segmented progress bar Paid 89% / Cancelled 8% /
Refunded 3%; "OVERVIEW This month ▾" 2×3 stat grid; "TOP SELLERS". Bottom floating dark bulk bar:
"✕ | Selected: 5 | ↑ Export | Print | Duplicate | ···". Green #2F6B4F for positives.

R5 Finance (ACRU), light lime. Off-white #F4F4F2 page, white cards radius 16, sidebar with nested
"Transactions ▾ / History 19 / Integration / Reports", "Cash flow", "Budget", "Investments", "Learning
center", "Support", an "Upgrade to Pro!" card, "Collapse sidebar". Top: "Quick search" pill, bell, gear,
user card "Michael Johnson m.johnson@finex.com", "+ Add widget". "$12,450 Balance overview" with "7d ▾" and
chart-type toggles, stacked bars lime/yellow/orange with hatched inactive bars and a tooltip card
"Wednesday, 7 Jan 2025 · Savings $240 · Income $700 · Expenses $460". "Total income $15,000 ↗5.1% from last
month". "My card" green debit card; quick actions row of square icon buttons "Top up, Send, Request,
History, More"; "Quick payment" avatar row. "Monthly spending limit" progress $8,600 of $10,000.
"Cost analysis $8,450" segmented colour bar + legend list with percentages. "Financial health 75%" semi-donut
in greens. "Goal tracker" rows with thumbnails, amounts and progress. "Transaction history" list with logos,
"+$1,100 Completed" green / "−$6,400 Declined" orange.

R6 Dark analytics, magenta/cyan. Page #121212, cards #1C1C1E radius 20. "Sales Report" two smooth lines
(magenta, cyan) with a glowing point and tooltip "$11,854.05", y 6k–18k, months on x. Small tiles "Sales
Report / Customer Growth / Visitors / Sales by Time" with mini charts. "Payment History" invoice rows
"Invoice #6709 $146.00 March 12 ● Completed" (green/yellow/red dots). "Sales by Time GMT-8" heatmap grid
hours × weekdays in cyan intensities. "Sales Locations" dotted world map with flag rows "United States 712".
"Traffic source" vertical stacked segment bars with a callout "3,567 / 3,124 / 1,431". "Balances overview"
cards with sparklines and "$51,674.86 +1.45%".

R7 Credit score, light frosted. Pill top nav "Dashboard / Credit History / Loans / Disputing / Documents /
Updates", "Hey, Stewart! Let's analyze your stats!", "Transunion Score ▾", giant "730 +6 pts Excellent",
three coloured range strips with dots, cards radius 24 "Payments on Time 24/38" with a dot grid, gradient
photo-like cards "TD Bank USA $12.340 Term 36 m.", "Credit History" line with a lime point "730", a floating
right glass panel with tabs Details / Timeline / Updates and a year × month grid of ✓ / ✕ chips, bottom pills
"Make a Payment / Create Dispute / Calculate".

R8 Learning hub, dark neon. Course cards with orange/blue/magenta gradients, mono captions "REACT • TS •
NEXT.JS", "56%" with a progress bar, weekly schedule gantt with gradient bars per weekday row and an hour
axis 1 pm–6 pm, "My Progress" segmented ring "80% OVERALL", "My Tasks 3 tasks" cards with progress bars.

R9 Dark settings panels. Charcoal #2B2B2E surfaces radius 28, indigo #6C63FF primaries. "Chat Settings"
with an icon segmented toggle and a "Notifications" switch with stacked avatars "+6"; "App Settings" with a
"Color Theme" segmented control ☼ / ☾ Dark / 🦇 (tooltip "Black"), "App Color" swatch row with a checked
swatch, rows "Open Overlay 20sec ⇅ [G]" and "Quick Call [Cmd] + [L]" as key-cap chips; "New Task" composer
with an avatar select, "Share your idea" placeholder and a "Cmd + V Paste" tooltip, "1 unsaved draft · Apply";
"Upcoming" with tabs "Chat 3 / Tasks / Activity", member chips "Scott ×" "Jessica ×" "+6", a "Today ‹ › 8"
date stepper; "Members List" with "New Task" input and a member invite row.

R10 Sidebar (Synerque). Expanded 300px, black #141414: round logo + wordmark, "Task manager ⌃⌄"
workspace select in a #1E1E1E box, nav rows with 20px icons and 18px text (Chat with "99+"), a "Tasks"
group with colored shape bullets and counts (● In progress, ▲ Paused, ■ Bugs 12 active row, ★ Done).
Collapsed 88px rail with icons and dot badges; hovering the rail opens a flyout list with drag handles, round
coloured logos, "CryptoFrog / Crypto company • UX/UI Design", one row highlighted.

R11 Agent monitoring (Stealth), dark. Page #0E0F11, cards #141619 radius 12, borders ~8% white. Sidebar:
wordmark "STEALTH v2.7", "A Anthropic / prod ⌃⌄" switcher, groups Monitor (Overview active, Agents 24,
Runs 12.4k, Traces), Analyze (Evals, Costs, Logs), Operate (Alerts 3 red, Settings), user card bottom.
Header "Overview", search "Search runs, agents, traces..", green "+ New Agent". "Live monitoring across 24
agents", "Filter" in red. Three KPI cards: "Runs 12,438 ↑ 8.4% vs yesterday" with a green area sparkline;
"Success Rate 98.7% ↓ 0.4 pts vs 7d avg" red sparkline; "Tokens Burned 8.4M ↑ 12.1% • $142 / hr". "Agent
Runs • 30 min buckets" three jittery lines green/yellow/red with legend "success 12,272 · failed 128 ·
timeout 38", dotted gridlines, x 00:00…24:00. Bottom row: "Top Tools" rows "web_search 24,820" with a green
progress bar and "p95 420ms · 0.4% err"; "Model Split 8.4M Tok" stacked colour bar and rows
"claude-sonnet-3.5 4.4M 52.4%"; "Recent Changes / Deploys & Config" rows "research-agent-v2 v2.71 → v2.7.2
maya 14:02". Right rail "● Live Activity" with pause and Filter, rows "● research-agent-v2 / r_8a3f12 •
14:32:18 / 1.4s 12.4k tok", amber pill "Retry 1/3", red pill "Tool Error". Green #22C55E accent.

R12 Agents list, light. Four KPI cards each with a round outlined icon, label and value ("Active Agents
1/2", "Actions taken (7d) 450", "Successful outcomes 97", "Time saved (est) 23.4 hrs"). Tabs "All / Running (1)
/ Paused (1) / Draft (0)". Agent cards: round icon, "ML Senior - Auto-Source" + "Auto-Sourcer · Realtime",
status dot "Running" violet / "Paused" amber / "Processing" / "Testing" / "Planning"; key/value rows "Runs
412 / Hits 86 (teal) / Approval Auto"; buttons "⏸ Pause" "Open" and a trash icon. A dashed "Create new
agent" card. Indigo "+ New Agent". "Invite Members".

R13 Agent execution viewer, dark navy #1E2130. Top: "☰ Menu 5", "AI Agent", bell, "John H.". Breadcrumb
"← Back to Agents List | ✦ Agent A1618 › Execution 1284". Card: "Agent Execution Viewer" with "↻ Restart /
↓ Export Logs / ⤴ Share"; stat strip "TOTAL STEPS 5 / ERRORS 1 / DURATIONS 2.78s / STATUS Completed". Left:
"Search steps", "Filter", tabs "All / Errors / Warnings / API Calls", numbered step rows "1 Initialize Agent
Context / 14:32:01.234 • 12ms" with pills Success (green) / Warning (amber) / Error (red) / Running (violet)
and a chevron; the first is expanded showing "Response" and "Request" JSON blocks in dark code boxes.
Right: "Execution Flow" canvas with zoom controls and step cards whose header strip is coloured by status
("1 Step" green, "3 Step" amber, "4 Step" red, "5 Step" violet), connected by thin lines. Below: "Execution
Output" with "Copy / Download", tabs "Raw Output / JSON / Logs", a monospace log block
"[14:32:01.234] Initialize Agent Context - SUCCESS (12ms)".

R14 "What it costs" cards, dark navy #070B16. Four cards, each with a tinted glow (purple, green, blue,
orange), an icon in a tinted circle, label "Monthly Cost", big number "$97.61", delta "↗ 12.5% (+10.84) vs
Apr 1–Apr 30", a sparkline area along the bottom. Numbered captions beside them "01 What it costs / 02 How
much is processed / 03 How often it runs / 04 What powers it". Fourth card "Active Models 3 of 5 allowed"
with a row of model logos and an orange progress "60%".

R15 AI cost overview (Core AI), dark navy. Sidebar Overview / Usage / Models / API Keys / Billing /
Reports / Alerts / Integrations / Settings with an "Upgrade Plan" card. Header "Overview / Monitor your AI
usage, cost and model activity", date "Aug 1 – Aug 31, 2026 · Last 30 days ▾". The four R14 cards in a row.
"Insights BETA" banner with a lightbulb and "View details →". "Aug 31 Spend So Far $4.37 ↗8.5% vs yesterday"
line chart with callout "Aug 17, 2026 (so far) $1.40", "Daily ▾". "Cost Breakdown" donut "$97.61 Total" with
legend rows "GPT-4 $51.96 (53.2%)". "Token Usage 339,170" bar chart. "Model Usage & Cost" table with columns
Model / Tokens / Request / Cost / Avg. Cost / Cost % / Trend (mini sparkline per row) and "Export CSV".
"Recent Activity" rows "10:32 am · GPT-4 · 2,450 tokens · $0.07 · ✓ Success". A right "AI Assistant" rail
with suggestion chips (do not copy the orb).

R16 Oreflow, light. Sidebar "General: Overview (active), My Agents, Tasks 3, Memory 87% Used! (red),
Execution Logs, Knowledge Base, Prompt Library; My Workspace: Automations, Workflows 8, Recent Runs,
Templates, Team Members". Top: bell, "July 12 ▾", stacked avatars. Canvas header "⚡ Market Scout ▾ ·
Environment: Production ▾ · + Add Node". Node cards with coloured tab headers (Shared Files cyan, Model
pink, LLM Responses green, Memory purple, Prompt blue, Review Queue yellow), content inside (checklist rows
with green checks, a quoted prompt, "17 +3 from yesterday" with "9 High / 5 Medium / 3 Low" dot matrices),
and one primary button each ("Retrieve Context →", "Open Queue →"). Cyan edges with small circular ports.
Bottom "Projects Time" gantt: "RUN HISTORY" legend, gradient bars per run on an hour axis 9 am–3 pm.

R17 Voice agent builder (ChatDash), frosted teal-grey. Header: "ChatDash | Acme Support / Billing Agent",
segmented "Flow / Orbit / Timeline", ring "72%", "Test call", dark "Publish". Left "Node library 12" with
search "/" and a two-column grid of icon tiles with drag handles (Voice, Language, Pace, Pitch, Tone,
Timing, Script, Response Logic, Intent, Business, Platforms, Connections). Canvas: "Business scopes" with
chips Invoices / Refunds / Payments, branches to "Platforms" (logo tiles) and "Routing" (logo tiles) via a
"● Prepare the call" pill, then "Write script" (quoted script) and "Voice" (waveform, selected with a teal
outline), then "Response logic" with a two-colour bar "Match intent / Fallback", branches labelled "Matched"
(green pill) and "Fallback" (red pill) to "Call ends / Logged to CRM" and "Transferred / Human ⏱ 40s".
Right panel "Pace / Customize the pace": arc gauge "1.15× 148 WPM" with 0.5×–2.0× ticks, "− + ▷ Play",
"Words stretching" word chips, "Pauses" sliders "Sentence 380ms / Question 520ms / Number 180ms", "Adapt"
toggles. Glass cards with 1px white borders on a soft gradient.

## 7. Directions (each agent reads only its own section, but the shared parts above apply to all)

### 7.1 Direction 01 Workbench (folder `01-workbench`), light-first

Character: a clean operations workbench. Dark charcoal sidebar against a white/off-white content area,
hairline borders, one restrained accent, dense readable tables, and floating layers (a detail card over the
table, a bulk-action bar) where a person acts. Feels like R4 and R5 with the KPI treatment of R3 and the
agent cards of R12.

Borrow, concretely:
- App frame from R4 and R10: dark sidebar (#1B1F22 light theme, #0F1113 dark theme) with wordmark, search
  "⌘K", nav with count badge on Queue, workspace switcher "Northwind Payments ⌃⌄" (R10 style), Priya at the
  bottom. Content area white in light, #141618 in dark.
- Filter chip row from R4 ("State 3 ▾" active black, "Tier ▾", "Class ▾", "Repo ▾", "All filters ▾").
- Table style from R4: checkbox column, key with a comment icon where the ticket has a queue item, initials
  avatars for owners, status text with a glyph ("✓ pass" green, "✕ fail" red, "↺ fix_round"), selected rows
  tinted, "···" trailing action, one row hover.
- Floating detail card from R4 for the Queue's selected item (drag handle, open/close icons, tabs "Packet /
  Evidence / Slots", act buttons at the bottom) and the bottom floating dark bulk bar on Tickets and Runs
  ("✕ | Selected: 3 | Export | Send back | Abandon | ···").
- Right rail from R4 on Queue and Report: uppercase 11px labels ("QUEUE LATENCY", "BY BUCKET"), a semicircle
  gauge, a segmented status bar with a legend (act today 50% / this week 30% / when convenient 20%), a 2×3
  stat grid.
- KPI cards from R3 and R5 for Report tiles: pastel-tinted card, label, number, delta with arrow, a thin
  progress or sparkline, "View detail" link. Stacked bars with hatched inactive bars (R5) for runs by outcome;
  the R5 segmented colour bar with legend list for stage cost share; the R5 semi-donut for first-pass check
  pass rate 71%; the R3 area chart with a dashed comparison line (median) for cost per merged PR.
- Agent cards from R12 for Factory: round icon, name + "claude-opus-5 · s4-implement.md", status dot, k/v
  rows (30d runs / pass rate / fixtures), "Open" and "Evals" buttons.
- Settings chips from R9 for Factory sandbox policy and recipe timeouts (key-cap chips, switches).
- Ticket detail hero: the S0→S6 timeline as a horizontal stepper of cards (like R5's goal rows turned
  sideways), current stage outlined in the accent, base advance as a thin connector label.
- Run detail: two-column, left the task table and recipe runs, right the cost budget bar, lease card and
  event log as a vertical timeline with times in mono.

Palette: light page #F6F7F5, card #FFFFFF, border #E4E6E3, text #15181A, muted #6B7176, accent deep green
#1E6B48 with a lime highlight #C8F169 used sparingly (active nav marker, a chart series). Dark: page
#0F1113, card #16191C, border rgba(255,255,255,.08), text #E8EAE6, muted #8E949A, accent lime #B9E85A on
dark with green #2F8F5E for pass. Semantic: pass #1F8A5B, fail #D14343, warn #C98A17, info #2F6BD6,
running #6F5BD9.

Type: Plus Jakarta Sans (bundled from `docs/design/mockups/03-studio/assets/`) for UI, Geist Mono (from
`01-atelier/assets/`) for ids, hashes, numbers in tables. If you prefer Inter or Manrope, download and bundle
it; say which in README.

### 7.2 Direction 02 Observatory (folder `02-observatory`), dark-first

Character: a monitoring room. Near-black surfaces, cards separated by 1px 8%-white borders, small
tabular numerals, sparklines everywhere numbers live, a live activity rail, and status colours that carry
the meaning. Feels like R11 with the KPI cards of R14/R15 and the execution viewer of R13; R2 and R6 for
chart variety. The light theme is a tuned off-white console, not an inverted dark one.

Borrow, concretely:
- App frame from R11: sidebar with wordmark "Soft Factory" + version "v0.14", "N Northwind / local ⌃⌄"
  switcher, groups "Work" (Queue 10, Tickets 12, Runs 20), "Record" (Report), "Factory" (Factory), user
  card bottom. Header with the page title, a "Search tickets, runs, hashes.." input, and the runner status
  pill "● runner-01 · run_d204 · 22:10".
- Right "● Live Activity" rail from R11 on Queue and Runs: rows "● run_d204 / T-0409 · S4 · 14:42 / 22:10 ·
  $3.52", amber pill "fix round 2/2" on T-0417, red pill "escalated" on T-0403, violet pulse on the running
  run.
- KPI cards from R14/R15 for Report tiles and the Runs header: icon in a tinted circle, label, big number,
  delta line "↗ 8.4% vs previous 30d", sparkline area at the bottom; subtle tint per card (violet for cost,
  green for merged, blue for cycle time, amber for queue latency). Keep the glow at ≤ 12% alpha.
- Charts: R11's three-series jittery line (pass/fail/other per day) for runs by outcome with a legend
  showing counts; R15's donut with centre total for stage cost share; R15's model table with a mini
  sparkline per row for model spend; R2's heatmap grid with hatched empty cells for queue latency by hour ×
  weekday (derive a plausible grid from the histogram); R11's "Top Tools" progress rows for the tag
  leaderboard; R6's invoice-style rows with status dots for recent decisions.
- Ticket detail hero from R13's "Execution Flow": stage cards S0…S6 in a row, each with a header strip
  coloured by outcome, run id, duration and cost, connected by thin lines; base advance as a small node
  under S4. Below it, R13's step list (expandable, first expanded) for artefacts and approvals.
- Run detail from R13: stat strip "TASKS 6 / FIX ROUNDS 1 / DURATION 31:05 / OUTCOME pass", left step list
  of the 6 tasks with pills, task 3 expanded showing the failing unit output and the fix; right the inputs by
  hash and the event log as a monospace "Raw output / JSON / Logs" block.
- Factory: R15's model table for agents (agent, model, skill, fixtures, 30d runs, pass %, trend sparkline),
  R11's "Recent Changes" rows for change control (PR #4802 "raise S3 budget to $6" priya 3 Sep), R11's
  "Model Split" stacked bar for model spend share.
- Queue list rows with the age right-aligned in mono and the bucket as a coloured dot, selected item in a
  right pane with the evidence table as a compact monospace-numbered table.

Palette dark: page #0B0C0E, card #121417, card-2 #181B1F, border rgba(255,255,255,.08), text #E7E9EC,
muted #9AA1A9, faint #5F666E, accent green #22C55E (running violet #8B7CF6, fail #EF4444, warn #F59E0B,
info #3B82F6). Light: page #F3F4F6, card #FFFFFF, border #E3E5E8, text #14171A, muted #667079, accent green
#15803D, and the same semantic hues darkened one step.

Type: Geist (bundled from `docs/design/mockups/01-atelier/assets/`) for UI, Geist Mono for ids, hashes and
all numbers. Sizes 11–13 dominate; page titles 18–20.

### 7.3 Direction 03 Canvas (folder `03-canvas`), light-first, pipeline as a graph

Character: the factory as a node canvas. The ticket's S0→S6 walk is drawn as connected node cards on a
dotted canvas with labelled edges for the artefacts that flow between stages; a console and a debug panel
sit beneath; the node library becomes the manifest. Feels like R1 with R17's frosted panels, R16's coloured
node headers, and R13's status-coloured flow. Glass is allowed here, restrained: 1px white borders, 60–70%
white cards over a very soft gradient in light; in dark, cards #1A1D24 at 85% over a #0F1115 canvas.

Borrow, concretely:
- App frame from R1 and R10: a 64px icon rail (home/Queue, Tickets, Runs, Report, Factory as icons with
  dot badges; hover flyout labels), a 280px panel that changes per screen (Queue: the list; Ticket: the
  artefact outline; Run: the task outline; Factory: the node library grid from R17 with drag handles;
  Report: the measures list), top bar with a tab strip ("◇ T-0412 LED-2291" + "+"), centre undo/redo and a
  name field, right "Save / Share / ⚙ / ▷ Run" (Run in lime as in R1, disabled with a tooltip "runner-01
  leased to run_d204").
- Ticket detail (the hero screen): canvas with 8 node cards (S0…S6 plus the S4 base advance as a small
  node), icon in a tinted circle, title "S3 spec and plan", subtitle "run_c4d8 · 14:37 · $4.60", a status
  strip or dot; bezier edges with outlined pill labels for what flows ("ticket source", "brief", "criteria +
  questions", "plan v2", "handoff + deviations", "check evidence", "packet"); the review gate drawn like
  R17's Matched/Fallback branch ("approved" green pill toward "pr_opened", "send back" red pill looping to
  S1/S2/S3). Zoom control "− 100% + | Reset". Beneath: "Console" (event log lines with INFO / PASS / WARN
  chips and one expanded JSON-like block for the deviation list) and "Debug" (per-stage cards "1 ● S0 intake
  PASS 0:41" with in/out artefacts and hashes; S1 card shows "WARN FM-4 stale context").
- Run detail: the 6 tasks as nodes left-to-right, task 3 with a red-outlined "fix round 1" branch that
  rejoins (R17 style), a right property panel like R17's: budget arc gauge "$9.85 of $12.00 · 82%", token
  split bars, lease card, guard decision toggles-as-readouts (allow 214 / redact 3 / deny 0), and the console
  beneath with the recipe log.
- Queue: left panel list of the 10 items (kind chip, key, age); the canvas shows the selected item as a
  frosted detail card (R17's right panel treatment) with slots, evidence, attestation and act buttons; the
  remaining space shows the ticket's mini pipeline with the blocked node highlighted.
- Tickets and Runs: tables inside a large frosted card with R1's rounded geometric type; the S0–S6 progress
  as a row of small connected dots; runs nest child rows.
- Report: R16's coloured-tab cards (each measure group gets a tab colour), the R16 gantt for today's runs
  per ticket on a 09:00–15:00 axis, R1-style dot matrices for queue by bucket, and the hero line chart in a
  frosted card.
- Factory: the R17 node-library grid for the manifest (one tile per stage with model chip and budget),
  the stage × tier table, agents as R16 cards with a coloured tab per stage, recipe catalogue tiles with
  timeouts, trust routes as a small tree.

Palette light: canvas gradient from #F7F8FA to #EEF1F5 with a dotted grid rgba(0,0,0,.08), cards
rgba(255,255,255,.72) with 1px rgba(255,255,255,.9) border and a faint 0 1px 2px shadow, text #17191F,
muted #6A7280, accent indigo #5B5BD6 for edges and selection, lime #C6F03A for the Run button only,
stage tab colours (S0 slate, S1 cyan, S2 amber, S3 violet, S4 indigo, S5 green, S6 pink) at low saturation.
Dark: canvas #0F1115 with grid rgba(255,255,255,.07), cards rgba(26,29,36,.85), border rgba(255,255,255,.1),
text #E9EBF0, muted #949CAB, accent #8C8CF0.

Type: a rounded geometric sans, Outfit or Lexend, downloaded and bundled (fallback Plus Jakarta Sans from
`03-studio/assets/`), with JetBrains Mono or Geist Mono for the console and hashes.
