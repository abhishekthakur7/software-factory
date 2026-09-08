"""Waivers: policy, issuance, and validity of a `waiver` row over a blocking epistemic blind spot.

A `check_result` or `human_verdict` row is immutable, so `waived` is never
stored on it. It is derived here, at the moment of asking, from a `waiver`
row that names the result and is valid right now -- a waiver that expires,
or whose subject, evidence, policy, or actor authority no longer holds,
stops covering the result without any row changing. Every reader that must
show or gate on a result's effective status (the S6 evidence table, the
checks gate, the dispatch recheck, a `policy_exception` tag) asks this
module rather than joining the two tables itself, so the rule for what a
valid waiver is lives in exactly one place.

`load_policy` parses `waiver-policy.yaml`'s never-waivable set and its
small list of policy entries, each with the subject kinds, conditions, and
roles it covers. `issue` is the one writer of `waiver`: a check name or
rubric line id in the never-waivable set is refused before any policy
entry is even consulted, and a `fail` result is never waivable at all --
only a declared `blind_spot` is. A successful review-tuple waiver shares
the `red_check` item S5's own failures opened, resolving it through
`queue.resolve_by_waiver` the moment the run's every blocking result is
`pass` or validly waived; a human never reaches that resolution through
`queue.act` directly. `validity` re-derives every reason a waiver no
longer holds -- expiry, a changed or retired policy, lost actor authority,
a drifted subject, or changed evidence -- every reason checked
independently rather than short-circuited on the first found. `recheck`
answers the same question for every waiver currently bound into a
ticket's plan and review tuples, for the S6 and dispatch rechecks another
builder wires in.
"""
import fnmatch
import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import yaml

from runner import canonical, owners, record, tags
from runner.paths import FACTORY_DIR

DEFAULT_POLICY_PATH = FACTORY_DIR / "config" / "waiver-policy.yaml"

# The `policy_exception` tag's failure-mode id: a waiver covers an
# epistemic gap, the FM-14 "unknown impact" class named for R-S5-13 in the
# failure-mode catalogue, whichever stage recorded the blind spot.
POLICY_EXCEPTION_FM_ID = "FM-14"

# `check_result.result`/`human_verdict.verdict` values a valid waiver may
# cover. A `fail` is a defect, never an epistemic gap, so no waiver ever
# turns one into `waived`.
WAIVABLE_RESULTS: frozenset[str] = frozenset({"blind_spot"})


class WaiverRefused(ValueError):
    """A waiver request fails a policy, authority, evidence, or expiry rule before any row is written."""


@dataclass(frozen=True)
class Validity:
    valid: bool
    # Empty when valid; otherwise every reason the waiver no longer holds.
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class PolicyEntry:
    id: str
    version: str
    subject_kinds: tuple[str, ...]
    conditions: tuple[str, ...]
    roles: tuple[str, ...]
    max_days: int
    severity: str


@dataclass(frozen=True)
class Policy:
    entries: tuple[PolicyEntry, ...]
    never_waivable: frozenset[str]
    # sha256 of the policy file's exact committed bytes, the hash a waiver
    # row pins so a later edit to the file -- even one that only reorders
    # entries -- is visible as `policy_changed` at recheck.
    policy_hash: str

    def entry(self, policy_id: str) -> PolicyEntry | None:
        return next((item for item in self.entries if item.id == policy_id), None)


def load_policy(path: Path = DEFAULT_POLICY_PATH) -> Policy:
    """Parse `path`'s never-waivable set and policy entries, hashing the file's exact bytes."""
    raw = Path(path).read_bytes()
    doc = yaml.safe_load(raw) or {}
    entries = tuple(
        PolicyEntry(
            id=item["id"],
            version=str(item["version"]),
            subject_kinds=tuple(item.get("subject_kinds", [])),
            conditions=tuple(item.get("conditions", [])),
            roles=tuple(item.get("roles", [])),
            max_days=int(item["max_days"]),
            severity=item["severity"],
        )
        for item in doc.get("policies", [])
    )
    return Policy(
        entries=entries,
        never_waivable=frozenset(doc.get("never_waivable", [])),
        policy_hash=hashlib.sha256(raw).hexdigest(),
    )


def _matches(condition: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatchcase(condition, pattern) for pattern in patterns)


