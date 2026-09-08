"""The eval-directory completeness walk (R-F-2), and the manifest's own refusal of an empty
fixture list over the real project tree.

`_build_synthetic_factory` lays out one directory per kind
`expected_eval_dirs` derives (agent, skill, shared skill, adapter, one
`scripts/checks` executable, one `scripts/tools` executable, rubric) so
each rejection case can mutate exactly one eval directory without ever
touching the real, committed `factory/` tree.
"""
import shutil

import pytest
import yaml

from runner import manifest
from runner.evals import EvalDirectoryError, check, eval_dir_for_adapter, eval_dir_for_file, expected_eval_dirs, walk
from runner.paths import FACTORY_DIR, REPO_ROOT

_OWNER = "someone"


def _write_eval_dir(eval_dir, *, owner=_OWNER, cases=None, fixture_name="ok", fixture_is_file=False):
    eval_dir.mkdir(parents=True, exist_ok=True)
    if fixture_is_file:
        (eval_dir / f"{fixture_name}.json").write_text('{"ok": true}\n')
        default_cases = [{"name": fixture_name, "fixture": f"{fixture_name}.json"}]
    else:
        fixture_dir = eval_dir / "fixtures" / fixture_name
        fixture_dir.mkdir(parents=True, exist_ok=True)
        (fixture_dir / "seed.txt").write_text("seed\n")
        default_cases = [{"name": fixture_name, "fixture": f"fixtures/{fixture_name}"}]
    spec = {"subject": "synthetic", "cases": cases if cases is not None else default_cases}
    if owner is not None:
        spec["owner"] = owner
    (eval_dir / "eval.yaml").write_text(yaml.safe_dump(spec))


def _build_synthetic_factory(tmp_path):
    """A minimal `factory/` tree with exactly one agent, skill, shared skill, adapter,
    `scripts/checks` and `scripts/tools` executable, and rubric -- each fully evaluable."""
    root = tmp_path / "factory"
    (root / "agents").mkdir(parents=True)
    (root / "agents" / "A1.md").write_text("# agent\n")
    (root / "skills").mkdir(parents=True)
    (root / "skills" / "S1.md").write_text("# skill\n")
    (root / "skills" / "shared").mkdir(parents=True)
    (root / "skills" / "shared" / "Shared1.md").write_text("# shared skill\n")
    (root / "rubrics").mkdir(parents=True)
    (root / "rubrics" / "R1.md").write_text("# rubric\n")
    (root / "scripts" / "checks").mkdir(parents=True)
    (root / "scripts" / "checks" / "check1").write_text("#!/usr/bin/env python3\n")
    (root / "scripts" / "tools").mkdir(parents=True)
    (root / "scripts" / "tools" / "tool1").write_text("#!/usr/bin/env python3\n")
    (root / "config").mkdir(parents=True)
    (root / "config" / "runtime.yaml").write_text(yaml.safe_dump({"adapters": {"adap1": {"package": "x"}}}))

    evals_root = root / "evals"
    _write_eval_dir(evals_root / "agents" / "A1")
    _write_eval_dir(evals_root / "skills" / "S1")
    _write_eval_dir(evals_root / "skills" / "shared" / "Shared1")
    _write_eval_dir(evals_root / "rubrics" / "R1")
    _write_eval_dir(evals_root / "scripts" / "checks" / "check1")
    _write_eval_dir(evals_root / "scripts" / "tools" / "tool1")
    _write_eval_dir(evals_root / "adapters" / "adap1", fixture_is_file=True)
    return root


# ---- the real tree, and a matching synthetic tree, both pass ----


def test_the_real_factory_tree_passes_the_completeness_walk():
    """R-F-2: every eval directory `expected_eval_dirs` derives from the committed `factory/`
    tree is owned and carries a real, non-empty fixture."""
    dirs = walk(FACTORY_DIR)
    assert dirs  # the walk actually covers something, not a vacuous empty list


def test_a_fully_built_synthetic_tree_passes(tmp_path):
    """A tree with one owned, fixtured eval directory per kind passes with no mutation."""
    root = _build_synthetic_factory(tmp_path)
    dirs = walk(root)
    assert len(dirs) == 7


