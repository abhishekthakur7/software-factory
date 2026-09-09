"""The loopback proxy: the only path out of an enforced sandbox to the network.

`start` runs one `CONNECT`-tunnelling HTTP proxy per run, in a background
thread of the trusted runner process, bound to an OS-chosen port on
`127.0.0.1`. A `CONNECT host:port` is tunnelled byte for byte only when
`(host, port)` is in the allowlist the run was given; anything else gets a
`403` and a closed connection, so a sandboxed child's Seatbelt profile can
allow `network-outbound` to the loopback address at all without that
address being a route around the endpoint allowlist.

`POST /routes/<route_id>` is the sandbox's other way out: an MCP-style
call a stage's agent hands to the trusted runner instead of reaching a
tool endpoint directly. Given a `RouteService`, the proxy relays a listed
route to its endpoint, shapes the result through `runner.tool_results.shape`,
writes the full, untruncated bytes to `<run_dir>/results/tool_results/`
as a governed `tool_result` artefact, and records one `tool_call` row --
all from the trusted runner's own thread, since the sandboxed child has no
write access to `results/` at all. Started with no `RouteService`, every
`POST` still refuses with `404`, matching a run whose stage admits no
routed tools at all.
"""
import hashlib
import http.server
import json
import socket
import sqlite3
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

from runner import artefact_registry, canonical, credentials, record, tool_results
from runner.db import connect as open_db
from runner.fs import write_bytes


@dataclass(frozen=True)
class Endpoint:
    route_id: str
    host: str
    port: int


# The artefact extension a stored result gets, by media type; anything not
# named here is opaque and lands as `.bin` -- deliberately not
# `mimetypes.guess_extension`, whose registered-type table and therefore
# its answer for a given media type varies by host.
_EXTENSION_BY_MEDIA_TYPE: dict[str, str] = {"text/plain": ".txt", "application/json": ".json"}

Relay = Callable[[Endpoint, str | None, str, dict], tuple[int, str, bytes]]


@dataclass(frozen=True)
class RouteService:
    """What the proxy needs to relay one `POST /routes/<route_id>` call and record it as governed evidence.

    Built by whatever launches the sandbox from state it already holds:
    `db_path` rather than a live connection, because the proxy runs in its
    own background thread and must never share a connection across
    threads. `routes` is keyed by route id and each value need only carry
    `credential_roles` (a trust profile's own `Route` satisfies this); a
    route id present in the stage's endpoint allowlist but absent here is
    treated the same as one absent from the allowlist -- unknown either
    way. `relay` does the actual upstream call: `live_relay` in
    production, a fake in every test that has no upstream to reach.
    """

    db_path: Path
    ticket_id: int
    stage_run_id: int
    stage: str
    run_dir: Path
    routes: Mapping[str, object]
    inline_rule: dict
    relay: Relay
    credential_fetch: Callable[[str], str] = credentials.fetch


class Proxy:
    """A running loopback proxy; `.port` is only meaningful once `start` has bound the socket."""

    def __init__(self, server: http.server.HTTPServer, thread: threading.Thread) -> None:
        self._server = server
        self._thread = thread

    @property
    def port(self) -> int:
        return self._server.server_address[1]

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)


def _relay(src: socket.socket, dst: socket.socket) -> None:
    try:
        while True:
            data = src.recv(4096)
            if not data:
                break
            dst.sendall(data)
    except OSError:
        pass
    finally:
        try:
            dst.shutdown(socket.SHUT_WR)
        except OSError:
            pass


