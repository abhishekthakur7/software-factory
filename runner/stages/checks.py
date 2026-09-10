"""Run this stage's ordered checks against one preflight-bound review tuple.

Recipes execute in disposable base/head sandboxes; trusted comparisons consume
retained evidence and immutable checkouts. Source integrity is rechecked on every
exit. Ordinary red results do not stop later checks. New recipe failures enter
the bounded repair loop when eligible; independent failures and unavailable
evidence share one review queue item, with blind spots governed by waiver policy.
"""
import fnmatch
from contextlib import contextmanager
import json
import os
import re
import sqlite3
import subprocess
from pathlib import Path

import yaml

from runner import (
    approvals, artefact_registry, artefacts, binding, canonical, checklist, freshness, git_trees, owners, plan_tuple,
    project, queue, record, recipes, reviewer_sets, transitions,
)
from runner.checks import exclusion, regression_only
from runner.fs import write_bytes, write_text
from runner.paths import FACTORY_DIR, REPO_ROOT, RUNS_DIR
from runner.sandbox import copies as sandbox_copies

# `Test strategy.criteria`'s `AC-n` shape -- the only criteria cell the
# both-views rerun treats as a real behaviour claim; a `no_behaviour_change`
# task id names anything else and is exempt from the rerun.
_AC_ID_RE = re.compile(r"^AC-\d+$")

ARTEFACT_KIND = "check_evidence"
PASS_EVENT = None

# The blocking checks follow this order after preflight and project recipes.
# The implementation hand-off names this list as the check policies the implementer
# will face, so the two never disagree about what the checks stage enforces.
CHECK_ORDER: tuple[str, ...] = (
    "regression_only",
    "base_test_diff",
    "security_checks",
    "dep_verify",
    "size_gate",
    "scope_diff",
    "source_declaration_diff",
    "behavior_contract_evidence",
    "approval_binding",
)

_SCRIPTS_DIR = REPO_ROOT / "factory" / "scripts" / "checks"
SIZE_GATE_SCRIPT = _SCRIPTS_DIR / "size_gate"
SCOPE_DIFF_SCRIPT = _SCRIPTS_DIR / "scope_diff"
SOURCE_DECLARATION_DIFF_SCRIPT = _SCRIPTS_DIR / "source_declaration_diff"
BEHAVIOR_CONTRACT_EVIDENCE_SCRIPT = _SCRIPTS_DIR / "behavior_contract_evidence"
BASE_TEST_DIFF_SCRIPT = _SCRIPTS_DIR / "base_test_diff"
DEP_VERIFY_SCRIPT = _SCRIPTS_DIR / "dep_verify"

TIERS_PATH = FACTORY_DIR / "config" / "tiers.yaml"
LIMITS_PATH = FACTORY_DIR / "config" / "limits.yaml"

_RAN_LINE = re.compile(r"^ran: (?P<fqcn>[\w.$]+)#(?P<method>\w+)$")
_FAILED_LINE = re.compile(r"^FAILED: (?P<method>\w+):")


def _tier(ticket: sqlite3.Row) -> str:
    return ticket["tier_final"] or ticket["tier_provisional"] or "standard"


def _run_dir(runs_dir: Path, ticket_id: int, stage_run_id: int) -> Path:
    return Path(runs_dir) / "tickets" / str(ticket_id) / "runs" / str(stage_run_id)


def _repo(runs_dir: Path, ticket_id: int) -> Path:
    return Path(runs_dir) / "tickets" / str(ticket_id) / "repo"


def _project_config() -> dict:
    return project.pilot()


def _limits_config() -> dict:
    return yaml.safe_load(Path(LIMITS_PATH).read_text())


def _scope_paths(plan_text: str) -> list[str]:
    """The plan's `Scope and discretion` `touch`/`create`/`delete` paths; a `discretion` glob contributes nothing."""
    section = artefacts.parse(plan_text).section("Scope and discretion")
    rows = section.table() if section is not None else None
    return [row["path"] for row in (rows or []) if row.get("action") in ("touch", "create", "delete") and row.get("path")]


def _record_check_result(
    conn: sqlite3.Connection, stage_run_id: int, *, check_name: str, result: str, summary: str,
    evidence_tuple_id: int | None = None, evidence_artefact: int | None = None, check_tier: str = "blocking",
) -> int:
    row = {
        "stage_run_id": stage_run_id, "check_name": check_name, "check_tier": check_tier, "source": "runner",
        "result": result, "summary": summary, "evidence_tuple_id": evidence_tuple_id,
        "evidence_artefact": evidence_artefact, "canonical_serialization_version": canonical.SERIALIZATION_VERSION,
    }
    row["content_hash"] = canonical.content_hash(row)
    return record.insert(conn, "check_result", **row)


def _latest_plan_tuple(conn: sqlite3.Connection, ticket_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM evidence_tuple WHERE ticket_id = ? AND kind = 'plan' ORDER BY id DESC LIMIT 1", (ticket_id,)
    ).fetchone()


