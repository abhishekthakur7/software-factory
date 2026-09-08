"""The S6 race guard: recomputing the actual reviewer set immediately before packet assembly and dispatch.

Reuses `test_reviewer_sets.py`'s git-repo helpers rather than duplicating
them, so the guard is exercised against the same real CODEOWNERS-reading
path `derive_actual` itself is tested against.
"""
import pytest

from runner import record
from runner.db import connect
from runner.reviewer_sets import derive_actual, recompute_before_dispatch
from runner.tests.test_reviewer_sets import OWNERS, _commit_codeowners, _init_repo, _ticket


@pytest.fixture
def conn(tmp_path):
    connection = connect(tmp_path / "factory.sqlite")
    yield connection
    connection.close()


def test_recompute_before_dispatch_writes_a_fresh_row_matching_s5_when_the_diff_did_not_move(conn, tmp_path):
    """the race guard always writes a new `actual` row, but when nothing
    changed between S5 preflight and S6 dispatch its content is identical
    to the row S5 produced (R-S6-6)."""
    repo = _init_repo(tmp_path)
    sha = _commit_codeowners(repo, "CODEOWNERS_precedence")
    ticket_id = _ticket(conn)
    kwargs = dict(
        ticket_id=ticket_id, repo_path=repo, target_base_sha=sha,
        changed_paths=["README.md"], owners=OWNERS, sensitive_paths={},
        authority_policy_hash="policy-hash", membership_snapshot_hash="members-hash",
    )
    s5 = derive_actual(conn, **kwargs)
    s6 = recompute_before_dispatch(conn, **kwargs)

    assert s6.id != s5.id
    s5_row = record.get(conn, "reviewer_set", s5.id)
    s6_row = record.get(conn, "reviewer_set", s6.id)
    assert s6_row["content_hash"] == s5_row["content_hash"]
    assert not s5.blocked and not s6.blocked


def test_recompute_before_dispatch_diverges_from_s5_when_the_diff_moved(conn, tmp_path):
    """a path added to the diff between S5 preflight and S6 dispatch makes
    the race guard's row differ from S5's, invalidating the earlier one (R-S6-6)."""
    repo = _init_repo(tmp_path)
    sha = _commit_codeowners(repo, "CODEOWNERS_precedence")
    ticket_id = _ticket(conn)
    s5 = derive_actual(
        conn, ticket_id=ticket_id, repo_path=repo, target_base_sha=sha,
        changed_paths=["README.md"], owners=OWNERS, sensitive_paths={},
        authority_policy_hash="policy-hash", membership_snapshot_hash="members-hash",
    )
    s6 = recompute_before_dispatch(
        conn, ticket_id=ticket_id, repo_path=repo, target_base_sha=sha,
        changed_paths=["README.md", "src/other/file.py"], owners=OWNERS, sensitive_paths={},
        authority_policy_hash="policy-hash", membership_snapshot_hash="members-hash",
    )

    s5_row = record.get(conn, "reviewer_set", s5.id)
    s6_row = record.get(conn, "reviewer_set", s6.id)
    assert s6_row["content_hash"] != s5_row["content_hash"]
    assert s6_row["path_set_hash"] != s5_row["path_set_hash"]
