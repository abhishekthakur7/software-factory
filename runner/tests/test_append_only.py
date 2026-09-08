"""Append-only enforcement: artefacts and the append-only tables.

Every test opens its own `tmp_path` database. A table's non-exception
columns are exercised individually here; the exhaustive per-column sweep
across every table lives in `test_mutable_exceptions.py` alongside the
allowlist it checks against.
"""
import sqlite3

import pytest

from runner import artefact_registry, record
from runner.db import connect


def _open(tmp_path):
    return connect(tmp_path / "factory.sqlite")


@pytest.fixture
def artefact_dir(tmp_path):
    directory = tmp_path / "artefacts"
    directory.mkdir()
    return directory


def test_artefact_new_version_appends_a_row_and_leaves_the_prior_unchanged(tmp_path, artefact_dir):
    """writing a new version of a registered file appends a row naming the prior one."""
    conn = _open(tmp_path)
    ticket_id = record.insert(conn, "ticket", title="t")
    target = artefact_dir / "brief.md"
    target.write_text("version one")
    first_id = artefact_registry.register(conn, ticket_id=ticket_id, kind="brief", path=target)

    target.write_text("version two")
    second_id = artefact_registry.register(
        conn, ticket_id=ticket_id, kind="brief", path=target, supersedes=first_id
    )

    first_row = record.get(conn, "artefact", first_id)
    second_row = record.get(conn, "artefact", second_id)
    assert first_row["version"] == 1
    assert second_row["version"] == 2
    assert second_row["supersedes"] == first_id
    # the prior row's own hash still reflects the file's first content
    assert first_row["hash"] != second_row["hash"]


def test_must_reject_registering_a_supersedes_with_a_mismatched_ticket_or_kind(
    tmp_path, artefact_dir
):
    """superseding a version of a different ticket or kind is refused before any write."""
    conn = _open(tmp_path)
    ticket_id = record.insert(conn, "ticket", title="t")
    other_ticket_id = record.insert(conn, "ticket", title="other")
    target = artefact_dir / "brief.md"
    target.write_text("v1")
    first_id = artefact_registry.register(conn, ticket_id=ticket_id, kind="brief", path=target)

    with pytest.raises(ValueError):
        artefact_registry.register(
            conn, ticket_id=other_ticket_id, kind="brief", path=target, supersedes=first_id
        )
    with pytest.raises(ValueError):
        artefact_registry.register(
            conn, ticket_id=ticket_id, kind="plan", path=target, supersedes=first_id
        )


def test_must_reject_artefact_edit_in_place(tmp_path, artefact_dir):
    """an existing artefact row cannot be edited in place."""
    conn = _open(tmp_path)
    ticket_id = record.insert(conn, "ticket", title="t")
    target = artefact_dir / "brief.md"
    target.write_text("v1")
    artefact_id = artefact_registry.register(conn, ticket_id=ticket_id, kind="brief", path=target)

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE artefact SET path = ? WHERE id = ?", ("elsewhere.md", artefact_id))


def test_assumption_supersede_is_a_new_row_naming_the_prior_and_leaves_it_unchanged(tmp_path):
    """superseding or withdrawing an assumption appends a new row; the prior row is untouched."""
    conn = _open(tmp_path)
    first_id = record.insert(conn, "assumption", text="original claim", origin="agent")

    second_id = record.insert(
        conn, "assumption", text="revised claim", origin="agent", supersedes=first_id
    )
    withdrawal_id = record.insert(
        conn,
        "assumption",
        text="revised claim",
        origin="agent",
        supersedes=second_id,
        withdrawn=1,
        withdrawal_reason="no longer needed",
    )

    prior = record.get(conn, "assumption", first_id)
    assert prior["text"] == "original claim"
    assert prior["supersedes"] is None
    successor = record.get(conn, "assumption", second_id)
    assert successor["supersedes"] == first_id
    withdrawal = record.get(conn, "assumption", withdrawal_id)
    assert withdrawal["supersedes"] == second_id
    assert withdrawal["withdrawn"] == 1


def test_must_reject_assumption_edit_in_place(tmp_path):
    """an existing assumption row is never edited in place."""
    conn = _open(tmp_path)
    assumption_id = record.insert(conn, "assumption", text="original claim", origin="agent")

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "UPDATE assumption SET text = ? WHERE id = ?", ("changed claim", assumption_id)
        )


def test_must_reject_tag_edit_in_place(tmp_path):
    """an existing tag row cannot be edited in place."""
    conn = _open(tmp_path)
    tag_id = record.insert(conn, "tag", fm_id="override", note="first note")

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE tag SET note = ? WHERE id = ?", ("changed note", tag_id))


def test_must_reject_deviation_edit_in_place(tmp_path):
    """an existing deviation row cannot be edited in place."""
    conn = _open(tmp_path)
    deviation_id = record.insert(conn, "deviation", why="the plan missed a case")

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE deviation SET why = ? WHERE id = ?", ("a different why", deviation_id))