# ---- expected_eval_dirs derivation ----


def test_expected_eval_dirs_names_one_directory_per_kind(tmp_path):
    root = _build_synthetic_factory(tmp_path)
    rels = {str(p.relative_to(root / "evals")) for p in expected_eval_dirs(root)}
    assert rels == {
        "agents/A1", "skills/S1", "skills/shared/Shared1", "adapters/adap1",
        "scripts/checks/check1", "scripts/tools/tool1", "rubrics/R1",
    }


def test_expected_eval_dirs_excludes_fixture_project_and_bootstrap(tmp_path):
    """`fixture-project/` and `bootstrap/` are seed/aggregation directories, not derived
    from any agent, skill, adapter, script, or rubric file, so neither is ever expected."""
    root = _build_synthetic_factory(tmp_path)
    (root / "evals" / "fixture-project").mkdir(parents=True)
    (root / "evals" / "bootstrap").mkdir(parents=True)
    dirs = expected_eval_dirs(root)
    assert (root / "evals" / "fixture-project") not in dirs
    assert (root / "evals" / "bootstrap") not in dirs


def test_a_shared_module_with_a_suffix_names_no_eval_directory_of_its_own(tmp_path):
    """A `.py` file beside an executable script is a shared, imported module, not a script
    meant to be run directly -- it gets no eval directory."""
    root = _build_synthetic_factory(tmp_path)
    (root / "scripts" / "tools" / "shared_helper.py").write_text("# shared\n")
    dirs = expected_eval_dirs(root)
    assert (root / "evals" / "scripts" / "tools" / "shared_helper.py") not in dirs
    assert (root / "evals" / "scripts" / "tools" / "shared_helper") not in dirs


# ---- must-reject: each rejection mutates exactly one eval directory ----


def test_must_reject_a_missing_eval_directory(tmp_path):
    root = _build_synthetic_factory(tmp_path)
    shutil.rmtree(root / "evals" / "rubrics" / "R1")
    with pytest.raises(EvalDirectoryError, match="directory absent"):
        walk(root)


def test_must_reject_an_eval_directory_with_an_empty_case_list(tmp_path):
    root = _build_synthetic_factory(tmp_path)
    eval_yaml = root / "evals" / "rubrics" / "R1" / "eval.yaml"
    eval_yaml.write_text(yaml.safe_dump({"subject": "synthetic", "owner": _OWNER, "cases": []}))
    with pytest.raises(EvalDirectoryError, match="empty case list"):
        walk(root)


def test_must_reject_an_eval_directory_with_no_owner(tmp_path):
    root = _build_synthetic_factory(tmp_path)
    eval_yaml = root / "evals" / "rubrics" / "R1" / "eval.yaml"
    spec = yaml.safe_load(eval_yaml.read_text())
    del spec["owner"]
    eval_yaml.write_text(yaml.safe_dump(spec))
    with pytest.raises(EvalDirectoryError, match="no owner"):
        walk(root)


def test_must_reject_an_unredacted_real_ticket_export_case(tmp_path):
    root = _build_synthetic_factory(tmp_path)
    eval_dir = root / "evals" / "rubrics" / "R1"
    (eval_dir / "fixtures" / "exported").mkdir(parents=True)
    (eval_dir / "fixtures" / "exported" / "raw.txt").write_text("unredacted ticket text\n")
    spec = yaml.safe_load((eval_dir / "eval.yaml").read_text())
    spec["cases"].append({"name": "exported", "fixture": "fixtures/exported", "source": "real_ticket_export"})
    (eval_dir / "eval.yaml").write_text(yaml.safe_dump(spec))
    with pytest.raises(EvalDirectoryError, match="redaction review"):
        walk(root)


