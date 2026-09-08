"""The ticket-state table: every transition a ticket can take.

Each test seeds a ticket (and, for the gate-derived events, the record
rows a real quorum/freshness/reviewer-set/outbox computation would leave
behind) and asserts the resulting state, never the table's own content --
a test that only re-read `state_table.TABLE` back to itself would prove
nothing about whether the table is *right*, only that it is internally
consistent. Fixture families under `fixtures/state_table/` back the
gate-derived transitions; a small loader below inserts their rows through `record.insert`, resolving `$name` references
to a previously inserted row's id.
"""
import os
import subprocess
from pathlib import Path

import pytest
import yaml

from runner import artefact_registry, gates, git_trees, manifest, record, tickets, transitions
from runner.db import connect
from runner.paths import FACTORY_DIR
from runner.stages import run_stage
from runner.state_table import TERMINAL_STATES
from runner.transitions import TransitionRefused

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "state_table"
S3_FIXTURES_DIR = Path(__file__).parent / "fixtures" / "s3"
S4_HANDOFF_FIXTURES_DIR = Path(__file__).parent / "fixtures" / "s4_handoff"

_COMMIT_ENV = {
    "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@example.invalid",
}


def _git(args, cwd, env=None):
    full_env = {**os.environ, **env} if env else None
    return subprocess.run(
        ["git", "-c", "commit.gpgsign=false", *args], cwd=cwd, env=full_env,
        capture_output=True, text=True, check=True,
    )


def _source_repo(tmp_path):
    repo = tmp_path / "source-repo"
    repo.mkdir()
    _git(["init", "-q"], cwd=repo)
    _git(["checkout", "-q", "-b", "main"], cwd=repo)
    (repo / "README.md").write_text("seed\n")
    _git(["add", "-A"], cwd=repo)
    _git(["commit", "-q", "-m", "init"], cwd=repo, env=_COMMIT_ENV)
    return repo


def _plan_review_ticket(conn, tmp_path):
    """A ticket cloned from a real repository, sitting in `plan_review`
    with a plan tuple and quorum that match its real, fetchable base --
    `plan_review_gate` now runs the real `BEFORE_S4` freshness check, so a
    bare ticket with a hand-written `base_sha` string can no longer stand
    in for one at this gate."""
    source = _source_repo(tmp_path)
    ticket_id = record.insert(conn, "ticket", state="intake", opened_at=record.now())
    runs_dir = tmp_path / "runs"
    trees = git_trees.clone_for_ticket(
        conn, ticket_id, source_checkout=source, target_branch="main", runs_dir=runs_dir,
    )
    record.update(conn, "ticket", ticket_id, state="plan_review")
    record.insert(
        conn, "evidence_tuple", kind="plan", ticket_id=ticket_id,
        base_sha=trees.base_sha, target_base_sha=trees.base_sha, content_hash="plan-subject-1",
    )
    record.insert(
        conn, "approval_record", ticket_id=ticket_id, gate="plan", decision="approve", subject_hash="plan-subject-1",
    )
    return ticket_id, source, runs_dir


def _implementing_ticket_with_plan_inputs(conn, tmp_path):
    """A ticket in `implementing` with a real worktree, manifest pin, and a bound plan tuple for a real S4 run."""
    source = _source_repo(tmp_path)
    ticket_id = record.insert(
        conn, "ticket", state="intake", opened_at=record.now(), factory_manifest_hash=manifest.current_hash(),
        tier_final="standard",
    )
    trees = git_trees.clone_for_ticket(conn, ticket_id, source_checkout=source, target_branch="main", runs_dir=tmp_path)
    git_trees.record_head(conn, ticket_id, trees.worktree)
    record.update(conn, "ticket", ticket_id, state="implementing")
    record.insert(
        conn, "evidence_tuple", kind="plan", ticket_id=ticket_id,
        base_sha=trees.base_sha, target_base_sha=trees.base_sha, content_hash="plan-subject-implementing",
    )
    artefact_registry.register(
        conn, ticket_id=ticket_id, kind="plan", path=S4_HANDOFF_FIXTURES_DIR / "plan.md",
    )
    artefact_registry.register(
        conn, ticket_id=ticket_id, kind="criteria", path=S3_FIXTURES_DIR / "criteria.md",
    )
    return ticket_id


