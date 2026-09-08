"""Shared rendering for the `packet` and `pr_body` artefacts.

Both open with tuple identity and freshness, then one evidence table, then
the plan's own narrative sections, in the fixed charter order; they differ
only in whether the exact branch diff is appended, so `packet_assemble`
and `pr_body_assemble` both import this module and pass `include_diff`.
Every row and prose line here is copied straight out of `packet_inputs.json`
-- this module authors no adjectives, only the fixed vocabulary (`kind`,
and a handful of literal `status` values) the evidence table's row shape
requires and the input itself does not carry.

Standalone: no import of `runner`. Local pipe-table rendering duplicates
the small subset `runner.artefacts.render_table` needs elsewhere.
"""
import json
from pathlib import Path

REQUIRED_KEYS: tuple[str, ...] = (
    "ticket", "identity", "freshness", "artefacts", "checks", "fix_rounds", "base_test_changes", "readiness",
    "approvals", "waivers", "deviations", "assumptions", "blind_spots", "test_summary", "plan_sections", "diff_path",
)

EVIDENCE_COLUMNS: tuple[str, ...] = ("element", "kind", "source_artefact", "hash", "status", "detail")
DEVIATION_COLUMNS: tuple[str, ...] = ("plan_item", "plan_said", "agent_did", "why", "kind", "contract_change")
ASSUMPTION_COLUMNS: tuple[str, ...] = ("id", "text", "origin", "created_at")
CONTRACT_COLUMNS: tuple[str, ...] = (
    "unit", "kind", "source_declaration", "input", "output", "errors", "side_effects", "invariants",
    "authorization", "ordering_concurrency", "transaction_persistence", "compatibility",
)
BLIND_SPOT_COLUMNS: tuple[str, ...] = ("kind", "text", "source_artefact", "hash")

# Section order, PACKET minus `Diff` is PR_BODY -- kept in sync with
# `runner.artefacts.SECTIONS["packet"]`/`["pr_body"]` by hand, since a
# standalone script never imports the trusted control plane's own code.
PACKET_SECTIONS: tuple[str, ...] = (
    "Identity and freshness", "Evidence", "Intent", "Scrutiny", "Decisions", "Not touched", "Risk map",
    "Deviations", "Assumptions", "Test summary", "Blind spots", "Diff",
)
PR_BODY_SECTIONS: tuple[str, ...] = PACKET_SECTIONS[:-1]

# `checks` entries carrying an epistemic `kind` (an impact method, a
# contract/declaration check, or a behaviour-limitation check) may never
# render `pass` in the evidence table: evidence language never calls an
# observation a green result on its own say-so, whatever the input seeded.
_EPISTEMIC_CHECK_KINDS = frozenset({"impact", "declaration", "behaviour_limitation"})

_PR_BODY_DIFF_NOTE = (
    "Base-test diffs are part of this packet's `Diff` section and are omitted here; "
    "GitHub's own diff view is this pull request's diff surface."
)


class PacketInputError(ValueError):
    """`packet_inputs.json` is missing a required key or is not a JSON object."""


def load_inputs(path: Path) -> dict:
    try:
        raw = Path(path).read_text()
    except OSError as exc:
        raise PacketInputError(f"cannot read {path}: {exc}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise PacketInputError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise PacketInputError(f"{path} is not a JSON object")
    missing = [key for key in REQUIRED_KEYS if key not in data]
    if missing:
        raise PacketInputError(f"{path} is missing keys: {', '.join(missing)}")
    return data


def _cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value).replace("|", "\\|")


def render_table(columns: tuple[str, ...], rows: list[dict]) -> str:
    header = "| " + " | ".join(columns) + " |"
    separator = "|" + "|".join("---" for _ in columns) + "|"
    body = ["| " + " | ".join(_cell(row.get(column)) for column in columns) + " |" for row in rows]
    return "\n".join([header, separator, *body])


