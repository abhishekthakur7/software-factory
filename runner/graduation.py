"""The graduation gate: a canonical report over a candidate window, and the recorded owner approval that binds it.

`evaluate` never decides anything by itself: it reads the record through
the measure views and the tables no view covers, writes one
`graduation_report` artefact holding every clause's inputs and verdict, and
finishes its own `utility_run` `pass` or `fail` by whether every clause
passed. Meeting every threshold only makes the report eligible for a
human decision -- `approve` (and `reject`, the same function under a
different decision) is the sole writer of the `approval_record` that binds
it, refusing outright rather than recording a decision against a report
that no longer matches the actor, the proposed configuration, or the
manifest currently in force. A second approval from the same actor on the
same subject supersedes its own earlier head, so repeating a decision
(the common case: an owner approves, the report is re-run and re-approved
under the same configuration) never counts as two independent actors and
never trips `approvals.forked_heads`.

The candidate window excludes every context measure by construction: it is
built once, from the ticket, tag, incident and approval rows the clause
functions below read directly or through
`stage_reliability_view`, `v_revisions_per_ticket_by_fm`,
`v_production_incidents_attributable`, `v_reconstruction_share_by_gate` and
`v_baseline_revisions_per_ticket`, and never through `v_default_shown_share`,
`v_default_accepted_share`, `v_plan_approved_no_redirect_share`, or any
`v_ctx_` view -- those are read once, separately, into the report's own
`context` block, for a human to read alongside the verdict rather than for
any clause to act on.
"""
import hashlib
import json
import sqlite3
from pathlib import Path

import yaml

from runner import approvals, artefact_registry, canonical, manifest, owners, record, run_ledger, tags, waivers
from runner.fs import write_text
from runner.paths import FACTORY_DIR, REPO_ROOT, RUNS_DIR
from runner.reviewer_sets import Slot

DEFAULT_LIMITS_PATH = FACTORY_DIR / "config" / "limits.yaml"

# The Initial stages the stage-reliability clause grades; merge is not yet a
# stage any driver runs, so `stage_reliability_view` never carries it.
_STAGES = ("intake", "context_gathering", "clarification", "planning", "implementation", "checks", "human_review")

# The named views a clause reads for its verdict, exactly as it queries
# them -- never `v_default_shown_share`, `v_default_accepted_share`,
# `v_plan_approved_no_redirect_share`, or any `v_ctx_` view, which the
# report's `context` block reads separately and no clause below touches.
VIEWS_READ: tuple[str, ...] = (
    "stage_reliability_view",
    "v_baseline_revisions_per_ticket",
    "v_production_incidents_attributable",
    "v_reconstruction_share_by_gate",
    "v_revisions_per_ticket_by_fm",
)

# The context measures carried into the report for information only.
_CONTEXT_VIEWS: tuple[str, ...] = (
    "v_ctx_completions_outcomes_per_window",
    "v_ctx_cost_per_ticket",
    "v_ctx_non_structural_touchpoints",
    "v_ctx_fix_rounds_per_ticket",
    "v_ctx_tool_calls_bytes_per_stage_run",
)

GRADUATION_ROLE = "factory_owner"
ATTESTATION_VERSION = "graduation-v1"


class GraduationRefused(ValueError):
    """A graduation `approve`/`reject` call fails validation before any row is written."""


def _load_limits(limits_path: Path) -> dict:
    doc = yaml.safe_load(Path(limits_path).read_text())
    return dict(doc["graduation"])


def _display_path(path: Path) -> str:
    resolved = Path(path).resolve()
    try:
        return str(resolved.relative_to(REPO_ROOT))
    except ValueError:
        return str(resolved)


def _placeholders(values: list) -> str:
    return ",".join("?" for _ in values)


def _context_block(conn: sqlite3.Connection) -> dict:
    return {view: [dict(row) for row in conn.execute(f"SELECT * FROM {view}").fetchall()] for view in _CONTEXT_VIEWS}


