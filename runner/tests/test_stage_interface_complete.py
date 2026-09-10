"""The stage interface complete: the export list, API exclusivity, graduation-authority, and import-graph tests.

Every AST scan below walks real parsed source (`ast.parse`, never a
string match), so a forbidden import or literal split across lines, or
one hidden behind a line continuation, is still caught. The import-graph
scans cover `runner/`'s production modules only, `runner/tests/`
excluded: a test seeds rows and imports internal driver modules for
monkeypatching constantly (`test_stub_walk.py`'s own `from runner.stages
import checks`, for one), which is exactly the access this file's checks
narrow for the shipped surface, not for the tests that exercise it --
`test_write_barrier.py`'s own production-only scan is the same
convention. The forbidden-import and forbidden-SQL scans instead cover
every file under `factory/scripts/`, extensionless executables included:
those scripts run outside `runner/`'s own import graph entirely.
"""
import ast
import hashlib
import json
import re
from pathlib import Path

import pytest
import yaml

from runner import approvals, artefact_registry, canonical, capacity, record, run_ledger, stage_interface
from runner.db import connect
from runner.paths import FACTORY_DIR, REPO_ROOT
from runner.reviewer_sets import Slot

RUNNER_DIR = REPO_ROOT / "runner"
FACTORY_SCRIPTS_DIR = FACTORY_DIR / "scripts"
FIXTURES_DIR = Path(__file__).parent / "fixtures" / "stage_interface"

# The record-writing outcome actions: each reaches `stage_interface` only
# as an `action` argument to `act`, never as an attribute of its own.
OUTCOME_ACTIONS = ("revision", "outcome", "exposure", "coverage", "incident_event", "control_event", "disposition")

# `runner/queue.py`'s `act` imports `intake` inside its own `if kind ==
# "eligibility"` branch, deferred, because intake itself opens that queue
# item through `queue.open_item` -- a top-level import in either
# direction would be circular. The one admitted site outside
# `runner/stages/` naming a stage driver module directly.
_ADMITTED_STAGE_IMPORT = (RUNNER_DIR / "queue.py", "intake")

_FORBIDDEN_SCRIPT_BASES = ("record", "run_ledger", "outbox", "adapters")
_FORBIDDEN_SCRIPT_MODULES = tuple(f"runner.{base}" for base in _FORBIDDEN_SCRIPT_BASES)

# Matched case-sensitively against the exact shape a real SQL write takes
# (as every SQL literal already in this codebase is written): the bare
# English words "Delete", "Update", "Create" open plenty of ordinary
# docstrings and error messages, but never followed by SQL's own next
# clause keyword the way an actual statement is.
_SQL_WRITE_RE = re.compile(r"^\s*(INSERT\s+INTO|UPDATE\s+\S+\s+SET|DELETE\s+FROM|CREATE\s+TABLE|DROP\s+TABLE)\b")


@pytest.fixture
def conn(tmp_path):
    connection = connect(tmp_path / "factory.sqlite")
    yield connection
    connection.close()


def _parse(path: Path) -> ast.AST:
    return ast.parse(path.read_text(), filename=str(path))


