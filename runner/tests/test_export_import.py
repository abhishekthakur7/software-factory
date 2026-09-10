"""Governed export, import and purge.

Every export test activates a tmp copy of the fixture trust profile first,
the same `profile_paths`/`_activate` convention `test_guard.py` and
`test_outbox.py` use, so a wrong guard or governance computation would fail
these tests too rather than only its own. A malicious-import test always
starts from a genuinely valid export produced by `export_ticket` and then
introduces exactly one defect (a tampered byte, a renamed path, a stray
symlink, an extra file), so the test proves the specific check named in its
title refuses -- not an incidental content-hash mismatch that a hand-built
manifest would also trip.
"""
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from runner import artefact_registry, canonical, export, git_trees, governance, record
from runner.db import connect
from runner.tickets import open_ticket

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "export_import"
FAR_FUTURE = "2999-01-01T00:00:00+00:00"

_COMMIT_ENV = {
    "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@example.invalid",
}


@pytest.fixture
def conn(tmp_path):
    connection = connect(tmp_path / "factory.sqlite")
    yield connection
    connection.close()


@pytest.fixture
def runs_dir(tmp_path):
    return tmp_path / "runs"


@pytest.fixture
def profile_paths(tmp_path):
    """A tmp copy of the fixture trust profile and owners file."""
    profile_path = tmp_path / "trust-profile.yaml"
    owners_path = tmp_path / "owners.yaml"
    shutil.copy(FIXTURES_DIR / "trust-profile.yaml", profile_path)
    shutil.copy(FIXTURES_DIR / "owners.yaml", owners_path)
    return profile_path, owners_path


def _activate(conn, profile_path, owners_path, expires_at=FAR_FUTURE):
    """Satisfy the trust profile's quorum through the real governance decisions."""
    proposal = governance.propose(profile_path, owners_path)
    for role in ("security_approver", "legal_data_governance_approver"):
        governance.decide(
            conn, proposal,
            actor_identity="abhishek", role=role, decision="approve",
            expires_at=expires_at, attestation_version="v1", attestation_hash=f"att-{role}",
            owners_path=owners_path, profile_path=profile_path,
        )
    conn.commit()
    return proposal


def _seed_ticket(conn, *, data_class="internal", title="export fixture ticket"):
    ticket_id = open_ticket(conn, source_kind="fixture", title=title, data_class=data_class)
    record.update(conn, "ticket", ticket_id, state="review")
    return ticket_id


def _seed_full_ticket_rows(conn, ticket_id):
    """One row in every exported table besides `ticket` and `artefact`."""
    stage_run_id = record.insert(
        conn, "stage_run", ticket_id=ticket_id, stage="implementation", attempt=1, outcome="pass", started_at=record.now(),
    )
    record.insert(conn, "tool_call", stage_run_id=stage_run_id, seq=1, tool="lint", tool_version="1")
    evidence_tuple_id = record.insert(
        conn, "evidence_tuple", kind="plan", ticket_id=ticket_id, base_sha="base-1",
        created_at=record.now(), content_hash="plan-hash-1",
    )
    record.insert(
        conn, "check_result", stage_run_id=stage_run_id, check_name="lint", check_tier="blocking",
        plan_tuple_id=evidence_tuple_id, source="runner", result="pass",
        canonical_serialization_version=1, content_hash="check-hash-1",
    )
    reviewer_set_id = record.insert(
        conn, "reviewer_set", ticket_id=ticket_id, kind="planned",
        canonical_serialization_version=1, content_hash="rs-hash-1",
    )
    record.insert(
        conn, "approval_record", ticket_id=ticket_id, gate="plan", decision="approve",
        subject_hash="plan-hash-1", reviewer_set_id=reviewer_set_id,
        decided_at=record.now(), canonical_serialization_version=1, content_hash="ar-hash-1",
    )
    record.insert(
        conn, "waiver", ticket_id=ticket_id, policy_id="p1", policy_version="1",
        subject_kind="check_result", subject_hash="check-hash-1", issued_at=record.now(),
        expires_at=FAR_FUTURE, canonical_serialization_version=1, content_hash="waiver-hash-1",
    )
    record.insert(
        conn, "incident_observation", ticket_id=ticket_id, record_kind="production_incident_event",
        created_at=record.now(), severity="low", occurred_at=record.now(),
    )
    record.insert(
        conn, "external_write", ticket_id=ticket_id, operation="digest", state="reconciled",
        payload_digest="digest-1", created_at=record.now(),
    )
    record.insert(
        conn, "tag", ticket_id=ticket_id, event_kind="abandoned", fm_id="unjustified_abstraction",
        ref=f"ticket:{ticket_id}", tagged_by="abhishek", tagged_at=record.now(),
    )
    return stage_run_id, evidence_tuple_id


