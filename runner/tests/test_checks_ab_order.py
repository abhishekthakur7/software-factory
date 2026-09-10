"""The checks execution policy places dependency evidence after planned test comparison."""
import pytest

from runner.stages import checks, run_stage
from runner.tests.test_checks_order import _ready_ticket, conn


def test_dependency_verification_follows_base_test_comparison_in_the_declared_order():
    assert checks.CHECK_ORDER.index("base_test_diff") < checks.CHECK_ORDER.index("dep_verify")
    assert checks.CHECK_ORDER.index("dep_verify") < checks.CHECK_ORDER.index("size_gate")


def test_recipe_exception_disposes_both_views_without_inventing_check_results(conn, tmp_path, monkeypatch):
    """A crash during execution leaves no writable copy or synthetic result."""
    ticket_id = _ready_ticket(conn, tmp_path)
    views = []

    def crash(*args, **kwargs):
        views.extend((kwargs["base_copy"], kwargs["head_copy"]))
        assert all(path.is_dir() for path in views)
        raise RuntimeError("injected execution crash")

    monkeypatch.setattr(checks, "_run_recipes", crash)
    with pytest.raises(RuntimeError, match="injected execution crash"):
        run_stage(conn, ticket_id, "checks", runs_dir=tmp_path)
    assert views and all(not path.exists() for path in views)
    assert conn.execute("SELECT COUNT(*) FROM check_result WHERE check_name LIKE 'recipe:%'").fetchone()[0] == 0


def test_must_fail_source_drift_after_disposal_even_when_execution_also_crashes(conn, tmp_path, monkeypatch):
    """Source drift is recorded as nonwaivable integrity failure on the crash path."""
    ticket_id = _ready_ticket(conn, tmp_path)

    def tamper(*args, **kwargs):
        (kwargs["run_dir"] / "checkouts/base/undeclared.txt").write_text("tampered\n")
        raise RuntimeError("injected execution crash")

    monkeypatch.setattr(checks, "_run_recipes", tamper)
    assert run_stage(conn, ticket_id, "checks", runs_dir=tmp_path) == "fail"
    failures = conn.execute("SELECT result, evidence_tuple_id FROM check_result WHERE check_name = 'sandbox_integrity'").fetchall()
    assert len(failures) == 1 and failures[0]["result"] == "fail" and failures[0]["evidence_tuple_id"] is not None
