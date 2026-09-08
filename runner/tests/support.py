"""Shared test seeding that must match what the real gates and drivers derive.

A ticket a test parks in `implementing` needs the same plan subject S4's
pre-invocation revalidation re-derives from the record: a planned reviewer
set, a plan tuple whose bound fields equal `plan_tuple.derive_components`,
and one approving record per planned slot. Hand-seeding a tuple with a
made-up hash used to be enough; it is not once anything re-derives the
subject, so every test that needs an approved current plan goes through
here rather than inventing its own approximation.
"""
import json
import sqlite3
import tempfile
from pathlib import Path

from runner import approvals, artefact_registry, artefacts, owners, plan_tuple, record
from runner.reviewer_sets import Slot

# Stand-in trust binding for a ticket a test never took through governance:
# the plan tuple binds both hashes and refuses a null, and both columns are
# written once at insert, so a seeder passes these when it opens the ticket.
TRUST_PROFILE_HASH = "trust-profile-1"
TRUST_APPROVAL_SET_HASH = "trust-approval-set-1"


def approve_current_plan(conn: sqlite3.Connection, ticket_id: int) -> int:
    """Derive and create the ticket's current plan tuple and approve it on the pilot's one S3 slot; return the tuple id.

    Call after every artefact the plan subject binds (brief, criteria,
    plan) is registered and the ticket's base is pinned, since the tuple
    is derived from exactly those rows. A planned reviewer set is added
    only when the ticket has none, so a test that derived a real one keeps it.
    """
    if artefact_registry.latest(conn, ticket_id, "brief") is None:
        # A one-section brief in a throwaway directory: the tuple binds a
        # brief hash and these tests judge S4, not the brief. Never written
        # beside the plan, which may be a committed eval fixture.
        brief_path = Path(tempfile.mkdtemp(prefix="seeded-brief-")) / f"brief-{ticket_id}.md"
        brief_path.write_text(f"## {artefacts.SECTIONS['brief'][0]}\n\nseeded brief\n")
        artefact_registry.register(conn, ticket_id=ticket_id, kind="brief", path=brief_path)
    identity = owners.load_owners().roles["s3_reviewer"]["identity"]
    slot = Slot(source_rule="s3_reviewer_role", role="s3_reviewer", owner=identity, min_count=1)
    planned = conn.execute(
        "SELECT slots FROM reviewer_set WHERE ticket_id = ? AND kind = 'planned' ORDER BY id DESC LIMIT 1", (ticket_id,)
    ).fetchone()
    if planned is None:
        record.insert(
            conn, "reviewer_set", ticket_id=ticket_id, kind="planned", content_hash=f"planned-{ticket_id}",
            slots=json.dumps([slot.to_json()]),
        )
        slots = [slot]
    else:
        slots = [Slot.from_json(item) for item in json.loads(planned["slots"] or "[]")]
    ticket = record.get(conn, "ticket", ticket_id)
    tuple_id = plan_tuple.ensure_current(conn, ticket)
    subject_hash = record.get(conn, "evidence_tuple", tuple_id)["content_hash"]
    for planned_slot in slots:
        approvals.record_approval(
            conn, gate="plan", subject_hash=subject_hash, slot_id=planned_slot.slot_id, actor_identity=identity,
            role=planned_slot.role or "owner", decision="approve", authority_policy_hash="authority-1",
            membership_snapshot_hash="membership-1", attestation_version="v1",
            attestation_hash=f"att-{planned_slot.slot_id}", ticket_id=ticket_id,
        )
    return tuple_id