def _seed_artefact(conn, runs_dir, ticket_id, *, text, kind="brief", data_class="internal", guard_decision_id=None):
    path = Path(runs_dir) / "tickets" / str(ticket_id) / f"{kind}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return artefact_registry.register(
        conn, ticket_id=ticket_id, kind=kind, path=path, data_class=data_class, guard_decision_id=guard_decision_id,
    )


def _git(args, cwd, env=None):
    full_env = {**os.environ, **env} if env else None
    return subprocess.run(
        ["git", "-c", "commit.gpgsign=false", *args], cwd=cwd, env=full_env,
        capture_output=True, text=True, check=True,
    )


def _source_repo(tmp_path):
    repo = tmp_path / "source-repo"
    repo.mkdir()
    _git(["init", "-q"], cwd=repo)
    _git(["checkout", "-q", "-b", "main"], cwd=repo)
    (repo / "README.md").write_text("seed\n")
    _git(["add", "-A"], cwd=repo)
    _git(["commit", "-q", "-m", "seed"], cwd=repo, env=_COMMIT_ENV)
    return repo


def _clone_ticket_branch(conn, tmp_path, runs_dir, ticket_id):
    """Give `ticket_id` a real branch, worktree, and one commit ahead of `base_sha`."""
    source = _source_repo(tmp_path)
    trees = git_trees.clone_for_ticket(
        conn, ticket_id, source_checkout=source, target_branch="main", runs_dir=runs_dir,
    )
    (trees.worktree / "change.txt").write_text("a real change for the branch patch\n")
    _git(["add", "-A"], cwd=trees.worktree)
    _git(["commit", "-q", "-m", "change"], cwd=trees.worktree, env=_COMMIT_ENV)
    git_trees.record_head(conn, ticket_id, trees.worktree)
    return trees


def _load_manifest(export_dir: Path) -> dict:
    return json.loads((Path(export_dir) / "manifest.json").read_text())


def _save_manifest(export_dir: Path, manifest: dict) -> None:
    (Path(export_dir) / "manifest.json").write_text(canonical.canonical_json(manifest).decode() + "\n")


def _table_rows(export_dir: Path, table: str) -> dict:
    """`{row_id: envelope}` from `rows/<table>.json`, or `{}` when the table was excluded."""
    path = Path(export_dir) / "rows" / f"{table}.json"
    if not path.is_file():
        return {}
    return {envelope["row"]["id"]: envelope for envelope in json.loads(path.read_text())}


# ---------------------------------------------------------------------------
# 1. an export directory holds the ticket's rows, artefacts, guard decisions
#    and the branch as a patch.
# ---------------------------------------------------------------------------

