# T-A-30 brief, part one: the S5 scripts and the regression-only comparison

## What this delivers

The four standalone scripts S5's blocking tier will call, the pure
regression-only comparison the S5 driver applies over lint/compile/
integration/end-to-end recipe output, and their eval directories and
tests. The S5 driver itself -- wiring these into `runner/stages/S5.py`'s
ordered check list, opening the review tuple, and the two criteria that
need a live driver run (public-compatibility blind spots triggering the
exclusion gate, and the full ordered pass over base and head checkouts)
-- is the next wave's work, built on top of these scripts.

- `factory/scripts/checks/scope_diff` -- `--diff --plan`. Files the diff
  touches, minus the plan's `Scope and discretion` `touch`/`create`/
  `delete` paths, minus its `discretion` globs (`fnmatch`). No import of
  `subprocess`, `socket`, `requests`, `urllib`, `http` or `runner`, and no
  checkout argument: the diff text and the plan text alone (R-S5-4,
  criteria 1-3).
- `factory/scripts/checks/source_declaration_diff` -- `--base --head
  --files --plan`. A regex extractor over Java source for public/
  protected class/interface/enum/record/method/constructor/field
  declarations in the touched files named by `--files`; matches base
  against head by kind, owner class and bare method/field name (a
  parameter-list change on an existing method is one `changed` finding,
  not a spurious remove-plus-add pair) and normalises each into a
  signature string. An added or removed declaration no `Contracts` row
  names is `unplanned`; a `changed` declaration whose `Contracts` row
  marks `source_declaration` `unchanged` is `unchanged_but_changed`;
  either non-empty is `fail` (R-S5-5, criteria 4-6). Beyond the six
  fields the ticket brief names, the printed JSON also carries `touched`
  (every path named by `--files`) and `all_declarations` (every
  declaration found at base and head, not only the added/removed/changed
  ones) -- `behavior_contract_evidence` has no `--base`/`--head`/`--files`
  of its own, so this is the only channel it has back to facts about the
  touched files; see "decisions this brief did not already settle" below.
- `factory/scripts/checks/behavior_contract_evidence` -- `--plan
  --verdicts --tests-base --tests-head --declarations --generated-paths`.
  Checks that every `Contracts` field cell with state `changed` or
  `unchanged`, and every R-S3-20 verdict, points to a test identity
  `--tests-head` actually ran or a plan characterization task; anything
  else is a blind spot naming the item. Runs six lax, independent
  detections over `--declarations` and `--generated-paths`: missing
  grammar or unit, inheritance, reflection, generated API, binary
  compatibility, and unchecked behavioural change (a `changed` cell with
  no evidence). A missing verdict evidence link is the only thing that
  fails the check on its own; every other gap is a blind spot, never a
  fail by itself (R-S5-5, criteria 7-8).
- `factory/scripts/checks/base_test_diff` -- `--base --head --globs
  [--globs-base] --plan --tests-base --tests-head`. Compares the test-file
  globs against both checkouts and the test identities each side's test
  recipe reported. A file matching the globs that differs between base
  and head (edited or deleted), a base test identity absent from head
  (covers a rename, since the old identity simply stops appearing), or a
  base-glob-matched file no longer matched by a narrower head glob
  (`--globs-base` is what lets the script tell "narrowed" apart from
  "never covered") is `unplanned` unless the plan's `Test strategy` table
  names it with action `change`/`remove` and a non-empty `criteria` cell;
  any `unplanned` entry is `fail` (R-S4-10's four detections -- edited,
  deleted, renamed, excluded through configuration). The both-views
  rerun and the `deviation` row R-S4-10 also describes are the next
  wave's work.
- `runner/checks/regression_only.py` (new, pure) -- `compare_diagnostics`
  and `compare_tests` return a `Comparison(new_or_worse, inherited)` over
  normalised, counted diagnostic lines or test identities; `governs`
  reports true only for `check_name == "regression_only"` over the lint,
  compile, integration-test and end-to-end-test kinds (R-S5-10,
  criteria 10-13, 15).
- `factory/lints/` stays a placeholder; a test walks it and asserts
  nothing there declares a blocking rule under a reserved name
  (criterion 14).
- Eval directories under `factory/evals/scripts/checks/` for all four
  scripts, and `runner/tests/test_s5_scope_diff.py`,
  `test_s5_declaration_diff.py`, `test_s5_regression_only.py`,
  `test_s5_base_test_diff.py`.
- `factory/manifest.yaml` -- every new file under `factory/` added.

## Rows covered

