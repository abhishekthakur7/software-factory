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
| src/main/java/com/example/Handler.java | explained | FIX-1: issue(s) FIX-1 resolved and consistent with the change |

## Impact evidence

| direction | dependency | method | source | mapping | owner | coverage | blind_spots |
|---|---|---|---|---|---|---|---|

## Flags

| flag | reference |
|---|---|

## Blind spots

| item | assumption |
|---|---|

## Unknowns

| unknown | tried |
|---|---|

## Index entries used

no entries

## Final tier

| files_touched | services_touched | unknowns | tier_provisional | tier_final |
|---|---|---|---|---|
| 1 | 0 | 0 | standard | standard |

## Pilot-exclusion recheck

No new surface outside the ticket's own target service was found.

## Blockers

None.
