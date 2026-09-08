"""The ticket-state fence of R-F-11 (PRD 2.3): who a state may be entered from.

This table -- and `anti_goals.py` beside it -- must stay outside `factory/`
and outside `factory/manifest.yaml`, so no proposal path (R-F-10, Later) can
ever reach the gates it enforces. This module holds data only; T-A-04 adds
the functions that read `TRANSITIONS` to actually gate a move.
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

# Read off the "Entered from" column of PRD 2.3, literally. A named state in
# that column (e.g. `plan_review`, `checks`) is transcribed as-is; a stage
# name (S0-S7) is resolved to the state that runs it (S0=intake, S1=context,
# S2=clarifying, S3=planning, S4=implementing, S5=checks, S6=review,
# S7=pr_checks); "any later state" is every state after this one in table
# order that is not itself terminal. Two routes the "Entered from" column
# omits but the "Leaves when" column states are included: `review` routes a
# pre-dispatch mismatch to `checks`, and any non-S4 stage whose single fresh
# rerun also fails moves to `escalated` ("Failed and blocked runs").
TRANSITIONS: dict[str, frozenset[str]] = {
    "intake": frozenset(),  # the entry state; no predecessor
    "rejected": frozenset({"intake", "context", "planning", "checks"}),
    "context": frozenset(
        {
            "intake",
            "clarifying",
            "planning",
            "plan_review",
            "implementing",
            "checks",
            "review",
            "pr_opened",
            "pr_checks",
            "escalated",
        }
    ),
    "clarifying": frozenset(
        {
            "context",
            "planning",
            "plan_review",
            "implementing",
            "checks",
            "review",
            "pr_opened",
            "pr_checks",
            "escalated",
        }
    ),
    "planning": frozenset({"clarifying", "plan_review", "checks", "review", "escalated"}),
    "plan_review": frozenset({"planning"}),
    "implementing": frozenset(
        {"plan_review", "review", "checks", "pr_checks", "escalated"}
    ),
    "checks": frozenset({"implementing", "review"}),
    "review": frozenset({"checks"}),
    "pr_opened": frozenset({"review"}),
    "pr_checks": frozenset({"pr_opened"}),
    "merged": frozenset({"pr_opened", "pr_checks"}),
    "abandoned": frozenset(
        {
            "intake",
            "context",
            "clarifying",
            "planning",
            "plan_review",
            "implementing",
            "checks",
            "review",
            "pr_opened",
            "pr_checks",
            "escalated",
        }
    ),
    "escalated": frozenset(
        {"context", "clarifying", "planning", "implementing", "checks", "review"}
    ),
}
