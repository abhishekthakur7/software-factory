---
name: checklist-fixture-rubric
kind: rubric
stage: S3
---

A small, self-contained S3-stage rubric carrying one `contract_unit`
checklist line, so the eval fixture's expected instance set exercises all
four subject kinds (`artefact`, `criterion`, `question`, `contract_unit`)
once combined with the real, committed `S1.md` and `S2.md`.

| line | row | half | subject | checklist | judgment |
|---|---|---|---|---|---|
| R-CK-1:grader | R-CK-1 | grader | contract_unit | yes | fail when a contracts-table unit's fields contradict the plan's own approach |
