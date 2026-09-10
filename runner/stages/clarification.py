"""The clarification driver: the question/assumption half and the criteria half, sharing one agent invocation.

The agent's one invocation writes both `out/questions.yaml` (this round's
open questions) and `out/criteria.md` (the restated acceptance criteria,
forced categories, agreement check, size estimate and completeness
verdict). This driver: (1) reads `criteria.md` and enforces `AC-n` id
continuity against the ticket's previous criteria version; (2) pre-fills
any forced category the ticket's intake exclusion record already closed; (3)
runs the agreement check -- `N` fresh restatement children per formalised
or provisional criterion, each a sibling `stage_run` under this attempt --
and downgrades a criterion to `provisional` wherever the restatements
disagreed or the agent's own notes flagged a contradiction; (4) requires a
consequential split question, naming one of the split patterns, whenever
the size estimate exceeds the tier's threshold; (5) combines the agent's
own question candidates with the ones this driver derived (an
unformalisable criterion, an ambiguous or contradicted criterion, an
uncovered region, an open category) and raises them as one round; (6)
rewrites and registers the checked criteria version; (7) exits `blocked`
while any blocking question is open, `pass` otherwise -- which is exactly
how every criterion ends up formalised (or its question answered) and
every category resolved before a `pass` exit, since this driver makes the
one question type that would leave either unresolved always blocking.
"""
import re
import sqlite3
from pathlib import Path

import yaml

from runner import artefact_registry, artefacts, canonical, manifest, questions, record
from runner.fs import write_text
from runner.paths import FACTORY_DIR, RUNS_DIR

ARTEFACT_KIND = "question_set"
CRITERIA_ARTEFACT_KIND = "criteria"
PASS_EVENT = "clarification_pass"

TIERS_PATH = FACTORY_DIR / "config" / "tiers.yaml"
LIMITS_PATH = FACTORY_DIR / "config" / "limits.yaml"

_INVOCATION_OUTCOMES_PASSED_THROUGH = frozenset({"aborted_budget", "infrastructure_failure", "sandbox_violation"})

_AC_ID_RE = re.compile(r"^AC-(\d+)$")

# Stands in for a section the agent's output omitted entirely, so every
# early table read goes through the same `.table() or []` shape whether
# the section is present-but-empty or missing outright.
_EMPTY_SECTION = artefacts.Section(title="", body="")

# The six split patterns a split proposal may name; a split candidate must
# name one of them (in its own text, reasoning, or affects) to count as a
# real split proposal rather than an ordinary consequential question.
SPLIT_PATTERNS: tuple[str, ...] = (
    "workflow steps", "business-rule variations", "data variations", "interface variations",
    "defer performance", "simple then complex",
)

# The two forced categories the Initial pilot's own eligibility matrix
# already closes for any ticket that reaches clarification at all: a ticket that
# touched either surface never left `intake`. The check_result naming
# them is read defensively -- nothing in intake writes one on a passing run
# today -- so the pre-fill only fires when a caller (or a future intake
# enhancement) actually records one.
_INTAKE_CLOSED_CATEGORIES: tuple[str, ...] = ("migration", "permissions")


def _artefact_id(conn: sqlite3.Connection, ticket_id: int, kind: str) -> int | None:
    row = artefact_registry.latest(conn, ticket_id, kind)
    return row["id"] if row is not None else None


def _run_dir(runs_dir: Path, ticket_id: int, stage_run_id: int) -> Path:
    return runs_dir / "tickets" / str(ticket_id) / "runs" / str(stage_run_id)


def _out_dir(runs_dir: Path, ticket_id: int, child_stage_run_id: int) -> Path:
    return runs_dir / "tickets" / str(ticket_id) / "runs" / str(child_stage_run_id) / "out"


