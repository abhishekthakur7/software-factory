"""Reads a workspace-level MCP config file placed inside the ticket's own worktree; refused when the read fails."""
import json
import sys


def main() -> int:
    mcp_config_path = sys.argv[1]
    try:
        with open(mcp_config_path) as handle:
            handle.read()
        refused = False
    except OSError:
        refused = True
    print(json.dumps({"attempted": True, "refused": refused}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
