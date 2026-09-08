# T-A-27 brief: bootstrap checklist, human verdicts, plan tuple and approval, race guard

## What this delivers

Until calibrated graders exist, the runner assembles one bootstrap
checklist standing in for every grader-only Initial rubric line across
S1, S2, and S3, derives the plan-approval subject from it, and admits
`implementing` only when that subject carries full, current, unforked
quorum plus a trusted target-head fetch.

- `runner/checklist.py` (new) -- `expected_instances(conn, ticket, *,
  rubric_paths=DEFAULT_RUBRIC_PATHS) -> tuple[Instance, ...]` expands
  every `checklist: yes` line across the pinned rubric files by its own
  `subject`: `artefact` keys one instance by the stage's own artefact
  kind (`brief`/`criteria`/`plan`); `criterion` one per `AC-n` row of the
  latest criteria artefact; `question` one per question row of the
  ticket; `contract_unit` one per `Contracts` row of the latest plan.
  Raises `ChecklistError` on a duplicate `(rubric_line_id,
  subject_item_key)` pair. `record_verdict` is the sole writer of
  `human_verdict`: binds the instance, the rubric file's own sha256, the
  stage-appropriate subject artefact and its hash, and the cited
  evidence's hashes; refuses an instance outside the expected set, a
  `pass` with no evidence, and an evidence id outside this ticket's own
  artefacts. `completeness` reads the newest verdict per instance and
  reports missing, unwaived-blind-spot, and failed instances; a
  `blind_spot` counts as unwaived unless an unexpired `waiver` row names
  that exact verdict row. `checklist_hash`/`verdict_set`/`waiver_set` feed
  the plan tuple's own three checklist-derived hashes.
- `runner/plan_tuple.py` (new) -- `derive_components` reads every bound
  field fresh off the record into a `binding.PlanComponents`;
  `ensure_current` is the one place a `plan` `evidence_tuple` is created,
  returning the latest tuple's id when `binding.plan_tuple_currency` says
  it still matches and a freshly created one otherwise; `current_subject`
  is the read-only queue-display lookup.
- `runner/reviewer_sets.py` -- `derive_planned` shares `_match_paths` with
  `derive_actual` (a new `flag_unmatched` parameter: `derive_actual` keeps
  flagging an uncovered path unresolved, `derive_planned` does not, since
  a plan's own forecast of scope is not the diff the real, later reviewer
  set must resolve), adding the pilot's one fixed `s3_reviewer_role` slot
  on top of whatever CODEOWNERS or the sensitive-path map contribute. A
  repository with no CODEOWNERS file at all no longer raises: an empty
  rule set stands in, so the sensitive-path mapping (which owes nothing
  to CODEOWNERS) is still consulted. `derive_actual`'s own signature and
  behaviour are unchanged.
