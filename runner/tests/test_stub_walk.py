"""The stub walk: one synthetic ticket from `intake` to `pr_opened` through
every stub stage `S0`-`S6`, `operations.advance`, and the human decisions its
gates need -- the milestone's exit test for the stage interface, proven
end to end before any stage becomes real.

`_run_walk` is the one driver every test in this file shares, through a
module-scoped fixture: it is expensive (git clones, subprocesses, a full
state-machine traversal), so it runs once and the short test functions
below assert one criterion each against what it produced, rather than
each replaying the whole walk. Every "kill" during the walk seeds a dead
`stage_run` the same way `test_crash_recovery.py`'s `_open_dead_run`
does -- a monkeypatched `process_identity` for exactly the one call that
opens it -- so every later liveness check in the walk runs the real
function; every "live" run (the stop demonstration) opens with no patch
at all, so its identity is this very test process.
"""
import ast
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from runner import (
    approvals, artefact_registry, checklist, envelope, git_trees, governance, guard, launcher, manifest, operations,
    owners, project, publication, queue, recipes, record, run_ledger, setup, stages, tickets, waivers,
)
from runner.adapters import cursor_sdk
from runner.db import connect
from runner.paths import FACTORY_DIR, REPO_ROOT
from runner.reviewer_sets import Slot
from runner.sandbox import os_policy
from runner.stages import S5
from runner.tests.support import launch_probe
from runner.trust_profile import DEFAULT_TRUST_PROFILE_PATH

ADAPTER_FIXTURES_DIR = Path(__file__).parent / "fixtures" / "adapter"

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "stub_walk"
TABLES = yaml.safe_load((FIXTURES_DIR / "tables.yaml").read_text())["tables"]
MANIFEST_HASH_SCRIPT = FACTORY_DIR / "scripts" / "tools" / "manifest_hash"

CAPABILITY_FIXTURES_DIR = Path(__file__).parent / "fixtures" / "capability_boundary"
ESCAPE_EVAL_DIR = REPO_ROOT / "factory" / "evals" / "sandbox" / "escape"

ABHISHEK = "abhishek"
FAR_FUTURE = "2999-01-01T00:00:00+00:00"
_DEAD_PID = os.getpid() + 999983
HAS_JAVAC = shutil.which("javac") is not None and shutil.which("java") is not None

_COMMIT_ENV = {
    "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@example.invalid",
}


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
    # S5's real reviewer-set derivation reads CODEOWNERS at the target
    # base; a repository with none raises rather than defaulting.
    (repo / "CODEOWNERS").write_text("* @abhishek\n")
    # A minimal pom so the now-real S1's impact_scan has something to read;
    # the dependency matches the committed artifact-to-service.yaml's one
    # authoritative entry.
    (repo / "pom.xml").write_text(
        "<project>\n  <groupId>com.example</groupId>\n  <artifactId>widget</artifactId>\n  <version>1.0.0</version>\n"
        "  <dependencies>\n    <dependency>\n      <groupId>com.fixturevendor</groupId>\n"
        "      <artifactId>strings</artifactId>\n      <version>1.0.0</version>\n    </dependency>\n  </dependencies>\n"
        "</project>\n"
    )
    src = repo / "src" / "main" / "java" / "com" / "example"
    src.mkdir(parents=True)
    (src / "Handler.java").write_text("package com.example;\n\npublic class Handler {\n}\n")
    # A trivial always-passing unit test: `fixture_unit` is ungoverned by
    # regression-only, so with none at all it would fail on its own and
    # block this walk's real S5 pass.
    handler_test_src = repo / "src" / "test" / "java" / "com" / "example"
    handler_test_src.mkdir(parents=True)
    (handler_test_src / "HandlerUnitTest.java").write_text(
        "package com.example;\n\npublic class HandlerUnitTest {\n"
        "    public static void main(String[] args) {\n"
        "        System.out.println(\"ran: com.example.HandlerUnitTest#testHandlerConstructs\");\n"
        "        new Handler();\n"
        "    }\n"
        "}\n"
    )
    # `Widget.java` (at base, no guard clause) and its own unit test are
    # the pair the S3 "ok" plan and the S4 hand-back fixture, both reused
    # from this walk, are written against: S4's fixture edits `Widget.java`
    # to add the guard clause, and this test's identity is the evidence
    # the plan's `Contracts` row and R-S3-20 checklist point to, so a real
    # S5 pass has resolvable evidence instead of a blind spot. The test
    # itself never changes between base and head, so it never enters the
    # diff `source_declaration_diff` walks -- only `Widget.java` does.
    widget_src = repo / "src" / "main" / "java" / "com" / "fixture"
    widget_src.mkdir(parents=True)
    (widget_src / "Widget.java").write_text(
        "package com.fixture;\n\npublic class Widget {\n    public int compute(int n) {\n        return n * 2;\n    }\n}\n"
    )
    widget_test_src = repo / "src" / "test" / "java" / "com" / "fixture"
    widget_test_src.mkdir(parents=True)
    (widget_test_src / "WidgetUnitTest.java").write_text(
        "package com.fixture;\n\npublic class WidgetUnitTest {\n"
        "    private static boolean failed = false;\n\n"
        "    public static void main(String[] args) {\n"
        "        run(\"testComputeRejectsNegative\", WidgetUnitTest::testComputeRejectsNegative);\n"
        "        if (failed) {\n            System.exit(1);\n        }\n"
        "    }\n\n"
        "    private static void run(String method, Runnable test) {\n"
        "        System.out.println(\"ran: com.fixture.WidgetUnitTest#\" + method);\n"
        "        try {\n            test.run();\n"
        "        } catch (Throwable t) {\n            failed = true;\n"
        "            System.out.println(\"FAILED: \" + method + \": \" + t);\n        }\n"
        "    }\n\n"
        "    private static void testComputeRejectsNegative() {\n"
        "        try {\n            new Widget().compute(-1);\n"
        "            throw new AssertionError(\"expected an IllegalArgumentException\");\n"
        "        } catch (IllegalArgumentException expected) {\n"
        "            // expected: negative input is invalid, once Widget.compute guards it\n"
        "        }\n"
        "    }\n"
        "}\n"
    )
    _git(["add", "-A"], cwd=repo)
    _git(["commit", "-q", "-m", "init"], cwd=repo, env=_COMMIT_ENV)
    return repo


