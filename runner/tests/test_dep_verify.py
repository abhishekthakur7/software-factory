"""Offline dependency resolution and verification over immutable base and head views."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from runner import setup
from runner.paths import FACTORY_DIR

SCRIPT = FACTORY_DIR / "scripts" / "checks" / "dep_verify"
RESOLVE_SCRIPT = FACTORY_DIR / "scripts" / "checks" / "dep_resolve"

pytestmark = pytest.mark.skipif(
    shutil.which("javac") is None or shutil.which("jar") is None,
    reason="requires javac and jar to prove offline import resolution",
)


def _pom(dependencies=(), repository: str = "") -> str:
    dependency_xml = "".join(
        "<dependency><groupId>com.vendor</groupId><artifactId>"
        f"{artifact}</artifactId><version>{version}</version></dependency>"
        for artifact, version in dependencies
    )
    repository_xml = f"<repositories><repository><url>{repository}</url></repository></repositories>" if repository else ""
    return f"<project><dependencies>{dependency_xml}</dependencies>{repository_xml}</project>"


def _plan(rows: str) -> str:
    return "## Dependencies\n\n| package | from_version | to_version | kind | ignored |\n| --- | --- | --- | --- | --- |\n" + rows


def _artifact(vendor: Path, artifact: str, version: str, source: str, dependencies=()):
    directory = vendor / "com" / "vendor" / artifact / version
    directory.mkdir(parents=True)
    dependency_xml = "".join(
        "<dependency><groupId>com.vendor</groupId><artifactId>"
        f"{name}</artifactId><version>{dependency_version}</version></dependency>"
        for name, dependency_version in dependencies
    )
    (directory / f"{artifact}-{version}.pom").write_text(
        "<project><groupId>com.vendor</groupId><artifactId>"
        f"{artifact}</artifactId><version>{version}</version><dependencies>{dependency_xml}</dependencies></project>"
    )
    package = source.split("package ", 1)[1].split(";", 1)[0]
    class_name = source.split("class ", 1)[1].split()[0].split("{")[0]
    source_path = directory / "src" / Path(*package.split(".")) / f"{class_name}.java"
    source_path.parent.mkdir(parents=True)
    source_path.write_text(source)
    classes = directory / "classes"
    classpath = [str(vendor / "com" / "vendor" / name / dependency_version / f"{name}-{dependency_version}.jar") for name, dependency_version in dependencies]
    command = ["javac", "-d", str(classes)]
    if classpath:
        command += ["-classpath", ":".join(classpath)]
    command.append(str(source_path))
    subprocess.run(command, check=True, capture_output=True, text=True)
    subprocess.run(["jar", "cf", str(directory / f"{artifact}-{version}.jar"), "-C", str(classes), "."], check=True, capture_output=True, text=True)
    shutil.rmtree(classes)


def _vendor(tmp_path: Path, *, versions=("1.0.0",)) -> Path:
    vendor = tmp_path / "vendor"
    _artifact(vendor, "util", "1.0.0", "package com.vendor.util; public class Util {}")
    for version in versions:
        _artifact(
            vendor, "strings", version,
            "package com.vendor.strings; import com.vendor.util.Util; public class Strings { Util value; }",
            dependencies=(("util", "1.0.0"),),
        )
    return vendor


def _resolve(pom: Path, vendor: Path) -> dict:
    result = subprocess.run([str(RESOLVE_SCRIPT), "--pom", str(pom), "--vendor", str(vendor)], capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def _run(tmp_path: Path, *, base_dependencies, head_dependencies, plan: str, source: str = "", repository: str = "", vendor=None, base_evidence=None, head_evidence=None, local_source: str = "") -> dict:
    tmp_path.mkdir(parents=True, exist_ok=True)
    base, head = tmp_path / "base", tmp_path / "head"
    base.mkdir()
    head.mkdir()
    base_pom, head_pom = base / "pom.xml", head / "pom.xml"
    base_pom.write_text(_pom(base_dependencies))
    head_pom.write_text(_pom(head_dependencies, repository))
    if source:
        java = head / "src" / "main" / "java" / "com" / "fixture"
        java.mkdir(parents=True)
        (java / "Feature.java").write_text(source)
        if local_source:
            (java / "Local.java").write_text(local_source)
    vendor = vendor or _vendor(tmp_path, versions=tuple(sorted({version for _, version in (*base_dependencies, *head_dependencies)})))
    base_evidence = base_evidence or _resolve(base_pom, vendor)
    head_evidence = head_evidence or _resolve(head_pom, vendor)
    base_resolution, head_resolution = tmp_path / "base-resolution.json", tmp_path / "head-resolution.json"
    base_resolution.write_text(json.dumps(base_evidence))
    head_resolution.write_text(json.dumps(head_evidence))
    plan_path = tmp_path / "plan.md"
    plan_path.write_text(plan)
    result = subprocess.run(
        [str(SCRIPT), "--base", str(base), "--head", str(head), "--base-resolution", str(base_resolution),
         "--head-resolution", str(head_resolution), "--plan", str(plan_path), "--allowed-registry", "registry.example"],
        capture_output=True, text=True, check=True,
    )
    return json.loads(result.stdout)


def test_offline_resolver_proves_pinned_direct_and_transitive_vendored_artifacts(tmp_path):
    vendor = _vendor(tmp_path)
    pom = tmp_path / "pom.xml"
    pom.write_text(_pom((("strings", "1.0.0"),)))
    payload = _resolve(pom, vendor)
    assert payload["result"] == "pass"
    assert [(item["package"], item["version"], item["depth"]) for item in payload["dependencies"]] == [
        ("com.vendor:strings", "1.0.0", 1), ("com.vendor:util", "1.0.0", 2),
    ]
    for item in payload["dependencies"]:
        assert item["pom_sha256"] == hashlib.sha256(Path(item["pom_path"]).read_bytes()).hexdigest()
        assert item["jar_sha256"] == hashlib.sha256(Path(item["jar_path"]).read_bytes()).hexdigest()


def test_offline_resolver_accepts_the_materialised_fixture_vendor_layout(tmp_path):
    config = tmp_path / "project.yaml"
    config.write_text(yaml.safe_dump({"projects": [{
        "name": "fixture-project", "checkout": "runs/checkout", "vendor": "runs/vendor", "target_branch": "main",
    }]}))
    materialised = setup.materialise(project_path=config, repo_root=tmp_path)

    payload = _resolve(materialised.checkout / "pom.xml", materialised.vendor)

    assert [(item["package"], item["version"]) for item in payload["dependencies"]] == [
        ("com.fixturevendor:strings", "1.0.0"), ("com.fixturevendor:util", "1.0.0"),
    ]


def test_must_fail_resolution_when_a_transitive_vendored_jar_is_missing(tmp_path):
    vendor = _vendor(tmp_path)
    (vendor / "com" / "vendor" / "util" / "1.0.0" / "util-1.0.0.jar").unlink()
    pom = tmp_path / "pom.xml"
    pom.write_text(_pom((("strings", "1.0.0"),)))
    payload = _resolve(pom, vendor)
    assert payload["result"] == "fail"
    assert "util-1.0.0.jar" in payload["reasons"][0]


def test_must_fail_resolution_for_a_maven_parent_or_dependency_management_model(tmp_path):
    vendor = _vendor(tmp_path)
    pom = tmp_path / "pom.xml"
    pom.write_text("<project><parent><groupId>com.vendor</groupId></parent></project>")
    payload = _resolve(pom, vendor)
    assert payload["result"] == "fail"
    assert "unsupported Maven element 'parent'" in payload["reasons"][0]


def test_must_fail_resolution_when_a_vendored_symlink_escapes_the_declared_repository(tmp_path):
    vendor = _vendor(tmp_path)
    outside = tmp_path / "outside"
    _artifact(outside, "strings", "1.0.0", "package com.vendor.strings; public class Strings {}")
    target = vendor / "com" / "vendor" / "strings" / "1.0.0"
    shutil.rmtree(target)
    target.symlink_to(outside / "com" / "vendor" / "strings" / "1.0.0", target_is_directory=True)
    pom = tmp_path / "pom.xml"
    pom.write_text(_pom((("strings", "1.0.0"),)))
    payload = _resolve(pom, vendor)
    assert payload["result"] == "fail"
    assert "escapes the declared vendor repository" in payload["reasons"][0]


def test_compares_validated_base_and_head_resolution_with_only_the_plan_comparison_columns(tmp_path):
    payload = _run(
        tmp_path, base_dependencies=(("strings", "1.0.0"),), head_dependencies=(("strings", "2.0.0"),),
        plan=_plan("| com.vendor:strings | 1.0.0 | 2.0.0 | changed | deliberately ignored |\n"),
        source="package com.fixture; import com.vendor.strings.Strings; class Feature { Strings value; }",
    )
    assert payload == {"changes": [{"from_version": "1.0.0", "kind": "changed", "package": "com.vendor:strings", "to_version": "2.0.0"}], "reasons": [], "result": "pass"}


def test_must_reject_a_fabricated_import_even_when_its_package_has_the_old_fixture_prefix(tmp_path):
    payload = _run(
        tmp_path, base_dependencies=(("strings", "1.0.0"),), head_dependencies=(("strings", "1.0.0"),), plan=_plan(""),
        source="package com.fixture; import com.fixture.Fabricated; class Feature {}",
    )
    assert payload["result"] == "fail"
    assert payload["reasons"] == ["unresolvable import: com.fixture.Fabricated"]


def test_actual_javac_accepts_a_local_source_import_without_a_maven_group_prefix(tmp_path):
    payload = _run(
        tmp_path, base_dependencies=(("strings", "1.0.0"),), head_dependencies=(("strings", "1.0.0"),), plan=_plan(""),
        source="package com.fixture; import com.fixture.Local; class Feature { Local local; }",
        local_source="package com.fixture; public class Local {}",
    )
    assert payload["result"] == "pass"


def test_must_reject_a_dependency_change_absent_from_the_plan(tmp_path):
    payload = _run(tmp_path, base_dependencies=(("strings", "1.0.0"),), head_dependencies=(("strings", "2.0.0"),), plan=_plan(""))
    assert payload["result"] == "fail"
    assert "undeclared dependency change: com.vendor:strings" in payload["reasons"]


def test_must_reject_a_mutable_dependency_resolution(tmp_path):
    payload = _run(tmp_path, base_dependencies=(("strings", "1.0.0"),), head_dependencies=(("strings", "2.0.0-SNAPSHOT"),), plan=_plan(""))
    assert payload["result"] == "fail"
    assert "forbidden unpinned resolution: com.vendor:strings" in payload["reasons"]


def test_must_reject_a_repository_outside_the_declared_registry(tmp_path):
    payload = _run(tmp_path, base_dependencies=(("strings", "1.0.0"),), head_dependencies=(("strings", "1.0.0"),), plan=_plan(""), repository="https://outside.invalid/repo")
    assert payload["result"] == "fail"
    assert payload["reasons"] == ["network source outside declared registry: outside.invalid"]


def test_allows_an_explicit_valid_empty_dependency_closure(tmp_path):
    payload = _run(tmp_path, base_dependencies=(), head_dependencies=(), plan=_plan(""))
    assert payload == {"changes": [], "reasons": [], "result": "pass"}


def test_allows_an_explicit_empty_closure_without_a_materialised_vendor_directory(tmp_path):
    payload = _run(
        tmp_path, base_dependencies=(), head_dependencies=(), plan=_plan(""), vendor=tmp_path / "no-vendor-needed",
    )
    assert payload == {"changes": [], "reasons": [], "result": "pass"}


def test_must_report_a_malformed_resolver_output_as_a_blind_spot(tmp_path):
    payload = _run(
        tmp_path, base_dependencies=(("strings", "1.0.0"),), head_dependencies=(("strings", "1.0.0"),), plan=_plan(""),
        base_evidence={"schema_version": 1, "result": "pass", "dependencies": [], "reasons": []},
    )
    assert payload == {"changes": [], "reasons": ["base resolution is missing dependency evidence"], "result": "blind_spot"}


def test_must_report_tampered_resolver_artifact_evidence_as_a_blind_spot(tmp_path):
    vendor = _vendor(tmp_path)
    pom = tmp_path / "head-pom.xml"
    pom.write_text(_pom((("strings", "1.0.0"),)))
    evidence = _resolve(pom, vendor)
    evidence["dependencies"][0]["jar_sha256"] = "0" * 64
    payload = _run(
        tmp_path / "run", base_dependencies=(("strings", "1.0.0"),), head_dependencies=(("strings", "1.0.0"),),
        plan=_plan(""), vendor=vendor, head_evidence=evidence,
    )
    assert payload["result"] == "blind_spot"
    assert "digest mismatch" in payload["reasons"][0]