R-S5-4, R-S5-5, R-S5-10 (`docs/prd/04-S5-cleanup-pass.md`); R-S4-10's
four detections (`docs/prd/04-S4-implementation.md`), for what
`base_test_diff` detects -- not R-S4-10's both-views rerun, `deviation`
row, or evidence-table listing, which stay the next wave's.

## Owner decisions this ticket follows

Scripts take files and directories, never a database connection or a
`runner` import; each prints one JSON line and exits 0 on a failed check,
non-zero only on a usage error; test identity JSON is exactly what
`factory/scripts/checks/java_test` prints on its last line; blind spots
are entries, never a fail on their own -- a missing required evidence
link is what fails a check.

## Decisions this brief did not already settle

- **The exit-code convention diverges from `size_gate`'s.**
  `factory/scripts/checks/size_gate` (an earlier ticket, not touched
  here) returns 1 on a failed check. This wave's brief is explicit --
  "non-zero exit only for a usage error, never for a failed check" -- so
  every script this ticket adds returns 0 whether `result` is `pass` or
  `fail`, reading the JSON `result` field as the source of truth. The
  next wave's driver, which will call both vintages, needs to know this:
  it cannot treat a script's exit code as the failed-check signal
  uniformly across `size_gate` and this ticket's four scripts.
- **`source_declaration_diff`'s printed JSON carries two fields beyond
  the six the ticket brief names: `touched` and `all_declarations`.**
  `behavior_contract_evidence` needs to know the full touched-file set
  (for the generated-API detection) and every declaration found at base
  and head, not only the added/removed/changed ones (for the "unit named
  in the plan absent from both checkouts" and inheritance detections),
  and its own argument list has no `--base`/`--head`/`--files` to derive
  either from itself -- `--declarations` is its only input describing the
  touched files at all. Rather than inventing a second script surface or
  quietly widening `behavior_contract_evidence`'s CLI beyond its own
  ticket-fixed signature, the extra facts ride inside the JSON
  `source_declaration_diff` already produces, alongside a matching
  extension to its `limitations` list (`"unparsable: <path>"` and
  `"reflection: <path>"` entries) as the channel for the two detections
  that need to know about a touched file's raw text rather than its
  declarations.
- **`behavior_contract_evidence`'s two evidence rules split into a fail
  path and a blind-spot path.** The ticket brief states both "every
  Contracts field cell ... must carry evidence ... anything else is a
  blind spot" and, separately, "a missing required evidence link is a
  fail" -- read together, the fail path is reserved for a verdict's
  `evidence_ids` being empty (a structural requirement, the same shape as
  `handback_structure`'s own missing-field failures elsewhere in this
  codebase), while a `Contracts` field cell with missing or unresolved
  evidence is always a blind spot (named "unchecked behavioural change"
  when the cell's state is `changed`), since it is inherently a judgment
  call a human or a waiver resolves, not a structural defect the script
  itself can refuse outright.
- **Declaration identity for methods and constructors excludes parameter
  types; the printed `name` includes them.** Matching base against head
  by `(kind, owner, bare_name)` -- not `(kind, owner, bare_name,
  parameter_types)` -- is what turns a parameter-list change on an
  existing method into one `changed` finding instead of a spurious
  remove-plus-add pair (criterion 6 exists to catch exactly this). This
  means a fixture that used a true overload (two methods sharing a bare
  name with different parameter lists) would collide under this scheme;
  no fixture in this ticket's eval directories does, and the next wave
  inherits this limitation along with the rest of the regex extractor's
  documented ones.
- **`base_test_diff`'s "renamed" detection has no file-level signal of
  its own.** A rename shows up because the old class's test identity
  stops appearing in `--tests-head`'s `ran` list (the same mechanism that
  also catches a test that simply stopped compiling under its old name);
  the fixture that exercises it pairs a deleted old-named file with a
  new file that carries a different class name, so the same case also
  happens to appear once under `changed_files` (reason `deleted`) -- that
  overlap is expected, not a bug to fix.

## Out of scope

The S5 driver itself (`runner/stages/S5.py`'s real body): opening the
review tuple, wiring `size_gate` and these four scripts plus the
regression-only comparison into the ordered check list over real base/
head checkouts, the public-compatibility blind spot triggering
`runner/checks/exclusion.py` (criterion 9), and the full-pass criterion
that needs a live run over the fixture project's own recipes
(criterion 16). The both-views rerun and `deviation` row R-S4-10
describes beyond the four detections. The waiver mechanism a blind spot
advances through. Security recipes, dependency verification, and
copy-on-write copies (AB milestone).
