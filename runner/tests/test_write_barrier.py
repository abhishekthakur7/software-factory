"""Write barrier: nothing at runtime writes into factory/.

The scanner parses source with `ast` rather than grepping, so it isn't
fooled by a write call split across lines or wrapped in a comment. It looks
for the raw write primitives Python offers, not for any particular caller,
because the barrier is "no module but runner/fs.py may open factory/ for
writing" -- not "these four call sites are forbidden".
"""
import ast

import pytest

from runner.fs import FactoryWriteRefused, write_text
from runner.paths import FACTORY_DIR, REPO_ROOT

# Module-level so later tickets can extend the primitive list without
# touching the walk/parse logic below.
WRITE_ATTR_CALLS = ("write_text", "write_bytes")
COPY_MOVE_CALLS = {
    ("shutil", "copy"),
    ("shutil", "copy2"),
    ("shutil", "copyfile"),
    ("shutil", "copytree"),
    ("shutil", "rmtree"),
    ("shutil", "move"),
    ("os", "rename"),
    ("os", "replace"),
}
UNSAFE_OPEN_MODE_CHARS = set("wax+")

FIXTURES_DIR = REPO_ROOT / "runner" / "tests" / "fixtures" / "write_barrier"

# One synthetic write target per event-kind fixture, matching what that
# fixture's function writes to, so the funnel is tested on the same target.
FIXTURE_TARGETS = {
    "tag.py": FACTORY_DIR / "catalogue" / "tags.md",
    "stale_index_entry.py": FACTORY_DIR / "index" / "example.md",
    "grader_failure.py": FACTORY_DIR / "rubrics" / "planning.md",
    "engineer_reading.py": FACTORY_DIR / "catalogue" / "reading_note.md",
}


def _is_unsafe_open_mode(call: ast.Call) -> bool:
    mode_node = call.args[1] if len(call.args) >= 2 else None
    if mode_node is None:
        for kw in call.keywords:
            if kw.arg == "mode":
                mode_node = kw.value
    if mode_node is None:
        return False  # open()'s default mode is "r", read-only
    if not (isinstance(mode_node, ast.Constant) and isinstance(mode_node.value, str)):
        return True  # a computed mode can't be proven read-only, so refuse it
    return any(ch in UNSAFE_OPEN_MODE_CHARS for ch in mode_node.value)


def find_write_violations(source: str, filename: str) -> list[str]:
    tree = ast.parse(source, filename=filename)
    violations = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == "open":
            if _is_unsafe_open_mode(node):
                violations.append(f"{filename}:{node.lineno}: open() with a non-read mode")
        elif isinstance(func, ast.Attribute):
            if func.attr in WRITE_ATTR_CALLS:
                violations.append(f"{filename}:{node.lineno}: .{func.attr}(...) call")
            elif isinstance(func.value, ast.Name) and (func.value.id, func.attr) in COPY_MOVE_CALLS:
                violations.append(f"{filename}:{node.lineno}: {func.value.id}.{func.attr}(...) call")
    return violations


def _runner_modules_excluding_fs_and_tests():
    runner_dir = REPO_ROOT / "runner"
    for path in sorted(runner_dir.rglob("*.py")):
        rel = path.relative_to(runner_dir)
        if rel.parts[0] == "tests":
            continue
        if rel.parts == ("fs.py",):
            continue
        yield path


def test_no_runner_module_writes_into_factory_at_runtime():
    """no runner/ module (besides fs.py) opens a
    write path, so the only route to a factory/ change is the engineer's own
    working-tree edit."""
    violations = []
    for path in _runner_modules_excluding_fs_and_tests():
        violations.extend(find_write_violations(path.read_text(), str(path)))
    assert violations == [], "raw write primitive(s) outside runner/fs.py:\n" + "\n".join(violations)


@pytest.mark.parametrize("fixture_name", sorted(FIXTURE_TARGETS))
def test_must_reject_synthetic_event_write_into_factory(fixture_name):
    """a runtime write under factory/ is refused whatever event drives it.

    Each fixture stands in for one event kind (tag, stale context-index
    entry, repeated grader failure, the engineer's own reading) attempting a
    runtime write under factory/. The same scanner that guards the runner
    modules must flag it, and runner.fs.write_text must independently refuse the
    same target -- together these are how "lands only as a git diff for the
    engineer to review" is enforced: the runtime has no write route into
    factory/, so a change there can exist only as the engineer's own
    working-tree edit.
    """
    path = FIXTURES_DIR / fixture_name
    violations = find_write_violations(path.read_text(), str(path))
    assert violations, f"{fixture_name} should have been flagged by the write-barrier scan"

    with pytest.raises(FactoryWriteRefused):
        write_text(FIXTURE_TARGETS[fixture_name], "synthetic event body")
