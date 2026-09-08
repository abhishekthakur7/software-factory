# T-A-20 brief: S0 for real -- lookups, provisional tier, sensitive paths,
scrutiny, eligibility, exclusion

## What this delivers

S0 stops being a stub: it runs the section 8 lookups and the whole
Initial exclusion matrix for real, no agent involved. A ticket's service
tier, ticket type and provisional tier are resolved once from
`service-tiers.yaml`/`ticket-types.yaml` and stamped onto the ticket. A
sensitive-path candidate in the ticket's title raises `tier_final` to
`heavy`; the pilot eligibility matrix and the excluded-surface scan (a
lax, generous text/path match against `exclusions.yaml`) together decide
whether S0 rejects the ticket mechanically. A ticket that clears both
gets its scrutiny paragraph filled from a per-type template and one
`eligibility` queue item opened; an empty rendering holds it at `intake`
with no item. `factory act` on that item now runs behind a governance
validity check, and `override` can move `tier_final` directly.

- `runner/stages/S0.py` (rewritten) -- `_lookup` (service tier, ticket
  type, provisional tier, from already-loaded config dicts);
  `sensitivity_match`/`SensitivityMatch` (provisional or authoritative,
  shared by S0 and the later S5 caller); `_render_scrutiny`;
  `governance_valid(conn, ticket, *, now=None, profile_path=..., 
  owners_path=...) -> list[str]`; `run(conn, ticket, stage_run_id, 
  runs_dir, *, service_tiers=None, ticket_types=None, sensitive_paths=None,
  exclusions=None)`, the extra keyword-only config overrides existing only
  for tests -- `run_stage` still calls it with the same four positional
  arguments every driver takes.
- `runner/checks/__init__.py`, `runner/checks/exclusion.py` (new) -- pure
  functions over data: `eligible`, `surfaces_in_text`,
  `surfaces_in_paths`, `decide_at_checks`, plus the one function that
  touches the database, `apply_recorded_exclusion(conn, ticket_id)`,
  which reads the ticket's latest `check_result` exclusion row through its
  `stage_run` and applies `s1_exclusion`/`s3_exclusion`/
  `checks_sensitive_path_required` by the stage that recorded it,
  returning whatever `transitions.apply` returns (the landed state).
- `factory/config/service-tiers.yaml` -- `language: java`,
  `repositories: [fixture-project]` added to the fixture service.
- `factory/config/ticket-types.yaml` -- all five types, each with
  `jira_issue_types`, `eligible_services`, and a `scrutiny_template`;
  `small_feature_max_points: 3`; the 15-cell `provisional_tier` matrix.
- `factory/config/sensitive-paths.yaml` -- `payments` and `secrets` globs
  added, owner `abhishek`.
- `factory/config/exclusions.yaml` (new) -- the eight excluded surfaces,
  each with `path_globs` and `text_patterns`; `sensitive_path`'s own globs
  are read from `sensitive-paths.yaml` rather than repeated.
- `runner/queue.py` -- `act` gains a `tier` parameter and, for an
  `eligibility` item, a `governance_valid` check before any action
  dispatches (imported inside `act`, not at module scope, since S0 itself
  opens this item through `queue.open_item` and a top-level import in
  either direction would be circular); `_override` takes `tier` and
  refuses outright when the ticket's `close_reason` is already
  `pilot_excluded`; `_resolve` now also writes `queue_item.resolved_role`
  from `_actor_role`.
- `runner/cli.py` -- `--tier` on `act`.
- `runner/state_table.py` -- `("intake", "s0_exclusion"): "rejected"` and
  `CLOSE_REASON["s0_exclusion"] = "pilot_excluded"`.
- `runner/schema.py` -- `ticket.service_tier`/`ticket_type`/
  `tier_provisional` become one `once="tier_provisional"` group (S0
  writes whichever of the three a ticket doesn't already carry, exactly
  once each); `ticket.tier_final` and `ticket.scrutiny_requested` become
  `mutable=True`; `queue_item.resolved_role` added to the `resolved_at`
  once-group.
- `runner/db.py` -- `USER_VERSION` bumped to 9.
- `runner/tests/test_s0.py`, `runner/tests/test_exclusion.py`,
  `runner/tests/fixtures/s0/owners_engineer2.yaml`,
  `runner/tests/fixtures/exclusion/*.yaml` (new).
- `runner/tests/test_mutable_exceptions.py` -- the three new/changed
  mutability groups added to the hand-written allowlist.
- `factory/manifest.yaml` -- hashes recomputed for the three changed
  config files, an entry added for `exclusions.yaml`, and the stale
  duplicated `content_hash:` line under `trust-profile.yaml` deleted.

