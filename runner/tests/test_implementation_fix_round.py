"""The fix-round route classifier and implementation's own bounded machine repair loop.

`red_route.classify` is pure -- its own tests below exercise it directly,
no database. The rest drive the real implementation driver through a ticket already
routed back by a seeded checks attempt, the same shape the real checks driver
(built alongside this one, elsewhere) leaves behind: a `check_result`
`fix_round_route` with `result = 'pass'` on the ticket's latest checks run.
"""
import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

from runner import artefact_registry, git_trees, manifest, operations, record, run_ledger, stages
from runner.checks import red_route
from runner.checks.red_route import CheckOutcome, RecipeOutcome, Route
from runner.db import connect
from runner.tests import support
from runner.paths import FACTORY_DIR
from runner.stages import implementation, checks, run_stage

EVAL_DIR = FACTORY_DIR / "evals" / "agents" / "implementation"
FIXTURES = Path(__file__).parent / "fixtures" / "implementation_fix_round"
PLAN_TEXT = (FIXTURES / "plan.md").read_text()
PLAN_TEXT_NO_TEST_STRATEGY = (FIXTURES / "plan_no_test_strategy.md").read_text()
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


def test_lint_and_compile_reds_alone_route_to_a_fix_round():
    """Every red result a lint or compile-type recipe -- always machine-only-eligible,
    whatever their base/head history."""
    results = [
        RecipeOutcome("fixture_lint", "lint", None, base=None, head="fail"),
        RecipeOutcome("fixture_compile", "compile", None, base="fail", head="fail"),
    ]
    assert red_route.classify(results, rounds_run=0, cap=2) == Route("fix_round")


def test_a_unit_test_green_at_base_and_red_at_head_routes_to_a_fix_round():
    """A unit/integration test that regressed at head, having been green at base."""
    results = [RecipeOutcome("fixture_unit", "test", "unit", base="pass", head="fail")]
    assert red_route.classify(results, rounds_run=1, cap=2) == Route("fix_round")


def test_a_test_already_red_at_base_refuses_the_machine_only_route():
    """A unit/integration test red at base too is inherited debt, not this ticket's
    regression -- refused, reason `base_red`."""
    results = [RecipeOutcome("fixture_unit", "test", "unit", base="fail", head="fail")]
    assert red_route.classify(results, rounds_run=0, cap=2) == Route("red_check", "base_red")


def test_an_end_to_end_red_refuses_the_machine_only_route_regardless_of_base():
    """An end-to-end result never routes through a fix round, whatever its base state."""
    results = [RecipeOutcome("fixture_e2e", "test", "end_to_end", base="pass", head="fail")]
    assert red_route.classify(results, rounds_run=0, cap=2) == Route("red_check", "end_to_end")


def test_a_red_outside_the_eligible_kinds_alongside_an_eligible_one_refuses_the_route():
    """Mixing a red result outside {lint, compile, unit test, integration test} with
    an otherwise-eligible one refuses the whole route -- reason `mixed`."""
    results = [
        RecipeOutcome("fixture_compile", "compile", None, base=None, head="fail"),
        CheckOutcome("behavior_contract_evidence", "fail"),
    ]
    assert red_route.classify(results, rounds_run=0, cap=2) == Route("red_check", "mixed")


def test_the_cap_refuses_the_route_before_the_red_results_are_even_examined():
    """A ticket at or past the fix-round cap is refused a further round regardless of
    how confined its red results look."""
    results = [RecipeOutcome("fixture_lint", "lint", None, base=None, head="fail")]
    assert red_route.classify(results, rounds_run=2, cap=2) == Route("red_check", "cap_reached")


_WIDGET_BASE = "package com.fixture;\n\npublic class Widget {\n    public int compute(int x) {\n        return x * 2;\n    }\n}\n"
_WIDGET_TEST_BASE = (
    "package com.fixture;\n\npublic class WidgetUnitTest {\n"
    "    public static void main(String[] args) {\n"
    "        Widget w = new Widget();\n"
    "        if (w.compute(2) != 4) {\n"
    "            System.out.println(\"compute(2) should be 4\");\n"
    "            System.exit(1);\n"
    "        }\n"
    "        System.out.println(\"ran: com.fixture.WidgetUnitTest#test\");\n"
    "    }\n"
    "}\n"
)


