"""The human review stage: the race guard, the freshness recheck, the checks-cleared check, then the packet assembly.

Script-only, run from the `checks` state alongside the checks stage (`PASS_EVENT`
stays `None`; `gates.checks_gate` admits to `review` once both this run and the
latest checks-stage run have passed). Every step below runs in order and stops the
run at the first failure: `reviewer_sets.recompute_before_dispatch` over the
current diff must still equal the review tuple's own `actual_reviewer_set_hash`
(the same actual diff a human or a merge could have moved since the checks
stage's own preflight bound it); `freshness.check` at `BEFORE_DISPATCH` must find the
base and the pending pull-request intent unmoved; the review tuple's own
checks-stage run must still be the ticket's latest checks-stage attempt and every
one of its blocking results must be `pass` or a validly waived `blind_spot`. Only
then does this run gather `packet_inputs.json` from the record and the
registered artefacts -- never from agent prose -- write the diff, run the
two standalone assembly scripts, register the `packet` and `pr_body`
artefacts, and open one `packet_approval` item naming the packet.
"""
import fnmatch
import json
import re
import sqlite3
import subprocess
from pathlib import Path

from runner import (
    artefact_registry, artefacts, canonical, checklist, freshness, owners, project, publication, queue, record,
    recipes, reviewer_sets, waivers,
)
from runner.checks import exclusion
from runner.fs import write_text
from runner.paths import REPO_ROOT, RUNS_DIR
from runner.stages import implementation, checks

ARTEFACT_KIND = "packet"
PR_BODY_ARTEFACT_KIND = "pr_body"
PASS_EVENT = None

# `freshness.check`'s own `BEFORE_DISPATCH` reason when the ticket carries no pending
# pull-request intent yet -- true of every ticket the first time its packet is assembled,
# since that intent is only created once `packet_approval` itself reaches quorum. This
# recheck exists to catch a base or subject that moved out from under an *existing* pending
# intent; a ticket with none yet has nothing to catch, so this one reason alone never blocks.
_NO_PENDING_INTENT_REASON = "no pending pull-request intent to check"

PACKET_ASSEMBLE_SCRIPT = REPO_ROOT / "factory" / "scripts" / "tools" / "packet_assemble"
PR_BODY_ASSEMBLE_SCRIPT = REPO_ROOT / "factory" / "scripts" / "tools" / "pr_body_assemble"



def _tier(ticket: sqlite3.Row) -> str:
    return ticket["tier_final"] or ticket["tier_provisional"] or "standard"


def _run_dir(runs_dir: Path, ticket_id: int, stage_run_id: int) -> Path:
    return Path(runs_dir) / "tickets" / str(ticket_id) / "runs" / str(stage_run_id)


def _record_check_result(
    conn: sqlite3.Connection, stage_run_id: int, *, check_name: str, result: str, summary: str,
) -> int:
    row = {
        "stage_run_id": stage_run_id, "check_name": check_name, "check_tier": "blocking", "source": "runner",
        "result": result, "summary": summary, "canonical_serialization_version": canonical.SERIALIZATION_VERSION,
    }
    row["content_hash"] = canonical.content_hash(row)
    return record.insert(conn, "check_result", **row)


def _latest_review_tuple(conn: sqlite3.Connection, ticket_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM evidence_tuple WHERE ticket_id = ? AND kind = 'review' ORDER BY id DESC LIMIT 1", (ticket_id,)
    ).fetchone()


def _latest_checks_run(conn: sqlite3.Connection, ticket_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM stage_run WHERE ticket_id = ? AND stage = 'checks' AND parent_run_id IS NULL ORDER BY id DESC LIMIT 1",
        (ticket_id,),
    ).fetchone()


def _checks_run_for_review_tuple(conn: sqlite3.Connection, review_tuple_id: int) -> int | None:
    """The one `stage_run` whose `check_result` rows bind `review_tuple_id` -- the checks
    stage's preflight that created it, since every check that run wrote names this same tuple."""
    row = conn.execute(
        "SELECT stage_run_id FROM check_result WHERE evidence_tuple_id = ? AND stage_run_id IS NOT NULL LIMIT 1",
        (review_tuple_id,),
    ).fetchone()
    return row["stage_run_id"] if row is not None else None