def window(conn: sqlite3.Connection, limits: dict, *, cutoff: str) -> dict:
    """The candidate window: every non-baseline `merged`/`abandoned` ticket closed in `[start, cutoff]`.

    `start` is the later of the previous graduation *approve* record's
    `decided_at` and the landing time of the newest `remediated`
    disposition over a severe, attributable `production_incident_event`.
    An open severe attributable incident (its latest disposition is not
    `remediated`) overrides everything else: the window is empty and
    `reset_pending` is true, since nothing before that incident's
    remediation may count toward graduation.
    """
    threshold = limits["window_min_outcomes"]
    severe = sorted(set(limits["severe_severities"]))

    prior_approval = conn.execute(
        "SELECT decided_at FROM approval_record WHERE gate = 'graduation' AND decision = 'approve' "
        "ORDER BY decided_at DESC, id DESC LIMIT 1"
    ).fetchone()
    prior_at = prior_approval["decided_at"] if prior_approval is not None else None

    severe_events = conn.execute(
        f"SELECT id FROM incident_observation WHERE record_kind = 'production_incident_event' "
        f"AND severity IN ({_placeholders(severe)})", severe,
    ).fetchall() if severe else []

    reset_pending = False
    remediated_ats: list[str] = []
    for event in severe_events:
        latest_disposition = conn.execute(
            "SELECT * FROM incident_observation WHERE record_kind = 'production_disposition' "
            "AND event_id = ? ORDER BY id DESC LIMIT 1", (event["id"],),
        ).fetchone()
        if latest_disposition is None or latest_disposition["attribution"] != "attributable":
            continue
        if latest_disposition["disposition"] == "remediated":
            remediated_ats.append(latest_disposition["created_at"])
        else:
            reset_pending = True

    if reset_pending:
        return {
            "passed": False,
            "inputs": {
                "start": None, "cutoff": cutoff, "ticket_ids": [], "reset_pending": True,
                "manifest_hashes": [], "eligible_count": 0, "window_min_outcomes": threshold,
            },
            "reasons": ["severe_attributable_incident_unremediated"],
        }

    candidates = [value for value in (prior_at, max(remediated_ats) if remediated_ats else None) if value is not None]
    start = max(candidates) if candidates else None

    query = "SELECT id FROM ticket WHERE (baseline IS NOT 1) AND close_reason IN ('merged', 'abandoned') AND closed_at <= ?"
    params: list = [cutoff]
    if start is not None:
        query += " AND closed_at >= ?"
        params.append(start)
    ticket_ids = sorted(row["id"] for row in conn.execute(query, params).fetchall())

    manifest_hashes: list[str] = []
    if ticket_ids:
        manifest_hashes = sorted({
            row["manifest_hash"] for row in conn.execute(
                f"SELECT DISTINCT manifest_hash FROM v_ticket_manifest_cohorts WHERE ticket_id IN "
                f"({_placeholders(ticket_ids)})", ticket_ids,
            ).fetchall()
            if row["manifest_hash"] is not None
        })

    passed = len(ticket_ids) >= threshold
    return {
        "passed": passed,
        "inputs": {
            "start": start, "cutoff": cutoff, "ticket_ids": ticket_ids, "reset_pending": False,
            "manifest_hashes": manifest_hashes, "eligible_count": len(ticket_ids), "window_min_outcomes": threshold,
        },
        "reasons": [] if passed else [f"insufficient_outcomes:{len(ticket_ids)}<{threshold}"],
    }


