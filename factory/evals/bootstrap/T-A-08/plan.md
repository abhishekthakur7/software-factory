# T-A-08 plan

## Steps

| # | Step | Files touched | Proves |
|---|---|---|---|
| 1 | Write barrier: `copy_tree`, the only sanctioned directory-tree copy in `runner/`; extend the scanner's copy/move primitive list. | `runner/fs.py`, `runner/tests/test_write_barrier.py` | existing write-barrier tests, unchanged in count, now also guard `shutil.copytree` |
| 2 | Mark the five ticket columns a ticket's git identity lives on mutable, with one comment explaining why; bump `USER_VERSION`; extend the hand-written mutable allowlist. | `runner/schema.py`, `runner/db.py`, `runner/tests/test_mutable_exceptions.py` | `test_mutable_exceptions.py`'s allowlist-driven tests, now covering `base_sha`, `target_base_sha`, `branch`, `worktree_path`, `head_sha` |
| 3 | Seed the fixture project: two main classes (one sensitive), a depth-two vendored dependency chain (source only, no jar), `CODEOWNERS`, and plain main-method tests at three levels. | `factory/evals/fixture-project/**` | `test_fixture_project.py` criteria 10, 11 |
| 4 | Seed the fixture project's own config rows. | `factory/config/project.yaml`, `service-tiers.yaml`, `ticket-types.yaml`, `sensitive-paths.yaml`, `artifact-to-service.yaml` | `test_fixture_project.py` criteria 10, 11, 12, 19 |
| 5 | `runner/setup.py`: `materialise` — copy the seed (without `vendor/`) via `fs.copy_tree`, copy `vendor/` beside it, build each vendored artefact's jar from source in dependency order, commit the checkout with a fixed, reproducible identity. | `runner/setup.py` | `test_fixture_project.py` criteria 11, 13 |
| 6 | `runner/git_trees.py`: `clone_for_ticket` (clone, branch, worktree, unusable push URL, `base_sha`/`target_base_sha` recorded), `record_head`, `plain_checkout`, `throwaway_copy`. | `runner/git_trees.py` | `test_fixture_project.py` criteria 14, 15, 16 |
| 7 | Wrapper scripts: `java_lint`, `java_compile`, `java_test`, `impact_scan`, standalone. | `factory/scripts/checks/*` | `test_fixture_project.py` criteria 17, 18, 19 |
| 8 | The typed recipe catalogue: five fixture-project recipes, each field the schema requires, with the committed wrapper's real sha256 as `executable_digest`. | `factory/config/command-recipes.yaml` | `test_recipes.py` criterion 1; `test_fixture_project.py` criteria 17, 18 |
| 9 | `runner/recipes.py`: `load_catalogue` (schema validation, injection/redirection refusal) and `run` (digest check, cwd-role bounds check, environment allowlist, timeout, expected exit codes, test-identity parsing). | `runner/recipes.py` | `test_recipes.py` criteria 1-9 |
| 10 | `impact_scan`'s conformance fixtures: authoritative, partial, and unknown coverage. | `factory/evals/scripts/checks/impact_scan/**` | `test_fixture_project.py` criterion 19 |
| 11 | Injection, redirection, undeclared-executable, cwd-escape, environment-leak, timeout, and expected-result fixtures, plus the tests that drive them. | `runner/tests/fixtures/command-recipes/**`, `runner/tests/test_recipes.py` | criteria 1-9 |
| 12 | The fixture-project test suite: seed shape, materialisation, git trees (against a throwaway git repository, no JDK needed), the five recipes by id, and `impact_scan`. | `runner/tests/test_fixture_project.py` | criteria 10-19 |
| 13 | Every new file under `factory/` except `factory/evals/fixture-project/**` added to the manifest, with its real sha256. | `factory/manifest.yaml` | `test_manifest_hash.py`'s real-manifest test |
| 14 | This ticket's own brief and plan. | `docs/build/T-A-08/brief.md`, `docs/build/T-A-08/plan.md` | reviewed by the human, not a test |

## Test strategy

`test_recipes.py` never touches the real fixture project: each of its nine
criteria gets a tiny, purpose-built catalogue fixture and, where the recipe
must actually run, a tiny committed Python script as its executable. Two
fixtures (`cwd_escape.yaml`, `env_leak.yaml`) carry a `{{DIGEST}}` template
token in place of a literal `executable_digest`, filled in by the test with
the real sha256 of the fixture script's current bytes, so the accepting
half of each scenario proves the boundary or allowlist check itself, not an
incidental digest mismatch; the digest-mismatch fixture (`wrong_digest.yaml`)
is the only one with a deliberately wrong, hand-written digest. The
environment tests go one step further than "not refused": `print_env.py`
echoes the one variable it was given, so the accepting test can show the
child process saw `env_source`'s value even when `os.environ` holds a
different one for the same name under `monkeypatch` — proof `recipes.run`
never reads `os.environ` itself, not just that it does not leak a
particular secret.

`test_fixture_project.py` splits along the JDK boundary on purpose. Criteria
10, 12, and 19, and the structural half of 11 (no registry endpoint named
anywhere), read the committed seed and config directly and need no
toolchain. Criteria 14, 15, and 16 — clone/worktree/push-url,
base/head plain checkouts, and throwaway copies — are exercised against a
trivial one-file git repository built inline in the test, since git_trees'
mechanics do not depend on what language the checkout holds; this also
means a missing JDK cannot mask a git-tree regression. Only materialising
the seed (which always builds the vendored jars) and actually invoking
lint/compile/test recipes need `javac`/`jar`, so exactly those tests carry
`@skip_without_jdk` (`pytest.mark.skipif(not HAS_JAVAC, ...)`), evaluated
before any fixture that would otherwise shell out to a missing toolchain.
The lint recipe is exercised on both a clean copy (pass) and a throwaway
copy with an injected syntax error (fail), so a validator that always
reports `pass` cannot pass the suite. `impact_scan`'s own eval fixtures
(authoritative, partial, unknown) are read from `eval.yaml` and
parametrized, in the same shape `test_manifest_hash.py` already uses for
`manifest_hash`'s conformance cases; one further test points the `unknown`
fixture's dependency at a mapping file that maps a *different* artefact, to
show that an absent entry, not merely an empty mapping file, is what drives
`unknown`.

## Verification

`uv run pytest -q` — 334 tests pass (301 before this ticket, plus 12 in
`test_recipes.py` and 21 in `test_fixture_project.py`); 8 of the 21 in
`test_fixture_project.py` skip loudly without `javac`/`jar` on `PATH`.
