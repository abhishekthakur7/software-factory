"""The enforced sandbox: OS-level Seatbelt policy, loopback proxy, copy-on-write copies, credential roles.

Every test either drives the fixture worker under `runner/tests/fixtures/
adapter/` through `runner.launcher.launch` (the non-OS-enforced contract
tests this repository already relied on before this policy), or launches a
small inline probe script through the real, committed `factory/config/
sandbox/{agent,build}-profile.sb` files (the OS-enforcement tests). The
escape suite in `test_escape_suite.py` is the exhaustive, per-category
proof of the same profiles; this file proves the structural pieces around
them -- the manifest's sandbox-policy entry, the digest, the proxy
allowlist resolution, and copy provisioning/disposal/recheck.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from runner import credentials, envelope, launcher, manifest, record, tickets, trust_profile
from runner.adapters import cursor_sdk
from runner.db import connect
from runner.paths import REPO_ROOT
from runner.sandbox import copies, os_policy, proxy

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "adapter"
WORKER_PATH = FIXTURES_DIR / "fixture_worker.py"
SANDBOX_PATH = FIXTURES_DIR / "sandbox.yaml"
REAL_SANDBOX_PATH = REPO_ROOT / "factory" / "config" / "sandbox.yaml"
PROFILE_DIR = REPO_ROOT / "factory" / "config" / "sandbox"
THIN_BEFORE_PATH = Path(__file__).parent / "fixtures" / "sandbox" / "thin_before" / "sandbox.yaml"


def _envelope_stub(tmp_path: Path) -> Path:
    path = tmp_path / "envelope.json"
    path.write_text(json.dumps({"stage": "S1", "model_requested": "claude-sonnet-5"}))
    return path


def _launch(tmp_path, case: str, *, role: str = "agent", runtime_key_value: str | None = None, extra_env: dict | None = None):
    """The non-OS-enforced fixture contract: this test sandbox names no `os_profiles`, matching adapter fixtures."""
    env_source = {"PATH": os.environ.get("PATH", ""), "FIXTURE_ADAPTER_CASE": case, "SECRET": "leaked-if-present"}
    if extra_env:
        env_source.update(extra_env)
    return launcher.launch(
        run_dir=tmp_path / "run", argv=[sys.executable, str(WORKER_PATH), str(_envelope_stub(tmp_path))],
        role=role, policy="enforced", cwd=tmp_path, wall_clock_seconds=15,
        env_source=env_source, runtime_key_value=runtime_key_value, sandbox_path=SANDBOX_PATH,
    )


_PROBE_COUNTER = {"n": 0}


def _run_real_probe(
    tmp_path: Path, code: str, *, role: str = "agent", stage: str = "S1", extra_argv: tuple = (), **launch_kwargs,
):
    """Run `code` as a standalone script under the real, committed OS-enforced profile; return the `LaunchResult`."""
    _PROBE_COUNTER["n"] += 1
    run_dir = tmp_path / f"run{_PROBE_COUNTER['n']}"
    scratch = run_dir / "tmp"
    scratch.mkdir(parents=True, exist_ok=True)
    probe_path = scratch / "probe.py"
    probe_path.write_text(code)
    return launcher.launch(
        run_dir=run_dir, argv=[sys.executable, str(probe_path), *extra_argv], role=role, policy="enforced",
        cwd=tmp_path, wall_clock_seconds=20, stage=stage, sandbox_path=REAL_SANDBOX_PATH, **launch_kwargs,
    )


def _git(args, cwd):
    return subprocess.run(
        ["git", "-c", "commit.gpgsign=false", *args], cwd=cwd, capture_output=True, text=True, check=True,
    )


def _tiny_repo(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    _git(["init", "-q"], cwd=root)
    _git(["checkout", "-q", "-b", "main"], cwd=root)
    (root / "README.md").write_text("seed\n")
    _git(["add", "-A"], cwd=root)
    env = {
        **os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid",
    }
    subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "commit", "-q", "-m", "seed"], cwd=root,
        env=env, capture_output=True, text=True, check=True,
    )
    return root


# The profile files exist, run for real, and enforce their documented
# shape (mount/writability/egress for agent; copy-scoped writes, no
# credential, and a narrow process-exec allowlist for build).


def test_agent_profile_file_exists_and_the_os_policy_is_available_on_this_host():
    assert (PROFILE_DIR / "agent-profile.sb").is_file()
    assert os_policy.available() is True


def test_build_profile_file_exists():
    assert (PROFILE_DIR / "build-profile.sb").is_file()


def test_agent_profile_permits_writes_to_out_and_denies_writes_to_results(tmp_path):
    result = _run_real_probe(
        tmp_path,
        "import os, json\n"
        "out_ok = True\n"
        "try:\n"
        "    open(os.path.join(os.environ['FACTORY_RUN_OUT'], 'x.txt'), 'w').write('x')\n"
        "except OSError:\n"
        "    out_ok = False\n"
        "results_denied = False\n"
        "try:\n"
        "    open(os.environ['FACTORY_RUN_OUT'] + '/../results/forged.json', 'w').write('x')\n"
        "except OSError:\n"
        "    results_denied = True\n"
        "print(json.dumps({'out_ok': out_ok, 'results_denied': results_denied}))\n",
        ticket_dir=tmp_path / "ticket",
    )
    assert result.stdout_json == {"out_ok": True, "results_denied": True}


def test_agent_profile_permits_a_worktree_write_at_s4_and_denies_it_at_every_other_stage(tmp_path):
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    code = (
        "import sys, json\n"
        "denied = False\n"
        "try:\n"
        "    open(sys.argv[1] + '/x.txt', 'w').write('x')\n"
        "except OSError:\n"
        "    denied = True\n"
        "print(json.dumps({'denied': denied}))\n"
    )
    result_s4 = _run_real_probe(
        tmp_path, code, stage="S4", worktree_path=worktree, extra_argv=(str(worktree),),
    )
    assert result_s4.stdout_json == {"denied": False}

    result_s1 = _run_real_probe(
        tmp_path, code, stage="S1", worktree_path=worktree, extra_argv=(str(worktree),),
    )
    assert result_s1.stdout_json == {"denied": True}


def test_agent_profile_admits_only_loopback_network_outbound(tmp_path):
    result = _run_real_probe(
        tmp_path,
        "import socket, json\n"
        "denied = False\n"
        "try:\n"
        "    socket.create_connection(('93.184.216.34', 80), timeout=3)\n"
        "except OSError:\n"
        "    denied = True\n"
        "print(json.dumps({'denied': denied}))\n",
        ticket_dir=tmp_path / "ticket",
    )
    assert result.stdout_json == {"denied": True}


def test_build_profile_permits_writes_to_the_copy_and_disposables_and_denies_elsewhere(tmp_path):
    copy_dir, build_dir, scratch_dir, cache_dir = (tmp_path / n for n in ("copy", "build", "scratch", "cache"))
    for d in (copy_dir, build_dir, scratch_dir, cache_dir):
        d.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    code = (
        "import os, sys, json\n"
        "results = []\n"
        "for t in sys.argv[1:]:\n"
        "    try:\n"
        "        open(os.path.join(t, 'w.txt'), 'w').write('x')\n"
        "        results.append(True)\n"
        "    except OSError:\n"
        "        results.append(False)\n"
        "print(json.dumps({'results': results}))\n"
    )
    result = _run_real_probe(
        tmp_path, code, role="build", stage="S5",
        extra_argv=(str(copy_dir), str(build_dir), str(scratch_dir), str(cache_dir), str(elsewhere)),
        copy_dir=copy_dir, build_dir=build_dir, scratch_dir=scratch_dir, cache_dir=cache_dir,
    )
    assert result.stdout_json == {"results": [True, True, True, True, False]}


def test_build_role_receives_no_credential_of_any_kind(tmp_path):
    result = _launch(tmp_path, "environment_probe", role="build", runtime_key_value="scoped-secret-value")
    assert "runtime_key" not in result.integrity.environment_names


def test_build_profile_admits_loopback_only_no_direct_egress_at_s5(tmp_path):
    result = _run_real_probe(
        tmp_path,
        "import socket, json\n"
        "denied = False\n"
        "try:\n"
        "    socket.create_connection(('93.184.216.34', 80), timeout=3)\n"
        "except OSError:\n"
        "    denied = True\n"
        "print(json.dumps({'denied': denied}))\n",
        role="build", stage="S5", copy_dir=tmp_path / "copy", build_dir=tmp_path / "build",
        scratch_dir=tmp_path / "scratch", cache_dir=tmp_path / "cache",
    )
    assert result.stdout_json == {"denied": True}


# sandbox.yaml's os_profile digests equal the profiles' own content hash.


def test_sandbox_yaml_os_profile_digests_equal_the_profiles_own_content_hash():
    doc = yaml.safe_load(REAL_SANDBOX_PATH.read_text())
    os_profiles = doc["policies"]["enforced"]["os_profiles"]
    for role, entry in os_profiles.items():
        assert os_policy.digest(REPO_ROOT / entry["path"]) == entry["digest"], role


# sandbox.yaml's proxy_allowlist names the route id, host and port
# admitted per stage.


def _resolve_allowlist(policy: dict, stage: str) -> list:
    endpoints = policy.get("endpoints", {})
    return [
        proxy.Endpoint(route_id=route_id, host=endpoints[route_id]["host"], port=endpoints[route_id]["port"])
        for route_id in policy.get("proxy_allowlist", {}).get(stage, [])
    ]


def test_sandbox_yaml_proxy_allowlist_resolves_to_route_host_port_per_stage():
    doc = yaml.safe_load(REAL_SANDBOX_PATH.read_text())
    policy = doc["policies"]["enforced"]
    endpoints = policy["endpoints"]
    assert _resolve_allowlist(policy, "S1") == [
        proxy.Endpoint(route_id="hosted_model", host=endpoints["hosted_model"]["host"], port=endpoints["hosted_model"]["port"])
    ]
    assert _resolve_allowlist(policy, "S5") == [
        proxy.Endpoint(route_id="registry", host=endpoints["registry"]["host"], port=endpoints["registry"]["port"])
    ]
    assert _resolve_allowlist(policy, "S0") == []


# sandbox.yaml names the disposable-copy location.


def test_sandbox_yaml_names_the_disposable_copy_location():
    doc = yaml.safe_load(REAL_SANDBOX_PATH.read_text())
    location = doc["policies"]["enforced"]["copies"]["location"]
    assert location == "runs/tickets/{ticket_id}/copies/{stage_run_id}"


# The launcher applies the OS policy through os_policy.py.


def test_launcher_applies_the_os_policy_and_records_it_in_exit_json(tmp_path):
    result = _run_real_probe(tmp_path, "print('{}')\n", ticket_dir=tmp_path / "ticket")
    assert result.os_policy_applied is True
    exit_doc = json.loads((result.results_dir / "exit.json").read_text())
    assert exit_doc["os_policy"] is True


def test_launcher_records_os_policy_false_when_the_policy_names_no_profiles(tmp_path):
    result = _launch(tmp_path, "settled")
    assert result.os_policy_applied is False
    exit_doc = json.loads((result.results_dir / "exit.json").read_text())
    assert exit_doc["os_policy"] is False


# The sandbox digest is computed over the OS profile, the proxy
# allowlist, and the runtime's sandbox configuration together, and
# differs from the digest a run recorded before this policy landed.


def test_sandbox_digest_differs_from_the_pre_os_enforcement_digest(tmp_path):
    before = envelope.sandbox_digest("thin", sandbox_path=THIN_BEFORE_PATH, stage="S1", runs_dir=tmp_path)
    after = envelope.sandbox_digest("enforced", sandbox_path=REAL_SANDBOX_PATH, stage="S1", runs_dir=tmp_path)
    assert before != after


def test_sandbox_digest_changes_with_the_stage_and_with_the_runs_directory(tmp_path):
    s1 = envelope.sandbox_digest("enforced", sandbox_path=REAL_SANDBOX_PATH, stage="S1", runs_dir=tmp_path)
    s5 = envelope.sandbox_digest("enforced", sandbox_path=REAL_SANDBOX_PATH, stage="S5", runs_dir=tmp_path)
    elsewhere = envelope.sandbox_digest("enforced", sandbox_path=REAL_SANDBOX_PATH, stage="S1", runs_dir=tmp_path / "elsewhere")
    assert s1 != s5
    assert s1 != elsewhere


# The manifest's sandbox-policy entry names the OS profile, proxy
# allowlist, and credential roles admitted per stage; only an agent stage
# admits runtime_key.


def test_manifest_sandbox_policy_names_os_profiles_proxy_allowlist_and_credential_roles():
    m = manifest.load()
    assert set(m.sandbox_policy["os_profiles"]) == {"agent", "build"}
    assert m.sandbox_policy["proxy_allowlist"] == "factory/config/sandbox.yaml"
    assert set(m.sandbox_policy["credential_roles"]) == set(manifest.SANDBOX_POLICY_SCOPES)


def test_manifest_admits_runtime_key_for_agent_stages_and_none_for_build_s0_s5_s6():
    m = manifest.load()
    roles = m.sandbox_policy["credential_roles"]
    for stage in ("S1", "S2", "S3", "S4"):
        assert roles[stage] == ("runtime_key",), stage
    for scope in ("S0", "S5", "S6", "build"):
        assert roles[scope] == (), scope


# credentials.fetch is called at the moment of use and never returns
# into a row, an artefact, a log, or a build sandbox's environment.


def _open_ticket(conn, tmp_path):
    ticket_id = tickets.open_ticket(
        conn, title="t", trust_profile_hash="tph", trust_approval_set_hash="tash", data_class="internal",
        base_sha="base", head_sha="head", worktree_path=str(tmp_path / "worktree"),
    )
    (tmp_path / "worktree").mkdir(parents=True, exist_ok=True)
    return record.get(conn, "ticket", ticket_id)


def _fixture_runtime_path(tmp_path):
    runtime_doc = yaml.safe_load((FIXTURES_DIR / "runtime.yaml").read_text())
    runtime_doc["adapters"]["cursor_sdk"]["command"] = [sys.executable, str(WORKER_PATH)]
    runtime_path = tmp_path / "runtime.yaml"
    runtime_path.write_text(yaml.safe_dump(runtime_doc))
    return runtime_path


def _entry_admitting_runtime_key() -> manifest.Entry:
    return manifest.Entry(
        stage="S1", tier="standard", agent="factory/agents/S1.md", skill="factory/skills/S1.md",
        shared_skills=(), rubric="factory/rubrics/S1.md", tool_allowlist=("read_file",),
        budget_source="factory/config/tiers.yaml", budget={"tokens": 400000, "wall_clock_seconds": 1200},
        runtime_adapter="cursor_sdk", runtime_version="1.0.31", model_requested="claude-sonnet-5",
        grader_model="claude-sonnet-5", sandbox_policy="enforced", credential_roles=("runtime_key",),
        toolchain={"jdk": "17"}, restatement_model=None, agent_hash="a", skill_hash="s", shared_skill_hashes=(),
        rubric_hash="r", manifest_hash="m",
    )


def test_credential_value_never_appears_in_any_row_file_or_stderr(tmp_path):
    conn = connect(tmp_path / "factory.sqlite")
    ticket = _open_ticket(conn, tmp_path)
    secret = "sk-live-do-not-leak-1234567890"

    def _fake_run(args, **kwargs):
        return subprocess.CompletedProcess(args, 0, stdout=secret + "\n", stderr="")

    result = cursor_sdk.invoke(
        conn, ticket=ticket, stage="S1", tier="standard", entry=_entry_admitting_runtime_key(),
        runs_dir=tmp_path / "runs", runtime_path=_fixture_runtime_path(tmp_path), sandbox_path=SANDBOX_PATH,
        env_source={"PATH": os.environ.get("PATH", ""), "FIXTURE_ADAPTER_CASE": "settled"},
        credential_run=_fake_run,
    )
    assert result.outcome == "pass"

    for table in ("stage_run", "ticket", "tool_call", "artefact"):
        for row in conn.execute(f"SELECT * FROM {table}").fetchall():
            for value in tuple(row):
                assert secret not in str(value)

    run_dir = tmp_path / "runs" / "tickets" / str(ticket["id"]) / "runs" / str(result.stage_run_id)
    for path in run_dir.rglob("*"):
        if path.is_file():
            assert secret not in path.read_text(errors="ignore")


def test_credential_unavailable_is_recorded_as_an_infrastructure_failure_never_a_crash(tmp_path):
    conn = connect(tmp_path / "factory.sqlite")
    ticket = _open_ticket(conn, tmp_path)

    def _failing_run(args, **kwargs):
        return subprocess.CompletedProcess(args, 44, stdout="", stderr="not found")

    result = cursor_sdk.invoke(
        conn, ticket=ticket, stage="S1", tier="standard", entry=_entry_admitting_runtime_key(),
        runs_dir=tmp_path / "runs", runtime_path=_fixture_runtime_path(tmp_path), sandbox_path=SANDBOX_PATH,
        env_source={"PATH": os.environ.get("PATH", ""), "FIXTURE_ADAPTER_CASE": "settled"},
        credential_run=_failing_run,
    )
    assert result.outcome == "infrastructure_failure"
    assert result.failure_kind == "infrastructure"
    run = record.get(conn, "stage_run", result.stage_run_id)
    assert run["outcome"] == "infrastructure_failure"
    assert run["failure_kind"] == "infrastructure"


def test_credentials_fetch_is_never_called_when_the_stage_admits_no_role(tmp_path):
    """A build-role or script-only stage's entry carries no `runtime_key` role, so `invoke` never even tries."""
    conn = connect(tmp_path / "factory.sqlite")
    ticket = _open_ticket(conn, tmp_path)
    calls: list = []

    def _spy_run(args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, stdout="should-never-be-called\n", stderr="")

    entry = manifest.Entry(
        stage="S5", tier="standard", agent="factory/agents/S1.md", skill="factory/skills/S1.md",
        shared_skills=(), rubric="factory/rubrics/S1.md", tool_allowlist=("read_file",),
        budget_source="factory/config/tiers.yaml", budget={"tokens": 400000, "wall_clock_seconds": 1200},
        runtime_adapter="cursor_sdk", runtime_version="1.0.31", model_requested="claude-sonnet-5",
        grader_model="claude-sonnet-5", sandbox_policy="enforced", credential_roles=(),
        toolchain={"jdk": "17"}, restatement_model=None, agent_hash="a", skill_hash="s", shared_skill_hashes=(),
        rubric_hash="r", manifest_hash="m",
    )
    result = cursor_sdk.invoke(
        conn, ticket=ticket, stage="S5", tier="standard", entry=entry, runs_dir=tmp_path / "runs",
        runtime_path=_fixture_runtime_path(tmp_path), sandbox_path=SANDBOX_PATH,
        env_source={"PATH": os.environ.get("PATH", ""), "FIXTURE_ADAPTER_CASE": "settled"},
        credential_run=_spy_run,
    )
    assert result.outcome == "pass"
    assert calls == []


