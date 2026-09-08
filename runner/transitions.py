"""Enforcement for `state_table.TABLE`: the one place `ticket.state` changes.

`apply` is the sole writer of `ticket.state`. It never decides which event
fires -- a gate function in `gates.py`, a stage's pass event applied by
`runner.stages.run_stage`, or a caller recording a human decision (abandon,
refresh_base, a send-back, request-changes, a merge, an escalation
resolution) all name the event explicitly and let this function look it up.
A missing `(state, event)` row is refused rather than silently ignored, so
a caller that guesses wrong about what is legal learns immediately instead
of leaving the ticket in a state nothing else expects.
"""
import sqlite3

from runner import record
from runner.state_table import CLOSE_REASON, TABLE, TERMINAL_STATES


class TransitionRefused(Exception):
    """No row in `state_table.TABLE` permits this event from the ticket's current state."""


def apply(conn: sqlite3.Connection, ticket_id: int, event: str) -> str:
    """Move `ticket_id` by `event`, returning the state it lands in.

    Raises `LookupError` for an unknown ticket and `TransitionRefused` when
    the ticket's current state has no row for `event`; a terminal state
    therefore refuses every event, since `TABLE` carries no row keyed by
    any of them. Entry to a terminal state stamps `closed_at` and the
    event's `close_reason`.
    """
    ticket = record.get(conn, "ticket", ticket_id)
    if ticket is None:
        raise LookupError(f"no such ticket: {ticket_id}")
    current_state = ticket["state"]
    to_state = TABLE.get((current_state, event))
    if to_state is None:
        raise TransitionRefused(
            f"ticket {ticket_id}: no transition for event {event!r} from state {current_state!r}"
        )
    fields = {"state": to_state}
    if to_state in TERMINAL_STATES:
        fields["closed_at"] = record.now()
        fields["close_reason"] = CLOSE_REASON[event]
    record.update(conn, "ticket", ticket_id, **fields)
    return to_state