@pytest.fixture
def conn(tmp_path):
    connection = connect(tmp_path / "factory.sqlite")
    yield connection
    connection.close()


def _ticket_in(conn, state, **fields):
    """Seed a ticket directly in `state`, bypassing `tickets.open_ticket` (which always opens in intake)."""
    return record.insert(conn, "ticket", state=state, opened_at=record.now(), **fields)


def load_scenario(conn, family: str, scenario: str) -> dict[str, int]:
    """Insert every row of `scenario` from `fixtures/state_table/<family>.yaml`, in order.

    A row's `as: name` is remembered; a later row may reference it with a
    `$name` string, which resolves to that row's id before insert. A
    `fixture:<name>` string resolves to the absolute path of that file
    under `FIXTURES_DIR`, for a row (an `artefact`) that must point at
    real file content rather than a bare string.
    """
    data = yaml.safe_load((FIXTURES_DIR / f"{family}.yaml").read_text())[scenario]
    refs: dict[str, int] = {}

    def resolve(value):
        if isinstance(value, str) and value.startswith("$"):
            return refs[value[1:]]
        if isinstance(value, str) and value.startswith("fixture:"):
            return str(FIXTURES_DIR / value[len("fixture:"):])
        return value

    for table, rows in data.items():
        for row in rows:
            row = dict(row)
            name = row.pop("as", None)
            row_id = record.insert(conn, table, **{k: resolve(v) for k, v in row.items()})
            if name:
                refs[name] = row_id
    return refs


# --- ticket creation ---------------------------------------


def test_a_newly_created_ticket_enters_intake(conn):
    """`tickets.open_ticket` always opens in `intake`."""
    ticket_id = tickets.open_ticket(conn, title="new ticket")
    assert record.get(conn, "ticket", ticket_id)["state"] == "intake"


# --- intake ---------------------------------------------


def test_intake_moves_to_context_on_s0_pass_and_eligibility_granted(conn):
    """S0 pass plus a granted `eligibility` item moves intake -> context."""
    ticket_id = _ticket_in(conn, "intake")
    record.insert(conn, "stage_run", ticket_id=ticket_id, stage="S0", attempt=1, outcome="pass")
    record.insert(conn, "queue_item", ticket_id=ticket_id, kind="eligibility", action="granted")
    ticket = record.get(conn, "ticket", ticket_id)
    event = gates.intake_gate(conn, ticket)
    assert event == "eligibility_granted"
    assert transitions.apply(conn, ticket_id, event) == "context"


def test_intake_eligibility_granted_without_an_s0_pass_withholds_the_gate(conn):
    """a granted `eligibility` item admits nothing until the latest S0 run has passed."""
    ticket_id = _ticket_in(conn, "intake")
    record.insert(conn, "stage_run", ticket_id=ticket_id, stage="S0", attempt=1, outcome="fail")
    record.insert(conn, "queue_item", ticket_id=ticket_id, kind="eligibility", action="granted")
    assert gates.intake_gate(conn, record.get(conn, "ticket", ticket_id)) is None


def test_intake_s0_mechanical_failure_moves_to_rejected(conn):
    """S0's mechanical gate failing moves intake -> rejected."""
    ticket_id = _ticket_in(conn, "intake")
    assert transitions.apply(conn, ticket_id, "s0_reject") == "rejected"
    ticket = record.get(conn, "ticket", ticket_id)
    assert ticket["close_reason"] == "rejected_at_s0"
    assert ticket["closed_at"] is not None


def test_intake_eligibility_declined_moves_to_rejected(conn):
    """a declined `eligibility` item moves intake -> rejected."""
    ticket_id = _ticket_in(conn, "intake")
    record.insert(conn, "queue_item", ticket_id=ticket_id, kind="eligibility", action="declined")
    ticket = record.get(conn, "ticket", ticket_id)
    event = gates.intake_gate(conn, ticket)
    assert event == "eligibility_declined"
    assert transitions.apply(conn, ticket_id, event) == "rejected"
    assert record.get(conn, "ticket", ticket_id)["close_reason"] == "rejected_at_s0"


