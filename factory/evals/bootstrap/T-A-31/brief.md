# T-A-31 brief: S6 packet and PR body, evidence table, test summary, the assembly run, and base-test protection completed

## What this delivers

The S6 assembly run stops being a stub: it becomes a script-only driver
that runs the race guard and the freshness recheck, confirms the review
tuple's own S5 run is both current and cleared, then assembles the local
`packet` and the `pr_body` from data gathered off the record -- never
agent prose -- and opens `packet_approval` on a pass. The packet itself
is produced by two standalone scripts sharing one rendering module.
Base-test protection is completed: the S5 `base_test_diff` script gains
the both-views rerun and per-row verdicts, and every base-test change or
removal is now recorded as a runner-written `deviation` row at S4
hand-back, for both an ordinary task run and a fix round.

- `factory/scripts/tools/packet_render.py` (new, shared) -- the section
  builders both assembly scripts call: identity and freshness, the one
  evidence table, decisions, not-touched, risk map, deviations (with the
  base-test diff subsection), assumptions, test summary, blind spots, and
  the diff. Nothing here is authored prose; every cell is copied from
  `packet_inputs.json`, with a fixed small vocabulary for `kind` and a
  few literal `status` values the input does not itself carry (e.g. a
  waiver row's status is always the literal `waived`).
- `factory/scripts/tools/packet_assemble` / `pr_body_assemble` -- thin
  CLIs (`--inputs --out`) over that module; `pr_body_assemble` renders
  with `include_diff=False` and appends one line explaining the omission.
  Both exit 0 on success, non-zero with a stderr message on a malformed
  or incomplete inputs file.
- `runner/artefacts.py` -- `SECTIONS["packet"]` replaced with the
  charter's fixed twelve-section order; `SECTIONS["pr_body"]` added
  (the same list minus `Diff`); `PACKET_TABLES` registers the evidence
  table's six columns beside `PLAN_TABLES`.
- `runner/checks/artefact_structure.py` -- `KIND_TABLES["packet"]` wired
  to `PACKET_TABLES`, so the general structure check still enforces the
  packet's section order and its evidence table's columns.
- `factory/scripts/checks/base_test_diff` -- a new optional
  `--tests-head-in-base` argument (same shape as `--tests-head` plus a
  `failed` list). For every planned `change` entry naming an `AC-n`
  criterion, records `verdict: pass` (the head test fails against base,
  proving the change), `blind_spot` (passes both views, proves nothing),
  or `exempt` (a `no_behaviour_change` task row, never rerun). `result`
  is `fail` when anything is unplanned, else `blind_spot` when any
  planned entry is a blind spot, else `pass`.
- `runner/stages/S5.py` -- the both-views rerun: for every diff test file
  a `change` row names with an `AC-n` criterion, copy the head version
  into a fresh throwaway copy of the base checkout, run the project's
  test recipes there once, and pass the ran/failed identities to
  `base_test_diff` as `--tests-head-in-base`. A second, unrelated fix
  applied in the same file: a governed recipe's raw per-side result, and
  an ungoverned recipe's own base-side result, are now recorded
  `check_tier = "advisory"` rather than `"blocking"` -- S5's own routing
  already never lets either gate the run on its own (`regression_only`
  folds the governed ones; only an ungoverned recipe's *head* result
  blocks directly), but every `_record_check_result` call had hard-coded
  `check_tier = "blocking"` regardless, so `waivers.cleared` -- which
  this ticket is the first caller of against a real S5 run -- read every
  one of them as a gate and never returned true even on an otherwise
  clean pass. See "decisions this brief did not already settle" below.
- `runner/stages/S4.py` -- `record_handback` gains optional `plan_text`/
  `base_sha` parameters; when given, it records a `deviation` row for
  every base-test file the hand-back's own diff touches (authorized or
  not), immediately after the commit, before any round-level refusal
  decision. Both call sites (`run`, for an ordinary task, and
  `_execute_fix_round`) now pass them. `_check_fix_round_diff` keeps its
  refusal logic (a fix round touching an unauthorized base test still
  fails the round) but no longer writes the deviation row itself, since
  `record_handback` already did.
- `runner/stages/S6.py` -- the real driver, replacing the stub. See
  "the S6 driver" below.
- New eval directories `factory/evals/scripts/tools/packet_assemble/`
  and `pr_body_assemble/`; three new `base_test_diff` fixtures
  (`both_views_pass`, `both_views_blind_spot`, `both_views_exempt`).
