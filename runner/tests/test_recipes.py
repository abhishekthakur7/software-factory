"""The typed recipe catalogue: schema validation and every before-dispatch
refusal a command recipe requires -- injection, redirection, an undeclared
executable, a cwd escape, an environment leak, a timeout, and an unexpected
result.

Fixture catalogues under `fixtures/command-recipes/catalogues/` are tiny,
one recipe each; where a fixture needs a genuinely matching executable
digest, its yaml carries a `{{DIGEST}}` placeholder that `_load` fills in
with the sha256 this test computes from the real fixture script's bytes, so
a wrong implementation that skips the digest check, or one that hashes the
declared value instead of the file, cannot pass by coincidence.
"""
import hashlib
import time

import pytest

from runner import recipes
from runner.paths import REPO_ROOT

FIXTURES_DIR = REPO_ROOT / "runner" / "tests" / "fixtures" / "command-recipes"
CATALOGUES_DIR = FIXTURES_DIR / "catalogues"
SCRIPTS_DIR = FIXTURES_DIR / "scripts"


def _digest(script_name: str) -> str:
    return hashlib.sha256((SCRIPTS_DIR / script_name).read_bytes()).hexdigest()


def _load(fixture_name: str, tmp_path, script_name: str | None = None):
    text = (CATALOGUES_DIR / fixture_name).read_text()
    if script_name is not None:
        text = text.replace("{{DIGEST}}", _digest(script_name))
    catalogue_path = tmp_path / fixture_name
    catalogue_path.write_text(text)
    return recipes.load_catalogue(catalogue_path)


@pytest.fixture
def scratch(tmp_path):
    root = tmp_path / "scratch"
    root.mkdir()
    return root


# ---- schema validation ----


def test_recipe_missing_a_required_field_fails_validation(tmp_path):
    """a recipe entry missing timeout_seconds is refused, naming the field."""
    with pytest.raises(recipes.RecipeError, match="timeout_seconds"):
        _load("missing_field.yaml", tmp_path)


def test_every_field_of_the_schema_validates_on_the_real_fixture_recipes():
    """the committed command-recipes.yaml -- what the fixture project's own
    recipes are dispatched from -- validates against the full schema,
    including the test-recipe-only level and test_globs fields."""
    catalogue = recipes.load_catalogue()
    assert set(catalogue) == {
        "fixture_lint", "fixture_compile", "fixture_unit", "fixture_integration", "fixture_e2e",
    }
    unit = catalogue["fixture_unit"]
    assert unit.level == "unit"
    assert unit.test_globs == ("src/test/java/**/*UnitTest.java",)
    assert catalogue["fixture_lint"].level is None


# ---- injection and redirection ----


def test_must_reject_literal_arg_with_command_substitution_syntax(tmp_path):
    with pytest.raises(recipes.RecipeError, match="forbidden"):
        _load("injection.yaml", tmp_path)


def test_must_reject_literal_arg_with_redirection_operator(tmp_path):
    with pytest.raises(recipes.RecipeError, match="forbidden"):
        _load("redirection.yaml", tmp_path)


# ---- executable digest ----


def test_must_reject_executable_digest_mismatch(tmp_path, scratch):
    catalogue = _load("wrong_digest.yaml", tmp_path)
    with pytest.raises(recipes.RecipeError, match="digest mismatch"):
        recipes.run(
            "wrong_digest_test", {}, catalogue=catalogue,
            cwd_roles={"scratch": scratch}, results_dir=tmp_path / "results", env_source={},
        )


# ---- cwd escape ----


def test_path_placeholder_resolving_inside_cwd_role_is_accepted(tmp_path, scratch):
    catalogue = _load("cwd_escape.yaml", tmp_path, script_name="ok.py")
    result = recipes.run(
        "cwd_escape_test", {"target": "inside.txt"}, catalogue=catalogue,
        cwd_roles={"scratch": scratch}, results_dir=tmp_path / "results", env_source={},
    )
    assert result.outcome == "pass"


def test_must_reject_path_placeholder_resolving_outside_cwd_role(tmp_path, scratch):
    catalogue = _load("cwd_escape.yaml", tmp_path, script_name="ok.py")
    with pytest.raises(recipes.RecipeError, match="outside its cwd_role"):
        recipes.run(
            "cwd_escape_test", {"target": "../../etc/passwd"}, catalogue=catalogue,
            cwd_roles={"scratch": scratch}, results_dir=tmp_path / "results", env_source={},
        )


# ---- environment leak ----


def test_requested_env_var_within_allowlist_is_taken_from_env_source(tmp_path, scratch, monkeypatch):
    """the value the child sees comes from env_source, not from os.environ,
    even when os.environ happens to hold a different value for the same name."""
    monkeypatch.setenv("SAFE_VAR", "from-os-environ")
    catalogue = _load("env_leak.yaml", tmp_path, script_name="print_env.py")
    result = recipes.run(
        "env_leak_test", {}, catalogue=catalogue, cwd_roles={"scratch": scratch},
        results_dir=tmp_path / "results", env_source={"SAFE_VAR": "from-env-source"},
        env_request=("SAFE_VAR",),
    )
    assert result.outcome == "pass"
    assert result.stdout_path.read_text().strip() == "from-env-source"


def test_must_reject_env_var_outside_allowlist(tmp_path, scratch):
    catalogue = _load("env_leak.yaml", tmp_path, script_name="print_env.py")
    with pytest.raises(recipes.RecipeError, match="outside its allowlist"):
        recipes.run(
            "env_leak_test", {}, catalogue=catalogue, cwd_roles={"scratch": scratch},
            results_dir=tmp_path / "results", env_source={"SECRET_VAR": "leak"},
            env_request=("SECRET_VAR",),
        )


# ---- timeout ----


def test_run_past_timeout_is_terminated_and_recorded_as_timeout(tmp_path, scratch):
    catalogue = _load("timeout.yaml", tmp_path, script_name="sleepy.py")
    started = time.monotonic()
    result = recipes.run(
        "timeout_test", {}, catalogue=catalogue, cwd_roles={"scratch": scratch},
        results_dir=tmp_path / "results", env_source={},
    )
    elapsed = time.monotonic() - started
    assert result.outcome == "timeout"
    assert result.exit_code is None
    assert elapsed < 4, "sleepy.py sleeps 5s; a 1s timeout must have actually killed it"


# ---- expected result ----


def test_unexpected_exit_code_is_recorded_as_a_failed_result(tmp_path, scratch):
    catalogue = _load("expected_result.yaml", tmp_path, script_name="exit_three.py")
    result = recipes.run(
        "expected_result_test", {}, catalogue=catalogue, cwd_roles={"scratch": scratch},
        results_dir=tmp_path / "results", env_source={},
    )
    assert result.outcome == "fail"
    assert result.exit_code == 3


# ---- catalogue id only, never a shell string ----


def test_must_reject_recipe_id_not_in_the_catalogue(tmp_path, scratch):
    catalogue = _load("expected_result.yaml", tmp_path, script_name="exit_three.py")
    with pytest.raises(recipes.RecipeError, match="unknown recipe id"):
        recipes.run(
            "; rm -rf /", {}, catalogue=catalogue, cwd_roles={"scratch": scratch},
            results_dir=tmp_path / "results", env_source={},
        )
