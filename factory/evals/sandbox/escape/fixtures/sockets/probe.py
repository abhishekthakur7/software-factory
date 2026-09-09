"""Opens the host's Docker socket; refused when the connect itself fails."""
import json
import socket


def main() -> int:
    try:
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.connect("/var/run/docker.sock")
        refused = False
    except OSError:
        refused = True
    print(json.dumps({"attempted": True, "refused": refused}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
