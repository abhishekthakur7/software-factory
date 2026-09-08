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

