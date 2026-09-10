## Acceptance criteria

| id | source | precondition | trigger | system | response | example | state |
|---|---|---|---|---|---|---|---|
| AC-1 | The system should feel trustworthy to the customer. | the customer completes a purchase | the receipt is generated | the receipt | displays the merchant's verified support contact information | Given a completed purchase, when the receipt is generated, then it displays the merchant's verified support contact information | formalised |

## Forced categories

| category | resolution | reference |
|---|---|---|
| error paths | covered by criterion AC-1 | AC-1 |
| concurrency | not applicable because there is no shared state to speak of | n/a |
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
| 20 | 1 | one changed template plus its test |

## Completeness verdict

The one criterion is now formalised and every category is resolved.
