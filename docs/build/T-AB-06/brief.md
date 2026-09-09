# T-AB-06 brief: trusted GitHub publication through the transactional outbox

## What this delivers

`runner/deliverers/github.py` is the one trusted-side adapter for the
scratch repository's two pull-request operations.  It receives a narrow,
injectable REST client, obtains `github_publish` only immediately before a
live call, pushes the ticket branch with a lease, and creates or updates the
same draft pull request.  The outbox retains ownership of intent creation,
freshness checks, reconciliation, receipt storage, and ticket transitions.

The adapter has no direct database dependency.  It validates the remote
state needed for a safe request and translates a remote response into the
existing `Receipt` type.  The worker chooses it only for the configured
scratch GitHub route.  Routine tests use an in-memory fake transport whose
operations mirror the REST and lease contract; the eventual closing run is
separate and requires an owner-created scratch repository and credential.

Row covered: R-S6-3.

## Owner decisions this ticket follows

- The configured scratch remote is currently absent.  A live route fails
  closed with a specific configuration error; no test or normal command may
  discover or substitute a repository.
- The GitHub adapter uses the official REST API for pull-request lookup and
  creation/update, while the git push remains a local `git push
  --force-with-lease` subprocess because GitHub's REST API cannot push a git
  ref with lease semantics.  Its injected client makes this boundary fully
  testable.
- A closed or merged pull request is surfaced before mutation as `pr_outcome`.
  This ticket records the queue item only; later work decides its action.

## Explicitly out

The GitHub credential-store implementation and scratch repository creation;
the `pr_outcome` response workflow; the S6 packet assembly path; and any
publication to a pilot repository.