def _materialise_fixture_vendor(tmp_path: Path) -> Path:
    """Build the committed fixture vendor beside a disposable setup project for S5's real dependency checks."""
    config_path = tmp_path / "fixture-project.yaml"
    config_path.write_text(yaml.safe_dump({"projects": [{
        "name": "fixture-project", "checkout": "fixture/checkout", "vendor": "fixture/vendor", "target_branch": "main",
    }]}))
    return setup.materialise(project_path=config_path, repo_root=tmp_path).vendor


def _activate_default_profile(conn) -> dict:
    """Satisfy the default trust profile's quorum, the same way `factory advance` reads it.

    Returns the ticket fields that bind a ticket to the activated profile
    and to the pilot's admitted source scope, so S0's governance check
    admits the walk's eligibility grant."""
    proposal = governance.propose(DEFAULT_TRUST_PROFILE_PATH, owners.DEFAULT_OWNERS_PATH)
    for role in ("security_approver", "legal_data_governance_approver"):
        governance.decide(
            conn, proposal, actor_identity=ABHISHEK, role=role, decision="approve",
            expires_at=FAR_FUTURE, attestation_version="v1", attestation_hash=f"att-{role}",
            owners_path=owners.DEFAULT_OWNERS_PATH, profile_path=DEFAULT_TRUST_PROFILE_PATH,
        )
    conn.commit()
    activated = governance.activation(conn, proposal)
    return {
        "trust_profile_hash": proposal.profile_hash,
        "trust_approval_set_hash": activated.trust_approval_set_hash,
        "source_kind": "jira",
        "source_ref": "FIX-1",
    }


def _seed_ticket_source(conn, ticket_id: int, tmp_path: Path) -> int:
    """A `ticket_source` artefact whose front matter already clears the intake field gate.

    Stands in for a real Jira read this walk never performs: no
    Atlassian server exists on this host, so S0's Jira intake leg would
    otherwise try to reach `sandbox.yaml`'s (still absent) endpoint and
    reject the ticket before ever reaching eligibility.
    """
    front_matter = {
        "jira_issue_type": "Story", "estimate": 2, "label": None, "owner": ABHISHEK,
        "parent_link": "FIX-0", "confluence_link": None,
        "acceptance_criteria": "Given a user opens the export dialog, when they click export, then a file downloads.",
    }
    text = "---\n" + yaml.safe_dump(front_matter, sort_keys=False) + "---\n\nSummary body.\n"
    path = tmp_path / "seeded_ticket_source.md"
    path.write_text(text)
    return artefact_registry.register(conn, ticket_id=ticket_id, kind="ticket_source", path=path)


def _manifest_hash() -> subprocess.CompletedProcess:
    return subprocess.run([str(MANIFEST_HASH_SCRIPT), "--root", str(REPO_ROOT)], capture_output=True, text=True)


def _open_dead_run(conn, **kwargs) -> int:
    """Open a run whose `process_identity` names a pid that does not exist -- a "killed" attempt."""
    fake_identity = f"deadhost:{_DEAD_PID}:Thu Jan  1 00:00:00 1970"
    with patch.object(run_ledger, "process_identity", lambda pid=None: fake_identity):
        return run_ledger.open_stage_run(conn, **kwargs)


def _kill_and_restart(conn, ticket_id, stage, tmp_path):
    """Seed a dead run for `stage`, then let one `factory advance` call expire it and pass a fresh attempt.

    Proves criterion 15 for `stage`: the killed attempt ends
    `infrastructure_failure`/`expired_lease`, and exactly one fresh attempt
    follows it with no duplicate row for the killed attempt.
    """
    dead_id = _open_dead_run(conn, ticket_id=ticket_id, stage=stage, lease_seconds=-1)
    operations.advance(conn, ticket_id, tmp_path)

    dead_row = record.get(conn, "stage_run", dead_id)
    assert dead_row["outcome"] == "infrastructure_failure"
    assert dead_row["failure_kind"] == "expired_lease"
    rows = conn.execute(
        "SELECT outcome FROM stage_run WHERE ticket_id = ? AND stage = ? AND parent_run_id IS NULL ORDER BY id",
        (ticket_id, stage)
    ).fetchall()
    assert rows[-1]["outcome"] == "pass"
    assert sum(1 for row in rows if row["outcome"] == "infrastructure_failure") == 1


def _kill_and_record_s5_security_blind_spot(conn, ticket_id, tmp_path) -> tuple[int, int]:
    """Restart S5 once and retain its sole waivable security gap for the review tuple waiver."""
    dead_id = _open_dead_run(conn, ticket_id=ticket_id, stage="S5", lease_seconds=-1)
    operations.advance(conn, ticket_id, tmp_path)

    dead_row = record.get(conn, "stage_run", dead_id)
    assert dead_row["outcome"] == "infrastructure_failure"
    assert dead_row["failure_kind"] == "expired_lease"
    stage_run = conn.execute(
        "SELECT id, outcome FROM stage_run WHERE ticket_id = ? AND stage = 'S5' AND parent_run_id IS NULL ORDER BY id DESC LIMIT 1",
        (ticket_id,),
    ).fetchone()
    assert stage_run["outcome"] == "fail"
    blocking = conn.execute(
        "SELECT id, check_name, result, evidence_artefact FROM check_result "
        "WHERE stage_run_id = ? AND check_tier = 'blocking' AND result != 'pass' ORDER BY id",
        (stage_run["id"],),
    ).fetchall()
    assert [(row["check_name"], row["result"]) for row in blocking] == [("recipe:fixture_security@head", "blind_spot")]
    assert blocking[0]["evidence_artefact"] is not None
    return stage_run["id"], blocking[0]["id"]


