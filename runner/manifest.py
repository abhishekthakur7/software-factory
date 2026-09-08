"""The manifest: what a stage and tier are entitled to run, resolved fail-closed.

`load` parses and validates `factory/manifest.yaml` end to end -- every
`files` entry, every stage's `default` entry and any tier override, the
null/non-null split between script-only stages (`S0`, `S5`, `S6`) and
agent-driven ones, and the budget-key shape of whichever `tiers.yaml` the
manifest's `budget` field names -- so a malformed manifest never reaches
`resolve`. Loading the real project manifest also refuses a stage entry
whose agent, skill, shared skill, rubric, or runtime adapter names an eval
directory that is missing, unowned, or carries an empty case list: an
empty fixture list never enters the manifest (`runner.evals.check`). A
synthetic test manifest loaded from outside the project's own `factory/`
root skips that check -- its stand-in files have no eval directory of
their own to fail. `resolve` merges a stage's `default` entry with its tier
override (if any), then re-verifies every file it names still hashes to
what the manifest declares before returning anything: an unresolved or
unavailable entry, or a file whose bytes have moved since the manifest was
written, raises `ManifestError` before a caller ever opens a stage run.
Neither function touches a database connection, so a resolution failure
is structurally incapable of leaving a stage run behind.

`current_hash` shells out to `factory/scripts/tools/manifest_hash` rather
than re-deriving its hashing rule, so the two can never drift apart. `migrate`
is the human-approved path that moves every open ticket onto a new manifest
hash: it always records one approval, under the `manifest` gate, for the
actor calling it; that approval counts toward the lone `factory_owner` slot's
quorum only when the actor actually holds that role in `owners.yaml`, so an
unauthorised call is recorded but leaves quorum unmet and no ticket touched.
"""
import hashlib
import re
import sqlite3
import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml

from runner import approvals, canonical, evals, owners, record, run_ledger, transitions
from runner.paths import FACTORY_DIR, REPO_ROOT
from runner.reviewer_sets import Slot
from runner.state_table import TERMINAL_STATES

MANIFEST_PATH = FACTORY_DIR / "manifest.yaml"
MANIFEST_HASH_SCRIPT = FACTORY_DIR / "scripts" / "tools" / "manifest_hash"

STAGES: tuple[str, ...] = ("S0", "S1", "S2", "S3", "S4", "S5", "S6")
TIERS: tuple[str, ...] = ("light", "standard", "heavy")

# The stages with no agent behind them: their manifest entry carries no
# agent, skill, or model identity, only the script-only infrastructure
# fields every stage shares (rubric, budget, sandbox, toolchain, ...).
NULL_MODEL_STAGES: frozenset[str] = frozenset({"S0", "S5", "S6"})

# Every field a stage's `default` entry must carry; a tier override may
# name any subset of these to override the default's value for that field
# alone. `restatement_model` is required in addition, but only on `S2`.
REQUIRED_ENTRY_FIELDS: tuple[str, ...] = (
    "agent", "skill", "shared_skills", "rubric", "tool_allowlist",
    "budget", "runtime_adapter", "runtime_version",
    "model_requested", "grader_model", "sandbox_policy", "toolchain",
)
_ALL_ENTRY_FIELDS: tuple[str, ...] = REQUIRED_ENTRY_FIELDS + ("restatement_model",)

# The only keys a budget mapping in tiers.yaml may carry, at any level
# (by_tier, a per-stage override, or s4_per_ticket).
ALLOWED_BUDGET_KEYS: frozenset[str] = frozenset({"tokens", "wall_clock_seconds"})

# An exact package version or digest, never a range: digits and dots only.
_EXACT_VERSION_RE = re.compile(r"^[0-9]+(\.[0-9]+)*$")

# The approval-record attestation this module stamps; a new attestation
# shape gets a new version rather than reinterpreting rows already written.
ATTESTATION_VERSION = "manifest-migrate-v1"

# The role a migration approval binds, and the quorum required before a
# migration takes effect: one distinct `factory_owner` approval.
_MIGRATION_ROLE = "factory_owner"


class ManifestError(ValueError):
    """The manifest fails validation, or a stage/tier can't be resolved from it, fail-closed."""


@dataclass(frozen=True)
class Manifest:
    """A validated `manifest.yaml`: its declared files, its per-stage entries, and the tree they resolve against."""

    version: int
    files: dict[str, str]  # path -> content_hash
    stages: dict[str, dict[str, dict]]  # stage -> {"default": {...}, tier: {...}}
    root: Path