def _load_candidates(out_dir: Path) -> list[dict]:
    """The agent's `questions.yaml` candidates, or `[]` when the child wrote none: absence means no more questions."""
    path = out_dir / "questions.yaml"
    if not path.is_file():
        return []
    return yaml.safe_load(path.read_text()) or []


def _record_check(conn: sqlite3.Connection, stage_run_id: int, *, check_name: str, passed: bool, detail: str) -> None:
    row = {
        "stage_run_id": stage_run_id, "check_name": check_name, "check_tier": "blocking", "source": "runner",
        "result": "pass" if passed else "fail", "summary": detail,
        "canonical_serialization_version": canonical.SERIALIZATION_VERSION,
    }
    row["content_hash"] = canonical.content_hash(row)
    record.insert(conn, "check_result", **row)


def _tiers_config() -> dict:
    return yaml.safe_load(Path(TIERS_PATH).read_text())


def _limits_config() -> dict:
    return yaml.safe_load(Path(LIMITS_PATH).read_text())


# --- AC-n id continuity across versions ---


def _check_id_continuity(rows: list[dict], prior_rows: list[dict]) -> list[str]:
    """Every reason this version's `id` assignment breaks continuity with `prior_rows`; `[]` means it holds.

    An id already used in `prior_rows` must name the same `source` text it
    named before (kept, not reassigned); a `source` text that already
    appeared in `prior_rows` must keep that row's id (never given a fresh
    one); every other id is a genuinely new criterion and must be the
    next unused number in restatement order -- assigned in table-row
    order, starting right after the prior version's highest id -- so a
    fresh id never skips or reuses a number.
    """
    reasons: list[str] = []
    prior_by_id = {row["id"]: row for row in prior_rows}
    prior_id_by_source = {row["source"]: row["id"] for row in prior_rows}
    prior_max = max((int(_AC_ID_RE.match(row["id"]).group(1)) for row in prior_rows if _AC_ID_RE.match(row["id"])), default=0)

    seen: set[str] = set()
    next_new_id = prior_max + 1
    for row in rows:
        ac_id, source = row.get("id") or "", row.get("source")
        match = _AC_ID_RE.match(ac_id)
        if not match:
            reasons.append(f"malformed id: {ac_id!r}")
            continue
        if ac_id in seen:
            reasons.append(f"id {ac_id} used twice in this version")
            continue
        seen.add(ac_id)
        if ac_id in prior_by_id:
            if prior_by_id[ac_id]["source"] != source:
                reasons.append(f"id {ac_id} was reused for a different criterion")
        else:
            number = int(match.group(1))
            if number != next_new_id:
                reasons.append(f"id {ac_id} is a new criterion but the next unused id is AC-{next_new_id}")
            next_new_id = max(next_new_id, number) + 1
        if source in prior_id_by_source and prior_id_by_source[source] != ac_id:
            reasons.append(f"criterion with source {source!r} must keep id {prior_id_by_source[source]}, not {ac_id}")
    return reasons


def _prior_ac_rows(conn: sqlite3.Connection, ticket_id: int) -> list[dict]:
    prior = artefact_registry.latest(conn, ticket_id, CRITERIA_ARTEFACT_KIND)
    if prior is None:
        return []
    section = artefacts.parse(Path(prior["path"]).read_text()).section("Acceptance criteria")
    return section.table() if section is not None else []


# --- forced-category pre-fill ---


def _intake_closed_categories(conn: sqlite3.Connection, ticket_id: int) -> dict[str, int]:
    """`{category: check_result id}` for every forced category the ticket's own intake exclusion record already closed."""
    rows = conn.execute(
        "SELECT check_result.id AS id, check_result.summary AS summary FROM check_result "
        "JOIN stage_run ON stage_run.id = check_result.stage_run_id "
        "WHERE stage_run.ticket_id = ? AND stage_run.stage = 'intake' AND check_result.check_name = 'exclusion'",
        (ticket_id,),
    ).fetchall()
    closed: dict[str, int] = {}
    for row in rows:
        summary = (row["summary"] or "").lower()
        for category in _INTAKE_CLOSED_CATEGORIES:
            if category.rstrip("s") in summary and category not in closed:
                closed[category] = row["id"]
    return closed


