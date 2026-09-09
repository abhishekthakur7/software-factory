# Milestone B build tickets: pilot

| | |
|---|---|
| Status | Draft v0.2 |
| Date | 2026-09-09 |
| Owner | Abhishek Thakur |
| Cites | `docs/design/milestones.md` v0.7 (section 3 "B, pilot", decision 7, Appendix A); `docs/prd/prd.md` v0.18 and its parts; `docs/charter.md` v0.14 (section 8 "Pilot graduation"); `docs/design/hld/README.md` v0.3; `docs/design/tickets/A.md`; `docs/design/tickets/AB.md` |
| Milestone | B: the manual outcome record, the list view complete, the graduation gate, the parallel limit with its graduation-bound raise, the stage interface complete, and the pilot ticket's definition of done, 5 requirement rows; plus two closing tickets that connect the live services and rehearse the pilot on a dry run |

## How to read

One ticket per section, in build order. A ticket depends only on tickets above it in this file or on Milestone A and AB tickets in `A.md` and `AB.md`, so the file order is a topological order. Every ticket names its milestone, its blocks by number from `milestones.md` section 1, its components by id from the HLD register, the tickets it depends on, the PRD rows it covers, what it builds and why, its scope in and out, numbered acceptance criteria that each restate one verification clause of one row as a test that passes or fails, and the test files and fixtures it adds. A row sits in exactly one ticket. The two closing tickets, T-B-06 and T-B-07, cover no row of their own: their `Rows exercised` cell names the rows of earlier tickets whose live, pilot-host clauses they run, and their criteria cite those rows. `tools/tickets_check.py` enforces the format, the coverage of Appendix A, the placement, the dependency order, the citation of a row id on every criterion, and that an exercised row belongs to an earlier ticket.

Three phases, fixed by `milestones.md` section 3 and its decision 7. Phase 1, the outcome record and the list view complete (T-B-01, T-B-02): the `pr_outcome` item's `revision` and `outcome` actions, the outcome fields on `ticket`, the exposure and coverage series, production incidents and dispositions under `incident-policy.yaml`, and every human action of the list view proven through `factory act`. Phase 2, the graduation gate and the capacity raise (T-B-03, T-B-04): the canonical graduation report over a window of the record and the frozen baseline, the recorded owner approval binding the report, the thresholds and the configuration hash, and the parallel ticket limit whose raise only that approval permits. Phase 3, the stage interface complete and the definition of done (T-B-05): `runner/stage_interface.py` as the one operation surface with the API-exclusivity, graduation-authority and import-graph tests, `fixture_from_export`, and the closing run that takes the pilot ticket from its Jira key to a draft pull request, records its outcome by hand, evaluates the real gate as not passed, and turns its governed export into the first redacted real fixture. Phase 4, the live connection and the dry run (T-B-06, T-B-07): every stub route and empty credential the AB tickets left behind wired to its real service, `factory doctor` as the one readiness predicate, and the dry run on the pilot host that executes every clause the earlier tickets deferred to it, first the AB exit test's dry-run ticket to `clarifying`, then a rehearsal ticket through every stage to a draft pull request on the scratch repository, with the record-reading assertions the pilot ticket's closing run reuses. Every criterion runs on seeded rows, the fakes under `runner/tests/fakes/` and the fixture project, except the criteria that open "On the closing run", which run once on the pilot ticket on the pilot host, and the criteria of T-B-07, which run on the pilot host over the live services. Under PRD decision 39, each ticket's builder hand-writes `docs/build/<ticket-id>/brief.md` and `plan.md` before building that ticket, the rule T-A-01 states. Names no source document fixes are stated in the ticket that first uses them and hold for every ticket after it: the outcome actions are `factory act` on the `pr_outcome` item and the ticket-scoped `act` actions, the graduation verb is `factory graduate`, the thresholds and the parallel limit live in `limits.yaml`, the one operation surface is `runner/stage_interface.py`, the readiness report is `factory doctor`, the owner-side steps no code can perform live under `docs/runbooks/`, and the dry run's inputs are the `SOFT_FACTORY_DRY_RUN_JIRA_KEY`, `SOFT_FACTORY_DRY_RUN_DB` and `SOFT_FACTORY_DRY_RUN_TICKET` environment variables.

## T-B-01: Manual outcome record: the `pr_outcome` item's `revision` and `outcome` actions, dispositions, the exposure and coverage series, production incidents, `incident-policy.yaml`, no polling

| | |
|---|---|
| Milestone | B |
| Blocks | 9 Ticket and its state; 12 Queue item and decision |
| HLD components | C2, H2, C1, R1, C7 |
| Depends on | T-A-01, T-A-03, T-A-04, T-A-06, T-A-10, T-A-12, T-A-13, T-A-29, T-A-32, T-A-33, T-A-34, T-AB-04, T-AB-06, T-AB-07, T-AB-10 |
| Rows covered | R-H-11 |

### Description

Once Initial opens the pilot ticket's first draft pull request, the runner queues one non-blocking `pr_outcome` item, since external truth about it is never inferred from the factory's own approved intent. A recorded revision writes a `revision_after_approval` tag and returns the ticket through `S3` to `S6` again, while the remote branch stays untouched until a new `pr_update` is approved. The final action records the observed `merged` or `abandoned` disposition with the actual final SHAs, the required-check disposition, and the PR-body hash from a governed snapshot or an immutable locator. It compares these against the ticket's latest approved subject, sets `approval_disposition` to `matched`, `mismatched`, or `unknown`, and never refuses or rewrites what actually happened. A mismatch appends a `control_defect` tag with `fm_id` `FM-25` and an approval-binding control-defect event, its severity read from `factory/config/incident-policy.yaml`, the file this ticket creates with content for the first time and which also gives S4's existing execution-boundary event a severity value it lacked. Independently, abandonment and merge each start the production-coverage series, and a human may later record exposure, coverage, or a production-incident event and its disposition. The runner performs no Initial polling of GitHub beyond the reconciliation reads T-A-13 and T-AB-06 already built and this action's own narrowly scoped locator read. It sits on the state table's existing `pr_opened` transitions, `runner/schema.py`'s once-settled outcome fields, and the owners file's roles, and its seeded tests run against T-AB-06's fake GitHub transport.

### Scope

