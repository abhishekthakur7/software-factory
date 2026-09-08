"""Governed export, import and purge: the record's one hand-over format.

`export_ticket` writes a single directory holding a ticket's permitted rows,
artefacts and branch patch. Every crossing out of the record -- the export
as a whole and, separately, each artefact file and each table's row file --
goes through `runner.guard.decide` over the `governed_export_display`
route, so a credential or a raw disallowed payload can never reach the
directory: a deny on the whole-export decision writes nothing at all, and a
deny on one item excludes only that item, recorded under `manifest.json`'s
`excluded` list rather than silently dropped. `import_export` is the
inverse: it recomputes every declared file's hash and the manifest's own
content hash before trusting any of it, rejects a path that could escape
the export directory, and only then inserts rows -- one transaction, so a
rejected import leaves the target record exactly as it was. `purge_export`
deletes an export directory once its recorded retention has passed and
refuses otherwise, recording the outcome either way on a utility run.

Row envelopes carry their own `data_class`/`redaction_state`/
`retention_until` when the table declares those columns (currently only
`artefact`); every other exported table has no such columns of its own, so
its rows inherit the ticket's `data_class`, a null `redaction_state`, and a
`retention_until` computed from the route's retention period at export
time -- this is the "inherits classification and retention" the ticket
record's export requirement describes.
"""
import hashlib
import json
import sqlite3
import subprocess
import uuid
from datetime import datetime, timedelta
from pathlib import Path, PurePosixPath

from runner import artefact_registry, canonical, guard, owners, record, run_ledger, trust_profile
from runner.fs import remove_tree, write_bytes, write_text
from runner.paths import RUNS_DIR

CROSSING = "export"
ROUTE_ID = "governed_export_display"

# The fixed table set the ticket record's export requirement names, in
# insertion order for import: `ticket` first (every other table's rows
# reference it), the rest following the same order they are described in.
EXPORT_TABLES: tuple[str, ...] = (
    "ticket", "stage_run", "tool_call", "artefact", "guard_decision",
    "reviewer_set", "approval_record", "waiver", "evidence_tuple",
    "incident_observation", "external_write", "check_result", "tag",
)


class ExportRefused(Exception):
    """The export is denied outright: the route does not admit the ticket's class, or the guard is unavailable."""


class ImportRefused(Exception):
    """A declared file's hash, the manifest's content hash, a path, or a row-id collision fails verification."""


class PurgeRefused(Exception):
    """The export directory's recorded retention has not yet passed."""


def _rows_where(conn: sqlite3.Connection, table: str, column: str, value) -> list[sqlite3.Row]:
    return conn.execute(f"SELECT * FROM {table} WHERE {column} = ? ORDER BY id", (value,)).fetchall()


def _rows_in(conn: sqlite3.Connection, table: str, column: str, values: list[int]) -> list[sqlite3.Row]:
    if not values:
        return []
    placeholders = ", ".join("?" for _ in values)
    return conn.execute(f"SELECT * FROM {table} WHERE {column} IN ({placeholders}) ORDER BY id", values).fetchall()


def _check_result_rows(conn: sqlite3.Connection, stage_run_ids: list[int], evidence_tuple_ids: list[int]) -> list[sqlite3.Row]:
    """`check_result` carries no `ticket_id` of its own, so a row belongs to the ticket only through its stage run or the plan/review tuple it names."""
    clauses, params = [], []
    if stage_run_ids:
        placeholders = ", ".join("?" for _ in stage_run_ids)
        clauses.append(f"stage_run_id IN ({placeholders})")
        params.extend(stage_run_ids)
    if evidence_tuple_ids:
        placeholders = ", ".join("?" for _ in evidence_tuple_ids)
        clauses.append(f"plan_tuple_id IN ({placeholders})")
        params.extend(evidence_tuple_ids)
        clauses.append(f"evidence_tuple_id IN ({placeholders})")
        params.extend(evidence_tuple_ids)
    if not clauses:
        return []
    return conn.execute(
        f"SELECT * FROM check_result WHERE {' OR '.join(clauses)} ORDER BY id", params
    ).fetchall()


