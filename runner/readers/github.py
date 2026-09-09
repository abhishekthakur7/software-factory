"""Read pull-request history through an injectable GitHub REST transport.

The reader fetches the `github_publish` credential only inside the real
transport call and does not retain it. Routine callers inject the same
callable fake used by delivery tests, so baseline measurement exercises the
reader boundary without requiring a GitHub account.
"""
import json
import re
import urllib.parse
import urllib.request
from typing import Callable

from runner import credentials

Transport = Callable[[str, dict], object]


class GitHubReader:
    """Reads a ticket's pull-request timeline through an injected transport."""

    def __init__(self, transport: Transport):
        self._transport = transport

    def read_pull_request_history(self, repository: str, pull_request_locator: str) -> list[dict]:
        """Pull-request timeline at an immutable GitHub PR locator in `repository`."""
        return self._transport("read_pull_request_history", {"repository": repository, "pull_request_locator": pull_request_locator})


class HttpTransport:
    """GitHub REST transport for read-only pull-request timelines."""

    def __init__(self, *, base_url: str = "https://api.github.com", credential_role: str = "github_publish", fetch=credentials.fetch):
        self._base_url = base_url.rstrip("/")
        self._credential_role = credential_role
        self._fetch = fetch

    def __call__(self, method: str, params: dict) -> list[dict]:
        if method != "read_pull_request_history":
            raise ValueError(f"unsupported GitHub method {method!r}")
        repository = urllib.parse.quote(params["repository"], safe="/")
        locator = str(params["pull_request_locator"])
        match = re.search(r"(?:/pull/|#)([1-9][0-9]*)$", locator)
        if locator.isdigit():
            number = locator
        elif match:
            number = match.group(1)
        else:
            raise ValueError("pull_request_locator must identify a numeric GitHub pull request")
        token = self._fetch(self._credential_role)
        request = urllib.request.Request(
            f"{self._base_url}/repos/{repository}/issues/{number}/timeline",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
        )
        with urllib.request.urlopen(request) as response:
            payload = json.loads(response.read())
        if not isinstance(payload, list):
            raise ValueError("GitHub pull-request timeline was not a list")
        return payload
