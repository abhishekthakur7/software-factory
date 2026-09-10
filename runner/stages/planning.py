"""The planning stage: the risk map, the agent's plan, the derived readiness table, and the structural and size gates.

Order matters and is fixed: `risk_map` runs over the brief's touched-area
candidates before the agent ever sees them, so it is attached as an
ordinary input rather than invented by the agent; the agent then writes
the plan; `handoff_ready` derives the readiness table from the criteria,
question/assumption log, brief, risk map and the plan's own tables --
never from agent prose -- immediately after, so every later reviewer sees
the same derived table the structure check does; the structure check, the
plan rubric's script-half findings, and the size gate run against that
exact version, in that order; only a version that clears all three is
registered as the ticket's `plan`. A structural, rubric, or size failure
is a `check_result` fail plus a `fail` outcome, never a silent default,
and the exact file `handoff_ready` wrote is what gets registered --
nothing here re-renders it afterward, so the readiness table's hash
column binds the same bytes every later verdict reads. A `Contracts` row
whose `compatibility` field is `unknown` on a public unit re-triggers the
same pilot-exclusion route context gathering uses for a discovered excluded scope: this
stage cannot itself judge whether a public contract genuinely changed, so
it defers to the human the same way context gathering defers a second discovered service.
"""
import json
import sqlite3
import subprocess
from pathlib import Path

import yaml

from runner import (
    artefact_registry, artefacts, canonical, owners, project, queue, questions, recipes, record, reviewer_sets,
)
from runner.checks import artefact_structure, exclusion, plan_rubric
from runner.fs import write_text
from runner.paths import FACTORY_DIR, REPO_ROOT, RUNS_DIR

ARTEFACT_KIND = "plan"
PASS_EVENT = "planning_pass"

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


def _record_plan_rubric_result(conn: sqlite3.Connection, stage_run_id: int, *, findings: list, extra_summary: str) -> str:
    """Record the `plan_rubric` check_result and return its result: `fail` over any fail finding, else `blind_spot` over any finding, else `pass`."""
    if any(f.result == "fail" for f in findings):
        outcome = "fail"
    elif findings:
        outcome = "blind_spot"
    else:
        outcome = "pass"
    summary = "; ".join(f"{f.rule} ({f.result}): {f.detail}" for f in findings) if findings else "no findings"
    row = {
        "stage_run_id": stage_run_id, "check_name": "plan_rubric", "check_tier": "blocking", "source": "runner",
        "result": outcome, "summary": f"{summary}. {extra_summary}",
        "canonical_serialization_version": canonical.SERIALIZATION_VERSION,
    }
    row["content_hash"] = canonical.content_hash(row)
    record.insert(conn, "check_result", **row)
    return outcome


def _contracts_exclusion_reason(plan_text: str) -> str | None:
    """The reason a `Contracts` row re-triggers pilot exclusion, or `None`: an `unknown` `compatibility` field on a public unit.

    "Public" is read from either cell a plan might use to say so -- the
    `kind` cell or the free-form `source_declaration` text -- since the
    Contracts table's `kind` column (function, module, endpoint, event,
    serialized shape) carries no dedicated visibility column of its own.
    """
    section = artefacts.parse(plan_text).section("Contracts")
    for row in (section.table() if section is not None else None) or []:
        try:
            state, _ = artefacts.contract_cell(row.get("compatibility"))
        except artefacts.ArtefactError:
            continue  # malformed cells are the structure check's finding, not this one's
        is_public = "public" in (row.get("kind") or "").lower() or "public" in (row.get("source_declaration") or "").lower()
        if state == "unknown" and is_public:
            return f"contracts row {row.get('unit')!r} carries an unknown compatibility field on a public unit"
    return None


