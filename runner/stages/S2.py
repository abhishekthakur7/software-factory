"""S2 driver: the question and assumption half.

Reads the agent's `questions.yaml`, runs the pre-queue gate over every
candidate through `questions.raise_round`, and queues what passes. The
criteria half -- the restatement children and the S3-bound exit gate --
belongs to a later driver; this `run` stays short and self-contained on
purpose, so a criteria half can be added around these same calls without
restructuring what is here.
"""
import sqlite3
from pathlib import Path

import yaml

from runner import artefact_registry, canonical, questions, record, stages
from runner.paths import RUNS_DIR

ARTEFACT_KIND = "question_set"
PASS_EVENT = "s2_pass"

_INVOCATION_OUTCOMES_PASSED_THROUGH = frozenset({"aborted_budget", "infrastructure_failure", "sandbox_violation"})


def _out_dir(runs_dir: Path, ticket_id: int, child_stage_run_id: int) -> Path:
    return runs_dir / "tickets" / str(ticket_id) / "runs" / str(child_stage_run_id) / "out"


def _load_candidates(out_dir: Path) -> list[dict]:
    """The agent's `questions.yaml` candidates, or `[]` when the child wrote none: absence means no more questions."""
    path = out_dir / "questions.yaml"
    if not path.is_file():
        return []
    return yaml.safe_load(path.read_text()) or []


def _record_gate_failure(conn: sqlite3.Connection, stage_run_id: int, summary: str) -> None:
    row = {
        "stage_run_id": stage_run_id,
        "check_name": "question_gate",
        "check_tier": "blocking",
        "source": "runner",
        "result": "fail",
        "summary": summary,
        "canonical_serialization_version": canonical.SERIALIZATION_VERSION,
    }
    row["content_hash"] = canonical.content_hash(row)
    record.insert(conn, "check_result", **row)


def _has_open_blocking_question(conn: sqlite3.Connection, ticket_id: int) -> bool:
    return conn.execute(
        "SELECT id FROM question WHERE ticket_id = ? AND stage = 'S2' AND blocking = 1 AND state = 'open'",
        (ticket_id,),
    ).fetchone() is not None


def run(conn: sqlite3.Connection, ticket: sqlite3.Row, stage_run_id: int, runs_dir: Path = RUNS_DIR):
    result = stages.invoke_agent(conn, ticket, "S2", runs_dir=runs_dir, parent_run_id=stage_run_id)
    if result.outcome in _INVOCATION_OUTCOMES_PASSED_THROUGH:
        return result.outcome, result.failure_kind
    if result.stage_run_id == -1:
        # No child run ever opened -- a manifest-pin refusal, since S2
        # always names a real agent. `refused_request` is a `utility_run`
        # kind, not a `stage_run` outcome, so the attempt itself records
        # this the same way an unresolvable invocation always would.
        return "fail", "infrastructure"

    tier = ticket["tier_final"] or ticket["tier_provisional"] or "standard"
    out_dir = _out_dir(runs_dir, ticket["id"], result.stage_run_id)
    candidates = _load_candidates(out_dir)

    try:
        questions.raise_round(conn, ticket_id=ticket["id"], stage="S2", candidates=candidates, tier=tier)
    except (questions.QuestionRejected, questions.RoundRefused) as exc:
        _record_gate_failure(conn, stage_run_id, str(exc))
        return "fail", "structural"

    questions_path = out_dir / "questions.yaml"
    if questions_path.is_file():
        prior = artefact_registry.latest(conn, ticket["id"], ARTEFACT_KIND)
        artefact_registry.register(
            conn, ticket_id=ticket["id"], kind=ARTEFACT_KIND, path=questions_path, stage_run_id=stage_run_id,
            supersedes=prior["id"] if prior is not None else None,
        )

    if _has_open_blocking_question(conn, ticket["id"]):
        return "blocked"
    return "pass"
