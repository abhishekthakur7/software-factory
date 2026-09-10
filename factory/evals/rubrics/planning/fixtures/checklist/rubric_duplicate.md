---
name: checklist-fixture-duplicate-rubric
kind: rubric
stage: planning
---

A deliberately malformed companion rubric for the `checklist_duplicate`
case: it reuses `clarification.md`'s own `criterion_restatement` row id for a `criterion` checklist
line, so combining it with the real `clarification.md` assembles the identical
`(rubric_line_id, subject_item_key)` pair for every `AC-n` -- the case
`expected_instances` must reject.

| line | row | half | subject | checklist | judgment |
|---|---|---|---|---|---|
| criterion_restatement:grader | criterion_restatement | grader | criterion | yes | fail when a restated `AC-n` criterion changes the meaning of its source acceptance criterion |
