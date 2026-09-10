## Ticket summary

The export handler currently omits a CSV header row. The fix adds one to the existing export path.

## Linked sources

| source | date |
|---|---|
| FIX-1 | 2026-08-01 |

## Touched area candidates

| path | reason |
|---|---|
| src/main/java/com/example/Handler.java | handles the ticket's own endpoint |

## History

| path | classification | evidence |
|---|---|---|
| src/main/java/com/example/Handler.java | explained | commit a1b2c3d fixed the same handler for a related bug |

## Impact evidence

| direction | dependency | method | source | mapping | owner | coverage | blind_spots |
|---|---|---|---|---|---|---|---|
| inbound | reporting-service | caller_catalogue | caller-catalogue.md (stale) | context_index:caller | reporting-team | unknown | the caller index entry for this path is stale, so the current caller set is not asserted |

## Flags

| flag | reference |
|---|---|
| export_header_row | src/main/java/com/example/Handler.java:12 |

## Blind spots

| item | assumption |
|---|---|
| reporting-service's current call pattern | the plan assumes no caller depends on the CSV's current headerless shape |

## Unknowns

| unknown | tried |
|---|---|
| whether any caller parses the CSV positionally | checked the stale caller catalogue entry; found no confirmation either way |

## Index entries used

| entry | last_verified | stale |
|---|---|---|

## Final tier

| files_touched | services_touched | unknowns | tier_provisional | tier_final |
|---|---|---|---|---|

## Pilot-exclusion recheck

No new surface outside the ticket's own target service was found.

## Blockers

None.
