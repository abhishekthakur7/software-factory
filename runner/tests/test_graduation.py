"""`factory graduate evaluate`/`approve`/`reject`: the canonical report, its recorded owner
approval, and the gate's own recorded runs.

Every test opens its own `tmp_path` database and passes an explicit
`manifest_hash` and a fixed `cutoff`, never the real git-derived hash or
wall-clock `now()`, so the suite never depends on this worktree's own
state. `_passing_window` seeds one ticket that, on its own, clears every
one of the nine clauses -- used by the approve/reject/quorum tests, which
care about the approval mechanics, not the clause verdicts themselves.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from runner import canonical, graduation, manifest, owners, record
from runner.db import connect
from runner.paths import FACTORY_DIR, REPO_ROOT
from runner.tests.fixtures.graduation import seed

CUTOFF = "2026-02-01T00:00:00"


def _conn(tmp_path):
    return connect(tmp_path / "factory.sqlite")


def _report(conn, artefact_id):
    row = record.get(conn, "artefact", artefact_id)
    return json.loads(Path(row["path"]).read_text())


def _passing_window(conn, tmp_path, *, manifest_hash: str = "mh1"):
    ticket_id = seed.seed_window_ticket(conn, closed_at="2026-01-10T00:00:00", manifest_hash=manifest_hash)
    seed.seed_coverage(conn, ticket_id, observed_through=CUTOFF)
    seed.seed_gate_run(conn, manifest_hash=manifest_hash, outcome="pass")
    for stage in ("intake", "context_gathering", "clarification", "planning", "implementation", "checks", "human_review"):
        seed.seed_stage_run(conn, ticket_id, stage=stage, manifest_hash=manifest_hash)
    seed.seed_baseline_measure(conn, value=5.0)
    limits_path = seed.write_limits(tmp_path)
    return limits_path, manifest_hash


def test_evaluate_runs_as_a_graduation_utility_run(tmp_path):
    """`evaluate` opens and finishes one `utility_run` of `kind = 'graduation'`."""
    conn = _conn(tmp_path)
    limits_path, manifest_hash = _passing_window(conn, tmp_path)
    conn.commit()

    graduation.evaluate(conn, limits_path=limits_path, manifest_hash=manifest_hash, cutoff=CUTOFF)
    conn.commit()

    runs = conn.execute("SELECT * FROM utility_run WHERE kind = 'graduation'").fetchall()
    assert len(runs) == 1
    assert runs[0]["outcome"] in ("pass", "fail")
    assert runs[0]["ended_at"] is not None


def test_evaluate_registers_one_graduation_report_artefact_with_canonical_json(tmp_path):
    """One `graduation_report` artefact, canonical JSON, holding the window start, cutoff, and manifest hashes spanned."""
    conn = _conn(tmp_path)
    limits_path, manifest_hash = _passing_window(conn, tmp_path)
    conn.commit()

    artefact_id = graduation.evaluate(conn, limits_path=limits_path, manifest_hash=manifest_hash, cutoff=CUTOFF)
    conn.commit()

    artefact_row = record.get(conn, "artefact", artefact_id)
    assert artefact_row["kind"] == "graduation_report"
    raw = Path(artefact_row["path"]).read_text()
    doc = json.loads(raw)
    assert canonical.canonical_json(doc).decode() == raw
    assert doc["window"]["cutoff"] == CUTOFF
    assert doc["window"]["start"] is None
    assert doc["window"]["manifest_hashes"] == [manifest_hash]


def test_evaluate_report_holds_thresholds_and_configuration_hash(tmp_path):
    """The report carries the applied thresholds, their hash, and the evaluated configuration's hash."""
    conn = _conn(tmp_path)
    limits_path, manifest_hash = _passing_window(conn, tmp_path)
    conn.commit()

    artefact_id = graduation.evaluate(conn, limits_path=limits_path, manifest_hash=manifest_hash, cutoff=CUTOFF)
    conn.commit()
    doc = _report(conn, artefact_id)

    assert doc["thresholds"]["window_min_outcomes"] == 1
    assert doc["thresholds_hash"] == canonical.content_hash(doc["thresholds"])
    assert doc["config_hash"] == hashlib.sha256(limits_path.read_bytes()).hexdigest()


