"""Tool results delivered through the sandbox proxy: shaping, artefact registration, and the `tool_call` row.

Most cases here drive `runner.sandbox.proxy` directly -- start one proxy
with a fake relay, POST to it over a plain `http.client` connection, and
read back the response, the stored artefact, and the `tool_call` row --
since the shaping and recording behaviour these cases prove has nothing to
do with the OS sandbox boundary itself. The boundary cases (a route call
actually dispatched from inside the sandbox, and `results/` staying
unwritable from inside it) run for real under the committed Seatbelt
profile through `runner.tests.support.launch_probe`, the way
`test_escape_suite.py` does.
"""
import hashlib
import http.client
import json
from dataclasses import dataclass
from pathlib import Path

import yaml

from runner import record, tickets
from runner.db import connect
from runner.paths import FACTORY_DIR
from runner.run_ledger import open_stage_run
from runner.sandbox import proxy
from runner.tests.support import launch_probe

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "proxy_results"
LIMITS_PATH = FACTORY_DIR / "config" / "limits.yaml"


def _inline_rule() -> dict:
    return yaml.safe_load(LIMITS_PATH.read_text())["tool_result_inline"]


@dataclass(frozen=True)
class _FakeRoute:
    """A trust-profile route needs only this much for the proxy: which credential role, if any, it admits."""

    credential_roles: tuple[str, ...] = ()


def _setup(tmp_path: Path):
    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = tickets.open_ticket(conn, title="t")
    stage_run_id = open_stage_run(conn, ticket_id=ticket_id, stage="S1")
    conn.commit()
    return conn, ticket_id, stage_run_id


def _route_service(
    *, tmp_path: Path, ticket_id: int, stage_run_id: int, relay, route_id: str = "fixture_route",
    credential_roles: tuple[str, ...] = (), run_dir: Path | None = None,
) -> proxy.RouteService:
    return proxy.RouteService(
        db_path=tmp_path / "factory.sqlite", ticket_id=ticket_id, stage_run_id=stage_run_id, stage="S1",
        run_dir=run_dir if run_dir is not None else tmp_path / "run",
        routes={route_id: _FakeRoute(credential_roles=credential_roles)},
        inline_rule=_inline_rule(), relay=relay,
    )


def _post(port: int, route_id: str, *, method: str = "call", params: dict | None = None):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    body = json.dumps({"method": method, "params": params or {}}).encode()
    try:
        connection.request("POST", f"/routes/{route_id}", body=body, headers={"Content-Type": "application/json"})
        response = connection.getresponse()
        raw = response.read()
    finally:
        connection.close()
    return response.status, (json.loads(raw) if raw else None)


def _fixed_relay(media_type: str, content: bytes):
    def relay(endpoint, credential, method, params):
        return 200, media_type, content

    return relay


def test_a_listed_route_call_reaches_the_relay_and_the_sandbox_gets_the_shaped_response(tmp_path):
    """R-I-17: a listed route is dispatched through the proxy to the fake upstream, not returned to the agent directly."""
    conn, ticket_id, stage_run_id = _setup(tmp_path)
    content = (FIXTURES_DIR / "small.txt").read_bytes()
    seen = {}

    def relay(endpoint, credential, method, params):
        seen["endpoint"] = endpoint
        seen["method"] = method
        seen["params"] = params
        return 200, "text/plain", content

    routes = _route_service(tmp_path=tmp_path, ticket_id=ticket_id, stage_run_id=stage_run_id, relay=relay)
    running = proxy.start([proxy.Endpoint(route_id="fixture_route", host="upstream.invalid", port=443)], routes)
    try:
        status, payload = _post(running.port, "fixture_route", method="probe_call", params={"a": 1})
    finally:
        running.stop()

    assert seen == {
        "endpoint": proxy.Endpoint(route_id="fixture_route", host="upstream.invalid", port=443),
        "method": "probe_call", "params": {"a": 1},
    }
    assert status == 200
    assert payload["exit_status"] == 200
    assert payload["inline"] is True
    assert payload["excerpt"] == content.decode()


def test_a_route_id_outside_the_stage_allowlist_is_refused_with_403(tmp_path):
    conn, ticket_id, stage_run_id = _setup(tmp_path)
    routes = _route_service(
        tmp_path=tmp_path, ticket_id=ticket_id, stage_run_id=stage_run_id,
        relay=_fixed_relay("text/plain", b"unreachable"),
    )
    running = proxy.start([proxy.Endpoint(route_id="fixture_route", host="upstream.invalid", port=443)], routes)
    try:
        status, payload = _post(running.port, "not_in_the_allowlist")
    finally:
        running.stop()
    assert status == 403
    assert payload is None