def _source_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "source-repo"
    repo.mkdir()
    _git(["init", "-q"], cwd=repo)
    _git(["checkout", "-q", "-b", "main"], cwd=repo)
    main_src = repo / "src" / "main" / "java" / "com" / "fixture"
    main_src.mkdir(parents=True)
    (main_src / "Widget.java").write_text(_WIDGET_BASE)
    test_src = repo / "src" / "test" / "java" / "com" / "fixture"
    test_src.mkdir(parents=True)
    (test_src / "WidgetUnitTest.java").write_text(_WIDGET_TEST_BASE)
    (repo / "README.md").write_text("seed\n")
    _git(["add", "-A"], cwd=repo)
    _git(["commit", "-q", "-m", "init"], cwd=repo, env=_COMMIT_ENV)
    return repo


def _ready_ticket(conn, tmp_path, *, plan_text: str = PLAN_TEXT) -> int:
    ticket_id = record.insert(
        conn, "ticket", trust_profile_hash=support.TRUST_PROFILE_HASH, trust_approval_set_hash=support.TRUST_APPROVAL_SET_HASH, state="implementing", opened_at=record.now(),
        service="fixture-project", ticket_type="small_feature", tier_provisional="standard",
        factory_manifest_hash=manifest.current_hash(),
    )
    source = _source_repo(tmp_path)
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


def _route_via_checks(conn, ticket_id: int) -> int:
    """Seed the marker the real checks driver leaves on a ticket it is routing to a fix round."""
    checks_run_id = run_ledger.open_stage_run(conn, ticket_id=ticket_id, stage="checks")
    run_ledger.finish(conn, checks_run_id, "blocked")
    record.insert(
        conn, "check_result", stage_run_id=checks_run_id, check_name="fix_round_route", check_tier="blocking",
        source="runner", result="pass", canonical_serialization_version=1, content_hash="fix-round-route-pass",
    )
    return checks_run_id


def _run_fix_round(conn, ticket_id, tmp_path, *, worktree=None, case=None) -> str:
    os.environ["FIXTURE_ADAPTER_OUT_DIR"] = str(EVAL_DIR / "fixtures" / "empty_deviations" / "out")
    if worktree is not None:
        os.environ["FIXTURE_ADAPTER_WORKTREE_DIR"] = str(EVAL_DIR / "fixtures" / worktree / "worktree")
    if case is not None:
        os.environ["FIXTURE_ADAPTER_CASE"] = case
    try:
        return run_stage(conn, ticket_id, "implementation", runs_dir=tmp_path)
    finally:
        os.environ.pop("FIXTURE_ADAPTER_OUT_DIR", None)
        os.environ.pop("FIXTURE_ADAPTER_WORKTREE_DIR", None)
        os.environ.pop("FIXTURE_ADAPTER_CASE", None)


def _last_implementation_run(conn, ticket_id):
    return conn.execute(
        "SELECT * FROM stage_run WHERE ticket_id = ? AND stage = 'implementation' AND parent_run_id IS NULL "
        "AND run_kind = 'fix_round' ORDER BY id DESC LIMIT 1",
        (ticket_id,),
    ).fetchone()


def test_an_authorized_base_test_change_passes_and_is_recorded_as_a_deviation(tmp_path):
    """A base test the plan's Test strategy table lists with `action = 'change'` may
    change; the fix round records that change as its own `deviation` row naming the authorizing
    criterion, on top of whatever the agent's own hand-back reported."""
    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = _ready_ticket(conn, tmp_path)
    _route_via_checks(conn, ticket_id)

    outcome = _run_fix_round(conn, ticket_id, tmp_path, worktree="fix_round_authorized")

    assert outcome == "pass"
    run = _last_implementation_run(conn, ticket_id)
    assert run["outcome"] == "pass"
    deviation = conn.execute(
        "SELECT * FROM deviation WHERE ticket_id = ? AND stage_run_id = ? AND agent_did LIKE '%WidgetUnitTest.java%'",
        (ticket_id, run["id"]),
    ).fetchone()
    assert deviation is not None
    assert deviation["plan_item"] == "AC-1"
    assert deviation["kind"] == "judgment"


