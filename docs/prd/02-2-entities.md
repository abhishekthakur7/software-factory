# 2.2 Entities

Part of the [Software Factory PRD](prd.md). The index holds the version, the reading rules, and the map from section numbers to files.

Field lists are the minimum. Additional fields are allowed; removals are not. Content-addressed record types use versioned canonical JSON: UTF-8 strings, lexicographically ordered object keys, schema-defined array ordering, and SHA-256. Subject hashes exclude database ids, the hash field itself, and audit-only creation timestamps; they include every field named as a binding. Approval-record hashes additionally include actor, slot, decision, authority evidence, decision time and expiry. Changing the serialization version changes the subject.

**`ticket`**. One row per factory candidate admitted to `intake`, including candidates later rejected at S0 or by a discovered pilot exclusion, plus one minimal provenance row per selected baseline ticket. A baseline row carries source, service, type, derived tier and `baseline = true`; factory bindings, state and lifecycle timestamps are null and it never enters the state machine.

| Field | Meaning |
|---|---|
| `id` | Factory identifier |
| `source_kind`, `source_ref` | `jira` plus the issue key, `confluence` plus the page id, or Later `maintenance` plus the enrolment id (R-S0-9) |
| `title` | From the source |
| `data_class` | Owner-confirmed class from `trust-profile.yaml`; unknown is ineligible |
| `trust_profile_hash`, `trust_approval_set_hash` | Exact current profile and satisfying governance approvals pinned at eligibility. Expiry blocks use until fresh quorum approves the same subject; a profile or authority-policy change creates a new subject and requires the corresponding reviewed configuration migration |
| `service` | Target service, from the configured Jira field (section 8) |
| `service_tier` | From the service tier list (section 8), looked up at S0 |
| `ticket_type` | One of the types in section 8 |
| `factory_manifest_hash` | Manifest pinned at eligibility for the lifetime of the ticket; an explicit human-approved migration changes it, invalidates S1 onward, and returns to `context` |
| `tier_provisional`, `tier_final` | Light, Standard, or Heavy (D11) |
| `tier_override_by`, `tier_override_at`, `tier_override_reason` | Set only by a human, with an `override` tag |
| `scrutiny_requested` | Free text from S0: what the reviewer should look hardest at and what they may take on the evidence |
| `required_approvers` | Display summary derived from the current planned `reviewer_set` until an effective set exists, then from the effective set; never an approval gate input. Sensitive work is excluded from Initial; after graduation the immutable reviewer slots and approval records enforce the distinct-owner decision, while GitHub enforcement is Later |
| `state` | See 2.3 |
| `blocked_on` | Null, or the single `queue_item` id for the current blocking decision or question round; a question-round item references its versioned `question_set` so several blocking questions remain one resumable boundary |
| `pause_requested`, `paused_at` | Human-requested stable-boundary pause; independent of the stage state (R-H-13) |
| `base_sha`, `target_base_sha`, `branch`, `worktree_path`, `head_sha` | The commit from which the current ticket branch is based, the current fetched head of the configured target branch, the ticket branch, its worktree, and the branch head. A human refresh creates a new tuple and invalidates downstream evidence (R-S5-12) |
| `pr_url`, `pr_identity`, `last_remote_head_sha`, `last_pr_body_hash` | Set from reconciled `pr_create`/`pr_update` receipts after S6 approval and retained across revision cycles |
| `baseline` | True for the pre-factory tickets of R-O-6; never mixed with factory tickets |
| `opened_at`, `factory_completed_at`, `closed_at`, `close_reason` | `factory_completed_at` is set at `pr_opened`; `closed_at` only when the human records `merged`, `abandoned`, or `rejected`, so factory cycle time and external outcome are not conflated |
| `final_head_sha`, `final_target_base_sha`, `final_pr_body_hash`, `merge_sha`, `required_checks_disposition`, `approval_disposition`, `external_revision_count` | Initial manual outcome evidence from R-H-11. The body hash comes from a governed observed-body snapshot or immutable remote locator. `approval_disposition` is `matched`, `mismatched`, or `unknown`; S7 automates observation Later |
| `close_survey` | Later: optional one-question answer at close (charter section 8, FM-09) |