def _grant_plan_approval(conn, ticket_id, tmp_path) -> None:
    """Read the `plan_approval` item S3 opened, record a `pass` verdict for every expected
    checklist instance citing the plan artefact, then approve -- the real path to `implementing`
    now that the bootstrap checklist and the plan tuple are real rather than hand-seeded.

    `queue.act`'s own "approve" resolves and records exactly one slot -- the
    first ABHISHEK fills on the planned reviewer set -- so a plan whose
    scope also falls under this walk's own CODEOWNERS rule (needed for a
    real S5 pass) gets a second, distinct slot naming the same person that
    call never touches; this pre-approves every other slot ABHISHEK fills
    directly first, leaving only the first for `queue.act` itself, so two
    approval_record rows are never written for the identical slot (a fork
    that would refuse quorum outright).
    """
    item = conn.execute(
        "SELECT * FROM queue_item WHERE ticket_id = ? AND kind = 'plan_approval' AND resolved_at IS NULL "
        "ORDER BY id DESC LIMIT 1",
        (ticket_id,),
    ).fetchone()
    ticket = record.get(conn, "ticket", ticket_id)
    plan_artefact = artefact_registry.latest(conn, ticket_id, "plan")
    for instance in checklist.expected_instances(conn, ticket):
        queue.act(
            conn, item_id=item["id"], action="verdict", actor=ABHISHEK, line=instance.rubric_line_id,
            key=instance.subject_item_key, verdict="pass", evidence=[plan_artefact["id"]], runs_dir=tmp_path,
        )

    reviewer_set = record.get(conn, "reviewer_set", item["reviewer_set_id"])
    owners_obj = owners.load_owners()
    plan_subject_hash = conn.execute(
        "SELECT content_hash FROM evidence_tuple WHERE ticket_id = ? AND kind = 'plan' ORDER BY id DESC LIMIT 1",
        (ticket_id,),
    ).fetchone()["content_hash"]
    first_slot_seen = False
    for slot_json in json.loads(reviewer_set["slots"] or "[]"):
        slot = Slot.from_json(slot_json)
        fills = (slot.role is not None and owners_obj.roles.get(slot.role, {}).get("identity") == ABHISHEK) or slot.owner == ABHISHEK
        if not fills:
            continue
        if not first_slot_seen:
            first_slot_seen = True
            continue  # `queue.act`'s own "approve" call resolves this one
        approvals.record_approval(
            conn, gate="plan", subject_hash=plan_subject_hash, slot_id=slot.slot_id, actor_identity=ABHISHEK,
            role=slot.role or "owner", decision="approve", authority_policy_hash=owners.authority_policy_hash(),
            membership_snapshot_hash="membership-1", attestation_version="v1", attestation_hash=f"att-{slot.slot_id}",
            ticket_id=ticket_id,
        )

    queue.act(conn, item_id=item["id"], action="approve", actor=ABHISHEK, bucket="under_2m", self_contained="yes", runs_dir=tmp_path)


def _grant_packet_approval(conn, ticket_id, tmp_path):
    """Approve the real `packet_approval` item the real S6 driver opened -- pre-approving every
    other slot ABHISHEK also fills on the review tuple's effective reviewer set first, the same
    shape `_grant_plan_approval` uses for the plan gate: this walk's own CODEOWNERS rule and its
    planned/final-reviewer roles all resolve to the same person, so `queue.act`'s own "approve"
    call must be left exactly one slot to resolve. Reaching quorum this way is what itself
    authors the ticket's `pr_create` outbox intent."""
    item = conn.execute(
        "SELECT * FROM queue_item WHERE ticket_id = ? AND kind = 'packet_approval' AND resolved_at IS NULL "
        "ORDER BY id DESC LIMIT 1",
        (ticket_id,),
    ).fetchone()
    reviewer_set = record.get(conn, "reviewer_set", item["reviewer_set_id"])
    owners_obj = owners.load_owners()
    first_slot_seen = False
    for slot_json in json.loads(reviewer_set["slots"] or "[]"):
        slot = Slot.from_json(slot_json)
        fills = (slot.role is not None and owners_obj.roles.get(slot.role, {}).get("identity") == ABHISHEK) or slot.owner == ABHISHEK
        if not fills:
            continue
        if not first_slot_seen:
            first_slot_seen = True
            continue  # `queue.act`'s own "approve" call resolves this one
        # The item's own `approval_subject_hash` -- the real, fully
        # computed `publication.review_approval_subject` S6 opened it
        # with -- not the bare review-tuple content hash, which is no
        # longer what an `approval_record` for this gate binds.
        approvals.record_approval(
            conn, gate="review", subject_hash=item["approval_subject_hash"], slot_id=slot.slot_id, actor_identity=ABHISHEK,
            role=slot.role or "owner", decision="approve", authority_policy_hash=owners.authority_policy_hash(),
            membership_snapshot_hash="membership-1", attestation_version="v1", attestation_hash=f"att-{slot.slot_id}",
            ticket_id=ticket_id,
        )

    queue.act(
        conn, item_id=item["id"], action="approve", actor=ABHISHEK, bucket="under_2m", self_contained="yes",
        runs_dir=tmp_path,
    )
    conn.commit()  # `create_intent` never commits; the caller owns the transaction.


@dataclass(frozen=True)
class WalkResult:
    conn: object
    ticket_id: int
    tmp_path: Path
    wrong_state_stage_run_id: int
    stopped_stage_run_id: int
    s5_stage_run_id: int
    security_blind_spot_id: int
    security_waiver_id: int
    manifest_hash_before: subprocess.CompletedProcess
    manifest_hash_after: subprocess.CompletedProcess


