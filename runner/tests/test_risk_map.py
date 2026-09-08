"""The risk map's churn-window computation (R-S3-11), and the plan-side floor `plan_rubric.risk_map_places` applies to it.

`factory/scripts/checks/risk_map` scores every candidate from git alone,
before the S3 agent ever runs; this file drives it over a repository built
here (`factory/evals/scripts/checks/risk_map/eval.yaml`'s
`churn_window_cases`, read separately from the `cases` key
`runner/tests/test_s3_structure.py` already parametrizes over its own
smaller repo) with four files chosen to hit each named-entry rule at
once: a single-author file with the highest churn-times-size score (top
decile), a three-author file no one holds 40 percent of (no clear
owner), a file whose one commit sits outside the twelve-month window
(excluded from the count entirely, not merely outside the top decile),
and a quiet file that is named for neither reason. `risk_map_places`
checks the plan's own `Risk map` table against that computed candidate
count -- the floor it enforces, and that a named place always carries a
`why` -- and the seeded `human_verdict` fixture for the R-S3-11 grader
line completes the row's checklist coverage.
"""
import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

from runner import artefacts
from runner.checks import plan_rubric
from runner.paths import FACTORY_DIR

RISK_MAP = FACTORY_DIR / "scripts" / "checks" / "risk_map"
EVAL_DIR = FACTORY_DIR / "evals" / "scripts" / "checks" / "risk_map"
EVAL_SPEC = yaml.safe_load((EVAL_DIR / "eval.yaml").read_text())
LIMITS = yaml.safe_load((FACTORY_DIR / "config" / "limits.yaml").read_text())

_COMMIT_ENV = {"GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@example.invalid", "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@example.invalid"}


def _git(args, cwd, env=None):
    full_env = {**os.environ, **env} if env else None
    return subprocess.run(["git", "-c", "commit.gpgsign=false", *args], cwd=cwd, env=full_env, capture_output=True, text=True, check=True)


def _author_env(name: str, *, when: str | None = None) -> dict:
    env = {**_COMMIT_ENV, "GIT_AUTHOR_NAME": name, "GIT_COMMITTER_NAME": name}
    if when:
        env["GIT_AUTHOR_DATE"] = when
        env["GIT_COMMITTER_DATE"] = when
    return env


def _churn_window_repo(tmp_path) -> Path:
    """Four files, each set up to hit exactly one named-entry rule (or none) at once.

    `old.txt`'s one commit is dated well outside the twelve-month churn
    window (500 days back, computed from the real clock so the fixture
    never goes stale); every other commit uses the real current time.
    """
    repo = tmp_path / "churn-window-repo"
    repo.mkdir()
    _git(["init", "-q"], repo)
    _git(["checkout", "-q", "-b", "main"], repo)
    old_date = (datetime.now(timezone.utc) - timedelta(days=500)).strftime("%Y-%m-%dT%H:%M:%S+00:00")

    # big.txt: one author, three commits, growing to the largest final size
    # in the candidate set -- the clear top-decile churn-times-size winner.
    (repo / "big.txt").write_text("x" * 50 + "\n")
    _git(["add", "-A"], repo)
    _git(["commit", "-q", "-m", "big v1"], repo, env=_author_env("Ada"))
    (repo / "big.txt").write_text("x" * 100 + "\n")
    _git(["commit", "-qam", "big v2"], repo, env=_author_env("Ada"))
    (repo / "big.txt").write_text("x" * 150 + "\n")
    _git(["commit", "-qam", "big v3"], repo, env=_author_env("Ada"))

    # shared.txt: three authors, one commit each -- no author reaches the
    # configured 40 percent share, so it is named for having no clear owner.
    (repo / "shared.txt").write_text("y" * 20 + "\n")
    _git(["add", "-A"], repo)
    _git(["commit", "-q", "-m", "shared v1"], repo, env=_author_env("Ada"))
    (repo / "shared.txt").write_text("y" * 21 + "\n")
    _git(["commit", "-qam", "shared v2"], repo, env=_author_env("Bao"))
    (repo / "shared.txt").write_text("y" * 22 + "\n")
    _git(["commit", "-qam", "shared v3"], repo, env=_author_env("Cy"))

    # old.txt: one commit, dated outside the churn window -- `--since-as-filter`
    # must exclude it, leaving zero commits (no clear owner) rather than
    # letting it silently truncate the walk for the commits made after it.
    (repo / "old.txt").write_text("z" * 30 + "\n")
    _git(["add", "-A"], repo)
    _git(["commit", "-q", "-m", "old commit"], repo, env=_author_env("Ada", when=old_date))

    # quiet.txt: one author, one commit, small size -- neither top decile
    # nor ownerless, the baseline "not worth naming" case.
    (repo / "quiet.txt").write_text("q\n")
    _git(["add", "-A"], repo)
    _git(["commit", "-q", "-m", "quiet v1"], repo, env=_author_env("Ada"))
    return repo


