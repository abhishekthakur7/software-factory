"""What an eval directory is: the complete set the tree entitles, and the completeness check each one owes.

`expected_eval_dirs` derives the full set from the files actually on disk
under `factory/` -- one directory per agent, skill, shared skill, runtime
adapter, `scripts/checks`/`scripts/tools` executable, and rubric, plus one
`sandbox/escape` directory when `config/sandbox/` holds OS profiles, plus
every `evals/tickets/<id>` directory already present, since a redacted
ticket fixture names no source file elsewhere to derive it from -- rather
than a hand-maintained list that drifts the moment a new file lands.
`factory/evals/fixture-project/` and `factory/evals/bootstrap/` are never
derived from anything under `factory/agents`, `factory/skills`,
`factory/rubrics`, `factory/scripts`, or `runtime.yaml`'s adapters, so
neither ever appears in the set.

`check` is the one completeness rule an eval directory must pass: it
exists, carries `eval.yaml`, names an `owner`, lists at least one case,
and at least one case's fixture is a real, non-empty file or directory.
A case whose `source` is `real_ticket_export` additionally needs a
`redaction_review` naming who reviewed it, when, what was redacted, and
the exported content's own hash; a `tickets/<id>` directory carries that
same four-field review at the top level instead, alongside the failure
modes its fixture is meant to exercise. `walk` runs `check` over every
directory `expected_eval_dirs` names, stopping at the first failure so
the reported directory is the one actually broken.
"""
import re
from pathlib import Path

import yaml

from runner.paths import FACTORY_DIR

# The redaction-review fields a real-ticket-export case, and a `tickets/`
# eval directory as a whole, must carry before either is considered
# redacted and reviewed -- one shape, so a reader never has to hold two.
_REDACTION_REVIEW_FIELDS = ("reviewer_identity", "reviewed_at", "redacted_fields", "export_content_hash")


class EvalDirectoryError(ValueError):
    """An eval directory fails completeness: absent, no `eval.yaml`, no owner, an empty case
    list, every case's fixture missing or empty, or an unreviewed real-ticket-export case."""


def _executable_names(script_dir: Path) -> list[str]:
    # A shared module a script imports (`packet_render.py`) carries a
    # suffix; the scripts meant to be run directly do not -- that split is
    # what tells the two apart on disk, not an executable-bit check alone.
    if not script_dir.is_dir():
        return []
    return sorted(
        p.name for p in script_dir.iterdir()
        if p.is_file() and p.suffix == "" and not p.name.startswith(".")
    )


def expected_eval_dirs(root: Path = FACTORY_DIR, runtime_path: Path | None = None) -> list[Path]:
    """Every eval directory the files under `root` currently entitle, derived from disk.

    `runtime_path` defaults to `root`'s own `config/runtime.yaml`; every
    adapter it names gets one `adapters/<name>` directory. Order is stable
    (agents, skills, shared skills, adapters, scripts/checks,
    scripts/tools, rubrics, tickets) but is not itself meaningful to a
    caller. `evals/tickets/<id>` is the one kind derived from `evals/`
    itself rather than from a source file elsewhere under `root`: a
    redacted ticket fixture has no other file that names it, so every
    directory already on disk there is expected.
    """
    if runtime_path is None:
        runtime_path = root / "config" / "runtime.yaml"
    evals_root = root / "evals"
    dirs: list[Path] = []

    dirs += [evals_root / "agents" / p.stem for p in sorted((root / "agents").glob("*.md"))]
    dirs += [evals_root / "skills" / p.stem for p in sorted((root / "skills").glob("*.md"))]
    dirs += [
        evals_root / "skills" / "shared" / p.stem
        for p in sorted((root / "skills" / "shared").glob("*.md"))
    ]

    if runtime_path.is_file():
        runtime_doc = yaml.safe_load(runtime_path.read_text()) or {}
        for adapter_name in sorted((runtime_doc.get("adapters") or {})):
            dirs.append(evals_root / "adapters" / adapter_name)

    if (root / "config" / "sandbox").is_dir():
        dirs.extend(evals_root / name for name in REQUIRED_MECHANICS)

    for kind in ("checks", "tools"):
        for name in _executable_names(root / "scripts" / kind):
            dirs.append(evals_root / "scripts" / kind / name)

    dirs += [evals_root / "rubrics" / p.stem for p in sorted((root / "rubrics").glob("*.md"))]

    if (evals_root / "tickets").is_dir():
        dirs += [
            evals_root / "tickets" / p.name
            for p in sorted((evals_root / "tickets").iterdir()) if p.is_dir()
        ]

    return dirs


REQUIRED_MECHANICS = (
    "sandbox/escape", "sandbox/copy-disposal", "record/incident-history",
    "record/control-history", "record/coverage-history",
)


def _fixture_exists_and_nonempty(fixture_path: Path) -> bool:
    if fixture_path.is_dir():
        return any(fixture_path.rglob("*"))
    return fixture_path.is_file() and fixture_path.stat().st_size > 0


def _redaction_review_missing_fields(review: dict) -> list[str]:
    """Which of `_REDACTION_REVIEW_FIELDS` `review` lacks -- `redacted_fields` must be a
    list (possibly empty: nothing needed redacting), the other three non-empty strings."""
    missing = []
    for field in _REDACTION_REVIEW_FIELDS:
        if field not in review:
            missing.append(field)
        elif field == "redacted_fields":
            if not isinstance(review[field], list):
                missing.append(field)
        elif not str(review[field]).strip():
            missing.append(field)
    return missing


