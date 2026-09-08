"""Parses the small YAML front matter every stub agent/skill/rubric file carries.

Front matter is the fenced `---`-delimited block at the top of the file,
same convention as the context index. This loader is the one place
that parses it, so the eval-directory conformance test in
`test_stub_stages.py` exercises real code rather than re-deriving the same
YAML slice the fixture already encodes.
"""
from pathlib import Path

import yaml

REQUIRED_KEYS = ("name", "kind", "stage")
VALID_KINDS = frozenset({"agent", "skill", "rubric"})


class DefinitionError(ValueError):
    """The file has no front matter, malformed YAML, a missing key, or an invalid `kind`."""


def load_definition(path: Path) -> dict:
    text = Path(path).read_text()
    if not text.startswith("---\n"):
        raise DefinitionError(f"{path}: missing front matter")
    end = text.find("\n---", 4)
    if end == -1:
        raise DefinitionError(f"{path}: unterminated front matter")
    try:
        front_matter = yaml.safe_load(text[4:end])
    except yaml.YAMLError as exc:
        raise DefinitionError(f"{path}: invalid YAML front matter: {exc}") from exc
    if not isinstance(front_matter, dict):
        raise DefinitionError(f"{path}: front matter is not a mapping")
    missing = [key for key in REQUIRED_KEYS if key not in front_matter]
    if missing:
        raise DefinitionError(f"{path}: front matter missing {missing}")
    if front_matter["kind"] not in VALID_KINDS:
        raise DefinitionError(f"{path}: invalid kind {front_matter['kind']!r}")
    return {**front_matter, "body": text[end + len("\n---"):].strip()}