**`stage_run`**. One row per ticket-stage execution. This is the C5 ledger at execution grain. At S4 there is one row per plan-task execution; `attempt` counts every start and `verification_attempt` counts only executions that reach task validation. S4 also holds the runner-driven runs of R-S4-9, distinguished by `run_kind`. S5 has one run per complete check pass. S6 has one run per packet/PR-body assembly and local validation cycle; human approvals are separate records and outbox dispatch/reconciliation lives only on `external_write`, so delivery retries do not distort stage reliability.

| Field | Meaning |
|---|---|
| `id`, `ticket_id`, `stage`, `plan_item`, `plan_tuple_id`, `attempt`, `verification_attempt` | `ticket_id` is non-null and `stage` is S0 to S7. `plan_item` and `verification_attempt` are null outside S4. `attempt` increments on every fresh execution of the same stage or S4 task; `verification_attempt` is 1 to 3 per approved plan-item version and is null when execution never reached validation |
| `run_kind` | `task` everywhere except the S4 cases: `task` for a plan-task execution with an agent; `fix_round` for an R-S4-9 agent run against failing machine checks; `validation_only` for the runner's script-only execution of every task's validation recipes after a fix round. Only `task` rows carry `plan_item` and `verification_attempt`; the other kinds are excluded from the first-attempt measure and reported separately (`base_advance` is Later, R-S5-14) |
| `parent_run_id` | Null except for a sub-invocation a stage makes, such as an R-S2-3 restatement: a child row carries its own runtime, model, tokens, cost, and wall clock, counts against its parent's budget (R-I-6), and is excluded from the first-attempt measure |
| `tier` | The tier in force when the run started |
| `runtime`, `runtime_version`, `adapter_version`, `model_requested`, `model_resolved` | Exact package/build identities and requested and resolved hosted-model identifiers, recorded verbatim (C4, D5). Null for a script-only stage; resolution never silently selects another model |
| `agent_ref`, `skill_ref`, `rubric_ref` | Versioned file identities used, with their content hashes (C6). Null for a script-only stage |
| `manifest_hash`, `trust_profile_hash`, `trust_approval_set_hash` | The factory and governance versions in force for this run; every measure can be sliced by manifest (charter section 8) |
| `tool_allowlist` | The MCP servers and tools attached for this run (C1) |
| `sandbox_digest`, `toolchain_digest`, `recipe_set_hash` | Execution-boundary identities from R-I-14 and R-I-15 |
| `inputs`, `outputs` | Artefact ids read and written |
| `reasoning_summary` | Agent-written, under the section 8 limit, stored verbatim. Null for a script-only stage |
| `tokens_in`, `tokens_out`, `cost`, `currency`, `cost_basis`, `pricing_table_hash`, `cost_settled_at`, `wall_clock_seconds` | Token and duration values are copied from the runtime's final result or are null. A cost the runtime settles after the run ends is written once when it arrives, with `cost_settled_at`; until then the cost fields hold a price-table estimate where that rule applies, otherwise null with `cost_basis` `unavailable`. `cost_basis` is `provider_settled`, `runtime_estimate`, `price_table_estimate`, or `unavailable`; currency is required for a non-null cost, and `pricing_table_hash` is required only for a price-table estimate. Estimates never fill missing tokens, duration, or per-tool-call usage and are never presented as settled cost |
| `outcome`, `failure_kind` | Outcome is `pass`, `fail`, `infrastructure_failure`, `sandbox_violation`, `blocked`, `aborted_budget`, `aborted_human`, or `refused`. `failure_kind` is nullable and classifies `implementation`, `verification`, `infrastructure`, `sandbox_integrity`, `structural`, `expired_lease`, or `stale_binding`. Escalation is a ticket state and queue event, never a second run outcome |
| `started_at`, `heartbeat_at`, `lease_expires_at`, `ended_at` | The lease lets restart distinguish a live process from an orphan without process-id reuse assumptions |

**`tool_call`**. One row per tool call inside a stage run. Ledger at call grain.