def test_evaluate_report_holds_every_clause_and_passes_only_when_all_do(tmp_path):
    """Every clause's inputs and verdict are on the report; `passed` is true only when all nine are."""
    conn = _conn(tmp_path)
    limits_path, manifest_hash = _passing_window(conn, tmp_path)
    conn.commit()

    artefact_id = graduation.evaluate(conn, limits_path=limits_path, manifest_hash=manifest_hash, cutoff=CUTOFF)
    conn.commit()
    doc = _report(conn, artefact_id)

    expected_clauses = {
        "window", "acceptance_gates", "exposure_coverage", "incidents", "stage_reliability",
        "baseline_revisions", "control_defects", "blind_spots", "self_containedness",
    }
    assert set(doc["clauses"]) == expected_clauses
    for clause in doc["clauses"].values():
        assert set(clause) == {"passed", "inputs", "reasons"}
    assert doc["passed"] == all(clause["passed"] for clause in doc["clauses"].values())
    assert doc["passed"] is True  # the seeded window clears every clause


def test_approve_writes_one_graduation_approval_record_binding_the_report(tmp_path):
    """`approve` writes one `approval_record` whose subject binds the report, thresholds and configuration hashes."""
    conn = _conn(tmp_path)
    limits_path, manifest_hash = _passing_window(conn, tmp_path)
    conn.commit()
    artefact_id = graduation.evaluate(conn, limits_path=limits_path, manifest_hash=manifest_hash, cutoff=CUTOFF)
    conn.commit()
    doc = _report(conn, artefact_id)
    artefact_row = record.get(conn, "artefact", artefact_id)

    approval_id = graduation.approve(
        conn, artefact_id, actor="abhishek", config_path=doc["config_path"], config_hash=doc["config_hash"],
        manifest_hash=manifest_hash,
    )
    conn.commit()

    approval = record.get(conn, "approval_record", approval_id)
    assert approval["gate"] == "graduation"
    assert approval["decision"] == "approve"
    expected_subject = canonical.content_hash({
        "report_content_hash": artefact_row["hash"], "thresholds_hash": doc["thresholds_hash"],
        "config_hash": doc["config_hash"],
    })
    assert approval["subject_hash"] == expected_subject


def test_approve_binds_the_factory_owner_slot_with_authority_and_identity_snapshot(tmp_path):
    """The approval's slot is the `factory_owner` role, carrying `authority_policy_hash` and a membership snapshot."""
    conn = _conn(tmp_path)
    limits_path, manifest_hash = _passing_window(conn, tmp_path)
    conn.commit()
    artefact_id = graduation.evaluate(conn, limits_path=limits_path, manifest_hash=manifest_hash, cutoff=CUTOFF)
    conn.commit()
    doc = _report(conn, artefact_id)

    approval_id = graduation.approve(
        conn, artefact_id, actor="abhishek", config_path=doc["config_path"], config_hash=doc["config_hash"],
        manifest_hash=manifest_hash,
    )
    conn.commit()

    approval = record.get(conn, "approval_record", approval_id)
    assert approval["role"] == "factory_owner"
    assert approval["slot_id"].startswith("factory_owner|")
    assert approval["authority_policy_hash"] == owners.authority_policy_hash()
    assert approval["membership_snapshot_hash"]


def test_must_reject_approve_over_a_report_that_did_not_pass(tmp_path):
    """A report with `passed = false` cannot be approved."""
    conn = _conn(tmp_path)
    limits_path = seed.write_limits(tmp_path, window_min_outcomes=99)  # no ticket clears this
    conn.commit()
    artefact_id = graduation.evaluate(conn, limits_path=limits_path, manifest_hash="mh1", cutoff=CUTOFF)
    conn.commit()
    doc = _report(conn, artefact_id)
    assert doc["passed"] is False

    with pytest.raises(graduation.GraduationRefused):
        graduation.approve(
            conn, artefact_id, actor="abhishek", config_path=doc["config_path"], config_hash=doc["config_hash"],
            manifest_hash="mh1",
        )


