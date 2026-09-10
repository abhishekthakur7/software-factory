## Acceptance criteria

| id | source | precondition | trigger | system | response | example | state |
|---|---|---|---|---|---|---|---|
| AC-1 | The export handler must add a header row naming each column. | the export handler runs | a caller requests the order-list export | the export handler | writes a header row naming each column before the data rows | Given the order list export for "2026-Q1", when a caller requests it, then the response's first line reads "order_id,customer_id,total" | formalised |

## Forced categories

| category | resolution | reference |
|---|---|---|
| error paths | not applicable because the header row cannot itself fail to write | n/a |
| concurrency | not applicable because the export is read-only and stateless | n/a |
| migration | not applicable because no stored data changes shape | n/a |
| backward compatibility | not applicable because the added row only prepends, existing columns are unchanged | n/a |
| permissions | not applicable because export access is unchanged by this criterion | n/a |
| observability | covered by criterion AC-1 | AC-1 |
| rollback | not applicable because the change is additive only | n/a |
| data retention | not applicable because no new data is stored | n/a |

## Agreement check

| id | samples | agreed | note |
|---|---|---|---|
| AC-1 | 3 | yes | |

## Size estimate

| estimated_lines | estimated_files | basis |
|---|---|---|
| 15 | 1 | one changed method plus its test |

## Completeness verdict

The one criterion is formalised, every category is resolved, and the
agreement check found no disagreement.