def _planned_slots(conn: sqlite3.Connection, plan_row: sqlite3.Row) -> list[reviewer_sets.Slot]:
    row = conn.execute(
        "SELECT * FROM reviewer_set WHERE ticket_id = ? AND kind = 'planned' AND content_hash = ? ORDER BY id DESC LIMIT 1",
        (plan_row["ticket_id"], plan_row["planned_reviewer_set_hash"]),
    ).fetchone()
    if row is None:
        return []
    return [reviewer_sets.Slot.from_json(item) for item in json.loads(row["slots"] or "[]")]


def _diff_touched_paths(repo: Path, base_sha: str, head_sha: str) -> list[str]:
    completed = subprocess.run(
        ["git", "-C", str(repo), "diff", "--name-only", base_sha, head_sha], capture_output=True, text=True, check=True,
    )
    return [line for line in completed.stdout.splitlines() if line.strip()]


def _preflight(
    conn: sqlite3.Connection, ticket: sqlite3.Row, stage_run_id: int, *, plan_text: str, runs_dir: Path,
):
    """The checks stage's preflight: one review tuple, or `(None, (outcome, failure_kind))` naming the refusal."""
    if not ticket["branch"] or not ticket["head_sha"] or not ticket["worktree_path"]:
        # A real hand-back always writes branch, head_sha and worktree_path together
        # (see implementation's own hand-back recorder); a ticket reaching `checks` without all
        # three recorded never completed one, so this is a structural defect rather
        # than a stale binding. Sending it back to `implementing` costs nothing extra
        # to bound: the ordinary per-task loop it resumes in already carries its own
        # verification-attempt cap.
        _record_check_result(
            conn, stage_run_id, check_name="review_tuple_preflight", result="fail",
            summary="ticket carries no recorded hand-back branch, head_sha, or worktree_path",
        )
        transitions.apply(conn, ticket["id"], "checks_bad_handback")
        return None, "fail"

    fresh = freshness.check(
        conn, ticket["id"], boundary=freshness.CHECKS_PREFLIGHT, target_branch=freshness.target_branch(), runs_dir=runs_dir,
    )
    if not fresh.fresh:
        return None, ("fail", "stale_binding")

    plan_row = _latest_plan_tuple(conn, ticket["id"])
    if plan_row is None:
        _record_check_result(conn, stage_run_id, check_name="review_tuple_preflight", result="fail", summary="no plan tuple is recorded for this ticket")
        return None, ("fail", "stale_binding")

    repo = _repo(runs_dir, ticket["id"])
    diff_paths = _diff_touched_paths(repo, plan_row["base_sha"], ticket["head_sha"])
    owners_obj = owners.load_owners()
    planned_slots = _planned_slots(conn, plan_row)

    actual = reviewer_sets.derive_actual(
        conn, ticket_id=ticket["id"], repo_path=repo, target_base_sha=ticket["target_base_sha"],
        changed_paths=diff_paths, owners=owners_obj, sensitive_paths=exclusion.load_sensitive_paths(),
        authority_policy_hash=owners.authority_policy_hash(),
        membership_snapshot_hash=canonical.content_hash(
            owners.identity_snapshot(owners_obj, owners_obj.roles["plan_reviewer"]["identity"])
        ),
    )
    if actual.blocked:
        # An unresolved, non-sensitive slot needs no transition of its own:
        # `checks_gate` already routes on this same `reviewer_set` row's
        # unresolved slot (the row `derive_actual` just wrote) the next
        # time the ticket is advanced. A sensitive path re-triggers pilot
        # exclusion only when the plan's own scope already declared it;
        # otherwise it routes back to implementation for a bounded round that removes
        # the accidental touch.
        if actual.sensitive:
            plan_paths = _scope_paths(plan_text)
            try:
                event = exclusion.decide_at_checks(plan_paths=plan_paths, diff_paths=diff_paths)
            except ValueError:
                event = None
            if event == "checks_sensitive_path_required":
                _record_check_result(
                    conn, stage_run_id, check_name="exclusion", result="fail",
                    summary=f"sensitive path required by the plan's own scope: {', '.join(actual.unresolved) or diff_paths}",
                )
                exclusion.apply_recorded_exclusion(conn, ticket["id"])
                return None, "fail"
            if event == "checks_removal_return":
                offending = [
                    path for path in diff_paths
                    if path not in plan_paths and exclusion.surfaces_in_paths([path])
                ]
                evidence_path = _run_dir(runs_dir, ticket["id"], stage_run_id) / "removal_evidence.json"
                write_text(evidence_path, json.dumps({"offending_paths": offending}, sort_keys=True))
                evidence_id = artefact_registry.register(
                    conn, ticket_id=ticket["id"], kind=ARTEFACT_KIND, path=evidence_path, stage_run_id=stage_run_id,
                )
                _record_check_result(
                    conn, stage_run_id, check_name="exclusion", result="fail",
                    summary=f"accidental touch of a sensitive path not required by the plan's own scope: {', '.join(offending) or diff_paths}",
                    evidence_artefact=evidence_id,
                )
                # A second, advisory marker naming the round implementation must run --
                # the same shape `_apply_routing` leaves for a fix round
                # (`fix_round_route`), so implementation's driver tells the two routes
                # apart by reading the latest checks run's own check results
                # rather than by guessing from the `exclusion` failure text.
                _record_check_result(
                    conn, stage_run_id, check_name="removal_route", check_tier="advisory", result="pass",
                    summary="accidental sensitive-path touch routes to a bounded implementation removal round",
                )
                transitions.apply(conn, ticket["id"], "checks_removal_return")
                return None, "fail"
        return None, ("fail", "structural")

    effective_id = reviewer_sets.effective_set(conn, ticket_id=ticket["id"], planned=planned_slots, actual=actual)
    quorum = approvals.evaluate(conn, gate="plan", subject_hash=plan_row["content_hash"], slots=planned_slots)
    current_plan = plan_tuple.derive_components(conn, ticket)

    components = binding.ReviewComponents(
        plan_tuple_id=plan_row["id"],
        plan_approval_set_hash=quorum.approval_set_hash,
        head_sha=ticket["head_sha"],
        diff_hash=fresh.diff_hash,
        deviation_set_hash=binding.deviation_set_hash(conn, ticket["id"]),
        target_base_sha=ticket["target_base_sha"],
        actual_reviewer_set_id=actual.id,
        actual_reviewer_set_hash=record.get(conn, "reviewer_set", actual.id)["content_hash"],
        effective_reviewer_set_id=effective_id,
        effective_reviewer_set_hash=record.get(conn, "reviewer_set", effective_id)["content_hash"],
        manifest_hash=current_plan.manifest_hash,
        project_config_hash=current_plan.project_config_hash,
        trust_profile_hash=current_plan.trust_profile_hash,
        trust_approval_set_hash=current_plan.trust_approval_set_hash,
        recipe_hash=current_plan.recipe_hash,
        sandbox_digest=current_plan.sandbox_digest,
        toolchain_digest=current_plan.toolchain_digest,
    )
    try:
        review_tuple_id = binding.preflight_review_tuple(
            conn, ticket["id"], plan_tuple_id=plan_row["id"], plan_slots=planned_slots,
            components=components, current_plan=current_plan,
        )
    except binding.PreflightRefused as exc:
        _record_check_result(conn, stage_run_id, check_name="review_tuple_preflight", result="fail", summary=exc.reason)
        return None, ("fail", "stale_binding")

    return {"review_tuple_id": review_tuple_id, "plan_row": plan_row, "planned_slots": planned_slots, "components": components, "repo": repo}, None


