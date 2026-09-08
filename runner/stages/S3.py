"""S3: the risk map, the agent's plan, the derived readiness table, and the structural and size gates.

Order matters and is fixed: `risk_map` runs over the brief's touched-area
candidates before the agent ever sees them, so it is attached as an
ordinary input rather than invented by the agent; the agent then writes
the plan; `handoff_ready` derives the readiness table from the criteria,
question/assumption log, brief, risk map and the plan's own tables --
never from agent prose -- immediately after, so every later reviewer sees
the same derived table the structure check does; the structure check and
the size gate run against that exact version; only a version that clears
both is registered as the ticket's `plan`. A structural or size failure is
a `check_result` fail plus a `fail` outcome, never a silent default, and
the exact file `handoff_ready` wrote is what gets registered -- nothing
here re-renders it afterward, so the readiness table's hash column binds
the same bytes every later verdict reads.
"""
import json
import sqlite3
import subprocess
from pathlib import Path

import yaml

from runner import artefact_registry, artefacts, canonical, owners, questions, recipes, record
from runner.checks import artefact_structure
from runner.fs import write_text
from runner.paths import FACTORY_DIR, PROJECT_CONFIG, REPO_ROOT, RUNS_DIR
from runner.reviewer_sets import Slot

ARTEFACT_KIND = "plan"
PASS_EVENT = "s3_pass"

TIERS_PATH = FACTORY_DIR / "config" / "tiers.yaml"
RISK_MAP_SCRIPT = REPO_ROOT / "factory" / "scripts" / "checks" / "risk_map"
SIZE_GATE_SCRIPT = REPO_ROOT / "factory" / "scripts" / "checks" / "size_gate"
HANDOFF_READY_SCRIPT = REPO_ROOT / "factory" / "scripts" / "tools" / "handoff_ready"


def _tiers_config() -> dict:
    return yaml.safe_load(Path(TIERS_PATH).read_text())


def _limits_config() -> dict:
    return yaml.safe_load(Path(FACTORY_DIR / "config" / "limits.yaml").read_text())


def _tier(ticket: sqlite3.Row) -> str:
    return ticket["tier_final"] or ticket["tier_provisional"] or "standard"


def _run_dir(runs_dir: Path, ticket_id: int, stage_run_id: int) -> Path:
    return runs_dir / "tickets" / str(ticket_id) / "runs" / str(stage_run_id)


def _child_out_dir(runs_dir: Path, ticket_id: int, child_stage_run_id: int) -> Path:
    return runs_dir / "tickets" / str(ticket_id) / "runs" / str(child_stage_run_id) / "out"


def _record_check_result(conn: sqlite3.Connection, stage_run_id: int, *, check_name: str, passed: bool, detail: str) -> None:
    row = {
        "stage_run_id": stage_run_id, "check_name": check_name, "check_tier": "blocking", "source": "runner",
        "result": "pass" if passed else "fail", "summary": detail,
        "canonical_serialization_version": canonical.SERIALIZATION_VERSION,
    }
    row["content_hash"] = canonical.content_hash(row)
    record.insert(conn, "check_result", **row)


def _pending_allowed(conn: sqlite3.Connection, ticket_id: int, stage_run_id: int) -> bool:
    """True when the ticket's most recent prior S3 attempt (not this one) ended `blocked`.

    Only top-level attempts count -- `parent_run_id IS NULL` excludes the
    agent-invocation children a prior attempt opened -- since a child's own
    outcome never determines whether the *attempt*'s pending sections are
    exempt.
    """
    prior = conn.execute(
        "SELECT outcome FROM stage_run WHERE ticket_id = ? AND stage = 'S3' AND parent_run_id IS NULL AND id != ? "
        "ORDER BY id DESC LIMIT 1",
        (ticket_id, stage_run_id),
    ).fetchone()
    return prior is not None and prior["outcome"] == "blocked"


