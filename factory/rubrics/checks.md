---
name: cleanup-pass-rubric
kind: rubric
stage: checks
---

The cleanup-pass stage's rubric: script-only lines over the blocking-tier
checks the checks driver runs. Every line here is mechanical -- a script
computes the verdict from the diff, the plan, and the recipe evidence
alone -- so none stands in for a human checklist instance the way the
context-gathering through planning stages' grader lines do.

| line | row | half | subject | checklist | judgment |
|---|---|---|---|---|---|
| scope_confinement:script | scope_confinement | script | artefact | no | fail when the diff touches a path outside the plan's scope table paths and discretion globs |
| declaration_contracts:script | declaration_contracts | script | artefact | no | fail when a public or protected declaration is added or removed with no `Contracts` row naming it, or changed while its `Contracts` row still calls it unchanged |
| contract_evidence:script | contract_evidence | script | artefact | no | fail when a recorded human verdict carries no evidence id; every other gap in a `Contracts` field's evidence is a named blind spot instead, never a fail on its own |
| regression_only:script | regression_only | script | artefact | no | fail when a lint, compile-type, integration, or end-to-end result is new or worse at head; a diagnostic or test already red at base stays visible as inherited debt, and `factory/lints/` adds no blocking rule of its own |
| diff_size:script | diff_size | script | artefact | no | fail when the diff's added-plus-removed lines, excluding lockfiles and the project's configured generated paths, exceed the tier's threshold and the approved plan's `Size` table carries no justification |
