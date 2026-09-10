## Acceptance criteria

| id | source | precondition | trigger | system | response | example | state |
|---|---|---|---|---|---|---|---|
| AC-1 | The archive job must move records older than one year to cold storage. | a record is older than one year | the archive job runs | the archive job | moves the record to cold storage | Given a record last touched over a year ago, when the archive job runs, then it moves the record to cold storage | formalised |

## Forced categories

| category | resolution | reference |
|---|---|---|
| error paths | covered by criterion AC-1 | AC-1 |
| concurrency | not applicable because the archive job runs alone on a schedule | n/a |
| migration | not applicable because no schema change is involved | n/a |
| backward compatibility | not applicable because no existing interface changes | n/a |
| permissions | not applicable because no permission boundary is involved | n/a |
| observability | covered by criterion AC-1 | AC-1 |
| rollback | open | |
| data retention | covered by criterion AC-1 | AC-1 |

## Agreement check

| id | samples | agreed | note |
|---|---|---|---|

## Size estimate

| estimated_lines | estimated_files | basis |
|---|---|---|
| 40 | 2 | one new job plus its test |

## Completeness verdict

The one criterion is formalised, but the rollback category is left open:
moving a record to cold storage may not be cheaply reversible.
