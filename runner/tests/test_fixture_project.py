"""The fixture project: its seed shape, materialisation, git trees, and its
five recipes and impact-scan method run against the same repository.

Tests that must actually compile or run Java (materialising the vendored
jars, or invoking a lint/compile/test recipe) skip loudly without a JDK;
everything else -- the seed's committed shape, the config rows, git-tree
mechanics against a throwaway git repository, and impact_scan's pure
XML/YAML resolution -- needs no toolchain and always runs.
"""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from runner import git_trees, project, record, recipes, setup
from runner.db import connect
from runner.paths import FACTORY_DIR

SEED_DIR = FACTORY_DIR / "evals" / "fixture-project"
IMPACT_SCAN = FACTORY_DIR / "scripts" / "checks" / "impact_scan"
IMPACT_EVAL_DIR = FACTORY_DIR / "evals" / "scripts" / "checks" / "impact_scan"

HAS_JAVAC = shutil.which("javac") is not None and shutil.which("jar") is not None
skip_without_jdk = pytest.mark.skipif(not HAS_JAVAC, reason="javac/jar not available")


def _project_config(tmp_path: Path) -> Path:
    path = tmp_path / "project.yaml"
    path.write_text(yaml.safe_dump({
        "projects": [{
            "name": "fixture-project",
            "checkout": "runs/sources/fixture-project",
            "vendor": "runs/sources/fixture-project-vendor",
            "target_branch": "main",
        }],
    }))
    return path


def _materialise_project(tmp_path: Path) -> setup.Materialised:
    return setup.materialise(project_path=_project_config(tmp_path), repo_root=tmp_path)


def _vendor_classpath(materialised: setup.Materialised) -> str:
    return os.pathsep.join(str(p) for p in sorted(materialised.vendor.rglob("*.jar")))


def _git(args, cwd, env=None):
    full_env = {**os.environ, **env} if env else None
    return subprocess.run(
        ["git", "-c", "commit.gpgsign=false", *args],
        cwd=cwd, env=full_env, capture_output=True, text=True, check=True,
    )


_COMMIT_ENV = {
    "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@example.invalid",
}


def _bare_git_project(tmp_path: Path) -> Path:
    """A trivial one-file git repository, independent of the Java fixture
    project, so git_trees' clone/worktree/checkout mechanics can be tested
    without a JDK."""
    repo = tmp_path / "source-repo"
    repo.mkdir()
    _git(["init", "-q"], cwd=repo)
    _git(["checkout", "-q", "-b", "main"], cwd=repo)
    (repo / "pom.xml").write_text("<project/>\n")
    _git(["add", "-A"], cwd=repo)
    _git(["commit", "-q", "-m", "init"], cwd=repo, env=_COMMIT_ENV)
    return repo


