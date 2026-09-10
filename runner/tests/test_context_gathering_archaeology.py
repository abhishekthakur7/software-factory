"""Context gathering archaeology through the Atlassian route: the script's own classification rule, the sandboxed launch
that reaches it, context_gathering's driver wiring the result into the checked brief's `History` section, and the dry-run
walk to `clarifying`.

Two levels. The script (`factory/scripts/tools/archaeology`) is exercised directly, over a small real git
repository this file builds and a local `http.server` standing in for the loopback proxy's own
`POST /routes/<route_id>` contract -- the proxy's own real route dispatch has not landed yet, so this
fakes exactly the response shape that contract fixes. The driver level runs `context_gathering.run` directly (`test_context_gathering.py`'s own
`_governed_ticket_fields`/`_ready_ticket` pattern, mirrored here with a git repository carrying an
issue-naming commit) with `archaeology_proxy_url` pointed at the same fake server. A dedicated pair of tests
proves the real thing: `archaeology` actually running under the committed, OS-enforced agent Seatbelt
profile, and that profile's environment allowlist admitting no credential-shaped name.
"""
import http.server
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest
import yaml

from runner import (
    artefact_registry, artefacts, credentials, git_trees, governance, manifest, project, queue, record,
    rubrics, run_ledger, transitions,
)
from runner.db import connect
from runner.paths import FACTORY_DIR
from runner.stages import context_gathering
from runner.tests.support import launch_probe

ABHISHEK = "abhishek"
FAR_FUTURE = "2999-01-01T00:00:00+00:00"

ARCHAEOLOGY_SCRIPT = FACTORY_DIR / "scripts" / "tools" / "archaeology"
RUBRIC_PATH = FACTORY_DIR / "rubrics" / "context_gathering.md"
RUBRIC_FIXTURES_DIR = FACTORY_DIR / "evals" / "rubrics" / "context_gathering" / "fixtures"
REAL_SANDBOX_PATH = FACTORY_DIR / "config" / "sandbox.yaml"
PLAIN_OK_OUT_DIR = FACTORY_DIR / "evals" / "agents" / "context_gathering" / "fixtures" / "plain_ok" / "out"
ISSUES_DIR = Path(__file__).parent / "fixtures" / "context_gathering_archaeology" / "issues"

_COMMIT_ENV = {
    "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@example.invalid",
}


def _issue(name: str) -> dict:
    return json.loads((ISSUES_DIR / f"{name}.json").read_text())


@pytest.fixture
def conn(tmp_path):
    connection = connect(tmp_path / "factory.sqlite")
    yield connection
    connection.close()


def _git(args, cwd, env=None):
    full_env = {**os.environ, **env} if env else None
    return subprocess.run(
        ["git", "-c", "commit.gpgsign=false", *args], cwd=cwd, env=full_env, capture_output=True, text=True, check=True,
    )


def _repo_with_history(
    base: Path, *, second_commit_message: str,
    pom_dependencies: tuple[tuple[str, str, str], ...] = (("com.fixturevendor", "strings", "1.0.0"),),
) -> Path:
    """A two-commit git repository: `init`, then one commit touching `Handler.java` with the given message.

    `pom_dependencies` defaults to the one pair `test_context_gathering.py`'s own
    `authoritative_build_graph`/`plain_ok` fixtures resolve
    `authoritative` against the real, committed `artifact-to-service.yaml`
    -- the driver-level tests below reuse `plain_ok`'s own agent output,
    which asserts exactly that row.
    """
    repo = base / "source-repo"
    repo.mkdir(parents=True)
    _git(["init", "-q"], cwd=repo)
    _git(["checkout", "-q", "-b", "main"], cwd=repo)
    src = repo / "src" / "main" / "java" / "com" / "example"
    src.mkdir(parents=True)
    (src / "Handler.java").write_text("package com.example;\n\npublic class Handler {\n}\n")
    deps_xml = "\n".join(
        f"    <dependency>\n      <groupId>{g}</groupId>\n      <artifactId>{a}</artifactId>\n"
        f"      <version>{v}</version>\n    </dependency>"
        for g, a, v in pom_dependencies
    )
    (repo / "pom.xml").write_text(
        "<project>\n  <groupId>com.example</groupId>\n  <artifactId>widget</artifactId>\n  <version>1.0.0</version>\n"
        f"  <dependencies>\n{deps_xml}\n  </dependencies>\n</project>\n"
    )
    _git(["add", "-A"], cwd=repo)
    _git(["commit", "-q", "-m", "init"], cwd=repo, env=_COMMIT_ENV)
    (src / "Handler.java").write_text("package com.example;\n\npublic class Handler {\n    // fix\n}\n")
    _git(["add", "-A"], cwd=repo)
    _git(["commit", "-q", "-m", second_commit_message], cwd=repo, env=_COMMIT_ENV)
    return repo


