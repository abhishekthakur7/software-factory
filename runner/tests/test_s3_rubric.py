"""The plan rubric's script-half findings (`runner.checks.plan_rubric`), the S3.md rubric lines, and their driver placement.

`plan_rubric.check` is exercised two ways: directly, against the
`factory/evals/rubrics/S3/` eval fixtures, one pass/reject pair per rubric
row's script rule; and through the real S3 driver, for the one thing only
a live run can pin -- that the `plan_rubric` check_result lands between
`artefact_structure` and `size_gate` in call order. `factory/rubrics/S3.md`
itself is checked through `runner.rubrics.load`: every grader line the
ticket dictates a judgment sentence for carries it verbatim and is marked
a bootstrap-checklist line, and the seeded `human_verdict` fixtures name
their rubric line and the stated verdict, mirroring S1's own pattern.
"""
import os
import subprocess
from pathlib import Path

import pytest
import yaml

from runner import artefact_registry, artefacts, git_trees, governance, manifest, record, recipes, rubrics
from runner.checks import artefact_structure, plan_rubric
from runner.db import connect
from runner.fs import write_text
from runner.paths import FACTORY_DIR
from runner.stages import run_stage

RUBRIC_PATH = FACTORY_DIR / "rubrics" / "S3.md"
EVAL_DIR = FACTORY_DIR / "evals" / "rubrics" / "S3"
EVAL_SPEC = yaml.safe_load((EVAL_DIR / "eval.yaml").read_text())
RUBRIC_FIXTURES_DIR = EVAL_DIR / "fixtures"

LIMITS = yaml.safe_load((FACTORY_DIR / "config" / "limits.yaml").read_text())
CATALOGUE = recipes.load_catalogue()
PROJECT_RECIPES = yaml.safe_load((FACTORY_DIR / "config" / "project.yaml").read_text())["recipes"]

RULE_CASES = [case for case in EVAL_SPEC["cases"] if "rule" in case]
assert any(c["expect"] == "plan_rubric_ok" for c in RULE_CASES) and any(c["expect"] == "plan_rubric_reject" for c in RULE_CASES)

ABHISHEK = "abhishek"


def _read(path: Path) -> str:
    return path.read_text() if path.is_file() else ""


def _check_case(case: dict) -> list[plan_rubric.Finding]:
    fixture = EVAL_DIR / case["fixture"]
    return plan_rubric.check(
        _read(fixture / "plan.md"), brief_text=_read(fixture / "brief.md"), criteria_text=_read(fixture / "criteria.md"),
        catalogue=CATALOGUE, project_recipes=PROJECT_RECIPES, questions=[], limits=LIMITS,
        risk_map_candidate_count=0,
    )


# --- the eval-fixture pairs, one per script rule ---


@pytest.mark.parametrize("case", [c for c in RULE_CASES if c["expect"] == "plan_rubric_ok"], ids=[c["name"] for c in RULE_CASES if c["expect"] == "plan_rubric_ok"])
def test_a_conforming_plan_fixture_raises_no_finding_for_its_rule(case):
    findings = _check_case(case)
    assert not any(f.rule == case["rule"] for f in findings), findings


@pytest.mark.parametrize(
    "case", [c for c in RULE_CASES if c["expect"] == "plan_rubric_reject"], ids=[c["name"] for c in RULE_CASES if c["expect"] == "plan_rubric_reject"],
)
def test_a_defective_plan_fixture_raises_its_named_rule(case):
    findings = _check_case(case)
    assert any(f.rule == case["rule"] for f in findings), findings


# --- the new_shared_abstraction/widened_shared_function clauses ---


def test_a_widened_shared_function_row_with_no_reason_fails():
    """R-S3-3: adding a parameter and a conditional to a shared function needs a stated reason inlining was rejected."""
    plan = artefacts.parse(
        "## Abstraction and separate debt\n\n| kind | unit | existing | reason |\n|---|---|---|---|\n"
        "| widened_shared_function | formatMoney |  |  |\n"
    )
    findings = plan_rubric.shared_abstraction_cited(plan)
    assert any(f.rule == "shared_abstraction_cited" for f in findings)