# --- abandon from every open state -------------------------


@pytest.mark.parametrize(
    "state",
    ["intake", "context", "clarifying", "planning", "plan_review", "implementing", "checks", "review", "escalated"],
)
def test_abandon_moves_any_open_state_to_abandoned(conn, state):
    """each of these states moves to `abandoned` on `abandon`."""
    ticket_id = _ticket_in(conn, state)
    assert transitions.apply(conn, ticket_id, "abandon") == "abandoned"
    assert record.get(conn, "ticket", ticket_id)["close_reason"] == "abandoned"


# --- context --------------------------------------------


def test_context_s1_pass_moves_to_clarifying(conn):
    """an S1 pass moves context -> clarifying."""
    ticket_id = _ticket_in(conn, "context")
    assert transitions.apply(conn, ticket_id, "s1_pass") == "clarifying"


def test_context_s1_exclusion_moves_to_rejected(conn):
    """an S1-discovered Initial exclusion moves context -> rejected."""
    ticket_id = _ticket_in(conn, "context")
    assert transitions.apply(conn, ticket_id, "s1_exclusion") == "rejected"
    assert record.get(conn, "ticket", ticket_id)["close_reason"] == "pilot_excluded"


# --- escalate ------------------------------------


@pytest.mark.parametrize("state", ["context", "clarifying", "planning", "implementing", "checks", "review"])
def test_escalate_moves_any_of_these_states_to_escalated(conn, state):
    """a second failure, budget/sandbox/control cause, or
    stop moves any of these states to `escalated`; the specific cause is
    recorded on the stage_run/tag, not in the transition event."""
    ticket_id = _ticket_in(conn, state)
    assert transitions.apply(conn, ticket_id, "escalate") == "escalated"


# --- clarifying / planning ---------------------------


def test_clarifying_s2_pass_moves_to_planning(conn):
    """S2 exit with no open blocking question moves clarifying -> planning."""
    ticket_id = _ticket_in(conn, "clarifying")
    assert transitions.apply(conn, ticket_id, "s2_pass") == "planning"


def test_planning_s3_pass_moves_to_plan_review(conn):
    """S3 producing the approval bundle moves planning -> plan_review."""
    ticket_id = _ticket_in(conn, "planning")
    assert transitions.apply(conn, ticket_id, "s3_pass") == "plan_review"


def test_planning_s3_exclusion_moves_to_rejected(conn):
    """an S3-discovered Initial exclusion moves planning -> rejected."""
    ticket_id = _ticket_in(conn, "planning")
    assert transitions.apply(conn, ticket_id, "s3_exclusion") == "rejected"
    assert record.get(conn, "ticket", ticket_id)["close_reason"] == "pilot_excluded"


# --- plan_review -----------------------------------


def test_plan_review_quorum_and_freshness_moves_to_implementing(conn, tmp_path):
    """full plan quorum plus base/target-head equality moves plan_review -> implementing."""
    ticket_id, _source, runs_dir = _plan_review_ticket(conn, tmp_path)
    ticket = record.get(conn, "ticket", ticket_id)
    event = gates.plan_review_gate(conn, ticket, runs_dir=runs_dir)
    assert event == "plan_quorum_fresh"
    assert transitions.apply(conn, ticket_id, event) == "implementing"


def test_plan_review_stale_base_withholds_the_gate_and_permits_only_human_action(conn, tmp_path):
    """a stale plan base never advances the gate on its own;
    only a recorded refresh_base or send-back moves the ticket."""
    ticket_id, source, runs_dir = _plan_review_ticket(conn, tmp_path)
    (source / "README.md").write_text("target moved\n")
    _git(["add", "-A"], cwd=source)
    _git(["commit", "-q", "-m", "target moved"], cwd=source, env=_COMMIT_ENV)

    ticket = record.get(conn, "ticket", ticket_id)
    assert gates.plan_review_gate(conn, ticket, runs_dir=runs_dir) is None
    assert transitions.apply(conn, ticket_id, "refresh_base") == "context"


