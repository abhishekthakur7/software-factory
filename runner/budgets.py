"""Budget enforcement: refuse a fresh invocation that would exceed its `tiers.yaml` allowance, abort one that already has.

`check_before_invocation` is the one pre-flight a caller runs immediately
after opening a stage run's own `stage_run` row and before doing any real
work: it sums the settled tokens and wall-clock seconds already recorded
against this invocation's family -- the run named by `parent_run_id`, if
any, plus every run recorded under it, direct or nested -- and compares
that total to the stage-and-tier budget `run_ledger.budget` names. `S4`
carries a second, cumulative check on top: every `S4` `stage_run` the
ticket has ever opened, family boundaries aside, against the per-ticket
budget `run_ledger.s4_per_ticket_budget` names, since that budget spans
the ticket's whole implementation effort rather than one invocation's
descendants. Wall clock itself is enforced live by the launcher's own
timeout; this function only re-checks what has already settled.

`abort` finishes an already-open `stage_run` `aborted_budget`, the same
way `control.stop` finishes one `aborted_human`: no new `stage_run` is
opened, `stage_run.attempt` and `verification_attempt` are left exactly as
they were, so nothing here ever consumes a verification slot. The
escalation record itself has nowhere else to live -- `queue_item.note` is
a one-time field a human can only set by resolving the item, and this is
the runner escalating on its own -- so the reasoning summary, registered
outputs, current binding, and failure history all land as one JSON object
on the aborted run's own `reasoning_summary`, the mutable free-text field
the `escalation` item's `ref` (`stage_run:<id>`) already points a reader
at.
"""
import json
import sqlite3

from runner import queue, record, run_ledger, transitions

# The run_kind values that represent an actual S4 execution attempt versus
# its script-only verification pass; RUN_KINDS' third member,
# validation_only, is deliberately not carried by any real agent
# invocation, so it stands for "a verification ran" on its own.
_S4_EXECUTION_KINDS = frozenset({"task", "fix_round"})
_S4_VERIFICATION_KIND = "validation_only"


def _descendant_ids(conn: sqlite3.Connection, root_id: int) -> list[int]:
    """`root_id` plus every `stage_run` recorded under it, at any depth, via `parent_run_id`."""
    ids = [root_id]
    frontier = [root_id]
    while frontier:
        parent_id = frontier.pop()
        children = [
            row["id"] for row in conn.execute(
                "SELECT id FROM stage_run WHERE parent_run_id = ?", (parent_id,)
            ).fetchall()
        ]
        ids.extend(children)
        frontier.extend(children)
    return ids


def _root_id(conn: sqlite3.Connection, run_id: int) -> int:
    """Walk `parent_run_id` up from `run_id` to its top-level ancestor."""
    row = record.get(conn, "stage_run", run_id)
    while row is not None and row["parent_run_id"] is not None:
        row = record.get(conn, "stage_run", row["parent_run_id"])
    return row["id"] if row is not None else run_id


def _usage_totals(conn: sqlite3.Connection, run_ids: list[int]) -> tuple[int, float]:
    """`(tokens_in + tokens_out, wall_clock_seconds)` settled so far, summed across `run_ids`."""
    if not run_ids:
        return 0, 0.0
    placeholders = ", ".join("?" for _ in run_ids)
    rows = conn.execute(
        f"SELECT tokens_in, tokens_out, wall_clock_seconds FROM stage_run WHERE id IN ({placeholders})",
        run_ids,
    ).fetchall()
    tokens = sum((row["tokens_in"] or 0) + (row["tokens_out"] or 0) for row in rows)
    seconds = sum(row["wall_clock_seconds"] or 0 for row in rows)
    return tokens, seconds


def _exceeds(tokens: int, seconds: float, budget: dict, *, label: str) -> str | None:
    """The refusal reason when `tokens`/`seconds` exceed `budget`'s named limits, else `None`.

    A `None` budget value (S5's wall-clock override, for instance) means
    that dimension carries no limit, matching `run_ledger.budget`'s own
    contract, so it is skipped rather than treated as zero.
    """
    if budget.get("tokens") is not None and tokens > budget["tokens"]:
        return f"{label} already used {tokens} tokens against a budget of {budget['tokens']}"
    if budget.get("wall_clock_seconds") is not None and seconds > budget["wall_clock_seconds"]:
        return f"{label} already used {seconds}s against a budget of {budget['wall_clock_seconds']}s"
    return None


