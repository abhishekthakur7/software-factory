"""The manual outcome record: what actually happened to an opened pull request, entered by hand.

`revision` records a human revision made after `pr_opened`'s approval and
sends the ticket back through the state table's `revision_to_*` events; the
remote branch and pull request are left exactly as they are, since no
outbox intent is created here. `outcome` records the final, observed
disposition -- `merged` or `abandoned`, with the actual final SHAs, the
required-check disposition, and (optionally) an observed PR-body snapshot
-- and settles `ticket`'s once-only outcome-fields group in one write. It
never refuses or rewrites what actually happened: a mismatch between the
observed values and the ticket's own approved subject is recorded as a
`control_defect` observation alongside the outcome, not as a reason to
reject the call. `exposure`, `coverage`, `incident_event`, and
`disposition` extend the production-coverage and incident series a merge
or abandonment starts, independently of and any time after the outcome
itself. `control_event` is the one action here dispatched from an
arbitrary open queue item rather than a ticket or the `pr_outcome` item;
`queue.act` still owns resolving that item, this module only records the
observation.

Every row this module writes carries the acting identity and a role fixed
by the action, not derived by asking `owners.yaml` who currently holds it
-- validating that the actor actually holds the role they are recorded
under is a later concern; here the identity is only checked against the
known-actor list `queue.act` already enforces before dispatching here.
"""
import sqlite3
from pathlib import Path

from runner import artefact_registry, canonical, incident_policy, outbox, publication, queue, record, tags, transitions
from runner.deliverers.github import GitHubRemoteRefused
from runner.fs import write_text
from runner.paths import RUNS_DIR
from runner.trust_profile import DEFAULT_TRUST_PROFILE_PATH

# `revision`'s `--to` accepts exactly the stages `pr_opened` may return to;
# `checks` and `review` are never a revision target since a revision names
# where the human wants the next attempt planned or built, not where
# automated checks or a fresh review cycle would pick it back up.
REVISION_TARGETS = ("context", "clarifying", "planning", "implementing")

CHECKS_DISPOSITIONS = ("green", "waived", "red", "unknown")
RESULT_VALUES = ("merged", "abandoned")

# The fixed role every row this module writes is recorded under, per
# action -- not derived per actor, since which identity may act under
# which role is a later ticket's concern (see the module docstring).
OUTCOME_RECORDER_ROLE = "outcome_recorder"
INCIDENT_REVIEWER_ROLE = "incident_reviewer"

APPROVAL_BINDING_CATEGORY = "approval_binding"
MISMATCH_FM_ID = "FM-25"


def revision(
    conn: sqlite3.Connection, *, ticket_id: int, actor: str, owners_obj, fields: dict, runs_dir: Path = RUNS_DIR,
) -> None:
    """Record a human revision made after `pr_opened`'s approval, sending the ticket back to `fields['to']`.

    Refuses before writing anything when `to` names a stage `pr_opened`
    cannot return to. The remote branch and pull request the outbox
    already opened are left untouched -- no outbox intent is created or
    superseded here.
    """
    to = fields.get("to")
    if to not in REVISION_TARGETS:
        raise queue.ActionRefused(f"revision --to must be one of {REVISION_TARGETS}, got {to!r}")
    tags.tag(
        conn, target=f"ticket:{ticket_id}", kind="revision_after_approval",
        fm_id=fields.get("fm_id"), actor=actor, note=fields.get("note"),
    )
    ticket = record.get(conn, "ticket", ticket_id)
    record.update(
        conn, "ticket", ticket_id, external_revision_count=(ticket["external_revision_count"] or 0) + 1,
    )
    transitions.apply(conn, ticket_id, f"revision_to_{to}")


