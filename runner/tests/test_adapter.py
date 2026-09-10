"""The Cursor SDK adapter: envelope, sandboxed invocation, tool-call rows, cost provenance.

Every test drives `adapters.cursor_sdk.invoke` against the fixture worker
under `runner/tests/fixtures/adapter/fixture_worker.py`, chosen by the
`FIXTURE_ADAPTER_CASE` environment variable, through a test copy of
`runtime.yaml` and `sandbox.yaml`: the adapter cannot tell this fixture
apart from the real Cursor SDK worker except by the argv it was given, so
these are true contract tests of `runner/adapters/cursor_sdk.py` and
`runner/envelope.py`, not of the SDK itself. No network runs in this
suite; the one test of the real worker skips loudly unless a live
`CURSOR_API_KEY` is set.
"""
import json
import os
import sys
from pathlib import Path

import pytest
import yaml

from runner import artefact_registry, canonical, envelope as envelope_mod, manifest, record, tickets
from runner.adapters import cursor_sdk, cursor_sdk_worker
from runner.db import connect

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "adapter"
WORKER_PATH = FIXTURES_DIR / "fixture_worker.py"
EVAL_DIR = Path(__file__).parent.parent.parent / "factory" / "evals" / "adapters" / "cursor_sdk"


def _runtime_path(tmp_path: Path, *, models: tuple[str, ...] = ("claude-sonnet-5",)) -> Path:
    doc = yaml.safe_load((FIXTURES_DIR / "runtime.yaml").read_text())
    doc["adapters"]["cursor_sdk"]["command"] = [sys.executable, str(WORKER_PATH)]
    doc["adapters"]["cursor_sdk"]["models"] = list(models)
    path = tmp_path / "runtime.yaml"
    path.write_text(yaml.safe_dump(doc))
    return path


def _entry(**overrides) -> manifest.Entry:
    fields = dict(
        stage="context_gathering", tier="standard", agent="factory/agents/context_gathering.md", skill="factory/skills/context_gathering.md",
        shared_skills=(), rubric="factory/rubrics/context_gathering.md", tool_allowlist=("read_file", "write_file"),
        budget_source="factory/config/tiers.yaml", budget={"tokens": 400000, "wall_clock_seconds": 1200},
        runtime_adapter="cursor_sdk", runtime_version="1.0.31", model_requested="claude-sonnet-5",
        grader_model="claude-sonnet-5", sandbox_policy="enforced", credential_roles=(), toolchain={"jdk": "17"},
        restatement_model=None, agent_hash="agenthash", skill_hash="skillhash", shared_skill_hashes=(),
        rubric_hash="rubrichash", manifest_hash="manifesthash",
    )
    fields.update(overrides)
    return manifest.Entry(**fields)


def _ticket(conn, tmp_path, **overrides) -> object:
    fields = dict(
        title="t", trust_profile_hash="tph", trust_approval_set_hash="tash", data_class="internal",
        base_sha="base123", head_sha="head123", worktree_path=str(tmp_path / "worktree"),
    )
    fields.update(overrides)
    ticket_id = tickets.open_ticket(conn, **fields)
    Path(fields["worktree_path"]).mkdir(parents=True, exist_ok=True)
    return record.get(conn, "ticket", ticket_id)


def _env_source(*, case: str | None = None, payload_path: Path | None = None) -> dict:
    env = {"PATH": os.environ.get("PATH", ""), "HOME": os.environ.get("HOME", ""), "TMPDIR": os.environ.get("TMPDIR", "")}
    if payload_path is not None:
        env["FIXTURE_ADAPTER_PAYLOAD_PATH"] = str(payload_path)
    if case is not None:
        env["FIXTURE_ADAPTER_CASE"] = case
    return env


def _invoke(conn, tmp_path, case, *, entry=None, ticket=None, parent_run_id=None, payload_path=None):
    entry = entry or _entry()
    ticket = ticket if ticket is not None else _ticket(conn, tmp_path)
    return cursor_sdk.invoke(
        conn, ticket=ticket, stage=entry.stage, tier=entry.tier, entry=entry,
        runs_dir=tmp_path / "runs", parent_run_id=parent_run_id,
        runtime_path=_runtime_path(tmp_path), sandbox_path=FIXTURES_DIR / "sandbox.yaml",
        env_source=_env_source(case=case, payload_path=payload_path),
    )


def _open(tmp_path):
    return connect(tmp_path / "factory.sqlite")