def test_an_unauthorized_base_test_change_is_refused(tmp_path):
    """The same worktree edit, against a plan whose Test strategy table lists no authorizing
    row, is refused -- the round fails and queues one `red_check` -- but the runner still
    records the change as an `unplanned` `deviation` row at hand-back, before the refusal
    is even decided."""
    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = _ready_ticket(conn, tmp_path, plan_text=PLAN_TEXT_NO_TEST_STRATEGY)
    _route_via_checks(conn, ticket_id)

    outcome = _run_fix_round(conn, ticket_id, tmp_path, worktree="fix_round_authorized")

    assert outcome == "fail"
    run = _last_implementation_run(conn, ticket_id)
    assert run["outcome"] == "fail"
    assert run["failure_kind"] == "verification"
    deviation = conn.execute(
        "SELECT * FROM deviation WHERE stage_run_id = ? AND agent_did LIKE '%WidgetUnitTest.java%'", (run["id"],)
    ).fetchone()
    assert deviation is not None
    assert deviation["plan_item"] == "unplanned"
    assert conn.execute(
        "SELECT COUNT(*) FROM queue_item WHERE ticket_id = ? AND kind = 'red_check' AND resolved_at IS NULL",
        (ticket_id,),
    ).fetchone()[0] == 1


def test_must_reject_a_diff_touching_only_test_files(tmp_path):
    """A fix round is meant to repair the production change, not just
    its tests -- a diff naming no production file at all is refused outright."""
    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = _ready_ticket(conn, tmp_path)
    _route_via_checks(conn, ticket_id)

    outcome = _run_fix_round(conn, ticket_id, tmp_path, worktree="fix_round_test_only")

    assert outcome == "fail"
    run = _last_implementation_run(conn, ticket_id)
    assert run["failure_kind"] == "verification"
    check = conn.execute(
        "SELECT * FROM check_result WHERE stage_run_id = ? AND check_name = 'fix_round_scope' ORDER BY id DESC LIMIT 1",
        (run["id"],),
    ).fetchone()
    assert check["result"] == "fail"
    assert "test" in check["summary"]


def test_must_reject_a_fix_round_diff_that_touches_a_path_outside_the_plan_scope(tmp_path):
    """An out-of-scope file in the round's diff fails `scope_diff` the
    same way it would for an ordinary task's hand-back."""
    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = _ready_ticket(conn, tmp_path)
    _route_via_checks(conn, ticket_id)

    outcome = _run_fix_round(conn, ticket_id, tmp_path, worktree="fix_round_out_of_scope")

    assert outcome == "fail"
    run = _last_implementation_run(conn, ticket_id)
    assert run["failure_kind"] == "verification"
    check = conn.execute(
        "SELECT * FROM check_result WHERE stage_run_id = ? AND check_name = 'scope_diff' ORDER BY id DESC LIMIT 1",
        (run["id"],),
    ).fetchone()
    assert check["result"] == "fail"
    assert "Unrelated.java" in check["summary"]


def test_must_reject_a_fix_round_whose_post_handback_validation_is_red(tmp_path):
    """After a passing hand-back, the runner validates every task once
    with no agent; a red validation fails the round even though the hand-back itself was clean."""
    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = _ready_ticket(conn, tmp_path)
    _route_via_checks(conn, ticket_id)

    outcome = _run_fix_round(conn, ticket_id, tmp_path, worktree="fix_round_break_compile")

    assert outcome == "fail"
    run = _last_implementation_run(conn, ticket_id)
    assert run["failure_kind"] == "verification"
    validation_only = conn.execute(
        "SELECT * FROM stage_run WHERE ticket_id = ? AND run_kind = 'validation_only' ORDER BY id DESC LIMIT 1",
        (ticket_id,),
    ).fetchone()
    assert validation_only is not None
    assert validation_only["outcome"] == "fail"


def test_a_fix_round_that_exceeds_the_per_ticket_budget_aborts_and_consumes_no_verification_attempt(tmp_path):
    """A `fix_round` `stage_run` that exceeds the per-ticket implementation budget aborts with
    `outcome = 'aborted_budget'` and never carries a `verification_attempt`."""
    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = _ready_ticket(conn, tmp_path)

    # Exhaust the per-ticket budget with one ordinary task run first.
    os.environ["FIXTURE_ADAPTER_OUT_DIR"] = str(EVAL_DIR / "fixtures" / "empty_deviations" / "out")
    os.environ["FIXTURE_ADAPTER_CASE"] = "price_table"
    try:
        first = run_stage(conn, ticket_id, "implementation", runs_dir=tmp_path)
    finally:
        os.environ.pop("FIXTURE_ADAPTER_OUT_DIR", None)
        os.environ.pop("FIXTURE_ADAPTER_CASE", None)
    assert first == "pass"
    assert record.get(conn, "ticket", ticket_id)["state"] == "checks"
    # The one task's own pass already moved the ticket to `checks`; stand
    # in for the `checks_fix_round` transition routing it back before this
    # round starts.
    record.update(conn, "ticket", ticket_id, state="implementing")

    _route_via_checks(conn, ticket_id)
    outcome = _run_fix_round(conn, ticket_id, tmp_path)

    assert outcome == "aborted_budget"
    run = _last_implementation_run(conn, ticket_id)
    assert run["outcome"] == "aborted_budget"
    assert run["verification_attempt"] is None
    assert record.get(conn, "ticket", ticket_id)["state"] == "escalated"


