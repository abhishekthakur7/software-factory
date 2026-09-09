"""Production and control-defect incident policy: severities, categories, attribution and disposition values.

`factory/config/incident-policy.yaml` is the one place a control category's
default severity, and the closed sets a human's incident record must fit,
are declared, so a new category or a new severity level needs one file
edit rather than a scattered literal in every module that writes an
`incident_observation` row. The file is read fresh on every call, the same
way `run_ledger.py` reads `tiers.yaml`: it is versioned config an engineer
edits by hand, not a value worth caching against the risk of serving a
stale copy after an edit.
"""
from pathlib import Path

import yaml

from runner.paths import FACTORY_DIR

DEFAULT = FACTORY_DIR / "config" / "incident-policy.yaml"


class IncidentPolicyError(ValueError):
    """A severity, category, attribution, disposition, or remediation reference fails the policy."""


def load(path: Path = DEFAULT) -> dict:
    """The policy file's parsed content."""
    return yaml.safe_load(Path(path).read_text())


def severity_for(category: str, policy: dict | None = None) -> str:
    """The default severity `control_categories` names for `category`.

    Raises `IncidentPolicyError` for a category the policy does not name,
    so a caller never silently falls back to an unrelated severity.
    """
    policy = policy if policy is not None else load()
    categories = policy["control_categories"]
    if category not in categories:
        raise IncidentPolicyError(f"unknown control category: {category!r}")
    return categories[category]


def validate_severity(value: str, policy: dict | None = None) -> None:
    """Raise `IncidentPolicyError` unless `value` is one of `severity_levels`."""
    policy = policy if policy is not None else load()
    levels = policy["severity_levels"]
    if value not in levels:
        raise IncidentPolicyError(f"severity must be one of {list(levels)}, got {value!r}")


def ATTRIBUTIONS(policy: dict | None = None) -> tuple[str, ...]:
    """The closed set `production_disposition.attribution` may take."""
    policy = policy if policy is not None else load()
    return tuple(policy["attribution_values"])


def DISPOSITIONS(policy: dict | None = None) -> tuple[str, ...]:
    """The closed set `production_disposition.disposition` may take."""
    policy = policy if policy is not None else load()
    return tuple(policy["disposition_values"])


def check_remediation(disposition: str, remediation_ref: str | None, policy: dict | None = None) -> None:
    """Raise `IncidentPolicyError` when `disposition` is `remediated` and `remediation_ref` fails the rule.

    A `remediated` disposition requires a reference prefixed with one of
    `remediation_rule.remediated_requires_ref_prefixes` (a catalogue
    failure mode or a rubric line); every other disposition takes no
    reference requirement from this rule.
    """
    if disposition != "remediated":
        return
    policy = policy if policy is not None else load()
    prefixes = tuple(policy["remediation_rule"]["remediated_requires_ref_prefixes"])
    if not remediation_ref or not remediation_ref.startswith(prefixes):
        raise IncidentPolicyError(
            f"a 'remediated' disposition requires --remediation-ref prefixed with one of {list(prefixes)}"
        )
