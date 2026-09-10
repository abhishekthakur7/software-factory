---
name: requirements-clarification-rubric
kind: rubric
stage: clarification
---

The question and assumption half of this stage's rubric, plus the
criteria half: restatement and id stability, the Given/When/Then example,
the agreement check, the forced-category checklist, and the split rule.

| line | row | half | subject | checklist | judgment |
|---|---|---|---|---|---|
| criterion_restatement:script | criterion_restatement | script | criterion | no | fail when a restated criterion omits the system or response field, reuses or skips an `AC-n` id across versions, or is not marked `unformalisable` with a question raised when it cannot be restated |
| criterion_restatement:grader | criterion_restatement | grader | criterion | yes | fail when a restated `AC-n` criterion changes the meaning of its source acceptance criterion |
| given_when_then_example:script | given_when_then_example | script | criterion | no | fail when a criterion carries no Given/When/Then example, or the example omits given/when/then wording or carries a placeholder token in place of a real value |
| given_when_then_example:grader | given_when_then_example | grader | criterion | yes | fail when a Given/When/Then example states no real values, only generic placeholders |
| agreement_check:script | agreement_check | script | criterion | no | fail when a criterion's agreement check does not spawn exactly `N` child `stage_run` rows on the manifest's restatement model, or when a disagreement, contradiction, or uncovered region found there raises no question |
| forced_categories:script | forced_categories | script | artefact | no | fail when a forced category is left silent, resolves to anything other than `covered by criterion AC-n`, `not applicable because <reason>`, or `open`, or when a category the ticket's own exclusion record already closed is re-evaluated instead of pre-filled |
| vertical_slice_size:script | vertical_slice_size | script | artefact | no | fail when the size estimate exceeds the tier's split threshold with no consequential split question naming one of the split patterns |
| vertical_slice_size:grader | vertical_slice_size | grader | artefact | yes | fail when criteria describe no single vertical slice with observable value |
| pass_completeness:script | pass_completeness | script | artefact | no | fail when a run exits `pass` while a criterion is neither formalised nor its `unformalisable` question answered, a category is unresolved, or a blocking question is still open, or when a `blocked` run leaves undone any criterion, category, or question that did not depend on the open question |
| question_reasoning:script | question_reasoning | script | question | no | fail when a candidate's `reasoning` or `affects` is empty |
| question_reasoning:grader | question_reasoning | grader | question | yes | fail when a question's reasoning names a source that never mentions the fact the question asks about |
| question_ranking:script | question_ranking | script | question | no | fail when a question is queued with no `rank` or no `rank_inputs` recorded, whether or not it carries a default |
| default_option:script | default_option | script | question | no | fail when a candidate's `default_option` is missing where required, present where both flags or a sensitive decision require it null, or when its options number outside two to four or omit a trailing "none of these" |
| question_flags:script | question_flags | script | question | no | fail when a candidate's `affects` names a consequential or hard-to-reverse surface without the matching flag set, or when a sensitive decision is queued without `consequential` set |
| follow_up_rounds:script | follow_up_rounds | script | question | no | fail when a follow-up candidate's `raised_by_answer` names no real answer of this ticket, or when a new round is queued while the previous round's blocking question is still open |
| default_accepted_assumption:script | default_accepted_assumption | script | artefact | no | fail when a `default_accepted` answer is recorded with no `assumption` row naming its question, or when a superseding or withdrawing assumption row is written with no new assumption-log hash following from it |
| self_contained_question:script | self_contained_question | script | question | no | fail when a question or option text names a requirement, principle, failure-mode, decision, or stage id, or an artefact-kind, script, or table name outside the service's own code |
| self_contained_question:grader | self_contained_question | grader | question | yes | fail when a reader with no access to the referenced artefact cannot give the right answer to the question |
