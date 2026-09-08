# T-A-06 brief: owners file, roles, authority-policy hash and identity snapshot

## What this delivers

The authority policy every trust and ticket approval binds against, plus the
one module that reads it:

- `factory/config/owners.yaml` — an identity and a non-empty responsibilities
  list (drawn from a closed category set) for every named role: factory
  owner, security approver, legal/data-governance approver, service owner,
  sensitive-path owner, ticket engineer, S3 reviewer, S6 reviewer, outcome
  recorder, incident reviewer. A `shared_identities` block records, as data,
  that the pilot's one identity holds several non-sensitive roles at once,
  with a one-sentence note saying so.
- `factory/config/trust-profile.yaml` — seeded with only the
  `both_trust_roles_identity` key, the one field this ticket owns in that
  file. Naming an identity there is what permits that identity to fill both
  of the two trust roles (security approver and legal/data-governance
  approver) at once; every other field in the file is a later ticket's.
- `runner/owners.py` — `load_owners` parses and validates the owners file
  (every required role present with a non-empty identity, responsibilities
  non-empty and from the closed set, `shared_identities` consistent with the
  roles it summarizes, and the trust-role rule above), raising one
  `OwnersError` on the first problem found; `authority_policy_hash` hashes
  the file's exact bytes, since the hash a decision binds to must catch any
  change to the committed file, not just ones a parser would treat as
  meaningful; `identity_snapshot` returns an identity's current roles and a
  timestamp, meant to be hashed independently (via `runner.canonical.content_hash`)
  at each decision, so a role assignment and the person holding it at
  decision time are never conflated into one hash.

## Row covered

R-F-13 (`docs/prd/07-factory-as-code.md`): the owners file names every role
with responsibilities; its content hash is the authority-policy hash bound
by approvals; identity/team membership is snapshotted separately at each
decision; one pilot identity may hold several non-sensitive roles, recorded
as such; one identity may fill both trust roles only when the trust profile
permits it.

## Owner decisions this ticket follows

- One pilot identity (`abhishek`) for every role.
- The closed responsibility-category set and its assignment per role.
- `shared_identities` lists only the non-sensitive roles the shared identity
  holds — the two trust roles and the sensitive-path-owner role are excluded
  from that list, since the trust-role pairing is already gated separately
  by `trust-profile.yaml`, and a role named for sensitive work is not the
  kind of role this ticket's shared-identity note is about.
- `trust-profile.yaml` seeded with exactly the one key this ticket owns;
  its remaining content is a later ticket's.
- `runner/owners.py` builds no approval-record writing, no quorum, and no
  `factory` CLI verb; those are later tickets. It never writes under
  `factory/` — it only reads `owners.yaml` and `trust-profile.yaml`.

## Out of scope

`trust-profile.yaml`'s remaining content, routes, classes and sanitiser
identities; reviewer sets, approval-record writing and quorum computation;
sensitive-path exclusion enforcement. `runner/schema.py`, `runner/db.py`,
`runner/stages/`, `runner/run_ledger.py`, and `factory/config/tiers.yaml`
are untouched by this ticket — they belong to work done in parallel.

## Decisions made during the build that the design did not cover

- `Owners` is a plain class holding `roles` (dict) and `shared_identities`
  (list) rather than a frozen dataclass, since both fields are themselves
  mutable containers straight from the parsed YAML and a frozen wrapper
  around them would not add any real immutability.
- `identity_snapshot` returns only the snapshot dict, not its hash — the
  brief's phrasing ("its hash via `runner.canonical.content_hash`") reads as
  "hash it by calling `content_hash`", so the hashing step is left to the
  caller (and to `test_owners.py`), matching how every other snapshot/hash
  pair in the record already works (`canonical.content_hash` takes a plain
  mapping, not a snapshot-specific type).
- `shared_identities` consistency is checked one entry and one role at a
  time against the identity already recorded on that role in `roles`,
  rather than reconstructing a reverse index — the file is small enough
  that a reverse index would be an abstraction for a single caller.