def test_a_ticket_at_the_fix_round_cap_is_refused_a_further_round(tmp_path):
    """Once `limits.yaml`'s `fix_rounds.max_per_ticket` rounds have already run, the
    next one is refused before starting and a `red_check` item is queued."""
    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = _ready_ticket(conn, tmp_path)
    cap = implementation._fix_rounds_cap()
    for _ in range(cap):
        prior_id = run_ledger.open_stage_run(conn, ticket_id=ticket_id, stage="implementation", run_kind="fix_round")
        run_ledger.finish(conn, prior_id, "fail", failure_kind="verification")
    _route_via_checks(conn, ticket_id)

    outcome = _run_fix_round(conn, ticket_id, tmp_path)

    assert outcome == "blocked"
    assert record.get(conn, "ticket", ticket_id)["state"] == "implementing"
    assert conn.execute(
        "SELECT COUNT(*) FROM queue_item WHERE ticket_id = ? AND kind = 'red_check' AND resolved_at IS NULL",
        (ticket_id,),
    ).fetchone()[0] == 1


def test_a_passing_round_returns_the_ticket_to_checks_with_its_validation_run_closed(tmp_path):
    """A round's pass applies `implementation_pass` itself -- the same event the ordinary
    per-task path applies -- so the ticket leaves `implementing` for `checks`
    instead of sitting there with nothing left to distinguish it from a ticket
    still mid-round."""
    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = _ready_ticket(conn, tmp_path)
    _route_via_checks(conn, ticket_id)

    outcome = _run_fix_round(conn, ticket_id, tmp_path, worktree="fix_round_authorized")

    assert outcome == "pass"
    assert record.get(conn, "ticket", ticket_id)["state"] == "checks"
    validation_only = conn.execute(
        "SELECT outcome FROM stage_run WHERE ticket_id = ? AND run_kind = 'validation_only' ORDER BY id DESC LIMIT 1",
        (ticket_id,),
    ).fetchone()
    assert validation_only["outcome"] == "pass"


def test_the_next_advance_after_a_passing_round_reruns_checks_instead_of_a_second_round(tmp_path, monkeypatch):
    """Once a round has passed the ticket back into `checks`, the next `factory
    advance` is due for a fresh checks attempt: `checks` no longer admits implementation at
    all, so the routing marker a stale re-read of the ticket's latest checks run
    would otherwise still show as `fix_round_route = pass` never gets asked
    again, and no second round opens against it."""
    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = _ready_ticket(conn, tmp_path)
    # Seeded like `_route_via_checks`, but `fix_round_route` carries the tier the
    # real checks driver actually gives it, `advisory` (checks.py's own
    # `_apply_routing`): `_due_stage` separately reads every *blocking*
    # result of a stage's latest run to decide whether that run is fully
    # cleared, and a `blocking`-tier stand-in here would make this seeded,
    # still-`blocked` run look spuriously cleared to that check.
    first_checks_run_id = run_ledger.open_stage_run(conn, ticket_id=ticket_id, stage="checks")
    run_ledger.finish(conn, first_checks_run_id, "blocked")
    record.insert(
        conn, "check_result", stage_run_id=first_checks_run_id, check_name="fix_round_route", check_tier="advisory",
        source="runner", result="pass", canonical_serialization_version=1, content_hash="fix-round-route-pass",
    )

    outcome = _run_fix_round(conn, ticket_id, tmp_path, worktree="fix_round_authorized")
    assert outcome == "pass"
    assert record.get(conn, "ticket", ticket_id)["state"] == "checks"

    # checks's own real recipe run is exercised by its own driver tests; here only
    # the choice of *which* stage `advance` invokes next -- and with which
    # fresh row -- is under test, so its body is a stand-in that just
    # reports which `stage_run` id it was handed.
    seen_stage_run_ids = []

    def fake_checks_run(conn, ticket, stage_run_id, runs_dir):
        seen_stage_run_ids.append(stage_run_id)
        return "pass"

    monkeypatch.setattr(checks, "run", fake_checks_run)

    operations.advance(conn, ticket_id, tmp_path)

    assert seen_stage_run_ids and seen_stage_run_ids[0] != first_checks_run_id
    fresh_run = record.get(conn, "stage_run", seen_stage_run_ids[0])
    assert fresh_run["stage"] == "checks"
    assert fresh_run["outcome"] == "pass"
    assert conn.execute(
        "SELECT COUNT(*) FROM stage_run WHERE ticket_id = ? AND stage = 'implementation' AND run_kind = 'fix_round'",
        (ticket_id,),
    ).fetchone()[0] == 1
    assert record.get(conn, "ticket", ticket_id)["state"] == "checks"