# runtime.yaml's runtime_key entry.


def test_runtime_yaml_runtime_key_entry_carries_role_scope_spend_cap_rotation_never_value():
    doc = yaml.safe_load((REPO_ROOT / "factory" / "config" / "runtime.yaml").read_text())
    entry = doc["runtime_key"]
    assert entry["role"] == "runtime_key"
    assert entry["role"] in credentials.ROLES
    assert isinstance(entry["scope"], str) and entry["scope"]
    assert "usd_per_month" in entry["spend_cap"]
    assert "days" in entry["rotation"]
    assert "value" not in entry


# The hosted_model route carries credential_role: runtime_key.


def test_trust_profile_hosted_model_route_carries_credential_role_runtime_key():
    profile = trust_profile.load_trust_profile()
    assert profile.routes["hosted_model"].credential_roles == ("runtime_key",)


# The loopback proxy.


def test_proxy_starts_one_process_on_127_0_0_1_and_the_port_reaches_the_sandbox_environment(tmp_path):
    p = proxy.start([])
    try:
        assert p.port > 0
    finally:
        p.stop()

    result = _run_real_probe(
        tmp_path,
        "import os, json\n"
        "print(json.dumps({'https_proxy': os.environ.get('HTTPS_PROXY'), 'port': os.environ.get('FACTORY_PROXY_PORT')}))\n",
        ticket_dir=tmp_path / "ticket",
    )
    assert result.stdout_json["https_proxy"].startswith("http://127.0.0.1:")
    assert result.stdout_json["port"] == result.stdout_json["https_proxy"].rsplit(":", 1)[1]