def test_a_new_utility_row_with_no_search_or_no_reason_fails():
    """R-S3-6: a new utility records the existing candidates it found and why each was rejected."""
    plan = artefacts.parse(
        "## Abstraction and separate debt\n\n| kind | unit | existing | reason |\n|---|---|---|---|\n"
        "| new_utility | SlugGenerator |  |  |\n"
    )
    findings = plan_rubric.shared_abstraction_cited(plan)
    assert any(f.rule == "shared_abstraction_cited" for f in findings)


# --- the characterization-test and altered-behaviour clauses, isolated from the classification-carry clause ---


def test_an_unexplained_row_with_no_characterization_task_fails():
    brief = artefacts.parse("## History\n\n| path | classification | evidence |\n|---|---|---|\n| a.java | unexplained | no test covers it |\n")
    plan = artefacts.parse(
        "## Archaeology and characterization tests\n\n| path | classification | characterization_task | alters_captured_behaviour |\n"
        "|---|---|---|---|\n| a.java | unexplained |  | no |\n\n## Tasks\n\n"
        "| id | title | depends_on | criteria | files | validation_recipe | validation_args | expected_result | no_behaviour_change |\n"
        "|---|---|---|---|---|---|---|---|---|\n"
    )
    findings = plan_rubric.archaeology_carried(plan, brief=brief)
    assert any(f.rule == "archaeology_carried" for f in findings)


def test_a_row_altering_captured_behaviour_with_no_matching_unknown_fails():
    brief = artefacts.parse("")
    plan = artefacts.parse(
        "## Archaeology and characterization tests\n\n| path | classification | characterization_task | alters_captured_behaviour |\n"
        "|---|---|---|---|\n| a.java | explained |  | yes |\n\n## Unknowns\n\nnone\n"
    )
    findings = plan_rubric.archaeology_carried(plan, brief=brief)
    assert any(f.rule == "archaeology_carried" for f in findings)


# --- the stacked-task exception is a blind spot, never a fail ---


def test_a_plan_mixing_flagged_and_unflagged_tasks_is_a_blind_spot_not_a_fail():
    plan = artefacts.parse(
        "## Tasks\n\n"
        "| id | title | depends_on | criteria | files | validation_recipe | validation_args | expected_result | no_behaviour_change |\n"
        "|---|---|---|---|---|---|---|---|---|\n"
        "| T-1 | ordinary change |  | AC-1 | a.java | fixture_unit | target=out | passes | no |\n"
        "| T-2 | rename only |  |  | a.java | fixture_lint | target=out | lints clean | yes |\n\n"
        "## Test strategy\n\n| test | action | size | criteria | proves |\n|---|---|---|---|---|\n"
        "| RenameTest | add | small | T-2 | behaviour unchanged after rename |\n"
    )
    findings = plan_rubric.no_behaviour_change_isolated(plan)
    assert findings and all(f.result == "blind_spot" for f in findings)


# --- the consequential-question exception and the unknown-field blind spot ---


def test_a_changed_field_with_no_evidence_passes_when_a_consequential_question_exists():
    plan = artefacts.parse(
        "## Contracts\n\n"
        "| unit | kind | source_declaration | input | output | errors | side_effects | invariants | authorization | "
        "ordering_concurrency | transaction_persistence | compatibility |\n|---|---|---|---|---|---|---|---|---|---|---|---|\n"
        "| Widget.compute | function | unchanged: Widget.java:42 | changed | unchanged | unchanged | unchanged | unchanged | "
        "unchanged | unchanged | unchanged | unchanged |\n"
    )
    findings = plan_rubric.contracts_declared(plan, questions=[{"consequential": True}])
    assert findings == []


def test_an_unknown_contract_field_is_a_blind_spot_not_a_fail():
    plan = artefacts.parse(
        "## Contracts\n\n"
        "| unit | kind | source_declaration | input | output | errors | side_effects | invariants | authorization | "
        "ordering_concurrency | transaction_persistence | compatibility |\n|---|---|---|---|---|---|---|---|---|---|---|---|\n"
        "| Widget.compute | function | unchanged: Widget.java:42 | unknown | unchanged | unchanged | unchanged | unchanged | "
        "unchanged | unchanged | unchanged | unchanged |\n"
    )
    findings = plan_rubric.contracts_declared(plan, questions=[])
    assert findings == [plan_rubric.Finding("contracts_declared", "Widget.compute.input", "blind_spot")]


