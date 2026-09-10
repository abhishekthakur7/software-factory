"""Shared test seeding that must match what the real gates and drivers derive.

A ticket a test parks in `implementing` needs the same plan subject implementation's
pre-invocation revalidation re-derives from the record: a planned reviewer
set, a plan tuple whose bound fields equal `plan_tuple.derive_components`,
and one approving record per planned slot. Hand-seeding a tuple with a
made-up hash used to be enough; it is not once anything re-derives the
subject, so every test that needs an approved current plan goes through
here rather than inventing its own approximation.
"""
import json
import sqlite3
import sys
from pathlib import Path

from runner import approvals, artefact_registry, artefacts, launcher, owners, plan_tuple, record
from runner.paths import REPO_ROOT
from runner.reviewer_sets import Slot

# Stand-in trust binding for a ticket a test never took through governance:
# the plan tuple binds both hashes and refuses a null, and both columns are
# written once at insert, so a seeder passes these when it opens the ticket.
TRUST_PROFILE_HASH = "trust-profile-1"
TRUST_APPROVAL_SET_HASH = "trust-approval-set-1"


def approve_current_plan(conn: sqlite3.Connection, ticket_id: int, scratch_dir: Path) -> int:
    """Derive and create the ticket's current plan tuple and approve it on the pilot's one planning slot; return the tuple id.

    Call after every artefact the plan subject binds (brief, criteria,
    plan) is registered and the ticket's base is pinned, since the tuple
    is derived from exactly those rows. A planned reviewer set is added
    only when the ticket has none, so a test that derived a real one keeps it.
    A ticket with no brief gets a one-section stand-in written under
    `scratch_dir` (the test's `tmp_path`): the tuple binds a brief hash,
    and these tests judge implementation, not the brief. The stand-in is never placed
    beside the plan, because a plan registered at a committed fixture path
    would then leave an untracked file inside the repository.
    """
    if artefact_registry.latest(conn, ticket_id, "brief") is None:
        brief_path = scratch_dir / f"brief-{ticket_id}.md"
        brief_path.write_text(f"## {artefacts.SECTIONS['brief'][0]}\n\nseeded brief\n")
        artefact_registry.register(conn, ticket_id=ticket_id, kind="brief", path=brief_path)
    identity = owners.load_owners().roles["plan_reviewer"]["identity"]
    slot = Slot(source_rule="plan_reviewer_role", role="plan_reviewer", owner=identity, min_count=1)
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


REAL_SANDBOX_PATH = REPO_ROOT / "factory" / "config" / "sandbox.yaml"


def launch_probe(
    tmp_path: Path, probe_source: Path, *, role: str, stage: str = "context_gathering", extra_argv: tuple = (),
    env_source: dict | None = None, ticket_dir: Path | None = None, worktree_path: Path | None = None,
    copy_dir: Path | None = None, build_dir: Path | None = None, scratch_dir: Path | None = None,
    cache_dir: Path | None = None, vendor_dir: Path | None = None, routes=None,
) -> dict:
    """Run `probe_source` for real under the committed Seatbelt profile for `role`; return its one stdout JSON line.

    The probe is copied into the run's own `tmp/`, the one path both
    profiles grant read access to without also granting it to the
    directory the probe was written in, so a probe never needs `factory/`
    or the test tree readable from inside the sandbox. A launch the OS
    policy did not actually wrap, or a probe with no parseable output,
    fails here rather than letting a caller read a refusal into silence.
    `routes` reaches the launcher unchanged, for a probe that dispatches a
    call through the sandbox's `POST /routes/<route_id>` handler; this
    function's own `run_dir` convention below (`tmp_path / "run"`) is
    exactly what a caller's `RouteService.run_dir` must match.
    """
    run_dir = tmp_path / "run"
    scratch = run_dir / "tmp"
    scratch.mkdir(parents=True, exist_ok=True)
    probe_copy = scratch / "probe.py"
    probe_copy.write_text(Path(probe_source).read_text())

    result = launcher.launch(
        run_dir=run_dir, argv=[sys.executable, str(probe_copy), *extra_argv], role=role, policy="enforced",
        cwd=tmp_path, wall_clock_seconds=20, stage=stage, ticket_dir=ticket_dir, worktree_path=worktree_path,
        copy_dir=copy_dir, build_dir=build_dir, scratch_dir=scratch_dir, cache_dir=cache_dir, vendor_dir=vendor_dir,
        env_source=env_source, sandbox_path=REAL_SANDBOX_PATH, routes=routes,
    )
    assert result.os_policy_applied is True, "a probe must run under a real OS-enforced profile"
    assert result.stdout_json is not None, f"probe produced no parseable JSON; stderr: {result.stderr_text}"
    return result.stdout_json
