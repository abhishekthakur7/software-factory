"""Canonical JSON and content hashing.

Every content hash and subject hash in the record — check results, guard
decisions, reviewer sets, approval records, waivers, evidence tuples, human
verdicts — calls `content_hash`, so a change here changes the meaning of
every hash already on disk. That is deliberate for
`SERIALIZATION_VERSION`: it is folded into the hashed object itself, not
just recorded beside it, so bumping it changes every hash without a
separate migration step.
"""
import hashlib
import json
from collections.abc import Mapping

SERIALIZATION_VERSION = 1

# Database ids are storage detail, not the subject; the hash field itself
# would be self-referential; creation timestamps are audit-only and would
# make identical records hash differently depending on when they were
# written.
DEFAULT_EXCLUDED = frozenset({"id", "content_hash", "created_at"})


def canonical_json(value: object) -> bytes:
    """UTF-8 JSON with sorted object keys and no insignificant whitespace.

    Array order is preserved as given — the caller's schema defines it.
    Raises `TypeError` for any value `json.dumps` cannot represent (no
    `default=` fallback), since a silently stringified value would hash
    unpredictably.
    """
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")


def content_hash(record: Mapping, *, exclude: frozenset[str] = DEFAULT_EXCLUDED) -> str:
    """SHA-256 hex digest of `record`'s canonical JSON, `exclude` keys dropped.

    `canonical_serialization_version` is added to the hashed object (not
    merely alongside it) so that changing `SERIALIZATION_VERSION` changes
    the subject even when every other field is unchanged.
    """
    subject = {key: value for key, value in record.items() if key not in exclude}
    subject["canonical_serialization_version"] = SERIALIZATION_VERSION
    return hashlib.sha256(canonical_json(subject)).hexdigest()
