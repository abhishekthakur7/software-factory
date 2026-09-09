"""The reconstructable invocation envelope: what one agent invocation is given, and how to prove it.

`build` assembles the envelope a fresh invocation receives: the ticket's
registered artefacts, the manifest entry's file hashes, the governance and
execution-boundary identities in force, and nothing from any earlier
invocation. `reconstruct` rebuilds the same shape afterward from the
governed record alone -- the `stage_run` row's own fields, the artefact
rows its `inputs` column names, and the ticket -- so an audit never has to
trust that the file a child process once read still matches what is
claimed today. Both return the same `Envelope` shape; `content_hash` is the
one hashing rule either caller uses, so a value written by `build` and one
recomputed by `reconstruct` are comparable byte for byte.

The manifest does not yet name, per stage, which artefact kinds a stage
reads (that lands with the manifest's full field set); until then, `build`
takes every one of the ticket's latest-version artefacts as its ordered
inputs, sorted by kind, rather than a stage-specific subset.
"""
import hashlib
import json
import shutil
import sqlite3
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from runner import canonical, record, recipes
from runner.paths import FACTORY_DIR, PROJECT_CONFIG, REPO_ROOT, RUNS_DIR

SANDBOX_PATH = FACTORY_DIR / "config" / "sandbox.yaml"

# Stages whose stage_run binds a plan- or review-approval subject; every
# other stage's envelope carries a null approval subject (R-I-15).
PLAN_BOUND_STAGES = frozenset({"S3"})
REVIEW_BOUND_STAGES = frozenset({"S5", "S6"})


class EnvelopeError(ValueError):
    """The envelope cannot be built or reconstructed: a config file is unreadable or malformed."""


@dataclass(frozen=True)
class InputRef:
    artefact_id: int
    kind: str
    hash: str
    guard_decision_id: int | None


@dataclass(frozen=True)
class Envelope:
    ticket_id: int
    stage: str
    inputs: tuple[InputRef, ...] = ()
    agent_hash: str | None = None
    skill_hash: str | None = None
    shared_skill_hashes: tuple[str, ...] = ()
    rubric_hash: str | None = None
    manifest_hash: str | None = None
    trust_profile_hash: str | None = None
    trust_approval_set_hash: str | None = None
    recipe_set_hash: str | None = None
    runtime_adapter: str | None = None
    runtime_version: str | None = None
    adapter_version: str | None = None
    tool_versions: dict = field(default_factory=dict)
    mcp_server_versions: dict = field(default_factory=dict)
    model_requested: str | None = None
    sandbox_digest: str | None = None
    toolchain_digest: str | None = None
    base_sha: str | None = None
    head_sha: str | None = None
    data_class: str | None = None
    tool_allowlist: tuple[str, ...] = ()
    approval_subject_hash: str | None = None
    # Unknown at build time (the invocation has not happened yet); recorded
    # once available from the worker's stdout payload, which the trusted
    # results/ directory keeps -- reconstruct reads it back from there.
    provider_request_id: str | None = None


def to_dict(envelope: Envelope) -> dict:
    """The canonical, order-preserving JSON-ready shape of `envelope`."""
    return {
        "ticket_id": envelope.ticket_id,
        "stage": envelope.stage,
        "inputs": [
            {
                "artefact_id": item.artefact_id,
                "kind": item.kind,
                "hash": item.hash,
                "guard_decision_id": item.guard_decision_id,
            }
            for item in envelope.inputs
        ],
        "agent_hash": envelope.agent_hash,
        "skill_hash": envelope.skill_hash,
        "shared_skill_hashes": list(envelope.shared_skill_hashes),
        "rubric_hash": envelope.rubric_hash,
        "manifest_hash": envelope.manifest_hash,
        "trust_profile_hash": envelope.trust_profile_hash,
        "trust_approval_set_hash": envelope.trust_approval_set_hash,
        "recipe_set_hash": envelope.recipe_set_hash,
        "runtime_adapter": envelope.runtime_adapter,
        "runtime_version": envelope.runtime_version,
        "adapter_version": envelope.adapter_version,
        "tool_versions": dict(envelope.tool_versions),
        "mcp_server_versions": dict(envelope.mcp_server_versions),
        "model_requested": envelope.model_requested,
        "sandbox_digest": envelope.sandbox_digest,
        "toolchain_digest": envelope.toolchain_digest,
        "base_sha": envelope.base_sha,
        "head_sha": envelope.head_sha,
        "data_class": envelope.data_class,
        "tool_allowlist": list(envelope.tool_allowlist),
        "approval_subject_hash": envelope.approval_subject_hash,
        "provider_request_id": envelope.provider_request_id,
    }