def test_export_writes_a_directory_with_ticket_rows_artefacts_and_branch_patch(conn, runs_dir, profile_paths, tmp_path):
    profile_path, owners_path = profile_paths
    _activate(conn, profile_path, owners_path)
    ticket_id = _seed_ticket(conn)
    _seed_full_ticket_rows(conn, ticket_id)
    _seed_artefact(conn, runs_dir, ticket_id, text="a governed artefact body")
    _clone_ticket_branch(conn, tmp_path, runs_dir, ticket_id)
    conn.commit()

    result = export.export_ticket(conn, ticket_id, runs_dir=runs_dir, profile_path=profile_path, owners_path=owners_path)
    export_dir = Path(result["export_dir"])

    assert (export_dir / "manifest.json").is_file()
    for table in export.EXPORT_TABLES:
        assert (export_dir / "rows" / f"{table}.json").is_file(), table
    ticket_rows = _table_rows(export_dir, "ticket")
    assert ticket_rows[ticket_id]["row"]["title"] == "export fixture ticket"
    tag_rows = _table_rows(export_dir, "tag")
    assert any(row["row"]["event_kind"] == "abandoned" for row in tag_rows.values())

    artefact_dirs = list((export_dir / "artefacts").iterdir())
    assert len(artefact_dirs) == 1
    assert (artefact_dirs[0] / "brief.md").read_text() == "a governed artefact body"

    branch_patch = (export_dir / "branch.patch").read_text()
    assert "diff --git" in branch_patch
    assert "a real change for the branch patch" in branch_patch


# ---------------------------------------------------------------------------
# 2. one `allow` guard_decision authorises the export; an unauthorised
#    route refuses the whole export.
# ---------------------------------------------------------------------------

def test_export_records_one_allow_guard_decision_authorising_the_route(conn, runs_dir, profile_paths):
    profile_path, owners_path = profile_paths
    _activate(conn, profile_path, owners_path)
    ticket_id = _seed_ticket(conn)
    conn.commit()

    result = export.export_ticket(conn, ticket_id, runs_dir=runs_dir, profile_path=profile_path, owners_path=owners_path)

    decision_row = record.get(conn, "guard_decision", result["guard_decision_id"])
    assert decision_row["decision"] == "allow"
    assert decision_row["route_id"] == "governed_export_display"
    assert decision_row["operation"] == "export"


def test_must_reject_export_over_a_route_the_profile_does_not_authorise(conn, runs_dir, profile_paths):
    """must-reject: a class the route's max_class does not admit refuses the whole export."""
    profile_path, owners_path = profile_paths
    _activate(conn, profile_path, owners_path)
    ticket_id = _seed_ticket(conn, data_class="restricted")
    conn.commit()

    before = conn.execute("SELECT COUNT(*) FROM guard_decision").fetchone()[0]
    with pytest.raises(export.ExportRefused):
        export.export_ticket(conn, ticket_id, runs_dir=runs_dir, profile_path=profile_path, owners_path=owners_path)

    after = conn.execute("SELECT COUNT(*) FROM guard_decision").fetchone()[0]
    assert after == before + 1
    denied = conn.execute("SELECT decision FROM guard_decision ORDER BY id DESC LIMIT 1").fetchone()
    assert denied["decision"] == "deny"
    assert not (runs_dir / "exports").exists()


# ---------------------------------------------------------------------------
# 3, 4. every row carries the data_class/redaction_state/retention_until
#    it had in the record.
# ---------------------------------------------------------------------------

def test_export_rows_carry_their_recorded_classification_and_retention(conn, runs_dir, profile_paths):
    profile_path, owners_path = profile_paths
    _activate(conn, profile_path, owners_path)
    ticket_id = _seed_ticket(conn, data_class="confidential")
    path = Path(runs_dir) / "tickets" / str(ticket_id) / "brief.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("classified artefact body")
    artefact_id = record.insert(
        conn, "artefact", ticket_id=ticket_id, kind="brief", version=1, path=str(path),
        hash=hashlib.sha256(path.read_bytes()).hexdigest(), created_at=record.now(),
        data_class="confidential", redaction_state="redacted", retention_until="2031-01-01T00:00:00+00:00",
    )
    conn.commit()

    result = export.export_ticket(conn, ticket_id, runs_dir=runs_dir, profile_path=profile_path, owners_path=owners_path)
    export_dir = Path(result["export_dir"])

    artefact_envelope = _table_rows(export_dir, "artefact")[artefact_id]
    assert artefact_envelope["data_class"] == "confidential"
    assert artefact_envelope["redaction_state"] == "redacted"
    assert artefact_envelope["retention_until"] == "2031-01-01T00:00:00+00:00"

    ticket_envelope = _table_rows(export_dir, "ticket")[ticket_id]
    assert ticket_envelope["data_class"] == "confidential"
    assert ticket_envelope["redaction_state"] is None
    assert ticket_envelope["retention_until"] == result["retention_until"]


