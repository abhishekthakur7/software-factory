"""S1 for real: reindex, impact scan, context-index reads, the agent, the brief's own checks, and impact-derived tiering.

Driver-level tests materialise a throwaway git repository as the
ticket's worktree (mirroring `test_stub_stages.py`'s `_source_repo`
pattern), stamp it eligible with `_governed_ticket_fields`, and run the
fixture worker over one of `factory/evals/agents/S1/fixtures/`'s canned
`out/brief.md` documents via `FIXTURE_ADAPTER_OUT_DIR`. `vendor_path`
points at an empty directory in every test: `impact_scan` treats a
missing vendor pom as a leaf, never an error, so no vendored dependency
tree is needed to prove coverage resolution -- only the target pom's own
declared dependencies and the real, committed `artifact-to-service.yaml`
are.
"""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from runner import artefact_registry, artefacts, git_trees, governance, manifest, record, rubrics, run_ledger
from runner.checks import brief as checks_brief
from runner.db import connect
from runner.paths import FACTORY_DIR
from runner.stages import S1, run_stage

ABHISHEK = "abhishek"
FAR_FUTURE = "2999-01-01T00:00:00+00:00"

AGENT_FIXTURES_DIR = FACTORY_DIR / "evals" / "agents" / "S1" / "fixtures"
RUBRIC_FIXTURES_DIR = FACTORY_DIR / "evals" / "rubrics" / "S1" / "fixtures"
REINDEX_SCRIPT = FACTORY_DIR / "scripts" / "tools" / "reindex"
REINDEX_EVAL_DIR = FACTORY_DIR / "evals" / "scripts" / "tools" / "reindex"
RUBRIC_PATH = FACTORY_DIR / "rubrics" / "S1.md"

_COMMIT_ENV = {
    "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@example.invalid",
}


@pytest.fixture
def conn(tmp_path):
    connection = connect(tmp_path / "factory.sqlite")
    yield connection
    connection.close()


def _git(args, cwd, env=None):
    full_env = {**os.environ, **env} if env else None
    return subprocess.run(
        ["git", "-c", "commit.gpgsign=false", *args], cwd=cwd, env=full_env, capture_output=True, text=True, check=True,
    )


def _render_pom(dependencies: list[tuple[str, str, str]]) -> str:
    deps_xml = "\n".join(
        f"    <dependency>\n      <groupId>{group}</groupId>\n      <artifactId>{artifact}</artifactId>\n"
        f"      <version>{version}</version>\n    </dependency>"
        for group, artifact, version in dependencies
    )
    return (
        "<project>\n  <groupId>com.example</groupId>\n  <artifactId>widget</artifactId>\n  <version>1.0.0</version>\n"
        f"  <dependencies>\n{deps_xml}\n  </dependencies>\n</project>\n"
    )


def _source_repo(tmp_path: Path, *, pom_dependencies: list[tuple[str, str, str]] = ()) -> Path:
    """A trivial one-commit git repository carrying a pom and the one Java file the fixture briefs' flags reference."""
    repo = tmp_path / "source-repo"
    repo.mkdir()
    _git(["init", "-q"], cwd=repo)
    _git(["checkout", "-q", "-b", "main"], cwd=repo)
    (repo / "pom.xml").write_text(_render_pom(list(pom_dependencies)))
    src = repo / "src" / "main" / "java" / "com" / "example"
    src.mkdir(parents=True)
    (src / "Handler.java").write_text("package com.example;\n\npublic class Handler {\n}\n")
    _git(["add", "-A"], cwd=repo)
    _git(["commit", "-q", "-m", "init"], cwd=repo, env=_COMMIT_ENV)
    return repo


def _governed_ticket_fields(conn) -> dict:
    """Ticket fields that satisfy the committed trust profile's default-path activation."""
    proposal = governance.propose()
    for role in ("security_approver", "legal_data_governance_approver"):
        governance.decide(
            conn, proposal, actor_identity=ABHISHEK, role=role, decision="approve",
            expires_at=FAR_FUTURE, attestation_version="v1", attestation_hash=f"att-{role}",
        )
    activated = governance.activation(conn, proposal)
    return {
        "trust_profile_hash": proposal.profile_hash, "trust_approval_set_hash": activated.trust_approval_set_hash,
        "service": "fixture-project", "source_kind": "jira", "source_ref": "FIX-1",
    }