def test_a_real_ticket_export_case_with_a_recorded_redaction_review_is_accepted(tmp_path):
    root = _build_synthetic_factory(tmp_path)
    eval_dir = root / "evals" / "rubrics" / "R1"
    (eval_dir / "fixtures" / "exported").mkdir(parents=True)
    (eval_dir / "fixtures" / "exported" / "raw.txt").write_text("redacted ticket text\n")
    spec = yaml.safe_load((eval_dir / "eval.yaml").read_text())
    spec["cases"].append({
        "name": "exported",
        "fixture": "fixtures/exported",
        "source": "real_ticket_export",
        "redaction_review": {"reviewer": "abhishek", "date": "2026-01-01", "note": "names and paths stripped"},
    })
    (eval_dir / "eval.yaml").write_text(yaml.safe_dump(spec))
    check(eval_dir)  # raises on failure; no exception is the assertion


# ---- the manifest itself refuses an empty case list for a referenced stage rubric ----

_VALID_MANIFEST_FIXTURE = REPO_ROOT / "runner" / "tests" / "fixtures" / "manifest" / "valid" / "factory"


def _build_manifest_tree(tmp_path):
    """The existing minimal 7-stage manifest fixture, plus a matching `evals/` tree for the
    one agent, skill, and rubric it references (and the `cursor_sdk` adapter every stage names)."""
    root = tmp_path / "factory"
    shutil.copytree(_VALID_MANIFEST_FIXTURE, root)
    evals_root = root / "evals"
    _write_eval_dir(evals_root / "agents" / "agent")
    _write_eval_dir(evals_root / "skills" / "skill")
    _write_eval_dir(evals_root / "rubrics" / "rubric")
    _write_eval_dir(evals_root / "adapters" / "cursor_sdk", fixture_is_file=True)
    return tmp_path


def test_manifest_load_passes_over_a_fully_evaluable_synthetic_tree(tmp_path, monkeypatch):
    root = _build_manifest_tree(tmp_path)
    monkeypatch.setattr(manifest, "REPO_ROOT", root)
    m = manifest.load(root / "factory" / "manifest.yaml")
    assert set(m.stages) == set(manifest.STAGES)


def test_manifest_refuses_a_referenced_stage_rubric_with_an_empty_case_list(tmp_path, monkeypatch):
    """R-F-2: an empty fixture list on an eval directory a stage entry actually references
    is refused by `manifest.load` itself, not only by the standalone completeness walk."""
    root = _build_manifest_tree(tmp_path)
    monkeypatch.setattr(manifest, "REPO_ROOT", root)
    rubric_eval_yaml = root / "factory" / "evals" / "rubrics" / "rubric" / "eval.yaml"
    rubric_eval_yaml.write_text(yaml.safe_dump({"subject": "synthetic", "owner": _OWNER, "cases": []}))

    with pytest.raises(manifest.ManifestError, match="empty case list"):
        manifest.load(root / "factory" / "manifest.yaml")


def test_manifest_load_over_a_fixture_root_skips_the_eval_dir_check(tmp_path):
    """Loading a synthetic manifest from outside the real project's own `factory/` root never
    fails over a missing eval directory -- its stand-in files have none, by design."""
    root = _build_manifest_tree(tmp_path)
    shutil.rmtree(root / "factory" / "evals")  # every eval directory this manifest references is now gone

    m = manifest.load(root / "factory" / "manifest.yaml")  # REPO_ROOT is untouched, so the guard skips
    assert set(m.stages) == set(manifest.STAGES)


# ---- the helpers manifest.py calls to locate a referenced eval directory ----


def test_eval_dir_for_file_maps_agent_skill_and_rubric_paths():
    assert eval_dir_for_file("factory/agents/S1.md", root=FACTORY_DIR) == FACTORY_DIR / "evals" / "agents" / "S1"
    assert eval_dir_for_file("factory/rubrics/S3.md", root=FACTORY_DIR) == FACTORY_DIR / "evals" / "rubrics" / "S3"


def test_eval_dir_for_file_maps_a_shared_skill_path_under_its_own_shared_directory():
    result = eval_dir_for_file("factory/skills/shared/codegraph-lookup.md", root=FACTORY_DIR)
    assert result == FACTORY_DIR / "evals" / "skills" / "shared" / "codegraph-lookup"


def test_eval_dir_for_adapter_maps_the_adapter_name_directly():
    assert eval_dir_for_adapter("cursor_sdk", root=FACTORY_DIR) == FACTORY_DIR / "evals" / "adapters" / "cursor_sdk"
