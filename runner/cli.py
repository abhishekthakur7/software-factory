"""The `factory` command: `advance`, `run`, `show`, `pause`, `resume`, `stop`, `queue`, `act`, `abandon`, `refresh-base`, `migrate-manifest`, `export`, `import`, `purge`, `tag`, `waive`, `report`.

Each verb is a thin wrapper over an in-process function (`runner.operations`
for the verbs with no module of their own) so tests and any later API call
the function directly without going through argument parsing at all.
"""
import argparse
from pathlib import Path

from runner import export, freshness, graduation, manifest, queue, refresh_base, tags
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
    act_parser.add_argument("item_id", type=int, nargs="?")
    act_parser.add_argument("action")
    act_parser.add_argument("--ticket", type=int, dest="ticket_id")
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
    # The manual outcome record's own flags: `revision`'s target stage
    # reuses `--to`/`--fm`/`--note` above; every other name here is unique
    # to `outcome`, `exposure`, `coverage`, `incident_event`, and
    # `disposition`, so they are collected into one `fields` mapping
    # rather than becoming twenty separate `queue.act` parameters.
    act_parser.add_argument("--result", choices=("merged", "abandoned"))
    act_parser.add_argument("--head-sha", dest="head_sha")
    act_parser.add_argument("--target-base-sha", dest="target_base_sha")
    act_parser.add_argument("--merge-sha", dest="merge_sha")
    act_parser.add_argument("--checks", choices=("green", "waived", "red", "unknown"))
    act_parser.add_argument("--checks-reason", dest="checks_reason")
    act_parser.add_argument("--observed-at", dest="observed_at")
    act_parser.add_argument("--body-file", dest="body_file")
    act_parser.add_argument("--pr-identity", dest="pr_identity")
    act_parser.add_argument("--observed-head-sha", dest="observed_head_sha")
    act_parser.add_argument("--start")
    act_parser.add_argument("--source")
    act_parser.add_argument("--through")
    act_parser.add_argument("--root")
    act_parser.add_argument("--occurred-at", dest="occurred_at")
    act_parser.add_argument("--event")
    act_parser.add_argument("--attribution")
    act_parser.add_argument("--disposition")
    act_parser.add_argument("--remediation-ref", dest="remediation_ref")

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

    graduate_parser = subparsers.add_parser("graduate")
    graduate_subparsers = graduate_parser.add_subparsers(dest="graduate_verb", required=True)

    graduate_evaluate_parser = graduate_subparsers.add_parser("evaluate")
    graduate_evaluate_parser.add_argument("--cutoff", default=None)

    graduate_approve_parser = graduate_subparsers.add_parser("approve")
    graduate_approve_parser.add_argument("report_artefact_id", type=int)
    graduate_approve_parser.add_argument("--actor", required=True)
    graduate_approve_parser.add_argument("--config", required=True, dest="config_path")
    graduate_approve_parser.add_argument("--config-hash", required=True)
    graduate_approve_parser.add_argument("--expires", default=None, dest="expires_at")
    graduate_approve_parser.add_argument("--note", default=None)

    graduate_reject_parser = graduate_subparsers.add_parser("reject")
    graduate_reject_parser.add_argument("report_artefact_id", type=int)
    graduate_reject_parser.add_argument("--actor", required=True)
    graduate_reject_parser.add_argument("--config", required=True, dest="config_path")
    graduate_reject_parser.add_argument("--config-hash", required=True)
    graduate_reject_parser.add_argument("--expires", default=None, dest="expires_at")
    graduate_reject_parser.add_argument("--note", default=None)

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
            fields = {
                "to": args.to, "fm_id": args.fm, "note": args.note,
                "result": args.result, "head_sha": args.head_sha, "target_base_sha": args.target_base_sha,
                "merge_sha": args.merge_sha, "checks": args.checks, "checks_reason": args.checks_reason,
                "observed_at": args.observed_at, "body_file": args.body_file, "pr_identity": args.pr_identity,
                "observed_head_sha": args.observed_head_sha, "start": args.start, "source": args.source,
                "through": args.through, "root": args.root, "severity": args.severity,
                "occurred_at": args.occurred_at, "event": args.event, "attribution": args.attribution,
                "disposition": args.disposition, "remediation_ref": args.remediation_ref, "category": args.category,
            }
            print(queue.act(
                conn, item_id=args.item_id, ticket_id=args.ticket_id, action=args.action, actor=args.actor,
                bucket=args.bucket, note=args.note, to=args.to, fm_id=args.fm,
                category=args.category, severity=args.severity, option=args.option,
                tier=args.tier, line=args.line, key=args.key, verdict=args.verdict,
                evidence=evidence, waiver=args.waiver, self_contained=args.self_contained,
                fields=fields, runs_dir=runs_dir,
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
        elif args.verb == "graduate":
            if args.graduate_verb == "evaluate":
                print(graduation.evaluate(conn, cutoff=args.cutoff))
            elif args.graduate_verb == "approve":
                print(graduation.approve(
                    conn, args.report_artefact_id, actor=args.actor, config_path=args.config_path,
                    config_hash=args.config_hash, expires_at=args.expires_at, note=args.note,
                ))
            elif args.graduate_verb == "reject":
                print(graduation.reject(
                    conn, args.report_artefact_id, actor=args.actor, config_path=args.config_path,
                    config_hash=args.config_hash, expires_at=args.expires_at, note=args.note,
                ))
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