def _observed_body(
    conn: sqlite3.Connection, *, ticket_id: int, fields: dict, runs_dir: Path, profile_path: Path,
) -> str | None:
    """Write the observed-body document fs artefact and return `final_pr_body_hash`, or `None` given neither source.

    The document is written the same way regardless of source, so a
    byte-identical body from either a governed file or the remote locator
    hashes identically against `ticket.last_pr_body_hash`.
    """
    body_file = fields.get("body_file")
    pr_identity = fields.get("pr_identity")
    observed_head_sha = fields.get("observed_head_sha")
    if body_file and (pr_identity or observed_head_sha):
        raise queue.ActionRefused("outcome accepts --body-file or --pr-identity/--observed-head-sha, not both")
    if bool(pr_identity) != bool(observed_head_sha):
        raise queue.ActionRefused("outcome --pr-identity and --observed-head-sha must be given together")

    if body_file:
        document = {
            "source": "file", "pr_identity": None, "observed_head_sha": None,
            "body": Path(body_file).read_text(),
        }
    elif pr_identity:
        ticket = record.get(conn, "ticket", ticket_id)
        repository = publication.publication_target(conn, ticket).repository
        _, deliverer = outbox.route_and_deliverer(outbox.GITHUB_ROUTE_ID, profile_path=profile_path, runs_dir=runs_dir)
        try:
            remote = deliverer.pull_request_body(repository, pr_identity)
        except GitHubRemoteRefused as exc:
            raise queue.ActionRefused(f"outcome locator read failed: {exc}") from exc
        if remote["head_sha"] != observed_head_sha:
            raise queue.ActionRefused(
                f"--observed-head-sha {observed_head_sha!r} does not match the remote pull request's "
                f"current head {remote['head_sha']!r}"
            )
        document = {
            "source": "locator", "pr_identity": pr_identity, "observed_head_sha": observed_head_sha,
            "body": remote["body"],
        }
    else:
        return None

    count = conn.execute(
        "SELECT COUNT(*) FROM artefact WHERE ticket_id = ? AND kind = 'pr_body_observed'", (ticket_id,)
    ).fetchone()[0]
    path = runs_dir / "tickets" / str(ticket_id) / "pr_body_observed" / f"{count + 1}.json"
    write_text(path, canonical.canonical_json(document).decode() + "\n")
    artefact_registry.register(conn, ticket_id=ticket_id, kind="pr_body_observed", path=path)
    return canonical.content_hash({"pr_body": document["body"]})


def _pair_status(observed, expected) -> str:
    """`"match"`/`"mismatch"` when both sides are recorded, else `"unavailable"`."""
    if observed is None or expected is None:
        return "unavailable"
    return "match" if observed == expected else "mismatch"


def _record_mismatch(conn: sqlite3.Connection, ticket_id: int) -> None:
    """The three rows a mismatched outcome appends: a mechanical `control_defect` tag, its event, and an open disposition."""
    severity = incident_policy.severity_for(APPROVAL_BINDING_CATEGORY)
    note = "outcome recorded an approval-binding mismatch"
    tag_id = tags.tag(
        conn, target=f"ticket:{ticket_id}", kind="control_defect", fm_id=MISMATCH_FM_ID,
        actor=tags.MECHANICAL_ACTOR, severity=severity, note=note,
    )
    event_id = record.insert(
        conn, "incident_observation", ticket_id=ticket_id, record_kind="control_defect_event",
        control_category=APPROVAL_BINDING_CATEGORY, recorder_identity=tags.MECHANICAL_ACTOR,
        created_at=record.now(), tag_id=tag_id, occurred_at=record.now(), severity=severity, note=note,
    )
    record.insert(
        conn, "incident_observation", ticket_id=ticket_id, record_kind="control_disposition",
        event_id=event_id, disposition="open", recorder_identity=tags.MECHANICAL_ACTOR, created_at=record.now(),
    )


