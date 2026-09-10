"""Clarification's criteria half: id continuity, forced-category pre-fill, the agreement check, the split
rule, the question candidates the driver derives on its own, and the blocking-only exit gate.

`_clarifying_ticket` mirrors `test_clarification_questions.py`'s own helper of the same shape, extended with
the `ticket_source` and `brief` artefacts the criteria half's restatement children read.
"""
from pathlib import Path

import yaml

from runner import (
    artefact_registry, artefacts, gates, manifest, questions, record, rubrics, run_ledger,
)
from runner.checks import artefact_structure
from runner.db import connect
from runner.paths import FACTORY_DIR
from runner.stages import clarification, run_stage

AGENT_FIXTURES_DIR = FACTORY_DIR / "evals" / "agents" / "clarification" / "fixtures"
RUBRIC_FIXTURES_DIR = FACTORY_DIR / "evals" / "rubrics" / "clarification" / "fixtures"
RUBRIC_PATH = FACTORY_DIR / "rubrics" / "clarification.md"

ABHISHEK = "abhishek"


def _conn(tmp_path):
    return connect(tmp_path / "factory.sqlite")


def _clarifying_ticket(conn, tmp_path, *, source_text: str = "seed criterion", **fields) -> int:
    ticket_id = record.insert(
        conn, "ticket", state="clarifying", opened_at=record.now(),
        tier_provisional=fields.pop("tier_provisional", "standard"),
        factory_manifest_hash=fields.pop("factory_manifest_hash", manifest.current_hash()),
        **fields,
    )
    source_path = tmp_path / "ticket_source.md"
    source_path.write_text(source_text + "\n")
    artefact_registry.register(conn, ticket_id=ticket_id, kind="ticket_source", path=source_path)
    brief_path = tmp_path / "brief.md"
    brief_path.write_text("A brief.\n")
    artefact_registry.register(conn, ticket_id=ticket_id, kind="brief", path=brief_path)
    return ticket_id


# --- AC-n id continuity across versions ---


def test_a_brand_new_id_passes():
    assert clarification._check_id_continuity([{"id": "AC-1", "source": "s"}], []) == []


def test_an_id_kept_across_versions_with_the_same_source_passes():
    prior = [{"id": "AC-1", "source": "the same source text"}]
    current = [{"id": "AC-1", "source": "the same source text"}]
    assert clarification._check_id_continuity(current, prior) == []


def test_must_reject_an_id_reused_for_a_different_criterion():
    prior = [{"id": "AC-1", "source": "original source text"}]
    current = [{"id": "AC-1", "source": "an entirely different criterion"}]
    reasons = clarification._check_id_continuity(current, prior)
    assert any("reused" in r for r in reasons)


def test_must_reject_a_gap_in_a_freshly_assigned_id():
    prior = [{"id": "AC-1", "source": "first"}]
    current = [{"id": "AC-1", "source": "first"}, {"id": "AC-3", "source": "third, skipping AC-2"}]
    reasons = clarification._check_id_continuity(current, prior)
    assert any("AC-3" in r for r in reasons)


def test_must_reject_a_source_reassigned_to_a_new_id_instead_of_keeping_its_own():
    prior = [{"id": "AC-1", "source": "kept text"}]
    current = [{"id": "AC-1", "source": "kept text"}, {"id": "AC-2", "source": "kept text"}]
    reasons = clarification._check_id_continuity(current, prior)
    assert any("must keep id AC-1" in r for r in reasons)


def test_must_reject_a_malformed_id():
    reasons = clarification._check_id_continuity([{"id": "criterion-1", "source": "s"}], [])
    assert any("malformed id" in r for r in reasons)


# --- EARS form and example concreteness, forced-category shape ---


def test_the_concrete_ears_form_fixture_passes_the_structure_check():
    text = (RUBRIC_FIXTURES_DIR / "ears_form" / "concrete.md").read_text()
    findings = artefact_structure.check("criteria", text)
    assert findings == []


def test_must_reject_the_not_concrete_ears_form_fixture():
    """A blank EARS field and a placeholder-laden example both fail structurally."""
    text = (RUBRIC_FIXTURES_DIR / "ears_form" / "not_concrete.md").read_text()
    findings = artefact_structure.check("criteria", text)
    rules = {f.rule for f in findings}
    assert "incomplete_ears_form" in rules
    assert "example_not_concrete" in rules


