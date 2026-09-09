"""The one loader of `project.yaml`: the pilot's own entry, and the fields shared across every project.

Every earlier reader of `project.yaml` read the whole file as one flat
mapping, because the pilot project was the file's only content. Now that
`projects` is a list -- ready for a second project none is configured for yet -- `pilot()` gives every one of those call sites back the exact same
flat shape they always read (`name`, `checkout`, `vendor`, `target_branch`,
`recipes`, `impact_methods`, `toolchain`), so a caller only needs to swap
its own `yaml.safe_load` for this module's `pilot()`, not change what it
reads off the result. `scratch_repository`, `generated_paths` and
`lockfiles` sit beside `projects` at the document's top level because they
are not per-project; `load()` is for a caller that needs one of those
instead of the pilot's own fields.
"""
from pathlib import Path

import yaml

from runner.paths import FACTORY_DIR

DEFAULT_PROJECT_CONFIG_PATH = FACTORY_DIR / "config" / "project.yaml"


class ProjectConfigError(ValueError):
    """`project.yaml` does not name exactly one project where a caller asked for the pilot."""


def load(path: Path = DEFAULT_PROJECT_CONFIG_PATH) -> dict:
    """The whole parsed document: `projects`, `scratch_repository`, `generated_paths`, `lockfiles`."""
    return yaml.safe_load(Path(path).read_text()) or {}


def pilot(path: Path = DEFAULT_PROJECT_CONFIG_PATH) -> dict:
    """The pilot project's own entry.

    Every current caller was written for a file that named exactly one
    project; `projects` must therefore still carry exactly one entry
    today, and a file that doesn't is a config defect worth refusing
    on rather than silently picking the first of several.
    """
    projects = load(path).get("projects") or []
    if len(projects) != 1:
        raise ProjectConfigError(f"project.yaml: expected exactly one project under 'projects', found {len(projects)}")
    return projects[0]