def test_must_reject_approve_with_a_configuration_hash_differing_from_the_report(tmp_path):
    """A given `config_hash` that differs from the report's own is refused."""
    conn = _conn(tmp_path)
    limits_path, manifest_hash = _passing_window(conn, tmp_path)
    conn.commit()
    artefact_id = graduation.evaluate(conn, limits_path=limits_path, manifest_hash=manifest_hash, cutoff=CUTOFF)
    conn.commit()
    doc = _report(conn, artefact_id)

    with pytest.raises(graduation.GraduationRefused):
        graduation.approve(
            conn, artefact_id, actor="abhishek", config_path=doc["config_path"], config_hash="not-the-real-hash",
            manifest_hash=manifest_hash,
        )


def test_must_reject_approve_from_an_actor_who_is_not_factory_owner(tmp_path):
    """An actor whose `owners.yaml` role is not `factory_owner` cannot approve."""
    conn = _conn(tmp_path)
    limits_path, manifest_hash = _passing_window(conn, tmp_path)
    conn.commit()
    artefact_id = graduation.evaluate(conn, limits_path=limits_path, manifest_hash=manifest_hash, cutoff=CUTOFF)
    conn.commit()
    doc = _report(conn, artefact_id)

    with pytest.raises(graduation.GraduationRefused):
        graduation.approve(
            conn, artefact_id, actor="not-the-factory-owner", config_path=doc["config_path"],
            config_hash=doc["config_hash"], manifest_hash=manifest_hash,
        )


def test_must_reject_approve_when_the_current_manifest_hash_differs_from_the_report(tmp_path):
    """A current manifest hash that differs from the report's own is refused."""
    conn = _conn(tmp_path)
    limits_path, manifest_hash = _passing_window(conn, tmp_path)
    conn.commit()
    artefact_id = graduation.evaluate(conn, limits_path=limits_path, manifest_hash=manifest_hash, cutoff=CUTOFF)
    conn.commit()
    doc = _report(conn, artefact_id)

    with pytest.raises(graduation.GraduationRefused):
        graduation.approve(
            conn, artefact_id, actor="abhishek", config_path=doc["config_path"], config_hash=doc["config_hash"],
            manifest_hash="a-different-manifest-hash",
        )


def test_reject_records_one_approval_record_with_decision_reject(tmp_path):
    """`reject` goes through the same writer as `approve`, with `decision = 'reject'`, over a report that need not pass."""
    conn = _conn(tmp_path)
    limits_path = seed.write_limits(tmp_path, window_min_outcomes=99)
    conn.commit()
    artefact_id = graduation.evaluate(conn, limits_path=limits_path, manifest_hash="mh1", cutoff=CUTOFF)
    conn.commit()
    doc = _report(conn, artefact_id)
    assert doc["passed"] is False

    approval_id = graduation.reject(
        conn, artefact_id, actor="abhishek", config_path=doc["config_path"], config_hash=doc["config_hash"],
        manifest_hash="mh1",
    )
    conn.commit()

    approval = record.get(conn, "approval_record", approval_id)
    assert approval["gate"] == "graduation"
    assert approval["decision"] == "reject"


def test_two_approvals_from_one_actor_count_once_toward_quorum(tmp_path):
    """A second `graduate approve` by the same actor on the same subject supersedes the first, not forks it."""
    conn = _conn(tmp_path)
    limits_path, manifest_hash = _passing_window(conn, tmp_path)
    conn.commit()
    artefact_id = graduation.evaluate(conn, limits_path=limits_path, manifest_hash=manifest_hash, cutoff=CUTOFF)
    conn.commit()
    doc = _report(conn, artefact_id)

    first_id = graduation.approve(
        conn, artefact_id, actor="abhishek", config_path=doc["config_path"], config_hash=doc["config_hash"],
        manifest_hash=manifest_hash,
    )
    conn.commit()
    second_id = graduation.approve(
        conn, artefact_id, actor="abhishek", config_path=doc["config_path"], config_hash=doc["config_hash"],
        manifest_hash=manifest_hash,
    )
    conn.commit()

    second = record.get(conn, "approval_record", second_id)
    assert second["supersedes"] == first_id
    assert graduation.quorum(conn, artefact_id) is True