def _vendor_classpath(project_cfg: dict) -> str:
    """Every jar already materialised under `project.yaml`'s configured vendor path, or `""` when none has been built yet."""
    vendor_dir = REPO_ROOT / project_cfg["vendor"]
    if not vendor_dir.is_dir():
        return ""
    return os.pathsep.join(str(p) for p in sorted(vendor_dir.rglob("*.jar")))


def _checkouts(repo: Path, base_sha: str, head_sha: str, run_dir: Path) -> tuple[Path, Path]:
    checkouts_dir = run_dir / "checkouts"
    base_checkout = git_trees.plain_checkout(repo, base_sha, checkouts_dir / "base")
    head_checkout = git_trees.plain_checkout(repo, head_sha, checkouts_dir / "head")
    return base_checkout, head_checkout


class SandboxIntegrityError(RuntimeError):
    """The build boundary or immutable source failed its integrity check."""


@contextmanager
def _checked_copies(conn, stage_run_id, review_tuple_id, *, base_sha, head_sha, **kwargs):
    """Dispose views on every exit and record source drift before allowing any result to proceed."""
    try:
        with sandbox_copies.provisioned(stage_run_id=stage_run_id, **kwargs) as views:
            yield views
    finally:
        if not all((
            sandbox_copies.recheck(kwargs["base_checkout"], base_sha),
            sandbox_copies.recheck(kwargs["head_checkout"], head_sha),
        )):
            _record_check_result(
                conn, stage_run_id, check_name="sandbox_integrity", result="fail",
                summary="immutable checkout changed during copy-backed checks", evidence_tuple_id=review_tuple_id,
            )
            raise SandboxIntegrityError("immutable checkout changed during copy-backed checks")


def _recipe_status(result: recipes.RecipeResult) -> str:
    if result.outcome == "unavailable":
        return "blind_spot"
    if result.outcome != "pass":
        return "fail"
    return result.reported_result or "pass"