def _identity_section(data: dict) -> str:
    identity = data["identity"] or {}
    freshness = data["freshness"] or {}
    lines = [
        f"- review tuple: {identity.get('review_tuple_id')} ({identity.get('review_tuple_hash')})",
        f"- plan tuple: {identity.get('plan_tuple_id')} ({identity.get('plan_tuple_hash')})",
        f"- base: {identity.get('base_sha')}",
        f"- head: {identity.get('head_sha')}",
        f"- target base: {identity.get('target_base_sha')}",
        f"- manifest: {identity.get('manifest_hash')}",
        f"- diff: {identity.get('diff_hash')}",
        f"- deviation set: {identity.get('deviation_set_hash')}",
        f"- effective reviewer set: {identity.get('effective_reviewer_set_hash')}",
        f"- freshness: {'fresh' if freshness.get('fresh') else 'stale'} at {freshness.get('boundary')} "
        f"(target head {freshness.get('target_head_sha')}, checked {freshness.get('checked_at')})",
    ]
    reasons = freshness.get("reasons") or []
    if reasons:
        lines.append(f"- freshness reasons: {'; '.join(reasons)}")
    return "\n".join(lines)


def _check_rows(checks: list[dict]) -> list[dict]:
    rows = []
    for entry in checks:
        status = entry.get("status") or entry.get("result") or "blind_spot"
        if entry.get("kind") in _EPISTEMIC_CHECK_KINDS and status == "pass":
            status = "blind_spot"
        detail = f"{entry.get('evidence_artefact_hash')}: {entry.get('summary')}"
        if status == "waived" and entry.get("waiver_id"):
            detail += f"; waiver {entry['waiver_id']}"
        rows.append({
            "element": entry.get("check_name"), "kind": "check",
            "source_artefact": f"check_result:{entry.get('id')}", "hash": entry.get("content_hash"),
            "status": status, "detail": detail,
        })
    return rows


def _fix_round_rows(fix_rounds: list[dict]) -> list[dict]:
    rows = []
    for entry in fix_rounds:
        cleared = ", ".join(entry.get("recipes_cleared") or [])
        rows.append({
            "element": f"fix round {entry.get('stage_run_id')}", "kind": "fix_round",
            "source_artefact": f"stage_run:{entry.get('stage_run_id')}", "hash": "",
            "status": "pass", "detail": f"started {entry.get('started_at')}; cleared: {cleared}",
        })
    return rows


def _base_test_change_rows(entries: list[dict]) -> list[dict]:
    rows = []
    for entry in entries:
        rows.append({
            "element": entry.get("path"), "kind": "base_test_change",
            "source_artefact": f"deviation:{entry.get('deviation_id')}", "hash": entry.get("diff_hash"),
            "status": "pass", "detail": f"{entry.get('action')}: {entry.get('plan_item')}",
        })
    return rows


def _readiness_rows(rows: list[dict]) -> list[dict]:
    out = []
    for row in rows:
        detail = row.get("note") or ""
        if row.get("waiver_id"):
            detail = f"{detail}; waiver {row['waiver_id']}" if detail else f"waiver {row['waiver_id']}"
        out.append({
            "element": row.get("condition"), "kind": "readiness",
            "source_artefact": row.get("source_artefact"), "hash": row.get("hash"),
            "status": row.get("status"), "detail": detail,
        })
    return out


def _approval_rows(entries: list[dict]) -> list[dict]:
    rows = []
    for entry in entries:
        rows.append({
            "element": f"{entry.get('gate')} {entry.get('slot_id')}", "kind": "approval",
            "source_artefact": f"approval_record:{entry.get('id')}", "hash": entry.get("content_hash"),
            "status": entry.get("decision"),
            "detail": (
                f"{entry.get('actor_identity')} ({entry.get('role')}); decided {entry.get('decided_at')}; "
                f"expires {entry.get('expires_at')}"
            ),
        })
    return rows


def _waiver_rows(entries: list[dict]) -> list[dict]:
    rows = []
    for entry in entries:
        rows.append({
            "element": f"waiver {entry.get('id')}", "kind": "waiver",
            "source_artefact": f"waiver:{entry.get('id')}", "hash": entry.get("content_hash"),
            "status": "waived",
            "detail": (
                f"policy {entry.get('policy_id')}@{entry.get('policy_version')}; "
                f"scope: {entry.get('scope')}; expires: {entry.get('expires_at')}"
            ),
        })
    return rows


def _evidence_section(data: dict) -> str:
    rows = [
        *_check_rows(data.get("checks") or []),
        *_fix_round_rows(data.get("fix_rounds") or []),
        *_base_test_change_rows(data.get("base_test_changes") or []),
        *_readiness_rows(data.get("readiness") or []),
        *_approval_rows(data.get("approvals") or []),
        *_waiver_rows(data.get("waivers") or []),
    ]
    return render_table(EVIDENCE_COLUMNS, rows)


