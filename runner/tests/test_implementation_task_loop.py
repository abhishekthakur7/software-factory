"""implementation's per-task loop: one fresh top-level `stage_run` per plan task, in dependency
order, the pre-invocation revalidation against the target base, and `verification_attempt`
numbering.
"""
import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml

from runner import artefact_registry, git_trees, manifest, record, run_ledger
from runner.db import connect
from runner.tests import support
from runner.paths import FACTORY_DIR
from runner.stages import run_stage

EVAL_DIR = FACTORY_DIR / "evals" / "agents" / "implementation"
FIXTURES = Path(__file__).parent / "fixtures" / "implementation_task_loop"
PLAN_TEXT = (FIXTURES / "plan.md").read_text()
CRITERIA_TEXT = (Path(__file__).parent / "fixtures" / "planning" / "criteria.md").read_text()

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


def _ready_ticket(conn, tmp_path, *, plan_text: str = PLAN_TEXT, widget_source: str = _WIDGET_OK, **ticket_fields) -> int:
    """A ticket in `implementing` with a real worktree, a bound plan tuple, and a registered plan/criteria."""
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


def _run_implementation(conn, ticket_id, tmp_path, *, out="empty_deviations", worktree=None) -> str:
    os.environ["FIXTURE_ADAPTER_OUT_DIR"] = str(EVAL_DIR / "fixtures" / out / "out")
    if worktree is not None:
        os.environ["FIXTURE_ADAPTER_WORKTREE_DIR"] = str(EVAL_DIR / "fixtures" / worktree / "worktree")
    try:
        return run_stage(conn, ticket_id, "implementation", runs_dir=tmp_path)
    finally:
        os.environ.pop("FIXTURE_ADAPTER_OUT_DIR", None)
        os.environ.pop("FIXTURE_ADAPTER_WORKTREE_DIR", None)


def _last_implementation_run(conn, ticket_id):
    """The latest top-level implementation run (`parent_run_id IS NULL`) -- never a child agent invocation."""
    return conn.execute(
        "SELECT * FROM stage_run WHERE ticket_id = ? AND stage = 'implementation' AND parent_run_id IS NULL ORDER BY id DESC LIMIT 1",
        (ticket_id,),
    ).fetchone()


def _task_validation_evidence(conn, top_level_run_id):
    """The artefact id `_validate_task` registered for this attempt's own validation-recipe run."""
    return conn.execute(
        "SELECT evidence_artefact FROM check_result WHERE stage_run_id = ? AND check_name = 'task_validation'",
        (top_level_run_id,),
    ).fetchone()["evidence_artefact"]


def _staged_input_artefact_ids(conn, top_level_run_id) -> list[int]:
    """The artefact ids the agent invocation under this attempt was actually handed, read back off its own `stage_run.inputs`."""
    child = conn.execute(
        "SELECT inputs FROM stage_run WHERE parent_run_id = ? ORDER BY id DESC LIMIT 1", (top_level_run_id,),
    ).fetchone()
    return json.loads(child["inputs"]) if child is not None and child["inputs"] else []


def _clean_compiled_output(conn, ticket_id) -> None:
    """Remove `fixture_compile`'s own output directory from the ticket worktree.

    The recipe writes compiled classes straight into the checkout (its
    `--out` argument, not a sandbox scratch dir), after the attempt that
    ran it already committed its hand-back -- a real passing compile
    between two attempts in the same test would otherwise leave classes
    on disk for `git add -A` to sweep into a later, unrelated task's
    commit and diff.
    """
    worktree = record.get(conn, "ticket", ticket_id)["worktree_path"]
    subprocess.run(["git", "clean", "-fdxq", "--", "out"], cwd=worktree, capture_output=True, text=True)