def test_generated_test_review_appends_a_new_decision_row(tmp_path):
    """a later review of a generated test appends a new decision row rather than editing the identity row."""
    conn = _open(tmp_path)
    identity_id = record.insert(
        conn,
        "generated_test",
        record_kind="identity",
        initial_path="tests/test_x.py",
        initial_hash="h1",
        generating_actor_kind="agent",
    )
    decision_id = record.insert(
        conn,
        "generated_test",
        record_kind="decision",
        identity_id=identity_id,
        decision="kept",
        final_path="tests/test_x.py",
        final_hash="h1",
        actor="reviewer",
    )

    identity_row = record.get(conn, "generated_test", identity_id)
    assert identity_row["decision"] is None
    decision_row = record.get(conn, "generated_test", decision_id)
    assert decision_row["identity_id"] == identity_id


def test_must_reject_generated_test_edit_in_place(tmp_path):
    """an existing identity or decision row cannot be edited in place."""
    conn = _open(tmp_path)
    row_id = record.insert(
        conn, "generated_test", record_kind="identity", initial_path="tests/test_x.py"
    )

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "UPDATE generated_test SET initial_path = ? WHERE id = ?", ("tests/test_y.py", row_id)
        )


def test_must_reject_answer_edit_in_place(tmp_path):
    """an existing answer row cannot be edited in place."""
    conn = _open(tmp_path)
    answer_id = record.insert(conn, "answer", resolution_kind="chosen_option", chosen_option="0")

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE answer SET chosen_option = ? WHERE id = ?", ("1", answer_id))


def test_must_reject_human_verdict_edit_in_place(tmp_path):
    """an existing verdict row cannot be edited in place."""
    conn = _open(tmp_path)
    verdict_id = record.insert(conn, "human_verdict", verdict="pass", note="looks right")

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE human_verdict SET note = ? WHERE id = ?", ("changed", verdict_id))


def test_must_reject_guard_decision_edit_in_place(tmp_path):
    """an existing guard decision row cannot be edited in place."""
    conn = _open(tmp_path)
    decision_id = record.insert(conn, "guard_decision", decision="allow", reason_codes="ok")

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "UPDATE guard_decision SET reason_codes = ? WHERE id = ?", ("changed", decision_id)
        )


def test_must_reject_reviewer_set_edit_in_place(tmp_path):
    """an existing reviewer-set row cannot be edited in place."""
    conn = _open(tmp_path)
    reviewer_set_id = record.insert(conn, "reviewer_set", kind="plan", subject_hash="h1")

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "UPDATE reviewer_set SET subject_hash = ? WHERE id = ?", ("h2", reviewer_set_id)
        )


def test_must_reject_approval_record_edit_in_place(tmp_path):
    """an existing approval record cannot be edited in place."""
    conn = _open(tmp_path)
    approval_id = record.insert(conn, "approval_record", gate="plan_approval", decision="approve")

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "UPDATE approval_record SET decision = ? WHERE id = ?", ("reject", approval_id)
        )


def test_must_reject_waiver_edit_in_place(tmp_path):
    """an existing waiver row cannot be edited in place."""
    conn = _open(tmp_path)
    waiver_id = record.insert(
        conn, "waiver", reason="known flake", expires_at="2030-01-01T00:00:00+00:00"
    )

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE waiver SET reason = ? WHERE id = ?", ("different reason", waiver_id))


def test_must_reject_evidence_tuple_edit_in_place(tmp_path):
    """an existing evidence tuple cannot be edited in place."""
    conn = _open(tmp_path)
    tuple_id = record.insert(conn, "evidence_tuple", kind="plan", content_hash="h1")

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE evidence_tuple SET content_hash = ? WHERE id = ?", ("h2", tuple_id))


def test_must_reject_incident_observation_edit_in_place(tmp_path):
    """an existing incident observation row cannot be edited in place."""
    conn = _open(tmp_path)
    observation_id = record.insert(
        conn, "incident_observation", record_kind="production_incident_event", note="first"
    )

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "UPDATE incident_observation SET note = ? WHERE id = ?", ("changed", observation_id)
        )


def test_must_reject_question_reasoning_edit_in_place(tmp_path):
    """question.reasoning is append-only; only question.state may change in place."""
    conn = _open(tmp_path)
    question_id = record.insert(conn, "question", reasoning="why we're asking")

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "UPDATE question SET reasoning = ? WHERE id = ?", ("a different reason", question_id)
        )


def test_must_reject_question_options_edit_in_place(tmp_path):
    """question.options is append-only; only question.state may change in place."""
    conn = _open(tmp_path)
    question_id = record.insert(conn, "question", options="[\"a\", \"b\"]")

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "UPDATE question SET options = ? WHERE id = ?", ("[\"a\", \"b\", \"c\"]", question_id)
        )
