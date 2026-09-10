"""`runner/checks/regression_only.py`, exercised on seeded texts.

The regression-only exception blocks a lint, compile-type, integration or
end-to-end result only when it worsens at head; unchanged base
diagnostics and tests already red at base stay visible as inherited
debt. `factory/lints/` adds no blocking rule of its own, and the
exception never reaches freshness, unit tests, security, dependency
policy, size, scope, contract evidence, reviewer/approval binding, or
blind spots.
"""
from runner.checks import regression_only
from runner.paths import FACTORY_DIR
from runner.stages.checks import CHECK_ORDER


def test_new_diagnostic_at_head_absent_at_base_is_new_or_worse():
    """Criterion 10: a diagnostic with no occurrence at base blocks."""
    comparison = regression_only.compare_diagnostics(
        base_text="Widget.java:10:5: warning: unused variable y\n",
        head_text="Widget.java:10:5: warning: unused variable y\nOther.java:3:1: warning: raw type List\n",
    )
    assert any("raw type List" in d for d in comparison.new_or_worse)


def test_diagnostic_more_frequent_at_head_than_base_is_new_or_worse():
    """Criterion 10: the same diagnostic present twice at head and once at base worsened."""
    comparison = regression_only.compare_diagnostics(
        base_text="/checkout-a/src/Widget.java:10:5: warning: unused variable y\n",
        head_text=(
            "/checkout-b/src/Widget.java:12:5: warning: unused variable y\n"
            "/checkout-b/src/Widget.java:40:5: warning: unused variable y\n"
        ),
    )
    assert comparison.new_or_worse == ("Widget.java: warning: unused variable y",)
    assert comparison.inherited == ()


def test_diagnostic_unchanged_between_base_and_head_is_inherited_not_blocking():
    """Criterion 11: a diagnostic present at base and unchanged at head never blocks,
    and remains visible as inherited debt rather than silently vanishing."""
    comparison = regression_only.compare_diagnostics(
        base_text="/checkout-a/src/Widget.java:10:5: warning: unused variable y\n",
        head_text="/checkout-b/src/Widget.java:99:1: warning: unused variable y\n",
    )
    assert comparison.new_or_worse == ()
    assert comparison.inherited == ("Widget.java: warning: unused variable y",)


def test_integration_test_red_at_head_and_green_at_base_is_new_or_worse():
    """Criterion 12: an integration/end-to-end result new-red at head blocks."""
    comparison = regression_only.compare_tests(
        base_ran=[{"class": "com.fixture.OrderIntegrationTest", "method": "chargesOrder"}],
        head_ran=[{"class": "com.fixture.OrderIntegrationTest", "method": "chargesOrder"}],
        base_failed=[],
        head_failed=[{"class": "com.fixture.OrderIntegrationTest", "method": "chargesOrder"}],
    )
    assert comparison.new_or_worse == ("com.fixture.OrderIntegrationTest#chargesOrder",)
    assert comparison.inherited == ()


def test_integration_test_already_red_at_base_and_still_red_at_head_does_not_block():
    """Criterion 13: a test already red at base and still red at head never blocks."""
    comparison = regression_only.compare_tests(
        base_ran=[{"class": "com.fixture.OrderIntegrationTest", "method": "chargesOrder"}],
        head_ran=[{"class": "com.fixture.OrderIntegrationTest", "method": "chargesOrder"}],
        base_failed=[{"class": "com.fixture.OrderIntegrationTest", "method": "chargesOrder"}],
        head_failed=[{"class": "com.fixture.OrderIntegrationTest", "method": "chargesOrder"}],
    )
    assert comparison.new_or_worse == ()
    assert comparison.inherited == ("com.fixture.OrderIntegrationTest#chargesOrder",)


def test_factory_lints_adds_no_blocking_rule():
    """Criterion 14: whatever `factory/lints/` holds, none of it names a check that
    `checks.CHECK_ORDER` or the regression-only governed kinds already treat as
    blocking -- a real assertion over the directory's actual contents, not a
    vacuous pass because the directory happens to be empty today."""
    lints_dir = FACTORY_DIR / "lints"
    reserved_names = set(CHECK_ORDER) | set(regression_only.GOVERNED_KINDS)
    lint_files = [p for p in lints_dir.rglob("*") if p.is_file() and p.name != ".gitkeep"]
    for path in lint_files:
        text = path.read_text()
        for name in reserved_names:
            assert f"blocking: {name}" not in text and f'"{name}": "blocking"' not in text, (path, name)


def test_regression_only_governs_only_lint_compile_and_integration_and_end_to_end_results():
    """Criterion 15: freshness, unit tests, security, dependency policy, size, scope,
    contract evidence, reviewer/approval binding and blind spots keep their own
    blocking rule; only the four governed kinds are ever exempted."""
    for kind in regression_only.GOVERNED_KINDS:
        assert regression_only.governs(kind) is True

    ungoverned_kinds = (
        "freshness", "unit_test", "security", "dependency_policy", "size", "scope",
        "contract_evidence", "reviewer_or_approval_binding", "blind_spot",
    )
    for kind in ungoverned_kinds:
        assert regression_only.governs(kind) is False


def test_recipe_governed_kind_maps_a_catalogue_recipe_to_its_governed_kind_or_none():
    """A recipe's own `kind`/`level` (`command-recipes.yaml`'s shape) maps onto
    `GOVERNED_KINDS` the same way `governs` reads them; a unit test recipe maps
    to nothing, so it keeps blocking on any head red regardless of base."""
    assert regression_only.recipe_governed_kind(kind="lint", level=None) == "lint"
    assert regression_only.recipe_governed_kind(kind="compile", level=None) == "compile"
    assert regression_only.recipe_governed_kind(kind="test", level="integration") == "integration_test"
    assert regression_only.recipe_governed_kind(kind="test", level="end_to_end") == "end_to_end_test"
    assert regression_only.recipe_governed_kind(kind="test", level="unit") is None
    assert regression_only.recipe_governed_kind(kind="other", level=None) is None