def test_a_stale_target_base_starts_no_agent_and_leaves_the_ticket_in_implementing(tmp_path):
    """The plan tuple's `base_sha` and the ticket's `target_base_sha` no longer
    equal the fetched target head -- no invocation, a `fail`/`stale_binding` run with a null
    `verification_attempt`, one `red_check` item, and the ticket stays `implementing`."""
    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = _ready_ticket(conn, tmp_path)
    source = Path(record.get(conn, "ticket", ticket_id)["worktree_path"]).parent.parent.parent / "source-repo"
    (source / "README.md").write_text("moved on\n")
    _git(["add", "-A"], cwd=source)
    _git(["commit", "-q", "-m", "target branch moved"], cwd=source, env=_COMMIT_ENV)

    outcome = _run_implementation(conn, ticket_id, tmp_path)

    assert outcome == "fail"
    ticket = record.get(conn, "ticket", ticket_id)
    assert ticket["state"] == "implementing"
    stage_run = _last_implementation_run(conn, ticket_id)
    assert stage_run["outcome"] == "fail"
    assert stage_run["failure_kind"] == "stale_binding"
    assert stage_run["verification_attempt"] is None
    assert conn.execute(
        "SELECT COUNT(*) FROM queue_item WHERE ticket_id = ? AND kind = 'red_check' AND resolved_at IS NULL",
        (ticket_id,),
    ).fetchone()[0] == 1


def test_a_second_stale_attempt_opens_no_second_red_check_item(tmp_path):
    """The reason clause is `unless one is open`: a repeat stale attempt never doubles the queue item."""
    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = _ready_ticket(conn, tmp_path)
    source = Path(record.get(conn, "ticket", ticket_id)["worktree_path"]).parent.parent.parent / "source-repo"
    (source / "README.md").write_text("moved on\n")
    _git(["add", "-A"], cwd=source)
    _git(["commit", "-q", "-m", "target branch moved"], cwd=source, env=_COMMIT_ENV)

    _run_implementation(conn, ticket_id, tmp_path)
    _run_implementation(conn, ticket_id, tmp_path)

    assert conn.execute(
        "SELECT COUNT(*) FROM queue_item WHERE ticket_id = ? AND kind = 'red_check'", (ticket_id,)
    ).fetchone()[0] == 1


def test_three_consecutive_verification_failures_number_one_two_three(tmp_path):
    """Three red validations against the same plan-item version consume
    `verification_attempt` 1, then 2, then 3, in order."""
    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = _ready_ticket(conn, tmp_path, widget_source=_WIDGET_BROKEN)

    attempts = []
    for _ in range(3):
        _run_implementation(conn, ticket_id, tmp_path)
        run = _last_implementation_run(conn, ticket_id)
        assert run["outcome"] == "fail"
        assert run["failure_kind"] == "verification"
        attempts.append(run["verification_attempt"])

    assert attempts == [1, 2, 3]


def test_an_infrastructure_failure_retries_without_consuming_a_verification_attempt(tmp_path):
    """An unavailable-runtime `stage_run` gets one ordinary retry, and neither it nor
    its retry has advanced past the verification slot the first genuine attempt will occupy."""
    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = _ready_ticket(conn, tmp_path)

    os.environ["FIXTURE_ADAPTER_CASE"] = "error"
    try:
        first = _run_implementation(conn, ticket_id, tmp_path)
    finally:
        os.environ.pop("FIXTURE_ADAPTER_CASE", None)
    assert first == "infrastructure_failure"
    first_run = _last_implementation_run(conn, ticket_id)
    assert first_run["outcome"] == "infrastructure_failure"
    assert record.get(conn, "ticket", ticket_id)["state"] == "implementing"

    second = _run_implementation(conn, ticket_id, tmp_path)
    assert second == "pass"
    second_run = _last_implementation_run(conn, ticket_id)
    assert second_run["verification_attempt"] == 1  # the infra failure consumed no slot