def acceptance_gates(conn: sqlite3.Connection, ticket_ids: list[int], manifest_hash: str) -> dict:
    """The latest `gate`-kind `utility_run` under `manifest_hash` passed, and the window saw a completion."""
    latest_gate_run = conn.execute(
        "SELECT * FROM utility_run WHERE kind = 'gate' AND manifest_hash = ? ORDER BY id DESC LIMIT 1",
        (manifest_hash,),
    ).fetchone()
    gate_passed = latest_gate_run is not None and latest_gate_run["outcome"] == "pass"

    completed_count = 0
    if ticket_ids:
        completed_count = conn.execute(
            f"SELECT COUNT(*) AS n FROM ticket WHERE id IN ({_placeholders(ticket_ids)}) "
            f"AND factory_completed_at IS NOT NULL", ticket_ids,
        ).fetchone()["n"]

    reasons = []
    if not gate_passed:
        reasons.append("no_passing_gate_run")
    if not completed_count:
        reasons.append("no_completed_ticket_with_recorded_outcome")
    return {
        "passed": not reasons,
        "inputs": {
            "manifest_hash": manifest_hash,
            "latest_gate_run_id": latest_gate_run["id"] if latest_gate_run is not None else None,
            "latest_gate_outcome": latest_gate_run["outcome"] if latest_gate_run is not None else None,
            "completed_ticket_count": completed_count,
        },
        "reasons": reasons,
    }


def exposure_coverage(conn: sqlite3.Connection, ticket_ids: list[int], cutoff: str) -> dict:
    """Every merged window ticket is demonstrably exposed and explicitly `none_observed` through `cutoff`."""
    merged_ids = sorted(
        row["id"] for row in conn.execute(
            f"SELECT id FROM ticket WHERE id IN ({_placeholders(ticket_ids)}) AND close_reason = 'merged'",
            ticket_ids,
        ).fetchall()
    ) if ticket_ids else []

    coverage_by_ticket = {
        row["ticket_id"]: row
        for row in conn.execute("SELECT * FROM v_production_incidents_attributable WHERE record_type = 'coverage'").fetchall()
    }

    missing_exposure: list[int] = []
    missing_coverage: list[int] = []
    for ticket_id in merged_ids:
        coverage = coverage_by_ticket.get(ticket_id)
        if coverage is None or coverage["exposure_start"] is None or coverage["exposure_source"] is None:
            missing_exposure.append(ticket_id)
            continue
        covered_through_cutoff = (
            coverage["coverage_status"] == "none_observed"
            and coverage["observed_through"] is not None
            and coverage["observed_through"] >= cutoff
        )
        if not covered_through_cutoff:
            missing_coverage.append(ticket_id)

    reasons = []
    if missing_exposure:
        reasons.append(f"no_recorded_exposure:{missing_exposure}")
    if missing_coverage:
        reasons.append(f"no_coverage_through_cutoff:{missing_coverage}")
    return {
        "passed": not reasons,
        "inputs": {
            "merged_ticket_ids": merged_ids, "cutoff": cutoff,
            "missing_exposure_ticket_ids": missing_exposure, "missing_coverage_ticket_ids": missing_coverage,
        },
        "reasons": reasons,
    }


def incidents(conn: sqlite3.Connection, ticket_ids: list[int], limits: dict) -> dict:
    """No window incident is a severe, attributable production event, and every one carries a full disposition."""
    severe = set(limits["severe_severities"])
    severe_attributable: list[int] = []
    missing_disposition: list[int] = []

    if ticket_ids:
        events = conn.execute(
            f"SELECT * FROM incident_observation WHERE record_kind = 'production_incident_event' "
            f"AND ticket_id IN ({_placeholders(ticket_ids)})", ticket_ids,
        ).fetchall()
        for event in events:
            latest_disposition = conn.execute(
                "SELECT * FROM incident_observation WHERE record_kind = 'production_disposition' "
                "AND event_id = ? ORDER BY id DESC LIMIT 1", (event["id"],),
            ).fetchone()
            if (
                latest_disposition is None
                or latest_disposition["attribution"] is None
                or latest_disposition["disposition"] is None
            ):
                missing_disposition.append(event["id"])
            if (
                event["severity"] in severe
                and latest_disposition is not None
                and latest_disposition["attribution"] == "attributable"
            ):
                severe_attributable.append(event["id"])

    aggregate = [
        dict(row) for row in conn.execute(
            "SELECT * FROM v_production_incidents_attributable WHERE record_type = 'incident'"
        ).fetchall()
    ]

    reasons = []
    if severe_attributable:
        reasons.append(f"severe_attributable_incident_in_window:{sorted(severe_attributable)}")
    if missing_disposition:
        reasons.append(f"incident_missing_attribution_or_disposition:{sorted(missing_disposition)}")
    return {
        "passed": not reasons,
        "inputs": {
            "severe_attributable_event_ids": sorted(severe_attributable),
            "missing_disposition_event_ids": sorted(missing_disposition),
            "aggregate_attributable_rows": aggregate,
        },
        "reasons": reasons,
    }


