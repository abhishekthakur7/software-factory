"""S4: the self-contained hand-off, the one governed invocation, and the hand-back that records it.

Three separate functions on purpose -- `build_handoff`, the
`stages.invoke_agent` call `run` makes, and `record_handback` -- because a
later ticket turns this single whole-plan invocation into one run per plan
task, reusing the same hand-off and hand-back shapes with only the
invocation loop changing; `task_id` already names which task a hand-off is
for, `None` meaning the whole plan. Every path a fresh implementer needs
comes from the record and the plan's own tables, never from the S3
transcript, so a reconstruction test can derive the same task list, recipe
set, and budget from `handoff.json` and the registered sandbox mounts
alone. A missing or malformed hand-back is a structural failure recorded
as a `check_result` fail and returned as `("fail", "structural")`: no
`red_check` item, no waiver route, the ordinary fresh rerun applies.
"""
import json
import sqlite3
from pathlib import Path

import yaml

from runner import artefact_registry, artefacts, binding, canonical, git_trees, record, run_ledger, schema, transitions
from runner.fs import write_text
from runner.paths import PROJECT_CONFIG, RUNS_DIR
from runner.run_ledger import budget as stage_budget, s4_per_ticket_budget
from runner.stages import S5

ARTEFACT_KIND = "handoff"
PASS_EVENT = "s4_pass"

# The `handback.json` deviation item's exact key set -- one-to-one with
# the `deviation` table's own agent-facing columns (`id`, `ticket_id`, and
# `stage_run_id` are the runner's to fill in, never the agent's).
DEVIATION_FIELDS: tuple[str, ...] = ("plan_item", "plan_said", "agent_did", "why", "kind", "contract_change")

# The `Contracts` table's ten field cells (COMMON.md), each `<state>` or
# `<state>: <evidence or decision>`; a cell whose state is `unknown` is a
# blind spot the plan left open, alongside a `Readiness` row of status
# `blind_spot`.
_CONTRACT_FIELDS: tuple[str, ...] = (
    "source_declaration", "input", "output", "errors", "side_effects", "invariants",
    "authorization", "ordering_concurrency", "transaction_persistence", "compatibility",
)


def _tier(ticket: sqlite3.Row) -> str:
    return ticket["tier_final"] or ticket["tier_provisional"] or "standard"


def _run_dir(runs_dir: Path, ticket_id: int, stage_run_id: int) -> Path:
    return Path(runs_dir) / "tickets" / str(ticket_id) / "runs" / str(stage_run_id)


def _child_out_dir(runs_dir: Path, ticket_id: int, child_stage_run_id: int) -> Path:
    return _run_dir(runs_dir, ticket_id, child_stage_run_id) / "out"


def _record_check_result(conn: sqlite3.Connection, stage_run_id: int, *, check_name: str, passed: bool, detail: str) -> None:
    row = {
        "stage_run_id": stage_run_id, "check_name": check_name, "check_tier": "blocking", "source": "runner",
        "result": "pass" if passed else "fail", "summary": detail,
        "canonical_serialization_version": canonical.SERIALIZATION_VERSION,
    }
    row["content_hash"] = canonical.content_hash(row)
    record.insert(conn, "check_result", **row)


def _latest_plan_tuple(conn: sqlite3.Connection, ticket_id: int) -> sqlite3.Row | None:
    """The ticket's most recent `plan` `evidence_tuple` row, read directly rather than through tuple-selection logic.

    Which plan tuple is *current* is a decision another module owns; S4
    only needs the one the ticket's approved plan actually bound, so it
    reads the latest `plan`-kind row by id and trusts the record.
    """
    return conn.execute(
        "SELECT * FROM evidence_tuple WHERE ticket_id = ? AND kind = 'plan' ORDER BY id DESC LIMIT 1",
        (ticket_id,),
    ).fetchone()