def test_a_second_consecutive_infrastructure_failure_escalates(tmp_path):
    """A repeat infrastructure failure escalates with `outcome = 'infrastructure_failure'`,
    never consuming a `verification_attempt`."""
    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = _ready_ticket(conn, tmp_path)

    os.environ["FIXTURE_ADAPTER_CASE"] = "error"
    try:
        _run_implementation(conn, ticket_id, tmp_path)
        outcome = _run_implementation(conn, ticket_id, tmp_path)
    finally:
        os.environ.pop("FIXTURE_ADAPTER_CASE", None)

    assert outcome == "infrastructure_failure"
    ticket = record.get(conn, "ticket", ticket_id)
    assert ticket["state"] == "escalated"
    run = _last_implementation_run(conn, ticket_id)
    # Neither infrastructure failure ever reached verification, so both
    # carry the same slot number the first genuine attempt would have.
    assert run["verification_attempt"] == 1
    assert conn.execute(
        "SELECT COUNT(*) FROM queue_item WHERE ticket_id = ? AND kind = 'escalation'", (ticket_id,)
    ).fetchone()[0] == 1


_UNDECLARED_RECIPE_PLAN = """## Scope and discretion

| path | action | reason |
|---|---|---|
| src/main/java/com/fixture/Widget.java | touch | implements widget compute |

## Tasks

| id | title | depends_on | criteria | files | validation_recipe | validation_args | expected_result | no_behaviour_change |
|---|---|---|---|---|---|---|---|---|
| T-1 | implement widget compute |  | AC-1 | src/main/java/com/fixture/Widget.java | not_a_real_recipe |  | compiles clean | no |
"""


def test_an_unapproved_recipe_id_ends_the_run_as_a_control_defect_and_escalates(tmp_path):
    """A task naming a recipe id outside `project.yaml`'s approved list ends its
    `stage_run` as a control defect (`fail`/`recipe_binding`), consumes no verification quota,
    tags `control_defect` (`unsafe_execution`), opens a `control_defect_event`, and escalates immediately."""
    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = _ready_ticket(conn, tmp_path, plan_text=_UNDECLARED_RECIPE_PLAN)

    outcome = _run_implementation(conn, ticket_id, tmp_path)

    assert outcome == "fail"
    run = _last_implementation_run(conn, ticket_id)
    assert run["outcome"] == "fail"
    # A control defect never reached verification, so it never counts
    # toward the verification-failure quota, whatever number its own row
    # happens to carry (computed before the recipe binding was checked).
    assert run["failure_kind"] == "recipe_binding"
    ticket = record.get(conn, "ticket", ticket_id)
    assert ticket["state"] == "escalated"
    tag = conn.execute(
        "SELECT * FROM tag WHERE ticket_id = ? AND event_kind = 'control_defect' ORDER BY id DESC LIMIT 1", (ticket_id,)
    ).fetchone()
    assert tag["fm_id"] == "unsafe_execution"
    incident = conn.execute(
        "SELECT * FROM incident_observation WHERE ticket_id = ? AND record_kind = 'control_defect_event'", (ticket_id,)
    ).fetchone()
    assert incident["control_category"] == "execution_boundary"
    assert conn.execute(
        "SELECT COUNT(*) FROM queue_item WHERE ticket_id = ? AND kind = 'escalation'", (ticket_id,)
    ).fetchone()[0] == 1


def test_a_retried_task_registers_a_fresh_handoff_version_not_a_continuation(tmp_path):
    """Each attempt registers its own `handoff` artefact version -- a retry never
    reuses the failed run's own registered inputs."""
    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = _ready_ticket(conn, tmp_path, widget_source=_WIDGET_BROKEN)

    _run_implementation(conn, ticket_id, tmp_path)
    _run_implementation(conn, ticket_id, tmp_path)

    handoffs = conn.execute(
        "SELECT version, stage_run_id FROM artefact WHERE ticket_id = ? AND kind = 'handoff' ORDER BY version",
        (ticket_id,),
    ).fetchall()
    assert [row["version"] for row in handoffs] == [1, 2]
    assert handoffs[0]["stage_run_id"] != handoffs[1]["stage_run_id"]


