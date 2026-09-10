## Rollout

### Flags

| flag | expected_life | owner | removal_condition | cleanup_task |
|---|---|---|---|---|

### Ramp

| step | description |
|---|---|

### Guardrails

| metric | query | critical_threshold |
|---|---|---|
| error rate | rate(widget_errors_total[5m]) |  |

### Kill trigger

| trigger | default_response |
|---|---|
| error rate crosses the critical threshold | page the on-call engineer |

### Log verification

| query | pass_pattern | fail_pattern |
|---|---|---|