def check_before_invocation(
    conn: sqlite3.Connection, ticket: sqlite3.Row, stage: str, tier: str, *, parent_run_id: int | None = None,
) -> str | None:
    """A refusal reason when starting a fresh invocation now would already exceed budget, else `None`.

    Checked at the start of every invocation -- "before every fresh S4
    execution starts", and equally before any other stage's next child --
    so a family already at or past its budget is caught before it does any
    more work, never mid-invocation.
    """
    family_ids = _descendant_ids(conn, _root_id(conn, parent_run_id)) if parent_run_id is not None else []
    tokens, seconds = _usage_totals(conn, family_ids)
    reason = _exceeds(tokens, seconds, run_ledger.budget(stage, tier), label=f"stage {stage} at tier {tier}")
    if reason is not None:
        return reason
    if stage == "S4":
        s4_ids = [
            row["id"] for row in conn.execute(
                "SELECT id FROM stage_run WHERE ticket_id = ? AND stage = 'S4'", (ticket["id"],)
            ).fetchall()
        ]
        s4_tokens, s4_seconds = _usage_totals(conn, s4_ids)
        reason = _exceeds(
            s4_tokens, s4_seconds, run_ledger.s4_per_ticket_budget(tier),
            label=f"ticket {ticket['id']}'s cumulative S4 usage",
        )
        if reason is not None:
            return reason
    return None


def _s4_progress(conn: sqlite3.Connection, ticket_id: int) -> dict:
    """`last_completed_task`, `execution_count`, and `verification_count` across this ticket's S4 history."""
    rows = conn.execute(
        "SELECT attempt, run_kind, outcome FROM stage_run WHERE ticket_id = ? AND stage = 'S4' ORDER BY id",
        (ticket_id,),
    ).fetchall()
    completed_tasks = [row["attempt"] for row in rows if row["run_kind"] in _S4_EXECUTION_KINDS and row["outcome"] == "pass"]
    return {
        "last_completed_task": completed_tasks[-1] if completed_tasks else None,
        "execution_count": sum(1 for row in rows if row["run_kind"] in _S4_EXECUTION_KINDS),
        "verification_count": sum(1 for row in rows if row["run_kind"] == _S4_VERIFICATION_KIND),
    }


def _escalation_note(conn: sqlite3.Connection, ticket: sqlite3.Row, stage_run: sqlite3.Row, *, reason: str) -> str:
    outputs = [
        row["id"] for row in conn.execute(
            "SELECT id FROM artefact WHERE stage_run_id = ? ORDER BY id", (stage_run["id"],)
        ).fetchall()
    ]
    binding = conn.execute(
        "SELECT id FROM evidence_tuple WHERE ticket_id = ? ORDER BY id DESC LIMIT 1", (ticket["id"],)
    ).fetchone()
    failure_history = [
        {"attempt": row["attempt"], "outcome": row["outcome"], "failure_kind": row["failure_kind"]}
        for row in conn.execute(
            "SELECT attempt, outcome, failure_kind FROM stage_run "
            "WHERE ticket_id = ? AND stage = ? AND id < ? ORDER BY id",
            (ticket["id"], stage_run["stage"], stage_run["id"]),
        ).fetchall()
    ]
    payload = {
        "reason": reason,
        "reasoning_summary": stage_run["reasoning_summary"],
        "registered_outputs": outputs,
        "binding_evidence_tuple_id": binding["id"] if binding is not None else None,
        "failure_history": failure_history,
    }
    if stage_run["stage"] == "S4":
        payload.update(_s4_progress(conn, ticket["id"]))
    return json.dumps(payload, sort_keys=True)


def abort(conn: sqlite3.Connection, ticket: sqlite3.Row, stage_run_id: int, *, reason: str) -> None:
    """Finish `stage_run_id` `aborted_budget`, escalate the ticket, and open one `escalation` item over it.

    Never opens a new `stage_run`, never touches `attempt` or
    `verification_attempt`, and never removes the ticket's worktree or any
    artefact already registered under this run -- an aborted run's
    isolation and its stopped-work evidence stay exactly as they were,
    the same guarantee `control.stop` gives a human-stopped run.
    """
    stage_run = record.get(conn, "stage_run", stage_run_id)
    if stage_run is None:
        raise LookupError(f"no such stage_run: {stage_run_id}")
    run_ledger.finish(conn, stage_run_id, "aborted_budget")
    note = _escalation_note(conn, ticket, stage_run, reason=reason)
    record.update(conn, "stage_run", stage_run_id, reasoning_summary=note)
    transitions.apply(conn, ticket["id"], "escalate")
    queue.open_item(
        conn, ticket_id=ticket["id"], kind="escalation", stage=stage_run["stage"], tier=stage_run["tier"],
        ref=f"stage_run:{stage_run_id}",
    )
