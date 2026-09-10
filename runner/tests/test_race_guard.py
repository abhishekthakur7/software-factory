"""The human_review race guard: recomputing the actual reviewer set immediately before packet assembly and dispatch.

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


def test_recompute_before_dispatch_writes_a_fresh_row_matching_checks_when_the_diff_did_not_move(conn, tmp_path):
    """The race guard always writes a new `actual` row, but when nothing
    changed between checks preflight and human_review dispatch its content is identical
    to the row checks produced."""
    repo = _init_repo(tmp_path)
    sha = _commit_codeowners(repo, "CODEOWNERS_precedence")
    ticket_id = _ticket(conn)
    kwargs = dict(
        ticket_id=ticket_id, repo_path=repo, target_base_sha=sha,
        changed_paths=["README.md"], owners=OWNERS, sensitive_paths={},
        authority_policy_hash="policy-hash", membership_snapshot_hash="members-hash",
    )
    checks_set = derive_actual(conn, **kwargs)
    human_review_set = recompute_before_dispatch(conn, **kwargs)

    assert human_review_set.id != checks_set.id
    checks_row = record.get(conn, "reviewer_set", checks_set.id)
    human_review_row = record.get(conn, "reviewer_set", human_review_set.id)
    assert human_review_row["content_hash"] == checks_row["content_hash"]
    assert not checks_set.blocked and not human_review_set.blocked


def test_recompute_before_dispatch_diverges_from_checks_when_the_diff_moved(conn, tmp_path):
    """A path added to the diff between checks preflight and human_review dispatch makes
    the race guard's row differ from checks's, invalidating the earlier one."""
    repo = _init_repo(tmp_path)
    sha = _commit_codeowners(repo, "CODEOWNERS_precedence")
    ticket_id = _ticket(conn)
    checks_set = derive_actual(
        conn, ticket_id=ticket_id, repo_path=repo, target_base_sha=sha,
        changed_paths=["README.md"], owners=OWNERS, sensitive_paths={},
        authority_policy_hash="policy-hash", membership_snapshot_hash="members-hash",
    )
    human_review_set = recompute_before_dispatch(
        conn, ticket_id=ticket_id, repo_path=repo, target_base_sha=sha,
        changed_paths=["README.md", "src/other/file.py"], owners=OWNERS, sensitive_paths={},
        authority_policy_hash="policy-hash", membership_snapshot_hash="members-hash",
    )

    checks_row = record.get(conn, "reviewer_set", checks_set.id)
    human_review_row = record.get(conn, "reviewer_set", human_review_set.id)
    assert human_review_row["content_hash"] != checks_row["content_hash"]
    assert human_review_row["path_set_hash"] != checks_row["path_set_hash"]
