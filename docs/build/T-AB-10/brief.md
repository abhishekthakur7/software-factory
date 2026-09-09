# T-AB-10 brief: baseline cohort import

## What this delivers

`factory/scripts/tools/baseline_import` imports a bounded, evidence-backed
baseline before Milestone B. It selects retrospective Jira tickets by service,
admitted type, completion, and cutoff; records the exact selection and source
locators in one artefact; and writes one baseline ticket and every requested
measure for each member. The post-plan revision count is observed only when a
timestamped approved plan or design decision anchors it. Question, latency,
and attention measurements are deliberately approximate, while missing,
mismatched, or non-attributable evidence is represented by an unavailable row.

The same importer optionally receives a separately cut off supplemental cohort
of prospective, non-factory tickets. It accepts it only when the retrospective
cohort has fewer than ten observed revision values and its endpoint identity
matches the retrospective cohort. Once both cohorts are complete, it freezes
the selection artefact. The record rejects a new baseline ticket or measure for
that frozen cohort, including after later factory data exists.

## Decisions

- The repository currently names only `fixture-project`, with no real Jira,
  Confluence, GitHub, or pilot checkout. Routine coverage therefore uses
  injectable transports and deterministic history fixtures. A closing-run test
  skips loudly until a non-fixture pilot and both credentials are configured;
  it never fabricates a live observation.
- The source contract is a small normalized record: ticket metadata comes from
  Jira; `history` holds approved-plan/design decisions and question/latency/
  attention evidence; GitHub supplies pull-request revisions. Readers own
  transport details, while the importer owns the measure rules.
- `baseline_read` is the only allowed route. Reader methods require that route
  and an allowed role before a transport call, and the importer projects only
  the route's declared fields into its artefact and measures. This keeps route
  enforcement at the external-read boundary and avoids storing raw payloads.
- A cohort is identified by a canonical hash of its selection artefact. The
  frozen flag lives on that artefact record, and write helpers require the
  cohort id for every baseline insertion. This gives one refusal path instead
  of relying on callers to remember a freeze check.

## Explicitly out

Graduation comparison and manual outcomes arrive later. The import does not
alter the existing baseline SQL views or invent a live pilot configuration.
