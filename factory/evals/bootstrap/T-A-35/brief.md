# T-A-35 brief: eval directories complete, manifest test, bootstrap fixtures, the gate

## What this delivers

The completeness walk R-F-2 promises: `runner/evals.py` derives, from the
files actually on disk under `factory/`, the full set of eval directories
every agent, skill, shared skill, runtime adapter, `scripts/checks` and
`scripts/tools` executable, and rubric currently entitles, and checks each
one for a real owner, a non-empty case list, at least one case whose
fixture exists and is non-empty, and (for a case exporting a real ticket)
a recorded redaction review. `runner/manifest.py` calls that same check
while loading the real project manifest, so a stage entry can never point
at an eval directory that fails it -- an empty fixture list cannot enter
the manifest, exactly as R-F-2 requires.

The three Java recipe wrappers T-A-01 stubbed without eval directories
(`java_compile`, `java_lint`, `java_test`) each get one: a real two-file
Java source tree the wrapper actually runs over, proven by a new
`runner/tests/test_recipe_wrappers.py` that skips loudly without a JDK.
Every eval directory that was still missing an `owner` line -- the
`cursor_sdk` adapter and six rubric/script directories besides the ones
the ticket brief named -- gets one, since the completeness walk this
ticket builds would otherwise fail over the real tree from the first
commit.

`tools/bootstrap_fixtures.py` copies every `docs/build/<ticket-id>/`
brief/plan pair into `factory/evals/bootstrap/<ticket-id>/`, byte for
byte, and computes -- from each plan's own file list, never by hand --
which eval directories that ticket's build exercised, writing the mapping
into `factory/evals/bootstrap/eval.yaml`. `runner/gate.py` becomes the
real three-step adoption gate: the manifest hash and the last commit that
touched `factory/` (both from local git history, no network call), the
eval-directory walk, then the test suite itself, exiting non-zero on any
step's failure.

Rows covered: R-F-2 (the completeness walk, the missing eval directories,
the bootstrap fixtures), R-F-4 (the manifest hash changing with any
`factory/` edit, the gate as the one adoption path).

## Owner decisions this ticket follows

- **The eval-directory set is derived, never hand-listed.**
  `expected_eval_dirs` walks `factory/agents/*.md`, `factory/skills/*.md`,
  `factory/skills/shared/*.md`, `runtime.yaml`'s adapters,
  `factory/scripts/{checks,tools}/*` (an executable is a file with no
  suffix; `packet_render.py` carries one and so is a shared module, not a
  script of its own), and `factory/rubrics/*.md` (`checklists/` excluded,
  since a checklist is never referenced as a rubric). `fixture-project/`
  and `bootstrap/` are built from neither list and so never appear.
- **A fixture is a file or a directory, not only a directory.** The
  original nine-directory check assumed every case's fixture was a
  directory; the adapter eval directory's cases each name a JSON file.
  `check` accepts either: a non-empty file, or a directory containing at
  least one file.
- **The manifest's own eval-directory check only fires over the real
  project manifest**, guarded on `root == REPO_ROOT` inside `_load_stages`.
  Every synthetic manifest fixture already in the suite (`test_manifest.py`,
  `test_manifest_hash.py`) names tiny stand-in agent/skill/rubric files
  under a fixture root with no `evals/` tree of their own; without the
  guard, loading any of them would fail for a reason unrelated to what
  that fixture tests. The four tiny manifests under
  `factory/evals/scripts/tools/manifest_hash/fixtures/` are never reached
  by `manifest.load` at all -- they drive the `manifest_hash` script
  directly, as a subprocess, and carry no `stages:` block for `load` to
  parse in the first place.
- **The bootstrap ticket-to-eval-directory mapping is computed from each
  plan's backtick-quoted `factory/`-rooted paths**, matched against
  `runner.evals.expected_eval_dirs`'s real, current set: a rubric/agent/
  skill markdown path, a `scripts/checks`|`scripts/tools` executable
  path, or a path already under an eval directory, each resolve to the
  eval directory they name; anything else (a config path, a glob
  shorthand like `S1..S4`, a path to something no longer real) is
  silently dropped rather than guessed at.

## Explicitly out

R-F-14's sandbox-escape and copy-disposal fixtures (need the OS sandbox,
sit at a later milestone). The Later quality harness, calibrated graders,
and branch-protection enforcement (R-F-3, R-F-8, R-F-9) -- this ticket's
gate proves mechanics, not subjective quality, exactly as R-F-14 already
scopes it.
