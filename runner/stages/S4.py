"""S4: one fresh top-level `stage_run` per plan task, in dependency order, plus bounded fix rounds.

`build_handoff`, `record_handback` and `run` stay the self-contained
hand-off/invocation/hand-back trio T-A-28 built -- `run` now takes an
optional `task` so the same three functions serve one plan task at a time
instead of the whole plan in a single invocation. `run_next` is the
per-attempt driver `stages.run_stage` delegates to: it revalidates the
target base before every attempt (plan-tuple currency, quorum, and trust
activation are already enforced once, authoritatively, at
`gates.plan_review_gate` and at eligibility; nothing between there and a
task attempt can move them, so re-deriving them here would only repeat an
unchanging check -- the target base is the one thing that can move on its
own, from outside the ticket entirely), then either continues the ordinary
per-task loop, opens a fix round when S5 has just routed one back, or -- for
`validation_only` -- runs every task's validation recipe once with no agent
at all. `run_next` opens and finishes its own top-level `stage_run` rows
through `run_ledger`, since the columns naming which attempt it is
(`plan_item`, `plan_tuple_id`, `verification_attempt`) are fixed at insert.
"""
import fnmatch
import json
import os
import re
import sqlite3
import subprocess
from pathlib import Path

import yaml

from runner import (
    artefact_registry, artefacts, binding, canonical, freshness, git_trees, queue, record, recipes, run_ledger,
    schema, tags, transitions,
)
from runner.checks import red_route
from runner.fs import write_text
from runner.paths import FACTORY_DIR, PROJECT_CONFIG, REPO_ROOT, RUNS_DIR
from runner.run_ledger import budget as stage_budget, s4_per_ticket_budget
from runner.stages import S5

ARTEFACT_KIND = "handoff"
PASS_EVENT = "s4_pass"
ESCALATE_EVENT = "escalate"

# The machine-actor identity every automated tag/incident this driver
# writes carries, matching `context_index.py`'s own default for a
# runner-initiated record rather than a human one.
RUNNER_ACTOR = "runner"

ESCALATION_FM_ID = "FM-19"
CONTROL_DEFECT_FM_ID = "FM-23"
CONTROL_CATEGORY = "execution_boundary"

LIMITS_PATH = FACTORY_DIR / "config" / "limits.yaml"
SCOPE_DIFF_SCRIPT = FACTORY_DIR / "scripts" / "checks" / "scope_diff"

# A test-only escape hatch matching the fixture worker's own env-var
# seams (`FIXTURE_ADAPTER_OUT_DIR`, ...): a test that needs a real,
# materialised vendor classpath sets this rather than requiring every
# validation-phase test to write into the repository's own `runs/` tree.
VENDOR_CLASSPATH_ENV = "FIXTURE_VENDOR_CLASSPATH"

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

_DIFF_GIT_LINE = re.compile(r"^diff --git a/(?P<a>\S+) b/(?P<b>\S+)$")


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


def _test_strategy_rows(plan_text: str) -> list[dict]:
    plan = artefacts.parse(plan_text)
    section = plan.section("Test strategy")
    return (section.table() if section is not None else None) or []


def _topological_order(tasks: list[dict]) -> list[dict]:
    """`tasks` reordered so every task follows all the ids its `depends_on` names, table order broken ties.

    An id a task depends on but that names no row in this table (a typo,
    or a dependency outside this plan) is simply not visited as a
    dependency -- it can never block a real task from becoming due.
    """
    by_id = {task["id"]: task for task in tasks}
    ordered: list[str] = []
    visiting: set[str] = set()

    def visit(task_id: str) -> None:
        if task_id in ordered or task_id not in by_id:
            return
        if task_id in visiting:
            raise ValueError(f"circular task dependency at {task_id!r}")
        visiting.add(task_id)
        for dep in by_id[task_id]["depends_on"]:
            visit(dep)
        visiting.discard(task_id)
        ordered.append(task_id)

    for task in tasks:
        visit(task["id"])
    return [by_id[task_id] for task_id in ordered]