def _imports(tree: ast.AST):
    """`(module, name, lineno)` for every import in `tree`; `name` is None for a plain `import module`."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name, None, node.lineno
        elif isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                yield node.module, alias.name, node.lineno


def _runner_production_files():
    """Every `.py` file under `runner/`, `runner/tests/` excluded."""
    for path in sorted(RUNNER_DIR.rglob("*.py")):
        if path.relative_to(RUNNER_DIR).parts[0] != "tests":
            yield path


def _stage_driver_names() -> set[str]:
    """Every `runner/stages/` module that drives a stage: every top-level `.py`
    file there except the registry (`__init__.py`) and shared helpers (`_common.py`)."""
    return {
        path.stem
        for path in (RUNNER_DIR / "stages").glob("*.py")
        if not path.stem.startswith("_")
    }


def _factory_script_files():
    """Every regular file under `factory/scripts/`: extensionless executables and shared `.py`
    modules alike, `__pycache__`'s own compiled bytecode excluded -- it is gitignored, not source."""
    for path in sorted(FACTORY_SCRIPTS_DIR.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts:
            yield path


# The export list


def test_stage_interface_exports_exactly_the_initial_operation_list():
    """`stage_interface.__all__` names exactly the Initial operation
    catalogue, each a real attribute of the module; the Later operations `sync_pr_head`,
    `score`, `proposal`, and `benchmark` are absent."""
    expected = yaml.safe_load((FIXTURES_DIR / "export_list.yaml").read_text())["operations"]
    assert list(stage_interface.__all__) == expected
    for name in expected:
        assert callable(getattr(stage_interface, name, None)), f"stage_interface.{name} is not a callable export"
    for later_operation in ("sync_pr_head", "score", "proposal", "benchmark"):
        assert later_operation not in stage_interface.__all__


# The outcome actions reach the surface only through `act`


@pytest.mark.parametrize("action_name", OUTCOME_ACTIONS)
def test_must_reject_a_record_writing_outcome_action_as_its_own_stage_interface_attribute(action_name):
    """`revision`, `outcome`, `exposure`, `coverage`, `incident_event`,
    `control_event`, and `disposition` name no attribute of their own on `stage_interface`."""
    assert not hasattr(stage_interface, action_name)


# `runner/cli.py`'s own import boundary and verb mapping


def test_cli_imports_only_stage_interface_and_paths_from_runner():
    """`runner/cli.py` imports `runner.stage_interface` and nothing
    else from `runner/` but `runner.paths`."""
    violations = []
    for module, name, lineno in _imports(_parse(RUNNER_DIR / "cli.py")):
        if module == "runner":
            if name != "stage_interface":
                violations.append(f"cli.py:{lineno}: from runner import {name}")
        elif module.startswith("runner."):
            if module != "runner.paths":
                violations.append(f"cli.py:{lineno}: from {module} import {name}")
    assert violations == [], violations


def test_every_cli_verb_reaches_the_record_only_through_an_exported_stage_interface_name():
    """Every `factory` verb maps to one exported name -- `cli.py` calls
    only attributes `stage_interface.__all__` exports, or the three documented non-export
    attributes (`connect`, `target_branch`, `show_artefact`) its own composition needs."""
    permitted = set(stage_interface.__all__) | {"connect", "target_branch", "show_artefact"}
    called = {
        node.func.attr
        for node in ast.walk(_parse(RUNNER_DIR / "cli.py"))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "api"
    }
    assert called, "no api.<name>(...) call found in cli.py"
    assert called <= permitted, f"cli.py calls stage_interface attribute(s) outside its export list: {called - permitted}"


# `runner/adapters/` imported only by `runner/stages/`


def test_runner_adapters_is_imported_only_by_runner_stages_modules():
    """Only a `runner/stages/` driver module imports `runner.adapters`."""
    violations = []
    for path in _runner_production_files():
        if path.relative_to(RUNNER_DIR).parts[0] == "stages":
            continue
        for module, name, lineno in _imports(_parse(path)):
            if module == "runner.adapters" or module.startswith("runner.adapters."):
                violations.append(f"{path.relative_to(RUNNER_DIR)}:{lineno}: from {module} import {name}")
    assert violations == [], violations


# `factory/scripts/` never reaches the record directly


def _forbidden_script_import(module: str, name: str | None) -> bool:
    if name is None:
        return module in _FORBIDDEN_SCRIPT_MODULES or any(
            module.startswith(f"{forbidden}.") for forbidden in _FORBIDDEN_SCRIPT_MODULES
        )
    if module == "runner":
        return name in _FORBIDDEN_SCRIPT_BASES
    return module in _FORBIDDEN_SCRIPT_MODULES or any(
        module.startswith(f"{forbidden}.") for forbidden in _FORBIDDEN_SCRIPT_MODULES
    )


def test_no_factory_script_imports_record_run_ledger_outbox_or_adapters():
    """No file under `factory/scripts/` imports `runner.record`,
    `runner.run_ledger`, `runner.outbox`, or `runner.adapters`."""
    violations = []
    for path in _factory_script_files():
        for module, name, lineno in _imports(_parse(path)):
            if _forbidden_script_import(module, name):
                dotted = module if name is None else f"{module}.{name}"
                violations.append(f"{path.relative_to(FACTORY_SCRIPTS_DIR)}:{lineno}: {dotted}")
    assert violations == [], violations


def test_no_factory_script_writes_sql_directly():
    """No string literal under `factory/scripts/` is an `INSERT`,
    `UPDATE`, `DELETE`, `CREATE`, or `DROP` statement."""
    violations = []
    for path in _factory_script_files():
        for node in ast.walk(_parse(path)):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and _SQL_WRITE_RE.match(node.value)
            ):
                violations.append(f"{path.relative_to(FACTORY_SCRIPTS_DIR)}:{node.lineno}: {node.value!r}")
    assert violations == [], violations


# The graduation gate's write literal and its authority


def _graduation_gate_write_lines(tree: ast.AST) -> list[int]:
    """Every `record_approval(...)` call naming `gate="graduation"` -- the write, never a
    `SELECT ... WHERE gate = 'graduation'` read, which names no `record_approval` call."""
    lines = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        calls_record_approval = (
            (isinstance(func, ast.Name) and func.id == "record_approval")
            or (isinstance(func, ast.Attribute) and func.attr == "record_approval")
        )
        if not calls_record_approval:
            continue
        for keyword in node.keywords:
            if keyword.arg == "gate" and isinstance(keyword.value, ast.Constant) and keyword.value.value == "graduation":
                lines.append(node.lineno)
    return lines


def test_the_graduation_gate_write_literal_lives_in_exactly_one_module():
    """The literal `gate="graduation"` write exists in exactly one
    module, `runner/graduation.py`, reached only through `stage_interface.graduate_approve`."""
    sites: dict[Path, list[int]] = {}
    for path in _runner_production_files():
        lines = _graduation_gate_write_lines(_parse(path))
        if lines:
            sites[path] = lines
    assert list(sites) == [RUNNER_DIR / "graduation.py"], sites
    assert len(sites[RUNNER_DIR / "graduation.py"]) == 1