# ---------------------------------------------------------------------------
# Criteria 1-7: fresh invocation, governed inputs, rubric, no
# user-level config, rerun from record, reconstructable envelope, child runs.
# ---------------------------------------------------------------------------


def test_setting_sources_is_empty_so_no_user_level_runtime_configuration_reaches_a_run():
    """the real worker passes setting_sources=[] to the SDK, admitting no user/team/MDM/plugin source."""
    source = Path(cursor_sdk_worker.__file__).read_text()
    assert "setting_sources=[]" in source


def test_invocation_receives_the_ticket_governed_artefacts_and_their_hashes(tmp_path):
    """the written envelope names every registered artefact's id and hash, the governed input set for the run."""
    conn = _open(tmp_path)
    ticket = _ticket(conn, tmp_path)
    source_path = tmp_path / "ticket_source.md"
    source_path.write_text("ticket body\n")
    artefact_id = artefact_registry.register(conn, ticket_id=ticket["id"], kind="ticket_source", path=source_path)
    artefact = record.get(conn, "artefact", artefact_id)

    result = _invoke(conn, tmp_path, "settled", ticket=ticket)

    envelope_path = tmp_path / "runs" / "tickets" / str(ticket["id"]) / "runs" / str(result.stage_run_id) / "envelope.json"
    written = json.loads(envelope_path.read_text())
    assert {"artefact_id": artefact_id, "kind": "ticket_source", "hash": artefact["hash"], "guard_decision_id": None} in written["inputs"]


def test_invocation_receives_the_rubric_hash(tmp_path):
    """the envelope names the manifest entry's rubric hash."""
    conn = _open(tmp_path)
    result = _invoke(conn, tmp_path, "settled")
    envelope_path = tmp_path / "runs" / "tickets" / "1" / "runs" / str(result.stage_run_id) / "envelope.json"
    written = json.loads(envelope_path.read_text())
    assert written["rubric_hash"] == "rubrichash"


def test_a_second_invocation_opens_its_own_run_dir_with_nothing_from_the_first(tmp_path):
    """two invocations of the same ticket and stage get separate run directories; neither's out/ leaks into the other's."""
    conn = _open(tmp_path)
    ticket = _ticket(conn, tmp_path)
    first = _invoke(conn, tmp_path, "with_output", ticket=ticket)
    second = _invoke(conn, tmp_path, "settled", ticket=ticket)

    assert first.stage_run_id != second.stage_run_id
    first_out = tmp_path / "runs" / "tickets" / str(ticket["id"]) / "runs" / str(first.stage_run_id) / "out"
    second_out = tmp_path / "runs" / "tickets" / str(ticket["id"]) / "runs" / str(second.stage_run_id) / "out"
    assert (first_out / "result.md").exists()
    assert not (second_out / "result.md").exists()


def test_envelope_reconstructs_from_the_record_alone_with_matching_hashes_and_versions(tmp_path):
    """export/reconstruct fixture: every hash and version identity reconstruct recovers matches what build wrote."""
    conn = _open(tmp_path)
    ticket = _ticket(conn, tmp_path)
    result = _invoke(conn, tmp_path, "settled", ticket=ticket)

    rebuilt = envelope_mod.reconstruct(conn, result.stage_run_id, runs_dir=tmp_path / "runs")
    assert envelope_mod.content_hash(rebuilt) is not None  # reconstruct does not raise
    run = record.get(conn, "stage_run", result.stage_run_id)
    assert rebuilt.agent_hash == run["agent_ref"] == "agenthash"
    assert rebuilt.skill_hash == run["skill_ref"] == "skillhash"
    assert rebuilt.rubric_hash == run["rubric_ref"] == "rubrichash"
    assert rebuilt.manifest_hash == run["manifest_hash"]
    assert rebuilt.recipe_set_hash == run["recipe_set_hash"]
    assert rebuilt.runtime_adapter == run["runtime"] == "cursor_sdk"
    assert rebuilt.runtime_version == run["runtime_version"] == "1.0.31"
    assert rebuilt.adapter_version == run["adapter_version"] == cursor_sdk.ADAPTER_VERSION
    assert rebuilt.sandbox_digest == run["sandbox_digest"]
    assert rebuilt.toolchain_digest == run["toolchain_digest"]
    assert rebuilt.provider_request_id == "req-settled"


