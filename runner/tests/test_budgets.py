"""Budget enforcement: a family already over its `tiers.yaml` budget refuses the next invocation; a live wall-clock timeout aborts it.

`check_before_invocation` is exercised directly against
`fixtures/budgets/tiers.yaml`, monkeypatched over `run_ledger.TIERS_PATH`
so a family can be pushed over budget with a handful of tokens rather than
the real committed matrix's hundreds of thousands; `abort` and the wiring
through `adapters.cursor_sdk.invoke` are exercised against the real
committed tier budgets, which are generous enough that only a deliberate
timeout or a deliberately pre-seeded family trips them.
"""
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from runner import budgets, manifest, queue, record, run_ledger, stages, tickets
from runner.adapters import cursor_sdk
from runner.db import connect

TIERS_PATH = Path(__file__).parent / "fixtures" / "budgets" / "tiers.yaml"
MANIFEST_FIXTURES_DIR = Path(__file__).parent / "fixtures" / "manifest"
OWNERS_PATH = MANIFEST_FIXTURES_DIR / "owners.yaml"
ADAPTER_FIXTURES_DIR = Path(__file__).parent / "fixtures" / "adapter"

_COMMIT_ENV = {
    "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@example.invalid",
}


def _git(args, cwd):
    return subprocess.run(
        ["git", "-c", "commit.gpgsign=false", *args], cwd=cwd, env={**os.environ, **_COMMIT_ENV},
        capture_output=True, text=True, check=True,
    )


def _committed_copy(tmp_path: Path, fixture_name: str) -> Path:
    """Copy `fixtures/manifest/<fixture_name>/factory` into a fresh, committed git repo; return its root."""
    repo = tmp_path / fixture_name
    shutil.copytree(MANIFEST_FIXTURES_DIR / fixture_name / "factory", repo / "factory")
    _git(["init", "-q"], cwd=repo)
    _git(["add", "factory"], cwd=repo)
    _git(["commit", "-q", "-m", "init"], cwd=repo)
    return repo


@pytest.fixture
def conn(tmp_path):
    connection = connect(tmp_path / "factory.sqlite")
    yield connection
    connection.close()


def _ticket_in(conn, state, **fields):
    ticket_id = tickets.open_ticket(conn, **fields)
    record.update(conn, "ticket", ticket_id, state=state)
    return ticket_id


def _entry(**overrides) -> manifest.Entry:
    fields = dict(
        stage="S1", tier="light", agent="factory/agents/S1.md", skill="factory/skills/S1.md",
        shared_skills=(), rubric="factory/rubrics/S1.md", tool_allowlist=("read_file",),
        budget_source="factory/config/tiers.yaml", budget={"tokens": 100, "wall_clock_seconds": 1},
        runtime_adapter="cursor_sdk", runtime_version="1.0.31", model_requested="claude-sonnet-5",
        grader_model="claude-sonnet-5", sandbox_policy="thin", toolchain={"jdk": "17"},
        restatement_model=None, agent_hash="a", skill_hash="s", shared_skill_hashes=(),
        rubric_hash="r", manifest_hash="m",
    )
    fields.update(overrides)
    return manifest.Entry(**fields)


def _runtime_path(tmp_path: Path) -> Path:
    doc = yaml.safe_load((ADAPTER_FIXTURES_DIR / "runtime.yaml").read_text())
    doc["adapters"]["cursor_sdk"]["command"] = [sys.executable, str(ADAPTER_FIXTURES_DIR / "fixture_worker.py")]
    path = tmp_path / "runtime.yaml"
    path.write_text(yaml.safe_dump(doc))
    return path


def _env_source(case: str) -> dict:
    return {"PATH": os.environ.get("PATH", ""), "FIXTURE_ADAPTER_CASE": case}


# ---- a family already over its stage-and-tier budget refuses the next invocation (criterion 11) ----


def test_check_before_invocation_refuses_a_family_already_over_its_stage_budget(conn, monkeypatch):
    """a run whose own settled tokens already exceed its stage-and-tier budget refuses the next sibling."""
    monkeypatch.setattr(run_ledger, "TIERS_PATH", TIERS_PATH)
    ticket_id = _ticket_in(conn, "clarifying")
    parent_id = record.insert(
        conn, "stage_run", ticket_id=ticket_id, stage="S2", attempt=1, run_kind="task",
        tokens_in=80, tokens_out=30, outcome="pass",
    )
    ticket = record.get(conn, "ticket", ticket_id)

    reason = budgets.check_before_invocation(conn, ticket, "S2", "light", parent_run_id=parent_id)

    assert reason is not None
    assert "tokens" in reason


