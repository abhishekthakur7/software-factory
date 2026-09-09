# T-AB-07 plan

| # | Step | Files touched | Proving test |
|---|---|---|---|
| 1 | Add configuration loading for the digest channel and cadence and write a launchd plist from it. | `factory/config/project.yaml`, `runner/project.py`, `runner/setup.py` | `runner/tests/test_digest.py` |
| 2 | Build the redacted queue projection, age grouping, cadence-slot key, transactional intent creation, and utility-run record. | `runner/digest.py`, `runner/cli.py` | `runner/tests/test_digest.py` |
| 3 | Add the narrow Slack post transport and select it for the Slack route. | `runner/deliverers/slack.py`, `runner/deliverers/__init__.py` | `runner/tests/test_digest.py` |
| 4 | Add fake transport and fixtures for populated, empty, redacted, secret, scheduler, and duplicate runs. | `runner/tests/fakes/slack_transport.py`, `runner/tests/fixtures/digest/` | `runner/tests/test_digest.py` |
| 5 | Add the digest script eval and this ticket's bootstrap copies and mapping. | `factory/evals/scripts/tools/digest/`, `factory/evals/bootstrap/T-AB-07/`, `factory/evals/bootstrap/eval.yaml` | `runner/tests/test_bootstrap_fixtures.py`, `runner/tests/test_manifest_eval_walk.py` |

## Test strategy

Tests seed real queue rows and inspect the persisted utility run and outbox
intent.  They prove empty work sends nothing, the idempotency key changes only
with its declared inputs, repeated invocation in the same slot is harmless,
the guard strips forbidden fields and denies secrets, and the fake transport
sees only the allowed projection.  Scheduler rendering is checked as a plist
artifact, without touching the user's launchd installation.  The real Slack
post remains a loud closing-run prerequisite.

The committed Slack route remains explicitly `stub` pending a channel and an
approved post-tool binding. Live delivery uses the
[official Slack MCP endpoint](https://docs.slack.dev/ai/slack-mcp-server/developing/).
Its channel and text argument names come from approved tool discovery; an
incomplete live configuration cannot produce a fixture receipt.
