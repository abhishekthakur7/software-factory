## Rollout

### Flags

| flag | expected_life | owner | removal_condition | cleanup_task |
|---|---|---|---|---|
| widget-negative-guard | 2 releases | abhishek | error rate stays flat for 2 releases | T-4 |

### Ramp

| step | description |
|---|---|
| 1 | enable for 5 percent of traffic |

### Guardrails

| metric | query | critical_threshold |
|---|---|---|
| error rate | rate(widget_errors_total[5m]) | > 0.01 |

### Kill trigger

| trigger | default_response |
|---|---|
| error rate crosses the critical threshold | rollback the deploy and disable the flag |

### Log verification

| query | pass_pattern | fail_pattern |
|---|---|---|
| widget compute logs | validation rejected | unhandled exception |