| Field | Meaning |
|---|---|
| `id`, `stage_run_id`, `seq`, `guard_decision_id` | The guard decision authorising the governed arguments and destination is required for any content-bearing call |
| `tool`, `tool_version`, `args_digest`, `result_digest` | Exact tool identity and digests. Credentials are stripped before digesting |
| `args_artefact`, `result_artefact` | Governed, redacted artefacts whenever arguments or results influence a later output; null only when the data is derivable from another registered input or declared unavailable |
| `duration_ms`, `tokens` | Where the runtime exposes them; null otherwise, never estimated |
| `result_bytes`, `inline` | Size of the governed result, and whether it was returned inline to the agent context or only as a `tool_result` artefact path with an excerpt (R-I-17) |

**`artefact`**. One row per file an agent or script produces.

| Field | Meaning |
|---|---|
| `id`, `ticket_id`, `stage_run_id`, `guard_decision_id` | The guard decision is required for content-bearing artefacts; safe metadata-only records name the policy decision that classified them so |
| `kind` | `ticket_source` (the permitted, redacted source fields written at S0), `brief`, `criteria`, `question_set`, `risk_map`, `plan`, `handoff`, `failure_history`, `check_evidence`, `tool_input`, `tool_result`, `packet`, `pr_body`, `pr_checks_summary` (Later), `export` (a directory) |
| `version`, `path`, `hash`, `created_at` | |
| `data_class`, `redaction_state`, `retention_until` | Governance metadata from R-T-9 |
| `supersedes` | Previous version's id, or null |

**`queue_item`**. One row per item that needs a human. The queue is the only channel to the human (D17) and every wait measure is computed from this table.

| Field | Meaning |
|---|---|
| `id`, `ticket_id`, `stage`, `tier` | |
| `kind` | `question`, `eligibility`, `plan_approval`, `packet_approval`, `red_check`, `escalation`, `manual_pause`, `pr_outcome`, `rubric_inspection`; Later `bloat_signal`, `close_survey` |
| `ref` | The `question_set`, `question`, `artefact`, `check_result`, or `stage_run` the item is about; blocking questions in one round share one item through `question_set` |
| `queued_at`, `resolved_at`, `resolved_by` | Queue latency is `resolved_at - queued_at`; it is not active attention. `resolved_by` is UI history, not approval authority |
| `action`, `note` | What the human did: answer, accept default, approve, redirect, request changes, send back (with the target stage), resume, override, abandon, decide eligibility, edit scrutiny, close inspection, stop; free text where the action requires it |
| `approval_subject_hash`, `reviewer_set_id` | Approval records join by subject and slot. Approval advances only when derived quorum for this exact subject passes; reject, redirect, request-changes, or another governed backward action resolves the item through its specified transition |
| `active_attention_bucket` | Optional coarse bucket for non-approval actions. Plan/final-review attention is authoritative on each immutable `approval_record`. Values: `under_2m`, `2_to_5m`, `5_to_15m`, `15_to_30m`, `over_30m`, or `unknown`; never inferred from editor activity |

**`question`**. One row per question that passed the gate (charter section 6).

| Field | Meaning |
|---|---|
| `id`, `ticket_id`, `stage`, `round` | Round starts at 1 |
| `rank` | Position in its round after ranking |
| `affects` | The eligibility condition, brief fact, criterion, plan item, or human decision the answer changes |
| `reasoning` | Why the agent cannot decide, including the sources it tried |
| `options` | Two to four, stored as a list; each option is a label and a one-sentence consequence (R-S2-14) |
| `default_option` | Index into options, or null when both `consequential` and `hard_to_reverse` are true, or when the sensitive-decision rule applies (D15) |
| `consequential`, `hard_to_reverse`, `blocking` | Booleans set by the agent, overridable by the human. A blocking question holds the ticket (R-S2-12); reversibility is independent of blocking |
| `rank_inputs` | The impact and decision-uncertainty estimates used to rank, stored so the ranking can be calibrated later |
| `raised_by_answer` | Answer id for a follow-up question, else null |
| `state` | `open`, `answered`, `default_accepted`, `assumption_accepted`; the last is set only by the S3 reviewer and names the resulting assumption row |

**`answer`**. One row per human response.