def _ready_ticket(conn, tmp_path: Path, *, pom_dependencies: list[tuple[str, str, str]] = (), **overrides) -> int:
    """A ticket in `context`, cloned from a real worktree, pinned to the committed manifest and eligible to invoke S1."""
    source = _source_repo(tmp_path, pom_dependencies=pom_dependencies)
    fields = {
        "state": "context", "opened_at": record.now(), "ticket_type": "small_feature", "service_tier": "T2",
        "tier_provisional": "standard", "factory_manifest_hash": manifest.current_hash(),
        **_governed_ticket_fields(conn),
    }
    fields.update(overrides)
    ticket_id = record.insert(conn, "ticket", **fields)
    trees = git_trees.clone_for_ticket(conn, ticket_id, source_checkout=source, target_branch="main", runs_dir=tmp_path)
    git_trees.record_head(conn, ticket_id, trees.worktree)
    return ticket_id


def _empty_vendor(tmp_path: Path) -> Path:
    return tmp_path / "vendor"


def _open_s1_run(conn, ticket_id: int):
    ticket = record.get(conn, "ticket", ticket_id)
    stage_run_id = run_ledger.open_stage_run(conn, ticket_id=ticket_id, stage="S1")
    return ticket, stage_run_id


def _run_s1_fixture(conn, tmp_path, ticket_id, fixture_name, *, monkeypatch, **run_kwargs):
    """Run `S1.run` directly (not through `run_stage`) so a test can pass config overrides a real run never sees."""
    monkeypatch.setenv("FIXTURE_ADAPTER_OUT_DIR", str(AGENT_FIXTURES_DIR / fixture_name / "out"))
    ticket, stage_run_id = _open_s1_run(conn, ticket_id)
    run_kwargs.setdefault("vendor_path", _empty_vendor(tmp_path))
    outcome = S1.run(conn, ticket, stage_run_id, tmp_path, **run_kwargs)
    return outcome, stage_run_id


def _checked_brief_table(conn, ticket_id, section_title):
    artefact_row = artefact_registry.latest(conn, ticket_id, "brief")
    parsed = artefacts.parse(Path(artefact_row["path"]).read_text())
    return parsed.section(section_title).table()


def test_fact_only_summary_fixture_is_under_the_section_8_word_limit():
    """The fact-only summary fixture passes the word-limit check (R-S1-2)."""
    text = (RUBRIC_FIXTURES_DIR / "fact_only_summary" / "summary.txt").read_text()
    finding = checks_brief.summary_word_limit(text, max_words=300)
    assert finding.result == "pass"


def test_must_fail_a_summary_over_the_configured_word_limit():
    """A summary over the configured word limit fails the check (R-S1-2)."""
    finding = checks_brief.summary_word_limit(" ".join(["word"] * 301), max_words=300)
    assert finding.result == "fail"


def test_rubric_line_r_s1_2_grader_is_a_bootstrap_checklist_with_the_dictated_judgment():
    """The R-S1-2 grader line is a bootstrap-checklist line with the dictated judgment sentence (R-S1-2)."""
    lines = rubrics.load(RUBRIC_PATH)
    line = rubrics.line(lines, row="R-S1-2", half="grader")
    assert line is not None
    assert line.checklist is True
    assert line.judgment == "fail when a ticket summary states a recommendation or an approach instead of facts alone"


def test_seeded_human_verdict_for_r_s1_2_names_its_rubric_line_and_a_fail_verdict():
    """The seeded human_verdict scenario for R-S1-2 names its rubric line and a fail verdict (R-S1-2)."""
    fixture = yaml.safe_load((RUBRIC_FIXTURES_DIR / "human_verdict" / "R-S1-2.yaml").read_text())
    assert fixture["rubric_line_id"] == "R-S1-2:grader"
    assert fixture["verdict"] == "fail"
    assert fixture["subject"]