@dataclass(frozen=True)
class Entry:
    """One stage-and-tier's resolved entitlement: its merged fields, the hashes backing them, and the manifest hash."""

    stage: str
    tier: str
    agent: str | None
    skill: str | None
    shared_skills: tuple[str, ...]
    rubric: str | None
    tool_allowlist: tuple[str, ...]
    budget_source: str
    budget: dict
    runtime_adapter: str | None
    runtime_version: str | None
    model_requested: str | None
    grader_model: str | None
    sandbox_policy: str | None
    toolchain: dict
    restatement_model: str | None
    agent_hash: str | None
    skill_hash: str | None
    shared_skill_hashes: tuple[str, ...]
    rubric_hash: str | None
    manifest_hash: str


def _load_files(entries: object, path: Path) -> dict[str, str]:
    if not isinstance(entries, list) or not entries:
        raise ManifestError(f"{path}: manifest 'files' must be a non-empty list")
    files: dict[str, str] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ManifestError(f"{path}: manifest entry is not a mapping: {entry!r}")
        file_path, content_hash = entry.get("path"), entry.get("content_hash")
        if not isinstance(file_path, str) or not file_path:
            raise ManifestError(f"{path}: manifest entry missing 'path': {entry!r}")
        if not isinstance(content_hash, str) or not content_hash:
            raise ManifestError(f"{path}: manifest entry missing 'content_hash': {entry!r}")
        if Path(file_path).is_absolute() or ".." in Path(file_path).parts:
            raise ManifestError(f"{path}: manifest entry path is unsafe: {file_path}")
        if not file_path.startswith("factory/"):
            raise ManifestError(f"{path}: manifest entry path is outside factory/: {file_path}")
        files[file_path] = content_hash
    return files


def _check_known_keys(stage: str, name: str, entry: dict, path: Path) -> None:
    unknown = set(entry) - set(_ALL_ENTRY_FIELDS)
    if unknown:
        raise ManifestError(f"{path}: stage {stage!r} entry {name!r} has unknown field(s) {sorted(unknown)}")
    if "restatement_model" in entry and stage != "S2":
        raise ManifestError(f"{path}: stage {stage!r} entry {name!r} names 'restatement_model' outside S2")


def _check_required_keys(stage: str, entry: dict, path: Path) -> None:
    required = REQUIRED_ENTRY_FIELDS + (("restatement_model",) if stage == "S2" else ())
    missing = [field_name for field_name in required if field_name not in entry]
    if missing:
        raise ManifestError(f"{path}: stage {stage!r} default entry missing field(s) {missing}")


def _is_exact_version(value: object) -> bool:
    return isinstance(value, str) and bool(_EXACT_VERSION_RE.fullmatch(value))


def _validate_field_types(stage: str, name: str, entry: dict, path: Path) -> None:
    def _fail(message: str) -> None:
        raise ManifestError(f"{path}: stage {stage!r} entry {name!r}: {message}")

    for key in (
        "agent", "skill", "rubric", "runtime_adapter", "runtime_version",
        "model_requested", "grader_model", "sandbox_policy", "budget", "restatement_model",
    ):
        if key in entry and entry[key] is not None and not isinstance(entry[key], str):
            _fail(f"{key!r} must be a string or null")
    if "shared_skills" in entry:
        value = entry["shared_skills"]
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            _fail("'shared_skills' must be a list of strings")
    if "tool_allowlist" in entry:
        value = entry["tool_allowlist"]
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            _fail("'tool_allowlist' must be a list of strings")
    if "toolchain" in entry:
        value = entry["toolchain"]
        if not isinstance(value, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in value.items()
        ):
            _fail("'toolchain' must be a mapping of strings")
    if "runtime_version" in entry and entry["runtime_version"] is not None and not _is_exact_version(
        entry["runtime_version"]
    ):
        _fail("'runtime_version' must be an exact version, not a range")


def _check_referenced_files(stage: str, name: str, entry: dict, files: dict[str, str], path: Path) -> None:
    for key in ("agent", "skill", "rubric", "budget"):
        value = entry.get(key)
        if value is not None and value not in files:
            raise ManifestError(
                f"{path}: stage {stage!r} entry {name!r} references {key} {value!r}, absent from 'files'"
            )
    for value in entry.get("shared_skills", []):
        if value not in files:
            raise ManifestError(
                f"{path}: stage {stage!r} entry {name!r} references shared skill {value!r}, absent from 'files'"
            )


