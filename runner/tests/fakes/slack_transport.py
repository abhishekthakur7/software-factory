"""A recorder for the one official Slack MCP post-tool call the digest deliverer makes."""


class FakeSlackPostTool:
    def __init__(self):
        self.calls: list[tuple[dict, str]] = []

    def __call__(self, arguments: dict, credential: str) -> dict:
        self.calls.append((dict(arguments), credential))
        return {"ts": "123.456"}
