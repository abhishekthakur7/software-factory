"""The typed recipe catalogue: schema validation and execution by id.

Commands are versioned typed recipes, never plan-authored shell. A recipe
names its executable by digest, its argument vector by typed placeholders,
and the boundaries -- working-directory role, timeout, expected exit codes,
environment-name allowlist -- a launcher must enforce; nothing here accepts
untyped free text or builds a shell command line. `load_catalogue` is the
schema validator: every required field is checked, and every literal
argument value is scanned for shell metacharacters, before any recipe can be
dispatched at all. `run` is the launcher: it re-checks the executable's
digest against what tampering could have changed since the catalogue was
loaded, resolves and bounds-checks every `path` placeholder against the
recipe's declared working-directory role, builds the child environment only
from the recipe's declared allowlist, and never invokes a shell.

Callers bind `RecipeResult` evidence to their review tuple. This module enforces
execution policy and retains output without writing database rows.
"""
import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml

from runner.fs import write_text
from runner import launcher
from runner.paths import FACTORY_DIR, REPO_ROOT

DEFAULT_CATALOGUE_PATH = FACTORY_DIR / "config" / "command-recipes.yaml"

CWD_ROLES = ("checkout", "base", "head", "scratch")
NETWORK_POLICIES = ("none", "registry")
OUTPUT_RETENTIONS = ("keep", "discard")
TEST_LEVELS = ("unit", "integration", "end_to_end")
# What a recipe checks, so the regression-only rule and the fix-round route
# can tell a lint or compile diagnostic from a test result without parsing ids.
RECIPE_KINDS = ("lint", "compile", "test", "dependency", "security", "other")
PLACEHOLDER_TYPES = ("path", "string", "int")

REQUIRED_FIELDS = (
    "id",
    "executable",
    "executable_digest",
    "args",
    "cwd_role",
    "stages",
    "timeout_seconds",
    "expected_exit_codes",
    "env_allowlist",
    "network",
    "output_retention",
    "kind",
)

# Shell interpolation ($, $(...), `...`), redirection (>, <, >>, |), and a
# literal newline (which would let one argument smuggle a second shell
# command past anything that later concatenates arguments for logging).
# Every one of these is also meaningless in a real argv entry passed with
# shell=False, so refusing them costs nothing a legitimate recipe needs.
_FORBIDDEN_CHARS = frozenset("$`|<>\n")


class RecipeError(Exception):
    """A recipe entry fails schema validation, or a run request is refused before dispatch."""


class RecipeUnavailable(RecipeError):
    """A declared recipe cannot run under the selected sandbox's admitted dependencies."""


class RecipeSandboxError(RecipeError):
    """A build child returned without the required OS policy or integrity proof."""


@dataclass(frozen=True)
class ArgPlaceholder:
    name: str
    type: str  # "path" | "string" | "int"


@dataclass(frozen=True)
class Recipe:
    id: str
    executable: Path
    executable_digest: str
    args: tuple  # each element is a literal str or an ArgPlaceholder
    cwd_role: str
    kind: str
    stages: tuple[str, ...]
    timeout_seconds: int
    expected_exit_codes: tuple[int, ...]
    env_allowlist: tuple[str, ...]
    network: str
    output_retention: str
    registry_endpoints: tuple[str, ...] = ()
    cache_policy: str | None = None
    level: str | None = None
    test_globs: tuple[str, ...] | None = None
    sandbox_inputs: tuple[tuple[str, Path], ...] = ()


@dataclass(frozen=True)
class RecipeResult:
    recipe_id: str
    outcome: str  # "pass" | "fail" | "timeout"
    exit_code: int | None
    stdout_path: Path | None
    stderr_path: Path | None
    level: str | None = None
    tests_ran: tuple | None = None
    reported_result: str | None = None


def _contains_forbidden_chars(value: str) -> bool:
    return any(ch in _FORBIDDEN_CHARS for ch in value)