def _decisions_section(data: dict) -> str:
    ps = data.get("plan_sections") or {}
    checklist_rows = [
        {
            "rubric_line": entry.get("line"), "verdict": entry.get("verdict"),
            "evidence_ids": ", ".join(str(item) for item in (entry.get("evidence_ids") or [])),
        }
        for entry in (ps.get("checklist_verdicts") or [])
    ]
    parts = [
        "### Alternatives\n\n" + render_table(("alternative", "rejected_because"), ps.get("alternatives") or []),
        "### Contracts changed\n\n" + render_table(CONTRACT_COLUMNS, ps.get("contracts_changed") or []),
        "### Semantic checklist\n\n" + render_table(("rubric_line", "verdict", "evidence_ids"), checklist_rows),
    ]
    return "\n\n".join(parts)


def _not_touched_section(data: dict) -> str:
    ps = data.get("plan_sections") or {}
    lines = [f"- {line}" for line in (ps.get("non_goals") or [])]
    table = render_table(("path", "action", "reason"), ps.get("scope_rows") or [])
    return ("\n".join(lines) + "\n\n" + table) if lines else table


def _risk_map_section(data: dict) -> str:
    ps = data.get("plan_sections") or {}
    return render_table(("place", "why"), ps.get("risk_map") or [])


def _deviations_section(data: dict, *, include_diffs: bool) -> str:
    table = render_table(DEVIATION_COLUMNS, data.get("deviations") or [])
    if not include_diffs:
        return table + "\n\n" + _PR_BODY_DIFF_NOTE
    parts = [table, "### Base-test diffs"]
    for entry in data.get("base_test_changes") or []:
        parts.append(f"```diff\n{entry.get('diff', '')}\n```")
    return "\n\n".join(parts)


def _assumptions_section(data: dict) -> str:
    return render_table(ASSUMPTION_COLUMNS, data.get("assumptions") or [])


def _test_summary_rows(test_summary: dict) -> list[dict]:
    strategy_rows = test_summary.get("strategy_rows") or []
    diff_files = test_summary.get("diff_test_files") or []
    rows = []
    for path in diff_files:
        name = Path(path).name
        stem = Path(path).stem
        match = None
        for row in strategy_rows:
            cell = (row.get("test") or "").strip()
            if cell and (cell == path or cell == name or cell == stem or cell in path):
                match = row
                break
        if match is None:
            rows.append({"test": path, "criteria": "", "summary": "unplanned test, purpose not stated"})
            continue
        rows.append({"test": path, "criteria": match.get("criteria") or "", "summary": match.get("proves") or ""})
    return rows


def _test_summary_section(data: dict) -> str:
    rows = _test_summary_rows(data.get("test_summary") or {})
    return render_table(("test", "criteria", "summary"), rows)


def _blind_spots_section(data: dict) -> str:
    return render_table(BLIND_SPOT_COLUMNS, data.get("blind_spots") or [])


def _diff_section(data: dict) -> str:
    diff_path = data.get("diff_path")
    text = Path(diff_path).read_text() if diff_path else ""
    return f"```diff\n{text}\n```"


def build_sections(data: dict, *, include_diff: bool) -> list[tuple[str, str]]:
    ps = data.get("plan_sections") or {}
    sections = [
        ("Identity and freshness", _identity_section(data)),
        ("Evidence", _evidence_section(data)),
        ("Intent", ps.get("intent") or ""),
        ("Scrutiny", ps.get("scrutiny") or ""),
        ("Decisions", _decisions_section(data)),
        ("Not touched", _not_touched_section(data)),
        ("Risk map", _risk_map_section(data)),
        ("Deviations", _deviations_section(data, include_diffs=include_diff)),
        ("Assumptions", _assumptions_section(data)),
        ("Test summary", _test_summary_section(data)),
        ("Blind spots", _blind_spots_section(data)),
    ]
    if include_diff:
        sections.append(("Diff", _diff_section(data)))
    return sections


def render(data: dict, *, include_diff: bool) -> str:
    parts = []
    for title, body in build_sections(data, include_diff=include_diff):
        parts.append(f"## {title}\n\n{body.rstrip()}\n")
    return "\n".join(parts)
