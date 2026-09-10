"""Replay configured build recipes in disposable views and retain the adoption evidence."""
import json
import os
import subprocess
from pathlib import Path

from runner.fs import write_text
from runner import artefact_registry, git_trees, project, recipes, record, run_ledger, setup
from runner.db import connect
from runner.paths import FACTORY_DIR
from runner.sandbox import copies


def dry_run_recipes(work_dir: Path, *, factory_root: Path = FACTORY_DIR) -> dict:
    """Record both views of every configured recipe, dispose copies, and verify source identity.

    The fixture service can be materialised from its committed seed when no
    checkout exists. A real project's absent checkout is a configuration error;
    adoption never substitutes the fixture service for it.
    """
    work_dir = Path(work_dir).resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    config_path = factory_root / "config/project.yaml"
    config = project.pilot(config_path)
    source = factory_root.parent / config["checkout"]
    vendor = factory_root.parent / config["vendor"]
    if not source.is_dir():
        if config["name"] != "fixture-project":
            raise setup.SetupError(f"configured project checkout is absent: {source}")
        materialised = setup.materialise(
            project_path=config_path, seed_dir=factory_root / "evals/fixture-project", repo_root=work_dir / "seed",
        )
        source, vendor = materialised.checkout, materialised.vendor
    base_sha = subprocess.run(
        ["git", "rev-parse", config["target_branch"]], cwd=source, capture_output=True, text=True, check=True,
    ).stdout.strip()
    base = git_trees.plain_checkout(source, base_sha, work_dir / "immutable/base")
    head = git_trees.plain_checkout(source, base_sha, work_dir / "immutable/head")
    catalogue = recipes.load_catalogue(factory_root / "config/command-recipes.yaml")
    classpath = os.pathsep.join(str(path) for path in sorted(vendor.rglob("*.jar")))
    conn = connect(work_dir / "evidence.sqlite")
    run_id = run_ledger.open_utility_run(conn, kind="fixture_replay", inputs=json.dumps({"base_sha": base_sha}))
    evidence = {"base_sha": base_sha, "recipes": [], "disposed": False, "unchanged": False}
    views = None
    try:
        with copies.provisioned(
            ticket_id=0, stage_run_id=run_id, base_checkout=base, head_checkout=head, runs_dir=work_dir,
        ) as views:
            for recipe_id in catalogue:
                outcomes = {}
                for side, checkout in (("base", views.base), ("head", views.head)):
                    result = recipes.run(
                        recipe_id, {"vendor_classpath": classpath, "vendor": str(vendor), "pom": "pom.xml"}, catalogue=catalogue,
                        cwd_roles={"checkout": checkout, "base": checkout, "head": checkout, "scratch": checkout / "scratch"},
                        results_dir=work_dir / "results" / recipe_id / side, env_source=os.environ,
                        sandbox_run_dir=work_dir / "sandbox" / recipe_id / side, sandbox_stage="checks",
                        sandbox_vendor_dir=vendor,
                    )
                    outcomes[side] = {
                        "transport_outcome": result.outcome,
                        "reported_result": result.reported_result,
                        "exit_code": result.exit_code,
                    }
                semantic = [
                    (item["reported_result"] or "pass") if item["transport_outcome"] == "pass" else "fail"
                    for item in outcomes.values()
                ]
                outcome = "fail" if "fail" in semantic or "timeout" in semantic else "blind_spot" if "blind_spot" in semantic else "pass"
                result_path = work_dir / "results" / recipe_id / "result.json"
                payload = {"recipe": recipe_id, "views": outcomes, "outcome": outcome}
                write_text(result_path, json.dumps(payload, sort_keys=True) + "\n")
                artefact_id = artefact_registry.register(
                    conn, ticket_id=None, utility_run_id=run_id, kind="recipe_dry_run", path=result_path,
                )
                record.insert(
                    conn, "check_result", check_name=f"recipe_dry_run:{recipe_id}", source="runner",
                    result=outcome, evidence_artefact=artefact_id, summary=json.dumps(outcomes, sort_keys=True),
                )
                evidence["recipes"].append(payload)
    finally:
        evidence["disposed"] = views is not None and not views.root.exists()
        evidence["unchanged"] = copies.recheck(base, base_sha) and copies.recheck(head, base_sha)
        path = work_dir / "results/disposal.json"
        write_text(path, json.dumps(evidence, sort_keys=True) + "\n")
        artefact_registry.register(conn, ticket_id=None, utility_run_id=run_id, kind="copy_disposal", path=path)
        passed = evidence["disposed"] and evidence["unchanged"] and len(evidence["recipes"]) == len(catalogue)
        passed = passed and all(result["outcome"] in {"pass", "blind_spot"} for result in evidence["recipes"])
        run_ledger.finish(conn, run_id, "pass" if passed else "fail", table="utility_run")
        conn.commit()
        conn.close()
    return evidence
