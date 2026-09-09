"""Reads a workspace MCP config inside the worktree, then tries to reach the server it names through the proxy.

The file itself is readable -- the worktree is every agent stage's code
mount -- so the boundary is the proxy: a `CONNECT` to the named server's
host is refused unless the stage's allowlist names it, which no workspace
file can change.
"""
import http.client
import json
import os
import sys


def main() -> int:
    with open(sys.argv[1]) as handle:
        config = json.load(handle)
    server = next(iter(config["mcpServers"].values()))
    host, port = server["host"], server["port"]
    connection = http.client.HTTPConnection("127.0.0.1", int(os.environ["FACTORY_PROXY_PORT"]), timeout=10)
    try:
        connection.request("CONNECT", f"{host}:{port}")
        refused = connection.getresponse().status != 200
    except OSError:
        refused = True
    print(json.dumps({"attempted": True, "refused": refused, "read": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