def stage_reliability(conn: sqlite3.Connection, limits: dict, manifest_hash: str) -> dict:
    """Every Initial stage clears `stage_min_first_attempts` eligible runs with a pass share above `stage_min_pass_share`."""
    min_first_attempts = limits["stage_min_first_attempts"]
    min_pass_share = limits["stage_min_pass_share"]

    per_stage: dict[str, dict] = {}
    failing: list[str] = []
    for stage in _STAGES:
        rows = conn.execute(
            "SELECT eligible_count, passed_count FROM stage_reliability_view WHERE manifest_hash = ? AND stage = ?",
            (manifest_hash, stage),
        ).fetchall()
        eligible = sum(row["eligible_count"] for row in rows)
        passed_count = sum(row["passed_count"] for row in rows)
        pass_share = (passed_count / eligible) if eligible else None
        stage_ok = eligible >= min_first_attempts and pass_share is not None and pass_share > min_pass_share
        per_stage[stage] = {
            "eligible_count": eligible, "passed_count": passed_count, "pass_share": pass_share, "passed": stage_ok,
        }
        if not stage_ok:
            failing.append(stage)

    excluded: dict[str, dict] = {}
    for stage in _STAGES:
        row = conn.execute(
            "SELECT "
            "SUM(CASE WHEN outcome = 'blocked' THEN 1 ELSE 0 END) AS blocked, "
            "SUM(CASE WHEN outcome = 'refused' THEN 1 ELSE 0 END) AS refused, "
            "SUM(CASE WHEN outcome = 'aborted_human' THEN 1 ELSE 0 END) AS aborted_human, "
            "SUM(CASE WHEN parent_run_id IS NOT NULL THEN 1 ELSE 0 END) AS child_runs, "
            "SUM(CASE WHEN run_kind != 'task' THEN 1 ELSE 0 END) AS non_task_run_kind "
            "FROM stage_run WHERE manifest_hash = ? AND stage = ?", (manifest_hash, stage),
        ).fetchone()
        excluded[stage] = {key: (row[key] or 0) for key in row.keys()}
    excluded["utility_runs"] = conn.execute(
        "SELECT COUNT(*) AS n FROM utility_run WHERE manifest_hash = ?", (manifest_hash,)
    ).fetchone()["n"]

    return {
        "passed": not failing,
        "inputs": {
            "per_stage": per_stage, "excluded": excluded,
            "stage_min_first_attempts": min_first_attempts, "stage_min_pass_share": min_pass_share,
        },
        "reasons": [f"stage_below_threshold:{stage}" for stage in failing],
    }