def test_must_reject_a_forced_category_left_silent():
    text = (RUBRIC_FIXTURES_DIR / "ears_form" / "concrete.md").read_text().replace(
        "| data retention | not applicable because no new data is stored | n/a |\n", ""
    )
    findings = artefact_structure.check("criteria", text)
    assert any(f.rule == "missing_forced_category" and f.detail == "data retention" for f in findings)


def test_must_reject_a_forced_category_resolved_outside_the_three_literal_forms():
    text = (RUBRIC_FIXTURES_DIR / "ears_form" / "concrete.md").read_text().replace(
        "not applicable because no new data is stored", "handled elsewhere"
    )
    findings = artefact_structure.check("criteria", text)
    assert any(f.rule == "bad_category_resolution" for f in findings)


def test_an_ac_id_outside_the_ac_n_shape_fails_structurally():
    text = (RUBRIC_FIXTURES_DIR / "ears_form" / "concrete.md").read_text().replace("AC-1", "criterion-1")
    findings = artefact_structure.check("criteria", text)
    assert any(f.rule == "bad_ac_id" for f in findings)


# --- forced-category pre-fill from the ticket's own intake exclusion record ---


def test_a_category_the_tickets_own_intake_exclusion_record_already_closed_is_prefilled(tmp_path):
    conn = _conn(tmp_path)
    ticket_id = record.insert(conn, "ticket", state="clarifying", opened_at=record.now())
    intake_run_id = run_ledger.open_stage_run(conn, ticket_id=ticket_id, stage="intake")
    check_id = record.insert(
        conn, "check_result", stage_run_id=intake_run_id, check_name="exclusion", result="fail",
        summary="ticket touches migration surfaces",
    )

    closed = clarification._intake_closed_categories(conn, ticket_id)
    assert closed == {"migration": check_id}

    rows = [
        {"category": "migration", "resolution": "open", "reference": ""},
        {"category": "permissions", "resolution": "open", "reference": ""},
    ]
    prefilled = clarification._prefill_forced_categories(rows, closed)
    migration_row = next(r for r in prefilled if r["category"] == "migration")
    permissions_row = next(r for r in prefilled if r["category"] == "permissions")
    assert migration_row["resolution"].startswith("not applicable because")
    assert migration_row["reference"] == f"check_result:{check_id}"
    # `permissions` was never closed by the seeded record: it is not
    # re-evaluated by this function, but it is also not touched.
    assert permissions_row["resolution"] == "open"


def test_a_category_with_no_intake_record_is_never_prefilled(tmp_path):
    conn = _conn(tmp_path)
    ticket_id = record.insert(conn, "ticket", state="clarifying", opened_at=record.now())
    assert clarification._intake_closed_categories(conn, ticket_id) == {}


# --- an open category becomes a ranked question ---


def test_an_open_category_yields_exactly_one_candidate_naming_it():
    rows = [
        {"category": "rollback", "resolution": "open", "reference": ""},
        {"category": "observability", "resolution": "covered by criterion AC-1", "reference": "AC-1"},
    ]
    candidates = clarification._open_category_candidates(rows)
    assert len(candidates) == 1
    assert "rollback" in candidates[0]["text"]
    assert candidates[0]["blocking"] is True


# --- the split rule ---


def test_split_required_when_lines_exceed_the_tiers_threshold():
    tiers_config = {"split_threshold": {"share_of_size_gate": 0.6, "max_files": 10}, "size_gate": {"standard": 300}}
    assert clarification._split_required({"estimated_lines": "250", "estimated_files": "1"}, tier="standard", tiers_config=tiers_config)


def test_split_not_required_under_both_thresholds():
    tiers_config = {"split_threshold": {"share_of_size_gate": 0.6, "max_files": 10}, "size_gate": {"standard": 300}}
    assert not clarification._split_required({"estimated_lines": "100", "estimated_files": "3"}, tier="standard", tiers_config=tiers_config)


def test_split_required_when_files_exceed_the_max_files_threshold():
    tiers_config = {"split_threshold": {"share_of_size_gate": 0.6, "max_files": 10}, "size_gate": {"standard": 300}}
    assert clarification._split_required({"estimated_lines": "10", "estimated_files": "11"}, tier="standard", tiers_config=tiers_config)


def test_a_candidate_naming_a_split_pattern_is_recognised():
    candidate = {"consequential": True, "text": "Should the first slice cover only business-rule variations?", "reasoning": "", "affects": ""}
    assert clarification._names_a_split_pattern(candidate)


