## Acceptance criteria

| id | source | precondition | trigger | system | response | example | state |
|---|---|---|---|---|---|---|---|
| AC-1 | The checkout flow must reject an order with an expired coupon. | a coupon is applied | the customer checks out | the checkout flow | rejects the order with an expired-coupon error | Given an expired coupon "SUMMER10", when the customer checks out, then the checkout flow rejects the order | formalised |
| AC-2 | The checkout flow must silently drop an expired coupon and continue. | a coupon is applied | the customer checks out | the checkout flow | drops the expired coupon and completes the order at full price | Given an expired coupon "SUMMER10", when the customer checks out, then the checkout flow completes the order at full price | formalised |

## Forced categories

| category | resolution | reference |
|---|---|---|
| error paths | covered by criterion AC-1 | AC-1 |
| concurrency | not applicable because checkout is per-session | n/a |
| migration | not applicable because no schema change is involved | n/a |
| backward compatibility | not applicable because no existing interface changes | n/a |
| permissions | not applicable because no permission boundary is involved | n/a |
| observability | covered by criterion AC-1 | AC-1 |
| rollback | not applicable because the change is additive only | n/a |
| data retention | not applicable because no new data is retained | n/a |

## Agreement check

| id | samples | agreed | note |
|---|---|---|---|
| AC-1 | | | contradicts AC-2 |
| AC-2 | | | contradicts AC-1 |

## Size estimate

| estimated_lines | estimated_files | basis |
|---|---|---|
| 35 | 1 | one changed method plus its test |

## Completeness verdict

Both criteria are formalised and every category is resolved, but AC-1 and
AC-2 require opposite behaviour for the same case.