def test_a_successful_invocation_runs_the_approved_recipe_once_and_passes(tmp_path):
    """A green task run leaves `stage_run.outcome = 'pass'`, with exactly one
    `task_validation` check result recorded against it."""
    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = _ready_ticket(conn, tmp_path)

    outcome = _run_implementation(conn, ticket_id, tmp_path)

    assert outcome == "pass"
    run = _last_implementation_run(conn, ticket_id)
    assert run["outcome"] == "pass"
    assert run["plan_item"] == "T-1"
    checks = conn.execute(
        "SELECT * FROM check_result WHERE stage_run_id = ? AND check_name = 'task_validation'", (run["id"],)
    ).fetchall()
    assert len(checks) == 1
    assert checks[0]["result"] == "pass"


def test_a_new_plan_tuple_starts_a_fresh_verification_count(tmp_path):
    """A superseding plan-item version (a new `plan` `evidence_tuple` row) starts
    `verification_attempt` back at 1 for the same task id -- no migration of the old count."""
    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = _ready_ticket(conn, tmp_path, widget_source=_WIDGET_BROKEN)

    _run_implementation(conn, ticket_id, tmp_path)
    _run_implementation(conn, ticket_id, tmp_path)
    second_run = _last_implementation_run(conn, ticket_id)
    assert second_run["verification_attempt"] == 2

    # A superseding plan version: a new plan artefact, re-derived and
    # re-approved the way a fresh planning pass and its approval would leave it.
    revised_path = tmp_path / f"plan-{ticket_id}-revised.md"
    revised_path.write_text(PLAN_TEXT.replace("implement widget compute", "implement widget compute, revised"))
    prior = artefact_registry.latest(conn, ticket_id, "plan")
    artefact_registry.register(conn, ticket_id=ticket_id, kind="plan", path=revised_path, supersedes=prior["id"])
    support.approve_current_plan(conn, ticket_id, tmp_path)

    _run_implementation(conn, ticket_id, tmp_path)
    third_run = _last_implementation_run(conn, ticket_id)
    assert third_run["verification_attempt"] == 1
    assert third_run["plan_tuple_id"] != second_run["plan_tuple_id"]


def test_a_task_with_a_retained_passing_result_is_skipped(tmp_path):
    """A task whose plan-bound inputs are unchanged and already carries a passing
    `task` run under the current plan tuple keeps that result -- `run_next` moves straight to
    the next due task instead of rerunning it."""
    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = _ready_ticket(conn, tmp_path)
    plan_tuple_id = record.get(conn, "ticket", ticket_id)
    plan_tuple = conn.execute(
        "SELECT id FROM evidence_tuple WHERE ticket_id = ? AND kind = 'plan' ORDER BY id DESC LIMIT 1", (ticket_id,)
    ).fetchone()["id"]

    retained_run_id = run_ledger.open_stage_run(
        conn, ticket_id=ticket_id, stage="implementation", run_kind="task", plan_item="T-1",
        plan_tuple_id=plan_tuple, verification_attempt=1,
    )
    run_ledger.finish(conn, retained_run_id, "pass")

    outcome = _run_implementation(conn, ticket_id, tmp_path)

    assert outcome == "pass"
    run = _last_implementation_run(conn, ticket_id)
    assert run["plan_item"] == "T-2"
    assert run["id"] != retained_run_id


