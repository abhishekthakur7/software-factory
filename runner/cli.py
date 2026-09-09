"""The `factory` command: `advance`, `run`, `show`, `pause`, `resume`, `stop`, `queue`, `act`, `abandon`, `refresh-base`, `migrate-manifest`, `export`, `import`, `purge`, `tag`, `waive`, `report`.

Each verb is a thin wrapper over an in-process function (`runner.operations`
for the verbs with no module of their own) so tests and any later API call
the function directly without going through argument parsing at all.
"""
import argparse
from pathlib import Path

from runner import export, freshness, manifest, queue, refresh_base, tags
from runner.db import connect
from runner.operations import advance, digest_open_items, pause, report, resume, run, show, stop, waive
from runner.paths import RUNS_DIR


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
