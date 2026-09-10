"""`factory show --artefact`: the governed-artefact display verb, over the guard's `display` crossing."""
import hashlib

import pytest
import yaml

from runner import operations, owners, queue, record
from runner.db import connect
from runner.tests.test_act import ABHISHEK, _governed_ticket_fields


@pytest.fixture
def conn(tmp_path):
    connection = connect(tmp_path / "factory.sqlite")
    yield connection
    connection.close()


def _activate_trust_profile(conn) -> None:
    """Activate the real, committed trust profile the same way `test_act.py`'s governed-ticket tests do."""
    _governed_ticket_fields(conn)


def _register_artefact(conn, tmp_path, *, data_class: str, retention_until: str | None = None, text: str = "governed body\n") -> tuple[int, int]:
    ticket_id = record.insert(conn, "ticket", state="checks", opened_at=record.now(), data_class=data_class)
    path = tmp_path / f"artefact-{ticket_id}.md"
    path.write_text(text)
    artefact_id = record.insert(
        conn, "artefact", ticket_id=ticket_id, kind="check_evidence", version=1, path=str(path),
        hash=hashlib.sha256(path.read_bytes()).hexdigest(), created_at=record.now(),
        data_class=data_class, retention_until=retention_until,
    )
    return ticket_id, artefact_id


def _reader_only_owners_path(tmp_path) -> str:
    """A copy of the default `owners.yaml` where `packet_reviewer`/`ticket_engineer` -- the display route's own
    reader roles -- both go to an identity that also holds a role the route does not name as a reader."""
    default = owners.load_owners()
    roles = {name: dict(entry) for name, entry in default.roles.items()}
    roles["sensitive_path_owner"] = {"identity": "not_a_reader", "responsibilities": ["approvals"]}
    path = tmp_path / "owners.yaml"
    path.write_text(yaml.safe_dump({"roles": roles, "shared_identities": []}))
    return str(path)


def test_show_artefact_prints_the_content_on_allow_and_writes_one_guard_decision(conn, tmp_path):
    """The guard is evaluated against `governed_export_display` over the `display` crossing, and
    exactly one `guard_decision` row is written for the call."""
    _activate_trust_profile(conn)
    before = conn.execute("SELECT COUNT(*) FROM guard_decision").fetchone()[0]
    ticket_id, artefact_id = _register_artefact(conn, tmp_path, data_class="confidential", text="the governed body\n")

    output = operations.show_artefact(conn, artefact_id, actor=ABHISHEK)

    assert "the governed body" in output
    after = conn.execute("SELECT COUNT(*) FROM guard_decision").fetchone()[0]
    assert after == before + 1
    decision = conn.execute("SELECT * FROM guard_decision ORDER BY id DESC LIMIT 1").fetchone()
    assert decision["operation"] == "display"
    assert decision["route_id"] == "governed_export_display"
    assert decision["decision"] == "allow"


def test_show_artefact_on_an_artefact_past_retention_prints_the_subject_to_deletion_line(conn, tmp_path):
    _activate_trust_profile(conn)
    ticket_id, artefact_id = _register_artefact(
        conn, tmp_path, data_class="confidential", retention_until="2000-01-01T00:00:00+00:00",
    )
    output = operations.show_artefact(conn, artefact_id, actor=ABHISHEK)
    assert output.splitlines()[0] == "subject to deletion: retention_until 2000-01-01T00:00:00+00:00 has passed"


def test_must_reject_show_artefact_for_a_reader_holding_none_of_the_routes_reader_roles(conn, tmp_path):
    """must-reject: refused before the guard is ever consulted -- no `guard_decision` row is written."""
    _activate_trust_profile(conn)
    ticket_id, artefact_id = _register_artefact(conn, tmp_path, data_class="confidential")
    owners_path = _reader_only_owners_path(tmp_path)
    before = conn.execute("SELECT COUNT(*) FROM guard_decision").fetchone()[0]

    with pytest.raises(queue.ActionRefused):
        operations.show_artefact(conn, artefact_id, actor="not_a_reader", owners_path=owners_path)

    after = conn.execute("SELECT COUNT(*) FROM guard_decision").fetchone()[0]
    assert after == before


def test_must_reject_show_artefact_for_a_data_class_the_route_does_not_admit(conn, tmp_path):
    """must-reject: a request outside the route -- a class beyond `governed_export_display`'s own `max_class` -- is
    refused, from the guard's own `deny` decision, still writing exactly one `guard_decision` row."""
    _activate_trust_profile(conn)
    ticket_id, artefact_id = _register_artefact(conn, tmp_path, data_class="restricted")
    before = conn.execute("SELECT COUNT(*) FROM guard_decision").fetchone()[0]

    with pytest.raises(queue.ActionRefused):
        operations.show_artefact(conn, artefact_id, actor=ABHISHEK)

    after = conn.execute("SELECT COUNT(*) FROM guard_decision").fetchone()[0]
    assert after == before + 1
    decision = conn.execute("SELECT * FROM guard_decision ORDER BY id DESC LIMIT 1").fetchone()
    assert decision["decision"] == "deny"


def test_must_reject_show_artefact_naming_no_such_artefact(conn):
    with pytest.raises(LookupError):
        operations.show_artefact(conn, 999999, actor=ABHISHEK)
