"""The context_gathering-implementation agent and skill files, the shared codegraph-lookup skill, and their eval directories.

Line counts read `tiers.yaml`'s `length_limits.instruction_file_lines`
rather than the literal number, so a future config change stays the one
place that number lives.
"""
import shutil
from pathlib import Path

import pytest
import yaml

from runner import manifest
from runner.evals import EvalDirectoryError, check as _check_eval_dir
from runner.paths import FACTORY_DIR

TIERS_PATH = FACTORY_DIR / "config" / "tiers.yaml"

STAGE_NAMES = ("context_gathering", "clarification", "planning", "implementation")

AGENT_FILES = tuple((FACTORY_DIR / "agents" / f"{name}.md") for name in STAGE_NAMES)
SKILL_FILES = tuple((FACTORY_DIR / "skills" / f"{name}.md") for name in STAGE_NAMES)
SHARED_SKILL = FACTORY_DIR / "skills" / "shared" / "codegraph-lookup.md"

EVAL_DIRS = (
    *((FACTORY_DIR / "evals" / "agents" / name) for name in STAGE_NAMES),
    *((FACTORY_DIR / "evals" / "skills" / name) for name in STAGE_NAMES),
    FACTORY_DIR / "evals" / "skills" / "shared" / "codegraph-lookup",
)


def _instruction_file_line_limit() -> int:
    return int(yaml.safe_load(TIERS_PATH.read_text())["length_limits"]["instruction_file_lines"])


# the instruction-file line limit


@pytest.mark.parametrize("path", [*AGENT_FILES, *SKILL_FILES], ids=[str(p.relative_to(FACTORY_DIR)) for p in [*AGENT_FILES, *SKILL_FILES]])
def test_each_stage_agent_and_skill_file_is_under_the_instruction_file_line_limit(path):
    """Every stage's agent file (`factory/agents/context_gathering.md` .. `implementation.md`) and
    skill file (`factory/skills/context_gathering.md` .. `implementation.md`) stays under the
    instruction-file line limit."""
    line_count = len(path.read_text().splitlines())
    assert line_count < _instruction_file_line_limit()


def test_the_shared_skill_file_is_under_the_same_instruction_file_line_limit():
    """`factory/skills/shared/codegraph-lookup.md` is under the same cap."""
    line_count = len(SHARED_SKILL.read_text().splitlines())
    assert line_count < _instruction_file_line_limit()


# the shared skill attaches only through the manifest


def test_the_shared_skill_is_named_in_the_manifest_entries_for_context_gathering_planning_and_implementation():
    """The shared skill is attached to context_gathering, planning, and implementation only through each stage's manifest entry."""
    m = manifest.load()
    shared_skill_path = "factory/skills/shared/codegraph-lookup.md"
    for stage in ("context_gathering", "planning", "implementation"):
        assert shared_skill_path in m.stages[stage]["default"]["shared_skills"]


def test_must_reject_the_shared_skill_being_implied_for_clarification():
    """Clarification's manifest entry never carries the shared skill -- attachment is per stage,
    never inferred from the file's directory placement alone."""
    m = manifest.load()
    assert "factory/skills/shared/codegraph-lookup.md" not in m.stages["clarification"]["default"]["shared_skills"]


# every stub's eval directory is owned and has a real fixture


@pytest.mark.parametrize("eval_dir", EVAL_DIRS, ids=[str(d.relative_to(FACTORY_DIR)) for d in EVAL_DIRS])
def test_each_of_the_nine_eval_directories_is_owned_and_has_a_non_empty_fixture(eval_dir):
    _check_eval_dir(eval_dir)  # raises EvalDirectoryError on failure; no exception is the assertion


def test_must_reject_an_eval_directory_with_no_owner(tmp_path):
    broken = tmp_path / "context_gathering"
    shutil.copytree(FACTORY_DIR / "evals" / "agents" / "context_gathering", broken)
    spec = yaml.safe_load((broken / "eval.yaml").read_text())
    del spec["owner"]
    (broken / "eval.yaml").write_text(yaml.safe_dump(spec))

    with pytest.raises(EvalDirectoryError):
        _check_eval_dir(broken)


def test_must_reject_an_eval_directory_whose_every_case_fixture_is_empty(tmp_path):
    broken = tmp_path / "context_gathering"
    shutil.copytree(FACTORY_DIR / "evals" / "agents" / "context_gathering", broken)
    spec = yaml.safe_load((broken / "eval.yaml").read_text())
    for case in spec["cases"]:
        fixture_dir = broken / case["fixture"]
        for child in fixture_dir.iterdir():
            child.unlink()

    with pytest.raises(EvalDirectoryError):
        _check_eval_dir(broken)


# no stray file under factory/agents/ or factory/skills/


def test_no_stray_file_exists_under_factory_agents_or_factory_skills():
    """No path-scoped agent or skill file exists -- only the stage files and the one shared skill."""
    agent_files = sorted(p for p in (FACTORY_DIR / "agents").rglob("*") if p.is_file())
    skill_files = sorted(p for p in (FACTORY_DIR / "skills").rglob("*") if p.is_file())

    assert agent_files == sorted(AGENT_FILES)
    assert skill_files == sorted([*SKILL_FILES, SHARED_SKILL])
