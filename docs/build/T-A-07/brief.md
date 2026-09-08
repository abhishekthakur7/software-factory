# T-A-07 brief: trust profile, governance approvals, and the guard on every crossing

## What this delivers

The one content-addressed governance policy, the metadata-only console that
approves it, and the single seat every content-bearing crossing must pass
through:

- `factory/config/trust-profile.yaml` — the classification taxonomy as a
  four-class dominance list (`public, internal, confidential, restricted`)
  with its join and default-deny rules; the admitted repository, Jira-project
  and Confluence-space scopes; the secret-detection rules and their bound
  `rule_set_hash`; the one permitted sanitizer pair; the five routes the
  walk crosses (`hosted_model`, `governed_export_display`, `github_pr`,
  `slack_digest`, `jira_feedback`), each carrying every field the ticket
  names; the immutable evidence references; the two governance approval
  slots; and the `both_trust_roles_identity` key T-A-06 seeded, unchanged.
- `runner/trust_profile.py` — `load_trust_profile` parses and validates
  every field above, raising `TrustProfileError` naming the first one
  missing or inconsistent; `profile_hash` hashes the file's exact bytes;
  `rule_set_hash` is the canonical hash every route's own `rule_set_hash`
  field must equal; `trust_approval_subject` binds the profile hash and the
  authority-policy hash into the one subject every `trust_profile` approval
  is decided against; `join` derives a class join or returns `None`;
  `resolve_sanitizer` looks up or confirms a permitted sanitizer pair;
  `approval_slots` builds the two `reviewer_sets.Slot`s activation is
  evaluated over; `export_permitted` and `retention_expired` answer the
  governed-export and retention questions the display route's fields carry.
- `runner/governance.py` — `propose` takes no database connection and no
  payload, building a metadata-only `Proposal` (hashes, route ids, trust-role
  identities, `both_trust_roles_identity`) from the two policy files alone;
  `decide` writes one `approval_record` per acting approver through
  `approvals.record_approval`; `activation` asks `approvals.evaluate`
  whether the profile's own slots and separation rule are currently
  satisfied, with `both_trust_roles_identity` as the one separation
  exemption.
- `runner/guard.py` — the single writer of `guard_decision`. `decide` walks
  a fixed, fail-closed order: guard unavailable (unreadable policy, dead
  connection, or a sink write failure) raises `GuardUnavailable`; an
  unrecognized class or no valid join denies; an absent route denies; a
  route that will not admit the joined class denies; a missing or expired
  trust-profile activation denies; a secret-rule hit denies, storing only
  the rule id and the caller's own safe provenance; a sanitizer rule hash
  outside its permitted pair denies, inside it records the downgrade; and
  otherwise a mapping payload is projected to the route's field allowlist,
  landing as `allow` or `redact`. `pass_through` is the seat every crossing
  calls: it re-reads the persisted row and refuses a hand-built, denied, or
  wrong-crossing decision.

## Row covered

R-T-9 (`docs/prd/02-1-ticket-record.md`): the trust profile's taxonomy,
join/default-deny rules, admitted scopes, and full per-route field set; the
metadata-only governance console and its signed, mandatory-expiry
approvals; the trust-approval subject binding the profile and
authority-policy hashes; the one guard seat on every content-bearing
crossing, fail-closed on an unknown class, absent route, unavailable guard,
secret hit, or missing/expired approval; and the non-retention of secret
material in a `guard_decision` row.

## Owner decisions this ticket follows

- Four classes (`public, internal, confidential, restricted`), the default
  join as the most dominant input, and `default_deny: true` for an
  unrecognized class or an underivable join.
- The five routes' shape, with `hosted_model` the one live deliverer and
  every other route a stub, per the ticket's field list.