def test_quorum_needs_one_approving_factory_owner_record(tmp_path):
    """With no recorded approval at all, the gate has no quorum."""
    conn = _conn(tmp_path)
    limits_path, manifest_hash = _passing_window(conn, tmp_path)
    conn.commit()
    artefact_id = graduation.evaluate(conn, limits_path=limits_path, manifest_hash=manifest_hash, cutoff=CUTOFF)
    conn.commit()

    assert graduation.quorum(conn, artefact_id) is False


def test_acceptance_gates_clause_requires_the_latest_gate_run_under_the_manifest_hash_to_pass(tmp_path):
    """The acceptance-gates clause reads the latest `kind = 'gate'` `utility_run` under the report's manifest hash."""
    conn = _conn(tmp_path)
    seed.seed_window_ticket(conn, closed_at="2026-01-10T00:00:00")
    seed.seed_gate_run(conn, outcome="fail")
    limits_path = seed.write_limits(tmp_path)
    conn.commit()

    artefact_id = graduation.evaluate(
        conn, limits_path=limits_path, manifest_hash=seed.DEFAULT_MANIFEST_HASH, cutoff=CUTOFF,
    )
    conn.commit()
    doc = _report(conn, artefact_id)

    assert doc["clauses"]["acceptance_gates"]["passed"] is False
    assert "no_passing_gate_run" in doc["clauses"]["acceptance_gates"]["reasons"]


def test_acceptance_gates_clause_requires_a_completed_window_ticket(tmp_path):
    """At least one window ticket must have `factory_completed_at` set with a recorded outcome."""
    conn = _conn(tmp_path)
    seed.seed_ticket(conn, closed_at="2026-01-10T00:00:00", close_reason="merged")  # no factory_completed_at
    seed.seed_gate_run(conn, outcome="pass")
    limits_path = seed.write_limits(tmp_path)
    conn.commit()

    artefact_id = graduation.evaluate(
        conn, limits_path=limits_path, manifest_hash=seed.DEFAULT_MANIFEST_HASH, cutoff=CUTOFF,
    )
    conn.commit()
    doc = _report(conn, artefact_id)

    assert doc["clauses"]["acceptance_gates"]["passed"] is False
    assert "no_completed_ticket_with_recorded_outcome" in doc["clauses"]["acceptance_gates"]["reasons"]


_COMMIT_ENV = {
    "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@example.invalid",
}


def _git(args, cwd):
    return subprocess.run(
        ["git", "-c", "commit.gpgsign=false", *args], cwd=cwd, env={**os.environ, **_COMMIT_ENV},
        capture_output=True, text=True, check=True,
    )


def test_gate_main_records_a_utility_run_of_kind_gate_with_outcome_and_manifest_hash(tmp_path):
    """Every `python3 -m runner.gate` run opens and finishes one `utility_run` of `kind = 'gate'`, in the record at `--db`."""
    from runner import gate

    repo = tmp_path / "repo"
    shutil.copytree(FACTORY_DIR, repo / "factory")
    subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools" / "refresh_manifest.py"), str(repo)],
        check=True, capture_output=True, text=True,
    )
    _git(["init", "-q"], cwd=repo)
    _git(["checkout", "-q", "-b", "main"], cwd=repo)
    _git(["add", "-A"], cwd=repo)
    _git(["commit", "-q", "-m", "init"], cwd=repo)
    tests_dir = tmp_path / "tests_gate_util"
    tests_dir.mkdir()
    (tests_dir / "test_probe_gate_util.py").write_text("def test_probe_gate_util():\n    assert True\n")
    db_path = tmp_path / "db" / "factory.sqlite"

    rc = gate.main(["--root", str(repo), "--tests", str(tests_dir), "--db", str(db_path)])

    assert rc == 0
    conn = connect(db_path)
    run = conn.execute("SELECT * FROM utility_run WHERE kind = 'gate'").fetchone()
    assert run is not None
    assert run["outcome"] == "pass"
    assert run["manifest_hash"] == manifest.current_hash(repo)
    conn.close()
