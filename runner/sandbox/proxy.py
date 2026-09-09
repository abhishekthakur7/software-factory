"""The loopback proxy: the only path out of an enforced sandbox to the network.

`start` runs one `CONNECT`-tunnelling HTTP proxy per run, in a background
thread of the trusted runner process, bound to an OS-chosen port on
`127.0.0.1`. A `CONNECT host:port` is tunnelled byte for byte only when
`(host, port)` is in the allowlist the run was given; anything else gets a
`403` and a closed connection, so a sandboxed child's Seatbelt profile can
allow `network-outbound` to the loopback address at all without that
address being a route around the endpoint allowlist. `POST /routes/<id>`
is reserved for a later ticket's route dispatch -- the handler already
carries that path so that ticket only adds a branch, not a new server.
"""
import http.server
import socket
import threading
from dataclasses import dataclass


@dataclass(frozen=True)
class Endpoint:
    route_id: str
    host: str
    port: int


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


def _make_handler(allowlist: list[Endpoint]) -> type[http.server.BaseHTTPRequestHandler]:
    allowed = {(endpoint.host, endpoint.port) for endpoint in allowlist}

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
            # `/routes/<route_id>` is a later ticket's own dispatch surface;
            # every POST refuses for now, including that path, so this
            # handler's shape is the only thing that ticket needs to extend.
            self.send_response(404)
            self.end_headers()

    return _Handler


def start(allowlist: list[Endpoint]) -> Proxy:
    """Start one loopback proxy for this run; `.stop()` it once the run has finished."""
    handler = _make_handler(allowlist)
    server = http.server.HTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return Proxy(server, thread)
