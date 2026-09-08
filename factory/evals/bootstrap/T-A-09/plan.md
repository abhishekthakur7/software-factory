# T-A-09 plan

## Steps

| # | Step | Files touched | Proves |
|---|---|---|---|
| 1 | `Rule`/`Codeowners` dataclasses; `read_codeowners` via `git show`/`git rev-parse` over the three GitHub locations, in order; `_parse_codeowners` skipping comments/blanks. | `runner/reviewer_sets.py` | `test_reviewer_sets.py`'s pinned-sha test (criteria 1, 8) |
| 2 | The hand-written glob matcher: `_segment_glob_match`, `_pattern_segments`, `_segments_match`, `_pattern_matches`; `match_rule` and `match_sensitive_path` as last-match-wins over it. | `runner/reviewer_sets.py` | the same pinned-sha test's precedence assertions, and the CODEOWNERS-wins-over-sensitive-paths test |
| 3 | `resolve_owner`: `@identity` resolves only against a role in `owners.yaml`; a team handle, an email, or an unknown identity are unresolved. | `runner/reviewer_sets.py` | the unresolved-owner test (criterion 3) |
| 4 | `_path_set_hash`, `_subject_hash`, `_reviewer_set_row` (full-column-set hashing, mirroring `approvals.record_approval`). | `runner/reviewer_sets.py` | the pinned-sha test's content-hash assertion |
| 5 | `Derivation`; `derive_actual`: match CODEOWNERS first, fall through to `sensitive_paths` only for a path CODEOWNERS doesn't cover, block an uncovered path the same as an unresolved owner; sensitive routes win over non-sensitive-unresolved routes when both are present; writes the `actual` row. | `runner/reviewer_sets.py` | criteria 1, 3, 4, 8 |
| 6 | `effective_set`: `merge_slots` over planned and a `Derivation`'s slots, carrying the actual row's hashes forward onto the effective row. | `runner/reviewer_sets.py` | criterion 2 |
| 7 | `is_current`: compares a stored row's `path_set_hash`/`base_sha` against freshly computed ones. | `runner/reviewer_sets.py` | criterion 7 |
| 8 | `recompute_before_dispatch`: the named S6 race-guard entry point, calling `derive_actual` again. | `runner/reviewer_sets.py` | criterion 6 |
| 9 | Fixtures: two CODEOWNERS files (one with several rules of differing precedence plus a team handle, one with an unknown identity and an email), a `sensitive-paths.yaml` mapping, an `owners.yaml` with two distinct known identities, and a planned/actual collision case. | `runner/tests/fixtures/reviewer_sets/` | every new test below |
| 10 | Extend `test_reviewer_sets.py` with the git-repo-building helpers and seven new tests (criteria 1, 2, 3, 4, 5, 7, 8), leaving the four existing merge/slot-id tests untouched. | `runner/tests/test_reviewer_sets.py` | criteria 1, 2, 3, 4, 5, 7, 8 |
| 11 | `test_race_guard.py`: recompute matches S5 when nothing moved, diverges when the diff moved. | `runner/tests/test_race_guard.py` | criterion 6 |
| 12 | One added test in `test_approval_records.py`: a recorded approval's `slot_id`/`scope` trace back to a real derived slot. | `runner/tests/test_approval_records.py` | the one thing criteria 9-11's existing tests didn't already assert |
| 13 | This ticket's own brief and plan. | `docs/build/T-A-09/brief.md`, `docs/build/T-A-09/plan.md` | reviewed by the human, not a test |

## Test strategy

Every new test in `test_reviewer_sets.py` builds a real throwaway git
repository in `tmp_path` (`_init_repo`/`_commit_codeowners`), commits a
CODEOWNERS fixture, and reads it back at that exact commit's sha —
`test_derive_actual_records_every_path_to_rule_to_owner_match_at_the_pinned_
target_base_sha` then commits a *second*, materially different CODEOWNERS
on top and asserts the derivation still reflects the first commit, so a
regression that reads `HEAD` instead of the pinned sha fails. The
CODEOWNERS precedence fixture is hand-traced against real GitHub semantics
before being committed (rather than "whatever the matcher happens to
return"): three rules match `src/legacy/special.py`, and only the last
one's owner should win.

The planned/actual collision test loads a YAML fixture of planned slots
into real `Slot` objects and merges them against a real derivation (not a
second hand-built `merge_slots` call) through `effective_set`, so it
exercises this ticket's row-writing path, not the merge function alone
(already pinned by the pre-existing tests in this file).

Criterion 5 is deliberately not tested by adding a second separation
check anywhere: it takes two slots a real derivation produced, seeds a
`distinct_from` onto one (as an owner/trust-profile config would), writes
that as a fresh row, reads it back with `Slot.from_json`, and calls
`approvals.evaluate` — proving the seam between this module's row shape
and the existing quorum function, not re-implementing quorum.

`test_race_guard.py` imports `test_reviewer_sets.py`'s repo-building
helpers directly (both live in the `runner.tests` package) rather than
duplicating git setup, and asserts the two race-guard properties named by
criterion 6 literally: same diff → identical `content_hash` on a fresh row;
moved diff → different `content_hash` and `path_set_hash`.

The one addition to `test_approval_records.py` derives a real actual
reviewer set and records an approval against its one slot, then asserts
the stored `slot_id`/`scope` equal that slot's own `slot_id`/`matched_path`
— everything else about the row shape, quorum, and forked heads was
already pinned by that file before this ticket.

## Decisions the design did not cover

See "Decisions made during the build that the design did not cover" in
`brief.md` — the unmatched-path block, the sensitive-route precedence
reading, and the row-building/hash-carrying conventions.

## Verification

`uv run pytest -q` — 311 tests pass (301 before this ticket): 7 new tests
in `test_reviewer_sets.py` (11 total, 4 pre-existing untouched), 2 new in
`test_race_guard.py`, and 1 new in `test_approval_records.py` (9 total, 8
pre-existing untouched).
