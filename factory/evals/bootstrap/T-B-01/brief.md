# T-B-01 brief: the manual outcome record

## What this delivers

`runner/outcome.py` is the one module recording what actually happened to
an opened pull request, entered by hand: `revision` (a review that sends
the ticket back before it merges or is abandoned), `outcome` (the final
`merged`/`abandoned` disposition, the actual final SHAs, the required-check
disposition, and an optional observed PR-body snapshot), the
`exposure`/`coverage` production-coverage series, `incident_event` and
`disposition` for a later production incident, and `control_event`
(unchanged in shape, now deriving its severity from policy when none is
given). `runner/queue.py`'s `act` dispatches `revision`/`outcome` for the
non-blocking `pr_outcome` item it already opens, and dispatches
`exposure`/`coverage`/`incident_event`/`disposition` for a bare ticket id
with no queue item at all -- these run any time after the outcome itself,
independently of it.

`factory/config/incident-policy.yaml` (new) names the severity scale,
each control category's default severity, and the closed attribution and
disposition value sets a production-incident disposition must fit;
`runner/incident_policy.py` is the one place that reads it. S4's existing
`execution_boundary` control-defect event, and the ticket-scoped
`control_event` action, both move from a literal `sev2` to this file.

`outcome` never refuses for a mismatch between what is observed and the
ticket's own approved subject -- it records `approval_disposition` and, on
a mismatch, appends one mechanical `control_defect` tag (`FM-25`) and its
control-defect event and open disposition, in the same call. The one
locator read this ticket performs -- an immutable `--pr-identity
--observed-head-sha` snapshot of a PR body -- reuses the outbox's own
GitHub route and deliverer rather than opening a second polling surface;
`runner/tests/test_outcome_no_poll.py` proves the GitHub transport is
reachable from nowhere else.

Row covered: R-H-11.

## Design decisions

- Every action reads its flags from one `fields` mapping, so the queue's
  `act` gains one parameter rather than twenty.
- `outcome_actor_role`/`recorder_role` are fixed role strings
  (`outcome_recorder`, `incident_reviewer`) per action, not derived from
  whichever role the acting identity happens to hold first; validating that
  the actor actually holds that role is later work.
- The observed-body document is written identically regardless of source
  (a governed file or the remote locator), so a byte-identical body hashes
  identically against `ticket.last_pr_body_hash`.

## Explicitly out

Exporting these actions through `runner/stage_interface.py`, API
exclusivity/graduation-authority/import-graph tests, per-action script
tests and RACI-role enforcement, the graduation report's own reading of
these rows, and S7's automated remote observation eventually replacing
this manual record.
