"""Configured local security controls report findings and unavailable evidence (R-S5-1)."""
import json
import subprocess
from pathlib import Path

import yaml

from runner.paths import FACTORY_DIR

SCRIPT = FACTORY_DIR / "scripts" / "checks" / "security_checks"
CONFIG = FACTORY_DIR / "config" / "security-checks.yaml"
WAIVER_POLICY = FACTORY_DIR / "config" / "waiver-policy.yaml"


def _checkout(tmp_path: Path, source: str, pom: str = "<project><licenses><license/></licenses></project>") -> Path:
    checkout = tmp_path / "checkout"
    source_path = checkout / "src" / "main" / "java"
    source_path.mkdir(parents=True)
    (source_path / "Feature.java").write_text(source)
    (checkout / "pom.xml").write_text(pom)
    return checkout


def _run(checkout: Path, config: Path = CONFIG, waiver_policy: Path = WAIVER_POLICY, *, check: bool = True):
    args = [str(SCRIPT), "--config", str(config), "--waiver-policy", str(waiver_policy), "--checkout", str(checkout)]
    result = subprocess.run(args, capture_output=True, text=True, check=check)
    if not check:
        return result
    return json.loads(result.stdout)


def test_must_reject_a_source_file_with_a_secret_assignment(tmp_path):
    payload = _run(_checkout(tmp_path, 'class Feature { String api_key = "secret"; }'))
    assert payload["result"] == "fail"
    assert next(item for item in payload["controls"] if item["control"] == "secret_scan")["result"] == "fail"


def test_unavailable_vulnerability_feed_is_a_named_blind_spot(tmp_path):
    payload = _run(_checkout(tmp_path, "class Feature {}"))
    controls = {item["control"]: item for item in payload["controls"]}
    assert payload["result"] == "blind_spot"
    assert controls["dependency_vulnerability"] == {"control": "dependency_vulnerability", "reason": "vulnerability database unavailable", "result": "blind_spot"}
    assert controls["license_policy"] == {"control": "license_policy", "reason": "license policy data unavailable", "result": "blind_spot"}


def test_must_reject_an_empty_control_list_instead_of_reporting_a_pass(tmp_path):
    config = tmp_path / "security.yaml"
    doc = yaml.safe_load(CONFIG.read_text())
    doc["controls"] = []
    config.write_text(yaml.safe_dump(doc))
    result = _run(_checkout(tmp_path, "class Feature {}"), config, check=False)
    assert result.returncode != 0
    assert "required control" in result.stderr


def test_must_reject_a_security_policy_whose_pinned_tool_digest_does_not_match(tmp_path):
    config = tmp_path / "security.yaml"
    doc = yaml.safe_load(CONFIG.read_text())
    doc["controls"][0]["tool_digest"] = "0" * 64
    config.write_text(yaml.safe_dump(doc))
    result = _run(_checkout(tmp_path, "class Feature {}"), config, check=False)
    assert result.returncode != 0
    assert "digest mismatch" in result.stderr


def test_must_reject_a_security_policy_whose_pinned_rules_digest_does_not_match(tmp_path):
    config = tmp_path / "security.yaml"
    doc = yaml.safe_load(CONFIG.read_text())
    doc["controls"][0]["ruleset_digest"] = "0" * 64
    config.write_text(yaml.safe_dump(doc))
    result = _run(_checkout(tmp_path, "class Feature {}"), config, check=False)
    assert result.returncode != 0
    assert "digest mismatch" in result.stderr


def test_must_reject_an_unknown_blind_spot_waiver_policy(tmp_path):
    config = tmp_path / "security.yaml"
    doc = yaml.safe_load(CONFIG.read_text())
    doc["blind_spot_policy"] = "unknown-policy"
    config.write_text(yaml.safe_dump(doc))
    result = _run(_checkout(tmp_path, "class Feature {}"), config, check=False)
    assert result.returncode != 0
    assert "unknown blind_spot_policy" in result.stderr


def test_must_reject_a_waiver_policy_input_that_does_not_match_its_digest(tmp_path):
    waiver_policy = tmp_path / "waiver-policy.yaml"
    waiver_policy.write_text("version: 1\npolicies: []\n")
    result = _run(_checkout(tmp_path, "class Feature {}"), waiver_policy=waiver_policy, check=False)
    assert result.returncode != 0
    assert "waiver policy digest mismatch" in result.stderr


def test_an_unavailable_feed_can_be_configured_to_fail_closed(tmp_path):
    config = tmp_path / "security.yaml"
    doc = yaml.safe_load(CONFIG.read_text())
    next(control for control in doc["controls"] if control["id"] == "dependency_vulnerability")["unavailable_feed"] = "fail_closed"
    config.write_text(yaml.safe_dump(doc))
    payload = _run(_checkout(tmp_path, "class Feature {}"), config)
    control = next(item for item in payload["controls"] if item["control"] == "dependency_vulnerability")
    assert control["result"] == "fail"
    assert payload["result"] == "fail"


def test_a_finding_below_the_configured_severity_threshold_does_not_fail(tmp_path):
    config = tmp_path / "security.yaml"
    doc = yaml.safe_load(CONFIG.read_text())
    next(control for control in doc["controls"] if control["id"] == "secret_scan")["severity_threshold"] = "critical"
    config.write_text(yaml.safe_dump(doc))
    payload = _run(_checkout(tmp_path, 'class Feature { String secret = "value"; }'), config)
    assert next(item for item in payload["controls"] if item["control"] == "secret_scan")["result"] == "pass"


def test_an_active_owned_suppression_is_applied_and_an_expired_one_is_rejected(tmp_path):
    doc = yaml.safe_load(CONFIG.read_text())
    doc["controls"][0]["suppressions"] = [{"rule": "secret_assignment", "owner": "security", "expires_on": "2999-01-01"}]
    allowed = tmp_path / "allowed.yaml"
    allowed.write_text(yaml.safe_dump(doc))
    payload = _run(_checkout(tmp_path, 'class Feature { String secret = "value"; }'), allowed)
    secret_result = next(item for item in payload["controls"] if item["control"] == "secret_scan")
    assert secret_result["result"] == "pass"
    assert secret_result["reason"] == "suppressed"

    doc["controls"][0]["suppressions"][0]["expires_on"] = "2000-01-01"
    expired = tmp_path / "expired.yaml"
    expired.write_text(yaml.safe_dump(doc))
    result = _run(_checkout(tmp_path / "expired", 'class Feature { String secret = "value"; }'), expired, check=False)
    assert result.returncode != 0
    assert "expired" in result.stderr
