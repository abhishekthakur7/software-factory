"""GitHub pull-request delivery on the trusted runner side.

The outbox owns intent, approval, and retry semantics.  This module owns
only the remote compare-and-set: inspect the branch and existing pull request,
push with a lease, then create or update that pull request through GitHub's
REST API.  Credentials are fetched immediately before a live call and never
persisted by the adapter.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import sys
from pathlib import Path
from typing import Callable, Mapping, Protocol

from runner.fs import write_text
from runner import credentials, record
from runner.deliverers.stub import Receipt, RemoteRefused
from runner.paths import RUNS_DIR
from runner import canonical, project


class GitHubTransport(Protocol):
    """The remote operations needed to publish and reconcile a pull request."""

    def branch_head(self, repository: str, ref: str) -> str | None: ...
    def open_pull_request(self, repository: str, head_ref: str) -> tuple[str, Mapping] | None: ...
    def push_branch(self, repository: str, ref: str, head_sha: str, expected_head: str | None) -> None: ...
    def create_pull_request(self, repository: str, *, head_ref: str, target_ref: str, body: str) -> tuple[str, Mapping]: ...
    def update_pull_request(self, repository: str, identity: str, *, target_ref: str, body: str) -> Mapping: ...
    def pull_request_body(self, repository: str, identity: str) -> Mapping: ...


class GitHubRemoteRefused(RemoteRefused):
    """GitHub rejected a requested mutation or the remote state changed before it."""


class GitHubNonRetryable(GitHubRemoteRefused):
    """GitHub rejected authority or a control precondition; retrying cannot repair it."""


def _write_askpass_helper(directory: Path) -> Path:
    """Create an executable helper that reaches the credential script without import-path assumptions."""
    credential_script = Path(__file__).with_name("git_credential.py").resolve()
    helper = directory / "askpass.py"
    write_text(
        helper,
        f"#!{sys.executable}\n"
        "import os\n"
        "import sys\n"
        f"os.execv({sys.executable!r}, [{sys.executable!r}, {str(credential_script)!r}, *sys.argv[1:]])\n"
    )
    helper.chmod(0o700)
    return helper


class GitHubRestClient:
    """Minimal GitHub REST and git client using one short-lived publish credential."""

    api_root = "https://api.github.com"

    def __init__(self, token: str, *, remote_url: str, checkout: Path | None = None, api_root: str | None = None):
        self._token = token
        self._remote_url = remote_url
        self._checkout = Path(checkout) if checkout is not None else None
        self._api_root = (api_root or self.api_root).rstrip("/")

    def _request(self, method: str, path: str, body: Mapping | None = None):
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(
            f"{self._api_root}{path}", data=data, method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self._token}",
                "X-GitHub-Api-Version": "2022-11-28",
                **({"Content-Type": "application/json"} if data is not None else {}),
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            if exc.code in (401, 403):
                raise GitHubNonRetryable(f"GitHub {method} {path} was not authorised") from exc
            raise GitHubRemoteRefused(f"GitHub {method} {path} failed: HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise GitHubRemoteRefused(f"GitHub {method} {path} failed: {exc.reason}") from exc

    @staticmethod
    def _path_ref(ref: str) -> str:
        return urllib.parse.quote(ref, safe="/")

    def branch_head(self, repository: str, ref: str) -> str | None:
        doc = self._request("GET", f"/repos/{repository}/git/ref/heads/{self._path_ref(ref)}")
        return None if doc is None else doc["object"]["sha"]

    def open_pull_request(self, repository: str, head_ref: str) -> tuple[str, Mapping] | None:
        owner, separator, _name = repository.partition("/")
        if not separator or not owner:
            raise GitHubRemoteRefused("GitHub repository must be owner/name")
        query = urllib.parse.urlencode({"state": "all", "head": f"{owner}:{head_ref}", "per_page": 100})
        rows = self._request("GET", f"/repos/{repository}/pulls?{query}") or []
        for row in rows:
            if row.get("head", {}).get("ref") == head_ref:
                return str(row["number"]), self._pr(row)
        return None

    @staticmethod
    def _pr(row: Mapping) -> Mapping:
        return {
            "head_sha": row["head"]["sha"],
            "body_hash": canonical.content_hash({"pr_body": row.get("body") or ""}),
            "state": "merged" if row.get("merged_at") else row.get("state"),
        }

    def push_branch(self, repository: str, ref: str, head_sha: str, expected_head: str | None) -> None:
        if self._checkout is None:
            raise GitHubRemoteRefused("GitHub publish has no configured checkout for a leased push")
        full_ref = f"refs/heads/{ref}"
        lease = f"--force-with-lease={full_ref}:{expected_head or ''}"
        with tempfile.TemporaryDirectory(prefix="soft-factory-git-") as directory:
            helper = _write_askpass_helper(Path(directory))
            environment = {
                "PATH": "/usr/bin:/bin",
                "GIT_ASKPASS": str(helper),
                "GIT_TERMINAL_PROMPT": "0",
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_CONFIG_GLOBAL": os.devnull,
                "SOFT_FACTORY_GITHUB_TOKEN": self._token,
            }
            try:
                completed = subprocess.run(
                    ["git", "-c", "credential.helper=", "-c", "core.hooksPath=/dev/null", "push", self._remote_url,
                     f"{head_sha}:{full_ref}", lease], cwd=self._checkout, env=environment, capture_output=True,
                    text=True, check=False, timeout=30,
                )
            except subprocess.TimeoutExpired as exc:
                raise GitHubRemoteRefused("leased GitHub branch push timed out") from exc
        if completed.returncode != 0:
            raise GitHubRemoteRefused("leased GitHub branch push was refused")

    def create_pull_request(self, repository: str, *, head_ref: str, target_ref: str, body: str) -> tuple[str, Mapping]:
        row = self._request("POST", f"/repos/{repository}/pulls", {
            "title": head_ref, "head": head_ref, "base": target_ref, "body": body, "draft": True,
        })
        return str(row["number"]), self._pr(row)

    def update_pull_request(self, repository: str, identity: str, *, target_ref: str, body: str) -> Mapping:
        row = self._request("PATCH", f"/repos/{repository}/pulls/{identity}", {"base": target_ref, "body": body})
        return self._pr(row)

    def pull_request_body(self, repository: str, identity: str) -> Mapping:
        """The remote pull request's current head SHA and body text, for the observed-outcome locator read."""
        row = self._request("GET", f"/repos/{repository}/pulls/{identity}")
        if row is None:
            raise GitHubRemoteRefused(f"no such pull request: {repository}#{identity}")
        return {"head_sha": row["head"]["sha"], "body": row.get("body") or ""}