def build_handoff(
    conn: sqlite3.Connection, ticket: sqlite3.Row, stage_run_id: int, *, task_id: str | None = None,
    runs_dir: Path = RUNS_DIR,
) -> int:
    """Write `handoff.json` (canonical JSON) into this attempt's run dir and register it, superseding the prior version.

    Carries what the plan tuple's own record holds for the approved
    criteria and plan hashes, the assumption-set hash, and the bootstrap
    checklist hash -- never recomputed here -- so a tuple seeded with null
    hashes (as a hand-seeded stub is) yields a hand-off with those same
    nulls rather than a fabricated value. `task_id` names the one plan
    task this invocation runs; `None` means the whole plan (kept for a
    caller with no per-task loop of its own, and for reconstructing the
    hand-off's non-task-specific fields in isolation).
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


def run(
    conn: sqlite3.Connection, ticket: sqlite3.Row, stage_run_id: int, runs_dir: Path = RUNS_DIR, *,
    task: dict | None = None,
) -> str | tuple[str, str]:
    """Hand off, invoke, and hand back one attempt: the whole plan when `task` is `None`, else just `task`.

    A missing plan tuple or plan artefact is a structural failure before
    any invocation is attempted, regardless of `task`. Past that point, a
    `task` also gets `scope_diff` over its own diff and its validation
    recipe run once after a passing hand-back; `task=None` (a direct,
    reconstruction-style caller) stops at the hand-back, exactly as
    before this driver grew a per-task loop.
    """
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

    task_id = task["id"] if task is not None else None
    handoff_id = build_handoff(conn, ticket, stage_run_id, task_id=task_id, runs_dir=runs_dir)

    # Imported here, not at module load, matching S3's own late import of
    # `runner.stages`: that package is still assembling `DRIVERS` while it
    # imports this file, so a top-level import would see it unfinished.
    from runner import stages

    criteria_artefact = artefact_registry.latest(conn, ticket_id, "criteria")
    input_ids = [handoff_id, plan_artefact["id"]]
    if criteria_artefact is not None:
        input_ids.append(criteria_artefact["id"])

    before_head = ticket["head_sha"]
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
    handback_result = record_handback(conn, ticket, stage_run_id, out_dir, runs_dir=runs_dir)
    outcome, _ = handback_result if isinstance(handback_result, tuple) else (handback_result, None)
    if outcome != "pass" or task is None:
        return handback_result

    after_ticket = record.get(conn, "ticket", ticket_id)
    diff_text = _git_diff(Path(after_ticket["worktree_path"]), before_head, after_ticket["head_sha"])
    if not _run_scope_diff(
        conn, stage_run_id, plan_path=Path(plan_artefact["path"]), diff_text=diff_text, runs_dir=runs_dir,
        ticket_id=ticket_id,
    ):
        return "fail", "verification"

    return _validate_task(conn, ticket, stage_run_id, task, runs_dir=runs_dir)


# --- the target-base revalidation every attempt makes ---------------------


def _revalidate(conn: sqlite3.Connection, ticket: sqlite3.Row, *, runs_dir: Path) -> freshness.Freshness | None:
    """The one condition worth re-deriving on every attempt: is the target base still what the plan was bound to.

    Plan-tuple currency, plan quorum, and trust-profile activation are
    each already enforced once, authoritatively -- currency and quorum at
    `gates.plan_review_gate` immediately before the ticket ever reaches
    `implementing`, trust activation at eligibility -- and nothing a task
    attempt does can move any of those bound rows again. The target
    branch can move at any moment, from outside the ticket entirely, so a
    fresh fetch-and-compare here is the one check that earns its place on
    every attempt rather than only once.
    """
    fresh = freshness.check(
        conn, ticket["id"], boundary=freshness.BEFORE_S4, target_branch=freshness.target_branch(), runs_dir=runs_dir,
    )
    return None if fresh.fresh else fresh


def _open_red_check_if_none_open(conn: sqlite3.Connection, ticket_id: int, *, ref: str | None) -> None:
    existing = conn.execute(
        "SELECT id FROM queue_item WHERE ticket_id = ? AND kind = 'red_check' AND resolved_at IS NULL",
        (ticket_id,),
    ).fetchone()
    if existing is None:
        queue.open_item(conn, ticket_id=ticket_id, kind="red_check", ref=ref)


def _record_stale_binding(conn: sqlite3.Connection, ticket: sqlite3.Row, stale: freshness.Freshness) -> str:
    stage_run_id = run_ledger.open_stage_run(conn, ticket_id=ticket["id"], stage="S4", run_kind="task")
    run_ledger.finish(conn, stage_run_id, "fail", failure_kind="stale_binding")
    _open_red_check_if_none_open(conn, ticket["id"], ref=f"check_result:{stale.check_result_id}")
    return "fail"


# --- the ordinary per-task loop --------------------------------------------


def _task_passed(conn: sqlite3.Connection, ticket_id: int, plan_tuple_id: int, task_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM stage_run WHERE ticket_id = ? AND stage = 'S4' AND run_kind = 'task' "
        "AND plan_tuple_id = ? AND plan_item = ? AND outcome = 'pass' LIMIT 1",
        (ticket_id, plan_tuple_id, task_id),
    ).fetchone()
    return row is not None


def _verification_attempt_number(conn: sqlite3.Connection, ticket_id: int, plan_tuple_id: int, task_id: str) -> int:
    """The count of prior runs for `(plan_tuple_id, task_id)` that reached verification, plus one.

    A run that reached verification is one whose outcome is `pass` or
    whose `failure_kind` is `verification` -- an infrastructure failure, a
    control defect, or a stale binding never reached it, so none of those
    advance this count: the next attempt after any of them lands on the
    same number it would have carried had that attempt not happened.
    """
    count = conn.execute(
        "SELECT COUNT(*) FROM stage_run WHERE ticket_id = ? AND stage = 'S4' AND run_kind = 'task' "
        "AND plan_tuple_id = ? AND plan_item = ? AND (outcome = 'pass' OR (outcome = 'fail' AND failure_kind = 'verification'))",
        (ticket_id, plan_tuple_id, task_id),
    ).fetchone()[0]
    return count + 1


def _verification_failure_count(conn: sqlite3.Connection, ticket_id: int, plan_tuple_id: int, task_id: str) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM stage_run WHERE ticket_id = ? AND stage = 'S4' AND run_kind = 'task' "
        "AND plan_tuple_id = ? AND plan_item = ? AND outcome = 'fail' AND failure_kind = 'verification'",
        (ticket_id, plan_tuple_id, task_id),
    ).fetchone()[0]


def _consecutive_infrastructure_failures(conn: sqlite3.Connection, ticket_id: int, plan_tuple_id: int, task_id: str) -> int:
    """How many of the most recent runs for `(plan_tuple_id, task_id)`, newest first, ended `infrastructure_failure`."""
    rows = conn.execute(
        "SELECT outcome FROM stage_run WHERE ticket_id = ? AND stage = 'S4' AND run_kind = 'task' "
        "AND plan_tuple_id = ? AND plan_item = ? ORDER BY id DESC",
        (ticket_id, plan_tuple_id, task_id),
    ).fetchall()
    streak = 0
    for row in rows:
        if row["outcome"] != "infrastructure_failure":
            break
        streak += 1
    return streak


def _verification_cap() -> int:
    return _limits()["verification"]["max_attempts"]


def _limits() -> dict:
    return yaml.safe_load(Path(LIMITS_PATH).read_text())


def _fix_rounds_cap() -> int:
    return _limits()["fix_rounds"]["max_per_ticket"]


def _fix_rounds_run(conn: sqlite3.Connection, ticket_id: int) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM stage_run WHERE ticket_id = ? AND stage = 'S4' AND run_kind = 'fix_round'",
        (ticket_id,),
    ).fetchone()[0]


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-c", "commit.gpgsign=false", *args], cwd=cwd, capture_output=True, text=True, check=True,
    )


def _git_diff(worktree: Path, base: str | None, head: str | None) -> str:
    if not base or not head or base == head:
        return ""
    return _git(["diff", base, head], cwd=worktree).stdout


def _existed_at(worktree: Path, sha: str | None, path: str) -> bool:
    if not sha:
        return False
    result = subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "cat-file", "-e", f"{sha}:{path}"], cwd=worktree,
        capture_output=True, text=True,
    )
    return result.returncode == 0


def _diff_touched_paths(diff_text: str) -> list[str]:
    paths: list[str] = []
    for line in diff_text.splitlines():
        match = _DIFF_GIT_LINE.match(line)
        if match:
            paths.append(match.group("b") or match.group("a"))
    return paths


def _run_scope_diff(
    conn: sqlite3.Connection, stage_run_id: int, *, plan_path: Path, diff_text: str, runs_dir: Path, ticket_id: int,
) -> bool:
    diff_path = _run_dir(runs_dir, ticket_id, stage_run_id) / "task_diff.txt"
    write_text(diff_path, diff_text)
    completed = subprocess.run(
        [str(SCOPE_DIFF_SCRIPT), "--diff", str(diff_path), "--plan", str(plan_path)],
        capture_output=True, text=True, check=True,
    )
    payload = json.loads(completed.stdout)
    _record_check_result(
        conn, stage_run_id, check_name="scope_diff", passed=payload["result"] == "pass",
        detail=json.dumps(payload, sort_keys=True),
    )
    return payload["result"] == "pass"


def _project_config() -> dict:
    return yaml.safe_load(Path(PROJECT_CONFIG).read_text())


def _vendor_classpath(project: dict) -> str:
    override = os.environ.get(VENDOR_CLASSPATH_ENV)
    if override is not None:
        return override
    vendor = project.get("vendor")
    vendor_dir = (REPO_ROOT / vendor) if vendor else None
    if vendor_dir is None or not vendor_dir.is_dir():
        return ""
    return os.pathsep.join(str(p) for p in sorted(vendor_dir.rglob("*.jar")))


def _validate_task(
    conn: sqlite3.Connection, ticket: sqlite3.Row, stage_run_id: int, task: dict, *, runs_dir: Path,
) -> tuple[str, str | None]:
    """Run `task`'s validation recipe once; an unapproved or invalid recipe binding is a control defect, not a verification failure."""
    project = _project_config()
    recipe_id = task["validation_recipe"]
    approved_ids = set(project.get("recipes") or [])
    if not recipe_id or recipe_id not in approved_ids:
        _record_check_result(
            conn, stage_run_id, check_name="recipe_binding", passed=False,
            detail=f"recipe {recipe_id!r} is not in project.yaml's approved recipe list",
        )
        return "fail", "recipe_binding"
    try:
        catalogue = recipes.load_catalogue()
        if recipe_id not in catalogue:
            raise recipes.RecipeError(f"recipe {recipe_id!r} is not in the catalogue")
        results_dir = _run_dir(runs_dir, ticket["id"], stage_run_id) / "results"
        values = {**task["validation_args"], "vendor_classpath": _vendor_classpath(project)}
        result = recipes.run(
            recipe_id, values, catalogue=catalogue, cwd_roles={"checkout": Path(ticket["worktree_path"])},
            results_dir=results_dir, env_source={"PATH": os.environ.get("PATH", "")},
        )
    except recipes.RecipeError as exc:
        _record_check_result(conn, stage_run_id, check_name="recipe_binding", passed=False, detail=str(exc))
        return "fail", "recipe_binding"

    _record_check_result(
        conn, stage_run_id, check_name="task_validation", passed=result.outcome == "pass",
        detail=f"{recipe_id}: {result.outcome} (exit {result.exit_code})",
    )
    if result.outcome != "pass":
        return "fail", "verification"
    return "pass", None


