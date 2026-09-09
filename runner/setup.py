"""Materialise the pilot project's seed into a pinned git repository.

`factory/evals/fixture-project/` is a committed seed tree: source code, its
own `vendor/` dependency repository, `CODEOWNERS`, and nothing else. Neither
the materialised checkout nor its vendor jars belong in the manifest hash --
they are generated state under the gitignored `runs/` tree, rebuilt by this
module whenever the pilot project needs a fresh pinned copy, not a change an
engineer reviews as a diff.

`javac`/`jar` are invoked as subprocesses; the jars and class files they
write land on disk through the OS, never through a Python `open()` this
module calls, so the write barrier has nothing to enforce here beyond what
it already enforces on `fs.copy_tree`.
"""
import os
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from runner import fs, project as project_config
from runner.paths import FACTORY_DIR, REPO_ROOT

DEFAULT_PROJECT_CONFIG = project_config.DEFAULT_PROJECT_CONFIG_PATH
DEFAULT_SEED_DIR = FACTORY_DIR / "evals" / "fixture-project"

# Fixed identity and timestamp for the seed commit, so materialising the
# same seed tree twice always produces the same commit sha.
_COMMIT_AUTHOR_NAME = "Fixture Seed"
_COMMIT_AUTHOR_EMAIL = "fixture-seed@example.invalid"
_COMMIT_DATE = "2020-01-01T00:00:00+00:00"
_COMMIT_MESSAGE = "Seed the fixture project"


class SetupError(Exception):
    """Materialisation cannot proceed: an existing checkout, or a build failure."""


@dataclass(frozen=True)
class Materialised:
    checkout: Path
    vendor: Path
    head_sha: str


def _git(args: list[str], cwd: Path, env: dict | None = None) -> subprocess.CompletedProcess:
    # commit.gpgsign is forced off for this internal, disposable repository:
    # its commits are throwaway fixture state, and a host-wide signing key
    # would otherwise make an unattended materialise() hang or fail.
    full_env = {**os.environ, **env} if env else None
    return subprocess.run(
        ["git", "-c", "commit.gpgsign=false", *args],
        cwd=cwd,
        env=full_env,
        capture_output=True,
        text=True,
        check=True,
    )


def _init_git_repo(checkout: Path, target_branch: str) -> str:
    _git(["init", "-q"], cwd=checkout)
    _git(["checkout", "-q", "-b", target_branch], cwd=checkout)
    _git(["add", "-A"], cwd=checkout)
    commit_env = {
        "GIT_AUTHOR_NAME": _COMMIT_AUTHOR_NAME,
        "GIT_AUTHOR_EMAIL": _COMMIT_AUTHOR_EMAIL,
        "GIT_AUTHOR_DATE": _COMMIT_DATE,
        "GIT_COMMITTER_NAME": _COMMIT_AUTHOR_NAME,
        "GIT_COMMITTER_EMAIL": _COMMIT_AUTHOR_EMAIL,
        "GIT_COMMITTER_DATE": _COMMIT_DATE,
    }
    _git(["commit", "-q", "-m", _COMMIT_MESSAGE], cwd=checkout, env=commit_env)
    return _git(["rev-parse", "HEAD"], cwd=checkout).stdout.strip()


