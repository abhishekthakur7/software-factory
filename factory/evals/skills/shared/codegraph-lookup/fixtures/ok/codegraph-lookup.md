---
name: codegraph-lookup
kind: skill
stage: shared
---

# Look up the codegraph before you grep

When `.codegraph/` exists at the repository root, query it before
searching by hand: it returns the relevant source together with call paths
in one call, so you see a symbol's real callers and callees instead of a
hand-swept guess from text matching.

## How

- MCP tool: `codegraph_explore` with a symbol name or a plain-language
  question ("who calls Greeter#greet", "what maps a Maven package to a
  service").
- Shell fallback, same query shape: `codegraph explore "<symbols or
  question>"`.

## When

- Before grepping a checkout for a symbol's usages (context gathering,
  archaeology).
- Before proposing a new utility, helper, or pattern (spec and plan): the
  codegraph is where you find the existing near-duplicates a new
  abstraction must cite or reject.
- Before touching a file during implementation: confirm what already
  calls the code you are about to change.

## If there is no `.codegraph/`

Skip straight to grep and the checkout; this skill adds nothing when the
index does not exist, and asking for it anyway wastes a call.
