"""S4's escalation causes (R-S4-6): verification exhaustion, a repeat infrastructure failure, a
control defect, and the routed resumption each cause permits.
"""
import os
import subprocess
from pathlib import Path

import pytest

from runner import artefact_registry, git_trees, manifest, queue, record
from runner.db import connect
from runner.tests import support
from runner.paths import FACTORY_DIR
from runner.queue import ActionRefused
from runner.stages import run_stage

EVAL_DIR = FACTORY_DIR / "evals" / "agents" / "S4"
FIXTURES = Path(__file__).parent / "fixtures" / "s4_escalation"
PLAN_TEXT = (FIXTURES / "plan.md").read_text()
CRITERIA_TEXT = (Path(__file__).parent / "fixtures" / "s3" / "criteria.md").read_text()

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


_WIDGET_OK = (
    "package com.fixture;\n\npublic class Widget {\n    public int compute(int x) {\n        return x * 2;\n    }\n}\n"
)
_WIDGET_BROKEN = "package com.fixture;\n\npublic class Widget {\n    this is not valid java;\n}\n"


def _source_repo(tmp_path: Path, *, widget_source: str = _WIDGET_OK) -> Path:
    repo = tmp_path / "source-repo"
    repo.mkdir()
    _git(["init", "-q"], cwd=repo)
    _git(["checkout", "-q", "-b", "main"], cwd=repo)
    src = repo / "src" / "main" / "java" / "com" / "fixture"
    src.mkdir(parents=True)
    (src / "Widget.java").write_text(widget_source)
    (repo / "README.md").write_text("seed\n")
    _git(["add", "-A"], cwd=repo)
    _git(["commit", "-q", "-m", "init"], cwd=repo, env=_COMMIT_ENV)
    return repo


def _ready_ticket(conn, tmp_path, *, widget_source: str = _WIDGET_OK, plan_text: str = PLAN_TEXT, **ticket_fields) -> int:
    ticket_id = record.insert(
        conn, "ticket", trust_profile_hash=support.TRUST_PROFILE_HASH, trust_approval_set_hash=support.TRUST_APPROVAL_SET_HASH, state="implementing", opened_at=record.now(),
        service="fixture-project", ticket_type="small_feature", tier_provisional="standard",
        factory_manifest_hash=manifest.current_hash(), **ticket_fields,
    )
    source = _source_repo(tmp_path, widget_source=widget_source)
    trees = git_trees.clone_for_ticket(conn, ticket_id, source_checkout=source, target_branch="main", runs_dir=tmp_path)
    git_trees.record_head(conn, ticket_id, trees.worktree)
    plan_path = tmp_path / f"plan-{ticket_id}.md"
    plan_path.write_text(plan_text)
    artefact_registry.register(conn, ticket_id=ticket_id, kind="plan", path=plan_path)
    criteria_path = tmp_path / f"criteria-{ticket_id}.md"
    criteria_path.write_text(CRITERIA_TEXT)
    artefact_registry.register(conn, ticket_id=ticket_id, kind="criteria", path=criteria_path)
    support.approve_current_plan(conn, ticket_id, tmp_path)
    return ticket_id


def _run_s4(conn, ticket_id, tmp_path, *, out="empty_deviations") -> str:
    os.environ["FIXTURE_ADAPTER_OUT_DIR"] = str(EVAL_DIR / "fixtures" / out / "out")
    try:
        return run_stage(conn, ticket_id, "S4", runs_dir=tmp_path)
    finally:
        os.environ.pop("FIXTURE_ADAPTER_OUT_DIR", None)


def _last_s4_run(conn, ticket_id):
    return conn.execute(
        "SELECT * FROM stage_run WHERE ticket_id = ? AND stage = 'S4' AND parent_run_id IS NULL ORDER BY id DESC LIMIT 1",
        (ticket_id,),
    ).fetchone()


def _open_escalation_item(conn, ticket_id):
    return conn.execute(
        "SELECT * FROM queue_item WHERE ticket_id = ? AND kind = 'escalation' AND resolved_at IS NULL "
        "ORDER BY id DESC LIMIT 1",
        (ticket_id,),
    ).fetchone()