def test_a_child_invocation_records_its_own_run_separate_from_its_parent(tmp_path):
    """a restatement-style child invocation opens its own stage_run under parent_run_id, with its own model/tokens/cost."""
    conn = _open(tmp_path)
    ticket = _ticket(conn, tmp_path)
    parent = _invoke(conn, tmp_path, "settled", ticket=ticket)
    child = _invoke(conn, tmp_path, "runtime_estimate", ticket=ticket, parent_run_id=parent.stage_run_id)

    assert child.stage_run_id != parent.stage_run_id
    child_row = record.get(conn, "stage_run", child.stage_run_id)
    assert child_row["parent_run_id"] == parent.stage_run_id
    assert child_row["cost_basis"] == "runtime_estimate"
    assert record.get(conn, "stage_run", parent.stage_run_id)["cost_basis"] == "provider_settled"


# ---------------------------------------------------------------------------
# Criteria 8-11: cost-basis fixtures.
# ---------------------------------------------------------------------------


def test_settled_fixture_sets_provider_settled_cost_fields(tmp_path):
    conn = _open(tmp_path)
    result = _invoke(conn, tmp_path, "settled")
    run = record.get(conn, "stage_run", result.stage_run_id)
    assert run["cost_basis"] == "provider_settled"
    assert run["cost"] == 0.42
    assert run["currency"] == "USD"
    assert run["cost_settled_at"] is not None


def test_runtime_estimate_fixture_sets_runtime_estimate_cost_basis(tmp_path):
    conn = _open(tmp_path)
    result = _invoke(conn, tmp_path, "runtime_estimate")
    run = record.get(conn, "stage_run", result.stage_run_id)
    assert run["cost_basis"] == "runtime_estimate"
    assert run["cost"] == 0.05


def test_price_table_fixture_sets_price_table_estimate_and_records_pricing_table_hash(tmp_path):
    conn = _open(tmp_path)
    result = _invoke(conn, tmp_path, "price_table")
    run = record.get(conn, "stage_run", result.stage_run_id)
    assert run["cost_basis"] == "price_table_estimate"
    assert run["pricing_table_hash"] is not None
    assert run["cost"] is not None and run["cost"] > 0


def test_null_fixture_leaves_cost_fields_null_and_unavailable(tmp_path):
    conn = _open(tmp_path)
    result = _invoke(conn, tmp_path, "null_cost")
    run = record.get(conn, "stage_run", result.stage_run_id)
    assert run["cost_basis"] == "unavailable"
    assert run["cost"] is None
    assert run["currency"] is None


# ---------------------------------------------------------------------------
# Criterion 12: silent-fallback fixture.
# ---------------------------------------------------------------------------


def test_silent_fallback_fixture_reports_the_model_actually_used_never_the_requested_one(tmp_path):
    """a runtime substituting a different model without flagging it is reported truthfully and refused as infrastructure_failure."""
    conn = _open(tmp_path)
    result = _invoke(conn, tmp_path, "silent_fallback")
    assert result.model_resolved == "claude-haiku-5-20260115"
    assert result.model_requested == "claude-sonnet-5"
    assert result.outcome == "infrastructure_failure"
    assert result.failure_kind == "infrastructure"
    # no output registered on a resolved-model mismatch
    assert conn.execute(
        "SELECT COUNT(*) FROM artefact WHERE stage_run_id = ?", (result.stage_run_id,)
    ).fetchone()[0] == 0


# ---------------------------------------------------------------------------
# Criterion 13: every available field returned.
# ---------------------------------------------------------------------------


def test_settled_fixture_returns_every_available_field(tmp_path):
    conn = _open(tmp_path)
    result = _invoke(conn, tmp_path, "settled")
    assert result.model_requested == "claude-sonnet-5"
    assert result.model_resolved == "claude-sonnet-5"
    assert result.provider_request_id == "req-settled"
    assert result.tokens_in == 1000
    assert result.tokens_out == 200
    assert result.wall_clock_seconds == pytest.approx(4.2)
    assert result.cost == 0.42
    assert result.outcome == "pass"
    assert result.reasoning_summary == "did the thing"


# ---------------------------------------------------------------------------
# Criteria 14, 17: tool_call rows and the inline limit.
# ---------------------------------------------------------------------------


def test_one_governed_tool_call_row_is_recorded_per_call(tmp_path):
    conn = _open(tmp_path)
    result = _invoke(conn, tmp_path, "with_tool_calls")
    rows = conn.execute(
        "SELECT * FROM tool_call WHERE stage_run_id = ? ORDER BY seq", (result.stage_run_id,)
    ).fetchall()
    assert [row["seq"] for row in rows] == [1, 2]
    assert len(result.tool_call_ids) == 2