def outcome(
    conn: sqlite3.Connection, *, ticket_id: int, actor: str, owners_obj, fields: dict, runs_dir: Path = RUNS_DIR,
    profile_path: Path = DEFAULT_TRUST_PROFILE_PATH,
) -> None:
    """Record the pull request's final, observed disposition and settle `ticket`'s outcome-fields group once.

    Never refuses for a mismatch between the observed values and the
    ticket's own approved subject -- `approval_disposition` records it
    instead, and a mismatch additionally appends one `control_defect` tag
    and its control-defect event and open disposition, in this same call.
    """
    result = fields.get("result")
    if result not in RESULT_VALUES:
        raise queue.ActionRefused(f"outcome --result must be one of {RESULT_VALUES}, got {result!r}")
    checks = fields.get("checks")
    if checks not in CHECKS_DISPOSITIONS:
        raise queue.ActionRefused(f"outcome --checks must be one of {CHECKS_DISPOSITIONS}, got {checks!r}")
    if checks == "waived" and not fields.get("checks_reason"):
        raise queue.ActionRefused("outcome --checks waived requires --checks-reason")
    head_sha = fields.get("head_sha")
    target_base_sha = fields.get("target_base_sha")
    observed_at = fields.get("observed_at")
    if not head_sha or not target_base_sha or not observed_at:
        raise queue.ActionRefused("outcome requires --head-sha, --target-base-sha, and --observed-at")
    merge_sha = fields.get("merge_sha")
    if merge_sha and result != "merged":
        raise queue.ActionRefused("outcome --merge-sha is only valid with --result merged")

    body_hash = _observed_body(conn, ticket_id=ticket_id, fields=fields, runs_dir=runs_dir, profile_path=profile_path)

    ticket = record.get(conn, "ticket", ticket_id)
    review_row = conn.execute(
        "SELECT target_base_sha FROM evidence_tuple WHERE ticket_id = ? AND kind = 'review' ORDER BY id DESC LIMIT 1",
        (ticket_id,),
    ).fetchone()
    expected_target_base = review_row["target_base_sha"] if review_row is not None else None

    statuses = (
        _pair_status(head_sha, ticket["last_remote_head_sha"]),
        _pair_status(target_base_sha, expected_target_base),
        _pair_status(body_hash, ticket["last_pr_body_hash"]),
    )
    if "mismatch" in statuses or checks == "red":
        approval_disposition = "mismatched"
    elif all(status == "match" for status in statuses):
        approval_disposition = "matched"
    else:
        approval_disposition = "unknown"

    settle = {
        "final_head_sha": head_sha,
        "final_target_base_sha": target_base_sha,
        "final_pr_body_hash": body_hash,
        "required_checks_disposition": checks,
        "approval_disposition": approval_disposition,
        "outcome_actor_role": OUTCOME_RECORDER_ROLE,
        "outcome_observed_at": observed_at,
    }
    if result == "merged":
        settle["merge_sha"] = merge_sha
    record.update(conn, "ticket", ticket_id, **settle)

    if approval_disposition == "mismatched":
        _record_mismatch(conn, ticket_id)

    if result == "merged":
        transitions.apply(conn, ticket_id, "merge_recorded")
        record.insert(
            conn, "incident_observation", ticket_id=ticket_id, record_kind="production_coverage",
            coverage_status="unknown", recorder_identity=actor, recorder_role=OUTCOME_RECORDER_ROLE,
            created_at=record.now(),
        )
    else:
        fm_id = fields.get("fm_id")
        if not fm_id:
            raise queue.ActionRefused("outcome --result abandoned requires --fm")
        queue.abandon(conn, ticket_id, actor=actor, fm_id=fm_id, note=fields.get("note"), runs_dir=runs_dir)