# --- the size-to-recipe mapping, change-row authorization, and the large-row registration rule ---


def test_the_size_to_recipe_level_mapping_is_fixed():
    """R-S3-9: small/medium/large run under the unit/integration/end_to_end recipe respectively."""
    assert plan_rubric.SIZE_TO_LEVEL == {"small": "unit", "medium": "integration", "large": "end_to_end"}


def test_a_change_row_naming_neither_an_ac_id_nor_a_no_behaviour_change_task_fails():
    plan = artefacts.parse("## Test strategy\n\n| test | action | size | criteria | proves |\n|---|---|---|---|---|\n| T | change | small | AC-99 | x |\n")
    findings = plan_rubric.test_strategy_typed(plan, criteria_text="", catalogue=CATALOGUE, project_recipes=PROJECT_RECIPES)
    assert any(f.rule == "test_strategy_typed" for f in findings)


def test_a_large_row_with_no_registered_end_to_end_recipe_fails():
    plan = artefacts.parse("## Test strategy\n\n| test | action | size | criteria | proves |\n|---|---|---|---|---|\n| T | add | large | AC-1 | x |\n")
    findings = plan_rubric.test_strategy_typed(plan, criteria_text="", catalogue=CATALOGUE, project_recipes=[])
    assert any(f.rule == "test_strategy_typed" for f in findings)


# --- the guardrail-count ceiling and the log-verification pattern requirement ---


def test_guardrail_metrics_over_the_section_8_limit_fail():
    rows = "\n".join(f"| metric_{i} | query_{i} | > {i} |" for i in range(LIMITS["guardrail_metrics"]["max"] + 1))
    plan = artefacts.parse(
        "## Rollout\n\n### Guardrails\n\n| metric | query | critical_threshold |\n|---|---|---|\n" + rows + "\n"
    )
    findings = plan_rubric.rollout_structured(plan, limits=LIMITS)
    assert any(f.rule == "rollout_structured" and "guardrail metrics" in f.detail for f in findings)


def test_a_log_verification_row_missing_a_pattern_fails():
    plan = artefacts.parse(
        "## Rollout\n\n### Log verification\n\n| query | pass_pattern | fail_pattern |\n|---|---|---|\n"
        "| widget logs | validation rejected |  |\n"
    )
    findings = plan_rubric.rollout_structured(plan, limits=LIMITS)
    assert any(f.rule == "rollout_structured" for f in findings)


# --- the rubric file itself: grader lines, checklist marking, and the script-only/contract_unit rows' shape ---


@pytest.mark.parametrize(
    "row,judgment",
    [
        ("R-S3-2", "fail when a rejected alternative's stated reason restates the alternative itself rather than naming a fact about cost, risk, or capability"),
        ("R-S3-3", "fail when a shared-path abstraction cites fewer than three existing near-duplicates and names no pre-abstraction risk"),
        ("R-S3-5", "fail when a task flagged `no_behaviour_change` describes a change that in fact alters behaviour"),
        ("R-S3-6", "fail when a recorded utility search names no context-index entry and no component-catalogue entry checked before proposing the new utility"),
        ("R-S3-9", "fail when a planned test's stated `proves` value names no `AC-n` criterion and no specific assertion the test's action checks"),
        ("R-S3-10", "fail when a rollout section's guardrail metrics carry no critical threshold, or its kill trigger names no rollback as the default response"),
        ("R-S3-11", "fail when a risk-map section reuses boilerplate language with no candidate-specific reasoning"),
    ],
)
def test_the_rubric_marks_each_grader_half_a_bootstrap_checklist_line_with_the_dictated_judgment(row, judgment):
    lines = rubrics.load(RUBRIC_PATH)
    grader = rubrics.line(lines, row, "grader")
    assert grader is not None
    assert grader.checklist is True
    assert grader.judgment == judgment


def test_r_s3_4_carries_a_script_line_only_no_grader_half():
    lines = rubrics.load(RUBRIC_PATH)
    assert rubrics.line(lines, "R-S3-4", "script") is not None
    assert rubrics.line(lines, "R-S3-4", "grader") is None