def test_check_before_invocation_allows_a_family_still_under_budget(conn, monkeypatch):
    """a family well under its budget is never refused."""
    monkeypatch.setattr(run_ledger, "TIERS_PATH", TIERS_PATH)
    ticket_id = _ticket_in(conn, "clarifying")
    parent_id = record.insert(
        conn, "stage_run", ticket_id=ticket_id, stage="S2", attempt=1, run_kind="task",
        tokens_in=5, tokens_out=5, outcome="pass",
    )
    ticket = record.get(conn, "ticket", ticket_id)

    assert budgets.check_before_invocation(conn, ticket, "S2", "light", parent_run_id=parent_id) is None


# ---- S4's cumulative per-ticket budget, checked before every fresh execution (criteria 12, 14) ----


def test_check_before_invocation_refuses_when_s4_cumulative_usage_exceeds_the_per_ticket_budget(conn, monkeypatch):
    """S4's cumulative tokens across every task invocation of the ticket, not just one family, trip the per-ticket budget."""
    monkeypatch.setattr(run_ledger, "TIERS_PATH", TIERS_PATH)
    ticket_id = _ticket_in(conn, "implementing")
    record.insert(
        conn, "stage_run", ticket_id=ticket_id, stage="S4", attempt=1, run_kind="task",
        tokens_in=300, tokens_out=250, outcome="pass",
    )
    ticket = record.get(conn, "ticket", ticket_id)

    # parent_run_id=None: a fresh top-level task attempt, so the plain
    # per-stage family check alone (nothing yet in this new run's own
    # family) would pass -- only the S4-cumulative check catches it.
    reason = budgets.check_before_invocation(conn, ticket, "S4", "light", parent_run_id=None)

    assert reason is not None
    assert "S4" in reason


def test_check_before_invocation_allows_a_fresh_s4_execution_under_the_cumulative_budget(conn, monkeypatch):
    """a ticket whose S4 history is still under the per-ticket budget is never refused."""
    monkeypatch.setattr(run_ledger, "TIERS_PATH", TIERS_PATH)
    ticket_id = _ticket_in(conn, "implementing")
    record.insert(
        conn, "stage_run", ticket_id=ticket_id, stage="S4", attempt=1, run_kind="task",
        tokens_in=10, tokens_out=10, outcome="pass",
    )
    ticket = record.get(conn, "ticket", ticket_id)

    assert budgets.check_before_invocation(conn, ticket, "S4", "light", parent_run_id=None) is None


# ---- a child's usage counts against its parent's family budget (criterion 15) ----


def test_a_childs_usage_counts_toward_its_parents_family_budget(conn, monkeypatch):
    """a child stage_run's tokens, recorded through parent_run_id, count against the same family budget as its parent."""
    monkeypatch.setattr(run_ledger, "TIERS_PATH", TIERS_PATH)
    ticket_id = _ticket_in(conn, "clarifying")
    parent_id = record.insert(
        conn, "stage_run", ticket_id=ticket_id, stage="S2", attempt=1, run_kind="task",
        tokens_in=10, tokens_out=10, outcome="pass",
    )
    record.insert(
        conn, "stage_run", ticket_id=ticket_id, stage="S2", attempt=1, run_kind="task",
        parent_run_id=parent_id, tokens_in=50, tokens_out=40, outcome="pass",
    )
    ticket = record.get(conn, "ticket", ticket_id)

    reason = budgets.check_before_invocation(conn, ticket, "S2", "light", parent_run_id=parent_id)

    assert reason is not None  # 20 (parent) + 90 (child) = 110 > the light budget of 100


# ---- wall clock is enforced live by the launcher's own timeout (criterion 13) ----


def test_a_launcher_timeout_aborts_the_run_budget_and_escalates(tmp_path):
    """a launcher timeout ends the run `aborted_budget`, not `infrastructure_failure`, and escalates the ticket."""
    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = tickets.open_ticket(conn, worktree_path=str(tmp_path / "worktree"))
    record.update(conn, "ticket", ticket_id, state="context")
    (tmp_path / "worktree").mkdir()
    ticket = record.get(conn, "ticket", ticket_id)

    result = cursor_sdk.invoke(
        conn, ticket=ticket, stage="S1", tier="light", entry=_entry(budget={"tokens": 400000, "wall_clock_seconds": 1}),
        runs_dir=tmp_path / "runs", runtime_path=_runtime_path(tmp_path), sandbox_path=ADAPTER_FIXTURES_DIR / "sandbox.yaml",
        env_source=_env_source("timeout"),
    )

    assert result.outcome == "aborted_budget"
    assert result.failure_kind is None
    run = record.get(conn, "stage_run", result.stage_run_id)
    assert run["outcome"] == "aborted_budget"
    assert record.get(conn, "ticket", ticket_id)["state"] == "escalated"
    item = conn.execute(
        "SELECT * FROM queue_item WHERE ticket_id = ? AND kind = 'escalation'", (ticket_id,)
    ).fetchone()
    assert item is not None
    assert item["ref"] == f"stage_run:{result.stage_run_id}"


