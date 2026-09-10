"""`factory/scripts/tools/fixture_from_export`: the first redacted real fixture under the `tickets/` eval kind.

Drives the actual script as a subprocess over a real `export.export_ticket`
output -- the same governed export the closing run's own fixture comes
from -- into a temporary root, never the real `factory/`, then proves the
completeness walk both accepts the directory it wrote and refuses one
whose top-level redaction review drops any of its four required fields.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from runner import evals, export, governance, record
from runner.db import connect
from runner.paths import FACTORY_DIR
from runner.tickets import open_ticket

SCRIPT = FACTORY_DIR / "scripts" / "tools" / "fixture_from_export"
FIXTURES_DIR = Path(__file__).parent / "fixtures" / "export_import"
FAR_FUTURE = "2999-01-01T00:00:00+00:00"


@pytest.fixture
def conn(tmp_path):
    connection = connect(tmp_path / "factory.sqlite")
    yield connection
    connection.close()


def _activate(conn, profile_path, owners_path):
    """Satisfy the trust profile's quorum through the real governance decisions, the
    same seam `test_export_import.py` uses so `export_ticket` below actually allows."""
    proposal = governance.propose(profile_path, owners_path)
    for role in ("security_approver", "legal_data_governance_approver"):
        governance.decide(
            conn, proposal,
            actor_identity="abhishek", role=role, decision="approve",
            expires_at=FAR_FUTURE, attestation_version="v1", attestation_hash=f"att-{role}",
            owners_path=owners_path, profile_path=profile_path,
        )
    conn.commit()


def _seed_exported_ticket(conn, runs_dir) -> tuple[Path, int]:
    profile_path, owners_path = FIXTURES_DIR / "trust-profile.yaml", FIXTURES_DIR / "owners.yaml"
    _activate(conn, profile_path, owners_path)
    ticket_id = open_ticket(conn, source_kind="fixture", title="fixture_from_export source ticket", data_class="internal")
    record.update(conn, "ticket", ticket_id, state="review")
    conn.commit()
    result = export.export_ticket(conn, ticket_id, runs_dir=runs_dir, profile_path=profile_path, owners_path=owners_path)
    return Path(result["export_dir"]), ticket_id


def _run_script(export_dir: Path, ticket_id: int, root: Path, *, reviewer="abhishek", redacted_fields="names"):
    return subprocess.run(
        [
            sys.executable, str(SCRIPT), str(export_dir), str(ticket_id),
            "--reviewer", reviewer, "--redacted-fields", redacted_fields,
            "--root", str(root), "--now", "2026-01-01T00:00:00+00:00",
        ],
        capture_output=True, text=True,
    )


def test_the_script_writes_a_ticket_eval_directory_the_completeness_walk_accepts(conn, tmp_path):
    """The script copies a real export directory under
    `factory/evals/tickets/<id>/fixtures/export/` and writes an `eval.yaml` naming the
    owner, the target failure modes, and the four-field redaction review, including the
    export's own manifest content hash -- `evals.check` accepts the result under a
    temporary fixture root, never the real `factory/`."""
    export_dir, ticket_id = _seed_exported_ticket(conn, tmp_path / "runs")
    manifest = json.loads((export_dir / "manifest.json").read_text())
    fixture_root = tmp_path / "fixture-root"

    result = _run_script(export_dir, ticket_id, fixture_root)

    assert result.returncode == 0, result.stderr
    ticket_eval_dir = fixture_root / "factory" / "evals" / "tickets" / str(ticket_id)
    spec = yaml.safe_load((ticket_eval_dir / "eval.yaml").read_text())
    assert spec["owner"] == "abhishek"
    assert spec["target_failure_modes"] == ["stale_approval"]
    assert spec["redaction_review"]["export_content_hash"] == manifest["content_hash"]
    assert spec["redaction_review"]["redacted_fields"] == ["names"]
    assert (ticket_eval_dir / "fixtures" / "export" / "manifest.json").is_file()
    evals.check(ticket_eval_dir)  # raises on failure; no exception is the assertion
    assert ticket_eval_dir in evals.expected_eval_dirs(fixture_root / "factory")


@pytest.mark.parametrize("missing_field", ["reviewer_identity", "reviewed_at", "redacted_fields", "export_content_hash"])
def test_must_reject_a_tickets_eval_directory_missing_one_redaction_review_field(conn, tmp_path, missing_field):
    """The completeness walk refuses a `tickets/` `eval.yaml` whose
    top-level redaction review drops any one of its four required fields."""
    export_dir, ticket_id = _seed_exported_ticket(conn, tmp_path / "runs")
    fixture_root = tmp_path / "fixture-root"
    _run_script(export_dir, ticket_id, fixture_root)
    ticket_eval_dir = fixture_root / "factory" / "evals" / "tickets" / str(ticket_id)
    eval_yaml = ticket_eval_dir / "eval.yaml"
    spec = yaml.safe_load(eval_yaml.read_text())
    del spec["redaction_review"][missing_field]
    eval_yaml.write_text(yaml.safe_dump(spec))

    with pytest.raises(evals.EvalDirectoryError, match="redaction review"):
        evals.check(ticket_eval_dir)


def test_must_reject_an_export_directory_with_no_manifest(tmp_path):
    """The script refuses before copying anything when `export_dir` carries no `manifest.json`
    -- there is no `export_content_hash` to write down honestly without it."""
    empty_export_dir = tmp_path / "not-an-export"
    empty_export_dir.mkdir()
    fixture_root = tmp_path / "fixture-root"

    result = _run_script(empty_export_dir, 999, fixture_root)

    assert result.returncode != 0
    assert "manifest.json" in result.stderr
    assert not (fixture_root / "factory" / "evals" / "tickets" / "999").exists()