def _prefill_forced_categories(rows: list[dict], closed: dict[str, int]) -> list[dict]:
    """`rows` with every intake-closed category's resolution and reference overwritten, never re-evaluated."""
    prefilled = []
    for row in rows:
        category = row.get("category")
        if category in closed:
            row = {
                **row,
                "resolution": f"not applicable because the pilot's own eligibility matrix already excludes {category}",
                "reference": f"check_result:{closed[category]}",
            }
        prefilled.append(row)
    return prefilled


def _open_category_candidates(rows: list[dict]) -> list[dict]:
    return [_category_open_candidate(row["category"]) for row in rows if (row.get("resolution") or "").strip().lower() == "open"]


# --- split rule ---


def _split_required(size_row: dict, *, tier: str, tiers_config: dict) -> bool:
    try:
        lines = int((size_row or {}).get("estimated_lines") or 0)
        files = int((size_row or {}).get("estimated_files") or 0)
    except ValueError:
        return False
    threshold = tiers_config["split_threshold"]
    lines_threshold = threshold["share_of_size_gate"] * tiers_config["size_gate"][tier]
    return lines > lines_threshold or files > threshold["max_files"]


def _names_a_split_pattern(candidate: dict) -> bool:
    haystack = " ".join(str(candidate.get(field, "")) for field in ("text", "reasoning", "affects")).lower()
    return bool(candidate.get("consequential")) and any(pattern in haystack for pattern in SPLIT_PATTERNS)


# --- question candidates the driver derives on the agent's behalf ---


def _unformalisable_candidate(ac_id: str, source: str) -> dict:
    return {
        "text": (
            f'The acceptance criterion described as "{source}" could not be restated formally. '
            "How should it be handled?"
        ),
        "reasoning": "Checked the ticket source and the linked sources; the wording could not be reduced to a testable statement.",
        "affects": f"criterion {ac_id}'s formal restatement",
        "options": [
            {"text": "Rewrite the source wording and restate it next round", "consequence": "It is restated once its wording is clarified."},
            {"text": "Drop it from scope", "consequence": "It is removed from scope and not implemented."},
            {"text": "none of these", "consequence": "If nobody answers, this run stays blocked until a human decides."},
        ],
        "default_option": None,
        "consequential": True,
        "consequential_reason": "an unresolved criterion blocks the plan from being written",
        "hard_to_reverse": True,
        "hard_to_reverse_reason": "dropping or reinterpreting it is not cheaply undone once downstream work proceeds",
        "blocking": True,
        "sensitive": False,
        "rank_inputs": {"impact": 1.0, "uncertainty": 1.0},
        "raised_by_answer": None,
    }


def _ambiguous_candidate(ac_id: str, source: str) -> dict:
    return {
        "text": (
            f'Restating the criterion described as "{source}" independently produced different readings. '
            "Which reading is correct?"
        ),
        "reasoning": "Compared independent restatements of the same source wording; they disagreed on its exact behavior.",
        "affects": f"criterion {ac_id}'s exact behavior",
        "options": [
            {"text": "The most literal reading of the source wording", "consequence": "The plan proceeds on the literal reading."},
            {"text": "A different reading, given below", "consequence": "The plan proceeds on the reading given in the response."},
            {"text": "none of these", "consequence": "If nobody answers, the plan proceeds on the most literal reading as a working default."},
        ],
        "default_option": 2,
        "consequential": False,
        "consequential_reason": "the reading affects this criterion's own behavior, not a declared contract",
        "hard_to_reverse": False,
        "hard_to_reverse_reason": "the reading can be corrected in a later round",
        "blocking": False,
        "sensitive": False,
        "rank_inputs": {"impact": 0.6, "uncertainty": 0.6},
        "raised_by_answer": None,
    }