def _control_defect(conn: sqlite3.Connection, ticket: sqlite3.Row, stage_run_id: int, *, failure_kind: str) -> None:
    """The shared side effect of a control-defect outcome: tag, incident, escalate, and one `escalation` item.

    No verification quota is consumed here -- the caller never advances
    `verification_attempt`'s count for a run that ends this way, since
    counting reads only `outcome`/`failure_kind`, and neither
    `sandbox_violation` nor `fail`/`recipe_binding` ever qualifies.
    """
    tag_id = tags.tag(
        conn, target=f"stage_run:{stage_run_id}", kind="control_defect", fm_id=CONTROL_DEFECT_FM_ID,
        actor=RUNNER_ACTOR, severity="sev2", note=f"control defect: {failure_kind}",
    )
    record.insert(
        conn, "incident_observation", ticket_id=ticket["id"], record_kind="control_defect_event",
        control_category=CONTROL_CATEGORY, recorder_identity=RUNNER_ACTOR, created_at=record.now(),
        tag_id=tag_id, occurred_at=record.now(), severity="sev2", note=f"control defect: {failure_kind}",
    )
    transitions.apply(conn, ticket["id"], ESCALATE_EVENT)
    queue.open_item(
        conn, ticket_id=ticket["id"], kind="escalation", stage="S4", tier=_tier(ticket), ref=f"stage_run:{stage_run_id}",
    )