def _days_between(start: str, end: str) -> float:
    return (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds() / 86400


def _ticket_id_for_check_result(conn: sqlite3.Connection, check_result: sqlite3.Row) -> int | None:
    run = record.get(conn, "stage_run", check_result["stage_run_id"])
    return run["ticket_id"] if run is not None else None


def _latest_review_tuple(conn: sqlite3.Connection, check_result: sqlite3.Row) -> sqlite3.Row | None:
    """The ticket's newest `review` `evidence_tuple`, or None when the check result names no ticket or the ticket has none."""
    ticket_id = _ticket_id_for_check_result(conn, check_result)
    if ticket_id is None:
        return None
    return conn.execute(
        "SELECT * FROM evidence_tuple WHERE ticket_id = ? AND kind = 'review' ORDER BY id DESC LIMIT 1",
        (ticket_id,),
    ).fetchone()


def subject_hash(
    conn: sqlite3.Connection,
    *,
    check_result: sqlite3.Row | None = None,
    human_verdict: sqlite3.Row | None = None,
    owners_path: Path = owners.DEFAULT_OWNERS_PATH,
    policy_path: Path = DEFAULT_POLICY_PATH,
) -> str:
    """The canonical subject a waiver over `check_result` or `human_verdict` (exactly one) binds.

    A verdict's subject is a canonical hash over the verdict's own frozen
    content -- its content hash, subject-artefact hash, evidence hashes,
    rubric file hash and line id -- plus the context every plan-candidate
    waiver must also track: the ticket's pinned manifest hash, trust-profile
    hash, the authority policy's hash, and this waiver policy's own hash. A
    check result's subject is simply its ticket's newest review tuple's
    content hash: an S5 waiver binds the review tuple as a whole, so any
    later review tuple -- a fresh preflight after a fix round -- is
    automatically a different subject with nothing else to compute.
    Raises `WaiverRefused` when a review-tuple waiver names a ticket with
    no review tuple at all.
    """
    if (check_result is None) == (human_verdict is None):
        raise ValueError("subject_hash takes exactly one of check_result or human_verdict")
    if human_verdict is not None:
        ticket = record.get(conn, "ticket", human_verdict["ticket_id"])
        policy = load_policy(policy_path)
        return canonical.content_hash({
            "verdict_content_hash": human_verdict["content_hash"],
            "subject_artefact_hash": human_verdict["subject_artefact_hash"],
            "evidence_hashes": human_verdict["evidence_hashes"],
            "rubric_hash": human_verdict["rubric_hash"],
            "rubric_line_id": human_verdict["rubric_line_id"],
            "manifest_hash": ticket["factory_manifest_hash"] if ticket is not None else None,
            "trust_profile_hash": ticket["trust_profile_hash"] if ticket is not None else None,
            "authority_policy_hash": owners.authority_policy_hash(owners_path),
            "waiver_policy_hash": policy.policy_hash,
        })
    review_tuple = _latest_review_tuple(conn, check_result)
    if review_tuple is None:
        raise WaiverRefused("no review tuple exists for a review-tuple waiver")
    return review_tuple["content_hash"]


def issue(
    conn: sqlite3.Connection,
    *,
    ticket_id: int,
    policy_id: str,
    check_result_id: int | None = None,
    human_verdict_id: int | None = None,
    actor: str,
    reason: str,
    scope: str,
    compensating_controls: str,
    evidence_ids: list[int],
    expires_at: str,
    now: str | None = None,
    owners_path: Path = owners.DEFAULT_OWNERS_PATH,
    policy_path: Path = DEFAULT_POLICY_PATH,
) -> int:
    """Insert one immutable `waiver` row over an existing `blind_spot` result and return its id.

    Exactly one of `check_result_id` or `human_verdict_id` names the
    waived row; the named row must already belong `ticket_id` and carry
    `blind_spot` -- a `fail` is a defect, never waivable, and the refusal
    says so. The condition (the check's own name, or the verdict's rubric
    line id) is refused outright when the policy file's never-waivable set
    names it, before `policy_id` is even looked up. Otherwise the exact
    policy entry must exist, cover this subject kind, permit the condition
    (glob-matched against its `conditions`), and list a role `actor` holds
    in `owners.yaml`; `reason`, `scope`, `compensating_controls`, and at
    least one evidence id (each naming an artefact of this ticket) are all
    mandatory, and `expires_at` must fall after `now` and within the
    policy's `max_days`. On success this call also writes the waiver's
    reporting `policy_exception` tag in the same transaction and, for a
    review-tuple waiver whose stage run is now fully clear, resolves the
    `red_check` item that run's failures shared through
    `runner.queue.resolve_by_waiver`.
    """
    if (check_result_id is None) == (human_verdict_id is None):
        raise WaiverRefused("issue a waiver against exactly one of a check result or a human verdict")
    now = now or record.now()
    if not reason:
        raise WaiverRefused("a waiver requires a reason")
    if not scope:
        raise WaiverRefused("a waiver requires an exact scope")
    if not compensating_controls:
        raise WaiverRefused("a waiver requires compensating controls")
    if not evidence_ids:
        raise WaiverRefused("a waiver requires at least one supporting evidence id")
    if not expires_at:
        raise WaiverRefused("a waiver requires a mandatory expiry")
    if expires_at <= now:
        raise WaiverRefused("a waiver's expiry must fall after the issuing time")

    check_result: sqlite3.Row | None = None
    human_verdict: sqlite3.Row | None = None
    if check_result_id is not None:
        check_result = record.get(conn, "check_result", check_result_id)
        if check_result is None:
            raise WaiverRefused(f"no such check_result: {check_result_id}")
        run = record.get(conn, "stage_run", check_result["stage_run_id"])
        if run is None or run["ticket_id"] != ticket_id:
            raise WaiverRefused(f"check_result {check_result_id} does not belong to ticket {ticket_id}")
        if check_result["result"] == "fail":
            raise WaiverRefused(f"check_result {check_result_id} is a fail, never waivable")
        if check_result["result"] not in WAIVABLE_RESULTS:
            raise WaiverRefused(f"check_result {check_result_id} carries no blind spot to waive")
        condition = check_result["check_name"]
        subject_kind = "review_tuple"
    else:
        human_verdict = record.get(conn, "human_verdict", human_verdict_id)
        if human_verdict is None:
            raise WaiverRefused(f"no such human_verdict: {human_verdict_id}")
        if human_verdict["ticket_id"] != ticket_id:
            raise WaiverRefused(f"human_verdict {human_verdict_id} does not belong to ticket {ticket_id}")
        if human_verdict["verdict"] == "fail":
            raise WaiverRefused(f"human_verdict {human_verdict_id} is a fail, never waivable")
        if human_verdict["verdict"] not in WAIVABLE_RESULTS:
            raise WaiverRefused(f"human_verdict {human_verdict_id} carries no blind spot to waive")
        condition = human_verdict["rubric_line_id"]
        subject_kind = "plan_candidate"

    policy = load_policy(policy_path)
    if condition in policy.never_waivable:
        raise WaiverRefused(f"{condition!r} is never waivable; no policy may cover it")
    entry = policy.entry(policy_id)
    if entry is None:
        raise WaiverRefused(f"no such waiver policy: {policy_id!r}")
    if subject_kind not in entry.subject_kinds:
        raise WaiverRefused(f"policy {policy_id!r} does not cover a {subject_kind!r} waiver")
    if not _matches(condition, entry.conditions):
        raise WaiverRefused(f"policy {policy_id!r} does not permit condition {condition!r}")

    owners_obj = owners.load_owners(owners_path)
    permitted_roles = sorted(
        role for role, info in owners_obj.roles.items() if info["identity"] == actor and role in entry.roles
    )
    if not permitted_roles:
        raise WaiverRefused(f"actor {actor!r} holds no role policy {policy_id!r} authorises")
    actor_role = permitted_roles[0]

    if _days_between(now, expires_at) > entry.max_days:
        raise WaiverRefused(f"expiry exceeds policy {policy_id!r}'s {entry.max_days}-day maximum")

    evidence_hashes: list[str] = []
    for evidence_id in evidence_ids:
        artefact_row = record.get(conn, "artefact", evidence_id)
        if artefact_row is None or artefact_row["ticket_id"] != ticket_id:
            raise WaiverRefused(f"evidence id {evidence_id} is not an artefact of ticket {ticket_id}")
        evidence_hashes.append(artefact_row["hash"])

    review_tuple_row: sqlite3.Row | None = None
    if subject_kind == "review_tuple":
        review_tuple_row = _latest_review_tuple(conn, check_result)
        if review_tuple_row is None:
            raise WaiverRefused("no review tuple exists for a review-tuple waiver")
        subj_hash = review_tuple_row["content_hash"]
    else:
        subj_hash = subject_hash(conn, human_verdict=human_verdict, owners_path=owners_path, policy_path=policy_path)

    row = {
        "ticket_id": ticket_id,
        "policy_id": entry.id,
        "policy_version": entry.version,
        "policy_hash": policy.policy_hash,
        "waived_check_result_id": check_result_id,
        "waived_human_verdict_id": human_verdict_id,
        "subject_kind": subject_kind,
        "subject_hash": subj_hash,
        "evidence_tuple_id": review_tuple_row["id"] if review_tuple_row is not None else None,
        "actor_identity": actor,
        "actor_role": actor_role,
        "reason": reason,
        "scope": scope,
        "compensating_controls": compensating_controls,
        "evidence_ids": canonical.canonical_json(list(evidence_ids)).decode(),
        "evidence_hashes": canonical.canonical_json(evidence_hashes).decode(),
        "issued_at": now,
        "expires_at": expires_at,
        "canonical_serialization_version": canonical.SERIALIZATION_VERSION,
    }
    row["content_hash"] = canonical.content_hash(row)
    waiver_id = record.insert(conn, "waiver", **row)

    # `tags._TARGET_TABLES` has no `waiver` entry yet, so this reports
    # against the ticket and names the waiver in the note; see the report
    # for the merge that should retarget it once that table is added.
    tags.tag(
        conn, target=f"ticket:{ticket_id}", kind="policy_exception", fm_id=POLICY_EXCEPTION_FM_ID,
        actor=actor, note=f"waiver:{waiver_id}", severity=entry.severity,
    )

    if subject_kind == "review_tuple":
        _resolve_shared_red_check(conn, ticket_id, check_result["stage_run_id"], waiver_id, now=now)

    return waiver_id


def _resolve_shared_red_check(
    conn: sqlite3.Connection, ticket_id: int, stage_run_id: int, waiver_id: int, *, now: str,
) -> None:
    """Resolve the open `red_check` item S5 opened for `stage_run_id`, once every blocking result on it clears."""
    if not cleared(conn, stage_run_id, now=now):
        return
    item = conn.execute(
        "SELECT * FROM queue_item WHERE ticket_id = ? AND kind = 'red_check' AND ref = ? AND resolved_at IS NULL",
        (ticket_id, f"stage_run:{stage_run_id}"),
    ).fetchone()
    if item is None:
        return
    from runner import queue

    queue.resolve_by_waiver(conn, item, waiver_id)


def validity(
    conn: sqlite3.Connection,
    waiver_id: int,
    *,
    now: str | None = None,
    owners_path: Path = owners.DEFAULT_OWNERS_PATH,
    policy_path: Path = DEFAULT_POLICY_PATH,
) -> Validity:
    """Whether `waiver_id` still permits advancement at `now`, every failing reason listed, none short-circuited.

    Checked independently: the row exists; it is not past `expires_at`;
    its recorded policy id/version/hash still match an entry the policy
    file on disk carries (`policy_changed`); its `actor_role` is still one
    that policy entry lists and `actor_identity` still holds it in
    `owners.yaml` (`lost_authority`); the subject recomputed right now
    equals the one stored at issuance (`subject_changed` -- for a
    review-tuple waiver this is what catches a fresh review tuple from a
    later fix round); and every evidence artefact's hash still matches
    what was recorded (`evidence_changed`). A missing waived row, or one
    that no longer carries `blind_spot`, is `subject_not_blind_spot` --
    structurally near-impossible against this schema's append-only rows,
    but checked rather than assumed.
    """
    row = record.get(conn, "waiver", waiver_id)
    if row is None:
        return Validity(False, ("no_such_waiver",))
    now = now or record.now()
    reasons: list[str] = []

    if row["expires_at"] <= now:
        reasons.append("expired")

    policy = load_policy(policy_path)
    entry = policy.entry(row["policy_id"]) if row["policy_id"] else None
    if entry is None or entry.version != row["policy_version"] or policy.policy_hash != row["policy_hash"]:
        reasons.append("policy_changed")

    owners_obj = owners.load_owners(owners_path)
    role_entry = owners_obj.roles.get(row["actor_role"]) if row["actor_role"] else None
    if (
        role_entry is None
        or role_entry["identity"] != row["actor_identity"]
        or entry is None
        or row["actor_role"] not in entry.roles
    ):
        reasons.append("lost_authority")

    if row["subject_kind"] == "review_tuple":
        check_result = (
            record.get(conn, "check_result", row["waived_check_result_id"])
            if row["waived_check_result_id"] is not None else None
        )
        if check_result is None or check_result["result"] not in WAIVABLE_RESULTS:
            reasons.append("subject_not_blind_spot")
        else:
            try:
                current = subject_hash(conn, check_result=check_result, owners_path=owners_path, policy_path=policy_path)
            except WaiverRefused:
                current = None
            if current is None or current != row["subject_hash"]:
                reasons.append("subject_changed")
    else:
        human_verdict = (
            record.get(conn, "human_verdict", row["waived_human_verdict_id"])
            if row["waived_human_verdict_id"] is not None else None
        )
        if human_verdict is None or human_verdict["verdict"] not in WAIVABLE_RESULTS:
            reasons.append("subject_not_blind_spot")
        else:
            current = subject_hash(conn, human_verdict=human_verdict, owners_path=owners_path, policy_path=policy_path)
            if current != row["subject_hash"]:
                reasons.append("subject_changed")

    evidence_ids = json.loads(row["evidence_ids"]) if row["evidence_ids"] else []
    evidence_hashes = json.loads(row["evidence_hashes"]) if row["evidence_hashes"] else []
    for evidence_id, stored_hash in zip(evidence_ids, evidence_hashes):
        artefact_row = record.get(conn, "artefact", evidence_id)
        if artefact_row is None or artefact_row["hash"] != stored_hash:
            reasons.append("evidence_changed")
            break

    return Validity(not reasons, tuple(reasons))


def waiver_for_result(conn: sqlite3.Connection, check_result_id: int, *, now: str | None = None) -> sqlite3.Row | None:
    """The newest valid waiver naming `check_result_id`, or None when no valid one does."""
    rows = conn.execute(
        "SELECT * FROM waiver WHERE waived_check_result_id = ? ORDER BY id DESC", (check_result_id,)
    ).fetchall()
    for row in rows:
        if validity(conn, row["id"], now=now).valid:
            return row
    return None


def effective_result(conn: sqlite3.Connection, check_result: sqlite3.Row, *, now: str | None = None) -> tuple[str, int | None]:
    """`(status, waiver_id)`: the stored result, or `("waived", id)` when a valid waiver covers a waivable result."""
    if check_result["result"] not in WAIVABLE_RESULTS:
        return check_result["result"], None
    waiver = waiver_for_result(conn, check_result["id"], now=now)
    if waiver is None:
        return check_result["result"], None
    return "waived", waiver["id"]


def blocking_status(conn: sqlite3.Connection, stage_run_id: int, *, now: str | None = None) -> list[dict]:
    """Every blocking-tier `check_result` of `stage_run_id`, in id order, with its effective status.

    Each entry carries the row's `id`, `check_name`, `content_hash`, the
    stored `result`, the effective `status` (`pass`, `fail`, `blind_spot`
    or `waived`) and the covering `waiver_id` when waived.
    """
    rows = conn.execute(
        "SELECT * FROM check_result WHERE stage_run_id = ? AND check_tier = 'blocking' ORDER BY id", (stage_run_id,)
    ).fetchall()
    entries = []
    for row in rows:
        status, waiver_id = effective_result(conn, row, now=now)
        entries.append({
            "id": row["id"], "check_name": row["check_name"], "content_hash": row["content_hash"],
            "result": row["result"], "status": status, "waiver_id": waiver_id,
        })
    return entries


def cleared(conn: sqlite3.Connection, stage_run_id: int, *, now: str | None = None) -> bool:
    """Whether every blocking result of `stage_run_id` is `pass` or validly `waived` at `now`."""
    entries = blocking_status(conn, stage_run_id, now=now)
    return bool(entries) and all(entry["status"] in ("pass", "waived") for entry in entries)


def recheck(conn: sqlite3.Connection, ticket_id: int, *, now: str | None = None) -> dict[int, Validity]:
    """Every waiver bound into `ticket_id`'s latest plan tuple and latest review tuple, each rechecked now.

    A plan-tuple waiver is one `runner.checklist.waiver_set` names -- every
    waiver over a `human_verdict` of this ticket, the same set the plan
    tuple's `plan_waiver_set_hash` binds. A review-tuple waiver is one
    naming a `check_result` bound (`evidence_tuple_id`) to the ticket's
    newest review tuple. The S6 driver and the dispatch path call this at
    their own recheck points; this module's own tests exercise it
    directly rather than through either caller.
    """
    from runner import checklist

    now = now or record.now()
    results: dict[int, Validity] = {}
    for waiver_row in checklist.waiver_set(conn, ticket_id):
        results[waiver_row["id"]] = validity(conn, waiver_row["id"], now=now)

    review_tuple = conn.execute(
        "SELECT * FROM evidence_tuple WHERE ticket_id = ? AND kind = 'review' ORDER BY id DESC LIMIT 1",
        (ticket_id,),
    ).fetchone()
    if review_tuple is not None:
        check_result_ids = [
            row["id"] for row in conn.execute(
                "SELECT id FROM check_result WHERE evidence_tuple_id = ?", (review_tuple["id"],)
            ).fetchall()
        ]
        if check_result_ids:
            placeholders = ",".join("?" for _ in check_result_ids)
            for row in conn.execute(
                f"SELECT id FROM waiver WHERE waived_check_result_id IN ({placeholders})", check_result_ids
            ).fetchall():
                results[row["id"]] = validity(conn, row["id"], now=now)
    return results