def test_post_refuses_with_404_when_the_launch_carries_no_route_service(tmp_path):
    """A launch with `routes=None` (every stage not wired for MCP routes) keeps every `POST` refused."""
    running = proxy.start([proxy.Endpoint(route_id="fixture_route", host="upstream.invalid", port=443)])
    try:
        status, payload = _post(running.port, "fixture_route")
    finally:
        running.stop()
    assert status == 404
    assert payload is None


def test_small_result_is_returned_inline_and_also_written_to_results(tmp_path):
    """R-I-17: a small result is inline and also lands in results/ with matching tool_call fields."""
    conn, ticket_id, stage_run_id = _setup(tmp_path)
    content = (FIXTURES_DIR / "small.txt").read_bytes()
    routes = _route_service(
        tmp_path=tmp_path, ticket_id=ticket_id, stage_run_id=stage_run_id,
        relay=_fixed_relay("text/plain", content),
    )
    running = proxy.start([proxy.Endpoint(route_id="fixture_route", host="upstream.invalid", port=443)], routes)
    try:
        status, payload = _post(running.port, "fixture_route")
    finally:
        running.stop()

    assert status == 200
    assert payload["inline"] is True
    assert payload["result_bytes"] == len(content)
    assert payload["excerpt"] == content.decode()
    assert payload["digest"] == hashlib.sha256(content).hexdigest()
    artefact_path = Path(payload["artefact_path"])
    assert artefact_path.read_bytes() == content

    row = conn.execute("SELECT * FROM tool_call WHERE stage_run_id = ?", (stage_run_id,)).fetchone()
    assert row["tool"] == "fixture_route"
    assert row["inline"] == 1
    assert row["result_bytes"] == len(content)
    artefact = record.get(conn, "artefact", row["result_artefact"])
    assert Path(artefact["path"]) == artefact_path.resolve()


def test_large_text_result_is_excerpted_and_the_stored_artefact_is_never_truncated(tmp_path):
    """R-I-17: a large text result is excerpted head-and-tail, and the stored artefact keeps every byte."""
    conn, ticket_id, stage_run_id = _setup(tmp_path)
    content = (FIXTURES_DIR / "large.txt").read_bytes()
    routes = _route_service(
        tmp_path=tmp_path, ticket_id=ticket_id, stage_run_id=stage_run_id,
        relay=_fixed_relay("text/plain", content),
    )
    running = proxy.start([proxy.Endpoint(route_id="fixture_route", host="upstream.invalid", port=443)], routes)
    try:
        status, payload = _post(running.port, "fixture_route")
    finally:
        running.stop()

    assert payload["inline"] is False
    assert payload["result_bytes"] == len(content)
    assert "line 000" in payload["excerpt"]
    assert "line 499" in payload["excerpt"]
    assert "line 200" not in payload["excerpt"]  # middle of the file, dropped by the head/tail excerpt
    artefact_path = Path(payload["artefact_path"])
    assert artefact_path.read_bytes() == content  # never truncated, unlike the excerpt

    row = conn.execute("SELECT * FROM tool_call WHERE stage_run_id = ?", (stage_run_id,)).fetchone()
    assert row["inline"] == 0
    assert row["result_bytes"] == len(content)


def test_one_line_oversized_result_is_stored_but_returns_no_inline_payload(tmp_path):
    """R-I-17: an oversized result with no line break has no head/tail split, so it is stored but carries no excerpt."""
    conn, ticket_id, stage_run_id = _setup(tmp_path)
    content = (FIXTURES_DIR / "one_line_oversized.txt").read_bytes()
    routes = _route_service(
        tmp_path=tmp_path, ticket_id=ticket_id, stage_run_id=stage_run_id,
        relay=_fixed_relay("text/plain", content),
    )
    running = proxy.start([proxy.Endpoint(route_id="fixture_route", host="upstream.invalid", port=443)], routes)
    try:
        status, payload = _post(running.port, "fixture_route")
    finally:
        running.stop()

    assert payload["inline"] is False
    assert payload["excerpt"] is None
    assert payload["result_bytes"] == len(content)
    assert Path(payload["artefact_path"]).read_bytes() == content

    row = conn.execute("SELECT * FROM tool_call WHERE stage_run_id = ?", (stage_run_id,)).fetchone()
    assert row["inline"] == 0


