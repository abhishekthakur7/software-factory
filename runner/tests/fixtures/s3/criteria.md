## Acceptance criteria

| id | source | precondition | trigger | system | response | example | state |
|---|---|---|---|---|---|---|---|
| AC-1 | ticket | widget module loaded | caller invokes compute | widget service | returns the computed value | compute(2) -> 4 | formalised |
| AC-2 | ticket | widget module loaded | caller passes an invalid input | widget service | rejects with a typed error | compute(-1) -> error | formalised |

## Forced categories

| category | resolution | reference |
|---|---|---|
| error paths | AC-2 covers the invalid-input path | AC-2 |
| concurrency | single-threaded, no shared state | n/a |
| migration | no schema touched | n/a |
| backward compatibility | additive only | n/a |
| permissions | no authorization change | n/a |
| observability | existing logging covers this path | n/a |
| rollback | plain revert, no data migration | n/a |
| data retention | no data written | n/a |

## Agreement check

| id | samples | agreed | note |
|---|---|---|---|
| AC-1 | 3 | yes | restatements matched |
| AC-2 | 3 | yes | restatements matched |

## Size estimate

| estimated_lines | estimated_files | basis |
|---|---|---|
| 80 | 1 | task table sum |

## Completeness verdict

Every forced category is addressed; both criteria are formalised.
