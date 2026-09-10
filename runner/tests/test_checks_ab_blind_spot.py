"""The checks stage routes unavailable security evidence to the waivable review path."""
from dataclasses import replace

import pytest

from runner import recipes, record
from runner.db import connect
from runner.run_ledger import open_stage_run
from runner.stages import checks


def test_a_security_evidence_blind_spot_opens_one_red_check_instead_of_a_fix_round(tmp_path):
    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = record.insert(conn, "ticket", state="checks", opened_at=record.now(), tier_final="light")
    stage_run_id = open_stage_run(conn, ticket_id=ticket_id, stage="checks")
    review_tuple_id = record.insert(conn, "evidence_tuple", ticket_id=ticket_id, kind="review", content_hash="review-subject")
    ticket = record.get(conn, "ticket", ticket_id)

    checks._apply_routing(
        conn, ticket, stage_run_id, review_tuple_id=review_tuple_id,
        blocking_results=[("recipe:fixture_security@head", "blind_spot", 1)], catalogue={}, project_recipes=[], recipe_results={},
    )

    route = conn.execute("SELECT result, summary FROM check_result WHERE stage_run_id = ?", (stage_run_id,)).fetchone()
    item = conn.execute("SELECT kind, stage FROM queue_item WHERE ticket_id = ?", (ticket_id,)).fetchone()
    assert route["result"] == "fail"
    assert "evidence gap" in route["summary"]
    assert (item["kind"], item["stage"]) == ("red_check", "checks")


@pytest.mark.parametrize("kind", ["dependency", "lint"])
def test_unavailable_recipe_registry_records_bound_evidence_without_launching(tmp_path, monkeypatch, kind):
    """An unmet recipe endpoint is a named, waivable evidence gap before any execution."""
    conn = connect(tmp_path / "factory.sqlite")
    ticket_id = record.insert(conn, "ticket", state="checks", tier_final="light")
    stage_run_id = open_stage_run(conn, ticket_id=ticket_id, stage="checks")
    review_tuple_id = record.insert(conn, "evidence_tuple", ticket_id=ticket_id, kind="review", content_hash="subject")
    recipe = replace(recipes.load_catalogue()["fixture_lint"], kind=kind, network="registry", registry_endpoints=("unavailable.invalid",))

    def forbidden_launch(**kwargs):
        raise AssertionError("an unavailable recipe must not launch")

    monkeypatch.setattr(recipes.launcher, "launch", forbidden_launch)
    results, blocking, _ = checks._run_recipes(
        conn, ticket_id, stage_run_id, catalogue={recipe.id: recipe}, project_recipes=[recipe.id],
        base_copy=tmp_path / "base", head_copy=tmp_path / "head", run_dir=tmp_path / "run",
        review_tuple_id=review_tuple_id, vendor_classpath="",
    )
    assert results[recipe.id]["head"].outcome == "unavailable"
    assert len(blocking) == 1 and blocking[0][1] == "blind_spot"
    rows = conn.execute("SELECT result, summary, evidence_tuple_id, evidence_artefact FROM check_result").fetchall()
    assert len(rows) == 2
    assert all(row["result"] == "blind_spot" and "unavailable.invalid" in row["summary"] for row in rows)
    assert all(row["evidence_tuple_id"] == review_tuple_id and row["evidence_artefact"] is not None for row in rows)
