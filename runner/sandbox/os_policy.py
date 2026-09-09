"""OS-enforced sandboxing: which Seatbelt profile a sandbox role runs under, and how a launch applies it.

`wrap` is the one place `sandbox-exec` enters an invocation's argv; every
named parameter a profile's `(param ...)` calls read must be supplied by
the caller, since a Seatbelt profile that reads an undefined parameter
raises rather than treating it as absent. `available()` proves the agent
profile can actually run a real command on this host -- the escape suite
fails outright, never skips, when it cannot (`test_escape_suite.py`
imports this module and calls it at collection time).
"""
import hashlib
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

from runner.paths import FACTORY_DIR, REPO_ROOT

SANDBOX_PATH = FACTORY_DIR / "config" / "sandbox.yaml"
SANDBOX_EXEC = "/usr/bin/sandbox-exec"
ROLES: tuple[str, ...] = ("agent", "build")

# How many registered-artefact paths the agent profile mounts by name
# (`INPUT_0`..`INPUT_{N-1}`): a fixed count, since a Seatbelt profile names
# its params statically rather than looping over an arbitrary list.
# `agent-profile.sb` defines exactly this many `input-N` params, so a
# caller that changes this constant must also edit the profile (and
# `sandbox.yaml`'s digest) to match.
REGISTERED_INPUT_SLOTS = 8


class OSPolicyError(Exception):
    """The named sandbox policy carries no os_profiles entry, or no entry for the given role."""


class MountParamError(OSPolicyError):
    """A sandbox mount parameter resolves to a path this profile must never grant."""


# Every param name a caller uses to name a directory the profile mounts
# (grants read or write access to) rather than an interpreter root, a
# stage label, or a port number. `wrap` checks only these against the
# host's own home directory: REPO_ROOT/PYTHON_ROOT/JDK_HOME legitimately
# sit outside a run's own tree, so a blanket check over every param would
# refuse an ordinary launch, not just a hidden one.
_MOUNT_PARAM_NAMES: frozenset[str] = frozenset({
    "TICKET_DIR", "WORKTREE", "RUN_DIR", "TMPDIR",
    "COPY_DIR", "BUILD_DIR", "SCRATCH_DIR", "CACHE_DIR",
})


def _policy(policy_name: str, *, sandbox_path: Path) -> dict:
    doc = yaml.safe_load(Path(sandbox_path).read_text())
    policies = doc.get("policies", {}) if isinstance(doc, dict) else {}
    if policy_name not in policies:
        raise OSPolicyError(f"{sandbox_path}: no such sandbox policy {policy_name!r}")
    return policies[policy_name]


def profile_for(role: str, *, policy_name: str = "enforced", sandbox_path: Path = SANDBOX_PATH) -> Path | None:
    """The Seatbelt profile `role` runs under, or None when this policy names no os_profiles at all.

    A policy with no `os_profiles` key is the one sandbox this milestone
    still allows without OS enforcement -- no flag or environment name
    disables it on a policy that does name one.
    """
    if role not in ROLES:
        raise OSPolicyError(f"unknown sandbox role: {role!r}")
    policy = _policy(policy_name, sandbox_path=sandbox_path)
    os_profiles = policy.get("os_profiles")
    if not os_profiles:
        return None
    entry = os_profiles.get(role)
    if entry is None:
        raise OSPolicyError(f"{sandbox_path}: policy {policy_name!r} names no os_profiles.{role}")
    return (REPO_ROOT / entry["path"]).resolve()


def digest(path: Path) -> str:
    """sha256 of `path`'s bytes; compared against `sandbox.yaml`'s own declared digest for the same file."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _refuse_home_mount(params: dict[str, str]) -> None:
    """Raise when a mount param resolves to the host's own home directory -- an extra mount hidden in plain sight.

    A legitimate run never sets `TICKET_DIR`/`WORKTREE`/`RUN_DIR`/etc to
    `$HOME` itself; every real caller derives these from `RUNS_DIR` or a
    checkout under it, so this check costs nothing on any real launch and
    closes the one concrete leak a corrupted or hostile param set could
    hand to `sandbox-exec` before it becomes a granted mount.
    """
    home = Path.home().resolve()
    for name in _MOUNT_PARAM_NAMES:
        value = params.get(name)
        if not value:
            continue
        if Path(value).resolve() == home:
            raise MountParamError(f"sandbox param {name!r} resolves to the host home directory: refused")


def wrap(
    argv: list[str], *, role: str, params: dict[str, str], policy_name: str = "enforced",
    sandbox_path: Path = SANDBOX_PATH,
) -> list[str]:
    """`argv`, wrapped to run under `role`'s Seatbelt profile; unchanged when this policy names no OS profile."""
    profile_path = profile_for(role, policy_name=policy_name, sandbox_path=sandbox_path)
    if profile_path is None:
        return list(argv)
    _refuse_home_mount(params)
    defines: list[str] = []
    for name, value in params.items():
        defines += ["-D", f"{name}={value}"]
    return [SANDBOX_EXEC, "-f", str(profile_path), *defines, *argv]


def _throwaway_params(scratch: str) -> dict[str, str]:
    params = {
        "REPO_ROOT": str(REPO_ROOT), "PYTHON_ROOT": sys.base_prefix, "WORKTREE": scratch,
        "RUN_DIR": scratch, "TICKET_DIR": scratch, "TMPDIR": scratch, "STAGE": "S0", "PROXY_PORT": "0",
    }
    params.update({f"INPUT_{i}": scratch for i in range(REGISTERED_INPUT_SLOTS)})
    return params


def available(*, policy_name: str = "enforced", sandbox_path: Path = SANDBOX_PATH) -> bool:
    """Whether `sandbox-exec` exists and can run `/usr/bin/true` under the agent profile, on this host, right now."""
    if not Path(SANDBOX_EXEC).exists():
        return False
    try:
        profile_path = profile_for("agent", policy_name=policy_name, sandbox_path=sandbox_path)
    except OSPolicyError:
        return False
    if profile_path is None or not profile_path.is_file():
        return False
    with tempfile.TemporaryDirectory() as scratch:
        argv = wrap(
            ["/usr/bin/true"], role="agent", params=_throwaway_params(scratch),
            policy_name=policy_name, sandbox_path=sandbox_path,
        )
        result = subprocess.run(argv, capture_output=True)
    return result.returncode == 0
