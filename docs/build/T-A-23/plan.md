# T-A-23 plan

## Steps

| # | Step | Files touched | Proves |
|---|---|---|---|
| 1 | `question_gate.validate`: reasoning/affects required, option shape and count, default-option requiredness over the four flag combinations, per-option consequence with the default's unanswered marker, the keyword-forced consequential/hard-to-reverse rule, the identifier ban with `allowed_names`. | `runner/checks/question_gate.py` | criteria 1, 5, 6, 7, 8, 9, 16, 17 |
| 2 | `questions.rank`/`raise_round`: validates every candidate before writing any row, computes and stores `rank`/`rank_inputs` regardless of a default, refuses a new round while the previous round's blocking question is open, stores the sensitive flag as `consequential = 1` with a prefixed reason, validates `raised_by_answer` against a real answer of the ticket. | `runner/questions.py` | criteria 3, 4, 5 (storage), 7, 8, 9, 11, 12 |
| 3 | `questions.record_answer`/`accept_assumption`/`supersede_assumption`/`assumption_log_hash`/`dependents_invalidated`: the two writers onto the assumption log, append-only supersession and withdrawal, the log's canonical hash, and the stale-dependent comparison over artefact front matter and `evidence_tuple`/`approval_record` rows. | `runner/questions.py` | criteria 13, 14, 15 |
| 4 | `questions.correct_flag`: the mutable-flag correction plus its `flag_correction` tag. | `runner/questions.py` | criterion 10 |
| 5 | `queue.py`'s `_answer` body moves into `questions.record_answer`, called from `_answer` through a deferred import (breaks the `questions` <-> `queue` import cycle, `queue.open_item` needing `questions` and vice versa). | `runner/queue.py` | criterion 13, the S2 walk |
| 6 | `S2.py` rewritten: invoke the real agent, read `out/questions.yaml`, gate through `raise_round`, register the round as a `question_set` artefact, decide `blocked`/`fail`/`pass`. | `runner/stages/S2.py` | criterion 19, and every gate criterion exercised through the real driver |
| 7 | `factory/rubrics/S2.md`: real front matter and table, R-S2-5/R-S2-14 script and grader lines, R-S2-6/7/8/9/11 script lines. | `factory/rubrics/S2.md` | criteria 2, 18 |
| 8 | Fixture round and rejected-candidate cases under `factory/evals/agents/S2/fixtures/`, referenced from `eval.yaml` with `expect` values outside the generic `ok`/`reject` pair. | `factory/evals/agents/S2/eval.yaml`, `.../fixtures/question_round/out/questions.yaml`, `.../fixtures/gate_rejected/out/questions.yaml` | criterion 19, the driver's fail path |
| 9 | Seeded `human_verdict` documents for the two grader lines, `owner:` added to the eval spec. | `factory/evals/rubrics/S2/eval.yaml`, `.../fixtures/r_s2_5_grader_pass/human_verdict.yaml`, `.../r_s2_5_grader_fail/human_verdict.yaml`, `.../r_s2_14_grader_pass/human_verdict.yaml`, `.../r_s2_14_grader_fail/human_verdict.yaml` | criteria 2, 18 (documentation) |
| 10 | Manifest hashes refreshed for every changed file, entries added for every new one. | `factory/manifest.yaml` | `test_manifest_hash.py`, every `stages.invoke_agent` call in the new tests |
| 11 | `runner/tests/test_s2_questions.py`: every criterion below. | `runner/tests/test_s2_questions.py` | criteria 1-19 |
| 12 | Two collateral fixes: a now-obsolete stub test dropped, a real manifest pin substituted for a placeholder in the completed-walk fixture. | `runner/tests/test_stub_stages.py`, `runner/tests/test_report.py` | full-suite green |
| 13 | This ticket's own brief and plan. | `docs/build/T-A-23/brief.md`, `docs/build/T-A-23/plan.md` | reviewed by the human, not a test |

## Test strategy

Most of `test_s2_questions.py` calls `question_gate.validate` and the
`questions` module's functions directly against an in-memory database and
a baseline valid candidate (`_candidate()`), overriding only the one
field each test's own rule is about -- isolating the pure gate logic from
the driver and the queue. Criterion 5's four flag combinations are one
parametrized test asserting only the `default_option`-shaped violations,
so an incidental change elsewhere in `validate` cannot mask or fake a
pass. Criteria 7, 8, and 9 each run a real `raise_round` and check the
stored flag, plus one `must_reject_` test per keyword rule asserting the
gate refuses the mismatched candidate outright. Criterion 15 seeds a real
artefact file with `assumption_log_hash` in its front matter, plus an
`evidence_tuple` and an `approval_record` referencing it, then supersedes
an assumption and asserts both that the log hash changed and that
`dependents_invalidated` lists all three as stale by id.

Criterion 19 is the one end-to-end test: it drives `run_stage` through
the real S2 driver with `FIXTURE_ADAPTER_OUT_DIR` pointed at the
committed two-question fixture, asserts `blocked` and two open queue
items, resolves the blocking one with `queue.act(..., "answer")` and the
other with `queue.act(..., "accept_default")`, asserts the assumption row
and that `ticket.blocked_on` clears, then reruns `run_stage` with no
fixture output (the agent found nothing left to ask) and asserts `pass`
and the `clarifying -> planning` transition. A second end-to-end test
drives the same driver against the malformed-candidate fixture and
asserts the `fail` outcome, the recorded `question_gate` `check_result`,
and that no `question` row was written for the rejected round. Both
share the real committed `factory/manifest.yaml`, which is why every
`factory/` change in this ticket is committed before these two tests
run.

## Verification

`uv run pytest -q`
