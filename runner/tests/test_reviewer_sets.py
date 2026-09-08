"""Reviewer sets: the slot model, the planned/actual merge, and deriving the
actual set from a real CODEOWNERS file read at a pinned commit.

`_init_repo`/`_commit_codeowners` build a throwaway git repository per test
so `read_codeowners` and `derive_actual` run against real git plumbing
rather than a stand-in; `test_approval_records.py` and `test_race_guard.py`
reuse them rather than duplicating the setup.
"""
import json
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from runner import approvals, canonical, record
from runner.db import connect
from runner.owners import load_owners
from runner.reviewer_sets import (
    Slot,
    derive_actual,
    effective_set,
    is_current,
    merge_slots,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "reviewer_sets"
OWNERS = load_owners(FIXTURES_DIR / "owners.yaml")
SENSITIVE_PATHS = yaml.safe_load((FIXTURES_DIR / "sensitive-paths.yaml").read_text())


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=repo, check=True)
    return repo


def _commit_codeowners(repo: Path, fixture_name: str) -> str:
    """Commit `fixture_name`'s text at `.github/CODEOWNERS` and return the new commit's sha."""
    target = repo / ".github" / "CODEOWNERS"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text((FIXTURES_DIR / fixture_name).read_text())
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", fixture_name], cwd=repo, check=True)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()


@pytest.fixture
def conn(tmp_path):
    connection = connect(tmp_path / "factory.sqlite")
    yield connection
    connection.close()


def _ticket(conn) -> int:
    """A minimal real `ticket` row: `reviewer_set.ticket_id` is a foreign key, so a derivation needs one to point at."""
    return record.insert(conn, "ticket", state="context", opened_at=record.now())


def test_slot_id_is_the_canonical_key_of_role_owner_and_source_rule():
    slot = Slot(source_rule="CODEOWNERS:3", owner="alice", matched_path="src/a.java", pattern="src/**")
    assert slot.slot_id == "|alice|CODEOWNERS:3"
    assert Slot.from_json(slot.to_json()) == slot


def test_matching_planned_and_actual_slots_merge_to_max_count_and_union_of_separation():
    planned = Slot(source_rule="CODEOWNERS:3", owner="alice", min_count=1, distinct_from=("x",))
    actual = Slot(source_rule="CODEOWNERS:3", owner="alice", min_count=2, distinct_from=("y",), matched_path="src/a.java")
    [merged] = merge_slots([planned], [actual])
    assert merged.key == planned.key
    assert merged.min_count == 2
    assert merged.distinct_from == ("x", "y")
    assert merged.matched_path == "src/a.java"


def test_removing_a_planned_path_never_removes_its_slot_and_a_nonmatching_slot_is_preserved():
    """the planned slot for a path the actual diff no longer touches stays in
    the effective set, and a slot only the actual diff produced is added."""
    planned_only = Slot(source_rule="CODEOWNERS:7", owner="bob", matched_path="src/b.java")
    actual_only = Slot(source_rule="CODEOWNERS:9", role="sensitive_path_owner", matched_path="src/auth/c.java")
    effective = merge_slots([planned_only], [actual_only])
    assert [slot.key for slot in effective] == [planned_only.key, actual_only.key]


def test_merged_slot_is_unresolved_when_either_side_is():
    planned = Slot(source_rule="CODEOWNERS:3", owner="alice")
    actual = Slot(source_rule="CODEOWNERS:3", owner="alice", resolved=False)
    [merged] = merge_slots([planned], [actual])
    assert merged.resolved is False


# --- deriving the actual set from CODEOWNERS -----------------------------


def test_derive_actual_records_every_path_to_rule_to_owner_match_at_the_pinned_target_base_sha(conn, tmp_path):
    """the derivation reads CODEOWNERS as committed at `target_base_sha`, not
    a later commit on top of it, and records each path's rule, pattern,
    precedence and owner (R-S6-6)."""
    repo = _init_repo(tmp_path)
    pinned_sha = _commit_codeowners(repo, "CODEOWNERS_precedence")
    _commit_codeowners(repo, "CODEOWNERS_precedence_v2")  # must never be read

    derivation = derive_actual(
        conn, ticket_id=_ticket(conn), repo_path=repo, target_base_sha=pinned_sha,
        changed_paths=["README.md", "src/other/file.py"], owners=OWNERS,
        sensitive_paths=SENSITIVE_PATHS, authority_policy_hash="policy-hash",
        membership_snapshot_hash="members-hash",
    )

    by_path = {slot.matched_path: slot for slot in derivation.slots}
    readme = by_path["README.md"]
    assert (readme.source_rule, readme.pattern, readme.precedence, readme.owner) == ("CODEOWNERS:3", "*.md", 3, "alice")
    assert readme.resolved is True
    other = by_path["src/other/file.py"]
    assert (other.source_rule, other.pattern, other.precedence, other.owner) == ("CODEOWNERS:4", "/src/**/*.py", 4, "bob")
    assert derivation.blocked is False

    row = record.get(conn, "reviewer_set", derivation.id)
    assert row["kind"] == "actual"
    assert row["codeowners_path"] == ".github/CODEOWNERS"
    expected_blob_sha = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", f"{pinned_sha}:.github/CODEOWNERS"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert row["codeowners_blob_sha"] == expected_blob_sha
    assert row["base_sha"] == pinned_sha
    assert json.loads(row["slots"]) == [slot.to_json() for slot in derivation.slots]
    hashed = {key: row[key] for key in row.keys() if key not in ("id", "content_hash")}
    assert row["content_hash"] == canonical.content_hash(hashed)


