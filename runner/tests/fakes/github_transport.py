"""In-memory GitHub remote shared by reader and publication tests."""
from __future__ import annotations

from typing import Mapping

from runner import canonical
from runner.deliverers.github import GitHubRemoteRefused


class FakeGitHubTransport:
    """A deterministic branch/PR remote with the callable history seam used by GitHubReader."""

    def __init__(self, *, history_by_ref: Mapping | None = None):
        self.history_by_ref = dict(history_by_ref or {})
        self.branches: dict[tuple[str, str], str] = {}
        self.pull_requests: dict[tuple[str, str], dict] = {}
        self.calls: list[tuple[str, dict]] = []

    def __call__(self, method: str, params: dict):
        self.calls.append((method, dict(params)))
        if method != "read_pull_request_history":
            raise KeyError(method)
        repository, locator = params["repository"], params["pull_request_locator"]
        return list(self.history_by_ref.get((repository, locator), self.history_by_ref.get(locator, [])))

    def branch_head(self, repository: str, ref: str) -> str | None:
        self.calls.append(("branch_head", {"repository": repository, "ref": ref}))
        return self.branches.get((repository, ref))

    def open_pull_request(self, repository: str, head_ref: str):
        self.calls.append(("open_pull_request", {"repository": repository, "head_ref": head_ref}))
        pull_request = self.pull_requests.get((repository, head_ref))
        return None if pull_request is None else (pull_request["identity"], dict(pull_request))

    def push_branch(self, repository: str, ref: str, head_sha: str, expected_head: str | None) -> None:
        self.calls.append(("push_branch", {"repository": repository, "ref": ref, "head_sha": head_sha, "expected_head": expected_head}))
        current = self.branches.get((repository, ref))
        if current is not None and current != expected_head:
            raise GitHubRemoteRefused("unexpected remote head")
        self.branches[(repository, ref)] = head_sha

    def create_pull_request(self, repository: str, *, head_ref: str, target_ref: str, body: str):
        self.calls.append(("create_pull_request", {"repository": repository, "head_ref": head_ref, "target_ref": target_ref, "body": body}))
        key = (repository, head_ref)
        if key in self.pull_requests:
            raise GitHubRemoteRefused("pull request already exists")
        identity = str(len(self.pull_requests) + 1)
        row = {
            "identity": identity, "head_sha": self.branches[key], "body_hash": canonical.content_hash({"pr_body": body}),
            "state": "open", "target_ref": target_ref, "body": body,
        }
        self.pull_requests[key] = row
        return identity, dict(row)

    def update_pull_request(self, repository: str, identity: str, *, target_ref: str, body: str):
        self.calls.append(("update_pull_request", {"repository": repository, "identity": identity, "target_ref": target_ref, "body": body}))
        row = next((row for (repo, _ref), row in self.pull_requests.items() if repo == repository and row["identity"] == identity), None)
        if row is None or row["state"] != "open":
            raise GitHubRemoteRefused("pull request is not open")
        row.update(head_sha=next(sha for (repo, ref), sha in self.branches.items() if repo == repository and self.pull_requests[(repo, ref)] is row), target_ref=target_ref, body_hash=canonical.content_hash({"pr_body": body}), body=body)
        return dict(row)

    def pull_request_body(self, repository: str, identity: str) -> Mapping:
        """The observed-outcome locator read: the remote pull request's current head SHA and body text."""
        self.calls.append(("pull_request_body", {"repository": repository, "identity": identity}))
        row = next((row for (repo, _ref), row in self.pull_requests.items() if repo == repository and row["identity"] == identity), None)
        if row is None:
            raise GitHubRemoteRefused(f"no such pull request: {repository}#{identity}")
        return {"head_sha": row["head_sha"], "body": row.get("body", "")}
