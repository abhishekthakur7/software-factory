"""The ticket-state table: every transition a ticket can take, as data.

This table -- and `anti_goals.py` beside it -- must stay outside `factory/`
and outside `factory/manifest.yaml`, so no proposal path can ever reach the
gates it enforces. This module holds data only; the enforcement that reads
`TABLE` to gate a move lives in `transitions.py` beside it, and the gate
functions that derive an event from already-recorded rows live in
`gates.py`.

`TABLE` is keyed by `(from_state, event)` and names the one `to_state` that
event reaches. A plain stage pass (`s1_pass` .. `s4_pass`) is applied by
`runner.stages.run_stage`; every other event -- a gate's derived event or a
human decision (`abandon`, `refresh_base`, `send_back_to_*`,
`request_changes`, `merge_recorded`, `revision_to_*`, `escalation_*`,
`migrate_manifest`) -- is applied by whoever decides it, through
`transitions.apply`.

A stale base by itself never moves a ticket: the state table says a
mismatch starts no work and permits only the human's `refresh_base`,
send-back, or abandon. So `plan_review`, `implementing` and `checks` carry
no automatic "stale" event, only the human-recorded rows, and a gate's
freshness check withholds its advancing event instead of redirecting. The
pre-dispatch mismatch in `review` is the one redirect the state table
describes as automatic, so it has its own events. Where the same sentence
governs several states (stale base; redirect with a `send_back` tag), each
state gets its own rows, one per site the policy governs.
"""

STATES = (
    "intake",
    "rejected",
    "context",
    "clarifying",
    "planning",
    "plan_review",
    "implementing",
    "checks",
    "review",
    "pr_opened",
    "pr_checks",
    "merged",
    "abandoned",
    "escalated",
)

# The state each stage runs from. S5 and S6 both run from `checks`: neither
# leaves it on its own pass (see the module docstring); `checks_gate`
# leaves checks only once both have passed.
STAGE_STATE: dict[str, str] = {
    "S0": "intake",
    "S1": "context",
    "S2": "clarifying",
    "S3": "planning",
    "S4": "implementing",
    "S5": "checks",
    "S6": "checks",
}

# The terminal states accept no further transition: `TABLE` carries no row
# keyed by any of them, and `transitions.apply` refuses whatever event is
# asked of them for that reason alone. `pr_checks` is kept in STATES as the
# later pull-request polling state after `pr_opened`; it carries no row
# either, but because nothing in this version reaches or leaves it yet.
TERMINAL_STATES: frozenset[str] = frozenset({"rejected", "merged", "abandoned"})

# Every state `abandon` can fire from: every open state, `pr_opened` where
# the human records a close without merge, and `escalated`, whose every
# resolution path may abandon.
_ABANDONABLE = (
    "intake",
    "context",
    "clarifying",
    "planning",
    "plan_review",
    "implementing",
    "checks",
    "review",
    "escalated",
    "pr_opened",
)

# Every state `factory migrate-manifest` reaches from: a human-approved
# manifest migration returns any open ticket to `context`.
_MIGRATABLE = (
    "intake",
    "context",
    "clarifying",
    "planning",
    "plan_review",
    "implementing",
    "checks",
    "review",
    "pr_opened",
    "escalated",
)

