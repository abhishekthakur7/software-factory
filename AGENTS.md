# AGENTS.md — working rules for soft-factory

## Comments

A comment you add must do one of three things:

1. **Explain why** — the trade-off, constraint, or rejected alternative.
2. **State a non-obvious invariant** — conditional field presence, ordering
   precondition, fail-closed contract, why a force-unwrap or a redundant-looking
   guard is safe.
3. **Warn** — platform quirk, thread hazard, TOCTOU race, macro workaround.

Never restate the adjacent line, narrate control flow, decorate (`// ====`),
or leave scaffolding chatter. Leave alone things that look like slop but are
deliberate: the same policy restated at each site it governs (each justifies a
different local decision), terse cross-references to rationale elsewhere,
numbered `// Step N:` sequences, and long owner-approved doc comments.

## Tests
- Every acceptance-criteria clause becomes at least one test; `must-reject:` /
  `must-fail:` clauses are mandatory negative tests. Use those prefixes only on
  tests that actually assert the rejection.
- Title the behaviour and cite the spec: New files use titled tests; in an existing file, match its idiom.
- The one question that decides whether a test earns its place: **does it
  assert something the implementation could get wrong, or only something the
  test just wrote down?
  Do not add:
  - **Echo-only** tests, whose assertion reads back a literal the test passed to
    a memberwise init or a one-line projection.
  - **Boundary-flag duplicates**: the same path and assertion as an existing
    test, differing only in a field the assertion never reads.
  - **Tautologies** that cannot fail against any implementation, including
    tests that exercise only the standard library or a helper defined in the
    test file.
  - Restatements of a neighbouring test's assertion with the same inputs.
- A test gated on a tool or a slow-test flag must skip loudly with
  `.enabled(if:)`, never `guard … else { return }`. A silent pass inflates the
  green count with tests that never ran.
- Never delete a test that pins a transformation, invariant, ordering,
  determinism, error path, boundary, default value, wire format, or a fixed
  defect. When in doubt, keep it.

## CodeGraph

When `.codegraph/` exists at the repo root, query it before grep or reading
files: the `codegraph_explore` MCP tool, or `codegraph explore "<symbols or
question>"` in the shell, returns the relevant source plus call paths in one
call. If there is no `.codegraph/`, skip it.
