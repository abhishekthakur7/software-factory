"""The plan tuple: derived components, currency, the planned reviewer-set derivation, and the
`plan_review_gate`'s real quorum, currency, and freshness checks (R-S3-15).

`factory/rubrics/S3.md` is still a stub while a parallel effort builds it; wherever a test here
needs a real, complete checklist it drives the same small `factory/evals/rubrics/S3/fixtures/checklist/`
rubric/artefact set `test_s3_checklist.py` uses, through `queue.act`'s own `verdict` and `approve`
actions -- the production path, not a hand-seeded tuple.
"""
import json
import os
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from runner import (
    approvals, artefact_registry, binding, canonical, checklist, gates, git_trees, manifest,
    plan_tuple, queue, record, reviewer_sets, transitions,
)
from runner.db import connect
from runner.owners import load_owners
from runner.paths import FACTORY_DIR
from runner.reviewer_sets import Slot
from runner.stages import S3

REVIEWER_SETS_FIXTURES = Path(__file__).parent / "fixtures" / "reviewer_sets"
OWNERS = load_owners(REVIEWER_SETS_FIXTURES / "owners.yaml")
SENSITIVE_PATHS = yaml.safe_load((REVIEWER_SETS_FIXTURES / "sensitive-paths.yaml").read_text())
PILOT_IDENTITY = OWNERS.roles["s3_reviewer"]["identity"]  # "alice", this fixture's single-person pilot

CHECKLIST_FIXTURE_DIR = FACTORY_DIR / "evals" / "rubrics" / "S3" / "fixtures" / "checklist"

ABHISHEK = "abhishek"  # the real, committed owners.yaml's own single pilot identity

_COMMIT_ENV = {
    "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@example.invalid",
}


def _conn(tmp_path):
    return connect(tmp_path / "factory.sqlite")


def _git(args, cwd, env=None):
    full_env = {**os.environ, **env} if env else None
    return subprocess.run(
        ["git", "-c", "commit.gpgsign=false", *args], cwd=cwd, env=full_env,
        capture_output=True, text=True, check=True,
    )


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(["init", "-q"], cwd=repo)
    _git(["checkout", "-q", "-b", "main"], cwd=repo)
    (repo / "README.md").write_text("seed\n")
    _git(["add", "-A"], cwd=repo)
    _git(["commit", "-q", "-m", "seed"], cwd=repo, env=_COMMIT_ENV)
    return repo


def _commit_codeowners(repo: Path, fixture_name: str) -> str:
    target = repo / ".github" / "CODEOWNERS"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text((REVIEWER_SETS_FIXTURES / fixture_name).read_text())
    _git(["add", "-A"], cwd=repo)
    _git(["commit", "-q", "-m", fixture_name], cwd=repo, env=_COMMIT_ENV)
    return _git(["rev-parse", "HEAD"], cwd=repo).stdout.strip()


def _latest_plan_tuple(conn, ticket_id):
    return conn.execute(
        "SELECT * FROM evidence_tuple WHERE ticket_id = ? AND kind = 'plan' ORDER BY id DESC LIMIT 1", (ticket_id,)
    ).fetchone()


def _cloned_ticket(conn, tmp_path, *, state="planning") -> tuple[int, Path]:
    """A ticket with a real, cloned worktree and every ticket-column bound field set."""
    source = _init_repo(tmp_path)
    ticket_id = record.insert(
        conn, "ticket", state="intake", opened_at=record.now(), factory_manifest_hash=manifest.current_hash(),
        trust_profile_hash="trust-1", trust_approval_set_hash="trust-approval-1",
    )
    trees = git_trees.clone_for_ticket(conn, ticket_id, source_checkout=source, target_branch="main", runs_dir=tmp_path)
    git_trees.record_head(conn, ticket_id, trees.worktree)
    record.update(conn, "ticket", ticket_id, state=state)
    return ticket_id, source


def _register_checklist_artefacts(conn, ticket_id) -> None:
    """Registers the checklist fixture's brief/criteria/plan and two already-answered questions.

    Answered, not open: these two rows exist so the fixture's `question`-
    subject checklist lines (grading the question's own phrasing quality)
    have something to expand over, but `plan_review_gate` withholds its
    event while any question is still open, so a ticket meant to reach a
    satisfied plan subject in these tests needs its questions resolved.
    """
    for kind in ("brief", "criteria", "plan"):
        artefact_registry.register(conn, ticket_id=ticket_id, kind=kind, path=CHECKLIST_FIXTURE_DIR / f"{kind}.md")
    for _ in range(2):
        record.insert(
            conn, "question", ticket_id=ticket_id, stage="S2", round=1, rank=1,
            options="[]", state="answered", blocking=0,
        )