@pytest.mark.parametrize(
    "fixture_name, expected_method",
    [("http_dependency", "http_call"), ("messaging_dependency", "message_publish"), ("config_dependency", "config_reference")],
)
def test_method_specific_dependency_fixture_records_full_impact_evidence_fields(conn, tmp_path, monkeypatch, fixture_name, expected_method):
    """An HTTP, messaging, or config dependency fixture records direction, method, source, mapping, owner, coverage, and a blind spot (R-S1-3)."""
    ticket_id = _ready_ticket(conn, tmp_path, pom_dependencies=[("com.fixturevendor", "strings", "1.0.0")])
    outcome, _ = _run_s1_fixture(conn, tmp_path, ticket_id, fixture_name, monkeypatch=monkeypatch)
    assert outcome == "pass"
    row = _checked_brief_table(conn, ticket_id, "Impact evidence")[0]
    assert row["method"] == expected_method
    assert row["direction"] in checks_brief.DIRECTIONS
    assert row["coverage"] in artefacts.IMPACT_COVERAGES
    assert row["source"] and row["mapping"] and row["owner"] and row["blind_spots"]


def _stale_caller_index_dir(tmp_path: Path) -> Path:
    index_dir = tmp_path / "index"
    index_dir.mkdir()
    (index_dir / "reporting-service-caller.md").write_text(
        "---\nkind: caller\nsource: reporting-service repo\nowner: reporting-team\n"
        "last_verified: 2020-01-01\nstaleness_rule: default\n"
        'paths: ["src/main/java/com/example/Handler.java"]\n---\n\nCallers of the export handler.\n'
    )
    return index_dir


def test_stale_caller_catalogue_fixture_marks_inbound_coverage_unknown_and_records_the_stale_read(conn, tmp_path, monkeypatch):
    """A stale `caller` context-index entry means the brief marks inbound coverage unknown rather than asserting it (R-S1-3)."""
    ticket_id = _ready_ticket(conn, tmp_path, pom_dependencies=[("com.fixturevendor", "strings", "1.0.0")])
    index_dir = _stale_caller_index_dir(tmp_path)
    outcome, stage_run_id = _run_s1_fixture(
        conn, tmp_path, ticket_id, "stale_catalogue", monkeypatch=monkeypatch, index_dir=index_dir,
    )
    assert outcome == "pass"
    row = _checked_brief_table(conn, ticket_id, "Impact evidence")[0]
    assert row["direction"] == "inbound"
    assert row["coverage"] == "unknown"
    reads = conn.execute("SELECT stale FROM index_use WHERE stage_run_id = ?", (stage_run_id,)).fetchall()
    assert len(reads) == 1
    assert reads[0]["stale"] == 1


def test_must_reject_an_inbound_row_asserting_non_unknown_coverage_with_no_fresh_caller_entry():
    """An inbound row asserting non-unknown coverage with no fresh caller entry behind it fails the check (R-S1-3)."""
    rows = [{"direction": "inbound", "dependency": "reporting-service", "coverage": "authoritative"}]
    finding = checks_brief.inbound_coverage_matches_caller_freshness(rows, any_fresh_caller_entry=False)
    assert finding.result == "fail"


def test_unmapped_package_fixture_matches_impact_scans_own_unknown_resolution(conn, tmp_path, monkeypatch):
    """A Maven dependency absent from `artifact-to-service.yaml` resolves unknown through `impact_scan`, not the brief's own claim (R-S1-3)."""
    ticket_id = _ready_ticket(conn, tmp_path, pom_dependencies=[("com.example", "mystery-lib", "1.0.0")])
    outcome, stage_run_id = _run_s1_fixture(conn, tmp_path, ticket_id, "unmapped_package", monkeypatch=monkeypatch)
    assert outcome == "pass"
    impact_scan_artefact = artefact_registry.latest(conn, ticket_id, "impact_scan")
    payload = json.loads(Path(impact_scan_artefact["path"]).read_text())
    assert payload["dependencies"][0]["coverage"] == "unknown"
    assert payload["dependencies"][0]["service"] is None
    row = _checked_brief_table(conn, ticket_id, "Impact evidence")[0]
    assert row["coverage"] == "unknown"