- `runner/stages/S3.py` -- `_reviewer_set_json` becomes
  `_planned_reviewer_set`, deriving from the plan's own `Scope and
  discretion` table (`_scope_paths`: `touch`/`create`/`delete` rows only,
  a `discretion` glob contributes nothing) instead of a single hard-coded
  slot. A sensitive derivation records `check_result` `exclusion` fail and
  applies the pilot exclusion before the plan is even structurally
  checked. Once the plan is registered, S3 opens one `plan_approval` queue
  item (`ref = artefact:<plan id>`, the planned reviewer set) carrying no
  subject of its own.
- `runner/queue.py` -- `plan_approval` gains the `verdict` action:
  `act` gains `line`/`key`/`verdict`/`evidence`/`waiver`/`rubric_paths`
  keywords, dispatching to `_act_verdict`. A `pass`/`blind_spot` verdict
  records and returns without resolving the item; a `fail` sends the
  ticket back to the failing line's own stage (`context`/`clarifying`/
  `planning` for S1/S2/S3) and resolves it. The checklist completing with
  no fail and no unwaived blind spot creates the plan tuple in the same
  transaction. `approve` on a `plan_approval` item refuses an incomplete
  checklist and re-derives currency as a race guard immediately before
  recording the decision, refusing (naming the changed fields) when a
  fresh subject had to be created; `_record_decision`/`_approval_context`
  read the subject from the ticket's current plan tuple, since the item
  itself carries none. `factory queue` lists the current subject and
  every expected instance's newest verdict (or `missing`).
- `runner/gates.py` -- `plan_review_gate` withholds while any question is
  open (not only a blocking one), refuses when `plan_tuple.derive_components`
  no longer matches the latest tuple, and evaluates real quorum
  (`approvals.evaluate`) over the plan tuple's own planned reviewer set,
  in place of the thin at-least-one-approval `_quorum` (removed, nothing
  else used it). The trusted `BEFORE_S4` fetch is unchanged.
- `runner/cli.py` -- `act` gains `--line`/`--key`/`--verdict`/`--evidence`
  (comma list)/`--waiver`.
- `runner/tests/test_s3_checklist.py`, `runner/tests/test_plan_tuple.py`
  (new); `factory/evals/rubrics/S3/fixtures/checklist/` and three new
  `factory/evals/rubrics/S3/eval.yaml` cases (`checklist_complete`,
  `checklist_missing_instance`, `checklist_duplicate`), appended after the
  file's existing two cases.
- `runner/tests/test_stub_walk.py`, `test_report.py`, `test_act.py`,
  `test_attention_bucket.py`, `test_freshness.py`, `test_state_table.py`
  (touched, not owned) -- every one of these built a `plan_approval`
  item, an evidence tuple, or `plan_review_gate`'s quorum from a bare
  hand-seeded row; the gate's now-real currency and quorum checks refuse
  those stand-ins outright, so each is rebuilt through the real checklist/
  plan-tuple path (or, where that is disproportionate to what the test
  actually pins, a real plan tuple built the same way and a matching
  approval).

## Rows covered

R-S3-20, R-S3-15 (`docs/prd/04-S3-spec-and-plan.md`); the `human_verdict`
and `evidence_tuple` entities (`docs/prd/02-2-entities.md`).

## Owner decisions this ticket follows

The plan_approval item carries no subject of its own; the subject is the
ticket's latest plan tuple, created when the checklist completes and
recreated when any bound field drifts. `head_sha` is not a plan
component, so an S4 hand-back alone never creates a new subject. Waivers
are seeded rows (`record.insert(conn, "waiver", ...)`); validating one
against a real policy is a later ticket's work. A verdict's
`reviewer_role` is the slot role the actor fills on the planned set;
`queue_item_id` is the item the verdict was recorded on. `human_verdict`
and `evidence_tuple` rows are immutable; a correction is a newer row.

## Decisions this brief did not already settle

- **`subject_item_key`'s exact string.** The brief states the `artefact`
  case exactly (`brief`/`criteria`/`plan`) but leaves `criterion`/
  `question`/`contract_unit` open. This ticket keys each instance by the
  item's own identifier as it already reads elsewhere in the record --
  the literal `AC-n`, the question's own integer id as a string, and the
  contracts-table `unit` cell -- rather than a namespaced form (some
  pre-existing illustrative `human_verdict.yaml` fixtures from an earlier
  ticket use a namespaced form, but nothing enforces it and this ticket's
  own machinery is the first to actually read the field).
- **`record_verdict`'s `waiver_id` parameter is validated for existence
  only, never linked.** A waiver names the verdict it waives
  (`waived_human_verdict_id`) after the verdict row already exists and
  its id is known, so the two writes can never happen in one call; this
  ticket's own scope explicitly excludes validating a waiver against
  policy content, so the parameter's only job here is to catch an
  obviously wrong id.
- **`derive_planned`'s shared body with `derive_actual`.** The brief asks
  for "the same derivation ... with a kind argument." A single
  parameterised function would need a fork for the pilot slot, the
  LookupError fallback, and the unmatched-path treatment; this ticket
  instead factors the one truly shared piece (`_match_paths`, now
  `flag_unmatched`-parameterised) and keeps two small top-level functions,
  which keeps `derive_actual`'s existing tests untouched by construction
  rather than by care.
- **An uncovered planned-scope path does not block.** Discovered while
  fixing the "no CODEOWNERS" fallback: making it flag every uncovered
  path unresolved (mirroring `derive_actual` exactly) would put an
  unresolvable slot on every ticket whose plan touches a path no
  CODEOWNERS rule or sensitive-path glob names, since Initial's pilot
  repository has no CODEOWNERS file at all -- forever blocking quorum.
  Since the real, later actual/effective reviewer set is what must
  resolve every touched path before `checks_gate` admits to review, the
  planned derivation only needs to add slots CODEOWNERS or the
  sensitive-path map actually name.
- **The sensitive-path exclusion check in S3 runs before the structural
  check and size gate**, not after: a ticket whose scope needs a
  sensitive-owner slot should never spend a fix round on structural
  content it will never keep.
- **Test-only `rubric_paths` threading through `queue.act`/`_act_verdict`.**
  `factory/rubrics/S3.md` is still a stub while a parallel ticket builds
  its real table, so no real S3-stage checklist line exists yet; `act`
  gained an optional `rubric_paths` keyword (defaulting to
  `checklist.DEFAULT_RUBRIC_PATHS`) so a test can substitute a small
  S3-stage rubric file and exercise the real `queue.act` verdict path
  instead of duplicating its logic.

## Out of scope

The real S4 execution that consumes the approved plan tuple; validating
a named waiver against a real waiver policy's content.