def _run(case: dict, repo: Path) -> dict:
    fixture = EVAL_DIR / case["fixture"]
    result = subprocess.run(
        [
            str(RISK_MAP), "--checkout", str(repo), "--branch", case["branch"], "--candidates", str(fixture / "candidates.txt"),
            "--months", str(case["months"]), "--min-share", str(case["min_share"]),
        ],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize("case", EVAL_SPEC["churn_window_cases"], ids=[c["name"] for c in EVAL_SPEC["churn_window_cases"]])
def test_churn_window_scoring_matches_the_seeded_expectation(tmp_path, case):
    """R-S3-11: the churn window is computed from git, per candidate, before any agent runs."""
    repo = _churn_window_repo(tmp_path)
    payload = _run(case, repo)
    expected = json.loads((EVAL_DIR / case["expected"]).read_text())
    assert payload == expected


def test_a_commit_outside_the_window_is_excluded_from_the_count_not_merely_unnamed(tmp_path):
    """R-S3-11: the window filters the whole walk (`--since-as-filter`), not just the top-decile ranking."""
    case = next(c for c in EVAL_SPEC["churn_window_cases"] if c["name"] == "churn_window")
    payload = _run(case, _churn_window_repo(tmp_path))
    old = next(c for c in payload["candidates"] if c["path"] == "old.txt")
    assert old["commits"] == 0


def test_the_top_decile_and_no_clear_owner_entries_are_named_for_different_reasons(tmp_path):
    """R-S3-11: churn-times-size ranking and the ownership-share floor are independent named-entry rules."""
    case = next(c for c in EVAL_SPEC["churn_window_cases"] if c["name"] == "churn_window")
    payload = _run(case, _churn_window_repo(tmp_path))
    by_path = {c["path"]: c for c in payload["candidates"]}
    assert by_path["big.txt"]["reason"] == "top_decile_churn_size"
    assert by_path["shared.txt"]["reason"] == "no_clear_owner"
    assert by_path["quiet.txt"]["named"] is False


# --- the plan's own Risk map table against the computed candidate count ---


def test_the_plan_names_at_least_one_place_per_computed_candidate_when_that_is_fewer_than_the_configured_floor():
    plan = artefacts.parse("## Risk map\n\n| place | why |\n|---|---|\n| big.txt | top-decile churn-times-size, worth a look |\n")
    findings = plan_rubric.risk_map_places(plan, limits=LIMITS, risk_map_candidate_count=1)
    assert findings == []  # one candidate computed, one place named: the floor is 1, not the configured 3


def test_must_reject_a_plan_naming_fewer_places_than_the_computed_candidate_count():
    plan = artefacts.parse("## Risk map\n\n| place | why |\n|---|---|\n")
    findings = plan_rubric.risk_map_places(plan, limits=LIMITS, risk_map_candidate_count=2)
    assert any(f.rule == "risk_map_places" for f in findings)


def test_must_reject_a_named_place_with_an_empty_why():
    plan = artefacts.parse("## Risk map\n\n| place | why |\n|---|---|\n| big.txt |  |\n")
    findings = plan_rubric.risk_map_places(plan, limits=LIMITS, risk_map_candidate_count=1)
    assert any(f.rule == "risk_map_places" for f in findings)


# --- the seeded human_verdict scenario for the risk-map grader line ---


def test_the_seeded_human_verdict_fixture_names_its_rubric_line_and_a_fail_verdict():
    fixture = yaml.safe_load((EVAL_DIR / "fixtures" / "human_verdict" / "R-S3-11.yaml").read_text())
    assert fixture["rubric_line_id"] == "R-S3-11:grader"
    assert fixture["verdict"] == "fail"