def test_small_tool_result_is_inline_and_large_one_is_a_result_artefact_with_an_excerpt(tmp_path):
    """The tool-result inline limit: a result over limits.yaml's bound is stored, not returned inline."""
    conn = _open(tmp_path)
    result = _invoke(conn, tmp_path, "with_tool_calls")
    rows = conn.execute(
        "SELECT * FROM tool_call WHERE stage_run_id = ? ORDER BY seq", (result.stage_run_id,)
    ).fetchall()
    small, large = rows[0], rows[1]
    assert small["inline"] == 1
    assert small["result_artefact"] is None
    assert large["inline"] == 0
    assert large["result_artefact"] is not None

    artefact = record.get(conn, "artefact", large["result_artefact"])
    full_path = Path(artefact["path"])
    assert full_path.exists()
    excerpt_path = full_path.parent / f"{large['seq']}.excerpt.txt"
    assert excerpt_path.exists()
    assert "line 0" in excerpt_path.read_text()
    assert "line 499" in excerpt_path.read_text()


# ---------------------------------------------------------------------------
# Criterion 15: missing runtime fields stay null.
# ---------------------------------------------------------------------------


def test_missing_runtime_fields_stay_null_never_estimated(tmp_path):
    conn = _open(tmp_path)
    result = _invoke(conn, tmp_path, "null_cost")
    assert result.tokens_in is None
    assert result.tokens_out is None
    assert result.wall_clock_seconds is None
    run = record.get(conn, "stage_run", result.stage_run_id)
    assert run["tokens_in"] is None
    assert run["tokens_out"] is None
    assert run["wall_clock_seconds"] is None


# ---------------------------------------------------------------------------
# Criterion 16: adoption gate / eval directory.
# ---------------------------------------------------------------------------


def test_eval_directory_cases_pass_the_adapter(tmp_path):
    """an adapter upgrade must pass every case factory/evals/adapters/cursor_sdk/ names."""
    eval_doc = yaml.safe_load((EVAL_DIR / "eval.yaml").read_text())
    conn = _open(tmp_path)
    for case in eval_doc["cases"]:
        fixture_path = EVAL_DIR / case["fixture"]
        result = _invoke(conn, tmp_path, None, payload_path=fixture_path)
        assert result.outcome == case["expected_outcome"], case["name"]
        if "expected_cost_basis" in case:
            assert result.cost_basis == case["expected_cost_basis"], case["name"]


# ---------------------------------------------------------------------------
# Additional owner-decision coverage: unavailable model, budget-driven refusal.
# ---------------------------------------------------------------------------


def test_must_reject_unavailable_model_before_any_run_is_opened(tmp_path):
    """A requested model absent from runtime.yaml's list is refused before anything starts, no output registered."""
    conn = _open(tmp_path)
    entry = _entry(model_requested="claude-opus-5")
    result = _invoke(conn, tmp_path, "settled", entry=entry)
    assert result.outcome == "infrastructure_failure"
    assert result.stage_run_id == -1
    assert conn.execute("SELECT COUNT(*) FROM stage_run").fetchone()[0] == 0


# ---------------------------------------------------------------------------
# Criteria 25, 26, 27, 28: governance binding, replayability, field
# completeness, provider request id.
# ---------------------------------------------------------------------------


def test_governance_binding_fixture_binds_trust_hashes_and_no_approval_subject_outside_planning_checks_human_review(tmp_path):
    conn = _open(tmp_path)
    ticket = _ticket(conn, tmp_path, trust_profile_hash="tph-x", trust_approval_set_hash="tash-x")
    result = _invoke(conn, tmp_path, "settled", ticket=ticket, entry=_entry(stage="context_gathering"))
    envelope_path = tmp_path / "runs" / "tickets" / str(ticket["id"]) / "runs" / str(result.stage_run_id) / "envelope.json"
    written = json.loads(envelope_path.read_text())
    assert written["trust_profile_hash"] == "tph-x"
    assert written["trust_approval_set_hash"] == "tash-x"
    assert written["approval_subject_hash"] is None


def test_governance_binding_fixture_binds_the_plan_approval_subject_for_planning(tmp_path):
    conn = _open(tmp_path)
    ticket = _ticket(conn, tmp_path)
    plan_row = {
        "kind": "plan", "ticket_id": ticket["id"], "canonical_serialization_version": canonical.SERIALIZATION_VERSION,
    }
    plan_row["content_hash"] = canonical.content_hash(plan_row)
    record.insert(conn, "evidence_tuple", **plan_row)

    result = _invoke(conn, tmp_path, "settled", ticket=ticket, entry=_entry(stage="planning"))
    envelope_path = tmp_path / "runs" / "tickets" / str(ticket["id"]) / "runs" / str(result.stage_run_id) / "envelope.json"
    written = json.loads(envelope_path.read_text())
    assert written["approval_subject_hash"] == plan_row["content_hash"]


