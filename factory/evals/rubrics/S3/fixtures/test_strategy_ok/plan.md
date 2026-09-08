## Test strategy

| test | action | size | criteria | proves |
|---|---|---|---|---|
| WidgetTest | add | small | AC-1 | compute rejects negative input |
| WidgetTest | change | small | AC-1 | the base assertion now also covers negative input |
| WidgetE2E | add | large | AC-1 | the end-to-end flow rejects negative input at the API boundary |
