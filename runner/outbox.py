"""The transactional outbox: every external write is an `external_write` intent row before it is anything else.

`create_intent` is the one writer of new intent rows. It computes the
operation's idempotency key from the row's own key columns, stores the
payload as a governed artefact with its digest, refuses a second intent that
would carry a different payload under an existing key, refuses to create
anything under a key whose earlier row is still ambiguously `sending`, and
supersedes the ticket's older pending intents for the same operation. It
never commits: the caller owns the transaction, which is what lets the
quorum-completing approval and the intent it authorises land together or
not at all.

`intent_for_review_quorum` is that caller's hook: given a ticket, it
evaluates the current review subject's quorum and, when it is satisfied,
creates the `pr_create` (no pull request yet) or `pr_update` (one exists)
intent for it, returning the existing intent when one already binds the
same subject and approval set.

`dispatch` performs exactly one intent: it guards the payload, hands it to
the route's deliverer, guards the receipt the deliverer returns, and
stores both the receipt artefact and the row's new state -- `reconciled`
on success, `failed` with `last_error` on a guard deny or a refused remote
call. `reconcile_pending` is what every state-advancing command calls
first: it resolves the ticket's `sending` rows by asking the deliverer
what it already knows before touching anything `pending`, so a row a
crashed attempt left ambiguous is never raced against a fresh one under
the same key. `_dispatch_pending` repeats the base-freshness check one
last time, right before ever calling `dispatch`, for a `pr_create`/
`pr_update` row that reaches that point: a target that moved after S5
preflight approved the candidate supersedes the intent instead of ever
reaching the deliverer.
"""
import json
import sqlite3
from pathlib import Path
from typing import Mapping

from runner import artefact_registry, canonical, freshness, guard, owners, queue, record, transitions, trust_profile, waivers
from runner import project
from runner.deliverers import Deliverer, GitHubDeliverer, SlackDeliverer, SlackMCPPostTool, SlackMCPUnavailable, StubDeliverer
from runner.trust_profile import Route
from runner.deliverers.github import GitHubNonRetryable
from runner.deliverers.stub import Receipt, RemoteRefused
from runner.fs import write_text
from runner.paths import RUNS_DIR
from runner.project import DEFAULT_PROJECT_CONFIG_PATH as DEFAULT_PROJECT_CONFIG
from runner.schema import EXTERNAL_WRITE_OPERATIONS

def deliverer_for(route: Route, runs_dir: Path) -> Deliverer:
    """A live route never falls back to a local fixture receipt."""
    if route.deliverer == "stub":
        return StubDeliverer(Path(runs_dir) / "remote" / f"{route.id}.json")
    if route.deliverer == "live" and route.id == "github_scratch":
        if project.load().get("scratch_repository", {}).get("remote"):
            return GitHubDeliverer(runs_dir=runs_dir)
        raise GitHubNonRetryable("scratch repository remote is not configured")
    if route.deliverer == "live" and route.id == "slack_digest":
        digest = project.load().get("digest", {})
        if digest.get("channel") and digest.get("mcp_post_tool") and all((digest.get("mcp_post_arguments") or {}).get(key) for key in ("channel", "text")):
            return SlackDeliverer(SlackMCPPostTool(digest["mcp_post_tool"], digest["mcp_post_arguments"]))
        raise SlackMCPUnavailable("Slack channel and MCP post-tool binding are not configured")
    if route.deliverer == "live":
        raise NotImplementedError(f"no live deliverer exists yet for route {route.id!r}")
    raise ValueError(f"unknown deliverer kind {route.deliverer!r} for route {route.id!r}")


PR_OPERATIONS: frozenset[str] = frozenset({"pr_create", "pr_update"})

# The scratch repository is the only one a pull request can actually reach
# today: the pilot repository's own route (`github_pilot`) has no
# real GitHub repository behind it yet. One constant, not a literal at
# each call site, so the day the pilot repository is real, retargeting
# every PR operation is a one-line change.
GITHUB_ROUTE_ID = "github_scratch"

# The route every operation dispatches through -- fixed by what each route
# admits (`trust-profile.yaml`'s route `operations` field), not derived at
# call time, so a caller can never send an operation through the wrong
# route by naming one explicitly.
ROUTE_FOR_OPERATION: dict[str, str] = {
    "pr_create": GITHUB_ROUTE_ID,
    "pr_update": GITHUB_ROUTE_ID,
    "digest": "slack_digest",
    "jira_feedback": "jira_feedback",
}


