"""T-A-02 canonical serialization tests (PRD 2.2 preamble).

Not listed in T-A-02's own verification section; the orchestrator adds
this file to that list once the ticket lands.
"""
import pytest

from runner import canonical
from runner.canonical import canonical_json, content_hash


def test_key_order_does_not_affect_hash():
    """T-A-02: canonical JSON sorts object keys, so insertion order is not part of the subject."""
    a = {"b": 1, "a": 2}
    b = {"a": 2, "b": 1}
    assert content_hash(a) == content_hash(b)


def test_excluded_fields_do_not_affect_hash():
    """T-A-02: id, content_hash and created_at are excluded from the hashed subject."""
    a = {"id": 1, "content_hash": "x", "created_at": "2026-01-01", "kind": "plan"}
    b = {"id": 2, "content_hash": "y", "created_at": "2026-02-02", "kind": "plan"}
    assert content_hash(a) == content_hash(b)


def test_a_bound_field_change_changes_the_hash():
    """T-A-02: a non-excluded field change is a different subject."""
    a = {"id": 1, "kind": "plan", "base_sha": "aaa"}
    b = {"id": 1, "kind": "plan", "base_sha": "bbb"}
    assert content_hash(a) != content_hash(b)


def test_array_order_is_significant():
    """T-A-02: array order is schema-defined and preserved, not sorted away."""
    a = {"evidence_ids": [1, 2, 3]}
    b = {"evidence_ids": [3, 2, 1]}
    assert canonical_json(a) != canonical_json(b)


def test_non_ascii_round_trips_as_utf8_not_escapes():
    """T-A-02: ensure_ascii=False keeps non-ASCII text literal in the UTF-8 bytes."""
    encoded = canonical_json({"title": "café"})
    assert "café".encode("utf-8") in encoded
    assert b"\\u" not in encoded


def test_serialization_version_is_part_of_the_hash(monkeypatch):
    """T-A-02: bumping SERIALIZATION_VERSION changes the hash of an unchanged record."""
    record = {"kind": "plan", "base_sha": "aaa"}
    before = content_hash(record)
    monkeypatch.setattr(canonical, "SERIALIZATION_VERSION", 2)
    after = content_hash(record)
    assert before != after


def test_non_json_value_is_rejected():
    """T-A-02, must-reject: a value json.dumps cannot represent raises TypeError, not a silent default."""
    with pytest.raises(TypeError):
        canonical_json({"bad": {1, 2, 3}})
