## Acceptance criteria

| id | source | precondition | trigger | system | response | example | state |
|---|---|---|---|---|---|---|---|
| AC-1 | The order service must confirm a submitted order within 5 seconds. | the order is valid | the customer submits an order | the order service | sends a confirmation within 5 seconds | Given a valid order for "SKU-42", when the customer submits it, then the order service sends a confirmation within 5 seconds | formalised |

## Forced categories

| category | resolution | reference |
|---|---|---|
| error paths | covered by criterion AC-1 | AC-1 |
| concurrency | not applicable because each order is handled by a single writer | n/a |
| migration | not applicable because no schema change is involved | n/a |
| backward compatibility | not applicable because no existing interface changes | n/a |
| permissions | not applicable because no permission boundary is involved | n/a |
| observability | covered by criterion AC-1 | AC-1 |
| rollback | not applicable because the change is additive only | n/a |
| data retention | not applicable because no new data is retained | n/a |

## Agreement check

| id | samples | agreed | note |
|---|---|---|---|

## Size estimate

| estimated_lines | estimated_files | basis |
|---|---|---|
| 40 | 2 | one new endpoint plus its test |

## Completeness verdict

The one criterion is formalised, every category is resolved, and the
agreement check has not yet run.