def _check_forbidden(value: str, context: str) -> None:
    if _contains_forbidden_chars(value):
        raise RecipeError(f"{context} contains forbidden shell/redirection syntax: {value!r}")


def _parse_args(raw_args: object, recipe_id: str) -> tuple:
    if not isinstance(raw_args, list):
        raise RecipeError(f"recipe {recipe_id!r} has a non-list args field")
    parsed = []
    for item in raw_args:
        if isinstance(item, str):
            _check_forbidden(item, f"recipe {recipe_id!r} literal arg {item!r}")
            parsed.append(item)
        elif isinstance(item, dict):
            name, ptype = item.get("placeholder"), item.get("type")
            if not isinstance(name, str) or not name:
                raise RecipeError(f"recipe {recipe_id!r} has a placeholder with no name")
            if ptype not in PLACEHOLDER_TYPES:
                raise RecipeError(f"recipe {recipe_id!r} placeholder {name!r} has unknown type {ptype!r}")
            parsed.append(ArgPlaceholder(name=name, type=ptype))
        else:
            raise RecipeError(f"recipe {recipe_id!r} has an arg that is neither text nor a placeholder: {item!r}")
    return tuple(parsed)


def _parse_recipe(entry: object) -> Recipe:
    if not isinstance(entry, dict):
        raise RecipeError(f"recipe entry is not a mapping: {entry!r}")
    recipe_id = entry.get("id")
    if not isinstance(recipe_id, str) or not recipe_id:
        raise RecipeError(f"recipe entry has no id: {entry!r}")
    missing = [f for f in REQUIRED_FIELDS if f not in entry]
    if missing:
        raise RecipeError(f"recipe {recipe_id!r} is missing required field(s) {missing}")

    cwd_role = entry["cwd_role"]
    if cwd_role not in CWD_ROLES:
        raise RecipeError(f"recipe {recipe_id!r} has unknown cwd_role {cwd_role!r}")
    network = entry["network"]
    if network not in NETWORK_POLICIES:
        raise RecipeError(f"recipe {recipe_id!r} has unknown network policy {network!r}")
    registry_endpoints: tuple[str, ...] = ()
    cache_policy = None
    if network == "registry":
        raw_endpoints = entry.get("registry_endpoints")
        if not isinstance(raw_endpoints, list) or not raw_endpoints or not all(isinstance(item, str) and item for item in raw_endpoints):
            raise RecipeError(f"recipe {recipe_id!r} needs non-empty registry_endpoints for registry network")
        if entry.get("cache_policy") != "isolated":
            raise RecipeError(f"recipe {recipe_id!r} needs isolated cache_policy for registry network")
        registry_endpoints = tuple(raw_endpoints)
        cache_policy = "isolated"
    output_retention = entry["output_retention"]
    if output_retention not in OUTPUT_RETENTIONS:
        raise RecipeError(f"recipe {recipe_id!r} has unknown output_retention {output_retention!r}")
    kind = entry["kind"]
    if kind not in RECIPE_KINDS:
        raise RecipeError(f"recipe {recipe_id!r} has unknown kind {kind!r}")

    level, test_globs = None, None
    sandbox_inputs: tuple[tuple[str, Path], ...] = ()
    raw_inputs = entry.get("sandbox_inputs", {})
    if not isinstance(raw_inputs, dict) or not all(isinstance(name, str) and isinstance(path, str) for name, path in raw_inputs.items()):
        raise RecipeError(f"recipe {recipe_id!r} has invalid sandbox_inputs")
    resolved_inputs = []
    for name, raw_path in raw_inputs.items():
        path = (REPO_ROOT / raw_path).resolve()
        if not path.is_file() or not path.is_relative_to(REPO_ROOT):
            raise RecipeError(f"recipe {recipe_id!r} sandbox input {name!r} is not a committed file")
        resolved_inputs.append((name, path))
    sandbox_inputs = tuple(resolved_inputs)
    if "level" in entry or "test_globs" in entry:
        level = entry.get("level")
        if kind != "test":
            raise RecipeError(f"recipe {recipe_id!r} carries a test level but is of kind {kind!r}")
        if level not in TEST_LEVELS:
            raise RecipeError(f"recipe {recipe_id!r} is a test recipe with an invalid level {level!r}")
        raw_globs = entry.get("test_globs")
        if not isinstance(raw_globs, list) or not raw_globs:
            raise RecipeError(f"recipe {recipe_id!r} is a test recipe with no test_globs")
        test_globs = tuple(raw_globs)

    return Recipe(
        id=recipe_id,
        executable=Path(entry["executable"]),
        executable_digest=entry["executable_digest"],
        args=_parse_args(entry["args"], recipe_id),
        cwd_role=cwd_role,
        kind=kind,
        stages=tuple(entry["stages"]),
        timeout_seconds=int(entry["timeout_seconds"]),
        expected_exit_codes=tuple(entry["expected_exit_codes"]),
        env_allowlist=tuple(entry["env_allowlist"]),
        network=network,
        output_retention=output_retention,
        registry_endpoints=registry_endpoints,
        cache_policy=cache_policy,
        level=level,
        test_globs=test_globs,
        sandbox_inputs=sandbox_inputs,
    )