def _check_redaction_review(eval_dir: Path, case: dict) -> None:
    if case.get("source", "synthetic") != "real_ticket_export":
        return
    review = case.get("redaction_review")
    name = case.get("name")
    if not isinstance(review, dict) or _redaction_review_missing_fields(review):
        raise EvalDirectoryError(
            f"{eval_dir}: real-ticket-export case {name!r} carries no redaction review "
            f"({', '.join(_REDACTION_REVIEW_FIELDS)})"
        )


def _check_ticket_redaction_review(eval_dir: Path, spec: dict) -> None:
    """A `tickets/<id>` eval directory carries its own redaction review at the top level,
    naming which failure modes the redacted export is meant to exercise."""
    review = spec.get("redaction_review")
    if not isinstance(review, dict) or _redaction_review_missing_fields(review):
        raise EvalDirectoryError(f"{eval_dir}: carries no redaction review ({', '.join(_REDACTION_REVIEW_FIELDS)})")
    modes = spec.get("target_failure_modes")
    if not isinstance(modes, list) or not modes or not all(
        isinstance(mode, str) and re.fullmatch(r"FM-\d{2}", mode) for mode in modes
    ):
        raise EvalDirectoryError(f"{eval_dir}: target failure-mode ids are required")


def check(eval_dir: Path) -> None:
    """Raise `EvalDirectoryError` on the first completeness problem `eval_dir` has; return nothing otherwise."""
    if not eval_dir.is_dir():
        raise EvalDirectoryError(f"{eval_dir}: directory absent")
    eval_yaml = eval_dir / "eval.yaml"
    if not eval_yaml.is_file():
        raise EvalDirectoryError(f"{eval_dir}: eval.yaml absent")
    spec = yaml.safe_load(eval_yaml.read_text()) or {}
    owner = spec.get("owner")
    if not owner or not str(owner).strip():
        raise EvalDirectoryError(f"{eval_dir}: eval.yaml carries no owner")
    cases = spec.get("cases")
    if not cases:
        raise EvalDirectoryError(f"{eval_dir}: eval.yaml carries an empty case list")

    has_fixture = False
    for case in cases:
        _check_redaction_review(eval_dir, case)
        fixture_rel = case.get("fixture")
        if fixture_rel and _fixture_exists_and_nonempty(eval_dir / fixture_rel):
            has_fixture = True
    if not has_fixture:
        raise EvalDirectoryError(f"{eval_dir}: no case names a fixture that exists and is non-empty")

    if eval_dir.parent.name == "tickets":
        _check_ticket_redaction_review(eval_dir, spec)

    if "/".join(eval_dir.parts[-2:]) in REQUIRED_MECHANICS:
        modes = spec.get("failure_modes")
        if not isinstance(modes, list) or not modes or not all(
            isinstance(mode, str) and re.fullmatch(r"FM-\d{2}", mode) for mode in modes
        ):
            raise EvalDirectoryError(f"{eval_dir}: target failure-mode ids are required")
        for case in cases:
            relative = case.get("fixture")
            if not isinstance(relative, str) or not relative:
                raise EvalDirectoryError(f"{eval_dir}: case {case.get('name')!r} has no fixture")
            fixture = (eval_dir / relative).resolve()
            files = list(fixture.rglob("*")) if fixture.is_dir() else [fixture]
            if (
                not fixture.is_relative_to(eval_dir.resolve())
                or any(not path.resolve().is_relative_to(eval_dir.resolve()) for path in files)
                or not any(path.is_file() and path.stat().st_size > 0 for path in files)
            ):
                raise EvalDirectoryError(f"{eval_dir}: missing or invalid fixture for {case.get('name')!r}")


def walk(root: Path = FACTORY_DIR) -> list[Path]:
    """Run `check` over every directory `expected_eval_dirs(root)` names; return that same list.

    Stops at the first failure -- `check`'s own error message already
    names the directory, so a caller need not re-derive which one broke.
    """
    dirs = expected_eval_dirs(root)
    for eval_dir in dirs:
        check(eval_dir)
    return dirs


def eval_dir_for_file(rel_path: str, root: Path = FACTORY_DIR) -> Path:
    """The eval directory an agent/skill/rubric file `rel_path` (e.g. `factory/agents/S1.md`) resolves to.

    Mirrors `expected_eval_dirs`'s own naming so a manifest entry's file
    reference and the completeness walk always agree on where its eval
    directory lives.
    """
    parts = Path(rel_path).parts
    if len(parts) < 2 or parts[0] != "factory" or parts[1] not in ("agents", "skills", "rubrics"):
        raise ValueError(f"not an agent/skill/rubric path under factory/: {rel_path!r}")
    kind = parts[1]
    if kind == "skills" and len(parts) == 4 and parts[2] == "shared":
        return root / "evals" / "skills" / "shared" / Path(parts[3]).stem
    return root / "evals" / kind / Path(parts[-1]).stem


def eval_dir_for_adapter(name: str, root: Path = FACTORY_DIR) -> Path:
    """The eval directory a `runtime.yaml` adapter name resolves to."""
    return root / "evals" / "adapters" / name