def _rows_by_table(conn: sqlite3.Connection, ticket_id: int, ticket_row: sqlite3.Row) -> dict[str, list[sqlite3.Row]]:
    stage_run_rows = _rows_where(conn, "stage_run", "ticket_id", ticket_id)
    evidence_tuple_rows = _rows_where(conn, "evidence_tuple", "ticket_id", ticket_id)
    stage_run_ids = [row["id"] for row in stage_run_rows]
    evidence_tuple_ids = [row["id"] for row in evidence_tuple_rows]
    return {
        "ticket": [ticket_row],
        "stage_run": stage_run_rows,
        "tool_call": _rows_in(conn, "tool_call", "stage_run_id", stage_run_ids),
        "artefact": _rows_where(conn, "artefact", "ticket_id", ticket_id),
        "guard_decision": _rows_where(conn, "guard_decision", "ticket_id", ticket_id),
        "reviewer_set": _rows_where(conn, "reviewer_set", "ticket_id", ticket_id),
        "approval_record": _rows_where(conn, "approval_record", "ticket_id", ticket_id),
        "waiver": _rows_where(conn, "waiver", "ticket_id", ticket_id),
        "evidence_tuple": evidence_tuple_rows,
        "incident_observation": _rows_where(conn, "incident_observation", "ticket_id", ticket_id),
        "external_write": _rows_where(conn, "external_write", "ticket_id", ticket_id),
        "check_result": _check_result_rows(conn, stage_run_ids, evidence_tuple_ids),
        "tag": _rows_where(conn, "tag", "ticket_id", ticket_id),
    }


def _envelope(table: str, row: sqlite3.Row, ticket_data_class: str | None, retention_until_fallback: str) -> dict:
    keys = row.keys()
    return {
        "table": table,
        "data_class": row["data_class"] if "data_class" in keys else ticket_data_class,
        "redaction_state": row["redaction_state"] if "redaction_state" in keys else None,
        "retention_until": row["retention_until"] if "retention_until" in keys else retention_until_fallback,
        "row": dict(row),
    }


def _add_days(now: str, days: int) -> str:
    return (datetime.fromisoformat(now) + timedelta(days=days)).isoformat(timespec="seconds")


def _scan(
    conn: sqlite3.Connection, *, ticket_id: int, data_class: str | None, payload, provenance: dict,
    profile_path: Path, owners_path: Path,
) -> guard.Decision:
    operation = guard.Operation(
        crossing=CROSSING,
        route_id=ROUTE_ID,
        payload=payload,
        input_classes=(data_class,),
        source_identity="ticket_record",
        destination_identity="export_directory",
        content_provenance=provenance,
        ticket_id=ticket_id,
    )
    return guard.decide(conn, operation, profile_path=profile_path, owners_path=owners_path)


def _branch_patch(ticket_row: sqlite3.Row, ticket_id: int, runs_dir: Path) -> str:
    """`git diff base_sha..head_sha` from the ticket's own clone, or an empty patch when there is no branch yet."""
    branch, base_sha = ticket_row["branch"], ticket_row["base_sha"]
    repo_dir = Path(runs_dir) / "tickets" / str(ticket_id) / "repo"
    if not branch or not base_sha or not repo_dir.is_dir():
        return ""
    head_sha = ticket_row["head_sha"] or base_sha
    result = subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "diff", f"{base_sha}..{head_sha}"],
        cwd=repo_dir, capture_output=True, text=True, check=True,
    )
    return result.stdout