def _check_entry_eval_dirs(stage: str, name: str, entry: dict, root: Path, path: Path) -> None:
    # Only the real project manifest is checked here -- a synthetic test
    # manifest under a fixture root names tiny stand-in agent/skill/rubric
    # files with no eval directory of their own, and would fail this check
    # for a reason that has nothing to do with what that fixture is
    # actually testing.
    factory_root = root / "factory"
    for field_name in ("agent", "skill", "rubric"):
        value = entry.get(field_name)
        if value is not None:
            eval_dir = evals.eval_dir_for_file(value, root=factory_root)
            _check_referenced_eval_dir(stage, name, field_name, eval_dir, path)
    for value in entry.get("shared_skills", []):
        eval_dir = evals.eval_dir_for_file(value, root=factory_root)
        _check_referenced_eval_dir(stage, name, "shared_skills", eval_dir, path)
    adapter = entry.get("runtime_adapter")
    if adapter is not None:
        eval_dir = evals.eval_dir_for_adapter(adapter, root=factory_root)
        _check_referenced_eval_dir(stage, name, "runtime_adapter", eval_dir, path)


def _check_referenced_eval_dir(stage: str, name: str, field_name: str, eval_dir: Path, path: Path) -> None:
    try:
        evals.check(eval_dir)
    except evals.EvalDirectoryError as exc:
        raise ManifestError(
            f"{path}: stage {stage!r} entry {name!r} field {field_name!r} references an incomplete eval "
            f"directory: {exc}"
        ) from exc


def _check_null_invariant(stage: str, entry: dict, description: str) -> None:
    must_be_null = stage in NULL_MODEL_STAGES
    for field_name in ("agent", "skill", "model_requested", "grader_model"):
        value = entry.get(field_name)
        if must_be_null and value is not None:
            raise ManifestError(f"{description}: stage {stage!r} field {field_name!r} must be null")
        if not must_be_null and value is None:
            raise ManifestError(f"{description}: stage {stage!r} field {field_name!r} must not be null")


def _check_budget_key_set(mapping: object, description: str) -> None:
    if not isinstance(mapping, dict):
        raise ManifestError(f"{description} is not a mapping")
    unknown = set(mapping) - ALLOWED_BUDGET_KEYS
    if unknown:
        raise ManifestError(
            f"{description} names budget key(s) outside {sorted(ALLOWED_BUDGET_KEYS)}: {sorted(unknown)}"
        )


