# T-A-32 brief: waivers and the non-waivable list

## What this delivers

`runner.waivers` gains a real write path (`issue`) and a deepened
`validity` over the seam another builder already committed
(`blocking_status`, `cleared`, `waiver_for_result`, `effective_result` --
signatures and return shapes unchanged). A blocking epistemic
`blind_spot`, whether a bootstrap-checklist verdict at S3 or an S5
`check_result`, advances only under an immutable `waiver` row whose
`waiver-policy.yaml` policy names the actor's role and the exact
condition, carries mandatory expiry, reason, scope, compensating
controls, and evidence, and is rechecked -- not merely trusted -- at
every later ask. Nine kinds of failure the pilot's human contract treats
as non-negotiable (a secret hit, an unknown classification or trust
approval, a sandbox-integrity failure, a stale base/head/tuple, a
reviewer-set or quorum mismatch, an approval mismatch, a missing
required artefact, and Initial-scope exclusion) are refused by check
name before any policy is even consulted.

## Rows covered

R-S5-13 (`docs/prd/04-S5-cleanup-pass.md`).

## Owner decisions this ticket follows

A `fail` result is never waivable -- only a declared `blind_spot` is,
since a fail is a defect, not an epistemic gap. A waiver's own
`policy_exception` tag reports the waiver but grants no authority beyond
it: `checklist.completeness`, `waivers.cleared`, and `waivers.validity`
never read a tag, only a `waiver` row. A review-tuple waiver shares the
`red_check` item S5's own failures opened, resolved automatically the
moment the run clears -- never through a human passing `waived` to
`queue.act`, which the action's absence from `ACTIONS["red_check"]`
enforces structurally rather than by convention.

## Design decisions this brief left open

- **`load_policy`'s YAML shape and the two pilot policies.** The ticket
  brief gave the never-waivable list verbatim (copied as-is into
  `factory/config/waiver-policy.yaml`) and one illustrative policy entry
  with a placeholder `"rubric:*"` condition, leaving "choose the real
  list of conditions" to this ticket. `impact-blind-spot` covers every
  plan-candidate grader-line blind spot (`conditions: ["*:grader"]`,
  glob-matched with `fnmatch`) under the pilot's one reviewer role plus
  the factory owner; `contract-evidence-gap` covers the two review-tuple
  conditions the entity paragraphs and the ticket's own text name by
  name (`behavior_contract_evidence`, `base_test_diff`) under the S6
  reviewer plus the factory owner. Two policies, matching "two or three
  are enough for the pilot".
- **The condition a waiver's own subject names.** For a review-tuple
  waiver the condition is the waived `check_result`'s `check_name`; for
  a plan-candidate waiver it is the verdict's `rubric_line_id`. Both are
  checked against `never_waivable` and a policy's `conditions` the same
  way, via `fnmatch.fnmatchcase`, so a policy may name either a literal
  check name or a glob over rubric line ids without two code paths.
- **The actor's recorded role.** `issue` intersects the actor's held
  roles (from `owners.yaml`) with the policy entry's `roles` and records
  the lowest-sorted match on `waiver.actor_role`; `validity`'s
  `lost_authority` check re-derives the same intersection at recheck
  time against whatever `owners.yaml` the caller points it at.
- **The `policy_exception` tag's target.** `tags._TARGET_TABLES` has no
  `waiver` entry (that table belongs to another builder this wave), so
  `issue` tags `ticket:<id>` and puts `waiver:<id>` in the note. The
  merge should retarget this to `waiver:<id>` once that table gains the
  entry.
- **`validity`'s reasons are independent, not layered.** Every check
  (expiry, policy drift, lost authority, subject drift, evidence drift,
  and the waived row's continued existence as a `blind_spot`) runs
  regardless of what already failed, so `reasons` can name more than one
  cause at once and a caller never has to guess which check produced a
  given `Validity(False, ...)`.
- **`checklist._waived`'s existing signature and callers are unchanged.**
  It still asks "does any waiver naming this verdict currently hold",
  now via `waivers.validity` instead of a bare expiry comparison;
  `completeness`, `verdict_set`, and `waiver_set` are untouched.
- **`gates.checks_gate` and `cli._due_stage`'s S5 rule are the same
  rule, expressed twice** (a passed run, or a cleared one) because the
  two call sites read different tables (`gates` reads the ticket's
  state; `cli` iterates the state's stages) and neither owns the other.

## Out of scope

The dispatch recheck's outbox wiring, the S6 evidence-table assembly
that lists a waiver by content (both the next ticket's, per the ticket
brief's own scope line) -- this ticket's own test of criterion 7 is
written and passes once `factory/scripts/tools/packet_assemble` exists,
`pytest.mark.skipif`'d until then. `tags.py`'s `_TARGET_TABLES` and the
tag catalogue itself (a parallel builder's ticket).
