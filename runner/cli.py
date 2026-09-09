"""The `factory` command: `advance`, `run`, `show`, `pause`, `resume`, `stop`, `queue`, `act`, `abandon`, `refresh-base`, `migrate-manifest`, `export`, `import`, `purge`, `tag`, `waive`, `report`.

Each verb is a thin wrapper over an in-process function so tests (and any
later API) can call the function directly without going through argument
parsing at all.
"""
import argparse
import sqlite3
import subprocess
import sys
from pathlib import Path

from runner import (
    control, digest, export, freshness, gates, manifest, outbox, project, queue, record, refresh_base, run_ledger, tags, transitions,
    waivers,
)
from runner.db import connect
from runner.paths import FACTORY_DIR, RUNS_DIR
from runner.stages import DRIVERS, run_stage
from runner.state_table import STAGE_STATE

REPORT_SCRIPT = FACTORY_DIR / "scripts" / "tools" / "report"

# Stages grouped by the state they run from, in run order (S5 before S6
# in `checks`), so `advance` can ask "which stage is due here?".
_STAGES_OF_STATE: dict[str, list[str]] = {}
for _stage, _state in STAGE_STATE.items():
    _STAGES_OF_STATE.setdefault(_state, []).append(_stage)


def _due_stage(conn: sqlite3.Connection, ticket: sqlite3.Row) -> str | None:
    """The first stage of the ticket's state still to run, or None.

    A stage whose pass leaves the state (S1 to S4) is always due while the
    ticket sits in that state: being there with a passing run means a
    send-back, so it runs again. A stage whose pass stays in the state (S0,
    S5, S6) is due only until its latest run has passed; after that the
    state's gate decides. S5 is the one exception: a latest run that did
    not pass outright still counts as not due once every blocking result
    it left is validly waived (`runner.waivers.cleared`), since rerunning
    it would write fresh `check_result` rows no waiver names and make the
    ticket's binding stale rather than cleared.
    """
    for stage in _STAGES_OF_STATE.get(ticket["state"], []):
        if DRIVERS[stage].PASS_EVENT is not None:
            return stage
        latest = conn.execute(
            "SELECT id, outcome FROM stage_run WHERE ticket_id = ? AND stage = ? ORDER BY id DESC LIMIT 1",
            (ticket["id"], stage),
        ).fetchone()
        if latest is None:
            return stage
        if latest["outcome"] == "pass":
            continue
        if stage == "S5" and waivers.cleared(conn, latest["id"]):
            continue
        return stage
    return None


def _open_stale_base_item(conn: sqlite3.Connection, ticket_id: int, fresh: freshness.Freshness) -> None:
    """Queue one `red_check` for a stale base, unless the ticket already has an open one."""
    existing = conn.execute(
        "SELECT id FROM queue_item WHERE ticket_id = ? AND kind = 'red_check' AND resolved_at IS NULL",
        (ticket_id,),
    ).fetchone()
    if existing is None:
        queue.open_item(conn, ticket_id=ticket_id, kind="red_check", ref=f"check_result:{fresh.check_result_id}")


def advance(conn: sqlite3.Connection, ticket_id: int, runs_dir: Path = RUNS_DIR) -> str:
    """Reconcile the outbox, expire dead leases, then run the stage due in the ticket's state, else evaluate its gate, else report the wait.

    A ticket with a live run refuses every command but `factory stop`,
    `advance` included, before touching anything else. Outbox
    reconciliation runs before lease expiry, and both run before any
    due-stage or gate logic: a restart must never advance ticket state on
    evidence a crashed attempt left ambiguous or a dead run still holds a
    lease over. Immediately before it would start a due stage or evaluate
    a gate -- the two recorded boundaries -- `advance` checks the durable
    pause flag; a pending pause consumes the boundary instead, so nothing
    below it runs this call. Before ever starting S4, the runner fetches
    the configured target branch and refuses to start it on a stale
    result: no stage runs, one `red_check` item is queued (unless the
    ticket already has one open), and the ticket stays where it is. The
    same freshness check backs `plan_review`'s own gate, so a moved target
    withholds `plan_quorum_fresh` too.
    """
    ticket = record.get(conn, "ticket", ticket_id)
    if ticket is None:
        return f"no such ticket: {ticket_id}"
    if control.live_run(conn, ticket_id) is not None:
        return control.live_run_refusal(ticket_id)
    outbox.reconcile_pending(conn, ticket_id, runs_dir=runs_dir)
    run_ledger.expire_dead_runs(conn, ticket_id)
    stage = _due_stage(conn, ticket)
    if stage is not None:
        if control.pause_pending(conn, ticket_id):
            return f"ticket {ticket_id}: paused at {ticket['state']}"
        if stage == "S4":
            fresh = freshness.check(
                conn, ticket_id, boundary=freshness.BEFORE_S4, target_branch=freshness.target_branch(), runs_dir=runs_dir,
            )
            if not fresh.fresh:
                _open_stale_base_item(conn, ticket_id, fresh)
                return f"ticket {ticket_id}: base is stale ({'; '.join(fresh.reasons)})"
        return f"ticket {ticket_id}: {stage} {run_stage(conn, ticket_id, stage, runs_dir=runs_dir)}"
    gate = gates.GATES.get(ticket["state"])
    if gate is not None and control.pause_pending(conn, ticket_id):
        return f"ticket {ticket_id}: paused at {ticket['state']}"
    event = gate(conn, ticket, runs_dir=runs_dir) if gate is not None else None
    if event is None:
        return f"ticket {ticket_id} is waiting on a human at {ticket['state']}"
    transitions.apply(conn, ticket_id, event)
    return f"ticket {ticket_id}: {event}"