@pytest.mark.parametrize(
    "event,target",
    [
        ("send_back_to_context", "context"),
        ("send_back_to_planning", "planning"),
        ("send_back_to_clarifying", "clarifying"),
    ],
)
def test_plan_review_redirect_targets(conn, event, target):
    """a recorded redirect from plan_review reaches context, planning, or clarifying."""
    ticket_id = _ticket_in(conn, "plan_review")
    assert transitions.apply(conn, ticket_id, event) == target


# --- implementing ----------------------------------


def test_implementing_s4_pass_moves_to_checks(conn):
    """a successful S4 hand-back moves implementing -> checks."""
    ticket_id = _ticket_in(conn, "implementing")
    assert transitions.apply(conn, ticket_id, "s4_pass") == "checks"


def test_implementing_stale_base_withholds_and_permits_only_human_action(conn):
    """a stale plan base at the pre-S4 boundary never advances on its own."""
    refs = load_scenario(conn, "plan_subject", "stale_at_implementing")
    ticket = record.get(conn, "ticket", refs["ticket"])
    # implementing has no gate of its own (see gates.py); the seeded stale
    # tuple only documents why a human would call refresh_base.
    assert transitions.apply(conn, refs["ticket"], "refresh_base") == "context"


@pytest.mark.parametrize(
    "event,target",
    [
        ("send_back_to_context", "context"),
        ("send_back_to_planning", "planning"),
        ("send_back_to_clarifying", "clarifying"),
    ],
)
def test_implementing_redirect_targets(conn, event, target):
    """a recorded redirect from implementing reaches context, planning, or clarifying."""
    ticket_id = _ticket_in(conn, "implementing")
    assert transitions.apply(conn, ticket_id, event) == target


# --- checks ----------------------------


@pytest.mark.parametrize("event", ["checks_bad_handback", "checks_removal_return", "checks_fix_round"])
def test_checks_returns_to_implementing(conn, event):
    """a missing/malformed hand-back, an S4 removal return, or a
    fix round remaining each return checks -> implementing."""
    ticket_id = _ticket_in(conn, "checks")
    assert transitions.apply(conn, ticket_id, event) == "implementing"


def test_checks_stale_review_base_withholds_the_gate(conn):
    """a stale review base never advances checks_gate on its own."""
    refs = load_scenario(conn, "review_subject", "stale")
    ticket = record.get(conn, "ticket", refs["ticket"])
    assert gates.checks_gate(conn, ticket) is None
    assert transitions.apply(conn, refs["ticket"], "refresh_base") == "context"


def test_checks_new_reviewer_slot_moves_to_planning(conn):
    """a new/unresolved non-sensitive reviewer slot moves checks -> planning."""
    refs = load_scenario(conn, "review_subject", "new_reviewer_slot")
    ticket = record.get(conn, "ticket", refs["ticket"])
    event = gates.checks_gate(conn, ticket)
    assert event == "checks_new_reviewer_slot"
    assert transitions.apply(conn, refs["ticket"], event) == "planning"


@pytest.mark.parametrize(
    "event,target",
    [
        ("send_back_to_context", "context"),
        ("send_back_to_planning", "planning"),
        ("send_back_to_clarifying", "clarifying"),
    ],
)
def test_checks_redirect_targets(conn, event, target):
    """a recorded redirect from checks reaches context, planning, or clarifying."""
    ticket_id = _ticket_in(conn, "checks")
    assert transitions.apply(conn, ticket_id, event) == target


def test_checks_sensitive_path_required_by_plan_moves_to_rejected(conn):
    """an accidental Initial-sensitive path required by the plan closes pilot_excluded."""
    ticket_id = _ticket_in(conn, "checks")
    assert transitions.apply(conn, ticket_id, "checks_sensitive_path_required") == "rejected"
    assert record.get(conn, "ticket", ticket_id)["close_reason"] == "pilot_excluded"


def test_checks_s5_pass_alone_does_not_leave_checks(conn):
    """S5's own pass never advances checks_gate without S6."""
    ticket_id = _ticket_in(conn, "checks")
    record.insert(conn, "stage_run", ticket_id=ticket_id, stage="S5", attempt=1, outcome="pass")
    ticket = record.get(conn, "ticket", ticket_id)
    assert gates.checks_gate(conn, ticket) is None