def content_hash(envelope: Envelope) -> str:
    """The canonical hash `stage_run.envelope_hash` stores for `envelope`."""
    return canonical.content_hash(to_dict(envelope), exclude=frozenset())


def sandbox_digest(policy_name: str, *, sandbox_path: Path = SANDBOX_PATH, stage: str, runs_dir: Path) -> str:
    """sha256 over every input that governs `stage`'s sandbox under `policy_name`.

    Hashes, in one canonical payload: both OS profile files' bytes, the
    stage's resolved proxy allowlist (route/host/port triples, not just
    route ids -- an endpoint's host or port changing must change the
    digest too), `sandbox_path`'s own bytes, the resolved environment
    allowlist, and the runs directory's resolved absolute location. Any of
    these can change what a run is actually permitted to do without
    `policy_name` itself changing, so each is bound into the digest rather
    than left for a caller to notice drifted on its own.
    """
    doc = yaml.safe_load(Path(sandbox_path).read_text())
    policies = doc.get("policies", {}) if isinstance(doc, dict) else {}
    if policy_name not in policies:
        raise EnvelopeError(f"{sandbox_path}: no such sandbox policy {policy_name!r}")
    policy = policies[policy_name]
    allowlist = tuple(policy.get("env_allowlist", []))

    endpoints = policy.get("endpoints", {})
    route_ids = policy.get("proxy_allowlist", {}).get(stage, [])
    proxy_triples = tuple(
        (route_id, endpoints[route_id]["host"], endpoints[route_id]["port"]) for route_id in route_ids
    )

    profile_bytes = b"".join(
        (REPO_ROOT / policy["os_profiles"][role]["path"]).read_bytes()
        for role in sorted(policy.get("os_profiles", {}))
    )

    payload = (
        Path(sandbox_path).read_bytes() + profile_bytes
        + canonical.canonical_json({
            "policy": policy_name,
            "env_allowlist": allowlist,
            "proxy_allowlist": proxy_triples,
            "runs_dir": str(Path(runs_dir).resolve()),
        })
    )
    return hashlib.sha256(payload).hexdigest()


def _detected_jdk_version() -> str | None:
    """The JDK version string `java -version` reports on `PATH`, or None when there is no `java`."""
    java = shutil.which("java")
    if java is None:
        return None
    result = subprocess.run([java, "-version"], capture_output=True, text=True)
    # `java -version` writes to stderr on every JDK distribution this
    # project has run against; stdout is not checked.
    first_line = (result.stderr or result.stdout or "").splitlines()[:1]
    return first_line[0].strip() if first_line else None


def toolchain_digest(toolchain: dict) -> str | None:
    """Canonical hash of `toolchain` plus the JDK version found on `PATH`; null only when no JDK is found."""
    jdk_version = _detected_jdk_version()
    if jdk_version is None and toolchain.get("jdk") is not None:
        # A toolchain names a JDK but none is on PATH: the digest is a
        # fact about what actually ran, never a guess from configuration,
        # so it stays null rather than echoing the declared version back.
        return None
    return canonical.content_hash({"toolchain": dict(toolchain), "jdk_on_path": jdk_version}, exclude=frozenset())


def recipe_set_hash(catalogue_path: Path = recipes.DEFAULT_CATALOGUE_PATH) -> str:
    """Canonical hash of the loaded recipe catalogue at `catalogue_path`."""
    catalogue = recipes.load_catalogue(catalogue_path)
    serializable = {
        recipe_id: {
            "executable": str(recipe.executable),
            "executable_digest": recipe.executable_digest,
            "cwd_role": recipe.cwd_role,
            "timeout_seconds": recipe.timeout_seconds,
            "expected_exit_codes": list(recipe.expected_exit_codes),
            "env_allowlist": list(recipe.env_allowlist),
        }
        for recipe_id, recipe in sorted(catalogue.items())
    }
    return canonical.content_hash({"recipes": serializable}, exclude=frozenset())


def _approval_subject_hash(conn: sqlite3.Connection, ticket_id: int, stage: str) -> str | None:
    if stage in PLAN_BOUND_STAGES:
        kind = "plan"
    elif stage in REVIEW_BOUND_STAGES:
        kind = "review"
    else:
        return None
    row = conn.execute(
        "SELECT content_hash FROM evidence_tuple WHERE ticket_id = ? AND kind = ? ORDER BY id DESC LIMIT 1",
        (ticket_id, kind),
    ).fetchone()
    return row["content_hash"] if row is not None else None


