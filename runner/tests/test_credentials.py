"""Credentials by role: fetched through the `security` command at the moment of use, never stored (R-I-14, R-S0-1)."""
import subprocess

import pytest

from runner import credentials


def _fake_run(stdout: str = "", returncode: int = 0):
    calls: list[list[str]] = []

    def run(argv, capture_output, text):
        calls.append(list(argv))
        return subprocess.CompletedProcess(argv, returncode, stdout=stdout, stderr="")

    run.calls = calls
    return run


def test_fetch_reads_the_role_item_through_the_security_command():
    """the value comes from `security find-generic-password` under the factory's service name, keyed by role."""
    run = _fake_run(stdout="scoped-value\n")
    assert credentials.fetch("runtime_key", run=run) == "scoped-value"
    assert run.calls == [["security", "find-generic-password", "-s", credentials.SERVICE_NAME, "-a", "runtime_key", "-w"]]


def test_must_reject_an_unknown_role_before_touching_the_keychain():
    run = _fake_run(stdout="value")
    with pytest.raises(credentials.CredentialUnavailable):
        credentials.fetch("push_token", run=run)
    assert run.calls == []


def test_must_reject_a_missing_keychain_item_rather_than_return_empty():
    with pytest.raises(credentials.CredentialUnavailable):
        credentials.fetch("atlassian_read", run=_fake_run(stdout="", returncode=44))
    with pytest.raises(credentials.CredentialUnavailable):
        credentials.fetch("atlassian_read", run=_fake_run(stdout="\n", returncode=0))


def test_available_reports_presence_without_raising():
    assert credentials.available("slack_digest", run=_fake_run(stdout="v"))
    assert not credentials.available("slack_digest", run=_fake_run(returncode=44))
