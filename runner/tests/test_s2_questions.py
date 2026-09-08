"""S2's question and assumption half: the pre-queue gate, ranking, rounds, flags, and the assumption log.

`_candidate` is a baseline valid `questions.yaml` item; every gate test
overrides only the field its own rule is about, so a failing assertion
names the one rule that actually changed rather than an incidental
difference between fixtures.
"""
import json

import pytest
import yaml

from runner import (
    artefact_registry, manifest, questions, record, queue, rubrics,
)
from runner.checks import question_gate
from runner.db import connect
from runner.paths import FACTORY_DIR
from runner.stages import run_stage

FIXTURES_DIR = FACTORY_DIR / "evals" / "agents" / "S2" / "fixtures"
RUBRIC_PATH = FACTORY_DIR / "rubrics" / "S2.md"

ABHISHEK = "abhishek"


@pytest.fixture
def conn(tmp_path):
    connection = connect(tmp_path / "factory.sqlite")
    yield connection
    connection.close()


def _ticket(conn, *, state: str = "clarifying", **fields) -> int:
    # `tickets.open_ticket` always opens in `intake`; every other state
    # here is seeded directly, the same way `test_stub_stages.py` does.
    return record.insert(conn, "ticket", state=state, opened_at=record.now(), **fields)


def _candidate(**overrides) -> dict:
    base = {
        "text": "Should feature flag Foo default to on?",
        "reasoning": (
            "Checked the rollout runbook and the on-call channel history; neither states a default."
        ),
        "affects": "the feature flag's default value",
        "options": [
            {"text": "on", "consequence": "New users see the feature immediately."},
            {"text": "off", "consequence": "New users see the feature only after an explicit opt-in."},
            {"text": "none of these", "consequence": "If nobody answers, the flag stays off, matching today's default."},
        ],
        "default_option": 2,
        "consequential": False,
        "consequential_reason": "the flag default is not a declared contract",
        "hard_to_reverse": False,
        "hard_to_reverse_reason": "the default can change again later",
        "blocking": False,
        "sensitive": False,
        "rank_inputs": {"impact": 0.5, "uncertainty": 0.4},
        "raised_by_answer": None,
    }
    base.update(overrides)
    return base


def test_gate_requires_reasoning_naming_sources_tried():
    assert any("reasoning" in reason for reason in question_gate.validate(_candidate(reasoning="")))


def test_must_reject_a_candidate_missing_affects():
    assert any("affects" in reason for reason in question_gate.validate(_candidate(affects="")))


def test_a_fully_valid_candidate_passes_the_gate():
    assert question_gate.validate(_candidate()) == []


def test_the_rubric_marks_r_s2_5s_grader_half_as_a_bootstrap_checklist_line():
    lines = rubrics.load(RUBRIC_PATH)
    grader = rubrics.line(lines, "R-S2-5", "grader")
    assert grader is not None
    assert grader.checklist is True
    assert grader.judgment == (
        "fail when a question's reasoning names a source that never mentions the fact the question asks about"
    )


def test_rank_inputs_are_stored_alongside_the_computed_rank(conn):
    ticket_id = _ticket(conn)
    ids = questions.raise_round(conn, ticket_id=ticket_id, stage="S2", candidates=[_candidate()], tier="standard")
    row = record.get(conn, "question", ids[0])
    assert row["rank"] == round(0.5 * 2 * 0.4 * 100)
    assert json.loads(row["rank_inputs"]) == {"impact": 0.5, "uncertainty": 0.4}


def test_a_question_with_no_default_still_gets_a_rank_and_rank_inputs(conn):
    ticket_id = _ticket(conn)
    candidate = _candidate(
        default_option=None, consequential=True, hard_to_reverse=True,
        consequential_reason="both flags apply", hard_to_reverse_reason="both flags apply",
    )
    ids = questions.raise_round(conn, ticket_id=ticket_id, stage="S2", candidates=[candidate], tier="standard")
    row = record.get(conn, "question", ids[0])
    assert row["default_option"] is None
    assert row["rank"] is not None
    assert json.loads(row["rank_inputs"]) == {"impact": 0.5, "uncertainty": 0.4}