def _run_recipes(
    conn: sqlite3.Connection, ticket_id: int, stage_run_id: int, *, catalogue, project_recipes: list[str],
    base_copy: Path, head_copy: Path, run_dir: Path, review_tuple_id: int, vendor_classpath: str,
) -> tuple[dict, list[tuple[str, str, int]], Path]:
    """Run every project recipe at base and head; return `(recipe_results, blocking, results_dir)`.

    `blocking` carries only the ungoverned recipes' head results (a unit
    test blocks on any head red on its own); a governed recipe's raw
    result is recorded for evidence but never entered here, since
    `regression_only` alone decides whether it actually blocks.
    """
    results_dir = run_dir / "recipes"
    recipe_results: dict[str, dict] = {}
    blocking: list[tuple[str, str, int]] = []
    prior_evidence = artefact_registry.latest(conn, ticket_id, ARTEFACT_KIND)
    vendor_dir = REPO_ROOT / _project_config()["vendor"]

    for recipe_id in project_recipes:
        recipe = catalogue[recipe_id]
        recipe_results[recipe_id] = {}
        for side, checkout in (("base", base_copy), ("head", head_copy)):
            values = {"vendor_classpath": vendor_classpath, "vendor": str(vendor_dir), "pom": "pom.xml"}
            try:
                result = recipes.run(
                    recipe_id, values, catalogue=catalogue,
                    cwd_roles={"checkout": checkout}, results_dir=results_dir / side, env_source=os.environ,
                    sandbox_run_dir=run_dir / "sandbox" / side / recipe_id, sandbox_stage="checks",
                    sandbox_vendor_dir=vendor_dir,
                )
            except recipes.RecipeUnavailable as exc:
                evidence_path = results_dir / side / f"{recipe_id}.unavailable.json"
                write_text(evidence_path, json.dumps({"result": "blind_spot", "unmet_dependency": str(exc)}))
                result = recipes.RecipeResult(
                    recipe_id=recipe_id, outcome="unavailable", exit_code=None, stdout_path=evidence_path,
                    stderr_path=None, level=recipe.level, reported_result="blind_spot",
                )
            except recipes.RecipeSandboxError as exc:
                _record_check_result(
                    conn, stage_run_id, check_name="sandbox_integrity", result="fail", summary=str(exc),
                    evidence_tuple_id=review_tuple_id,
                )
                raise SandboxIntegrityError(str(exc)) from exc
            recipe_results[recipe_id][side] = result

            evidence_id = None
            if result.stdout_path is not None:
                evidence_id = artefact_registry.register(
                    conn, ticket_id=ticket_id, kind=ARTEFACT_KIND, path=result.stdout_path,
                    stage_run_id=stage_run_id, supersedes=prior_evidence["id"] if prior_evidence is not None else None,
                )
                prior_evidence = record.get(conn, "artefact", evidence_id)

            outcome = _recipe_status(result)
            payload = None
            if result.stdout_path is not None:
                try:
                    payload = json.loads(result.stdout_path.read_text().splitlines()[-1])
                except (IndexError, json.JSONDecodeError):
                    pass
            governed_kind = regression_only.recipe_governed_kind(kind=recipe.kind, level=recipe.level)
            is_blocking = side == "head" and (governed_kind is None or outcome == "blind_spot")
            cr_id = _record_check_result(
                conn, stage_run_id, check_name=f"recipe:{recipe_id}@{side}", result=outcome,
                summary=json.dumps(payload or {"outcome": result.outcome, "exit_code": result.exit_code}, sort_keys=True),
                evidence_tuple_id=review_tuple_id, evidence_artefact=evidence_id,
                # Governed failures use regression comparison; an unavailable head
                # remains blocking because comparison cannot fill an evidence gap.
                check_tier="blocking" if is_blocking else "advisory",
            )
            if is_blocking:
                blocking.append((f"recipe:{recipe_id}@head", outcome, cr_id))

    return recipe_results, blocking, results_dir


def _recipe_output_text(result: recipes.RecipeResult) -> str:
    parts = []
    for path in (result.stdout_path, result.stderr_path):
        if path is not None and Path(path).is_file():
            parts.append(Path(path).read_text())
    return "\n".join(parts)


def _failed_test_identities(text: str) -> list[dict]:
    """`{"class","method"}` identities `java_test`'s stdout marks `FAILED`, paired with the
    class the preceding `ran:` line named for that same method."""
    failed: list[dict] = []
    ran_class_by_method: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        ran = _RAN_LINE.match(line)
        if ran:
            ran_class_by_method[ran.group("method")] = ran.group("fqcn")
            continue
        bad = _FAILED_LINE.match(line)
        if bad and bad.group("method") in ran_class_by_method:
            failed.append({"class": ran_class_by_method[bad.group("method")], "method": bad.group("method")})
    return failed


def _changed_test_rerun_paths(plan_text: str, diff_paths: list[str], test_globs: list[str]) -> list[str]:
    """Diff test paths a `Test strategy` row with `action = change` names and that names an
    `AC-n` criterion -- the set the both-views rerun copies from head into a base checkout.

    A row naming a `no_behaviour_change` task instead contributes nothing here: it is exempt
    from the rerun, matching what `base_test_diff` itself does with the same row.
    """
    section = artefacts.parse(plan_text).section("Test strategy")
    rows = section.table() if section is not None else None
    matched: list[str] = []
    for path in diff_paths:
        if not any(fnmatch.fnmatch(path, pattern) for pattern in test_globs):
            continue
        name, stem = Path(path).name, Path(path).stem
        for row in (rows or []):
            if (row.get("action") or "").strip() != "change":
                continue
            criteria = [c.strip() for c in (row.get("criteria") or "").split(",") if c.strip()]
            if not any(_AC_ID_RE.match(c) for c in criteria):
                continue
            test_cell = (row.get("test") or "").strip()
            if test_cell and test_cell in (path, name, stem):
                matched.append(path)
                break
    return matched


