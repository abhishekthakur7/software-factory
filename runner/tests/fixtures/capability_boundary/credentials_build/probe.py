"""Reads an ambient credential from inside a non-agent (build) sandbox: the Keychain, an SSH agent socket, or the
scoped runtime-key environment name; `refused` is true only when none of the three ever surfaces."""
import json
import os
import subprocess


def main() -> int:
    ssh_sock = os.environ.get("SSH_AUTH_SOCK")
    runtime_key = os.environ.get("CURSOR_API_KEY")

    # A build sandbox's process-exec grant is scoped to the recipe scripts,
    # the interpreter and the JDK -- `/usr/bin/security` itself is outside
    # it, so the exec can fail before the Keychain lookup ever runs; that
    # is refusal too, just at an earlier layer than the agent profile's
    # own (exec allowed, mach-lookup denied) boundary.
    try:
        result = subprocess.run(
            ["/usr/bin/security", "find-generic-password", "-s", "soft-factory", "-a", "runtime_key", "-w"],
            capture_output=True, text=True,
        )
        security_leaked = bool(result.stdout.strip())
    except OSError:
        security_leaked = False

    refused = ssh_sock is None and runtime_key is None and not security_leaked
    print(json.dumps({"attempted": True, "refused": refused}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