# ---------------------------------------------------------------------------
# 5. a content hash is recorded on the export directory when it is created.
# ---------------------------------------------------------------------------

def test_export_records_a_content_hash_over_its_declared_file_list(conn, runs_dir, profile_paths):
    profile_path, owners_path = profile_paths
    _activate(conn, profile_path, owners_path)
    ticket_id = _seed_ticket(conn)
    conn.commit()

    result = export.export_ticket(conn, ticket_id, runs_dir=runs_dir, profile_path=profile_path, owners_path=owners_path)
    manifest = _load_manifest(result["export_dir"])

    assert manifest["content_hash"] == result["content_hash"]
    assert manifest["content_hash"] == canonical.content_hash({"files": manifest["files"]})


# ---------------------------------------------------------------------------
# 6. a secret and a raw disallowed payload are absent from the export
#    directory.
# ---------------------------------------------------------------------------

def test_secret_and_denied_artefacts_are_excluded_and_never_written_to_disk(conn, runs_dir, profile_paths):
    profile_path, owners_path = profile_paths
    _activate(conn, profile_path, owners_path)
    ticket_id = _seed_ticket(conn)
    secret_text = "leaked credential: AKIAABCDEFGHIJKLMNOP embedded in this artefact"
    secret_artefact_id = _seed_artefact(conn, runs_dir, ticket_id, text=secret_text, kind="secret")

    deny_id = record.insert(
        conn, "guard_decision", ticket_id=ticket_id, operation="dispatch", route_id="hosted_model",
        decision="deny", reason_codes="[]", created_at=record.now(), canonical_serialization_version=1,
        content_hash="deny-1",
    )
    disallowed_artefact_id = _seed_artefact(
        conn, runs_dir, ticket_id, text="raw disallowed payload", kind="disallowed", guard_decision_id=deny_id,
    )
    conn.commit()

    result = export.export_ticket(conn, ticket_id, runs_dir=runs_dir, profile_path=profile_path, owners_path=owners_path)
    export_dir = Path(result["export_dir"])
    manifest = _load_manifest(export_dir)

    excluded_ids = {entry["artefact_id"] for entry in manifest["excluded"]["artefacts"]}
    assert excluded_ids == {secret_artefact_id, disallowed_artefact_id}
    assert not (export_dir / "artefacts" / str(secret_artefact_id)).exists()
    assert not (export_dir / "artefacts" / str(disallowed_artefact_id)).exists()

    for path in export_dir.rglob("*"):
        if path.is_file():
            assert "AKIAABCDEFGHIJKLMNOP" not in path.read_text(errors="ignore")
            assert "raw disallowed payload" not in path.read_text(errors="ignore")


# ---------------------------------------------------------------------------
# 7-11. import verifies the export's content hash and refuses a malicious
#    or tampered directory before writing anything.
# ---------------------------------------------------------------------------

def _export_minimal(conn, runs_dir, profile_path, owners_path):
    _activate(conn, profile_path, owners_path)
    ticket_id = _seed_ticket(conn)
    _seed_full_ticket_rows(conn, ticket_id)
    _seed_artefact(conn, runs_dir, ticket_id, text="a governed artefact body")
    conn.commit()
    result = export.export_ticket(conn, ticket_id, runs_dir=runs_dir, profile_path=profile_path, owners_path=owners_path)
    return ticket_id, Path(result["export_dir"])


def test_must_reject_import_of_an_export_whose_bytes_no_longer_match_its_declared_hash(conn, runs_dir, profile_paths, tmp_path):
    profile_path, owners_path = profile_paths
    _ticket_id, export_dir = _export_minimal(conn, runs_dir, profile_path, owners_path)
    (export_dir / "branch.patch").write_text("tampered after export\n")

    target_conn = connect(tmp_path / "target.sqlite")
    with pytest.raises(export.ImportRefused):
        export.import_export(target_conn, export_dir, runs_dir=tmp_path / "target-runs")
    assert record.get(target_conn, "ticket", 1) is None
    target_conn.close()


