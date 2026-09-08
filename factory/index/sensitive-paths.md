---
kind: sensitive_paths
source: factory/config/sensitive-paths.yaml
owner: abhishek
last_verified: 2026-09-08
staleness_rule: default
paths:
  - src/main/java/com/fixture/auth/**
  - src/main/java/com/fixture/payments/**
  - src/main/resources/secrets/**
---

## Sensitive paths

`src/main/java/com/fixture/auth/**`, `src/main/java/com/fixture/payments/**`,
and `src/main/resources/secrets/**` need the named owner's review; a change
under any of them raises scrutiny regardless of the ticket's other tier
signals.

## Owners

`factory/evals/fixture-project/CODEOWNERS` names `abhishek` for the whole
tree and again explicitly for `src/main/java/com/fixture/auth/`.
`factory/config/sensitive-paths.yaml` adds `payments` and `secrets`, both
owned by `abhishek`, for paths CODEOWNERS does not cover.
