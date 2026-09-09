"""Credentials by role, fetched from the macOS Keychain at the moment of use and never stored.

Every external credential the factory holds is a Keychain generic-password
item under one service name, keyed by its role. The trusted runner fetches
a value through the `security` command exactly when a call needs it and
hands it to that call alone: no row, artefact, log or build-sandbox
environment ever receives a value, and the runtime key reaches an agent
sandbox only by the launcher's own environment injection. The role names
here are the closed set every route's `credential_role` and the manifest's
per-stage admission list are validated against.
"""
import subprocess

SERVICE_NAME = "soft-factory"

SLACK_DIGEST_ROLE = "slack_digest"
ROLES: tuple[str, ...] = ("runtime_key", "atlassian_read", "github_publish", SLACK_DIGEST_ROLE)


class CredentialUnavailable(Exception):
    """The role is unknown, or the Keychain holds no item for it on this host."""


def _command(role: str) -> list[str]:
    return ["security", "find-generic-password", "-s", SERVICE_NAME, "-a", role, "-w"]


def fetch(role: str, *, run=subprocess.run) -> str:
    """The Keychain value for `role`, read now; raises `CredentialUnavailable` rather than returning an empty value.

    `run` is `subprocess.run` in production and an injected fake in tests,
    so the suite never touches a real Keychain. The value is returned to
    the caller only; this function neither logs nor caches it.
    """
    if role not in ROLES:
        raise CredentialUnavailable(f"unknown credential role {role!r}")
    result = run(_command(role), capture_output=True, text=True)
    if result.returncode != 0 or not result.stdout.strip():
        raise CredentialUnavailable(f"no Keychain item for role {role!r} under service {SERVICE_NAME!r}")
    return result.stdout.strip()


def available(role: str, *, run=subprocess.run) -> bool:
    """Whether `fetch(role)` would succeed on this host, for a test that must skip loudly without the real item."""
    try:
        fetch(role, run=run)
    except CredentialUnavailable:
        return False
    return True