def test_cursor_sdk_invoke_aborts_before_launching_when_s4_cumulative_budget_is_already_spent(tmp_path, monkeypatch):
    """tokens are checked at the invocation boundary: an S4 attempt whose ticket already spent its per-ticket budget never launches."""
    monkeypatch.setattr(run_ledger, "TIERS_PATH", TIERS_PATH)
    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = tickets.open_ticket(conn, worktree_path=str(tmp_path / "worktree"))
    record.update(conn, "ticket", ticket_id, state="implementing")
    (tmp_path / "worktree").mkdir()
    record.insert(
        conn, "stage_run", ticket_id=ticket_id, stage="S4", attempt=1, run_kind="task",
        tokens_in=400, tokens_out=200, outcome="pass",
    )
    ticket = record.get(conn, "ticket", ticket_id)

    result = cursor_sdk.invoke(
        conn, ticket=ticket, stage="S4", tier="light", entry=_entry(stage="S4", budget={"tokens": 400000, "wall_clock_seconds": 1200}),
        runs_dir=tmp_path / "runs", runtime_path=_runtime_path(tmp_path), sandbox_path=ADAPTER_FIXTURES_DIR / "sandbox.yaml",
        env_source=_env_source("settled"),
    )

    assert result.outcome == "aborted_budget"
    assert record.get(conn, "ticket", ticket_id)["state"] == "escalated"
    # never launched at all: no tool_call or artefact row exists for it.
    assert conn.execute(
        "SELECT COUNT(*) FROM artefact WHERE stage_run_id = ?", (result.stage_run_id,)
    ).fetchone()[0] == 0
    assert conn.execute(
        "SELECT COUNT(*) FROM tool_call WHERE stage_run_id = ?", (result.stage_run_id,)
    ).fetchone()[0] == 0


# ---- the escalation note: reasoning summary, outputs, binding, failure history, S4 progress (criterion 16) ----


def _open_escalation_item(conn, ticket_id):
    return conn.execute(
        "SELECT * FROM queue_item WHERE ticket_id = ? AND kind = 'escalation' AND resolved_at IS NULL", (ticket_id,)
    ).fetchone()


def test_abort_leaves_the_agents_reasoning_summary_alone_and_the_escalation_item_carries_the_derived_context(conn):
    """The escalation item's reason, binding, failure history and S4 progress are derived from the record; the agent's own summary is not overwritten."""
    ticket_id = _ticket_in(conn, "implementing")
    record.insert(
        conn, "stage_run", ticket_id=ticket_id, stage="S4", attempt=1, run_kind="task",
        outcome="fail", failure_kind="implementation",
    )
    binding_id = record.insert(
        conn, "evidence_tuple", ticket_id=ticket_id, kind="plan", content_hash="plan-subject",
        canonical_serialization_version=1,
    )
    run_id = record.insert(conn, "stage_run", ticket_id=ticket_id, stage="S4", attempt=2, run_kind="task")
    ticket = record.get(conn, "ticket", ticket_id)

    budgets.abort(conn, ticket, run_id, reason="exceeded the per-ticket S4 token budget")

    run = record.get(conn, "stage_run", run_id)
    assert run["outcome"] == "aborted_budget"
    assert run["reasoning_summary"] is None
    note = queue.escalation_context(conn, _open_escalation_item(conn, ticket_id))
    assert note["reason"] == "exceeded the per-ticket S4 token budget"
    assert note["binding_evidence_tuple_id"] == binding_id
    assert note["failure_history"] == [{"attempt": 1, "outcome": "fail", "failure_kind": "implementation"}]
    assert note["registered_outputs"] == []
    # S4 progress: neither attempt ever reached outcome=pass, so nothing
    # counts as a completed task; both task rows (the earlier failure and
    # the just-aborted attempt itself) count toward execution_count.
    assert note["last_completed_task"] is None
    assert note["execution_count"] == 2
    assert note["verification_count"] == 0