def run(conn: sqlite3.Connection, ticket_id: int, stage: str, runs_dir: Path = RUNS_DIR) -> str:
    """Run the named stage for `ticket_id`; `run_stage` refuses and records a stage its state does not precede.

    A ticket with a live run refuses this call too, before `run_stage`
    ever sees it: only `factory stop` may act on a ticket while one of its
    stages is actually running.
    """
    if record.get(conn, "ticket", ticket_id) is not None:
        if control.live_run(conn, ticket_id) is not None:
            return control.live_run_refusal(ticket_id)
        outbox.reconcile_pending(conn, ticket_id, runs_dir=runs_dir)
    return run_stage(conn, ticket_id, stage, runs_dir=runs_dir)


def show(conn: sqlite3.Connection, ticket_id: int) -> str:
    """The ticket's state, its stage runs (id, stage, attempt, outcome), and its current control status, plain text."""
    ticket = record.get(conn, "ticket", ticket_id)
    if ticket is None:
        return f"no such ticket: {ticket_id}"
    lines = [f"ticket {ticket_id}: {ticket['state']}"]
    for stage_run in conn.execute(
        "SELECT id, stage, attempt, outcome FROM stage_run WHERE ticket_id = ? ORDER BY id",
        (ticket_id,),
    ):
        lines.append(
            f"  stage_run {stage_run['id']}: {stage_run['stage']} "
            f"attempt {stage_run['attempt']} outcome {stage_run['outcome']}"
        )
    info = control.status(conn, ticket_id)
    lines.append(f"  pause pending: {info['pause_pending']}")
    if info["stage"] is not None:
        lines.append(
            f"  current: {info['stage']} attempt {info['attempt']}, elapsed {info['elapsed_seconds']:.1f}s"
        )
        remaining = info["budget_remaining"]
        lines.append(
            f"  budget remaining: tokens {remaining['tokens']}, wall_clock_seconds {remaining['wall_clock_seconds']}"
        )
        for output in info["outputs"]:
            lines.append(f"    output: artefact {output['id']} {output['kind']} {output['path']}")
    return "\n".join(lines)


def pause(conn: sqlite3.Connection, ticket_id: int) -> str:
    """Request a pause for `ticket_id`; `advance` honours it at the next recorded boundary."""
    return control.pause(conn, ticket_id)


def resume(conn: sqlite3.Connection, ticket_id: int, *, actor: str, runs_dir: Path = RUNS_DIR) -> str:
    """Resume `ticket_id` from its held pause boundary."""
    return control.resume(conn, ticket_id, actor=actor, runs_dir=runs_dir)


def stop(conn: sqlite3.Connection, ticket_id: int, *, actor: str, fm_id: str, note: str | None = None) -> str:
    """Terminate `ticket_id`'s running stage(s) and escalate the ticket."""
    return control.stop(conn, ticket_id, actor=actor, fm_id=fm_id, note=note)


def report(
    db_path: Path,
    *,
    manifest_hash: str | None = None,
    window_days: int = 30,
    until: str | None = None,
) -> str:
    """Run the report script over `db_path` and return its stdout as text."""
    argv = [sys.executable, str(REPORT_SCRIPT), "--db", str(db_path), "--window-days", str(window_days)]
    if manifest_hash is not None:
        argv += ["--manifest-hash", manifest_hash]
    if until is not None:
        argv += ["--until", until]
    result = subprocess.run(argv, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "report script failed")
    return result.stdout


