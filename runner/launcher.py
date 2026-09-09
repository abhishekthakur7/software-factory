"""The enforced sandbox: an OS-level policy, a loopback proxy, and a launcher-built environment.

`launch` is the one place a runtime adapter's worker process is started.
It builds the child's entire environment from `sandbox.yaml`'s allowlist --
starting from an empty mapping and copying in only the allowlisted names,
never the launching process's whole environment -- adds the scoped
runtime key only for the `agent` role, starts a loopback proxy scoped to
the stage's own endpoint allowlist, and wraps the child's argv under
`runner/sandbox/os_policy.py`'s Seatbelt profile for `role` whenever the
named policy carries one. `<run_dir>/out/` is where the child writes;
`<run_dir>/results/` is written only by this module, after the child has
exited, so nothing the child does can forge what the trusted runner
records about it. A sandbox-integrity check runs on every launch,
comparing what the child reported about its own environment and any files
it wrote outside `out/` against what the sandbox actually allowed; the
launcher's own `results/exit.json` separately records whether the OS
policy was actually applied, so a test or an audit never has to infer it
from the argv.
"""
import json
import os
import shutil
import signal
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

from runner.fs import write_bytes, write_text
from runner.paths import FACTORY_DIR, REPO_ROOT
from runner.sandbox import os_policy, proxy

SANDBOX_PATH = FACTORY_DIR / "config" / "sandbox.yaml"

# The environment name an agent sandbox receives the runtime key under
# when the caller names none; a runtime adapter passes its own
# (`runtime.yaml` `key_role`), since the worker's SDK reads a fixed name.
RUNTIME_KEY_ENV_NAME = "runtime_key"

# macOS's own process-spawning runtime (CoreFoundation) injects these two
# locale/encoding names into a child's environment even when `env=` names
# an explicit, complete mapping -- neither is a credential, a path, or
# anything the allowlist governs, so counting either as a leak would make
# every launch on this platform a false-positive sandbox violation.
_PLATFORM_INJECTED_NAMES = frozenset({"__CF_USER_TEXT_ENCODING", "LC_CTYPE"})


class SandboxPolicyError(Exception):
    """`sandbox.yaml` cannot be read, or names no such policy."""


@dataclass(frozen=True)
class SandboxIntegrity:
    ok: bool
    violations: tuple[str, ...]
    environment_names: tuple[str, ...]
    codegraph_started: bool


@dataclass(frozen=True)
class LaunchResult:
    run_dir: Path
    out_dir: Path
    results_dir: Path
    pid: int | None
    timed_out: bool
    exit_code: int | None
    stdout_json: dict | None
    stdout_text: str
    stderr_text: str
    integrity: SandboxIntegrity
    os_policy_applied: bool


def _load_policy(policy_name: str, *, sandbox_path: Path) -> dict:
    try:
        doc = yaml.safe_load(Path(sandbox_path).read_text())
    except OSError as exc:
        raise SandboxPolicyError(f"cannot read {sandbox_path}: {exc}") from exc
    policies = doc.get("policies", {}) if isinstance(doc, dict) else {}
    if policy_name not in policies:
        raise SandboxPolicyError(f"{sandbox_path}: no such sandbox policy {policy_name!r}")
    return policies[policy_name]


def _build_child_env(
    policy: dict, role: str, *, env_source: dict[str, str], runtime_key_value: str | None,
    runtime_key_env_name: str, out_dir: Path, tmp_dir: Path, envelope_path: Path | None, proxy_port: int,
) -> dict[str, str]:
    """The child's whole environment: only the allowlisted names, plus the injected ones every launch carries."""
    allowlist = policy.get("env_allowlist", [])
    env = {name: env_source[name] for name in allowlist if name in env_source}
    if role == "agent" and runtime_key_value is not None:
        env[runtime_key_env_name] = runtime_key_value
    env["FACTORY_RUN_OUT"] = str(out_dir)
    if envelope_path is not None:
        env["FACTORY_ENVELOPE_PATH"] = str(envelope_path)
    # Overrides whatever TMPDIR and HOME the allowlist copied from the
    # launching process: the sandbox profile grants write access only to
    # this run's own scratch directory, and the host home directory is
    # unreadable inside it -- a tool such as git treats a denied read of
    # `~/.gitconfig` as fatal, where a missing file is fine.
    env["TMPDIR"] = str(tmp_dir)
    env["HOME"] = str(tmp_dir)
    proxy_url = f"http://127.0.0.1:{proxy_port}"
    env["HTTPS_PROXY"] = proxy_url
    env["HTTP_PROXY"] = proxy_url
    env["FACTORY_PROXY_PORT"] = str(proxy_port)
    return env