def test_proxy_admits_only_allowlisted_host_port_pairs():
    import http.client
    import socket
    import threading

    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    listen_port = listener.getsockname()[1]

    def _accept_once():
        conn, _ = listener.accept()
        conn.recv(16)
        conn.sendall(b"pong")
        conn.close()

    thread = threading.Thread(target=_accept_once, daemon=True)
    thread.start()

    p = proxy.start([proxy.Endpoint(route_id="test", host="localhost", port=listen_port)])
    try:
        allowed = http.client.HTTPConnection("127.0.0.1", p.port)
        allowed.set_tunnel("localhost", listen_port)
        allowed.connect()
        allowed.sock.sendall(b"ping")
        assert allowed.sock.recv(16) == b"pong"
        allowed.close()

        refused = http.client.HTTPConnection("127.0.0.1", p.port)
        with pytest.raises(OSError):
            refused.set_tunnel("localhost", listen_port + 1)
            refused.connect()
    finally:
        p.stop()
        listener.close()
        thread.join(timeout=2)


def test_runtime_key_reaches_the_hosted_model_endpoint_only_through_the_loopback_proxy(tmp_path):
    """The agent sandbox's own network-outbound rule admits loopback only; HTTPS_PROXY is the one route out."""
    doc = yaml.safe_load(REAL_SANDBOX_PATH.read_text())
    assert doc["policies"]["enforced"]["proxy_allowlist"]["S1"] == ["hosted_model", "atlassian_read"]
    result = _run_real_probe(
        tmp_path,
        "import socket, json\n"
        "denied = False\n"
        "try:\n"
        "    socket.create_connection(('93.184.216.34', 443), timeout=3)\n"
        "except OSError:\n"
        "    denied = True\n"
        "print(json.dumps({'direct_egress_denied': denied}))\n",
        ticket_dir=tmp_path / "ticket",
    )
    assert result.stdout_json == {"direct_egress_denied": True}


