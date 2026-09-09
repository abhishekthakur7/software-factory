"""S5 routes the collected recipe and independent check results (R-S5-1)."""
from types import SimpleNamespace

import pytest

from runner import record
from runner.db import connect
from runner.run_ledger import open_stage_run
from runner.stages import S5


@pytest.mark.parametrize("kind,level,extra_red,reported", [
    ("lint", None, False, False), ("compile", None, False, False),
    ("test", "unit", False, False), ("test", "integration", False, False),
    ("test", "end_to_end", False, False), ("test", "unit", True, False),
    ("security", None, False, True),
])
def test_driver_routes_recipe_failures_without_counting_their_check_rows_twice(tmp_path, kind, level, extra_red, reported):
    conn = connect(tmp_path / "record.sqlite")
    try:
        ticket_id = record.insert(conn, "ticket", state="checks", tier_final="light")
        stage_id = open_stage_run(conn, ticket_id=ticket_id, stage="S5")
        tuple_id = record.insert(conn, "evidence_tuple", ticket_id=ticket_id, kind="review", content_hash="review")
        results = {"base": SimpleNamespace(outcome="pass", reported_result=None),
                   "head": SimpleNamespace(outcome="pass" if reported else "fail", reported_result="fail" if reported else None)}
        checks = [("recipe:sample@head", "fail", 1), ("regression_only", "fail" if not reported else "pass", 2)]
        if extra_red:
            checks.append(("scope_diff", "fail", 3))
        S5._apply_routing(
            conn, record.get(conn, "ticket", ticket_id), stage_id, review_tuple_id=tuple_id,
            blocking_results=checks, catalogue={"sample": SimpleNamespace(kind=kind, level=level)},
            project_recipes=["sample"], recipe_results={"sample": results},
        )
        repairable = kind in {"lint", "compile"} or (kind == "test" and level in {"unit", "integration"})
        repairable = repairable and not extra_red
        assert record.get(conn, "ticket", ticket_id)["state"] == ("implementing" if repairable else "checks")
        items = conn.execute("SELECT kind FROM queue_item WHERE ticket_id = ?", (ticket_id,)).fetchall()
        assert [row["kind"] for row in items] == ([] if repairable else ["red_check"])
        route = conn.execute("SELECT check_tier FROM check_result WHERE check_name = 'fix_round_route'").fetchone()
        assert route["check_tier"] == "advisory"
    finally:
        conn.close()
