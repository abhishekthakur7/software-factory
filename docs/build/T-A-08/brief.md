# T-A-08 brief: fixture project seed and git trees; typed recipe catalogue, validator, execution by id, the fixture project's recipes and impact method

## What this delivers

The pilot project the rest of the factory runs checks against, and the
mechanism that runs any command at all:

- `factory/evals/fixture-project/` — a tiny synthetic Java project (package
  `com.fixture`, two main classes, one under the sensitive
  `.../auth/` directory), its own vendored dependency repository
  (`vendor/`, Maven layout, depth-two chain: `strings` depends on `util`,
  source only, no committed jar), a `CODEOWNERS` file, and plain
  main-method test classes at three levels (`src/test`, `src/it`,
  `src/e2e`) that print one `ran: <FullyQualifiedClass>#<method>` line per
  method and exit non-zero on failure.
- `factory/config/project.yaml`, `service-tiers.yaml`, `ticket-types.yaml`,
  `sensitive-paths.yaml`, `artifact-to-service.yaml` — the fixture
  project's own rows: a T2 service, `small_feature`-eligible, one sensitive
  path, and a groupId:artifactId mapping with one authoritative and one
  partial entry so an absent artefact resolves `unknown`.
- `factory/config/command-recipes.yaml` — the typed recipe catalogue's five
  fixture-project entries (`fixture_lint`, `fixture_compile`,
  `fixture_unit`, `fixture_integration`, `fixture_e2e`), each naming its
  executable's committed sha256 digest, a typed argument vector, a fixed
  cwd role, permitted stages, timeout, expected exit codes, an
  environment-name allowlist, `network: none`, an output-retention rule,
  and, for the three test recipes, a `level` and `test_globs`.
- `factory/scripts/checks/{java_lint,java_compile,java_test,impact_scan}` —
  standalone wrapper scripts (no `runner` import) the recipes above and the
  impact method invoke; `factory/evals/scripts/checks/impact_scan/` holds
  `impact_scan`'s conformance fixtures (authoritative, partial, unknown).
- `runner/setup.py` — `materialise` turns the seed into a pinned,
  reproducible git repository outside `factory/` and the manifest, with the
  vendored jars built from source at materialisation time.
- `runner/git_trees.py` — `clone_for_ticket` (isolated clone, branch,
  worktree, unusable push URL), `record_head`, `plain_checkout`, and
  `throwaway_copy`.
- `runner/recipes.py` — `load_catalogue` (schema validation, the
  injection/redirection refusal before dispatch) and `run` (digest check,
  cwd-role bounds check, environment-allowlist enforcement, timeout and
  expected-exit-code handling, test-identity parsing).
- `runner/fs.py` gains `copy_tree`, the only sanctioned way any `runner/`
  module copies a directory tree; `runner/schema.py` marks the five ticket
  columns a ticket's git identity lives on (`base_sha`, `target_base_sha`,
  `branch`, `worktree_path`, `head_sha`) mutable, since they are pinned
  after the ticket row already exists and moved again only by the human's
  refresh-base and the S4 hand-back.

## Row covered

R-I-16 (`docs/prd/03-stage-interface.md`): commands are versioned typed
recipes, never plan-authored shell; a recipe's full schema; the catalogue
validator's before-dispatch refusals (injection, redirection, undeclared
executable, cwd escape, environment leak); the launcher's timeout and
expected-exit-code handling; invocation by catalogue id and typed values
only. R-S1-3 (`docs/prd/04-S1-context-gathering.md`) for `impact_scan`'s
direction/method/mapping/coverage evidence shape.

## Owner decisions this ticket follows

- The fixture project is package `com.fixture`, two main classes
  (`Greeter`, `auth.TokenChecker`), one vendored dependency chain
  (`com.fixturevendor:strings` depending on `com.fixturevendor:util`).
- Five fixture-project recipe ids, exactly as named in the ticket
  (`fixture_lint`, `fixture_compile`, `fixture_unit`, `fixture_integration`,
  `fixture_e2e`); `impact_scan` is a separate impact method, not a sixth
  catalogue recipe.
- The five ticket-identity columns on `ticket` (`base_sha`,
  `target_base_sha`, `branch`, `worktree_path`, `head_sha`) become mutable;
  nothing else in `runner/schema.py` changes; `USER_VERSION` becomes 5.

## Out of scope