# The event-keyed transition table: `(from_state, event) -> to_state`.
# Ticket creation (a new ticket starts in `intake`) and the script-only
# `validation_only` run of S4 (recorded with no state change) are not
# transitions and so have no row here.
TABLE: dict[tuple[str, str], str] = {
    # intake
    ("intake", "eligibility_granted"): "context",
    ("intake", "s0_reject"): "rejected",
    ("intake", "s0_exclusion"): "rejected",
    ("intake", "eligibility_declined"): "rejected",
    # context
    ("context", "s1_pass"): "clarifying",
    ("context", "s1_exclusion"): "rejected",
    # clarifying
    ("clarifying", "s2_pass"): "planning",
    # planning
    ("planning", "s3_pass"): "plan_review",
    ("planning", "s3_exclusion"): "rejected",
    # plan_review
    ("plan_review", "plan_quorum_fresh"): "implementing",
    ("plan_review", "refresh_base"): "context",
    ("plan_review", "send_back_to_context"): "context",
    ("plan_review", "send_back_to_planning"): "planning",
    ("plan_review", "send_back_to_clarifying"): "clarifying",
    # implementing
    ("implementing", "s4_pass"): "checks",
    ("implementing", "refresh_base"): "context",
    ("implementing", "send_back_to_context"): "context",
    ("implementing", "send_back_to_planning"): "planning",
    ("implementing", "send_back_to_clarifying"): "clarifying",
    # checks
    ("checks", "checks_bad_handback"): "implementing",
    ("checks", "checks_removal_return"): "implementing",
    ("checks", "checks_fix_round"): "implementing",
    ("checks", "refresh_base"): "context",
    ("checks", "send_back_to_context"): "context",
    ("checks", "checks_new_reviewer_slot"): "planning",
    ("checks", "send_back_to_planning"): "planning",
    ("checks", "send_back_to_clarifying"): "clarifying",
    ("checks", "checks_sensitive_path_required"): "rejected",
    ("checks", "checks_pass_to_review"): "review",
    # review
    ("review", "review_quorum_reconciled"): "pr_opened",
    ("review", "review_predispatch_mismatch_to_checks"): "checks",
    ("review", "review_predispatch_mismatch_to_context"): "context",
    ("review", "review_predispatch_mismatch_to_planning"): "planning",
    ("review", "send_back_to_context"): "context",
    ("review", "send_back_to_planning"): "planning",
    ("review", "send_back_to_clarifying"): "clarifying",
    ("review", "request_changes"): "implementing",
    # pr_opened
    ("pr_opened", "merge_recorded"): "merged",
    ("pr_opened", "revision_to_context"): "context",
    ("pr_opened", "revision_to_clarifying"): "clarifying",
    ("pr_opened", "revision_to_implementing"): "implementing",
    ("pr_opened", "revision_to_planning"): "planning",
    # escalated
    ("escalated", "escalation_verification_resolved_to_planning"): "planning",
    ("escalated", "escalation_verification_resolved_to_clarifying"): "clarifying",
    ("escalated", "escalation_verification_resolved_to_context"): "context",
    ("escalated", "escalation_control_defect_remediated"): "context",
    ("escalated", "escalation_resume_implementing"): "implementing",
    ("escalated", "escalation_resume_checks"): "checks",
    ("escalated", "escalation_resume_review"): "review",
    # escalate: the single second-failure, exhaustion, violation or stop
    # event. The specific cause (verification exhaustion, budget abort,
    # sandbox violation, an unresolved refresh_base conflict, ...) is
    # recorded on the stage_run or check_result and its tag, not in the
    # transition event: the state machine only cares that the ticket is
    # now escalated. `plan_review` carries this event because a human's
    # refresh_base may be called from there (see `("plan_review",
    # "refresh_base")` above) and its own conflict path escalates the
    # same way every other refresh_base call site does.
    **{(state, "escalate"): "escalated" for state in
       ("context", "clarifying", "planning", "plan_review", "implementing", "checks", "review")},
    # abandon
    **{(state, "abandon"): "abandoned" for state in _ABANDONABLE},
    # migrate_manifest, expressed as data rather than a special case:
    # valid from every open state.
    **{(state, "migrate_manifest"): "context" for state in _MIGRATABLE},
}

# The close_reason stamped when an event's row lands on a terminal state.
# Every event that reaches `rejected`, `merged` or `abandoned` must appear
# here; `transitions.apply` fails loudly on one that does not.
CLOSE_REASON: dict[str, str] = {
    "s0_reject": "rejected_at_s0",
    "s0_exclusion": "pilot_excluded",
    "eligibility_declined": "rejected_at_s0",
    "s1_exclusion": "pilot_excluded",
    "s3_exclusion": "pilot_excluded",
    "checks_sensitive_path_required": "pilot_excluded",
    "merge_recorded": "merged",
    "abandon": "abandoned",
}