def test_a_non_consequential_candidate_naming_a_split_pattern_does_not_count():
    """Only a consequential candidate counts: the split decision changes the plan's own shape."""
    candidate = {"consequential": False, "text": "business-rule variations", "reasoning": "", "affects": ""}
    assert not clarification._names_a_split_pattern(candidate)


def test_a_candidate_naming_no_split_pattern_does_not_count():
    candidate = {"consequential": True, "text": "Should we ship this faster?", "reasoning": "", "affects": ""}
    assert not clarification._names_a_split_pattern(candidate)


# --- rubric grader lines ---


def test_the_rubric_marks_criterion_restatements_grader_half_as_a_bootstrap_checklist_line():
    lines = rubrics.load(RUBRIC_PATH)
    grader = rubrics.line(lines, "criterion_restatement", "grader")
    assert grader is not None
    assert grader.checklist is True
    assert grader.judgment == "fail when a restated `AC-n` criterion changes the meaning of its source acceptance criterion"


def test_the_rubric_marks_given_when_then_examples_grader_half_as_a_bootstrap_checklist_line():
    lines = rubrics.load(RUBRIC_PATH)
    grader = rubrics.line(lines, "given_when_then_example", "grader")
    assert grader is not None
    assert grader.checklist is True
    assert grader.judgment == "fail when a Given/When/Then example states no real values, only generic placeholders"


def test_the_rubric_marks_vertical_slice_sizes_grader_half_as_a_bootstrap_checklist_line():
    lines = rubrics.load(RUBRIC_PATH)
    grader = rubrics.line(lines, "vertical_slice_size", "grader")
    assert grader is not None
    assert grader.checklist is True
    assert grader.judgment == "fail when criteria describe no single vertical slice with observable value"


def test_the_rubric_carries_a_script_line_for_every_new_row():
    lines = rubrics.load(RUBRIC_PATH)
    for row in ("criterion_restatement", "given_when_then_example", "agreement_check", "forced_categories", "vertical_slice_size", "pass_completeness"):
        assert rubrics.line(lines, row, "script") is not None, row


def test_the_seeded_human_verdict_fixtures_name_their_rubric_line_and_the_stated_verdict():
    cases = [
        ("criterion_restatement_grader_pass", "criterion_restatement:grader", "pass"),
        ("criterion_restatement_grader_fail", "criterion_restatement:grader", "fail"),
        ("given_when_then_example_grader_pass", "given_when_then_example:grader", "pass"),
        ("given_when_then_example_grader_fail", "given_when_then_example:grader", "fail"),
        ("vertical_slice_size_grader_pass", "vertical_slice_size:grader", "pass"),
        ("vertical_slice_size_grader_fail", "vertical_slice_size:grader", "fail"),
    ]
    for directory, line_id, verdict in cases:
        fixture = yaml.safe_load((RUBRIC_FIXTURES_DIR / directory / "human_verdict.yaml").read_text())
        assert fixture["rubric_line_id"] == line_id
        assert fixture["verdict"] == verdict


# --- the full walk: happy path and id continuity across two versions ---


def test_a_clean_criteria_version_passes_with_no_questions_raised(tmp_path, monkeypatch):
    conn = _conn(tmp_path)
    ticket_id = _clarifying_ticket(conn, tmp_path)
    monkeypatch.setenv("FIXTURE_ADAPTER_OUT_DIR", str(AGENT_FIXTURES_DIR / "criteria_clean" / "out"))

    outcome = run_stage(conn, ticket_id, "clarification", runs_dir=tmp_path)

    assert outcome == "pass"
    assert record.get(conn, "ticket", ticket_id)["state"] == "planning"
    criteria = artefact_registry.latest(conn, ticket_id, "criteria")
    assert criteria is not None


def test_must_reject_a_reused_id_naming_a_different_criterion_against_a_seeded_prior_version(tmp_path, monkeypatch):
    """must-reject: a second version that reuses AC-1 for a different criterion fails structurally
    before any restatement child is ever spawned."""
    conn = _conn(tmp_path)
    ticket_id = _clarifying_ticket(conn, tmp_path)
    prior_path = tmp_path / "prior_criteria.md"
    prior_path.write_text(
        "## Acceptance criteria\n\n"
        "| id | source | precondition | trigger | system | response | example | state |\n"
        "|---|---|---|---|---|---|---|---|\n"
        "| AC-1 | An original criterion. | p | t | s | r | Given p, when t, then r | formalised |\n\n"
        "## Forced categories\n\n## Agreement check\n\n## Size estimate\n\n## Completeness verdict\n\ndone\n"
    )
    artefact_registry.register(conn, ticket_id=ticket_id, kind="criteria", path=prior_path)
    monkeypatch.setenv("FIXTURE_ADAPTER_OUT_DIR", str(AGENT_FIXTURES_DIR / "criteria_id_conflict" / "out"))

    outcome = run_stage(conn, ticket_id, "clarification", runs_dir=tmp_path)

    assert outcome == "fail"
    assert record.get(conn, "ticket", ticket_id)["state"] == "clarifying"


