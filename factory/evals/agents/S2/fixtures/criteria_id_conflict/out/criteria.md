## Acceptance criteria

| id | source | precondition | trigger | system | response | example | state |
|---|---|---|---|---|---|---|---|
| AC-1 | An entirely different criterion than the one AC-1 named before. | a different precondition | a different trigger | the affected component | does something different | Given something else, when it happens, then something different results | formalised |

## Forced categories

| category | resolution | reference |
|---|---|---|
| error paths | covered by criterion AC-1 | AC-1 |
| concurrency | not applicable because there is no shared state | n/a |
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
| 10 | 1 | small change |

## Completeness verdict

The one criterion is formalised and every category is resolved.
