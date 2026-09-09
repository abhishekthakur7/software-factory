"""Required mechanical fixture replays for adoption (R-F-14)."""
import os
import json
import sqlite3
from pathlib import Path

import pytest
import yaml

from runner import evals, record
from runner.db import connect
from runner.paths import REPO_ROOT

ROOT = Path(os.environ.get("FACTORY_GATE_ROOT", str(REPO_ROOT)))
EVAL_ROOT = ROOT / "factory/evals"


@pytest.mark.parametrize("name", ["incident-history", "control-history", "coverage-history"])
def test_history_replay_preserves_prior_evidence_and_rejects_rewriting_it(tmp_path, name):
    """R-F-14: seeded history survives reopening and the write path refuses evidence replacement."""
    directory = EVAL_ROOT / "record" / name
    evals.check(directory)
    spec = yaml.safe_load((directory / "eval.yaml").read_text())
    for index, case in enumerate(spec["cases"]):
        seed = yaml.safe_load((directory / case["fixture"]).read_text())
        assert seed["rows"] and seed["immutable"]
        database = tmp_path / f"history-{index}.sqlite"
        conn = connect(database)
        for row in seed["rows"]:
            record.insert(conn, row["table"], **row["fields"])
        conn.commit()
        conn.close()
        conn = connect(database)
        try:
            for target in seed["immutable"]:
                table, row_id, field = target["table"], target["id"], target["field"]
                before = dict(record.get(conn, table, row_id))
                assert before[field] != target["replacement"]
                with pytest.raises(sqlite3.IntegrityError):
                    record.update(conn, table, row_id, **{field: target["replacement"]})
                assert dict(record.get(conn, table, row_id)) == before
                if table == "incident_observation":
                    with pytest.raises(sqlite3.IntegrityError):
                        conn.execute(f"DELETE FROM {table} WHERE id = ?", (row_id,))
            assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        finally:
            conn.close()


def test_every_configured_recipe_runs_in_both_copies_and_disposes_them(tmp_path):
    """R-F-14: the configured current base produces retained recipe evidence and no surviving copies."""
    from runner.adoption import dry_run_recipes

    directory = EVAL_ROOT / "sandbox/copy-disposal"
    evals.check(directory)
    spec = yaml.safe_load((directory / "eval.yaml").read_text())
    for index, case in enumerate(spec["cases"]):
        fixture = yaml.safe_load((directory / case["fixture"]).read_text())
        expected_results = fixture.pop("expected_results", {})
        assert fixture == {
            "source": "configured_project_current_base", "views": ["base", "head"], "expected_disposed": True,
        }
        evidence = dry_run_recipes(tmp_path / str(index), factory_root=ROOT / "factory")
        assert evidence["recipes"]
        assert evidence["disposed"] and evidence["unchanged"]
        assert all(set(result["views"]) == {"base", "head"} for result in evidence["recipes"])
        assert all(result["outcome"] == expected_results.get(result["recipe"], "pass") for result in evidence["recipes"]), evidence
        conn = connect(tmp_path / str(index) / "evidence.sqlite")
        rows = conn.execute(
            "SELECT cr.check_name, cr.result, a.path, a.utility_run_id FROM check_result cr "
            "JOIN artefact a ON a.id = cr.evidence_artefact"
        ).fetchall()
        assert {row["check_name"] for row in rows} == {f"recipe_dry_run:{result['recipe']}" for result in evidence["recipes"]}
        assert len(rows) == len(evidence["recipes"])
        for row in rows:
            persisted = json.loads(Path(row["path"]).read_text())
            assert row["result"] == persisted["outcome"]
            assert set(persisted["views"]) == {"base", "head"}
            assert row["utility_run_id"] is not None
        conn.close()


def test_recipe_crash_still_records_disposal_and_preserves_immutable_checkouts(tmp_path, monkeypatch):
    """R-F-14/R-I-14: a failed recipe cannot leave writable copies or erase the disposal evidence."""
    from runner import recipes
    from runner.adoption import dry_run_recipes

    def crash(*args, **kwargs):
        raise RuntimeError("injected recipe crash")

    monkeypatch.setattr(recipes, "run", crash)
    with pytest.raises(RuntimeError, match="injected recipe crash"):
        dry_run_recipes(tmp_path)
    evidence = json.loads((tmp_path / "results/disposal.json").read_text())
    assert evidence["disposed"] and evidence["unchanged"]
    conn = connect(tmp_path / "evidence.sqlite")
    assert conn.execute("SELECT outcome FROM utility_run").fetchone()[0] == "fail"
    assert conn.execute("SELECT COUNT(*) FROM check_result").fetchone()[0] == 0
    conn.close()