def test_abort_reports_the_last_completed_task_and_verification_count_for_s4(conn):
    """S4-specific progress: the highest passing task attempt, the execution count, and the verification count."""
    ticket_id = _ticket_in(conn, "implementing")
    record.insert(conn, "stage_run", ticket_id=ticket_id, stage="S4", attempt=1, run_kind="task", outcome="pass")
    record.insert(conn, "stage_run", ticket_id=ticket_id, stage="S4", attempt=1, run_kind="validation_only", outcome="fail")
    record.insert(conn, "stage_run", ticket_id=ticket_id, stage="S4", attempt=2, run_kind="fix_round", outcome="pass")
    record.insert(conn, "stage_run", ticket_id=ticket_id, stage="S4", attempt=2, run_kind="validation_only", outcome="fail")
    run_id = record.insert(conn, "stage_run", ticket_id=ticket_id, stage="S4", attempt=3, run_kind="fix_round")
    ticket = record.get(conn, "ticket", ticket_id)

    budgets.abort(conn, ticket, run_id, reason="over budget")

    note = queue.escalation_context(conn, _open_escalation_item(conn, ticket_id))
    assert note["last_completed_task"] == 2
    assert note["execution_count"] == 3  # attempts 1, 2 (both pass/fail-irrelevant task/fix_round rows), and the aborted 3
    assert note["verification_count"] == 2


# ---- isolation: the worktree and its files survive an abort untouched (criterion 18) ----


def test_abort_leaves_the_ticket_worktree_and_its_files_untouched(conn, tmp_path):
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    (worktree / "in_progress.txt").write_text("partial work\n")
    ticket_id = _ticket_in(conn, "implementing", worktree_path=str(worktree))
    run_id = record.insert(conn, "stage_run", ticket_id=ticket_id, stage="S4", attempt=1, run_kind="task")
    ticket = record.get(conn, "ticket", ticket_id)

    budgets.abort(conn, ticket, run_id, reason="over budget")

    assert worktree.exists()
    assert (worktree / "in_progress.txt").read_text() == "partial work\n"


# ---- budget abort never consumes a verification attempt or opens a new run (criterion 17) ----


def test_abort_never_opens_a_new_run_or_touches_verification_attempt(conn):
    ticket_id = _ticket_in(conn, "implementing")
    run_id = record.insert(
        conn, "stage_run", ticket_id=ticket_id, stage="S4", attempt=1, run_kind="task", verification_attempt=2,
    )
    ticket = record.get(conn, "ticket", ticket_id)
    before = conn.execute("SELECT COUNT(*) FROM stage_run").fetchone()[0]

    budgets.abort(conn, ticket, run_id, reason="over budget")

    after = conn.execute("SELECT COUNT(*) FROM stage_run").fetchone()[0]
    assert after == before
    run = record.get(conn, "stage_run", run_id)
    assert run["verification_attempt"] == 2
    assert run["attempt"] == 1


# ---- a changed S4 budget is plan-bound: migration and reapproval before it takes effect (criterion 19) ----


def test_a_changed_s4_budget_requires_migration_and_reapproval_before_it_takes_effect(tmp_path):
    """lowering tiers.yaml's S4 budget changes the manifest hash; a ticket pinned to the old hash is refused until `migrate-manifest` re-pins it."""
    repo = _committed_copy(tmp_path, "reapproval")
    old_hash = manifest.current_hash(repo)

    tiers_path = repo / "factory" / "config" / "tiers.yaml"
    old_tiers_hash = hashlib.sha256(tiers_path.read_bytes()).hexdigest()
    new_text = tiers_path.read_text().replace("tokens: 5000", "tokens: 2500", 1)
    tiers_path.write_text(new_text)
    new_tiers_hash = hashlib.sha256(new_text.encode()).hexdigest()

    manifest_path = repo / "factory" / "manifest.yaml"
    manifest_path.write_text(manifest_path.read_text().replace(old_tiers_hash, new_tiers_hash, 1))
    _git(["add", "-A"], cwd=repo)
    _git(["commit", "-q", "-m", "lower the S4 per-ticket budget"], cwd=repo)

    new_hash = manifest.current_hash(repo)
    assert new_hash != old_hash

    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = tickets.open_ticket(conn, factory_manifest_hash=old_hash)
    record.update(conn, "ticket", ticket_id, state="implementing")
    ticket = record.get(conn, "ticket", ticket_id)

    outcome = stages.invoke_agent(conn, ticket, "S5", tier="light", manifest_path=manifest_path, runs_dir=tmp_path)
    assert outcome == "refused_request"
    assert conn.execute("SELECT COUNT(*) FROM stage_run").fetchone()[0] == 0

    manifest.migrate(conn, actor="abhishek", root=repo, owners_path=OWNERS_PATH)

    ticket = record.get(conn, "ticket", ticket_id)
    assert ticket["factory_manifest_hash"] == new_hash

    outcome = stages.invoke_agent(conn, ticket, "S5", tier="light", manifest_path=manifest_path, runs_dir=tmp_path)
    assert outcome == "pass"
