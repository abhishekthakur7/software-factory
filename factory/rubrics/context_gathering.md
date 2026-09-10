---
name: context-gathering-rubric
kind: rubric
stage: context_gathering
---

The context-gathering stage's rubric: one line per row and half. A
script half's judgment is the sentence the runner's own check enforces
mechanically; a grader half marked `checklist: yes` stands in for a
calibrated grader until one exists, so a human applies its judgment
sentence directly against the checked brief.

| line | row | half | subject | checklist | judgment |
|---|---|---|---|---|---|
| ticket_summary:script | ticket_summary | script | artefact | no | fail when the ticket summary exceeds the section 8 word limit |
| ticket_summary:grader | ticket_summary | grader | artefact | yes | fail when a ticket summary states a recommendation or an approach instead of facts alone |
| impact_evidence:script | impact_evidence | script | artefact | no | fail when an impact evidence row carries an invalid direction or coverage, omits a required field, contradicts impact_scan's own resolution, or an inbound row asserts non-unknown coverage with no fresh caller index entry backing it |
| impact_evidence:grader | impact_evidence | grader | artefact | yes | fail when the plan names an owner other than the one the brief's impact evidence names |
| history_classification:grader | history_classification | grader | artefact | yes | fail when a touched-area candidate that is not self-evident has no history classification, or is classified explained without a resolved issue behind it |
| reference_grounding:script | reference_grounding | script | artefact | no | fail when a Flags row's reference is not a code path or path:line that exists in the worktree, or when live production state -- an SLI, error budget, dashboard, or log claim -- appears outside the Blind spots section |
| reference_grounding:grader | reference_grounding | grader | artefact | yes | fail when a brief asserts a live production fact, such as an SLI or an error-budget value, outside the blind spots section |
| context_index_use:script | context_index_use | script | artefact | no | fail when a context index entry the context-gathering stage read is not recorded in index_use with its last-verified date, or a stale entry is not also listed as stale in the brief |
| final_tier:script | final_tier | script | artefact | no | fail when the computed final tier is lower than the provisional tier, or does not match the files-touched, services-touched, and unknowns threshold rule |
| impact_tiering:script | impact_tiering | script | artefact | no | fail when impact-derived tiering picks a tier lower than the highest known criticality among the target and impacted services, or omits the unknown-impact flag for a service absent from service-tiers.yaml |
| impact_tiering:grader | impact_tiering | grader | artefact | yes | fail when the plan's contracts table does not restate the brief's impact evidence and blind spots by name |
