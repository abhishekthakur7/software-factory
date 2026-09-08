# T-A-09 brief: reviewer sets from CODEOWNERS and the owners file into slots, approval records, quorum

## What this delivers

`runner/reviewer_sets.py` already carried the `Slot` model and `merge_slots`.
This ticket adds the derivation half beside them, and nothing else:

- `read_codeowners(repo_path, sha)` — reads the CODEOWNERS blob at that
  commit with `git show`/`git rev-parse`, checking `.github/CODEOWNERS`,
  `CODEOWNERS`, then `docs/CODEOWNERS` in order, and parses it into `Rule`s
  (1-based line number, pattern, owner handles), skipping comments and
  blank lines.
- `match_rule(rules, path)` and `match_sensitive_path(sensitive_paths, path)`
  — a hand-written gitignore-style glob matcher (no `fnmatch`/`re`): `*`
  within one path segment, `**` across segments, a leading or interior `/`
  anchoring the pattern to the repository root, a trailing `/` folding into
  a directory-and-everything-under-it match, and a bare name (no `/`
  anywhere but a possible trailing one) matching at any depth. Both
  functions return the *last* matching rule, GitHub's own precedence.
- `resolve_owner(owners, handle)` — an `@identity` handle resolves when that
  identity holds some role in `owners.yaml`; a team handle, an email, or an
  identity absent from the policy are all unresolved.
- `derive_actual(conn, ...)` — for every changed path, decides sensitivity
  from the sensitive-paths mapping and ownership from CODEOWNERS first,
  falling back to the mapping's owner only for a path CODEOWNERS does not
  cover; a path neither source claims at all blocks the same way an
  unresolved owner does. Writes one `reviewer_set` row of kind `actual`
  carrying every hash and provenance field the schema already declares, and
  returns a `Derivation` (the row id, the slots, whether it's blocked, the
  unresolved handles/paths, whether a sensitive-path match fired, the
  routes open to the human, and `waivable=False`).
- `effective_set(conn, ...)` — writes the `effective` row from `merge_slots`
  over a planned list and a `Derivation`'s slots, carrying forward the
  actual row's identifying hashes.
- `is_current(conn, reviewer_set_id, ...)` — whether a stored `actual` row's
  path-set hash and base sha still match a given diff and base.
- `recompute_before_dispatch` — the S6 race guard; `derive_actual` under
  its own name so a dispatch path reads as "the guard fires."

Nothing here changes `Slot`, `merge_slots`, `runner/approvals.py`,
`runner/schema.py`, or any other module named as off-limits; `derive_actual`
and `effective_set` write through `record.insert`/`record.get` and hash
through `runner.canonical.content_hash`, exactly like every other write in
the record.

## Row covered

R-S6-6 (`docs/prd/04-S6-human-review.md`): the actual reviewer set is
derived from the exact diff using CODEOWNERS at the recorded
`target_base_sha`, pinned sensitive-path and owner mappings, and pinned
membership evidence; every path-to-rule-to-owner match is recorded; the
effective set merges planned/actual by canonical key (maximum count, union
of separation constraints, nonmatching slots preserved); a new or
unresolved owner blocks review-tuple creation with a non-sensitive-mismatch
route set, and an Initial sensitive-path match is restricted to
removal/`pilot_excluded`, neither waivable; S6 recomputes the same
derivation before dispatch as a race guard.

## Owner decisions this ticket follows

- CODEOWNERS/gitignore glob semantics are hand-written rather than built on
  `fnmatch`/`re`, per the ticket's explicit instruction, since a
  precedence bug here is exactly the failure this module exists to catch.
- `derive_actual`'s signature, field set on the `actual` row, and the
  `Derivation` shape (`id`, `slots`, `blocked`, `unresolved`, `sensitive`,
  `routes`, `waivable`) are fixed by the ticket text; this ticket
  implements them without renaming or reshaping.
- Criterion 5 (a seeded `distinct_from` blocking a shared actor) is proved
  through `approvals.evaluate` over slots read back from a derived
  `reviewer_set` row, never by a second separation check in this module.
- Criteria 9-11 stay pinned in `test_approval_records.py`; this ticket adds
  only the one thing that file didn't already assert — that a recorded
  approval's `slot_id`/`scope` trace back to an actual derived slot rather
  than a hand-typed string.

## Decisions made during the build that the design did not cover