def test_unavailable_provider_field_fixture_no_build_suffix_is_best_effort(tmp_path):
    """A model_resolved with no immutable build/version suffix sets replayability best_effort, naming the gap."""
    conn = _open(tmp_path)
    result = _invoke(conn, tmp_path, "no_build_suffix")
    assert result.replayability == "best_effort"
    assert "no_build_suffix" not in result.replayability_blind_spot  # names the model gap, not the fixture
    assert "claude-sonnet-5" in result.replayability_blind_spot
    run = record.get(conn, "stage_run", result.stage_run_id)
    assert run["replayability"] == "best_effort"
    assert run["replayability_blind_spot"] == result.replayability_blind_spot


def test_unavailable_provider_field_fixture_retention_blind_spot_is_best_effort(tmp_path):
    """A tool result that cannot lawfully be retained also sets replayability best_effort."""
    conn = _open(tmp_path)
    result = _invoke(conn, tmp_path, "retention_blind_spot")
    assert result.replayability == "best_effort"
    assert result.replayability_blind_spot == "a tool result exceeded the retention rule"


def test_exact_replayability_when_model_resolved_names_an_immutable_build(tmp_path):
    conn = _open(tmp_path)
    pinned_model = "claude-sonnet-5-20260115"
    entry = _entry(model_requested=pinned_model)
    ticket = _ticket(conn, tmp_path)
    result = cursor_sdk.invoke(
        conn, ticket=ticket, stage=entry.stage, tier=entry.tier, entry=entry,
        runs_dir=tmp_path / "runs", runtime_path=_runtime_path(tmp_path, models=(pinned_model,)),
        sandbox_path=FIXTURES_DIR / "sandbox.yaml", env_source=_env_source(case="settled_pinned_build"),
    )
    assert result.model_resolved == pinned_model
    assert result.outcome == "pass"
    assert result.replayability == "exact"
    assert result.replayability_blind_spot is None


def test_envelope_records_ordered_inputs_hashes_versions_digests_and_tool_allowlist(tmp_path):
    """The written envelope carries every field the governance-binding contract names."""
    conn = _open(tmp_path)
    result = _invoke(conn, tmp_path, "settled")
    envelope_path = tmp_path / "runs" / "tickets" / "1" / "runs" / str(result.stage_run_id) / "envelope.json"
    written = json.loads(envelope_path.read_text())
    for field_name in (
        "inputs", "agent_hash", "skill_hash", "rubric_hash", "manifest_hash", "recipe_set_hash",
        "runtime_adapter", "runtime_version", "adapter_version", "tool_versions", "mcp_server_versions",
        "model_requested", "sandbox_digest", "toolchain_digest", "base_sha", "head_sha", "data_class",
        "tool_allowlist",
    ):
        assert field_name in written
    assert written["base_sha"] == "base123"
    assert written["head_sha"] == "head123"
    assert written["data_class"] == "internal"
    assert written["tool_allowlist"] == ["read_file", "write_file"]
    assert written["sandbox_digest"] is not None
    assert written["recipe_set_hash"] is not None


def test_provider_request_id_is_recorded_where_available(tmp_path):
    """criterion 28."""
    conn = _open(tmp_path)
    result = _invoke(conn, tmp_path, "settled")
    assert result.provider_request_id == "req-settled"
    rebuilt = envelope_mod.reconstruct(conn, result.stage_run_id, runs_dir=tmp_path / "runs")
    assert rebuilt.provider_request_id == "req-settled"


# ---------------------------------------------------------------------------
# The real worker: skips loudly without a live key. No network otherwise.
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not os.environ.get("CURSOR_API_KEY"),
    reason="requires a live CURSOR_API_KEY; this suite runs no network by design",
)
def test_real_worker_invokes_the_hosted_model(tmp_path):
    envelope_path = tmp_path / "envelope.json"
    envelope_path.write_text(json.dumps({"model_requested": "claude-sonnet-5", "stage": "context_gathering"}))
    os.environ["FACTORY_RUN_OUT"] = str(tmp_path)
    result = cursor_sdk_worker.main([str(cursor_sdk_worker.__file__), str(envelope_path)])
    assert result == 0