def _run_walk(tmp_path) -> WalkResult:
    conn = connect(tmp_path / "factory.sqlite")
    manifest_hash_before = _manifest_hash()
    governed = _activate_default_profile(conn)

    # A pilot-eligible service and type, since the real S0 rejects anything else.
    ticket_id = record.insert(
        conn, "ticket", state="intake", opened_at=record.now(),
        service="fixture-project", ticket_type="small_feature", **governed,
    )
    # `governed`'s source_kind is "jira", so S0 now runs the Jira intake
    # leg; no real Atlassian server exists on this host (or in CI), so the
    # walk seeds a ticket_source artefact up front the same way a ticket
    # that already completed one earlier attempt would carry one, and S0
    # reuses it instead of reading.
    _seed_ticket_source(conn, ticket_id, tmp_path)

    # criterion 14: a stage invoked from a state the transition table does not permit is refused and recorded.
    wrong_state_outcome = operations.run(conn, ticket_id, "S4", runs_dir=tmp_path)
    assert wrong_state_outcome == "refused"
    wrong_state_row = conn.execute(
        "SELECT id FROM stage_run WHERE ticket_id = ? AND stage = 'S4' ORDER BY id LIMIT 1", (ticket_id,)
    ).fetchone()
    assert record.get(conn, "stage_run", wrong_state_row["id"])["outcome"] == "refused"

    # S0, kill and restart, then eligibility admits to `context`.
    _kill_and_restart(conn, ticket_id, "S0", tmp_path)
    eligibility_item = conn.execute(
        "SELECT id FROM queue_item WHERE ticket_id = ? AND kind = 'eligibility' AND resolved_at IS NULL",
        (ticket_id,),
    ).fetchone()
    queue.act(conn, item_id=eligibility_item["id"], action="granted", actor=ABHISHEK, runs_dir=tmp_path)
    operations.advance(conn, ticket_id, tmp_path)
    assert record.get(conn, "ticket", ticket_id)["state"] == "context"

    # A real, fetchable worktree: the now-real S1 needs one to run its
    # impact scan over, and S4's freshness preflight and the plan-review
    # gate's own freshness check both fetch the configured target branch
    # from this same clone later in the walk.
    source = _source_repo(tmp_path)
    trees = git_trees.clone_for_ticket(conn, ticket_id, source_checkout=source, target_branch="main", runs_dir=tmp_path)
    git_trees.record_head(conn, ticket_id, trees.worktree)

    # S1, S2, S3: each always due while its state holds, killed and restarted once.
    os.environ["FIXTURE_ADAPTER_OUT_DIR"] = str(
        FACTORY_DIR / "evals" / "agents" / "S1" / "fixtures" / "plain_ok" / "out"
    )
    try:
        _kill_and_restart(conn, ticket_id, "S1", tmp_path)
    finally:
        del os.environ["FIXTURE_ADAPTER_OUT_DIR"]
    assert record.get(conn, "ticket", ticket_id)["state"] == "clarifying"
    # S2's criteria half needs a real out/criteria.md; `criteria_clean`
    # carries one formalised criterion with agreeing restatements and no
    # open questions, so both the killed and the fresh attempt pass.
    os.environ["FIXTURE_ADAPTER_OUT_DIR"] = str(
        FACTORY_DIR / "evals" / "agents" / "S2" / "fixtures" / "criteria_clean" / "out"
    )
    try:
        _kill_and_restart(conn, ticket_id, "S2", tmp_path)
    finally:
        del os.environ["FIXTURE_ADAPTER_OUT_DIR"]
    assert record.get(conn, "ticket", ticket_id)["state"] == "planning"
    # The real S3 plans against a brief and a criteria artefact: the
    # fixture pair test_report's walk uses, and a local copy of the
    # committed "ok" plan whose `Contracts` row evidence points at this
    # walk's own `WidgetUnitTest` identity (the shared fixture's own
    # "Widget.java:42" text resolves nowhere real, which S5's now-real
    # `behavior_contract_evidence` would otherwise -- correctly -- call a
    # blind spot; see `test_s3_rubric.py`'s own exact-text assertions
    # against the shared fixture for why it is copied here rather than
    # edited in place).
    for kind in ("brief", "criteria"):
        prior = artefact_registry.latest(conn, ticket_id, kind)
        artefact_registry.register(
            conn, ticket_id=ticket_id, kind=kind, path=Path(__file__).parent / "fixtures" / "s3" / f"{kind}.md",
            supersedes=prior["id"] if prior is not None else None,
        )
    os.environ["FIXTURE_ADAPTER_OUT_DIR"] = str(FIXTURES_DIR / "s3_ok" / "out")
    try:
        _kill_and_restart(conn, ticket_id, "S3", tmp_path)
    finally:
        del os.environ["FIXTURE_ADAPTER_OUT_DIR"]
    assert record.get(conn, "ticket", ticket_id)["state"] == "plan_review"

    _grant_plan_approval(conn, ticket_id, tmp_path)
    operations.advance(conn, ticket_id, tmp_path)
    assert record.get(conn, "ticket", ticket_id)["state"] == "implementing"

    # criterion 16 (stop half): a live S4 run stopped ends `aborted_human`
    # and escalates; resuming the escalation returns the ticket to `implementing`.
    stopped_run_id = run_ledger.open_stage_run(conn, ticket_id=ticket_id, stage="S4")
    # `escalation` is tagged mechanically regardless of which human typed `factory stop`.
    operations.stop(conn, ticket_id, actor=ABHISHEK, fm_id="FM-07", note="paused for a manual look")
    assert record.get(conn, "stage_run", stopped_run_id)["outcome"] == "aborted_human"
    assert record.get(conn, "ticket", ticket_id)["state"] == "escalated"
    escalation_item = conn.execute(
        "SELECT id FROM queue_item WHERE ticket_id = ? AND kind = 'escalation' ORDER BY id DESC LIMIT 1", (ticket_id,)
    ).fetchone()
    queue.act(conn, item_id=escalation_item["id"], action="resume", actor=ABHISHEK, self_contained="yes", runs_dir=tmp_path)
    assert record.get(conn, "ticket", ticket_id)["state"] == "implementing"

    # The real S4 hands off, invokes the fixture worker, and records a real
    # hand-back: `ok`'s `out/handback.json` and `worktree/` stand in for
    # the agent's own deviation report and edits.
    os.environ["FIXTURE_ADAPTER_OUT_DIR"] = str(FACTORY_DIR / "evals" / "agents" / "S4" / "fixtures" / "ok" / "out")
    os.environ["FIXTURE_ADAPTER_WORKTREE_DIR"] = str(FACTORY_DIR / "evals" / "agents" / "S4" / "fixtures" / "ok" / "worktree")
    try:
        _kill_and_restart(conn, ticket_id, "S4", tmp_path)
    finally:
        del os.environ["FIXTURE_ADAPTER_OUT_DIR"]
        del os.environ["FIXTURE_ADAPTER_WORKTREE_DIR"]
    assert record.get(conn, "ticket", ticket_id)["state"] == "checks"

    # criterion 16 (pause half), 6, 8, 12: a pending pause takes effect at
    # the next boundary, before S5 ever starts, and repeating the same
    # boundary opens no duplicate `manual_pause` item.
    operations.pause(conn, ticket_id)
    paused_result = operations.advance(conn, ticket_id, tmp_path)
    assert paused_result == f"ticket {ticket_id}: paused at checks"
    operations.advance(conn, ticket_id, tmp_path)
    manual_pause_items = conn.execute(
        "SELECT id FROM queue_item WHERE ticket_id = ? AND kind = 'manual_pause'", (ticket_id,)
    ).fetchall()
    assert len(manual_pause_items) == 1
    assert conn.execute("SELECT COUNT(*) FROM stage_run WHERE ticket_id = ? AND stage = 'S5'", (ticket_id,)).fetchone()[0] == 0
    operations.resume(conn, ticket_id, actor=ABHISHEK)

    # S5 is a real driver now: it runs the pilot project's own Java
    # recipes over real base/head checkouts, so without a JDK it cannot
    # produce the clean pass this walk's later criteria (S6, checks_gate,
    # review, pr_opened) all build on. Skipping loudly here, before any of
    # those run, is the honest outcome -- silently limping past S5 on a
    # missing toolchain would make every criterion downstream of it an
    # unearned pass.
    if not HAS_JAVAC:
        pytest.skip("javac/java not available: the walk cannot run S5's real recipes past this point")

    vendor = _materialise_fixture_vendor(tmp_path)
    s5_project = {**project.pilot(), "vendor": str(vendor)}
    with patch.object(S5, "_project_config", return_value=s5_project):
        s5_stage_run_id, security_blind_spot_id = _kill_and_record_s5_security_blind_spot(conn, ticket_id, tmp_path)
    security_result = record.get(conn, "check_result", security_blind_spot_id)
    security_evidence = record.get(conn, "artefact", security_result["evidence_artefact"])
    assert security_evidence is not None and Path(security_evidence["path"]).is_file()
    expires_at = (datetime.fromisoformat(record.now()) + timedelta(days=1)).isoformat()
    red_check_item = conn.execute(
        "SELECT id FROM queue_item WHERE ticket_id = ? AND kind = 'red_check' AND resolved_at IS NULL ORDER BY id DESC LIMIT 1",
        (ticket_id,),
    ).fetchone()
    message = queue.act(
        conn, item_id=red_check_item["id"], action="waiver", actor=ABHISHEK, evidence=[security_evidence["id"]],
        fields={
            "policy_id": "recipe-execution-gap", "check_result_id": security_blind_spot_id,
            "reason": "security feeds are unavailable in the fixture environment",
            "scope": "fixture_security head recipe", "controls": "local secret and static checks remain recorded",
            "expires_at": expires_at,
        },
        runs_dir=tmp_path,
    )
    assert "waiver" in message and "issued" in message
    security_waiver_id = int(message.split("waiver ")[1].split()[0])
    assert waivers.validity(conn, security_waiver_id).valid
    conn.commit()
    assert record.get(conn, "ticket", ticket_id)["state"] == "checks"
    _kill_and_restart(conn, ticket_id, "S6", tmp_path)
    assert record.get(conn, "ticket", ticket_id)["state"] == "checks"

    operations.advance(conn, ticket_id, tmp_path)  # checks_gate: both S5 and S6 passed
    assert record.get(conn, "ticket", ticket_id)["state"] == "review"

    _grant_packet_approval(conn, ticket_id, tmp_path)
    operations.advance(conn, ticket_id, tmp_path)  # reconciles the pr_create intent, then review_quorum_reconciled

    manifest_hash_after = _manifest_hash()

    return WalkResult(
        conn=conn, ticket_id=ticket_id, tmp_path=tmp_path,
        wrong_state_stage_run_id=wrong_state_row["id"], stopped_stage_run_id=stopped_run_id,
        s5_stage_run_id=s5_stage_run_id, security_blind_spot_id=security_blind_spot_id,
        security_waiver_id=security_waiver_id,
        manifest_hash_before=manifest_hash_before, manifest_hash_after=manifest_hash_after,
    )