def _ordered_inputs(conn: sqlite3.Connection, ticket_id: int) -> tuple[InputRef, ...]:
    rows = conn.execute(
        "SELECT a.id, a.kind, a.hash, a.guard_decision_id FROM artefact a "
        "WHERE a.ticket_id = ? AND a.version = ("
        "SELECT MAX(a2.version) FROM artefact a2 WHERE a2.ticket_id = a.ticket_id AND a2.kind = a.kind"
        ") ORDER BY a.kind, a.id",
        (ticket_id,),
    ).fetchall()
    return tuple(
        InputRef(artefact_id=row["id"], kind=row["kind"], hash=row["hash"], guard_decision_id=row["guard_decision_id"])
        for row in rows
    )


def _named_inputs(conn: sqlite3.Connection, ticket_id: int, artefact_ids) -> tuple[InputRef, ...]:
    """The caller-chosen input set, in the caller's order; an id that is not this ticket's artefact is refused."""
    refs = []
    for artefact_id in artefact_ids:
        row = record.get(conn, "artefact", artefact_id)
        if row is None or row["ticket_id"] != ticket_id:
            raise EnvelopeError(f"artefact {artefact_id} is not an artefact of ticket {ticket_id}")
        refs.append(InputRef(artefact_id=row["id"], kind=row["kind"], hash=row["hash"], guard_decision_id=row["guard_decision_id"]))
    return tuple(refs)


def build(
    conn: sqlite3.Connection, ticket: sqlite3.Row, entry, *, adapter_version: str | None = None,
    sandbox_path: Path | None = None, input_artefact_ids=None, runs_dir: Path = RUNS_DIR,
) -> Envelope:
    """The envelope a fresh invocation of `entry.stage` for `ticket` receives.

    Built before the run's row opens, so the row can carry the envelope's
    identity fields and hash from its insert. `adapter_version` names the
    calling adapter module's own pinned version -- distinct from `entry`'s
    `runtime_version`, the SDK/CLI package version -- so this function
    stays adapter-agnostic rather than assuming which one is calling it.
    `input_artefact_ids` fixes the input set and its order when the stage
    driver knows exactly which artefacts this invocation reads (a
    restatement child reads one subject, S2 reads the source and the
    brief); left None, every latest-version artefact of the ticket is an
    input, sorted by kind. `runs_dir` feeds `sandbox_digest` only.
    """
    project = yaml.safe_load(Path(PROJECT_CONFIG).read_text())
    toolchain = dict(entry.toolchain) if entry.toolchain else dict(project.get("toolchain", {}))
    sandbox_path = sandbox_path if sandbox_path is not None else SANDBOX_PATH
    inputs = (
        _named_inputs(conn, ticket["id"], input_artefact_ids) if input_artefact_ids is not None
        else _ordered_inputs(conn, ticket["id"])
    )
    return Envelope(
        ticket_id=ticket["id"],
        stage=entry.stage,
        inputs=inputs,
        agent_hash=entry.agent_hash,
        skill_hash=entry.skill_hash,
        shared_skill_hashes=entry.shared_skill_hashes,
        rubric_hash=entry.rubric_hash,
        manifest_hash=entry.manifest_hash,
        trust_profile_hash=ticket["trust_profile_hash"],
        trust_approval_set_hash=ticket["trust_approval_set_hash"],
        recipe_set_hash=recipe_set_hash(),
        runtime_adapter=entry.runtime_adapter,
        runtime_version=entry.runtime_version,
        adapter_version=adapter_version,
        tool_versions={name: None for name in entry.tool_allowlist},
        mcp_server_versions={},
        model_requested=entry.model_requested,
        sandbox_digest=(
            sandbox_digest(entry.sandbox_policy, sandbox_path=sandbox_path, stage=entry.stage, runs_dir=runs_dir)
            if entry.sandbox_policy else None
        ),
        toolchain_digest=toolchain_digest(toolchain),
        base_sha=ticket["base_sha"],
        head_sha=ticket["head_sha"],
        data_class=ticket["data_class"],
        tool_allowlist=entry.tool_allowlist,
        approval_subject_hash=_approval_subject_hash(conn, ticket["id"], entry.stage),
    )


