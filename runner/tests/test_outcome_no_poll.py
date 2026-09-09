"""No Initial polling: the only modules reaching the GitHub transport, and the only scheduled entry setup.py writes.

The manual outcome record's own locator read is one narrowly scoped call
through the same transport the outbox already uses for delivery -- not a
new polling surface. This scans `runner/` with `ast`, the same technique
`test_write_barrier.py` uses, so a later import that only *happens* not to
poll today cannot silently widen the surface without this test noticing.
"""
import ast

from runner.paths import REPO_ROOT

SETUP_PATH = REPO_ROOT / "runner" / "setup.py"

# The exact modules the GitHub transport (`runner.deliverers.github`) may
# be imported from: the outbox's own delivery path and the outcome
# action's own locator read.
EXPECTED_GITHUB_IMPORTERS = frozenset({"runner/outbox.py", "runner/outcome.py"})


def _imported_top_level_names(tree: ast.AST) -> set[str]:
    """Every dotted module path this file's `import`/`from ... import ...` statements name."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            prefix = "." * node.level + node.module
            names.add(prefix)
            names.update(f"{prefix}.{alias.name}" for alias in node.names)
    return names


def _imports_github_transport(names: set[str]) -> bool:
    return any(name in ("runner.deliverers.github", "runner.readers.github") for name in names)


def _runner_modules():
    runner_dir = REPO_ROOT / "runner"
    for path in sorted(runner_dir.rglob("*.py")):
        rel = path.relative_to(runner_dir)
        if rel.parts[0] == "tests":
            continue
        if rel.parts[-1] == "github.py" and rel.parts[0] in ("deliverers", "readers"):
            continue  # the transport modules themselves, not importers of it
        if rel.parts[-1] == "__init__.py":
            continue  # a package re-exporting its own submodule is not a new importer of the transport
        yield path, rel


def test_only_the_outbox_and_the_outcome_locator_read_import_the_github_transport():
    """R-H-11: no other module under `runner/` reaches GitHub at all, so nothing polls it."""
    importers = set()
    for path, rel in _runner_modules():
        names = _imported_top_level_names(ast.parse(path.read_text(), filename=str(path)))
        if _imports_github_transport(names):
            importers.add(f"runner/{rel.as_posix()}")
    assert importers == set(EXPECTED_GITHUB_IMPORTERS)


def test_setup_writes_no_scheduler_entry_but_the_digests():
    """R-H-11: `runner/setup.py` names exactly one launchd `Label`, the digest's."""
    tree = ast.parse(SETUP_PATH.read_text(), filename=str(SETUP_PATH))
    labels = [
        value.value
        for node in ast.walk(tree) if isinstance(node, ast.Dict)
        for key, value in zip(node.keys, node.values)
        if isinstance(key, ast.Constant) and key.value == "Label" and isinstance(value, ast.Constant)
    ]
    assert labels == ["com.soft-factory.digest"]