def test_effective_set_merges_planned_and_actual_slots_by_canonical_key(conn, tmp_path):
    """a planned slot sharing a key with a derived actual slot merges to the
    max minimum count and the union of separation constraints; a
    planned-only slot for a path the actual diff never touched survives (R-S6-6)."""
    repo = _init_repo(tmp_path)
    sha = _commit_codeowners(repo, "CODEOWNERS_precedence")
    ticket_id = _ticket(conn)
    derivation = derive_actual(
        conn, ticket_id=ticket_id, repo_path=repo, target_base_sha=sha,
        changed_paths=["README.md"], owners=OWNERS, sensitive_paths={},
        authority_policy_hash="policy-hash", membership_snapshot_hash="members-hash",
    )
    collision = yaml.safe_load((FIXTURES_DIR / "planned_actual_collision.yaml").read_text())
    planned = []
    for entry in collision["planned_slots"]:
        entry = dict(entry)
        entry["distinct_from"] = tuple(entry.get("distinct_from", ()))
        planned.append(Slot(**entry))

    effective_id = effective_set(conn, ticket_id=ticket_id, planned=planned, actual=derivation)
    row = record.get(conn, "reviewer_set", effective_id)
    assert row["kind"] == "effective"
    assert row["subject_hash"] == record.get(conn, "reviewer_set", derivation.id)["subject_hash"]

    slots = [Slot.from_json(data) for data in json.loads(row["slots"])]
    by_key = {slot.key: slot for slot in slots}
    merged = by_key[(None, "alice", "CODEOWNERS:3")]
    assert merged.min_count == 2  # max(planned's 2, actual's 1)
    assert merged.matched_path == "README.md"  # the actual slot fills in what the planned slot left blank
    assert merged.distinct_from == ("security_approver||trust-profile",)

    planned_only = by_key[(None, "dana", "CODEOWNERS:planned-only")]
    assert planned_only.matched_path == "README-planned.md"


def test_unresolved_owner_blocks_derivation_with_the_non_sensitive_routes(conn, tmp_path):
    """an unknown identity and an email are both unresolved owners; the
    derivation blocks with the plan/S4-removal/abandon routes, none waivable (R-S6-6)."""
    repo = _init_repo(tmp_path)
    sha = _commit_codeowners(repo, "CODEOWNERS_unknown_identity")
    derivation = derive_actual(
        conn, ticket_id=_ticket(conn), repo_path=repo, target_base_sha=sha,
        changed_paths=["docs/readme.txt", "secrets/key.pem"], owners=OWNERS,
        sensitive_paths={}, authority_policy_hash="policy-hash",
        membership_snapshot_hash="members-hash",
    )
    assert derivation.blocked is True
    assert derivation.sensitive is False
    assert derivation.waivable is False
    assert derivation.routes == ("planning", "s4_removal", "abandon")
    assert "@carol" in derivation.unresolved
    assert "legal@example.com" in derivation.unresolved
    assert all(not slot.resolved for slot in derivation.slots)


def test_initial_sensitive_path_match_only_offers_removal_or_pilot_excluded_routes(conn, tmp_path):
    """a changed path the sensitive-paths mapping claims blocks with only the
    S4-removal/pilot-excluded routes, neither waivable, even when the owner
    it names resolves cleanly (R-S6-6)."""
    repo = _init_repo(tmp_path)
    sha = _commit_codeowners(repo, "CODEOWNERS_precedence")  # doesn't cover infra/
    derivation = derive_actual(
        conn, ticket_id=_ticket(conn), repo_path=repo, target_base_sha=sha,
        changed_paths=["infra/deploy.sh"], owners=OWNERS, sensitive_paths=SENSITIVE_PATHS,
        authority_policy_hash="policy-hash", membership_snapshot_hash="members-hash",
    )
    assert derivation.sensitive is True
    assert derivation.blocked is True
    assert derivation.waivable is False
    assert derivation.routes == ("s4_removal", "pilot_excluded")
    [slot] = derivation.slots
    assert slot.role == "sensitive_path_owner"
    assert slot.owner == "bob"
    assert slot.resolved is True


