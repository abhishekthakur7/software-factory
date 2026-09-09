"""Read a Jira issue through an injectable transport, real or fake.

`AtlassianReader` never talks to a network itself: it hands `(method,
params)` to whatever `transport` callable it was built with, so the
routine test suite drives it against `runner/tests/fakes/atlassian_transport.py`
and only a dry-run ticket ever reaches `HttpTransport`. `HttpTransport`
fetches its credential inside `__call__`, for the one request that call
makes, and never stores it on `self` -- the trusted runner is the only
thing that ever holds the value, and only for as long as the request that
needed it.
"""
import json
import urllib.request
from pathlib import Path
from typing import Callable

import yaml

from runner import credentials
from runner.paths import FACTORY_DIR

DEFAULT_SANDBOX_PATH = FACTORY_DIR / "config" / "sandbox.yaml"

Transport = Callable[[str, dict], dict]


class AtlassianReader:
    """Reads Jira issues through an injectable transport."""

    def __init__(self, transport: Transport):
        self._transport = transport

    def read_issue(self, key: str) -> dict:
        """The raw issue payload `key` resolves to, exactly as the transport returns it."""
        return self._transport("read_issue", {"key": key})


class HttpTransport:
    """The real Atlassian transport: one HTTP request per call, over `urllib.request`."""

    def __init__(self, base_url: str, *, credential_role: str = "atlassian_read", fetch=credentials.fetch):
        self._base_url = base_url.rstrip("/")
        self._credential_role = credential_role
        self._fetch = fetch

    def __call__(self, method: str, params: dict) -> dict:
        if method != "read_issue":
            raise ValueError(f"unsupported Atlassian method {method!r}")
        # Fetched here, for this one request, never before and never kept:
        # the credential must not outlive the call that needed it.
        token = self._fetch(self._credential_role)
        request = urllib.request.Request(
            f"{self._base_url}/rest/api/2/issue/{params['key']}",
            headers={"Authorization": f"Bearer {token}"},
        )
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read())


def endpoint(sandbox_path: Path = DEFAULT_SANDBOX_PATH) -> str | None:
    """`https://<host>:<port>` for the `atlassian_read` route in `sandbox.yaml`'s one policy, or `None` when it names none yet.

    Walks whichever single policy `sandbox.yaml` carries rather than
    naming it, since the policy's own name belongs to `sandbox.yaml`'s
    owner, not to this reader.
    """
    doc = yaml.safe_load(Path(sandbox_path).read_text()) or {}
    for policy in (doc.get("policies") or {}).values():
        route = ((policy or {}).get("endpoints") or {}).get("atlassian_read")
        if route:
            return f"https://{route['host']}:{route['port']}"
    return None