class InjectedCrash(Exception):
    """A test asked `dispatch` to stop at one of its three crash-injection points."""

# The `external_write` columns each operation's idempotency key is taken
# over. A pull-request intent is keyed by what it publishes and where; an
# update is further keyed by the pull request it updates and the remote
# head it expects to find. The digest and Jira feedback are keyed by their
# content alone, so re-running the same digest sends nothing twice.
KEY_COLUMNS: dict[str, tuple[str, ...]] = {
    "pr_create": (
        "review_approval_subject_hash",
        "repository",
        "target_ref",
        "head_ref",
        "desired_remote_head_sha",
        "pr_body_hash",
    ),
    "pr_update": (
        "remote_pr_identity",
        "review_approval_subject_hash",
        "repository",
        "target_ref",
        "head_ref",
        "desired_remote_head_sha",
        "expected_prior_remote_head_sha",
        "pr_body_hash",
    ),
    "digest": ("digest_channel", "cadence_slot", "payload_digest"),
    "jira_feedback": ("ticket_id", "payload_digest"),
}


class IntentRefused(Exception):
    """The intent cannot be created without breaking the one-key-one-payload or reconcile-first rule."""


def idempotency_key(operation: str, row: Mapping) -> str:
    """The canonical hash over `operation` and its `KEY_COLUMNS` values in `row`."""
    return canonical.content_hash(
        {"operation": operation, **{name: row.get(name) for name in KEY_COLUMNS[operation]}}
    )


def _store_payload(
    conn: sqlite3.Connection, ticket_id: int | None, key: str, payload: Mapping, runs_dir: Path
) -> int:
    root = runs_dir / "tickets" / str(ticket_id) / "outbox" if ticket_id is not None else runs_dir / "outbox"
    path = root / f"{key}.json"
    write_text(path, canonical.canonical_json(dict(payload)).decode() + "\n")
    return artefact_registry.register(conn, ticket_id=ticket_id, kind="outbox_payload", path=path)


def create_intent(
    conn: sqlite3.Connection,
    *,
    ticket_id: int | None,
    operation: str,
    payload: Mapping,
    runs_dir: Path = RUNS_DIR,
    stage_run_id: int | None = None,
    review_tuple_id: int | None = None,
    review_approval_subject_hash: str | None = None,
    review_approval_set_hash: str | None = None,
    publication_target_hash: str | None = None,
    repository: str | None = None,
    target_ref: str | None = None,
    head_ref: str | None = None,
    desired_remote_head_sha: str | None = None,
    expected_prior_remote_head_sha: str | None = None,
    remote_pr_identity: str | None = None,
    digest_channel: str | None = None,
    cadence_slot: str | None = None,
) -> int:
    """Insert one `pending` intent for `operation` and return its id, or the id of the row its key already names.

    Raises `IntentRefused` when a row under the same key carries a different
    payload digest, or when one is still `sending`. Creating the intent
    marks the ticket's older `pending` rows for the same operation
    `superseded`. The caller commits.
    """
    if operation not in EXTERNAL_WRITE_OPERATIONS:
        raise ValueError(f"unknown external_write operation: {operation!r}")
    row = {
        "ticket_id": ticket_id,
        "stage_run_id": stage_run_id,
        "operation": operation,
        "payload_digest": canonical.content_hash({"payload": dict(payload)}),
        "review_tuple_id": review_tuple_id,
        "review_approval_subject_hash": review_approval_subject_hash,
        "review_approval_set_hash": review_approval_set_hash,
        # A caller that already computed the canonical publication-target
        # hash (`runner.publication.publication_target`) passes it
        # explicitly; a direct low-level caller naming only a repository
        # and target ref gets this narrower stand-in instead, since this
        # module has no ticket to derive the full target from.
        "publication_target_hash": publication_target_hash or (
            canonical.content_hash({"repository": repository, "target_ref": target_ref})
            if repository is not None else None
        ),
        "repository": repository,
        "target_ref": target_ref,
        "head_ref": head_ref,
        "desired_remote_head_sha": desired_remote_head_sha,
        "expected_prior_remote_head_sha": expected_prior_remote_head_sha,
        "pr_body_hash": (
            canonical.content_hash({"pr_body": payload["pr_body"]}) if "pr_body" in payload else None
        ),
        "remote_pr_identity": remote_pr_identity,
        "digest_channel": digest_channel,
        "cadence_slot": cadence_slot,
    }
    key = idempotency_key(operation, row)

    for existing in conn.execute(
        "SELECT * FROM external_write WHERE idempotency_key = ? ORDER BY id", (key,)
    ):
        if existing["payload_digest"] != row["payload_digest"]:
            raise IntentRefused(f"idempotency key {key} already carries a different payload")
        if existing["state"] == "sending":
            raise IntentRefused(f"intent {existing['id']} is still sending; reconcile it first")
        if existing["state"] in ("pending", "reconciled"):
            return existing["id"]

    if ticket_id is not None:
        for stale in conn.execute(
            "SELECT id FROM external_write WHERE ticket_id = ? AND operation = ? AND state = 'pending'",
            (ticket_id, operation),
        ).fetchall():
            record.update(conn, "external_write", stale["id"], state="superseded")

    revision = None
    if operation in PR_OPERATIONS:
        revision = 1 + conn.execute(
            "SELECT COUNT(*) FROM external_write WHERE ticket_id = ? "
            "AND operation IN ('pr_create', 'pr_update') AND state = 'reconciled'",
            (ticket_id,),
        ).fetchone()[0]

    return record.insert(
        conn,
        "external_write",
        **row,
        idempotency_key=key,
        payload_artefact_id=_store_payload(conn, ticket_id, key, payload, runs_dir),
        revision=revision,
        state="pending",
        attempt_count=0,
        created_at=record.now(),
    )