# --- the agreement check: ambiguous, contradictory, and uncovered findings ---


def test_a_seeded_ambiguous_criterion_raises_a_non_blocking_question_and_is_marked_provisional(tmp_path, monkeypatch):
    conn = _conn(tmp_path)
    ticket_id = _clarifying_ticket(conn, tmp_path, source_text="The retry handler must back off before a second attempt.")
    monkeypatch.setenv("FIXTURE_ADAPTER_OUT_DIR", str(AGENT_FIXTURES_DIR / "criteria_ambiguous" / "out"))

    outcome = run_stage(conn, ticket_id, "clarification", runs_dir=tmp_path)

    assert outcome == "pass"
    non_blocking = conn.execute(
        "SELECT id FROM question WHERE ticket_id = ? AND blocking = 0", (ticket_id,)
    ).fetchall()
    assert len(non_blocking) == 1

    criteria = artefact_registry.latest(conn, ticket_id, "criteria")
    parsed = artefacts.parse(Path(criteria["path"]).read_text())
    row = parsed.section("Acceptance criteria").table()[0]
    assert row["state"] == "provisional"
    agreement_row = parsed.section("Agreement check").table()[0]
    assert agreement_row["agreed"] == "no"


def test_a_seeded_contradictory_pair_raises_exactly_one_question(tmp_path, monkeypatch):
    conn = _conn(tmp_path)
    ticket_id = _clarifying_ticket(conn, tmp_path, source_text="The checkout flow's coupon handling.")
    monkeypatch.setenv("FIXTURE_ADAPTER_OUT_DIR", str(AGENT_FIXTURES_DIR / "criteria_contradiction" / "out"))

    outcome = run_stage(conn, ticket_id, "clarification", runs_dir=tmp_path)

    assert outcome == "pass"
    questions_raised = conn.execute("SELECT id, text FROM question WHERE ticket_id = ?", (ticket_id,)).fetchall()
    assert len(questions_raised) == 1
    assert "contradict" in questions_raised[0]["text"]


def test_a_seeded_uncovered_region_raises_a_question(tmp_path, monkeypatch):
    conn = _conn(tmp_path)
    ticket_id = _clarifying_ticket(conn, tmp_path, source_text="The refund handler's payment-method handling.")
    monkeypatch.setenv("FIXTURE_ADAPTER_OUT_DIR", str(AGENT_FIXTURES_DIR / "criteria_uncovered" / "out"))

    outcome = run_stage(conn, ticket_id, "clarification", runs_dir=tmp_path)

    assert outcome == "pass"
    questions_raised = conn.execute("SELECT id, text FROM question WHERE ticket_id = ?", (ticket_id,)).fetchall()
    assert len(questions_raised) == 1
    assert "No criterion covers" in questions_raised[0]["text"]


def test_each_criterions_agreement_check_spawns_exactly_n_sibling_child_runs(tmp_path, monkeypatch):
    """N (3, from limits.yaml) sibling `stage_run` rows under the attempt, on the
    manifest's restatement model, and excluded from `stage_reliability_view`'s first-attempt count."""
    conn = _conn(tmp_path)
    ticket_id = _clarifying_ticket(conn, tmp_path)
    monkeypatch.setenv("FIXTURE_ADAPTER_OUT_DIR", str(AGENT_FIXTURES_DIR / "criteria_clean" / "out"))

    run_stage(conn, ticket_id, "clarification", runs_dir=tmp_path)

    attempt = conn.execute(
        "SELECT id FROM stage_run WHERE ticket_id = ? AND stage = 'clarification' AND parent_run_id IS NULL", (ticket_id,)
    ).fetchone()
    children = conn.execute(
        "SELECT id, model_requested FROM stage_run WHERE parent_run_id = ? AND stage = 'clarification'", (attempt["id"],)
    ).fetchall()
    # One child is the main invocation, three are the restatement children
    # for the one formalised criterion `criteria_clean` carries; the
    # fixture manifest happens to name the same model for both, so the
    # restatement children are identified by their registered subject
    # input instead.
    assert len(children) == 4
    entry = manifest.resolve(manifest.load(), "clarification", "standard")
    assert all(c["model_requested"] == entry.restatement_model for c in children)
    subjects = conn.execute(
        "SELECT id FROM artefact WHERE ticket_id = ? AND kind = 'restatement_subject'", (ticket_id,)
    ).fetchall()
    assert len(subjects) == 3

    view_row = conn.execute(
        "SELECT eligible_count FROM stage_reliability_view WHERE stage = 'clarification'"
    ).fetchone()
    assert view_row["eligible_count"] == 1  # the attempt alone, never its restatement children