def _complete_checklist(conn, ticket_id, item_id, *, actor=ABHISHEK) -> None:
    ticket = record.get(conn, "ticket", ticket_id)
    plan_artefact = artefact_registry.latest(conn, ticket_id, "plan")
    for instance in checklist.expected_instances(conn, ticket):
        queue.act(
            conn, item_id=item_id, action="verdict", actor=actor, line=instance.rubric_line_id,
            key=instance.subject_item_key, verdict="pass", evidence=[plan_artefact["id"]],
        )


def _reviewer_set(conn, ticket_id, slots) -> int:
    return record.insert(
        conn, "reviewer_set", ticket_id=ticket_id, kind="planned", content_hash=f"planned-{ticket_id}-{len(slots)}",
        slots=json.dumps([slot.to_json() for slot in slots]),
    )


def _planned_ticket_with_complete_checklist(conn, tmp_path, *, slots=None) -> tuple[int, int]:
    """A ticket in `plan_review`, cloned from a real repo, with a complete checklist and a fresh plan tuple.

    `slots` overrides the planned reviewer set's own slots (default: the
    pilot's one `s3_reviewer` slot, real owners.yaml identity `abhishek`
    so `queue.act`'s own actor-identity check accepts it).
    """
    ticket_id, source = _cloned_ticket(conn, tmp_path, state="planning")
    _register_checklist_artefacts(conn, ticket_id)
    slots = slots if slots is not None else [Slot(source_rule="s3_reviewer_role", role="s3_reviewer", owner=ABHISHEK, min_count=1)]
    reviewer_set_id = _reviewer_set(conn, ticket_id, slots)
    item_id = queue.open_item(conn, ticket_id=ticket_id, kind="plan_approval", stage="S3", reviewer_set_id=reviewer_set_id)
    record.update(conn, "ticket", ticket_id, state="plan_review")
    _complete_checklist(conn, ticket_id, item_id)
    return ticket_id, item_id




def test_derive_planned_always_includes_the_pilot_slot_plus_codeowners_slots(tmp_path):
    conn = _conn(tmp_path)
    repo = _init_repo(tmp_path)
    sha = _commit_codeowners(repo, "CODEOWNERS_precedence")
    ticket_id = record.insert(conn, "ticket", state="planning", opened_at=record.now())

    derivation = reviewer_sets.derive_planned(
        conn, ticket_id=ticket_id, repo_path=repo, target_base_sha=sha, changed_paths=["README.md"],
        owners=OWNERS, sensitive_paths={}, authority_policy_hash="policy-hash", membership_snapshot_hash="members-hash",
    )

    pilot = next(s for s in derivation.slots if s.source_rule == "s3_reviewer_role")
    assert (pilot.role, pilot.owner) == ("s3_reviewer", PILOT_IDENTITY)
    codeowners_slot = next(s for s in derivation.slots if s.matched_path == "README.md")
    assert codeowners_slot.owner == "alice"
    row = record.get(conn, "reviewer_set", derivation.id)
    assert row["kind"] == "planned"
    assert json.loads(row["slots"]) == [slot.to_json() for slot in derivation.slots]


def test_derive_planned_stands_in_with_only_the_pilot_slot_when_the_repo_has_no_codeowners(tmp_path):
    """An empty scope over a repo with no CODEOWNERS at all: nothing to match, so the pilot's
    own fixed slot is the only one -- `derive_planned` never raises for the file's absence."""
    conn = _conn(tmp_path)
    repo = _init_repo(tmp_path)  # no CODEOWNERS committed
    sha = _git(["rev-parse", "HEAD"], cwd=repo).stdout.strip()
    ticket_id = record.insert(conn, "ticket", state="planning", opened_at=record.now())

    derivation = reviewer_sets.derive_planned(
        conn, ticket_id=ticket_id, repo_path=repo, target_base_sha=sha, changed_paths=[],
        owners=OWNERS, sensitive_paths={}, authority_policy_hash="policy-hash", membership_snapshot_hash="members-hash",
    )
    assert len(derivation.slots) == 1
    assert derivation.slots[0].source_rule == "s3_reviewer_role"
    assert derivation.blocked is False


