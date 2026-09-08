"""The adoption-gate entry point: `python3 -m runner.gate`."""
import pytest

from runner.paths import REPO_ROOT


def main() -> int:
    return pytest.main([str(REPO_ROOT / "runner" / "tests"), "-q"])


if __name__ == "__main__":
    raise SystemExit(main())
