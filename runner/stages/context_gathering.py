"""The context gathering stage: reindex, impact scan, context-index reads, the agent, then the brief's own checks.

The driver's own `stage_run_id` (the attempt) is where every artefact it
registers itself lands -- `impact_scan`, `index_reads`, and the checked
`brief` -- while the agent's raw `out/brief.md` lives under its own child
run. Reading the raw file, checking it, and writing the checked version
back under the attempt keeps the registered `brief` always the checked
one: nothing downstream of the context gathering stage ever reads an unchecked agent output.

`Final tier` is never trusted from the agent: the driver computes
`files_touched`/`services_touched`/`unknowns` from the brief's own other
tables plus the registered `impact_scan` payload, applies the
files/services/unknowns threshold rule and then impact-derived tiering
(the highest known criticality among the target and impacted services)
on top, stamps `ticket.tier_final`, and overwrites the section before
registering. A brief that discovers scope outside the Initial pilot's
one repository and target service, or an `unknown` row that says so in
its own `blind_spots` cell, re-triggers the exclusion gate before any
content check is even consulted; every other content problem -- an
over-length summary, a flag with no code reference, a live-state
assertion outside blind spots, an impact row `impact_scan` itself
contradicts -- fails the attempt as a verification problem instead, so a
rerun can fix the content without the ticket ever leaving `context`.
"""
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import yaml

from runner import artefact_registry, artefacts, context_index, launcher, project, record, run_ledger
from runner.checks import brief as checks_brief
from runner.checks import exclusion
from runner.fs import write_text
from runner.paths import FACTORY_DIR, REPO_ROOT, RUNS_DIR

ARTEFACT_KIND = "brief"
PASS_EVENT = "context_gathering_pass"

REINDEX_SCRIPT = FACTORY_DIR / "scripts" / "tools" / "reindex"
IMPACT_SCAN_SCRIPT = FACTORY_DIR / "scripts" / "checks" / "impact_scan"
ARCHAEOLOGY_SCRIPT = FACTORY_DIR / "scripts" / "tools" / "archaeology"
ARCHAEOLOGY_ROUTE = "atlassian_read"
DEFAULT_ARTIFACT_TO_SERVICE_PATH = FACTORY_DIR / "config" / "artifact-to-service.yaml"
DEFAULT_PROJECT_CONFIG_PATH = project.DEFAULT_PROJECT_CONFIG_PATH
DEFAULT_TIERS_PATH = FACTORY_DIR / "config" / "tiers.yaml"
DEFAULT_LIMITS_PATH = FACTORY_DIR / "config" / "limits.yaml"


def _project_config(path: Path = DEFAULT_PROJECT_CONFIG_PATH) -> dict:
    return project.pilot(path=path)


def _default_vendor_path(repo_root: Path, project_config: dict) -> Path:
    return Path(repo_root) / project_config["vendor"]


def _run_reindex(conn: sqlite3.Connection, ticket_id: int, worktree: Path) -> None:
    """Refresh the code graph, as one `utility_run`; a failed or absent binary is recorded, never fatal at this tier."""
    result = subprocess.run([str(REINDEX_SCRIPT), str(worktree)], capture_output=True, text=True)
    run_id = run_ledger.open_utility_run(
        conn, kind="reindex", ticket_id=ticket_id, inputs=str(worktree), outputs=result.stdout.strip(),
    )
    run_ledger.finish(conn, run_id, "pass" if result.returncode == 0 else "fail", table="utility_run")