def _write_risk_map(
    conn: sqlite3.Connection, ticket: sqlite3.Row, stage_run_id: int, run_dir: Path, brief_text: str,
) -> Path:
    """Run `risk_map` over the brief's touched-area candidates and register its output as the ticket's `risk_map` artefact."""
    section = artefacts.parse(brief_text).section("Touched area candidates")
    paths = [row["path"] for row in (section.table() if section is not None else None) or [] if row.get("path")]
    candidates_path = run_dir / "risk_map_candidates.txt"
    write_text(candidates_path, "\n".join(paths) + ("\n" if paths else ""))

    project = yaml.safe_load(Path(PROJECT_CONFIG).read_text())
    risk_limits = _limits_config()["risk_map"]
    completed = subprocess.run(
        [
            str(RISK_MAP_SCRIPT), "--checkout", ticket["worktree_path"], "--branch", project["target_branch"],
            "--candidates", str(candidates_path), "--months", str(risk_limits["churn_window_months"]),
            "--min-share", str(risk_limits["clear_owner_min_share"]),
        ],
        capture_output=True, text=True, check=False,
    )
    risk_map_path = run_dir / "risk_map.json"
    write_text(risk_map_path, completed.stdout if completed.returncode == 0 else json.dumps({"candidates": []}))

    prior = artefact_registry.latest(conn, ticket["id"], "risk_map")
    artefact_registry.register(
        conn, ticket_id=ticket["id"], kind="risk_map", path=risk_map_path, stage_run_id=stage_run_id,
        supersedes=prior["id"] if prior is not None else None,
    )
    return risk_map_path


def _reviewer_set_json(run_dir: Path) -> Path:
    """A single planned slot for the S3 reviewer role, from `owners.yaml`.

    The real derivation from the plan's own scope belongs to a later
    ticket; until then, S3's readiness check needs *a* reviewer-set input,
    so this stands in with the one role every Initial ticket needs.
    """
    identity = owners.load_owners().roles["s3_reviewer"]["identity"]
    slot = Slot(source_rule="s3_reviewer_role", role="s3_reviewer", owner=identity, min_count=1)
    path = run_dir / "reviewer_set.json"
    write_text(path, json.dumps([slot.to_json()], sort_keys=True))
    return path


def _questions_json(conn: sqlite3.Connection, ticket_id: int, run_dir: Path) -> Path:
    rows = conn.execute("SELECT id, state, blocking FROM question WHERE ticket_id = ?", (ticket_id,)).fetchall()
    payload = [{"id": row["id"], "state": row["state"], "blocking": bool(row["blocking"])} for row in rows]
    path = run_dir / "questions.json"
    write_text(path, json.dumps(payload, sort_keys=True))
    return path


def _assumptions_json(conn: sqlite3.Connection, ticket_id: int, run_dir: Path) -> Path:
    rows = conn.execute(
        "SELECT id, text FROM assumption WHERE ticket_id = ? AND (withdrawn IS NULL OR withdrawn = 0)", (ticket_id,)
    ).fetchall()
    payload = [{"id": row["id"], "text": row["text"]} for row in rows]
    path = run_dir / "assumptions.json"
    write_text(path, json.dumps(payload, sort_keys=True))
    return path