def test_derive_planned_leaves_a_codeowners_uncovered_path_unblocked(tmp_path):
    """Unlike `derive_actual`, a planned-scope path neither CODEOWNERS nor the sensitive-path
    map claims does not block: the plan's own forecast of scope is not the real diff, and the
    real diff's actual reviewer set is what must resolve every touched path, at S6."""
    conn = _conn(tmp_path)
    sha = _commit_codeowners(_init_repo(tmp_path), "CODEOWNERS_precedence")  # covers *.md and src/**/*.py only
    repo = tmp_path / "repo"
    ticket_id = record.insert(conn, "ticket", state="planning", opened_at=record.now())

    derivation = reviewer_sets.derive_planned(
        conn, ticket_id=ticket_id, repo_path=repo, target_base_sha=sha, changed_paths=["docs/notes.txt"],
        owners=OWNERS, sensitive_paths={}, authority_policy_hash="policy-hash", membership_snapshot_hash="members-hash",
    )
    assert derivation.blocked is False
    assert derivation.unresolved == ()
    assert len(derivation.slots) == 1  # only the pilot slot; docs/notes.txt matches nothing


def test_s3_scope_paths_takes_touch_create_delete_and_a_discretion_glob_contributes_nothing():
    """The plan's own `Scope and discretion` table: `touch`/`create`/`delete` rows contribute
    their path, a `discretion` row's glob does not (it names a pattern, not one path)."""
    plan_text = (
        "## Scope and discretion\n\n"
        "| path | action | reason |\n|---|---|---|\n"
        "| src/a.py | touch | edits a |\n"
        "| src/b.py | create | adds b |\n"
        "| src/c.py | delete | removes c |\n"
        "| src/**/*.tmp | discretion | may touch generated files |\n"
    )
    assert S3._scope_paths(plan_text) == ["src/a.py", "src/b.py", "src/c.py"]




def test_the_completing_verdict_creates_a_plan_tuple_whose_hash_is_recomputable_and_current(tmp_path):
    conn = _conn(tmp_path)
    ticket_id, item_id = _planned_ticket_with_complete_checklist(conn, tmp_path)
    row = _latest_plan_tuple(conn, ticket_id)
    assert row is not None
    assert row["kind"] == "plan"
    hashed = {key: row[key] for key in row.keys() if key not in ("id", "content_hash", "created_at")}
    assert row["content_hash"] == canonical.content_hash(hashed)

    ticket = record.get(conn, "ticket", ticket_id)
    assert binding.plan_tuple_currency(conn, row["id"], plan_tuple.derive_components(conn, ticket)).current




def test_partial_quorum_over_two_required_slots_withholds_the_gate(tmp_path):
    conn = _conn(tmp_path)
    unlinked_b = Slot(source_rule="extra_slot", owner="second-reviewer", min_count=1)
    slot_a = Slot(source_rule="s3_reviewer_role", role="s3_reviewer", owner=ABHISHEK, min_count=1, distinct_from=(unlinked_b.slot_id,))
    slot_b = replace(unlinked_b, distinct_from=(slot_a.slot_id,))
    ticket_id, item_id = _planned_ticket_with_complete_checklist(conn, tmp_path, slots=[slot_a, slot_b])

    queue.act(conn, item_id=item_id, action="approve", actor=ABHISHEK, bucket="under_2m", self_contained="yes", runs_dir=tmp_path)
    ticket = record.get(conn, "ticket", ticket_id)
    assert gates.plan_review_gate(conn, ticket, runs_dir=tmp_path) is None  # only slot_a's approval exists

    row = _latest_plan_tuple(conn, ticket_id)
    approvals.record_approval(
        conn, gate="plan", subject_hash=row["content_hash"], slot_id=slot_b.slot_id, actor_identity="second-reviewer",
        role="owner", decision="approve", authority_policy_hash="policy-1", membership_snapshot_hash="members-1",
        attestation_version="v1", attestation_hash="att-2", ticket_id=ticket_id,
    )
    ticket = record.get(conn, "ticket", ticket_id)
    assert gates.plan_review_gate(conn, ticket, runs_dir=tmp_path) == "plan_quorum_fresh"


def test_identity_separation_violation_withholds_quorum_even_with_a_row_on_each_slot(tmp_path):
    conn = _conn(tmp_path)
    unlinked_b = Slot(source_rule="extra_slot", owner=ABHISHEK, min_count=1)
    slot_a = Slot(source_rule="s3_reviewer_role", role="s3_reviewer", owner=ABHISHEK, min_count=1, distinct_from=(unlinked_b.slot_id,))
    slot_b = replace(unlinked_b, distinct_from=(slot_a.slot_id,))
    ticket_id, item_id = _planned_ticket_with_complete_checklist(conn, tmp_path, slots=[slot_a, slot_b])

    queue.act(conn, item_id=item_id, action="approve", actor=ABHISHEK, bucket="under_2m", self_contained="yes", runs_dir=tmp_path)
    row = _latest_plan_tuple(conn, ticket_id)
    approvals.record_approval(
        conn, gate="plan", subject_hash=row["content_hash"], slot_id=slot_b.slot_id, actor_identity=ABHISHEK,
        role="owner", decision="approve", authority_policy_hash="policy-1", membership_snapshot_hash="members-1",
        attestation_version="v1", attestation_hash="att-2", ticket_id=ticket_id,
    )
    ticket = record.get(conn, "ticket", ticket_id)
    # the same identity fills both distinct_from-linked slots: separation fails, so quorum
    # never holds even though every slot individually has an approving row.
    assert gates.plan_review_gate(conn, ticket, runs_dir=tmp_path) is None