class GitHubDeliverer:
    """A pull-request deliverer over an injected remote client, safe for fake or live use."""

    def __init__(
        self, client: GitHubTransport | None = None, *, client_factory: Callable[[str], GitHubTransport] | None = None,
        runs_dir: Path = RUNS_DIR,
    ):
        self._client = client
        self._client_factory = client_factory
        self._runs_dir = Path(runs_dir)

    @staticmethod
    def _target(intent: Mapping, payload: Mapping) -> None:
        scratch = project.load().get("scratch_repository") or {}
        if intent["repository"] != scratch.get("name"):
            raise GitHubRemoteRefused("publication target is not the configured scratch repository")
        prefix = scratch.get("branch_prefix")
        if not isinstance(prefix, str) or not payload.get("branch_ref", "").startswith(prefix):
            raise GitHubRemoteRefused("publication branch is outside the configured scratch prefix")

    @staticmethod
    def _configured_remote(scratch: Mapping) -> str:
        """Require a canonical GitHub HTTPS remote for the named scratch repository."""
        name = scratch.get("name")
        remote = scratch.get("remote")
        if not isinstance(name, str) or name.count("/") != 1:
            raise GitHubRemoteRefused("scratch repository name must be owner/name")
        if not isinstance(remote, str) or not remote:
            raise GitHubRemoteRefused("scratch repository remote is not configured")
        expected = f"https://github.com/{name}.git"
        if remote != expected:
            raise GitHubRemoteRefused("scratch repository remote must be canonical GitHub HTTPS for its configured name")
        return remote

    def _remote(self, intent: Mapping | None = None) -> GitHubTransport:
        if self._client is not None:
            return self._client
        scratch = project.load().get("scratch_repository") or {}
        remote_url = self._configured_remote(scratch)
        token = credentials.fetch("github_publish")
        if self._client_factory is not None:
            return self._client_factory(token)
        checkout = None if intent is None or intent["ticket_id"] is None else self._runs_dir / "tickets" / str(intent["ticket_id"]) / "repo"
        return GitHubRestClient(token, remote_url=remote_url, checkout=checkout)

    def receipt_for_key(self, key: str) -> Receipt | None:
        return None

    def branch_head(self, repository: str, ref: str) -> str | None:
        return self._remote().branch_head(repository, ref)

    def open_pull_request(self, repository: str, head_ref: str) -> tuple[str, Mapping] | None:
        return self._remote().open_pull_request(repository, head_ref)

    def pull_request_body(self, repository: str, identity: str) -> Mapping:
        return self._remote().pull_request_body(repository, identity)

    @staticmethod
    def _receipt(intent: Mapping, identity: str, pull_request: Mapping) -> Receipt:
        return Receipt(
            remote_identity=identity, remote_pr_identity=identity,
            remote_head_sha=pull_request["head_sha"], body_hash=intent["pr_body_hash"],
            payload_digest=intent["payload_digest"], idempotency_key=intent["idempotency_key"], created_at=record.now(),
        )

    def pr_create(self, intent: Mapping, payload: Mapping) -> Receipt:
        self._target(intent, payload)
        remote = self._remote(intent)
        current = remote.branch_head(intent["repository"], payload["branch_ref"])
        expected = intent["expected_prior_remote_head_sha"]
        if current is not None and current != expected:
            raise GitHubRemoteRefused("unexpected remote head")
        remote.push_branch(intent["repository"], payload["branch_ref"], payload["head_sha"], expected)
        identity, pull_request = remote.create_pull_request(
            intent["repository"], head_ref=payload["branch_ref"], target_ref=payload["target_ref"], body=payload["pr_body"],
        )
        if pull_request["head_sha"] != payload["head_sha"] or pull_request["body_hash"] != intent["pr_body_hash"]:
            raise GitHubRemoteRefused("GitHub pull request does not match the approved branch or body")
        return self._receipt(intent, identity, pull_request)

    def pr_update(self, intent: Mapping, payload: Mapping) -> Receipt:
        self._target(intent, payload)
        remote = self._remote(intent)
        found = remote.open_pull_request(intent["repository"], payload["branch_ref"])
        if found is None or found[0] != intent["remote_pr_identity"]:
            raise GitHubRemoteRefused("the recorded pull request no longer exists")
        identity, pull_request = found
        if pull_request.get("state") != "open":
            raise GitHubRemoteRefused("the recorded pull request is closed or merged")
        expected = intent["expected_prior_remote_head_sha"]
        if remote.branch_head(intent["repository"], payload["branch_ref"]) != expected:
            raise GitHubRemoteRefused("unexpected remote head")
        remote.push_branch(intent["repository"], payload["branch_ref"], payload["head_sha"], expected)
        updated = remote.update_pull_request(
            intent["repository"], identity, target_ref=payload["target_ref"], body=payload["pr_body"],
        )
        if updated["head_sha"] != payload["head_sha"] or updated["body_hash"] != intent["pr_body_hash"]:
            raise GitHubRemoteRefused("GitHub pull request does not match the approved branch or body")
        return self._receipt(intent, identity, updated)
