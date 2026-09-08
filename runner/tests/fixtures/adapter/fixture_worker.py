"""A fixture runtime worker for adapter contract tests.

Prints exactly one JSON document to stdout, matching the same contract
`runner/adapters/cursor_sdk_worker.py` follows, chosen by the
`FIXTURE_ADAPTER_CASE` environment variable the launcher's allowlist lets
through -- so `runner/adapters/cursor_sdk.py` is exercised as a black box,
unable to tell this fixture apart from the real worker except by the argv
it was given. `environment_names` and `files_written` reflect this
process's own environment and the files it actually wrote, except where a
case deliberately overrides them to drive a sandbox-integrity violation.
"""
import json
import os
import sys
import time
from pathlib import Path

_BASE = {
    "provider_request_id": None, "status": "ok", "tokens_in": None, "tokens_out": None,
    "duration_ms": None, "cost": None, "currency": None, "cost_basis": None,
    "cost_settled_at": None, "reasoning_summary": None, "tool_calls": [],
}

# Every case's model_resolved matches the fixture entries' bare
# "claude-sonnet-5" model_requested exactly, except the two cases built to
# exercise a mismatch on purpose (silent_fallback: a different model
# family; error: no model at all). "settled_pinned_build" is the one case
# whose resolved model carries an immutable build suffix while still
# matching what that case's own test requests, for the replayability
# "exact" path -- every other resolved id stays bare on purpose, to keep
# "no immutable build suffix" the default and not a mismatch.
CASES: dict[str, dict] = {
    "settled": {
        **_BASE, "model_resolved": "claude-sonnet-5", "provider_request_id": "req-settled",
        "tokens_in": 1000, "tokens_out": 200, "duration_ms": 4200,
        "cost": 0.42, "currency": "USD", "cost_basis": "provider_settled",
        "cost_settled_at": "2026-09-08T00:00:00+00:00", "reasoning_summary": "did the thing",
    },
    "settled_pinned_build": {
        **_BASE, "model_resolved": "claude-sonnet-5-20260115", "provider_request_id": "req-pinned",
        "tokens_in": 1000, "tokens_out": 200, "duration_ms": 4200,
        "cost": 0.42, "currency": "USD", "cost_basis": "provider_settled",
        "cost_settled_at": "2026-09-08T00:00:00+00:00",
    },
    "runtime_estimate": {
        **_BASE, "model_resolved": "claude-sonnet-5", "provider_request_id": "req-estimate",
        "tokens_in": 500, "tokens_out": 100, "duration_ms": 1200,
        "cost": 0.05, "currency": "USD", "cost_basis": "runtime_estimate",
    },
    "price_table": {
        **_BASE, "model_resolved": "claude-sonnet-5", "provider_request_id": "req-pricetable",
        "tokens_in": 2_000_000, "tokens_out": 500_000, "duration_ms": 9000,
    },
    "null_cost": {
        **_BASE, "model_resolved": "claude-sonnet-5", "provider_request_id": "req-null",
    },
    "silent_fallback": {
        **_BASE, "model_resolved": "claude-haiku-5-20260115", "provider_request_id": "req-fallback",
        "tokens_in": 10, "tokens_out": 5, "duration_ms": 100,
    },
    "with_tool_calls": {
        **_BASE, "model_resolved": "claude-sonnet-5", "provider_request_id": "req-tools",
        "tokens_in": 300, "tokens_out": 150, "duration_ms": 800, "cost": 0.01, "currency": "USD",
        "cost_basis": "runtime_estimate",
        "tool_calls": [
            {
                "seq": 1, "tool": "read_file", "tool_version": "1", "args": {"path": "a.txt"},
                "result": "small result", "duration_ms": 5, "tokens": 12,
            },
            {
                "seq": 2, "tool": "run_command", "tool_version": "1", "args": {"cmd": "big"},
                "result": "\n".join(f"line {i}" for i in range(500)), "duration_ms": 50, "tokens": 900,
            },
        ],
    },
    "with_output": {
        **_BASE, "model_resolved": "claude-sonnet-5", "provider_request_id": "req-output",
        "tokens_in": 20, "tokens_out": 10, "duration_ms": 30,
    },
    "no_build_suffix": {
        **_BASE, "model_resolved": "claude-sonnet-5", "provider_request_id": "req-nobuild",
        "tokens_in": 1, "tokens_out": 1, "duration_ms": 1,
    },
    "environment_probe": {
        **_BASE, "model_resolved": "claude-sonnet-5", "provider_request_id": "req-envprobe",
        "tokens_in": 1, "tokens_out": 1, "duration_ms": 1,
    },
    "retention_blind_spot": {
        **_BASE, "model_resolved": "claude-sonnet-5", "provider_request_id": "req-retention",
        "tokens_in": 1, "tokens_out": 1, "duration_ms": 1,
        "retention_blind_spot": "a tool result exceeded the retention rule",
    },
    "environment_violation": {
        **_BASE, "model_resolved": "claude-sonnet-5", "provider_request_id": "req-envviolation",
        "tokens_in": 1, "tokens_out": 1, "duration_ms": 1,
        "environment_names": ["PATH", "HOME", "SECRET_LEAK"],
    },
    "path_violation": {
        **_BASE, "model_resolved": "claude-sonnet-5", "provider_request_id": "req-pathviolation",
        "tokens_in": 1, "tokens_out": 1, "duration_ms": 1,
        "files_written": ["/etc/outside-the-sandbox.txt"],
    },
    "error": {
        **_BASE, "model_resolved": None, "status": "error",
    },
}


def main() -> int:
    out_dir = Path(os.environ["FACTORY_RUN_OUT"])
    envelope_path = Path(sys.argv[1])
    envelope = json.loads(envelope_path.read_text())

    # The adoption-gate eval directory (factory/evals/adapters/cursor_sdk/)
    # supplies its own canned JSON documents on disk; when the launcher
    # passed one through, it takes priority over the named-case table
    # below so the same worker script serves both this repository's own
    # tests and an eval walk of that directory's fixtures.
    payload_path = os.environ.get("FIXTURE_ADAPTER_PAYLOAD_PATH")
    if payload_path:
        payload = json.loads(Path(payload_path).read_text())
        payload.setdefault("environment_names", sorted(os.environ))
        payload.setdefault("files_written", [str(p) for p in out_dir.rglob("*") if p.is_file()])
        payload["_envelope_stage"] = envelope.get("stage")
        print(json.dumps(payload))
        return 0

    case_name = os.environ.get("FIXTURE_ADAPTER_CASE", "settled")
    if case_name == "timeout":
        time.sleep(30)
        return 0

    payload = dict(CASES[case_name])
    if case_name == "with_output":
        (out_dir / "result.md").write_text("agent output\n")

    payload.setdefault("environment_names", sorted(os.environ))
    payload.setdefault("files_written", [str(p) for p in out_dir.rglob("*") if p.is_file()])
    # Proves the worker actually read the envelope it was given, without
    # leaking its content into any case table above.
    payload["_envelope_stage"] = envelope.get("stage")
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