@pytest.mark.parametrize(
    "consequential,hard_to_reverse,sensitive,default_option,ok",
    [
        (False, False, False, 2, True),   # neither flag: default required and given
        (False, False, False, None, False),  # neither flag: default missing
        (True, False, False, 2, True),    # one flag only: default still required
        (False, True, False, 2, True),    # one flag only: default still required
        (True, True, False, None, True),  # both flags: default must be null
        (True, True, False, 2, False),    # both flags: default given anyway
        (False, False, True, None, True),  # sensitive: default must be null
        (False, False, True, 2, False),   # sensitive: default given anyway
    ],
)
def test_default_option_requiredness_over_the_four_flag_combinations(consequential, hard_to_reverse, sensitive, default_option, ok):
    candidate = _candidate(
        consequential=consequential, hard_to_reverse=hard_to_reverse, sensitive=sensitive,
        default_option=default_option,
        affects="the outcome of an internal team preference with no other implications",
    )
    reasons = question_gate.validate(candidate)
    default_reasons = [r for r in reasons if "default_option" in r]
    assert (not default_reasons) == ok


def test_must_reject_a_candidate_with_only_one_option():
    candidate = _candidate(options=[{"text": "none of these", "consequence": "If nobody answers, nothing changes."}], default_option=0)
    assert any("options must number" in reason for reason in question_gate.validate(candidate))


def test_must_reject_a_candidate_with_five_options():
    options = [{"text": f"choice {i}", "consequence": "Something happens."} for i in range(4)]
    options.append({"text": "none of these", "consequence": "If nobody answers, nothing changes."})
    candidate = _candidate(options=options, default_option=4)
    assert any("options must number" in reason for reason in question_gate.validate(candidate))


def test_must_reject_a_candidate_whose_last_option_is_not_none_of_these():
    candidate = _candidate(options=[
        {"text": "on", "consequence": "Something happens."},
        {"text": "off", "consequence": "Something else happens."},
    ], default_option=0)
    assert any("none of these" in reason for reason in question_gate.validate(candidate))


def test_affects_naming_a_contract_forces_consequential_true(conn):
    ticket_id = _ticket(conn)
    candidate = _candidate(
        affects="a declared contract for the billing service", consequential=True,
        consequential_reason="changes a declared contract",
    )
    ids = questions.raise_round(conn, ticket_id=ticket_id, stage="S2", candidates=[candidate], tier="standard")
    assert record.get(conn, "question", ids[0])["consequential"] == 1


def test_must_reject_a_contract_affecting_candidate_with_consequential_false():
    candidate = _candidate(affects="a declared contract for the billing service", consequential=False)
    assert any("consequential" in reason for reason in question_gate.validate(candidate))


def test_affects_naming_customer_visible_state_forces_hard_to_reverse_true(conn):
    ticket_id = _ticket(conn)
    candidate = _candidate(
        affects="customer-visible state in the billing statement", hard_to_reverse=True,
        hard_to_reverse_reason="cannot cheaply restore customer-visible history",
    )
    ids = questions.raise_round(conn, ticket_id=ticket_id, stage="S2", candidates=[candidate], tier="standard")
    assert record.get(conn, "question", ids[0])["hard_to_reverse"] == 1


def test_must_reject_a_hard_to_reverse_affecting_candidate_with_the_flag_false():
    candidate = _candidate(affects="customer-visible state in the billing statement", hard_to_reverse=False)
    assert any("hard_to_reverse" in reason for reason in question_gate.validate(candidate))


def test_a_sensitive_decision_sets_consequential_true_regardless_of_hard_to_reverse(conn):
    ticket_id = _ticket(conn)
    candidate = _candidate(
        sensitive=True, consequential=False, hard_to_reverse=False, default_option=None,
        consequential_reason="handles authentication credentials",
    )
    ids = questions.raise_round(conn, ticket_id=ticket_id, stage="S2", candidates=[candidate], tier="standard")
    row = record.get(conn, "question", ids[0])
    assert row["consequential"] == 1
    assert row["consequential_reason"].startswith("sensitive decision:")


def test_correcting_a_flag_records_the_reason_as_a_tag(conn):
    ticket_id = _ticket(conn)
    ids = questions.raise_round(conn, ticket_id=ticket_id, stage="S2", candidates=[_candidate()], tier="standard")
    question_id = ids[0]

    questions.correct_flag(
        conn, question_id, consequential=True, reason="reclassified after a security review",
        actor=ABHISHEK, fm_id="FM-07",
    )

    assert record.get(conn, "question", question_id)["consequential"] == 1
    tag_row = conn.execute(
        "SELECT * FROM tag WHERE ref = ? AND event_kind = 'flag_correction'", (f"question:{question_id}",)
    ).fetchone()
    assert tag_row is not None
    assert tag_row["note"] == "reclassified after a security review"


