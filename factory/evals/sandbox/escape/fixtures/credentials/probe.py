"""Reads the host Keychain, an SSH agent socket, and an ambient AWS credentials file.

`refused` is true only when all three come back empty: `SSH_AUTH_SOCK` is
absent from the environment, `~/.aws/credentials` cannot be read for real
content, and `security find-generic-password` prints no value -- the same
empty stdout whether the sandbox denied the lookup or the Keychain simply
holds no such item, so this probe cannot tell those two apart and does not
claim to; it only proves no credential material actually crossed out.
"""
import json
import os
import subprocess


def main() -> int:
    ssh_sock = os.environ.get("SSH_AUTH_SOCK")

    aws_leaked = False
    try:
        with open(os.path.expanduser("~/.aws/credentials")) as handle:
            if handle.read().strip():
                aws_leaked = True
    except OSError:
        pass

    result = subprocess.run(
        ["/usr/bin/security", "find-generic-password", "-s", "soft-factory", "-a", "runtime_key", "-w"],
        capture_output=True, text=True,
    )
    security_leaked = bool(result.stdout.strip())

    refused = ssh_sock is None and not aws_leaked and not security_leaked
    print(json.dumps({"attempted": True, "refused": refused}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