def _resolve_root(conn: sqlite3.Connection, ticket_id: int, root: str | None) -> int | None:
    """The `production_coverage` row `root` names, or the ticket's latest one when `root` is omitted.

    Refuses a `root` that does not name a `production_coverage` row of
    this exact ticket -- an incident root or another ticket's row alike.
    """
    if root is None:
        row = conn.execute(
            "SELECT id FROM incident_observation WHERE ticket_id = ? AND record_kind = 'production_coverage' "
            "ORDER BY id DESC LIMIT 1",
            (ticket_id,),
        ).fetchone()
        return row["id"] if row is not None else None
    try:
        root_id = int(root)
    except (TypeError, ValueError):
        raise queue.ActionRefused(f"--root must name a production_coverage row, got {root!r}") from None
    row = record.get(conn, "incident_observation", root_id)
    if row is None or row["ticket_id"] != ticket_id or row["record_kind"] != "production_coverage":
        raise queue.ActionRefused(f"--root does not name a production_coverage row of this ticket: {root!r}")
    return root_id


def exposure(conn: sqlite3.Connection, *, ticket_id: int, actor: str, owners_obj, fields: dict) -> int:
    """Append one `unknown`-status coverage row recording when and how the change first reached production."""
    start, source = fields.get("start"), fields.get("source")
    if not start or not source:
        raise queue.ActionRefused("exposure requires --start and --source")
    supersedes = _resolve_root(conn, ticket_id, fields.get("root"))
    return record.insert(
        conn, "incident_observation", ticket_id=ticket_id, record_kind="production_coverage",
        coverage_status="unknown", exposure_start=start, exposure_source=source, supersedes=supersedes,
        recorder_identity=actor, recorder_role=OUTCOME_RECORDER_ROLE, created_at=record.now(),
    )


def coverage(conn: sqlite3.Connection, *, ticket_id: int, actor: str, owners_obj, fields: dict) -> int:
    """Append one `none_observed`-status coverage row over the exposure window the current row already opened."""
    through = fields.get("through")
    if not through:
        raise queue.ActionRefused("coverage requires --through")
    supersedes = _resolve_root(conn, ticket_id, fields.get("root"))
    current = record.get(conn, "incident_observation", supersedes) if supersedes is not None else None
    if current is None or not current["exposure_start"] or not current["exposure_source"]:
        raise queue.ActionRefused("coverage requires the ticket's current coverage row to carry an exposure start and source")
    return record.insert(
        conn, "incident_observation", ticket_id=ticket_id, record_kind="production_coverage",
        coverage_status="none_observed", observed_through=through, supersedes=supersedes,
        recorder_identity=actor, recorder_role=OUTCOME_RECORDER_ROLE, created_at=record.now(),
    )


def incident_event(conn: sqlite3.Connection, *, ticket_id: int, actor: str, owners_obj, fields: dict) -> int:
    """Append one `production_incident_event` row and its required `incident` tag; this root is never superseded."""
    severity, occurred_at, fm_id = fields.get("severity"), fields.get("occurred_at"), fields.get("fm_id")
    if not severity or not occurred_at or not fm_id:
        raise queue.ActionRefused("incident_event requires --severity, --occurred-at, and --fm")
    incident_policy.validate_severity(severity)
    note = fields.get("note")
    tag_id = tags.tag(conn, target=f"ticket:{ticket_id}", kind="incident", fm_id=fm_id, actor=actor, note=note, severity=severity)
    return record.insert(
        conn, "incident_observation", ticket_id=ticket_id, record_kind="production_incident_event",
        recorder_identity=actor, recorder_role=INCIDENT_REVIEWER_ROLE, created_at=record.now(),
        tag_id=tag_id, occurred_at=occurred_at, severity=severity, note=note,
    )


def _latest_disposition(conn: sqlite3.Connection, event_id: int) -> int | None:
    row = conn.execute(
        "SELECT id FROM incident_observation WHERE record_kind = 'production_disposition' AND event_id = ? "
        "ORDER BY id DESC LIMIT 1",
        (event_id,),
    ).fetchone()
    return row["id"] if row is not None else None


