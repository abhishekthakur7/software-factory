# T-AB-06 plan

| # | Step | Files touched | Proving test |
|---|---|---|---|
| 1 | Define the small GitHub transport protocol, live REST client, safe push request, remote-state reconciliation, and failure types. | `runner/deliverers/github.py` | `runner/tests/test_deliverer_github.py` |
| 2 | Select the GitHub deliverer only for the scratch route and preserve the stub for other routes. | `runner/deliverers/__init__.py`, `runner/outbox.py` | `runner/tests/test_deliverer_github.py`, `runner/tests/test_outbox_crash_github.py` |
| 3 | Add the fake GitHub transport and scenario fixtures for create, update, unexpected heads, closed pull requests, and denied permission. | `runner/tests/fakes/github_transport.py`, `runner/tests/fixtures/deliverer_github/` | `runner/tests/test_deliverer_github.py` |
| 4 | Cover crash recovery and ambiguous/idempotency paths through the live-deliverer selection. | `runner/tests/fixtures/outbox_crash_github/`, `runner/tests/test_outbox_crash_github.py` | `runner/tests/test_outbox_crash_github.py` |
| 5 | Record this brief and plan and copy them to the bootstrap fixture tree. | `docs/build/T-AB-06/`, `factory/evals/bootstrap/T-AB-06/`, `factory/evals/bootstrap/eval.yaml` | `runner/tests/test_bootstrap_fixtures.py` |

## Test strategy

The adapter tests assert calls and remote state rather than its internal
mapping.  They prove no push precedes the worker's approval gate, update
keeps the existing pull request, a changed remote head blocks both mutations,
and a closed pull request becomes an outcome item.  The outbox crash tests
exercise its existing pending, sending, receipt reconciliation, and duplicate
key protections with the GitHub fake selected as the dispatch target.  The configured project remains fixture-only; live closing validation requires
an owner-supplied scratch repository and publication credential.

## Live configuration

The committed scratch route is explicitly `stub`. To enable live delivery,
set `scratch_repository.name` to `owner/repo`, its remote to the matching
`https://github.com/owner/repo.git`, and the trusted route's deliverer to `live`.
A missing or mismatched live target is refused before credentials are fetched.
The helper runs from any checkout and Git cannot inherit ambient credential
helpers or hooks. The API request shape follows the
[GitHub pull-request reference](https://docs.github.com/en/rest/pulls/pulls).