def _pr_body(conn: sqlite3.Connection, ticket_id: int) -> str:
    """The text of the ticket's latest `pr_body` artefact, else its latest `packet`, else empty."""
    for kind in ("pr_body", "packet"):
        artefact = artefact_registry.latest(conn, ticket_id, kind)
        if artefact is not None:
            return Path(artefact["path"]).read_text()
    return ""


def intent_for_review_quorum(
    conn: sqlite3.Connection,
    ticket_id: int,
    *,
    runs_dir: Path = RUNS_DIR,
    project_path: Path = DEFAULT_PROJECT_CONFIG,
    now: str | None = None,
    owners_path: Path = owners.DEFAULT_OWNERS_PATH,
) -> int | None:
    """The pull-request intent the ticket's current review quorum authorises, or None while quorum is unmet.

    Evaluates `runner.publication.quorum` -- the review-approval subject
    plus the authority check plain `approvals.evaluate` does not make --
    and, on satisfaction, creates the `pr_update`/`pr_create` intent
    `runner.publication.publication_target` names, keyed by the subject
    quorum was actually satisfied on rather than the bare review-tuple
    hash. Any waiver currently bound into the ticket's plan or review
    tuple that `waivers.recheck` finds invalid also withholds the intent,
    the same way an unmet quorum does. Never commits, so a caller that
    records the quorum-completing approval first lands both in one
    transaction.
    """
    from runner import publication

    ticket = record.get(conn, "ticket", ticket_id)
    if ticket is None:
        raise LookupError(f"no such ticket: {ticket_id}")

    invalid_waivers = any(not validity.valid for validity in waivers.recheck(conn, ticket_id, now=now).values())
    if invalid_waivers:
        return None

    try:
        review_quorum = publication.quorum(conn, ticket_id, now=now, owners_path=owners_path, project_path=project_path)
    except publication.PublicationSubjectIncomplete:
        return None
    if not review_quorum.satisfied:
        return None

    subject = publication.review_approval_subject(conn, ticket_id, now=now, project_path=project_path)
    target = publication.publication_target(conn, ticket, project_path=project_path)
    review_tuple = conn.execute(
        "SELECT id FROM evidence_tuple WHERE ticket_id = ? AND kind = 'review' ORDER BY id DESC LIMIT 1",
        (ticket_id,),
    ).fetchone()

    return create_intent(
        conn,
        ticket_id=ticket_id,
        operation=target.operation,
        payload={
            "branch_ref": ticket["branch"],
            "head_sha": ticket["head_sha"],
            "target_ref": target.target_ref,
            "pr_body": _pr_body(conn, ticket_id),
        },
        runs_dir=runs_dir,
        review_tuple_id=review_tuple["id"] if review_tuple is not None else None,
        review_approval_subject_hash=subject.hash,
        review_approval_set_hash=review_quorum.approval_set_hash,
        publication_target_hash=target.hash,
        repository=target.repository,
        target_ref=target.target_ref,
        head_ref=target.head_ref,
        desired_remote_head_sha=target.desired_head_sha,
        expected_prior_remote_head_sha=target.expected_prior_remote_head_sha,
        remote_pr_identity=target.pr_identity,
    )