## Row covered

R-S0-2, R-S0-5, R-S0-6, R-S0-7, R-S0-8 (`docs/prd/04-S0-intake.md`); the
pilot eligibility, ticket-type/Jira mapping, provisional-tier matrix and
sensitive-paths tables of `docs/prd/08-configuration.md`.

## Owner decisions this ticket follows

Every decision named in the ticket brief: config over code for every
table; the S0 driver's four-step order (lookups, sensitive-path
candidates, the exclusion gate, the scrutiny fill); `eligibility`'s
closed action set keeping `granted` even though the ticket text says
"approve"; `override` taking `--tier`; `resolved_role` recorded by
`_resolve`; the exclusion checks module's four pure functions plus
`apply_recorded_exclusion`; the criterion-6 fixture using a sensitive-path
owner distinct from the pilot's shared identity.

## Decisions this brief did not already settle

- **The once-settlement group for `service_tier`/`ticket_type`/
  `tier_provisional`.** The ticket brief says S0 writes these "once to
  the ticket's immutable columns" but the schema carried no mechanism for
  that before this ticket -- a plain immutable column accepts no UPDATE
  ever, even a first one. The existing precedent (`stage_run`'s cost
  fields, `queue_item`'s resolution fields) is exactly this shape: an
  `once=<sentinel>` group settles together, in place, exactly once.
  `tier_provisional` is the sentinel since it is always the last of the
  three S0 sets; a ticket seeded with all three already set never
  triggers the UPDATE at all (S0 only writes the still-null members), so
  "a ticket seeded with them already set keeps them" holds without S0
  needing to special-case it.
- **`scrutiny_requested` becomes `mutable=True`, not part of that
  once-group.** R-S0-6 says the human "confirms or edits it at
  eligibility" -- a field a human may still change later cannot share a
  write-once group with three lookups that never change again.
- **`governance_valid` takes `profile_path`/`owners_path` overrides,
  defaulting to the committed files.** Every other governance-reading
  call in this codebase (`governance.propose`, `governance.activation`)
  takes the same pair for the same reason: production code always uses
  the defaults, and a test can exercise a deliberately broken profile
  (the "invalid route" governance scenario, criterion 10's fourth case)
  without touching the committed one. A profile that fails to load is
  caught inside `governance_valid` and reported as `"invalid route"`
  rather than raised, since a broken policy file is exactly the situation
  an eligibility decision must refuse against, not crash on.
- **`S0.run`'s extra keyword-only config parameters exist for tests.**
  `run_stage` always calls every driver's `run` with the same four
  positional arguments, so they can never be wired through the ordinary
  advance/run path; criterion 8's empty-template case (needing a
  `ticket-types.yaml` with one type's template blanked) calls `S0.run`
  directly with an overridden `ticket_types` dict instead.
- **The exclusion text/path scan reads `ticket.title` only.** R-S0-1's
  real Jira ingestion and redacted source text are out of this ticket's
  scope, so no other free-text field exists on a ticket yet; the same
  scan later reads `ticket_source`'s registered front matter when one is
  pre-registered (the Epic-mapping and Jira-derived-ticket-type paths),
  captured before S0's own stub write supersedes it.
- **Collateral fixes to five pre-existing tests, each because the real S0
  driver refuses what the stub always passed.** `test_stub_stages.py`'s
  S0 test, `test_cli_skeleton.py`'s advance walk, and
  `test_report.py`'s completed-walk fixture each seeded a bare ticket
  with no `service`/`ticket_type`; all three now seed the pilot-eligible
  pair (`fixture-project`/`small_feature`) so S0's lookups pass rather
  than reject, with no other change to what each test asserts.
  `test_act.py` and `test_attention_bucket.py` each call `queue.act` on
  an `eligibility` item from a ticket that carried no governance state at
  all; both now activate the committed trust profile through
  `governance.propose`/`decide` (the same default-path convention
  `test_outbox.py`'s reconcile-first test already uses) and stamp the
  resulting hashes onto the ticket, since `trust_profile_hash` is itself
  append-only and cannot be patched in after the fact.

## Out of scope

R-S0-1's real Jira ingestion, redaction and mechanical acceptance-gate
(a separate, earlier PRD row this ticket does not cover); the real S1
final-tier computation over touched files/services/unknowns (T-A-22); the
real S3 planned-reviewer-set derivation bound into the plan tuple
(T-A-27); the real S5 preflight driver's actual-diff exclusion proof
(T-A-30) -- criterion 4 exercises `sensitivity_match`'s authoritative path
directly instead, since no live S5 driver exists yet.
