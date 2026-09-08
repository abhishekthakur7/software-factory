---
kind: convention
source: fixture
owner: tester
last_verified: "2026-09-01"
staleness_rule: default
paths:
  - watched.txt
---

A day-fresh entry whose one watched path a later base-branch commit
touches, so it is stale under the commit clause even though the day rule
alone would call it fresh.
