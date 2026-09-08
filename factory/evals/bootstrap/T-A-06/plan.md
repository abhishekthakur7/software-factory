# T-A-06 plan

## Steps

| # | Step | Files touched | Proves |
|---|---|---|---|
| 1 | Seed the owners file: an identity and a non-empty, closed-set responsibilities list for every required role, plus a `shared_identities` entry recording the pilot identity's non-sensitive roles with a one-sentence note. | `factory/config/owners.yaml` | `test_owners.py`'s committed-file tests (criteria 1, 2, 6, 8) |
| 2 | Seed the trust profile with only the one key this ticket owns. | `factory/config/trust-profile.yaml` | `test_owners.py`'s committed-file test (criterion 9) |
| 3 | `load_owners`: parse, validate every required role's identity and responsibilities, validate `shared_identities` against the roles it summarizes, and validate the trust-role rule via `trust_profile_path`; raise one `OwnersError` on the first problem. | `runner/owners.py` | `test_owners.py`'s must-reject tests (criteria 2, 3); `test_trust_role_permission.py` (criterion 7) |
| 4 | `authority_policy_hash`: SHA-256 hex of the file's exact bytes. | `runner/owners.py` | `test_owners.py`'s hash tests (criterion 4) |
| 5 | `identity_snapshot`: an identity's current roles plus a timestamp, meant to be hashed independently via `runner.canonical.content_hash`. | `runner/owners.py` | `test_owners.py`'s snapshot tests (criterion 5) |
| 6 | Write both hashes onto one `approval_record` row through the ordinary `record.insert` path and read them back. | `runner/tests/test_owners.py` | criteria 4, 5 together, against a real row rather than the bare functions |
| 7 | This ticket's own brief and plan. | `docs/build/T-A-06/brief.md`, `docs/build/T-A-06/plan.md` | reviewed by the human, not a test |

## Test strategy

`test_owners.py` loads the real committed `owners.yaml` and
`trust-profile.yaml` for the structural assertions (criteria 1, 2, 6, 8, 9),
then switches to `tmp_path` fixtures built from one Python dict
(`_owners_doc`) for every negative case, so each must-reject test mutates
exactly the field it means to break rather than committing a whole fixture
file per scenario. The hash tests recompute a SHA-256 over the file bytes
independently of `authority_policy_hash` (so a wrong implementation that
hashes the parsed structure instead of the bytes, or a no-op hash function,
fails), and the snapshot tests hash two different identities' snapshots to
confirm they diverge from each other and from the policy hash, then rewrite
the file to confirm the policy hash moves while an already-taken snapshot's
hash does not.

`test_trust_role_permission.py` isolates the one rule acceptance criterion 7
names: it holds the owners file constant (both trust roles pointing at the
same identity) and varies only the trust-profile file across five cases —
naming that identity (accept), the key absent, the file missing entirely,
the key set to `null`, and the key naming a different identity (all reject)
— plus one control case with distinct trust-role identities and no profile
file at all, to confirm the gate only fires when it needs to.

## Verification

`uv run pytest -q` — 251 tests pass (230 before this ticket, plus 15 in
`test_owners.py` and 6 in `test_trust_role_permission.py`).
