"""Trusted delivery transports and their shared interface."""
from typing import Protocol

from runner.deliverers.github import GitHubDeliverer
from runner.deliverers.slack import SlackDeliverer, SlackMCPPostTool, SlackMCPUnavailable
from runner.deliverers.stub import Receipt, RemoteRefused, StubDeliverer

__all__ = ["Deliverer", "Receipt", "RemoteRefused", "StubDeliverer", "GitHubDeliverer", "SlackDeliverer"]


class Deliverer(Protocol):
    """The shape every deliverer, stub or live, presents to the outbox worker."""

    def pr_create(self, intent, payload): ...

    def pr_update(self, intent, payload): ...

    def digest(self, intent, payload): ...

    def jira_feedback(self, intent, payload): ...