def _run_impact_scan(pom: Path, vendor_repo: Path, mapping: Path) -> dict:
    result = subprocess.run(
        [str(IMPACT_SCAN), "--pom", str(pom), "--vendor-repo", str(vendor_repo), "--mapping", str(mapping)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


# ---- the committed seed ----


def test_fixture_project_seed_holds_codeowners_and_one_sensitive_path():
    codeowners = (SEED_DIR / "CODEOWNERS").read_text()
    assert "auth/" in codeowners

    sensitive = yaml.safe_load((FACTORY_DIR / "config" / "sensitive-paths.yaml").read_text())
    assert any("auth" in glob_pattern for glob_pattern in sensitive["paths"])
    assert (SEED_DIR / "src" / "main" / "java" / "com" / "fixture" / "auth" / "TokenChecker.java").is_file()


# ---- vendored dependency repository, no registry ----


def test_vendor_directory_holds_source_and_poms_but_no_committed_jar():
    vendor_seed = SEED_DIR / "vendor"
    poms = list(vendor_seed.rglob("*.pom"))
    assert len(poms) >= 2, "the dependency tree must have depth two: strings depends on util"
    assert not list(vendor_seed.rglob("*.jar")), "no jar is committed; setup.py builds it at materialise time"


def test_project_and_recipes_name_no_registry_endpoint():
    pilot_cfg = project.pilot()
    assert "registry" not in pilot_cfg

    catalogue_doc = yaml.safe_load((FACTORY_DIR / "config" / "command-recipes.yaml").read_text())
    for entry in catalogue_doc["recipes"]:
        assert entry["network"] == "none"


@skip_without_jdk
def test_fixture_compile_succeeds_reading_only_the_vendored_repository(tmp_path):
    materialised = _materialise_project(tmp_path)
    catalogue = recipes.load_catalogue()
    result = recipes.run(
        "fixture_compile", {"vendor_classpath": _vendor_classpath(materialised)}, catalogue=catalogue,
        cwd_roles={"checkout": materialised.checkout}, results_dir=tmp_path / "results",
        env_source={"PATH": os.environ["PATH"]},
    )
    assert result.outcome == "pass"


# ---- fixture-project's own rows ----


def test_fixture_project_is_a_t2_service_and_small_feature_eligible():
    tiers = yaml.safe_load((FACTORY_DIR / "config" / "service-tiers.yaml").read_text())
    assert tiers["services"]["fixture-project"]["tier"] == "T2"

    types = yaml.safe_load((FACTORY_DIR / "config" / "ticket-types.yaml").read_text())
    assert "fixture-project" in types["types"]["small_feature"]["eligible_services"]


# ---- materialise() ----


@skip_without_jdk
def test_materialise_pins_the_project_outside_factory_and_the_manifest(tmp_path):
    materialised = _materialise_project(tmp_path)
    assert not str(materialised.checkout).startswith(str(FACTORY_DIR))
    assert not str(materialised.vendor).startswith(str(FACTORY_DIR))
    assert (materialised.checkout / ".git").is_dir()
    assert materialised.head_sha

    manifest = yaml.safe_load((FACTORY_DIR / "manifest.yaml").read_text())
    manifest_paths = {entry["path"] for entry in manifest["files"]}
    assert not any(p.startswith("runs/") for p in manifest_paths)
    assert not any("fixture-project-vendor" in p for p in manifest_paths)


@skip_without_jdk
def test_must_reject_materialise_over_an_existing_checkout_without_force(tmp_path):
    project_cfg = _project_config(tmp_path)
    setup.materialise(project_path=project_cfg, repo_root=tmp_path)

    with pytest.raises(setup.SetupError):
        setup.materialise(project_path=project_cfg, repo_root=tmp_path)

    replaced = setup.materialise(project_path=project_cfg, repo_root=tmp_path, force=True)
    assert replaced.head_sha


# ---- eligibility clone, worktree, no push URL ----


def test_eligibility_creates_isolated_clone_and_worktree_recording_base_sha_and_no_push_url(tmp_path):
    source = _bare_git_project(tmp_path)
    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = record.insert(conn, "ticket", title="t", state="intake", opened_at=record.now())

    trees = git_trees.clone_for_ticket(
        conn, ticket_id, source_checkout=source, target_branch="main", runs_dir=tmp_path / "runs"
    )

    row = record.get(conn, "ticket", ticket_id)
    assert row["base_sha"] == trees.base_sha
    assert row["target_base_sha"] == trees.base_sha
    assert row["branch"] == trees.branch
    assert row["worktree_path"] == str(trees.worktree)
    assert (trees.worktree / "pom.xml").is_file()

    push_url = _git(["remote", "get-url", "--push", "origin"], cwd=trees.repo).stdout.strip()
    assert push_url == git_trees.DISABLED_PUSH_URL

    pushed = subprocess.run(["git", "-C", str(trees.repo), "push"], capture_output=True, text=True)
    assert pushed.returncode != 0


def test_record_head_reads_the_worktree_head_onto_the_ticket_row(tmp_path):
    source = _bare_git_project(tmp_path)
    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = record.insert(conn, "ticket", title="t", state="intake", opened_at=record.now())
    trees = git_trees.clone_for_ticket(
        conn, ticket_id, source_checkout=source, target_branch="main", runs_dir=tmp_path / "runs"
    )

    (trees.worktree / "NEW.txt").write_text("agent work")
    _git(["add", "-A"], cwd=trees.worktree)
    _git(["commit", "-q", "-m", "agent change"], cwd=trees.worktree, env=_COMMIT_ENV)

    head_sha = git_trees.record_head(conn, ticket_id, trees.worktree)
    assert head_sha != trees.base_sha
    assert record.get(conn, "ticket", ticket_id)["head_sha"] == head_sha


# ---- plain base and head checkouts ----


def test_plain_base_and_head_checkouts_are_independently_usable(tmp_path):
    source = _bare_git_project(tmp_path)
    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = record.insert(conn, "ticket", title="t", state="intake", opened_at=record.now())
    trees = git_trees.clone_for_ticket(
        conn, ticket_id, source_checkout=source, target_branch="main", runs_dir=tmp_path / "runs"
    )

    (trees.worktree / "NEW.txt").write_text("agent work")
    _git(["add", "-A"], cwd=trees.worktree)
    _git(["commit", "-q", "-m", "agent change"], cwd=trees.worktree, env=_COMMIT_ENV)
    head_sha = git_trees.record_head(conn, ticket_id, trees.worktree)

    # base_sha is reachable from the shared project checkout; head_sha only
    # exists once the ticket's own clone has it, since nothing is ever
    # pushed back to the shared checkout.
    base_dest = tmp_path / "base-checkout"
    head_dest = tmp_path / "head-checkout"
    git_trees.plain_checkout(source, trees.base_sha, base_dest)
    git_trees.plain_checkout(trees.repo, head_sha, head_dest)

    assert (base_dest / "pom.xml").is_file()
    assert not (base_dest / "NEW.txt").exists(), "the base checkout predates the agent's change"
    assert (head_dest / "NEW.txt").is_file()

    # each checkout is independent of the ticket worktree: a later worktree
    # mutation does not reach either one.
    (trees.worktree / "NEW.txt").write_text("mutated after the checkouts were taken")
    assert (head_dest / "NEW.txt").read_text() == "agent work"


# ---- throwaway copy ----


def test_throwaway_copy_lets_a_check_write_without_touching_the_original(tmp_path):
    source = _bare_git_project(tmp_path)
    base_sha = _git(["rev-parse", "main"], cwd=source).stdout.strip()
    base_dest = tmp_path / "base-checkout"
    git_trees.plain_checkout(source, base_sha, base_dest)

    throwaway = tmp_path / "throwaway"
    git_trees.throwaway_copy(base_dest, throwaway)
    (throwaway / "build-output.txt").write_text("generated by a check")

    assert (throwaway / "build-output.txt").is_file()
    assert not (base_dest / "build-output.txt").exists()


# ---- lint and compile recipes ----


@skip_without_jdk
def test_fixture_lint_and_compile_report_pass_on_the_clean_seed(tmp_path):
    materialised = _materialise_project(tmp_path)
    catalogue = recipes.load_catalogue()
    values = {"vendor_classpath": _vendor_classpath(materialised)}
    env_source = {"PATH": os.environ["PATH"]}

    for recipe_id in ("fixture_lint", "fixture_compile"):
        result = recipes.run(
            recipe_id, values, catalogue=catalogue, cwd_roles={"checkout": materialised.checkout},
            results_dir=tmp_path / "results", env_source=env_source,
        )
        assert result.outcome == "pass", (recipe_id, result.exit_code)


@skip_without_jdk
def test_fixture_lint_reports_fail_on_a_broken_throwaway_copy(tmp_path):
    materialised = _materialise_project(tmp_path)
    broken = tmp_path / "broken-checkout"
    git_trees.throwaway_copy(materialised.checkout, broken)
    greeter = broken / "src" / "main" / "java" / "com" / "fixture" / "Greeter.java"
    greeter.write_text(greeter.read_text() + "\nthis is not valid java;\n")

    catalogue = recipes.load_catalogue()
    result = recipes.run(
        "fixture_lint", {"vendor_classpath": _vendor_classpath(materialised)}, catalogue=catalogue,
        cwd_roles={"checkout": broken}, results_dir=tmp_path / "results",
        env_source={"PATH": os.environ["PATH"]},
    )
    assert result.outcome == "fail"
    assert not (materialised.checkout / "src" / "main" / "java" / "com" / "fixture" / "Greeter.java").read_text().endswith(
        "not valid java;\n"
    )


# ---- unit, integration, end-to-end test recipes ----


@skip_without_jdk
@pytest.mark.parametrize(
    "recipe_id,expected_level,expected_classes",
    [
        ("fixture_unit", "unit", {"com.fixture.GreeterUnitTest", "com.fixture.auth.TokenCheckerUnitTest"}),
        ("fixture_integration", "integration", {"com.fixture.GreeterIntegrationTest"}),
        ("fixture_e2e", "end_to_end", {"com.fixture.AppEndToEndTest"}),
    ],
)
def test_fixture_test_recipes_carry_their_level_and_report_the_test_identities_that_ran(
    tmp_path, recipe_id, expected_level, expected_classes
):
    materialised = _materialise_project(tmp_path)
    catalogue = recipes.load_catalogue()
    recipe = catalogue[recipe_id]
    assert recipe.level == expected_level
    assert recipe.test_globs

    result = recipes.run(
        recipe_id, {"vendor_classpath": _vendor_classpath(materialised)}, catalogue=catalogue,
        cwd_roles={"checkout": materialised.checkout}, results_dir=tmp_path / "results",
        env_source={"PATH": os.environ["PATH"]},
    )
    assert result.outcome == "pass"
    assert result.level == expected_level
    assert {identity["class"] for identity in result.tests_ran} == expected_classes


# ---- impact_scan and its coverage classes ----


def test_impact_scan_over_the_fixture_project_resolves_depth_two_with_authoritative_and_partial_coverage():
    payload = _run_impact_scan(
        SEED_DIR / "pom.xml", SEED_DIR / "vendor", FACTORY_DIR / "config" / "artifact-to-service.yaml",
    )
    by_artifact = {dep["artifact_id"]: dep for dep in payload["dependencies"]}
    assert by_artifact["strings"]["coverage"] == "authoritative"
    assert by_artifact["strings"]["depth"] == 1
    assert by_artifact["util"]["coverage"] == "partial"
    assert by_artifact["util"]["depth"] == 2
    for dep in payload["dependencies"]:
        assert dep["method"] == "import_scan"
        assert dep["direction"] == "outbound"


_IMPACT_EVAL_SPEC = yaml.safe_load((IMPACT_EVAL_DIR / "eval.yaml").read_text())


@pytest.mark.parametrize(
    "case", _IMPACT_EVAL_SPEC["cases"], ids=[c["name"] for c in _IMPACT_EVAL_SPEC["cases"]]
)
def test_impact_scan_eval_fixtures_resolve_their_declared_coverage(case):
    fixture_dir = IMPACT_EVAL_DIR / case["fixture"]
    payload = _run_impact_scan(
        fixture_dir / "checkout" / "pom.xml", fixture_dir / "vendor", fixture_dir / "mapping.yaml",
    )
    assert len(payload["dependencies"]) == 1
    dep = payload["dependencies"][0]
    assert dep["group_id"] == case["dependency"]["group_id"]
    assert dep["artifact_id"] == case["dependency"]["artifact_id"]
    assert dep["coverage"] == case["expect_coverage"]


def test_an_artifact_absent_from_the_mapping_resolves_unknown_even_with_other_entries_present():
    """the unknown case's mapping.yaml is empty; this proves absence, not an
    empty file, is what drives unknown, by pointing the same fixture's
    dependency at a mapping file that maps a different artifact."""
    fixture_dir = IMPACT_EVAL_DIR / "fixtures" / "unknown"
    other_mapping = IMPACT_EVAL_DIR / "fixtures" / "authoritative" / "mapping.yaml"
    payload = _run_impact_scan(fixture_dir / "checkout" / "pom.xml", fixture_dir / "vendor", other_mapping)
    assert payload["dependencies"][0]["coverage"] == "unknown"
    assert payload["dependencies"][0]["service"] is None