def test_must_reject_correct_flag_with_neither_flag_named(conn):
    ticket_id = _ticket(conn)
    ids = questions.raise_round(conn, ticket_id=ticket_id, stage="S2", candidates=[_candidate()], tier="standard")
    with pytest.raises(ValueError):
        questions.correct_flag(conn, ids[0], reason="no flag named", actor=ABHISHEK, fm_id="FM-07")


def test_a_follow_up_question_names_its_raising_answer(conn):
    ticket_id = _ticket(conn)
    first_ids = questions.raise_round(
        conn, ticket_id=ticket_id, stage="S2", candidates=[_candidate(blocking=False)], tier="standard"
    )
    answer_id = questions.record_answer(conn, first_ids[0], action="answer", actor=ABHISHEK, option=0)

    follow_up = _candidate(raised_by_answer=answer_id)
    second_ids = questions.raise_round(conn, ticket_id=ticket_id, stage="S2", candidates=[follow_up], tier="standard")

    assert record.get(conn, "question", second_ids[0])["raised_by_answer"] == answer_id


def test_must_reject_a_raised_by_answer_that_names_no_real_answer(conn):
    ticket_id = _ticket(conn)
    candidate = _candidate(raised_by_answer=999999)
    with pytest.raises(questions.QuestionRejected):
        questions.raise_round(conn, ticket_id=ticket_id, stage="S2", candidates=[candidate], tier="standard")


def test_must_reject_a_new_round_while_the_previous_rounds_blocking_question_is_open(conn):
    ticket_id = _ticket(conn)
    questions.raise_round(conn, ticket_id=ticket_id, stage="S2", candidates=[_candidate(blocking=True)], tier="standard")

    with pytest.raises(questions.RoundRefused):
        questions.raise_round(conn, ticket_id=ticket_id, stage="S2", candidates=[_candidate()], tier="standard")


def test_round_is_read_from_the_record_and_increments_once_the_prior_blocker_is_resolved(conn):
    ticket_id = _ticket(conn)
    first_ids = questions.raise_round(
        conn, ticket_id=ticket_id, stage="S2", candidates=[_candidate(blocking=True)], tier="standard"
    )
    assert record.get(conn, "question", first_ids[0])["round"] == 1

    questions.record_answer(conn, first_ids[0], action="answer", actor=ABHISHEK, option=0)
    second_ids = questions.raise_round(conn, ticket_id=ticket_id, stage="S2", candidates=[_candidate()], tier="standard")
    assert record.get(conn, "question", second_ids[0])["round"] == 2


def test_an_empty_candidate_list_raises_no_round_and_touches_nothing(conn):
    ticket_id = _ticket(conn)
    assert questions.raise_round(conn, ticket_id=ticket_id, stage="S2", candidates=[], tier="standard") == []
    assert conn.execute("SELECT COUNT(*) FROM question").fetchone()[0] == 0


def test_a_default_accepted_answer_writes_an_assumption_row_naming_its_question(conn):
    ticket_id = _ticket(conn)
    ids = questions.raise_round(conn, ticket_id=ticket_id, stage="S2", candidates=[_candidate()], tier="standard")
    question_id = ids[0]

    questions.record_answer(conn, question_id, action="accept_default", actor=ABHISHEK)

    row = conn.execute("SELECT * FROM assumption WHERE ticket_id = ? AND origin = ?", (ticket_id, str(question_id))).fetchone()
    assert row is not None
    assert row["text"] == "If nobody answers, the flag stays off, matching today's default."


def test_answering_with_a_chosen_option_writes_no_assumption_row(conn):
    ticket_id = _ticket(conn)
    ids = questions.raise_round(conn, ticket_id=ticket_id, stage="S2", candidates=[_candidate()], tier="standard")
    questions.record_answer(conn, ids[0], action="answer", actor=ABHISHEK, option=0)
    assert conn.execute("SELECT COUNT(*) FROM assumption WHERE ticket_id = ?", (ticket_id,)).fetchone()[0] == 0


def test_an_s3_reviewer_accepting_an_assumption_sets_state_and_writes_the_row(conn):
    ticket_id = _ticket(conn)
    ids = questions.raise_round(
        conn, ticket_id=ticket_id, stage="S2", candidates=[_candidate(blocking=False)], tier="standard"
    )
    question_id = ids[0]

    assumption_id = questions.accept_assumption(
        conn, question_id, actor=ABHISHEK, text="Assume the flag stays off until told otherwise."
    )

    assert record.get(conn, "question", question_id)["state"] == "assumption_accepted"
    row = record.get(conn, "assumption", assumption_id)
    assert row["origin"] == str(question_id)
    assert row["text"] == "Assume the flag stays off until told otherwise."