def _candidate(path="src/main/java/com/example/Handler.java", *, symbol=None, self_evident=False) -> dict:
    return {"path": path, "symbol": symbol, "self_evident": self_evident}


class _FakeAtlassianProxy:
    """A loopback `http.server` implementing the proxy's `POST /routes/<id>` route contract, standing in for the real proxy."""

    def __init__(self, issues: dict[str, dict]):
        self._server = http.server.HTTPServer(("127.0.0.1", 0), self._handler(issues))
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    @staticmethod
    def _handler(issues: dict[str, dict]):
        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):  # noqa: A002 - matches BaseHTTPRequestHandler's own signature
                pass

            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length))
                issue = issues.get(body["params"]["key"])
                if issue is None:
                    envelope = {
                        "artefact_path": None, "result_bytes": 0, "inline": True, "excerpt": "null",
                        "media_type": "application/json", "digest": "none", "exit_status": 404,
                    }
                else:
                    text = json.dumps(issue)
                    envelope = {
                        "artefact_path": None, "result_bytes": len(text), "inline": True, "excerpt": text,
                        "media_type": "application/json", "digest": "none", "exit_status": 200,
                    }
                data = json.dumps(envelope).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        return Handler

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_address[1]}"

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)


@pytest.fixture
def fake_proxy():
    started: list[_FakeAtlassianProxy] = []

    def start(issues: dict[str, dict]) -> _FakeAtlassianProxy:
        server = _FakeAtlassianProxy(issues)
        started.append(server)
        return server

    yield start
    for server in started:
        server.stop()