def _contradiction_candidate(ac_id: str, other_id: str | None) -> dict:
    other = other_id or "another criterion"
    return {
        "text": f"Criterion {ac_id} appears to contradict {other} in what it requires. How should this be resolved?",
        "reasoning": "The restatement pass noted a direct contradiction between the two criteria's requirements.",
        "affects": f"criteria {ac_id} and {other}'s requirements",
        "options": [
            {"text": f"Keep {ac_id} and adjust {other}", "consequence": f"{other} is rewritten to remove the conflict."},
            {"text": f"Keep {other} and adjust {ac_id}", "consequence": f"{ac_id} is rewritten to remove the conflict."},
            {"text": "none of these", "consequence": "If nobody answers, both stay as written with the contradiction unresolved."},
        ],
        "default_option": 2,
        "consequential": False,
        "consequential_reason": "resolving the contradiction affects only these two criteria",
        "hard_to_reverse": False,
        "hard_to_reverse_reason": "either criterion can still be rewritten in a later round",
        "blocking": False,
        "sensitive": False,
        "rank_inputs": {"impact": 0.7, "uncertainty": 0.5},
        "raised_by_answer": None,
    }


def _uncovered_candidate(region: str) -> dict:
    named_region = region or "this part of the source wording"
    return {
        "text": f"No criterion covers {named_region}. Should it be included in scope?",
        "reasoning": "The restatement pass found no acceptance criterion whose source text addresses this region.",
        "affects": "the acceptance criteria's coverage of the ticket source",
        "options": [
            {"text": "Add a new criterion for it", "consequence": "A new criterion is added to cover it."},
            {"text": "Leave it out of scope", "consequence": "It stays out of this ticket's scope."},
            {"text": "none of these", "consequence": "If nobody answers, it stays out of scope for now."},
        ],
        "default_option": 2,
        "consequential": False,
        "consequential_reason": "leaving a region uncovered does not itself change a declared contract",
        "hard_to_reverse": False,
        "hard_to_reverse_reason": "a criterion can still be added for it in a later round",
        "blocking": False,
        "sensitive": False,
        "rank_inputs": {"impact": 0.6, "uncertainty": 0.6},
        "raised_by_answer": None,
    }


def _category_open_candidate(category: str) -> dict:
    return {
        "text": f'The "{category}" aspect of this work has not been resolved. How should it be handled?',
        "reasoning": f'The forced-category checklist left "{category}" open with no resolution.',
        "affects": f"the {category} aspect of this ticket's scope",
        "options": [
            {"text": "Resolve it as covered by an existing criterion", "consequence": "It is marked covered once a criterion is identified."},
            {"text": "Resolve it as not applicable", "consequence": "It is marked not applicable with a stated reason."},
            {"text": "none of these", "consequence": "If nobody answers, this run stays blocked until a human decides."},
        ],
        "default_option": None,
        "consequential": True,
        "consequential_reason": "an unresolved forced category blocks the plan from being written",
        "hard_to_reverse": True,
        "hard_to_reverse_reason": "a scope decision made here is not cheaply undone once the plan is written",
        "blocking": True,
        "sensitive": False,
        "rank_inputs": {"impact": 0.9, "uncertainty": 0.8},
        "raised_by_answer": None,
    }


# --- the agreement check: N restatement children per formalised/provisional criterion ---


def _read_restatement(path: Path) -> dict | None:
    if not path.is_file():
        return None
    lines = [line for line in path.read_text().splitlines() if line.lstrip().startswith("|")]
    try:
        rows = artefacts.parse_table(lines)
    except artefacts.ArtefactError:
        return None
    return rows[0] if rows else None


_AGREEMENT_FIELDS: tuple[str, ...] = ("precondition", "trigger", "response")


