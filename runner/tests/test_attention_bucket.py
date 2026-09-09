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

from runner import governance, queue, record
from runner.db import connect
from runner.paths import FACTORY_DIR, REPO_ROOT

ABHISHEK = "abhishek"
FAR_FUTURE = "2999-01-01T00:00:00+00:00"


def _governed_ticket_fields(conn) -> dict:
    """Ticket fields that satisfy `S0.governance_valid`, the same default-path activation `test_outbox.py`'s reconcile-first test uses."""
    proposal = governance.propose()
    for role in ("security_approver", "legal_data_governance_approver"):
        governance.decide(
            conn, proposal, actor_identity=ABHISHEK, role=role, decision="approve",
            expires_at=FAR_FUTURE, attestation_version="v1", attestation_hash=f"att-{role}",
        )
    activated = governance.activation(conn, proposal)
    return {
        "trust_profile_hash": proposal.profile_hash,
        "trust_approval_set_hash": activated.trust_approval_set_hash,
        "service": "fixture-project",
        "source_kind": "jira",
        "source_ref": "FIX-1",
    }

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



def test_a_multi_reviewer_plan_decision_shows_each_reviewers_own_bucket(conn, tmp_path):
    """each reviewer's `active_attention_bucket`, `unknown` among them, shows
    on its own approval record, never collapsed into one shared value; the
    item itself stays open until the second slot's decision arrives, so no
    latency or outcome line stands in for a bucket."""
    import json as _json

    from runner import artefact_registry, artefacts, checklist, manifest, owners, plan_tuple
    from runner.reviewer_sets import Slot

    ticket_id = record.insert(
        conn, "ticket", state="plan_review", opened_at=record.now(), title="multi-reviewer plan",
        # Append-only columns: set at insert time, since the bootstrap
        # checklist's own plan tuple requires both non-null.
        trust_profile_hash="trust-1", trust_approval_set_hash="trust-approval-1",
        factory_manifest_hash=manifest.current_hash(), base_sha="base-1", target_base_sha="base-1",
    )
    for kind in ("brief", "criteria", "plan"):
        path = tmp_path / f"{kind}.md"
        path.write_text(f"## {artefacts.SECTIONS[kind][0]}\n\nstub\n")
        artefact_registry.register(conn, ticket_id=ticket_id, kind=kind, path=path)

    s3_identity = owners.load_owners().roles["s3_reviewer"]["identity"]
    slots = [
        Slot(source_rule="s3_reviewer_role", role="s3_reviewer", owner=s3_identity, min_count=1),
        Slot(source_rule="sensitive_paths:1", role="sensitive_path_owner", owner="second-reviewer", min_count=1),
    ]
    reviewer_set_id = record.insert(
        conn, "reviewer_set", ticket_id=ticket_id, kind="planned", content_hash="planned-subj",
        slots=_json.dumps([slot.to_json() for slot in slots]),
    )
    item_id = queue.open_item(
        conn, ticket_id=ticket_id, kind="plan_approval", stage="S3", tier="standard", reviewer_set_id=reviewer_set_id,
    )
    conn.commit()

    ticket = record.get(conn, "ticket", ticket_id)
    plan_artefact = artefact_registry.latest(conn, ticket_id, "plan")
    for instance in checklist.expected_instances(conn, ticket):
        queue.act(
            conn, item_id=item_id, action="verdict", actor=s3_identity, line=instance.rubric_line_id,
            key=instance.subject_item_key, verdict="pass", evidence=[plan_artefact["id"]], runs_dir=tmp_path,
        )
    subject_hash = plan_tuple.current_subject(conn, record.get(conn, "ticket", ticket_id))

    queue.act(conn, item_id=item_id, action="approve", actor=ABHISHEK, bucket="under_2m", self_contained="yes", runs_dir=tmp_path)

    # A second, independent reviewer record on the same subject records its
    # own bucket directly, standing in for a distinct actor's decision --
    # `record_approval` itself, not `act`, is what a second slot's actor calls.
    from runner import approvals
    approvals.record_approval(
        conn, gate="plan", subject_hash=subject_hash, slot_id=slots[1].slot_id,
        actor_identity="second-reviewer", role="sensitive_path_owner", decision="approve",
        authority_policy_hash="policy-1", membership_snapshot_hash="members-1",
        attestation_version="v1", attestation_hash="att-2", active_attention_bucket="unknown",
    )
    conn.commit()

    output = queue.list_queue(conn, include_resolved=True)
    approval_section = output.split("approval records:")[1].split("queue latency")[0]
    assert "abhishek: approve (active_attention_bucket: under_2m)" in approval_section
    assert "second-reviewer: approve (active_attention_bucket: unknown)" in approval_section
    assert record.get(conn, "queue_item", item_id)["resolved_at"] is None
    assert "queue latency:" not in output



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
    # One shared governance decision for both tickets below: deciding the
    # same trust-profile subject twice in one test would leave two
    # unsuperseded heads for the same slot and actor, forking activation.
    governed = _governed_ticket_fields(conn)
    ticket_id = record.insert(conn, "ticket", state="intake", opened_at=record.now(), **governed)
    item_id = queue.open_item(conn, ticket_id=ticket_id, kind="eligibility")
    queue.act(conn, item_id=item_id, action="granted", actor=ABHISHEK)
    assert record.get(conn, "queue_item", item_id)["active_attention_bucket"] is None

    ticket_id2 = record.insert(conn, "ticket", state="intake", opened_at=record.now(), **governed)
    item_id2 = queue.open_item(conn, ticket_id=ticket_id2, kind="eligibility")
    queue.act(conn, item_id=item_id2, action="granted", actor=ABHISHEK, bucket="unknown")
    assert record.get(conn, "queue_item", item_id2)["active_attention_bucket"] == "unknown"