**In:** `runner/outcome.py` (new module holding the `revision`, `outcome`, `exposure`, `coverage`, `incident_event`, `disposition`, and A's `control_event` actions), wired into T-A-12's `runner/queue.py` act dispatch for the `pr_outcome` item and for the ticket-scoped calls; the `act` parser in `runner/cli.py` changed so `item_id` is optional when `--ticket <ticket-id>` names a ticket-scoped action, `revision` reading its target stage from the existing `--to`, its failure-mode id from `--fm` and its review ground from `--note`, `outcome` gaining `--result merged|abandoned`, `--head-sha`, `--target-base-sha`, `--merge-sha`, `--checks green|waived|red|unknown`, `--checks-reason`, `--observed-at`, and either `--body-file <path>` or `--pr-identity <id> --observed-head-sha <sha>`, `exposure` gaining `--start` and `--source`, `coverage` gaining `--through`, `incident_event` gaining `--severity`, `--occurred-at`, `--note` and `--fm`, and `disposition` gaining `--event`, `--attribution`, `--disposition` and `--remediation-ref`; `factory/config/incident-policy.yaml` (new, with content: `severity_levels` naming `sev1` through `sev4`, `control_categories` mapping each of the five control categories to a severity level with every category defaulting to `sev2`, `production_incident` validating a human-entered severity against `severity_levels`, `attribution_values`, `disposition_values`, and `remediation_rule` requiring at least one catalogue or rubric remediation ref on a `remediated` disposition); a change to the ticket-scoped `control_event` action so its `--severity` flag becomes optional, deriving the value from `incident-policy.yaml`'s `control_categories` mapping when absent; `runner/schema.py`'s `ticket` table gains the sentinel column `outcome_observed_at` and the once group over `final_head_sha`, `final_target_base_sha`, `final_pr_body_hash`, `merge_sha`, `required_checks_disposition`, `approval_disposition`, `outcome_actor_role`, and `outcome_observed_at` itself, settled together exactly once; `external_revision_count` is `mutable=True`; `closed_at` and `close_reason` keep the transition stamping T-A-04 built; the new artefact kind `pr_body_observed`; the observed-body write path copying a human-supplied file into `runs/tickets/<id>/` through T-A-01's write barrier and registering it through T-A-03's `runner/artefact_registry.py`; the observed-body locator read through `runner/deliverers/github.py` on the ticket's `github_pilot` or `github_scratch` route; `tag` rows of `event_kind = 'revision_after_approval'` (human) and `event_kind = 'control_defect'`, `fm_id = 'FM-25'` (mechanical); `incident_observation` rows of `record_kind` `production_coverage`, `production_incident_event`, `production_disposition`, `control_defect_event` with `control_category = 'approval_binding'`, and `control_disposition`; a change to `runner/stages/S4.py`'s existing `control_category = 'execution_boundary'` event write so it also derives severity from `factory/config/incident-policy.yaml`; `runner/tests/test_outcome_revision.py`; `runner/tests/test_outcome_body.py`; `runner/tests/test_outcome_final.py`; `runner/tests/test_outcome_mismatch.py`; `runner/tests/test_outcome_coverage.py`; `runner/tests/test_outcome_incident.py`; `runner/tests/test_outcome_no_poll.py`; `runner/tests/test_pilot_walk.py` (new, the pilot ticket's walk from its Jira key through the A and AB mechanisms to `pr_opened`, holding this ticket's own closing-run criterion, later extended by T-B-03, T-B-04, and T-B-05); `runner/tests/fixtures/outcome/`.

**Out:** the export of `revision`, `outcome`, `exposure`, `coverage`, `incident_event`, `disposition`, and `control_event` through `runner/stage_interface.py`, and the API-exclusivity, graduation-authority, and import-graph tests (T-B-05); the per-action script tests, actor and RACI-role recording, and the batch-verdict entry over the full R-H-4 action list (T-B-02); the graduation report's reading of the `incident_observation`, `tag`, and `approval_record` rows this ticket writes (T-B-03); `runner/tests/test_pilot_walk.py`'s further closing-run criteria for graduation, capacity, and the stage interface (T-B-03, T-B-04, T-B-05); S7's automated remote observation replacing this manual record (Later, R-H-11).

### Acceptance criteria

1. On a ticket whose `external_write` receipt reconciles into `pr_opened` with no unresolved `pr_outcome` item for that ticket, exactly one `queue_item` of `kind = 'pr_outcome'` is created with `blocked_on` null and `ref` the string `artefact:<id>` naming the reconciled receipt's artefact (R-H-11)
2. A ticket already carrying an unresolved `pr_outcome` item receives no second item on a further reconciled receipt entering `pr_opened`, so exactly one current `pr_outcome` item remains across create and update cycles (R-H-11)
3. `factory act <pr_outcome item> revision`, given review-ground text through `--note`, a failure-mode id through `--fm` and `--to implementing`, writes one `tag` row of `event_kind = 'revision_after_approval'` with a human-chosen `fm_id` and moves the ticket from `pr_opened` to `implementing` (R-H-11)
4. `factory act <pr_outcome item> revision` given a `--to` value outside `context`, `clarifying`, `planning`, and `implementing` is refused, and no `tag` row or transition is written (R-H-11)
5. After a `revision` is recorded, the ticket's prior review-approval subject no longer satisfies quorum for a new `pr_update`, since the ticket has left `pr_opened` and must revisit `plan_review` through `review` (R-H-11)
6. After a `revision` is recorded, the remote branch and pull request the outbox already opened remain unchanged until a fresh `pr_update` intent reconciles (R-H-11)
7. `factory act <pr_outcome item> outcome`, given `--body-file <path>` naming the observed PR body, copies that file into `runs/tickets/<id>/` and registers it as an artefact of `kind = 'pr_body_observed'`, setting `ticket.final_pr_body_hash` to that artefact's content hash (R-H-11)
8. `factory act <pr_outcome item> outcome`, given `--pr-identity <id> --observed-head-sha <sha>` as the immutable locator, performs one narrowly scoped read through `runner/deliverers/github.py` on the ticket's `github_pilot` or `github_scratch` route, and registers the body it reads as an artefact of `kind = 'pr_body_observed'` carrying the locator in its metadata (R-H-11)
9. `factory act <pr_outcome item> outcome`, given neither `--body-file` nor `--pr-identity`, leaves `ticket.final_pr_body_hash` null (R-H-11)
10. `factory act <pr_outcome item> outcome`, given `--result merged` with `--head-sha`, `--target-base-sha`, `--merge-sha`, `--checks` and `--observed-at`, sets `ticket.close_reason = 'merged'`, `closed_at`, `final_head_sha`, `final_target_base_sha`, `merge_sha`, and `required_checks_disposition`, and moves the ticket to `merged` (R-H-11)
11. `factory act <pr_outcome item> outcome`, given `--result abandoned` with `--head-sha`, `--target-base-sha`, `--checks` and `--observed-at`, sets `ticket.close_reason = 'abandoned'`, `closed_at`, `final_head_sha`, and `final_target_base_sha`, leaves `merge_sha` null, and moves the ticket to `abandoned` (R-H-11)
12. `factory act <pr_outcome item> outcome` records the acting canonical identity and sets `ticket.outcome_actor_role` to `outcome recorder` read from `owners.yaml`, and `ticket.outcome_observed_at` to the given observation time, on the write (R-H-11)
13. For each of the four `required_checks_disposition` values, `green`, `waived` with a reason, `red`, and `unknown`, `outcome` accepts a seeded value of that kind, and a `waived` value given with no reason is refused (R-H-11)
14. For each of a final head SHA, a final target-base SHA, and a final body hash that differs from `ticket.last_remote_head_sha`, the review tuple's recorded target-base SHA, and `ticket.last_pr_body_hash` respectively, and a `required_checks_disposition` of `red`, `outcome` still records the outcome rather than refusing the call (R-H-11)
15. In each of the four mismatch cases of criterion 14, `outcome` sets `ticket.approval_disposition = 'mismatched'` (R-H-11)
16. A `mismatched` `outcome` call appends one `tag` row of `event_kind = 'control_defect'`, `fm_id = 'FM-25'`, `tagged_by` mechanical, in the same transaction as the outcome (R-H-11)
17. A `mismatched` `outcome` call appends one `incident_observation` row of `record_kind = 'control_defect_event'`, `control_category = 'approval_binding'`, with severity read from `factory/config/incident-policy.yaml` (R-H-11)
18. A `mismatched` `outcome` call appends one `incident_observation` row of `record_kind = 'control_disposition'` naming that event root with `disposition = 'open'` (R-H-11)
19. A `waiver` or `policy_exception` tag recorded after a `mismatched` `approval_disposition` does not change the recorded value (R-H-11)
20. `outcome`, given a final head, target-base, and body hash that all equal the latest approved subject and a `required_checks_disposition` other than `red`, sets `ticket.approval_disposition = 'matched'` (R-H-11)
21. `outcome`, given no mismatch and at least one of the final head, target-base, or body hash unavailable, sets `ticket.approval_disposition = 'unknown'` (R-H-11)
22. `outcome` with disposition `abandoned` appends one `incident_observation` row of `record_kind = 'production_coverage'`, `status = 'not_deployed'` (R-H-11)
23. `outcome` with disposition `merged` appends one `incident_observation` row of `record_kind = 'production_coverage'`, `status = 'unknown'`, with no exposure fields (R-H-11)
24. `factory act --ticket <ticket-id> exposure`, given `--start` and `--source`, appends one `incident_observation` row of `record_kind = 'production_coverage'`, `status = 'unknown'`, superseding the ticket's earlier coverage row (R-H-11)
25. `factory act --ticket <ticket-id> coverage`, given `--through` as the `observed_through` time, appends one `incident_observation` row of `record_kind = 'production_coverage'`, `status = 'none_observed'`, superseding within the coverage series (R-H-11)
26. `coverage` recorded on a ticket whose current coverage row carries no exposure start and source is refused (R-H-11)
27. `factory act --ticket <ticket-id> incident_event`, given `--severity`, `--occurred-at`, `--note` and `--fm`, appends one `incident_observation` row of `record_kind = 'production_incident_event'` and its required `incident` tag with a human-chosen `fm_id`, and this root is never superseded (R-H-11)
28. `factory act --ticket <ticket-id> disposition`, given `--event` naming an event root, `--attribution`, `--disposition`, and `--remediation-ref` when `remediated`, appends one `incident_observation` row of `record_kind = 'production_disposition'` naming that root, records the acting identity's role `incident reviewer` from `owners.yaml`, and supersedes only an earlier `production_disposition` for the same root (R-H-11)
29. A `coverage` action naming a `production_incident_event` root as its target is refused (R-H-11)
30. An `exposure` or `coverage` action naming a coverage root of a different ticket is refused (R-H-11)
31. `factory/config/incident-policy.yaml` is created with `severity_levels` `sev1` through `sev4`, `control_categories` mapping each of the five control categories to a severity level with every category defaulting to `sev2`, `production_incident`, `attribution_values`, `disposition_values`, and a `remediation_rule` requiring at least one catalogue or rubric remediation ref on a `remediated` disposition (R-H-11)
32. `runner/stages/S4.py`'s `control_category = 'execution_boundary'` control-defect event write reads its severity from `factory/config/incident-policy.yaml` on a seeded control-defect event (R-H-11)
33. The `control_event` action on a seeded open item, called with no `--severity` flag, derives the severity from `factory/config/incident-policy.yaml`'s `control_categories` mapping for the event's control category (R-H-11)
34. An AST scan over `runner/` finds only `runner/outbox.py`, the `outcome` action's own locator read, and `runner/readers/github.py` importing the GitHub transport, and `runner/setup.py` writes no scheduler entry but the digest's (R-H-11)
35. On the closing run, the pilot ticket's eventual `merged` or `abandoned` disposition is entered manually with its actual final SHA and body hash, approval and required-check dispositions, and production-coverage status (R-H-11)

### Verification

`runner/tests/test_outcome_revision.py`: criteria 1, 2, 3, 4, 5, 6 against `runner/tests/fakes/github_transport.py`
`runner/tests/test_outcome_body.py`: criteria 7, 8, 9 against `runner/tests/fakes/github_transport.py`
`runner/tests/test_outcome_final.py`: criteria 10, 11, 12, 13
`runner/tests/test_outcome_mismatch.py`: criteria 14, 15, 16, 17, 18, 19, 20, 21
`runner/tests/test_outcome_coverage.py`: criteria 22, 23, 24, 25, 26, 29, 30
`runner/tests/test_outcome_incident.py`: criteria 27, 28, 31, 32, 33
`runner/tests/test_outcome_no_poll.py`: criterion 34
`runner/tests/fixtures/outcome/`: seeded ticket, receipt, locator, mismatch, coverage, and incident fixtures for criteria 1, 2, 7, 8, 9, 10, 11, 14 through 21, 24 through 30
`runner/tests/test_pilot_walk.py`: criterion 35, the closing-run criterion

## T-B-02: The list view complete: every human action through `factory act`, actor and RACI role, one record per slot, batch verdicts, guards on resume, governed artefacts opened, no credential shown

| | |
|---|---|
| Milestone | B |
| Blocks | 12 Queue item and decision; 14 Approval and quorum |
| HLD components | H2, C1, H4 |
| Depends on | T-A-06, T-A-07, T-A-09, T-A-12, T-A-14, T-A-16, T-A-17, T-A-19, T-A-20, T-A-23, T-A-27, T-A-29, T-A-32, T-A-33, T-A-34, T-B-01 |
| Rows covered | R-H-4 |

### Description

The local list view is the only channel a human uses to steer the factory, so this ticket completes it: every human action across the nine Initial `queue_item` kinds and the ticket-scoped outcome actions T-B-01 adds now runs through one `factory act` call surface. It adds three small mechanisms beyond what earlier tickets already built: the batch form of `factory act` on a `plan_approval` item, which accepts several `(rubric_line_id, subject_item_key, verdict, evidence)` tuples in one call and writes one `human_verdict` row per tuple through T-A-27's write path; the governed-artefact display verb `factory show --artefact <artefact id>`, which evaluates T-A-07's guard against the display route before printing the artefact; and the `override` action on the `question` item, correcting `question.consequential` or `question.hard_to_reverse` with a recorded reason, extending T-A-12's day-one mapping the way T-B-01 already extends it for `pr_outcome`. Every other action reuses the mechanism its building ticket already tests: eligibility at T-A-20, questions at T-A-23, plan and packet approvals at T-A-27, T-A-33, and T-A-34, pause, resume, stop, and escalation at T-A-17, base refresh and manifest migration at T-A-14 and T-A-19, waivers at T-A-32, export, import, and purge at T-A-16, and the outcome, exposure, coverage, incident, and control-event actions at T-B-01. It proves the acting canonical identity and RACI role are recorded on every resolution, that acting resumes only when quorum and other guards permit, and that inspection never silently advances the ticket. It also proves a governed artefact opens only under the display route's rule and that no response ever exposes a credential.

### Scope

**In:** the batch-verdict form of `factory act <plan_approval item> verdicts <file>` in `runner/queue.py`, taking a list of `(rubric_line_id, subject_item_key, verdict, evidence)` tuples and writing one `human_verdict` row per tuple through T-A-27's write path, resolving the item once every expected instance has a row; the governed-artefact display verb `factory show --artefact <artefact id>` added to `runner/cli.py`'s `show` command, evaluating T-A-07's guard against `trust-profile.yaml`'s `governed_export_display` route for the reader's `owners.yaml` role, writing one `guard_decision`, refusing a request outside the route, and flagging an artefact whose `retention_until` has passed as subject to deletion; `question.consequential` and `question.hard_to_reverse` in `runner/schema.py` gaining `mutable=True`, and `runner/queue.py`'s `question` entry in `ACTIONS_BY_KIND` gaining the `override` action, writing the corrected flag and a `tag` row of `event_kind = 'override'` naming the question with the recorded reason T-A-23's criterion 10 requires; `runner/tests/test_act_full_list.py`; `runner/tests/test_act_batch_verdicts.py`; `runner/tests/test_approval_slot.py`; `runner/tests/test_resolution_role.py`; `runner/tests/test_act_guards.py`; `runner/tests/test_governed_artefact_open.py`; `runner/tests/test_no_credential_exposure.py`; `runner/tests/fixtures/act_full_list/`.

**Out:** every action's own mechanism, already built by T-A-06, T-A-07, T-A-09, T-A-12, T-A-14, T-A-16, T-A-17, T-A-19, T-A-20, T-A-23, T-A-27, T-A-32, T-A-33, T-A-34, and T-B-01; the graduation approval's own quorum and report mechanism (T-B-03); the capacity-wait line at `intake` (T-B-04); the export of every action through `runner/stage_interface.py` (T-B-05).

### Acceptance criteria

1. `factory act <eligibility item>` with `granted`, `declined`, `edit_scrutiny`, and `override`, each shown with the ticket's data class, is accepted for each of the four actions (R-H-4)
2. `factory act <question item>` with `answer` and `accept_default` is accepted for each of the two actions (R-H-4)
3. `factory act <question item> override`, correcting `question.consequential` or `question.hard_to_reverse`, is accepted and writes the recorded reason T-A-23's criterion 10 requires (R-H-4)
4. `factory act <plan_approval item>` with `approve`, `redirect`, `send_back`, and `abandon` is accepted for each of the four actions, `approve` additionally carrying the batch's `human_verdict` rows per criterion 5, and `redirect`, `send_back`, and `abandon` recording no verdict row (R-H-4)
5. Verdicts on a `plan_approval` item entered as one batch through `factory act <plan_approval item> verdicts <file>`, given a list of tuples each naming `rubric_line_id`, `subject_item_key`, `verdict`, and `evidence`, write one `human_verdict` row per tuple, and resolve the item once every expected instance has a row (R-H-4)
6. `factory act <packet_approval item>` with `approve`, `request_changes`, and `send_back` is accepted for each of the three actions (R-H-4)
7. `factory act <red_check item>` with `send_back` and `abandon` is accepted for each of the two actions (R-H-4)
8. `factory act <escalation item>` with `resume`, `send_back`, and `abandon` is accepted for each of the three actions (R-H-4)
9. `factory act <manual_pause item>` with `resume`, `stop`, and `send_back` is accepted for each of the three actions (R-H-4)
10. `factory act <rubric_inspection item> close_inspection` is accepted (R-H-4)
11. `factory act <pr_outcome item>` with `revision` and `outcome` is accepted for each of the two actions (R-H-4)
12. `factory act --ticket <ticket-id>` with `exposure` and `coverage` is accepted for each of the two actions (R-H-4)
13. `factory act --ticket <ticket-id>` with `incident_event` and `disposition`, and `factory act <open item> control_event` on a seeded open item, is accepted for each of the three actions (R-H-4)
14. A policy-permitted blind-spot `waiver` issued through `factory act` on a `plan_approval` or `red_check` item is accepted, and one issued by an actor whose role the exact policy does not authorise is refused (R-H-4)
15. `factory refresh-base` and `factory migrate-manifest` are each accepted (R-H-4)
16. `factory pause`, `factory resume`, and `factory stop` are each accepted (R-H-4)
17. A `packet_defect` or `policy_exception` tag and its `resolves_tag_id`/`resolution_evidence_ref` resolution chain are each accepted through `factory tag` (R-H-4)
18. `factory abandon` and `factory purge` are each accepted (R-H-4)
19. A seeded second `approval_record` from an actor who already satisfies a `plan_approval` or `packet_approval` slot for the same subject is refused as a forked head, and only one immutable row per actor and required slot remains (R-H-4)
20. Every resolved `queue_item` carries the acting identity in `resolved_by` and the acting role read from `owners.yaml`, and on an approval the `approval_record`'s actor identity and role are recorded (R-H-4)
21. `factory act --ticket <ticket-id> disposition` records the acting identity's role `incident reviewer` from `owners.yaml` (R-H-4)
22. `factory act <escalation item> resume` on a seeded control-defect escalation is refused while its event has no `remediated` disposition or no passing gate run, and accepted once both exist (R-H-4)
23. `factory act <plan_approval item> approve` by one actor on a seeded two-slot reviewer set leaves the ticket in `plan_review` until the second slot's record exists (R-H-4)
24. `close_inspection` on a `rubric_inspection` item carries no state transition of its own (R-H-4)
25. `factory show --artefact <artefact id>` evaluates T-A-07's guard against `trust-profile.yaml`'s `governed_export_display` route for the reader's `owners.yaml` role and writes one `guard_decision`, and a request outside that route is refused (R-H-4)
26. `factory show --artefact <artefact id>` on an artefact whose `retention_until` has passed prints it flagged as subject to deletion (R-H-4)
27. No response, row, or log across every action and command of this ticket's list contains a credential value (R-H-4)

### Verification

`runner/tests/test_act_full_list.py`: criteria 1, 2, 3, 4, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18
`runner/tests/test_act_batch_verdicts.py`: criterion 5
`runner/tests/test_approval_slot.py`: criterion 19
`runner/tests/test_resolution_role.py`: criteria 20, 21
`runner/tests/test_act_guards.py`: criteria 22, 23, 24
`runner/tests/test_governed_artefact_open.py`: criteria 25, 26
`runner/tests/test_no_credential_exposure.py`: criterion 27
`runner/tests/fixtures/act_full_list/`: seeded queue-item, waiver, and tag fixtures across every kind for criteria 1 through 18

## T-B-03: Graduation: the canonical report over a window, the clause-by-clause gate over the record and the frozen baseline, the recorded owner approval binding report, thresholds and configuration hash

| | |
|---|---|
| Milestone | B |
| Blocks | 14 Approval and quorum; 17 Record |
| HLD components | H4, R5, R1, C1, F6 |
| Depends on | T-A-02, T-A-05, T-A-06, T-A-09, T-A-10, T-A-11, T-A-18, T-A-19, T-A-32, T-A-33, T-A-34, T-A-35, T-AB-10, T-AB-11, T-B-01 |
| Rows covered | R-O-13 |

### Description

Graduation is a recorded owner approval, never automatic, against a canonical report and a proposed configuration hash, so meeting the numbers only makes a human decision eligible. `runner/graduation.py` builds `factory graduate evaluate`, which runs as a `utility_run` of `kind = 'graduation'` and registers one `graduation_report` artefact holding the candidate window, the thresholds applied, the configuration hash evaluated, and every clause's verdict read from T-A-11's measure views, T-AB-10's frozen baseline, T-A-09's approval records, and T-A-33's tag catalogue. `factory graduate approve` writes one `approval_record` with `gate = 'graduation'` binding the report's content hash, the thresholds hash, and the proposed configuration hash, refused unless the report passed, the actor is the factory owner of `owners.yaml`, and the manifest hash still matches. The window excludes context measures from every clause and resets only after a severe attributable incident's remediation lands. It sits on T-A-02's canonical serialisation, T-A-05's run kinds, T-A-06's owner role, T-A-09's quorum shape, T-A-10's canonical hashing, T-A-11's views, T-A-18's `limits.yaml`, T-A-19's manifest hash, T-A-32's waiver validity, T-A-33's tag catalogue, T-A-34's packet-defect resolution chain, T-A-35's gate, T-AB-10's baseline, T-AB-11's adoption gate, and T-B-01's outcome, exposure, coverage and incident rows. Its nine tests run over a seeded window, never the pilot ticket, and its closing-run criterion evaluates the real gate and records it as not passed.

### Scope

**In:** `runner/graduation.py` (`factory graduate evaluate`, `factory graduate approve`, `factory graduate reject` in-process functions and their commands in `runner/cli.py`); artefact kind `graduation_report`; `utility_run.kind = 'graduation'`; a change to `runner/schema.py`'s `UTILITY_KINDS` tuple adding `graduation` and `gate`; `approval_record` rows with `gate = 'graduation'`; `factory/config/limits.yaml`'s `graduation` key (`window_min_outcomes`, `stage_min_first_attempts`, `stage_min_pass_share`, `baseline_min_comparable`, `severe_severities`); a change to `runner/gate.py` recording each of its runs as a `utility_run` of `kind = 'gate'` with its outcome and manifest hash; `runner/tests/test_graduation.py`; `runner/tests/test_graduation_window.py`; `runner/tests/test_graduation_clauses.py`; `runner/tests/fixtures/graduation/`; a change extending `runner/tests/test_pilot_walk.py` with the closing-run criterion.

**Out:** the parallel-limit raise that reads this ticket's approval (T-B-04); `runner/stage_interface.py`'s export of `graduate_evaluate` and `graduate_approve` (T-B-05); the manual outcome, exposure, coverage and incident rows the window reads (T-B-01).

### Acceptance criteria

1. `factory graduate evaluate` runs as a `utility_run` of `kind = 'graduation'` (R-O-13)
2. `factory graduate evaluate` registers one artefact of kind `graduation_report`, canonical JSON through `runner/canonical.py`, holding the window start, decision cutoff, and the manifest hashes it spans (R-O-13)
3. The `graduation_report` holds the thresholds applied with their hash and the configuration hash evaluated (R-O-13)
4. The `graduation_report` holds each clause's inputs read from T-A-11's views and T-AB-10's baseline views, and each clause's verdict, with `passed` true only when every clause passed (R-O-13)
5. `factory graduate approve <report artefact id> --config <path> --config-hash <hash>` writes one `approval_record` with `gate = 'graduation'`, `decision = 'approve'`, subject the canonical hash over the report's content hash, the thresholds hash, and the proposed configuration hash (R-O-13)
6. The approval's slot is the `factory owner` role of `owners.yaml`, carrying `authority_policy_hash` and the identity snapshot T-A-06 records (R-O-13)
7. A seeded `graduate approve` call over a report with `passed = false` is refused (R-O-13)
8. A seeded `graduate approve` call whose given configuration hash differs from the report's configuration hash is refused (R-O-13)
9. A seeded `graduate approve` call from an actor whose `owners.yaml` role is not factory owner is refused (R-O-13)
10. A seeded `graduate approve` call whose current manifest hash differs from the report's manifest hash is refused (R-O-13)
11. `factory graduate reject <report artefact id>` records one `approval_record` with `gate = 'graduation'`, `decision = 'reject'`, through the same `graduate_approve` function (R-O-13)
12. Two `approval_record` rows with `gate = 'graduation'` from one actor count once toward the gate's quorum (R-O-13)
13. The graduation gate's slot needs one approving `approval_record` from the factory owner (R-O-13)
14. The acceptance-gates clause reads the latest `utility_run` of `kind = 'gate'` under the current manifest hash and requires `outcome = 'pass'` (R-O-13)
15. The acceptance-gates clause requires at least one factory ticket with `factory_completed_at` set and a recorded `merged` or `abandoned` outcome (R-O-13)
16. `runner/gate.py` records each of its runs as a `utility_run` of `kind = 'gate'` with its outcome and manifest hash (R-O-13)
17. The candidate window is the set of factory tickets with `baseline = false`, `close_reason` `merged` or `abandoned`, and `closed_at` between the window start and the decision cutoff (R-O-13)
18. The window start is the latest of the previous graduation approval's decision time and the landing time of the last remediation of a severe attributable `production_incident_event` (R-O-13)
19. A seeded prior graduation approval excludes a ticket whose `closed_at` precedes the approval's decision time from the window, the fresh-window test (R-O-13)
20. A seeded severe attributable incident with a `remediated` disposition opens the window at that disposition's timestamp (R-O-13)
21. A seeded severe attributable incident with no `remediated` disposition leaves the window empty, the incident-reset test (R-O-13)
22. A seeded window with fewer than `window_min_outcomes` eligible tickets fails the report with `passed = false`, the window-size test (R-O-13)
23. A seeded merged ticket in the window with no recorded exposure fails the exposure/coverage clause (R-O-13)
24. A seeded merged ticket in the window with no explicit production coverage through the decision cutoff fails the exposure/coverage clause (R-O-13)
25. A seeded `sev1` or `sev2` `production_incident_event` in the window with disposition `attributable` fails the exposure/coverage clause (R-O-13)
26. A seeded production incident in the window with no reviewed attribution or disposition fails the exposure/coverage clause (R-O-13)
27. The stage clause reads `stage_reliability_view` per Initial stage `S0` to `S6`, and a seeded stage with fewer than `stage_min_first_attempts` first attempts fails it, the excluded-denominator test (R-O-13)
28. A seeded stage with a first-attempt pass share at or below `stage_min_pass_share` fails the stage clause, and excluded outcomes `blocked`, `refused`, `aborted_human`, child runs, utility runs, and non-`task` run kinds are reported separately (R-O-13)
29. The baseline clause compares mean post-plan revisions over the window's tickets from `v_revisions_per_ticket_by_fm` against the mean of `observed` and comparable `baseline_measure` rows (R-O-13)
30. A seeded window with fewer than `baseline_min_comparable` comparable `baseline_measure` values fails the baseline clause with reason `unavailable_baseline`, the unavailable-baseline test (R-O-13)
31. A seeded `approximate` or `unavailable` `baseline_measure` value standing in for a comparable one fails the baseline clause with reason `unavailable_baseline` (R-O-13)
32. A seeded `revision_after_approval` or `abandoned` tag in the window with no human-chosen `fm_id` fails the baseline clause (R-O-13)
33. A seeded `control_defect` tag in the window whose event's current `control_disposition` is `open`, for each of the five categories `data_boundary`, `execution_boundary`, `approval_binding`, `reviewer_enforcement`, and `audit_reconstruction`, fails the control-defect clause, the tagged-control test (R-O-13)
34. A seeded `check_result` with `blind_spot` on a blocking check in the window, neither resolved by a later passing result nor covered by a `waiver` valid at its subject's approval time, fails the blind-spot clause (R-O-13)
35. A seeded plan or review `approval_record` in the window with `decision_supported_without_transcript = false` and no `packet_defect` tag with `fm_id = 'FM-10'` resolved by a later tag with `resolves_tag_id` and `resolution_evidence_ref` fails the self-containedness clause, the FM-10 resolution test (R-O-13)
36. The report carries the context measures in a block labelled context (R-O-13)
37. A test asserts the `graduation_report`'s list of views each clause read equals `stage_reliability_view`, `v_revisions_per_ticket_by_fm`, `v_production_incidents_attributable`, `v_reconstruction_share_by_gate`, and the baseline views, naming none of `v_default_shown_share`, `v_default_accepted_share`, `v_plan_approved_no_redirect_share`, or any `v_ctx_` view (R-O-13)
38. A test that changes every seeded value of `v_default_shown_share`, `v_default_accepted_share`, `v_plan_approved_no_redirect_share`, and every seeded context measure, leaves every clause's verdict unchanged (R-O-13)
39. Every one of this ticket's nine verification tests runs over a seeded window of `ticket`, `stage_run`, `incident_observation`, `tag`, `waiver`, `approval_record`, and `baseline_measure` rows, and none reads the pilot ticket's own record as the gate's evidence (R-O-13)
40. On the closing run, `factory graduate evaluate` runs over the pilot ticket's record and the recorded `graduation_report` has `passed = false`, naming the failing clauses, with no `approval_record` of `gate = 'graduation'`, `decision = 'approve'` recorded against it (R-O-13)

### Verification

`runner/tests/test_graduation.py`: criteria 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16
`runner/tests/test_graduation_window.py`: criteria 17, 18, 19, 20, 21, 22
`runner/tests/test_graduation_clauses.py`: criteria 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39
`runner/tests/fixtures/graduation/`: seeded report, approval, window, incident, exposure, coverage, stage, baseline, control-defect, blind-spot, and self-containedness fixtures for criteria 4, 7 through 39
`runner/tests/test_pilot_walk.py`: criterion 40, the closing-run criterion, extended here

## T-B-04: Parallel ticket limit: capacity wait at `intake` shown from state and configuration, the raise bound to a graduation approval, unsigned edits and stale reports refused

| | |
|---|---|
| Milestone | B |
| Blocks | 9 Ticket and its state; 14 Approval and quorum |
| HLD components | C2, C1, H2, F6, H4 |
| Depends on | T-A-04, T-A-12, T-A-17, T-A-18, T-B-03 |
| Rows covered | R-I-10 |

### Description

The runner enforces the parallel ticket limit of section 8, one in the initial version, so a ticket beyond it waits at `intake` rather than starting a stage. `runner/capacity.py`'s `effective_parallel_limit()` reads `limits.yaml`'s `parallel_tickets` key and stays at one unless a current, unexpired `approval_record` with `gate = 'graduation'` binds a passing `graduation_report` and the exact hash of the file's current bytes, so editing the number alone is refused. `effective_parallel_limit()` returns the effective limit paired with a refusal reason, one of `unsigned_edit`, `stale_report`, or none, and `factory advance`, `factory queue`, and `factory show` read that reason from the same call. `factory advance` on a ticket in `intake` at the limit starts no run and writes no `queue_item`, while `factory queue` and `factory show` derive a capacity-wait line from state and configuration, labelled distinctly from a human wait or queue latency. It sits on T-A-04's state table, T-A-12's queue, T-A-17's status surface, T-A-18's `limits.yaml`, and T-B-03's graduation report and approval. Its capacity, unsigned-edit, stale-report and approved-change tests are seeded, and its closing-run criterion confirms the effective limit stays one and the pilot ticket never waited on capacity.

### Scope

**In:** `runner/capacity.py` (`effective_parallel_limit()` returning the effective limit paired with a refusal reason, one of `unsigned_edit`, `stale_report`, or none); `factory/config/limits.yaml`'s `parallel_tickets` key; a change to `runner/cli.py`'s `advance` boundary refusing a new `S0` run when the ticket count is at the effective limit and printing the refusal reason; a change to `factory queue` and `factory show` deriving the capacity-wait line from state, configuration, and the refusal reason; `runner/tests/test_capacity.py`; `runner/tests/fixtures/capacity/`; a change extending `runner/tests/test_pilot_walk.py` with the closing-run criterion.

**Out:** the graduation report and approval the raise reads (T-B-03); `runner/stage_interface.py`'s export of `advance` gated on this check (T-B-05).

### Acceptance criteria

1. `runner/capacity.py`'s `effective_parallel_limit()` reads `limits.yaml`'s `parallel_tickets` key (R-I-10)
2. On a seeded `limits.yaml` with `parallel_tickets = 1` and no graduation approval, `effective_parallel_limit()` returns `1` with reason `None` (R-I-10)
3. Given a seeded ticket count at the effective limit, `factory advance` on a ticket in `intake` starts no `S0` run, leaves the ticket in `intake` with `blocked_on` null, and writes no `queue_item` (R-I-10)
4. The counted states are `context`, `clarifying`, `planning`, `plan_review`, `implementing`, `checks`, `review`, and `escalated`; `intake`, `pr_opened`, and every terminal state are not counted (R-I-10)
5. `factory queue` derives a capacity-wait line for a ticket held at `intake` from its state and `limits.yaml`'s configured limit, labelled capacity wait (R-I-10)
6. `factory show` derives the same capacity-wait line, labelled capacity wait, distinct from a human wait or queue latency (R-I-10)
7. A seeded `limits.yaml` edit raising `parallel_tickets` above `1` with no `approval_record` binding any hash for the file makes `effective_parallel_limit()` return `1` with reason `unsigned_edit` (R-I-10)
8. A seeded current unexpired `approval_record` with `gate = 'graduation'`, `decision = 'approve'` binding a `graduation_report` with `passed = true`, whose bound configuration path is `factory/config/limits.yaml` and bound hash equals the sha256 of the file's current bytes, raises `effective_parallel_limit()` to the new `parallel_tickets` value (R-I-10)
9. A seeded `approval_record` binding a configuration hash that differs from the sha256 of `limits.yaml`'s current bytes makes `effective_parallel_limit()` return `1` with reason `stale_report` (R-I-10)
10. A seeded `approval_record` binding a `graduation_report` recorded under a manifest hash different from the current manifest hash makes `effective_parallel_limit()` return `1` with reason `stale_report` (R-I-10)
11. An expired `approval_record` with `gate = 'graduation'` confers no effective limit above `1` (R-I-10)
12. On the closing run, `effective_parallel_limit()` returns `1`, and the pilot ticket's record shows no capacity-wait line (R-I-10)

### Verification

`runner/tests/test_capacity.py`: criteria 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11
`runner/tests/fixtures/capacity/`: seeded ticket-count, unsigned-edit, stale-report, and approved-change fixtures for criteria 2, 3, 7, 8, 9, 10, 11
`runner/tests/test_pilot_walk.py`: criterion 12, the closing-run criterion, extended here

## T-B-05: Stage interface complete: `runner/stage_interface.py`, API exclusivity, graduation authority and import-graph tests; `fixture_from_export`; the pilot ticket's closing run to the definition of done

| | |
|---|---|
| Milestone | B |
| Blocks | 18 Stage interface; 7 Fixtures and evals |
| HLD components | C1, F7, F8, C7, E1, E2 |
| Depends on | T-A-16, T-A-35, T-AB-01, T-AB-04, T-AB-06, T-AB-07, T-AB-11, T-B-01, T-B-02, T-B-03, T-B-04 |
| Rows covered | R-I-1 |

### Description

The factory exposes one API and every client uses it, so `runner/stage_interface.py` re-exports every Initial operation by name, each a thin wrapper over the function its building ticket wrote, complete now that T-B-01's outcome actions and T-B-03's graduation operations exist. `runner/cli.py` imports nothing from `runner/` but `runner.stage_interface` and `runner.paths`, and three tests prove exclusivity: no module outside `runner/` writes the record directly, the literal `gate = 'graduation'` write lives only in `runner/graduation.py` reached through `stage_interface.graduate_approve`, and no module crosses the `runner/stages/` boundary except through the driver registry. `factory/scripts/tools/fixture_from_export` reads a governed export and writes the first redacted real fixture under the new `tickets/` eval kind, extending T-A-35's manifest test with the redaction review record's fields. The closing run, `runner/tests/test_pilot_walk.py`, drives the pilot ticket from its Jira key to a draft pull request through this one API, and its record restates the milestone's definition of done. It sits on T-A-16's export, T-A-35's gate, T-AB-01's escape suite, T-AB-04's pilot routes, T-AB-06's dispatch, T-AB-07's digest, T-AB-11's adoption gate, and T-B-01 through T-B-04's completed operations.

### Scope

**In:** `runner/stage_interface.py`; a change to `runner/cli.py` so it imports only `runner.stage_interface` and `runner.paths`; `factory/scripts/tools/fixture_from_export`; the `factory/evals/tickets/` eval kind; a change to T-A-35's manifest test for the `tickets/` kind's review-record fields; `runner/tests/test_stage_interface_complete.py`; `runner/tests/fixtures/stage_interface/`; `runner/tests/test_fixture_from_export.py`; `factory/evals/scripts/tools/fixture_from_export/`; a change extending `runner/tests/test_pilot_walk.py` with the closing-run criteria.

**Out:** the operations' own mechanisms, built by their respective A, AB and B tickets; the Later operations `sync_pr_head`, score, proposal, and benchmark (Later, R-I-1).

### Acceptance criteria

1. `runner/stage_interface.py` exports `advance`, `run_stage`, `pause`, `resume`, `stop`, `show`, `queue`, `act`, `migrate_manifest`, `refresh_base`, `tag`, `abandon`, `report`, `export`, `import_record`, `purge`, `digest`, `graduate_evaluate`, and `graduate_approve`, each a thin re-export of the function its building ticket wrote (R-I-1)
2. The record-writing actions `revision`, `outcome`, `exposure`, `coverage`, `incident_event`, `control_event`, and `disposition` reach `runner/stage_interface.py` only through `act` (R-I-1)
3. A test asserts `runner/stage_interface.py`'s export list equals the Initial operation list, omitting the Later operations `sync_pr_head`, score, proposal, and benchmark (R-I-1)
4. `runner/cli.py` imports `runner.stage_interface` and nothing else from `runner/` but `runner.paths`, and every `factory` verb maps to one exported name (R-I-1)
5. An AST scan over `runner/` finds `runner/adapters/` imported only by `runner/stages/` drivers reached through `stage_interface.run_stage` (R-I-1)
6. An AST scan over `factory/scripts/` finds no file importing `runner.record`, `runner.run_ledger`, `runner.outbox`, or `runner.adapters` (R-I-1)
7. An AST scan over `factory/scripts/` finds no SQL literal in a script is an `INSERT`, `UPDATE`, `DELETE`, `CREATE`, or `DROP` statement (R-I-1)
8. The literal `gate = 'graduation'` write exists in exactly one module, `runner/graduation.py`, reached only through `stage_interface.graduate_approve` (R-I-1)
9. A seeded `approval_record` of `gate = 'graduation'` from an identity whose `owners.yaml` role is not factory owner confers no authority on `runner/capacity.py`'s `effective_parallel_limit()` (R-I-1)
10. An AST scan finds `runner/cli.py` and `runner/stage_interface.py` import nothing under `runner/stages/` except the driver registry `stage_interface.run_stage` dispatches through (R-I-1)
11. An AST scan finds no module under `runner/stages/` importing `runner.cli` or `runner.stage_interface` (R-I-1)
12. An AST scan finds no module outside `runner/stages/` importing a `runner/stages/S<n>.py` name other than its driver entry point (R-I-1)
13. `factory/scripts/tools/fixture_from_export <export directory> <ticket id>` reads a T-A-16 export directory and writes `factory/evals/tickets/<ticket id>/` with `eval.yaml` naming `owner`, `target_failure_modes` as a list, and `redaction_review` with `reviewer_identity`, `reviewed_at`, `redacted_fields`, and `export_content_hash`, plus a `cases` list of `name`, `fixture`, and `expect`, plus `fixtures/export/` (R-I-1)
14. T-A-35's manifest test rejects an `eval.yaml` under the `tickets/` eval kind that is missing one of `redaction_review`'s four fields (R-I-1)
15. On the closing run, `runner/tests/test_pilot_walk.py` drives the pilot ticket from its Jira key to a draft pull request whose native GitHub view carries the diff of the approved narrative, every operation issued through `runner/stage_interface.py` (R-I-1)
16. On the closing run, the governed export of the pilot ticket shows every run, tool result used as evidence, boundary, human decision, and external write recorded (R-I-1)
17. On the closing run, the escape suite's `credentials` category re-runs against the pilot ticket's agent sandbox and finds no credential but the scoped runtime key (R-I-1)
18. On the closing run, the `external_write` row dispatching the pilot ticket's pull request commits no earlier than the quorum-completing `approval_record` (R-I-1)
19. On the closing run, T-AB-06's pre-dispatch recheck on the pilot ticket confirms S5's review subject and the PR-publication worker's referenced approved plan subject are the same fresh subjects (R-I-1)
20. On the closing run, `factory report`'s `get measures` operation over the pilot ticket's record distinguishes first-attempt reliability, queue latency, active attention, and unavailable evidence (R-I-1)
21. On the closing run, the redacted fixture directory `factory/evals/tickets/<pilot ticket id>/` exists, is listed in the manifest, and `python3 -m runner.gate` passes over it (R-I-1)

### Verification

`runner/tests/test_stage_interface_complete.py`: criteria 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12
`runner/tests/fixtures/stage_interface/`: seeded export-list and non-owner-approval fixtures for criteria 3, 9
`runner/tests/test_fixture_from_export.py`: criteria 13, 14
`factory/evals/scripts/tools/fixture_from_export/`: eval.yaml, fixtures for criterion 13
`runner/tests/test_pilot_walk.py`: criteria 15, 16, 17, 18, 19, 20, 21, extended here as the closing-run criteria

## T-B-06: Live connections: credentials by role in the host store, the Atlassian site, the pilot and scratch repositories on GitHub, the Slack post-tool binding and its scheduler entry, live routes in the trust profile, and `factory doctor`

| | |
|---|---|
| Milestone | B |
| Blocks | 24 External access; 6 Trust profile; 20 Sandbox |
| HLD components | C7, C5, G2, C1, E1, E2, E3, E4, E5 |
| Depends on | T-AB-01, T-AB-04, T-AB-05, T-AB-06, T-AB-07, T-AB-10, T-B-05 |
| Rows covered | none |
| Rows exercised | R-I-14, R-S0-1, R-S1-4, R-S6-3, R-H-3, R-O-6, R-I-1 |

### Description

Every outside connection the AB tickets built is real code behind empty configuration. `runner/credentials.py` reads the macOS Keychain, but no item exists under its service name. `runner/deliverers/github.py` and `runner/deliverers/slack.py` are complete clients behind `deliverer: stub` routes and null `project.yaml` keys. `runner/readers/atlassian.py` and the proxy's live relay are real transports pointed at the Atlassian API gateway with bearer authentication and site-style REST paths, a combination that resolves nowhere. The Cursor adapter fetches a runtime key nobody has stored, and the digest scheduler entry is written but never loaded. This ticket turns those into working connections without adding a mechanism the AB tickets did not already name. It moves the Atlassian transport to the site host with API-token authentication and makes the proxy's `atlassian_read` relay reuse that one transport. It gives the project entry in `project.yaml` its own `repository` and `publication_route`, so `github_pilot` resolves to a real repository the way `github_scratch` already does through `scratch_repository`. It flips the four stub routes that have real deliverers to `live` and re-approves the profile hash. And it adds `factory doctor`, a read-only readiness report over every credential role and live route, one status per line and never a value, so the dry run and every loudly skipping live test gate on one predicate. The owner-side steps no code can perform, storing each credential under its role, creating the scratch repository, approving the Slack app and discovering its post tool, loading the scheduler entry, are written once in `docs/runbooks/live-connections.md`. Everything this ticket adds runs against `runner/tests/fakes/` in the suite; the real connections are proven by T-B-07's dry run.

### Scope

**In:** `runner/doctor.py` (new: `check(...)` returning one finding per role in `credentials.ROLES` and per route at `deliverer: live`, each `ready`, `missing` naming the absent Keychain item or configuration key, or `unreachable` naming the probe's status; the read-only probes are the Atlassian `myself` resource, the GitHub repository resource's push permission for each configured repository, the Slack MCP server's `tools/list` for the configured post tool, `launchctl print` for the digest entry, and Keychain presence alone for `runtime_key`); `factory doctor` in `runner/cli.py`, reached through `runner/stage_interface.py` as a non-export name beside `show_artefact`, exit status non-zero when any finding is not `ready`; `runner/readers/atlassian.py`'s `HttpTransport` changed to Basic authentication over a Keychain item of the form `<account email>:<API token>` against the site host `sandbox.yaml` names; `runner/sandbox/proxy.py`'s `atlassian_read` relay changed to call `runner/readers/atlassian.py` for the route contract's read methods and to refuse every other method before any upstream call; `factory/config/sandbox.yaml`'s `atlassian_read` endpoint pointed at the pilot site host; `factory/config/project.yaml`'s project entry gaining `repository` (`name`, `remote`, `branch_prefix`) and `publication_route`, with `scratch_repository.remote` and every `digest` key filled by the owner; `runner/project.py` validating `publication_route` against the two GitHub route ids; `runner/outbox.py`'s `deliverer_for` resolving `github_pilot` live to the pinned project's `repository` and `github_scratch` live to `scratch_repository`, and its pull-request route read from `publication_route`; `runner/deliverers/github.py` taking the repository mapping it publishes to instead of reading `scratch_repository` itself; `runner/trust_profile.py`'s live-route set admitting `github_pilot`; `factory/config/trust-profile.yaml` with `github_pilot`, `github_scratch`, `slack_digest` and `baseline_read` at `deliverer: live` and the resulting profile hash approved in both governance slots; `docs/runbooks/live-connections.md`; `runner/tests/test_doctor.py`; `runner/tests/test_atlassian_live_transport.py`; `runner/tests/test_publication_route.py`; `runner/tests/fixtures/doctor/`.

**Out:** the dry run itself and every clause that needs a real service to answer (T-B-07); the pilot service's own project entry, recipes, security-check content, registry and vulnerability-feed endpoints, which arrive by the owner's reviewed pull request under the shapes T-AB-04, T-AB-08 and T-AB-09 fixed once that service is named; a live deliverer for `jira_feedback`, which no Initial operation dispatches through; any change to `runner/credentials.py`'s role set or Keychain service name; the trust profile's governance-approval mechanism, already built (T-AB-04).

### Acceptance criteria

1. `factory doctor` prints one line per role in `credentials.ROLES` reading `ready` or `missing`, from a Keychain lookup whose value it discards, and a seeded fake store returning a known value leaves that value absent from every line at every status (R-I-14)
2. `factory doctor` performs no hosted-model call: the `runtime_key` finding is Keychain presence alone (R-I-14)
3. For each route at `deliverer: live`, `factory doctor` reports `missing` naming the `project.yaml` or `sandbox.yaml` key that is still null, before it attempts any probe (R-S0-1, R-S6-3, R-H-3)
4. Given complete configuration, `factory doctor` performs one read-only probe per live route, the Atlassian `myself` resource, the GitHub repository resource for each configured repository reporting its push permission, and the Slack MCP server's `tools/list` reporting whether the configured post tool is listed, and a failed probe prints the status code and never the response body (R-S0-1, R-S6-3, R-H-3)
5. `factory doctor` reports whether the digest scheduler entry `runner/setup.py` writes is loaded, by `launchctl print` on its label (R-H-3)
6. `factory doctor` reports the trust profile's hash and whether each of its two governance slots holds an approval for that exact hash (R-S0-1)
7. `factory doctor` exits non-zero when any finding is not `ready`, and `runner/cli.py` reaches it through `runner/stage_interface.py` as a non-export name, leaving the export list T-B-05's exclusivity test pins unchanged (R-I-1)
8. `runner/readers/atlassian.py`'s `HttpTransport` sends Basic authentication built from a Keychain item of the form `<account email>:<API token>` to `/rest/api/2/` and `/wiki/rest/api/` paths on the site host `sandbox.yaml`'s `atlassian_read` endpoint names, and the item's value appears in no request URL, log, or raised error (R-S0-1)
9. An `atlassian_read` Keychain item with no `:` separator is refused before any request is sent (R-S0-1)
10. The proxy's `atlassian_read` relay performs an agent-side `read_issue` through the same `runner/readers/atlassian.py` transport the runner side uses, so one client serves S0 and S1 (R-S1-4)
11. A relay request on the `atlassian_read` route naming a method outside the reader's read methods is refused with a client-error status, and no upstream connection is opened (R-S1-4)
12. `project.yaml`'s project entry carries `repository` with `name`, `remote` and `branch_prefix`, and `publication_route`, and `runner/project.py` refuses a `publication_route` outside `github_pilot` and `github_scratch` (R-S6-3)
13. `runner/outbox.py` dispatches `pr_create` and `pr_update` through the pinned project's `publication_route`, `github_scratch` resolving to `scratch_repository` and `github_pilot` to the project's `repository`, and the route-literal test T-AB-04 left in `runner/tests/test_stub_walk.py` still finds no route id outside its one constant (R-S6-3)
14. A live GitHub route whose resolved repository has a null `remote`, or a `remote` that is not the canonical HTTPS URL of its `name`, fails closed before any credential fetch (R-S6-3)
15. A `pr_create` on `github_pilot` whose branch is outside the project repository's `branch_prefix` is refused, the same rule `github_scratch` applies under `scratch_repository.branch_prefix` (R-S6-3)
16. `trust-profile.yaml` carries `github_pilot`, `github_scratch`, `slack_digest` and `baseline_read` at `deliverer: live`, `runner/trust_profile.py` admits `github_pilot` among its live routes, and the profile's hash has one approval in each governance slot (R-S0-1, R-S6-3, R-H-3, R-O-6)
17. `factory/scripts/tools/baseline_import` builds its Atlassian transport from the same `sandbox.yaml` endpoint and Basic authentication S0 uses, and its GitHub transport from the `github_publish` role (R-O-6)
18. `docs/runbooks/live-connections.md` names, for every role in `credentials.ROLES`, the `security add-generic-password` command with `runner/credentials.py`'s service name and the role as the account, and for every live route the owner-side creation and approval steps, and a test asserts the runbook names every role and every live route (R-I-14)

### Verification

`runner/tests/test_doctor.py` with `runner/tests/fixtures/doctor/`: criteria 1, 2, 3, 4, 5, 6, 7, 18 against a fake Keychain lookup, a fake `launchctl`, `runner/tests/fakes/atlassian_transport.py`, `runner/tests/fakes/github_transport.py` and `runner/tests/fakes/slack_transport.py`
`runner/tests/test_atlassian_live_transport.py`: criteria 8, 9, 10, 11 against a fake `urlopen`
`runner/tests/test_publication_route.py`: criteria 12, 13, 14, 15, 16, 17 against `runner/tests/fakes/github_transport.py`

## T-B-07: The dry run on the pilot host: readiness, the escape suite, the baseline read, the dry-run ticket to `clarifying`, then the rehearsal ticket through every stage to a draft pull request on the scratch repository, the digest, the outcome by hand, the gate not passed, and the record-reading assertions the closing run reuses

| | |
|---|---|
| Milestone | B |
| Blocks | 24 External access; 7 Fixtures and evals; 18 Stage interface |
| HLD components | C1, C7, G1, G2, F8, E1, E2, E3, E4, E5 |
| Depends on | T-AB-02, T-AB-11, T-B-01, T-B-02, T-B-03, T-B-04, T-B-05, T-B-06 |
| Rows covered | none |
| Rows exercised | R-I-14, R-T-2, R-O-6, R-S0-1, R-S1-4, R-F-14, R-S6-3, R-H-3, R-H-11, R-O-13, R-I-10, R-I-1 |

### Description

Every "on the pilot host", "on the dry-run ticket" and "on the closing run" clause of the AB and B tickets was built as a loudly skipping test, because no real Jira key, repository or credential existed when its ticket was built. This ticket runs them, in two legs on the pilot host, over T-B-06's live connections and with the fixture project as the pinned source, pushed by the owner to the scratch repository so it has a real remote and a real history. Leg one is the AB exit test's dry-run ticket: opened from one real Jira key, read through the Atlassian site at S0, its archaeology resolved through the proxy's relay at S1, passed into `clarifying` and abandoned there with no later stage run. Leg two rehearses B's definition of done on a second ticket from the same key: every stage with real invocations under the real runtime key, every human action through `factory act`, one draft pull request created and then updated on the scratch repository's throwaway branch, the digest posted once, the outcome entered by hand after the owner closes that pull request, the real gate evaluated and recorded as not passed, the export complete, and the redacted fixture produced into a temporary root without being committed. Leg one and the escape suite are scripted. Leg two is a hand-driven procedure in `docs/runbooks/dry-run.md`, each step naming its command and the record row it must leave, and `runner/tests/test_dry_run.py` asserts those rows afterwards from the recorded database. That record-reading shape is what `runner/tests/test_pilot_walk.py`'s live test takes from here on, pointed at the pilot ticket's record by the same two inputs, so T-B-05's closing run reuses these assertions unchanged. The pilot ticket's closing run is still T-B-05's, executed after this ticket passes.

### Scope

**In:** `docs/runbooks/dry-run.md` (the owner-side preparation: the fixture project's materialised checkout pushed to the scratch repository's target branch with one commit whose message names the dry-run issue key, the dry-run issue created by hand in the admitted Jira project carrying the fields `ticket-types.yaml` names; then leg two step by step, each step its `factory` command and the row it leaves); `runner/tests/test_dry_run.py` (new: leg one scripted through `runner/stage_interface.py` against the live services, and the leg-two assertions read from the record at the database and ticket id the `SOFT_FACTORY_DRY_RUN_DB` and `SOFT_FACTORY_DRY_RUN_TICKET` inputs name, every test skipping loudly with the `factory doctor` finding that would clear it); `SOFT_FACTORY_DRY_RUN_JIRA_KEY` kept as the one key both legs open their ticket from; a change to the live tests of `runner/tests/test_s0.py`, `runner/tests/test_s1_archaeology.py` and `runner/tests/test_baseline_import.py` so they gate on `factory doctor`'s findings instead of their own partial checks; a change to `runner/tests/test_pilot_walk.py` replacing its unconditional skip with `test_dry_run.py`'s record-reading assertions over the pilot ticket's record; `runs/dry-run/<date>/` as the kept copy of the dry run's database, per-run directories and doctor output.

**Out:** the pilot ticket's own closing run and its redacted fixture under `factory/evals/tickets/` (T-B-05's closing-run criteria); the pilot service's project entry and recipes (owner content under the shapes T-AB-04, T-AB-08 and T-AB-09 fixed); any change to a stage, deliverer, reader or the doctor (T-B-06 and earlier).

### Acceptance criteria

1. `factory doctor` on the pilot host reports every credential role and every live route `ready` before either leg starts, and its output is kept under `runs/dry-run/<date>/` (R-I-14)
2. The escape suite passes on the pilot host over every category `factory/evals/sandbox/escape/eval.yaml` names, the unregistered-file probe among them (R-I-14, R-T-2)
3. `baseline_import` reads the admitted Jira project's completed tickets and the scratch repository's pull-request history from the live services, checks the retrospective and supplemental endpoints as equivalent, records `unavailable` for every measure the history cannot supply, freezes once, and a second run against the frozen cohort is refused (R-O-6)
4. Leg one: a ticket opened from the real dry-run key and granted eligibility has S0 read it through the Atlassian site, write one classified `ticket_source` artefact, and pin `trust_profile_hash` and `trust_approval_set_hash` to the live profile's hash and its approval set (R-S0-1)
5. Leg one: S1 runs `archaeology` in its sandbox on the pinned checkout, resolves the issue the seeded commit names through the proxy's `atlassian_read` relay, records the classification in the brief's history section, and the ticket moves to `clarifying` (R-S1-4)
6. Leg one: `factory abandon` at `clarifying` writes the `abandoned` tag and the `not_deployed` coverage row, and the ticket's record holds no `stage_run` for S2 or any later stage (R-S1-4)
7. Leg two: a second ticket from the same key walks S0 to S6 with real invocations under the real runtime key, every stage's output passing its rubric's script lines, every semantic verdict, question answer, plan approval and packet approval recorded through `factory act`, and every operation issued through `runner/stage_interface.py` (R-I-1)
8. Leg two: the escape suite's `credentials` category re-runs against the leg-two ticket's real agent sandbox and finds no credential but the scoped runtime key (R-I-14, R-I-1)
9. `python3 -m runner.gate` on the pilot host runs every recipe the pinned project names at its current base in a base and a head copy, records one result per recipe, disposes of both copies, and passes (R-F-14)
10. Leg two: the outbox creates one draft pull request on the scratch repository's throwaway branch, its `external_write` row committing no earlier than the quorum-completing `approval_record`, and no branch reaches the remote before that record exists (R-S6-3, R-I-1)
11. Leg two: T-AB-06's pre-dispatch recheck records S5's review subject and the publication worker's approved plan subject as the same fresh subjects (R-I-1)
12. Leg two: the pull request's native GitHub view carries the diff of the approved narrative, and the receipt's body hash equals the approved `pr_body` hash (R-I-1)
13. Leg two: `factory act <pr_outcome item> revision` leaves the remote branch and pull request unchanged, and after reapproval the outbox updates that same pull request rather than opening a second (R-S6-3, R-H-11)
14. `factory digest` posts once to the configured channel with a receipt carrying the message identity, a second run in the same cadence slot creates no intent, and a `launchctl kickstart` of the loaded scheduler entry records one `digest` utility run (R-H-3)
15. Leg two: after the owner closes the pull request by hand, `factory act <pr_outcome item> outcome --result abandoned` with the real final SHAs, `--pr-identity` and `--observed-head-sha` reads the body through the live route, and the ticket's outcome fields, approval disposition and coverage row are set from what the remote shows (R-H-11)
16. `factory graduate evaluate` over the dry run's record registers a `graduation_report` with `passed = false` naming the failing clauses, and no `approval_record` of `gate = 'graduation'`, `decision = 'approve'` exists (R-O-13)
17. `effective_parallel_limit()` returns `1` throughout both legs, and neither ticket's record shows a capacity-wait line (R-I-10)
18. The governed export of the leg-two ticket shows every run, tool result used as evidence, boundary, human decision and external write, and `factory report`'s measures over it distinguish first-attempt reliability, queue latency, active attention and unavailable evidence (R-I-1)
19. `fixture_from_export` over that export, into a temporary root, writes a `tickets/` eval directory `python3 -m runner.gate` passes over, and nothing is committed under `factory/evals/tickets/` for either dry-run ticket (R-I-1)
20. No credential value appears in any row, artefact, log, doctor line or test output across both legs, checked against each Keychain value the assertions fetch once and discard (R-I-14)
21. `runner/tests/test_dry_run.py` and the live tests of `test_s0.py`, `test_s1_archaeology.py`, `test_baseline_import.py` and `test_pilot_walk.py` skip loudly on a host where `factory doctor` reports a needed role or route not `ready`, each skip reason naming that finding (R-I-14)

### Verification

`runner/tests/test_dry_run.py`: criteria 1, 2, 3, 4, 5, 6 run live on the pilot host; criteria 7 through 20 asserted over the recorded database and ticket `SOFT_FACTORY_DRY_RUN_DB` and `SOFT_FACTORY_DRY_RUN_TICKET` name after the runbook's leg two; criterion 21 in the routine suite with the doctor's findings faked
`docs/runbooks/dry-run.md`: the leg-two procedure whose steps produce the rows criteria 7 through 19 assert
`runs/dry-run/<date>/`: the kept record, per-run directories and doctor output of the run the criteria were checked on
