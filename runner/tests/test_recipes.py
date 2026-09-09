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
import os
import time
from types import SimpleNamespace

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
        "fixture_lint", "fixture_compile", "fixture_unit", "fixture_integration", "fixture_e2e", "fixture_dependencies", "fixture_security",
    }
    unit = catalogue["fixture_unit"]
    assert unit.level == "unit"
    assert unit.test_globs == ("src/test/java/**/*UnitTest.java",)
    assert catalogue["fixture_lint"].level is None
    assert catalogue["fixture_dependencies"].network == "none"
    assert catalogue["fixture_dependencies"].cache_policy is None


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


def test_dependency_resolution_recipe_runs_under_the_build_profile(tmp_path):
    """The configured resolver reads its copied project view under the real S5 build sandbox;
    the launch record proves the OS profile wrapped this execution rather than a test double."""
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    vendor = tmp_path / "vendor"
    vendor.mkdir()
    (checkout / "pom.xml").write_text("<project/>")
    result = recipes.run(
        "fixture_dependencies", {"pom": "pom.xml", "vendor": str(vendor)}, catalogue=recipes.load_catalogue(),
        cwd_roles={"checkout": checkout}, results_dir=tmp_path / "results", env_source={"PATH": os.environ["PATH"]},
        sandbox_run_dir=tmp_path / "sandbox-run", sandbox_stage="S5", sandbox_vendor_dir=vendor,
    )
    assert result.outcome == "pass"
    assert (tmp_path / "sandbox-run" / "results" / "exit.json").read_text().find('"os_policy": true') >= 0


def test_security_recipe_receives_pinned_inputs_from_the_read_only_sandbox_results_area(tmp_path):
    """Security policy files are staged by the trusted runner, so the build copy cannot supply
    a replacement policy while the child still receives the exact recipe inputs it needs."""
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    vendor = tmp_path / "vendor"
    vendor.mkdir()
    (checkout / "pom.xml").write_text("<project/>")
    result = recipes.run(
        "fixture_security", {}, catalogue=recipes.load_catalogue(), cwd_roles={"checkout": checkout},
        results_dir=tmp_path / "results", env_source={"PATH": os.environ["PATH"]},
        sandbox_run_dir=tmp_path / "sandbox-run", sandbox_stage="S5",
    )
    inputs = tmp_path / "sandbox-run" / "results" / "inputs"
    assert result.outcome == "pass"
    assert result.reported_result == "blind_spot"
    assert (inputs / "security-checks.yaml").is_file()
    assert (inputs / "security-rules.yaml").is_file()


def test_must_reject_a_sandbox_stage_absent_from_the_recipe_declaration(tmp_path):
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    vendor = tmp_path / "vendor"
    vendor.mkdir()
    (checkout / "pom.xml").write_text("<project/>")
    with pytest.raises(recipes.RecipeError, match="not declared"):
        recipes.run(
            "fixture_dependencies", {"pom": "pom.xml", "vendor": str(vendor)}, catalogue=recipes.load_catalogue(),
            cwd_roles={"checkout": checkout}, results_dir=tmp_path / "results", env_source={"PATH": os.environ["PATH"]},
            sandbox_run_dir=tmp_path / "sandbox", sandbox_stage="S4",
        )


def test_must_reject_an_unadmitted_registry_endpoint_before_launch(tmp_path, monkeypatch):
    executable = REPO_ROOT / "factory/scripts/checks/dep_resolve"
    recipe = recipes.Recipe(
        id="networked", executable=executable.relative_to(REPO_ROOT), executable_digest=hashlib.sha256(executable.read_bytes()).hexdigest(),
        args=("--pom", recipes.ArgPlaceholder("pom", "path")), cwd_role="checkout", kind="dependency", stages=("S5",),
        timeout_seconds=1, expected_exit_codes=(0,), env_allowlist=("PATH",), network="registry", output_retention="keep",
        registry_endpoints=("registry.invalid",), cache_policy="isolated",
    )
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    vendor = tmp_path / "vendor"
    vendor.mkdir()
    (checkout / "pom.xml").write_text("<project/>")
    monkeypatch.setattr(recipes.launcher, "launch", lambda **_: pytest.fail("unavailable recipe dispatched"))
    with pytest.raises(recipes.RecipeUnavailable, match="registry endpoint"):
        recipes.run(
            "networked", {"pom": "pom.xml"}, catalogue={"networked": recipe}, cwd_roles={"checkout": checkout},
            results_dir=tmp_path / "results", env_source={"PATH": os.environ["PATH"]}, sandbox_run_dir=tmp_path / "sandbox", sandbox_stage="S5",
        )


def test_must_reject_a_build_result_without_policy_or_integrity_proof(tmp_path, monkeypatch):
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    vendor = tmp_path / "vendor"
    vendor.mkdir()
    (checkout / "pom.xml").write_text("<project/>")
    launched = SimpleNamespace(
        os_policy_applied=False, integrity=SimpleNamespace(ok=False, violations=("missing profile",)), stdout_text="", stderr_text="", timed_out=False, exit_code=0,
    )
    monkeypatch.setattr(recipes.launcher, "launch", lambda **_: launched)
    with pytest.raises(recipes.RecipeSandboxError, match="without an OS sandbox"):
        recipes.run(
            "fixture_dependencies", {"pom": "pom.xml", "vendor": str(vendor)}, catalogue=recipes.load_catalogue(), cwd_roles={"checkout": checkout},
            results_dir=tmp_path / "results", env_source={"PATH": os.environ["PATH"]}, sandbox_run_dir=tmp_path / "sandbox", sandbox_stage="S5",
        )


# ---- catalogue id only, never a shell string ----


def test_must_reject_recipe_id_not_in_the_catalogue(tmp_path, scratch):
    catalogue = _load("expected_result.yaml", tmp_path, script_name="exit_three.py")
    with pytest.raises(recipes.RecipeError, match="unknown recipe id"):
        recipes.run(
            "; rm -rf /", {}, catalogue=catalogue, cwd_roles={"scratch": scratch},
            results_dir=tmp_path / "results", env_source={},
        )
