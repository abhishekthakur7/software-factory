"""Regression-only comparison: base and head diagnostics or test results, pure over already-collected text.

This exception blocks a lint, compile-type, integration or end-to-end
result only when it worsens at head; an unchanged base diagnostic or a
test already red at base stays visible as inherited debt rather than a
fresh block. Every function here takes plain text or already-parsed
identities and returns data -- no filesystem, no subprocess, no database
-- so the checks stage's driver decides what to do with a `Comparison` without this
module ever running a recipe itself.
"""
import re
from collections import Counter
from dataclasses import dataclass

# The only kinds this exception ever governs; every other check (freshness,
# unit tests, security, dependency policy, size, scope, contract evidence,
# reviewer/approval binding, blind spots) keeps its own blocking rule
# untouched by regression-only.
GOVERNED_KINDS: tuple[str, ...] = ("lint", "compile", "integration_test", "end_to_end_test")

# A catalogue recipe's own `kind` ("lint", "compile", "test", "other") plus,
# for a test recipe, its `level` ("unit", "integration", "end_to_end") name
# the governed kind the driver compares against `GOVERNED_KINDS`; a unit
# test has no entry here and so is never governed, matching the checks
# stage's own rule that unit tests keep their own blocking rule.
_TEST_LEVEL_KINDS: dict[str, str] = {"integration": "integration_test", "end_to_end": "end_to_end_test"}

_LINE_COLUMN = re.compile(r":\d+:\d+")
_TRAILING_LINE_NUMBER = re.compile(r":\d+\b")
_ABSOLUTE_PATH_TOKEN = re.compile(r"(?:^|(?<=[\s(]))/\S+")


@dataclass(frozen=True)
class Comparison:
    new_or_worse: tuple[str, ...]
    inherited: tuple[str, ...]


def _normalize_diagnostic(line: str) -> str:
    """Strip line:column numbers and absolute path prefixes so the same
    diagnostic at a different checkout root or a shifted line number still
    counts as the same diagnostic when comparing base against head."""
    text = _LINE_COLUMN.sub("", line)
    text = _TRAILING_LINE_NUMBER.sub("", text)
    text = _ABSOLUTE_PATH_TOKEN.sub(lambda m: m.group(0).rsplit("/", 1)[-1], text)
    return text.strip()


def compare_diagnostics(base_text: str, head_text: str) -> Comparison:
    """Normalised, counted diagnostic lines: a diagnostic more frequent at head than
    at base is `new_or_worse` in full; one at head no more frequent than at base is
    `inherited`. A diagnostic fixed entirely at head reports in neither list."""
    base_counts = Counter(_normalize_diagnostic(line) for line in base_text.splitlines() if line.strip())
    head_counts = Counter(_normalize_diagnostic(line) for line in head_text.splitlines() if line.strip())

    new_or_worse, inherited = [], []
    for diagnostic, head_count in head_counts.items():
        if head_count > base_counts.get(diagnostic, 0):
            new_or_worse.append(diagnostic)
        else:
            inherited.append(diagnostic)
    return Comparison(new_or_worse=tuple(sorted(new_or_worse)), inherited=tuple(sorted(inherited)))


def _identity(entry: dict) -> str:
    return f"{entry['class']}#{entry['method']}"


def compare_tests(base_ran: list[dict], head_ran: list[dict], base_failed: list[dict], head_failed: list[dict]) -> Comparison:
    """Test identities red at head: `new_or_worse` when not red at base, `inherited`
    when already red at base. `base_ran`/`head_ran` are accepted for symmetry with
    the recipe's own `{"ran": [...]}` shape but the verdict turns on redness alone --
    a test that simply stopped running is `base_test_diff`'s concern, not this one's."""
    del base_ran, head_ran  # not needed for the red/inherited verdict itself
    red_at_base = {_identity(e) for e in base_failed}
    red_at_head = {_identity(e) for e in head_failed}

    new_or_worse = tuple(sorted(red_at_head - red_at_base))
    inherited = tuple(sorted(red_at_head & red_at_base))
    return Comparison(new_or_worse=new_or_worse, inherited=inherited)


def governs(recipe_kind: str) -> bool:
    """True when `recipe_kind` (one of `GOVERNED_KINDS`) is exempted by the regression-only rule."""
    return recipe_kind in GOVERNED_KINDS


def recipe_governed_kind(*, kind: str, level: str | None) -> str | None:
    """The `GOVERNED_KINDS` member `kind`/`level` maps to, or `None` when nothing governs this recipe.

    `lint` and `compile` map straight through; a `test` recipe maps by its
    `level` (`unit` has no entry, so it is never governed); every other
    `kind` (`other`) maps to nothing.
    """
    if kind in ("lint", "compile"):
        return kind
    if kind == "test":
        return _TEST_LEVEL_KINDS.get(level or "")
    return None