def test_checks_s5_and_s6_pass_moves_to_review(conn):
    """only once both the latest S5 and the S6 assembly run have passed does checks -> review."""
    refs = load_scenario(conn, "s6_assembly", "both_pass")
    ticket = record.get(conn, "ticket", refs["ticket"])
    event = gates.checks_gate(conn, ticket)
    assert event == "checks_pass_to_review"
    assert transitions.apply(conn, refs["ticket"], event) == "review"


# --- review --------------------------------


def test_review_quorum_and_reconciled_receipt_moves_to_pr_opened(conn):
    """full review quorum plus a reconciled outbox receipt moves review -> pr_opened."""
    refs = load_scenario(conn, "outbox_receipt", "reconciled")
    ticket = record.get(conn, "ticket", refs["ticket"])
    event = gates.review_gate(conn, ticket)
    assert event == "review_quorum_reconciled"
    assert transitions.apply(conn, refs["ticket"], event) == "pr_opened"


def test_review_superseded_intent_moves_to_checks(conn):
    """a pre-dispatch mismatch that superseded the outbox intent routes review -> checks."""
    refs = load_scenario(conn, "review_subject", "superseded_intent")
    ticket = record.get(conn, "ticket", refs["ticket"])
    event = gates.review_gate(conn, ticket)
    assert event == "review_predispatch_mismatch_to_checks"
    assert transitions.apply(conn, refs["ticket"], event) == "checks"


def test_review_pending_intent_withholds_the_gate(conn):
    """an intent still pending neither opens the pull request nor routes back."""
    refs = load_scenario(conn, "review_subject", "pending_intent")
    ticket = record.get(conn, "ticket", refs["ticket"])
    assert gates.review_gate(conn, ticket) is None


@pytest.mark.parametrize(
    "event,target",
    [
        ("review_predispatch_mismatch_to_planning", "planning"),
        ("review_predispatch_mismatch_to_context", "context"),
    ],
)
def test_review_predispatch_mismatch_routes_to_planning_or_context(conn, event, target):
    """a pre-dispatch mismatch recorded as applicable to planning or context reaches that state."""
    ticket_id = _ticket_in(conn, "review")
    assert transitions.apply(conn, ticket_id, event) == target


@pytest.mark.parametrize(
    "event,target",
    [
        ("send_back_to_planning", "planning"),
        ("send_back_to_context", "context"),
        ("send_back_to_clarifying", "clarifying"),
    ],
)
def test_review_redirect_targets(conn, event, target):
    """a recorded send-back from review reaches planning, context, or clarifying."""
    ticket_id = _ticket_in(conn, "review")
    assert transitions.apply(conn, ticket_id, event) == target


def test_review_request_changes_moves_to_implementing(conn):
    """request changes returns review -> implementing."""
    ticket_id = _ticket_in(conn, "review")
    assert transitions.apply(conn, ticket_id, "request_changes") == "implementing"


# --- pr_opened -----------------------------------------


def test_pr_opened_merge_recorded_moves_to_merged(conn):
    """the human recording the observed merge moves pr_opened -> merged."""
    ticket_id = _ticket_in(conn, "pr_opened")
    assert transitions.apply(conn, ticket_id, "merge_recorded") == "merged"
    assert record.get(conn, "ticket", ticket_id)["close_reason"] == "merged"


def test_pr_opened_abandon_moves_to_abandoned(conn):
    """the human recording abandonment moves pr_opened -> abandoned."""
    ticket_id = _ticket_in(conn, "pr_opened")
    assert transitions.apply(conn, ticket_id, "abandon") == "abandoned"


@pytest.mark.parametrize(
    "event,target",
    [
        ("revision_to_context", "context"),
        ("revision_to_clarifying", "clarifying"),
        ("revision_to_implementing", "implementing"),
        ("revision_to_planning", "planning"),
    ],
)
def test_pr_opened_revision_returns_to_the_selected_earlier_stage(conn, event, target):
    """a requested revision returns pr_opened through the selected earlier stage."""
    ticket_id = _ticket_in(conn, "pr_opened")
    assert transitions.apply(conn, ticket_id, event) == target