def test_a_retried_task_s_invocation_carries_the_failed_attempt_s_validation_evidence(tmp_path):
    """A failed attempt closes with its evidence and feeds the next fresh attempt: the retry's
    own invocation is handed the artefact the failed attempt's validation recipe registered,
    while the first attempt -- having no prior failure of its own -- is handed none of it."""
    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = _ready_ticket(conn, tmp_path, widget_source=_WIDGET_BROKEN)

    _run_implementation(conn, ticket_id, tmp_path)
    first_run = _last_implementation_run(conn, ticket_id)
    assert first_run["outcome"] == "fail"
    assert first_run["failure_kind"] == "verification"
    evidence_id = _task_validation_evidence(conn, first_run["id"])
    assert evidence_id is not None
    assert evidence_id not in _staged_input_artefact_ids(conn, first_run["id"])

    _run_implementation(conn, ticket_id, tmp_path)
    second_run = _last_implementation_run(conn, ticket_id)
    assert second_run["plan_item"] == first_run["plan_item"]
    assert evidence_id in _staged_input_artefact_ids(conn, second_run["id"])


def test_a_verification_failure_s_evidence_still_reaches_the_attempt_after_an_intervening_infrastructure_failure(tmp_path):
    """Infrastructure failures consume no verification bound and produce no validation evidence of
    their own; the ordinary single retry the per-task loop gives them never breaks the chain -- the next real
    attempt still carries what the last genuine verification failure registered."""
    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = _ready_ticket(conn, tmp_path, widget_source=_WIDGET_BROKEN)

    _run_implementation(conn, ticket_id, tmp_path)
    first_run = _last_implementation_run(conn, ticket_id)
    evidence_id = _task_validation_evidence(conn, first_run["id"])
    assert evidence_id is not None

    os.environ["FIXTURE_ADAPTER_CASE"] = "error"
    try:
        infra_outcome = _run_implementation(conn, ticket_id, tmp_path)
    finally:
        os.environ.pop("FIXTURE_ADAPTER_CASE", None)
    assert infra_outcome == "infrastructure_failure"

    _run_implementation(conn, ticket_id, tmp_path)
    third_run = _last_implementation_run(conn, ticket_id)
    assert third_run["plan_item"] == first_run["plan_item"]
    assert third_run["verification_attempt"] == 2  # the infra failure consumed no slot
    assert evidence_id in _staged_input_artefact_ids(conn, third_run["id"])


def test_a_different_task_s_first_attempt_carries_no_evidence_from_an_earlier_task(tmp_path):
    """Evidence is per task: a task's own retry gets its own failed attempt's evidence, but a
    different task's first attempt under the same ticket and plan tuple gets none of it."""
    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = _ready_ticket(conn, tmp_path, widget_source=_WIDGET_BROKEN)

    _run_implementation(conn, ticket_id, tmp_path)
    t1_first_run = _last_implementation_run(conn, ticket_id)
    assert t1_first_run["plan_item"] == "T-1"
    t1_evidence_id = _task_validation_evidence(conn, t1_first_run["id"])
    assert t1_evidence_id is not None

    _run_implementation(conn, ticket_id, tmp_path, worktree="ok")
    t1_second_run = _last_implementation_run(conn, ticket_id)
    assert t1_second_run["plan_item"] == "T-1"
    assert t1_second_run["outcome"] == "pass"
    _clean_compiled_output(conn, ticket_id)

    _run_implementation(conn, ticket_id, tmp_path, worktree="fix_round_break_compile")
    t2_first_run = _last_implementation_run(conn, ticket_id)
    assert t2_first_run["plan_item"] == "T-2"
    assert t2_first_run["outcome"] == "fail"
    assert t2_first_run["failure_kind"] == "verification"
    t2_evidence_id = _task_validation_evidence(conn, t2_first_run["id"])
    assert t2_evidence_id is not None
    assert t1_evidence_id not in _staged_input_artefact_ids(conn, t2_first_run["id"])

    _run_implementation(conn, ticket_id, tmp_path, worktree="ok")
    t2_second_run = _last_implementation_run(conn, ticket_id)
    assert t2_second_run["plan_item"] == "T-2"
    t2_second_inputs = _staged_input_artefact_ids(conn, t2_second_run["id"])
    assert t2_evidence_id in t2_second_inputs
    assert t1_evidence_id not in t2_second_inputs