def _race_guard(
    conn: sqlite3.Connection, ticket: sqlite3.Row, stage_run_id: int, *, review_tuple: sqlite3.Row, plan_row: sqlite3.Row,
    repo: Path,
) -> bool:
    """`reviewer_sets.recompute_before_dispatch` over the current diff; True when unmoved.

    Reuses the authority-policy and membership-snapshot hashes the bound
    `actual` reviewer set already recorded, rather than taking a fresh
    membership snapshot: `identity_snapshot` stamps its own `taken_at`, so
    a fresh one would report a "moved" set on every call, whether or not
    the diff or CODEOWNERS resolution actually changed since the checks stage's own
    preflight bound it. The race guard's job is to catch that real
    movement, not the mere passage of time.
    """
    diff_paths = checks._diff_touched_paths(repo, plan_row["base_sha"], ticket["head_sha"])
    owners_obj = owners.load_owners()
    bound_actual = record.get(conn, "reviewer_set", review_tuple["actual_reviewer_set_id"])
    actual = reviewer_sets.recompute_before_dispatch(
        conn, ticket_id=ticket["id"], repo_path=repo, target_base_sha=ticket["target_base_sha"],
        changed_paths=diff_paths, owners=owners_obj, sensitive_paths=exclusion.load_sensitive_paths(),
        authority_policy_hash=bound_actual["owner_config_hash"],
        membership_snapshot_hash=bound_actual["membership_snapshot_hash"],
    )
    new_hash = record.get(conn, "reviewer_set", actual.id)["content_hash"]
    if new_hash == review_tuple["actual_reviewer_set_hash"]:
        return True
    _record_check_result(
        conn, stage_run_id, check_name="race_guard", result="fail",
        summary=f"actual reviewer set moved: {review_tuple['actual_reviewer_set_hash']} -> {new_hash}",
    )
    return False


def _split_intent_and_scrutiny(section_text: str) -> tuple[str, str]:
    """The plan's `Intent and scrutiny` prose, split on the first `Scrutiny:` marker.

    A plan that never wrote the marker leaves `scrutiny` empty rather than
    guessing where intent ends -- this driver authors no prose of its own.
    """
    match = re.search(r"Scrutiny:", section_text, re.IGNORECASE)
    if match is None:
        return section_text.strip(), ""
    return section_text[: match.start()].strip(), section_text[match.start():].strip()


def _non_goal_lines(section_text: str) -> list[str]:
    return [
        segment.strip() for segment in re.split(r"(?<=[.!?])\s+", section_text)
        if segment.strip().lower().startswith("non-goal")
    ]


def _changed_contract_rows(plan: artefacts.Artefact) -> list[dict]:
    section = plan.section("Contracts")
    rows = section.table() if section is not None else None
    changed = []
    for row in (rows or []):
        for field in artefacts.CONTRACT_FIELDS:
            try:
                state, _ = artefacts.contract_cell(row.get(field))
            except artefacts.ArtefactError:
                continue
            if state == "changed":
                changed.append(row)
                break
    return changed


def _untouched_scope_rows(plan: artefacts.Artefact, diff_paths: list[str]) -> list[dict]:
    section = plan.section("Scope and discretion")
    rows = section.table() if section is not None else None
    untouched = []
    for row in (rows or []):
        path = (row.get("path") or "").strip()
        action = (row.get("action") or "").strip()
        touched = any(fnmatch.fnmatch(p, path) for p in diff_paths) if action == "discretion" else path in diff_paths
        if not touched:
            untouched.append(row)
    return untouched

def _checklist_verdicts_payload(conn: sqlite3.Connection, ticket_id: int) -> list[dict]:
    return [
        {
            "line": row["rubric_line_id"], "verdict": row["verdict"],
            "evidence_ids": json.loads(row["evidence_ids"]) if row.get("evidence_ids") else [],
        }
        for row in checklist.verdict_set(conn, ticket_id)
    ]


