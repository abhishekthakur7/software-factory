"""Crash recovery: a killed run's lease and process identity both dead,
restart through `factory advance`, outbox-first reconciliation, and the
reasoning-summary cap `tiers.yaml` sets.

Every test opens its own `tmp_path` database, matching the rest of the
record/schema test suite. A "killed" run is seeded exactly as a ticket's
restart path expects to find one: an open `stage_run`/`utility_run` row
(no `outcome` yet) whose `process_identity` names a process that is gone.
`_open_dead_run` gets that identity onto the row by monkeypatching
`run_ledger.process_identity` for the one call that opens it, then
undoing the patch immediately so every later liveness check in the same
test runs the real function.
"""
import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml

from runner import (
    approvals, artefact_registry, artefacts, git_trees, governance, manifest, operations, outbox, owners, plan_tuple,
    record, run_ledger,
)
from runner.db import connect
from runner.paths import FACTORY_DIR
from runner.reviewer_sets import Slot
from runner.trust_profile import DEFAULT_TRUST_PROFILE_PATH

S1_FIXTURE_OUT = FACTORY_DIR / "evals" / "agents" / "S1" / "fixtures" / "plain_ok" / "out"

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "crash_recovery"
PER_STAGE = yaml.safe_load((FIXTURES_DIR / "per_stage.yaml").read_text())["stages"]
OUTBOX_FIRST = yaml.safe_load((FIXTURES_DIR / "outbox_first.yaml").read_text())

FAR_FUTURE = "2999-01-01T00:00:00+00:00"
# Well before any lease a test opens with a positive `lease_seconds`, and
# after none: a fixed past timestamp for a deliberately lapsed lease.
PAST = "2000-01-01T00:00:00+00:00"
# A pid this test process almost certainly is not and does not share a
# start time with, so the real `process_identity`/`process_alive` pair
# reports it as gone without ever touching another real process.
_DEAD_PID = os.getpid() + 999983


@pytest.fixture
def conn(tmp_path):
    connection = connect(tmp_path / "factory.sqlite")
    yield connection
    connection.close()


def _ticket_in(conn, state, **fields):
    return record.insert(conn, "ticket", state=state, opened_at=record.now(), **fields)


def _open_dead_run(monkeypatch, conn, *, table="stage_run", **kwargs):
    """Open a run whose `process_identity` names a pid that does not exist."""
    fake_identity = f"deadhost:{_DEAD_PID}:Thu Jan  1 00:00:00 1970"
    monkeypatch.setattr(run_ledger, "process_identity", lambda pid=None: fake_identity)
    try:
        if table == "stage_run":
            return run_ledger.open_stage_run(conn, **kwargs)
        return run_ledger.open_utility_run(conn, **kwargs)
    finally:
        monkeypatch.undo()


_COMMIT_ENV = {
    "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@example.invalid",
}


def _give_real_base(conn, runs_dir, ticket_id):
    """Clone a one-commit repository for the ticket and bind a plan tuple to its base.

    The S4 and S5 boundaries fetch the configured target branch from the
    ticket's own clone, so a ticket that reaches them needs a real
    fetchable base, a recorded head, and a plan tuple bound to that base.
    """
    source = runs_dir / f"source-repo-{ticket_id}"
    source.mkdir(parents=True)
    for args in (["init", "-q"], ["checkout", "-q", "-b", "main"]):
        subprocess.run(["git", *args], cwd=source, check=True, capture_output=True)
    (source / "README.md").write_text("seed\n")
    # S5's real reviewer-set derivation reads CODEOWNERS at the target
    # base; a repository with none raises rather than defaulting, since an
    # actual diff's derivation has no plan-scope fallback the way a
    # planned one does.
    (source / "CODEOWNERS").write_text("* @abhishek\n")
    # A minimal pom so the now-real S1's impact_scan has something to
    # read, and the one file its `plain_ok` fixture's Flags row names.
    (source / "pom.xml").write_text(
        "<project>\n  <groupId>com.example</groupId>\n  <artifactId>widget</artifactId>\n  <version>1.0.0</version>\n"
        "  <dependencies>\n    <dependency>\n      <groupId>com.fixturevendor</groupId>\n"
        "      <artifactId>strings</artifactId>\n      <version>1.0.0</version>\n    </dependency>\n  </dependencies>\n"
        "</project>\n"
    )
    src = source / "src" / "main" / "java" / "com" / "example"
    src.mkdir(parents=True)
    (src / "Handler.java").write_text("package com.example;\n\npublic class Handler {\n}\n")
    # A trivial always-passing unit test: `fixture_unit` is ungoverned by
    # regression-only, so with none at all it would fail on its own and
    # block every ticket that reaches S5 through this fixture.
    test_src = source / "src" / "test" / "java" / "com" / "example"
    test_src.mkdir(parents=True)
    (test_src / "HandlerUnitTest.java").write_text(
        "package com.example;\n\npublic class HandlerUnitTest {\n"
        "    public static void main(String[] args) {\n"
        "        System.out.println(\"ran: com.example.HandlerUnitTest#testHandlerConstructs\");\n"
        "        new Handler();\n"
        "    }\n"
        "}\n"
    )
    subprocess.run(["git", "add", "-A"], cwd=source, check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "commit", "-q", "-m", "init"],
        cwd=source, check=True, capture_output=True, env={**os.environ, **_COMMIT_ENV},
    )
    trees = git_trees.clone_for_ticket(conn, ticket_id, source_checkout=source, target_branch="main", runs_dir=runs_dir)
    git_trees.record_head(conn, ticket_id, trees.worktree)
    record.insert(
        conn, "evidence_tuple", kind="plan", ticket_id=ticket_id,
        base_sha=trees.base_sha, target_base_sha=trees.base_sha, content_hash=f"plan-subject-{ticket_id}",
    )


