---
name: requirements-clarification-skill
kind: skill
stage: clarification
---

# Clarify requirements, step by step

1. Read the brief and the ticket's acceptance criteria from its source.
2. Restate each criterion in EARS form; assign the next unused `AC-n` id in
   restatement order. Keep the same id across later versions of the same
   criterion; never reuse an id for a different one.
3. Write one concrete Given/When/Then example per criterion, with real
   values drawn from the fixture project or the ticket itself, never a
   placeholder.
4. Resolve every forced category in turn, using
   `rubrics/checklists/forced-categories.md`; check whether an
   intake-stage exclusion already pre-filled it before evaluating it
   yourself.
5. Before raising any question, try the brief, the linked sources, the
   checkout, and the context index; list exactly what you tried and what
   each one told you.
6. For each question that survives the gate, write it into
   `out/questions.yaml` in the shape the agent file states, worded for a
   reader who has opened nothing.
7. Estimate size (lines, files) with your basis; compare it against the
   tier's split threshold and propose a split if it applies, using
   `rubrics/checklists/split-patterns.md`.
8. Write the completeness verdict: every criterion formalised or its
   question raised, every category resolved, no silent gaps.
9. If a blocking question is open, finish every criterion, category, and
   question that does not depend on its answer, then stop — the run ends
   `blocked` and the human answers through the queue.