# --- an unformalisable criterion blocks the exit, then a resolved rerun passes ---


def test_an_unformalisable_criterion_raises_a_blocking_question_and_the_run_stays_blocked(tmp_path, monkeypatch):
    conn = _conn(tmp_path)
    ticket_id = _clarifying_ticket(
        conn, tmp_path, source_text="The system should feel trustworthy to the customer.",
    )
    monkeypatch.setenv("FIXTURE_ADAPTER_OUT_DIR", str(AGENT_FIXTURES_DIR / "criteria_unformalisable" / "out"))

    outcome = run_stage(conn, ticket_id, "clarification", runs_dir=tmp_path)

    assert outcome == "blocked"
    assert record.get(conn, "ticket", ticket_id)["state"] == "clarifying"
    blocking = questions.open_blocking(conn, ticket_id, stage="clarification")
    assert len(blocking) == 1
    # Every category was still resolved and registered, even though the
    # run ends blocked: nothing here was left undone.
    criteria = artefact_registry.latest(conn, ticket_id, "criteria")
    assert criteria is not None


def test_answering_the_unformalisable_criterions_question_lets_the_next_round_pass(tmp_path, monkeypatch):
    conn = _conn(tmp_path)
    ticket_id = _clarifying_ticket(
        conn, tmp_path, source_text="The system should feel trustworthy to the customer.",
    )
    monkeypatch.setenv("FIXTURE_ADAPTER_OUT_DIR", str(AGENT_FIXTURES_DIR / "criteria_unformalisable" / "out"))
    run_stage(conn, ticket_id, "clarification", runs_dir=tmp_path)
    blocking_id = questions.open_blocking(conn, ticket_id, stage="clarification")[0]
    questions.record_answer(conn, blocking_id, action="answer", actor=ABHISHEK, option=0)

    monkeypatch.setenv("FIXTURE_ADAPTER_OUT_DIR", str(AGENT_FIXTURES_DIR / "criteria_unformalisable_resolved" / "out"))
    outcome = run_stage(conn, ticket_id, "clarification", runs_dir=tmp_path)

    assert outcome == "pass"
    assert record.get(conn, "ticket", ticket_id)["state"] == "planning"


# --- an open forced category blocks the exit the same way ---


def test_an_open_forced_category_raises_a_blocking_question_and_the_run_stays_blocked(tmp_path, monkeypatch):
    conn = _conn(tmp_path)
    ticket_id = _clarifying_ticket(
        conn, tmp_path, source_text="The archive job must move records older than one year to cold storage.",
    )
    monkeypatch.setenv("FIXTURE_ADAPTER_OUT_DIR", str(AGENT_FIXTURES_DIR / "criteria_open_category" / "out"))

    outcome = run_stage(conn, ticket_id, "clarification", runs_dir=tmp_path)

    assert outcome == "blocked"
    blocking_questions = conn.execute(
        "SELECT text FROM question WHERE ticket_id = ? AND blocking = 1", (ticket_id,)
    ).fetchall()
    assert len(blocking_questions) == 1
    assert "rollback" in blocking_questions[0]["text"]


# --- the split rule over a real run ---


