"""Reviewer slots: the canonical requirement a gate must see approved.

A slot is keyed by role, owner and source rule; that key, rendered as
`slot_id`, is what an `approval_record` names and what another slot's
`distinct_from` constraint points at. `merge_slots` builds the effective
set from a planned and an actual set: two slots sharing one key collapse to
the larger minimum count and the union of their separation constraints,
and every slot present on only one side is kept, so a path dropped from the
plan never silently drops the reviewer the plan promised. Derivation of the
actual set from a diff and CODEOWNERS lives beside this in the same module;
the slot model and the merge come first because approval quorum and
evidence tuples read slots without ever deriving one.
"""
import json
import sqlite3
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path

from runner import canonical, record, schema
from runner.owners import Owners


@dataclass(frozen=True)
class Slot:
    """One requirement slot. `role` xor `owner` is the canonical reviewer; both may be set when a role resolves to a person."""

    source_rule: str
    role: str | None = None
    owner: str | None = None
    matched_path: str | None = None
    pattern: str | None = None
    precedence: int | None = None
    min_count: int = 1
    # slot_ids whose satisfying actors must differ from this slot's actors.
    distinct_from: tuple[str, ...] = ()
    # False marks a new or unresolved owner: the slot blocks the gate.
    resolved: bool = True

    @property
    def key(self) -> tuple[str | None, str | None, str]:
        return (self.role, self.owner, self.source_rule)

    @property
    def slot_id(self) -> str:
        return "|".join(part or "" for part in self.key)

    def to_json(self) -> dict:
        return {**asdict(self), "slot_id": self.slot_id, "distinct_from": list(self.distinct_from)}

    @classmethod
    def from_json(cls, data: dict) -> "Slot":
        fields = {name: data[name] for name in cls.__dataclass_fields__ if name in data}
        fields["distinct_from"] = tuple(fields.get("distinct_from", ()))
        return cls(**fields)


def merge_slots(planned: list[Slot], actual: list[Slot]) -> list[Slot]:
    """The effective set: matching keys merge, everything else is preserved, order is planned-first then new actual keys."""
    merged: dict[tuple, Slot] = {slot.key: slot for slot in planned}
    for slot in actual:
        prior = merged.get(slot.key)
        if prior is None:
            merged[slot.key] = slot
            continue
        merged[slot.key] = Slot(
            source_rule=slot.source_rule,
            role=slot.role,
            owner=slot.owner,
            matched_path=slot.matched_path or prior.matched_path,
            pattern=slot.pattern or prior.pattern,
            precedence=slot.precedence if slot.precedence is not None else prior.precedence,
            min_count=max(prior.min_count, slot.min_count),
            distinct_from=tuple(sorted(set(prior.distinct_from) | set(slot.distinct_from))),
            resolved=prior.resolved and slot.resolved,
        )
    return list(merged.values())


# The GitHub locations checked, in order, for a repository's CODEOWNERS file.
CODEOWNERS_LOCATIONS: tuple[str, ...] = (".github/CODEOWNERS", "CODEOWNERS", "docs/CODEOWNERS")

# The routes a blocked derivation may offer, and the two situations that
# produce them. Neither set is waivable: an owner mismatch or a sensitive-path
# touch is exactly the situation waivers exist to not cover.
_NON_SENSITIVE_UNRESOLVED_ROUTES: tuple[str, ...] = ("planning", "implementation_removal", "abandon")
_SENSITIVE_ROUTES: tuple[str, ...] = ("implementation_removal", "pilot_excluded")


@dataclass(frozen=True)
class Rule:
    """One CODEOWNERS line: its 1-based line number, pattern, and owner handles."""

    line: int
    pattern: str
    owners: tuple[str, ...]


@dataclass(frozen=True)
class Codeowners:
    """A CODEOWNERS file read at one commit: which location held it, its blob sha, and its parsed rules."""

    path: str
    blob_sha: str
    rules: tuple[Rule, ...]


def _git_show(repo_path: Path, ref: str) -> str | None:
    """The text `git show ref` prints, or `None` when git refuses -- most often because the blob doesn't exist."""
    result = subprocess.run(
        ["git", "-C", str(repo_path), "show", ref], capture_output=True, text=True
    )
    return result.stdout if result.returncode == 0 else None


