# T-AB-04 brief: the intake field gate, the Atlassian reader, the pilot trust profile and configuration content

## What this delivers

S0's mechanical gate now crosses the trust boundary a Jira-sourced ticket
requires. `runner/checks/intake_fields.py` is a pure gate over a payload
and a field-name mapping: it rejects a source ticket with empty
acceptance criteria, no named owner, neither a parent nor a Confluence
link, or an `Epic` issue type, naming the first reason found. The mapping
comes from `ticket-types.yaml`'s new `jira_fields` block for a fresh Jira
read, and from a fixed identity mapping for a ticket that already carries
a `ticket_source` artefact -- the front matter now carries every field
the gate needs, so the same check runs whichever path produced the
artefact.

`runner/readers/atlassian.py` reads a Jira issue through an injectable
transport: `AtlassianReader` never touches a network itself, `HttpTransport`
fetches the `atlassian_read` credential from `runner/credentials.py`
inside the one call that needs it and never stores it, and `endpoint()`
resolves the real server's address from `sandbox.yaml`'s one policy when
it names one. `runner/tests/fakes/atlassian_transport.py` drives the
routine suite; only a dry-run ticket against a real pilot Jira key would
ever reach `HttpTransport`, and since no real pilot repository, Jira key,
Atlassian server, or Keychain item exists yet, every test that would
exercise that path skips loudly naming the missing piece.

`runner/stages/S0.py` runs the Jira intake leg before its existing
lookup/exclusion/scrutiny flow, for any ticket whose `source_kind` is
`jira`: read-or-reuse, the field gate, then (only on a fresh read) the
guard's classify-and-redact into the `ticket_source` artefact, setting
`ticket.data_class`. A field-gate failure or a guard denial rejects the
ticket (`s0_reject`) the same way a lookup failure always did. Every
other `source_kind` keeps the original stand-in `run_stub` write.

The pilot trust profile gains the routes later tickets use --
`atlassian_read`, `github_pilot`, `github_scratch` (replacing `github_pr`),
`baseline_read`, `registry`, `vulnerability_feed` -- each carrying real
governance content and a `credential_role` where one applies, plus the
scratch repository as an admitted scope and the pilot repository's data
class (`repository_data_classes`, joined through a new
`trust_profile.repository_class`). `factory/config/project.yaml` becomes a
`projects` list (the pilot is still the only entry) plus a
`scratch_repository` key; `runner/project.py` is the one loader, and every
current reader of `project.yaml` across the stage drivers, `setup.py`,
`freshness.py`, `plan_tuple.py`, `publication.py` and their tests now
calls it instead of parsing the file directly.

## Design decisions the brief left open

- The field gate's mapping for the "already has an artefact" path is a
  fixed identity mapping (`_FRONT_MATTER_FIELD_NAMES` in `S0.py`) rather
  than `ticket-types.yaml`'s `jira_fields`, since the artefact's own front
  matter already uses the logical names, not raw Jira field keys. The
  front matter gained a seventh key, `acceptance_criteria`, beyond the six
  the ticket brief named, since the gate needs to read it from there too.
- The guard crossing S0's own Jira read is decided and passed through
  under is named `s0_intake` (a literal the ticket brief gave), not one of
  `runner.guard.CROSSINGS`'s five names; that tuple documents the crossings
  a proxied agent tool call uses; a runner-side read never touches a
  sandbox, so it was left untouched rather than widened for one more name
  it does not need to enumerate.
- `ticket.data_class` was immutable (append-only) before this ticket; S0
  now needs to set it after insert, once, so it became a `once=` column
  (`runner/schema.py`, `USER_VERSION` bumped, `ALLOWED_COLUMNS` in
  `test_mutable_exceptions.py` extended) rather than a new column.
- `TrustProfile.repository_data_classes` is optional (default `{}`) rather
  than a required field, so the many trust-profile fixtures already used
  by other tickets' tests keep loading unchanged; only the committed
  profile and its own test fixture declare it.
- `runner/outbox.py`'s pull-request operations now dispatch through a
  named `GITHUB_ROUTE_ID` constant, pinned to `github_scratch` -- the
  scratch repository is what publication can reach until the pilot
  repository is real; retargeting it later is a one-line change.
- `runner/envelope.py` was left untouched (explicitly out of scope):
  its `project.get("toolchain", {})` fallback becomes dead code once
  `project.yaml`'s top-level `toolchain` key moves under `projects`, but
  every stage entry in the manifest always sets its own `toolchain`, so
  `entry.toolchain` is never falsy and that fallback is never exercised
  in practice.
- The dry-run ticket's real-server test reads a `SOFT_FACTORY_DRY_RUN_JIRA_KEY`
  environment variable for the Jira key to read; nothing else in the repo
  names where that value should live, so this is a placeholder the real
  dry run can override once the pilot Jira project exists.

## Out of scope (left for later tickets, per the ticket brief)

The Atlassian route's agent-side S1 leg; the outbox worker's own choice of
which GitHub route a PR uses (this ticket only renames the constant and
points it at the scratch route); the Slack digest route's use; the pilot
repository's recipes and the registry route's use; the baseline route's
use.