def _run_impact_scan(pom: Path, vendor_repo: Path, mapping: Path) -> dict | None:
    """The parsed `impact_scan` payload, or `None` when the scan itself failed (no pom, unreadable mapping, ...)."""
    result = subprocess.run(
        [str(IMPACT_SCAN_SCRIPT), "--pom", str(pom), "--vendor-repo", str(vendor_repo), "--mapping", str(mapping)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return None
    return json.loads(result.stdout)


def _known_worktree_paths(worktree: Path) -> frozenset[str]:
    """Every path git tracks in `worktree` -- the evidence `flags_are_code_references` checks a flag's reference against."""
    result = subprocess.run(["git", "-C", str(worktree), "ls-files"], capture_output=True, text=True)
    if result.returncode != 0:
        return frozenset()
    return frozenset(line.strip() for line in result.stdout.splitlines() if line.strip())


def _record_check(conn: sqlite3.Connection, stage_run_id: int, finding: checks_brief.Finding) -> None:
    record.insert(
        conn, "check_result", stage_run_id=stage_run_id, check_name=finding.check_name,
        result=finding.result, summary=finding.detail,
    )


def _out_dir(runs_dir: Path, ticket_id: int, run_id: int) -> Path:
    return Path(runs_dir) / "tickets" / str(ticket_id) / "runs" / str(run_id) / "out"


def _archaeology_run_dir(runs_dir: Path, ticket_id: int, stage_run_id: int) -> Path:
    return Path(runs_dir) / "tickets" / str(ticket_id) / "runs" / str(stage_run_id) / "archaeology"


def _archaeology_candidates(touched_rows: list[dict]) -> list[dict]:
    """One archaeology candidate per non-empty `Touched area candidates` path, `path#symbol` split apart.

    `self_evident` is always false: the brief's `Touched area candidates`
    table (`path`, `reason`) carries no self-evidence signal of its own
    for this to read, and the lax default is to always run archaeology
    rather than silently skip a candidate that turns out not to be
    self-evident.
    """
    candidates = []
    for row in touched_rows:
        cell = (row.get("path") or "").strip()
        if not cell:
            continue
        path, _, symbol = cell.partition("#")
        candidates.append({"path": path, "symbol": symbol or None, "self_evident": False})
    return candidates


def _history_row(candidate: dict) -> dict:
    path = f"{candidate['path']}#{candidate['symbol']}" if candidate.get("symbol") else candidate["path"]
    issues = candidate.get("issues") or []
    evidence = f"{', '.join(issues) if issues else 'no issue named'}: {candidate['why']}"
    return {"path": path, "classification": candidate["classification"], "evidence": evidence}


def _run_archaeology(
    conn: sqlite3.Connection, ticket_id: int, stage_run_id: int, runs_dir: Path, worktree: Path,
    touched_rows: list[dict], *, proxy_url: str | None, sandbox_path: Path | None,
) -> tuple[bool, str, str]:
    """`(ok, check detail, History section text)`; `History` text is only meaningful when `ok`.

    Runs `archaeology` as a subprocess launch under the agent profile for
    the context gathering stage -- the same sandboxed boundary a real agent invocation
    crosses, so the script's own proxy call (and the credential it never
    sees) cross it too. `factory/` is unreadable from inside that profile,
    so the script is staged into the launch's own `tmp/` first, the same
    way a sandbox test probe is; the worktree itself is readable there
    (the ticket directory is a read-only mount at every stage). The
    classification is never trusted from the agent, the same rule
    `Final tier` follows.
    """
    candidates = _archaeology_candidates(touched_rows)
    if not candidates:
        return True, "no touched-area candidates", "no touched-area candidates"

    run_dir = _archaeology_run_dir(runs_dir, ticket_id, stage_run_id)
    tmp_dir = run_dir / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    script_copy = tmp_dir / "archaeology.py"
    write_text(script_copy, ARCHAEOLOGY_SCRIPT.read_text())
    candidates_path = tmp_dir / "candidates.json"
    write_text(candidates_path, json.dumps(candidates))

    argv = [
        sys.executable, str(script_copy), "--worktree", str(worktree), "--candidates", str(candidates_path),
        "--route", ARCHAEOLOGY_ROUTE,
    ]
    if proxy_url:
        argv += ["--proxy", proxy_url]

    limits = yaml.safe_load(DEFAULT_LIMITS_PATH.read_text())
    result = launcher.launch(
        run_dir=run_dir, argv=argv, role="agent", policy="enforced", cwd=tmp_dir,
        wall_clock_seconds=limits["archaeology"]["wall_clock_seconds"], stage="context_gathering",
        ticket_dir=Path(runs_dir) / "tickets" / str(ticket_id), worktree_path=worktree,
        # Read at call time, never bound as a default parameter value: a
        # test's session-scoped fixture patches `launcher.SANDBOX_PATH`
        # after this module has already been imported, so only a runtime
        # attribute read (not `launcher.launch`'s own default argument)
        # picks it up. `sandbox_path` lets a boundary test force the real,
        # OS-enforcing profile regardless of that patch.
        sandbox_path=sandbox_path if sandbox_path is not None else launcher.SANDBOX_PATH,
    )
    payload = result.stdout_json
    if payload is None or "candidates" not in payload:
        return False, f"archaeology script produced no parseable result; stderr: {result.stderr_text}", ""

    history_path = _out_dir(runs_dir, ticket_id, stage_run_id) / "history.json"
    write_text(history_path, json.dumps(payload, sort_keys=True))
    artefact_registry.register(conn, ticket_id=ticket_id, kind="history", path=history_path, stage_run_id=stage_run_id)

    rows = [_history_row(c) for c in payload["candidates"]]
    text = artefacts.render_table(artefacts.BRIEF_TABLES["History"], rows) if rows else "no candidates required archaeology"
    return True, f"{len(rows)} candidate(s) classified", text


def run(
    conn: sqlite3.Connection,
    ticket: sqlite3.Row,
    stage_run_id: int,
    runs_dir: Path = RUNS_DIR,
    *,
    service_tiers: dict | None = None,
    ticket_types: dict | None = None,
    index_dir: Path | None = None,
    artifact_to_service_path: Path = DEFAULT_ARTIFACT_TO_SERVICE_PATH,
    vendor_path: Path | None = None,
    target_branch: str | None = None,
    tiers_config: dict | None = None,
    repo_root: Path = REPO_ROOT,
    archaeology_proxy_url: str | None = None,
    archaeology_sandbox_path: Path | None = None,
) -> str | tuple[str, str]:
    """Run context gathering for `ticket`: reindex, impact scan, context-index reads, the agent, then the brief's own checks.

    The keyword-only config parameters all default to the committed
    files (or, for `vendor_path`/`target_branch`, to what
    `project.yaml` names); `run_stage` never passes them, so they exist
    only for a test that needs a worktree, mapping, or index the real
    project would never carry. `archaeology_proxy_url`/
    `archaeology_sandbox_path` are the same kind of test-only override,
    for a test standing in its own loopback server or forcing the real
    OS-enforced sandbox profile in place of the production defaults.
    """
    from runner.stages import intake, invoke_agent  # local: avoids the package __init__ import cycle

    ticket_id = ticket["id"]
    if ticket["tier_provisional"] is None or ticket["ticket_type"] is None or not ticket["service"]:
        # intake stamps these before eligibility; a ticket here without them
        # never had a valid intake, so the tier rule has no floor to
        # raise from and the run refuses rather than guessing one.
        _record_check(conn, stage_run_id, checks_brief.Finding(
            "ticket_lookups", "fail", "ticket lacks the service, ticket type or provisional tier intake stamps",
        ))
        return ("fail", "structural")
    worktree = Path(ticket["worktree_path"])
    project_config = _project_config()
    vendor_path = vendor_path if vendor_path is not None else _default_vendor_path(repo_root, project_config)
    target_branch = target_branch if target_branch is not None else project_config.get("target_branch")
    tiers_config = tiers_config if tiers_config is not None else yaml.safe_load(DEFAULT_TIERS_PATH.read_text())
    service_tiers = service_tiers if service_tiers is not None else intake.load_service_tiers()
    ticket_types = ticket_types if ticket_types is not None else intake.load_ticket_types()

    _run_reindex(conn, ticket_id, worktree)

    attempt_out_dir = _out_dir(runs_dir, ticket_id, stage_run_id)
    impact_payload = _run_impact_scan(worktree / "pom.xml", vendor_path, artifact_to_service_path)
    if impact_payload is None:
        _record_check(
            conn, stage_run_id,
            checks_brief.Finding("impact_scan", "fail", f"impact_scan failed over {worktree / 'pom.xml'}"),
        )
        return ("fail", "infrastructure")
    impact_scan_path = attempt_out_dir / "impact_scan.json"
    write_text(impact_scan_path, json.dumps(impact_payload, sort_keys=True))
    impact_artefact_id = artefact_registry.register(
        conn, ticket_id=ticket_id, kind="impact_scan", path=impact_scan_path, stage_run_id=stage_run_id,
    )

    entries = context_index.load_entries(index_dir or context_index.INDEX_DIR)
    reads = context_index.record_reads(
        conn, stage_run_id=stage_run_id, entries=entries, checkout=worktree, target_branch=target_branch,
    )
    index_reads_path = attempt_out_dir / "index_reads.md"
    if reads:
        index_reads_text = artefacts.render_table(
            artefacts.BRIEF_TABLES["Index entries used"],
            [
                {"entry": r.entry.path.name, "last_verified": r.entry.last_verified or "", "stale": "yes" if r.stale else "no"}
                for r in reads
            ],
        )
    else:
        index_reads_text = "no entries"
    write_text(index_reads_path, index_reads_text + "\n")
    index_reads_artefact_id = artefact_registry.register(
        conn, ticket_id=ticket_id, kind="index_reads", path=index_reads_path, stage_run_id=stage_run_id,
    )

    result = invoke_agent(
        conn, ticket, "context_gathering", runs_dir=runs_dir, parent_run_id=stage_run_id,
        input_artefact_ids=[impact_artefact_id, index_reads_artefact_id],
    )
    if result.outcome != "pass":
        return result.outcome

    child_out_dir = _out_dir(runs_dir, ticket_id, result.stage_run_id)
    brief_path = child_out_dir / "brief.md"
    if not brief_path.is_file():
        _record_check(conn, stage_run_id, checks_brief.Finding("brief_structure", "fail", f"no brief.md written to {brief_path}"))
        return ("fail", "structural")
    raw_text = brief_path.read_text()
    try:
        parsed = artefacts.parse(raw_text)
    except artefacts.ArtefactError as exc:
        _record_check(conn, stage_run_id, checks_brief.Finding("brief_structure", "fail", str(exc)))
        return ("fail", "structural")
    if parsed.titles() != artefacts.SECTIONS["brief"]:
        _record_check(
            conn, stage_run_id,
            checks_brief.Finding("brief_structure", "fail", f"sections are {parsed.titles()}, expected {artefacts.SECTIONS['brief']}"),
        )
        return ("fail", "structural")

    summary_prose = parsed.section("Ticket summary").prose()
    touched_rows = parsed.section("Touched area candidates").table() or []
    impact_rows = parsed.section("Impact evidence").table() or []
    flag_rows = parsed.section("Flags").table() or []
    unknown_rows = parsed.section("Unknowns").table() or []

    archaeology_ok, archaeology_detail, history_text = _run_archaeology(
        conn, ticket_id, stage_run_id, runs_dir, worktree, touched_rows,
        proxy_url=archaeology_proxy_url, sandbox_path=archaeology_sandbox_path,
    )
    _record_check(conn, stage_run_id, checks_brief.Finding("archaeology", "pass" if archaeology_ok else "fail", archaeology_detail))
    if not archaeology_ok:
        return ("fail", "infrastructure")

    impact_scan_deps = impact_payload["dependencies"]
    files_touched = checks_brief.count_files_touched(touched_rows)
    services = checks_brief.touched_services(
        impact_rows, target_service=ticket["service"], impact_scan_dependencies=impact_scan_deps,
    )
    services_touched = len(services)
    unknowns = checks_brief.count_unknowns(unknown_rows, impact_rows)

    tier_provisional = ticket["tier_provisional"]
    tier_so_far = ticket["tier_final"] or tier_provisional
    tier_after_rule = checks_brief.final_tier_rule(
        files_touched=files_touched, services_touched=services_touched, unknowns=unknowns,
        tier_provisional=tier_provisional, tier_so_far=tier_so_far, rule=tiers_config["final_tier_rule"],
    )
    impacted_services = services - {ticket["service"]}
    tier_final, unknown_impact = checks_brief.impact_derived_tier(
        impacted_services=impacted_services, service_tiers=service_tiers, ticket_type=ticket["ticket_type"],
        provisional_tier_matrix=ticket_types["provisional_tier"], tier_so_far=tier_after_rule,
    )
    record.update(conn, "ticket", ticket_id, tier_final=tier_final)

    final_tier_row = {
        "files_touched": str(files_touched), "services_touched": str(services_touched), "unknowns": str(unknowns),
        "tier_provisional": tier_provisional, "tier_final": tier_final,
    }
    # Three sections are the runner's, not the agent's: what the index
    # read actually recorded, the archaeology script's own classification,
    # and the tier the rule computed.
    runner_sections = {
        "Index entries used": index_reads_text,
        "History": history_text,
        "Final tier": artefacts.render_table(artefacts.BRIEF_TABLES["Final tier"], [final_tier_row]),
    }
    checked_sections = [
        (title, runner_sections.get(title, parsed.section(title).body)) for title in artefacts.SECTIONS["brief"]
    ]
    checked_path = attempt_out_dir / "brief.md"
    write_text(checked_path, artefacts.render(checked_sections, front_matter=parsed.front_matter))
    prior = artefact_registry.latest(conn, ticket_id, ARTEFACT_KIND)
    artefact_registry.register(
        conn, ticket_id=ticket_id, kind=ARTEFACT_KIND, path=checked_path, stage_run_id=stage_run_id,
        supersedes=prior["id"] if prior is not None else None,
    )

    _record_check(
        conn, stage_run_id,
        checks_brief.Finding(
            "brief_impact_unknown", "fail" if unknown_impact else "pass",
            f"impacted services {sorted(impacted_services)}; unknown_impact={unknown_impact}",
        ),
    )

    exclusion_reason = checks_brief.discovers_excluded_scope(
        impact_rows, target_service=ticket["service"], impact_scan_dependencies=impact_scan_deps,
    )
    if exclusion_reason is not None:
        _record_check(conn, stage_run_id, checks_brief.Finding("exclusion", "fail", exclusion_reason))
        exclusion.apply_recorded_exclusion(conn, ticket_id)
        return "fail"

    any_fresh_caller_entry = any(r.entry.kind == "caller" and not r.stale for r in reads)
    findings = [
        checks_brief.summary_word_limit(summary_prose, max_words=tiers_config["length_limits"]["brief_summary_words"]),
        checks_brief.flags_are_code_references(flag_rows, known_paths=_known_worktree_paths(worktree)),
        checks_brief.live_state_confined_to_blind_spots(parsed),
        checks_brief.impact_evidence_valid(
            impact_rows, impact_scan_dependencies=impact_scan_deps, mapping_name=Path(artifact_to_service_path).name,
        ),
        checks_brief.inbound_coverage_matches_caller_freshness(impact_rows, any_fresh_caller_entry=any_fresh_caller_entry),
    ]
    for finding in findings:
        _record_check(conn, stage_run_id, finding)

    if any(finding.result == "fail" for finding in findings):
        return ("fail", "verification")
    return "pass"