def _give_s5_ready_preflight(conn, tmp_path, ticket_id):
    """Extend `_give_real_base`'s ticket with a real, currently-current plan tuple and a
    satisfying `plan` approval, so a fresh S5 attempt clears the preflight far enough to
    run its checks and register `check_evidence` -- mirrors `test_freshness.py`'s
    `_real_plan_quorum`, needed now that S5 is a real driver rather than a stub.
    """
    record.update(conn, "ticket", ticket_id, factory_manifest_hash=manifest.current_hash())
    for kind in ("brief", "criteria", "plan"):
        path = tmp_path / f"{kind}-{ticket_id}.md"
        path.write_text(f"## {artefacts.SECTIONS[kind][0]}\n\nstub\n")
        artefact_registry.register(conn, ticket_id=ticket_id, kind=kind, path=path)

    identity = owners.load_owners().roles["s3_reviewer"]["identity"]
    slot = Slot(source_rule="s3_reviewer_role", role="s3_reviewer", owner=identity, min_count=1)
    record.insert(
        conn, "reviewer_set", ticket_id=ticket_id, kind="planned", content_hash=f"planned-{ticket_id}",
        slots=json.dumps([slot.to_json()]),
    )
    ticket = record.get(conn, "ticket", ticket_id)
    tuple_id = plan_tuple.ensure_current(conn, ticket)
    subject_hash = record.get(conn, "evidence_tuple", tuple_id)["content_hash"]
    approvals.record_approval(
        conn, gate="plan", subject_hash=subject_hash, slot_id=slot.slot_id, actor_identity=identity,
        role="s3_reviewer", decision="approve", authority_policy_hash="authority-1",
        membership_snapshot_hash="membership-1", attestation_version="v1", attestation_hash="att-1",
        ticket_id=ticket_id,
    )


def _activate_default_profile(conn):
    """Satisfy the default trust profile's quorum, the same way `factory advance` reads it."""
    proposal = governance.propose(DEFAULT_TRUST_PROFILE_PATH, owners.DEFAULT_OWNERS_PATH)
    for role in ("security_approver", "legal_data_governance_approver"):
        governance.decide(
            conn, proposal, actor_identity="abhishek", role=role, decision="approve",
            expires_at=FAR_FUTURE, attestation_version="v1", attestation_hash=f"att-{role}",
            owners_path=owners.DEFAULT_OWNERS_PATH, profile_path=DEFAULT_TRUST_PROFILE_PATH,
        )
    conn.commit()


def test_killed_stage_run_restarted_produces_no_duplicate_row_for_the_attempt(conn, tmp_path, monkeypatch):
    """R-O-1: a stage_run killed mid-execution restarts through `factory advance`
    as `infrastructure_failure`/`expired_lease`, with a fresh attempt + 1 and
    no second row for the killed attempt."""
    ticket_id = _ticket_in(
        conn, "context", service="fixture-project", ticket_type="small_feature", tier_provisional="standard",
        factory_manifest_hash=manifest.current_hash(),
    )
    _give_real_base(conn, tmp_path, ticket_id)
    dead_id = _open_dead_run(monkeypatch, conn, ticket_id=ticket_id, stage="S1", lease_seconds=-1)
    conn.commit()

    monkeypatch.setenv("FIXTURE_ADAPTER_OUT_DIR", str(S1_FIXTURE_OUT))
    operations.advance(conn, ticket_id, tmp_path)

    dead_row = record.get(conn, "stage_run", dead_id)
    assert dead_row["outcome"] == "infrastructure_failure"
    assert dead_row["failure_kind"] == "expired_lease"

    # `parent_run_id IS NULL`: S1's own agent invocation opens a second,
    # child `stage_run` under the same stage name once it passes, which
    # is not a second driver attempt.
    rows = conn.execute(
        "SELECT id, attempt FROM stage_run WHERE ticket_id = ? AND stage = 'S1' AND parent_run_id IS NULL ORDER BY attempt",
        (ticket_id,),
    ).fetchall()
    assert [row["attempt"] for row in rows] == [1, 2]
    fresh = rows[1]
    assert record.get(conn, "stage_run", fresh["id"])["attempt"] == dead_row["attempt"] + 1


