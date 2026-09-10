## Acceptance criteria

| id | source | precondition | trigger | system | response | example | state |
|---|---|---|---|---|---|---|---|
| AC-1 | The refund handler must credit the original payment method. | a refund is approved | the refund is processed | the refund handler | credits the original payment method | Given an approved refund of $20, when it is processed, then the refund handler credits the original payment method | formalised |

## Forced categories

| category | resolution | reference |
|---|---|---|
| error paths | covered by criterion AC-1 | AC-1 |
| concurrency | not applicable because refunds are processed one at a time | n/a |
| migration | not applicable because no schema change is involved | n/a |
| backward compatibility | not applicable because no existing interface changes | n/a |
| permissions | not applicable because no permission boundary is involved | n/a |
| observability | covered by criterion AC-1 | AC-1 |
| rollback | not applicable because the change is additive only | n/a |
| data retention | not applicable because no new data is retained | n/a |

## Agreement check

| id | samples | agreed | note |
|---|---|---|---|
| region-1 | | | uncovered: what happens when the original payment method has expired |

## Size estimate

| estimated_lines | estimated_files | basis |
|---|---|---|
| 25 | 1 | one changed method plus its test |

## Completeness verdict

The one criterion is formalised and every category is resolved, but the
ticket source also describes an expired-payment-method case no criterion
covers.