def export_ticket(
    conn: sqlite3.Connection,
    ticket_id: int,
    *,
    runs_dir: Path = RUNS_DIR,
    now: str | None = None,
    profile_path: Path = trust_profile.DEFAULT_TRUST_PROFILE_PATH,
    owners_path: Path = owners.DEFAULT_OWNERS_PATH,
) -> dict:
    """Write `<runs_dir>/exports/<ticket_id>/<export_id>/` and return its manifest metadata.

    Raises `ExportRefused` before writing anything when the guard denies
    the export as a whole (an unauthorised route, an inactive trust
    profile, or a secret in the authorisation payload itself). After that
    one decision allows, each table's row file and each artefact's file is
    scanned again on its own: a deny on one of those excludes only that
    item -- its file is never written, and `manifest.json` records the
    exclusion and the guard's reason codes -- rather than refusing the
    whole export.
    """
    now = now or record.now()
    ticket_row = record.get(conn, "ticket", ticket_id)
    if ticket_row is None:
        raise ExportRefused(f"no such ticket: {ticket_id}")
    ticket_data_class = ticket_row["data_class"]

    rows_by_table = _rows_by_table(conn, ticket_id, ticket_row)
    artefact_ids = sorted(row["id"] for row in rows_by_table["artefact"])

    overall_decision = _scan(
        conn, ticket_id=ticket_id, data_class=ticket_data_class,
        payload={
            "ticket_record": {"ticket_id": ticket_id},
            "artefacts": {"tables": list(EXPORT_TABLES), "artefact_ids": artefact_ids},
        },
        provenance={"ticket_id": ticket_id}, profile_path=profile_path, owners_path=owners_path,
    )
    if overall_decision.decision != "allow":
        raise ExportRefused(f"export of ticket {ticket_id} refused: {list(overall_decision.reason_codes)}")

    export_id = uuid.uuid4().hex
    export_dir = Path(runs_dir) / "exports" / str(ticket_id) / export_id
    route = trust_profile.load_trust_profile(profile_path).routes[ROUTE_ID]
    retention_until = _add_days(now, route.retention_days)

    files: dict[str, str] = {}
    excluded_tables: list[dict] = []
    excluded_artefacts: list[dict] = []

    for table in EXPORT_TABLES:
        envelopes = [_envelope(table, row, ticket_data_class, retention_until) for row in rows_by_table[table]]
        text = canonical.canonical_json(envelopes).decode() + "\n"
        decision = _scan(
            conn, ticket_id=ticket_id, data_class=ticket_data_class, payload=text,
            provenance={"ticket_id": ticket_id, "table": table},
            profile_path=profile_path, owners_path=owners_path,
        )
        if decision.decision == "deny":
            excluded_tables.append({"table": table, "reason_codes": list(decision.reason_codes)})
            continue
        rel_path = f"rows/{table}.json"
        write_text(export_dir / rel_path, text)
        files[rel_path] = hashlib.sha256(text.encode()).hexdigest()

    for artefact_row in rows_by_table["artefact"]:
        artefact_id = artefact_row["id"]
        guard_decision_id = artefact_row["guard_decision_id"]
        if guard_decision_id is not None:
            named_decision = record.get(conn, "guard_decision", guard_decision_id)
            if named_decision is not None and named_decision["decision"] == "deny":
                excluded_artefacts.append({
                    "artefact_id": artefact_id,
                    "reason_codes": json.loads(named_decision["reason_codes"] or "[]"),
                })
                continue
        source_path = Path(artefact_row["path"]) if artefact_row["path"] else None
        if source_path is None or not source_path.is_file():
            continue
        text = source_path.read_text()
        decision = _scan(
            conn, ticket_id=ticket_id, data_class=ticket_data_class, payload=text,
            provenance={"ticket_id": ticket_id, "artefact_id": artefact_id},
            profile_path=profile_path, owners_path=owners_path,
        )
        if decision.decision == "deny":
            excluded_artefacts.append({"artefact_id": artefact_id, "reason_codes": list(decision.reason_codes)})
            continue
        rel_path = f"artefacts/{artefact_id}/{source_path.name}"
        write_text(export_dir / rel_path, text)
        files[rel_path] = hashlib.sha256(text.encode()).hexdigest()

    branch_patch_text = _branch_patch(ticket_row, ticket_id, runs_dir)
    write_text(export_dir / "branch.patch", branch_patch_text)
    files["branch.patch"] = hashlib.sha256(branch_patch_text.encode()).hexdigest()

    content_hash = canonical.content_hash({"files": files})
    manifest = {
        "ticket_id": ticket_id,
        "export_id": export_id,
        "guard_decision_id": overall_decision.id,
        "data_class": ticket_data_class,
        "retention_until": retention_until,
        "files": files,
        "excluded": {"tables": excluded_tables, "artefacts": excluded_artefacts},
        "content_hash": content_hash,
    }
    write_text(export_dir / "manifest.json", canonical.canonical_json(manifest).decode() + "\n")

    manifest_artefact_id = artefact_registry.register(
        conn, ticket_id=ticket_id, kind="export", path=export_dir / "manifest.json",
        data_class=ticket_data_class, guard_decision_id=overall_decision.id,
    )

    return {
        "export_dir": export_dir,
        "export_id": export_id,
        "manifest_artefact_id": manifest_artefact_id,
        "guard_decision_id": overall_decision.id,
        "content_hash": content_hash,
        "retention_until": retention_until,
    }


def _validate_declared_path(export_dir_resolved: Path, rel_path: str) -> Path:
    pure = PurePosixPath(rel_path)
    if pure.is_absolute():
        raise ImportRefused(f"declared path is absolute: {rel_path}")
    if any(part == ".." for part in pure.parts):
        raise ImportRefused(f"declared path contains a traversal segment: {rel_path}")
    resolved = (export_dir_resolved / rel_path).resolve()
    if not resolved.is_relative_to(export_dir_resolved):
        raise ImportRefused(f"declared path resolves outside the export directory: {rel_path}")
    return resolved


