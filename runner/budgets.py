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
they were, so nothing here ever consumes a verification slot. The reason
is recorded as one failed runner `check_result` on the aborted run, the
same shape a stale base or a manifest migration leaves; the `escalation`
item's content (reasoning summary, registered outputs, current binding,
failure history, S4 progress) is derived from the record when the queue
shows the item (`queue.escalation_context`), never stored as a second
copy and never written over the agent's own reasoning summary.
"""
import sqlite3

from runner import canonical, queue, record, run_ledger, transitions

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
    row = {
        "stage_run_id": stage_run_id,
        "check_name": "budget",
        "check_tier": "blocking",
        "source": "runner",
        "result": "fail",
        "summary": reason,
        "canonical_serialization_version": canonical.SERIALIZATION_VERSION,
    }
    row["content_hash"] = canonical.content_hash(row)
    record.insert(conn, "check_result", **row)
    transitions.apply(conn, ticket["id"], "escalate")
    queue.open_item(
        conn, ticket_id=ticket["id"], kind="escalation", stage=stage_run["stage"], tier=stage_run["tier"],
        ref=f"stage_run:{stage_run_id}",
    )