def test_r_s3_7s_grader_half_names_contract_unit_as_its_subject():
    """R-S3-20: the semantic contract fields of every touched unit are their own checklist instances."""
    lines = rubrics.load(RUBRIC_PATH)
    grader = rubrics.line(lines, "R-S3-7", "grader")
    assert grader is not None
    assert grader.subject == "contract_unit"
    assert grader.checklist is True


def test_the_rubric_carries_a_script_line_for_every_row():
    lines = rubrics.load(RUBRIC_PATH)
    for row in ("R-S3-2", "R-S3-3", "R-S3-4", "R-S3-5", "R-S3-6", "R-S3-7", "R-S3-9", "R-S3-10", "R-S3-11"):
        assert rubrics.line(lines, row, "script") is not None, row


@pytest.mark.parametrize(
    "row",
    ["R-S3-2", "R-S3-3", "R-S3-5", "R-S3-6", "R-S3-9", "R-S3-10"],
)
def test_the_seeded_human_verdict_fixture_names_its_rubric_line_and_a_fail_verdict(row):
    fixture = yaml.safe_load((RUBRIC_FIXTURES_DIR / "human_verdict" / f"{row}.yaml").read_text())
    assert fixture["rubric_line_id"] == f"{row}:grader"
    assert fixture["verdict"] == "fail"


# --- the driver: plan_rubric lands between artefact_structure and size_gate ---


_COMMIT_ENV = {
    "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@example.invalid",
}


def _git(args, cwd, env=None):
    full_env = {**os.environ, **env} if env else None
    return subprocess.run(
        ["git", "-c", "commit.gpgsign=false", *args], cwd=cwd, env=full_env, capture_output=True, text=True, check=True,
    )


def _source_repo(tmp_path):
    repo = tmp_path / "source-repo"
    repo.mkdir()
    _git(["init", "-q"], cwd=repo)
    _git(["checkout", "-q", "-b", "main"], cwd=repo)
    (repo / "README.md").write_text("seed\n")
    _git(["add", "-A"], cwd=repo)
    _git(["commit", "-q", "-m", "init"], cwd=repo, env=_COMMIT_ENV)
    return repo


_S3_BRIEF_TEXT = """## Touched area candidates

| path | reason |
|---|---|
| README.md | the file this ticket's plan touches |

## Linked sources

| source | date |
|---|---|
| JIRA-123 | 2026-01-01 |

## Impact evidence

| direction | dependency | method | source | mapping | owner | coverage | blind_spots |
|---|---|---|---|---|---|---|---|
| outbound | svc-x | import_scan | pom.xml | mapping.yaml | abhishek | authoritative | none |
"""


def _governed_ticket_fields(conn) -> dict:
    proposal = governance.propose()
    for role in ("security_approver", "legal_data_governance_approver"):
        governance.decide(
            conn, proposal, actor_identity=ABHISHEK, role=role, decision="approve",
            expires_at="2999-01-01T00:00:00+00:00", attestation_version="v1", attestation_hash=f"att-{role}",
        )
    activated = governance.activation(conn, proposal)
    return {
        "trust_profile_hash": proposal.profile_hash, "trust_approval_set_hash": activated.trust_approval_set_hash,
        "service": "fixture-project", "source_kind": "jira", "source_ref": "FIX-1",
    }