def test_authoritative_build_graph_fixture_records_authoritative_coverage(conn, tmp_path, monkeypatch):
    """An outbound dependency the mapping marks authoritative is recorded with authoritative coverage (R-S1-3)."""
    ticket_id = _ready_ticket(conn, tmp_path, pom_dependencies=[("com.fixturevendor", "strings", "1.0.0")])
    outcome, _ = _run_s1_fixture(conn, tmp_path, ticket_id, "authoritative_build_graph", monkeypatch=monkeypatch)
    assert outcome == "pass"
    row = _checked_brief_table(conn, ticket_id, "Impact evidence")[0]
    assert row["coverage"] == "authoritative"


def test_eligibility_triggering_unknown_fixture_re_triggers_the_exclusion_gate(conn, tmp_path, monkeypatch):
    """An unknown impact-evidence row that changes eligibility re-triggers the exclusion gate instead of proceeding unresolved (R-S1-3)."""
    ticket_id = _ready_ticket(conn, tmp_path, pom_dependencies=[("com.fixturevendor", "strings", "1.0.0")])
    outcome, stage_run_id = _run_s1_fixture(conn, tmp_path, ticket_id, "eligibility_triggering_unknown", monkeypatch=monkeypatch)
    assert outcome == "fail"
    ticket = record.get(conn, "ticket", ticket_id)
    assert ticket["state"] == "rejected"
    assert ticket["close_reason"] == "pilot_excluded"
    check = conn.execute(
        "SELECT * FROM check_result WHERE stage_run_id = ? AND check_name = 'exclusion'", (stage_run_id,)
    ).fetchone()
    assert check["result"] == "fail"


def test_discovers_excluded_scope_when_impact_scan_resolves_a_second_service():
    """`impact_scan` resolving a dependency onto a service other than the ticket's own is a discovered exclusion (R-S1-3)."""
    deps = [{"group_id": "com.other", "artifact_id": "thing", "service": "another-service"}]
    reason = checks_brief.discovers_excluded_scope([], target_service="fixture-project", impact_scan_dependencies=deps)
    assert reason is not None


def test_discovers_excluded_scope_is_none_when_every_dependency_maps_to_the_target_service():
    """Every dependency mapping to the ticket's own service is not an exclusion (R-S1-3)."""
    deps = [{"group_id": "com.fixturevendor", "artifact_id": "strings", "service": "fixture-project"}]
    reason = checks_brief.discovers_excluded_scope([], target_service="fixture-project", impact_scan_dependencies=deps)
    assert reason is None


def test_rubric_line_r_s1_3_grader_is_a_bootstrap_checklist_with_the_dictated_judgment():
    """The R-S1-3 grader line is a bootstrap-checklist line with the dictated judgment sentence (R-S1-3)."""
    lines = rubrics.load(RUBRIC_PATH)
    line = rubrics.line(lines, row="R-S1-3", half="grader")
    assert line is not None
    assert line.checklist is True
    assert line.judgment == "fail when the plan names an owner other than the one the brief's impact evidence names"


def test_seeded_human_verdict_for_r_s1_3_names_its_rubric_line_and_a_fail_verdict():
    """The seeded human_verdict scenario for R-S1-3 names its rubric line and a fail verdict (R-S1-3)."""
    fixture = yaml.safe_load((RUBRIC_FIXTURES_DIR / "human_verdict" / "R-S1-3.yaml").read_text())
    assert fixture["rubric_line_id"] == "R-S1-3:grader"
    assert fixture["verdict"] == "fail"


def test_a_flags_row_referencing_a_real_worktree_path_passes():
    """A flag whose reference is a real path in the worktree passes the code-reference check (R-S1-6)."""
    finding = checks_brief.flags_are_code_references(
        [{"flag": "x", "reference": "src/main/java/com/example/Handler.java:12"}],
        known_paths=frozenset({"src/main/java/com/example/Handler.java"}),
    )
    assert finding.result == "pass"


def test_must_reject_a_flags_row_whose_reference_is_not_a_path_in_the_worktree():
    """A flag whose reference is a sentence rather than a worktree path fails the code-reference check (R-S1-6)."""
    finding = checks_brief.flags_are_code_references(
        [{"flag": "x", "reference": "the export flag is stable in production"}],
        known_paths=frozenset({"src/main/java/com/example/Handler.java"}),
    )
    assert finding.result == "fail"