def baseline_revisions(conn: sqlite3.Connection, limits: dict, ticket_ids: list[int]) -> dict:
    """The window's mean post-plan revisions is no greater than the mean of comparable observed baseline values."""
    min_comparable = limits["baseline_min_comparable"]

    totals: dict[int, int] = {}
    if ticket_ids:
        for row in conn.execute(
            f"SELECT ticket_id, SUM(revision_count) AS total FROM v_revisions_per_ticket_by_fm "
            f"WHERE ticket_id IN ({_placeholders(ticket_ids)}) GROUP BY ticket_id", ticket_ids,
        ).fetchall():
            totals[row["ticket_id"]] = row["total"]
    revision_counts = {ticket_id: totals.get(ticket_id, 0) for ticket_id in ticket_ids}
    factory_mean = (sum(revision_counts.values()) / len(revision_counts)) if revision_counts else None

    observed = [
        row["value"] for row in conn.execute(
            "SELECT value FROM v_baseline_revisions_per_ticket WHERE status = 'observed'"
        ).fetchall()
    ]

    reasons: list[str] = []
    baseline_mean = None
    if len(observed) < min_comparable:
        reasons.append("unavailable_baseline")
    else:
        baseline_mean = sum(observed) / len(observed)
        if factory_mean is None or factory_mean > baseline_mean:
            reasons.append(f"factory_mean_exceeds_baseline:{factory_mean}>{baseline_mean}")

    mechanical_tag_ids: list[int] = []
    if ticket_ids:
        mechanical_tag_ids = sorted(
            row["id"] for row in conn.execute(
                f"SELECT id FROM tag WHERE ticket_id IN ({_placeholders(ticket_ids)}) "
                f"AND event_kind IN ('revision_after_approval', 'abandoned') AND tagged_by = ?",
                (*ticket_ids, tags.MECHANICAL_ACTOR),
            ).fetchall()
        )
    if mechanical_tag_ids:
        reasons.append(f"mechanically_tagged_human_decision:{mechanical_tag_ids}")

    return {
        "passed": not reasons,
        "inputs": {
            "factory_mean_revisions": factory_mean, "baseline_mean_revisions": baseline_mean,
            "observed_comparable_count": len(observed), "baseline_min_comparable": min_comparable,
            "revision_counts_by_ticket": revision_counts, "mechanical_tag_ids": mechanical_tag_ids,
        },
        "reasons": reasons,
    }


def control_defects(conn: sqlite3.Connection, ticket_ids: list[int]) -> dict:
    """No window `control_defect` tag's event is undispositioned or still `open`."""
    failing_tag_ids: list[int] = []
    failing_categories: set[str] = set()

    if ticket_ids:
        defect_tags = conn.execute(
            f"SELECT * FROM tag WHERE ticket_id IN ({_placeholders(ticket_ids)}) AND event_kind = 'control_defect'",
            ticket_ids,
        ).fetchall()
        for tag_row in defect_tags:
            event = conn.execute(
                "SELECT * FROM incident_observation WHERE record_kind = 'control_defect_event' AND tag_id = ?",
                (tag_row["id"],),
            ).fetchone()
            if event is None:
                failing_tag_ids.append(tag_row["id"])
                continue
            latest_disposition = conn.execute(
                "SELECT * FROM incident_observation WHERE record_kind = 'control_disposition' "
                "AND event_id = ? ORDER BY id DESC LIMIT 1", (event["id"],),
            ).fetchone()
            if latest_disposition is None or latest_disposition["disposition"] == "open":
                failing_tag_ids.append(tag_row["id"])
                if event["control_category"]:
                    failing_categories.add(event["control_category"])

    return {
        "passed": not failing_tag_ids,
        "inputs": {"failing_tag_ids": sorted(failing_tag_ids), "failing_categories": sorted(failing_categories)},
        "reasons": [f"control_defect_open:{sorted(failing_categories)}"] if failing_tag_ids else [],
    }