| Field | Meaning |
|---|---|
| `id`, `question_id`, `question_version_hash`, `resolution_kind`, `chosen_option`, `free_text`, `answered_by`, `answered_at` | `resolution_kind` is `answered`, `default_accepted`, or `assumption_accepted` and immutably records the event even if a later answer supersedes it. `chosen_option` may be "none of these", which requires `free_text` |

**`assumption`**. Append-only log (charter section 6).

| Field | Meaning |
|---|---|
| `id`, `ticket_id`, `text`, `origin` | `text` is required for an assertion and null for a withdrawal. Origin is a question id when the assumption came from an accepted default, else `agent` |
| `supersedes`, `withdrawn`, `withdrawal_reason` | Prior assumption id, or null. Replacing or withdrawing an assumption appends a row naming the prior row; prior rows are never updated. `withdrawn = true` requires null `text` and a non-empty reason. An assumption is current when no later row supersedes it, so active/superseded is derived rather than stored |
| `created_at` | |

**`deviation`**. One row per deviation from the approved plan, written by the trusted runner from the S4 hand-back; the canonical digest of the ticket's deviation rows at a hand-back is the deviation digest bound at S5 and shown at S6 before the diff.

| Field | Meaning |
|---|---|
| `id`, `ticket_id`, `stage_run_id`, `plan_item` | |
| `plan_said`, `agent_did`, `why` | For a base-test change or removal, `why` names the `AC-n` criterion or the `no_behaviour_change` task from the plan's test strategy row (R-S4-10) |
| `kind` | `judgment` or `error` |
| `contract_change` | Boolean (FM-15) |

**`generated_test`**. Append-only records use `record_kind`. An `identity` row has `id`, ticket id, originating S4 run id, initial path and content hash, generating actor kind, and creation time. A `decision` row has its own id, the identity-row id, deciding review subject, `kept` or `removed`, final path/hash when kept, reason, actor and time; a later review subject appends a new decision rather than editing one. Tests not introduced by the factory create no identity row and never enter the denominator.

**`failure_history`**. The artefact an S4 escalation attaches (R-S4-6). Fixed content: the approved plan-item version with typed recipes and expected results; per execution, its `attempt`, optional `verification_attempt`, outcome/failure kind, files changed, governed verbatim validation output, agent diagnosis and next change, reasoning summary, head SHA, tokens and wall clock; the consumed and remaining verification quota; infrastructure retries; and dependent-task state. It is written so the human can act from the escalation item alone (R-H-8).

**`check_result`**. One row per deterministic or advisory check.

| Field | Meaning |
|---|---|
| `id`, `stage_run_id`, `check_name`, `check_tier`, `evidence_tuple_id`, `plan_tuple_id` | `check_tier` is `blocking` or `advisory`. The pre-S4 freshness result binds a plan tuple. Every S5 result after successful preflight binds one review tuple. If that tuple cannot be created, exactly one non-waivable `review_tuple_preflight` result may have a null evidence tuple, must bind the approved plan tuple, and may be only `fail` or `blind_spot`; its evidence records every observed or unavailable candidate component. Unrun checks are not fabricated as blind spots |
| `source` | `factory`; Later `github_actions` |
| `result` | For factory checks: `pass`, `fail`, or `blind_spot`. For Later GitHub checks: null while `external_status` is `queued` or `in_progress`, `pass` or `fail` at a terminal status; required `cancelled` and `skipped` map to `fail`, never green |
| `external_status`, `external_run_identity`, `observed_head_sha`, `observed_target_base_sha`, `observed_merge_group_sha` | Null for factory checks. Later GitHub checks use `queued`, `in_progress`, `pass`, `fail`, `cancelled`, or `skipped` plus the immutable external run and observed commit identities; a merge-group SHA is observation context, not a substitute for its target-base parent |
| `evidence_artefact` | Artefact id holding the full output |
| `summary` | One line for the packet, naming the likely catalogue id where the check has one |
| `canonical_serialization_version`, `content_hash` | The content hash includes check identity, binding, result/external status, evidence hash and summary; changing a verdict therefore changes the review-approval subject |

**`tag`**. The evidence process (D21).