# Copy-on-write copies.


def test_copies_provision_creates_apfs_clones_with_empty_disposable_directories(tmp_path):
    source = _tiny_repo(tmp_path / "source")
    result = copies.provision(
        ticket_id=7, stage_run_id=3, base_checkout=source, head_checkout=source, runs_dir=tmp_path / "runs",
    )
    assert (result.base / "README.md").read_text() == "seed\n"
    assert (result.head / "README.md").read_text() == "seed\n"
    for checkout in (result.base, result.head):
        for name in ("target", "scratch", "cache"):
            assert (checkout / name).is_dir()
            assert not any((checkout / name).iterdir())
    assert result.root == tmp_path / "runs" / "tickets" / "7" / "copies" / "3"


def test_copies_disposable_writes_never_reach_the_immutable_checkout(tmp_path):
    source = _tiny_repo(tmp_path / "source")
    result = copies.provision(ticket_id=1, stage_run_id=1, base_checkout=source, head_checkout=source, runs_dir=tmp_path / "runs")
    (result.base / "target" / "built.class").write_text("compiled\n")
    assert not (source / "target").exists()
    assert not (source / "built.class").exists()


def test_copies_dispose_removes_the_whole_directory(tmp_path):
    source = _tiny_repo(tmp_path / "source")
    result = copies.provision(ticket_id=1, stage_run_id=1, base_checkout=source, head_checkout=source, runs_dir=tmp_path / "runs")
    copies.dispose(result)
    assert not result.root.exists()