def blind_spots(conn: sqlite3.Connection, ticket_ids: list[int], cutoff: str) -> dict:
    """No window blocking `blind_spot` stands unresolved: neither a later pass nor a valid waiver covers it."""
    failing: list[int] = []

    if ticket_ids:
        rows = conn.execute(
            f"SELECT cr.* FROM check_result cr JOIN stage_run sr ON sr.id = cr.stage_run_id "
            f"WHERE sr.ticket_id IN ({_placeholders(ticket_ids)}) AND cr.check_tier = 'blocking' "
            f"AND cr.result = 'blind_spot'", ticket_ids,
        ).fetchall()
        for check_result in rows:
            stage_run = record.get(conn, "stage_run", check_result["stage_run_id"])
            later_pass = conn.execute(
                "SELECT 1 FROM check_result cr2 JOIN stage_run sr2 ON sr2.id = cr2.stage_run_id "
                "WHERE sr2.ticket_id = ? AND cr2.check_name = ? AND cr2.result = 'pass' AND cr2.id > ?",
                (stage_run["ticket_id"], check_result["check_name"], check_result["id"]),
            ).fetchone()
            if later_pass is not None:
                continue
            covering_approval = None
            if check_result["evidence_tuple_id"] is not None:
                covering_approval = conn.execute(
                    "SELECT decided_at FROM approval_record WHERE gate = 'review' AND evidence_tuple_id = ? "
                    "ORDER BY id DESC LIMIT 1", (check_result["evidence_tuple_id"],),
                ).fetchone()
            reference_now = covering_approval["decided_at"] if covering_approval is not None else cutoff
            status, _waiver_id = waivers.effective_result(conn, check_result, now=reference_now)
            if status != "waived":
                failing.append(check_result["id"])

    return {
        "passed": not failing,
        "inputs": {"failing_check_result_ids": sorted(failing)},
        "reasons": [f"unwaived_blind_spot:{sorted(failing)}"] if failing else [],
    }


def self_containedness(conn: sqlite3.Connection, ticket_ids: list[int]) -> dict:
    """Every window plan/review decision recorded `decision_supported_without_transcript = 0` has a resolved unreviewable_diff tag."""
    failing: list[int] = []

    if ticket_ids:
        rows = conn.execute(
            f"SELECT * FROM approval_record WHERE ticket_id IN ({_placeholders(ticket_ids)}) "
            f"AND gate IN ('plan', 'review') AND decision_supported_without_transcript = 0", ticket_ids,
        ).fetchall()
        for approval in rows:
            defect_tag = conn.execute(
                "SELECT * FROM tag WHERE event_kind = 'packet_defect' AND fm_id = ? AND ref = ?",
                (tags.PACKET_DEFECT_FM_ID, f"approval_record:{approval['id']}"),
            ).fetchone()
            resolved = False
            if defect_tag is not None:
                resolution = conn.execute(
                    "SELECT 1 FROM tag WHERE resolves_tag_id = ? AND resolution_evidence_ref IS NOT NULL",
                    (defect_tag["id"],),
                ).fetchone()
                resolved = resolution is not None
            if not resolved:
                failing.append(approval["id"])

    reconstruction_rows = [
        dict(row) for row in conn.execute(
            "SELECT * FROM v_reconstruction_share_by_gate WHERE gate IN ('plan', 'review')"
        ).fetchall()
    ]

    return {
        "passed": not failing,
        "inputs": {"failing_approval_record_ids": sorted(failing), "reconstruction_share_rows": reconstruction_rows},
        "reasons": [f"unresolved_packet_defect:{sorted(failing)}"] if failing else [],
    }


