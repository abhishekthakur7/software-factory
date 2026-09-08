# T-A-34 plan

## Steps

| # | Step | Files touched | Proves |
|---|---|---|---|
| 1 | `publication_target`/`Target`: operation, repository, refs, PR identity, desired/prior heads, hashed. | `runner/publication.py` | criterion 1 |
| 2 | `review_approval_subject`/`Subject`: review tuple, ordered bound blocking check-result hashes, valid review-tuple waiver hashes, packet/`pr_body` hashes, effective reviewer-set hash, publication-target hash; refuses on a missing component. | `runner/publication.py` | criteria 2, 3, 4 |
| 3 | `evaluate` gains `excluded_ids`; `publication.quorum` applies the authority check (drop a row whose policy hash or actor-role no longer holds) on top of `approvals.evaluate`. | `runner/approvals.py`, `runner/publication.py` | criteria 5, 6, 7, 8 |
| 4 | `FINAL_REVIEW_ATTESTATION`/`_VERSION`. | `runner/approvals.py` | criterion 10 |
| 5 | S6 opens `packet_approval` with `approval_subject_hash = review_approval_subject(...).hash`. | `runner/stages/S6.py` | criteria 2, 9 |
| 6 | `queue._record_decision`: for gate `review`, recompute the subject and refuse on drift, fill `evidence_tuple_id/hash`, `reviewer_set_hash`, `publication_target_hash`, the attestation fields, `decision_supported_without_transcript`; `_approval_context` shows the publication target to a `packet_approval` reviewer. | `runner/queue.py` | criteria 10, 15 |
| 7 | `outbox.create_intent` takes an explicit `publication_target_hash`; `intent_for_review_quorum` rewritten over `publication.quorum`/`publication_target`, rechecking waivers first. | `runner/outbox.py` | criterion 9 |
| 8 | `factory act --self-contained yes|no`: mandatory on `approve`/`request_changes`/`answer`/`accept_default` always, and on an `escalation` item's `resume`/`send_back`/`abandon`; a `no` writes a `packet_defect` tag bound to the approval record, question, or `failure_history` artefact. | `runner/queue.py`, `runner/cli.py` | criteria 14, 15, 16 |
| 9 | `answer.supported_without_transcript`; `questions.record_answer` takes and stores it; `USER_VERSION` bumped. | `runner/schema.py`, `runner/db.py`, `runner/questions.py` | criterion 15 |
| 10 | `S4._failure_history_payload` carries `self_containedness`; `_loop_note` verified already reading the latest `revision_after_approval` note (no change needed). | `runner/stages/S4.py` | criteria 12, 17 |
| 11 | Forced fixes outside this ticket's file list, in their own commit: `gates._review_quorum_satisfied` reads the reconciled intent's own subject hash; `freshness.py`'s `BEFORE_DISPATCH` check compares against the live publication subject. | `runner/gates.py`, `runner/freshness.py` | keeps `test_outbox.py`/`test_state_table.py` correct under the new subject |
| 12 | `test_s6_publication_subjects.py`: both hash functions, refusal on a missing component, sensitivity to a changed check result or destination, quorum's count/separation/authority/expiry refusals. | `runner/tests/test_s6_publication_subjects.py`, `runner/tests/fixtures/s6_publication/` | criteria 1-8 |
| 13 | `test_s6_dispatch.py`: full quorum drives one `pr_create` with a receipt; a revision on a ticket already carrying a PR identity drives one `pr_update` with a receipt. | `runner/tests/test_s6_dispatch.py` | criterion 9 |
| 14 | `test_s6_approval_wording.py`: the verbatim attestation on every gate-`review` record, request-changes routing and its tag, the note carried into the next hand-off, the red tier barred from `review`. | `runner/tests/test_s6_approval_wording.py` | criteria 10-13 |
| 15 | `test_s6_self_containedness.py`: the engineer's answer on both surfaces, the mandatory flag, the bound `packet_defect` on each of a decision/question/escalation, the resolution chain, the `failure_history` rule text. | `runner/tests/test_s6_self_containedness.py` | criteria 14-17 |
| 16 | Existing seeds adjusted for the new subject and the mandatory flag: `test_outbox.py`, `test_stub_walk.py`, `test_freshness.py`, `test_state_table.py`'s fixture, `test_act.py`, `test_attention_bucket.py`, `test_plan_tuple.py`, `test_report.py`, `test_s2_questions.py`, `test_s4_escalation.py`, `test_stage_interface.py`. | (listed) | full-suite green |
| 17 | This plan and its brief. | `docs/build/T-A-34/brief.md`, `docs/build/T-A-34/plan.md` | reviewed by the human, not a test |

## Test strategy

`test_s6_publication_subjects.py` owns criteria 1-8 with a shared seeding
module (`seed_ticket`, `seed_review_tuple`, `approve`) the other three
files import, mirroring `test_act.py`'s reuse of `test_s5_waivers.py`.
Every quorum-refusal test isolates one failure mode at a time: fewer
records than a slot's minimum, two `distinct_from`-linked slots satisfied
by the one real pilot identity that holds both roles, an approval from an
identity the current `owners.yaml` no longer names for the slot, and two
required slots whose approvals both expire before two fresh ones (against
the same subject) satisfy them. `test_s6_dispatch.py` drives the real
`intent_for_review_quorum` → `reconcile_pending` path over a real git
clone and the stub deliverer, proving a receipt lands for both a
`pr_create` and a revision's `pr_update`. `test_s6_approval_wording.py`
pins the attestation text and version, proves `request_changes` both
tags the ticket and reaches the next real `S4.build_handoff`'s
`loop_note`, and proves the red-tier bar through `gates.checks_gate`
directly (no new production code backs it; the test exists so a
regression there is caught). `test_s6_self_containedness.py` covers the
mandatory flag, the exact-target binding on all three surfaces including a
must-reject for a missing `failure_history` artefact, and the resolution
chain leaving the original row untouched.

## Known simplifications

Two tests in `runner/tests/test_s6_publication_subjects.py`
(`test_distinct_from_slots_...` and `...expired_approvals...`) rely on
the pilot's single real identity holding every role in the committed
`owners.yaml`, since that is the only identity the authority check
accepts; a multi-person authority policy is out of this ticket's scope.