def test_a_non_owner_actor_s_graduation_approval_confers_no_authority_on_capacity(conn, tmp_path):
    """A seeded `approval_record` of `gate = 'graduation'` from an
    identity whose `owners.yaml` role is not `factory_owner` -- here `mallory`, who holds
    only `incident_reviewer` in the fixture owners file -- confers no authority on
    `capacity.effective_parallel_limit`, whatever role or scope the row itself claims."""
    limits_path = tmp_path / "limits.yaml"
    limits_path.write_text(yaml.safe_dump({"parallel_tickets": 3}))
    owners_path = FIXTURES_DIR / "owners.yaml"
    manifest_hash = "manifest-non-owner-1"

    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps({"passed": True, "manifest_hash": manifest_hash}))
    run_id = run_ledger.open_utility_run(conn, kind="graduation")
    artefact_id = artefact_registry.register(
        conn, ticket_id=None, utility_run_id=run_id, kind="graduation_report", path=report_path,
    )
    report_artefact = record.get(conn, "artefact", artefact_id)

    config_hash = hashlib.sha256(limits_path.read_bytes()).hexdigest()
    thresholds_hash = "thresholds-1"
    scope = {
        "config_path": capacity.CONFIG_PATH, "config_hash": config_hash,
        "thresholds_hash": thresholds_hash, "manifest_hash": manifest_hash,
    }
    subject_hash = canonical.content_hash({
        "report_content_hash": report_artefact["hash"], "thresholds_hash": thresholds_hash, "config_hash": config_hash,
    })
    slot = Slot(source_rule="factory_owner_role", role="factory_owner", owner="mallory", min_count=1)
    approvals.record_approval(
        conn, gate="graduation", subject_hash=subject_hash, slot_id=slot.slot_id,
        actor_identity="mallory", role="factory_owner", decision="approve",
        authority_policy_hash="authority-1", membership_snapshot_hash="membership-1",
        attestation_version="v1", attestation_hash="att-1",
        evidence_ids=json.dumps([artefact_id]), evidence_hashes=json.dumps([report_artefact["hash"]]),
        scope=json.dumps(scope),
    )
    conn.commit()

    limit = capacity.effective_parallel_limit(
        conn, limits_path=limits_path, manifest_hash=manifest_hash, owners_path=owners_path,
    )

    assert limit.limit == 1
    assert limit.reason == capacity.UNSIGNED_EDIT


# The `runner/stages/` boundary, both directions


def test_cli_and_stage_interface_import_nothing_under_runner_stages_except_the_registry():
    """`runner/cli.py` and `runner/stage_interface.py` import nothing
    under `runner/stages/` except the driver registry `stage_interface.run_stage` dispatches
    through -- neither file names a stage driver module directly."""
    drivers = _stage_driver_names()
    violations = []
    for path in (RUNNER_DIR / "cli.py", RUNNER_DIR / "stage_interface.py"):
        for module, name, lineno in _imports(_parse(path)):
            if module == "runner.stages" and name in drivers:
                violations.append(f"{path.name}:{lineno}: from runner.stages import {name}")
            elif module is not None and module.startswith("runner.stages.") and module.rsplit(".", 1)[-1] in drivers:
                violations.append(f"{path.name}:{lineno}: from {module} import {name}")
    assert violations == [], violations


def test_no_runner_stages_module_imports_cli_or_stage_interface():
    """No module under `runner/stages/` imports `runner.cli` or
    `runner.stage_interface`."""
    violations = []
    for path in sorted((RUNNER_DIR / "stages").rglob("*.py")):
        for module, name, lineno in _imports(_parse(path)):
            if module in ("runner.cli", "runner.stage_interface"):
                violations.append(f"{path.relative_to(RUNNER_DIR)}:{lineno}: from {module} import {name}")
            elif module == "runner" and name in ("cli", "stage_interface"):
                violations.append(f"{path.relative_to(RUNNER_DIR)}:{lineno}: from runner import {name}")
    assert violations == [], violations


def test_no_module_outside_runner_stages_imports_a_stage_driver_except_the_admitted_queue_import():
    """No module outside `runner/stages/` imports a `runner/stages/` driver module
    name other than through the registry, except the existing deferred `intake` import in
    `queue.act` (see its own comment for why: intake itself opens the item `queue.act` resolves,
    so a top-level import in either direction would be circular)."""
    drivers = _stage_driver_names()
    violations = []
    for path in _runner_production_files():
        if path.relative_to(RUNNER_DIR).parts[0] == "stages":
            continue
        for module, name, lineno in _imports(_parse(path)):
            driver = None
            if module == "runner.stages" and name in drivers:
                driver = name
            elif module is not None and module.startswith("runner.stages.") and module.rsplit(".", 1)[-1] in drivers:
                driver = module.rsplit(".", 1)[-1]
            if driver is None:
                continue
            if (path, driver) == _ADMITTED_STAGE_IMPORT:
                continue
            violations.append(f"{path.relative_to(RUNNER_DIR)}:{lineno}: {driver}")
    assert violations == [], violations
