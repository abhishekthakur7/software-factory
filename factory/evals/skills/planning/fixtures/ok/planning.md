---
name: spec-and-plan-skill
kind: skill
stage: planning
---

# Plan, step by step

1. Read the approved criteria, the brief, and the attached risk-map
   artefact before writing anything.
2. Write intent and scrutiny first — a reviewer should be able to stop
   after the first page and understand the change.
3. For every candidate the brief classified `unexplained` or
   `contradictory`, add a characterization test to Tasks before any other
   change to that code.
4. Fill Goals/non-goals, then Approach, then Alternatives — one line per
   rejected alternative naming what it was and why it lost.
5. Fill Scope and discretion, Dependencies, Contracts (every touched
   function, module, endpoint, event, or serialized shape), and the
   semantic-contract checklist.
6. Build Tasks in dependency order; give each a recipe id from
   `command-recipes.yaml`, never a shell string; tie every task to the
   `AC-n` ids it serves, or flag it `no_behaviour_change`.
7. Build Test strategy: size against the tier's target mix, `action`
   add/change/remove, and what each row proves. A `change` or `remove` row
   on a base test names the criterion or `no_behaviour_change` task that
   authorizes it — nothing else may touch a base test.
8. Write Rollout for the human to execute after merge: any flag with owner
   and removal condition, ramp steps, guardrail queries with thresholds,
   the kill trigger, log-verification queries.
9. Name the three risk-map places and why, from the attached scan; a
   generic answer fails review.
10. Estimate Size; if over the tier's threshold, justify it in the table
    or propose a split.
11. Write Assumptions (from the accepted defaults), Unknowns, and Required
    approvers.
12. Before finishing, check every `AC-n` is served by a task row and a
    test row — an id served by neither fails structure before a human
    ever reads it.