def test_must_reject_expiring_a_lease_whose_process_is_still_alive(conn):
    """R-O-1: a lapsed lease whose process is still alive is left open, not expired."""
    ticket_id = _ticket_in(conn, "implementing")
    run_id = run_ledger.open_stage_run(conn, ticket_id=ticket_id, stage="S4", lease_seconds=-1)
    conn.commit()

    expired = run_ledger.expire_dead_runs(conn, ticket_id)

    assert expired == []
    row = record.get(conn, "stage_run", run_id)
    assert row["outcome"] is None
    assert row["failure_kind"] is None


def test_an_open_run_whose_lease_has_not_lapsed_is_left_alone(conn, monkeypatch):
    """R-O-1: a dead process whose lease has not yet lapsed is left open."""
    ticket_id = _ticket_in(conn, "implementing")
    dead_id = _open_dead_run(monkeypatch, conn, ticket_id=ticket_id, stage="S4", lease_seconds=3600)
    conn.commit()

    expired = run_ledger.expire_dead_runs(conn, ticket_id)

    assert expired == []
    assert record.get(conn, "stage_run", dead_id)["outcome"] is None


def test_expiring_a_dead_run_preserves_artefacts_and_worktree_path(conn, monkeypatch):
    """R-O-1: expiring a dead run touches only its own row -- registered artefacts
    and the ticket's worktree_path are untouched."""
    ticket_id = _ticket_in(conn, "implementing", worktree_path="runs/tickets/1/worktree")
    dead_id = _open_dead_run(monkeypatch, conn, ticket_id=ticket_id, stage="S4", lease_seconds=-1)
    artefact_id = record.insert(
        conn, "artefact", ticket_id=ticket_id, stage_run_id=dead_id, kind="handoff",
        path="runs/tickets/1/runs/1/out/handoff.md", created_at=record.now(),
    )
    conn.commit()

    run_ledger.expire_dead_runs(conn, ticket_id)

    artefact = record.get(conn, "artefact", artefact_id)
    assert artefact["path"] == "runs/tickets/1/runs/1/out/handoff.md"
    assert artefact["stage_run_id"] == dead_id
    assert record.get(conn, "ticket", ticket_id)["worktree_path"] == "runs/tickets/1/worktree"


def test_expiring_a_dead_utility_run_carries_no_failure_kind(conn, monkeypatch):
    """R-O-1: a dead utility_run also expires to infrastructure_failure; the table has no failure_kind column."""
    ticket_id = _ticket_in(conn, "context")
    dead_id = _open_dead_run(
        monkeypatch, conn, table="utility_run", kind="digest", ticket_id=ticket_id, lease_seconds=-1
    )
    conn.commit()

    expired = run_ledger.expire_dead_runs(conn, ticket_id)

    assert expired == [dead_id]
    row = record.get(conn, "utility_run", dead_id)
    assert row["outcome"] == "infrastructure_failure"
    assert "failure_kind" not in row.keys()


