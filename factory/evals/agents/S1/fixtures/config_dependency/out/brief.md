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
| outbound | export.header_row.enabled | config_reference | feature-flags.yaml@a1b2c3d (2026-08-01) | config:feature-flags | platform-team | authoritative | the flag's current rollout percentage is not read; only its existence is confirmed |

## Flags

| flag | reference |
|---|---|
| export_header_row | src/main/java/com/example/Handler.java:12 |

## Blind spots

| item | assumption |
|---|---|
| the flag's live rollout percentage | the plan assumes the flag is off by default until raised |

## Unknowns

| unknown | tried |
|---|---|

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