def _plan_sections_payload(conn: sqlite3.Connection, ticket_id: int, plan: artefacts.Artefact, diff_paths: list[str]) -> dict:
    intent_scrutiny = plan.section("Intent and scrutiny")
    intent, scrutiny = _split_intent_and_scrutiny(intent_scrutiny.body if intent_scrutiny is not None else "")
    non_goals_section = plan.section("Goals and non-goals")
    alternatives_section = plan.section("Alternatives")
    risk_map_section = plan.section("Risk map")
    return {
        "intent": intent,
        "scrutiny": scrutiny,
        "alternatives": (alternatives_section.table() if alternatives_section is not None else None) or [],
        "contracts_changed": _changed_contract_rows(plan),
        "non_goals": _non_goal_lines(non_goals_section.body if non_goals_section is not None else ""),
        "scope_rows": _untouched_scope_rows(plan, diff_paths),
        "risk_map": (risk_map_section.table() if risk_map_section is not None else None) or [],
        "checklist_verdicts": _checklist_verdicts_payload(conn, ticket_id),
    }


def _test_globs(project_recipes: list[str], catalogue: dict) -> list[str]:
    return sorted({
        glob for recipe_id in project_recipes if recipe_id in catalogue and catalogue[recipe_id].kind == "test"
        for glob in (catalogue[recipe_id].test_globs or ())
    })


def _test_summary_payload(plan: artefacts.Artefact, diff_paths: list[str], test_globs: list[str]) -> dict:
    section = plan.section("Test strategy")
    strategy_rows = (section.table() if section is not None else None) or []
    diff_test_files = [path for path in diff_paths if any(fnmatch.fnmatch(path, pattern) for pattern in test_globs)]
    return {"strategy_rows": strategy_rows, "diff_test_files": diff_test_files}


def _checks_payload(conn: sqlite3.Connection, checks_run_id: int) -> list[dict]:
    entries = []
    for status_entry in waivers.blocking_status(conn, checks_run_id):
        row = record.get(conn, "check_result", status_entry["id"])
        evidence_hash = None
        if row["evidence_artefact"] is not None:
            artefact_row = record.get(conn, "artefact", row["evidence_artefact"])
            evidence_hash = artefact_row["hash"] if artefact_row is not None else None
        entries.append({
            "id": row["id"], "check_name": row["check_name"], "result": row["result"], "status": status_entry["status"],
            "content_hash": row["content_hash"], "waiver_id": status_entry["waiver_id"],
            "evidence_artefact_hash": evidence_hash, "summary": row["summary"],
        })
    return entries


def _fix_round_recipes_cleared(conn: sqlite3.Connection, ticket_id: int, fix_round_run_id: int) -> list[str]:
    """The recipe ids named in the `task_validation` check results of the `validation_only`
    run that immediately followed this fix round -- the runner's own post-hand-back
    validation pass, the nearest thing this schema carries to "what a round cleared"."""
    validation_run = conn.execute(
        "SELECT id FROM stage_run WHERE ticket_id = ? AND stage = 'implementation' AND run_kind = 'validation_only' AND id > ? "
        "ORDER BY id LIMIT 1",
        (ticket_id, fix_round_run_id),
    ).fetchone()
    if validation_run is None:
        return []
    rows = conn.execute(
        "SELECT summary FROM check_result WHERE stage_run_id = ? AND check_name = 'task_validation'",
        (validation_run["id"],),
    ).fetchall()
    return [row["summary"].split(":", 1)[0] for row in rows if row["summary"]]


def _fix_rounds_payload(conn: sqlite3.Connection, ticket_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM stage_run WHERE ticket_id = ? AND stage = 'implementation' AND run_kind = 'fix_round' AND outcome = 'pass' "
        "ORDER BY id",
        (ticket_id,),
    ).fetchall()
    return [
        {
            "stage_run_id": row["id"], "started_at": row["started_at"],
            "recipes_cleared": _fix_round_recipes_cleared(conn, ticket_id, row["id"]),
        }
        for row in rows
    ]


def _base_test_change_diff(repo: Path, base_sha: str, head_sha: str, path: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), "diff", base_sha, head_sha, "--", path], capture_output=True, text=True, check=True,
    )
    return completed.stdout


