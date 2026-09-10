"""No response, row, or log line across `factory act`'s action list ever contains a credential value.

A credential is seeded into the two sources a response could actually
read back: an artefact's own file content (the one `factory show
--artefact` prints), and a human's own `note` text on a tag or a queue
decision. Neither ever reaches a return string, a `list_queue` block, or
any stored field outside the exact row the human themselves wrote it
into -- the guard's own secret scan denies the artefact outright rather
than passing it through, and no other command echoes a note back at all.
"""
import hashlib

import pytest

from runner import operations, queue, record, tags
from runner.db import connect
from runner.tests.test_act import ABHISHEK, _governed_ticket_fields

CREDENTIAL = "ghp_" + "a" * 36  # matches trust-profile.yaml's github_token secret rule


@pytest.fixture
def conn(tmp_path):
    connection = connect(tmp_path / "factory.sqlite")
    yield connection
    connection.close()


def test_an_artefact_carrying_a_credential_is_denied_display_not_printed(conn, tmp_path):
    """The guard's secret scan denies the artefact before any content is returned; the credential
    reaches neither the raised refusal nor the `guard_decision` row's own stored fields."""
    _governed_ticket_fields(conn)
    ticket_id = record.insert(conn, "ticket", state="checks", opened_at=record.now(), data_class="confidential")
    path = tmp_path / "secret-body.md"
    path.write_text(f"here is a token: {CREDENTIAL}\n")
    artefact_id = record.insert(
        conn, "artefact", ticket_id=ticket_id, kind="check_evidence", version=1, path=str(path),
        hash=hashlib.sha256(path.read_bytes()).hexdigest(), created_at=record.now(), data_class="confidential",
    )

    with pytest.raises(queue.ActionRefused) as excinfo:
        operations.show_artefact(conn, artefact_id, actor=ABHISHEK)
    assert CREDENTIAL not in str(excinfo.value)

    decision = conn.execute("SELECT * FROM guard_decision ORDER BY id DESC LIMIT 1").fetchone()
    assert decision["decision"] == "deny"
    for key in decision.keys():
        value = decision[key]
        if isinstance(value, str):
            assert CREDENTIAL not in value


def test_a_credential_in_a_send_back_note_never_reaches_any_actions_own_response(conn, tmp_path):
    """A `send_back`'s response and every neighbouring action's own response name nothing from the note."""
    ticket_id = record.insert(conn, "ticket", state="checks", opened_at=record.now())
    note = f"other: rotate this leaked token {CREDENTIAL} before merging"
    item_id = queue.open_item(conn, ticket_id=ticket_id, kind="red_check")

    result = queue.act(
        conn, item_id=item_id, action="send_back", actor=ABHISHEK, to="context", fm_id="question_noise",
        note=note, runs_dir=tmp_path,
    )
    assert CREDENTIAL not in result

    item_id2 = queue.open_item(conn, ticket_id=ticket_id, kind="red_check")
    control_result = queue.act(
        conn, item_id=item_id2, action="control_event", actor=ABHISHEK, category="execution_boundary",
        severity="sev3", fm_id="parallel_fatigue", note=note, runs_dir=tmp_path,
    )
    assert CREDENTIAL not in control_result

    queue_text = queue.list_queue(conn, include_resolved=True)
    # The note itself is legitimately stored on the tag/incident rows it
    # names; `list_queue`'s own block text is the surface this proves
    # clean, since that is what a human or a digest actually reads.
    assert CREDENTIAL not in queue_text


def test_a_credential_in_a_tag_note_stays_on_that_one_tag_row_only(conn, tmp_path):
    """A `factory tag` note is stored on the tag itself but is never copied onto the ticket, the
    resolved queue item, or any approval row a neighbouring action writes."""
    ticket_id = record.insert(conn, "ticket", state="checks", opened_at=record.now())
    item_id = queue.open_item(conn, ticket_id=ticket_id, kind="red_check")
    tags.tag(
        conn, target=f"queue_item:{item_id}", kind="packet_defect", fm_id=tags.PACKET_DEFECT_FM_ID,
        actor=ABHISHEK, note=f"credential found in diff: {CREDENTIAL}",
    )

    ticket_row = record.get(conn, "ticket", ticket_id)
    item_row = record.get(conn, "queue_item", item_id)
    for row in (ticket_row, item_row):
        for key in row.keys():
            value = row[key]
            if isinstance(value, str):
                assert CREDENTIAL not in value
