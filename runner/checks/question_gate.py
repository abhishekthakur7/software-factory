"""The pre-queue question gate: format, option, and identifier rules a candidate question must clear.

`validate` is pure -- it takes one candidate mapping (the shape an agent's
`questions.yaml` item carries) and returns every violation found, never
touching the database or the filesystem -- so `questions.raise_round` can
validate a whole round before writing any row. The identifier ban treats a
requirement, principle, failure-mode, decision, or stage id, or an
artefact-kind, script, or table name, as leaked internal vocabulary: a
reader with no access to the plan, the schema, or the codebase behind the
question should still be able to answer it. `allowed_names` carries the
one exception the row states: names that are the service's own code (a
class name, say), supplied by the caller rather than derived here.

The two keyword lists below are the one deterministic classification rule
applied at the gate: when a candidate's `affects` names a surface the
owner has flagged as consequential or hard-to-reverse, the matching flag
must already be set, or the candidate is refused rather than trusted on
its own say-so. Both lists are lax and owner-tuned, not exhaustive.
"""
import re

from runner.schema import TABLES

MIN_OPTIONS = 2
MAX_OPTIONS = 4
NONE_OF_THESE = "none of these"

# The phrases a default option's consequence must carry, so a reader knows
# what happens if the question goes unanswered.
UNANSWERED_MARKERS: tuple[str, ...] = ("if nobody answers", "unanswered")

ARTEFACT_KIND_NAMES: tuple[str, ...] = ("brief", "criteria", "plan", "packet", "handoff", "question_set")
SCRIPT_NAMES: tuple[str, ...] = (
    "impact_scan", "java_compile", "java_lint", "java_test", "export", "import", "manifest_hash", "purge", "report",
)
TABLE_NAMES: tuple[str, ...] = tuple(table.name for table in TABLES)

CONSEQUENTIAL_KEYWORDS: tuple[str, ...] = (
    "contract", "migration", "permission", "public interface", "rollout", "sensitive path",
)
HARD_TO_REVERSE_KEYWORDS: tuple[str, ...] = ("data", "interface", "authorization", "customer-visible")

_IDENTIFIER_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"\bR-[A-Z0-9]+-\d+\b"),
    re.compile(r"\bP\d+\b"),
    re.compile(r"\bFM-\d+\b"),
    re.compile(r"\bD\d+\b"),
    re.compile(r"\bS[0-7]\b"),
)


def _word_patterns(names) -> tuple[re.Pattern, ...]:
    return tuple(re.compile(rf"\b{re.escape(name)}\b", re.IGNORECASE) for name in names)


_NAME_PATTERNS: tuple[re.Pattern, ...] = (
    _IDENTIFIER_PATTERNS + _word_patterns(ARTEFACT_KIND_NAMES) + _word_patterns(SCRIPT_NAMES) + _word_patterns(TABLE_NAMES)
)


def _identifier_hit(text: str, *, allowed_names: frozenset) -> str | None:
    """The first banned identifier found in `text`, or `None`; a hit that is itself an `allowed_names` entry is not a hit."""
    for pattern in _NAME_PATTERNS:
        match = pattern.search(text or "")
        if match and match.group(0) not in allowed_names:
            return match.group(0)
    return None


def _consequence_ok(option: dict, *, is_default: bool) -> bool:
    consequence = (option.get("consequence") or "").strip()
    if not consequence:
        return False
    if is_default and not any(marker in consequence.lower() for marker in UNANSWERED_MARKERS):
        return False
    return True


def validate(candidate: dict, *, allowed_names: frozenset = frozenset()) -> list[str]:
    """Every reason `candidate` fails the pre-queue gate, in no particular order; `[]` means it passes."""
    reasons: list[str] = []
    reasoning, affects = candidate.get("reasoning"), candidate.get("affects")
    options = candidate.get("options") or []
    default_option = candidate.get("default_option")
    sensitive = bool(candidate.get("sensitive"))
    # A sensitive decision is consequential regardless of what the agent
    # itself reported (R-S2-8 criterion 9): the effective flag, not the
    # raw field, drives every rule below.
    consequential = bool(candidate.get("consequential")) or sensitive
    hard_to_reverse = bool(candidate.get("hard_to_reverse"))

    if not reasoning:
        reasons.append("reasoning is required and must name sources tried")
    if not affects:
        reasons.append("affects is required and must name what the answer changes")

    if not (MIN_OPTIONS <= len(options) <= MAX_OPTIONS):
        reasons.append(f"options must number between {MIN_OPTIONS} and {MAX_OPTIONS}, got {len(options)}")
    elif (options[-1].get("text") or "").strip().lower() != NONE_OF_THESE:
        reasons.append("the last option must be 'none of these'")

    for index, option in enumerate(options):
        if not _consequence_ok(option, is_default=(index == default_option)):
            reasons.append(f"option {index} needs a one-sentence consequence")

    default_must_be_null = (consequential and hard_to_reverse) or sensitive
    if default_must_be_null and default_option is not None:
        reasons.append("default_option must be null when both flags are true or the decision is sensitive")
    if not default_must_be_null and default_option is None:
        reasons.append("default_option is required")
    if default_option is not None and not (0 <= default_option < len(options)):
        reasons.append("default_option does not name a real option")

    if affects:
        lowered = affects.lower()
        if any(keyword in lowered for keyword in CONSEQUENTIAL_KEYWORDS) and not consequential:
            reasons.append("affects names a consequential surface but consequential is not set")
        if any(keyword in lowered for keyword in HARD_TO_REVERSE_KEYWORDS) and not hard_to_reverse:
            reasons.append("affects names a hard-to-reverse surface but hard_to_reverse is not set")

    for source in (candidate.get("text"), *(option.get("text") for option in options)):
        hit = _identifier_hit(source or "", allowed_names=allowed_names)
        if hit is not None:
            reasons.append(f"text names a banned identifier: {hit!r}")
            break

    return reasons