def _base_test_changes_payload(conn: sqlite3.Connection, ticket_id: int, *, repo: Path, base_sha: str, head_sha: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM deviation WHERE ticket_id = ? AND why = ? ORDER BY id", (ticket_id, implementation.BASE_TEST_DEVIATION_WHY),
    ).fetchall()
    entries = []
    for row in rows:
        action, _, path = row["agent_did"].partition(" ")
        diff_text = _base_test_change_diff(repo, base_sha, head_sha, path)
        entries.append({
            "deviation_id": row["id"], "path": path, "action": action, "plan_item": row["plan_item"],
            "diff_hash": canonical.content_hash({"diff": diff_text}), "diff": diff_text,
        })
    return entries


def _readiness_payload(plan: artefacts.Artefact) -> list[dict]:
    section = plan.section("Readiness")
    return (section.table() if section is not None else None) or []


def _approvals_payload(conn: sqlite3.Connection, review_tuple: sqlite3.Row) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM approval_record WHERE gate = 'plan' AND subject_hash = "
        "(SELECT content_hash FROM evidence_tuple WHERE id = ?) ORDER BY id",
        (review_tuple["plan_tuple_id"],),
    ).fetchall()
    return [
        {
            "id": row["id"], "gate": row["gate"], "slot_id": row["slot_id"], "actor_identity": row["actor_identity"],
            "role": row["role"], "decision": row["decision"], "decided_at": row["decided_at"],
            "expires_at": row["expires_at"], "content_hash": row["content_hash"],
        }
        for row in rows
    ]


def _waivers_payload(conn: sqlite3.Connection, review_tuple: sqlite3.Row) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM waiver WHERE subject_kind = 'review_tuple' AND subject_hash = ? ORDER BY id",
        (review_tuple["content_hash"],),
    ).fetchall()
    return [
        {
            "id": row["id"], "policy_id": row["policy_id"], "policy_version": row["policy_version"],
            "subject_kind": row["subject_kind"], "scope": row["scope"], "expires_at": row["expires_at"],
            "waived_check_result_id": row["waived_check_result_id"], "waived_human_verdict_id": row["waived_human_verdict_id"],
            "content_hash": row["content_hash"],
        }
        for row in rows
    ]


def _deviations_payload(conn: sqlite3.Connection, ticket_id: int) -> list[dict]:
    rows = conn.execute("SELECT * FROM deviation WHERE ticket_id = ? ORDER BY id", (ticket_id,)).fetchall()
    return [
        {
            "plan_item": row["plan_item"], "plan_said": row["plan_said"], "agent_did": row["agent_did"],
            "why": row["why"], "kind": row["kind"], "contract_change": bool(row["contract_change"]),
        }
        for row in rows
    ]


def _assumptions_payload(conn: sqlite3.Connection, ticket_id: int) -> list[dict]:
    """The current assumption set: every row no later row supersedes and no row withdraws."""
    rows = conn.execute("SELECT * FROM assumption WHERE ticket_id = ? ORDER BY id", (ticket_id,)).fetchall()
    superseded = {row["supersedes"] for row in rows if row["supersedes"] is not None}
    return [
        {"id": row["id"], "text": row["text"], "origin": row["origin"], "created_at": row["created_at"]}
        for row in rows if row["id"] not in superseded and not row["withdrawn"]
    ]


def _blind_spots_payload(conn: sqlite3.Connection, ticket_id: int, plan: artefacts.Artefact) -> list[dict]:
    """Every plan `Readiness` row marked `blind_spot`, and every `Contracts` cell marked `unknown`."""
    spots = []
    readiness = plan.section("Readiness")
    for row in (readiness.table() if readiness is not None else None) or []:
        if row.get("status") == "blind_spot":
            spots.append({
                "kind": "declaration", "text": f"{row.get('condition')}: {row.get('note') or ''}".strip(": "),
                "source_artefact": row.get("source_artefact"), "hash": row.get("hash"),
            })
    contracts = plan.section("Contracts")
    for row in (contracts.table() if contracts is not None else None) or []:
        for field in artefacts.CONTRACT_FIELDS:
            cell = (row.get(field) or "").strip()
            if cell.split(":", 1)[0].strip() == "unknown":
                spots.append({
                    "kind": "behaviour_limitation", "text": f"{row.get('unit')}.{field}: {cell}",
                    "source_artefact": "plan:Contracts", "hash": None,
                })
    return spots