def _run_script(tmp_path: Path, *, repo: Path, candidates: list[dict], proxy_url: str, route: str = "atlassian_read") -> dict:
    candidates_path = tmp_path / "candidates.json"
    candidates_path.write_text(json.dumps(candidates))
    result = subprocess.run(
        [
            sys.executable, str(ARCHAEOLOGY_SCRIPT), "--worktree", str(repo), "--candidates", str(candidates_path),
            "--proxy", proxy_url, "--route", route,
        ],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


# The script's own classification rule.

def test_explained_classification_from_a_blame_linked_resolved_issue(tmp_path, fake_proxy):
    """A candidate whose blame-linked commit names a resolved issue is classified `explained`."""
    repo = _repo_with_history(tmp_path, second_commit_message="fix bug\n\nFixes FIX-10")
    proxy = fake_proxy({"FIX-10": _issue("explained")})
    payload = _run_script(tmp_path, repo=repo, candidates=[_candidate()], proxy_url=proxy.url)
    row = payload["candidates"][0]
    assert row["classification"] == "explained"
    assert row["issues"] == ["FIX-10"]
    assert row["commits"]


def test_unexplained_classification_when_the_named_issue_is_not_resolved(tmp_path, fake_proxy):
    """A named issue still open leaves the candidate `unexplained`, not `explained`."""
    repo = _repo_with_history(tmp_path, second_commit_message="touch handler\n\nRelates to FIX-11")
    proxy = fake_proxy({"FIX-11": _issue("unresolved")})
    payload = _run_script(tmp_path, repo=repo, candidates=[_candidate()], proxy_url=proxy.url)
    assert payload["candidates"][0]["classification"] == "unexplained"


def test_unexplained_classification_when_the_commit_history_names_no_issue(tmp_path, fake_proxy):
    """A candidate whose commit history names no issue is classified `unexplained`."""
    repo = _repo_with_history(tmp_path, second_commit_message="unrelated tidy-up, no ticket referenced")
    proxy = fake_proxy({})
    payload = _run_script(tmp_path, repo=repo, candidates=[_candidate()], proxy_url=proxy.url)
    row = payload["candidates"][0]
    assert row["classification"] == "unexplained"
    assert row["issues"] == []


def test_contradictory_classification_when_the_named_issue_is_closed_wont_do(tmp_path, fake_proxy):
    """A named issue closed as Won't Do contradicts the change: `contradictory`."""
    repo = _repo_with_history(tmp_path, second_commit_message="fix bug\n\nFixes FIX-12")
    proxy = fake_proxy({"FIX-12": _issue("contradictory")})
    payload = _run_script(tmp_path, repo=repo, candidates=[_candidate()], proxy_url=proxy.url)
    assert payload["candidates"][0]["classification"] == "contradictory"


def test_a_self_evident_candidate_gets_no_row_at_all(tmp_path, fake_proxy):
    """A `self_evident: true` candidate is skipped outright: blame never runs on it."""
    repo = _repo_with_history(tmp_path, second_commit_message="fix bug\n\nFixes FIX-10")
    proxy = fake_proxy({"FIX-10": _issue("explained")})
    payload = _run_script(tmp_path, repo=repo, candidates=[_candidate(self_evident=True)], proxy_url=proxy.url)
    assert payload["candidates"] == []


def test_must_reject_an_unreadable_candidates_file(tmp_path, fake_proxy):
    """must-reject: a malformed `--candidates` file is a usage error -- non-zero exit, one JSON reason line."""
    repo = _repo_with_history(tmp_path, second_commit_message="fix bug\n\nFixes FIX-10")
    proxy = fake_proxy({"FIX-10": _issue("explained")})
    candidates_path = tmp_path / "candidates.json"
    candidates_path.write_text("not valid json")
    result = subprocess.run(
        [
            sys.executable, str(ARCHAEOLOGY_SCRIPT), "--worktree", str(repo), "--candidates", str(candidates_path),
            "--proxy", proxy.url, "--route", "atlassian_read",
        ],
        capture_output=True, text=True,
    )
    assert result.returncode != 0
    assert json.loads(result.stdout)["ok"] is False


# The sandbox's own atlassian_read route.

def test_sandbox_yaml_names_the_atlassian_read_route_for_context_gathering_only():
    """`sandbox.yaml`'s `proxy_allowlist` admits `atlassian_read` for context_gathering only, resolved through `endpoints`."""
    doc = yaml.safe_load(REAL_SANDBOX_PATH.read_text())
    policy = doc["policies"]["enforced"]
    assert policy["endpoints"]["atlassian_read"]["host"]
    assert policy["endpoints"]["atlassian_read"]["port"]
    assert "atlassian_read" in policy["proxy_allowlist"]["context_gathering"]
    for stage in ("clarification", "planning", "implementation", "checks"):
        assert "atlassian_read" not in policy["proxy_allowlist"].get(stage, [])


# The real OS-enforced boundary.

def test_archaeology_runs_git_blame_and_resolves_a_classification_under_the_real_sandbox(tmp_path, fake_proxy):
    """The script runs for real under the committed, OS-enforced agent profile for stage context_gathering and still
    resolves a classification through the loopback route contract."""
    run_dir = tmp_path / "run"
    scratch = run_dir / "tmp"
    scratch.mkdir(parents=True)
    repo = _repo_with_history(scratch, second_commit_message="fix bug\n\nFixes FIX-10")
    proxy = fake_proxy({"FIX-10": _issue("explained")})
    candidates_path = scratch / "candidates.json"
    candidates_path.write_text(json.dumps([_candidate()]))

    result = launch_probe(
        tmp_path, ARCHAEOLOGY_SCRIPT, role="agent", stage="context_gathering",
        extra_argv=(
            "--worktree", str(repo), "--candidates", str(candidates_path), "--proxy", proxy.url,
            "--route", "atlassian_read",
        ),
        worktree_path=repo, ticket_dir=tmp_path / "ticket_dir",
    )
    assert result["candidates"][0]["classification"] == "explained"


def test_the_agent_sandboxs_environment_allowlist_admits_no_atlassian_credential(tmp_path):
    """A value injected under a plausible credential-role env name into the launching process's own
    environment never reaches an agent-role, stage-context_gathering sandboxed child -- the same launch `archaeology`
    itself runs under -- because `sandbox.yaml`'s `env_allowlist` never names it.

    The proxy's own responsibility -- fetching the credential to relay the
    call, and never writing it to a `tool_call` row or artefact -- is
    is code that has not landed yet, and outside what this test can prove.
    """
    probe = tmp_path / "env_probe.py"
    probe.write_text("import json, os\nprint(json.dumps({'environment_names': sorted(os.environ.keys())}))\n")
    marker_name = "ATLASSIAN_READ_TOKEN"
    env_source = {**os.environ, marker_name: "sk-test-marker-should-never-reach-the-sandbox"}
    result = launch_probe(
        tmp_path, probe, role="agent", stage="context_gathering", env_source=env_source, ticket_dir=tmp_path / "ticket_dir",
    )
    assert marker_name not in result["environment_names"]


# The rubric line.

def test_rubric_line_history_classification_grader_is_a_bootstrap_checklist_with_the_dictated_judgment():
    """The history_classification grader line is a bootstrap-checklist line with the dictated judgment sentence."""
    lines = rubrics.load(RUBRIC_PATH)
    line = rubrics.line(lines, row="history_classification", half="grader")
    assert line is not None
    assert line.checklist is True
    assert line.judgment == (
        "fail when a touched-area candidate that is not self-evident has no history classification, "
        "or is classified explained without a resolved issue behind it"
    )


def test_seeded_human_verdict_for_history_classification_names_its_rubric_line_and_a_fail_verdict():
    """The seeded human_verdict scenario for history_classification names its rubric line and a fail verdict."""
    fixture = yaml.safe_load((RUBRIC_FIXTURES_DIR / "human_verdict" / "history_classification.yaml").read_text())
    assert fixture["rubric_line_id"] == "history_classification:grader"
    assert fixture["verdict"] == "fail"
    assert fixture["subject"]


# The driver: History section, the dry-run walk to `clarifying`, and abandon.

def _governed_ticket_fields(conn) -> dict:
    """Ticket fields that satisfy the committed trust profile's default-path activation (mirrors `test_context_gathering.py`)."""
    proposal = governance.propose()
    for role in ("security_approver", "legal_data_governance_approver"):
        governance.decide(
            conn, proposal, actor_identity=ABHISHEK, role=role, decision="approve",
            expires_at=FAR_FUTURE, attestation_version="v1", attestation_hash=f"att-{role}",
        )
    activated = governance.activation(conn, proposal)
    return {
        "trust_profile_hash": proposal.profile_hash, "trust_approval_set_hash": activated.trust_approval_set_hash,
        "service": "fixture-project", "source_kind": "jira", "source_ref": "FIX-1",
    }


def _ready_ticket(conn, tmp_path: Path, source_repo: Path) -> int:
    fields = {
        "state": "context", "opened_at": record.now(), "ticket_type": "small_feature", "service_tier": "T2",
        "tier_provisional": "standard", "factory_manifest_hash": manifest.current_hash(),
        **_governed_ticket_fields(conn),
    }
    ticket_id = record.insert(conn, "ticket", **fields)
    trees = git_trees.clone_for_ticket(conn, ticket_id, source_checkout=source_repo, target_branch="main", runs_dir=tmp_path)
    git_trees.record_head(conn, ticket_id, trees.worktree)
    return ticket_id


def _ticket_moved_to_clarifying(conn, tmp_path: Path, monkeypatch, fake_proxy) -> int:
    """A ticket whose worktree carries a `FIX-10`-naming commit, run through context_gathering with the fake proxy resolving
    it `explained`, moved to `clarifying`; shared by the History-section test and the abandon test below."""
    repo = _repo_with_history(tmp_path, second_commit_message="fix bug\n\nFixes FIX-10")
    ticket_id = _ready_ticket(conn, tmp_path, repo)
    proxy = fake_proxy({"FIX-10": _issue("explained")})
    monkeypatch.setenv("FIXTURE_ADAPTER_OUT_DIR", str(PLAIN_OK_OUT_DIR))
    ticket = record.get(conn, "ticket", ticket_id)
    stage_run_id = run_ledger.open_stage_run(conn, ticket_id=ticket_id, stage="context_gathering")
    outcome = context_gathering.run(conn, ticket, stage_run_id, tmp_path, vendor_path=tmp_path / "vendor", archaeology_proxy_url=proxy.url)
    assert outcome == "pass"
    # `context_gathering.run` is called directly (not through `run_stage`) so the proxy
    # override above can be passed; `run_stage` applies the pass event
    # itself in production, so the test applies it explicitly here too.
    transitions.apply(conn, ticket_id, context_gathering.PASS_EVENT)
    return ticket_id


def test_the_dry_run_ticket_resolves_the_blame_linked_issue_and_moves_to_clarifying(conn, tmp_path, monkeypatch, fake_proxy):
    """On the dry-run ticket, context_gathering resolves the one blame-linked issue, the checked brief's `History` section
    records that classification (never the agent's own -- `plain_ok`'s fixture brief names a different one),
    a `history` artefact is registered, and the ticket moves `context` to `clarifying`."""
    ticket_id = _ticket_moved_to_clarifying(conn, tmp_path, monkeypatch, fake_proxy)

    brief = artefact_registry.latest(conn, ticket_id, "brief")
    history_rows = artefacts.parse(Path(brief["path"]).read_text()).section("History").table()
    assert history_rows[0]["path"] == "src/main/java/com/example/Handler.java"
    assert history_rows[0]["classification"] == "explained"
    assert "FIX-10" in history_rows[0]["evidence"]

    history_artefact = artefact_registry.latest(conn, ticket_id, "history")
    assert history_artefact is not None
    assert json.loads(Path(history_artefact["path"]).read_text())["candidates"][0]["classification"] == "explained"

    assert record.get(conn, "ticket", ticket_id)["state"] == "clarifying"


def test_factory_abandon_on_the_clarifying_ticket_writes_the_tag_and_coverage_record_and_no_later_stage_run(
    conn, tmp_path, monkeypatch, fake_proxy,
):
    """`factory abandon` on the dry-run ticket in `clarifying` writes the `abandoned` tag and the
    `not_deployed` production-coverage record, and no `stage_run` for clarification or later exists -- `queue.abandon`
    already does both, this only asserts them."""
    ticket_id = _ticket_moved_to_clarifying(conn, tmp_path, monkeypatch, fake_proxy)

    queue.abandon(conn, ticket_id, actor=ABHISHEK, fm_id="load_bearing_hack", runs_dir=tmp_path)

    assert record.get(conn, "ticket", ticket_id)["state"] == "abandoned"
    tag_rows = conn.execute(
        "SELECT * FROM tag WHERE ticket_id = ? AND event_kind = 'abandoned'", (ticket_id,)
    ).fetchall()
    assert len(tag_rows) == 1
    coverage_rows = conn.execute(
        "SELECT * FROM incident_observation WHERE ticket_id = ? AND record_kind = 'production_coverage'", (ticket_id,)
    ).fetchall()
    assert len(coverage_rows) == 1
    assert coverage_rows[0]["coverage_status"] == "not_deployed"
    later_stage_runs = conn.execute(
        "SELECT * FROM stage_run WHERE ticket_id = ? AND stage IN ('clarification', 'planning', 'implementation', 'checks', 'human_review')", (ticket_id,)
    ).fetchall()
    assert later_stage_runs == []


def test_dry_run_ticket_reads_the_real_atlassian_server():
    """Skipped loudly wherever the pilot's real Atlassian credential or a non-fixture pilot project don't
    exist on this host -- the owner has confirmed neither exists yet, so this test always skips today."""
    if not credentials.available("atlassian_read"):
        pytest.skip("no atlassian_read Keychain item on this host: archaeology cannot reach a real Jira")
    if project.pilot()["name"] == "fixture-project":
        pytest.skip("runner.project.pilot() names the fixture project only: no real pilot repository exists yet")