def _patch_fixture_runtime(tmp_path_factory) -> None:
    """Point the adapter at the fixture worker directly, module-attribute assignment rather than
    `conftest.py`'s `monkeypatch` -- `walk` is module-scoped and so sets up before that
    function-scoped autouse fixture ever runs, and the now-real S1 driver this walk exercises is
    the first stage in this file to actually reach `cursor_sdk.invoke`."""
    doc = yaml.safe_load((ADAPTER_FIXTURES_DIR / "runtime.yaml").read_text())
    doc["adapters"]["cursor_sdk"]["command"] = [sys.executable, str(ADAPTER_FIXTURES_DIR / "fixture_worker.py")]
    runtime_path = tmp_path_factory.mktemp("runtime") / "runtime.yaml"
    runtime_path.write_text(yaml.safe_dump(doc))
    cursor_sdk.RUNTIME_PATH = runtime_path
    launcher.SANDBOX_PATH = ADAPTER_FIXTURES_DIR / "sandbox.yaml"
    envelope.SANDBOX_PATH = ADAPTER_FIXTURES_DIR / "sandbox.yaml"


@pytest.fixture(scope="module")
def walk(tmp_path_factory):
    _patch_fixture_runtime(tmp_path_factory)
    result = _run_walk(tmp_path_factory.mktemp("stub_walk"))
    yield result
    result.conn.close()


def test_the_walk_reaches_pr_opened_and_every_touched_table_carries_rows(walk):
    """R-I-8, R-H-13, criterion 13: the synthetic ticket reaches `pr_opened`
    through every stub stage `S0`-`S6`, and every table the walk touches
    (named in the fixture) carries at least one row."""
    assert record.get(walk.conn, "ticket", walk.ticket_id)["state"] == "pr_opened"
    for table in TABLES:
        count = walk.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        assert count > 0, f"expected at least one {table} row"


def test_every_expected_checklist_instance_has_a_verdict_and_no_runner_check_failed_through_s3(walk):
    """R-S3-20: every semantic rubric line or half-line instance from S1 through S3 carries a
    recorded `human_verdict` row, no runner-side `check_result` failed across the S0 through S3
    attempts, and the ticket reached `implementing`."""
    ticket = record.get(walk.conn, "ticket", walk.ticket_id)
    expected = checklist.expected_instances(walk.conn, ticket)
    assert expected
    verdicted = {
        (row["rubric_line_id"], row["subject_item_key"])
        for row in walk.conn.execute(
            "SELECT DISTINCT rubric_line_id, subject_item_key FROM human_verdict WHERE ticket_id = ?",
            (walk.ticket_id,),
        ).fetchall()
    }
    missing = [instance for instance in expected if (instance.rubric_line_id, instance.subject_item_key) not in verdicted]
    assert not missing, f"no human_verdict recorded for {missing}"

    failed = walk.conn.execute(
        "SELECT check_result.check_name, stage_run.stage FROM check_result "
        "JOIN stage_run ON stage_run.id = check_result.stage_run_id "
        "WHERE stage_run.ticket_id = ? AND stage_run.stage IN ('S0', 'S1', 'S2', 'S3') "
        "AND check_result.source = 'runner' AND check_result.result = 'fail'",
        (walk.ticket_id,),
    ).fetchall()
    assert not failed, [(row["stage"], row["check_name"]) for row in failed]

    assert walk.conn.execute(
        "SELECT 1 FROM stage_run WHERE ticket_id = ? AND stage = 'S4' AND outcome = 'pass' LIMIT 1",
        (walk.ticket_id,),
    ).fetchone() is not None