def test_codeowners_coverage_of_a_path_skips_the_sensitive_paths_mapping(conn, tmp_path):
    """CODEOWNERS wins: a path it covers is never looked up in the
    sensitive-paths mapping, even when that mapping also names a glob
    covering the same path (docs/configuration.md QP-3)."""
    repo = _init_repo(tmp_path)
    sha = _commit_codeowners(repo, "CODEOWNERS_precedence")
    derivation = derive_actual(
        conn, ticket_id=_ticket(conn), repo_path=repo, target_base_sha=sha,
        changed_paths=["src/legacy/special.py"], owners=OWNERS, sensitive_paths=SENSITIVE_PATHS,
        authority_policy_hash="policy-hash", membership_snapshot_hash="members-hash",
    )
    assert derivation.sensitive is False
    [slot] = derivation.slots
    assert slot.source_rule == "CODEOWNERS:6"  # the last matching rule wins over lines 4 and 5
    assert slot.role is None
    assert slot.resolved is False  # @org/team is a team handle, unresolved
    assert derivation.routes == ("planning", "s4_removal", "abandon")


def test_seeded_distinct_from_slot_blocks_the_gate_when_one_actor_satisfies_both(conn, tmp_path):
    """separation is proved through `approvals.evaluate` over slots read
    back from a derived reviewer_set row, not by re-implementing
    separation: a `distinct_from` constraint seeded onto one derived slot
    blocks quorum when the same actor approves both slots it names (R-S6-6)."""
    repo = _init_repo(tmp_path)
    sha = _commit_codeowners(repo, "CODEOWNERS_precedence")
    ticket_id = _ticket(conn)
    derivation = derive_actual(
        conn, ticket_id=ticket_id, repo_path=repo, target_base_sha=sha,
        changed_paths=["README.md", "src/other/file.py"], owners=OWNERS,
        sensitive_paths={}, authority_policy_hash="policy-hash",
        membership_snapshot_hash="members-hash",
    )
    by_path = {slot.matched_path: slot for slot in derivation.slots}
    alice_slot = by_path["README.md"]
    bob_slot = by_path["src/other/file.py"]
    seeded_alice_slot = replace(alice_slot, distinct_from=(bob_slot.slot_id,))

    row_id = record.insert(
        conn, "reviewer_set", ticket_id=ticket_id, kind="effective",
        slots=json.dumps([seeded_alice_slot.to_json(), bob_slot.to_json()]),
        canonical_serialization_version=canonical.SERIALIZATION_VERSION,
    )
    stored = record.get(conn, "reviewer_set", row_id)
    slots = [Slot.from_json(data) for data in json.loads(stored["slots"])]

    subject = "subject-5"
    common = {
        "gate": "review", "subject_hash": subject, "role": "owner", "decision": "approve",
        "authority_policy_hash": "policy-hash", "membership_snapshot_hash": "members-hash",
        "attestation_version": "v1", "attestation_hash": "att-1",
    }
    approvals.record_approval(conn, slot_id=seeded_alice_slot.slot_id, actor_identity="alice", **common)
    alice_on_bob_slot = approvals.record_approval(conn, slot_id=bob_slot.slot_id, actor_identity="alice", **common)

    blocked = approvals.evaluate(conn, gate="review", subject_hash=subject, slots=slots)
    assert not blocked.satisfied
    assert any(reason.startswith("separation:") for reason in blocked.reasons)

    # Superseding alice's approval on the bob-owned slot with bob's own
    # clears the separation constraint: the two slots no longer share an actor.
    approvals.record_approval(
        conn, slot_id=bob_slot.slot_id, actor_identity="bob", supersedes=alice_on_bob_slot, **common
    )
    cleared = approvals.evaluate(conn, gate="review", subject_hash=subject, slots=slots)
    assert cleared.satisfied


def test_a_changed_diff_invalidates_the_stored_actual_set_and_recompute_makes_a_fresh_one(conn, tmp_path):
    """a stored actual set is current only for the exact path set and base
    sha it was derived from; a moved diff invalidates it, and deriving
    again produces a fresh, current row (R-S6-6)."""
    repo = _init_repo(tmp_path)
    sha = _commit_codeowners(repo, "CODEOWNERS_precedence")
    ticket_id = _ticket(conn)
    derivation = derive_actual(
        conn, ticket_id=ticket_id, repo_path=repo, target_base_sha=sha,
        changed_paths=["README.md"], owners=OWNERS, sensitive_paths={},
        authority_policy_hash="policy-hash", membership_snapshot_hash="members-hash",
    )
    assert is_current(conn, derivation.id, changed_paths=["README.md"], target_base_sha=sha)
    assert not is_current(
        conn, derivation.id, changed_paths=["README.md", "src/other/file.py"], target_base_sha=sha
    )
    assert not is_current(conn, derivation.id, changed_paths=["README.md"], target_base_sha="a-different-sha")

    fresh = derive_actual(
        conn, ticket_id=ticket_id, repo_path=repo, target_base_sha=sha,
        changed_paths=["README.md", "src/other/file.py"], owners=OWNERS, sensitive_paths={},
        authority_policy_hash="policy-hash", membership_snapshot_hash="members-hash",
    )
    assert fresh.id != derivation.id
    assert is_current(
        conn, fresh.id, changed_paths=["README.md", "src/other/file.py"], target_base_sha=sha
    )