def evaluate(
    conn: sqlite3.Connection,
    *,
    cutoff: str | None = None,
    limits_path: Path = DEFAULT_LIMITS_PATH,
    manifest_hash: str | None = None,
    runs_dir: Path = RUNS_DIR,
    now: str | None = None,
) -> int:
    """Evaluate every clause over a fresh window and register the report; return its artefact id.

    `manifest_hash=None` resolves to `manifest.current_hash()`; every test
    passes an explicit hash instead, so evaluating a report never depends
    on this worktree's own git state. The `utility_run` this call opens
    finishes `pass` only when every clause's `passed` is true.
    """
    now = now or record.now()
    cutoff = cutoff or now
    resolved_manifest_hash = manifest_hash if manifest_hash is not None else manifest.current_hash()
    limits = _load_limits(limits_path)
    thresholds_hash = canonical.content_hash(dict(limits))
    config_hash = hashlib.sha256(Path(limits_path).read_bytes()).hexdigest()
    config_path = _display_path(limits_path)

    run_id = run_ledger.open_utility_run(
        conn, kind="graduation",
        inputs=canonical.canonical_json({
            "cutoff": cutoff, "thresholds_hash": thresholds_hash, "manifest_hash": resolved_manifest_hash,
        }).decode(),
    )

    window_result = window(conn, limits, cutoff=cutoff)
    ticket_ids = window_result["inputs"]["ticket_ids"]

    clauses = {
        "window": window_result,
        "acceptance_gates": acceptance_gates(conn, ticket_ids, resolved_manifest_hash),
        "exposure_coverage": exposure_coverage(conn, ticket_ids, cutoff),
        "incidents": incidents(conn, ticket_ids, limits),
        "stage_reliability": stage_reliability(conn, limits, resolved_manifest_hash),
        "baseline_revisions": baseline_revisions(conn, limits, ticket_ids),
        "control_defects": control_defects(conn, ticket_ids),
        "blind_spots": blind_spots(conn, ticket_ids, cutoff),
        "self_containedness": self_containedness(conn, ticket_ids),
    }
    passed = all(clause["passed"] for clause in clauses.values())

    report_doc = {
        "manifest_hash": resolved_manifest_hash,
        "window": {
            key: window_result["inputs"][key]
            for key in ("start", "cutoff", "ticket_ids", "reset_pending", "manifest_hashes")
        },
        "thresholds": dict(limits),
        "thresholds_hash": thresholds_hash,
        "config_path": config_path,
        "config_hash": config_hash,
        "clauses": clauses,
        "views_read": list(VIEWS_READ),
        "context": _context_block(conn),
        "passed": passed,
    }

    report_path = Path(runs_dir) / "graduation" / str(run_id) / "report.json"
    write_text(report_path, canonical.canonical_json(report_doc).decode())
    artefact_id = artefact_registry.register(
        conn, ticket_id=None, kind="graduation_report", path=report_path, utility_run_id=run_id,
    )
    run_ledger.finish(conn, run_id, "pass" if passed else "fail", table="utility_run")
    return artefact_id


def _report_doc(artefact_row: sqlite3.Row) -> dict:
    return json.loads(Path(artefact_row["path"]).read_text())