def test_the_third_verification_failure_escalates_in_the_same_write_as_the_fail_outcome(tmp_path):
    """The third red validation for one plan-item version leaves the run `fail` and
    moves the ticket to `escalated` -- both visible immediately, from the one call that made them."""
    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = _ready_ticket(conn, tmp_path, widget_source=_WIDGET_BROKEN)

    for _ in range(2):
        outcome = _run_s4(conn, ticket_id, tmp_path)
        assert outcome == "fail"
        assert record.get(conn, "ticket", ticket_id)["state"] == "implementing"

    outcome = _run_s4(conn, ticket_id, tmp_path)

    assert outcome == "fail"
    run = _last_s4_run(conn, ticket_id)
    assert run["outcome"] == "fail"
    assert run["failure_kind"] == "verification"
    assert run["verification_attempt"] == 3
    ticket = record.get(conn, "ticket", ticket_id)
    assert ticket["state"] == "escalated"
    tag = conn.execute(
        "SELECT * FROM tag WHERE ticket_id = ? AND event_kind = 'escalation' ORDER BY id DESC LIMIT 1", (ticket_id,)
    ).fetchone()
    assert tag["fm_id"] == "FM-19"


def test_verification_exhaustion_registers_a_failure_history_artefact_on_the_escalating_run(tmp_path):
    """The escalation carries complete per-attempt failure history -- here, the
    JSON artefact the third verification failure itself registers."""
    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = _ready_ticket(conn, tmp_path, widget_source=_WIDGET_BROKEN)
    for _ in range(3):
        _run_s4(conn, ticket_id, tmp_path)

    run = _last_s4_run(conn, ticket_id)
    history = artefact_registry.latest(conn, ticket_id, "failure_history")
    assert history is not None
    assert history["stage_run_id"] == run["id"]
    import json
    payload = json.loads(Path(history["path"]).read_text())
    assert payload["plan_item"] == "T-1"
    assert len(payload["executions"]) == 3
    assert payload["quota"] == {"consumed": 3, "remaining": 0, "cap": 3}

    item = _open_escalation_item(conn, ticket_id)
    context = queue.escalation_context(conn, item)
    assert context["failure_history_artefact_id"] == history["id"]


@pytest.mark.parametrize("case", ["path_violation", "environment_violation"])
def test_a_sandbox_integrity_violation_is_a_control_defect_that_escalates_immediately(tmp_path, case):
    """A sandbox-integrity failure (an unwritable path, or an undeclared
    environment name) tags `control_defect` (`FM-23`), opens a `control_defect_event` of
    `control_category = 'execution_boundary'`, and escalates without consuming a verification
    attempt -- for either fixture case, since both violate the same sandbox boundary."""
    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = _ready_ticket(conn, tmp_path)

    os.environ["FIXTURE_ADAPTER_CASE"] = case
    try:
        outcome = _run_s4(conn, ticket_id, tmp_path)
    finally:
        os.environ.pop("FIXTURE_ADAPTER_CASE", None)

    assert outcome == "sandbox_violation"
    run = _last_s4_run(conn, ticket_id)
    assert run["outcome"] == "sandbox_violation"
    assert run["failure_kind"] == "sandbox_integrity"
    ticket = record.get(conn, "ticket", ticket_id)
    assert ticket["state"] == "escalated"
    tag = conn.execute(
        "SELECT * FROM tag WHERE ticket_id = ? AND event_kind = 'control_defect' ORDER BY id DESC LIMIT 1", (ticket_id,)
    ).fetchone()
    assert tag["fm_id"] == "FM-23"
    incident = conn.execute(
        "SELECT * FROM incident_observation WHERE ticket_id = ? AND record_kind = 'control_defect_event'", (ticket_id,)
    ).fetchone()
    assert incident["control_category"] == "execution_boundary"


def test_a_verification_exhaustion_escalation_refuses_plain_resume(tmp_path):
    """Verification exhaustion resumes only through a new plan-item version and a
    fresh S3 approval -- `resume` itself is refused outright."""
    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = _ready_ticket(conn, tmp_path, widget_source=_WIDGET_BROKEN)
    for _ in range(3):
        _run_s4(conn, ticket_id, tmp_path)
    item = _open_escalation_item(conn, ticket_id)

    with pytest.raises(ActionRefused):
        queue.act(conn, item_id=item["id"], action="resume", actor="abhishek", runs_dir=tmp_path)


