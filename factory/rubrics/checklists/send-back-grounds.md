# Send-back grounds

A `send_back` tag's note names one of these grounds by id, in the form
`<ground>: <text>`. `other` requires text after the colon;
`wrong_brief_or_criteria` requires the target stage in that text. A note
that opens with none of these ids is refused.

## Grounds

| ground | description |
|---|---|
| duplicates_existing_work | The work duplicates something already done or already in flight. |
| technically_unsound | The approach itself does not hold up. |
| missing_compatibility_analysis | No backward-compatibility or migration analysis was done for a change that needs one. |
| contradicts_non_goal | The work contradicts a non-goal the brief or plan already states. |
| wrong_brief_or_criteria | The brief or acceptance criteria are wrong; the text names the stage the ticket sends back to. |
| other | A ground not covered above; the text explains it. |