def test_superseding_an_assumption_changes_the_log_hash_and_lists_every_stale_dependent(conn, tmp_path):
    ticket_id = _ticket(conn)
    ids = questions.raise_round(
        conn, ticket_id=ticket_id, stage="S2", candidates=[_candidate(blocking=False)], tier="standard"
    )
    assumption_id = questions.accept_assumption(conn, ids[0], actor=ABHISHEK, text="Assume defaults hold.")
    old_hash = questions.assumption_log_hash(conn, ticket_id)

    plan_path = tmp_path / "plan.md"
    plan_path.write_text(f"---\nassumption_log_hash: {old_hash}\n---\n## Intent and scrutiny\n\nSome text.\n")
    artefact_id = artefact_registry.register(conn, ticket_id=ticket_id, kind="plan", path=plan_path)

    evidence_tuple_id = record.insert(
        conn, "evidence_tuple", kind="plan", ticket_id=ticket_id, current_assumption_set_hash=old_hash,
        content_hash="subject-1",
    )
    approval_id = record.insert(
        conn, "approval_record", ticket_id=ticket_id, gate="plan", subject_hash="subject-1",
        evidence_tuple_id=evidence_tuple_id, decision="approve",
    )

    questions.supersede_assumption(
        conn, assumption_id, text="Assume defaults hold, revised.", reason="clarified with the team", actor=ABHISHEK,
    )
    new_hash = questions.assumption_log_hash(conn, ticket_id)

    assert new_hash != old_hash
    stale = questions.dependents_invalidated(conn, ticket_id)
    stale_ids = {(entry["type"], entry["id"]) for entry in stale}
    assert ("artefact", artefact_id) in stale_ids
    assert ("evidence_tuple", evidence_tuple_id) in stale_ids
    assert ("approval_record", approval_id) in stale_ids


def test_withdrawing_an_assumption_keeps_the_prior_row_and_records_the_reason(conn):
    ticket_id = _ticket(conn)
    ids = questions.raise_round(
        conn, ticket_id=ticket_id, stage="S2", candidates=[_candidate(blocking=False)], tier="standard"
    )
    assumption_id = questions.accept_assumption(conn, ids[0], actor=ABHISHEK, text="Assume defaults hold.")

    new_id = questions.supersede_assumption(
        conn, assumption_id, withdraw=True, reason="no longer applies", actor=ABHISHEK,
    )

    prior = record.get(conn, "assumption", assumption_id)
    new = record.get(conn, "assumption", new_id)
    assert prior["text"] == "Assume defaults hold."  # never touched
    assert new["supersedes"] == assumption_id
    assert new["withdrawn"] == 1
    assert new["withdrawal_reason"] == "no longer applies"


def test_must_reject_a_supersession_with_no_text_and_no_withdrawal(conn):
    ticket_id = _ticket(conn)
    ids = questions.raise_round(
        conn, ticket_id=ticket_id, stage="S2", candidates=[_candidate(blocking=False)], tier="standard"
    )
    assumption_id = questions.accept_assumption(conn, ids[0], actor=ABHISHEK, text="Assume defaults hold.")
    with pytest.raises(ValueError):
        questions.supersede_assumption(conn, assumption_id, reason="no text given", actor=ABHISHEK)


@pytest.mark.parametrize("text", [
    "Should we follow R-S2-9 exactly?",
    "Does this affect P3 at all?",
    "Is FM-07 still a concern here?",
    "Was D15 the final word?",
    "Should S4 own this instead?",
    "Should the criteria section change?",
    "Should we rerun manifest_hash first?",
    "Should the assumption table gain a column?",
])
def test_must_reject_question_text_naming_a_banned_identifier(text):
    candidate = _candidate(text=text)
    assert any("banned identifier" in reason for reason in question_gate.validate(candidate))


def test_an_allowed_name_is_not_treated_as_a_banned_identifier():
    """`Waiver` would otherwise match the `waiver` table name; naming it in `allowed_names` (the service's own
    code, per R-S2-14) lifts the ban for that exact name only."""
    candidate = _candidate(text="Should the Waiver class own this instead?")
    assert any("banned identifier" in reason for reason in question_gate.validate(candidate))

    reasons = question_gate.validate(candidate, allowed_names=frozenset({"Waiver"}))
    assert not any("banned identifier" in reason for reason in reasons)


def test_must_reject_a_default_option_whose_consequence_does_not_say_what_happens_if_unanswered():
    candidate = _candidate(options=[
        {"text": "on", "consequence": "New users see the feature immediately."},
        {"text": "off", "consequence": "New users do not see the feature."},
        {"text": "none of these", "consequence": "Nothing in particular."},
    ], default_option=2)
    assert any("consequence" in reason for reason in question_gate.validate(candidate))


