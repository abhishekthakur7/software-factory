"""The S1-S4 agent and skill files, the shared codegraph-lookup skill, and their eval directories.

Line counts read `tiers.yaml`'s `length_limits.instruction_file_lines`
rather than the literal number, so a future config change stays the one
place that number lives.
"""
import shutil
from pathlib import Path

import pytest
import yaml

from runner import manifest
from runner.paths import FACTORY_DIR

TIERS_PATH = FACTORY_DIR / "config" / "tiers.yaml"

AGENT_FILES = tuple((FACTORY_DIR / "agents" / f"S{n}.md") for n in range(1, 5))
SKILL_FILES = tuple((FACTORY_DIR / "skills" / f"S{n}.md") for n in range(1, 5))
SHARED_SKILL = FACTORY_DIR / "skills" / "shared" / "codegraph-lookup.md"

EVAL_DIRS = (
    *((FACTORY_DIR / "evals" / "agents" / f"S{n}") for n in range(1, 5)),
    *((FACTORY_DIR / "evals" / "skills" / f"S{n}") for n in range(1, 5)),
    FACTORY_DIR / "evals" / "skills" / "shared" / "codegraph-lookup",
)


def _instruction_file_line_limit() -> int:
    return int(yaml.safe_load(TIERS_PATH.read_text())["length_limits"]["instruction_file_lines"])


class EvalDirectoryError(ValueError):
    """An eval directory carries no owner, or none of its cases names a fixture directory
    that exists and is non-empty."""


def _check_eval_dir(eval_dir: Path) -> None:
    spec = yaml.safe_load((eval_dir / "eval.yaml").read_text())
    owner = spec.get("owner")
    if not owner or not str(owner).strip():
        raise EvalDirectoryError(f"{eval_dir}: eval.yaml carries no owner")
    for case in spec["cases"]:
        fixture_dir = eval_dir / case["fixture"]
        if fixture_dir.is_dir() and any(fixture_dir.rglob("*")):
            return
    raise EvalDirectoryError(f"{eval_dir}: no case names a fixture directory that exists and is non-empty")


# the section 8 line limit


@pytest.mark.parametrize("path", [*AGENT_FILES, *SKILL_FILES], ids=[str(p.relative_to(FACTORY_DIR)) for p in [*AGENT_FILES, *SKILL_FILES]])
def test_each_stage_agent_and_skill_file_is_under_the_instruction_file_line_limit(path):
    """R-F-7: `factory/agents/S1.md` .. `S4.md` and `factory/skills/S1.md` .. `S4.md`
    are each under the section 8 instruction-file limit."""
    line_count = len(path.read_text().splitlines())
    assert line_count < _instruction_file_line_limit()


def test_the_shared_skill_file_is_under_the_same_instruction_file_line_limit():
    """R-F-7: `factory/skills/shared/codegraph-lookup.md` is under the same cap."""
    line_count = len(SHARED_SKILL.read_text().splitlines())
    assert line_count < _instruction_file_line_limit()


# the shared skill attaches only through the manifest


def test_the_shared_skill_is_named_in_the_manifest_entries_for_s1_s3_and_s4():
    """R-F-7: attached to S1, S3, and S4 only through each stage's manifest entry."""
    m = manifest.load()
    shared_skill_path = "factory/skills/shared/codegraph-lookup.md"
    for stage in ("S1", "S3", "S4"):
        assert shared_skill_path in m.stages[stage]["default"]["shared_skills"]


def test_must_reject_the_shared_skill_being_implied_for_s2():
    """R-F-7: S2's manifest entry never carries the shared skill -- attachment is per stage,
    never inferred from the file's directory placement alone."""
    m = manifest.load()
    assert "factory/skills/shared/codegraph-lookup.md" not in m.stages["S2"]["default"]["shared_skills"]


# every stub's eval directory is owned and has a real fixture


@pytest.mark.parametrize("eval_dir", EVAL_DIRS, ids=[str(d.relative_to(FACTORY_DIR)) for d in EVAL_DIRS])
def test_each_of_the_nine_eval_directories_is_owned_and_has_a_non_empty_fixture(eval_dir):
    _check_eval_dir(eval_dir)  # raises EvalDirectoryError on failure; no exception is the assertion


def test_must_reject_an_eval_directory_with_no_owner(tmp_path):
    broken = tmp_path / "S1"
    shutil.copytree(FACTORY_DIR / "evals" / "agents" / "S1", broken)
    spec = yaml.safe_load((broken / "eval.yaml").read_text())
    del spec["owner"]
    (broken / "eval.yaml").write_text(yaml.safe_dump(spec))

    with pytest.raises(EvalDirectoryError):
        _check_eval_dir(broken)


def test_must_reject_an_eval_directory_whose_every_case_fixture_is_empty(tmp_path):
    broken = tmp_path / "S1"
    shutil.copytree(FACTORY_DIR / "evals" / "agents" / "S1", broken)
    spec = yaml.safe_load((broken / "eval.yaml").read_text())
    for case in spec["cases"]:
        fixture_dir = broken / case["fixture"]
        for child in fixture_dir.iterdir():
            child.unlink()

    with pytest.raises(EvalDirectoryError):
        _check_eval_dir(broken)


# no stray file under factory/agents/ or factory/skills/


def test_no_stray_file_exists_under_factory_agents_or_factory_skills():
    """R-F-7: no path-scoped agent or skill file exists at this stage -- only the eight
    stage files and the one shared skill."""
    agent_files = sorted(p for p in (FACTORY_DIR / "agents").rglob("*") if p.is_file())
    skill_files = sorted(p for p in (FACTORY_DIR / "skills").rglob("*") if p.is_file())

    assert agent_files == sorted(AGENT_FILES)
    assert skill_files == sorted([*SKILL_FILES, SHARED_SKILL])