def test_provisioned_disposes_even_when_the_caller_raises_mid_run(tmp_path):
    source = _tiny_repo(tmp_path / "source")
    captured = {}
    with pytest.raises(RuntimeError):
        with copies.provisioned(ticket_id=1, stage_run_id=1, base_checkout=source, head_checkout=source, runs_dir=tmp_path / "runs") as provisioned:
            captured["root"] = provisioned.root
            assert provisioned.root.exists()
            raise RuntimeError("build step crashed")
    assert not captured["root"].exists()


def test_recheck_is_true_when_the_checkout_is_untouched_and_false_once_modified(tmp_path):
    source = _tiny_repo(tmp_path / "source")
    head_sha = _git(["rev-parse", "HEAD"], cwd=source).stdout.strip()
    assert copies.recheck(source, head_sha) is True
    (source / "README.md").write_text("modified\n")
    assert copies.recheck(source, head_sha) is False


# Registered inputs stay read-only (worktree/copies are the named
# exceptions); results/ is read-only from inside every sandbox.


def test_ticket_dir_is_readable_but_writing_it_is_refused(tmp_path):
    ticket_dir = tmp_path / "ticket"
    ticket_dir.mkdir()
    (ticket_dir / "input.txt").write_text("registered input\n")
    result = _run_real_probe(
        tmp_path,
        "import os, sys, json\n"
        "d = sys.argv[1]\n"
        "read_ok = open(os.path.join(d, 'input.txt')).read() == 'registered input\\n'\n"
        "write_denied = False\n"
        "try:\n"
        "    open(os.path.join(d, 'escape.txt'), 'w').write('x')\n"
        "except OSError:\n"
        "    write_denied = True\n"
        "print(json.dumps({'read_ok': read_ok, 'write_denied': write_denied}))\n",
        ticket_dir=ticket_dir, extra_argv=(str(ticket_dir),),
    )
    assert result.stdout_json == {"read_ok": True, "write_denied": True}


