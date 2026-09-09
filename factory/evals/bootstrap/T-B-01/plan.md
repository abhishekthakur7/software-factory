# T-B-01 plan

| # | Step | Files touched | Proving test |
|---|---|---|---|
| 1 | Add the incident policy config and its one reader: severity scale, control-category defaults, attribution/disposition value sets, and the remediation-reference rule. | `factory/config/incident-policy.yaml`, `runner/incident_policy.py` | `runner/tests/test_outcome_incident.py` |
| 2 | Move S4's `execution_boundary` control-defect event, and the `control_event` action, off a literal `sev2` onto the policy. | `runner/stages/S4.py`, `runner/outcome.py`, `runner/queue.py` | `runner/tests/test_outcome_incident.py` |
| 3 | Add the observed-outcome locator read: a public `route_and_deliverer` helper factored out of the outbox's own resolution, and `pull_request_body` on the GitHub transport, its REST client, and the fake. | `runner/outbox.py`, `runner/deliverers/github.py`, `runner/tests/fakes/github_transport.py` | `runner/tests/test_outcome_body.py` |
| 4 | Build `runner/outcome.py`: `revision`, `outcome` (body sourcing, the mismatch comparison and its control-defect rows, the once-group settle, the merged/abandoned branches), `exposure`, `coverage`, `incident_event`, `disposition`, `control_event`, `open_pr_outcome_item`. | `runner/outcome.py` | `runner/tests/test_outcome_revision.py`, `test_outcome_body.py`, `test_outcome_final.py`, `test_outcome_mismatch.py`, `test_outcome_coverage.py` |
| 5 | Wire the queue: `pr_outcome`'s two actions, the ticket-scoped `TICKET_ACTIONS` dispatch with no item, and the `act` CLI's optional `item_id`/`--ticket` and new flags collected into one `fields` mapping. | `runner/queue.py`, `runner/cli.py` | `runner/tests/test_outcome_revision.py`, `test_act.py` |
| 6 | Open the `pr_outcome` item from `advance`'s own `review_quorum_reconciled` transition. | `runner/operations.py` | `runner/tests/test_outcome_revision.py` |
| 7 | Prove no new GitHub polling surface exists, and record the pilot ticket's closing run. | `runner/tests/test_outcome_no_poll.py`, `runner/tests/test_pilot_walk.py` | themselves |
| 8 | Record this brief and plan and copy them to the bootstrap fixture tree. | `docs/build/T-B-01/`, `factory/evals/bootstrap/T-B-01/`, `factory/evals/bootstrap/eval.yaml` | `runner/tests/test_bootstrap_fixtures.py` |

## Test strategy

Each `test_outcome_*` file seeds a ticket directly in the state its action
needs (`pr_opened`, matching `test_act.py`'s convention) rather than
replaying the stages that would reach it, and asserts real rows and
transitions -- never an echoed-back literal. The mismatch tests assert
`outcome` never refuses, only records; the no-poll test is a static `ast`
scan, so a later import cannot silently widen the GitHub surface without
failing it.
