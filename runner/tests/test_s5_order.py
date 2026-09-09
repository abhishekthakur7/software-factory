"""S5, run for real, over a real base/head diff: the full ordered check list bound to one review
tuple (criterion 16), and criterion 9's public-compatibility exclusion route (R-S5-1, R-S5-4,
R-S5-5, R-S5-10, R-S0-8).

The fixture pair (a `Widget.java`/`WidgetUnitTest.java` repository, CODEOWNERS, and a plan whose
`Contracts` row evidence resolves against the unit test's own identity) is the same shape
`test_stub_walk.py` builds for its own local S3 plan copy, reproduced here directly since this
file drives S5 in isolation -- no S1 through S4 -- rather than through a whole ticket walk.
"""
import json
from datetime import datetime, timedelta, timezone
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from runner import approvals, artefact_registry, artefacts, git_trees, manifest, owners, plan_tuple, record, waivers
from runner.checks import exclusion
from runner.db import connect
from runner.fs import write_text
from runner.reviewer_sets import Slot
from runner.run_ledger import open_stage_run
from runner.stages import S5, run_stage

HAS_JAVAC = shutil.which("javac") is not None and shutil.which("java") is not None
skip_without_jdk = pytest.mark.skipif(not HAS_JAVAC, reason="javac/java not available")

_COMMIT_ENV = {
    "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@example.invalid",
}

_PLAN_TEXT = (Path(__file__).parent / "fixtures" / "stub_walk" / "s3_ok" / "out" / "plan.md").read_text()