def test_live_state_word_confined_to_blind_spots_passes():
    """Live production state named only inside Blind spots passes the confinement check (R-S1-6)."""
    text = "## Flags\n\nNo live claims here.\n\n## Blind spots\n\nThe dashboard shows this flag is stable, unverified.\n"
    finding = checks_brief.live_state_confined_to_blind_spots(artefacts.parse(text))
    assert finding.result == "pass"


def test_must_reject_a_live_state_word_asserted_outside_blind_spots():
    """Live production state asserted outside Blind spots fails the confinement check (R-S1-6)."""
    text = "## Flags\n\nThe dashboard shows this flag is stable in production.\n\n## Blind spots\n\nNothing here.\n"
    finding = checks_brief.live_state_confined_to_blind_spots(artefacts.parse(text))
    assert finding.result == "fail"


def test_rubric_line_r_s1_6_grader_is_a_bootstrap_checklist_with_the_dictated_judgment():
    """The R-S1-6 grader line is a bootstrap-checklist line with the dictated judgment sentence (R-S1-6)."""
    lines = rubrics.load(RUBRIC_PATH)
    line = rubrics.line(lines, row="R-S1-6", half="grader")
    assert line is not None
    assert line.checklist is True
    assert line.judgment == (
        "fail when a brief asserts a live production fact, such as an SLI or an error-budget value, "
        "outside the blind spots section"
    )


def test_seeded_human_verdict_for_r_s1_6_names_its_rubric_line_and_a_fail_verdict():
    """The seeded human_verdict scenario for R-S1-6 names its rubric line and a fail verdict (R-S1-6)."""
    fixture = yaml.safe_load((RUBRIC_FIXTURES_DIR / "human_verdict" / "R-S1-6.yaml").read_text())
    assert fixture["rubric_line_id"] == "R-S1-6:grader"
    assert fixture["verdict"] == "fail"


_RULE = {"services_touched_at_least": 2, "files_touched_over": 10, "unknowns_at_least": 3}


@pytest.mark.parametrize(
    "files_touched, services_touched, unknowns, expected",
    [
        (11, 1, 0, "heavy"),  # files touched over the threshold
        (1, 2, 0, "heavy"),  # two or more services touched
        (1, 1, 3, "heavy"),  # three or more unknowns
        (1, 1, 0, "standard"),  # no trigger: stays at the provisional tier
    ],
)
def test_final_tier_rule_raises_one_level_on_each_trigger_in_turn(files_touched, services_touched, unknowns, expected):
    """The final tier is raised one level above provisional when files, services, or unknowns cross their threshold (R-S1-8)."""
    tier = checks_brief.final_tier_rule(
        files_touched=files_touched, services_touched=services_touched, unknowns=unknowns,
        tier_provisional="standard", tier_so_far="standard", rule=_RULE,
    )
    assert tier == expected


def test_must_reject_final_tier_rule_lowering_an_already_higher_tier():
    """The final tier rule never lowers a tier already higher than what its own thresholds would compute (R-S1-8)."""
    tier = checks_brief.final_tier_rule(
        files_touched=1, services_touched=1, unknowns=0, tier_provisional="light", tier_so_far="heavy", rule=_RULE,
    )
    assert tier == "heavy"


def test_a_t1_consumer_of_a_t2_target_raises_impact_derived_tiering_to_the_t1_mapping():
    """Impact-derived tiering picks the highest known criticality among the target and impacted services (R-S1-11)."""
    service_tiers = {"fixture-project": {"tier": "T2"}, "order-service": {"tier": "T1"}}
    matrix = {"T1": {"small_feature": "heavy"}, "T2": {"small_feature": "standard"}}
    tier, unknown = checks_brief.impact_derived_tier(
        impacted_services=frozenset({"fixture-project", "order-service"}), service_tiers=service_tiers,
        ticket_type="small_feature", provisional_tier_matrix=matrix, tier_so_far="standard",
    )
    assert tier == "heavy"
    assert unknown is False