def _pump(client_sock: socket.socket, upstream_sock: socket.socket) -> None:
    """Tunnel bytes both directions until either side closes; blocks the request thread until the tunnel ends."""
    threads = [
        threading.Thread(target=_relay, args=(client_sock, upstream_sock), daemon=True),
        threading.Thread(target=_relay, args=(upstream_sock, client_sock), daemon=True),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    upstream_sock.close()


def live_relay(endpoint: Endpoint, credential: str | None, method: str, params: dict) -> tuple[int, str, bytes]:
    """The production relay: one `urllib.request` POST to the route's own endpoint, credential as a bearer token.

    The upstream's own status, `Content-Type`, and raw response body pass
    straight through -- this function decides nothing about size or
    inline-ness, that is `tool_results.shape`'s job once the proxy has the
    bytes back.
    """
    headers = {"Content-Type": "application/json"}
    if credential is not None:
        headers["Authorization"] = f"Bearer {credential}"
    body = json.dumps({"method": method, "params": params}).encode()
    request = urllib.request.Request(
        f"https://{endpoint.host}:{endpoint.port}/", data=body, headers=headers, method="POST",
    )
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, response.headers.get_content_type(), response.read()
    except urllib.error.HTTPError as exc:
        media_type = exc.headers.get_content_type() if exc.headers is not None else "application/octet-stream"
        return exc.code, media_type, exc.read()


def next_seq(conn: sqlite3.Connection, stage_run_id: int) -> int:
    """The next free `tool_call.seq` for the run: proxy-routed and direct calls share one sequence."""
    row = conn.execute("SELECT MAX(seq) AS m FROM tool_call WHERE stage_run_id = ?", (stage_run_id,)).fetchone()
    return (row["m"] or 0) + 1


def _extension_for(media_type: str) -> str:
    return _EXTENSION_BY_MEDIA_TYPE.get(media_type, ".bin")


def _relay_and_record(routes: RouteService, *, route_id: str, endpoint: Endpoint, route: object, method: str, params: dict):
    """Relay one route call, shape and store its result, and write the `tool_call` row; return `(status, payload)`.

    `status` is the HTTP status this handler sends to the sandbox --
    `502` when the route's credential cannot be fetched, `200` otherwise
    with `payload` carrying the route contract's response body.
    """
    credential_roles = getattr(route, "credential_roles", ())
    role = credential_roles[0] if credential_roles else None
    try:
        credential = routes.credential_fetch(role) if role is not None else None
    except credentials.CredentialUnavailable:
        return 502, None

    started = time.monotonic()
    status, media_type, result = routes.relay(endpoint, credential, method, params)
    duration_ms = int((time.monotonic() - started) * 1000)

    shaped = tool_results.shape(result, media_type=media_type, rule=routes.inline_rule)
    digest = hashlib.sha256(result).hexdigest()
    args_digest = hashlib.sha256(canonical.canonical_json({"method": method, "params": params})).hexdigest()

    # A connection of its own: this handler runs on the proxy's background
    # thread, and sqlite3 connections are not safe to share across threads.
    conn = open_db(routes.db_path)
    try:
        seq = next_seq(conn, routes.stage_run_id)
        artefact_path = routes.run_dir / "results" / "tool_results" / f"{seq}{_extension_for(media_type)}"
        write_bytes(artefact_path, result)
        artefact_id = artefact_registry.register(
            conn, ticket_id=routes.ticket_id, kind="tool_result", path=artefact_path, stage_run_id=routes.stage_run_id,
        )
        record.insert(
            conn, "tool_call",
            stage_run_id=routes.stage_run_id, seq=seq, tool=route_id, args_digest=args_digest,
            result_digest=digest, result_artefact=artefact_id, duration_ms=duration_ms,
            result_bytes=shaped.result_bytes, inline=1 if shaped.inline else 0,
        )
        conn.commit()
    finally:
        conn.close()

    return 200, {
        "artefact_path": str(artefact_path),
        "result_bytes": shaped.result_bytes,
        "inline": shaped.inline,
        "excerpt": shaped.excerpt,
        "media_type": media_type,
        "digest": digest,
        "exit_status": status,
    }


def _make_handler(allowlist: list[Endpoint], routes: RouteService | None) -> type[http.server.BaseHTTPRequestHandler]:
    allowed = {(endpoint.host, endpoint.port) for endpoint in allowlist}
    endpoints_by_route = {endpoint.route_id: endpoint for endpoint in allowlist}

    class _Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, format: str, *args) -> None:  # noqa: A002 - matches BaseHTTPRequestHandler's own signature
            pass  # a run's proxy traffic is not part of this milestone's audit trail

        def do_CONNECT(self) -> None:  # noqa: N802 - http.server's own dispatch convention
            host, _, port_text = self.path.partition(":")
            port = int(port_text) if port_text.isdigit() else None
            if (host, port) not in allowed:
                self.send_response(403)
                self.end_headers()
                self.connection.close()
                return
            try:
                upstream = socket.create_connection((host, port), timeout=10)
            except OSError:
                self.send_response(502)
                self.end_headers()
                self.connection.close()
                return
            self.send_response(200, "Connection Established")
            self.end_headers()
            _pump(self.connection, upstream)

        def do_POST(self) -> None:  # noqa: N802
            # Drained before any early return, refusal included: leaving
            # the client's body unread on the socket while this handler
            # closes the connection races the client's own read of the
            # response with a kernel-level RST on some platforms, turning
            # a clean 403/404 into a `ConnectionResetError` at the caller.
            length = int(self.headers.get("Content-Length") or 0)
            raw_body = self.rfile.read(length) if length else b""

            # `self.path` may be an absolute-URI ("http://host/routes/x")
            # rather than an origin-form path: the sandbox's own
            # `HTTP_PROXY`/`HTTPS_PROXY` point at this same server, so a
            # plain `urllib.request` call to it is itself proxied, and a
            # proxied request line is legitimately absolute-URI. Only the
            # path component ever names a route.
            request_path = urllib.parse.urlsplit(self.path).path
            if routes is None or not request_path.startswith("/routes/"):
                self.send_response(404)
                self.end_headers()
                return
            route_id = request_path[len("/routes/") :]
            endpoint = endpoints_by_route.get(route_id)
            route = routes.routes.get(route_id)
            if endpoint is None or route is None:
                self.send_response(403)
                self.end_headers()
                return
            try:
                body = json.loads(raw_body) if raw_body else {}
            except json.JSONDecodeError:
                self.send_response(400)
                self.end_headers()
                return
            status, payload = _relay_and_record(
                routes, route_id=route_id, endpoint=endpoint, route=route,
                method=body.get("method"), params=body.get("params") or {},
            )
            if payload is None:
                self.send_response(status)
                self.end_headers()
                return
            encoded = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    return _Handler


def start(allowlist: list[Endpoint], routes: RouteService | None = None) -> Proxy:
    """Start one loopback proxy for this run; `.stop()` it once the run has finished."""
    handler = _make_handler(allowlist, routes)
    server = http.server.HTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return Proxy(server, thread)