_WIDGET_UNIT_TEST = (
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


def _git(args, cwd, env=None):
    full_env = {**os.environ, **env} if env else None
    return subprocess.run(
        ["git", "-c", "commit.gpgsign=false", *args], cwd=cwd, env=full_env,
        capture_output=True, text=True, check=True,
    )


def _source_repo(tmp_path: Path) -> Path:
    """A real repository carrying `Widget.compute` (no guard yet) and its own unit test,
    matching the S3 plan fixture's own Contracts row and Scope table."""
    repo = tmp_path / "source-repo"
    repo.mkdir()
    _git(["init", "-q"], cwd=repo)
    _git(["checkout", "-q", "-b", "main"], cwd=repo)
    (repo / "CODEOWNERS").write_text("* @abhishek\n")
    (repo / "pom.xml").write_text("<project><licenses><license/></licenses></project>\n")
    widget_src = repo / "src" / "main" / "java" / "com" / "fixture"
    widget_src.mkdir(parents=True)
    (widget_src / "Widget.java").write_text(
        "package com.fixture;\n\npublic class Widget {\n    public int compute(int n) {\n        return n * 2;\n    }\n}\n"
    )
    widget_test_src = repo / "src" / "test" / "java" / "com" / "fixture"
    widget_test_src.mkdir(parents=True)
    (widget_test_src / "WidgetUnitTest.java").write_text(_WIDGET_UNIT_TEST)
    _git(["add", "-A"], cwd=repo)
    _git(["commit", "-q", "-m", "init"], cwd=repo, env=_COMMIT_ENV)
    return repo


@pytest.fixture
def conn(tmp_path):
    connection = connect(tmp_path / "factory.sqlite")
    yield connection
    connection.close()


def _ready_ticket(conn, tmp_path):
    """A ticket in `checks` with a real base/head diff (a guard clause added to
    `Widget.compute`, no signature change), a real plan artefact and current plan tuple, and
    satisfied plan quorum -- everything S5's preflight needs, built directly rather than
    through S1 through S4 so this file drives S5 in isolation.
    """
    source = _source_repo(tmp_path)
    ticket_id = record.insert(
        conn, "ticket", state="checks", opened_at=record.now(), tier_final="light",
        trust_profile_hash="trust-1", trust_approval_set_hash="trust-approval-1",
    )
    trees = git_trees.clone_for_ticket(conn, ticket_id, source_checkout=source, target_branch="main", runs_dir=tmp_path)

    widget = trees.worktree / "src" / "main" / "java" / "com" / "fixture" / "Widget.java"
    widget.write_text(
        "package com.fixture;\n\nimport java.util.List;\n\npublic class Widget {\n"
        "    public int compute(int n) {\n        if (n < 0) {\n"
        "            throw new IllegalArgumentException(\"n must not be negative\");\n        }\n"
        "        return n * 2;\n    }\n}\n"
    )
    _git(["add", "-A"], cwd=trees.worktree)
    _git(["commit", "-q", "-m", "add a negative-input guard"], cwd=trees.worktree, env=_COMMIT_ENV)
    git_trees.record_head(conn, ticket_id, trees.worktree)
    record.update(conn, "ticket", ticket_id, factory_manifest_hash=manifest.current_hash())

    for kind in ("brief", "criteria"):
        path = tmp_path / f"{kind}.md"
        write_text(path, f"## {artefacts.SECTIONS[kind][0]}\n\nstub\n")
        artefact_registry.register(conn, ticket_id=ticket_id, kind=kind, path=path)
    plan_path = tmp_path / "plan.md"
    write_text(plan_path, _PLAN_TEXT)
    artefact_registry.register(conn, ticket_id=ticket_id, kind="plan", path=plan_path)

    identity = owners.load_owners().roles["s3_reviewer"]["identity"]
    slot = Slot(source_rule="s3_reviewer_role", role="s3_reviewer", owner=identity, min_count=1)
    record.insert(
        conn, "reviewer_set", ticket_id=ticket_id, kind="planned", content_hash="planned-1",
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
    return ticket_id


@skip_without_jdk
def test_s5_runs_the_full_ordered_controls_and_routes_unavailable_security_evidence_for_review(conn, tmp_path):
    """The configured metadata lets dependency and security controls run in both copies.
    Unavailable vulnerability and licence data stay visible as a waivable review gap."""
    ticket_id = _ready_ticket(conn, tmp_path)

    outcome = run_stage(conn, ticket_id, "S5", runs_dir=tmp_path)
    assert outcome == "fail"

    stage_run = conn.execute(
        "SELECT * FROM stage_run WHERE ticket_id = ? AND stage = 'S5' ORDER BY id DESC LIMIT 1", (ticket_id,)
    ).fetchone()
    rows = conn.execute(
        "SELECT check_name, result, evidence_tuple_id FROM check_result WHERE stage_run_id = ? ORDER BY id",
        (stage_run["id"],),
    ).fetchall()
    names = [row["check_name"] for row in rows]
    by_name = {row["check_name"]: row["result"] for row in rows}
    # The base-side and the governed-recipe head results (integration/end-to-end have no
    # matching test tree in this fixture at either side) are recorded for evidence but never
    # decide blocking by themselves -- `regression_only`'s own verdict is what must be clean.
    for name in ("base_test_diff", "dep_verify", "size_gate", "scope_diff", "source_declaration_diff", "behavior_contract_evidence", "regression_only", "approval_binding", "recipe:fixture_lint@head", "recipe:fixture_compile@head", "recipe:fixture_unit@head"):
        assert by_name[name] == "pass", (name, by_name)

    assert by_name["recipe:fixture_security@head"] == "blind_spot"
    ordered_controls = ["base_test_diff", "recipe:fixture_security@head", "recipe:fixture_dependencies@head", "dep_verify", "size_gate", "scope_diff", "source_declaration_diff", "behavior_contract_evidence", "approval_binding"]
    assert [names.index(name) for name in ordered_controls] == sorted(names.index(name) for name in ordered_controls), names
    for name in ordered_controls:
        assert names.count(name) == 1, names

    recipe_names = [name for name in names if name.startswith("recipe:")]
    assert recipe_names
    initial_names = [name for name in recipe_names if not name.startswith(("recipe:fixture_security", "recipe:fixture_dependencies"))]
    assert all(names.index(recipe_name) < names.index("base_test_diff") for recipe_name in initial_names)
    assert names.index("base_test_diff") < names.index("recipe:fixture_security@head") < names.index("dep_verify")

    review_tuple_ids = {row["evidence_tuple_id"] for row in rows}
    assert review_tuple_ids == {conn.execute(
        "SELECT id FROM evidence_tuple WHERE ticket_id = ? AND kind = 'review' ORDER BY id DESC LIMIT 1", (ticket_id,)
    ).fetchone()["id"]}

    run_dir = Path(tmp_path) / "tickets" / str(ticket_id) / "runs" / str(stage_run["id"])
    checkouts_dir = run_dir / "checkouts"
    assert (checkouts_dir / "base" / ".git").is_dir()
    assert (checkouts_dir / "head" / ".git").is_dir()
    # Build output lands only in run-local copies, which are gone once their
    # evidence has been captured; immutable views remain free of generated output.
    copies_root = Path(tmp_path) / "tickets" / str(ticket_id) / "copies" / str(stage_run["id"])
    assert not copies_root.exists()
    assert not (checkouts_dir / "base" / "out").exists()
    assert not (checkouts_dir / "head" / "out").exists()

    evidence = artefact_registry.latest(conn, ticket_id, "check_evidence")
    assert evidence is not None
    red_items = conn.execute("SELECT * FROM queue_item WHERE ticket_id = ? AND kind = 'red_check'", (ticket_id,)).fetchall()
    assert len(red_items) == 1 and red_items[0]["resolved_at"] is None
    assert not waivers.cleared(conn, stage_run["id"])
    security_result = conn.execute(
        "SELECT id FROM check_result WHERE stage_run_id = ? AND check_name = 'recipe:fixture_security@head'",
        (stage_run["id"],),
    ).fetchone()["id"]
    waivers.issue(
        conn, ticket_id=ticket_id, policy_id="recipe-execution-gap", check_result_id=security_result,
        actor="abhishek", reason="fixture feed unavailable", scope="this review tuple's unavailable security feeds",
        compensating_controls="local secret and static scans ran; fixture-only adoption",
        evidence_ids=[evidence["id"]], expires_at=(datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
    )
    assert waivers.cleared(conn, stage_run["id"])
    assert record.get(conn, "queue_item", red_items[0]["id"])["resolved_at"] is not None


# ---- criterion 9: a public-compatibility blind spot re-triggers pilot exclusion ----


def _bce_payload(item: str) -> dict:
    return {"result": "blind_spot", "blind_spots": [{"item": item, "reason": "binary compatibility"}]}


def test_a_public_compatibility_blind_spot_on_a_plan_declared_excluded_path_triggers_pilot_exclusion(conn, tmp_path):
    """Criterion 9: a `behavior_contract_evidence` blind spot naming a public declaration's
    binary compatibility, whose file is both an excluded surface and one the plan's own scope
    already declared, triggers the same pilot-exclusion route S1 and S3 take."""
    ticket_id = record.insert(conn, "ticket", state="checks", opened_at=record.now())
    stage_run_id = open_stage_run(conn, ticket_id=ticket_id, stage="S5")
    item_path = "src/main/java/com/fixture/auth/TokenChecker.java"

    triggered = S5._handle_compatibility_exclusion(
        conn, ticket_id, stage_run_id, bce_payload=_bce_payload(f"{item_path}:check"), plan_paths=[item_path],
    )

    assert triggered is True
    check_result = conn.execute(
        "SELECT * FROM check_result WHERE stage_run_id = ? AND check_name = 'exclusion'", (stage_run_id,)
    ).fetchone()
    assert check_result is not None
    assert check_result["result"] == "fail"
    ticket = record.get(conn, "ticket", ticket_id)
    assert ticket["state"] == "rejected"
    assert ticket["close_reason"] == "pilot_excluded"


def test_must_reject_a_public_compatibility_blind_spot_outside_the_plans_scope_from_auto_excluding(conn, tmp_path):
    """Criterion 9 (negative half): the identical blind spot on a path the plan never declared
    in its own scope is not an automatic exclusion -- `exclusion.decide_at_checks` would route
    it to `checks_removal_return` instead (an accidental touch, not a planned one), and this
    driver only ever auto-excludes on `checks_sensitive_path_required`. The blind spot rides
    into the ordinary `red_check` aggregation instead of guessing a route."""
    ticket_id = record.insert(conn, "ticket", state="checks", opened_at=record.now())
    stage_run_id = open_stage_run(conn, ticket_id=ticket_id, stage="S5")
    item_path = "src/main/java/com/fixture/auth/TokenChecker.java"

    triggered = S5._handle_compatibility_exclusion(
        conn, ticket_id, stage_run_id, bce_payload=_bce_payload(f"{item_path}:check"), plan_paths=[],
    )

    assert triggered is False
    assert conn.execute(
        "SELECT COUNT(*) FROM check_result WHERE stage_run_id = ? AND check_name = 'exclusion'", (stage_run_id,)
    ).fetchone()[0] == 0
    assert record.get(conn, "ticket", ticket_id)["state"] == "checks"


def test_must_reject_a_public_compatibility_blind_spot_on_no_excluded_surface_from_auto_excluding(conn, tmp_path):
    """Criterion 9 (negative half): a public-compatibility blind spot whose file matches no
    excluded surface at all (`exclusion.decide_at_checks` raises `ValueError`, there being no
    excluded path in the diff) never auto-excludes regardless of the plan's own scope."""
    ticket_id = record.insert(conn, "ticket", state="checks", opened_at=record.now())
    stage_run_id = open_stage_run(conn, ticket_id=ticket_id, stage="S5")
    item_path = "src/main/java/com/fixture/Widget.java"

    triggered = S5._handle_compatibility_exclusion(
        conn, ticket_id, stage_run_id, bce_payload=_bce_payload(f"{item_path}:compute"), plan_paths=[item_path],
    )

    assert triggered is False
    assert conn.execute(
        "SELECT COUNT(*) FROM check_result WHERE stage_run_id = ? AND check_name = 'exclusion'", (stage_run_id,)
    ).fetchone()[0] == 0
    assert record.get(conn, "ticket", ticket_id)["state"] == "checks"
