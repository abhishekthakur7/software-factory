"""Suite-wide fixture runtime: every agent invocation in the tests runs the fixture worker, never the Cursor SDK.

The adapter resolves its runtime, pricing, limits and sandbox paths at
call time from module constants, so patching two constants here points
every stage driver that reaches `stages.invoke_agent` -- through
`run_stage`, `cli.advance`, or a walk -- at `fixtures/adapter/
fixture_worker.py` under the test sandbox policy. A test that wants a
specific worker behaviour sets `FIXTURE_ADAPTER_CASE` (a canned stdout
document) or `FIXTURE_ADAPTER_OUT_DIR` (a canned `out/` tree the worker
copies, standing in for what the agent wrote) in its own environment;
both names pass the test sandbox's allowlist. Tests that pass explicit
paths to `cursor_sdk.invoke` are unaffected, since an explicit argument
wins over the patched default. Session-scoped, because a module-scoped
fixture (the stub walk) runs before any function-scoped autouse fixture
and would otherwise reach the real Cursor SDK worker.
"""
import sys
from pathlib import Path

import pytest
import yaml

from runner import envelope, launcher
from runner.adapters import cursor_sdk

ADAPTER_FIXTURES = Path(__file__).parent / "fixtures" / "adapter"


@pytest.fixture(autouse=True, scope="session")
def fixture_runtime(tmp_path_factory):
    doc = yaml.safe_load((ADAPTER_FIXTURES / "runtime.yaml").read_text())
    doc["adapters"]["cursor_sdk"]["command"] = [sys.executable, str(ADAPTER_FIXTURES / "fixture_worker.py")]
    runtime_path = tmp_path_factory.mktemp("runtime") / "runtime.yaml"
    runtime_path.write_text(yaml.safe_dump(doc))
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(cursor_sdk, "RUNTIME_PATH", runtime_path)
        patch.setattr(launcher, "SANDBOX_PATH", ADAPTER_FIXTURES / "sandbox.yaml")
        patch.setattr(envelope, "SANDBOX_PATH", ADAPTER_FIXTURES / "sandbox.yaml")
        for name in ("FIXTURE_ADAPTER_CASE", "FIXTURE_ADAPTER_OUT_DIR", "FIXTURE_ADAPTER_PAYLOAD_PATH"):
            patch.delenv(name, raising=False)
        yield


@pytest.fixture(autouse=True, scope="session")
def red_route_stub():
    """A minimal stand-in for `runner.checks.red_route`, built alongside the S5 driver
    by a ticket that runs in parallel with it: `S5.py` imports `classify`,
    `RecipeOutcome`, and `CheckOutcome` from there only at its one red-aggregation
    call site, so any test whose seeded S5 pass ends red needs something importable
    there until that module lands. Routes every red result to `red_check` -- the
    conservative default a human always sees -- since this stand-in carries none of
    the real eligibility rules. Installed only when the real module is still absent,
    so this becomes an inert no-op the moment it merges.
    """
    try:
        import runner.checks.red_route as _real  # noqa: F401
        yield
        return
    except ModuleNotFoundError:
        pass

    import types
    from dataclasses import dataclass

    @dataclass(frozen=True)
    class RecipeOutcome:
        recipe_id: str
        kind: str
        level: str | None
        base: str
        head: str

    @dataclass(frozen=True)
    class CheckOutcome:
        check_name: str
        result: str

    @dataclass(frozen=True)
    class Route:
        route: str
        reason: str

    def classify(results, *, rounds_run, cap):
        del results, rounds_run, cap
        return Route(route="red_check", reason="red_route stand-in: no real eligibility rules, always a human")

    module = types.ModuleType("runner.checks.red_route")
    module.RecipeOutcome = RecipeOutcome
    module.CheckOutcome = CheckOutcome
    module.Route = Route
    module.classify = classify
    sys.modules["runner.checks.red_route"] = module
    try:
        yield
    finally:
        del sys.modules["runner.checks.red_route"]