def test_every_earlier_ticket_wrote_its_build_brief_and_plan_pair():
    """Under PRD decision 39 every ticket before this one hand-writes `docs/build/<id>/brief.md`
    and `plan.md` before building; whichever earlier ticket directories have already landed in
    this tree carry both files -- one present without the other is the defect this test exists to
    catch, and this ticket itself is the one that first reads every pair back."""
    build_dir = REPO_ROOT / "docs" / "build"
    earlier_ids = [f"T-A-{n:02d}" for n in range(1, 27)]
    present = [ticket_id for ticket_id in earlier_ids if (build_dir / ticket_id).is_dir()]
    assert present, "no earlier ticket's docs/build directory was found"
    for ticket_id in present:
        for filename in ("brief.md", "plan.md"):
            path = build_dir / ticket_id / filename
            assert path.is_file(), f"{path} is missing"


def test_a_wrong_state_stage_invocation_is_refused_and_recorded(walk):
    """criterion 14: `S4` invoked from `intake` -- a state the transition
    table does not permit for it -- is refused and its own `stage_run`
    records the refusal."""
    row = record.get(walk.conn, "stage_run", walk.wrong_state_stage_run_id)
    assert row["stage"] == "S4"
    assert row["outcome"] == "refused"


def test_a_kill_at_every_stage_leaves_no_duplicate_attempt(walk):
    """criterion 15: across the whole walk, every stage `S0`-`S6` was
    killed once and restarted with exactly one fresh, passing attempt --
    proven inline by `_kill_and_restart` during the walk itself; this test
    pins that every stage was actually exercised that way. Attempts only:
    a real stage's agent invocations are child rows under the attempt."""
    for stage in ("S0", "S1", "S2", "S3", "S4", "S5", "S6"):
        rows = walk.conn.execute(
            "SELECT outcome FROM stage_run WHERE ticket_id = ? AND stage = ? AND parent_run_id IS NULL",
            (walk.ticket_id, stage)
        ).fetchall()
        outcomes = [row["outcome"] for row in rows]
        assert outcomes.count("infrastructure_failure") == 1, stage
        assert outcomes.count("pass") == (0 if stage == "S5" else 1), stage
        assert outcomes.count("fail") == (1 if stage == "S5" else 0), stage


def test_s5_security_blind_spot_has_generated_evidence_and_a_valid_recipe_waiver(walk):
    """The real security recipe records its unavailable feeds as the single S5 gap, cleared only by its evidence-backed waiver."""
    result = record.get(walk.conn, "check_result", walk.security_blind_spot_id)
    evidence = record.get(walk.conn, "artefact", result["evidence_artefact"])
    waiver = record.get(walk.conn, "waiver", walk.security_waiver_id)

    assert result["stage_run_id"] == walk.s5_stage_run_id
    assert result["check_name"] == "recipe:fixture_security@head"
    assert result["result"] == "blind_spot"
    assert evidence is not None and Path(evidence["path"]).is_file()
    assert waiver["policy_id"] == "recipe-execution-gap"
    assert waiver["waived_check_result_id"] == result["id"]
    assert waivers.validity(walk.conn, waiver["id"]).valid


def test_the_stop_demonstration_ended_the_run_aborted_human(walk):
    """criterion 16 (stop half): the stage run stopped mid-walk carries
    `aborted_human`, distinct from every killed attempt's `infrastructure_failure`."""
    assert record.get(walk.conn, "stage_run", walk.stopped_stage_run_id)["outcome"] == "aborted_human"


def test_an_in_place_edit_on_an_append_only_row_is_refused(walk):
    """criterion 17: an attempted in-place edit of an append-only `stage_run`
    column raises `sqlite3.IntegrityError`, refused by the schema's own trigger."""
    import sqlite3

    row = walk.conn.execute(
        "SELECT id FROM stage_run WHERE ticket_id = ? AND stage = 'S0' LIMIT 1", (walk.ticket_id,)
    ).fetchone()
    with pytest.raises(sqlite3.IntegrityError):
        record.update(walk.conn, "stage_run", row["id"], stage="S1")


def test_must_reject_a_recipe_given_a_shell_string(walk):
    """criterion 18: a recipe catalogue entry whose literal argument carries
    shell command substitution is refused by `recipes.load_catalogue`
    before any recipe from it could ever be dispatched."""
    with pytest.raises(recipes.RecipeError):
        recipes.load_catalogue(FIXTURES_DIR / "shell_recipe.yaml")


def test_the_manifest_hash_validates_identically_before_and_after_the_walk(walk):
    """criterion 19: the manifest hash script validates the real repository
    both before and after the stub walk, and reports the identical hash --
    the walk, which only ever writes to a tmp database and tmp run tree,
    changes nothing under `factory/`."""
    assert walk.manifest_hash_before.returncode == 0, walk.manifest_hash_before.stderr
    assert walk.manifest_hash_after.returncode == 0, walk.manifest_hash_after.stderr
    assert walk.manifest_hash_before.stdout == walk.manifest_hash_after.stdout


def test_one_guard_decision_row_per_content_bearing_crossing(walk):
    """criterion 20: the walk's one `pr_create` dispatch performs exactly
    two content-bearing crossings through the guard -- the outbound
    payload and the inbound receipt -- and each writes exactly one
    `guard_decision` row, neither denied."""
    rows = walk.conn.execute("SELECT decision, operation FROM guard_decision ORDER BY id").fetchall()
    assert len(rows) == 2
    assert all(row["operation"] == "outbox" for row in rows)
    assert all(row["decision"] in ("allow", "redact") for row in rows)


def test_must_reject_a_crossing_that_bypasses_the_guard(tmp_path):
    """criterion 21: `guard.pass_through` refuses a hand-built `Decision`
    that was never actually persisted through `guard.decide`."""
    conn = connect(tmp_path / "factory.sqlite")
    fake = guard.Decision(id=999999, decision="allow", reason_codes=(), effective_class="internal", payload="x", capabilities={})
    with pytest.raises(guard.GuardRefused):
        guard.pass_through(conn, fake, "outbox")
    conn.close()