def waive(
    conn: sqlite3.Connection,
    *,
    ticket_id: int,
    policy_id: str,
    check_result_id: int | None,
    human_verdict_id: int | None,
    actor: str,
    reason: str,
    scope: str,
    controls: str,
    evidence: list[int],
    expires_at: str,
) -> str:
    """Issue a waiver over a seeded `blind_spot` and report its id."""
    waiver_id = waivers.issue(
        conn, ticket_id=ticket_id, policy_id=policy_id, check_result_id=check_result_id,
        human_verdict_id=human_verdict_id, actor=actor, reason=reason, scope=scope,
        compensating_controls=controls, evidence_ids=evidence, expires_at=expires_at,
    )
    return f"waiver {waiver_id}: issued"


def digest_open_items(conn: sqlite3.Connection, runs_dir: Path = RUNS_DIR) -> str:
    """Build and dispatch the configured cadence's digest through the transactional outbox."""
    config = project.load().get("digest") or {}
    intent_id = digest.run(conn, channel=config.get("channel"), cadence=config.get("cadence", "daily"), runs_dir=runs_dir)
    return "digest: no open items" if intent_id is None else f"digest: intent {intent_id}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="factory")
    parser.add_argument("--db", type=Path, default=RUNS_DIR / "factory.sqlite")
    subparsers = parser.add_subparsers(dest="verb", required=True)

    advance_parser = subparsers.add_parser("advance")
    advance_parser.add_argument("ticket_id", type=int)

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("ticket_id", type=int)
    run_parser.add_argument("stage")

    show_parser = subparsers.add_parser("show")
    show_parser.add_argument("ticket_id", type=int)

    pause_parser = subparsers.add_parser("pause")
    pause_parser.add_argument("ticket_id", type=int)

    resume_parser = subparsers.add_parser("resume")
    resume_parser.add_argument("ticket_id", type=int)
    resume_parser.add_argument("--actor", required=True)

    stop_parser = subparsers.add_parser("stop")
    stop_parser.add_argument("ticket_id", type=int)
    stop_parser.add_argument("--actor", required=True)
    stop_parser.add_argument("--fm", required=True)
    stop_parser.add_argument("--note")

    queue_parser = subparsers.add_parser("queue")
    queue_parser.add_argument("--all", action="store_true", dest="show_all")

    act_parser = subparsers.add_parser("act")
    act_parser.add_argument("item_id", type=int)
    act_parser.add_argument("action")
    act_parser.add_argument("--actor", required=True)
    act_parser.add_argument("--bucket")
    act_parser.add_argument("--note")
    act_parser.add_argument("--to")
    act_parser.add_argument("--fm")
    act_parser.add_argument("--category")
    act_parser.add_argument("--severity")
    act_parser.add_argument("--option", type=int)
    act_parser.add_argument("--tier")
    act_parser.add_argument("--line")
    act_parser.add_argument("--key")
    act_parser.add_argument("--verdict")
    act_parser.add_argument("--evidence")
    act_parser.add_argument("--waiver", type=int)
    act_parser.add_argument("--self-contained", dest="self_contained", choices=("yes", "no"))

    abandon_parser = subparsers.add_parser("abandon")
    abandon_parser.add_argument("ticket_id", type=int)
    abandon_parser.add_argument("--actor", required=True)
    abandon_parser.add_argument("--fm", required=True)
    abandon_parser.add_argument("--note")

    refresh_base_parser = subparsers.add_parser("refresh-base")
    refresh_base_parser.add_argument("ticket_id", type=int)
    refresh_base_parser.add_argument("--actor", required=True)
    refresh_base_parser.add_argument("--note")

    migrate_manifest_parser = subparsers.add_parser("migrate-manifest")
    migrate_manifest_parser.add_argument("--actor", required=True)
    migrate_manifest_parser.add_argument("--note")

    tag_parser = subparsers.add_parser("tag")
    tag_parser.add_argument("target")
    tag_parser.add_argument("kind")
    tag_parser.add_argument("--fm", required=True)
    tag_parser.add_argument("--actor", required=True)
    tag_parser.add_argument("--note")
    tag_parser.add_argument("--severity")
    tag_parser.add_argument("--resolves", type=int)
    tag_parser.add_argument("--resolution-evidence")

    waive_parser = subparsers.add_parser("waive")
    waive_parser.add_argument("--ticket", type=int, required=True, dest="ticket_id")
    waive_parser.add_argument("--policy", required=True, dest="policy_id")
    waive_parser.add_argument("--check-result", type=int, dest="check_result_id")
    waive_parser.add_argument("--verdict", type=int, dest="human_verdict_id")
    waive_parser.add_argument("--actor", required=True)
    waive_parser.add_argument("--reason", required=True)
    waive_parser.add_argument("--scope", required=True)
    waive_parser.add_argument("--controls", required=True)
    waive_parser.add_argument("--evidence", required=True)
    waive_parser.add_argument("--expires", required=True, dest="expires_at")

    report_parser = subparsers.add_parser("report")
    report_parser.add_argument("--manifest-hash", default=None)
    report_parser.add_argument("--window-days", type=int, default=30)
    report_parser.add_argument("--until", default=None)

    subparsers.add_parser("digest")

    export_parser = subparsers.add_parser("export")
    export_parser.add_argument("ticket_id", type=int)

    import_parser = subparsers.add_parser("import")
    import_parser.add_argument("export_dir", type=Path)

    purge_parser = subparsers.add_parser("purge")
    purge_parser.add_argument("export_dir", type=Path)

    args = parser.parse_args(argv)
    # The run tree lives beside the database: one root holds every piece of
    # run state, so pointing `--db` elsewhere moves the artefacts with it.
    runs_dir = args.db.parent
    conn = connect(args.db)
    try:
        if args.verb == "advance":
            print(advance(conn, args.ticket_id, runs_dir))
        elif args.verb == "run":
            print(run(conn, args.ticket_id, args.stage, runs_dir))
        elif args.verb == "show":
            print(show(conn, args.ticket_id))
        elif args.verb == "pause":
            print(pause(conn, args.ticket_id))
        elif args.verb == "resume":
            print(resume(conn, args.ticket_id, actor=args.actor, runs_dir=runs_dir))
        elif args.verb == "stop":
            print(stop(conn, args.ticket_id, actor=args.actor, fm_id=args.fm, note=args.note))
        elif args.verb == "queue":
            print(queue.list_queue(conn, include_resolved=args.show_all))
        elif args.verb == "act":
            evidence = [int(item) for item in args.evidence.split(",")] if args.evidence else None
            print(queue.act(
                conn, item_id=args.item_id, action=args.action, actor=args.actor,
                bucket=args.bucket, note=args.note, to=args.to, fm_id=args.fm,
                category=args.category, severity=args.severity, option=args.option,
                tier=args.tier, line=args.line, key=args.key, verdict=args.verdict,
                evidence=evidence, waiver=args.waiver, self_contained=args.self_contained, runs_dir=runs_dir,
            ))
        elif args.verb == "abandon":
            print(queue.abandon(
                conn, args.ticket_id, actor=args.actor, fm_id=args.fm, note=args.note, runs_dir=runs_dir,
            ))
        elif args.verb == "refresh-base":
            print(refresh_base.refresh_base(
                conn, args.ticket_id, actor=args.actor, note=args.note,
                target_branch=freshness.target_branch(), runs_dir=runs_dir,
            ))
        elif args.verb == "migrate-manifest":
            print(manifest.migrate(conn, actor=args.actor, note=args.note))
        elif args.verb == "tag":
            print(tags.tag(
                conn, target=args.target, kind=args.kind, fm_id=args.fm,
                actor=args.actor, note=args.note, severity=args.severity,
                resolves_tag_id=args.resolves, resolution_evidence_ref=args.resolution_evidence,
            ))
        elif args.verb == "waive":
            evidence = [int(item) for item in args.evidence.split(",")] if args.evidence else []
            print(waive(
                conn, ticket_id=args.ticket_id, policy_id=args.policy_id,
                check_result_id=args.check_result_id, human_verdict_id=args.human_verdict_id,
                actor=args.actor, reason=args.reason, scope=args.scope, controls=args.controls,
                evidence=evidence, expires_at=args.expires_at,
            ))
        elif args.verb == "report":
            print(
                report(
                    args.db,
                    manifest_hash=args.manifest_hash,
                    window_days=args.window_days,
                    until=args.until,
                ),
                end="",
            )
        elif args.verb == "digest":
            print(digest_open_items(conn, runs_dir))
        elif args.verb == "export":
            result = export.export_ticket(conn, args.ticket_id, runs_dir=runs_dir)
            print(f"ticket {args.ticket_id}: exported to {result['export_dir']}")
        elif args.verb == "import":
            result = export.import_export(conn, args.export_dir, runs_dir=runs_dir)
            print(f"imported ticket {result['ticket_id']} from {args.export_dir}")
        elif args.verb == "purge":
            print(export.purge_export(conn, args.export_dir))
        conn.commit()
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