def test_must_reject_an_option_with_no_consequence_at_all():
    candidate = _candidate(options=[
        {"text": "on", "consequence": ""},
        {"text": "off", "consequence": "New users do not see the feature."},
        {"text": "none of these", "consequence": "If nobody answers, nothing changes."},
    ], default_option=2)
    assert any("consequence" in reason for reason in question_gate.validate(candidate))


def test_the_rubric_marks_r_s2_14s_grader_half_as_a_bootstrap_checklist_line():
    lines = rubrics.load(RUBRIC_PATH)
    grader = rubrics.line(lines, "R-S2-14", "grader")
    assert grader is not None
    assert grader.checklist is True
    assert grader.judgment == (
        "fail when a reader with no access to the referenced artefact cannot give the right answer to the question"
    )


def _clarifying_ticket(conn) -> int:
    return _ticket(conn, tier_provisional="standard", factory_manifest_hash=manifest.current_hash())


def test_s2_walk_raises_ranks_and_answers_one_round_then_passes(conn, tmp_path, monkeypatch):
    """R-S2-6, R-S2-11: one round is raised and ranked, the blocking question is answered, the
    non-blocking one's default is accepted into the assumption log, and a second, empty-questions
    run then passes -- clarifying -> planning."""
    ticket_id = _clarifying_ticket(conn)

    monkeypatch.setenv("FIXTURE_ADAPTER_OUT_DIR", str(FIXTURES_DIR / "question_round" / "out"))
    outcome = run_stage(conn, ticket_id, "S2", runs_dir=tmp_path)

    assert outcome == "blocked"
    assert record.get(conn, "ticket", ticket_id)["state"] == "clarifying"

    open_items = conn.execute(
        "SELECT * FROM queue_item WHERE ticket_id = ? AND kind = 'question' AND resolved_at IS NULL ORDER BY id",
        (ticket_id,),
    ).fetchall()
    assert len(open_items) == 2

    blocking_item, non_blocking_item = None, None
    for item in open_items:
        question_id = int(item["ref"].split(":", 1)[1])
        question = record.get(conn, "question", question_id)
        if question["blocking"]:
            blocking_item = item
        else:
            non_blocking_item = item
    assert blocking_item is not None and non_blocking_item is not None

    queue.act(conn, item_id=blocking_item["id"], action="answer", actor=ABHISHEK, option=0)
    queue.act(conn, item_id=non_blocking_item["id"], action="accept_default", actor=ABHISHEK)

    non_blocking_question_id = int(non_blocking_item["ref"].split(":", 1)[1])
    assumption = conn.execute(
        "SELECT * FROM assumption WHERE ticket_id = ? AND origin = ?", (ticket_id, str(non_blocking_question_id))
    ).fetchone()
    assert assumption is not None
    assert record.get(conn, "ticket", ticket_id)["blocked_on"] is None

    monkeypatch.delenv("FIXTURE_ADAPTER_OUT_DIR", raising=False)
    second_outcome = run_stage(conn, ticket_id, "S2", runs_dir=tmp_path)

    assert second_outcome == "pass"
    assert record.get(conn, "ticket", ticket_id)["state"] == "planning"


def test_s2_driver_records_a_check_result_and_fails_over_a_rejected_candidate(conn, tmp_path, monkeypatch):
    ticket_id = _clarifying_ticket(conn)
    monkeypatch.setenv("FIXTURE_ADAPTER_OUT_DIR", str(FIXTURES_DIR / "gate_rejected" / "out"))

    outcome = run_stage(conn, ticket_id, "S2", runs_dir=tmp_path)

    assert outcome == "fail"
    assert record.get(conn, "ticket", ticket_id)["state"] == "clarifying"
    check = conn.execute(
        "SELECT * FROM check_result WHERE check_name = 'question_gate' AND result = 'fail' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert check is not None
    assert conn.execute("SELECT COUNT(*) FROM question WHERE ticket_id = ?", (ticket_id,)).fetchone()[0] == 0


def test_the_fixture_eval_yaml_names_a_readable_questions_yaml_for_each_new_case():
    spec = yaml.safe_load((FIXTURES_DIR.parent / "eval.yaml").read_text())
    names = {case["name"] for case in spec["cases"]}
    assert {"question_round", "gate_rejected"} <= names
    for case_name in ("question_round", "gate_rejected"):
        candidates = yaml.safe_load((FIXTURES_DIR / case_name / "out" / "questions.yaml").read_text())
        assert isinstance(candidates, list) and candidates
