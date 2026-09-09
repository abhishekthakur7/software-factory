"""The Cursor SDK worker: the untrusted child of one agent invocation, run inside the enforced sandbox.

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


def _read_locations(argv: list[str]) -> dict:
    """The locations document (argv[2]) naming the files behind the envelope's hashes, or `{}` when none was given."""
    return json.loads(Path(argv[2]).read_text()) if len(argv) > 2 else {}


def _prompt(envelope: dict, locations: dict) -> str:
    """The stage prompt: skill, then shared skills, then rubric, then every input artefact, each body under a path heading.

    `envelope.json` carries only hashes and ids; `locations.json`, written
    beside it by the adapter, carries the paths. The agent definition is
    not part of the prompt text: it is the runtime's own rules file,
    passed as the agent's `cwd`-independent instructions below. A named
    file that is missing is reported in the prompt rather than raised, so
    the parent classifies the run from the worker's one JSON document.
    """
    parts = [f"ticket {envelope.get('ticket_id')} stage {envelope.get('stage')}"]
    named = [locations.get("skill"), *locations.get("shared_skills", []), locations.get("rubric")]
    named += [item.get("path") for item in locations.get("inputs", [])]
    for path in named:
        if not path:
            continue
        try:
            body = Path(path).read_text()
        except OSError as exc:
            body = f"(unreadable: {exc})"
        parts.append(f"--- {path} ---\n{body}")
    return "\n\n".join(parts)


def _agent_rules(locations: dict) -> str | None:
    path = locations.get("agent")
    if not path:
        return None
    try:
        return Path(path).read_text()
    except OSError:
        return None


def _files_written(out_dir: Path) -> list[str]:
    return [str(path) for path in out_dir.rglob("*") if path.is_file()]


def _run(envelope: dict, locations: dict) -> dict:
    import cursor_sdk

    out_dir = Path(os.environ["FACTORY_RUN_OUT"])
    model_requested = envelope.get("model_requested")
    agent = cursor_sdk.Agent.create(
        model=model_requested,
        local=cursor_sdk.LocalAgentOptions(
            cwd=locations.get("worktree_path") or str(out_dir),
            setting_sources=[],
        ),
    )
    # The agent definition leads the one prompt this worker sends, since
    # the local runtime takes no separate rules file per invocation.
    rules = _agent_rules(locations)
    prompt = _prompt(envelope, locations)
    text = f"{rules}\n\n{prompt}" if rules else prompt
    run = agent.send(text, cursor_sdk.SendOptions(model=model_requested))

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
        payload = _run(envelope, _read_locations(argv))
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