| Field | Meaning |
|---|---|
| `id`, `ticket_id`, `event_kind` | `revision_after_approval`, `incident`, `control_defect`, `override`, `abandoned`, `escalation`, `stale_index`, `send_back`, `packet_defect`, `policy_exception` |
| `fm_id` | A catalogue id, required |
| `ref` | The exact stage run, question/version, artefact, queue item, approval record, incident/control event, or external incident the tag points at. An FM-10 decision defect points to the affected approval record, not merely its shared queue item |
| `severity`, `note`, `tagged_by`, `tagged_at` | Severity is `sev1` to `sev4` and required for incident, control-defect, and policy-exception tags. `tagged_by` is a human except `stale_index`, escalation, and mechanically detected control defects. For `send_back` the note carries the ground from `rubrics/checklists/send-back-grounds.md`. A policy-exception tag must reference a valid waiver and grants no authority itself |
| `resolves_tag_id`, `resolution_evidence_ref` | Optional prior defect tag and immutable evidence that resolves it. Defect status is derived; an occurrence row is never overwritten or made to disappear |

**`incident_observation`**. Append-only records separate occurrence from review and coverage. Common fields are `id`, optional ticket id, factory-manifest hash, record kind (`production_incident_event`, `production_disposition`, `production_coverage`, `control_defect_event`, `control_disposition`), optional control category (`data_boundary`, `execution_boundary`, `approval_binding`, `reviewer_enforcement`, `audit_reconstruction`), recorder identity/role, timestamp, and immutable evidence refs. An event is an immutable root with its required `incident` or `control_defect` tag, severity under pinned `incident-policy.yaml`, occurrence time, and note; it is never superseded. A disposition names its event root, attribution (`attributable`, `not_attributable`, `undetermined`), disposition (`open`, `remediated`, `reviewed_no_change`), catalogue/rubric remediation refs, and may supersede only an earlier disposition for that root. A production-coverage record has status `none_observed`, `unknown`, or `not_deployed`, deployment/exposure start and source when applicable, `observed_through`, and may supersede only earlier coverage for that ticket; `none_observed` requires demonstrable exposure. Ticketless control events capture factory defects found by conformance or operations. Production and control series never supersede each other, and the absence of a current coverage record is `unknown`.

**`index_use`**. Which context index entries a stage read, and whether they were stale (FM-17).

| Field | Meaning |
|---|---|
| `id`, `stage_run_id`, `entry_path`, `entry_last_verified`, `stale` | Stale is computed from the entry's staleness rule at read time |

**`score`**. One row per grader verdict on a stage run, from the observer pass, an eval, or a benchmark. Created with R-O-10 (Later). Its shape was fixed on 2026-09-10 after the Mastra study (`docs/research/mastra-comparison.md`) so the table is created once: a grader with more than one step keeps the exact prompt and result of every step, a `batch_id` groups the rows one observer pass wrote, and the row points at the graded run and, separately, at the grader's own run for its cost.

| Field | Meaning |
|---|---|
| `id`, `stage_run_id`, `grader_ref` | Grader by path and content hash |
| `dimension` | A requirement id from section 4, or a named measure such as cost against tier budget |
| `grade`, `evidence` | `insufficient_information` is a valid grade; `evidence` is the final step's support |
| `step_prompts`, `step_results`, `reason` | One prompt-and-result pair per grading step a multi-step grader ran, plus the final reasoning text, each under the section 8 limit for `reasoning_summary`; null for a single-step grader |
| `batch_id`, `grader_run_id` | The observer pass or benchmark run that wrote this row; the grader's own `utility_run`, which carries its tokens and cost separately from the graded run |
| `grader_model`, `context` | `context` is `observer`, `eval`, or `benchmark` |
| `human_grade`, `graded_by` | Filled when the engineer grades the same item, for calibration (R-O-11) |
| `scored_at` | |

**`human_signal`**. Human reactions captured from outside the queue, read-only. Created with R-S7-6 (Later).

| Field | Meaning |
|---|---|
| `id`, `ticket_id`, `source`, `ref` | `source` is `pr_review_comment` |
| `author`, `text_digest`, `at` | Digest, not payload; the comment stays on GitHub |

**`proposal`**. One row per improvement proposal, whoever drafted it. Created with R-F-10 (Later).