def _load_payload(conn: sqlite3.Connection, write: sqlite3.Row) -> dict:
    artefact = record.get(conn, "artefact", write["payload_artefact_id"])
    return json.loads(Path(artefact["path"]).read_text())


def _guard_outbox(
    conn: sqlite3.Connection,
    write: sqlite3.Row,
    route: trust_profile.Route,
    payload: object,
    *,
    profile_path: Path,
    owners_path: Path,
    now: str | None,
) -> guard.Decision:
    return guard.decide(
        conn,
        guard.Operation(
            crossing="outbox",
            route_id=route.id,
            payload=payload,
            input_classes=("internal",),
            source_identity="factory_outbox",
            destination_identity=route.provider,
            ticket_id=write["ticket_id"],
            content_provenance={
                "source_identity": "factory_outbox",
                "destination_identity": route.provider,
                "crossing": "outbox",
            },
        ),
        profile_path=profile_path,
        owners_path=owners_path,
        now=now,
    )


def route_and_deliverer(route_id: str, *, profile_path: Path, runs_dir: Path):
    """The trust profile's `route_id` route and that route's deliverer.

    Public so a caller outside the outbox -- the observed-outcome locator
    read, which has no `external_write` intent to dispatch by operation --
    can resolve the same GitHub route (`GITHUB_ROUTE_ID`) and deliverer
    `_route_and_deliverer` below resolves for a pull-request intent.
    """
    route = trust_profile.load_trust_profile(profile_path).routes[route_id]
    return route, deliverer_for(route, runs_dir)


def _route_and_deliverer(write: sqlite3.Row, *, profile_path: Path, runs_dir: Path):
    """The trust-profile route `write`'s operation dispatches through, and that route's deliverer."""
    return route_and_deliverer(ROUTE_FOR_OPERATION[write["operation"]], profile_path=profile_path, runs_dir=runs_dir)


def _receipt_from_pull_request(write: sqlite3.Row, identity: str, pr: Mapping, now: str | None) -> Receipt:
    """A receipt for an open remote pull request `write` is being reconciled to, as if it had been issued for it."""
    return Receipt(
        remote_identity=identity, remote_pr_identity=identity, remote_head_sha=pr["head_sha"],
        body_hash=pr["body_hash"], payload_digest=write["payload_digest"],
        idempotency_key=write["idempotency_key"], created_at=now or record.now(),
    )


def _receipt_root(runs_dir: Path, ticket_id: int | None) -> Path:
    return runs_dir / "tickets" / str(ticket_id) / "outbox" if ticket_id is not None else runs_dir / "outbox"


def _apply_ticket_update(conn: sqlite3.Connection, write: sqlite3.Row, receipt: Receipt) -> None:
    """On a reconciled `pr_create`/`pr_update`, advance the ticket's remote-publication fields.

    `factory_completed_at` is stamped only the first time a ticket ever
    reconciles a pull-request intent -- once set it is never moved again,
    since it marks the first successful create, not the latest revision.
    """
    ticket = record.get(conn, "ticket", write["ticket_id"])
    fields = {
        "pr_identity": receipt.remote_pr_identity,
        "pr_url": receipt.remote_identity,
        "last_remote_head_sha": receipt.remote_head_sha,
        "last_pr_body_hash": receipt.body_hash,
    }
    if ticket["factory_completed_at"] is None:
        fields["factory_completed_at"] = record.now()
    record.update(conn, "ticket", write["ticket_id"], **fields)