def approve(
    conn: sqlite3.Connection,
    report_artefact_id: int,
    *,
    actor: str,
    config_path: str,
    config_hash: str,
    decision: str = "approve",
    note: str | None = None,
    expires_at: str | None = None,
    owners_path: Path = owners.DEFAULT_OWNERS_PATH,
    manifest_hash: str | None = None,
) -> int:
    """Write one `approval_record` binding `report_artefact_id`, or raise `GraduationRefused`.

    Every refusal is checked in the ticket's own order -- unknown report,
    wrong actor, a proposed configuration that does not match the report's
    own, a manifest that has since moved, and (approve only) a report that
    did not pass -- so a caller always learns the first reason a decision
    cannot be recorded rather than a row half-written against a stale
    report. A second call by the same actor on the identical subject
    (report, thresholds and configuration all unchanged) supersedes its own
    prior head instead of forking it, so repeating a decision never
    contests the gate's own quorum.
    """
    artefact_row = record.get(conn, "artefact", report_artefact_id)
    if artefact_row is None or artefact_row["kind"] != "graduation_report":
        raise GraduationRefused(f"no such graduation_report artefact: {report_artefact_id}")

    owners_obj = owners.load_owners(owners_path)
    owner_identity = owners_obj.roles[GRADUATION_ROLE]["identity"]
    if actor != owner_identity:
        raise GraduationRefused(f"actor {actor!r} does not hold {GRADUATION_ROLE!r} in {owners_path}")

    report_doc = _report_doc(artefact_row)
    if config_path != report_doc["config_path"] or config_hash != report_doc["config_hash"]:
        raise GraduationRefused("given config_path/config_hash differ from the report's own")

    current_hash = manifest_hash if manifest_hash is not None else manifest.current_hash()
    if current_hash != report_doc["manifest_hash"]:
        raise GraduationRefused("current manifest hash differs from the report's manifest hash")

    if decision == "approve" and not report_doc["passed"]:
        raise GraduationRefused(f"report {report_artefact_id} did not pass; it cannot be approved")

    subject_hash = canonical.content_hash({
        "report_content_hash": artefact_row["hash"],
        "thresholds_hash": report_doc["thresholds_hash"],
        "config_hash": config_hash,
    })
    slot = Slot(source_rule="factory_owner_role", role=GRADUATION_ROLE, owner=owner_identity, min_count=1)
    prior_head = next(
        (
            row for row in approvals.current_heads(conn, "graduation", subject_hash)
            if row["slot_id"] == slot.slot_id and row["actor_identity"] == actor
        ),
        None,
    )
    scope = canonical.canonical_json({
        "config_path": config_path, "config_hash": config_hash,
        "thresholds_hash": report_doc["thresholds_hash"], "manifest_hash": current_hash,
    }).decode()
    attestation_hash = canonical.content_hash({
        "report_artefact_id": report_artefact_id, "decision": decision, "note": note,
    })
    return approvals.record_approval(
        conn,
        gate="graduation",
        subject_hash=subject_hash,
        slot_id=slot.slot_id,
        actor_identity=actor,
        role=GRADUATION_ROLE,
        decision=decision,
        authority_policy_hash=owners.authority_policy_hash(owners_path),
        membership_snapshot_hash=canonical.content_hash(owners.identity_snapshot(owners_obj, actor)),
        attestation_version=ATTESTATION_VERSION,
        attestation_hash=attestation_hash,
        evidence_ids=canonical.canonical_json([report_artefact_id]).decode(),
        evidence_hashes=canonical.canonical_json([artefact_row["hash"]]).decode(),
        scope=scope,
        expires_at=expires_at,
        supersedes=prior_head["id"] if prior_head is not None else None,
    )


def reject(
    conn: sqlite3.Connection,
    report_artefact_id: int,
    *,
    actor: str,
    config_path: str,
    config_hash: str,
    note: str | None = None,
    expires_at: str | None = None,
    owners_path: Path = owners.DEFAULT_OWNERS_PATH,
    manifest_hash: str | None = None,
) -> int:
    """`approve` under `decision="reject"`: the same refusals except the passing-report requirement."""
    return approve(
        conn, report_artefact_id, actor=actor, config_path=config_path, config_hash=config_hash,
        decision="reject", note=note, expires_at=expires_at, owners_path=owners_path, manifest_hash=manifest_hash,
    )


def quorum(conn: sqlite3.Connection, report_artefact_id: int, *, now: str | None = None) -> bool:
    """Whether the graduation gate's one `factory_owner` slot currently has quorum over `report_artefact_id`.

    Reads the subject off the newest recorded `approval_record` that names
    this report in its `evidence_ids` (every decision on the same report,
    thresholds and configuration shares one subject, so which row supplies
    it does not matter), then asks `approvals.evaluate` the same question
    every other gate asks. No prior decision means no subject and no
    quorum.
    """
    subject_hash = None
    for row in conn.execute("SELECT * FROM approval_record WHERE gate = 'graduation' ORDER BY id").fetchall():
        evidence_ids = json.loads(row["evidence_ids"]) if row["evidence_ids"] else []
        if report_artefact_id in evidence_ids:
            subject_hash = row["subject_hash"]
    if subject_hash is None:
        return False
    owners_obj = owners.load_owners()
    identity = owners_obj.roles[GRADUATION_ROLE]["identity"]
    slot = Slot(source_rule="factory_owner_role", role=GRADUATION_ROLE, owner=identity, min_count=1)
    result = approvals.evaluate(conn, gate="graduation", subject_hash=subject_hash, slots=[slot], now=now)
    return result.satisfied