def _parse_codeowners(text: str) -> tuple[Rule, ...]:
    rules = []
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        pattern, *owners = stripped.split()
        rules.append(Rule(line=number, pattern=pattern, owners=tuple(owners)))
    return tuple(rules)


def read_codeowners(repo_path: Path, sha: str) -> Codeowners:
    """Read the CODEOWNERS blob committed at `sha`, checking the GitHub locations in order.

    Line numbers are counted over the raw file text (comments and blanks
    included) so `source_rule` on a derived slot points at the exact
    committed line an owner reads to find the rule that named them.
    Raises `LookupError` when none of the three locations holds a blob at
    `sha` -- there is no owner-less default, since "CODEOWNERS is absent"
    and "CODEOWNERS covers nothing" are different situations and only the
    parsed-rules path can tell them apart.
    """
    for location in CODEOWNERS_LOCATIONS:
        text = _git_show(repo_path, f"{sha}:{location}")
        if text is None:
            continue
        blob_sha = subprocess.run(
            ["git", "-C", str(repo_path), "rev-parse", f"{sha}:{location}"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        return Codeowners(path=location, blob_sha=blob_sha, rules=_parse_codeowners(text))
    raise LookupError(f"no CODEOWNERS file at {sha} in {', '.join(CODEOWNERS_LOCATIONS)}")


def _segment_glob_match(pattern: str, name: str) -> bool:
    """Whether `pattern` matches `name` within one path segment; `*` is the only wildcard, and it never crosses a `/`."""
    if not pattern:
        return not name
    if pattern[0] == "*":
        return _segment_glob_match(pattern[1:], name) or (bool(name) and _segment_glob_match(pattern, name[1:]))
    if not name or pattern[0] != name[0]:
        return False
    return _segment_glob_match(pattern[1:], name[1:])


def _pattern_segments(pattern: str) -> list[str]:
    """Turn one gitignore-style pattern into segments for `_segments_match`.

    A trailing `/` becomes a `**` suffix, so a directory pattern also
    matches everything under it. A pattern with no `/` anywhere else (a
    bare name) gets a `**` prefix instead, so it matches at any depth the
    way GitHub resolves an unanchored CODEOWNERS pattern; a leading `/` or
    an interior `/` both anchor the pattern to the repository root by
    leaving it without that prefix.
    """
    directory = pattern.endswith("/")
    core = pattern[:-1] if directory else pattern
    anchored = core.startswith("/")
    if anchored:
        core = core[1:]
    segments = core.split("/") if core else []
    if not anchored and len(segments) <= 1:
        segments = ["**", *segments]
    if directory:
        segments = [*segments, "**"]
    return segments


def _segments_match(pattern: list[str], path: list[str]) -> bool:
    if not pattern:
        return not path
    head, *rest = pattern
    if head == "**":
        if not rest:
            return True
        return any(_segments_match(rest, path[i:]) for i in range(len(path) + 1))
    if not path:
        return False
    return _segment_glob_match(head, path[0]) and _segments_match(rest, path[1:])


def _pattern_matches(pattern: str, path: str) -> bool:
    return _segments_match(_pattern_segments(pattern), path.split("/"))


def match_rule(rules: list[Rule], path: str) -> Rule | None:
    """The rule in `rules` that governs `path`: the last one whose pattern matches, or `None`.

    GitHub CODEOWNERS semantics are last-match-wins, the same as
    `.gitignore` -- a rule list is read top to bottom and a later, more
    specific rule overrides an earlier, broader one. Picking the wrong
    precedent here would hand a path to the wrong owner while looking
    exactly as authoritative as the right answer.
    """
    match = None
    for rule in rules:
        if _pattern_matches(rule.pattern, path):
            match = rule
    return match


def match_sensitive_path(sensitive_paths: dict[str, str], path: str) -> tuple[str, str] | None:
    """The `(glob, owner)` entry in `sensitive_paths` that governs `path`: the last matching one, or `None`.

    Uses the same glob syntax and last-match-wins precedence as
    `match_rule`, over `sensitive-paths.yaml`'s glob-to-owner mapping.
    """
    match = None
    for glob, owner in sensitive_paths.items():
        if _pattern_matches(glob, path):
            match = (glob, owner)
    return match


def resolve_owner(owners: Owners, handle: str) -> str | None:
    """The identity `handle` names, or `None` when it can't be resolved to one.

    Only a bare `@identity` handle can resolve, and only when that exact
    identity holds some role in `owners.yaml`. A team handle (`@org/team`),
    an email address, or an identity absent from the authority policy are
    all unresolved -- CODEOWNERS lets any of them stand in for an owner,
    but this factory's authority policy only ever names individual
    identities, so none of the other forms has anyone to resolve against.
    """
    if not handle.startswith("@"):
        return None
    identity = handle[1:]
    if not identity or "/" in identity:
        return None
    known_identities = {entry["identity"] for entry in owners.roles.values()}
    return identity if identity in known_identities else None


def _path_set_hash(changed_paths: list[str]) -> str:
    return canonical.content_hash({"changed_paths": sorted(changed_paths)})


def _subject_hash(changed_paths: list[str], target_base_sha: str) -> str:
    return canonical.content_hash({"changed_paths": sorted(changed_paths), "target_base_sha": target_base_sha})


def _reviewer_set_row(**fields) -> dict:
    """Every `reviewer_set` column, absent ones filled with `None`, with a fresh content hash.

    Mirrors `approvals.record_approval`'s row-building contract: the hash
    is taken over the full declared column set, not just the fields this
    call happened to pass, so it stays recomputable from the row alone
    without knowing which columns a given kind of row leaves null.
    """
    columns = {column.name for column in schema.table("reviewer_set").columns}
    unknown = set(fields) - columns
    if unknown:
        raise ValueError(f"reviewer_set has no column(s) {sorted(unknown)}")
    row = {**{name: None for name in columns}, **fields}
    row.pop("id")
    row["canonical_serialization_version"] = canonical.SERIALIZATION_VERSION
    row["content_hash"] = canonical.content_hash(row)
    return row


@dataclass(frozen=True)
class Derivation:
    """The result of deriving the actual reviewer set for one diff.

    `blocked` is true exactly when review-tuple creation must be refused:
    either an owner failed to resolve (`unresolved` names the offending
    handles or, for a path no rule covers at all, the path itself) or a
    changed path fell under a sensitive-path mapping (`sensitive`). `routes`
    names the dispositions open to the human in that case; `waivable` is
    always false, since neither situation is the kind a waiver covers.
    """

    id: int
    slots: tuple[Slot, ...]
    blocked: bool
    unresolved: tuple[str, ...]
    sensitive: bool
    routes: tuple[str, ...]
    waivable: bool


def _match_paths(
    codeowners: Codeowners, changed_paths: list[str], *, owners: Owners, sensitive_paths: dict[str, str],
    flag_unmatched: bool = True,
) -> tuple[list[Slot], list[str], bool]:
    """The `(slots, unresolved, sensitive)` a diff's paths derive against `codeowners` and `sensitive_paths`.

    Ownership and sensitivity are two separate questions. For ownership
    CODEOWNERS wins: a path it covers takes its owners from there, and the
    sensitive-path mapping supplies an owner only for a path CODEOWNERS
    does not cover. Sensitivity is decided for every path by the mapping
    alone, whoever owns it, since a repository-wide `*` rule must never
    hide that a diff touched an authentication or payments directory. A
    path neither source claims is unresolved the same way an owner that
    fails to resolve is, since nobody has been assigned to review it --
    `flag_unmatched=False` (the planned derivation's own case) skips that:
    a plan's intended scope naming no CODEOWNERS-covered or sensitive path
    simply adds nothing, since the real, later diff is what actually must
    resolve every touched path, not the plan's own forecast of it. One
    `Slot` is recorded per `(rule, owner)` match, so a rule naming several
    owners counts quorum against each individually; a sensitive path's
    slots carry the `sensitive_path_owner` role.
    """
    slots: list[Slot] = []
    unresolved: list[str] = []
    sensitive = False

    for path in sorted(changed_paths):
        sensitive_match = match_sensitive_path(sensitive_paths, path)
        rule = match_rule(codeowners.rules, path)
        if rule is not None:
            matches = [(f"CODEOWNERS:{rule.line}", rule.pattern, rule.line, handle) for handle in rule.owners]
        elif sensitive_match is not None:
            glob, handle = sensitive_match
            matches = [(f"sensitive_paths:{glob}", glob, None, handle)]
        else:
            if flag_unmatched:
                slots.append(Slot(source_rule=f"unmatched:{path}", matched_path=path, min_count=1, resolved=False))
                unresolved.append(path)
            continue
        sensitive = sensitive or sensitive_match is not None
        for source_rule, pattern, precedence, handle in matches:
            identity = resolve_owner(owners, handle)
            slot = Slot(
                source_rule=source_rule,
                role="sensitive_path_owner" if sensitive_match is not None else None,
                owner=identity or handle,
                matched_path=path,
                pattern=pattern,
                precedence=precedence,
                min_count=1,
                resolved=identity is not None,
            )
            slots.append(slot)
            if not slot.resolved:
                unresolved.append(slot.owner)

    return slots, unresolved, sensitive


def _routes_for(*, sensitive: bool, unresolved: list[str]) -> tuple[bool, tuple[str, ...]]:
    if sensitive:
        return True, _SENSITIVE_ROUTES
    if unresolved:
        return True, _NON_SENSITIVE_UNRESOLVED_ROUTES
    return False, ()


def derive_actual(
    conn: sqlite3.Connection,
    *,
    ticket_id: int,
    repo_path: Path,
    target_base_sha: str,
    changed_paths: list[str],
    owners: Owners,
    sensitive_paths: dict[str, str],
    authority_policy_hash: str,
    membership_snapshot_hash: str,
) -> Derivation:
    """Derive the actual reviewer set for `changed_paths` from CODEOWNERS at `target_base_sha`.

    Raises `LookupError` (from `read_codeowners`) when the repository
    carries no CODEOWNERS file at all -- an actual, real-diff derivation
    has nothing to fall back to. The row is written before this function
    returns, so its id is available for `effective_set` and `is_current`
    even when the derivation is blocked.
    """
    codeowners = read_codeowners(repo_path, target_base_sha)
    slots, unresolved, sensitive = _match_paths(codeowners, changed_paths, owners=owners, sensitive_paths=sensitive_paths)
    blocked, routes = _routes_for(sensitive=sensitive, unresolved=unresolved)

    row = _reviewer_set_row(
        ticket_id=ticket_id,
        kind="actual",
        subject_hash=_subject_hash(changed_paths, target_base_sha),
        base_sha=target_base_sha,
        path_set_hash=_path_set_hash(changed_paths),
        codeowners_path=codeowners.path,
        codeowners_blob_sha=codeowners.blob_sha,
        sensitive_path_hash=canonical.content_hash({"sensitive_paths": sensitive_paths}),
        owner_config_hash=authority_policy_hash,
        membership_snapshot_hash=membership_snapshot_hash,
        slots=json.dumps([slot.to_json() for slot in slots]),
    )
    row_id = record.insert(conn, "reviewer_set", **row)
    return Derivation(
        id=row_id,
        slots=tuple(slots),
        blocked=blocked,
        unresolved=tuple(sorted(set(unresolved))),
        sensitive=sensitive,
        routes=routes,
        waivable=False,
    )


def derive_planned(
    conn: sqlite3.Connection,
    *,
    ticket_id: int,
    repo_path: Path,
    target_base_sha: str,
    changed_paths: list[str],
    owners: Owners,
    sensitive_paths: dict[str, str],
    authority_policy_hash: str,
    membership_snapshot_hash: str,
) -> Derivation:
    """Derive the planned reviewer set from the plan's own `Scope and discretion` paths.

    Shares `_match_paths` with `derive_actual` -- the same CODEOWNERS and
    sensitive-path matching over a path list -- with two differences: the
    Initial pilot's own fixed planning slot (`plan_reviewer_role`, owned by
    `owners.yaml`'s `plan_reviewer`) is always included, on top of whatever
    CODEOWNERS or the sensitive-path map add, since Initial always needs a
    human planning reviewer even for a plan that touches nothing either source
    covers; and a repository with no CODEOWNERS file at all contributes no
    CODEOWNERS-derived slot rather than raising, since a plan's own
    intended scope is not itself evidence that the repository must carry
    that file the way a real, already-happened diff is.
    """
    try:
        codeowners = read_codeowners(repo_path, target_base_sha)
    except LookupError:
        # No CODEOWNERS file anywhere in the repo: an empty rule set, not a
        # skipped match -- `_match_paths` still runs below, so the
        # sensitive-path mapping (which owes nothing to CODEOWNERS) is
        # still consulted regardless of whether the file exists.
        codeowners = Codeowners(path=None, blob_sha=None, rules=())
    slots, unresolved, sensitive = _match_paths(
        codeowners, changed_paths, owners=owners, sensitive_paths=sensitive_paths, flag_unmatched=False,
    )

    pilot_identity = owners.roles["plan_reviewer"]["identity"]
    pilot_slot = Slot(source_rule="plan_reviewer_role", role="plan_reviewer", owner=pilot_identity, min_count=1)
    all_slots = [pilot_slot, *slots]
    blocked, routes = _routes_for(sensitive=sensitive, unresolved=unresolved)

    row = _reviewer_set_row(
        ticket_id=ticket_id,
        kind="planned",
        subject_hash=_subject_hash(changed_paths, target_base_sha),
        base_sha=target_base_sha,
        path_set_hash=_path_set_hash(changed_paths),
        codeowners_path=codeowners.path,
        codeowners_blob_sha=codeowners.blob_sha,
        sensitive_path_hash=canonical.content_hash({"sensitive_paths": sensitive_paths}),
        owner_config_hash=authority_policy_hash,
        membership_snapshot_hash=membership_snapshot_hash,
        slots=json.dumps([slot.to_json() for slot in all_slots]),
    )
    row_id = record.insert(conn, "reviewer_set", **row)
    return Derivation(
        id=row_id,
        slots=tuple(all_slots),
        blocked=blocked,
        unresolved=tuple(sorted(set(unresolved))),
        sensitive=sensitive,
        routes=routes,
        waivable=False,
    )


def effective_set(conn: sqlite3.Connection, *, ticket_id: int, planned: list[Slot], actual: Derivation) -> int:
    """Write the `effective` row: `merge_slots` over `planned` and `actual`'s slots.

    The row carries forward the actual row's identifying hashes (subject,
    base/head sha, path set, CODEOWNERS and sensitive-path provenance) so
    the effective set stays traceable to the exact diff it was merged
    against, without recomputing anything `derive_actual` already settled.
    """
    merged = merge_slots(planned, list(actual.slots))
    actual_row = record.get(conn, "reviewer_set", actual.id)
    row = _reviewer_set_row(
        ticket_id=ticket_id,
        kind="effective",
        subject_hash=actual_row["subject_hash"],
        base_sha=actual_row["base_sha"],
        head_sha=actual_row["head_sha"],
        path_set_hash=actual_row["path_set_hash"],
        codeowners_path=actual_row["codeowners_path"],
        codeowners_blob_sha=actual_row["codeowners_blob_sha"],
        sensitive_path_hash=actual_row["sensitive_path_hash"],
        owner_config_hash=actual_row["owner_config_hash"],
        membership_snapshot_hash=actual_row["membership_snapshot_hash"],
        slots=json.dumps([slot.to_json() for slot in merged]),
    )
    return record.insert(conn, "reviewer_set", **row)


def is_current(conn: sqlite3.Connection, reviewer_set_id: int, *, changed_paths: list[str], target_base_sha: str) -> bool:
    """Whether the stored reviewer-set row `reviewer_set_id` still describes this diff and base.

    Compares the row's own `path_set_hash`/`base_sha` against fresh values
    computed from `changed_paths`/`target_base_sha`, rather than
    re-deriving the set, since staleness is a question about identity, not
    about whether CODEOWNERS itself has moved.
    """
    row = record.get(conn, "reviewer_set", reviewer_set_id)
    if row is None:
        return False
    return row["path_set_hash"] == _path_set_hash(changed_paths) and row["base_sha"] == target_base_sha


# The human-review race guard: the same derivation run again immediately before packet
# assembly and dispatch, writing a fresh row every call. Named so a dispatch
# path reads as "the race guard fires" rather than as an ordinary derivation.
recompute_before_dispatch = derive_actual