# ---- the removal round checks routes to for an accidental sensitive-path touch ----


def _add_offending_path(worktree: Path) -> None:
    """Add and commit one file under a `sensitive-paths.yaml` glob the fixture plan's own
    scope table never names."""
    auth_dir = worktree / "src" / "main" / "java" / "com" / "fixture" / "auth"
    auth_dir.mkdir(parents=True, exist_ok=True)
    (auth_dir / "Extra.java").write_text("package com.fixture.auth;\n\npublic class Extra {\n}\n")
    _git(["add", "-A"], cwd=worktree)
    _git(["commit", "-q", "-m", "accidental auth touch"], cwd=worktree, env=_COMMIT_ENV)


def _route_via_checks_for_removal(conn, ticket_id: int) -> int:
    """Seed the marker the real checks driver leaves on a ticket it is routing back for a bounded
    removal round -- the same shape `_route_via_checks` seeds for a fix round, under its own check
    name and at the advisory tier the real driver actually uses."""
    checks_run_id = run_ledger.open_stage_run(conn, ticket_id=ticket_id, stage="checks")
    run_ledger.finish(conn, checks_run_id, "blocked")
    record.insert(
        conn, "check_result", stage_run_id=checks_run_id, check_name="removal_route", check_tier="advisory",
        source="runner", result="pass", canonical_serialization_version=1, content_hash="removal-route-pass",
    )
    return checks_run_id


def _fake_removal_agent(remove_offending: bool):
    """Stand in for `stages.invoke_agent`: optionally deletes the offending file, then hands
    back an empty deviation set. The fixture-worker mechanism the other tests in this file use
    can only add files onto a ticket worktree, never remove one, so a round that is actually
    supposed to remove a file needs this direct a substitute instead."""
    def _invoke(conn, ticket, stage, *, runs_dir, parent_run_id=None, input_artefact_ids=None, **_ignored):
        worktree = Path(ticket["worktree_path"])
        offending = worktree / "src" / "main" / "java" / "com" / "fixture" / "auth" / "Extra.java"
        if remove_offending and offending.exists():
            offending.unlink()
        child_id = run_ledger.open_stage_run(
            conn, ticket_id=ticket["id"], stage="implementation", run_kind="task", parent_run_id=parent_run_id,
        )
        run_ledger.finish(conn, child_id, "pass")
        out_dir = implementation._child_out_dir(runs_dir, ticket["id"], child_id)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "handback.json").write_text(json.dumps({"deviations": []}))
        return SimpleNamespace(outcome="pass", failure_kind=None, stage_run_id=child_id)
    return _invoke