def test_a_control_defect_escalation_refuses_resume_until_remediated_and_gated(tmp_path):
    """A control-defect escalation refuses plain `resume` until its event carries a
    `remediated` disposition and a newer passing `gate` run -- then, and only then, it resumes
    through `escalation_control_defect_remediated`."""
    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = _ready_ticket(conn, tmp_path)
    os.environ["FIXTURE_ADAPTER_CASE"] = "path_violation"
    try:
        _run_s4(conn, ticket_id, tmp_path)
    finally:
        os.environ.pop("FIXTURE_ADAPTER_CASE", None)
    item = _open_escalation_item(conn, ticket_id)

    with pytest.raises(ActionRefused):
        queue.act(conn, item_id=item["id"], action="resume", actor="abhishek", runs_dir=tmp_path)

    event = conn.execute(
        "SELECT id, created_at FROM incident_observation WHERE ticket_id = ? AND record_kind = 'control_defect_event'",
        (ticket_id,),
    ).fetchone()
    record.insert(
        conn, "incident_observation", ticket_id=ticket_id, record_kind="control_disposition",
        event_id=event["id"], disposition="remediated", created_at=record.now(),
        recorder_identity="abhishek",
    )

    # A disposition alone is not enough: no passing gate run yet.
    with pytest.raises(ActionRefused):
        queue.act(conn, item_id=item["id"], action="resume", actor="abhishek", runs_dir=tmp_path)

    gate_id = record.insert(
        conn, "utility_run", kind="gate", ticket_id=ticket_id, outcome="pass",
        started_at=record.now(), heartbeat_at=record.now(), lease_expires_at=record.now(),
    )
    assert gate_id

    queue.act(conn, item_id=item["id"], action="resume", actor="abhishek", runs_dir=tmp_path)
    assert record.get(conn, "ticket", ticket_id)["state"] == "context"


def test_an_infrastructure_escalation_resumes_the_same_item_with_quota_preserved(tmp_path):
    """An infrastructure-caused escalation resumes the same item outright, straight
    back to `implementing`, no remediation ceremony required."""
    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = _ready_ticket(conn, tmp_path)
    os.environ["FIXTURE_ADAPTER_CASE"] = "error"
    try:
        _run_s4(conn, ticket_id, tmp_path)
        _run_s4(conn, ticket_id, tmp_path)
    finally:
        os.environ.pop("FIXTURE_ADAPTER_CASE", None)
    assert record.get(conn, "ticket", ticket_id)["state"] == "escalated"
    item = _open_escalation_item(conn, ticket_id)

    queue.act(conn, item_id=item["id"], action="resume", actor="abhishek", runs_dir=tmp_path)

    assert record.get(conn, "ticket", ticket_id)["state"] == "implementing"


_TWO_TASK_PLAN = """## Scope and discretion

| path | action | reason |
|---|---|---|
| src/main/java/com/fixture/Widget.java | touch | implements widget compute |
| src/main/java/com/fixture/WidgetHelper.java | create | helper extracted from Widget |

## Tasks

| id | title | depends_on | criteria | files | validation_recipe | validation_args | expected_result | no_behaviour_change |
|---|---|---|---|---|---|---|---|---|
| T-1 | implement widget compute |  | AC-1 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile | compiles clean | no |
| T-2 | add widget helper | T-1 | AC-1 | src/main/java/com/fixture/WidgetHelper.java | fixture_compile | target=out/compile | compiles clean | no |
"""


def test_a_second_tasks_invocation_aborts_on_budget_and_keeps_that_outcome(tmp_path):
    """A `stage_run` that exceeds the per-ticket S4 budget keeps
    `outcome = 'aborted_budget'`, already escalated by `budgets.abort` -- S4 adds nothing further.

    A two-task plan, so the first task's pass alone does not already fire
    `s4_pass` and leave `implementing` -- the second task's own invocation
    is what the cumulative per-ticket budget then refuses.
    """
    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = _ready_ticket(conn, tmp_path, tier_final="standard", plan_text=_TWO_TASK_PLAN)

    os.environ["FIXTURE_ADAPTER_CASE"] = "price_table"
    try:
        first = _run_s4(conn, ticket_id, tmp_path)
    finally:
        os.environ.pop("FIXTURE_ADAPTER_CASE", None)
    assert first == "pass"

    second = _run_s4(conn, ticket_id, tmp_path)

    assert second == "aborted_budget"
    run = _last_s4_run(conn, ticket_id)
    assert run["outcome"] == "aborted_budget"
    ticket = record.get(conn, "ticket", ticket_id)
    assert ticket["state"] == "escalated"
    assert conn.execute(
        "SELECT COUNT(*) FROM queue_item WHERE ticket_id = ? AND kind = 'escalation'", (ticket_id,)
    ).fetchone()[0] == 1