def test_plan_review_gate_withholds_the_event_when_the_target_branch_has_moved(tmp_path):
    """`_cloned_ticket` (through `_init_repo`) always seeds its source checkout at `tmp_path/"repo"`;
    a fresh commit there, after cloning, moves the target branch out from under the pinned base."""
    conn = _conn(tmp_path)
    ticket_id, item_id = _planned_ticket_with_complete_checklist(conn, tmp_path)
    queue.act(conn, item_id=item_id, action="approve", actor=ABHISHEK, bucket="under_2m", self_contained="yes", runs_dir=tmp_path)
    ticket = record.get(conn, "ticket", ticket_id)
    assert gates.plan_review_gate(conn, ticket, runs_dir=tmp_path) == "plan_quorum_fresh"

    repo = tmp_path / "repo"
    (repo / "moved.txt").write_text("target moved\n")
    _git(["add", "-A"], cwd=repo)
    _git(["commit", "-q", "-m", "target moved"], cwd=repo, env=_COMMIT_ENV)

    ticket = record.get(conn, "ticket", ticket_id)
    assert gates.plan_review_gate(conn, ticket, runs_dir=tmp_path) is None




def test_derive_planned_marks_a_sensitive_scope_path_and_offers_only_its_routes(tmp_path):
    conn = _conn(tmp_path)
    repo = _init_repo(tmp_path)
    sha = _git(["rev-parse", "HEAD"], cwd=repo).stdout.strip()
    ticket_id = record.insert(conn, "ticket", state="planning", opened_at=record.now())

    derivation = reviewer_sets.derive_planned(
        conn, ticket_id=ticket_id, repo_path=repo, target_base_sha=sha, changed_paths=["infra/deploy.sh"],
        owners=OWNERS, sensitive_paths=SENSITIVE_PATHS, authority_policy_hash="policy-hash",
        membership_snapshot_hash="members-hash",
    )
    assert derivation.sensitive is True
    assert derivation.blocked is True
    assert derivation.routes == ("s4_removal", "pilot_excluded")
    # the pilot slot is still present alongside the sensitive-path slot
    assert any(s.source_rule == "s3_reviewer_role" for s in derivation.slots)


def _s3_ready_ticket(conn, tmp_path):
    source = _init_repo(tmp_path)
    ticket_id = record.insert(
        conn, "ticket", state="intake", opened_at=record.now(), tier_final="light",
        factory_manifest_hash=manifest.current_hash(),
    )
    git_trees.clone_for_ticket(conn, ticket_id, source_checkout=source, target_branch="main", runs_dir=tmp_path)
    record.update(conn, "ticket", ticket_id, state="planning")
    brief_path = tmp_path / "brief.md"
    brief_path.write_text("## Touched area candidates\n\n| path | reason |\n|---|---|\n| README.md | seed |\n")
    artefact_registry.register(conn, ticket_id=ticket_id, kind="brief", path=brief_path)
    criteria_path = tmp_path / "criteria.md"
    criteria_path.write_text("## Acceptance criteria\n\n| id | source | precondition | trigger | system | response | example | state |\n|---|---|---|---|---|---|---|---|\n")
    artefact_registry.register(conn, ticket_id=ticket_id, kind="criteria", path=criteria_path)
    return ticket_id


def test_a_plan_scope_touching_a_sensitive_path_applies_the_pilot_exclusion(tmp_path, monkeypatch):
    """R-S0-8: a plan whose own scope names a path `sensitive-paths.yaml` maps rejects the
    ticket through S3's own `exclusion` check_result and the `s3_exclusion` event."""
    conn = _conn(tmp_path)
    ticket_id = _s3_ready_ticket(conn, tmp_path)

    out_dir = tmp_path / "s3_out"
    out_dir.mkdir()
    (out_dir / "plan.md").write_text(
        "## Scope and discretion\n\n| path | action | reason |\n|---|---|---|\n"
        "| src/main/java/com/fixture/auth/Login.java | touch | touches auth |\n"
    )
    monkeypatch.setenv("FIXTURE_ADAPTER_OUT_DIR", str(out_dir))
    from runner.stages import run_stage
    outcome = run_stage(conn, ticket_id, "S3", runs_dir=tmp_path)

    assert outcome == "fail"
    ticket = record.get(conn, "ticket", ticket_id)
    assert ticket["state"] == "rejected"
    assert ticket["close_reason"] == "pilot_excluded"
    failed = conn.execute(
        "SELECT * FROM check_result WHERE check_name = 'exclusion' AND result = 'fail'"
    ).fetchall()
    assert len(failed) == 1




