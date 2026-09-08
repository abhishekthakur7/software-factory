"""`active_attention_bucket` (R-H-12): mandatory and per-reviewer on a plan
or packet decision, optional elsewhere, never derived from anything but the
human's own input, and nowhere named beside a keystroke, focus-event, or
editor-telemetry source.

The forbidden-token scan and the AST derivation check are static: they read
every governed configuration file and every non-test module under
`runner/` from disk, so a later ticket that adds a new module or config
file is covered automatically rather than needing its path added to a list
here.
"""
import ast
import json

import pytest

from runner import queue, record
from runner.db import connect
from runner.paths import FACTORY_DIR, REPO_ROOT

ABHISHEK = "abhishek"

FORBIDDEN_TOKENS = (
    "keystroke",
    "focus_event",
    "focus-event",
    "editor_telemetry",
    "editor-telemetry",
    "pynput",
    "keyboard",
    "activity_monitor",
)


@pytest.fixture
def conn(tmp_path):
    connection = connect(tmp_path / "factory.sqlite")
    yield connection
    connection.close()


def _reviewer_set(conn, ticket_id, *, kind, subject_hash, roles):
    slots = [
        {"source_rule": f"{kind}:{i}", "role": role, "min_count": 1, "distinct_from": [], "resolved": True}
        for i, role in enumerate(roles)
    ]
    return record.insert(conn, "reviewer_set", ticket_id=ticket_id, kind=kind, subject_hash=subject_hash, slots=json.dumps(slots))



def test_a_multi_reviewer_plan_decision_shows_each_reviewers_own_bucket(conn):
    """each reviewer's `active_attention_bucket`, `unknown` among them, shows
    on its own approval record -- distinct from the queue latency line and
    the decision outcome, never collapsed into one shared value."""
    ticket_id = record.insert(
        conn, "ticket", state="plan_review", opened_at=record.now(), title="multi-reviewer plan",
    )
    reviewer_set_id = _reviewer_set(
        conn, ticket_id, kind="planned", subject_hash="plan-subj",
        roles=["s3_reviewer", "sensitive_path_owner"],
    )
    item_id = queue.open_item(
        conn, ticket_id=ticket_id, kind="plan_approval", stage="S3", tier="standard",
        approval_subject_hash="plan-subj", reviewer_set_id=reviewer_set_id,
    )
    conn.commit()

    queue.act(conn, item_id=item_id, action="approve", actor=ABHISHEK, bucket="under_2m")

    # A second, independent reviewer record on the same subject records its
    # own bucket directly, standing in for a distinct actor's decision --
    # `record_approval` itself, not `act`, is what a second slot's actor calls.
    from runner import approvals
    approvals.record_approval(
        conn, gate="plan", subject_hash="plan-subj", slot_id="second-slot",
        actor_identity="second-reviewer", role="sensitive_path_owner", decision="approve",
        authority_policy_hash="policy-1", membership_snapshot_hash="members-1",
        attestation_version="v1", attestation_hash="att-2", active_attention_bucket="unknown",
    )
    conn.commit()

    output = queue.list_queue(conn, include_resolved=True)
    approval_section = output.split("approval records:")[1].split("queue latency")[0]
    assert "abhishek: approve (active_attention_bucket: under_2m)" in approval_section
    assert "second-reviewer: approve (active_attention_bucket: unknown)" in approval_section
    assert "queue latency:" in output
    assert "outcome: approve" in output



def _config_and_manifest_files():
    yield FACTORY_DIR / "manifest.yaml"
    config_dir = FACTORY_DIR / "config"
    if config_dir.is_dir():
        yield from config_dir.rglob("*")


def _runner_source_files():
    for path in (REPO_ROOT / "runner").rglob("*.py"):
        if "tests" in path.relative_to(REPO_ROOT / "runner").parts:
            continue
        yield path


def test_must_reject_a_keystroke_or_editor_telemetry_source_anywhere_governed(conn):
    """no manifest entry, configuration file, or runner module names a
    keystroke, focus-event, or editor-telemetry source for the bucket."""
    for path in _config_and_manifest_files():
        if not path.is_file():
            continue
        text = path.read_text(errors="ignore").lower()
        for token in FORBIDDEN_TOKENS:
            assert token not in text, f"{path} names forbidden telemetry token {token!r}"
    for path in _runner_source_files():
        text = path.read_text().lower()
        for token in FORBIDDEN_TOKENS:
            assert token not in text, f"{path} names forbidden telemetry token {token!r}"



def _bucket_value_nodes(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "active_attention_bucket":
                    yield node.value
        elif isinstance(node, ast.keyword) and node.arg == "active_attention_bucket":
            yield node.value


def test_no_runner_code_path_derives_active_attention_bucket(conn):
    """every assignment or keyword argument named `active_attention_bucket`
    is a plain name (a parameter carrying the human's own input) or the
    literal `"unknown"` -- never a call result or an expression, so no code
    path can compute a bucket from anything but what the human supplied."""
    for path in _runner_source_files():
        tree = ast.parse(path.read_text(), filename=str(path))
        for value in _bucket_value_nodes(tree):
            allowed = isinstance(value, ast.Name) or (
                isinstance(value, ast.Constant) and value.value == "unknown"
            )
            assert allowed, f"{path}: active_attention_bucket is set to a derived expression"



def test_must_reject_a_plan_or_packet_decision_missing_its_attention_bucket(conn):
    ticket_id = record.insert(conn, "ticket", state="plan_review", opened_at=record.now())
    reviewer_set_id = _reviewer_set(conn, ticket_id, kind="planned", subject_hash="plan-subj", roles=["s3_reviewer"])
    item_id = queue.open_item(
        conn, ticket_id=ticket_id, kind="plan_approval", approval_subject_hash="plan-subj", reviewer_set_id=reviewer_set_id,
    )
    with pytest.raises(queue.ActionRefused):
        queue.act(conn, item_id=item_id, action="approve", actor=ABHISHEK)


def test_a_non_approval_action_may_record_its_bucket_optionally(conn):
    """`granted` on an eligibility item takes no bucket at all, and takes
    one, of any value in the closed set, exactly as given when it does."""
    ticket_id = record.insert(conn, "ticket", state="intake", opened_at=record.now())
    item_id = queue.open_item(conn, ticket_id=ticket_id, kind="eligibility")
    queue.act(conn, item_id=item_id, action="granted", actor=ABHISHEK)
    assert record.get(conn, "queue_item", item_id)["active_attention_bucket"] is None

    ticket_id2 = record.insert(conn, "ticket", state="intake", opened_at=record.now())
    item_id2 = queue.open_item(conn, ticket_id=ticket_id2, kind="eligibility")
    queue.act(conn, item_id=item_id2, action="granted", actor=ABHISHEK, bucket="unknown")
    assert record.get(conn, "queue_item", item_id2)["active_attention_bucket"] == "unknown"