- **A changed path neither CODEOWNERS nor `sensitive_paths` claims at all**
  is not named by any acceptance criterion. It is treated as blocking the
  same way an unresolved owner is (a `Slot` with `resolved=False`,
  `source_rule=f"unmatched:{path}"`, and the path itself recorded in
  `Derivation.unresolved`) rather than silently passing with no reviewer —
  an ungoverned path is a strictly worse situation than an unresolved one,
  never a better one, so it cannot fall through the gate unblocked.
- **Whether a sensitive-path match always forces the restricted route set,
  or only when the owner it names is also unresolved.** The ticket's "What
  this ticket builds" section states the two route cases in parallel — "for
  a non-sensitive unresolved mismatch ... for a sensitive-path match at
  this milestone" — without qualifying the second case as unresolved. This
  build takes that literally: any changed path the sensitive-paths mapping
  matches forces `sensitive=True` and the S4-removal/`pilot_excluded`
  routes, whether or not the owner resolves and whoever owns it. The
  reviewer of the merged branch corrected an earlier reading in which a
  path CODEOWNERS covered was never checked against the mapping: with a
  repository-wide `*` rule that would have hidden every sensitive path.
  Ownership precedence (CODEOWNERS wins) and sensitivity are two
  separate questions. `test_initial_sensitive_path_
  match_only_offers_removal_or_pilot_excluded_routes` seeds a *resolved*
  sensitive owner precisely to pin this reading down.
- **Precedence between the sensitive and non-sensitive-unresolved route
  sets when a diff has both.** `derive_actual` checks `sensitive` before
  `unresolved`, so a diff carrying any sensitive-path match always gets the
  stricter two-route set even if it also has an ordinary unresolved owner
  elsewhere — the stricter policy should never be silently loosened by an
  unrelated mismatch on the same diff.
- **`Rule`/`Codeowners` as new public dataclasses** (line, pattern, owners;
  path, blob sha, rules) — needed to carry the parsed file and its
  provenance between `read_codeowners` and `derive_actual`, and useful on
  their own for a caller that wants to inspect the raw rule set.
- **`sensitive_paths` is typed `dict[str, str]`** (glob to owner handle),
  matched with the same last-match-wins glob logic as CODEOWNERS itself,
  rather than a list of pairs — `sensitive-paths.yaml` parses directly into
  this shape and Python dicts preserve insertion order, which is all
  last-match-wins needs.
- **`owner_config_hash` is written as exactly the `authority_policy_hash`
  argument**, per the ticket's own parenthetical ("= the authority-policy
  hash"); `sensitive_path_hash` is computed inside `derive_actual` as
  `canonical.content_hash({"sensitive_paths": sensitive_paths})` over the
  mapping actually used for that derivation, since the ticket asks for a
  hash of "the sensitive-paths mapping used," and this module never reads
  the file itself (whoever loads `sensitive-paths.yaml` is a different
  ticket's concern).
- **`head_sha` is always `None` on an `actual` row** — `derive_actual`'s own
  signature has no `head_sha` parameter (only `target_base_sha`), so the
  "where given" clause on that column is simply never satisfied by this
  ticket's call shape.
- **`effective_set` carries forward the actual row's subject/base/head/
  path-set/CODEOWNERS/sensitive-path hashes** onto the effective row,
  rather than leaving them null, so the effective set stays traceable to
  the exact diff it was merged against without a second lookup.
- **`_reviewer_set_row` is a private helper mirroring `approvals.
  record_approval`'s row-building contract** (every declared column
  present, absent ones null, hash over the full row) so `derive_actual` and
  `effective_set` share one place that enforces it, the same way
  `approvals.py` has exactly one such place for `approval_record`.

## Out of scope

The plan/review evidence-tuple construction and the refusal of tuple
creation on an unresolved owner (T-A-10); waivers over a blocking blind
spot (T-A-32); the post-graduation distinct-owner rule (Milestone B); the
fixture project's real CODEOWNERS file (T-A-08, not yet built — tests here
build their own throwaway git repositories instead); loading
`sensitive-paths.yaml` or `owners.yaml` from `factory/config/` into this
module's parameters, which is a caller's concern; any change to
`runner/schema.py`, `runner/approvals.py`, `runner/canonical.py`,
`runner/gates.py`, `runner/owners.py`, or the `Slot`/`merge_slots`
definitions.
