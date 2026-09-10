"""The fix-round route: whether the checks stage's red result set stays inside the machine's bounded repair loop.

`classify` is pure over already-collected outcomes -- no filesystem, no
subprocess, no database -- so the checks stage's driver assembles the recipe and check
results and this module only decides the route. `fix_round` requires every
red result to be a lint or compile-type recipe, or a unit/integration test
green at base and red at head, with no other check red and the per-ticket
cap not yet reached; anything else routes to a human `red_check` with a
reason a queue item can display. The cap is checked first, ahead of the
red results themselves, since a ticket that has already spent its rounds
gets no more regardless of how confined this particular red set looks.
"""
from dataclasses import dataclass

# The test levels a red result may still route through a fix round for,
# provided it was green at base: an end-to-end result never does, whatever
# its base state, since it exercises more than this ticket's own change.
_ELIGIBLE_TEST_LEVELS: tuple[str, ...] = ("unit", "integration")


@dataclass(frozen=True)
class RecipeOutcome:
    """One recipe's base/head result, as the checks stage's driver observed it."""

    recipe_id: str
    kind: str  # "lint" | "compile" | "test" | "other" (recipes.RECIPE_KINDS)
    level: str | None  # "unit" | "integration" | "end_to_end", test recipes only
    base: str | None  # "pass" | "fail" | None (not run at base)
    head: str | None  # "pass" | "fail" | None (not run at head)


@dataclass(frozen=True)
class CheckOutcome:
    """One non-recipe check's result from the checks stage (`scope_diff`, `behavior_contract_evidence`, ...)."""

    check_name: str
    result: str  # "pass" | "fail" | "blind_spot"


@dataclass(frozen=True)
class Route:
    kind: str  # "fix_round" | "red_check"
    # None for fix_round; "base_red" | "end_to_end" | "mixed" | "cap_reached" for red_check.
    reason: str | None = None


def _recipe_verdict(item: RecipeOutcome) -> str:
    """"eligible" when this one red recipe alone stays inside the confinement, else its own ineligibility reason."""
    if item.kind in ("lint", "compile"):
        return "eligible"
    if item.kind == "test" and item.level in _ELIGIBLE_TEST_LEVELS:
        return "eligible" if item.base == "pass" else "base_red"
    # An end-to-end test, or a "other"-kind recipe: neither is ever
    # machine-only, whatever its base result.
    return "end_to_end"


def classify(results, *, rounds_run: int, cap: int) -> Route:
    """The route for `results`: `fix_round` only when every red result is machine-only-eligible and the cap allows it.

    `results` carries every observed recipe and check outcome, red and
    green alike; only the red ones (`head == "fail"` for a recipe,
    `result == "fail"` for a check) affect the route. A ticket at or past
    `cap` fix rounds already run is refused one more before its red
    results are even examined.
    """
    if rounds_run >= cap:
        return Route("red_check", "cap_reached")

    red_recipes = [item for item in results if isinstance(item, RecipeOutcome) and item.head == "fail"]
    red_checks = [item for item in results if isinstance(item, CheckOutcome) and item.result == "fail"]

    verdicts = {_recipe_verdict(item) for item in red_recipes}
    if red_checks:
        verdicts.add("other_check_red")

    if verdicts <= {"eligible"}:
        return Route("fix_round")
    if verdicts == {"base_red"}:
        return Route("red_check", "base_red")
    if verdicts == {"end_to_end"}:
        return Route("red_check", "end_to_end")
    return Route("red_check", "mixed")
