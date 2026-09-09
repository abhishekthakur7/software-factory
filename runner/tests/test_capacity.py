"""The parallel-ticket limit: the configured read, the counted-state set, the capacity-wait line, and the graduation-approval raise.

Every case seeds real rows through the record's own write paths -- a
ticket at `record.insert`, a bound report through
`artefact_registry.register` against a file actually written to disk, and
the raising decision through `approvals.record_approval` -- and asserts on
`capacity.effective_parallel_limit`'s returned `Limit`, on
`operations.advance`'s refusal at capacity, and on the wait line's text
from `factory queue` and `factory show`, never on a value a test only just
wrote down. The unsigned-edit, stale-hash, stale-manifest and
expired-record cases each change exactly one bound value away from a
seeded passing case, so each proves that one check and not another.
"""
import hashlib
import json
from pathlib import Path

import pytest
import yaml

from runner import approvals, artefact_registry, canonical, capacity, operations, queue, record, run_ledger
from runner.db import connect
from runner.reviewer_sets import Slot

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "capacity"

OWNER_IDENTITY = "abhishek"
MANIFEST_HASH = "manifest-capacity-1"
FAR_FUTURE = "2999-01-01T00:00:00+00:00"
FAR_PAST = "2000-01-01T00:00:00+00:00"


@pytest.fixture
def conn(tmp_path):
    connection = connect(tmp_path / "factory.sqlite")
    yield connection
    connection.close()


def _limits_yaml(tmp_path: Path, parallel_tickets: int) -> Path:
    path = tmp_path / "limits.yaml"
    path.write_text(yaml.safe_dump({"parallel_tickets": parallel_tickets}))
    return path


def _report(tmp_path: Path, name: str, *, passed: bool, manifest_hash: str) -> Path:
    path = tmp_path / f"{name}.json"
    path.write_text(json.dumps({"passed": passed, "manifest_hash": manifest_hash}))
    return path


def _seed_graduation_approval(
    conn,
    *,
    limits_path: Path,
    report_path: Path,
    expires_at: str | None = None,
    config_hash: str | None = None,
) -> int:
    """A `graduation`-gate approval binding `report_path` and `limits_path`'s current bytes, the COMMON.md shape."""
    run_id = run_ledger.open_utility_run(conn, kind="graduation")
    artefact_id = artefact_registry.register(
        conn, ticket_id=None, utility_run_id=run_id, kind="graduation_report", path=report_path,
    )
    report_artefact = record.get(conn, "artefact", artefact_id)
    thresholds_hash = "thresholds-1"
    bound_config_hash = config_hash if config_hash is not None else hashlib.sha256(limits_path.read_bytes()).hexdigest()
    scope = {
        "config_path": capacity.CONFIG_PATH,
        "config_hash": bound_config_hash,
        "thresholds_hash": thresholds_hash,
        "manifest_hash": MANIFEST_HASH,
    }
    subject_hash = canonical.content_hash({
        "report_content_hash": report_artefact["hash"],
        "thresholds_hash": thresholds_hash,
        "config_hash": bound_config_hash,
    })
    slot = Slot(source_rule="factory_owner_role", role="factory_owner", owner=OWNER_IDENTITY, min_count=1)
    return approvals.record_approval(
        conn, gate="graduation", subject_hash=subject_hash, slot_id=slot.slot_id,
        actor_identity=OWNER_IDENTITY, role="factory_owner", decision="approve",
        authority_policy_hash="authority-1", membership_snapshot_hash="membership-1",
        attestation_version="v1", attestation_hash="att-graduation-1",
        evidence_ids=json.dumps([artefact_id]), evidence_hashes=json.dumps([report_artefact["hash"]]),
        scope=json.dumps(scope), expires_at=expires_at,
    )


def _seed_one_ticket_per_state(conn) -> None:
    for row in yaml.safe_load((FIXTURES_DIR / "tickets.yaml").read_text())["all_states"]:
        record.insert(conn, "ticket", **row)


def test_effective_parallel_limit_reads_configured_value_with_no_approval(conn, tmp_path):
    """R-I-10: `effective_parallel_limit` reads `limits.yaml`'s `parallel_tickets` key; at one, with no
    graduation approval on record, the effective limit is one with no refusal reason."""
    limits_path = _limits_yaml(tmp_path, 1)
    assert capacity.effective_parallel_limit(conn, limits_path=limits_path) == capacity.Limit(1, None)


def test_in_flight_counts_exactly_the_defined_open_working_states(conn):
    """R-I-10: with one ticket seeded in every state, `in_flight` counts only the eight counted states
    (`context`, `clarifying`, `planning`, `plan_review`, `implementing`, `checks`, `review`, `escalated`);
    `intake`, `pr_opened`, `pr_checks`, and the terminal states are not counted."""
    _seed_one_ticket_per_state(conn)
    conn.commit()
    assert capacity.in_flight(conn) == len(capacity.COUNTED_STATES) == 8


def test_in_flight_excludes_a_baseline_ticket_even_in_a_counted_state(conn):
    """R-I-10: a pre-factory baseline ticket seeded into a counted state holds no capacity slot."""
    record.insert(conn, "ticket", state="context", title="baseline-context", baseline=1)
    conn.commit()
    assert capacity.in_flight(conn) == 0