def test_must_reject_import_of_a_declared_absolute_path(conn, runs_dir, profile_paths, tmp_path):
    profile_path, owners_path = profile_paths
    ticket_id, export_dir = _export_minimal(conn, runs_dir, profile_path, owners_path)
    manifest = _load_manifest(export_dir)
    a_path, a_hash = next(iter(manifest["files"].items()))
    del manifest["files"][a_path]
    manifest["files"]["/etc/passwd"] = a_hash
    manifest["content_hash"] = canonical.content_hash({"files": manifest["files"]})
    _save_manifest(export_dir, manifest)

    target_conn = connect(tmp_path / "target.sqlite")
    with pytest.raises(export.ImportRefused):
        export.import_export(target_conn, export_dir, runs_dir=tmp_path / "target-runs")
    assert record.get(target_conn, "ticket", ticket_id) is None
    target_conn.close()


def test_must_reject_import_of_a_declared_path_with_a_traversal_segment(conn, runs_dir, profile_paths, tmp_path):
    profile_path, owners_path = profile_paths
    ticket_id, export_dir = _export_minimal(conn, runs_dir, profile_path, owners_path)
    manifest = _load_manifest(export_dir)
    a_path, a_hash = next(iter(manifest["files"].items()))
    del manifest["files"][a_path]
    manifest["files"]["../outside.json"] = a_hash
    manifest["content_hash"] = canonical.content_hash({"files": manifest["files"]})
    _save_manifest(export_dir, manifest)

    target_conn = connect(tmp_path / "target.sqlite")
    with pytest.raises(export.ImportRefused):
        export.import_export(target_conn, export_dir, runs_dir=tmp_path / "target-runs")
    assert record.get(target_conn, "ticket", ticket_id) is None
    target_conn.close()


def test_must_reject_import_of_a_declared_path_whose_symlink_resolves_outside_the_export_directory(conn, runs_dir, profile_paths, tmp_path):
    profile_path, owners_path = profile_paths
    ticket_id, export_dir = _export_minimal(conn, runs_dir, profile_path, owners_path)

    outside = tmp_path / "outside_secret.txt"
    outside.write_text("content that lives outside the export directory\n")
    link = export_dir / "evil.json"
    os.symlink(os.path.relpath(outside, export_dir), link)

    manifest = _load_manifest(export_dir)
    manifest["files"]["evil.json"] = hashlib.sha256(outside.read_bytes()).hexdigest()
    manifest["content_hash"] = canonical.content_hash({"files": manifest["files"]})
    _save_manifest(export_dir, manifest)

    target_conn = connect(tmp_path / "target.sqlite")
    with pytest.raises(export.ImportRefused):
        export.import_export(target_conn, export_dir, runs_dir=tmp_path / "target-runs")
    assert record.get(target_conn, "ticket", ticket_id) is None
    target_conn.close()


def test_must_reject_import_of_a_directory_holding_a_file_the_manifest_does_not_declare(conn, runs_dir, profile_paths, tmp_path):
    profile_path, owners_path = profile_paths
    ticket_id, export_dir = _export_minimal(conn, runs_dir, profile_path, owners_path)
    (export_dir / "rows" / "undeclared.json").write_text("[]\n")

    target_conn = connect(tmp_path / "target.sqlite")
    with pytest.raises(export.ImportRefused):
        export.import_export(target_conn, export_dir, runs_dir=tmp_path / "target-runs")
    assert record.get(target_conn, "ticket", ticket_id) is None
    target_conn.close()


# ---------------------------------------------------------------------------
# 12. prose content brought in by import is marked untrusted.
# ---------------------------------------------------------------------------

def test_imported_ticket_and_artefact_rows_are_marked_untrusted(conn, runs_dir, profile_paths, tmp_path):
    profile_path, owners_path = profile_paths
    ticket_id, export_dir = _export_minimal(conn, runs_dir, profile_path, owners_path)

    target_conn = connect(tmp_path / "target.sqlite")
    result = export.import_export(target_conn, export_dir, runs_dir=tmp_path / "target-runs")

    imported_ticket = record.get(target_conn, "ticket", ticket_id)
    assert imported_ticket["imported_from"] == result["content_hash"]
    imported_artefacts = target_conn.execute("SELECT * FROM artefact WHERE ticket_id = ?", (ticket_id,)).fetchall()
    assert imported_artefacts
    for row in imported_artefacts:
        assert row["imported_from"] == result["content_hash"]
    target_conn.close()