def _strip_namespace(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _parse_pom_identity_and_deps(pom_path: Path) -> tuple[tuple[str, str, str], list[tuple[str, str, str]]]:
    """((groupId, artifactId, version), [dependency (groupId, artifactId, version), ...])."""
    root = ET.parse(pom_path).getroot()
    fields = {}
    for child in root:
        name = _strip_namespace(child.tag)
        if name in ("groupId", "artifactId", "version"):
            fields[name] = (child.text or "").strip()
    identity = (fields["groupId"], fields["artifactId"], fields["version"])

    dependencies = []
    for deps_el in root:
        if _strip_namespace(deps_el.tag) != "dependencies":
            continue
        for dep_el in deps_el:
            if _strip_namespace(dep_el.tag) != "dependency":
                continue
            dep_fields = {}
            for f in dep_el:
                name = _strip_namespace(f.tag)
                if name in ("groupId", "artifactId", "version"):
                    dep_fields[name] = (f.text or "").strip()
            dependencies.append((dep_fields["groupId"], dep_fields["artifactId"], dep_fields["version"]))
    return identity, dependencies


def _vendor_build_order(vendor_path: Path) -> list[tuple[tuple[str, str, str], Path]]:
    """[(artifact identity, pom path), ...] with every dependency before its dependent.

    Raises `SetupError` on a dependency cycle, which would otherwise make
    the topological walk below loop forever.
    """
    artifacts: dict[tuple[str, str, str], tuple[Path, list[tuple[str, str, str]]]] = {}
    for pom_path in sorted(vendor_path.rglob("*.pom")):
        identity, deps = _parse_pom_identity_and_deps(pom_path)
        artifacts[identity] = (pom_path, deps)

    ordered: list[tuple[tuple[str, str, str], Path]] = []
    visited: set[tuple[str, str, str]] = set()
    in_progress: set[tuple[str, str, str]] = set()

    def visit(identity: tuple[str, str, str]) -> None:
        if identity in visited:
            return
        if identity in in_progress:
            raise SetupError(f"vendor dependency cycle at {identity}")
        if identity not in artifacts:
            return  # dependency outside the vendored repository: nothing to build
        in_progress.add(identity)
        pom_path, deps = artifacts[identity]
        for dep in deps:
            visit(dep)
        in_progress.discard(identity)
        visited.add(identity)
        ordered.append((identity, pom_path))

    for identity in artifacts:
        visit(identity)
    return ordered


def _build_vendor_jars(vendor_path: Path) -> None:
    built_jars: list[str] = []
    for (_group_id, artifact_id, version), pom_path in _vendor_build_order(vendor_path):
        src_dir = pom_path.parent / "src"
        java_files = sorted(str(p) for p in src_dir.rglob("*.java"))
        if not java_files:
            continue
        jar_path = pom_path.parent / f"{artifact_id}-{version}.jar"
        with TemporaryDirectory() as tmp:
            classes_dir = Path(tmp)
            javac_cmd = ["javac", "-d", str(classes_dir)]
            if built_jars:
                javac_cmd += ["-cp", os.pathsep.join(built_jars)]
            javac_cmd += java_files
            subprocess.run(javac_cmd, check=True, capture_output=True, text=True)
            subprocess.run(
                ["jar", "cf", str(jar_path), "-C", str(classes_dir), "."],
                check=True,
                capture_output=True,
                text=True,
            )
        built_jars.append(str(jar_path))


def materialise(
    project_path: Path = DEFAULT_PROJECT_CONFIG,
    seed_dir: Path = DEFAULT_SEED_DIR,
    repo_root: Path = REPO_ROOT,
    force: bool = False,
) -> Materialised:
    """Materialise `seed_dir` as a pinned git repository at `project_path`'s checkout.

    Refuses an existing checkout unless `force=True`, in which case the
    prior checkout and vendor directory are removed first. Nothing this
    writes lands under `factory/`: the checkout and vendor directories are
    generated state under `repo_root`, resolved from `project_path`'s
    `checkout`/`vendor` fields.
    """
    config = project_config.pilot(path=project_path)
    checkout = Path(repo_root) / config["checkout"]
    vendor = Path(repo_root) / config["vendor"]

    if checkout.exists():
        if not force:
            raise SetupError(f"checkout already exists: {checkout} (pass force=True to replace it)")
        fs.remove_tree(checkout)
    if vendor.exists():
        if not force:
            raise SetupError(f"vendor directory already exists: {vendor} (pass force=True to replace it)")
        fs.remove_tree(vendor)

    fs.copy_tree(Path(seed_dir), checkout)
    fs.remove_tree(checkout / "vendor")  # vendor/ is materialised separately, beside the checkout

    fs.copy_tree(Path(seed_dir) / "vendor", vendor)
    _build_vendor_jars(vendor)

    head_sha = _init_git_repo(checkout, config["target_branch"])
    return Materialised(checkout=checkout, vendor=vendor, head_sha=head_sha)