Freshness at the three boundaries and `refresh-base` (a later ticket); the
pilot repository's own recipes and the security recipes; binding a recipe
result to a review tuple, the ordered S5 check list, result delivery to the
agent through the proxy, and the inline-truncation limit — all later
tickets. `runner/approvals.py`, `runner/reviewer_sets.py`,
`runner/canonical.py`, `runner/gates.py`, `runner/state_table.py`,
`runner/owners.py`, and the trust-profile/owners config files are untouched.

## Decisions made during the build that the design did not cover

- **`impact_scan` is not a catalogue recipe.** The ticket's "Wrapper
  scripts" section lists it alongside the Java wrappers, but
  `command-recipes.yaml`'s five ids are exactly the ones the ticket names
  for lint/compile/unit/integration/e2e; `import_scan` is `project.yaml`'s
  impact method and is invoked directly, matching R-S1-3's description of
  impact evidence as its own mechanism, distinct from R-I-16's command
  recipes. `factory/evals/scripts/checks/impact_scan/`'s own eval fixtures
  need no JDK at all, since the script only parses XML/YAML.
  - **`path`-typed placeholders are bounds-checked against `cwd_role`;
  `string`-typed placeholders are not.** The vendored classpath a lint,
  compile, or test recipe needs lives outside the checkout entirely (it
  belongs to `project.yaml`'s separate `vendor` location, or to a
  ticket-scoped throwaway build directory), so it is passed as a `string`
  placeholder, scanned for shell/redirection syntax like every value but
  not resolved against any single cwd role. Only a `path`-typed value is
  bounds-checked, matching the ticket's own three-type list assigning each
  type a different job.
- **`PATH` sits on every fixture recipe's `env_allowlist`.** Each recipe's
  executable is a `#!/usr/bin/env python3` script, and that script's own
  `javac`/`java` subprocess calls need `PATH` resolved; without it neither
  the interpreter nor the JDK tools could be found, whatever else the
  allowlist names.
- **`env_request` empty means "every allowlisted name env_source has."**
  The ticket's design section is silent on the caller-facing shape of
  environment selection beyond "a requested name outside the allowlist is
  refused"; making the empty case fall back to the full allowlist (rather
  than to nothing) means a straightforward recipe invocation does not have
  to enumerate every one of its own recipe's allowed names just to get the
  default behaviour, while a caller can still name a strict subset.
- **`runner/setup.py` uses `shutil.rmtree` directly for `force=True`
  replacement and for stripping `vendor/` out of a freshly copied
  checkout**, rather than adding a delete primitive to `runner/fs.py`. The
  ticket names exactly one `fs.py` addition (`copy_tree`) and one barrier
  extension (`shutil.copytree`); deletion under `runs/` is not a write into
  `factory/` and the barrier scanner does not gate it, so adding a second
  funnel function for a primitive the ticket never asked for would be
  scope creep, not safety.
- **Every internal `git commit` this ticket's modules make runs with
  `commit.gpgsign=false`.** `materialise` and `clone_for_ticket` create and
  commit into disposable, throwaway repositories; a host-wide commit-signing
  key would otherwise make an unattended run hang or fail for reasons
  having nothing to do with the fixture project itself.
- **The seed commit uses a fixed author, committer, and timestamp** (not
  just a fixed message) so that materialising the same seed tree twice
  always produces the same commit sha — a stronger, still-cheap reading of
  "reproducible."
- **`plain_checkout`'s first argument is whichever repository actually
  has the requested sha**, not always the shared project checkout: a base
  checkout reads from the shared source, but a head checkout reads from the
  ticket's own clone, since nothing is ever pushed back to the shared
  checkout and the head commit only exists in the ticket's clone.
- **`RecipeResult.tests_ran` is parsed whenever the recipe declares a
  `level`**, regardless of pass or fail, since a wrapper script prints its
  JSON identities after reporting every test it ran, including a run that
  ultimately fails.
- **`git_trees` tests for clone/worktree/checkout mechanics (criteria 14,
  15, 16) run against a trivial one-file git repository built in the test,
  not the materialised Java fixture project**, so they need no JDK; only
  the lint/compile/test recipe and `materialise` tests are JDK-gated.

## Test count

Before this ticket: 301 tests. After: 334 (12 in `test_recipes.py`, 21 in
`test_fixture_project.py`, 8 of which skip loudly without `javac`/`jar`).