def import_export(conn: sqlite3.Connection, export_dir: Path, *, runs_dir: Path = RUNS_DIR) -> dict:
    """Verify `export_dir` against its own manifest and insert every declared row, or refuse without writing anything.

    Every check below runs before the first `record.insert`: the
    manifest's content hash against its own declared file list, every
    declared file's hash against the bytes actually on disk, every
    declared path's safety (not absolute, no traversal segment, no
    symlink resolving outside `export_dir`), no undeclared file present,
    and no row-id collision in the target record. Only once every check
    passes does insertion begin, inside one transaction (foreign keys
    deferred to its commit, since `artefact` and `guard_decision` can
    reference each other): a failure there rolls the whole import back
    rather than leaving a partial record.
    """
    export_dir = Path(export_dir)
    manifest_path = export_dir / "manifest.json"
    if not manifest_path.is_file():
        raise ImportRefused(f"no manifest.json under {export_dir}")
    manifest = json.loads(manifest_path.read_text())

    computed_content_hash = canonical.content_hash({"files": manifest["files"]})
    if computed_content_hash != manifest["content_hash"]:
        raise ImportRefused("export content hash does not match its declared file list")

    export_dir_resolved = export_dir.resolve()
    resolved_paths: dict[str, Path] = {}
    for rel_path, declared_sha in manifest["files"].items():
        resolved = _validate_declared_path(export_dir_resolved, rel_path)
        if not resolved.is_file():
            raise ImportRefused(f"declared file missing: {rel_path}")
        actual_sha = hashlib.sha256(resolved.read_bytes()).hexdigest()
        if actual_sha != declared_sha:
            raise ImportRefused(f"content hash mismatch for {rel_path}")
        resolved_paths[rel_path] = resolved

    declared = set(manifest["files"])
    found: set[str] = set()
    for path in export_dir.rglob("*"):
        if path.is_file():
            rel = path.relative_to(export_dir).as_posix()
            if rel != "manifest.json":
                found.add(rel)
    undeclared = found - declared
    if undeclared:
        raise ImportRefused(f"undeclared file(s) present in export directory: {sorted(undeclared)}")

    rows_by_table: dict[str, list[dict]] = {}
    for table in EXPORT_TABLES:
        rel_path = f"rows/{table}.json"
        rows_by_table[table] = json.loads(resolved_paths[rel_path].read_text()) if rel_path in resolved_paths else []

    for table, envelopes in rows_by_table.items():
        for envelope in envelopes:
            if record.get(conn, table, envelope["row"]["id"]) is not None:
                raise ImportRefused(f"{table} {envelope['row']['id']} already exists in the target record")

    content_hash = manifest["content_hash"]
    imported_ticket_id = None
    conn.execute("PRAGMA defer_foreign_keys = ON")
    try:
        for table in EXPORT_TABLES:
            for envelope in rows_by_table[table]:
                fields = dict(envelope["row"])
                if table == "artefact":
                    art_prefix = f"artefacts/{fields['id']}/"
                    matches = [rp for rp in resolved_paths if rp.startswith(art_prefix)]
                    if matches:
                        source = resolved_paths[matches[0]]
                        dest = Path(runs_dir) / "imports" / content_hash / str(fields["id"]) / source.name
                        write_bytes(dest, source.read_bytes())
                        fields["path"] = str(dest)
                    fields["imported_from"] = content_hash
                elif table == "ticket":
                    fields["imported_from"] = content_hash
                    imported_ticket_id = fields["id"]
                record.insert(conn, table, **fields)
        conn.commit()
    except sqlite3.Error as exc:
        conn.rollback()
        raise ImportRefused(f"import refused: {exc}") from exc

    return {"ticket_id": imported_ticket_id, "content_hash": content_hash}


def purge_export(conn: sqlite3.Connection, export_dir: Path, *, now: str | None = None) -> str:
    """Delete `export_dir` once its manifest's `retention_until` has passed, else refuse; either way records a utility run."""
    now = now or record.now()
    export_dir = Path(export_dir)
    manifest_path = export_dir / "manifest.json"
    if not manifest_path.is_file():
        raise PurgeRefused(f"no manifest.json under {export_dir}")
    manifest = json.loads(manifest_path.read_text())

    run_id = run_ledger.open_utility_run(conn, kind="purge", inputs=str(export_dir))
    if datetime.fromisoformat(now) < datetime.fromisoformat(manifest["retention_until"]):
        run_ledger.finish(conn, run_id, "refused", table="utility_run")
        raise PurgeRefused(f"export directory is within its retention period (until {manifest['retention_until']})")
    remove_tree(export_dir)
    run_ledger.finish(conn, run_id, "pass", table="utility_run")
    return f"purged {export_dir}"
