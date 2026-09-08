#!/usr/bin/env python3
"""Sync docs/build/<ticket-id>/{brief.md,plan.md} into factory/evals/bootstrap/<ticket-id>/.

Every ticket's own builder writes its brief and plan under `docs/build/`
before building; this tool copies that pair, byte for byte, into the
bootstrap eval directory so R-F-2's completeness walk has a real fixture
set that grows with the tickets, rather than one hand authored and left to
rot. A ticket whose `docs/build/` pair has since been removed loses its
bootstrap copy too, so the fixture set never outlives its source.

The sibling `eval.yaml`'s `tickets:` mapping (which eval directories each
ticket's build exercised) is computed here from each plan's own "Files
touched" text, not typed by hand: a path naming an agent/skill/rubric file,
or a `scripts/checks`/`scripts/tools` executable, or an eval directory
directly, resolves to the eval directory it names -- checked against the
real directories `runner.evals.expected_eval_dirs` currently lists, so a
stale or invented path is silently dropped rather than fabricated.

Usage: python3 tools/bootstrap_fixtures.py [repo-root]
"""
import re
import sys
from pathlib import Path

_REPO_ROOT_DEFAULT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT_DEFAULT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT_DEFAULT))

import yaml  # noqa: E402

from runner import evals  # noqa: E402

PAIR_FILES = ("brief.md", "plan.md")
_PATH_TOKEN_RE = re.compile(r"`(factory/[^`]+)`")


def _valid_eval_dir_rels(factory_root: Path) -> set[str]:
    evals_root = factory_root / "evals"
    return {str(p.relative_to(evals_root)) for p in evals.expected_eval_dirs(factory_root)}


def _agent_skill_rubric_rel(token: str) -> str | None:
    """A rubric/agent/skill markdown path (e.g. `factory/rubrics/S3.md`) -> its eval-dir relpath."""
    parts = token.rstrip("/").split("/")
    if len(parts) < 3 or parts[0] != "factory" or parts[1] not in ("agents", "skills", "rubrics"):
        return None
    if not parts[-1].endswith(".md"):
        return None
    stem = parts[-1][: -len(".md")]
    if parts[1] == "skills" and len(parts) == 4 and parts[2] == "shared":
        return f"skills/shared/{stem}"
    if len(parts) != 3:
        return None  # a nested path (e.g. rubrics/checklists/*.md) names no rubric of its own
    return f"{parts[1]}/{stem}"


def _script_rel(token: str) -> str | None:
    """A `factory/scripts/checks|tools/<name>` executable path -> its eval-dir relpath."""
    parts = token.rstrip("/").split("/")
    if len(parts) != 4 or parts[0] != "factory" or parts[1] != "scripts" or parts[2] not in ("checks", "tools"):
        return None
    return f"scripts/{parts[2]}/{parts[3]}"


def _evals_rel(token: str, valid: set[str]) -> str | None:
    """A path already under `factory/evals/<rel>/...` -> the `rel` eval directory it sits inside."""
    if not token.startswith("factory/evals/"):
        return None
    candidate = token[len("factory/evals/"):].rstrip("/")
    for rel in valid:
        if candidate == rel or candidate.startswith(rel + "/"):
            return rel
    return None


def eval_dirs_exercised(plan_text: str, valid: set[str]) -> list[str]:
    """Every eval directory (relative to `factory/evals/`) `plan_text` names, directly or through
    the agent/skill/rubric file or `scripts/checks`|`scripts/tools` executable it points at.

    Only paths matching a directory `valid` (i.e. `runner.evals.expected_eval_dirs`
    actually lists today) are kept, so a typo, a shorthand range, or a path to
    something that no longer exists never fabricates a mapping entry.
    """
    found: set[str] = set()
    for token in _PATH_TOKEN_RE.findall(plan_text):
        rel = _evals_rel(token, valid) or _agent_skill_rubric_rel(token) or _script_rel(token)
        if rel is not None and rel in valid:
            found.add(rel)
    return sorted(found)


def _render_eval_yaml(tickets_mapping: dict[str, list[str]]) -> str:
    doc = {
        "owner": "abhishek",
        "subject": "docs/build",
        "tickets": {ticket_id: tickets_mapping[ticket_id] for ticket_id in sorted(tickets_mapping)},
    }
    return yaml.safe_dump(doc, sort_keys=False, default_flow_style=False)


def sync(root: Path) -> list[str]:
    """Copy every docs/build ticket pair into `factory/evals/bootstrap/`, drop orphaned copies,
    and rewrite the bootstrap `eval.yaml`'s ticket -> eval-directory mapping.

    Returns a change log, one line per file added, updated, or removed; an
    empty list means the bootstrap tree already matches what this run would
    produce.
    """
    build_dir = root / "docs" / "build"
    factory_root = root / "factory"
    bootstrap_dir = factory_root / "evals" / "bootstrap"
    valid = _valid_eval_dir_rels(factory_root)

    changes: list[str] = []
    tickets = sorted(
        p.name for p in build_dir.iterdir()
        if p.is_dir() and all((p / f).is_file() for f in PAIR_FILES)
    )
    existing_bootstrap = (
        {p.name for p in bootstrap_dir.iterdir() if p.is_dir()} if bootstrap_dir.is_dir() else set()
    )

    tickets_mapping: dict[str, list[str]] = {}
    for ticket_id in tickets:
        source_dir = build_dir / ticket_id
        dest_dir = bootstrap_dir / ticket_id
        dest_dir.mkdir(parents=True, exist_ok=True)
        for filename in PAIR_FILES:
            source_bytes = (source_dir / filename).read_bytes()
            dest_path = dest_dir / filename
            if not dest_path.is_file() or dest_path.read_bytes() != source_bytes:
                dest_path.write_bytes(source_bytes)
                changes.append(f"updated {dest_path.relative_to(root)}")
        tickets_mapping[ticket_id] = eval_dirs_exercised((source_dir / "plan.md").read_text(), valid)

    for stray in sorted(existing_bootstrap - set(tickets)):
        stray_dir = bootstrap_dir / stray
        for filename in PAIR_FILES:
            stray_path = stray_dir / filename
            if stray_path.is_file():
                stray_path.unlink()
        try:
            stray_dir.rmdir()
        except OSError:
            pass
        changes.append(f"removed {stray_dir.relative_to(root)} (source ticket gone)")

    eval_yaml_path = bootstrap_dir / "eval.yaml"
    new_eval_yaml = _render_eval_yaml(tickets_mapping)
    if not eval_yaml_path.is_file() or eval_yaml_path.read_text() != new_eval_yaml:
        eval_yaml_path.write_text(new_eval_yaml)
        changes.append(f"updated {eval_yaml_path.relative_to(root)}")

    return changes


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    root = Path(argv[0]).resolve() if argv else _REPO_ROOT_DEFAULT
    changes = sync(root)
    for change in changes:
        print(change)
    if not changes:
        print("nothing changed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