def _start_codegraph(policy: dict, env: dict[str, str], cwd: Path) -> tuple[subprocess.Popen | None, bool]:
    """Start the policy's codegraph command as the child's only local server, or record that none started."""
    command = policy.get("codegraph_command")
    if not command:
        return None, False
    executable = shutil.which(command[0], path=env.get("PATH"))
    if executable is None:
        return None, False
    try:
        process = subprocess.Popen(
            [executable, *command[1:]], cwd=cwd, env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except OSError:
        return None, False
    return process, True


def _stop_codegraph(process: subprocess.Popen | None) -> None:
    if process is None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()


def _resolve_proxy_allowlist(policy: dict, stage: str | None) -> list[proxy.Endpoint]:
    endpoints = policy.get("endpoints", {})
    route_ids = policy.get("proxy_allowlist", {}).get(stage, []) if stage else []
    return [
        proxy.Endpoint(route_id=route_id, host=endpoints[route_id]["host"], port=endpoints[route_id]["port"])
        for route_id in route_ids
    ]


def stage_inputs(run_dir: Path, locations: dict) -> dict:
    """Copy every file `locations` names into `<run_dir>/inputs/` and return the same document pointing there.

    TODO (when the factory is stable): take a fresh `sandbox_mount` guard
    decision per input against the target stage's route before copying it
    in, so an artefact admitted for one stage is re-checked for the sandbox
    it is about to enter. Today an input carries only the decision of the
    crossing that created it, forwarded unchanged through the envelope;
    that forwarding is the seam the mount-time decision will replace, not
    dead plumbing.

    The agent profile grants the sandbox exactly one read-only directory
    for what the envelope names -- registered input artefacts and the
    agent, skill and rubric definitions -- because `factory/` and the
    rest of the per-ticket directory are unreadable inside it. Staging
    copies rather than links: Seatbelt resolves a symlink to its target
    before deciding, so a link would grant nothing. Each copy keeps its
    own basename under a directory named by its position, so two inputs
    with one basename never collide and a reader keying on the name
    still works; the envelope's hashes are over content, so they hold. `worktree_path`
    is a mount of its own and is left untouched. A file an agent produced
    but never registered is not in `locations`, so it is never staged and
    stays invisible to the next stage.
    """
    inputs_dir = Path(run_dir) / "inputs"
    counter = 0

    def _stage(path: str | None) -> str | None:
        nonlocal counter
        if not path:
            return path
        source = Path(path)
        destination = inputs_dir / str(counter) / source.name
        counter += 1
        write_bytes(destination, source.read_bytes())
        return str(destination)

    staged = dict(locations)
    for key in ("agent", "skill", "rubric"):
        staged[key] = _stage(locations.get(key))
    staged["shared_skills"] = [_stage(path) for path in locations.get("shared_skills", [])]
    staged["inputs"] = [{**item, "path": _stage(item.get("path"))} for item in locations.get("inputs", [])]
    return staged


def _sandbox_params(
    *, run_dir: Path, tmp_dir: Path, ticket_dir: Path | None, worktree_path: Path | None, stage: str | None,
    copy_dir: Path | None, build_dir: Path | None, scratch_dir: Path | None, cache_dir: Path | None,
    jdk_home: str | None, vendor_dir: Path | None, proxy_port: int,
) -> dict[str, str]:
    """Every named parameter either profile file's `(param ...)` calls might read, agent or build alike.

    A profile that never dereferences one of these simply never asks for
    it; passing it anyway costs nothing (`sandbox-exec` accepts an unused
    `-D` silently), so one builder covers both roles instead of branching
    on which profile is about to run.
    """
    placeholder = str(tmp_dir)
    return {
        "REPO_ROOT": str(REPO_ROOT),
        "PYTHON_ROOT": sys.base_prefix,
        "WORKTREE": str(worktree_path) if worktree_path else placeholder,
        "RUN_DIR": str(run_dir),
        "TICKET_DIR": str(ticket_dir) if ticket_dir else placeholder,
        "TMPDIR": str(tmp_dir),
        "STAGE": stage or "",
        "PROXY_PORT": str(proxy_port),
        "COPY_DIR": str(copy_dir) if copy_dir else placeholder,
        "BUILD_DIR": str(build_dir) if build_dir else placeholder,
        "SCRATCH_DIR": str(scratch_dir) if scratch_dir else placeholder,
        "CACHE_DIR": str(cache_dir) if cache_dir else placeholder,
        "JDK_HOME": jdk_home or placeholder,
        "VENDOR_DIR": str(vendor_dir) if vendor_dir else placeholder,
    }


def _check_integrity(
    *, stdout_json: dict | None, allowed_names: set[str], codegraph_started: bool,
    out_dir: Path, cwd: Path,
) -> SandboxIntegrity:
    """The child's self-reported environment and written files, checked against what the sandbox allowed.

    A worker that reports nothing (no `environment_names`/`files_written`
    keys at all) is not itself a violation -- only a reported name outside
    the allowlist, or a reported file outside `out/` and the worktree, is.
    """
    payload = stdout_json or {}
    reported_names = set(payload.get("environment_names") or [])
    reported_files = payload.get("files_written") or []
    violations: list[str] = []
    extra_names = reported_names - allowed_names
    if extra_names:
        violations.append(f"environment carried name(s) outside the allowlist: {sorted(extra_names)}")
    for file_path in reported_files:
        resolved = Path(file_path).resolve()
        if not (resolved.is_relative_to(out_dir.resolve()) or resolved.is_relative_to(cwd.resolve())):
            violations.append(f"file written outside out/ and the worktree: {file_path}")
    return SandboxIntegrity(
        ok=not violations, violations=tuple(violations),
        environment_names=tuple(sorted(reported_names)), codegraph_started=codegraph_started,
    )


def launch(
    *,
    run_dir: Path,
    argv: list[str],
    role: str,
    policy: str,
    cwd: Path,
    wall_clock_seconds: float | None,
    stage: str | None = None,
    ticket_dir: Path | None = None,
    worktree_path: Path | None = None,
    copy_dir: Path | None = None,
    build_dir: Path | None = None,
    scratch_dir: Path | None = None,
    cache_dir: Path | None = None,
    vendor_dir: Path | None = None,
    env_source: dict[str, str] | None = None,
    runtime_key_value: str | None = None,
    runtime_key_env_name: str = RUNTIME_KEY_ENV_NAME,
    envelope_path: Path | None = None,
    sandbox_path: Path = SANDBOX_PATH,
    routes: proxy.RouteService | None = None,
) -> LaunchResult:
    """Run `argv` as the sandbox child: build its environment, apply its OS policy, check its integrity.

    Creates `<run_dir>/out/` (writable from inside), `<run_dir>/tmp/`
    (the child's own scratch directory), and `<run_dir>/results/` (written
    only here, after the child exits): `results/child.pid` while the child
    runs, then `results/stdout.json`, `results/stderr.txt`, and
    `results/exit.json` (which also carries `os_policy`, whether this
    launch's argv actually ran under a Seatbelt profile). A loopback proxy
    scoped to `stage`'s own endpoint allowlist runs for the lifetime of the
    child and is stopped in `finally`, whether or not the child timed out;
    `routes` is that proxy's `POST /routes/<route_id>` dispatch table --
    every such call refuses with `404` when it is left `None`.
    `wall_clock_seconds=None` means no timeout is enforced by this call.
    The child's stdout is parsed as one JSON document (its last non-blank
    line, matching the worker contract); a non-JSON or empty stdout leaves
    `stdout_json` `None` rather than raising, since a crashed or
    misbehaving child is the caller's outcome to classify, not this
    function's to refuse.
    """
    env_source = env_source if env_source is not None else dict(os.environ)
    policy_doc = _load_policy(policy, sandbox_path=sandbox_path)
    run_dir = Path(run_dir)
    out_dir = run_dir / "out"
    results_dir = run_dir / "results"
    tmp_dir = run_dir / "tmp"
    out_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir.mkdir(parents=True, exist_ok=True)

    run_proxy = proxy.start(_resolve_proxy_allowlist(policy_doc, stage), routes)
    try:
        env = _build_child_env(
            policy_doc, role, env_source=env_source, runtime_key_value=runtime_key_value,
            runtime_key_env_name=runtime_key_env_name, out_dir=out_dir, tmp_dir=tmp_dir, envelope_path=envelope_path, proxy_port=run_proxy.port,
        )
        codegraph_process, codegraph_started = (
            _start_codegraph(policy_doc, env, cwd) if role == "agent" else (None, False)
        )

        os_policy_applied = os_policy.profile_for(role, policy_name=policy, sandbox_path=sandbox_path) is not None
        sandbox_argv = os_policy.wrap(
            argv, role=role, policy_name=policy, sandbox_path=sandbox_path,
            params=_sandbox_params(
                run_dir=run_dir, tmp_dir=tmp_dir, ticket_dir=ticket_dir, worktree_path=worktree_path, stage=stage,
                copy_dir=copy_dir, build_dir=build_dir, scratch_dir=scratch_dir, cache_dir=cache_dir,
                jdk_home=_jdk_home(env_source), vendor_dir=vendor_dir, proxy_port=run_proxy.port,
            ),
        )

        pid: int | None = None
        timed_out = False
        exit_code: int | None = None
        stdout_text = ""
        stderr_text = ""
        try:
            process = subprocess.Popen(
                sandbox_argv, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            pid = process.pid
            write_text(results_dir / "child.pid", str(pid))
            try:
                stdout_text, stderr_text = process.communicate(timeout=wall_clock_seconds)
                exit_code = process.returncode
            except subprocess.TimeoutExpired:
                process.kill()
                stdout_text, stderr_text = process.communicate()
                timed_out = True
                exit_code = process.returncode
        finally:
            _stop_codegraph(codegraph_process)
    finally:
        run_proxy.stop()

    stdout_json: dict | None = None
    stdout_lines = [line for line in stdout_text.splitlines() if line.strip()]
    if stdout_lines:
        try:
            parsed = json.loads(stdout_lines[-1])
        except json.JSONDecodeError:
            parsed = None
        stdout_json = parsed if isinstance(parsed, dict) else None

    write_text(results_dir / "stdout.json", json.dumps(stdout_json))
    write_text(results_dir / "stderr.txt", stderr_text)
    write_text(
        results_dir / "exit.json",
        json.dumps({"exit_code": exit_code, "timed_out": timed_out, "os_policy": os_policy_applied}),
    )

    integrity = _check_integrity(
        stdout_json=stdout_json, allowed_names=set(env) | _PLATFORM_INJECTED_NAMES, codegraph_started=codegraph_started,
        out_dir=out_dir, cwd=Path(cwd),
    )

    return LaunchResult(
        run_dir=run_dir, out_dir=out_dir, results_dir=results_dir, pid=pid,
        timed_out=timed_out, exit_code=exit_code, stdout_json=stdout_json, stderr_text=stderr_text,
        stdout_text=stdout_text,
        integrity=integrity, os_policy_applied=os_policy_applied,
    )


def _jdk_home(env_source: dict[str, str]) -> str | None:
    """The JDK root that contains the resolved `javac` and `java` binaries, if the recipe environment exposes one."""
    configured = env_source.get("JAVA_HOME") or env_source.get("JDK_HOME")
    if configured:
        return configured
    discovered = subprocess.run(["/usr/libexec/java_home", "-v", "17"], capture_output=True, text=True)
    if discovered.returncode == 0 and discovered.stdout.strip():
        return discovered.stdout.strip()
    javac = shutil.which("javac", path=env_source.get("PATH"))
    return str(Path(javac).resolve().parent.parent) if javac else None


def terminate_child(run_dir: Path) -> bool:
    """Kill the process `<run_dir>/results/child.pid` names, if it is still alive; return whether one was killed.

    `factory stop` calls this before finishing the run `aborted_human`, so
    a live launcher child never keeps running past the human's stop
    request. A missing pid file, or a pid that is already gone, is not an
    error -- there is simply nothing left to kill.
    """
    pid_path = Path(run_dir) / "results" / "child.pid"
    if not pid_path.exists():
        return False
    try:
        pid = int(pid_path.read_text().strip())
    except ValueError:
        return False
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return False
    except PermissionError:
        return False
    return True