def test_an_unknown_consumer_sets_the_unknown_impact_flag(conn, tmp_path, monkeypatch):
    """An unknown consumer sets an explicit unknown-impact flag rather than relying on a partial-scan count (R-S1-11)."""
    service_tiers = {"fixture-project": {"tier": "T2"}}
    matrix = {"T2": {"small_feature": "standard"}}
    tier, unknown = checks_brief.impact_derived_tier(
        impacted_services=frozenset({"fixture-project", "mystery-service"}), service_tiers=service_tiers,
        ticket_type="small_feature", provisional_tier_matrix=matrix, tier_so_far="standard",
    )
    assert unknown is True

    ticket_id = _ready_ticket(conn, tmp_path, pom_dependencies=[("com.fixturevendor", "strings", "1.0.0")])
    outcome, stage_run_id = _run_s1_fixture(conn, tmp_path, ticket_id, "authoritative_build_graph", monkeypatch=monkeypatch)
    assert outcome == "pass"
    check = conn.execute(
        "SELECT * FROM check_result WHERE stage_run_id = ? AND check_name = 'brief_impact_unknown'", (stage_run_id,)
    ).fetchone()
    assert check is not None  # the flag is always recorded, pass or fail, never silently skipped


def test_a_second_service_discovered_in_impact_evidence_triggers_the_ticket_exclusion(conn, tmp_path, monkeypatch):
    """Impact evidence discovering another service, since Initial eligibility is exactly one repository and
    target service, triggers exclusion through the full driver (R-S1-11) -- the same discovery
    `discovers_excluded_scope` proves in isolation above."""
    ticket_id = _ready_ticket(conn, tmp_path, pom_dependencies=[("com.other", "thing", "1.0.0")])
    # a real mapping entry pointed at a service other than the ticket's own,
    # so impact_scan itself resolves a second service.
    mapping_path = tmp_path / "artifact-to-service.yaml"
    mapping_path.write_text(
        "mappings:\n  \"com.other:thing\":\n    service: another-service\n    coverage: authoritative\n"
    )
    outcome, stage_run_id = _run_s1_fixture(
        conn, tmp_path, ticket_id, "authoritative_build_graph", monkeypatch=monkeypatch,
        artifact_to_service_path=mapping_path,
    )
    assert outcome == "fail"
    ticket = record.get(conn, "ticket", ticket_id)
    assert ticket["state"] == "rejected"
    assert ticket["close_reason"] == "pilot_excluded"


def test_rubric_line_r_s1_11_grader_is_a_bootstrap_checklist_with_the_dictated_judgment():
    """The R-S1-11 grader line is a bootstrap-checklist line with the dictated judgment sentence (R-S1-11)."""
    lines = rubrics.load(RUBRIC_PATH)
    line = rubrics.line(lines, row="R-S1-11", half="grader")
    assert line is not None
    assert line.checklist is True
    assert line.judgment == "fail when the plan's contracts table does not restate the brief's impact evidence and blind spots by name"


def test_seeded_human_verdict_for_r_s1_11_names_its_rubric_line_and_a_fail_verdict():
    """The seeded human_verdict scenario for R-S1-11 names its rubric line and a fail verdict (R-S1-11)."""
    fixture = yaml.safe_load((RUBRIC_FIXTURES_DIR / "human_verdict" / "R-S1-11.yaml").read_text())
    assert fixture["rubric_line_id"] == "R-S1-11:grader"
    assert fixture["verdict"] == "fail"


def test_rubric_line_r_s1_7_script_exists_with_no_checklist_grader_half():
    """R-S1-7 (index reads recorded, an entry past staleness listed stale) carries a script line and no grader half."""
    lines = rubrics.load(RUBRIC_PATH)
    script_line = rubrics.line(lines, row="R-S1-7", half="script")
    assert script_line is not None
    assert script_line.checklist is False
    assert rubrics.line(lines, row="R-S1-7", half="grader") is None


