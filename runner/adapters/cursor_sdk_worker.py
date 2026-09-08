"""The Cursor SDK worker: the untrusted child of one agent invocation, run inside the thin sandbox.

Reads the envelope path from `argv[1]`, drives one Cursor SDK local-runtime
agent turn against the requested model, and prints exactly one JSON
document to stdout -- the parent adapter (`runner/adapters/cursor_sdk.py`)
is the only reader. Every field the runtime does not expose is printed
`null` rather than guessed. This module never opens the database, never
imports anything under `runner` except the standard library, and never
writes outside `FACTORY_RUN_OUT`: it runs inside the launcher-built
environment, not the trusted boundary, so the parent re-derives every
governed fact itself rather than trusting anything this process claims
except by cross-checking it (the sandbox-integrity check compares this
process's own reported `environment_names` and `files_written` against
what the launcher actually allowed).
"""
import json
import os
import sys
from pathlib import Path


def _read_envelope(path: str) -> dict:
    return json.loads(Path(path).read_text())


def _prompt_from_envelope(envelope: dict) -> str:
    """The concatenated body of every file the envelope names, in envelope order.

    `envelope.json` as written by `runner/envelope.py` carries only hashes
    and ids, not file bodies -- a later ticket that wires real stage
    content extends the envelope with the actual agent/skill/rubric/input
    paths this worker reads; until then, the envelope's own dict is
    itself the prompt payload, so a fixture worker and the real one agree
    on what "the envelope" means without this file needing a shape only
    the real SDK understands.
    """
    return json.dumps(envelope, sort_keys=True)


def _files_written(out_dir: Path) -> list[str]:
    return [str(path) for path in out_dir.rglob("*") if path.is_file()]


def _run(envelope: dict) -> dict:
    import cursor_sdk

    out_dir = Path(os.environ["FACTORY_RUN_OUT"])
    model_requested = envelope.get("model_requested")
    agent = cursor_sdk.Agent.create(
        model=model_requested,
        local=cursor_sdk.LocalAgentOptions(
            cwd=envelope.get("worktree_path") or str(out_dir),
            setting_sources=[],
        ),
    )
    run = agent.send(_prompt_from_envelope(envelope), cursor_sdk.SendOptions(model=model_requested))

    tool_calls = []
    for seq, event in enumerate(run.events(), start=1):
        update = event.interaction_update
        if update is None or getattr(update, "type", None) != "tool-call-completed":
            continue
        call = dict(update.tool_call)
        tool_calls.append(
            {
                "seq": seq,
                "tool": call.get("tool") or call.get("name"),
                "tool_version": call.get("tool_version"),
                "args": call.get("args") or call.get("arguments"),
                "result": call.get("result"),
                "duration_ms": call.get("duration_ms"),
                "tokens": call.get("tokens"),
            }
        )

    result = run.wait()
    usage = result.usage
    try:
        billed = agent.get_usage()
    except Exception:
        # The package README states local agents are not supported for
        # cost yet; any failure here means cost is simply unavailable,
        # never estimated by this worker.
        billed = None

    return {
        "model_resolved": result.model.id if result.model else None,
        "provider_request_id": result.id or None,
        "status": str(result.status),
        "tokens_in": usage.input_tokens if usage else None,
        "tokens_out": usage.output_tokens if usage else None,
        "duration_ms": result.duration_ms or None,
        "cost": billed.charged_cents / 100 if billed is not None else None,
        "currency": "USD" if billed is not None else None,
        "cost_basis": "provider_settled" if billed is not None else None,
        "cost_settled_at": None,
        "reasoning_summary": None,
        "tool_calls": tool_calls,
        "environment_names": sorted(os.environ),
        "files_written": _files_written(out_dir),
    }


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(json.dumps({"error": "usage: cursor_sdk_worker.py <envelope_path>"}))
        return 2
    envelope = _read_envelope(argv[1])
    try:
        payload = _run(envelope)
    except Exception as exc:
        # The worker's one contract is printing exactly one JSON document;
        # a raised exception is reported as data, in that same document,
        # never as a bare traceback the parent would have to parse.
        payload = {
            "model_resolved": None, "provider_request_id": None, "status": "error",
            "tokens_in": None, "tokens_out": None, "duration_ms": None, "cost": None,
            "currency": None, "cost_basis": None, "cost_settled_at": None,
            "reasoning_summary": None, "tool_calls": [],
            "environment_names": sorted(os.environ),
            "files_written": _files_written(Path(os.environ.get("FACTORY_RUN_OUT", "."))),
            "error": str(exc),
        }
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