def test_an_unknown_compatibility_field_on_a_public_unit_re_triggers_pilot_exclusion(tmp_path):
    """design decision: S1's discovered-excluded-scope route reopens at S3 for a public unit's unknown compatibility,
    since the runner cannot itself judge whether the contract genuinely changed."""
    conn = connect(tmp_path / "factory.sqlite")
    source = _source_repo(tmp_path)
    ticket_id = record.insert(
        conn, "ticket", state="intake", opened_at=record.now(), factory_manifest_hash=manifest.current_hash(),
        tier_final="light", **_governed_ticket_fields(conn),
    )
    trees = git_trees.clone_for_ticket(conn, ticket_id, source_checkout=source, target_branch="main", runs_dir=tmp_path)
    git_trees.record_head(conn, ticket_id, trees.worktree)
    record.update(conn, "ticket", ticket_id, state="planning")

    brief_path = tmp_path / "s3_brief.md"
    write_text(brief_path, _S3_BRIEF_TEXT)
    artefact_registry.register(conn, ticket_id=ticket_id, kind="brief", path=brief_path)
    criteria_path = Path(__file__).parent / "fixtures" / "s3" / "criteria.md"
    artefact_registry.register(conn, ticket_id=ticket_id, kind="criteria", path=criteria_path)

    ok_plan = (FACTORY_DIR / "evals" / "agents" / "S3" / "fixtures" / "ok" / "out" / "plan.md").read_text()
    public_unknown_plan = ok_plan.replace(
        "| Widget.compute | function | unchanged: Widget.java:42 | changed: added a negative-input guard | unchanged | "
        "changed: raises a typed error for negative input | unchanged | unchanged | unchanged | unchanged | "
        "unchanged | unchanged |",
        "| Widget.compute | public function | unchanged: Widget.java:42 | changed: added a negative-input guard | "
        "unknown | changed: raises a typed error for negative input | unchanged | unchanged | unchanged | unchanged | "
        "unchanged | unknown |",
    )
    assert public_unknown_plan != ok_plan  # the replacement actually matched the fixture's current contents
    out_dir = tmp_path / "patched_out"
    write_text(out_dir / "plan.md", public_unknown_plan)

    os.environ["FIXTURE_ADAPTER_OUT_DIR"] = str(out_dir)
    try:
        outcome = run_stage(conn, ticket_id, "S3", runs_dir=tmp_path)
    finally:
        os.environ.pop("FIXTURE_ADAPTER_OUT_DIR", None)
    assert outcome == "fail"
    assert record.get(conn, "ticket", ticket_id)["state"] == "rejected"
    assert record.get(conn, "ticket", ticket_id)["close_reason"] == "pilot_excluded"
    conn.close()


def test_plan_rubric_check_result_lands_between_artefact_structure_and_size_gate(tmp_path):
    conn = connect(tmp_path / "factory.sqlite")
    source = _source_repo(tmp_path)
    ticket_id = record.insert(
        conn, "ticket", state="intake", opened_at=record.now(), factory_manifest_hash=manifest.current_hash(),
        tier_final="light", **_governed_ticket_fields(conn),
    )
    trees = git_trees.clone_for_ticket(conn, ticket_id, source_checkout=source, target_branch="main", runs_dir=tmp_path)
    git_trees.record_head(conn, ticket_id, trees.worktree)
    record.update(conn, "ticket", ticket_id, state="planning")

    brief_path = tmp_path / "s3_brief.md"
    write_text(brief_path, _S3_BRIEF_TEXT)
    artefact_registry.register(conn, ticket_id=ticket_id, kind="brief", path=brief_path)
    criteria_path = Path(__file__).parent / "fixtures" / "s3" / "criteria.md"
    artefact_registry.register(conn, ticket_id=ticket_id, kind="criteria", path=criteria_path)

    os.environ["FIXTURE_ADAPTER_OUT_DIR"] = str(FACTORY_DIR / "evals" / "agents" / "S3" / "fixtures" / "ok" / "out")
    try:
        outcome = run_stage(conn, ticket_id, "S3", runs_dir=tmp_path)
    finally:
        os.environ.pop("FIXTURE_ADAPTER_OUT_DIR", None)
    assert outcome == "pass"

    stage_run = conn.execute(
        "SELECT id FROM stage_run WHERE ticket_id = ? AND stage = 'S3' AND parent_run_id IS NULL ORDER BY id DESC LIMIT 1",
        (ticket_id,),
    ).fetchone()
    checks = conn.execute(
        "SELECT check_name, result FROM check_result WHERE stage_run_id = ? ORDER BY id", (stage_run["id"],),
    ).fetchall()
    names = [row["check_name"] for row in checks]
    assert names.index("artefact_structure") < names.index("plan_rubric") < names.index("size_gate")
    plan_rubric_row = next(row for row in checks if row["check_name"] == "plan_rubric")
    assert plan_rubric_row["result"] in ("pass", "blind_spot")
    conn.close()
