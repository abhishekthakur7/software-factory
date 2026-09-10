---
name: intake-rubric
kind: rubric
stage: intake
---

The intake stage's rubric: script-only lines over the mechanical intake
gate. Intake never runs an agent -- every line here is a script reading
the ticket's own fields or a `factory/config/` table and then stamping a
ticket column, applying a transition, or opening the one `eligibility`
item a human decides -- so none stands in for a human checklist instance
the way the context-gathering through planning stages' grader lines do.

| line | row | half | subject | checklist | judgment |
|---|---|---|---|---|---|
| intake_fields:script | intake_fields | script | artefact | no | fail when the read ticket has blank acceptance criteria, no named owner, neither a parent link nor a Confluence link, or an epic issue type that needs child tickets instead, and the ticket is not rejected naming the first of those in that order as the reason |
| source_redaction:script | source_redaction | script | artefact | no | fail when a stored ticket source holds fields the guard did not classify and redact first, or when a guard denial or a service whose repositories resolve no data class leaves a stored ticket source behind instead of rejecting the ticket |
| service_tier_lookup:script | service_tier_lookup | script | artefact | no | fail when a service absent from `service-tiers.yaml` is given a guessed tier rather than rejecting the ticket with the service named as untiered |
| ticket_type_mapping:script | ticket_type_mapping | script | artefact | no | fail when the ticket type does not follow the issue-type mapping -- a bug to the bug type, a story to the small-feature type at or under the configured story-point maximum and to the plain feature type above it, a task to the docs-or-config type when it carries the docs label and to the refactor type otherwise -- or when an epic or an unmapped issue type is not rejected |
| provisional_tier_matrix:script | provisional_tier_matrix | script | artefact | no | fail when the stamped provisional tier is not the tier matrix's entry for the looked-up service tier and ticket type, or when a pair the matrix has no entry for is not rejected |
| sensitive_path_tier:script | sensitive_path_tier | script | artefact | no | fail when a path-like token in the ticket title matches a `sensitive-paths.yaml` glob and the ticket's final tier is not raised to heavy, with that glob's configured owner carried on the match, before the exclusion gate runs |
| pilot_exclusion:script | pilot_exclusion | script | artefact | no | fail when a ticket carrying a sensitive-path match, a pilot-matrix violation (the service's tier or language, the ticket type, or a repository or service count outside the admitted matrix), or an excluded surface named in its title or its path-like tokens is not excluded from the pilot |
| scrutiny_paragraph:script | scrutiny_paragraph | script | artefact | no | fail when a ticket that clears both gates carries a scrutiny paragraph other than its ticket type's own template filled with the title, the ticket type, the provisional tier, and either the matched sensitive glob and owner or the absence of one |
| scrutiny_hold:script | scrutiny_hold | script | artefact | no | fail when a ticket whose rendered scrutiny paragraph is empty -- an unmapped ticket type, or one whose template is blank -- has an eligibility item opened for it instead of being held at intake |
