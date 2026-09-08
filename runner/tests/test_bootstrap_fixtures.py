"""The bootstrap fixture set `tools/bootstrap_fixtures.py` builds under `factory/evals/bootstrap/`
(R-F-2: every ticket's build-time brief and plan copied into the eval directories its build
exercised).

The committed tree is the thing under test, not the tool's internals: a
stale plan edited after its own sync run, or a hand-typed mapping entry
that has since gone stale, would fail these tests exactly as a missing
fixture would.
"""
import sys

import pytest
import yaml

from runner import evals
from runner.paths import FACTORY_DIR, REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "tools"))
import bootstrap_fixtures  # noqa: E402

BUILD_DIR = REPO_ROOT / "docs" / "build"
BOOTSTRAP_DIR = FACTORY_DIR / "evals" / "bootstrap"
EVAL_YAML = yaml.safe_load((BOOTSTRAP_DIR / "eval.yaml").read_text())

_TICKET_DIRS = sorted(
    p.name for p in BUILD_DIR.iterdir()
    if p.is_dir() and (p / "brief.md").is_file() and (p / "plan.md").is_file()
)


def test_every_docs_build_ticket_has_a_bootstrap_copy():
    assert _TICKET_DIRS  # the walking skeleton has written at least one ticket pair by now
    assert set(_TICKET_DIRS) == set(EVAL_YAML["tickets"])


@pytest.mark.parametrize("ticket_id", _TICKET_DIRS)
@pytest.mark.parametrize("filename", ["brief.md", "plan.md"])
def test_the_bootstrap_copy_is_byte_identical_to_its_docs_build_source(ticket_id, filename):
    source = (BUILD_DIR / ticket_id / filename).read_bytes()
    copy = (BOOTSTRAP_DIR / ticket_id / filename).read_bytes()
    assert copy == source


def test_every_mapped_eval_directory_in_the_committed_mapping_exists():
    for ticket_id, rels in EVAL_YAML["tickets"].items():
        for rel in rels:
            assert (FACTORY_DIR / "evals" / rel).is_dir(), f"{ticket_id} names missing eval directory {rel!r}"


def test_the_bootstrap_eval_yaml_carries_an_owner_and_the_docs_build_subject():
    assert EVAL_YAML["owner"]
    assert EVAL_YAML["subject"] == "docs/build"


def test_fixture_project_sits_outside_the_expected_eval_dir_walk():
    """R-F-2: `factory/evals/fixture-project/` is a seed project, not an evaluable subject."""
    assert (FACTORY_DIR / "evals" / "fixture-project") not in evals.expected_eval_dirs()


def test_bootstrap_itself_sits_outside_the_expected_eval_dir_walk():
    assert BOOTSTRAP_DIR not in evals.expected_eval_dirs()


def test_running_the_sync_again_over_the_real_repository_changes_nothing():
    """The committed bootstrap tree already is what a fresh sync run would produce."""
    changes = bootstrap_fixtures.sync(REPO_ROOT)
    assert changes == []


def test_eval_dirs_exercised_keeps_only_paths_that_resolve_to_a_real_eval_directory():
    valid = {"rubrics/S3", "scripts/checks/size_gate"}
    plan_text = (
        "| 1 | Update the rubric | `factory/rubrics/S3.md` | test |\n"
        "| 2 | Add the check | `factory/scripts/checks/size_gate` | test |\n"
        "| 3 | Bump config | `factory/config/tiers.yaml` | test |\n"
        "| 4 | Shorthand range | `factory/evals/agents/S1..S4/eval.yaml` | test |\n"
    )
    assert bootstrap_fixtures.eval_dirs_exercised(plan_text, valid) == ["rubrics/S3", "scripts/checks/size_gate"]


def test_eval_dirs_exercised_reads_a_path_already_under_an_eval_directory():
    valid = {"scripts/checks/scope_diff"}
    plan_text = "Eval fixtures: `factory/evals/scripts/checks/scope_diff/fixtures/over_threshold`"
    assert bootstrap_fixtures.eval_dirs_exercised(plan_text, valid) == ["scripts/checks/scope_diff"]


def test_eval_dirs_exercised_excludes_a_checklist_path_from_the_rubric_mapping():
    """`factory/rubrics/checklists/*.md` is never referenced as a rubric of its own (R-F-7)."""
    valid = {"rubrics/checklists"}  # would only match if the exclusion were missing
    plan_text = "`factory/rubrics/checklists/forced-categories.md`"
    assert bootstrap_fixtures.eval_dirs_exercised(plan_text, valid) == []