| Field | Meaning |
|---|---|
| `id`, `window` | The window of runs the proposal rests on |
| `pattern`, `evidence_runs`, `fm_ids` | The pattern observed, the stage runs it cites, and the catalogue ids it implicates (P8) |
| `diff_ref`, `eval_change` | The pull request on the factory repository and the eval change that accompanies it |
| `proposed_by`, `state`, `decided_by`, `at` | `proposed_by` is the engineer or the improvement agent; `state` is `open`, `merged`, `rejected` |

**`benchmark`**. One row per configuration run against a fixture set. Created with R-F-12 (Later).

| Field | Meaning |
|---|---|
| `id`, `fixture_set`, `stage`, `manifest_hash` | The configuration under test, by its manifest hash |
| `scores_ref`, `cost`, `currency`, `cost_basis`, `pricing_table_hash`, `at` | Scores are `score` rows with `context = benchmark`; cost fields use the same provenance contract as a stage run |

**`fixture_candidate`**. One row per candidate eval fixture written from an outcome. Created with R-F-15 (Later); a row never writes into `factory/`.

| Field | Meaning |
|---|---|
| `id`, `ticket_id`, `stage_run_id`, `trigger` | The run it came from and the trigger: `send_back`, `revision_after_approval`, `abandoned`, or `fix_round` |
| `skill_ref`, `rubric_ref` | The skill whose eval directory the candidate targets and the rubric in force, with hashes |
| `note`, `artefact_ids` | The human note or failing recipe output, and the governed artefacts the candidate rests on |
| `state` | `open`, `accepted` (exported by `fixture_from_export` under redaction review), or `dismissed` |

**`baseline_measure`**. One row exists for every selected baseline ticket and requested measure, including unavailable values: `id`, `ticket_id`, `measure`, `measure_definition_hash`, `service`, `ticket_type`, derived tier under the pinned tier-rule hash, nullable `value`, `status` (`observed`, `approximate`, `unavailable`), `source_kind`, immutable `source_ref` and content hash, `source_observed_at`, `entered_by`, `entered_at`, and `unavailable_reason`. Only `observed` rows whose definition hash, service, type, and tier match the factory view are comparable. Approximate and unavailable rows remain visible but never enter a pass/fail comparison. Baseline views read only this table; all other views exclude baseline tickets (R-O-4).

**`human_verdict`**. One append-only row per uncalibrated semantic rubric-line instance inspected at S3: `id`, `ticket_id`, `queue_item_id`, stable `rubric_line_id`, `subject_item_key` for repeated units/fields, rubric file and hash, subject artefact id and hash, verdict (`pass`, `fail`, `blind_spot`), evidence ids and hashes or note, reviewer canonical identity and role, timestamp, canonical serialization version, and `content_hash`. Completeness is derived over the expected `(rubric_line_id, subject_item_key)` set. The complete canonical verdict set is hashed independently into the plan tuple; any waiver points to the verdict and is hashed as a separate plan-waiver set. A failed verdict sends the ticket back; a blind spot needs a valid waiver.

**`guard_decision`**. One append-only metadata-only row per R-T-9 content enforcement point: `id`, optional ticket and run ids, operation, canonical route id, source and destination identities, safe content provenance, input and effective data classes, trust-profile, trust-approval-set and rule-set hashes, allowed post-redaction content digest, sanitizer/declassification rule id where used, decision (`allow`, `redact`, `deny`), reason codes, produced redacted artefact id when applicable, timestamp, canonical serialization version, and `content_hash`. These bindings prevent a decision id from authorising another route or payload. It never stores rejected secret material and the trusted sink does not recursively guard this row.

**`reviewer_set`**. One immutable planned, actual, or effective set: `id`, ticket id, kind, subject hash, base/head SHA where applicable, planned- or changed-path-set hash, CODEOWNERS path and blob SHA at the target base, sensitive-path and owner-config hashes, identity/team-membership snapshot hash where used, canonical serialization version, `content_hash`, and canonical requirement slots. Each slot records its canonical key (role, owner and source rule), matched path, source rule and pattern, precedence, canonical role or owner, minimum approval count, and `distinct_from` constraints. The effective set merges a matching planned/actual key using the maximum count and union of separation constraints and preserves nonmatching slots. Unmatched, ambiguous, or unresolvable ownership blocks the gate.

