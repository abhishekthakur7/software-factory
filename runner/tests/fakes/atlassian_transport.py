"""A fake Atlassian transport: an in-memory issue map, no network, no credential.

Drives `runner.readers.atlassian.AtlassianReader` in the routine test
suite exactly the way `HttpTransport` would, but every call is answered
from `issues` and recorded for a test to assert against.
"""


class FakeAtlassianTransport:
    def __init__(self, issues: dict[str, dict], *, completed: list[dict] | None = None, histories: dict[str, dict] | None = None, confluence_histories: dict[str, dict] | None = None):
        self._issues = issues
        self._completed = completed or []
        self._histories = histories or {}
        self._confluence_histories = confluence_histories or {}
        self.calls: list[tuple[str, dict]] = []

    def __call__(self, method: str, params: dict) -> dict:
        self.calls.append((method, dict(params)))
        if method == "read_issue":
            return self._issues[params["key"]]
        if method == "list_completed_baseline_tickets":
            return list(self._completed)
        if method == "read_baseline_history":
            return self._histories[params["key"]]
        if method == "read_baseline_confluence_history":
            return self._confluence_histories[params["locator"]]
        raise ValueError(f"unsupported fake Atlassian method {method!r}")