- New tests `test_s6_packet_assemble.py`, `test_s6_pr_body_assemble.py`,
  `test_s6_test_summary.py`; `test_s5_base_test_diff.py` extended;
  `test_s4_handback.py`/`test_s4_fix_round.py` adjusted where the
  generalised deviation recording changed what they could assert;
  `test_stub_walk.py` adjusted so the walk reaches the real S6.

## Rows covered

R-S6-1, R-S6-2 (`docs/prd/05-S6-human-review.md`); R-S4-10
(`docs/prd/03-S4-implementation.md`).

## The S6 driver

In order: `reviewer_sets.recompute_before_dispatch` over the current
diff, compared against the review tuple's own bound `actual_reviewer_set_hash`
(reusing that tuple's already-bound authority-policy and membership-
snapshot hashes -- see below); `freshness.check` at `BEFORE_DISPATCH`;
the review tuple's own S5 run must be the ticket's latest S5 attempt and
`waivers.cleared` over it must hold. Only then does it gather
`packet_inputs.json` (identity and freshness from the tuples and the
freshness result; checks from `waivers.blocking_status` plus the
`check_result`/`artefact` rows it points at; fix rounds from the S4
`fix_round` runs; base-test changes from the `deviation` rows S4 now
writes, with each file's own `git diff` hunk and hash; readiness,
alternatives, changed contracts, non-goals, untouched scope rows, risk
map and checklist verdicts parsed from the plan artefact; assumptions
from the current, unsuperseded, non-withdrawn set; blind spots from the
plan's own blind-spot rows), runs both assembly scripts, registers
`packet`/`pr_body`, and opens one `packet_approval` item naming the
packet, unless one is already open.

## Decisions this brief did not already settle

- **`BEFORE_DISPATCH`'s "no pending pull-request intent" reason is not
  itself blocking at S6.** That boundary's intent-identity check exists
  to catch an *existing* pending intent whose base or subject moved; a
  ticket assembling its packet for the first time has no intent yet --
  intent creation is triggered later, by `packet_approval` reaching
  quorum. Calling `freshness.check(boundary=BEFORE_DISPATCH)` with no
  intent yet always adds exactly that one reason and nothing else; S6
  treats that specific, singular reason as non-blocking and any other
  reason (a moved base, a moved subject) as the stale binding the brief
  describes. The check_result `freshness.check` itself writes on any
  non-fresh result is left as-is either way -- accurate evidence of what
  was found, whether or not this driver routes on it.
- **The race guard reuses the bound `actual` reviewer set's own
  authority-policy and membership-snapshot hashes** rather than taking a
  fresh snapshot via `owners.identity_snapshot`. That function stamps its
  own `taken_at`, so a fresh snapshot changes on every call regardless of
  whether anything real moved, which would make the race guard report a
  moved set on every single invocation. Reusing what S5 already bound
  isolates the comparison to what can actually have moved: the diff's
  touched paths, the target base, and CODEOWNERS itself.
- **A fix round's "recipes cleared"** is derived from the `task_validation`
  check results of the `validation_only` run the runner opens
  immediately after that round's own hand-back -- the nearest thing the
  schema carries to what a round cleared, since neither row is linked to
  the other by a foreign key.
- **The "Intent and scrutiny" section's intent/scrutiny split** is a
  plain text split on the first `Scrutiny:` marker (the convention the
  existing S3 fixture plans already use); a plan that never wrote the
  marker leaves `scrutiny` empty rather than guessing.
- **"Non-goal" lines** are extracted from the `Goals and non-goals`
  section's prose by sentence, keeping any sentence that starts with
  "Non-goal" case-insensitively; there is no other machine-readable
  convention for this section anywhere else in the codebase.
- **An approvals list for the evidence table's `approval` rows** reads
  every current `approval_record` for the `gate = 'plan'` subject the
  review tuple's own plan tuple bound -- the plan approvals a reviewer
  can already see recorded; final-review approvals are the next ticket's
  (the `packet_approval` subject itself, per the brief, stays the review
  tuple hash "for now").

## Known simplifications

- The evidence table's `fix_round` rows carry no `hash` cell: a
  `stage_run` carries no content hash of its own in this schema for the
  script to cite, so that cell renders empty for that one row kind only.
- `packet_render.py`'s per-row `source_artefact` cells use the same
  `<table>:<id>` convention COMMON.md already establishes for `ref`
  columns elsewhere (e.g. `check_result:<id>`, `waiver:<id>`), since the
  packet's own evidence rows are not literally artefact-table rows.