def locations(conn: sqlite3.Connection, ticket: sqlite3.Row, entry, envelope: Envelope) -> dict:
    """Where the worker finds each thing the envelope names by hash: the second, unhashed file an invocation receives.

    The envelope carries identities (hashes and ids) so it can be rebuilt
    from the record alone; the worker needs paths. Keeping the two apart
    means adding a path here never changes an envelope hash, and every
    path is derivable from the record (artefact rows carry their path,
    the manifest entry names its files) rather than being a second
    source of identity. Manifest paths are repository-relative and are
    resolved here so the worker never has to know the repository root.
    """
    def _abs(rel: str | None) -> str | None:
        return str(REPO_ROOT / rel) if rel else None

    inputs = []
    for ref in envelope.inputs:
        row = record.get(conn, "artefact", ref.artefact_id)
        inputs.append({"artefact_id": ref.artefact_id, "kind": ref.kind, "path": row["path"]})
    return {
        "agent": _abs(entry.agent),
        "skill": _abs(entry.skill),
        "shared_skills": [_abs(path) for path in entry.shared_skills],
        "rubric": _abs(entry.rubric),
        "inputs": inputs,
        "worktree_path": ticket["worktree_path"],
    }


def reconstruct(conn: sqlite3.Connection, stage_run_id: int, *, runs_dir: Path = RUNS_DIR) -> Envelope:
    """Rebuild the envelope `stage_run_id` was given, from its own row, the ticket, and the artefacts it names.

    Reads only what the record already holds: the `stage_run` row's own
    hash/version/digest fields (written at its insert from what `build`
    produced), the ticket row, and the
    artefact rows named by the run's own `inputs` column -- never the
    manifest file or the recipe catalogue again, since a later edit to
    either must not silently change what an already-run invocation is
    said to have received. `provider_request_id` is unknown until the
    invocation completes, so `build` never sets it; this reads it back
    from the run's own `results/stdout.json`, the one place the trusted
    runner keeps the worker's raw payload, when that file exists.
    """
    run = record.get(conn, "stage_run", stage_run_id)
    if run is None:
        raise EnvelopeError(f"no such stage_run: {stage_run_id}")
    ticket = record.get(conn, "ticket", run["ticket_id"])
    if ticket is None:
        raise EnvelopeError(f"stage_run {stage_run_id} names no such ticket: {run['ticket_id']}")

    input_ids = json.loads(run["inputs"]) if run["inputs"] else []
    inputs = []
    for artefact_id in input_ids:
        artefact = record.get(conn, "artefact", artefact_id)
        if artefact is None:
            raise EnvelopeError(f"stage_run {stage_run_id} names missing artefact {artefact_id}")
        inputs.append(
            InputRef(
                artefact_id=artefact["id"], kind=artefact["kind"], hash=artefact["hash"],
                guard_decision_id=artefact["guard_decision_id"],
            )
        )
    tool_allowlist = tuple(json.loads(run["tool_allowlist"])) if run["tool_allowlist"] else ()

    provider_request_id = None
    stdout_path = Path(runs_dir) / "tickets" / str(run["ticket_id"]) / "runs" / str(stage_run_id) / "results" / "stdout.json"
    if stdout_path.exists():
        stdout_payload = json.loads(stdout_path.read_text())
        if isinstance(stdout_payload, dict):
            provider_request_id = stdout_payload.get("provider_request_id")

    return Envelope(
        ticket_id=run["ticket_id"],
        stage=run["stage"],
        inputs=tuple(inputs),
        agent_hash=run["agent_ref"],
        skill_hash=run["skill_ref"],
        shared_skill_hashes=(),
        rubric_hash=run["rubric_ref"],
        manifest_hash=run["manifest_hash"],
        trust_profile_hash=run["trust_profile_hash"],
        trust_approval_set_hash=run["trust_approval_set_hash"],
        recipe_set_hash=run["recipe_set_hash"],
        runtime_adapter=run["runtime"],
        runtime_version=run["runtime_version"],
        adapter_version=run["adapter_version"],
        tool_versions={name: None for name in tool_allowlist},
        mcp_server_versions={},
        model_requested=run["model_requested"],
        sandbox_digest=run["sandbox_digest"],
        toolchain_digest=run["toolchain_digest"],
        base_sha=ticket["base_sha"],
        head_sha=ticket["head_sha"],
        data_class=ticket["data_class"],
        tool_allowlist=tool_allowlist,
        approval_subject_hash=_approval_subject_hash(conn, run["ticket_id"], run["stage"]),
        provider_request_id=provider_request_id,
    )