- The digest route's five-field allowlist (`ticket_id, tier, item_kind,
  age, command`) as a closed set the validator enforces.
- The two approval slots (`security_approver`,
  `legal_data_governance_approver`), each requiring one distinct actor from
  the other except `both_trust_roles_identity`.
- No deliverer implementation for any route; the stub/live flag is data
  only, per the ticket's explicit exclusion.

## Decisions made during the build that the design did not cover

- **`join_rules` shape.** The ticket names "how classes join" and "an
  explicit table may name exceptions" without fixing a schema. Built as
  `join_rules: {default: dominant, exceptions: [{classes: [a, b], result:
  c}, ...], default_deny: true}` — `exceptions` stays an explicit,
  independently-required list (empty here, since no pair among four totally
  ordered classes needs one) rather than a field with a silent default, so
  a file that forgot the key entirely still fails loudly.
- **`export_rule`'s shape and how `export_permitted` reads it without a
  profile.** The ticket's own signature, `export_permitted(route,
  request)`, takes no profile argument, yet judging "is this class within
  the rule" needs the taxonomy's dominance order. Resolved by precomputing
  `admitted_classes` (every class at or below `max_class`) onto the route's
  `ExportRule` at load time, so the route object alone answers the
  question and the profile's order never has to travel with every call.
- **`resolve_sanitizer`'s `target_class` becoming optional.** An `Operation`
  names only the sanitizer it invoked and the class it downgrades from,
  never the class it expects to land on, so the guard cannot ask "is this
  exact triple permitted" the way a direct unit test can. Made
  `target_class` default to `None`: given, it confirms one exact registered
  triple (what `test_trust_profile.py`'s criterion-7 tests do); left out,
  it looks up whatever target the rule is registered for from that source
  class (what `guard.decide` does), and either form returns `None` when the
  pair is not registered.
- **How `guard.decide` gets an active-or-not answer without a profile
  argument on `governance.activation`.** Solved by having `decide` build a
  `Proposal` itself (`governance.propose(profile_path, owners_path)`) and
  pass it to `governance.activation`, so the guard and the console always
  agree on what the current subject is; the cost is loading the profile and
  owners files twice per guard decision, accepted for correctness over a
  micro-optimization at this scale.
- **`governance.decide`/`governance.activation` needing file paths the
  ticket's signatures do not list.** `decide` must take a fresh
  `identity_snapshot`, which needs a loaded `Owners`, which needs both file
  paths; `activation` must build `approval_slots`, which needs a loaded
  `TrustProfile`. Both signatures grew optional `owners_path`/`profile_path`
  keyword arguments defaulting to the committed paths, so the tests'
  "activate against a tmp copy of the committed profile and owners" rule
  works without smuggling a path onto the metadata-only `Proposal` itself.
- **`guard_decision.input_data_class`'s single column holding a tuple of
  input classes.** Stored as the canonical JSON encoding of the list, the
  same convention the schema already uses for `reviewer_set.slots` and
  other JSON-shaped `TEXT` columns.
- **`pass_through`'s refusal of a raw payload.** Added an explicit
  `isinstance(decision, Decision)` check so handing the seat a bare string
  instead of a `Decision` object is refused the same way a hand-built or
  denied one is, rather than relying on a caller convention no test could
  pin.
- **`SecretRule`'s compiled pattern.** Given a custom `__init__` (dataclass
  skips generating one when the class defines its own) so the regex
  compiles once at load time instead of on every scan.
- **`test_owners.py`'s pinned single-key test.** Per the build instructions,
  `test_committed_trust_profile_carries_only_the_one_key` is rewritten
  (renamed to `test_committed_trust_profile_still_names_both_trust_roles_identity`)
  to assert the invariant it exists to pin — `both_trust_roles_identity:
  abhishek` still loads through the real validator — now that the file
  carries this ticket's full governance content rather than the one key
  alone.

## Out of scope

Any real deliverer for a stub route (a sibling ticket's work); the pilot
repository and its real admitted scope beyond the `fixture-project` name;
the Atlassian read routes; the outbox's own dispatch mechanics; governed
export/import/purge execution (only the display route's rule and retention
flag are built here); and the reviewer-set derivation behind quorum
(already built by T-A-09, landed ahead of this ticket). `runner/schema.py`,
`runner/db.py`, `runner/approvals.py`, `runner/reviewer_sets.py`,
`runner/canonical.py`, `runner/gates.py`, `runner/state_table.py`, and
`runner/owners.py` are untouched.

## Verification

`uv run pytest -q` — 383 tests pass (301 before this ticket, plus 41 in
`test_guard.py` and 41 in `test_trust_profile.py`; `test_owners.py` keeps
its existing count with one test rewritten rather than added).