def _escalate(conn: sqlite3.Connection, ticket: sqlite3.Row, stage_run_id: int, *, note: str) -> None:
    tags.tag(
        conn, target=f"stage_run:{stage_run_id}", kind="escalation", fm_id=ESCALATION_FM_ID, actor=RUNNER_ACTOR, note=note,
    )
    transitions.apply(conn, ticket["id"], ESCALATE_EVENT)
    queue.open_item(
        conn, ticket_id=ticket["id"], kind="escalation", stage="S4", tier=_tier(ticket), ref=f"stage_run:{stage_run_id}",
    )


def _failure_history_payload(
    conn: sqlite3.Connection, ticket: sqlite3.Row, plan_tuple_id: int, task: dict, tasks_ordered: list[dict],
) -> dict:
    ticket_id = ticket["id"]
    rows = conn.execute(
        "SELECT * FROM stage_run WHERE ticket_id = ? AND stage = 'S4' AND run_kind = 'task' "
        "AND plan_tuple_id = ? AND plan_item = ? ORDER BY id",
        (ticket_id, plan_tuple_id, task["id"]),
    ).fetchall()
    executions = []
    for row in rows:
        validation = conn.execute(
            "SELECT summary FROM check_result WHERE stage_run_id = ? AND check_name = 'task_validation' ORDER BY id DESC LIMIT 1",
            (row["id"],),
        ).fetchone()
        tokens = None
        if row["tokens_in"] is not None or row["tokens_out"] is not None:
            tokens = (row["tokens_in"] or 0) + (row["tokens_out"] or 0)
        executions.append({
            "attempt": row["attempt"], "verification_attempt": row["verification_attempt"],
            "outcome": row["outcome"], "failure_kind": row["failure_kind"],
            "validation_summary": validation["summary"] if validation is not None else None,
            "reasoning_summary": row["reasoning_summary"], "head_sha": ticket["head_sha"],
            "tokens": tokens, "wall_clock_seconds": row["wall_clock_seconds"],
        })
    cap = _verification_cap()
    consumed = sum(1 for r in rows if r["outcome"] == "pass" or (r["outcome"] == "fail" and r["failure_kind"] == "verification"))
    infra_retries = sum(1 for r in rows if r["outcome"] == "infrastructure_failure")
    dependents_not_run = [
        t["id"] for t in tasks_ordered
        if t["id"] != task["id"] and not _task_passed(conn, ticket_id, plan_tuple_id, t["id"])
    ]
    return {
        "plan_item": task["id"], "recipe": task["validation_recipe"], "expected_result": task["expected_result"],
        "executions": executions,
        "quota": {"consumed": consumed, "remaining": max(cap - consumed, 0), "cap": cap},
        "infrastructure_retries": infra_retries,
        "dependent_tasks_not_yet_run": dependents_not_run,
    }


