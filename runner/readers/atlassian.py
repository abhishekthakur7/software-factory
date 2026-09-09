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
import urllib.parse
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

    def list_completed_baseline_tickets(self, service: str, cutoff: str) -> list[dict]:
        """Completed service tickets at `cutoff`, available only on the baseline route."""
        payload = self._transport("list_completed_baseline_tickets", {"service": service, "cutoff": cutoff})
        if isinstance(payload, list):
            return payload
        issues = payload.get("issues", []) if isinstance(payload, dict) else []
        mapped = {"Bug": "bug", "Story": "small_feature", "Task": "config_or_docs"}
        return [{
            "ticket_id": issue.get("key"), "title": (issue.get("fields") or {}).get("summary"),
            "status": ((issue.get("fields") or {}).get("status") or {}).get("name"),
            "completed_at": (issue.get("fields") or {}).get("resolutiondate"),
            "issue_type": ((issue.get("fields") or {}).get("issuetype") or {}).get("name"),
            "ticket_type": mapped.get(((issue.get("fields") or {}).get("issuetype") or {}).get("name")),
            "service": service, "source_locator": f"jira:{issue.get('key')}",
            "agent_assisted": "agent-assisted" in ((issue.get("fields") or {}).get("labels") or []),
        } for issue in issues]

    def read_baseline_history(self, key: str) -> dict:
        """The Jira and Confluence history associated with retrospective ticket `key`."""
        payload = self._transport("read_baseline_history", {"key": key})
        if "decisions" in payload:
            return payload
        # Jira's changelog has no canonical approved-plan signal. Preserve
        # its locator but leave that measure unavailable until an admitted
        # Confluence/design-decision reader supplies attributable evidence.
        return {"decisions": [], "source_locator": f"jira:{key}"}

    def read_baseline_confluence_history(self, locator: str) -> dict:
        """Confluence design history named by an immutable content locator."""
        return self._transport("read_baseline_confluence_history", {"locator": locator})


class HttpTransport:
    """The real Atlassian transport: one HTTP request per call, over `urllib.request`."""

    def __init__(self, base_url: str, *, credential_role: str = "atlassian_read", fetch=credentials.fetch):
        self._base_url = base_url.rstrip("/")
        self._credential_role = credential_role
        self._fetch = fetch

    def __call__(self, method: str, params: dict) -> dict:
        if method == "read_issue":
            path = f"/rest/api/2/issue/{params['key']}"
        elif method == "list_completed_baseline_tickets":
            service = str(params["service"]).replace('"', '\\"')
            cutoff = str(params["cutoff"]).replace('"', '\\"')
            jql = urllib.parse.urlencode({"jql": f'project = "{service}" AND statusCategory = Done AND resolved <= "{cutoff}"', "startAt": 0, "maxResults": 100})
            path = f"/rest/api/2/search?{jql}"
        elif method == "read_baseline_history":
            path = f"/rest/api/2/issue/{params['key']}?expand=changelog"
        elif method == "read_baseline_confluence_history":
            path = f"/wiki/rest/api/content/{urllib.parse.quote(str(params['locator']), safe='')}?expand=history"
        else:
            raise ValueError(f"unsupported Atlassian method {method!r}")
        # Fetched here, for this one request, never before and never kept:
        # the credential must not outlive the call that needed it.
        token = self._fetch(self._credential_role)
        def fetch(url):
            request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
            with urllib.request.urlopen(request) as response:
                return json.loads(response.read())
        payload = fetch(f"{self._base_url}{path}")
        if method != "list_completed_baseline_tickets":
            return payload
        issues = list(payload.get("issues") or [])
        start = int(payload.get("startAt") or 0) + len(issues)
        total = int(payload.get("total") or len(issues))
        while start < total:
            page = fetch(f"{self._base_url}/rest/api/2/search?" + urllib.parse.urlencode({"jql": f'project = "{service}" AND statusCategory = Done AND resolved <= "{cutoff}"', "startAt": start, "maxResults": 100}))
            page_issues = list(page.get("issues") or [])
            if not page_issues:
                break
            issues.extend(page_issues)
            start += len(page_issues)
        return {"issues": issues}


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
