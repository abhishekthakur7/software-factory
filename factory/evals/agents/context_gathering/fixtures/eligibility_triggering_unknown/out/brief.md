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
| outbound | billing-service | http_call | unknown | openapi:billing-service | unassigned | unknown | this call was found by accident while reading the handler; it changes eligibility since it reaches a second service the pilot never scoped |

## Flags

| flag | reference |
|---|---|
| export_header_row | src/main/java/com/example/Handler.java:12 |

## Blind spots

| item | assumption |
|---|---|
| billing-service's involvement in this path | none; this discovery is handed to the exclusion gate rather than assumed away |

## Unknowns

| unknown | tried |
|---|---|
| why the export handler calls billing-service at all | read the handler; found the call but no documentation of it |

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