def _artefacts_payload(conn: sqlite3.Connection, ticket_id: int) -> dict:
    payload = {}
    for kind in ("brief", "criteria", "plan", "check_evidence"):
        row = artefact_registry.latest(conn, ticket_id, kind)
        payload[kind] = {"id": row["id"], "path": row["path"], "hash": row["hash"]} if row is not None else None
    return payload


def _gather_packet_inputs(
    conn: sqlite3.Connection, ticket: sqlite3.Row, *, review_tuple: sqlite3.Row, plan_row: sqlite3.Row,
    checks_run_id: int, fresh: freshness.Freshness, repo: Path, run_dir: Path,
) -> dict:
    ticket_id = ticket["id"]
    plan_artefact = artefact_registry.latest(conn, ticket_id, "plan")
    plan_text = Path(plan_artefact["path"]).read_text()
    plan = artefacts.parse(plan_text)

    diff_paths = checks._diff_touched_paths(repo, plan_row["base_sha"], review_tuple["head_sha"])
    diff_path = run_dir / "diff.patch"
    diff_text = subprocess.run(
        ["git", "-C", str(repo), "diff", plan_row["base_sha"], review_tuple["head_sha"]],
        capture_output=True, text=True, check=True,
    ).stdout
    write_text(diff_path, diff_text)

    project_cfg = project.pilot()
    catalogue = recipes.load_catalogue()
    test_globs = _test_globs([r for r in (project_cfg.get("recipes") or []) if r], catalogue)

    return {
        "ticket": {
            "id": ticket_id, "title": ticket["title"], "service": ticket["service"], "ticket_type": ticket["ticket_type"],
            "tier": _tier(ticket),
        },
        "identity": {
            "review_tuple_id": review_tuple["id"], "review_tuple_hash": review_tuple["content_hash"],
            "plan_tuple_id": plan_row["id"], "plan_tuple_hash": plan_row["content_hash"],
            "base_sha": plan_row["base_sha"], "head_sha": review_tuple["head_sha"],
            "target_base_sha": review_tuple["target_base_sha"], "manifest_hash": review_tuple["manifest_hash"],
            "diff_hash": review_tuple["diff_hash"], "deviation_set_hash": review_tuple["deviation_set_hash"],
            "effective_reviewer_set_hash": review_tuple["effective_reviewer_set_hash"],
        },
        "freshness": {
            "fresh": fresh.fresh, "boundary": fresh.boundary, "target_head_sha": fresh.fetched_target_head,
            "checked_at": record.now(), "reasons": list(fresh.reasons),
        },
        "artefacts": _artefacts_payload(conn, ticket_id),
        "checks": _checks_payload(conn, checks_run_id),
        "fix_rounds": _fix_rounds_payload(conn, ticket_id),
        "base_test_changes": _base_test_changes_payload(
            conn, ticket_id, repo=repo, base_sha=plan_row["base_sha"], head_sha=review_tuple["head_sha"],
        ),
        "readiness": _readiness_payload(plan),
        "approvals": _approvals_payload(conn, review_tuple),
        "waivers": _waivers_payload(conn, review_tuple),
        "deviations": _deviations_payload(conn, ticket_id),
        "assumptions": _assumptions_payload(conn, ticket_id),
        "blind_spots": _blind_spots_payload(conn, ticket_id, plan),
        "test_summary": _test_summary_payload(plan, diff_paths, test_globs),
        "plan_sections": _plan_sections_payload(conn, ticket_id, plan, diff_paths),
        "diff_path": str(diff_path),
    }


def _assemble(script: Path, inputs_path: Path, out_path: Path) -> tuple[bool, str]:
    completed = subprocess.run(
        [str(script), "--inputs", str(inputs_path), "--out", str(out_path)], capture_output=True, text=True,
    )
    return completed.returncode == 0, completed.stderr.strip()