def test_an_s4_hand_backs_head_sha_change_alone_leaves_the_plan_tuple_current(tmp_path):
    conn = _conn(tmp_path)
    ticket_id, item_id = _planned_ticket_with_complete_checklist(conn, tmp_path)
    row = _latest_plan_tuple(conn, ticket_id)

    record.update(conn, "ticket", ticket_id, head_sha="deadbeef" * 5)
    ticket = record.get(conn, "ticket", ticket_id)
    currency = binding.plan_tuple_currency(conn, row["id"], plan_tuple.derive_components(conn, ticket))
    assert currency.current
    assert currency.changed == ()




def test_an_open_question_withholds_the_gate_even_with_full_approval(tmp_path):
    conn = _conn(tmp_path)
    ticket_id, item_id = _planned_ticket_with_complete_checklist(conn, tmp_path)
    record.insert(
        conn, "question", ticket_id=ticket_id, stage="S2", round=1, rank=1,
        options="[]", state="open", blocking=0,
    )
    ticket = record.get(conn, "ticket", ticket_id)
    assert gates.plan_review_gate(conn, ticket, runs_dir=tmp_path) is None




PLAN_FIELD_OVERRIDES = {name: f"changed-{name}" for name in binding.PLAN_COMPONENT_FIELDS}


@pytest.mark.parametrize("field_name", binding.PLAN_COMPONENT_FIELDS)
def test_a_changed_bound_field_alone_makes_the_tuple_no_longer_current(tmp_path, field_name):
    conn = _conn(tmp_path)
    ticket_id, item_id = _planned_ticket_with_complete_checklist(conn, tmp_path)
    row = _latest_plan_tuple(conn, ticket_id)
    ticket = record.get(conn, "ticket", ticket_id)
    baseline = plan_tuple.derive_components(conn, ticket)
    assert binding.plan_tuple_currency(conn, row["id"], baseline).current  # sanity: nothing drifted yet

    drifted = replace(baseline, **{field_name: PLAN_FIELD_OVERRIDES[field_name]})
    currency = binding.plan_tuple_currency(conn, row["id"], drifted)
    assert not currency.current
    assert field_name in currency.changed




def test_an_expired_approval_requires_a_fresh_one_on_the_same_subject(tmp_path):
    conn = _conn(tmp_path)
    ticket_id, item_id = _planned_ticket_with_complete_checklist(conn, tmp_path)
    row = _latest_plan_tuple(conn, ticket_id)
    slot = Slot(source_rule="s3_reviewer_role", role="s3_reviewer", owner=ABHISHEK, min_count=1)

    expired_id = approvals.record_approval(
        conn, gate="plan", subject_hash=row["content_hash"], slot_id=slot.slot_id, actor_identity=ABHISHEK,
        role="s3_reviewer", decision="approve", authority_policy_hash="policy-1", membership_snapshot_hash="members-1",
        attestation_version="v1", attestation_hash="att-expired", ticket_id=ticket_id,
        expires_at="2000-01-01T00:00:00+00:00",
    )
    ticket = record.get(conn, "ticket", ticket_id)
    assert gates.plan_review_gate(conn, ticket, runs_dir=tmp_path) is None  # expired: quorum unmet

    # `supersedes` names the expired row as this fresh approval's predecessor -- without it,
    # both rows are unsuperseded heads on the same (slot, actor), which `approvals.evaluate`
    # treats as a fork and refuses regardless of either row's own expiry.
    approvals.record_approval(
        conn, gate="plan", subject_hash=row["content_hash"], slot_id=slot.slot_id, actor_identity=ABHISHEK,
        role="s3_reviewer", decision="approve", authority_policy_hash="policy-1", membership_snapshot_hash="members-1",
        attestation_version="v1", attestation_hash="att-fresh", ticket_id=ticket_id, supersedes=expired_id,
    )
    ticket = record.get(conn, "ticket", ticket_id)
    assert gates.plan_review_gate(conn, ticket, runs_dir=tmp_path) == "plan_quorum_fresh"