def test_must_reject_a_run_whose_size_estimate_exceeds_the_threshold_with_no_split_question(tmp_path, monkeypatch):
    conn = _conn(tmp_path)
    ticket_id = _clarifying_ticket(
        conn, tmp_path, source_text="The reporting module must generate a monthly summary across every account type.",
    )
    monkeypatch.setenv("FIXTURE_ADAPTER_OUT_DIR", str(AGENT_FIXTURES_DIR / "criteria_split_missing" / "out"))

    outcome = run_stage(conn, ticket_id, "clarification", runs_dir=tmp_path)

    assert outcome == "fail"
    check = conn.execute(
        "SELECT * FROM check_result WHERE check_name = 'criteria_structure' AND result = 'fail' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert "split" in check["summary"]


def test_a_consequential_split_question_naming_a_pattern_lets_the_run_pass(tmp_path, monkeypatch):
    conn = _conn(tmp_path)
    ticket_id = _clarifying_ticket(
        conn, tmp_path, source_text="The reporting module must generate a monthly summary across every account type.",
    )
    monkeypatch.setenv("FIXTURE_ADAPTER_OUT_DIR", str(AGENT_FIXTURES_DIR / "criteria_split_present" / "out"))

    outcome = run_stage(conn, ticket_id, "clarification", runs_dir=tmp_path)

    assert outcome == "pass"
    questions_raised = conn.execute("SELECT text, reasoning FROM question WHERE ticket_id = ?", (ticket_id,)).fetchall()
    assert len(questions_raised) == 1
    assert "business-rule variations" in questions_raised[0]["reasoning"]


# --- planning approval refused while a question is open; a later contradicting answer invalidates the
# plan and its dependents ---


def test_plan_review_gate_withholds_its_event_while_a_blocking_question_is_open(tmp_path):
    conn = _conn(tmp_path)
    ticket_id = record.insert(conn, "ticket", state="plan_review", opened_at=record.now())
    plan_tuple_id = record.insert(
        conn, "evidence_tuple", kind="plan", ticket_id=ticket_id, content_hash="plan-subject-1",
    )
    record.insert(
        conn, "approval_record", ticket_id=ticket_id, gate="plan", subject_hash="plan-subject-1",
        evidence_tuple_id=plan_tuple_id, decision="approve",
    )
    questions.raise_round(
        conn, ticket_id=ticket_id, stage="clarification",
        candidates=[{
            "text": "Should this stay blocking for the gate test?", "reasoning": "seeded for the test",
            "affects": "the gate's own withholding behavior",
            "options": [
                {"text": "yes", "consequence": "It stays blocking."},
                {"text": "no", "consequence": "It stops blocking."},
                {"text": "none of these", "consequence": "If nobody answers, it stays blocking."},
            ],
            "default_option": None, "consequential": True, "consequential_reason": "blocks the gate",
            "hard_to_reverse": True, "hard_to_reverse_reason": "affects downstream approval",
            "blocking": True, "sensitive": False,
            "rank_inputs": {"impact": 1.0, "uncertainty": 1.0}, "raised_by_answer": None,
        }],
        tier="standard",
    )

    assert gates.plan_review_gate(conn, record.get(conn, "ticket", ticket_id)) is None


def test_superseding_an_accepted_assumption_invalidates_the_recorded_plan(tmp_path):
    """A later answer contradicting an accepted assumption invalidates the plan
    artefact that recorded the old assumption-log hash, via `dependents_invalidated`."""
    conn = _conn(tmp_path)
    ticket_id = record.insert(conn, "ticket", state="clarifying", opened_at=record.now())
    ids = questions.raise_round(
        conn, ticket_id=ticket_id, stage="clarification",
        candidates=[{
            "text": "Should the default hold?", "reasoning": "seeded for the test",
            "affects": "an internal default with no other implications",
            "options": [
                {"text": "yes", "consequence": "The default holds."},
                {"text": "no", "consequence": "The default changes."},
                {"text": "none of these", "consequence": "If nobody answers, the default holds."},
            ],
            "default_option": 2, "consequential": False, "consequential_reason": "internal only",
            "hard_to_reverse": False, "hard_to_reverse_reason": "can change again later",
            "blocking": False, "sensitive": False,
            "rank_inputs": {"impact": 0.3, "uncertainty": 0.3}, "raised_by_answer": None,
        }],
        tier="standard",
    )
    assumption_id = questions.accept_assumption(conn, ids[0], actor=ABHISHEK, text="Assume the default holds.")
    old_hash = questions.assumption_log_hash(conn, ticket_id)

    plan_path = tmp_path / "plan.md"
    plan_path.write_text(f"---\nassumption_log_hash: {old_hash}\n---\n## Intent and scrutiny\n\ntext\n")
    plan_artefact_id = artefact_registry.register(conn, ticket_id=ticket_id, kind="plan", path=plan_path)

    questions.supersede_assumption(
        conn, assumption_id, text="Assume the default no longer holds.", reason="a later answer contradicted it",
        actor=ABHISHEK,
    )

    stale = questions.dependents_invalidated(conn, ticket_id)
    assert ("artefact", plan_artefact_id) in {(s["type"], s["id"]) for s in stale}