def test_outbox_reconciles_before_a_fresh_attempt_opens(conn, tmp_path, monkeypatch):
    """R-O-1: restart reconciles pending external_write rows before expiring a
    dead lease or opening the fresh attempt it leads to."""
    _activate_default_profile(conn)
    ticket_id = _ticket_in(
        conn, trust_profile_hash="trust-1", trust_approval_set_hash="trust-approval-1", **OUTBOX_FIRST["ticket"]
    )
    _give_real_base(conn, tmp_path, ticket_id)
    _give_s5_ready_preflight(conn, tmp_path, ticket_id)
    outbox.create_intent(
        conn, ticket_id=ticket_id, operation="digest",
        payload={"ticket_id": str(ticket_id), **OUTBOX_FIRST["digest_payload"]},
        runs_dir=tmp_path,
    )
    dead_id = _open_dead_run(monkeypatch, conn, ticket_id=ticket_id, stage="S5", lease_seconds=-1)
    conn.commit()

    operations.advance(conn, ticket_id, tmp_path)

    intent = conn.execute(
        "SELECT * FROM external_write WHERE ticket_id = ?", (ticket_id,)
    ).fetchone()
    assert intent["state"] == "reconciled"
    assert intent["receipt_artefact_id"] is not None

    assert record.get(conn, "stage_run", dead_id)["outcome"] == "infrastructure_failure"
    fresh = conn.execute(
        "SELECT id FROM stage_run WHERE ticket_id = ? AND stage = 'S5' AND attempt = 2", (ticket_id,)
    ).fetchone()
    assert fresh is not None
    # Both the receipt and the fresh attempt's own check_evidence artefact
    # land in the same `artefact` table, so their row ids are directly
    # comparable: the receipt's lower id proves reconciliation's artefact
    # was written before the fresh attempt's.
    fresh_artefact = artefact_registry.latest(conn, ticket_id, "check_evidence")
    assert fresh_artefact["stage_run_id"] == fresh["id"]
    assert intent["receipt_artefact_id"] < fresh_artefact["id"]


def test_must_reject_a_reasoning_summary_over_the_cap(conn):
    """R-O-1: a summary longer than tiers.yaml's max_words is stored truncated to exactly that many words."""
    ticket_id = _ticket_in(conn, "implementing")
    run_id = run_ledger.open_stage_run(conn, ticket_id=ticket_id, stage="S4")
    max_words = run_ledger._tiers_config()["reasoning_summary"]["max_words"]
    long_summary = " ".join(f"word{i}" for i in range(max_words + 50))

    stored = run_ledger.record_reasoning_summary(conn, run_id, long_summary)

    assert len(stored.split()) == max_words
    assert record.get(conn, "stage_run", run_id)["reasoning_summary"] == stored


def test_reasoning_summary_under_the_cap_is_stored_unchanged(conn):
    """a summary within the cap is stored verbatim, word for word."""
    ticket_id = _ticket_in(conn, "implementing")
    run_id = run_ledger.open_stage_run(conn, ticket_id=ticket_id, stage="S4")

    stored = run_ledger.record_reasoning_summary(conn, run_id, "short summary of the run")

    assert stored == "short summary of the run"
    assert record.get(conn, "stage_run", run_id)["reasoning_summary"] == "short summary of the run"


@pytest.mark.parametrize("stage", sorted(PER_STAGE))
def test_per_stage_kill_and_restart_leaves_no_duplicate_row(conn, tmp_path, monkeypatch, stage):
    """R-O-1: for every stage S0 to S6, killing its run and rerunning `factory
    advance` completes with no duplicate stage_run row for the killed attempt."""
    spec = PER_STAGE[stage]
    # S1 is a real, agent-invoking driver: it needs the fields S0 stamps
    # (service, type, provisional tier) and the manifest pin eligibility
    # writes, which the stub and script-only stages under test do not.
    extra_fields = (
        {
            "service": "fixture-project", "ticket_type": "small_feature", "tier_provisional": "standard",
            "factory_manifest_hash": manifest.current_hash(),
        }
        if stage == "S1" else {}
    )
    ticket_id = _ticket_in(conn, spec["state"], **extra_fields)
    for prior_stage in spec.get("prior_passes", []):
        prior_id = run_ledger.open_stage_run(conn, ticket_id=ticket_id, stage=prior_stage)
        run_ledger.finish(conn, prior_id, "pass")
    if spec.get("real_base"):
        _give_real_base(conn, tmp_path, ticket_id)
    conn.commit()

    dead_id = _open_dead_run(monkeypatch, conn, ticket_id=ticket_id, stage=stage, lease_seconds=-1)
    conn.commit()

    if stage == "S1":
        monkeypatch.setenv("FIXTURE_ADAPTER_OUT_DIR", str(S1_FIXTURE_OUT))
    operations.advance(conn, ticket_id, tmp_path)

    dead_row = record.get(conn, "stage_run", dead_id)
    assert dead_row["outcome"] == "infrastructure_failure"
    assert dead_row["failure_kind"] == "expired_lease"

    # `parent_run_id IS NULL`: S1's own agent invocation opens a second,
    # child `stage_run` under the same stage name once it passes, which
    # is not a second driver attempt.
    rows = conn.execute(
        "SELECT attempt FROM stage_run WHERE ticket_id = ? AND stage = ? AND parent_run_id IS NULL ORDER BY attempt",
        (ticket_id, stage),
    ).fetchall()
    assert [row["attempt"] for row in rows] == [1, 2]