def test_non_text_result_is_represented_by_size_media_type_and_digest_only(tmp_path):
    """R-I-17: a non-text result carries no excerpt regardless of size, only size, media type, and digest."""
    conn, ticket_id, stage_run_id = _setup(tmp_path)
    content = (FIXTURES_DIR / "binary.bin").read_bytes()
    routes = _route_service(
        tmp_path=tmp_path, ticket_id=ticket_id, stage_run_id=stage_run_id,
        relay=_fixed_relay("application/octet-stream", content),
    )
    running = proxy.start([proxy.Endpoint(route_id="fixture_route", host="upstream.invalid", port=443)], routes)
    try:
        status, payload = _post(running.port, "fixture_route")
    finally:
        running.stop()

    assert payload["inline"] is False
    assert payload["excerpt"] is None
    assert payload["media_type"] == "application/octet-stream"
    assert payload["result_bytes"] == len(content)
    assert payload["digest"] == hashlib.sha256(content).hexdigest()
    assert Path(payload["artefact_path"]).read_bytes() == content

    row = conn.execute("SELECT * FROM tool_call WHERE stage_run_id = ?", (stage_run_id,)).fetchone()
    assert row["inline"] == 0
    assert row["result_bytes"] == len(content)


def test_the_seq_counter_continues_from_the_runs_existing_max_seq(tmp_path):
    """The proxy shares one sequence with any calls the adapter already recorded directly, via `MAX(seq)`."""
    conn, ticket_id, stage_run_id = _setup(tmp_path)
    record.insert(
        conn, "tool_call", stage_run_id=stage_run_id, seq=5, tool="direct_call", args_digest=None,
        result_digest=None, result_artefact=None, duration_ms=None, tokens=None, result_bytes=10, inline=1,
    )
    conn.commit()
    content = (FIXTURES_DIR / "small.txt").read_bytes()
    routes = _route_service(
        tmp_path=tmp_path, ticket_id=ticket_id, stage_run_id=stage_run_id,
        relay=_fixed_relay("text/plain", content),
    )
    running = proxy.start([proxy.Endpoint(route_id="fixture_route", host="upstream.invalid", port=443)], routes)
    try:
        _post(running.port, "fixture_route")
    finally:
        running.stop()

    rows = conn.execute("SELECT seq FROM tool_call WHERE stage_run_id = ? ORDER BY seq", (stage_run_id,)).fetchall()
    assert [row["seq"] for row in rows] == [5, 6]


def test_a_route_call_from_inside_the_agent_sandbox_reaches_the_relay_and_rereads_a_further_slice(tmp_path):
    """R-I-17: a route call dispatched from inside the sandbox reaches the relay; the artefact lands in results/ and rereads by path."""
    conn, ticket_id, stage_run_id = _setup(tmp_path)
    content = (FIXTURES_DIR / "large.txt").read_bytes()
    seen = {}

    def relay(endpoint, credential, method, params):
        seen["endpoint"], seen["method"] = endpoint, method
        return 200, "text/plain", content

    # `launch_probe` always launches under `tmp_path / "run"`; the route
    # service's own `run_dir` must name that same directory so the
    # artefact the proxy writes lands where the probe's launch actually ran.
    run_dir = tmp_path / "run"
    routes = proxy.RouteService(
        db_path=tmp_path / "factory.sqlite", ticket_id=ticket_id, stage_run_id=stage_run_id, stage="S1",
        run_dir=run_dir, routes={"hosted_model": _FakeRoute()}, inline_rule=_inline_rule(), relay=relay,
    )
    payload = launch_probe(
        tmp_path, FIXTURES_DIR / "route_call_probe.py", role="agent", stage="S1",
        ticket_dir=tmp_path / "ticket", extra_argv=("hosted_model", "1800", "8"), routes=routes,
    )

    assert seen["method"] == "probe_call"
    response = payload["response"]
    assert response["inline"] is False
    assert response["result_bytes"] == len(content)
    artefact_path = Path(response["artefact_path"])
    assert artefact_path.is_relative_to(run_dir / "results" / "tool_results")
    assert artefact_path.read_bytes() == content
    assert payload["further_slice"] == "line 200"  # byte 1800, past the excerpt's own head/tail bound

    row = conn.execute("SELECT * FROM tool_call WHERE stage_run_id = ?", (stage_run_id,)).fetchone()
    assert row["tool"] == "hosted_model"
    assert row["inline"] == 0


def test_a_probe_writing_into_the_results_subpath_is_refused(tmp_path):
    """R-I-17: the results subpath stays unwritable from inside the agent sandbox."""
    payload = launch_probe(
        tmp_path, FIXTURES_DIR / "write_results_probe.py", role="agent", stage="S1", ticket_dir=tmp_path / "ticket",
    )
    assert payload == {"attempted": True, "refused": True}