def _loop_note(conn: sqlite3.Connection, ticket_id: int) -> str | None:
    row = conn.execute(
        "SELECT note FROM tag WHERE ticket_id = ? AND event_kind = 'revision_after_approval' ORDER BY id DESC LIMIT 1",
        (ticket_id,),
    ).fetchone()
    return row["note"] if row is not None else None


def _split_list(cell: str | None) -> list[str]:
    """A comma-separated plan-table cell as a list of trimmed, non-empty tokens."""
    return [part.strip() for part in (cell or "").split(",") if part.strip()]


def _typed_value(raw: str):
    if raw in ("true", "false"):
        return raw == "true"
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        return raw


def _validation_args(cell: str | None) -> dict:
    """A task's `validation_args` cell (space-separated `key=value` tokens) as a typed mapping."""
    args: dict = {}
    for token in (cell or "").split():
        key, sep, value = token.partition("=")
        if sep:
            args[key.strip()] = _typed_value(value.strip())
    return args


def _blind_spots(plan_text: str) -> list[dict]:
    """The plan's readiness rows with status `blind_spot`, plus every `Contracts` cell marked `unknown`."""
    plan = artefacts.parse(plan_text)
    spots: list[dict] = []
    readiness = plan.section("Readiness")
    for row in (readiness.table() if readiness is not None else None) or []:
        if row.get("status") == "blind_spot":
            spots.append({
                "source": "readiness", "condition": row.get("condition"),
                "waiver_id": row.get("waiver_id") or None, "note": row.get("note"),
            })
    contracts = plan.section("Contracts")
    for row in (contracts.table() if contracts is not None else None) or []:
        for field in _CONTRACT_FIELDS:
            cell = (row.get(field) or "").strip()
            state = cell.split(":", 1)[0].strip()
            if state == "unknown":
                spots.append({"source": "contract", "unit": row.get("unit"), "field": field, "note": cell})
    return spots


def _tasks(plan_text: str) -> list[dict]:
    plan = artefacts.parse(plan_text)
    section = plan.section("Tasks")
    rows = (section.table() if section is not None else None) or []
    return [
        {
            "id": row.get("id"), "title": row.get("title"), "depends_on": _split_list(row.get("depends_on")),
            "criteria": _split_list(row.get("criteria")), "files": _split_list(row.get("files")),
            "validation_recipe": row.get("validation_recipe"),
            "validation_args": _validation_args(row.get("validation_args")),
            "expected_result": row.get("expected_result"),
            "no_behaviour_change": (row.get("no_behaviour_change") or "").strip().lower() in ("yes", "true", "1"),
        }
        for row in rows
    ]


def _scope(plan_text: str) -> list[dict]:
    plan = artefacts.parse(plan_text)
    section = plan.section("Scope and discretion")
    rows = (section.table() if section is not None else None) or []
    return [{"path": row.get("path"), "action": row.get("action"), "reason": row.get("reason")} for row in rows]