def _both_views_rerun(
    *, catalogue, project_recipes: list[str], base_checkout: Path, head_checkout: Path, run_dir: Path,
    plan_text: str, diff_paths: list[str], test_globs: list[str], vendor_classpath: str,
) -> Path | None:
    """Copy every matched head test file into a fresh throwaway copy of base, run the
    project's test recipes there once, and write the ran/failed identities `base_test_diff`
    needs to tell a proven regression from a blind spot. `None` when no row's test file
    changed at head -- the check then runs its ordinary detections alone.
    """
    matched_paths = _changed_test_rerun_paths(plan_text, diff_paths, test_globs)
    if not matched_paths:
        return None

    with sandbox_copies.provisioned(
        ticket_id=0, stage_run_id=0, base_checkout=base_checkout, head_checkout=head_checkout,
        runs_dir=run_dir / "planned-rerun",
    ) as views:
        rerun_copy = views.base
        for rel_path in matched_paths:
            head_file = head_checkout / rel_path
            if head_file.is_file():
                write_bytes(rerun_copy / rel_path, head_file.read_bytes())

        ran: list[dict] = []
        failed: list[dict] = []
        for recipe_id in project_recipes:
            if catalogue[recipe_id].kind != "test":
                continue
            result = recipes.run(
                recipe_id, {"vendor_classpath": vendor_classpath, "pom": "pom.xml"}, catalogue=catalogue,
                cwd_roles={"checkout": rerun_copy}, results_dir=run_dir / "recipes" / "both-views",
                env_source=os.environ, sandbox_run_dir=run_dir / "sandbox" / "both-views" / recipe_id,
                sandbox_stage="checks", sandbox_vendor_dir=REPO_ROOT / _project_config()["vendor"],
            )
            ran += [dict(entry) for entry in (result.tests_ran or ())]
            failed += _failed_test_identities(_recipe_output_text(result))

        payload_path = run_dir / "tests_head_in_base.json"
        write_text(payload_path, json.dumps({"ran": ran, "failed": failed}))
        return payload_path


def _tests_payload(catalogue, project_recipes: list[str], recipe_results: dict, side: str) -> dict:
    ran: list[dict] = []
    for recipe_id in project_recipes:
        if catalogue[recipe_id].kind != "test":
            continue
        ran += [dict(entry) for entry in (recipe_results[recipe_id][side].tests_ran or ())]
    return {"ran": ran}


def _verdicts_payload(conn: sqlite3.Connection, ticket_id: int) -> list[dict]:
    """`checklist.verdict_set` with `evidence_ids` decoded back to a list, matching what
    `behavior_contract_evidence`'s own falsy-check on an empty list expects."""
    payload = []
    for row in checklist.verdict_set(conn, ticket_id):
        entry = dict(row)
        entry["evidence_ids"] = json.loads(entry["evidence_ids"]) if entry.get("evidence_ids") else []
        payload.append(entry)
    return payload


def _run_check_script(
    conn: sqlite3.Connection, stage_run_id: int, *, check_name: str, script: Path, args: list[str],
    review_tuple_id: int, trust_json_over_exit_code: bool = False,
) -> tuple[dict, int]:
    """Run one standalone check script and record its `check_result`.

    A non-zero exit is the script's own fail signal only for `size_gate`
    (`trust_json_over_exit_code=True`); every other script this driver
    calls exits 0 whether its own `result` is `pass` or `fail`, so a
    non-zero exit from one of them means the script itself could not run
    -- a `blind_spot` naming it, never an invented result.
    """
    completed = subprocess.run([str(script), *args], capture_output=True, text=True)
    if not trust_json_over_exit_code and completed.returncode != 0:
        payload = {"result": "blind_spot", "reason": f"{script.name} exited {completed.returncode}: {completed.stderr.strip()}"}
    else:
        try:
            payload = json.loads(completed.stdout)
        except (json.JSONDecodeError, ValueError):
            payload = {"result": "blind_spot", "reason": f"{script.name} produced no parseable JSON: {completed.stderr.strip()}"}
    cr_id = _record_check_result(
        conn, stage_run_id, check_name=check_name, result=payload.get("result", "blind_spot"),
        summary=json.dumps(payload, sort_keys=True), evidence_tuple_id=review_tuple_id,
    )
    return payload, cr_id


def _run_regression_only(
    conn: sqlite3.Connection, stage_run_id: int, *, catalogue, project_recipes: list[str], recipe_results: dict,
    review_tuple_id: int,
) -> tuple[dict, int]:
    by_recipe: dict[str, dict] = {}
    any_new_or_worse = False
    for recipe_id in project_recipes:
        recipe = catalogue[recipe_id]
        governed_kind = regression_only.recipe_governed_kind(kind=recipe.kind, level=recipe.level)
        if governed_kind is None:
            continue
        base_result, head_result = recipe_results[recipe_id]["base"], recipe_results[recipe_id]["head"]
        if recipe.kind == "test":
            base_text, head_text = _recipe_output_text(base_result), _recipe_output_text(head_result)
            comparison = regression_only.compare_tests(
                base_ran=list(base_result.tests_ran or ()), head_ran=list(head_result.tests_ran or ()),
                base_failed=_failed_test_identities(base_text), head_failed=_failed_test_identities(head_text),
            )
        else:
            comparison = regression_only.compare_diagnostics(_recipe_output_text(base_result), _recipe_output_text(head_result))
        by_recipe[recipe_id] = {
            "governed_kind": governed_kind, "new_or_worse": list(comparison.new_or_worse), "inherited": list(comparison.inherited),
        }
        any_new_or_worse = any_new_or_worse or bool(comparison.new_or_worse)

    payload = {"result": "fail" if any_new_or_worse else "pass", "by_recipe": by_recipe}
    cr_id = _record_check_result(
        conn, stage_run_id, check_name="regression_only", result=payload["result"],
        summary=json.dumps(payload, sort_keys=True), evidence_tuple_id=review_tuple_id,
    )
    return payload, cr_id