def _restatements_agree(restatements: list[dict | None]) -> bool:
    if not restatements or restatements[0] is None:
        return False
    first = restatements[0]
    return all(
        r is not None and all((r.get(f) or "").strip() == (first.get(f) or "").strip() for f in _AGREEMENT_FIELDS)
        for r in restatements
    )


_CONTRADICTS_RE = re.compile(r"contradicts\s+(AC-\d+)", re.IGNORECASE)


def _run_agreement_check(
    conn: sqlite3.Connection, ticket: sqlite3.Row, stage_run_id: int, runs_dir, run_dir: Path,
    ac_rows: list[dict], original_agreement: dict[str, dict], *, tier: str, restatement_model: str | None,
    ticket_source_id: int | None, brief_id: int | None, n: int,
) -> tuple[list[dict], list[dict], list[dict]] | tuple[str, str | None]:
    """`(updated_ac_rows, agreement_rows, candidates)`, or `(outcome, failure_kind)` when a child aborts the family.

    One formalised or provisional criterion at a time: write `n` subject
    files, invoke `n` restatement children, and compare what came back.
    Disagreement or a `contradicts AC-m` note the agent already left
    downgrades the row to `provisional` and raises a non-blocking
    question; an `aborted_budget`/`infrastructure_failure`/
    `sandbox_violation` child ends the whole attempt on the spot, the same
    way the main invocation would.
    """
    from runner import stages

    updated_rows: list[dict] = []
    agreement_rows: list[dict] = []
    candidates: list[dict] = []
    seen_pairs: set[frozenset] = set()

    for row in ac_rows:
        ac_id, state = row.get("id"), row.get("state")
        if state == "unformalisable":
            updated_rows.append(row)
            continue

        if ticket_source_id is None or brief_id is None:
            _record_check(
                conn, stage_run_id, check_name="agreement_check", passed=False,
                detail="ticket carries no ticket_source and/or brief artefact to restate criteria against",
            )
            return "fail", "infrastructure"

        restatements: list[dict | None] = []
        for k in range(1, n + 1):
            subject_path = run_dir / "restatement" / f"{ac_id}.{k}.md"
            write_text(
                subject_path,
                "Restate this acceptance criterion in EARS form as a one-row table with columns "
                "precondition, trigger, system, response; write it to out/restatement.md: "
                f"{row.get('source', '')}\n",
            )
            subject_id = artefact_registry.register(
                conn, ticket_id=ticket["id"], kind="restatement_subject", path=subject_path, stage_run_id=stage_run_id,
            )
            result = stages.invoke_agent(
                conn, ticket, "clarification", runs_dir=runs_dir, parent_run_id=stage_run_id,
                input_artefact_ids=[ticket_source_id, brief_id, subject_id], model_override=restatement_model,
            )
            if result.outcome in _INVOCATION_OUTCOMES_PASSED_THROUGH:
                return result.outcome, result.failure_kind
            if result.stage_run_id == -1:
                return "fail", "infrastructure"
            restatements.append(_read_restatement(_out_dir(runs_dir, ticket["id"], result.stage_run_id) / "restatement.md"))

        agreed = _restatements_agree(restatements)
        original = original_agreement.get(ac_id, {})
        original_note = (original.get("note") or "").strip()
        note_parts = [part for part in (original_note, "" if agreed else "disagreement across independent restatements") if part]
        agreement_rows.append({"id": ac_id, "samples": str(n), "agreed": "yes" if agreed else "no", "note": "; ".join(note_parts)})

        provisional = not agreed
        if not agreed:
            candidates.append(_ambiguous_candidate(ac_id, row.get("source", "")))
        contradicts = _CONTRADICTS_RE.search(original_note)
        if contradicts:
            provisional = True
            pair = frozenset({ac_id, contradicts.group(1)})
            if pair not in seen_pairs:
                seen_pairs.add(pair)
                candidates.append(_contradiction_candidate(ac_id, contradicts.group(1)))

        new_row = dict(row)
        if provisional and row.get("state") == "formalised":
            new_row["state"] = "provisional"
        updated_rows.append(new_row)

    known_ids = {row.get("id") for row in ac_rows}
    for original_id, original in original_agreement.items():
        if original_id in known_ids:
            continue
        note = original.get("note") or ""
        agreement_rows.append({"id": original_id, "samples": "0", "agreed": "", "note": note})
        if "uncovered" in note.lower():
            region = note.split(":", 1)[1].strip() if ":" in note else ""
            candidates.append(_uncovered_candidate(region))

    return updated_rows, agreement_rows, candidates