# Forbidden capabilities, tested over the manifest, the sandbox and the
# route ids a direct GitHub or Slack write would need: no stage sandbox
# can exec an arbitrary shell, open an arbitrary network client, write
# source outside S4, write outside S5's own disposable layers, or reach a
# GitHub/Slack write through anything but the outbox dispatcher and the
# digest intent. A hidden capability injected at any of six surfaces the
# stub walk touches fails at the boundary that owns that surface.

def _capability_boundary_entry(tmp_path: Path, base: Path, name: str, stage: str = "S1", tier: str = "light"):
    """A resolved manifest `Entry` from `base/factory`, committed into a fresh git repo first --
    `manifest.resolve` and `manifest.current_hash` both require committed bytes."""
    repo = tmp_path / f"{name}_repo"
    shutil.copytree(base / "factory", repo / "factory")
    _git(["init", "-q"], cwd=repo)
    _git(["add", "factory"], cwd=repo)
    _git(["commit", "-q", "-m", "init"], cwd=repo, env=_COMMIT_ENV)
    m = manifest.load(repo / "factory" / "manifest.yaml")
    return manifest.resolve(m, stage, tier)


def _capability_boundary_runtime_path(tmp_path: Path) -> Path:
    doc = yaml.safe_load((ADAPTER_FIXTURES_DIR / "runtime.yaml").read_text())
    doc["adapters"]["cursor_sdk"]["command"] = [sys.executable, str(ADAPTER_FIXTURES_DIR / "fixture_worker.py")]
    path = tmp_path / "runtime.yaml"
    path.write_text(yaml.safe_dump(doc))
    return path


def test_must_reject_an_arbitrary_shell_exec_from_inside_a_build_sandbox(tmp_path):
    """R-I-11: a process outside the build profile's recipe-executable allowlist never runs, from any
    build-role sandbox -- the same boundary an agent-issued `/bin/sh -c '...'` would meet."""
    payload = launch_probe(
        tmp_path, ESCAPE_EVAL_DIR / "fixtures" / "subprocesses" / "probe.py", role="build", stage="S5",
        copy_dir=tmp_path / "copy", build_dir=tmp_path / "build", scratch_dir=tmp_path / "scratch",
        cache_dir=tmp_path / "cache",
    )
    assert payload == {"attempted": True, "refused": True}


def test_must_reject_an_arbitrary_network_client_from_inside_an_agent_sandbox(tmp_path):
    """R-I-11: a raw socket to a host outside the stage's proxy allowlist never connects, from any
    agent-role sandbox."""
    payload = launch_probe(
        tmp_path, ESCAPE_EVAL_DIR / "fixtures" / "network" / "probe.py", role="agent", stage="S1",
        ticket_dir=tmp_path / "ticket",
    )
    assert payload == {"attempted": True, "refused": True}


def test_must_reject_a_source_tree_write_at_every_agent_stage_but_s4(tmp_path):
    """R-I-11: source-tree write succeeds only at S4's worktree mount; a probe at any other agent
    stage attempting one is refused."""
    for stage in ("S1", "S2", "S3", "S5", "S6"):
        stage_tmp = tmp_path / stage
        worktree = stage_tmp / "worktree"
        worktree.mkdir(parents=True)
        payload = launch_probe(
            stage_tmp, CAPABILITY_FIXTURES_DIR / "source_write" / "probe.py", role="agent", stage=stage,
            ticket_dir=stage_tmp / "ticket", worktree_path=worktree, extra_argv=(str(worktree),),
        )
        assert payload == {"attempted": True, "refused": True}, stage
        assert not (worktree / "escape_write.txt").exists()


def test_a_source_tree_write_succeeds_only_at_s4(tmp_path):
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    payload = launch_probe(
        tmp_path, CAPABILITY_FIXTURES_DIR / "source_write" / "probe.py", role="agent", stage="S4",
        ticket_dir=tmp_path / "ticket", worktree_path=worktree, extra_argv=(str(worktree),),
    )
    assert payload == {"attempted": True, "refused": False}
    assert (worktree / "escape_write.txt").exists()


def test_s5_writing_outside_its_disposable_layers_is_refused(tmp_path):
    """R-I-11: a build-role probe at S5 writing outside COPY_DIR/BUILD_DIR/SCRATCH_DIR/CACHE_DIR --
    here, a path shaped like the immutable checkout the copy was cloned from -- is refused."""
    immutable_checkout = tmp_path / "immutable_checkout"
    immutable_checkout.mkdir()
    payload = launch_probe(
        tmp_path, CAPABILITY_FIXTURES_DIR / "source_write" / "probe.py", role="build", stage="S5",
        copy_dir=tmp_path / "copy", build_dir=tmp_path / "build", scratch_dir=tmp_path / "scratch",
        cache_dir=tmp_path / "cache", extra_argv=(str(immutable_checkout),),
    )
    assert payload == {"attempted": True, "refused": True}
    assert not (immutable_checkout / "escape_write.txt").exists()


def test_s1_grants_no_write_capability_outside_its_declared_out_directory(tmp_path):
    """R-I-11: a probe at S1 writing anywhere but `RUN_DIR/out` -- here, the read-only ticket
    directory -- is refused."""
    ticket_dir = tmp_path / "ticket"
    ticket_dir.mkdir()
    payload = launch_probe(
        tmp_path, CAPABILITY_FIXTURES_DIR / "source_write" / "probe.py", role="agent", stage="S1",
        ticket_dir=ticket_dir, extra_argv=(str(ticket_dir),),
    )
    assert payload == {"attempted": True, "refused": True}


# `credentials.py` names `slack_digest` too, but only as a credential ROLE
# in `credentials.ROLES` -- a name in a different namespace that happens
# to share the same text, never a route construction; excluded here for
# that reason, not because it is exempt from the boundary this test proves.
_FORBIDDEN_ROUTE_ID_LITERALS = ("github_pilot", "github_scratch", "slack_digest")
_ROUTE_CONSTRUCTION_HOMES = frozenset({"outbox.py", "trust_profile.py", "credentials.py"})


def test_github_and_slack_route_ids_are_named_only_by_the_outbox_dispatcher():
    """R-I-11: no module but the outbox dispatcher (and the trust-profile schema that defines the
    route ids in the first place) ever names a GitHub or Slack route id, so a direct GitHub merge,
    default-branch push, PR approval, Actions rerun, or Slack post has no route left to address."""
    offenders = []
    for path in sorted((REPO_ROOT / "runner").rglob("*.py")):
        relative_parts = path.relative_to(REPO_ROOT / "runner").parts
        if path.name in _ROUTE_CONSTRUCTION_HOMES or "tests" in relative_parts:
            continue
        source = path.read_text()
        for literal in _FORBIDDEN_ROUTE_ID_LITERALS:
            if literal in source:
                offenders.append(f"{path.relative_to(REPO_ROOT)}: {literal!r}")
    assert offenders == []