def _validate_budget_keys(root: Path, budget_rel_path: str, path: Path) -> None:
    budget_file = root / budget_rel_path
    try:
        budget_doc = yaml.safe_load(budget_file.read_text())
    except OSError as exc:
        raise ManifestError(f"{path}: cannot read budget source {budget_rel_path!r}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ManifestError(f"{path}: budget source {budget_rel_path!r} is not valid YAML: {exc}") from exc
    if not isinstance(budget_doc, dict):
        raise ManifestError(f"{path}: budget source {budget_rel_path!r} is not a mapping")
    budgets = budget_doc.get("budgets", {})
    for tier_name, tier_budget in budgets.get("by_tier", {}).items():
        _check_budget_key_set(tier_budget, f"{path}: {budget_rel_path} budgets.by_tier.{tier_name}")
    for stage_name, stage_override in budgets.get("overrides", {}).items():
        _check_budget_key_set(stage_override, f"{path}: {budget_rel_path} budgets.overrides.{stage_name}")
    for tier_name, tier_budget in budget_doc.get("s4_per_ticket", {}).items():
        _check_budget_key_set(tier_budget, f"{path}: {budget_rel_path} s4_per_ticket.{tier_name}")


def _load_stages(stages_raw: object, files: dict[str, str], root: Path, path: Path) -> dict[str, dict]:
    if not isinstance(stages_raw, dict):
        raise ManifestError(f"{path}: manifest 'stages' must be a mapping")
    missing_stages = [stage for stage in STAGES if stage not in stages_raw]
    if missing_stages:
        raise ManifestError(f"{path}: manifest 'stages' is missing stage(s) {missing_stages}")

    budget_paths: set[str] = set()
    stages: dict[str, dict] = {}
    for stage in STAGES:
        stage_raw = stages_raw[stage]
        if not isinstance(stage_raw, dict) or "default" not in stage_raw:
            raise ManifestError(f"{path}: stage {stage!r} has no 'default' entry")
        variants: dict[str, dict] = {}
        for variant_name, variant_raw in stage_raw.items():
            if variant_name != "default" and variant_name not in TIERS:
                raise ManifestError(f"{path}: stage {stage!r} names unknown tier {variant_name!r}")
            if not isinstance(variant_raw, dict):
                raise ManifestError(f"{path}: stage {stage!r} entry {variant_name!r} is not a mapping")
            _check_known_keys(stage, variant_name, variant_raw, path)
            _validate_field_types(stage, variant_name, variant_raw, path)
            _check_referenced_files(stage, variant_name, variant_raw, files, path)
            if root == REPO_ROOT:
                _check_entry_eval_dirs(stage, variant_name, variant_raw, root, path)
            if variant_name == "default":
                _check_required_keys(stage, variant_raw, path)
                _check_null_invariant(stage, variant_raw, f"{path}")
                budget_paths.add(variant_raw["budget"])
            variants[variant_name] = variant_raw
        stages[stage] = variants

    for budget_path in budget_paths:
        _validate_budget_keys(root, budget_path, path)
    return stages


def load(path: Path = MANIFEST_PATH) -> Manifest:
    """Parse and fully validate `path`, raising `ManifestError` on the first problem found."""
    path = Path(path)
    try:
        text = path.read_text()
    except OSError as exc:
        raise ManifestError(f"cannot read {path}: {exc}") from exc
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ManifestError(f"{path}: manifest is not valid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ManifestError(f"{path}: manifest is not a mapping")
    version = data.get("version")
    if not isinstance(version, int):
        raise ManifestError(f"{path}: manifest 'version' must be an integer")
    files = _load_files(data.get("files"), path)
    root = path.resolve().parent.parent
    stages = _load_stages(data.get("stages"), files, root, path)
    return Manifest(version=version, files=files, stages=stages, root=root)


def resolve(manifest: Manifest, stage: str, tier: str) -> Entry:
    """The fully merged, hash-verified entitlement for `stage` at `tier`.

    Merges the stage's `default` entry with its `tier` override (if any),
    re-checks the null/non-null invariant on the merged result, then
    re-hashes every file the merged entry names against the manifest's
    declared hash for it. Any of that failing raises `ManifestError`
    before this function returns -- and since neither this function nor
    `load` ever takes a database connection, nothing here can open a
    stage run on a resolution that fails.
    """
    if stage not in manifest.stages:
        raise ManifestError(f"unknown stage: {stage!r}")
    if tier not in TIERS:
        raise ManifestError(f"unknown tier: {tier!r}")
    variants = manifest.stages[stage]
    merged = {**variants["default"], **variants.get(tier, {})}
    description = f"resolve({stage!r}, {tier!r})"
    _check_null_invariant(stage, merged, description)

    def _verify(rel_path: str | None) -> str | None:
        if rel_path is None:
            return None
        declared = manifest.files.get(rel_path)
        if declared is None:
            raise ManifestError(f"{description}: {rel_path!r} is not in manifest 'files'")
        absolute = manifest.root / rel_path
        try:
            actual = hashlib.sha256(absolute.read_bytes()).hexdigest()
        except OSError as exc:
            raise ManifestError(f"{description}: cannot read {rel_path!r}: {exc}") from exc
        if actual != declared:
            raise ManifestError(f"{description}: on-disk hash of {rel_path!r} no longer matches its manifest hash")
        return declared

    agent_hash = _verify(merged.get("agent"))
    skill_hash = _verify(merged.get("skill"))
    rubric_hash = _verify(merged.get("rubric"))
    shared_skill_hashes = tuple(_verify(item) for item in merged.get("shared_skills", []))
    _verify(merged.get("budget"))

    return Entry(
        stage=stage,
        tier=tier,
        agent=merged.get("agent"),
        skill=merged.get("skill"),
        shared_skills=tuple(merged.get("shared_skills", [])),
        rubric=merged.get("rubric"),
        tool_allowlist=tuple(merged.get("tool_allowlist", [])),
        budget_source=merged["budget"],
        budget=run_ledger.budget(stage, tier),
        runtime_adapter=merged.get("runtime_adapter"),
        runtime_version=merged.get("runtime_version"),
        model_requested=merged.get("model_requested"),
        grader_model=merged.get("grader_model"),
        sandbox_policy=merged.get("sandbox_policy"),
        toolchain=dict(merged.get("toolchain", {})),
        restatement_model=merged.get("restatement_model"),
        agent_hash=agent_hash,
        skill_hash=skill_hash,
        shared_skill_hashes=shared_skill_hashes,
        rubric_hash=rubric_hash,
        manifest_hash=current_hash(manifest.root),
    )


def current_hash(root: Path = REPO_ROOT) -> str:
    """The manifest hash `factory/scripts/tools/manifest_hash` would print for `root`'s committed tree.

    Shells out to the script itself rather than re-deriving its rule, so
    the two can never quietly drift apart. Raises `ManifestError` on
    anything the script refuses: an uncommitted edit, a validation
    failure, or a tree with no git history at all.
    """
    result = subprocess.run(
        [str(MANIFEST_HASH_SCRIPT), "--root", str(root)], capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise ManifestError(result.stderr.strip() or "manifest_hash script failed")
    return result.stdout.strip()


def migrate(
    conn: sqlite3.Connection,
    *,
    actor: str,
    note: str | None = None,
    root: Path = REPO_ROOT,
    owners_path: Path = owners.DEFAULT_OWNERS_PATH,
) -> str:
    """Move every open ticket onto the current manifest hash, once a `factory_owner` has approved it.

    Always records one `approval_record` on the `manifest` gate for
    `actor`, under `_MIGRATION_ROLE`: `decision` is `approve` only when
    `actor` actually holds that role in `owners.yaml` right now, else
    `reject` -- an unauthorised call is still recorded, but never
    qualifies for the slot's quorum. Quorum is one distinct `factory_owner`
    approval; when it holds, every ticket outside `TERMINAL_STATES` whose
    `factory_manifest_hash` differs from the new hash is migrated: one
    `check_result` names the ids of its artefacts registered from `S1`
    onward (the artefacts themselves are untouched, append-only rows),
    `transitions.apply` returns it to `context` through the
    `migrate_manifest` event, and `factory_manifest_hash` is re-pinned.
    Without quorum, only the approval row is written; no ticket changes.
    """
    new_hash = current_hash(root)
    owners_doc = owners.load_owners(owners_path)
    authority_hash = owners.authority_policy_hash(owners_path)
    snapshot_hash = canonical.content_hash(owners.identity_snapshot(owners_doc, actor))
    slot = Slot(source_rule="manifest", role=_MIGRATION_ROLE)
    holds_role = owners_doc.roles.get(_MIGRATION_ROLE, {}).get("identity") == actor
    approvals.record_approval(
        conn,
        gate="manifest",
        subject_hash=new_hash,
        slot_id=slot.slot_id,
        actor_identity=actor,
        role=_MIGRATION_ROLE,
        decision="approve" if holds_role else "reject",
        authority_policy_hash=authority_hash,
        membership_snapshot_hash=snapshot_hash,
        attestation_version=ATTESTATION_VERSION,
        attestation_hash=canonical.content_hash({"manifest_hash": new_hash, "actor": actor, "note": note}),
    )
    quorum = approvals.evaluate(conn, gate="manifest", subject_hash=new_hash, slots=[slot])
    if not quorum.satisfied:
        return f"manifest migration to {new_hash} is waiting on approval ({'; '.join(quorum.reasons)})"

    migrated: list[int] = []
    for ticket in conn.execute("SELECT * FROM ticket").fetchall():
        if ticket["state"] in TERMINAL_STATES or ticket["factory_manifest_hash"] == new_hash:
            continue
        artefact_ids = [
            row["id"]
            for row in conn.execute(
                "SELECT a.id FROM artefact a JOIN stage_run sr ON sr.id = a.stage_run_id "
                "WHERE a.ticket_id = ? AND sr.stage != ? ORDER BY a.id",
                (ticket["id"], "S0"),
            ).fetchall()
        ]
        row = {
            "stage_run_id": None,
            "check_name": "manifest_migration",
            "check_tier": "blocking",
            "source": "runner",
            "result": "fail",
            "summary": f"manifest migrated to {new_hash}; invalidates artefact(s) {artefact_ids}",
            "canonical_serialization_version": canonical.SERIALIZATION_VERSION,
        }
        row["content_hash"] = canonical.content_hash(row)
        record.insert(conn, "check_result", **row)
        transitions.apply(conn, ticket["id"], "migrate_manifest")
        record.update(conn, "ticket", ticket["id"], factory_manifest_hash=new_hash)
        migrated.append(ticket["id"])
    return f"manifest migrated to {new_hash}; ticket(s) {migrated} returned to context"