def _pending_allowed(conn: sqlite3.Connection, ticket_id: int, stage_run_id: int) -> bool:
    """True when the ticket's most recent prior clarification attempt (not this one) ended `blocked`."""
    prior = conn.execute(
        "SELECT outcome FROM stage_run WHERE ticket_id = ? AND stage = 'clarification' AND parent_run_id IS NULL AND id != ? "
        "ORDER BY id DESC LIMIT 1",
        (ticket_id, stage_run_id),
    ).fetchone()
    return prior is not None and prior["outcome"] == "blocked"


def run(conn: sqlite3.Connection, ticket: sqlite3.Row, stage_run_id: int, runs_dir: Path = RUNS_DIR):
    from runner import stages
    from runner.checks import artefact_structure

    ticket_id = ticket["id"]
    tier = ticket["tier_final"] or ticket["tier_provisional"] or "standard"
    run_dir = _run_dir(runs_dir, ticket_id, stage_run_id)

    result = stages.invoke_agent(conn, ticket, "clarification", runs_dir=runs_dir, parent_run_id=stage_run_id)
    if result.outcome in _INVOCATION_OUTCOMES_PASSED_THROUGH:
        return result.outcome, result.failure_kind
    if result.stage_run_id == -1:
        # No child run ever opened -- a manifest-pin refusal, since clarification
        # always names a real agent. `refused_request` is a `utility_run`
        # kind, not a `stage_run` outcome, so the attempt itself records
        # this the same way an unresolvable invocation always would.
        return "fail", "infrastructure"

    out_dir = _out_dir(runs_dir, ticket_id, result.stage_run_id)

    # --- the criteria half ---
    criteria_path = out_dir / "criteria.md"
    if not criteria_path.is_file():
        _record_check(conn, stage_run_id, check_name="criteria_structure", passed=False, detail="agent wrote no out/criteria.md")
        return "fail", "structural"
    try:
        parsed = artefacts.parse(criteria_path.read_text())
    except artefacts.ArtefactError as exc:
        _record_check(conn, stage_run_id, check_name="criteria_structure", passed=False, detail=str(exc))
        return "fail", "structural"

    try:
        ac_rows = (parsed.section("Acceptance criteria") or _EMPTY_SECTION).table() or []
        fc_rows_raw = (parsed.section("Forced categories") or _EMPTY_SECTION).table() or []
        size_rows = (parsed.section("Size estimate") or _EMPTY_SECTION).table() or []
        original_agreement = {row["id"]: row for row in (parsed.section("Agreement check") or _EMPTY_SECTION).table() or []}
    except artefacts.ArtefactError as exc:
        _record_check(conn, stage_run_id, check_name="criteria_structure", passed=False, detail=str(exc))
        return "fail", "structural"

    id_reasons = _check_id_continuity(ac_rows, _prior_ac_rows(conn, ticket_id))
    if id_reasons:
        _record_check(conn, stage_run_id, check_name="criteria_structure", passed=False, detail="; ".join(id_reasons))
        return "fail", "structural"

    fc_rows = _prefill_forced_categories(fc_rows_raw, _intake_closed_categories(conn, ticket_id))
    tiers_config = _tiers_config()
    entry = manifest.resolve(manifest.load(), "clarification", tier)

    agreement_result = _run_agreement_check(
        conn, ticket, stage_run_id, runs_dir, run_dir, ac_rows, original_agreement, tier=tier,
        restatement_model=entry.restatement_model,
        ticket_source_id=_artefact_id(conn, ticket_id, "ticket_source"),
        brief_id=_artefact_id(conn, ticket_id, "brief"),
        n=_limits_config()["agreement_check"]["n"],
    )
    if len(agreement_result) == 2:
        return agreement_result
    ac_rows, agreement_rows, agreement_candidates = agreement_result

    size_row = size_rows[0] if size_rows else {}

    agent_candidates = _load_candidates(out_dir)

    if _split_required(size_row, tier=tier, tiers_config=tiers_config) and not any(_names_a_split_pattern(c) for c in agent_candidates):
        _record_check(
            conn, stage_run_id, check_name="criteria_structure", passed=False,
            detail="the size estimate exceeds the tier's split threshold with no consequential split question naming a split pattern",
        )
        return "fail", "structural"

    unformalisable_candidates = [
        _unformalisable_candidate(row["id"], row.get("source", "")) for row in ac_rows if row.get("state") == "unformalisable"
    ]
    category_candidates = _open_category_candidates(fc_rows)

    combined = [*agent_candidates, *unformalisable_candidates, *agreement_candidates, *category_candidates]
    try:
        questions.raise_round(conn, ticket_id=ticket_id, stage="clarification", candidates=combined, tier=tier)
    except (questions.QuestionRejected, questions.RoundRefused) as exc:
        _record_check(conn, stage_run_id, check_name="question_gate", passed=False, detail=str(exc))
        return "fail", "structural"

    checked_sections = []
    for title in artefacts.SECTIONS["criteria"]:
        section = parsed.section(title)
        if title == "Acceptance criteria":
            body = artefacts.render_table(artefacts.CRITERIA_TABLES[title], ac_rows)
        elif title == "Forced categories":
            body = artefacts.render_table(artefacts.CRITERIA_TABLES[title], fc_rows)
        elif title == "Agreement check":
            body = artefacts.render_table(artefacts.CRITERIA_TABLES[title], agreement_rows)
        else:
            body = section.body if section is not None else ""
        checked_sections.append((title, body))

    front_matter = {"assumption_log_hash": questions.assumption_log_hash(conn, ticket_id)}
    checked_path = run_dir / "criteria.md"
    write_text(checked_path, artefacts.render(checked_sections, front_matter=front_matter))
    checked_text = checked_path.read_text()

    findings = artefact_structure.check(
        "criteria", checked_text, pending_allowed=_pending_allowed(conn, ticket_id, stage_run_id),
    )
    _record_check(
        conn, stage_run_id, check_name="criteria_structure", passed=not findings,
        detail="; ".join(f"{f.rule}: {f.detail}" for f in findings) if findings else "structurally sound",
    )
    if findings:
        return "fail", "structural"

    prior = artefact_registry.latest(conn, ticket_id, CRITERIA_ARTEFACT_KIND)
    artefact_registry.register(
        conn, ticket_id=ticket_id, kind=CRITERIA_ARTEFACT_KIND, path=checked_path, stage_run_id=stage_run_id,
        supersedes=prior["id"] if prior is not None else None,
    )

    # --- the question round's own artefact ---
    questions_path = out_dir / "questions.yaml"
    if questions_path.is_file():
        prior_qs = artefact_registry.latest(conn, ticket_id, ARTEFACT_KIND)
        artefact_registry.register(
            conn, ticket_id=ticket_id, kind=ARTEFACT_KIND, path=questions_path, stage_run_id=stage_run_id,
            supersedes=prior_qs["id"] if prior_qs is not None else None,
        )

    if questions.open_blocking(conn, ticket_id, stage="clarification"):
        return "blocked"
    return "pass"
