"""A fake Atlassian transport: an in-memory issue map, no network, no credential.

Drives `runner.readers.atlassian.AtlassianReader` in the routine test
suite exactly the way `HttpTransport` would, but every call is answered
from `issues` and recorded for a test to assert against.
"""


class FakeAtlassianTransport:
    def __init__(self, issues: dict[str, dict]):
        self._issues = issues
        self.calls: list[tuple[str, dict]] = []

    def __call__(self, method: str, params: dict) -> dict:
        self.calls.append((method, dict(params)))
        return self._issues[params["key"]]