def test_a_removal_round_that_removes_the_offending_path_returns_the_ticket_to_checks(tmp_path, monkeypatch):
    """The round checks routes to for an accidental sensitive-path touch is a bounded implementation loop just
    like a fix round: once the hand-back no longer touches the path outside the plan's own
    scope, the round applies `implementation_pass` itself and the ticket leaves `implementing` for
    `checks` with a fresh validation-only run closed."""
    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = _ready_ticket(conn, tmp_path)
    ticket = record.get(conn, "ticket", ticket_id)
    _add_offending_path(Path(ticket["worktree_path"]))
    git_trees.record_head(conn, ticket_id, Path(ticket["worktree_path"]))
    _route_via_checks_for_removal(conn, ticket_id)

    monkeypatch.setattr(stages, "invoke_agent", _fake_removal_agent(remove_offending=True))
    outcome = run_stage(conn, ticket_id, "implementation", runs_dir=tmp_path)

    assert outcome == "pass"
    assert record.get(conn, "ticket", ticket_id)["state"] == "checks"
    run = conn.execute(
        "SELECT * FROM stage_run WHERE ticket_id = ? AND stage = 'implementation' AND run_kind = 'fix_round' ORDER BY id DESC LIMIT 1",
        (ticket_id,),
    ).fetchone()
    assert run["outcome"] == "pass"
    scope_check = conn.execute(
        "SELECT * FROM check_result WHERE stage_run_id = ? AND check_name = 'removal_round_scope' ORDER BY id DESC LIMIT 1",
        (run["id"],),
    ).fetchone()
    assert scope_check["result"] == "pass"
    diff_artefact = conn.execute(
        "SELECT * FROM artefact WHERE stage_run_id = ? AND kind = 'removal_round_diff'", (run["id"],),
    ).fetchone()
    assert diff_artefact is not None
    validation_only = conn.execute(
        "SELECT outcome FROM stage_run WHERE ticket_id = ? AND run_kind = 'validation_only' ORDER BY id DESC LIMIT 1",
        (ticket_id,),
    ).fetchone()
    assert validation_only["outcome"] == "pass"


def test_a_removal_round_whose_handback_still_touches_the_sensitive_path_is_refused(tmp_path, monkeypatch):
    """A round that fails to remove the accidental touch ends where a failed fix round does:
    the ticket stays in `implementing` and one `red_check` is queued, instead of passing back
    into `checks` for a full checks rerun that would only rediscover the same accidental touch."""
    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = _ready_ticket(conn, tmp_path)
    ticket = record.get(conn, "ticket", ticket_id)
    _add_offending_path(Path(ticket["worktree_path"]))
    git_trees.record_head(conn, ticket_id, Path(ticket["worktree_path"]))
    _route_via_checks_for_removal(conn, ticket_id)

    monkeypatch.setattr(stages, "invoke_agent", _fake_removal_agent(remove_offending=False))
    outcome = run_stage(conn, ticket_id, "implementation", runs_dir=tmp_path)

    assert outcome == "fail"
    assert record.get(conn, "ticket", ticket_id)["state"] == "implementing"
    run = conn.execute(
        "SELECT * FROM stage_run WHERE ticket_id = ? AND stage = 'implementation' AND run_kind = 'fix_round' ORDER BY id DESC LIMIT 1",
        (ticket_id,),
    ).fetchone()
    assert run["failure_kind"] == "verification"
    scope_check = conn.execute(
        "SELECT * FROM check_result WHERE stage_run_id = ? AND check_name = 'removal_round_scope' ORDER BY id DESC LIMIT 1",
        (run["id"],),
    ).fetchone()
    assert scope_check["result"] == "fail"
    assert conn.execute(
        "SELECT COUNT(*) FROM queue_item WHERE ticket_id = ? AND kind = 'red_check' AND resolved_at IS NULL",
        (ticket_id,),
    ).fetchone()[0] == 1


def test_a_ticket_at_the_fix_round_cap_is_refused_a_further_removal_round(tmp_path):
    """The removal route shares the fix round's own per-ticket cap (`limits.yaml` carries no
    separate entry): once that cap has already run out on ordinary fix rounds, a ticket checks
    routes back for removal is refused the same way, before a round even starts."""
    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = _ready_ticket(conn, tmp_path)
    cap = implementation._fix_rounds_cap()
    for _ in range(cap):
        prior_id = run_ledger.open_stage_run(conn, ticket_id=ticket_id, stage="implementation", run_kind="fix_round")
        run_ledger.finish(conn, prior_id, "fail", failure_kind="verification")
    _route_via_checks_for_removal(conn, ticket_id)

    outcome = run_stage(conn, ticket_id, "implementation", runs_dir=tmp_path)

    assert outcome == "blocked"
    assert record.get(conn, "ticket", ticket_id)["state"] == "implementing"
    assert conn.execute(
        "SELECT COUNT(*) FROM queue_item WHERE ticket_id = ? AND kind = 'red_check' AND resolved_at IS NULL",
        (ticket_id,),
    ).fetchone()[0] == 1
