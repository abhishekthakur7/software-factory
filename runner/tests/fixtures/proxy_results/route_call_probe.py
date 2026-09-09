"""Probe: POST one MCP-route call through the sandbox proxy, then reread a further slice of the result by path.

`argv[1]` is the route id, `argv[2]`/`argv[3]` a byte offset and length to
read from the artefact path the proxy hands back -- proving the artefact
is reachable by an ordinary file read from inside the sandbox, not only
through the proxy's own inline response.
"""
import json
import os
import sys
import urllib.request


def main() -> int:
    port = os.environ["FACTORY_PROXY_PORT"]
    route_id = sys.argv[1]
    offset, length = int(sys.argv[2]), int(sys.argv[3])
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/routes/{route_id}",
        data=json.dumps({"method": "probe_call", "params": {"probe": True}}).encode(),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(request) as response:
        body = json.loads(response.read())

    with open(body["artefact_path"], "rb") as handle:
        handle.seek(offset)
        further_slice = handle.read(length).decode(errors="ignore")

    print(json.dumps({"response": body, "further_slice": further_slice}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