def test_an_empty_context_index_records_no_entries_and_still_passes(conn, tmp_path, monkeypatch):
    """An empty context index is valid: no `index_use` rows, and the registered artefact says "no entries" (R-S1-7)."""
    ticket_id = _ready_ticket(conn, tmp_path, pom_dependencies=[("com.fixturevendor", "strings", "1.0.0")])
    empty_index = tmp_path / "empty-index"
    empty_index.mkdir()
    outcome, stage_run_id = _run_s1_fixture(
        conn, tmp_path, ticket_id, "authoritative_build_graph", monkeypatch=monkeypatch, index_dir=empty_index,
    )
    assert outcome == "pass"
    count = conn.execute("SELECT COUNT(*) FROM index_use WHERE stage_run_id = ?", (stage_run_id,)).fetchone()[0]
    assert count == 0
    index_reads_artefact = artefact_registry.latest(conn, ticket_id, "index_reads")
    assert Path(index_reads_artefact["path"]).read_text().strip() == "no entries"


def test_a_clean_pass_moves_context_to_clarifying_through_the_full_driver(conn, tmp_path, monkeypatch):
    """The full driver contract: a clean pass through `run_stage` moves the ticket from context to clarifying
    and stamps a computed `tier_final` matching the checked brief's own Final tier row."""
    ticket_id = _ready_ticket(conn, tmp_path, pom_dependencies=[("com.fixturevendor", "strings", "1.0.0")])
    monkeypatch.setenv("FIXTURE_ADAPTER_OUT_DIR", str(AGENT_FIXTURES_DIR / "plain_ok" / "out"))
    outcome = run_stage(conn, ticket_id, "S1", runs_dir=tmp_path)
    assert outcome == "pass"
    ticket = record.get(conn, "ticket", ticket_id)
    assert ticket["state"] == "clarifying"
    assert ticket["tier_final"] is not None
    brief = artefact_registry.latest(conn, ticket_id, "brief")
    assert brief is not None
    final_tier_row = artefacts.parse(Path(brief["path"]).read_text()).section("Final tier").table()[0]
    assert final_tier_row["tier_final"] == ticket["tier_final"]


def _reindex_eval_case(name: str) -> dict:
    spec = yaml.safe_load((REINDEX_EVAL_DIR / "eval.yaml").read_text())
    return next(case for case in spec["cases"] if case["name"] == name)


@pytest.mark.skipif(shutil.which("codegraph") is None, reason="codegraph is not installed")
def test_reindex_succeeds_when_codegraph_is_installed():
    """The reindex tool reports ok when the codegraph binary is installed and indexing succeeds."""
    worktree = REINDEX_EVAL_DIR / _reindex_eval_case("indexed")["fixture"] / "worktree"
    result = subprocess.run([str(REINDEX_SCRIPT), str(worktree)], capture_output=True, text=True)
    assert result.returncode == 0
    assert json.loads(result.stdout)["ok"] is True


def test_must_reject_reindex_when_codegraph_is_absent_from_path(monkeypatch):
    """The reindex tool exits 1 with a JSON reason when the codegraph binary is absent from PATH."""
    worktree = REINDEX_EVAL_DIR / _reindex_eval_case("absent_binary")["fixture"] / "worktree"
    codegraph = shutil.which("codegraph")
    path_dirs = os.environ.get("PATH", "").split(os.pathsep)
    if codegraph:
        path_dirs = [d for d in path_dirs if d != str(Path(codegraph).parent)]
    monkeypatch.setenv("PATH", os.pathsep.join(path_dirs))
    result = subprocess.run([str(REINDEX_SCRIPT), str(worktree)], capture_output=True, text=True)
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["reason"]


def test_must_reject_a_ticket_that_reaches_s1_without_s0_stamped_fields(conn, tmp_path, monkeypatch):
    """R-S1-8: the final-tier rule has no floor without a provisional tier, so a ticket missing S0's stamps is refused structurally, never guessed."""
    ticket_id = _ready_ticket(conn, tmp_path, tier_provisional=None)
    outcome, stage_run_id = _run_s1_fixture(conn, tmp_path, ticket_id, "ok", monkeypatch=monkeypatch)
    assert outcome == ("fail", "structural")
    row = conn.execute(
        "SELECT result FROM check_result WHERE stage_run_id = ? AND check_name = 'ticket_lookups'", (stage_run_id,)
    ).fetchone()
    assert row["result"] == "fail"
    assert record.get(conn, "ticket", ticket_id)["tier_final"] is None
