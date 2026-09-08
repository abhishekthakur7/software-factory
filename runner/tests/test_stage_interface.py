"""`factory pause`, `factory resume`, `factory stop`, and `factory show`
over the durable pause flag `advance` checks before each recorded
boundary.

Every seeded "live" run in this file opens with no monkeypatched process
identity at all, so `run_ledger.process_identity()` names this very test
process -- `run_ledger.process_alive` then finds it genuinely alive, the
same convention `test_crash_recovery.py` uses for its own alive-process
negative case, just exercised here as the positive one `control.live_run`
must detect.
"""
import os
import subprocess

import pytest

from runner import cli, git_trees, manifest, queue, record, run_ledger
from runner.db import connect
from runner.paths import FACTORY_DIR

ABHISHEK = "abhishek"
S1_FIXTURE_OUT = FACTORY_DIR / "evals" / "agents" / "S1" / "fixtures" / "plain_ok" / "out"
_COMMIT_ENV = {
    "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@example.invalid",
}


@pytest.fixture
def conn(tmp_path):
    connection = connect(tmp_path / "factory.sqlite")
    yield connection
    connection.close()


def _ticket_in(conn, state, **fields):
    return record.insert(conn, "ticket", state=state, opened_at=record.now(), **fields)


def _source_repo_with_pom(tmp_path):
    """A trivial one-commit git repository carrying the pom and the one Java file the
    `plain_ok` S1 fixture's Flags row references -- the now-real S1 needs a real worktree."""
    repo = tmp_path / "source-repo"
    repo.mkdir()
    subprocess.run(["git", "-c", "commit.gpgsign=false", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "-c", "commit.gpgsign=false", "checkout", "-q", "-b", "main"], cwd=repo, check=True)
    (repo / "pom.xml").write_text(
        "<project>\n  <groupId>com.example</groupId>\n  <artifactId>widget</artifactId>\n  <version>1.0.0</version>\n"
        "  <dependencies>\n    <dependency>\n      <groupId>com.fixturevendor</groupId>\n"
        "      <artifactId>strings</artifactId>\n      <version>1.0.0</version>\n    </dependency>\n  </dependencies>\n"
        "</project>\n"
    )
    src = repo / "src" / "main" / "java" / "com" / "example"
    src.mkdir(parents=True)
    (src / "Handler.java").write_text("package com.example;\n\npublic class Handler {\n}\n")
    subprocess.run(["git", "-c", "commit.gpgsign=false", "add", "-A"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "commit", "-q", "-m", "init"], cwd=repo,
        env={**os.environ, **_COMMIT_ENV}, check=True,
    )
    return repo


def _s1_ready_ticket(conn, tmp_path, state="context"):
    """A ticket at `state`, cloned from a real worktree and pinned, eligible to invoke a real S1."""
    ticket_id = _ticket_in(
        conn, state, service="fixture-project", tier_provisional="standard",
        factory_manifest_hash=manifest.current_hash(),
    )
    source = _source_repo_with_pom(tmp_path)
    trees = git_trees.clone_for_ticket(conn, ticket_id, source_checkout=source, target_branch="main", runs_dir=tmp_path)
    git_trees.record_head(conn, ticket_id, trees.worktree)
    return ticket_id


def _open_live_run(conn, ticket_id, stage="S4") -> int:
    """An open `stage_run` whose process identity is this test process itself: a genuinely live run."""
    return run_ledger.open_stage_run(conn, ticket_id=ticket_id, stage=stage)


# --- criteria 1-4: stop terminates a running stage; every other command refuses one ---