def _escalate_verification_exhausted(
    conn: sqlite3.Connection, ticket: sqlite3.Row, stage_run_id: int, *, plan_tuple_id: int, task: dict,
    tasks_ordered: list[dict], runs_dir: Path,
) -> None:
    payload = _failure_history_payload(conn, ticket, plan_tuple_id, task, tasks_ordered)
    path = _run_dir(runs_dir, ticket["id"], stage_run_id) / "failure_history.json"
    write_text(path, canonical.canonical_json(payload).decode())
    artefact_registry.register(conn, ticket_id=ticket["id"], kind="failure_history", path=path, stage_run_id=stage_run_id)
    _escalate(conn, ticket, stage_run_id, note=f"task {task['id']} failed verification {_verification_cap()} times")


def _run_task(
    conn: sqlite3.Connection, ticket: sqlite3.Row, task: dict, plan_tuple_id: int, tasks_ordered: list[dict], *,
    runs_dir: Path,
) -> str:
    ticket_id = ticket["id"]
    verification_attempt = _verification_attempt_number(conn, ticket_id, plan_tuple_id, task["id"])
    stage_run_id = run_ledger.open_stage_run(
        conn, ticket_id=ticket_id, stage="S4", run_kind="task",
        plan_item=task["id"], plan_tuple_id=plan_tuple_id, verification_attempt=verification_attempt,
    )
    # A retried task's run is a brand-new invocation: nothing above passes
    # a prior run's context in, and `stages.invoke_agent` always opens a
    # fresh child with its own envelope and freshly registered outputs.
    result = run(conn, ticket, stage_run_id, runs_dir, task=task)
    outcome, failure_kind = result if isinstance(result, tuple) else (result, None)
    run_ledger.finish(conn, stage_run_id, outcome, failure_kind=failure_kind)

    if outcome == "sandbox_violation" or failure_kind == "recipe_binding":
        _control_defect(conn, ticket, stage_run_id, failure_kind=failure_kind or "sandbox_integrity")
    elif outcome == "infrastructure_failure":
        if _consecutive_infrastructure_failures(conn, ticket_id, plan_tuple_id, task["id"]) >= 2:
            _escalate(conn, ticket, stage_run_id, note=f"task {task['id']} hit a repeat infrastructure failure")
    elif outcome == "fail" and failure_kind == "verification":
        if _verification_failure_count(conn, ticket_id, plan_tuple_id, task["id"]) >= _verification_cap():
            _escalate_verification_exhausted(
                conn, ticket, stage_run_id, plan_tuple_id=plan_tuple_id, task=task, tasks_ordered=tasks_ordered,
                runs_dir=runs_dir,
            )
    # aborted_budget (`budgets.abort`) and aborted_human (`control.stop`)
    # have already finished their own run and escalated -- nothing further
    # to do here for either.
    return outcome