def test_import_refuses_a_row_id_that_already_exists_in_the_target_record(conn, runs_dir, profile_paths, tmp_path):
    """must-reject: a collision is refused before any write."""
    profile_path, owners_path = profile_paths
    ticket_id, export_dir = _export_minimal(conn, runs_dir, profile_path, owners_path)

    target_conn = connect(tmp_path / "target.sqlite")
    record.insert(target_conn, "ticket", id=ticket_id, state="intake", opened_at=record.now(), title="already here")
    target_conn.commit()

    with pytest.raises(export.ImportRefused):
        export.import_export(target_conn, export_dir, runs_dir=tmp_path / "target-runs")
    target_conn.close()


# ---------------------------------------------------------------------------
# 13. purge removes an expired export and refuses one still within
#    retention, recording the outcome either way.
# ---------------------------------------------------------------------------

def test_purge_removes_an_export_directory_past_its_retention(conn, runs_dir, profile_paths):
    profile_path, owners_path = profile_paths
    _ticket_id, export_dir = _export_minimal(conn, runs_dir, profile_path, owners_path)
    conn.commit()

    far_future_now = "2999-06-01T00:00:00+00:00"
    message = export.purge_export(conn, export_dir, now=far_future_now)
    conn.commit()

    assert not export_dir.exists()
    assert "purged" in message
    outcome = conn.execute(
        "SELECT outcome FROM utility_run WHERE kind = 'purge' ORDER BY id DESC LIMIT 1"
    ).fetchone()["outcome"]
    assert outcome == "pass"


def test_must_reject_purge_of_an_export_directory_still_within_retention(conn, runs_dir, profile_paths):
    profile_path, owners_path = profile_paths
    _ticket_id, export_dir = _export_minimal(conn, runs_dir, profile_path, owners_path)
    conn.commit()

    with pytest.raises(export.PurgeRefused):
        export.purge_export(conn, export_dir, now=record.now())
    conn.commit()

    assert export_dir.exists()
    outcome = conn.execute(
        "SELECT outcome FROM utility_run WHERE kind = 'purge' ORDER BY id DESC LIMIT 1"
    ).fetchone()["outcome"]
    assert outcome == "refused"


# ---------------------------------------------------------------------------
# 14. export, import into an empty record, export again: every hash on the
#    rows themselves reproduces.
# ---------------------------------------------------------------------------

def test_export_import_export_round_trip_reproduces_every_row_hash(conn, runs_dir, profile_paths, tmp_path):
    profile_path, owners_path = profile_paths
    ticket_id, first_export_dir = _export_minimal(conn, runs_dir, profile_path, owners_path)

    target_conn = connect(tmp_path / "target.sqlite")
    target_runs_dir = tmp_path / "target-runs"
    export.import_export(target_conn, first_export_dir, runs_dir=target_runs_dir)
    _activate(target_conn, profile_path, owners_path)

    second_result = export.export_ticket(
        target_conn, ticket_id, runs_dir=target_runs_dir, profile_path=profile_path, owners_path=owners_path,
    )
    second_export_dir = Path(second_result["export_dir"])
    target_conn.close()

    hash_field_by_table = {
        "artefact": "hash",
        "evidence_tuple": "content_hash",
        "approval_record": "content_hash",
        "reviewer_set": "content_hash",
        "waiver": "content_hash",
        "check_result": "content_hash",
    }
    for table, field in hash_field_by_table.items():
        first_rows = _table_rows(first_export_dir, table)
        second_rows = _table_rows(second_export_dir, table)
        assert first_rows, table
        for row_id, envelope in first_rows.items():
            assert second_rows[row_id]["row"][field] == envelope["row"][field], (table, row_id)