**`approval_record`**. One immutable row per actor and required slot: `id`, optional ticket id, gate (`trust_profile`, `plan`, `review`, `graduation`), canonical subject hash, evidence-tuple and reviewer-set ids/hashes where applicable, publication-target hash for review, slot id and scope, actor canonical identity, identity-source/authentication reference, role, authority-policy hash and membership snapshot, decision (`approve`, `reject`, or `redirect`), attestation version/hash, evidence ids and hashes, `decision_supported_without_transcript` and active-attention bucket where the gate is plan or review, decision time, optional expiry, optional `supersedes`, canonical serialization version, and `content_hash`. Expiry is mandatory for `trust_profile` approvals. For each `(gate, subject, slot, actor)`, exactly one unsuperseded head is current; a forked head blocks the gate. Quorum counts distinct canonical actor identities, never repeated records by one actor. An approval-set hash is the canonical ordered hash of the qualifying current approval-record content hashes. A false self-containedness answer requires an FM-10 `packet_defect` tag on this record. A gate passes only when the current records for every slot approve the same subject, meet each minimum count and identity-separation constraint, and are unexpired. Bound evidence or authority change creates a new subject; expiry requires fresh records against the same subject. Old records remain audit evidence but confer no authority.

**`waiver`**. One immutable row: `id`, ticket id, policy id/version/hash from `waiver-policy.yaml` or the check's explicitly named content-addressed policy, waived check result or human verdict, subject kind (`plan_candidate` or `review_tuple`) and canonical subject hash, optional evidence-tuple id, authorised actor identity and role, reason, exact ticket/path/check/condition scope, compensating controls, evidence ids and hashes, issued time, mandatory expiry, canonical serialization version, and `content_hash`. A plan-candidate hash canonically binds the waived verdict, its subject artefact and evidence hashes, rubric/check identity, and pinned manifest, trust, authority and waiver-policy context; it is then included in the plan tuple. An S5 waiver binds the review tuple. Validity is derived from subject, policy, evidence, actor authority, and expiry. The accompanying `policy_exception` tag points here for reporting but grants no authority.

**`evidence_tuple`**. One immutable row per R-T-10 binding. Common fields: `id`, `kind`, `ticket_id`, current target-base SHA; manifest, project-config, trust-profile, trust-approval-set and recipe hashes; sandbox and toolchain digests; `created_at`; canonical serialization version; and `content_hash`. A `plan` tuple adds ticket-source, brief, criteria and plan hashes, question-resolution-set and current-assumption-set hashes, `base_sha`, planned reviewer-set hash, semantic-checklist, human-verdict-set and plan-waiver-set hashes. Its `content_hash` is the plan-approval subject. A `review` tuple adds `plan_tuple_id`, satisfying plan-approval-set hash, exact head, diff and deviation-set hashes, and actual/effective reviewer-set ids and hashes. Tuples are never updated with validity state; validity is derived by comparison with current state, authority, and approval-set expiry, and rejection records the reason.

**`external_write`**. The transactional outbox of R-T-11: `id`, optional `ticket_id`, originating stage-run id, `operation`, `idempotency_key`, governed payload artefact and digest, authorising guard-decision id, review tuple and review-approval-subject/set hashes where applicable, publication-target hash, repository/target/head refs, desired and expected prior remote head SHAs, PR-body hash, revision number, remote PR identity, `state` (`pending`, `sending`, `reconciled`, `failed`, `superseded`), attempt count, remote identity and governed receipt artefact, last error, and timestamps. One key's destination and payload fields are immutable. Payloads obey R-T-9 and never contain credentials.

**`utility_run`**. Work outside a ticket stage: `id`, optional `ticket_id`, `kind`, inputs, outputs, manifest hash, exact runtime/model fields where an agent is used, tokens, cost, currency, `cost_basis`, optional pricing-table hash, wall clock, outcome, lease and timestamps. It uses the same cost-provenance, append-as-work-proceeds and crash rules as a stage run but never appears in stage reliability.