def run(conn: sqlite3.Connection, ticket: sqlite3.Row, stage_run_id: int, runs_dir: Path = RUNS_DIR) -> str | tuple[str, str]:
    ticket_id = ticket["id"]
    run_dir = _run_dir(runs_dir, ticket_id, stage_run_id)
    repo = checks._repo(runs_dir, ticket_id)

    review_tuple = _latest_review_tuple(conn, ticket_id)
    if review_tuple is None:
        _record_check_result(
            conn, stage_run_id, check_name="review_tuple_missing", result="fail",
            summary="no review tuple is recorded for this ticket",
        )
        return "fail", "stale_binding"
    plan_row = record.get(conn, "evidence_tuple", review_tuple["plan_tuple_id"])

    if not _race_guard(conn, ticket, stage_run_id, review_tuple=review_tuple, plan_row=plan_row, repo=repo):
        return "fail", "stale_binding"

    fresh = freshness.check(
        conn, ticket_id, boundary=freshness.BEFORE_DISPATCH, target_branch=freshness.target_branch(), runs_dir=runs_dir,
    )
    if not fresh.fresh and tuple(fresh.reasons) != (_NO_PENDING_INTENT_REASON,):
        return "fail", "stale_binding"

    latest_checks = _latest_checks_run(conn, ticket_id)
    bound_checks_run_id = _checks_run_for_review_tuple(conn, review_tuple["id"])
    if (
        latest_checks is None or bound_checks_run_id is None or bound_checks_run_id != latest_checks["id"]
        or not waivers.cleared(conn, bound_checks_run_id)
    ):
        _record_check_result(
            conn, stage_run_id, check_name="checks_not_cleared", result="fail",
            summary="the review tuple's checks-stage run is not the ticket's latest checks-stage run, or is not cleared",
        )
        return "fail"

    inputs = _gather_packet_inputs(
        conn, ticket, review_tuple=review_tuple, plan_row=plan_row, checks_run_id=bound_checks_run_id, fresh=fresh, repo=repo,
        run_dir=run_dir,
    )
    inputs_path = run_dir / "packet_inputs.json"
    write_text(inputs_path, json.dumps(inputs, sort_keys=True))

    packet_path = run_dir / "packet.md"
    packet_ok, packet_error = _assemble(PACKET_ASSEMBLE_SCRIPT, inputs_path, packet_path)
    if not packet_ok:
        _record_check_result(conn, stage_run_id, check_name="packet_assemble", result="fail", summary=packet_error)
        return "fail"

    pr_body_path = run_dir / "pr_body.md"
    pr_body_ok, pr_body_error = _assemble(PR_BODY_ASSEMBLE_SCRIPT, inputs_path, pr_body_path)
    if not pr_body_ok:
        _record_check_result(conn, stage_run_id, check_name="pr_body_assemble", result="fail", summary=pr_body_error)
        return "fail"

    prior_packet = artefact_registry.latest(conn, ticket_id, ARTEFACT_KIND)
    packet_id = artefact_registry.register(
        conn, ticket_id=ticket_id, kind=ARTEFACT_KIND, path=packet_path, stage_run_id=stage_run_id,
        supersedes=prior_packet["id"] if prior_packet is not None else None,
    )
    prior_pr_body = artefact_registry.latest(conn, ticket_id, PR_BODY_ARTEFACT_KIND)
    artefact_registry.register(
        conn, ticket_id=ticket_id, kind=PR_BODY_ARTEFACT_KIND, path=pr_body_path, stage_run_id=stage_run_id,
        supersedes=prior_pr_body["id"] if prior_pr_body is not None else None,
    )

    _record_check_result(
        conn, stage_run_id, check_name="packet_assemble", result="pass",
        summary=json.dumps({"packet_artefact_id": packet_id}, sort_keys=True),
    )

    open_item = conn.execute(
        "SELECT id FROM queue_item WHERE ticket_id = ? AND kind = 'packet_approval' AND resolved_at IS NULL",
        (ticket_id,),
    ).fetchone()
    if open_item is None:
        # The packet and `pr_body` artefacts just registered above are what
        # `review_approval_subject` reads back as this ticket's latest --
        # the subject a required final-review slot approves is therefore
        # exactly what this run assembled, never an artefact from a prior
        # attempt still on record when this one started.
        subject = publication.review_approval_subject(conn, ticket_id)
        queue.open_item(
            conn, ticket_id=ticket_id, kind="packet_approval", reviewer_set_id=review_tuple["effective_reviewer_set_id"],
            approval_subject_hash=subject.hash, ref=f"artefact:{packet_id}",
        )
    return "pass"
