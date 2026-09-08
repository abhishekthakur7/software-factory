# T-A-24 brief: S2 criteria half -- restatement, agreement check, forced
categories, split rule, exit gate

## What this delivers

`runner/stages/S2.py`'s `run` grows a criteria half around the existing
question half, sharing the one agent invocation that now writes both
`out/questions.yaml` and `out/criteria.md`. After the invocation:

1. **`AC-n` id continuity.** The freshly parsed `Acceptance criteria`
   table is checked against the ticket's previous criteria version (if
   any): an id already used must still name the same source text, a
   source already restated must keep its id, and every genuinely new id
   must be strictly greater than the prior version's highest. Any
   violation fails the attempt structurally before anything downstream
   runs.
2. **Forced-category pre-fill.** `migration` and `permissions` are the
   two categories the pilot's own eligibility matrix already excludes for
   any ticket that ever reaches S2 at all; when the ticket's `S0` `stage_run`
   carries an `exclusion` `check_result` naming either, that category's
   resolution and reference are overwritten by the runner and never left
   to the agent, however the agent itself resolved it.
3. **The agreement check.** For every criterion the agent marked
   `formalised` or `provisional` (never `unformalisable`), the driver
   writes `N` (`agreement_check.n`, config) subject files under the
   attempt's own run directory, registers each as a `restatement_subject`
   artefact, and invokes the agent `N` more times as sibling child
   `stage_run`s on the manifest's restatement model, each reading the
   ticket source, the brief, and its one subject file. Every restatement
   child writes a one-row `precondition | trigger | system | response`
   table to `out/restatement.md`; the driver compares the three fields
   the PRD names (precondition, trigger, response) across the `N`
   results. Disagreement, or a `contradicts AC-m` note the agent already
   left in its own `Agreement check` table, downgrades a `formalised` row
   to `provisional` and raises a non-blocking question; an `uncovered:
   <region>` note with no matching criterion id raises one too. The
   `Agreement check` table itself is entirely rewritten by the runner
   from what it measured, the same way S1 fills the brief's `Final tier`
   section -- the agent's own guess is a hint, not the record.
4. **The split rule.** When the `Size estimate` table's `estimated_lines`
   exceeds `split_threshold.share_of_size_gate` of the tier's
   `size_gate`, or `estimated_files` exceeds `split_threshold.max_files`,
   the agent's own `questions.yaml` must already carry a consequential
   candidate naming one of the six split patterns; if it does not, the
   attempt fails structurally. The driver never invents a split
   candidate on the agent's behalf -- proposing *which* split makes
   sense is inherently the agent's judgement call.
5. **Candidates, combined and raised once.** The agent's own
   `questions.yaml` candidates are combined with every candidate the
   driver derived on its own -- one per `unformalisable` criterion, one
   per ambiguous/contradicted/uncovered agreement-check finding, one per
   forced category left `open` -- and raised through the existing
   `questions.raise_round` as a single round, exactly as the question
   half already did.
6. **The exit gate.** An `unformalisable` criterion's question and an
   `open` category's question are always raised `blocking = true`; every
   other driver-derived candidate is non-blocking. This one property is
   the whole exit mechanism: `questions.open_blocking` non-empty is
   *exactly* the condition under which some criterion is still
   unformalised or some category is still unresolved, so the driver never
   needs a second, bespoke check for either -- `blocked` when it is
   non-empty, `pass` otherwise. Every criterion, category, and question
   not depending on an open blocking question is still fully computed and
   written before a `blocked` exit, since nothing in this design defers
   any of that work to a later round.

## Design decisions this brief made that the ticket left open

- **`AC-n` id continuity lives in the driver, not the structure check.**
  `runner.checks.artefact_structure` gained a `_check_criteria` step for
  the EARS-form, example-concreteness, forced-category-shape, and
  `AC-n`-id-*shape* rules -- everything decidable from one version's text
  alone. Continuity across versions needs the ticket's *previous*
  version, which only the driver already reads (via
  `artefact_registry.latest`), so it stays a driver-level check.
- **Example concreteness is a script rule, not only a grader one.** The
  ticket's own design notes make the placeholder-token list
  (`TODO`, `X`, `foo`, `bar`, `placeholder`, `<...>`) a deterministic,
  script-level check; the R-S2-2 grader (bootstrap-checklist) line covers
  the subtler placeholder-shaped prose a token list cannot catch (a
  generic "the customer" with no real name, say).
- **Blocking is the one exit mechanism.** Rather than tracking which
  question resolves which criterion or category, the driver makes
  exactly the two candidate kinds that must be resolved before a plan can
  be written (`unformalisable`, `open` category) always blocking, and
  every other kind non-blocking. `S2 exits to planning only when every
  criterion is formalised or answered and every category is resolved` is
  then true *by construction* of `questions.open_blocking`, not by a
  second computation the driver could get out of sync with the first.
- **Forced-category pre-fill is read defensively.** Nothing in `S0`
  writes an `exclusion` `check_result` on a *passing* run today (only a
  full-ticket rejection applies `s0_exclusion` directly, with no
  `check_result` of its own) -- a ticket that actually touched `migration`
  or `permissions` never reaches `clarifying` at all under the current
  `S0`. The read path is built and tested against a seeded
  `check_result` row so the mechanism is correct and ready the day a
  future `S0` change (or another caller) starts recording one; it is not
  exercised by any real walk through `S0` as it stands today.
- **Contradiction pairing is a substring match on `contradicts AC-m`,
  deduplicated by unordered pair.** The PRD says deterministic detection
  beyond the agent's own notes is not expected at this stage; the driver
  turns whatever the agent already wrote into exactly one question per
  pair, however many of the two criteria's notes mention it.
- **The restatement subject's instruction text lives in the subject file
  itself**, not in `factory/agents/S2.md`: a restatement child is given
  the same agent and skill as the main invocation (only the model
  differs), so the one thing that tells it to write `out/restatement.md`
  instead of `out/criteria.md` has to travel with that one input, not the
  shared agent file.
- **`questions.open_blocking(conn, ticket_id, stage=None)`** replaces
  the question half's private `_has_open_blocking_question`, and
  `gates.plan_review_gate` now withholds its event while it is non-empty
  -- the one minimal seam the ticket named as already decided.

## Deviations from the common brief

- `runner/tests/test_s2_questions.py`'s `_clarifying_ticket` now also
  registers a `ticket_source` and a `brief` artefact (the restatement
  children's fixed input set), and its second, quiet-round run now points
  at a new `criteria_clean` fixture instead of an empty environment,
  since a real criteria half always requires `out/criteria.md` even on a
  round that raises nothing new. Nothing else in that file changed; every
  existing assertion still holds.
- `factory/agents/S2.md` was not touched: the skill already names
  `rubrics/checklists/split-patterns.md`; only the missing reference to
  `rubrics/checklists/forced-categories.md` was added, to
  `factory/skills/S2.md`, exactly as the ticket anticipated.