# --- fix rounds -------------------------------------------------------------


def _latest_s5_run(conn: sqlite3.Connection, ticket_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM stage_run WHERE ticket_id = ? AND stage = 'S5' ORDER BY id DESC LIMIT 1", (ticket_id,)
    ).fetchone()


def _fix_round_routed(conn: sqlite3.Connection, ticket_id: int) -> bool:
    s5_run = _latest_s5_run(conn, ticket_id)
    if s5_run is None:
        return False
    row = conn.execute(
        "SELECT result FROM check_result WHERE stage_run_id = ? AND check_name = 'fix_round_route' ORDER BY id DESC LIMIT 1",
        (s5_run["id"],),
    ).fetchone()
    return row is not None and row["result"] == "pass"


def _all_test_globs(catalogue: dict) -> list[str]:
    globs: list[str] = []
    for recipe in catalogue.values():
        if recipe.test_globs:
            globs.extend(recipe.test_globs)
    return globs


def _is_test_path(path: str, globs: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in globs)


def _authorized_base_test_row(path: str, rows: list[dict]) -> dict | None:
    name = Path(path).name
    for row in rows:
        if row.get("action") in ("change", "remove") and (row.get("test") or "").strip() in (path, name):
            return row
    return None


def _check_fix_round_diff(
    conn: sqlite3.Connection, ticket: sqlite3.Row, stage_run_id: int, *, plan_text: str, base_sha: str | None,
    worktree: Path, diff_text: str,
) -> tuple[str, str] | None:
    """The round's own confinement rule: no test-only diff, and every changed base test must be plan-authorized.

    A changed test file the plan's `Test strategy` table does not list
    with `action` `change`/`remove`, and that already existed at the
    ticket's base, is refused outright; one that did not exist at base is
    a test this ticket itself added, always allowed. Every authorized
    change is recorded as its own `deviation` row naming the authorizing
    criterion.
    """
    touched = _diff_touched_paths(diff_text)
    if not touched:
        return None
    catalogue = recipes.load_catalogue()
    globs = _all_test_globs(catalogue)
    if all(_is_test_path(path, globs) for path in touched):
        _record_check_result(
            conn, stage_run_id, check_name="fix_round_scope", passed=False, detail="diff touches only test files",
        )
        return "fail", "verification"

    rows = _test_strategy_rows(plan_text)
    for path in touched:
        if not _is_test_path(path, globs):
            continue
        if not _existed_at(worktree, base_sha, path):
            continue  # a test this ticket added itself; never restricted
        authorizing = _authorized_base_test_row(path, rows)
        if authorizing is None:
            _record_check_result(
                conn, stage_run_id, check_name="fix_round_scope", passed=False,
                detail=f"changed base test {path!r} is not listed in the plan's Test strategy table",
            )
            return "fail", "verification"
        record.insert(
            conn, "deviation", ticket_id=ticket["id"], stage_run_id=stage_run_id,
            plan_item=(authorizing.get("criteria") or authorizing.get("test") or ""),
            plan_said=f"Test strategy: {authorizing.get('test')} ({authorizing.get('action')})",
            agent_did=f"changed base test {path}", why=f"authorized by {authorizing.get('criteria') or authorizing.get('test')}",
            kind="judgment", contract_change=0,
        )
    _record_check_result(conn, stage_run_id, check_name="fix_round_scope", passed=True, detail="ok")
    return None


def _run_all_task_validations(
    conn: sqlite3.Connection, ticket: sqlite3.Row, stage_run_id: int, plan_text: str, *, runs_dir: Path,
) -> tuple[str, str | None]:
    for task in _tasks(plan_text):
        outcome, failure_kind = _validate_task(conn, ticket, stage_run_id, task, runs_dir=runs_dir)
        if outcome != "pass":
            return "fail", "verification"
    return "pass", None


