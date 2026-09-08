"""The thin sandbox: a subprocess with a launcher-built environment, an `out/`+`results/` per-run directory.

`launch` is the one place a runtime adapter's worker process is started.
It builds the child's entire environment from `sandbox.yaml`'s allowlist --
starting from an empty mapping and copying in only the allowlisted names,
never the launching process's whole environment -- adds the scoped
runtime key only for the `agent` role, and never a push URL or any other
credential. `<run_dir>/out/` is where the child writes; `<run_dir>/results/`
is written only by this module, after the child has exited, so nothing the
child does can forge what the trusted runner records about it. A
sandbox-integrity check runs on every launch, comparing what the child
reported about its own environment and any files it wrote outside
`out/` against what the sandbox actually allowed.

This is the *thin* sandbox: an OS-enforced policy, the loopback proxy, and
copy-on-write base/head copies are absent until Milestone B (R-I-14). The
environment allowlist and the `out/`/`results/` split are the whole of
this milestone's isolation.
"""
import json
import os
import shutil
import signal
import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml

from runner.fs import write_text
from runner.paths import FACTORY_DIR

SANDBOX_PATH = FACTORY_DIR / "config" / "sandbox.yaml"

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
    stderr_text: str
    integrity: SandboxIntegrity


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
    out_dir: Path, envelope_path: Path | None,
) -> dict[str, str]:
    """The child's whole environment: only the allowlisted names, plus the injected ones the role earns."""
    allowlist = policy.get("env_allowlist", [])
    env = {name: env_source[name] for name in allowlist if name in env_source}
    if role == "agent":
        key_role = policy.get("credential_roles", {}).get("agent")
        if key_role and runtime_key_value is not None:
            env[key_role] = runtime_key_value
    env["FACTORY_RUN_OUT"] = str(out_dir)
    if envelope_path is not None:
        env["FACTORY_ENVELOPE_PATH"] = str(envelope_path)
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
    env_source: dict[str, str] | None = None,
    runtime_key_value: str | None = None,
    envelope_path: Path | None = None,
    sandbox_path: Path = SANDBOX_PATH,
) -> LaunchResult:
    """Run `argv` as the sandbox child: build its environment, capture its output, check its integrity.

    Creates `<run_dir>/out/` (writable from inside) and `<run_dir>/results/`
    (written only here, after the child exits): `results/child.pid` while
    the child runs, then `results/stdout.json`, `results/stderr.txt`, and
    `results/exit.json`. `wall_clock_seconds=None` means no timeout is
    enforced by this call. The child's stdout is parsed as one JSON
    document (its last non-blank line, matching the worker contract); a
    non-JSON or empty stdout leaves `stdout_json` `None` rather than
    raising, since a crashed or misbehaving child is the caller's outcome
    to classify, not this function's to refuse.
    """
    env_source = env_source if env_source is not None else dict(os.environ)
    policy_doc = _load_policy(policy, sandbox_path=sandbox_path)
    run_dir = Path(run_dir)
    out_dir = run_dir / "out"
    results_dir = run_dir / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)

    env = _build_child_env(
        policy_doc, role, env_source=env_source, runtime_key_value=runtime_key_value,
        out_dir=out_dir, envelope_path=envelope_path,
    )
    codegraph_process, codegraph_started = (
        _start_codegraph(policy_doc, env, cwd) if role == "agent" else (None, False)
    )

    pid: int | None = None
    timed_out = False
    exit_code: int | None = None
    stdout_text = ""
    stderr_text = ""
    try:
        process = subprocess.Popen(
            argv, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
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
    write_text(results_dir / "exit.json", json.dumps({"exit_code": exit_code, "timed_out": timed_out}))

    integrity = _check_integrity(
        stdout_json=stdout_json, allowed_names=set(env) | _PLATFORM_INJECTED_NAMES, codegraph_started=codegraph_started,
        out_dir=out_dir, cwd=Path(cwd),
    )

    return LaunchResult(
        run_dir=run_dir, out_dir=out_dir, results_dir=results_dir, pid=pid,
        timed_out=timed_out, exit_code=exit_code, stdout_json=stdout_json, stderr_text=stderr_text,
        integrity=integrity,
    )


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