def test_advance_at_capacity_starts_no_run_and_leaves_the_ticket_in_intake(conn):
    """R-I-10: a ticket in `intake` at the effective limit starts no `S0` run, opens no `queue_item`,
    and stays in `intake` with `blocked_on` null; `factory advance` reports the wait instead."""
    record.insert(conn, "ticket", state="context", title="in-flight")
    ticket_id = record.insert(conn, "ticket", state="intake", title="waiting")
    conn.commit()
    result = operations.advance(conn, ticket_id)
    assert "capacity wait: 1 of 1 tickets in flight" in result
    ticket = record.get(conn, "ticket", ticket_id)
    assert ticket["state"] == "intake"
    assert ticket["blocked_on"] is None
    assert conn.execute("SELECT COUNT(*) AS n FROM stage_run WHERE ticket_id = ?", (ticket_id,)).fetchone()["n"] == 0
    assert conn.execute("SELECT COUNT(*) AS n FROM queue_item WHERE ticket_id = ?", (ticket_id,)).fetchone()["n"] == 0


def test_queue_lists_a_capacity_wait_line_for_a_ticket_held_at_intake(conn):
    """R-I-10: `factory queue` derives a capacity-wait line, labelled `capacity wait`, for a ticket held
    at `intake` by the configured limit -- the only place it can appear, since the ticket carries no
    `queue_item` of its own."""
    record.insert(conn, "ticket", state="context", title="in-flight")
    ticket_id = record.insert(conn, "ticket", state="intake", title="waiting")
    conn.commit()
    output = queue.list_queue(conn)
    assert f"ticket {ticket_id}: capacity wait: 1 of 1 tickets in flight" in output


def test_show_reports_the_same_capacity_wait_line(conn):
    """R-I-10: `factory show` derives the same capacity-wait line, labelled `capacity wait`, distinct in
    wording from a human wait or queue latency."""
    record.insert(conn, "ticket", state="context", title="in-flight")
    ticket_id = record.insert(conn, "ticket", state="intake", title="waiting")
    conn.commit()
    output = operations.show(conn, ticket_id)
    assert "capacity wait: 1 of 1 tickets in flight" in output
    for forbidden in ("human wait", "attention", "queue latency"):
        assert forbidden not in output


def test_an_unsigned_edit_to_the_configured_limit_is_refused(conn, tmp_path):
    """R-I-10: raising `parallel_tickets` above one with no `approval_record` binding any hash for the
    file leaves the effective limit at one, reason `unsigned_edit`."""
    limits_path = _limits_yaml(tmp_path, 3)
    limit = capacity.effective_parallel_limit(conn, limits_path=limits_path, manifest_hash=MANIFEST_HASH)
    assert limit == capacity.Limit(1, capacity.UNSIGNED_EDIT)


def test_a_current_graduation_approval_raises_the_effective_limit(conn, tmp_path):
    """R-I-10: a current, unexpired `graduation` approval binding a passing report and the file's exact
    current bytes raises `effective_parallel_limit` to the configured value."""
    limits_path = _limits_yaml(tmp_path, 3)
    report_path = _report(tmp_path, "report", passed=True, manifest_hash=MANIFEST_HASH)
    _seed_graduation_approval(conn, limits_path=limits_path, report_path=report_path, expires_at=FAR_FUTURE)
    conn.commit()
    limit = capacity.effective_parallel_limit(conn, limits_path=limits_path, manifest_hash=MANIFEST_HASH)
    assert limit == capacity.Limit(3, None)


def test_a_stale_configuration_hash_refuses_the_raise(conn, tmp_path):
    """R-I-10: an approval binding a configuration hash that differs from `limits.yaml`'s current bytes
    leaves the effective limit at one, reason `stale_report`."""
    limits_path = _limits_yaml(tmp_path, 3)
    report_path = _report(tmp_path, "report", passed=True, manifest_hash=MANIFEST_HASH)
    _seed_graduation_approval(
        conn, limits_path=limits_path, report_path=report_path, expires_at=FAR_FUTURE, config_hash="0" * 64,
    )
    conn.commit()
    limit = capacity.effective_parallel_limit(conn, limits_path=limits_path, manifest_hash=MANIFEST_HASH)
    assert limit == capacity.Limit(1, capacity.STALE_REPORT)


def test_a_stale_manifest_hash_on_the_bound_report_refuses_the_raise(conn, tmp_path):
    """R-I-10: an approval binding a `graduation_report` recorded under a manifest hash different from
    the current one leaves the effective limit at one, reason `stale_report`."""
    limits_path = _limits_yaml(tmp_path, 3)
    report_path = _report(tmp_path, "report", passed=True, manifest_hash="a-different-manifest-hash")
    _seed_graduation_approval(conn, limits_path=limits_path, report_path=report_path, expires_at=FAR_FUTURE)
    conn.commit()
    limit = capacity.effective_parallel_limit(conn, limits_path=limits_path, manifest_hash=MANIFEST_HASH)
    assert limit == capacity.Limit(1, capacity.STALE_REPORT)


def test_an_expired_graduation_approval_confers_no_raise(conn, tmp_path):
    """R-I-10: an expired `approval_record` on the `graduation` gate confers no effective limit above one --
    the same as no approval ever having been recorded."""
    limits_path = _limits_yaml(tmp_path, 3)
    report_path = _report(tmp_path, "report", passed=True, manifest_hash=MANIFEST_HASH)
    _seed_graduation_approval(conn, limits_path=limits_path, report_path=report_path, expires_at=FAR_PAST)
    conn.commit()
    limit = capacity.effective_parallel_limit(conn, limits_path=limits_path, manifest_hash=MANIFEST_HASH)
    assert limit == capacity.Limit(1, capacity.UNSIGNED_EDIT)
