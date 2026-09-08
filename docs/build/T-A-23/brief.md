# T-A-23 brief: S2 question gate, format, ranking, flags, rounds, wording, assumption log

## What this delivers

S2 gains a real question and assumption half. The stub S2 driver is
replaced by one that invokes the ticket's real (fixture, at A) agent,
reads the `questions.yaml` it wrote, runs every candidate through a pure
pre-queue gate, and either queues a whole validated round, fails the
attempt with a recorded `check_result` over a rejected round, or leaves
the ticket `blocked` on an open blocking question. `question`, `answer`,
and `assumption` rows now have exactly one write path, `runner/
questions.py`, shared by the driver and by `queue.act`'s `answer`/
`accept_default` actions. The criteria half of S2 (forced categories,
agreement check, restatement children, the S3-bound exit gate) is left
for the next ticket in the sequence; this driver's `run` stays short and
free of that concern so it can be extended around these same calls.

- `runner/checks/question_gate.py` (new) -- `validate(candidate, *,
  allowed_names=frozenset()) -> list[str]`, pure: required `reasoning`/
  `affects`, two-to-four options with a trailing "none of these",
  `default_option` required unless both flags (or a sensitive decision)
  hold, in which case it must be null, a one-sentence consequence per
  option with the default's naming what happens if nobody answers, the
  keyword-forced consequential/hard-to-reverse rule, and the identifier
  ban (requirement/principle/failure-mode/decision/stage ids, artefact-
  kind/script/table names, `allowed_names` excepted).