def _finalize_receipt(
    conn: sqlite3.Connection,
    write: sqlite3.Row,
    receipt: Receipt,
    *,
    runs_dir: Path,
    profile_path: Path,
    owners_path: Path,
    now: str | None,
    fault: str | None = None,
) -> None:
    """Guard `receipt`, store it as a governed artefact, and mark `write` reconciled.

    The receipt's own field names (identities and hashes) do not appear in
    any route's field allowlist, which exists to police what an *outbound*
    payload may carry -- so the guard call here is fail-closed enforcement
    (a deny stops the write) and the source of the receipt artefact's
    `guard_decision_id`, never a projection substituted for the receipt's
    actual content.
    """
    route, _ = _route_and_deliverer(write, profile_path=profile_path, runs_dir=runs_dir)
    decision = _guard_outbox(
        conn, write, route, receipt.to_json(), profile_path=profile_path, owners_path=owners_path, now=now,
    )
    try:
        guard.pass_through(conn, decision, "outbox")
    except guard.GuardRefused as exc:
        record.update(
            conn, "external_write", write["id"], state="failed", last_error=str(exc), guard_decision_id=decision.id,
        )
        conn.commit()
        return

    receipt_path = _receipt_root(runs_dir, write["ticket_id"]) / f"{write['idempotency_key']}.receipt.json"
    write_text(receipt_path, canonical.canonical_json(receipt.to_json()).decode() + "\n")
    receipt_artefact_id = artefact_registry.register(
        conn, ticket_id=write["ticket_id"], kind="receipt", path=receipt_path, guard_decision_id=decision.id,
    )
    record.update(
        conn, "external_write", write["id"], state="reconciled",
        remote_identity=receipt.remote_identity, remote_pr_identity=receipt.remote_pr_identity,
        receipt_artefact_id=receipt_artefact_id, guard_decision_id=decision.id,
    )
    if write["operation"] in PR_OPERATIONS:
        _apply_ticket_update(conn, write, receipt)

    if fault == "before_local_commit":
        raise InjectedCrash(fault)
    conn.commit()


def dispatch(
    conn: sqlite3.Connection,
    intent_id: int,
    *,
    fault: str | None = None,
    runs_dir: Path = RUNS_DIR,
    profile_path: Path = trust_profile.DEFAULT_TRUST_PROFILE_PATH,
    owners_path: Path = owners.DEFAULT_OWNERS_PATH,
    now: str | None = None,
) -> None:
    """Perform one `pending` intent: guard its payload, deliver it, guard and store the receipt.

    Ends in `reconciled` on success or `failed` with `last_error` on a
    guard deny or a refused remote call. `fault` names one of three points
    -- `before_send`, `after_remote_success`, `before_local_commit` -- at
    which this raises `InjectedCrash` right after the real side effect
    that precedes it, for a test to prove reconciliation recovers from a
    crash at each. Nothing here decides *whether* `intent_id` should be
    sent yet; the reconcile-first checks that decide that for a `pending`
    row live in `reconcile_pending`, which calls this only once they pass.
    """
    write = record.get(conn, "external_write", intent_id)
    if write is None:
        raise LookupError(f"no such external_write intent: {intent_id}")
    operation = write["operation"]
    try:
        route, deliverer = _route_and_deliverer(write, profile_path=profile_path, runs_dir=runs_dir)
    except GitHubNonRetryable as exc:
        _escalate_nonretryable_github_failure(conn, write, str(exc))
        return
    except RemoteRefused as exc:
        _fail(conn, write["id"], str(exc))
        return
    payload = _load_payload(conn, write)

    decision = _guard_outbox(
        conn, write, route, payload, profile_path=profile_path, owners_path=owners_path, now=now,
    )
    try:
        passed_payload = guard.pass_through(conn, decision, "outbox")
    except guard.GuardRefused as exc:
        record.update(
            conn, "external_write", intent_id, state="failed", last_error=str(exc), guard_decision_id=decision.id,
        )
        conn.commit()
        return

    if fault == "before_send":
        raise InjectedCrash(fault)

    record.update(
        conn, "external_write", intent_id, state="sending",
        guard_decision_id=decision.id, attempt_count=write["attempt_count"] + 1,
    )
    conn.commit()

    try:
        receipt = getattr(deliverer, operation)(write, passed_payload)
    except GitHubNonRetryable as exc:
        record.update(conn, "external_write", intent_id, state="failed", last_error=str(exc))
        ticket = record.get(conn, "ticket", write["ticket_id"])
        if ticket is not None and (ticket["state"], "escalate") in transitions.TABLE:
            transitions.apply(conn, ticket["id"], "escalate")
        conn.commit()
        return
    except RemoteRefused as exc:
        record.update(conn, "external_write", intent_id, state="failed", last_error=str(exc))
        conn.commit()
        return

    if fault == "after_remote_success":
        raise InjectedCrash(fault)

    write = record.get(conn, "external_write", intent_id)
    _finalize_receipt(
        conn, write, receipt, runs_dir=runs_dir, profile_path=profile_path, owners_path=owners_path,
        now=now, fault=fault,
    )