def _run_task_validations_only(conn: sqlite3.Connection, ticket: sqlite3.Row, runs_dir: Path) -> str:
    """The standalone `validation_only` mechanism: every task's validation recipe, once, no agent, no state change."""
    ticket_id = ticket["id"]
    plan_tuple = _latest_plan_tuple(conn, ticket_id)
    plan_artefact = artefact_registry.latest(conn, ticket_id, "plan")
    stage_run_id = run_ledger.open_stage_run(
        conn, ticket_id=ticket_id, stage="S4", run_kind="validation_only",
        plan_tuple_id=plan_tuple["id"] if plan_tuple is not None else None,
    )
    if plan_artefact is None:
        _record_check_result(
            conn, stage_run_id, check_name="handoff_structure", passed=False,
            detail="ticket carries no plan artefact to validate",
        )
        run_ledger.finish(conn, stage_run_id, "fail", failure_kind="structural")
        return "fail"
    outcome, failure_kind = _run_all_task_validations(
        conn, ticket, stage_run_id, Path(plan_artefact["path"]).read_text(), runs_dir=runs_dir,
    )
    run_ledger.finish(conn, stage_run_id, outcome, failure_kind=failure_kind)
    return outcome


def _red_evidence_artefact_ids(conn: sqlite3.Connection, s5_run_id: int) -> list[int]:
    rows = conn.execute(
        "SELECT evidence_artefact FROM check_result WHERE stage_run_id = ? AND result = 'fail' "
        "AND evidence_artefact IS NOT NULL",
        (s5_run_id,),
    ).fetchall()
    return [row["evidence_artefact"] for row in rows]


def _execute_fix_round(
    conn: sqlite3.Connection, ticket: sqlite3.Row, stage_run_id: int, plan_tuple: sqlite3.Row, *, runs_dir: Path,
) -> str | tuple[str, str]:
    ticket_id = ticket["id"]
    plan_artefact = artefact_registry.latest(conn, ticket_id, "plan")
    if plan_artefact is None:
        _record_check_result(
            conn, stage_run_id, check_name="handoff_structure", passed=False, detail="ticket carries no plan artefact to hand off",
        )
        return "fail", "structural"

    handoff_id = build_handoff(conn, ticket, stage_run_id, task_id=None, runs_dir=runs_dir)

    before_head = ticket["head_sha"]
    diff_path = _run_dir(runs_dir, ticket_id, stage_run_id) / "current_diff.txt"
    write_text(diff_path, _git_diff(Path(ticket["worktree_path"]), plan_tuple["base_sha"], before_head))
    diff_artefact_id = artefact_registry.register(conn, ticket_id=ticket_id, kind="fix_round_diff", path=diff_path, stage_run_id=stage_run_id)

    from runner import stages

    criteria_artefact = artefact_registry.latest(conn, ticket_id, "criteria")
    input_ids = [handoff_id, plan_artefact["id"], diff_artefact_id]
    if criteria_artefact is not None:
        input_ids.append(criteria_artefact["id"])
    s5_run = _latest_s5_run(conn, ticket_id)
    if s5_run is not None:
        input_ids.extend(_red_evidence_artefact_ids(conn, s5_run["id"]))

    result = stages.invoke_agent(
        conn, ticket, "S4", runs_dir=runs_dir, parent_run_id=stage_run_id, input_artefact_ids=input_ids,
    )
    if result.outcome == "refused_request":
        return "fail", "infrastructure"
    if result.outcome != "pass":
        return result.outcome, result.failure_kind

    out_dir = _child_out_dir(runs_dir, ticket_id, result.stage_run_id)
    handback_result = record_handback(conn, ticket, stage_run_id, out_dir, runs_dir=runs_dir)
    outcome, _ = handback_result if isinstance(handback_result, tuple) else (handback_result, None)
    if outcome != "pass":
        return handback_result

    after_ticket = record.get(conn, "ticket", ticket_id)
    worktree = Path(after_ticket["worktree_path"])
    diff_text = _git_diff(worktree, before_head, after_ticket["head_sha"])
    plan_text = Path(plan_artefact["path"]).read_text()

    round_failure = _check_fix_round_diff(
        conn, ticket, stage_run_id, plan_text=plan_text, base_sha=plan_tuple["base_sha"], worktree=worktree,
        diff_text=diff_text,
    )
    if round_failure is not None:
        return round_failure

    if not _run_scope_diff(
        conn, stage_run_id, plan_path=Path(plan_artefact["path"]), diff_text=diff_text, runs_dir=runs_dir,
        ticket_id=ticket_id,
    ):
        return "fail", "verification"

    validation_outcome = _run_task_validations_only(conn, ticket, runs_dir)
    if validation_outcome != "pass":
        return "fail", "verification"
    return "pass"