def test_results_subpath_is_read_only_from_inside_every_role(tmp_path):
    for role, kwargs, stage in (
        ("agent", {"ticket_dir": tmp_path / "agent-ticket"}, "S1"),
        (
            "build",
            {
                "copy_dir": tmp_path / "copy", "build_dir": tmp_path / "build",
                "scratch_dir": tmp_path / "scratch", "cache_dir": tmp_path / "cache",
            },
            "S5",
        ),
    ):
        result = _run_real_probe(
            tmp_path,
            "import os, json\n"
            "results_dir = os.path.dirname(os.environ['FACTORY_RUN_OUT']) + '/results'\n"
            "denied = False\n"
            "try:\n"
            "    open(results_dir + '/forged.json', 'w').write('x')\n"
            "except OSError:\n"
            "    denied = True\n"
            "print(json.dumps({'denied': denied}))\n",
            role=role, stage=stage, **kwargs,
        )
        assert result.stdout_json == {"denied": True}, role


# factory/ and runs/factory.sqlite are absent from every mount.


def test_factory_and_runs_sqlite_are_unreadable_from_inside_the_agent_sandbox(tmp_path):
    result = _run_real_probe(
        tmp_path,
        "import os, sys, json\n"
        "repo_root = sys.argv[1]\n"
        "factory_denied = False\n"
        "try:\n"
        "    open(os.path.join(repo_root, 'factory', 'manifest.yaml')).read()\n"
        "except OSError:\n"
        "    factory_denied = True\n"
        "db_denied = False\n"
        "try:\n"
        "    open(os.path.join(repo_root, 'runs', 'factory.sqlite'), 'rb').read()\n"
        "except OSError:\n"
        "    db_denied = True\n"
        "print(json.dumps({'factory_denied': factory_denied, 'db_denied': db_denied}))\n",
        ticket_dir=tmp_path / "ticket", extra_argv=(str(REPO_ROOT),),
    )
    assert result.stdout_json == {"factory_denied": True, "db_denied": True}


def test_factory_and_runs_sqlite_are_unreadable_from_inside_the_build_sandbox(tmp_path):
    result = _run_real_probe(
        tmp_path,
        "import os, sys, json\n"
        "repo_root = sys.argv[1]\n"
        "factory_denied = False\n"
        "try:\n"
        "    open(os.path.join(repo_root, 'factory', 'manifest.yaml')).read()\n"
        "except OSError:\n"
        "    factory_denied = True\n"
        "db_denied = False\n"
        "try:\n"
        "    open(os.path.join(repo_root, 'runs', 'factory.sqlite'), 'rb').read()\n"
        "except OSError:\n"
        "    db_denied = True\n"
        "print(json.dumps({'factory_denied': factory_denied, 'db_denied': db_denied}))\n",
        role="build", stage="S5", copy_dir=tmp_path / "copy", build_dir=tmp_path / "build",
        scratch_dir=tmp_path / "scratch", cache_dir=tmp_path / "cache", extra_argv=(str(REPO_ROOT),),
    )
    assert result.stdout_json == {"factory_denied": True, "db_denied": True}
