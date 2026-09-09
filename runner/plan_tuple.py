"""The plan tuple: every field a plan-approval subject binds, derived fresh from the record.

`derive_components` is a pure read: it never writes, so a caller can ask
"what would the plan subject be right now" without side effects.
`ensure_current` is the one place a `plan` `evidence_tuple` row is
created for a ticket -- called once the bootstrap checklist completes
with no fail and no unwaived blind spot, and again as `queue.act`'s
approve-time race guard -- so both callers always compare a freshly
derived `PlanComponents` against the ticket's latest stored plan tuple
rather than trusting a value computed earlier in the same request. Every
bound hash but `semantic_checklist_hash`, `human_verdict_set_hash`, and
`plan_waiver_set_hash` is read straight off already-registered rows;
those three are the one place this module and `runner.checklist` meet,
since the checklist's own expected set and the verdicts and waivers
answering it are themselves bound fields.
"""
import hashlib
import sqlite3
from pathlib import Path

from runner import artefact_registry, binding, canonical, checklist, envelope, project, questions, record
from runner.paths import RUNS_DIR

# The sandbox policy every stage runs under; the plan tuple binds its
# digest the same way `runner.envelope.build` does for a stage
# invocation's own envelope, resolved for S3 -- the stage a plan tuple
# itself belongs to.
SANDBOX_POLICY = "enforced"
_SANDBOX_DIGEST_STAGE = "S3"


def _latest_hash(conn: sqlite3.Connection, ticket_id: int, kind: str) -> str | None:
    row = artefact_registry.latest(conn, ticket_id, kind)
    return row["hash"] if row is not None else None


def _ticket_source_hash(conn: sqlite3.Connection, ticket: sqlite3.Row) -> str:
    row = artefact_registry.latest(conn, ticket["id"], "ticket_source")
    if row is not None:
        return row["hash"]
    return canonical.content_hash(
        {"source_kind": ticket["source_kind"], "source_ref": ticket["source_ref"], "title": ticket["title"]}
    )


def _question_resolution_set_hash(conn: sqlite3.Connection, ticket_id: int) -> str:
    rows = conn.execute(
        "SELECT answer.* FROM answer JOIN question ON question.id = answer.question_id WHERE question.ticket_id = ?",
        (ticket_id,),
    ).fetchall()
    return binding.set_hash(dict(row) for row in rows)


def _project_config() -> dict:
    return project.pilot()


def _project_config_hash() -> str:
    # The whole file's bytes, not just the pilot's own entry: any change
    # to `project.yaml` -- another project added, the scratch repository
    # renamed -- must invalidate a plan approved before it, the same as a
    # change to any other bound-subject file.
    return hashlib.sha256(Path(project.DEFAULT_PROJECT_CONFIG_PATH).read_bytes()).hexdigest()


def _planned_reviewer_set_hash(conn: sqlite3.Connection, ticket_id: int) -> str | None:
    row = conn.execute(
        "SELECT content_hash FROM reviewer_set WHERE ticket_id = ? AND kind = 'planned' ORDER BY id DESC LIMIT 1",
        (ticket_id,),
    ).fetchone()
    return row["content_hash"] if row is not None else None


def _latest_plan_tuple(conn: sqlite3.Connection, ticket_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM evidence_tuple WHERE ticket_id = ? AND kind = 'plan' ORDER BY id DESC LIMIT 1",
        (ticket_id,),
    ).fetchone()


def derive_components(conn: sqlite3.Connection, ticket: sqlite3.Row) -> binding.PlanComponents:
    """Every field a `plan` `evidence_tuple` row would bind for `ticket`, read fresh from the record.

    A pure read over already-registered rows and the ticket's own
    columns; the one derivation this module performs beyond a straight
    lookup is the checklist's own expected set and the verdict/waiver sets
    answering it, through `runner.checklist`.
    """
    ticket_id = ticket["id"]
    project_cfg = _project_config()
    expected = checklist.expected_instances(conn, ticket)
    return binding.PlanComponents(
        ticket_source_hash=_ticket_source_hash(conn, ticket),
        brief_hash=_latest_hash(conn, ticket_id, "brief"),
        criteria_hash=_latest_hash(conn, ticket_id, "criteria"),
        plan_hash=_latest_hash(conn, ticket_id, "plan"),
        question_resolution_set_hash=_question_resolution_set_hash(conn, ticket_id),
        current_assumption_set_hash=questions.assumption_log_hash(conn, ticket_id),
        base_sha=ticket["base_sha"],
        target_base_sha=ticket["target_base_sha"],
        manifest_hash=ticket["factory_manifest_hash"],
        project_config_hash=_project_config_hash(),
        trust_profile_hash=ticket["trust_profile_hash"],
        trust_approval_set_hash=ticket["trust_approval_set_hash"],
        recipe_hash=envelope.recipe_set_hash(),
        sandbox_digest=envelope.sandbox_digest(SANDBOX_POLICY, stage=_SANDBOX_DIGEST_STAGE, runs_dir=RUNS_DIR),
        toolchain_digest=envelope.toolchain_digest(project_cfg.get("toolchain", {})),
        planned_reviewer_set_hash=_planned_reviewer_set_hash(conn, ticket_id),
        semantic_checklist_hash=checklist.checklist_hash(expected),
        human_verdict_set_hash=binding.set_hash(checklist.verdict_set(conn, ticket_id)),
        plan_waiver_set_hash=binding.set_hash(checklist.waiver_set(conn, ticket_id)),
    )


def ensure_current(conn: sqlite3.Connection, ticket: sqlite3.Row) -> int:
    """The ticket's latest plan-tuple id when it is still current, else a freshly created one.

    `head_sha` is not a bound `PlanComponents` field, so an S4 hand-back
    that only advances it never trips `plan_tuple_currency` here and no
    new subject is created; every other drift this module can see (a new
    answer, a superseded assumption, a corrected verdict, a fresh waiver,
    a moved base) does.
    """
    components = derive_components(conn, ticket)
    latest = _latest_plan_tuple(conn, ticket["id"])
    if latest is not None and binding.plan_tuple_currency(conn, latest["id"], components).current:
        return latest["id"]
    return binding.create_plan_tuple(conn, ticket["id"], components)


def current_subject(conn: sqlite3.Connection, ticket: sqlite3.Row) -> str | None:
    """The ticket's current plan-approval subject hash for display, or `None` before any plan tuple exists.

    Never creates a tuple -- `factory queue`'s read side must not have a
    side effect a human merely looking at the queue would not expect.
    """
    row = _latest_plan_tuple(conn, ticket["id"])
    return row["content_hash"] if row is not None else None