def load_catalogue(path: Path = DEFAULT_CATALOGUE_PATH) -> dict[str, Recipe]:
    """Parse and validate every recipe in `path`, keyed by id.

    Raises `RecipeError` naming the missing field on the first recipe that
    fails validation, or on a literal argument value carrying shell
    interpolation, command substitution, a redirection operator, or a
    newline.
    """
    doc = yaml.safe_load(Path(path).read_text())
    if not isinstance(doc, dict) or not isinstance(doc.get("recipes"), list):
        raise RecipeError(f"{path}: must be a mapping with a 'recipes' list")
    catalogue = {}
    for entry in doc["recipes"]:
        recipe = _parse_recipe(entry)
        catalogue[recipe.id] = recipe
    return catalogue


def _executable_digest(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _resolve_path_arg(value: str, cwd: Path, recipe_id: str, name: str) -> str:
    candidate = Path(value)
    absolute = candidate if candidate.is_absolute() else cwd / candidate
    resolved = absolute.resolve()
    if not resolved.is_relative_to(cwd):
        raise RecipeError(
            f"recipe {recipe_id!r} placeholder {name!r} resolves outside its cwd_role: {resolved}"
        )
    return str(resolved)


def _build_argv(recipe: Recipe, values: dict, cwd: Path) -> list[str]:
    argv = [str(REPO_ROOT / recipe.executable)]
    for item in recipe.args:
        if isinstance(item, str):
            argv.append(item)
            continue
        if item.name not in values:
            raise RecipeError(f"recipe {recipe.id!r} has no value for placeholder {item.name!r}")
        raw_value = values[item.name]
        if item.type == "int":
            try:
                argv.append(str(int(raw_value)))
            except (TypeError, ValueError) as exc:
                raise RecipeError(f"recipe {recipe.id!r} value for {item.name!r} is not an int: {raw_value!r}") from exc
            continue
        value_str = str(raw_value)
        _check_forbidden(value_str, f"recipe {recipe.id!r} value for {item.name!r}")
        if item.type == "path":
            argv.append(_resolve_path_arg(value_str, cwd, recipe.id, item.name))
        else:
            argv.append(value_str)
    return argv


def _build_env(recipe: Recipe, env_source: dict, env_request: tuple[str, ...]) -> dict[str, str]:
    for name in env_request:
        if name not in recipe.env_allowlist:
            raise RecipeError(f"recipe {recipe.id!r} refuses env var {name!r}: outside its allowlist")
    requested = env_request if env_request else recipe.env_allowlist
    return {name: env_source[name] for name in requested if name in env_source}


def _write_outputs(results_dir: Path, recipe_id: str, stdout: str, stderr: str, retention: str):
    if retention == "discard":
        return None, None
    stdout_path = Path(results_dir) / f"{recipe_id}.stdout.txt"
    stderr_path = Path(results_dir) / f"{recipe_id}.stderr.txt"
    write_text(stdout_path, stdout or "")
    write_text(stderr_path, stderr or "")
    return stdout_path, stderr_path


def _stage_sandbox_inputs(recipe: Recipe, sandbox_run_dir: Path) -> dict[str, str]:
    """Copy a recipe's pinned files into the launch results area before the child starts.

    The build profile can read this area but cannot write it, so a preceding
    recipe cannot replace configuration that a later control consumes.
    """
    staged = {}
    for name, source in recipe.sandbox_inputs:
        destination = Path(sandbox_run_dir) / "results" / "inputs" / source.name
        write_text(destination, source.read_text())
        staged[name] = str(destination)
    return staged


def _validate_sandbox_network(recipe: Recipe, stage: str, sandbox_path: Path) -> None:
    """Refuse a registry recipe before dispatch when its hosts are absent from that stage's proxy routes."""
    if recipe.network == "none":
        return
    document = yaml.safe_load(Path(sandbox_path).read_text()) or {}
    policy = (document.get("policies") or {}).get("enforced") or {}
    endpoints = policy.get("endpoints") or {}
    admitted = {
        (endpoints[route_id].get("host"), endpoints[route_id].get("port"))
        for route_id in (policy.get("proxy_allowlist") or {}).get(stage, [])
        if route_id in endpoints
    }
    missing = [host for host in recipe.registry_endpoints if (host, 443) not in admitted]
    if missing:
        raise RecipeUnavailable(f"recipe {recipe.id!r} requires registry endpoint(s) unavailable at {stage}: {', '.join(missing)}")


def _parse_test_identities(stdout: str):
    """The `{"ran": [...]}` JSON a test wrapper prints as its last stdout line, or `None`."""
    lines = [line for line in (stdout or "").splitlines() if line.strip()]
    if not lines:
        return None
    try:
        payload = json.loads(lines[-1])
    except json.JSONDecodeError:
        return None
    ran = payload.get("ran") if isinstance(payload, dict) else None
    if not isinstance(ran, list):
        return None
    return tuple(ran)


def _reported_result(stdout: str) -> str | None:
    lines = [line for line in (stdout or "").splitlines() if line.strip()]
    if not lines:
        return None
    try:
        result = json.loads(lines[-1]).get("result")
    except (AttributeError, json.JSONDecodeError):
        return None
    return result if result in {"pass", "fail", "blind_spot"} else None


def run(
    recipe_id: str,
    values: dict,
    *,
    catalogue: dict[str, Recipe],
    cwd_roles: dict[str, Path],
    results_dir: Path,
    env_source: dict,
    env_request: tuple[str, ...] = (),
    sandbox_run_dir: Path | None = None,
    sandbox_stage: str | None = None,
    sandbox_vendor_dir: Path | None = None,
    sandbox_path: Path = launcher.SANDBOX_PATH,
) -> RecipeResult:
    """Validate and execute `recipe_id` from `catalogue` with `values`, never a shell string.

    Refuses: an id absent from `catalogue`; a stale `executable_digest`; a
    `path` placeholder resolving outside `cwd_roles[recipe.cwd_role]`; a
    requested env var outside the recipe's `env_allowlist`. Runs with
    `shell=False`; a timeout is recorded as `outcome="timeout"` and an
    unexpected exit code as `outcome="fail"`.
    """
    if recipe_id not in catalogue:
        raise RecipeError(f"unknown recipe id: {recipe_id!r}")
    recipe = catalogue[recipe_id]

    executable_path = REPO_ROOT / recipe.executable
    actual_digest = _executable_digest(executable_path)
    if actual_digest != recipe.executable_digest:
        raise RecipeError(
            f"recipe {recipe_id!r} executable digest mismatch: "
            f"declared {recipe.executable_digest}, found {actual_digest}"
        )

    if recipe.cwd_role not in cwd_roles:
        raise RecipeError(f"recipe {recipe_id!r} needs cwd role {recipe.cwd_role!r}, not supplied")
    cwd = Path(cwd_roles[recipe.cwd_role]).resolve()

    env = _build_env(recipe, env_source, env_request)

    if sandbox_run_dir is not None:
        if sandbox_stage is None:
            raise RecipeError("sandbox_stage is required when sandbox_run_dir is set")
        if sandbox_stage not in recipe.stages:
            raise RecipeError(f"recipe {recipe.id!r} is not declared for sandbox stage {sandbox_stage}")
        _validate_sandbox_network(recipe, sandbox_stage, sandbox_path)
        values = {**values, **_stage_sandbox_inputs(recipe, Path(sandbox_run_dir))}
        argv = _build_argv(recipe, values, cwd)
        jdk_home = launcher._jdk_home(env)
        if jdk_home:
            env = {**env, "PATH": f"{Path(jdk_home) / 'bin'}:{env.get('PATH', '')}"}
        launched = launcher.launch(
            run_dir=Path(sandbox_run_dir), argv=argv, role="build", policy="enforced", cwd=cwd,
            wall_clock_seconds=recipe.timeout_seconds, stage=sandbox_stage, copy_dir=cwd,
            build_dir=cwd / "target", scratch_dir=cwd / "scratch", cache_dir=cwd / "cache", vendor_dir=sandbox_vendor_dir,
            env_source=env,
            sandbox_path=sandbox_path,
        )
        if not launched.os_policy_applied:
            raise RecipeSandboxError(f"recipe {recipe.id!r} ran without an OS sandbox policy")
        if not launched.integrity.ok:
            raise RecipeSandboxError(f"recipe {recipe.id!r} failed sandbox integrity: {'; '.join(launched.integrity.violations)}")
        stdout_path, stderr_path = _write_outputs(
            results_dir, recipe_id, launched.stdout_text, launched.stderr_text, recipe.output_retention
        )
        outcome = "timeout" if launched.timed_out else "pass" if launched.exit_code in recipe.expected_exit_codes else "fail"
        return RecipeResult(
            recipe_id=recipe_id, outcome=outcome, exit_code=None if launched.timed_out else launched.exit_code,
            stdout_path=stdout_path, stderr_path=stderr_path, level=recipe.level,
            tests_ran=_parse_test_identities(launched.stdout_text) if recipe.level is not None else None,
            reported_result=_reported_result(launched.stdout_text),
        )

    argv = _build_argv(recipe, values, cwd)

    try:
        completed = subprocess.run(
            argv, cwd=cwd, env=env, shell=False,
            timeout=recipe.timeout_seconds, capture_output=True, text=True,
        )
    except subprocess.TimeoutExpired as exc:
        _write_outputs(results_dir, recipe_id, exc.stdout or "", exc.stderr or "", recipe.output_retention)
        return RecipeResult(
            recipe_id=recipe_id, outcome="timeout", exit_code=None,
            stdout_path=None, stderr_path=None, level=recipe.level,
        )

    stdout_path, stderr_path = _write_outputs(
        results_dir, recipe_id, completed.stdout, completed.stderr, recipe.output_retention
    )
    outcome = "pass" if completed.returncode in recipe.expected_exit_codes else "fail"
    tests_ran = _parse_test_identities(completed.stdout) if recipe.level is not None else None

    return RecipeResult(
        recipe_id=recipe_id,
        outcome=outcome,
        exit_code=completed.returncode,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        level=recipe.level,
        tests_ran=tests_ran,
        reported_result=_reported_result(completed.stdout),
    )