- `runner/questions.py` (new) -- `rank`, `raise_round` (validates a whole
  round before writing any of it, refuses a new round while the previous
  round's blocking question is still open), `record_answer` (the answer
  write path `queue.act` now calls, writing the `default_accepted`
  assumption row in the same call), `accept_assumption` (the S3-reviewer
  path), `supersede_assumption` (append-only; a withdrawal and a plain
  text replacement both carry their reason in the table's one
  reason-carrying column, `withdrawal_reason`), `correct_flag` (the
  mutable-flag correction, its reason landing as a `flag_correction` tag
  rather than overwriting the agent's own `_reason` column),
  `assumption_log_hash`, `dependents_invalidated`.
- `runner/stages/S2.py` (rewritten) -- the question half only: invoke,
  read `out/questions.yaml` (absent means no more questions), gate,
  register the artefact, decide `blocked`/`fail`/`pass`.
- `runner/queue.py` -- `_answer`'s body moves into
  `questions.record_answer`; nothing else in the module changes.
- `factory/rubrics/S2.md` -- real front matter and table: R-S2-5 and
  R-S2-14 each carry a script line and a bootstrap-checklist grader line
  with the row's own judgment sentence; R-S2-6/7/8/9/11 carry script
  lines. The criteria rubric lines land with the next ticket.
- `factory/evals/agents/S2/fixtures/question_round/`,
  `.../gate_rejected/` (new) -- a two-question round (one blocking, one
  not) and one malformed candidate, each under `out/questions.yaml` so
  the same fixture drives both a driver test and `FIXTURE_ADAPTER_OUT_DIR`;
  `factory/evals/agents/S2/eval.yaml` gains two cases naming them, with
  `expect` values (`blocked`, `fail`) outside the generic definition-
  conformance walk's `ok`/`reject` pair so that walk skips them by
  construction.
- `factory/evals/rubrics/S2/` -- `eval.yaml` gains an `owner:` field and
  four cases; `fixtures/r_s2_5_grader_pass/`, `.../r_s2_5_grader_fail/`,
  `.../r_s2_14_grader_pass/`, `.../r_s2_14_grader_fail/` each seed one
  `human_verdict` document until a calibrated grader records real ones.
- `factory/manifest.yaml` -- hashes refreshed for every changed file,
  entries added for every new one.
- `runner/tests/test_s2_questions.py` (new).

## Row covered

R-S2-5, R-S2-6, R-S2-7, R-S2-8, R-S2-9, R-S2-11, R-S2-14.

## Owner decisions this ticket follows

Every design decision the ticket brief names: the `questions.yaml`
candidate shape; `options` and `rank_inputs` stored as canonical JSON;
`rank = round(impact * tier_weight * uncertainty * 100)` with tier
weights `{light: 1, standard: 2, heavy: 3}` kept as a module constant in
`questions.py` (a placeholder the owner calibrates, not moved into
`tiers.yaml`); the sensitive flag stored as `consequential = 1` with
`consequential_reason` prefixed `sensitive decision:`; the classification
keyword lists as lax, owner-tuned module constants in
`question_gate.py`; `round = 1 + max round at this stage`, refused while
the previous round's blocking question is still open; follow-up
questions naming `raised_by_answer`, validated against a real `answer`
row of the same ticket; no `correct_flag` CLI verb added (criterion 10 is
proven by calling `questions.correct_flag` directly, since wiring it into
`queue.act`'s `_ACTIONS` table was explicitly out of this ticket's
`queue.py` edit); the criterion-19 walk shape (one round, one answer, one
default acceptance, a second empty-questions pass).

## Decisions this brief left open

- **`question.text` is not a database column.** The schema section this
  ticket may extend lists only the tables already in the record
  (`question`, `answer`, `assumption`, ...), and `question` carries no
  `text` field to begin with -- adding one is exactly the kind of new
  column the working rules ask a builder to avoid where an existing path
  already covers the need. The question's full wording lives in the
  `question_set` artefact the driver registers from `out/questions.yaml`;
  `question_gate.validate` still checks it (and each option's `text`) for
  banned identifiers before any row is written, so the ban is enforced on
  the full text even though the database only ever sees the governance
  fields.
- **What "invalidated" means in code (criterion 15).** There is no
  invalidation column anywhere in the schema, and none is added.
  `assumption_log_hash(conn, ticket_id)` is the canonical hash of the
  ticket's current assumption set (every row that is neither superseded
  by a later row nor itself a withdrawal). A downstream artefact records
  the hash it was built against in its own front matter
  (`assumption_log_hash`, written by the plan driver in a later ticket);
  an `evidence_tuple` records it in `current_assumption_set_hash`; an
  `approval_record` inherits it through the `evidence_tuple` it approved.
  `dependents_invalidated(conn, ticket_id)` does not flip anything: it
  compares each of those recorded hashes against the log's current value
  and lists every one that no longer matches. "Invalidated" is exactly
  that mismatch -- a consumer that never compares hashes gets no
  protection from this function alone, which is why every later
  consumer's own gate is expected to make that comparison itself, not
  trust a flag this ticket could plant instead.
- **`supersede_assumption`'s `reason` always lands in
  `withdrawal_reason`.** The `assumption` table carries exactly one
  reason-carrying column. A plain text replacement is not literally a
  withdrawal, but reusing that column for both kinds of supersession (the
  `withdrawn` flag tells them apart) is the only way to record the reason
  at all without adding a column the ticket's own rule discourages.
- **`correct_flag`'s reason is a `flag_correction` tag, not the
  question's own `_reason` column.** `consequential_reason` and
  `hard_to_reverse_reason` are not `mutable=True` in the schema -- only
  the two boolean flags are -- so a human correction cannot overwrite the
  agent's original reasoning even if it wanted to; the correction's own
  reason is recorded as a tag on `question:<id>` instead, which is
  already a valid tag target and already carries the `flag_correction`
  event kind.
- **The manifest-pin refusal path inside the S2 driver.**
  `stages.invoke_agent` can refuse an invocation before any child
  `stage_run` opens (a missing or stale `factory_manifest_hash` pin), and
  that refusal is recorded as a `utility_run`, not a value in
  `stage_run.OUTCOMES`. Since S2 always names a real agent, this can only
  happen through a governance failure outside this ticket's scope; the
  driver maps it to `("fail", "infrastructure")` -- a legal `stage_run`
  outcome -- rather than trying to pass the ineligible `"refused_request"`
  value through to `run_ledger.finish`, which the schema's `CHECK`
  constraint would reject outright. No test exercises this path since
  every test ticket carries a real pin; it exists only so the driver
  never crashes if one doesn't.
- **Collateral fixes to two pre-existing tests, each because the real S2
  driver refuses what the stub always passed.**
  `test_stub_stages.py::test_s2_stub_writes_criteria_and_passes_to_planning`
  is dropped outright (its ground -- a driver that writes a placeholder
  artefact and passes unconditionally -- no longer exists; the same
  transition is now covered by `test_s2_questions.py`'s own walk).
  `test_report.py`'s completed-walk fixture pinned its ticket to a
  placeholder manifest hash (`"m1"`); S2 now genuinely checks the pin
  before invoking its agent, so the walk now pins the ticket to the real,
  currently committed manifest hash instead. Neither change alters what
  either test file otherwise asserts.

## Out of scope

The criteria half of S2 (forced categories, agreement check, restatement
children, size estimate, completeness verdict, the S3-bound exit gate)
and its own rubric lines; the grader-verdict recording for the R-S2-5 and
R-S2-14 bootstrap-checklist lines through the real checklist walker; a
`correct_flag` CLI verb; the plan driver that will actually write
`assumption_log_hash` into a plan artefact's front matter, and the
evidence-tuple binding that will actually populate
`current_assumption_set_hash` -- `dependents_invalidated`'s test seeds
both by hand to prove the comparison itself.