def build_handoff(
    conn: sqlite3.Connection, ticket: sqlite3.Row, stage_run_id: int, *, task_id: str | None = None,
    runs_dir: Path = RUNS_DIR,
) -> int:
    """Write `handoff.json` (canonical JSON) into this attempt's run dir and register it, superseding the prior version.

    Carries what the plan tuple's own record holds for the approved
    criteria and plan hashes, the assumption-set hash, and the bootstrap
    checklist hash -- never recomputed here -- so a tuple seeded with null
    hashes (as a hand-seeded stub is) yields a hand-off with those same
    nulls rather than a fabricated value.
    """
    ticket_id = ticket["id"]
    tier = _tier(ticket)
    plan_tuple = _latest_plan_tuple(conn, ticket_id)
    plan_artefact = artefact_registry.latest(conn, ticket_id, "plan")
    criteria_artefact = artefact_registry.latest(conn, ticket_id, "criteria")
    plan_text = Path(plan_artefact["path"]).read_text()
    project = yaml.safe_load(Path(PROJECT_CONFIG).read_text())

    payload = {
        "ticket_id": ticket_id,
        "plan_tuple_id": plan_tuple["id"],
        "plan_artefact_id": plan_artefact["id"],
        "plan_hash": plan_tuple["plan_hash"],
        "criteria_artefact_id": criteria_artefact["id"] if criteria_artefact is not None else None,
        "criteria_hash": plan_tuple["criteria_hash"],
        "assumption_set_hash": plan_tuple["current_assumption_set_hash"],
        "blind_spots": _blind_spots(plan_text),
        "tier": tier,
        "budget": {"run": stage_budget("S4", tier), "ticket": s4_per_ticket_budget(tier)},
        "check_policies": list(S5.CHECK_ORDER),
        "recipe_ids": list(project.get("recipes") or []),
        "tasks": _tasks(plan_text),
        "scope": _scope(plan_text),
        "bootstrap_checklist_hash": plan_tuple["semantic_checklist_hash"],
        "deviation_schema": [column.name for column in schema.table("deviation").columns],
        "loop_note": _loop_note(conn, ticket_id),
        "task": task_id,
    }

    path = _run_dir(runs_dir, ticket_id, stage_run_id) / "handoff.json"
    write_text(path, canonical.canonical_json(payload).decode())
    prior = artefact_registry.latest(conn, ticket_id, ARTEFACT_KIND)
    return artefact_registry.register(
        conn, ticket_id=ticket_id, kind=ARTEFACT_KIND, path=path, stage_run_id=stage_run_id,
        supersedes=prior["id"] if prior is not None else None,
    )


def _valid_deviation(item) -> bool:
    if not isinstance(item, dict) or set(item.keys()) != set(DEVIATION_FIELDS):
        return False
    if item["kind"] not in schema.DEVIATION_KINDS:
        return False
    if not isinstance(item["contract_change"], bool):
        return False
    return all(isinstance(item[field], str) for field in ("plan_item", "plan_said", "agent_did", "why"))


def record_handback(
    conn: sqlite3.Connection, ticket: sqlite3.Row, stage_run_id: int, out_dir: Path, *, runs_dir: Path = RUNS_DIR,
) -> str | tuple[str, str]:
    """Read `out/handback.json`, validate its deviation set, commit the worktree, and record what it says.

    Every write below -- the commit, the ticket's `branch`/`head_sha`/
    `worktree_path`, the `deviation` rows -- happens only after validation
    passes; a missing file, a missing `deviations` key, or one row outside
    the 2.2 schema returns before any of it, so a structural failure never
    leaves a partial hand-back behind.
    """
    handback_path = Path(out_dir) / "handback.json"
    if not handback_path.is_file():
        _record_check_result(
            conn, stage_run_id, check_name="handback_structure", passed=False, detail="agent wrote no out/handback.json",
        )
        return "fail", "structural"
    try:
        payload = json.loads(handback_path.read_text())
    except json.JSONDecodeError as exc:
        _record_check_result(
            conn, stage_run_id, check_name="handback_structure", passed=False,
            detail=f"out/handback.json is not valid JSON: {exc}",
        )
        return "fail", "structural"
    if not isinstance(payload, dict) or "deviations" not in payload:
        _record_check_result(
            conn, stage_run_id, check_name="handback_structure", passed=False,
            detail="out/handback.json carries no 'deviations' key",
        )
        return "fail", "structural"
    deviations = payload["deviations"]
    if not isinstance(deviations, list) or not all(_valid_deviation(item) for item in deviations):
        _record_check_result(
            conn, stage_run_id, check_name="handback_structure", passed=False,
            detail="deviation set does not conform to the deviation schema",
        )
        return "fail", "structural"

    head_sha = git_trees.commit_worktree(
        Path(ticket["worktree_path"]), f"ticket {ticket['id']}: S4 hand-back (stage_run {stage_run_id})",
    )
    record.update(
        conn, "ticket", ticket["id"], branch=ticket["branch"], head_sha=head_sha, worktree_path=ticket["worktree_path"],
    )
    for item in deviations:
        record.insert(
            conn, "deviation", ticket_id=ticket["id"], stage_run_id=stage_run_id,
            plan_item=item["plan_item"], plan_said=item["plan_said"], agent_did=item["agent_did"],
            why=item["why"], kind=item["kind"], contract_change=1 if item["contract_change"] else 0,
        )

    # `binding.deviation_set_hash` recomputes over the rows just inserted,
    # so this summary and any later reader of the same function always
    # agree by construction -- never two independent derivations of the
    # same digest.
    deviation_set_hash = binding.deviation_set_hash(conn, ticket["id"])
    count = conn.execute("SELECT COUNT(*) FROM deviation WHERE ticket_id = ?", (ticket["id"],)).fetchone()[0]
    _record_check_result(
        conn, stage_run_id, check_name="handback_structure", passed=True,
        detail=json.dumps({"deviation_set_hash": deviation_set_hash, "count": count}, sort_keys=True),
    )
    return "pass"


