"""Connects to a real external host and port outside `proxy_allowlist`; refused when the connect itself fails."""
import json
import socket


def main() -> int:
    try:
        socket.create_connection(("93.184.216.34", 80), timeout=3)
        refused = False
    except OSError:
        refused = True
    print(json.dumps({"attempted": True, "refused": refused}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
