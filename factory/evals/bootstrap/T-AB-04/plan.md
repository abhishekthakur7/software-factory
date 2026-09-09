# T-AB-04 plan

| # | Step | Files touched | Proving test |
|---|---|---|---|
| 1 | `intake_fields.check`: a pure gate over a payload and a field-name mapping, `Finding(check_name, result, detail)`. | `runner/checks/intake_fields.py` | `runner/tests/test_intake_fields.py` |
| 2 | Four reject fixtures and one ok fixture, raw-Jira-keyed payload dicts. | `runner/tests/fixtures/intake_fields/*.yaml` | `runner/tests/test_intake_fields.py` |
| 3 | `AtlassianReader`, `HttpTransport` (credential fetched inside `__call__`, never stored), `endpoint()` reading `sandbox.yaml`'s one policy. | `runner/readers/atlassian.py` | `runner/tests/test_s0.py` |
| 4 | `FakeAtlassianTransport`: records every call, `KeyError` on an unknown key. | `runner/tests/fakes/atlassian_transport.py` | `runner/tests/test_s0.py` |
| 5 | `ticket-types.yaml` gains `jira_fields`. | `factory/config/ticket-types.yaml` | `runner/tests/test_intake_fields.py`, `test_pilot_config.py` |
| 6 | `ticket.data_class` becomes a `once=` column instead of append-only. | `runner/schema.py`, `runner/db.py` (`USER_VERSION`), `runner/tests/test_mutable_exceptions.py` | `test_mutable_exceptions.py` |
| 7 | `runner/trust_profile.py`: `ROUTE_IDS` becomes the full ten-route list, `LIVE_ROUTES` replaces `LIVE_ROUTE`, `GITHUB_ROUTE_IDS` generalises the operations check, `repository_data_classes` + `repository_class()`. | `runner/trust_profile.py` | `runner/tests/test_trust_profile.py` |
| 8 | `trust-profile.yaml`: scratch repository admitted, `repository_data_classes`, `github_pilot`/`github_scratch` replacing `github_pr`, `atlassian_read`/`baseline_read`/`registry`/`vulnerability_feed` added, `credential_role` on every route that needs one. | `factory/config/trust-profile.yaml` | `runner/tests/test_pilot_config.py`, `test_trust_profile.py` |
| 9 | Every trust-profile fixture shared with other tickets' tests gets the same route-set update so it keeps loading. | `runner/tests/fixtures/{trust_profile,outbox,export_import,guard}/*.yaml` (byte-identical to each other) | `test_trust_profile.py`, `test_outbox.py`, `test_guard.py`, `test_freshness.py`, `test_s6_dispatch.py` |
| 10 | `runner/project.py`: `load()`/`pilot()`, the one loader of `project.yaml`. | `runner/project.py` | `runner/tests/test_pilot_config.py` |
| 11 | `project.yaml` becomes a `projects` list plus `scratch_repository`; `generated_paths`/`lockfiles` stay top-level. | `factory/config/project.yaml` | `runner/tests/test_pilot_config.py`, `test_fixture_project.py` |
| 12 | Every current reader of `project.yaml` switched to `runner.project`. | `runner/freshness.py`, `plan_tuple.py`, `setup.py`, `publication.py`, `outbox.py` (loader only), `stages/{S1,S3,S4,S5,S6}.py` | each module's own existing test file |
| 13 | S0's Jira intake leg: read-or-reuse, the field gate, guard classify-and-redact, `ticket_source` write. | `runner/stages/S0.py` | `runner/tests/test_s0.py`, `test_intake_fields.py` |
| 14 | `runner/outbox.py`'s PR route id becomes a named constant, pinned to `github_scratch`. | `runner/outbox.py` | `runner/tests/test_outbox.py` |
| 15 | Every reader that hardcoded `github_pr` renamed to `github_scratch`. | `runner/tests/{test_outbox,test_s6_dispatch,test_freshness,test_guard,test_trust_profile}.py` | same files |
| 16 | `test_intake_fields.py`, `test_pilot_config.py`: new test files for this ticket. | `runner/tests/test_intake_fields.py`, `runner/tests/test_pilot_config.py` | themselves |
| 17 | `test_s0.py` extended: the seeded-artefact path for every `_governed_ticket_fields` test that now runs the Jira intake leg, plus new tests for the fresh-read redaction, the secret-deny path, the credential/transport contract, the manifest's S0 credential-role check, and the loudly-skipped dry-run test. | `runner/tests/test_s0.py` | itself |
| 18 | `factory/manifest.yaml`'s `files:` list refreshed for every changed file under `factory/`. | `factory/manifest.yaml` | `runner/tests/test_manifest_hash.py` |
| 19 | This ticket's own brief and plan. | `docs/build/T-AB-04/brief.md`, `docs/build/T-AB-04/plan.md` | reviewed by the human, not a test |

## Test strategy

`test_intake_fields.py` drives `intake_fields.check` directly over the
five raw-payload fixtures (four reject, one ok), plus a scrambled-mapping
test proving the function truly reads `field_names` rather than fixed
keys, and one S0-driver test proving the wiring: a jira-sourced ticket
whose already-registered `ticket_source` carries no owner is rejected
with exactly one `intake_fields` `check_result` row.

`test_s0.py` covers the Jira intake leg end to end against
`FakeAtlassianTransport`: a fresh read whose payload carries a field
outside the `atlassian_read` route's admitted set proves the redaction is
faithful (the extra field never survives) and sets `ticket.data_class`;
a payload carrying a `ghp_`-shaped secret proves the guard's deny path
rejects the ticket before any artefact is written. `HttpTransport` gets
its own test with a fake `fetch` and a mocked `urlopen`, asserting the
credential is requested inside the call and never held as an attribute
afterward. The manifest's own `sandbox_policy.credential_roles["S0"] == ()`
gets a one-line assertion. The dry-run ticket's real-server behaviour
(reading through `HttpTransport`, the credential never leaking into a row
or artefact, the pinned governance hashes) is one test gated on three
`skipif`-style checks -- `credentials.available`, `atlassian.endpoint()`,
and an environment variable naming a real dry-run Jira key -- so it
always skips today and runs for real the moment any one of those exists.

`test_pilot_config.py` asserts structure and resolution over the
committed files, not literals: the `repository_data_classes` join
resolves to `confidential`; every route's `credential_role` is inside
`credentials.ROLES`; every route in `GITHUB_ROUTE_IDS` carries the
`pr_create`/`pr_update` operations pair; every service in
`service-tiers.yaml` names repositories inside `trust-profile.yaml`'s
admitted scopes; `runner.project.pilot()["checkout"]` resolves outside
`factory/`; the scratch repository's name is itself an admitted
repository scope; every `factory/index/` entry still carries
`last_verified` and the pilot's known caller is still indexed; the
committed trust profile is governance-approved and pinned before a
freshly opened ticket reaches eligibility, the same activation path
`test_s0.py`'s `_governed_ticket_fields` already exercises.

Every reader-migration site (`freshness.py`, `plan_tuple.py`, `setup.py`,
`publication.py`, the stage drivers) is proven by its own pre-existing
test file continuing to pass unchanged in behaviour -- the loader
changed, not what each caller reads off the result.