def disposition(conn: sqlite3.Connection, *, ticket_id: int, actor: str, owners_obj, fields: dict) -> int:
    """Append one `production_disposition` row over `fields['event']`, superseding only the same root's earlier one."""
    event_ref = fields.get("event")
    if not event_ref:
        raise queue.ActionRefused("disposition requires --event")
    try:
        event_id = int(event_ref)
    except (TypeError, ValueError):
        raise queue.ActionRefused(f"--event must name a production_incident_event, got {event_ref!r}") from None
    event = record.get(conn, "incident_observation", event_id)
    if event is None or event["ticket_id"] != ticket_id or event["record_kind"] != "production_incident_event":
        raise queue.ActionRefused(f"--event does not name a production_incident_event of this ticket: {event_ref!r}")

    policy = incident_policy.load()
    attribution_value = fields.get("attribution")
    if attribution_value not in incident_policy.ATTRIBUTIONS(policy):
        raise queue.ActionRefused(f"--attribution must be one of {incident_policy.ATTRIBUTIONS(policy)}, got {attribution_value!r}")
    disposition_value = fields.get("disposition")
    if disposition_value not in incident_policy.DISPOSITIONS(policy):
        raise queue.ActionRefused(f"--disposition must be one of {incident_policy.DISPOSITIONS(policy)}, got {disposition_value!r}")
    remediation_ref = fields.get("remediation_ref")
    try:
        incident_policy.check_remediation(disposition_value, remediation_ref, policy)
    except incident_policy.IncidentPolicyError as exc:
        raise queue.ActionRefused(str(exc)) from exc

    return record.insert(
        conn, "incident_observation", ticket_id=ticket_id, record_kind="production_disposition",
        event_id=event_id, attribution=attribution_value, disposition=disposition_value, remediation_ref=remediation_ref,
        supersedes=_latest_disposition(conn, event_id), recorder_identity=actor, recorder_role=INCIDENT_REVIEWER_ROLE,
        created_at=record.now(),
    )


def control_event(conn: sqlite3.Connection, item: sqlite3.Row, *, actor: str, owners_obj, fields: dict) -> None:
    """Record one control-defect observation against `item`, deriving severity from the policy when none is given.

    Does not resolve `item` -- `queue.act` records this observation in
    addition to whatever else the item is open for, not instead of it.
    """
    category = fields.get("category")
    if not category:
        raise queue.ActionRefused("control_event requires --category")
    severity = fields.get("severity") or incident_policy.severity_for(category)
    incident_policy.validate_severity(severity)
    note = fields.get("note")
    record.insert(
        conn, "incident_observation", ticket_id=item["ticket_id"], record_kind="control_defect_event",
        control_category=category, recorder_identity=actor, recorder_role=INCIDENT_REVIEWER_ROLE,
        occurred_at=record.now(), severity=severity, note=note, created_at=record.now(),
    )
    tags.tag(
        conn, target=f"queue_item:{item['id']}", kind="control_defect",
        fm_id=fields.get("fm_id"), actor=actor, note=note, severity=severity,
    )


def open_pr_outcome_item(conn: sqlite3.Connection, ticket_id: int) -> int | None:
    """Open the ticket's non-blocking `pr_outcome` item on a first reconciled receipt, else return `None`.

    A ticket already carrying an unresolved `pr_outcome` item receives no
    second one: exactly one stays current across create and update
    cycles. `ref` names the latest reconciled pull-request receipt's
    artefact, when one exists.
    """
    existing = conn.execute(
        "SELECT id FROM queue_item WHERE ticket_id = ? AND kind = 'pr_outcome' AND resolved_at IS NULL",
        (ticket_id,),
    ).fetchone()
    if existing is not None:
        return None
    receipt = conn.execute(
        "SELECT receipt_artefact_id FROM external_write WHERE ticket_id = ? AND state = 'reconciled' "
        "AND operation IN ('pr_create', 'pr_update') AND receipt_artefact_id IS NOT NULL ORDER BY id DESC LIMIT 1",
        (ticket_id,),
    ).fetchone()
    ref = f"artefact:{receipt['receipt_artefact_id']}" if receipt is not None else None
    return queue.open_item(conn, ticket_id=ticket_id, kind="pr_outcome", ref=ref)