def run(conn: sqlite3.Connection, ticket: sqlite3.Row, stage_run_id: int, runs_dir: Path = RUNS_DIR) -> str | tuple[str, str]:
    ticket_id = ticket["id"]
    tier = _tier(ticket)
    run_dir = _run_dir(runs_dir, ticket_id, stage_run_id)

    brief_artefact = artefact_registry.latest(conn, ticket_id, "brief")
    criteria_artefact = artefact_registry.latest(conn, ticket_id, "criteria")
    if brief_artefact is None or criteria_artefact is None:
        _record_check_result(
            conn, stage_run_id, check_name="artefact_structure", passed=False,
            detail="ticket carries no brief and/or criteria artefact to plan against",
        )
        return "fail", "structural"
    brief_text = Path(brief_artefact["path"]).read_text()
    criteria_text = Path(criteria_artefact["path"]).read_text()

    # (1) the risk map, computed before the agent runs, attached as an
    # ordinary latest-version input alongside the brief and criteria.
    _write_risk_map(conn, ticket, stage_run_id, run_dir, brief_text)

    # (2) the agent's own invocation, a child of this attempt. Imported
    # here, not at module load: `runner.stages` (this module's own
    # package) is still assembling `DRIVERS` and `invoke_agent` while it
    # imports this file, so a top-level import would see neither.
    from runner import stages

    result = stages.invoke_agent(conn, ticket, "S3", runs_dir=runs_dir, parent_run_id=stage_run_id)
    if result.outcome == "refused_request":
        # Not a `stage_run.outcome` value: the pin mismatch this names is
        # an infrastructure-level condition on this attempt, not a
        # judgeable structural or verification failure.
        return "fail", "infrastructure"
    if result.outcome != "pass":
        return result.outcome, result.failure_kind

    # (3) parse the agent's plan.
    plan_path = _child_out_dir(runs_dir, ticket_id, result.stage_run_id) / "plan.md"
    if not plan_path.is_file():
        _record_check_result(
            conn, stage_run_id, check_name="artefact_structure", passed=False, detail="agent wrote no out/plan.md",
        )
        return "fail", "structural"
    plan_text = plan_path.read_text()

    # Front matter is written before `handoff_ready` runs, not after, so
    # the file it edits in place -- and that this driver later registers
    # unmodified -- already carries it; the readiness table's hash column
    # then binds the exact bytes every later verdict and the plan tuple read.
    front_matter = {
        "assumption_log_hash": questions.assumption_log_hash(conn, ticket_id),
        "criteria_hash": criteria_artefact["hash"],
    }
    working_path = run_dir / "plan.md"
    write_text(working_path, "---\n" + yaml.safe_dump(front_matter, sort_keys=False) + "---\n" + plan_text)

    # (4) handoff_ready derives and writes the readiness table, in place.
    questions_path = _questions_json(conn, ticket_id, run_dir)
    assumptions_path = _assumptions_json(conn, ticket_id, run_dir)
    risk_map_path = run_dir / "risk_map.json"
    reviewer_set_path = _reviewer_set_json(run_dir)
    handoff = subprocess.run(
        [
            str(HANDOFF_READY_SCRIPT), "--plan", str(working_path), "--criteria", str(criteria_artefact["path"]),
            "--brief", str(brief_artefact["path"]), "--questions", str(questions_path),
            "--assumptions", str(assumptions_path), "--risk-map", str(risk_map_path),
            "--reviewer-set", str(reviewer_set_path), "--tier", tier, "--tiers-config", str(TIERS_PATH), "--in-place",
        ],
        capture_output=True, text=True, check=False,
    )
    if handoff.returncode != 0:
        _record_check_result(
            conn, stage_run_id, check_name="artefact_structure", passed=False,
            detail=f"handoff_ready refused: {handoff.stderr.strip()}",
        )
        return "fail", "structural"
    final_text = working_path.read_text()

    # (5) the structure check, against the exact version handoff_ready left.
    findings = artefact_structure.check(
        "plan", final_text, tier=tier, criteria_text=criteria_text, catalogue=recipes.load_catalogue(),
        limits=_tiers_config()["length_limits"], pending_allowed=_pending_allowed(conn, ticket_id, stage_run_id),
    )
    _record_check_result(
        conn, stage_run_id, check_name="artefact_structure", passed=not findings,
        detail="; ".join(f"{f.rule}: {f.detail}" for f in findings) if findings else "structurally sound",
    )
    if findings:
        return "fail", "structural"

    # (6) the size gate, over the plan's own Size table.
    size_gate = subprocess.run(
        [str(SIZE_GATE_SCRIPT), "--plan", str(working_path), "--tier", tier, "--tiers-config", str(TIERS_PATH)],
        capture_output=True, text=True, check=False,
    )
    size_payload = json.loads(size_gate.stdout) if size_gate.stdout else {"result": "fail", "reason": size_gate.stderr}
    _record_check_result(
        conn, stage_run_id, check_name="size_gate", passed=size_payload.get("result") == "pass",
        detail=json.dumps(size_payload, sort_keys=True),
    )
    if size_payload.get("result") != "pass":
        return "fail"

    # (7) register the exact version handoff_ready wrote as the plan.
    prior = artefact_registry.latest(conn, ticket_id, ARTEFACT_KIND)
    artefact_registry.register(
        conn, ticket_id=ticket_id, kind=ARTEFACT_KIND, path=working_path, stage_run_id=stage_run_id,
        supersedes=prior["id"] if prior is not None else None,
    )
    return "pass"