def test_hidden_capability_in_the_manifest_fails_the_walk(tmp_path):
    """R-I-11: a manifest entry carrying an extra, undeclared tool-allowlist item changes the
    manifest's own hash; a ticket pinned to the hash resolved before that change is refused
    outright, before any `stage_run` is ever opened."""
    repo = tmp_path / "repo"
    shutil.copytree(CAPABILITY_FIXTURES_DIR / "hidden" / "manifest" / "factory", repo / "factory")
    _git(["init", "-q"], cwd=repo)
    _git(["add", "factory"], cwd=repo)
    _git(["commit", "-q", "-m", "init"], cwd=repo, env=_COMMIT_ENV)

    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = tickets.open_ticket(conn, factory_manifest_hash="pinned-before-the-hidden-tool-was-added")
    ticket = record.get(conn, "ticket", ticket_id)

    result = stages.invoke_agent(
        conn, ticket, "S1", tier="light", manifest_path=repo / "factory" / "manifest.yaml", runs_dir=tmp_path,
    )

    assert result.outcome == "refused_request"
    assert conn.execute("SELECT COUNT(*) FROM stage_run").fetchone()[0] == 0


def test_hidden_capability_in_the_inherited_runtime_configuration_fails_the_walk(tmp_path):
    """R-I-11: a runtime.yaml adapter command carrying one extra, unreviewed argument shifts every
    positional argument the worker expects; the worker crashes reading what it takes to be its own
    envelope, and the invocation is recorded `infrastructure_failure` with nothing registered."""
    entry = _capability_boundary_entry(tmp_path, CAPABILITY_FIXTURES_DIR / "entry", "entry")
    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = tickets.open_ticket(conn)
    ticket = record.get(conn, "ticket", ticket_id)

    doc = yaml.safe_load((CAPABILITY_FIXTURES_DIR / "hidden" / "runtime" / "runtime.yaml").read_text())
    doc["adapters"]["cursor_sdk"]["command"] = [
        sys.executable, str(ADAPTER_FIXTURES_DIR / "fixture_worker.py"), "--unexpected-argument",
    ]
    runtime_path = tmp_path / "runtime.yaml"
    runtime_path.write_text(yaml.safe_dump(doc))

    result = cursor_sdk.invoke(
        conn, ticket=ticket, stage="S1", tier="light", entry=entry, runs_dir=tmp_path / "runs",
        runtime_path=runtime_path, sandbox_path=ADAPTER_FIXTURES_DIR / "sandbox.yaml",
    )

    assert result.outcome == "infrastructure_failure"
    assert conn.execute(
        "SELECT COUNT(*) FROM artefact WHERE stage_run_id = ?", (result.stage_run_id,)
    ).fetchone()[0] == 0


def test_hidden_capability_in_the_recipe_catalogue_fails_the_walk(tmp_path):
    """R-I-11: a catalogue entry whose declared `executable_digest` no longer matches the file on
    disk -- as if the executable had been swapped after the catalogue was authored -- is refused by
    `recipes.run`'s own digest check, before the executable is ever invoked."""
    catalogue = recipes.load_catalogue(CAPABILITY_FIXTURES_DIR / "hidden" / "recipe" / "command-recipes.yaml")
    with pytest.raises(recipes.RecipeError, match="executable digest mismatch"):
        recipes.run(
            "hidden_capability_probe", {}, catalogue=catalogue, cwd_roles={"checkout": tmp_path},
            results_dir=tmp_path / "results", env_source={"PATH": os.environ.get("PATH", "")},
        )


def test_hidden_capability_as_an_extra_mount_pointing_at_home_fails_the_walk():
    """R-I-11: a sandbox param naming a mount (here, `TICKET_DIR`) that resolves to the host's own
    home directory is refused by `os_policy.wrap` before `sandbox-exec` ever sees it."""
    params = {
        "REPO_ROOT": str(REPO_ROOT), "PYTHON_ROOT": sys.base_prefix, "WORKTREE": "/tmp/nonexistent",
        "RUN_DIR": "/tmp/nonexistent", "TICKET_DIR": os.path.expanduser("~"), "TMPDIR": "/tmp/nonexistent",
        "STAGE": "S1", "PROXY_PORT": "0",
    }
    with pytest.raises(os_policy.MountParamError):
        os_policy.wrap(["/usr/bin/true"], role="agent", params=params)


def test_hidden_capability_as_an_unallowlisted_environment_name_fails_the_walk(tmp_path):
    """R-I-11: an environment name the launching process set but the sandbox policy never
    allowlisted never crosses into the child."""
    env_source = {"PATH": os.environ.get("PATH", ""), "HIDDEN_CAPABILITY_ENV_CANARY": "leak-if-present"}
    payload = launch_probe(
        tmp_path, CAPABILITY_FIXTURES_DIR / "hidden" / "environment" / "probe.py", role="agent", stage="S1",
        ticket_dir=tmp_path / "ticket", env_source=env_source,
    )
    assert payload == {"attempted": True, "refused": True}


def test_hidden_capability_as_a_credential_role_the_manifest_does_not_admit_fails_the_walk(tmp_path):
    """R-I-11: a resolved entry whose stage the manifest's own `sandbox_policy` admits no credential
    role for never reaches `credentials.fetch`, even though the stage is agent-bearing."""
    entry = _capability_boundary_entry(tmp_path, CAPABILITY_FIXTURES_DIR / "hidden" / "credential", "credential")
    assert entry.credential_roles == ()
    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = tickets.open_ticket(conn)
    ticket = record.get(conn, "ticket", ticket_id)

    def _must_not_be_called(*args, **kwargs):
        raise AssertionError("credentials.fetch must never be called for a stage the manifest admits no role for")

    result = cursor_sdk.invoke(
        conn, ticket=ticket, stage="S1", tier="light", entry=entry, runs_dir=tmp_path / "runs",
        runtime_path=_capability_boundary_runtime_path(tmp_path), sandbox_path=ADAPTER_FIXTURES_DIR / "sandbox.yaml",
        credential_run=_must_not_be_called,
    )

    assert result.outcome == "pass"