def test_stop_terminates_the_running_stage_records_aborted_human_and_escalates(conn, tmp_path):
    """R-I-8, criteria 1-3: `factory stop` finishes the open run `aborted_human`
    with the given note as its reasoning summary, and moves the ticket to `escalated`."""
    ticket_id = _ticket_in(conn, "implementing")
    run_id = _open_live_run(conn, ticket_id, stage="S4")

    result = cli.stop(conn, ticket_id, actor=ABHISHEK, fm_id="FM-07", note="stopped for a manual check")

    assert "stopped" in result
    run = record.get(conn, "stage_run", run_id)
    assert run["outcome"] == "aborted_human"
    assert run["reasoning_summary"] == "stopped for a manual check"
    assert record.get(conn, "ticket", ticket_id)["state"] == "escalated"
    item = conn.execute(
        "SELECT * FROM queue_item WHERE ticket_id = ? AND kind = 'escalation'", (ticket_id,)
    ).fetchone()
    assert item is not None
    assert item["ref"] == f"stage_run:{run_id}"
    tag = conn.execute("SELECT * FROM tag WHERE ticket_id = ? AND event_kind = 'escalation'", (ticket_id,)).fetchone()
    assert tag is not None


def test_stop_keeps_a_run_s_own_reasoning_summary_over_the_stop_note(conn):
    """`stop` only stores its note as the reasoning summary when the run has none yet."""
    ticket_id = _ticket_in(conn, "implementing")
    run_id = _open_live_run(conn, ticket_id, stage="S4")
    run_ledger.record_reasoning_summary(conn, run_id, "the agent's own report")

    cli.stop(conn, ticket_id, actor=ABHISHEK, fm_id="FM-07", note="a stop note")

    assert record.get(conn, "stage_run", run_id)["reasoning_summary"] == "the agent's own report"


def test_must_reject_every_command_but_stop_while_a_run_is_live(conn, tmp_path):
    """R-I-8, criterion 4: a seeded live stage run refuses `pause`, `resume`, `run`,
    `advance`, and `act` on the ticket's open item, leaving the run untouched;
    `stop` alone terminates it."""
    ticket_id = _ticket_in(conn, "implementing")
    run_id = _open_live_run(conn, ticket_id, stage="S4")
    question_id = record.insert(
        conn, "question", ticket_id=ticket_id, stage="S2", round=1, rank=1,
        options='[{"label": "A", "consequence": "does A"}]', default_option=0, state="open",
    )
    item_id = queue.open_item(conn, ticket_id=ticket_id, kind="question", ref=f"question:{question_id}")

    assert "live run" in cli.pause(conn, ticket_id)
    assert "live run" in cli.resume(conn, ticket_id, actor=ABHISHEK)
    assert "live run" in cli.run(conn, ticket_id, "S4", runs_dir=tmp_path)
    assert "live run" in cli.advance(conn, ticket_id, tmp_path)
    with pytest.raises(queue.ActionRefused, match="live run"):
        queue.act(conn, item_id=item_id, action="answer", actor=ABHISHEK, runs_dir=tmp_path)

    # Nothing above touched the run, the ticket's state, or the question item.
    run = record.get(conn, "stage_run", run_id)
    assert run["outcome"] is None
    assert record.get(conn, "ticket", ticket_id)["state"] == "implementing"
    assert record.get(conn, "queue_item", item_id)["resolved_at"] is None

    result = cli.stop(conn, ticket_id, actor=ABHISHEK, fm_id="FM-07")
    assert "stopped" in result
    assert record.get(conn, "stage_run", run_id)["outcome"] == "aborted_human"


# --- criterion 5: neither stop nor pause injects steering text or touches artefacts ---


def test_pause_and_stop_leave_the_running_stage_s_registered_artefacts_untouched(conn, tmp_path):
    """R-I-8, criterion 5: a pause request and a stop change no byte of the
    run's already-registered artefact file, its `artefact` row, or its
    `inputs`, and add no new artefact -- neither ever writes steering text
    into a live run's own inputs or outputs."""
    from runner import artefact_registry
    from runner.fs import write_text

    ticket_id = _ticket_in(conn, "implementing")
    run_id = _open_live_run(conn, ticket_id, stage="S4")
    artefact_path = tmp_path / "handoff.md"
    write_text(artefact_path, "stub handoff artefact\n")
    artefact_id = artefact_registry.register(conn, ticket_id=ticket_id, kind="handoff", path=artefact_path, stage_run_id=run_id)
    before_row = dict(record.get(conn, "artefact", artefact_id))
    before_run_inputs = record.get(conn, "stage_run", run_id)["inputs"]
    before_bytes = artefact_path.read_bytes()
    before_count = conn.execute("SELECT COUNT(*) FROM artefact").fetchone()[0]

    cli.pause(conn, ticket_id)

    assert record.get(conn, "stage_run", run_id)["inputs"] == before_run_inputs
    assert artefact_path.read_bytes() == before_bytes
    assert dict(record.get(conn, "artefact", artefact_id)) == before_row
    assert conn.execute("SELECT COUNT(*) FROM artefact").fetchone()[0] == before_count

    cli.stop(conn, ticket_id, actor=ABHISHEK, fm_id="FM-07")

    assert record.get(conn, "stage_run", run_id)["inputs"] == before_run_inputs
    assert artefact_path.read_bytes() == before_bytes
    assert dict(record.get(conn, "artefact", artefact_id)) == before_row
    assert conn.execute("SELECT COUNT(*) FROM artefact").fetchone()[0] == before_count