def _reconcile_sending(
    conn: sqlite3.Connection, write: sqlite3.Row, *, runs_dir: Path, profile_path: Path, owners_path: Path, now,
) -> None:
    """Adopt a `sending` receipt, retaining an unobservable digest as ambiguous.

    The idempotency key is checked first, since every deliverer operation
    stores its receipt under that key in the same call that performs the
    remote effect; the pull-request identity lookup is the fallback for a
    `pr_create`/`pr_update` row whose crash landed before that receipt
    lookup could have found anything by key alone. Slack cannot look up a
    digest by that key, so its absent receipt cannot safely mean the post
    failed; it remains `sending` for operator resolution. Other operations
    return to `pending` when their remote state shows no prior effect.
    """
    _, deliverer = _route_and_deliverer(write, profile_path=profile_path, runs_dir=runs_dir)
    receipt = deliverer.receipt_for_key(write["idempotency_key"])
    if receipt is None and write["operation"] in PR_OPERATIONS and write["repository"] and write["head_ref"]:
        found = deliverer.open_pull_request(write["repository"], write["head_ref"])
        if found is not None:
            receipt = _receipt_from_pull_request(write, *found, now)
    if receipt is None:
        if write["operation"] == "digest":
            # Slack cannot look up a post by our idempotency key, so resending
            # after a crash could duplicate a message. Preserve the ambiguity
            # for an operator instead of reopening the intent automatically.
            return
        record.update(conn, "external_write", write["id"], state="pending")
        conn.commit()
        return
    _finalize_receipt(
        conn, write, receipt, runs_dir=runs_dir, profile_path=profile_path, owners_path=owners_path, now=now,
    )


def _fail(conn: sqlite3.Connection, write_id: int, reason: str) -> None:
    record.update(conn, "external_write", write_id, state="failed", last_error=reason)
    conn.commit()


def _escalate_nonretryable_github_failure(conn: sqlite3.Connection, write: sqlite3.Row, reason: str) -> None:
    """Record a GitHub authority/control refusal and escalate when the ticket still has an escalation transition."""
    record.update(conn, "external_write", write["id"], state="failed", last_error=reason)
    ticket = record.get(conn, "ticket", write["ticket_id"])
    if ticket is not None and (ticket["state"], "escalate") in transitions.TABLE:
        transitions.apply(conn, ticket["id"], "escalate")
    conn.commit()