def _run_fix_round(conn: sqlite3.Connection, ticket: sqlite3.Row, runs_dir: Path) -> str:
    ticket_id = ticket["id"]
    plan_tuple = _latest_plan_tuple(conn, ticket_id)
    cap = _fix_rounds_cap()
    rounds_run = _fix_rounds_run(conn, ticket_id)
    stage_run_id = run_ledger.open_stage_run(
        conn, ticket_id=ticket_id, stage="S4", run_kind="fix_round",
        plan_tuple_id=plan_tuple["id"] if plan_tuple is not None else None,
    )
    if rounds_run >= cap:
        run_ledger.finish(conn, stage_run_id, "blocked")
        _open_red_check_if_none_open(conn, ticket_id, ref=f"stage_run:{stage_run_id}")
        return "blocked"

    result = _execute_fix_round(conn, ticket, stage_run_id, plan_tuple, runs_dir=runs_dir)
    outcome, failure_kind = result if isinstance(result, tuple) else (result, None)
    run_ledger.finish(conn, stage_run_id, outcome, failure_kind=failure_kind)

    if outcome == "sandbox_violation" or failure_kind == "recipe_binding":
        _control_defect(conn, ticket, stage_run_id, failure_kind=failure_kind or "sandbox_integrity")
    elif outcome != "pass":
        current = record.get(conn, "ticket", ticket_id)
        if current["state"] != "escalated":
            _open_red_check_if_none_open(conn, ticket_id, ref=f"stage_run:{stage_run_id}")
    return outcome


# --- the driver's entry point -----------------------------------------------


def run_next(
    conn: sqlite3.Connection, ticket: sqlite3.Row, *, runs_dir: Path = RUNS_DIR, validation_only: bool = False,
) -> str:
    """Open one S4 run, drive it, finish it, and apply `s4_pass` when the last task's hand-back passes.

    `run_stage` delegates here instead of opening the row itself because
    an S4 row names the plan task it executes, and those columns are
    written at insert. `validation_only` is the runner's own script-only
    mechanism (used standalone here, and internally by a fix round's own
    post hand-back step): no agent, no state change, whatever the plan's
    validation recipes say. Otherwise: a stale target base starts no
    agent; a ticket S5 has just routed back for one gets a fix round
    instead of a task; else the next not-yet-passed task, in dependency
    order, gets one fresh run.
    """
    if validation_only:
        return _run_task_validations_only(conn, ticket, runs_dir)

    ticket_id = ticket["id"]
    stale = _revalidate(conn, ticket, runs_dir=runs_dir)
    if stale is not None:
        return _record_stale_binding(conn, ticket, stale)

    if _fix_round_routed(conn, ticket_id):
        return _run_fix_round(conn, ticket, runs_dir)

    plan_tuple = _latest_plan_tuple(conn, ticket_id)
    plan_artefact = artefact_registry.latest(conn, ticket_id, "plan")
    if plan_tuple is None or plan_artefact is None:
        stage_run_id = run_ledger.open_stage_run(conn, ticket_id=ticket_id, stage="S4", run_kind="task")
        result = run(conn, ticket, stage_run_id, runs_dir)
        outcome, failure_kind = result if isinstance(result, tuple) else (result, None)
        run_ledger.finish(conn, stage_run_id, outcome, failure_kind=failure_kind)
        return outcome

    tasks_ordered = _topological_order(_tasks(Path(plan_artefact["path"]).read_text()))
    next_task = next((t for t in tasks_ordered if not _task_passed(conn, ticket_id, plan_tuple["id"], t["id"])), None)
    if next_task is None:
        # Every task already carries a passing run under this plan tuple;
        # `s4_pass` should already have fired when the last one did, so
        # this is a defensive no-op rather than a path real callers take.
        return "pass"

    outcome = _run_task(conn, ticket, next_task, plan_tuple["id"], tasks_ordered, runs_dir=runs_dir)
    if outcome == "pass":
        remaining = any(
            not _task_passed(conn, ticket_id, plan_tuple["id"], t["id"]) for t in tasks_ordered
        )
        if not remaining:
            transitions.apply(conn, ticket_id, PASS_EVENT)
    return outcome