# --- criteria 6, 8, 11, 12: pause takes effect only at the next boundary ---


def test_pause_takes_effect_at_the_next_boundary_not_immediately(conn, tmp_path):
    """R-I-8, R-H-13, criteria 6, 8: a pending pause, read from the durable
    `ticket.pause_requested` column, is honoured immediately before `advance`
    would start the next due stage, running nothing that call."""
    ticket_id = _ticket_in(conn, "context")
    record.update(conn, "ticket", ticket_id, pause_requested=1)  # set directly: proves the durable column is read

    result = cli.advance(conn, ticket_id, tmp_path)

    assert result == f"ticket {ticket_id}: paused at context"
    assert conn.execute("SELECT COUNT(*) FROM stage_run WHERE ticket_id = ?", (ticket_id,)).fetchone()[0] == 0
    ticket = record.get(conn, "ticket", ticket_id)
    assert ticket["paused_at"] is not None
    item = conn.execute(
        "SELECT * FROM queue_item WHERE ticket_id = ? AND kind = 'manual_pause' AND resolved_at IS NULL",
        (ticket_id,),
    ).fetchone()
    assert item is not None


def test_a_pause_request_at_a_boundary_never_opens_a_second_manual_pause_item(conn, tmp_path):
    """R-H-13, criterion 12: a pause request arriving at the same moment as a
    boundary crossing resolves to pausing there, repeatably -- a second
    `advance` call while still paused opens no duplicate `manual_pause` item
    and still runs nothing."""
    ticket_id = _ticket_in(conn, "context")
    cli.pause(conn, ticket_id)

    cli.advance(conn, ticket_id, tmp_path)
    cli.advance(conn, ticket_id, tmp_path)

    items = conn.execute(
        "SELECT id FROM queue_item WHERE ticket_id = ? AND kind = 'manual_pause'", (ticket_id,)
    ).fetchall()
    assert len(items) == 1
    assert conn.execute("SELECT COUNT(*) FROM stage_run WHERE ticket_id = ?", (ticket_id,)).fetchone()[0] == 0


def test_resume_continues_the_paused_ticket_from_its_held_boundary(conn, tmp_path, monkeypatch):
    """R-H-13, criterion 11: `factory resume` resolves the open `manual_pause`
    item and clears the pause flag, and the next `advance` runs the stage the
    pause had held."""
    ticket_id = _s1_ready_ticket(conn, tmp_path)
    cli.pause(conn, ticket_id)
    cli.advance(conn, ticket_id, tmp_path)

    result = cli.resume(conn, ticket_id, actor=ABHISHEK)

    assert "resolved" in result
    ticket = record.get(conn, "ticket", ticket_id)
    assert ticket["pause_requested"] == 0
    item = conn.execute(
        "SELECT resolved_at FROM queue_item WHERE ticket_id = ? AND kind = 'manual_pause'", (ticket_id,)
    ).fetchone()
    assert item["resolved_at"] is not None

    monkeypatch.setenv("FIXTURE_ADAPTER_OUT_DIR", str(S1_FIXTURE_OUT))
    cli.advance(conn, ticket_id, tmp_path)

    # S1's own agent invocation opens a second, child `stage_run` under
    # the same stage name once it passes, so one stage running is two rows.
    assert conn.execute("SELECT COUNT(*) FROM stage_run WHERE ticket_id = ?", (ticket_id,)).fetchone()[0] == 2
    assert record.get(conn, "ticket", ticket_id)["state"] == "clarifying"


