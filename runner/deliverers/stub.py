"""Stub deliverers standing in for GitHub, Slack and Jira until a live route exists.

`StubDeliverer` is driven the way the real remote would behave closely
enough to exercise idempotency and race handling before any live
credential exists: `pr_create` refuses to open a pull request over a
branch head other than the one the intent expected to find, `pr_update`
applies the same compare-and-set check against the pull request it
already holds, and a duplicate idempotency key returns the receipt
already on file instead of touching the remote state a second time. All
state -- branch heads, pull requests, and issued receipts -- is one JSON
document per route, read at construction and rewritten through
`fs.write_text` after every change, so it survives the separate `factory`
invocations a crash-and-retry test runs across.
"""
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping

from runner import record
from runner.fs import write_text


class RemoteRefused(Exception):
    """The stub remote refuses the call: an unexpected branch head, or no such pull request."""


@dataclass(frozen=True)
class Receipt:
    """What a deliverer call returns: the remote object's identity and the content it now holds."""

    remote_identity: str
    remote_pr_identity: str | None
    remote_head_sha: str | None
    body_hash: str | None
    payload_digest: str
    idempotency_key: str
    created_at: str

    def to_json(self) -> dict:
        return asdict(self)

    @classmethod
    def from_json(cls, data: Mapping) -> "Receipt":
        return cls(**{name: data.get(name) for name in cls.__dataclass_fields__})


class StubDeliverer:
    """One route's fake remote: branch heads and pull requests kept per repository, receipts kept by key."""

    def __init__(self, state_path: Path):
        self.state_path = Path(state_path)
        self._state = self._load()

    def _load(self) -> dict:
        if self.state_path.exists():
            return json.loads(self.state_path.read_text())
        return {"repositories": {}, "receipts": {}}

    def _save(self) -> None:
        write_text(self.state_path, json.dumps(self._state, indent=2, sort_keys=True) + "\n")

    def _repo(self, repository: str) -> dict:
        return self._state["repositories"].setdefault(repository, {"branches": {}, "pull_requests": {}})

    def set_branch_head(self, repository: str, ref: str, sha: str) -> None:
        self._repo(repository)["branches"][ref] = sha
        self._save()

    def seed_pull_request(
        self, repository: str, identity: str, *, head_ref: str, target_ref: str,
        head_sha: str, body_hash: str, state: str = "open",
    ) -> None:
        self._repo(repository)["pull_requests"][identity] = {
            "head_ref": head_ref, "target_ref": target_ref, "head_sha": head_sha,
            "body_hash": body_hash, "state": state,
        }
        self._save()

    def seed_receipt(self, key: str, receipt: Receipt) -> None:
        self._state["receipts"][key] = receipt.to_json()
        self._save()

    def receipt_for_key(self, key: str) -> Receipt | None:
        data = self._state["receipts"].get(key)
        return Receipt.from_json(data) if data is not None else None

    def open_pull_request(self, repository: str, head_ref: str) -> tuple[str, dict] | None:
        """The `(identity, row)` of the open pull request against `head_ref`, or None."""
        for identity, pr in self._repo(repository)["pull_requests"].items():
            if pr["head_ref"] == head_ref and pr["state"] == "open":
                return identity, dict(pr)
        return None

    def branch_head(self, repository: str, ref: str) -> str | None:
        return self._repo(repository)["branches"].get(ref)

    def _issue_receipt(
        self, intent: Mapping, *, remote_identity: str, remote_pr_identity: str | None,
        remote_head_sha: str | None, body_hash: str | None,
    ) -> Receipt:
        receipt = Receipt(
            remote_identity=remote_identity,
            remote_pr_identity=remote_pr_identity,
            remote_head_sha=remote_head_sha,
            body_hash=body_hash,
            payload_digest=intent["payload_digest"],
            idempotency_key=intent["idempotency_key"],
            created_at=record.now(),
        )
        self._state["receipts"][intent["idempotency_key"]] = receipt.to_json()
        self._save()
        return receipt

    def pr_create(self, intent: Mapping, payload: Mapping) -> Receipt:
        existing = self.receipt_for_key(intent["idempotency_key"])
        if existing is not None:
            return existing
        repository = intent["repository"]
        branch_ref = payload["branch_ref"]
        current_head = self.branch_head(repository, branch_ref)
        expected = intent["expected_prior_remote_head_sha"]
        if current_head is not None and current_head != expected:
            raise RemoteRefused(
                f"unexpected remote head on {repository}:{branch_ref}: {current_head!r} != {expected!r}"
            )
        head_sha = payload["head_sha"]
        body_hash = intent["pr_body_hash"]
        repo_state = self._repo(repository)
        identity = f"{repository}#{len(repo_state['pull_requests']) + 1}"
        repo_state["branches"][branch_ref] = head_sha
        repo_state["pull_requests"][identity] = {
            "head_ref": branch_ref, "target_ref": payload["target_ref"], "head_sha": head_sha,
            "body_hash": body_hash, "state": "open",
        }
        return self._issue_receipt(
            intent, remote_identity=identity, remote_pr_identity=identity,
            remote_head_sha=head_sha, body_hash=body_hash,
        )

    def pr_update(self, intent: Mapping, payload: Mapping) -> Receipt:
        existing = self.receipt_for_key(intent["idempotency_key"])
        if existing is not None:
            return existing
        repository = intent["repository"]
        identity = intent["remote_pr_identity"]
        pr = self._repo(repository)["pull_requests"].get(identity)
        if pr is None:
            raise RemoteRefused(f"no such pull request: {identity!r}")
        branch_ref = payload["branch_ref"]
        current_head = self.branch_head(repository, branch_ref)
        expected = intent["expected_prior_remote_head_sha"]
        if current_head != expected:
            raise RemoteRefused(
                f"unexpected remote head on {repository}:{branch_ref}: {current_head!r} != {expected!r}"
            )
        head_sha = payload["head_sha"]
        body_hash = intent["pr_body_hash"]
        self._repo(repository)["branches"][branch_ref] = head_sha
        pr.update(head_sha=head_sha, body_hash=body_hash, target_ref=payload["target_ref"])
        return self._issue_receipt(
            intent, remote_identity=identity, remote_pr_identity=identity,
            remote_head_sha=head_sha, body_hash=body_hash,
        )

    def digest(self, intent: Mapping, payload: Mapping) -> Receipt:
        existing = self.receipt_for_key(intent["idempotency_key"])
        if existing is not None:
            return existing
        return self._issue_receipt(
            intent, remote_identity=f"digest:{intent['idempotency_key']}",
            remote_pr_identity=None, remote_head_sha=None, body_hash=None,
        )

    def jira_feedback(self, intent: Mapping, payload: Mapping) -> Receipt:
        existing = self.receipt_for_key(intent["idempotency_key"])
        if existing is not None:
            return existing
        return self._issue_receipt(
            intent, remote_identity=f"jira:{intent['idempotency_key']}",
            remote_pr_identity=None, remote_head_sha=None, body_hash=None,
        )