# --- escalated -------------------------------------


@pytest.mark.parametrize(
    "event,target",
    [
        ("escalation_verification_resolved_to_planning", "planning"),
        ("escalation_verification_resolved_to_clarifying", "clarifying"),
        ("escalation_verification_resolved_to_context", "context"),
    ],
)
def test_escalated_verification_exhaustion_resolution(conn, event, target):
    """verification exhaustion resolved by a superseding plan-item
    version and new approval moves escalated to the named earlier stage."""
    ticket_id = _ticket_in(conn, "escalated")
    assert transitions.apply(conn, ticket_id, event) == target


def test_escalated_control_defect_remediated_moves_to_context(conn):
    """a remediated control defect moves escalated -> context."""
    ticket_id = _ticket_in(conn, "escalated")
    assert transitions.apply(conn, ticket_id, "escalation_control_defect_remediated") == "context"


@pytest.mark.parametrize(
    "event,target",
    [
        ("escalation_resume_implementing", "implementing"),
        ("escalation_resume_checks", "checks"),
        ("escalation_resume_review", "review"),
    ],
)
def test_escalated_infrastructure_or_stop_resume(conn, event, target):
    """infrastructure exhaustion or a human stop resumes escalated
    back to implementing, checks, or review with verification count preserved
    (the count itself is the run ledger's; this table only proves the state move)."""
    ticket_id = _ticket_in(conn, "escalated")
    assert transitions.apply(conn, ticket_id, event) == target


# --- terminal states accept nothing further ----------------


@pytest.mark.parametrize("state", sorted(TERMINAL_STATES))
@pytest.mark.parametrize("event", ["abandon", "migrate_manifest", "s1_pass"])
def test_must_reject_any_event_from_a_terminal_state(conn, state, event):
    """`rejected`, `merged`, and `abandoned` accept no further transition."""
    ticket_id = _ticket_in(conn, state)
    with pytest.raises(TransitionRefused):
        transitions.apply(conn, ticket_id, event)
    assert record.get(conn, "ticket", ticket_id)["state"] == state


# --- migrate-manifest ---------------------------------------


@pytest.mark.parametrize(
    "state",
    [
        "intake",
        "context",
        "clarifying",
        "planning",
        "plan_review",
        "implementing",
        "checks",
        "review",
        "pr_opened",
        "escalated",
    ],
)
def test_migrate_manifest_moves_any_non_terminal_state_to_context(conn, state):
    """`factory migrate-manifest` moves a ticket from any open state to `context`."""
    ticket_id = _ticket_in(conn, state)
    assert transitions.apply(conn, ticket_id, "migrate_manifest") == "context"


# --- validation_only changes nothing ------------------------


def test_validation_only_s4_run_records_no_state_change(conn, tmp_path):
    """a `validation_only` run is recorded as an S4 run from `implementing`
    with no transition, even though an ordinary S4 pass would move the
    ticket to `checks`."""
    ticket_id = _implementing_ticket_with_plan_inputs(conn, tmp_path)
    os.environ["FIXTURE_ADAPTER_OUT_DIR"] = str(FACTORY_DIR / "evals" / "agents" / "S4" / "fixtures" / "ok" / "out")
    os.environ["FIXTURE_ADAPTER_WORKTREE_DIR"] = str(FACTORY_DIR / "evals" / "agents" / "S4" / "fixtures" / "ok" / "worktree")
    try:
        outcome = run_stage(conn, ticket_id, "S4", validation_only=True, runs_dir=tmp_path)
    finally:
        os.environ.pop("FIXTURE_ADAPTER_OUT_DIR", None)
        os.environ.pop("FIXTURE_ADAPTER_WORKTREE_DIR", None)
    assert outcome == "pass"
    assert record.get(conn, "ticket", ticket_id)["state"] == "implementing"
    stage_run = conn.execute(
        "SELECT * FROM stage_run WHERE ticket_id = ? AND stage = 'S4'", (ticket_id,)
    ).fetchone()
    assert stage_run["run_kind"] == "validation_only"
    assert stage_run["outcome"] == "pass"
