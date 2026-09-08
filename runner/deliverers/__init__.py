"""One factory function over a route's `deliverer` field: `stub` today, `live` once a real one exists.

Every route in `trust-profile.yaml` names its deliverer kind, and this is
the one place that name turns into an object the outbox worker can call --
so adding a real GitHub, Slack, or Jira deliverer later is a change to this
function and a new module beside `stub.py`, never a change to the worker
that calls `deliverer_for`.
"""
from pathlib import Path
from typing import Protocol

from runner.deliverers.stub import Receipt, RemoteRefused, StubDeliverer
from runner.trust_profile import Route

__all__ = ["Deliverer", "Receipt", "RemoteRefused", "StubDeliverer", "deliverer_for"]


class Deliverer(Protocol):
    """The shape every deliverer, stub or live, presents to the outbox worker."""

    def pr_create(self, intent, payload): ...

    def pr_update(self, intent, payload): ...

    def digest(self, intent, payload): ...

    def jira_feedback(self, intent, payload): ...


def deliverer_for(route: Route, runs_dir: Path) -> Deliverer:
    """The deliverer `route.deliverer` names.

    A stub keeps its fake remote state in one JSON file per route under
    `runs_dir/remote/`, so every call for that route across the life of a
    run reads and writes the same document. A `live` route raises
    `NotImplementedError` naming the route rather than returning anything,
    since AB is what adds real credentials and push authority.
    """
    if route.deliverer == "stub":
        return StubDeliverer(Path(runs_dir) / "remote" / f"{route.id}.json")
    if route.deliverer == "live":
        raise NotImplementedError(f"no live deliverer exists yet for route {route.id!r}")
    raise ValueError(f"unknown deliverer kind {route.deliverer!r} for route {route.id!r}")