def run(conn: sqlite3.Connection, ticket: sqlite3.Row, stage_run_id: int, runs_dir: Path = RUNS_DIR) -> str | tuple[str, str]:
    ticket_id = ticket["id"]
    plan_tuple = _latest_plan_tuple(conn, ticket_id)
    plan_artefact = artefact_registry.latest(conn, ticket_id, "plan")
    missing = [
        name for name, present in (("plan tuple", plan_tuple is not None), ("plan artefact", plan_artefact is not None))
        if not present
    ]
    if missing:
        _record_check_result(
            conn, stage_run_id, check_name="handoff_structure", passed=False,
            detail=f"ticket carries no {' and '.join(missing)} to hand off",
        )
        return "fail", "structural"

    handoff_id = build_handoff(conn, ticket, stage_run_id, runs_dir=runs_dir)

    # Imported here, not at module load, matching S3's own late import of
    # `runner.stages`: that package is still assembling `DRIVERS` while it
    # imports this file, so a top-level import would see it unfinished.
    from runner import stages

    criteria_artefact = artefact_registry.latest(conn, ticket_id, "criteria")
    input_ids = [handoff_id, plan_artefact["id"]]
    if criteria_artefact is not None:
        input_ids.append(criteria_artefact["id"])

    result = stages.invoke_agent(
        conn, ticket, "S4", runs_dir=runs_dir, parent_run_id=stage_run_id, input_artefact_ids=input_ids,
    )
    if result.outcome == "refused_request":
        # A manifest-pin mismatch: infrastructure-level, not a judgeable
        # structural or verification failure.
        return "fail", "infrastructure"
    if result.outcome != "pass":
        return result.outcome, result.failure_kind

    out_dir = _child_out_dir(runs_dir, ticket_id, result.stage_run_id)
    return record_handback(conn, ticket, stage_run_id, out_dir, runs_dir=runs_dir)


def run_next(
    conn: sqlite3.Connection, ticket: sqlite3.Row, *, runs_dir: Path = RUNS_DIR, validation_only: bool = False,
) -> str:
    """Open one S4 run, drive it, finish it, and apply `s4_pass` when a non-validation run's hand-back passes.

    `run_stage` delegates here instead of opening the row itself because
    an S4 row names the plan task it executes, and those columns are
    written at insert. A `validation_only` run is recorded with no state
    change, as the state table says.
    """
    run_kind = "validation_only" if validation_only else "task"
    stage_run_id = run_ledger.open_stage_run(conn, ticket_id=ticket["id"], stage="S4", run_kind=run_kind)
    result = run(conn, ticket, stage_run_id, runs_dir)
    outcome, failure_kind = result if isinstance(result, tuple) else (result, None)
    run_ledger.finish(conn, stage_run_id, outcome, failure_kind=failure_kind)
    if outcome == "pass" and not validation_only:
        transitions.apply(conn, ticket["id"], PASS_EVENT)
    return outcome