def test_must_reject_resume_with_no_open_pause_to_resume(conn):
    """a ticket with no open `manual_pause` item refuses `resume`."""
    ticket_id = _ticket_in(conn, "context")
    result = cli.resume(conn, ticket_id, actor=ABHISHEK)
    assert "no open pause" in result


# --- criteria 7, 9: `factory show` reports stage, attempt, elapsed, budget, outputs, pause ---


def test_show_reports_stage_attempt_elapsed_budget_and_pause_state(conn, tmp_path):
    """R-H-13, criterion 7: `factory show` reports the open run's stage,
    attempt, elapsed wall clock, and tier budget remaining, and that no
    pause is pending."""
    ticket_id = _ticket_in(conn, "implementing", tier_final="light")
    _open_live_run(conn, ticket_id, stage="S4")

    output = cli.show(conn, ticket_id)

    assert "current: S4 attempt 1" in output
    assert "elapsed" in output
    assert "budget remaining: tokens 400000" in output
    assert "pause pending: False" in output


def test_show_lists_a_paused_ticket_s_registered_output_artefact(conn, tmp_path, monkeypatch):
    """R-H-13, criterion 9: given a ticket paused mid-pipeline with one
    registered output artefact from its latest completed run, `factory
    show` lists that artefact's path among the run's currently registered
    outputs, and reports the pause as pending."""
    ticket_id = _s1_ready_ticket(conn, tmp_path)
    monkeypatch.setenv("FIXTURE_ADAPTER_OUT_DIR", str(S1_FIXTURE_OUT))
    cli.advance(conn, ticket_id, tmp_path)  # S1 runs for real and passes, registering `brief`
    assert record.get(conn, "ticket", ticket_id)["state"] == "clarifying"
    cli.pause(conn, ticket_id)

    cli.advance(conn, ticket_id, tmp_path)  # paused at the clarifying boundary before S2 ever starts
    output = cli.show(conn, ticket_id)

    assert "brief.md" in output
    assert "pause pending: True" in output


# --- criterion 10: send-back from any open item, with no approval added ---

_SEND_BACK_STATES = {
    "plan_approval": "plan_review",
    "packet_approval": "review",
    "red_check": "checks",
    "escalation": "checks",
    "manual_pause": "implementing",
}


def _seed_send_back_item(conn, kind: str) -> tuple[int, int]:
    ticket_id = _ticket_in(conn, _SEND_BACK_STATES[kind])
    kwargs = {"ticket_id": ticket_id, "kind": kind}
    if kind == "escalation":
        stage_run_id = record.insert(conn, "stage_run", ticket_id=ticket_id, stage="S4", attempt=1, outcome="fail")
        kwargs["ref"] = f"stage_run:{stage_run_id}"
    item_id = queue.open_item(conn, **kwargs)
    return ticket_id, item_id


@pytest.mark.parametrize("kind", sorted(_SEND_BACK_STATES))
def test_send_back_from_any_open_item_moves_the_ticket_and_adds_no_approval(conn, kind):
    """R-H-13, criterion 10: from a plan approval, packet approval, red
    check, escalation, or manual-pause item, a human may send the ticket
    back with a `send_back` tag, and no `approval_record` row is added."""
    ticket_id, item_id = _seed_send_back_item(conn, kind)
    before_approvals = conn.execute("SELECT COUNT(*) FROM approval_record").fetchone()[0]

    queue.act(conn, item_id=item_id, action="send_back", actor=ABHISHEK, to="context", fm_id="FM-07")

    assert record.get(conn, "ticket", ticket_id)["state"] == "context"
    assert record.get(conn, "queue_item", item_id)["resolved_at"] is not None
    tag = conn.execute(
        "SELECT * FROM tag WHERE ref = ? AND event_kind = 'send_back'", (f"queue_item:{item_id}",)
    ).fetchone()
    assert tag is not None
    assert conn.execute("SELECT COUNT(*) FROM approval_record").fetchone()[0] == before_approvals