def _pending_allowed(conn: sqlite3.Connection, ticket_id: int, stage_run_id: int) -> bool:
    """True when the ticket's most recent prior planning attempt (not this one) ended `blocked`.

    Only top-level attempts count -- `parent_run_id IS NULL` excludes the
    agent-invocation children a prior attempt opened -- since a child's own
    outcome never determines whether the *attempt*'s pending sections are
    exempt.
    """
    prior = conn.execute(
        "SELECT outcome FROM stage_run WHERE ticket_id = ? AND stage = 'planning' AND parent_run_id IS NULL AND id != ? "
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

    project_cfg = project.pilot()
    risk_limits = _limits_config()["risk_map"]
    completed = subprocess.run(
        [
            str(RISK_MAP_SCRIPT), "--checkout", ticket["worktree_path"], "--branch", project_cfg["target_branch"],
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


def _scope_paths(plan_text: str) -> list[str]:
    """The `Scope and discretion` table's `touch`/`create`/`delete` paths; a `discretion` glob contributes nothing."""
    section = artefacts.parse(plan_text).section("Scope and discretion")
    rows = section.table() if section is not None else None
    return [row["path"] for row in (rows or []) if row.get("action") in ("touch", "create", "delete") and row.get("path")]


def _planned_reviewer_set(
    conn: sqlite3.Connection, ticket: sqlite3.Row, run_dir: Path, plan_text: str,
) -> tuple[Path, reviewer_sets.Derivation]:
    """Derive the planned reviewer set from the plan's own scope and write it for `handoff_ready --reviewer-set`."""
    owners_obj = owners.load_owners()
    identity = owners_obj.roles["plan_reviewer"]["identity"]
    derivation = reviewer_sets.derive_planned(
        conn,
        ticket_id=ticket["id"],
        repo_path=Path(ticket["worktree_path"]),
        target_base_sha=ticket["target_base_sha"],
        changed_paths=_scope_paths(plan_text),
        owners=owners_obj,
        sensitive_paths=exclusion.load_sensitive_paths(),
        authority_policy_hash=owners.authority_policy_hash(),
        membership_snapshot_hash=canonical.content_hash(owners.identity_snapshot(owners_obj, identity)),
    )
    path = run_dir / "reviewer_set.json"
    write_text(path, json.dumps([slot.to_json() for slot in derivation.slots], sort_keys=True))
    return path, derivation


def _questions_json(conn: sqlite3.Connection, ticket_id: int, run_dir: Path) -> Path:
    # A row a flag correction has superseded is left out: its replacement
    # already carries its state forward, so counting both would show the
    # readiness table one question it never actually had.
    rows = conn.execute(
        "SELECT id, state, blocking FROM question WHERE ticket_id = ? "
        "AND id NOT IN (SELECT supersedes FROM question WHERE supersedes IS NOT NULL)",
        (ticket_id,),
    ).fetchall()
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

    result = stages.invoke_agent(conn, ticket, "planning", runs_dir=runs_dir, parent_run_id=stage_run_id)
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
    reviewer_set_path, planned_derivation = _planned_reviewer_set(conn, ticket, run_dir, plan_text)
    if planned_derivation.sensitive:
        _record_check_result(
            conn, stage_run_id, check_name="exclusion", passed=False,
            detail=f"plan scope touches a sensitive path: {', '.join(planned_derivation.unresolved) or 'see reviewer_set.json'}",
        )
        exclusion.apply_recorded_exclusion(conn, ticket_id)
        return "fail"
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

    # (5b) the plan rubric's script-half findings, over the same version.
    # `unknown` on a public unit's compatibility field is checked ahead of
    # the ordinary findings: it is a bigger-picture pilot-exclusion signal,
    # not an in-place plan defect, so it takes the exclusion route even
    # when the rest of the rubric would otherwise pass.
    risk_map_doc = json.loads(risk_map_path.read_text()) if risk_map_path.is_file() else {"candidates": []}
    risk_map_candidate_count = sum(1 for c in risk_map_doc.get("candidates", []) if c.get("named"))
    project_config = project.pilot()
    # A row a flag correction has superseded is left out for the same
    # reason `_questions_json` above excludes one: the rubric should see
    # each question once, at its current classification.
    question_rows = conn.execute(
        "SELECT id, text, consequential, state, blocking FROM question WHERE ticket_id = ? "
        "AND id NOT IN (SELECT supersedes FROM question WHERE supersedes IS NOT NULL)",
        (ticket_id,),
    ).fetchall()
    limits = _limits_config()
    rubric_findings = plan_rubric.check(
        final_text, brief_text=brief_text, criteria_text=criteria_text, catalogue=recipes.load_catalogue(),
        project_recipes=project_config.get("recipes", []), questions=[dict(row) for row in question_rows],
        limits=limits, risk_map_candidate_count=risk_map_candidate_count,
    )
    rubric_outcome = _record_plan_rubric_result(
        conn, stage_run_id, findings=rubric_findings, extra_summary=plan_rubric.test_mix_report(
            artefacts.parse(final_text), limits=limits,
        ),
    )

    exclusion_reason = _contracts_exclusion_reason(final_text)
    if exclusion_reason is not None:
        _record_check_result(conn, stage_run_id, check_name="exclusion", passed=False, detail=exclusion_reason)
        exclusion.apply_recorded_exclusion(conn, ticket_id)
        return "fail"

    if rubric_outcome == "fail":
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
    plan_artefact_id = artefact_registry.register(
        conn, ticket_id=ticket_id, kind=ARTEFACT_KIND, path=working_path, stage_run_id=stage_run_id,
        supersedes=prior["id"] if prior is not None else None,
    )

    # (8) open the one plan_approval item this pass raises; the item
    # carries no subject of its own -- the plan tuple `queue.act` creates
    # once the bootstrap checklist completes is the subject a human
    # eventually approves.
    queue.open_item(
        conn, ticket_id=ticket_id, kind="plan_approval", stage="planning", tier=tier,
        ref=f"artefact:{plan_artefact_id}", reviewer_set_id=planned_derivation.id,
    )
    return "pass"
