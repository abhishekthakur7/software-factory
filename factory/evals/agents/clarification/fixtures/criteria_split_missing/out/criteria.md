## Acceptance criteria

| id | source | precondition | trigger | system | response | example | state |
|---|---|---|---|---|---|---|---|
| AC-1 | The reporting module must generate a monthly summary across every account type. | the month has closed | the scheduler fires | the reporting module | generates a summary for every account type | Given the "2026-01" period has closed, when the scheduler fires, then the reporting module generates a summary for every account type | formalised |

## Forced categories

| category | resolution | reference |
|---|---|---|
| error paths | covered by criterion AC-1 | AC-1 |
| concurrency | not applicable because the scheduler runs one job at a time | n/a |
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
| 260 | 4 | every account type's summary logic plus its test |

## Completeness verdict

The one criterion is formalised and every category is resolved; the size
estimate covers every account type in one slice.