def _handle_compatibility_exclusion(
    conn: sqlite3.Connection, ticket_id: int, stage_run_id: int, *, bce_payload: dict, plan_paths: list[str],
) -> bool:
    """A `behavior_contract_evidence` blind spot naming a public declaration's binary
    compatibility re-triggers pilot exclusion exactly when the declaration's own file is
    an excluded path the plan's scope already declared -- the same route context gathering and planning take
    for a discovered excluded surface. Every other public-compatibility blind spot (no
    excluded surface matches its file, or the touch was never in the plan's own scope)
    rides into the ordinary `red_check` aggregation instead: this driver never guesses at
    a route `exclusion.decide_at_checks` itself does not confirm.
    """
    for spot in bce_payload.get("blind_spots", []):
        if spot.get("reason") != "binary compatibility":
            continue
        item_path = spot.get("item", "").rsplit(":", 1)[0]
        try:
            event = exclusion.decide_at_checks(plan_paths=plan_paths, diff_paths=[item_path])
        except ValueError:
            continue
        if event != "checks_sensitive_path_required":
            continue
        _record_check_result(
            conn, stage_run_id, check_name="exclusion", result="fail",
            summary=f"public-compatibility change on a plan-declared excluded path: {item_path}",
        )
        exclusion.apply_recorded_exclusion(conn, ticket_id)
        return True
    return False


def _apply_routing(
    conn: sqlite3.Connection, ticket: sqlite3.Row, stage_run_id: int, *, review_tuple_id: int,
    blocking_results: list[tuple[str, str, int]], catalogue, project_recipes: list[str], recipe_results: dict,
) -> None:
    non_passing = [entry for entry in blocking_results if entry[1] != "pass"]
    if not non_passing:
        return

    if any(outcome == "blind_spot" for _name, outcome, _cr_id in non_passing):
        _record_check_result(
            conn, stage_run_id, check_name="fix_round_route", check_tier="advisory", result="fail",
            summary="a waivable evidence gap requires review rather than a source fix round",
            evidence_tuple_id=review_tuple_id,
        )
        queue.open_item(conn, ticket_id=ticket["id"], kind="red_check", stage="checks", tier=_tier(ticket), ref=f"stage_run:{stage_run_id}")
        return

    from runner.checks.red_route import CheckOutcome, RecipeOutcome, classify

    recipe_outcomes = [
        RecipeOutcome(
            recipe_id=recipe_id, kind=catalogue[recipe_id].kind, level=catalogue[recipe_id].level,
            base=_recipe_status(recipe_results[recipe_id]["base"]), head=_recipe_status(recipe_results[recipe_id]["head"]),
        )
        for recipe_id in project_recipes
    ]
    # Recipe rows and their regression comparison describe the same execution;
    # counting them as independent checks would reject every repairable failure.
    check_outcomes = [
        CheckOutcome(check_name=name, result=outcome) for name, outcome, _cr_id in blocking_results
        if not name.startswith("recipe:") and name != "regression_only"
    ]
    rounds_run = conn.execute(
        "SELECT COUNT(*) FROM stage_run WHERE ticket_id = ? AND stage = 'implementation' AND run_kind = 'fix_round'", (ticket["id"],)
    ).fetchone()[0]
    cap = _limits_config()["fix_rounds"]["max_per_ticket"]
    route = classify([*recipe_outcomes, *check_outcomes], rounds_run=rounds_run, cap=cap)

    if route.kind == "fix_round":
        _record_check_result(
            conn, stage_run_id, check_name="fix_round_route", check_tier="advisory", result="pass", summary=route.reason,
            evidence_tuple_id=review_tuple_id,
        )
        transitions.apply(conn, ticket["id"], "checks_fix_round")
        return

    _record_check_result(
        conn, stage_run_id, check_name="fix_round_route", check_tier="advisory", result="fail", summary=route.reason,
        evidence_tuple_id=review_tuple_id,
    )
    queue.open_item(conn, ticket_id=ticket["id"], kind="red_check", stage="checks", tier=_tier(ticket), ref=f"stage_run:{stage_run_id}")


