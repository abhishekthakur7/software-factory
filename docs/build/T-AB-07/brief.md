# T-AB-07 brief: scheduled, redacted Slack digest through the outbox

## What this delivers

`factory digest` reads open attention rows, reduces them to the five
trust-profile fields, groups them by ticket and age, and submits one
transactional `digest` intent for the current configured cadence slot.  It
records the command as a `utility_run`; an empty queue records the run but
does not create an intent.  Intent idempotency binds channel, slot, and the
canonical item list, so repeated invocations cannot post twice.

`runner/deliverers/slack.py` is the only Slack-writing path.  It receives an
injectable post-tool client, obtains `slack_digest` only for a real post, and
turns its response into the existing outbox receipt.  `runner.setup` renders
a launchd plist from the configured cadence and channel without installing
or starting it as a side effect.

Row covered: R-H-3.

## Owner decisions this ticket follows

- `project.yaml` keeps the digest channel unset until an owner supplies it.
  A digest with pending items fails closed instead of selecting a channel.
- Cadence slots are UTC ISO week/day/hour values matching the configured
  cadence.  They are deterministic inputs to intent idempotency and avoid
  a scheduler-specific timestamp interpretation.
- The digest tool is a Python module behind the CLI rather than a standalone
  process.  This keeps database transactions and outbox intent creation in
  the same process and makes the utility run atomic with the generated work.

## Explicitly out

The Slack route and credential-role declaration; any real post before a
channel and credential are supplied; and the source workflows that create
attention rows.
