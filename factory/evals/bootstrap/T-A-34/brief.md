# T-A-34 brief: publication target, review-approval subject, approval wording, request-changes routing, self-containedness

## What this delivers

One canonical publication-target hash and one review-approval subject
hash, both computed through `runner/canonical.py`, wired everywhere a
final-review decision, a pull-request intent, or the post-dispatch gate
reads "the subject a reviewer approved." The verbatim final-review
attestation line. `factory act --self-contained yes|no`, mandatory on the
decisions R-H-8 covers, and the `packet_defect` tag a false answer writes
bound to the exact row it was about.

## Design decisions

**`runner/publication.py` is the one home of both hashes.** `Target`
folds operation kind, repository, target/head refs, current PR identity,
desired head, and expected prior remote head. `Subject` folds the review
tuple's content hash, the review tuple's own bound blocking check-result
hashes in id order, the content hashes of currently valid waivers bound
to that review tuple (sorted), the packet and `pr_body` artefact hashes,
the effective reviewer-set hash, and the publication-target hash.
`review_approval_subject` refuses with a named exception
(`PublicationSubjectIncomplete`) when any component -- a review tuple, a
bound blocking check result, a packet, a `pr_body` artefact, or an
effective reviewer-set hash -- is not yet on record, checked
independently rather than short-circuited.

**`publication.quorum` layers the authority check `approvals.evaluate`
never made.** `approvals.evaluate` gained an `excluded_ids` parameter so
`quorum` can drop a row before counting rather than reimplementing the
counting logic. A counted `approval_record` whose `authority_policy_hash`
no longer matches the current `owners.yaml`, or whose actor no longer
holds the slot's role (or is no longer its named owner), is dropped and
reported as `unauthorised:<slot>:<actor>`.

**Wiring the subject touched more than S6's own opening call.**
`queue._record_decision` recomputes the subject fresh for every gate
`review` decision and refuses on drift (the same shape as the plan gate's
own race guard), filling `evidence_tuple_id`, `evidence_tuple_hash`,
`reviewer_set_hash`, `publication_target_hash`, and the attestation
fields in the same call. `outbox.intent_for_review_quorum` now evaluates
`publication.quorum` and rechecks every waiver bound into the ticket's
plan or review tuple before creating an intent; an invalid one withholds
the intent the same way unmet quorum does.

**Two files outside this ticket's ownership list needed a forced,
minimal fix, in their own commit.** `gates.py`'s `review_gate` used to
evaluate quorum against the bare review-tuple content hash; once
`approval_record` rows are written against the real publication subject
instead, that comparison would never match, so `_review_quorum_satisfied`
now reads the exact subject hash the reconciled `external_write` row
itself carries rather than recomputing a live one (recomputing live is
wrong here for an orthogonal reason: a reconciled `pr_create` updates
`ticket.last_remote_head_sha`, which is itself one of the publication
target's own fields, so a live recompute would always find yesterday's
successful dispatch "stale"). `freshness.py`'s `BEFORE_DISPATCH` boundary
compared a pending intent's subject hash against the bare review-tuple
hash for the same reason and needed the same fix, now comparing against a
freshly recomputed `publication.review_approval_subject`.

**Self-containedness has no dedicated column for an escalation.**
Section 5's rule distinguishes three surfaces: a plan or review decision
records the answer on `approval_record.decision_supported_without_transcript`;
a question records it on the new `answer.supported_without_transcript`
column; an escalation's decision has neither, so a `no` is the only trace
it leaves, as a `packet_defect` tag bound to the exact `failure_history`
artefact the escalation's stage run registered. An escalation with no
such artefact (any cause but verification exhaustion) refuses a `no`
answer outright rather than binding the tag to nothing real.

**`--self-contained` is mandatory only where R-H-8 says it is.**
`approve`, `request_changes`, `answer`, and `accept_default` require it
regardless of item kind; `resume`, `send_back`, and `abandon` require it
only on an `escalation` item -- the same three actions on a `red_check`,
`manual_pause`, or `plan_approval` item stay exactly as they were.

**The final-review attestation is stamped on every gate-`review`
decision, approve and reject alike**, not only on approve: `request_changes`
is still a final-review decision under the same subject, and C11 draws no
line between the two for what the record must carry.

## Known simplifications

`gates.checks_gate` and `S6.run()` already refuse a red blocking tier
entry to `review` (S6 fails its `s5_not_cleared` check, so `checks_gate`
never sees a passed S6 run); this ticket adds no new code there, only the
test that pins the behaviour.
