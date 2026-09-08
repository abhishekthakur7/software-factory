"""The fence: the fence lives in runner/, not factory/."""
import yaml

from runner import anti_goals, state_table
from runner.paths import FACTORY_DIR, REPO_ROOT


def test_state_table_lives_outside_factory_with_plausible_states():
    """the state table is runner code outside factory/."""
    module_path = REPO_ROOT / "runner" / "state_table.py"
    assert module_path.is_file()
    assert FACTORY_DIR not in module_path.parents
    assert "intake" in state_table.STATES
    assert "merged" in state_table.STATES
    assert len(state_table.STATES) == 14
    # Every state named as a transition target must itself be a real state,
    # otherwise the table could route a ticket into a state that doesn't exist.
    assert set(state_table.TRANSITIONS) == set(state_table.STATES)
    for sources in state_table.TRANSITIONS.values():
        assert sources <= set(state_table.STATES)


def test_anti_goals_lives_outside_factory_with_eleven_entries():
    """the anti-goals are runner code outside factory/."""
    module_path = REPO_ROOT / "runner" / "anti_goals.py"
    assert module_path.is_file()
    assert FACTORY_DIR not in module_path.parents
    assert len(anti_goals.ANTI_GOALS) == 11
    slugs = [slug for slug, _ in anti_goals.ANTI_GOALS]
    assert len(slugs) == len(set(slugs))  # each anti-goal is distinct


def test_must_reject_manifest_naming_the_fence_modules():
    """the manifest never references the fence,
    so no proposal path can reach it through a governed change."""
    manifest = yaml.safe_load((FACTORY_DIR / "manifest.yaml").read_text())
    paths = {entry["path"] for entry in manifest["files"]}
    assert "runner/state_table.py" not in paths
    assert "runner/anti_goals.py" not in paths