def _dispatch_pending(
    conn: sqlite3.Connection, write: sqlite3.Row, *, runs_dir: Path, profile_path: Path, owners_path: Path, now,
    project_path: Path = DEFAULT_PROJECT_CONFIG,
) -> None:
    """A `pending` row: reconcile a `pr_create`/`pr_update` against the remote before ever sending it.

    An existing open pull request whose head and body already match what
    this intent wants published is adopted rather than recreated; an
    existing branch at neither the expected prior head nor the desired one
    fails the row without ever calling the deliverer, so an unexpected
    remote head is never overwritten. Anything else -- no branch yet, or
    one already at the expected head -- repeats the `BEFORE_DISPATCH`
    freshness check immediately before `dispatch`, which is the only path
    that ever calls the deliverer: a stale result supersedes the row with
    no call to the deliverer at all, since a receipt over stale evidence
    would be worse than no receipt.
    """
    operation = write["operation"]
    if operation not in PR_OPERATIONS:
        dispatch(conn, write["id"], runs_dir=runs_dir, profile_path=profile_path, owners_path=owners_path, now=now)
        return

    repository, head_ref = write["repository"], write["head_ref"]

    try:
        _, deliverer = _route_and_deliverer(write, profile_path=profile_path, runs_dir=runs_dir)
        existing = deliverer.open_pull_request(repository, head_ref)
    except GitHubNonRetryable as exc:
        _escalate_nonretryable_github_failure(conn, write, str(exc))
        return
    if existing is not None:
        identity, pr = existing
        if pr.get("state") != "open":
            already_raised = conn.execute(
                "SELECT id FROM queue_item WHERE ticket_id = ? AND kind = 'pr_outcome' AND resolved_at IS NULL",
                (write["ticket_id"],),
            ).fetchone()
            if already_raised is None:
                queue.open_item(
                    conn, ticket_id=write["ticket_id"], kind="pr_outcome", ref=f"pull_request:{identity}",
                )
            record.update(conn, "external_write", write["id"], state="superseded", last_error="remote_pull_request_closed")
            conn.commit()
            return
        if pr["head_sha"] == write["desired_remote_head_sha"] and pr["body_hash"] == write["pr_body_hash"]:
            _finalize_receipt(
                conn, write, _receipt_from_pull_request(write, identity, pr, now), runs_dir=runs_dir,
                profile_path=profile_path, owners_path=owners_path, now=now,
            )
            return

    if operation == "pr_create":
        try:
            current_head = deliverer.branch_head(repository, head_ref)
        except GitHubNonRetryable as exc:
            _escalate_nonretryable_github_failure(conn, write, str(exc))
            return
        if current_head is not None and current_head != write["expected_prior_remote_head_sha"]:
            _fail(conn, write["id"], "unexpected_remote_head")
            return
    else:
        ticket = record.get(conn, "ticket", write["ticket_id"])
        try:
            current_head = deliverer.branch_head(repository, head_ref)
        except GitHubNonRetryable as exc:
            _escalate_nonretryable_github_failure(conn, write, str(exc))
            return
        if current_head != ticket["last_remote_head_sha"]:
            _fail(conn, write["id"], "unexpected_remote_head")
            return

    fresh = freshness.check(
        conn, write["ticket_id"], boundary=freshness.BEFORE_DISPATCH,
        target_branch=freshness.target_branch(project_path), runs_dir=runs_dir,
    )
    if not fresh.fresh:
        record.update(conn, "external_write", write["id"], state="superseded", last_error="; ".join(fresh.reasons))
        conn.commit()
        return

    dispatch(conn, write["id"], runs_dir=runs_dir, profile_path=profile_path, owners_path=owners_path, now=now)


def reconcile_pending(
    conn: sqlite3.Connection,
    ticket_id: int,
    *,
    runs_dir: Path = RUNS_DIR,
    profile_path: Path = trust_profile.DEFAULT_TRUST_PROFILE_PATH,
    owners_path: Path = owners.DEFAULT_OWNERS_PATH,
    now: str | None = None,
) -> list[int]:
    """Reconcile every `sending` row for `ticket_id`, oldest first, then every `pending` one.

    Every state-advancing command calls this before touching ticket state.
    `sending` rows go first because an ambiguous row must resolve before a
    fresh intent is ever created or sent under its key; `pending` rows are
    re-read one at a time since resolving an earlier one (a supersede, or
    the ticket fields a reconciled `pr_create` moves) can change what a
    later one should do. Returns the ids of every row this call acted on.
    """
    acted: list[int] = []
    for row in conn.execute(
        "SELECT id FROM external_write WHERE ticket_id = ? AND state = 'sending' ORDER BY id", (ticket_id,)
    ).fetchall():
        write = record.get(conn, "external_write", row["id"])
        if write["state"] != "sending":
            continue
        _reconcile_sending(conn, write, runs_dir=runs_dir, profile_path=profile_path, owners_path=owners_path, now=now)
        acted.append(row["id"])

    for row in conn.execute(
        "SELECT id FROM external_write WHERE ticket_id = ? AND state = 'pending' ORDER BY id", (ticket_id,)
    ).fetchall():
        write = record.get(conn, "external_write", row["id"])
        if write["state"] != "pending":
            continue
        _dispatch_pending(conn, write, runs_dir=runs_dir, profile_path=profile_path, owners_path=owners_path, now=now)
        acted.append(row["id"])
    return acted