def run(
    conn: sqlite3.Connection, ticket: sqlite3.Row, stage_run_id: int, runs_dir: Path = RUNS_DIR,
) -> str | tuple[str, str]:
    ticket_id = ticket["id"]
    run_dir = _run_dir(runs_dir, ticket_id, stage_run_id)
    tier = _tier(ticket)

    plan_artefact = artefact_registry.latest(conn, ticket_id, "plan")
    plan_text = Path(plan_artefact["path"]).read_text() if plan_artefact is not None else ""

    preflight, failure = _preflight(conn, ticket, stage_run_id, plan_text=plan_text, runs_dir=runs_dir)
    if failure is not None:
        return failure
    review_tuple_id = preflight["review_tuple_id"]
    plan_row = preflight["plan_row"]
    planned_slots = preflight["planned_slots"]
    components = preflight["components"]
    repo = preflight["repo"]

    project_cfg = _project_config()
    catalogue = recipes.load_catalogue()
    project_recipes = [
        recipe_id for recipe_id in (project_cfg.get("recipes") or [])
        if recipe_id
    ]
    vendor_classpath = _vendor_classpath(project_cfg)

    base_sha, head_sha = plan_row["base_sha"], ticket["head_sha"]
    base_checkout, head_checkout = _checkouts(repo, base_sha, head_sha, run_dir)
    initial_recipes = [name for name in project_recipes if catalogue[name].kind not in {"security", "dependency"}]
    security_recipes = [name for name in project_recipes if catalogue[name].kind == "security"]
    dependency_recipes = [name for name in project_recipes if catalogue[name].kind == "dependency"]
    try:
        with _checked_copies(
            conn, stage_run_id, review_tuple_id, ticket_id=ticket_id, base_checkout=base_checkout,
            head_checkout=head_checkout, runs_dir=runs_dir, base_sha=base_sha, head_sha=head_sha,
        ) as copy_views:
            recipe_results, blocking_results, _results_dir = _run_recipes(
                conn, ticket_id, stage_run_id, catalogue=catalogue, project_recipes=initial_recipes,
                base_copy=copy_views.base, head_copy=copy_views.head, run_dir=run_dir, review_tuple_id=review_tuple_id,
                vendor_classpath=vendor_classpath,
            )

            diff_text = subprocess.run(
                ["git", "-C", str(repo), "diff", base_sha, head_sha], capture_output=True, text=True, check=True,
            ).stdout
            diff_path = run_dir / "diff.patch"
            write_text(diff_path, diff_text)
            diff_paths = _diff_touched_paths(repo, base_sha, head_sha)
            touched_path = run_dir / "touched_files.txt"
            write_text(touched_path, "\n".join(diff_paths) + ("\n" if diff_paths else ""))

            tests_base_path, tests_head_path = run_dir / "tests_base.json", run_dir / "tests_head.json"
            write_text(tests_base_path, json.dumps(_tests_payload(catalogue, initial_recipes, recipe_results, "base")))
            write_text(tests_head_path, json.dumps(_tests_payload(catalogue, initial_recipes, recipe_results, "head")))
            verdicts_path = run_dir / "verdicts.json"
            write_text(verdicts_path, json.dumps(_verdicts_payload(conn, ticket_id)))

            regression_payload, regression_cr_id = _run_regression_only(
                conn, stage_run_id, catalogue=catalogue, project_recipes=initial_recipes, recipe_results=recipe_results,
                review_tuple_id=review_tuple_id,
            )
            blocking_results.append(("regression_only", regression_payload["result"], regression_cr_id))

            test_globs = sorted({
                glob for recipe_id in initial_recipes if catalogue[recipe_id].kind == "test"
                for glob in (catalogue[recipe_id].test_globs or ())
            })
            rerun_payload_path = _both_views_rerun(
                catalogue=catalogue, project_recipes=initial_recipes, base_checkout=base_checkout, head_checkout=head_checkout,
                run_dir=run_dir, plan_text=plan_text, diff_paths=diff_paths, test_globs=test_globs,
                vendor_classpath=vendor_classpath,
            )
            base_test_args = [
                "--base", str(base_checkout), "--head", str(head_checkout), "--globs", ",".join(test_globs),
                "--plan", str(plan_artefact["path"]), "--tests-base", str(tests_base_path), "--tests-head", str(tests_head_path),
            ]
            if rerun_payload_path is not None:
                base_test_args += ["--tests-head-in-base", str(rerun_payload_path)]
            base_test_payload, base_test_cr_id = _run_check_script(
                conn, stage_run_id, check_name="base_test_diff", script=BASE_TEST_DIFF_SCRIPT, review_tuple_id=review_tuple_id,
                args=base_test_args,
            )
            blocking_results.append(("base_test_diff", base_test_payload.get("result", "blind_spot"), base_test_cr_id))

            for recipe_group in (security_recipes, dependency_recipes):
                results, blocking, _ = _run_recipes(
                    conn, ticket_id, stage_run_id, catalogue=catalogue, project_recipes=recipe_group,
                    base_copy=copy_views.base, head_copy=copy_views.head, run_dir=run_dir,
                    review_tuple_id=review_tuple_id, vendor_classpath=vendor_classpath,
                )
                recipe_results.update(results)
                blocking_results.extend(blocking)
            dependency_results = recipe_results.get(dependency_recipes[0], {}) if len(dependency_recipes) == 1 else {}
            base_resolution = dependency_results.get("base")
            head_resolution = dependency_results.get("head")
            if base_resolution is None or head_resolution is None or base_resolution.stdout_path is None or head_resolution.stdout_path is None:
                dep_payload = {"result": "blind_spot", "reason": "dependency resolution did not produce both immutable-view evidence"}
                dep_cr_id = _record_check_result(conn, stage_run_id, check_name="dep_verify", result="blind_spot", summary=json.dumps(dep_payload), evidence_tuple_id=review_tuple_id)
            else:
                # TODO (when the factory is stable): pass the registries the
                # recipe declares instead of an empty allowlist. The empty
                # `--allowed-registry` is deliberate, not a missing value: the
                # checks stage's sandbox has no `registry` route in `sandbox.yaml` yet, so
                # every repository host a head resolution names counts as
                # undeclared until then. The future source is the recipe's
                # declared registry endpoints under that route id, joined
                # into this one argument; the script already accepts it.
                dep_payload, dep_cr_id = _run_check_script(
                    conn, stage_run_id, check_name="dep_verify", script=DEP_VERIFY_SCRIPT, review_tuple_id=review_tuple_id,
                    args=["--base", str(base_checkout), "--head", str(head_checkout), "--base-resolution", str(base_resolution.stdout_path),
                          "--head-resolution", str(head_resolution.stdout_path), "--plan", str(plan_artefact["path"]), "--allowed-registry", ""],
                )
            blocking_results.append(("dep_verify", dep_payload.get("result", "blind_spot"), dep_cr_id))

            size_payload, size_cr_id = _run_check_script(
                conn, stage_run_id, check_name="size_gate", script=SIZE_GATE_SCRIPT, review_tuple_id=review_tuple_id,
                trust_json_over_exit_code=True,
                args=["--plan", str(plan_artefact["path"]), "--tier", tier, "--diff", str(diff_path),
                      "--tiers-config", str(TIERS_PATH), "--project-config", str(project.DEFAULT_PROJECT_CONFIG_PATH)],
            )
            blocking_results.append(("size_gate", size_payload.get("result", "blind_spot"), size_cr_id))

            scope_payload, scope_cr_id = _run_check_script(
                conn, stage_run_id, check_name="scope_diff", script=SCOPE_DIFF_SCRIPT, review_tuple_id=review_tuple_id,
                args=["--diff", str(diff_path), "--plan", str(plan_artefact["path"])],
            )
            blocking_results.append(("scope_diff", scope_payload.get("result", "blind_spot"), scope_cr_id))

            decl_payload, decl_cr_id = _run_check_script(
                conn, stage_run_id, check_name="source_declaration_diff", script=SOURCE_DECLARATION_DIFF_SCRIPT,
                review_tuple_id=review_tuple_id,
                args=["--base", str(base_checkout), "--head", str(head_checkout), "--files", str(touched_path),
                      "--plan", str(plan_artefact["path"])],
            )
            blocking_results.append(("source_declaration_diff", decl_payload.get("result", "blind_spot"), decl_cr_id))
            declarations_path = run_dir / "source_declaration_diff.json"
            write_text(declarations_path, json.dumps(decl_payload, sort_keys=True))

            bce_payload, bce_cr_id = _run_check_script(
                conn, stage_run_id, check_name="behavior_contract_evidence", script=BEHAVIOR_CONTRACT_EVIDENCE_SCRIPT,
                review_tuple_id=review_tuple_id,
                args=["--plan", str(plan_artefact["path"]), "--verdicts", str(verdicts_path), "--tests-base", str(tests_base_path),
                      "--tests-head", str(tests_head_path), "--declarations", str(declarations_path),
                      "--generated-paths", ",".join(project.load().get("generated_paths") or [])],
            )
            blocking_results.append(("behavior_contract_evidence", bce_payload.get("result", "blind_spot"), bce_cr_id))

            if _handle_compatibility_exclusion(conn, ticket_id, stage_run_id, bce_payload=bce_payload, plan_paths=_scope_paths(plan_text)):
                return "fail"

            quorum = approvals.evaluate(conn, gate="plan", subject_hash=plan_row["content_hash"], slots=planned_slots)
            binding_ok = quorum.satisfied and quorum.approval_set_hash == components.plan_approval_set_hash
            binding_payload = {"result": "pass" if binding_ok else "fail", "reasons": list(quorum.reasons)}
            binding_cr_id = _record_check_result(
                conn, stage_run_id, check_name="approval_binding", result=binding_payload["result"],
                summary=json.dumps(binding_payload, sort_keys=True), evidence_tuple_id=review_tuple_id,
            )
            blocking_results.append(("approval_binding", binding_payload["result"], binding_cr_id))

            summary_path = run_dir / "check_evidence.json"
            write_text(summary_path, json.dumps(
                {"checks": [{"id": cr_id, "check_name": name, "result": outcome} for name, outcome, cr_id in blocking_results]},
                sort_keys=True,
            ))
            prior_summary = artefact_registry.latest(conn, ticket_id, ARTEFACT_KIND)
            artefact_registry.register(
                conn, ticket_id=ticket_id, kind=ARTEFACT_KIND, path=summary_path, stage_run_id=stage_run_id,
                supersedes=prior_summary["id"] if prior_summary is not None else None,
            )

            if all(outcome == "pass" for _name, outcome, _cr_id in blocking_results):
                return "pass"
            _apply_routing(
                conn, ticket, stage_run_id, review_tuple_id=review_tuple_id, blocking_results=blocking_results,
                catalogue=catalogue, project_recipes=project_recipes, recipe_results=recipe_results,
            )
            return "fail"
    except SandboxIntegrityError:
        return "fail"
    except recipes.RecipeSandboxError as exc:
        _record_check_result(
            conn, stage_run_id, check_name="sandbox_integrity", result="fail", summary=str(exc),
            evidence_tuple_id=review_tuple_id,
        )
        return "fail"
