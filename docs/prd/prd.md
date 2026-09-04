# Software Factory PRD

| | |
|---|---|
| Status | Draft v0.7 |
| Date | 2026-09-04 |
| Owner | Abhishek Thakur |
| Cites | `docs/charter.md` v0.9; `docs/prd/inputs.md` v0.8; `docs/research/synthesis.md` v0.1; `docs/research/synthesis-factories.md` v0.1; `docs/research/inbox/warp-article-self-improving-factories.md` |
| Scope | The whole factory, S0 to S7. Every requirement is Initial or Later, nothing in between. Initial is the version scoped in D20 and described on one page below. |

## 1. How to read this document

**What it is.** The requirements for the factory described in the charter. The charter says what the factory must be and why. This document says what it must do, precisely enough to build and test. Where the charter deliberately leaves out rubric contents and schemas, this document holds them.

**Stance.** The factory is a collaborator (P11). Every requirement below that adds automation adds, with it, a human-readable artefact and a record of the reasoning. The self-improvement machinery in sections 6 and 7, scorers, an improvement pass, and benchmarks, is taken from the factory literature and pointed at our measures and rubrics, not at cost or throughput (C8). In the initial version that machinery exists as tables and directories only; it switches on after the first ticket has been exported (section 11, call 21).

**Citation rule.** Every requirement cites at least one principle (P-n) and at least one failure mode (FM-n) from the charter. Constraints (C-n) and decisions (D-n) may be cited in addition. A requirement that cannot cite a principle and a failure mode is removed, not kept in case. This is P8 applied to the document itself. `tools/prd_check.py` enforces the rule and derives section 9 from the rows.

**Requirement format.** Requirements are numbered `R-<area>-<n>` and appear in tables with four columns: the requirement, its citations, its version, and how it is verified. The version is exactly `Initial` or `Later`. Where an obligation has an initial part and a later part, the initial part is the requirement and the later part is a sentence in section 10 or a separate Later row. The verification column names the check, not the tool: a script test, a manifest test, a grader in the observer pass, or inspection by the engineer. Inspection is a temporary state and is marked `(temporary)`. A grader-verified line is advisory until that grader is calibrated (R-F-8); its deterministic half runs from the first ticket, its grader half produces `score` rows once the observer pass runs (R-O-10, Later), and until then the engineer's own reading is the check.

**Rubric lines.** A rubric line is a requirement on an agent's output, stated as a pass or fail check. Rubric lines are requirement rows; the rubric list under each stage names the rows by id and says whether each is deterministic, a grader, or both, and where it came from. The versioned rubric file for a stage (section 7) is generated from those rows, and `score.dimension` is a requirement id. Retired ids are never reused (section 13).

**What this document does not do.** It selects tools only in section 8, after research packets R10 to R10c, with the reasons recorded in `docs/prd/inputs.md` section 6. It does not describe architecture beyond the interfaces the charter requires in C7 and the day-one decisions in section 8. It does not restate the charter; it cites it.

**Areas.** T ticket record. I stage interface. S0 to S7 the stages. H human interaction. O observability and measures. F factory as code. Configuration values and day-one decisions are in section 8 and are not requirements.

## The initial version

**What runs.** One ticket at a time, on the engineer's machine. The engineer hands the runner a Jira key. The runner moves the ticket from `intake` to `pr_opened` (section 2.3), stopping at every human touchpoint; acting in the list view records the decision and runs the ticket on to the next touchpoint (section 8, runner invocation). S1 to S4 are agent invocations through the primary runtime, one per stage and one per plan task at S4, plus the S2 restatement sub-invocations recorded as child runs (R-S2-3). S0 is scripts plus one drafted paragraph, and the draft can be switched off. S5 and S6 are scripts. No agent runs on a ticket after S4.

**In order.**

1. **S0.** Scripts check the Jira fields, look up the service tier, map the ticket type, set the provisional tier (Standard for every pilot ticket unless a sensitive path is named), and match sensitive paths. Engineer: eligible or not, confirm the type, tier override, confirm the scrutiny paragraph.
2. **S1.** The brief. Engineer: nothing, unless a blocker arrives as a question.
3. **S2.** Criteria in EARS form with examples, the forced categories, the agreement check, the questions. Engineer: answer or accept defaults in the list view.
4. **S3.** The risk-map script runs on the brief's touched-area candidates, then the plan is written with its fixed tables (R-S3-18), each task carrying the commands that prove it. Engineer: approve, or send back to S3, S2, or S1 with a send-back tag.
5. **S4.** The ticket worktree on the ticket branch. One invocation per plan task; a task passes when its validation commands exit as expected, three attempts, then escalation. Engineer: nothing, unless escalated.
6. **S5.** The project's lint, types, and unit tests, then dependency check, size gate, scope diff, and contract diff, on the branch diff, all of them, with every red result in one item. Engineer: only if a check is red.
7. **S6.** The packet with the diff appended, read locally. Engineer: approve or request changes. Approval runs `pr_open`, which pushes the branch and opens the pull request with the packet as its description. The ticket reaches `pr_opened` and is closed. The initial version ends here.

**Written to the record.** Every stage run, child run, and tool call as it happens, with runtime, model, manifest hash, tokens, cost, and outcome, through the runtime adapter (R-I-13). Every artefact as a versioned file with a table row. Every queue item, question, answer, assumption, deviation, tag, and index use. A text report over the views on demand. The ticket directory exportable.

**Explicitly not there.** S7 and anything after the pull request opens. The advisory pass. The observer pass, scores, and calibration. The eval harness, the adoption gate, benchmarks, and the improvement pass, beyond their directories and tables. Confluence sync, dashboards, the read-only MCP server, stacked pull requests, required-reviewer enforcement, the close survey, S1 fan-out. More than one ticket at a time.

**Definition of done.** One `small_feature` ticket on the pilot Java service goes from a Jira key to an open pull request whose description is the packet, with every stage run recorded, every human decision taken in the list view, nothing pushed before approval, and the report showing first-attempt pass or fail per stage, where an S4 task passes only by its own validation commands. What the ticket showed becomes the first rubric edits. The parallel limit rises only under the section 8 rule.

## 2. The ticket record

The stage map implies a ticket record and never defines it. This section defines it, because every stage reads and writes only this record (C3, C7), every measure is computed only from it (C5, D18), and every catalogue tag lands in it (D21).

### 2.1 Where it lives

Run state lives in one SQLite database. Large artefacts, meaning briefs, criteria, plans, packets, and check evidence, live as files in a per-ticket directory, and the database holds a row per artefact with its path, version, and hash. The database is the index and the ledger; the files are what humans and agents read. Neither is versioned in the factory repository (C3). Versioned files, meaning rubrics, agents, skills, scripts, index entries, and configuration, are section 7.

| # | Requirement | Cites | Version | Verified by |
|---|---|---|---|---|
| R-T-1 | One SQLite database holds all run state for all tickets: tickets, runs, tool calls, artefacts, queue items, questions, answers, assumptions, deviations, checks, tags, index use, and the `score`, `human_signal`, `proposal`, and `benchmark` tables that Later machinery fills. No stage keeps state anywhere else between invocations. | C3, C5, C7, C8, P4, FM-21, FM-22 | Initial | Script test: a stage run with the database path changed finds no prior state |
| R-T-2 | Every artefact an agent or script produces is a file under the ticket's directory, registered in the `artefact` table with kind, version, path, and content hash. A stage reads artefacts only through the table. | C3, C5, P9, FM-21, FM-10 | Initial | Script test: an unregistered file is invisible to the next stage |
| R-T-3 | Artefacts and the append-only tables, `assumption`, `tag`, `deviation`, `answer`, and the content fields of `question`, are never edited in place: a new version is a new row and a new file, and superseded versions remain readable. The lifecycle fields of `ticket`, `queue_item`, `question.state`, and `stage_run` (state, outcome, timestamps) are the exception, and each change carries its timestamp. | C3, P4, FM-17, FM-21 | Initial | Script test on the append-only set; schema test that no other field is mutable |
| R-T-4 | The record is exportable as a single directory: the ticket's rows as JSON, the artefact files, and the branch as a patch against `base_sha`. The export is the eval fixture (C6, R-F-3) and the hand-over to another engineer. The API has a matching import. | C6, C7, P2, FM-17 | Initial | Script test: export then import yields an identical record |
| R-T-5 | The state table in 2.3 is enforced. A stage invoked from the wrong state, or without a ticket and a stage, is refused and recorded as a `stage_run` with outcome `refused`. Refusals are excluded from the first-attempt measure. | C5, C7, P10, FM-21, FM-18 | Initial | Script test per transition and for the missing-ticket case |
| R-T-6 | Every transition that a human decides against the factory's output commits only with a `tag` row carrying a failure-mode id the human chose from the catalogue list: tier override (`override`), plan redirect or send-back to an earlier stage (`send_back`, ground and target stage in `note`), request changes or send back from `checks` (`revision_after_approval`), `abandoned`, and a packet or question that needed reconstruction (`packet_defect`, R-H-8). The factory never infers a human tag. The factory itself writes `stale_index` (R-S1-7) and `escalation` (R-S4-6). Rejection at S0 is mechanical and carries no tag; the missing item is the reason. | D21, P8, FM-17 | Initial | Script test: each transition without its tag is refused; each factory-written kind appears with the right `fm_id` |

### 2.2 Entities

Field lists are the minimum. Additional fields are allowed; removals are not.

**`ticket`**. One row per ticket accepted at S0.

| Field | Meaning |
|---|---|
| `id` | Factory identifier |
| `source_kind`, `source_ref` | `jira` plus the issue key, or `confluence` plus the page id |
| `title` | From the source |
| `service` | Target service, from the configured Jira field (section 8) |
| `service_tier` | From the service tier list (section 8), looked up at S0 |
| `ticket_type` | One of the types in section 8 |
| `tier_provisional`, `tier_final` | Light, Standard, or Heavy (D11) |
| `tier_override_by`, `tier_override_at`, `tier_override_reason` | Set only by a human, with an `override` tag |
| `scrutiny_requested` | Free text from S0: what the reviewer should look hardest at and what they may take on the evidence |
| `required_approvers` | Owners named by sensitive paths and discretion paths (R-S0-5, R-S6-6); named in the plan and packet, enforced Later |
| `state` | See 2.3 |
| `blocked_on` | Null, or the `queue_item` id the ticket waits on |
| `base_sha`, `branch`, `worktree_path`, `head_sha` | The base-branch commit pinned at eligibility and never re-pinned, the ticket branch, its worktree, and the branch head recorded at S4 hand-back and after every push |
| `pr_url` | Set when `pr_open` opens the pull request after S6 approval |
| `baseline` | True for the pre-factory tickets of R-O-6; never mixed with factory tickets |
| `opened_at`, `closed_at`, `close_reason` | `pr_opened` (the initial version's close), `merged` (Later), `abandoned`, or `rejected_at_s0` |
| `close_survey` | Later: optional one-question answer at close (charter section 8, FM-09) |

**`stage_run`**. One row per invocation of a stage for a ticket. This is the C5 ledger at invocation grain. At S4 there is one row per plan task.

| Field | Meaning |
|---|---|
| `id`, `ticket_id`, `stage`, `plan_item`, `attempt` | `plan_item` is null except at S4. Attempt increments on every rerun of the same stage, or of the same S4 task, so first attempt means `attempt = 1` per (`stage`, `plan_item`) |
| `parent_run_id` | Null except for a sub-invocation a stage makes, such as an R-S2-3 restatement: a child row carries its own runtime, model, tokens, cost, and wall clock, counts against its parent's budget (R-I-6), and is excluded from the first-attempt measure |
| `tier` | The tier in force when the run started |
| `runtime`, `model` | Which agent runtime and which model, recorded verbatim (C4, D5). Null for a script-only stage |
| `agent_ref`, `skill_ref`, `rubric_ref` | Versioned file identities used, with their content hashes (C6). Null for a script-only stage |
| `manifest_hash` | The factory version in force for this run; every measure can be sliced by it (charter section 8) |
| `tool_allowlist` | The MCP servers and tools attached for this run (C1) |
| `inputs`, `outputs` | Artefact ids read and written |
| `reasoning_summary` | Agent-written, under the section 8 limit, stored verbatim. Null for a script-only stage |
| `tokens_in`, `tokens_out`, `cost`, `cost_provenance`, `wall_clock_seconds` | From the runtime; `cost_provenance` is `runtime` for a settled figure or `estimate` for a price-table estimate |
| `outcome` | `pass`; `fail`; `blocked` (ended waiting on a blocking question); `escalated` (D14 bound reached); `aborted_budget`; `aborted_human`; `refused` (R-T-5) |
| `started_at`, `ended_at` | |

**`tool_call`**. One row per tool call inside a stage run. Ledger at call grain.

| Field | Meaning |
|---|---|
| `id`, `stage_run_id`, `seq` | |
| `tool`, `args_digest`, `result_digest` | Digests, not payloads, unless the payload is itself an artefact |
| `duration_ms`, `tokens` | Where the runtime exposes them; null otherwise, never estimated |

**`artefact`**. One row per file an agent or script produces.

| Field | Meaning |
|---|---|
| `id`, `ticket_id`, `stage_run_id` | |
| `kind` | `ticket_source` (the source ticket's fields verbatim, written at S0), `brief`, `criteria`, `question_set`, `risk_map`, `plan`, `handoff`, `deviation_list`, `failure_history`, `check_evidence`, `packet`, `pr_checks_summary` (Later), `export` (a directory) |
| `version`, `path`, `hash`, `created_at` | |
| `supersedes` | Previous version's id, or null |

**`queue_item`**. One row per item that needs a human. The queue is the only channel to the human (D17) and every wait measure is computed from this table.

| Field | Meaning |
|---|---|
| `id`, `ticket_id`, `stage`, `tier` | |
| `kind` | `question`, `eligibility`, `plan_approval`, `packet_approval`, `red_check`, `escalation`, `rubric_inspection`; Later `bloat_signal`, `close_survey` |
| `ref` | The `question`, `artefact`, `check_result`, or `stage_run` the item is about |
| `queued_at`, `resolved_at`, `resolved_by` | The wait measure is `resolved_at - queued_at` |
| `action`, `note` | What the human did: answer, accept default, approve, redirect, request changes, send back (with the target stage), resume, override, abandon, decide eligibility, edit scrutiny, close inspection, stop; free text where the action requires it |

**`question`**. One row per question that passed the gate (charter section 6).

| Field | Meaning |
|---|---|
| `id`, `ticket_id`, `stage`, `round` | Round starts at 1 |
| `rank` | Position in its round after ranking |
| `affects` | The criterion, plan item, or decision the answer changes |
| `reasoning` | Why the agent cannot decide, including the sources it tried |
| `options` | Two to four, stored as a list; each option is a label and a one-sentence consequence (R-S2-14) |
| `default_option` | Index into options, or null when the question is consequential and hard to reverse (D15) |
| `consequential`, `blocking` | Booleans set by the agent, overridable by the human. A blocking question holds the ticket (R-S2-12) |
| `rank_inputs` | The impact and probability estimates used to rank, stored so the ranking can be calibrated later |
| `raised_by_answer` | Answer id for a follow-up question, else null |
| `state` | `open`, `answered`, `default_accepted` |

**`answer`**. One row per human response.

| Field | Meaning |
|---|---|
| `id`, `question_id`, `chosen_option`, `free_text`, `answered_by`, `answered_at` | `chosen_option` may be "none of these", which requires `free_text` |

**`assumption`**. Append-only log (charter section 6).

| Field | Meaning |
|---|---|
| `id`, `ticket_id`, `text`, `origin` | Origin is a question id when the assumption came from an accepted default, else `agent` |
| `state`, `supersedes` | `active` or `superseded`; a superseding entry names the old one; nothing is edited |
| `created_at` | |

**`deviation`**. One row per deviation from the approved plan. This is the deviation-list schema S4 hands back and S6 shows before the diff.

| Field | Meaning |
|---|---|
| `id`, `ticket_id`, `stage_run_id`, `plan_item` | |
| `plan_said`, `agent_did`, `why` | |
| `kind` | `judgment` or `error` |
| `contract_change` | Boolean (FM-15) |

**`failure_history`**. The artefact an S4 escalation attaches (R-S4-6). Fixed content: the plan task with its validation commands and expected results; per attempt, the files changed, the verbatim validation output, the agent's diagnosis and what it changed next, the reasoning summary, `head_sha`, tokens and wall clock; the tasks that depend on this one and their state. It is written so the human can act from the escalation item alone (R-H-8).

**`check_result`**. One row per deterministic or advisory check.

| Field | Meaning |
|---|---|
| `id`, `stage_run_id`, `check_name`, `check_tier` | `check_tier` is `blocking` or `advisory` |
| `source` | `factory`; Later `github_actions` |
| `result` | `pass`, `fail`, `blind_spot` |
| `evidence_artefact` | Artefact id holding the full output |
| `summary` | One line for the packet, naming the likely catalogue id where the check has one |

**`tag`**. The evidence process (D21).

| Field | Meaning |
|---|---|
| `id`, `ticket_id`, `event_kind` | `revision_after_approval`, `incident`, `override`, `abandoned`, `escalation`, `stale_index`, `send_back`, `packet_defect` |
| `fm_id` | A catalogue id, required |
| `ref` | The stage run, question, artefact, or external incident the tag points at |
| `note`, `tagged_by`, `tagged_at` | `tagged_by` is a human for every kind except `stale_index` and `escalation`, which the factory writes. For `send_back` the note carries the ground from `checklists/send-back-grounds.md` |

**`index_use`**. Which context index entries a stage read, and whether they were stale (FM-17).

| Field | Meaning |
|---|---|
| `id`, `stage_run_id`, `entry_path`, `entry_last_verified`, `stale` | Stale is computed from the entry's staleness rule at read time |

**`score`**. One row per grader verdict on a stage run, from the observer pass, an eval, or a benchmark. Filled by Later machinery (R-O-10, R-F-3, R-F-12); the table exists from the start.

| Field | Meaning |
|---|---|
| `id`, `stage_run_id`, `grader_ref` | Grader by path and content hash |
| `dimension` | A requirement id from section 4, or a named measure such as cost against tier budget |
| `grade`, `evidence` | `insufficient_information` is a valid grade |
| `grader_model`, `context` | `context` is `observer`, `eval`, or `benchmark` |
| `human_grade`, `graded_by` | Filled when the engineer grades the same item, for calibration (R-O-11) |
| `scored_at` | |

**`human_signal`**. Human reactions captured from outside the queue, read-only. Filled Later by R-S7-6.

| Field | Meaning |
|---|---|
| `id`, `ticket_id`, `source`, `ref` | `source` is `pr_review_comment` |
| `author`, `text_digest`, `at` | Digest, not payload; the comment stays on GitHub |

**`proposal`**. One row per improvement proposal, whoever drafted it. Filled Later by R-F-10.

| Field | Meaning |
|---|---|
| `id`, `window` | The window of runs the proposal rests on |
| `pattern`, `evidence_runs`, `fm_ids` | The pattern observed, the stage runs it cites, and the catalogue ids it implicates (P8) |
| `diff_ref`, `eval_change` | The pull request on the factory repository and the eval change that accompanies it |
| `proposed_by`, `state`, `decided_by`, `at` | `proposed_by` is the engineer or the improvement agent; `state` is `open`, `merged`, `rejected` |

**`benchmark`**. One row per configuration run against a fixture set. Filled Later by R-F-12.

| Field | Meaning |
|---|---|
| `id`, `fixture_set`, `stage`, `manifest_hash` | The configuration under test, by its manifest hash |
| `scores_ref`, `cost`, `at` | Scores are `score` rows with `context = benchmark` |

**`baseline_measure`**. One row per figure of a pre-factory ticket (R-O-6): `ticket_id` (a `ticket` row with `baseline = true`), `measure` (a charter section 8 measure that history or the retrospective yields), `value`, `source` (`pr_history` or `retrospective`), `entered_at`. Baseline views read this table and nothing else; every other view excludes baseline tickets (R-O-4).

### 2.3 Ticket states

States are the only orchestration the initial version has (D24, D27). A stage may run only from the state that precedes it, and a stage's outcome moves the ticket to exactly one next state. Every wait on a human is a `queue_item`; `blocked_on` names it.

| State | Entered from | Leaves when |
|---|---|---|
| `intake` | Ticket picked up; also where a ticket beyond the parallel limit waits (R-I-10) | S0 scripts pass and the human decides eligibility (`eligibility` item); a mechanical failure or a decline goes to `rejected` |
| `rejected` | S0 fails the mechanical gate, the ticket is outside pilot scope, or the human declines | Terminal; `close_reason = rejected_at_s0` |
| `context` | Eligibility granted; a send-back from any later state | S1 passes; an S1 blocker is a blocking question and the run ends `blocked` |
| `clarifying` | S1 pass; a send-back from any later state | S2 exit (R-S2-12) with no open blocking question; an S2 run that raises a blocking question ends `blocked` and reruns from the record when it is answered |
| `planning` | S2 exit; a send-back from `plan_review`, `checks`, `review`, or `escalated` | S3 produces a plan |
| `plan_review` | Plan produced (`plan_approval` item) | Approve moves to `implementing`; redirect returns to `planning`, `clarifying`, or `context` with a `send_back` tag and a note the rerun receives |
| `implementing` | Plan approved; request changes from `review`; send back from `checks`; a resolved escalation | S4 hand-back recorded: `branch`, `head_sha`, deviation list |
| `checks` | Hand-back recorded | Blocking tier green moves to `review`; any red check queues a `red_check` item, and the engineer sends the ticket back to `implementing` with a `revision_after_approval` tag and a note S4 receives, or to an earlier stage with a `send_back` tag |
| `review` | Blocking tier green (`packet_approval` item) | Approve runs `pr_open` and moves to `pr_opened`; request changes returns to `implementing` with a `revision_after_approval` tag and the reviewer's note, or sends the ticket back to an earlier stage with a `send_back` tag; a failed `pr_open` leaves the ticket here with the approval standing (R-S6-3) |
| `pr_opened` | `pr_open` succeeded | Terminal in the initial version: `closed_at` is set and `close_reason = pr_opened`. Later: S7 takes it through `pr_checks` to `merged` |
| `pr_checks` | `pr_opened` (Later) | S7 reports all required checks green |
| `merged` | Human merges (Later) | Terminal |
| `abandoned` | Human closes without merge, from any state | Terminal; requires an `abandoned` tag |
| `escalated` | Any stage aborted on budget (R-I-6), an S4 task past the D14 bound (R-S4-6), or stop (R-I-8); an `escalation` item is queued | The human's action returns the ticket to the state of the stage that escalated, with `attempt + 1` and the resolution note in the next handoff (R-S4-1), sends it back to `planning` or an earlier stage with a `send_back` tag, or moves it to `abandoned` |

**Send-back.** From any open queue item (plan approval, red check, packet approval, escalation) the human may send the ticket back to `context`, `clarifying`, or `planning` with a `send_back` tag and a note. The target stage reruns with `attempt + 1` and receives the note; artefacts produced after it are superseded by the rerun's. This is the between-gate intervention P11 asks for (call 32).

**Failed and blocked runs.** A run ending `fail`, including an R-I-12 structural failure and a crash, leaves the ticket in its current state; `advance` reruns it with `attempt + 1` up to the retry count in section 8, then queues an `escalation` item and moves the ticket to `escalated`. On start, the runner closes any `stage_run` with no `ended_at` and no live process as `fail`. A run ending `blocked` writes its artefact with the sections that depend on the open answer marked `pending answer`, exempt from R-I-12 until the rerun, which keeps the rest (charter section 6, delivery).

## 3. Stage interface

| # | Requirement | Cites | Version | Verified by |
|---|---|---|---|---|
| R-I-1 | The factory exposes one API and every client uses it: the runner, the list view, the digest, and any later MCP server. Initial operations: advance a ticket to its next human touchpoint; run a named stage for a ticket; stop a running stage; get a ticket's record; list the queue; act on a queue item; get measures; export and import a ticket. Later operations: score runs, open a proposal, run a benchmark. Nothing else invokes an agent or writes the record, and the runner imports the stage interface and nothing inside a stage. | C7, C5, P10, P11, FM-21, FM-19 | Initial | Script test that no other path creates a `stage_run` or writes a table; import-graph test on the runner |
| R-I-2 | Each stage run is a fresh agent invocation. It receives the ticket's artefacts named in the manifest for that stage, the rubric file for that stage, and nothing from any earlier invocation's transcript. A rerun after a blocking question or an escalation learns the round and the history from the record alone. | C1, C3, C4, P4, FM-21, FM-19 | Initial | Script test: the invocation input is reproducible from the record alone |
| R-I-3 | Each stage run attaches only the MCP servers and tools the manifest lists for that stage and tier (the attachment table in section 8), and the runtime's native write tools are denied where the stage has no write role. At S4 writes are confined to `worktree_path`, the worktree's remote has no push URL until `pr_open` sets it, and build commands run through a wrapper limited to the commands in `project.yaml`. The attached set is written to `stage_run.tool_allowlist` before the agent starts. | C1, D8, P10, FM-05 | Initial | Script test comparing manifest to recorded allowlist; script test that a read-only stage cannot write a file, that S4 cannot write outside `worktree_path`, and that a push from S4 fails |
| R-I-4 | The manifest names, per stage and per tier, with a `default` tier entry that the pilot uses for every tier: the agent definition, the skill, the rubric, the tool allowlist, the budget, the runtime, the model, the grader model, and for S2 the restatement model (R-S2-3). Files by path and content hash; runtime and model by name. Budgets are tokens and wall-clock seconds, never runtime-specific units (D5); adapters translate. For a script-only stage (S0 without the draft, S5, S6) the agent, skill, model, and grader model are null. A stage run that cannot resolve every non-null entry does not start. | C6, C1, D5, D31, P2, P10, FM-17, FM-19 | Initial | Script test; schema test that budget keys are `tokens` and `wall_clock_seconds` only |
| R-I-6 | A stage run that exceeds its tier budget, or an S4 task whose stage's cumulative tokens or wall clock on the ticket exceed the S4 per-ticket budget (section 8), is stopped, recorded with outcome `aborted_budget`, and the ticket is placed in `escalated` with an `escalation` queue item carrying the run's reasoning summary and last outputs, and an `escalation` tag with FM-19. Where the runtime settles cost after the fact, the wall-clock half of the budget is enforced live and the token half at the run boundary. The per-ticket total is checked before each S4 task starts and at each run boundary, child runs count against their parent, work a stopped task left in the worktree is kept, and the escalation names the last completed task. | D14, P10, FM-19, FM-21 | Initial | Script test with a deliberately small budget |
| R-I-8 | Stop terminates a running stage, records outcome `aborted_human` with the reasoning summary and outputs so far, and moves the ticket to `escalated`. It is the only mid-run intervention. There is no steering, because a steered run cannot be reproduced from the record (R-I-2) and a watched run is the attention pattern FM-09 exists to end. | C3, P10, P11, FM-19, FM-09 | Initial | Script test |
| R-I-9 | A read-only MCP server exposes get record, list queue, get measures, and export, so the engineer's own agent sessions and the improvement agent can read the factory without touching it. | C5, P11, FM-17 | Later | Script test: no write operation is exposed |
| R-I-10 | The runner enforces the parallel ticket limit in section 8. A ticket beyond the limit waits at `intake` and the list view shows it as waiting on capacity, derived from its state and the limit with `blocked_on` null, not on a human. The limit changes only when the engineer edits configuration. | D28, P1, FM-09 | Initial | Script test |
| R-I-11 | Forbidden tools, tested on the manifest as a whole: no GitHub merge, push to a default branch, pull-request approval, or Actions re-run tool at any stage; repository write only at S4 and in the `pr_open` script; Slack post only in the digest script; no write tool of any kind at S1 or S5. The manifest test fails if one appears. | D4, C1, P10, FM-18, FM-05 | Initial | Manifest test |
| R-I-12 | Every artefact with a fixed section list (brief, criteria, plan, packet) fails on structure, before any judgment check runs, when a section is missing or empty, and for the plan when a table of R-S3-18 is missing a column or a required row, or a traceability rule of R-S3-19 fails. The section lists are the "Produces" paragraphs in section 4; a section marked `pending answer` by a run that ended `blocked` is exempt until the rerun. | P4, P9, FM-16 | Initial | Script test per artefact kind and per plan table |
| R-I-13 | The runtime adapter is runner code outside `factory/`, one per runtime, the Cursor SDK adapter first. It takes a manifest entry and the input artefacts, invokes the runtime, and returns every `stage_run` field the runtime can supply (`tokens_in`, `tokens_out`, `cost`, `cost_provenance`, `wall_clock_seconds`, `outcome`, `reasoning_summary`) and one `tool_call` row per call, null where the runtime does not expose a value and never estimated. The record never depends on which adapter ran. | C5, D5, D31, P7, FM-19, FM-21 | Initial | Adapter contract test with a stub runtime; script test that a null field is never filled by an estimate |
## 4. Stage requirements and rubrics

For each stage: the artefact it produces, its requirements, its rubric lines, and the human touchpoint. A rubric line is a requirement row named by id in the "Rubric" list, marked deterministic (a script), grader (a single-dimension grader in the observer pass), or both, with its research source or "original".

Deterministic lines run as scripts and block. Grader lines produce `score` rows once the observer pass runs (R-O-10, Later) and may block a stage only after the grader's agreement with the engineer's own grading has been recorded (R-F-8). Until then they are advisory, and the engineer's own reading is the check.

### S0 Intake

**Produces.** Fields on the `ticket` row: service tier, ticket type, provisional tier, scrutiny requested, required approvers. No artefact file. S0 is scripts except the scrutiny draft, which configuration can switch off.

| # | Requirement | Cites | Version | Verified by |
|---|---|---|---|---|
| R-S0-1 | Mechanical gate, no LLM: the source ticket has a non-empty acceptance criteria field, a named owner, and a linked parent (epic) or linked Confluence page, read through the field mapping in `config/ticket-types.yaml`. Any missing item rejects the ticket with the missing item named. An epic is rejected with "needs child tickets"; a ticket type outside the pilot list (D32) is rejected with "outside pilot scope". The reason is recorded on the ticket; posting it back to Jira is configuration, off by default. The source ticket's fields are written verbatim as a `ticket_source` artefact, the input S1 and S2 restate from; the S0 scripts read Jira through their own credential, as `pr_open` reads GitHub. | P1, P6, FM-06, FM-16 | Initial | Script test per missing item and per rejection reason |
| R-S0-2 | Lookups, all from section 8 tables: service tier from `service-tiers.yaml`, failing with "service not tiered" when the service is absent (the factory never guesses a tier); ticket type from the Jira issue-type mapping; provisional tier from the tier matrix, service tier by ticket type. | D11, P1, P7, FM-05 | Initial | Script test over the full matrix and every unmapped input |
| R-S0-5 | Sensitive paths (section 8: authentication, authorisation, payments, secrets, schema migrations, infrastructure) force the tier to at least Heavy and add the path's owner to `required_approvers`, named in the plan and the packet as a required approver at S3 and S6. Applied at S0 by matching the globs against path-shaped tokens in the ticket text, and authoritatively at S1 against the brief's touched-area candidates. Enforcement of the second approver is Later; in the pilot the one engineer approves and the packet shows the named owner. | P5, P10, FM-02, FM-14 | Initial | Script test |
| R-S0-6 | Scrutiny requested: when the draft is enabled, the agent drafts one paragraph from the ticket type and title, naming what the reviewer should look hardest at and what they may take on the evidence; when disabled (`scrutiny_draft` in `project.yaml`), the engineer writes it in the list view and the manifest's S0 agent, skill, and model entries are null. The human confirms or edits it at eligibility. Empty scrutiny holds the ticket at `intake`. | P9, P1, FM-10 | Initial | Script test for the hold; grader for draft quality (advisory) |
| R-S0-7 | The human decides eligibility, confirms the ticket type, and may override the provisional tier, through one `eligibility` queue item. All three are recorded on the ticket; an override carries its tag (R-T-6). | D11, D21, P1, FM-09, FM-05 | Initial | Script test |

**Rubric, S0.** R-S0-1, R-S0-2, R-S0-5: deterministic, original. R-S0-6: grader, original.

**Human touchpoint.** One decision: eligible or not, with the type confirmed, an optional tier override, and the scrutiny paragraph. Target under two minutes for a Light ticket.

### S1 Context gathering

**Produces.** `brief`, one file, fixed sections in this order: ticket summary; linked sources with dates; touched area candidates; history of each non-obvious candidate; impacted services with method; flags in the touched path; blind spots; unknowns, being facts the plan will need that no source available to S1 settled, each with what was tried; index entries used and stale; final tier with the files-touched, services-touched, and unknown counts it was computed from; blockers. In the initial version S1 is one invocation and produces one brief.

| # | Requirement | Cites | Version | Verified by |
|---|---|---|---|---|
| R-S1-2 | The ticket summary is fact-only: no recommendations, no approach, under the word limit in section 8. An unfamiliar reviewer can orient from it alone. | P9, FM-10, FM-16 | Initial | Script test for length; grader for fact-only |
| R-S1-3 | Impacted services are listed in two directions, each with the method that produced it. Outbound, the services this one calls: the import and client-library scan against the project's Maven or Gradle dependency tree, enabled per service in configuration; if the scan cannot run, "outbound unknown" is a blocker, becomes a blocking question, and holds the ticket. Inbound, the services that call this one: the hand-maintained, optional entry for the service in `config/service-callers.yaml`; when there is none, the brief states "callers unknown" as a declared blind spot handed to the human (P7), never as coverage. Neither is ever a footnote. | P7, FM-14 | Initial | Script test: a scan with no method produces a blocker; a service with no callers entry produces the blind spot |
| R-S1-4 | Two-step archaeology on every candidate file or function that is not self-evident: blame, then the issues named in the commit messages, read through the Atlassian server; the pull-request chain arrives with the GitHub read attachment (Later). Each is classified `explained`, `unexplained`, or `contradictory` in the brief, and a candidate whose history names no issue is `unexplained`. What the plan does with the classification is R-S3-4. | P5, FM-02 | Initial | Script test for the classification; grader for "non-obvious" coverage |
| R-S1-6 | Production facts the plan may depend on, including SLIs, error budget, live flag state, and logs, are never asserted. Flags in the touched path are inventoried from code references only. Live state appears only in the blind spots section, each with what the plan will assume about it (C2). | C2, P7, FM-14 | Initial | Script test for the flag inventory; grader: any asserted production fact fails |
| R-S1-7 | Every context index entry read is recorded in `index_use` with its last-verified date. An entry past its staleness rule is listed in the brief as stale and the factory writes a `stale_index` tag with FM-17. An empty index is allowed and the section says "no entries". | C3, P7, FM-17 | Initial | Script test |
| R-S1-8 | Final tier is computed by the rule in section 8 from files touched, services touched, and unknown count. It is never lower than the provisional tier. The human may override with a tag (R-T-6). | D11, P1, FM-05 | Initial | Script test over the rule |
| R-S1-10 | For tickets touching more than one service, S1 may fan out one sub-invocation per service and merge the results into one brief. The human never receives more than one brief per ticket. | P1, FM-09, FM-14 | Later | Script test on the merge |

**Rubric, S1.** R-I-12 on the brief: deterministic, original. R-S1-2: deterministic length, grader content; synthesis S1, the context section orients an unfamiliar reviewer in under a minute. R-S1-3: deterministic; synthesis S1. R-S1-4: deterministic presence, grader coverage; synthesis S1, FM-02. R-S1-6: deterministic inventory, grader assertions; original, from C2. R-S1-7: deterministic; synthesis-factories finding 6.

**Human touchpoint.** None unless a blocker is raised. A blocker arrives as a question through the queue.

### S2 Requirements clarification

**Produces.** `criteria`, one file, fixed sections in this order: each acceptance criterion restated in EARS form with at least one example; the forced-category checklist result; the agreement-check result; the size estimate for the split rule, as estimated lines and files with the basis; the completeness verdict. `question_set` per round. `assumption` rows for accepted defaults.

| # | Requirement | Cites | Version | Verified by |
|---|---|---|---|---|
| R-S2-1 | Every acceptance criterion is restated in EARS form: optional precondition, optional trigger, the system, the response, and carries an id `AC-n` assigned in restatement order that later versions of the criteria keep and never reuse. A criterion that cannot be restated is marked `unformalisable` and becomes a question. | P3, FM-06, FM-16 | Initial | Script test for form and for id stability across versions; grader for faithfulness to the source criterion |
| R-S2-2 | At least one concrete Given/When/Then example per criterion, with real values, not placeholders. | P6, FM-06, FM-08 | Initial | Script test for presence; grader for concreteness |
| R-S2-3 | Agreement check: each criterion is restated independently in N fresh contexts (N in section 8), each a child `stage_run` under the S2 run (`parent_run_id`), on the restatement model the manifest names for S2, counted in the S2 budget and excluded from the first-attempt measure. Disagreement on precondition, trigger, or response marks the criterion ambiguous and raises a question. A contradiction between criteria raises a question. An input region no criterion covers raises a question. | C4, C5, P6, FM-16, FM-06 | Initial | Script test on three seeded cases: an ambiguous criterion, a contradictory pair, an uncovered input region; record test that N child rows exist per criterion |
| R-S2-4 | The forced-category checklist (`checklists/forced-categories.md`) is run against the criteria. Categories: error paths, concurrency, migration, backward compatibility, permissions, observability, rollback, data retention. Each category resolves to `covered by criterion n`, `not applicable because`, or `open`. `open` becomes a ranked question. No category is left silent. | P2, P4, FM-08 | Initial | Script test |
| R-S2-5 | Question gate, which with R-S2-6 to R-S2-9 governs every question at any stage, including an S1 blocker: a question is emitted only if the agent lists the sources it tried and none answered, and the answer changes a named criterion or plan item. Both are recorded on the question. | P1, FM-07 | Initial | Script test for the fields; grader for whether the sources listed would plausibly have answered |
| R-S2-6 | Questions are ranked by impact times the probability the default is wrong, where impact counts the criteria affected, weighted by tier. The inputs are stored in `rank_inputs` so the ranking can be calibrated against the accept-given-shown rate later. | P1, FM-07 | Initial | Script test for stored inputs |
| R-S2-7 | Question format is validated before queueing: reasoning present, two to four options, a default marked unless `consequential`, no default when `consequential`, "none of these" always present. A malformed question is rejected back to the agent. | D15, P1, FM-07 | Initial | Script test per rule |
| R-S2-8 | A question is `consequential` when its answer changes a declared contract, a data migration, a permission boundary, a public interface, or the rollout strategy, or when the sensitive-path list applies. The human may flip the flag either way. | P10, FM-07, FM-15 | Initial | Script test on seeded cases |
| R-S2-9 | A follow-up question names the answer that raised it. A new round is queued only after the previous round's blocking questions are resolved; the round number comes from the record (R-I-2). | P1, FM-07, FM-09 | Initial | Script test |
| R-S2-10 | Split rule: if the criteria do not describe one vertical slice with observable value, or the size estimate in the criteria (estimated lines and files, with the basis) exceeds the tier's split threshold (section 8), the agent proposes a split as a consequential question, using the patterns in `checklists/split-patterns.md`: workflow steps, business-rule variations, data variations, interface variations, defer performance, simple then complex. | P1, P3, FM-05 | Initial | Script test on the size half; grader on the vertical-slice half, with seeded oversized tickets |
| R-S2-11 | Every accepted default writes an `assumption` row naming its question. The assumption log is attached to the criteria and carried unmodified into every later question, the plan, and the packet. | P4, FM-16 | Initial | Script test |
| R-S2-12 | Blocking is a property of the question, set by the agent and overridable by the human. Open blocking questions hold the ticket in `clarifying`; non-blocking questions do not. Criteria that depend on an open non-blocking question are marked `provisional`, and the plan carries the corresponding assumption until the answer arrives. A run that raises a blocking question completes every criterion, category, and question that does not depend on the answer before it ends `blocked`. S2 exits when every criterion is formalised or its `unformalisable` question answered, every category resolved, the criteria artefact passes R-I-12, and no blocking question open. | P1, P3, FM-07, FM-09 | Initial | Script test |
| R-S2-14 | Question wording. A question and its options are written for a reader who has opened nothing: no requirement, principle, failure-mode, or decision ids, no stage codes, and no artefact, script, or table names in the question text or its options; names from the service's own code are allowed. Every option carries a one-sentence consequence, and the default's consequence says what happens if nobody answers. The identifier check runs with R-S2-7 and rejects the question back to the agent; readability is graded. | P1, P11, FM-07 | Initial | Script test on the identifier list; grader on a question answered correctly without the artefact |

**Rubric, S2.** R-I-12 on the criteria: deterministic, original. R-S2-1 and R-S2-2: deterministic form, grader faithfulness and concreteness; synthesis S2, headline 5. R-S2-3: deterministic; synthesis headlines 4 and 5, Kiro's semantic-entropy pattern. R-S2-4: deterministic; synthesis S2. R-S2-5: deterministic fields, grader sources; synthesis headline 4. R-S2-7: deterministic; charter D15, synthesis headline 4. R-S2-10: deterministic size, grader slice; synthesis S2. R-S2-11: deterministic; synthesis cross-cutting. R-S2-14: deterministic on identifiers, grader on readability; the v0.6 review round.

**Human touchpoint.** Answers through the queue only. For a Light ticket, the expected question count is zero or one; a Light ticket that raises more than the section 8 ceiling queues a `rubric_inspection` item, a signal to inspect the rubric, not to answer faster.

### S3 Spec and plan

**Produces.** `plan`, one file, sections in this order: intent in two sentences and the scrutiny requested; goals and non-goals; approach; alternatives considered; scope, being files to touch, files deliberately not touched with reasons, and discretion paths; dependencies added, changed, or removed, with the reason for each; archaeology outcomes and required characterization tests; abstraction decisions; tech-debt proposals; contracts of touched code; task list with dependencies and validation commands; test strategy; rollout section for the engineer; risk map; size estimate against the gate; blind spots; assumption log; unknowns for human confirmation; required approvers. Six of these, scope, dependencies, contracts, tasks, test strategy, and size estimate, are the fixed tables of section 8 (R-S3-18); the checks and the runner read only the tables. The task list being ordered with dependencies and every task carrying its validation commands is D16 and is checked by R-I-12 through the tasks table.

| # | Requirement | Cites | Version | Verified by |
|---|---|---|---|---|
| R-S3-2 | Every rejected alternative gets one line: what it was and why it was rejected, so "not considered" and "considered and rejected" are distinguishable. | P4, FM-01 | Initial | Script test for presence; grader for substance |
| R-S3-3 | A new shared abstraction cites at least three existing near-duplicates it replaces, or names pre-abstraction as a risk. Adding both a parameter and a conditional to a shared function serving two or more unrelated callers states why inlining was not chosen. | P5, FM-01 | Initial | Script test: a new file under a shared path lists three replaced call sites or a risk entry; grader for the judgment |
| R-S3-4 | Before any non-self-evident code is modified, the plan carries its archaeology classification from the brief. Code classified `unexplained` or `contradictory` gets a characterization test in the task list, and a change that alters captured behaviour is a named risk for the human to rule load-bearing or accidental. | P5, FM-02 | Initial | Script test that every such candidate in the brief has a test task and an unknown in the plan |
| R-S3-5 | A change whose entire justification is "no behaviour change" is its own task, flagged `no_behaviour_change` in the tasks table, with behaviour-preserving tests, and its own pull request once stacked pull requests exist (R-S6-8); until then it is a separate ticket or a named exception the human approves at S3. | P5, FM-04 | Initial | Script test on the tasks table: every flagged task is separate and has a behaviour-preserving test; grader for hidden refactors |
| R-S3-6 | Before proposing a new utility, helper, or pattern, the agent queries the repository index or component catalogue and records the existing candidates it found and why each was rejected. | P5, FM-03 | Initial | Script test for the record; grader for search adequacy |
| R-S3-7 | For every touched function, module, or endpoint, the contracts table declares its input, output, and error contract and marks it `unchanged` or `changed`. A `changed` contract is a named decision and, if not already answered at S2, a consequential question. | P4, FM-15, FM-08 | Initial | Script test |
| R-S3-9 | The test strategy table states tests by size (small, medium, large) against the target mix in section 8, and each planned test states what it proves. A test justified only by coverage is a rubric failure. | P6, FM-11 | Initial | Script test for structure; grader for "what it proves" |
| R-S3-10 | The rollout section is written for the engineer to execute after merge and the factory never executes it. It contains: any flag with expected life, owner, removal condition, and a cleanup task; ramp steps; guardrail metrics up to the section 8 limit, each as a query with a critical threshold; the kill trigger with rollback as the default response; and the log-verification queries with pass and fail patterns. | D25, C2, P7, FM-16 | Initial | Script test for structure; grader for substance |
| R-S3-11 | The risk map is computed first by the `risk_map` script from git, before the agent runs, over the brief's touched-area candidates, and attached as a `risk_map` artefact input: per candidate file, commits in the churn window and the top-author share (section 8). Files in the top decile of churn times size within the candidate set, or with no clear owner, are named entries. The agent then names the three places worth a reviewer's eyes and says why. A generic risk map fails. | D16, P9, FM-10, FM-02 | Initial | Script test for the computation and for the inputs being attached; grader for non-genericity |
| R-S3-12 | Size gate, one tier threshold (section 8) applied twice. At S3 the estimated changed lines in the plan's size table over the threshold require a split proposal or a justification in that table, approved with the plan. At S5 the real diff, added plus removed lines excluding lockfiles and configured generated files, over the threshold is a blocking failure unless the approved plan version's size table carries the justification, in which case the check passes and says so. | P1, FM-05 | Initial | Script test at both points |
| R-S3-14 | The plan is judgeable in one sitting: its prose is under the tier length ceiling in section 8 and its tables under the row ceiling, and intent, scrutiny, and the risk map are within its first 60 lines. | P1, P9, FM-10 | Initial | Script test |
| R-S3-15 | Approval is by one named human, recorded on the `plan_approval` queue item against the plan's artefact version. Owners in `required_approvers` are shown on the item as required approvers; enforcing a second approval is Later. Any new plan version reopens approval, and nothing enters `implementing` while approval is open (R-T-5). | D4, P10, FM-18 | Initial | Script test |
| R-S3-18 | Plan tables. The scope, dependencies, contracts, tasks, test strategy, and size sections are fixed tables with the columns in section 8. Every task row carries at least one validation command with its expected result, and those commands are what S4 runs (R-S4-5); approving the plan approves them. The scripts `scope_diff`, `contract_diff`, `dep_verify`, `size_gate`, the handoff builder, the packet's test summary, and the S4 runner read only these tables. | P2, P9, D16, FM-16, FM-05, FM-15 | Initial | Script test per table: a missing column, a task with no validation command, and a prose-only section each fail R-I-12 |
| R-S3-19 | Criterion traceability. The tasks table and the test strategy table each carry a `criteria` column listing the `AC-n` ids (R-S2-1) the row serves. The plan fails R-I-12 when a cited id is not in the criteria, when a criterion is served by no task row, when a criterion is served by no test row, or when a task row cites nothing without the `no_behaviour_change` flag. A criterion with no automated test is a test-strategy row with test `none` and the reason in `proves`. The packet's test summary groups tests by criterion. | P8, P6, FM-16, FM-11, FM-05 | Initial | Script test: a dangling id, an unserved criterion, and an unflagged task with no criterion each fail R-I-12 |

**Rubric, S3.** R-I-12 on the plan: deterministic; synthesis S3, universal template core. R-S3-2: deterministic presence, grader substance; synthesis S3. R-S3-3: deterministic floor, grader judgment; synthesis FM-01, Metz and rule of three. R-S3-4: deterministic; synthesis S3, FM-02. R-S3-5: deterministic on the task list, grader for hidden refactors; synthesis FM-04, Google policy. R-S3-6: deterministic record, grader adequacy; synthesis FM-03. R-S3-7: deterministic; synthesis headline 7. R-S3-9: deterministic structure, grader substance; synthesis S3, Google test sizes. R-S3-10: deterministic structure; synthesis S7 adapted to D25. R-S3-11: deterministic computation, grader for the three places; synthesis S3, Meta Diff Risk Score and churn evidence. R-S3-12: deterministic; synthesis headline 3. R-S3-14: deterministic; original. R-S3-18: deterministic; original, from the v0.5 review. R-S3-19: deterministic; the section 9 pattern applied to the plan.

**Human touchpoint.** Approve or redirect, one named human. This is the first of the two structural gates. The plan is read from the first page; the reviewer should be able to decide from intent, scrutiny, and the risk map, and open the rest only when those raise a doubt. A redirect, to `planning` or to an earlier stage, records a `send_back` tag with a ground from `checklists/send-back-grounds.md`: duplicates existing work; technically unsound; missing backward-compatibility or migration analysis; contradicts a stated non-goal; built on a wrong brief or wrong criteria, naming the target stage; other, with a note (R-T-6).

### S4 Implementation

S4 is automated from the initial version (D20): the factory runs the implementation through the primary runtime, one invocation per plan task, under the D14 bounds, in an isolated worktree on a ticket branch. Nothing is pushed until the engineer approves the packet at S6. The hand-off and hand-back fix what S5 and S6 need whoever produced the change, so an external implementer stays possible.

| # | Requirement | Cites | Version | Verified by |
|---|---|---|---|---|
| R-S4-1 | The `handoff` artefact is self-contained: the approved plan version, the criteria, the assumption log, the brief's blind spots, the tier and its budget, the list of deterministic checks S5 will run with their thresholds, the bodies of `checklists/comment-rules.md` and `checklists/test-filter.md` with their hashes, the `deviation` schema, and any note from a request-changes, send-back, or escalation loop. An implementer with nothing else can start. | D20, P4, FM-21, FM-05 | Initial | Script test: the handoff references no artefact outside itself and embeds both checklists by hash |
| R-S4-2 | Hand-back: `branch`, `head_sha`, and `worktree_path` on the ticket, and the `deviation_list` artefact in the `deviation` schema (2.2), possibly empty. No pull request exists yet. A missing deviation list is recorded as a `check_result` with result `blind_spot` and the packet says "no deviation list supplied". | P4, P7, FM-21, FM-15 | Initial | Script test |
| R-S4-5 | Automated S4: one `stage_run` per plan task in dependency order, in the ticket's worktree, each a fresh invocation (R-I-2) that receives the handoff and the branch state. A verification attempt is one execution of the task's validation commands from the tasks table after the agent's change, run by the runner, not the agent, each result a `check_result` row (`check_name` `task_validation`) on the task's run; the task's outcome is `pass` only when every command exits as expected, and the agent's own judgment sets nothing; a command that cannot run is a failed attempt with the reason. Three attempts per task, then escalation (R-S4-6); the tier budget is the runaway stop (R-I-6). The conformance self-report across tasks is the deviation list. After a request-changes, send-back, or escalation loop, only the tasks the note names rerun; the rest keep their outcome. | D14, D28, P6, P10, FM-19, FM-21 | Initial | Script test with seeded failing tasks, a task whose command cannot run, and a seeded rerun note; test that no task run reaches `pass` without green `task_validation` rows |
| R-S4-6 | An S4 escalation ends the run with outcome `escalated`, queues an `escalation` item with the `failure_history` artefact attached and the task's plan item named, writes an `escalation` tag with FM-19, and moves the ticket to `escalated`. There is no bare retry. | P1, FM-19, FM-09 | Initial | Script test |
| R-S4-7 | The advisory tier (R-S5-8) enforces the two checklists the handoff carries. Comment rules: a comment fails if it can be regenerated by paraphrasing the adjacent code; a comment is required where the plan marked a decision non-obvious or where behaviour deviates from what the name or signature implies; TODO comments carry an owner. Test filter: a generated test is kept only if it builds, passes N reruns without flake, raises coverage or kills a mutant the existing suite missed, and states what it proves. | P6, FM-11, FM-12, FM-13 | Later | Grader on recorded fixtures |

**Rubric, S4.** R-S4-2: deterministic, deviation list present and well-formed; synthesis S4, original schema. R-S4-5: deterministic, task validation commands run by the runner; original, from the v0.5 review.

**Human touchpoint.** None, unless escalated to through the queue (R-S4-6).

### S5 Cleanup pass

Two tiers (D16). The blocking tier is deterministic and runs first. S5 flags; it never edits: no script modifies the diff or the branch (R-I-11). The advisory tier is Later and never runs on a red build.

| # | Requirement | Cites | Version | Verified by |
|---|---|---|---|---|
| R-S5-1 | Blocking tier, in order, all scripts: the project's own lint, type check, and unit tests as configured in the repository and invoked by the commands in section 8; dependency verification (R-S5-2); size gate (R-S3-12); scope diff (R-S5-4); contract diff (R-S5-5). Every check runs even after a red one. Each check writes one `check_result` with an evidence artefact and a one-line summary; a configured command that does not exist for the project records `blind_spot`. All red results go into one `red_check` item; the ticket holds in `checks` and the engineer sends it back to `implementing`, or to an earlier stage, with a note (2.3). | D16, P6, P10, FM-11, FM-20, FM-05, FM-15 | Initial | Script test per check and for the red path |
| R-S5-2 | Dependency verification: every import in the diff resolves in the project's real environment; the resolved dependency list the build tool prints, taken at `base_sha` and at head (section 8), is diffed and compared with the plan's dependencies table. An unresolvable import, an undeclared new dependency, or an undeclared version change is a blocking failure. The summary names the likely catalogue id, FM-20 for a dependency that does not resolve and FM-05 for one that resolves but was not declared, for the human to confirm when tagging. | D20, P6, FM-20, FM-05 | Initial | Script test with a fabricated import and an undeclared package |
| R-S5-4 | Scope diff: files in the diff, minus the paths in the plan's scope table, minus its discretion globs. A non-empty result is a blocking failure listing the files. No LLM is involved. | P5, FM-05, FM-04 | Initial | Script test |
| R-S5-5 | Contract diff: for every unit in the plan's contracts table, the `contract_diff` script extracts the public declarations, signature, parameters, return type, declared error or exception types, and visibility, from the source at `base_sha` and at head with the tree-sitter grammar configured for the file's language in `project.yaml`, and compares them with the declaration. A change to a contract the plan marked `unchanged` is a blocking failure. Where no grammar is configured for a file's language, or a unit cannot be located, the check records `blind_spot` for that unit and the packet names it. Inherited members and binary compatibility are outside the script's reach and are named as its blind spot in the packet; a compiled-API comparison such as japicmp is a Later upgrade. | P4, P7, FM-15 | Initial | Script test on seeded signature, return-type, and exception changes, and on a file with no grammar |
| R-S5-8 | Advisory tier: an independent agent pass in a fresh context, on a different model where the runtime offers one (C4), never on a red build, against the test filter, the comment rules, style and pattern conformance to the index, and scope judgment on discretion paths. Findings attach as evidence, never block, and never remove anything. | C4, P6, FM-11, FM-12, FM-13, FM-03, FM-18 | Later | Eval with recorded fixtures |
| R-S5-10 | The blocking tier blocks only on regressions: it uses the project's existing lint and type configuration, and `factory/lints/` adds no blocking rule of its own. | P5, FM-03 | Initial | Script test: `factory/lints/` contributes nothing to the blocking tier |
| R-S5-11 | Sliced advisory pass. The advisory pass may be split into slices by concern (correctness, contracts, tests, comments and style), each a child `stage_run` in a fresh context writing one report artefact, consolidated by a script into the single advisory report with findings deduplicated by file and line and ordered by severity. The single pass of R-S5-8 stays the default until the pilot shows it truncating on a Standard-tier diff. | P1, P9, FM-21 | Later | Script test on consolidation: the same finding from two slices appears once |

**Rubric, S5.** The blocking tier is the rubric: R-S5-1, R-S5-2, R-S3-12, R-S5-4, R-S5-5, deterministic throughout. Synthesis S5 and synthesis-factories finding 5 for the ordering; synthesis headline 7 for the contract diff; synthesis headline 3 for the size gate.

**Human touchpoint.** Only when the blocking tier is red: the engineer sends the ticket back through the queue with a note; nothing is fixed by hand outside a stage run.

### S6 Human review

| # | Requirement | Cites | Version | Verified by |
|---|---|---|---|---|
| R-S6-1 | The packet is assembled by script from the record, in the fixed order of charter section 6 (checks, intent, scrutiny, decisions, not touched, risk map, deviations, assumption log, test summary, blind spots, diff), with the diff appended from the branch. Each element names the artefact it came from: decisions are composed from the plan's approach, alternatives, abstraction decisions, and `changed` contracts; blind spots are the union of the brief's, the plan's, and every `check_result` with result `blind_spot`. No element is agent-written at S6. Packet length is not a quality proxy and is not measured; the risk map's three places are graded once, at R-S3-11. | D16, P9, FM-10, FM-18 | Initial | Script test for order and provenance |
| R-S6-2 | The test summary matches the plan's test strategy table to the test files in the diff. A test in the diff with no planned purpose is listed as "unplanned test, purpose not stated". | P6, FM-11, FM-10 | Initial | Script test |
| R-S6-3 | Before approval, the review surface is the `packet` artefact with the diff appended, read from the ticket directory or opened from the list view; nothing has left the machine. On approval, the `pr_open` script pushes the ticket branch, opens the pull request with the packet as its description, records `pr_url` and `head_sha`, and moves the ticket to `pr_opened`. It is the only write to GitHub in the initial version and it is a script, not an agent (D16), recorded as an S6 `stage_run` with no agent. A failed push or pull-request creation leaves the ticket in `review` with the approval standing, writes a `check_result` with the error as evidence, and queues a `red_check` item; `advance` retries on the engineer's action. | P9, FM-10, D4, D16, D25 | Initial | Script test for the surface; script test for the `pr_open` contract |
| R-S6-6 | A file on a discretion path, or on the sensitive-path list, names its owner as a required reviewer in the packet, from `required_approvers`. Enforcement through GitHub required reviewers is Later. | P10, FM-05, FM-02 | Initial | Script test |
| R-S6-7 | The approval line reads, verbatim, that approval certifies judgment, intent, and residual risk, and that defect evidence was supplied by S5. Request changes returns the ticket to `implementing` with a `revision_after_approval` tag (R-T-6) and the reviewer's note, which the next S4 handoff carries. Nothing enters `review` while the blocking tier is red (R-T-5). | D16, D21, P9, FM-18 | Initial | Script test |
| R-S6-8 | Independently mergeable plan tasks may go to S6 as an ordered stack of single-purpose pull requests mapping one-to-one to plan tasks, each with its own packet. | P1, FM-05, FM-10 | Later | Script test |

**Rubric, S6.** R-I-12 on the packet, R-S6-1, R-S6-2, R-S6-7: deterministic. Synthesis S6 and synthesis-factories S6.

**Human touchpoint.** Approve or request changes. The second structural gate. S6 reviews conformance to an approved design, not the design. The reviewer reads the checks and the risk map first and opens the diff at the three named places. The wait is measured on the `packet_approval` item (R-H-1).

### S7 PR checks and merge

S7 is Later in its entirety (D20): the initial version ends when the pull request is opened and the ticket closes at `pr_opened`. The requirements stay here so the record and the runner are built with the states they will need.

| # | Requirement | Cites | Version | Verified by |
|---|---|---|---|---|
| R-S7-1 | Every check run the pull request triggers is read through the GitHub MCP server and recorded as a `check_result` with `check_tier = blocking` and `source = github_actions`, and summarised in the `pr_checks_summary` artefact. | D25, P7, FM-10 | Later | Script test against a PR with mixed results |
| R-S7-2 | For a failed run, the factory fetches the job log and writes a summary of the likely cause with the log lines it rests on, into `pr_checks_summary`, at Light budget. It never re-runs, approves, or merges (R-I-11). | D4, D25, P7, FM-10 | Later | Script test |
| R-S7-3 | The pull request is left open for the human. The runner polls on the runner cadence in section 8; a detected merge moves the ticket to `merged`. | D4, D25, P10, FM-18 | Later | Script test |
| R-S7-4 | Any commit pushed to the branch after `pr_open` invalidates the approval: the ticket returns to `checks`, S5 reruns, a new packet version is produced, and a `revision_after_approval` tag is required. | D21, P10, FM-18 | Later | Script test |
| R-S7-5 | At close, one optional survey question is queued as a `close_survey` item (charter section 8, FM-09): how many tickets the engineer held in parallel and whether returning to this one cost effort. Skipping is allowed and recorded. Arrives with the parallel limit rising above 1. | P1, FM-09 | Later | Script test |
| R-S7-6 | Review comments on the pull request are read through the GitHub MCP server and recorded as `human_signal` rows, so scorers and the improvement pass see the human's reaction to the packet and the diff. Read-only; nothing is posted. | C5, C8, P11, FM-10, FM-18 | Later | Script test |

**Human touchpoint.** Merge, or send back. Rollout after merge is outside the factory (D25).
## 5. Human interaction requirements

| # | Requirement | Cites | Version | Verified by |
|---|---|---|---|---|
| R-H-1 | One queue holds every item needing a human, as `queue_item` rows of the kinds in 2.2: questions, eligibility decisions, plan approvals, packet approvals, red checks, escalations, rubric inspections; Later bloat signals and close surveys. Each item records `queued_at` and `resolved_at` and shows ticket, tier, stage, what is asked, `blocked_on`, and age in the list view and the digest. The wait and touchpoint measures in charter section 8 are computed from this table by tier. | D17, P1, FM-09, FM-07 | Initial | Script test per kind; view test on a seeded queue |
| R-H-3 | The factory never interrupts (D17). The digest goes to the configured Slack channel on the digest cadence in section 8, fired by the scheduler entry named there, listing open items grouped by ticket, oldest first, with counts, and an empty queue sends nothing. It is the only Slack write: the allowlist has one post tool, used by the digest script alone (R-I-11). | D17, P1, FM-09, FM-07 | Initial | Script test; manifest test |
| R-H-4 | A local list view prints the queue and takes every human action: answer a question, accept a default in one action with no free text, choose "none of these" with required free text, approve or redirect a plan, approve or request changes on a packet, decide eligibility and confirm the type, confirm or edit the scrutiny paragraph, override a tier, act on an escalation (resume, send back, or abandon), send back from `checks`, send a ticket back to an earlier stage with a note, note and close a rubric inspection without holding the ticket, stop a running stage, tag an incident or a packet defect, abandon. Incident tags and abandon are ticket-addressed and reach closed tickets; every other action is on a queue item, and acting runs the ticket on to its next touchpoint. It opens any artefact, including the packet with its diff, in the engineer's editor or pager. Every action records who and when on the queue item. | D17, D15, C5, P1, FM-09, FM-07 | Initial | Script test per action |
| R-H-8 | Every packet and every question is self-contained: a reader with no access to any transcript can decide from the item alone. Failure is a factory defect: the human records a `packet_defect` tag with FM-10 on the item, on approve as well as on request changes. Escalation items are held to the same rule through the `failure_history` schema. | P9, FM-10 | Initial | Engineer's reading of each item (temporary); grader in the observer pass when it runs (R-O-10) |
| R-H-10 | One-way sync of human-facing artefacts, brief, plan, decisions, packet, to the Confluence user space (D22). | D22, P9, FM-10 | Later | Script test |

## 6. Observability and measures

| # | Requirement | Cites | Version | Verified by |
|---|---|---|---|---|
| R-O-1 | Every ledger row, `stage_run`, `tool_call`, `queue_item`, `check_result`, and the rest, is written as the run proceeds, not reconstructed after. A crashed run leaves a `stage_run` with outcome `fail` and whatever was recorded to that point. The reasoning summary is stored verbatim and rejected over the section 8 limit. Script invocations outside a ticket, the digest and a setup-time `reindex`, write a `stage_run` with `ticket_id` null and `stage` naming the script. | C5, P7, P9, FM-19, FM-21, FM-10 | Initial | Script test with a killed run; length test |
| R-O-4 | Every measure in charter section 8 is a named SQL view over the record, computed as in the table below. Nothing outside the record enters a view, every view excludes `baseline` tickets, and every view accepts a `manifest_hash` filter: a ticket's factory version is the `manifest_hash` of its plan-approval stage run, or of its latest stage run before that, and views over `question`, `queue_item`, `tag`, and `index_use` join to it through `ticket_id`. | D18, C5, P1, FM-09 | Initial | View tests on a seeded database |
| R-O-5 | The report generator is the only reader of the views and enforces the charter's reporting rules: every growth figure carries its window; the primary panel is unranked; context measures appear in their own block labelled as context; no view exists for agent-attributed share of pull requests, estimated savings over human work, cost per pull request as distinct from cost per ticket, or any breakdown by person. The initial output is a text report on demand. | D18, D28, C8, P1, FM-07, FM-09, FM-10, FM-11, FM-22 | Initial | View-list test for forbidden views; generator test |
| R-O-6 | Before the first factory ticket, the baseline set in section 8 is entered by the `baseline_import` script as tickets flagged `baseline` with one `baseline_measure` row per figure: from pull request history, revisions after first approval, tests kept at first approval, and time to first approval; from one retrospective with the engineer, question count and wait. Baseline views read `baseline_measure` only, and no other view reads a baseline ticket. | P1, FM-09, FM-10 | Initial | Script test on the flag |
| R-O-8 | Dashboards over the views. | D23, C5, P1, FM-09 | Later | Inspection (temporary) |
| R-O-10 | Observer pass: stage runs are scored against that stage's rubric lines, cost against the tier budget, and the self-containedness of packets and questions (R-H-8), by graders running in a fresh context on the grader model the manifest names for that stage, never the authoring model (R-F-3). Results are `score` rows with `context = observer`. Sample rate and cadence are configuration; at pilot scale every run is scored. The bloat signal of R-F-7 is one of its graders. | C4, C8, P2, P11, FM-16, FM-17 | Later | Script test on a seeded run; manifest test for model separation |
| R-O-11 | Calibration: the engineer grades the same items as the observer pass in the list view, the grades land in `score.human_grade`, and the sample feeds R-F-8. | C6, C8, P2, FM-16, FM-18 | Later | Script test |
| R-O-12 | Objective rule. The improvement pass, a grader's right to block, and a benchmark's winner are decided on the primary measures and the rubric-line scores. Cost, tickets closed per window, and non-structural touchpoints are available to them as context columns only, and the report generator and the proposal schema label them as such. | C8, D28, D29, P11, FM-22 | Initial | Schema test for the context label; generator test |

**Measure computations.** All views accept a `manifest_hash` filter and report which factory versions the window spans.

| Measure (charter section 8) | Computation |
|---|---|
| Revisions per ticket after plan approval, by failure mode | Count of `revision_after_approval` tags per ticket, grouped by `fm_id` |
| Questions surfaced per ticket, by tier | Count of `question` rows per ticket, by the tier on the question's `queue_item` |
| Share shown with a default | Questions with `default_option` not null, over all questions |
| Share where the default was accepted when shown | `state = default_accepted` over questions shown with a default |
| Minutes waited at S2, S3, S6, by tier | Per ticket and stage, the union of the open intervals `queued_at` to `resolved_at` over `queue_item` rows of kinds `question`, grouped by the item's own stage, `plan_approval`, and `packet_approval`, so a batch answered in one sitting counts once; by tier |
| Share of generated tests kept after review | Initial: test files in the first packet's diff still present in the approved packet's diff; the figure moves only through a request-changes loop and is 1 for a ticket approved first time. Later: still present at merge, and attribution from the advisory tier |
| Share of plans approved without redirect | Plans with no `send_back` tag, over plans that reached approval |
| Production incidents attributable to factory changes | Count of `incident` tags, entered by a human in the list view |
| "Deliberately not touched" items later shown correct | Later; needs a signal from a subsequent ticket touching the same code |
| Escalations per ticket from S4 | Count of `escalation` tags with `ref` in an S4 stage run, per ticket |
| Index entries found stale per ticket | `index_use` rows with `stale = true`, per ticket |
| Close survey | Later: `ticket.close_survey`, reported as answered share and the answers |
| Share of stage runs passing on the first attempt, by stage and tier | `stage_run` rows with `attempt = 1` and `outcome = pass`, over all rows with `attempt = 1`, excluding `refused`, `blocked`, and child runs (`parent_run_id` set), so a run that stopped to ask a gated question is not a failure; at S4 the unit is (`stage`, `plan_item`) and `pass` comes only from green `task_validation` checks (R-S4-5) |
| Context: tickets closed per window | `ticket` rows with `closed_at` in the window and `close_reason` other than `rejected_at_s0` |
| Context: cost per ticket, by stage and tier | Sum of `stage_run.cost` per ticket, per stage, and per tier, child runs included, with `cost_provenance` shown |
| Context: non-structural touchpoints per ticket, by tier | `queue_item` rows of kinds `question`, `red_check`, and `escalation` per ticket (D29); `eligibility` is excluded as structural and `rubric_inspection` as a factory-health signal |

## 7. Factory as code

The versioned half of memory (C3, C6). Layout is fixed from the start so nothing moves later; contents grow with the rubrics. `factory/` and `runs/` live in this repository, the factory repository, alongside `docs/` (QP-8, call 34). The pilot service is a separate checkout whose path `project.yaml` names; nothing of the factory's is written inside it, and ticket worktrees are created under `runs/` (section 8).

```
factory/
  manifest.yaml       stage -> tier -> agent, skill, rubric, allowlist, budget, runtime, model, grader model; files by path and content hash
  agents/             one agent definition per agent stage (S0 draft, S1 to S4); later one per advisory pass
  skills/             one skill per agent stage
  rubrics/            S0.md to S6.md, generated from the rubric rows of section 4
  checklists/         forced-categories.md, send-back-grounds.md, split-patterns.md, comment-rules.md, test-filter.md
  scripts/            size_gate, scope_diff, contract_diff, dep_verify, risk_map, archaeology, index_staleness, impact_scan, packet_assemble, pr_open, pr_checks, digest, export, import, reindex, manifest_hash, rubric_gen, report, baseline_import, fixture_from_export
  lints/              factory-owned lint configuration; contributes nothing to the blocking tier (R-S5-10)
  evals/              one directory per skill and per agent: fixtures, graders, thresholds, calibration record
  benchmarks/         fixture sets per stage; result matrices by manifest hash
  index/              context index entries: markdown with front matter
  config/             tiers.yaml, service-tiers.yaml, service-callers.yaml, sensitive-paths.yaml, budgets.yaml, limits.yaml, digest.yaml, ticket-types.yaml, project.yaml, tools.yaml, runtime.yaml
  catalogue/          failure-modes.md mirroring charter section 4, with the tag schema; decisions.md
runs/                 not versioned: factory.sqlite; tickets/<id>/ for artefacts and worktrees
```

Secrets and credentials are not under `factory/`: `config/` names environment variables, and the engineer's shell or keychain supplies them.

| # | Requirement | Cites | Version | Verified by |
|---|---|---|---|---|
| R-F-1 | The layout above is the layout. The manifest references every file by path and content hash, and references nothing outside `factory/`. The manifest hash is the hash of the manifest file, recomputed by `scripts/manifest_hash` from the committed tree; an uncommitted edit fails validation. | C6, C3, P2, FM-17 | Initial | Script test; a manual hash edit fails validation |
| R-F-2 | Every skill and every agent definition has an eval directory under `evals/` from the day it is referenced. Its first fixture is the R-T-4 export of the first ticket; until then the directory holds the grader stubs and an empty fixture list. | C6, D26, P2, FM-16, FM-17 | Initial | Manifest test: a referenced skill or agent without an eval directory fails |
| R-F-3 | The eval harness replays a fixture (R-T-4 export) through a stage with the candidate skill or agent, runs the graders, and compares with thresholds. Graders are single-dimension, have an explicit `insufficient_information` output, and run on a model other than the one that authored the change, recorded by name. Once a stage has a fixture, the manifest may reference a skill or agent for it only with at least one fixture and one grader present, and a change is adopted only when its eval passes. | C6, C4, D26, P2, FM-16, FM-18 | Later | Harness test with a seeded fixture; manifest test |
| R-F-4 | A change to a skill, agent, rubric, checklist, script, or configuration file changes the manifest hash, and only through a commit the engineer made or reviewed. During the pilot the engineer edits rubric files directly and records the reason in the commit message; the eval-gated adoption of R-F-3 replaces that once fixtures exist. | C6, D26, P2, FM-17 | Initial | Script test: the hash follows the tree |
| R-F-5 | Nothing at runtime writes to `factory/`. Every change to a versioned file, whether from a tag, a stale entry, a repeated grader failure, or the engineer's own reading, is a diff the engineer reviews. | C3, P2, FM-17, FM-16 | Initial | Script test that no runtime path writes to `factory/` |
| R-F-6 | Every context index entry carries front matter: `source`, `owner`, `last_verified`, `staleness_rule`, `paths`. The rule is evaluated at read time. An entry with no `last_verified` is stale. | C3, P7, FM-17 | Initial | Script test |
| R-F-7 | Agent and skill files are capped at the section 8 line limit; path-scoped files hold path-specific guidance. Every line is expected to answer "would removing this cause a mistake?", and an agent asking a question the file already answers is a bloat signal, a `bloat_signal` queue item detected by the observer pass (Later), not a reason to add text. | P2, FM-03, FM-17 | Initial | Line-count test |
| R-F-8 | Before any grader may block, or contribute to a benchmark or a proposal, its agreement with the engineer's grades over the section 8 minimum sample is recorded in its eval directory, with the protocol used. The sample comes from R-O-11. | C6, C8, P10, FM-16, FM-18 | Later | Eval record test: sample at or above the minimum, protocol named, blocking refused otherwise |
| R-F-9 | Branch protection on `factory/`: every change lands as a pull request with the adoption gate (R-F-3) as a required check, and a direct commit to the default branch touching `factory/` is refused. | C6, C8, P2, FM-17 | Later | Repository configuration test |
| R-F-10 | Improvement pass: a stage over the factory repository, not over a ticket. Input: `score`, `tag`, `human_signal`, and `index_use` rows over the window in section 8. Output: a `proposal` naming the pattern, the evidence runs, the failure-mode ids, the diff to versioned files, and the eval change that accompanies it, opened as a pull request. A proposal may also update the catalogue's frequency columns (D21). The first proposals are engineer-written in the schema; an improvement agent drafts them later, in a fresh context, for the engineer to review. | C8, D30, P2, P8, P11, FM-22, FM-17 | Later | Schema test; eval on recorded windows |
| R-F-11 | The fence: the state table that enforces the gates (R-T-5) and the anti-goals live in runner code outside `factory/`, outside the manifest, and beyond the reach of any proposal. When R-F-9 lands, the adoption gate rejects any pull request whose diff touches them. | C8, P10, FM-18, FM-22 | Initial | Script test that no manifest entry or proposal path can reference the state table |
| R-F-12 | Benchmark: one fixture set through one stage under several manifest configurations, varying runtime, model, skill, or rubric, scored by the same graders, one `benchmark` row per configuration. The winner is chosen by R-O-12 with cost shown beside it, and enters the manifest only through a proposal (R-F-10). A benchmark runs only with calibrated graders (R-F-8). The first benchmark per stage is how D5 is decided for that stage. | C8, D5, D31, P2, FM-16, FM-22 | Later | Harness test; benchmark report inspection (temporary) |

## 8. Configuration values and day-one decisions

Not requirements. Recommended defaults, owned by the engineer, living in `factory/config/`. Q10, Q11, and Q12 from the charter are answered here as configuration. The day-one decisions at the end settle the mechanics a builder meets first; they are architecture in the small and stay out of the requirements.

**Service tiers** (Q11). Hand-maintained `service-tiers.yaml`: service to T1 (customer-facing, critical), T2 (important), T3 (internal or tooling). Filled for the pilot service first.

**Pilot eligibility** (D32). One T2 service, written in Java. Eligible ticket type at S0: `small_feature`. Any other type is rejected at S0 with "outside pilot scope" until the owner widens the list. The provisional tier for every pilot ticket is therefore Standard, unless R-S0-5 raises it.

**Ticket types and Jira fields.** `bug`, `small_feature`, `feature`, `refactor`, `config_or_docs`. Mapping from Jira: Bug to `bug`; Story to `feature`, or `small_feature` when the estimate is at or under the configured point value; Task to `config_or_docs` or `refactor` by label; Epic rejected at S0 with "needs child tickets". Human confirms at eligibility. `ticket-types.yaml` also names the Jira fields for acceptance criteria, owner, parent, and service (a component or label), filled by hand from one pilot ticket viewed in Jira before the first run (QP-2).

**Provisional tier matrix** (D11).

| Service tier | bug | small_feature | feature | refactor | config_or_docs |
|---|---|---|---|---|---|
| T1 | Heavy | Heavy | Heavy | Heavy | Standard |
| T2 | Standard | Standard | Heavy | Standard | Light |
| T3 | Light | Light | Standard | Standard | Light |

**Final tier rule** (S1). Raise one level when services touched is two or more, or files touched exceeds 10, or unknowns are three or more. Sensitive paths raise to Heavy per R-S0-5. Never lower automatically.

**Size gate** (Q10). Light 300, Standard 300, Heavy 200 changed lines (definition in R-S3-12). Heavy is tighter because reviewer attention matters more there, not less. Generated paths and lockfiles to exclude are listed in `project.yaml`.

**Split threshold at S2.** 60 percent of the tier's size gate as estimated lines, or more than 10 files.

**Budgets per stage run** (D14, Q10). Placeholders until three pilot tickets have run, then set from their records. Light: 400k tokens, 20 minutes. Standard: 800k tokens, 40 minutes. Heavy: 1.5M tokens, 60 minutes. S4, per ticket across all its task invocations, on the same placeholder basis: Light 1M tokens, 45 minutes; Standard 2M tokens, 90 minutes; Heavy 4M tokens, 150 minutes. S5 wall clock counts against no budget; the build commands carry their own timeout.

**Agreement check N** (R-S2-3). 3.

**Question ceiling as a signal, not a cap.** Light 2, Standard 6, Heavy none. Exceeding it queues a `rubric_inspection` item; it never suppresses a question.

**Length limits.** Brief summary 300 words. Plan prose: Light 800, Standard 1500, Heavy 2500 words, excluding tables; plan tables: Light 40, Standard 80, Heavy 150 rows in total; first page is the first 60 lines. Reasoning summary 200 words. Instruction files 300 lines.

**Plan tables** (R-S3-18). Fixed columns, validated by R-I-12. Scope: `path`, `action` (`touch`, `not_touched`, `discretion`), `reason`. Dependencies: `package`, `from_version`, `to_version`, `kind` (`add`, `change`, `remove`), `reason`; an empty table is written explicitly. Contracts: `unit`, `kind` (function, module, endpoint), `input`, `output`, `errors`, `status` (`unchanged`, `changed`). Tasks: `id`, `title`, `depends_on`, `criteria`, `files`, `validation_command`, `expected_result`, `no_behaviour_change`; at least one validation row per task. Test strategy: `test`, `size` (small, medium, large, or `none` with the reason in `proves`), `criteria`, `proves`. The two `criteria` columns list `AC-n` ids and R-S3-19 checks them in both directions. Size: `estimated_lines`, `estimated_files`, `basis`, `justification` (empty unless over the gate).

**Stage retries on `fail`.** 1 rerun, then escalation (2.3).

**Risk map.** Churn window 12 months. Ownership concentration is the top author's share of commits in the window; under 40 percent means no clear owner. Named entries are the top decile of churn times file size, plus every file with no clear owner.

**Test mix target.** 80 small, 15 medium, 5 large, by count.

**Guardrail metrics in the rollout section.** At most 12.

**Digest cadence** (Q12). Twice per working day, Monday to Friday, 10:00 and 15:00 local, from a launchd entry (cron on Linux) installed by setup that runs `factory digest`; times, weekdays, and channel in `digest.yaml`, channel chosen by the engineer.

**Index staleness default.** 90 days since `last_verified`, or any commit on the base branch touching the entry's `paths`.

**Index seed.** Two entries written by hand before the first run, each with `last_verified` set at seeding: the pilot service's conventions, and its sensitive paths with their owners.

**Grader calibration minimum sample.** 20 items graded by the engineer before a grader may block.

**Sensitive paths.** `sensitive-paths.yaml`: glob to owner. Seeded with the pilot service's authentication, authorisation, payments, secrets, migration, and infrastructure directories. Where the repository has CODEOWNERS, it wins; the file adds owners only for paths CODEOWNERS does not cover (QP-3).

**Impact methods.** `project.yaml` lists the outbound methods enabled per service; the pilot service has `import_scan` (Maven or Gradle dependency tree). Inbound callers come from `service-callers.yaml`, hand-maintained and optional: service to the services known to call it, with a `last_verified` date; absent means "callers unknown" in the brief (R-S1-3).

**Baseline set.** The last 10 tickets completed the current way before the first factory ticket.

**Runner cadence.** Later, with S7: poll GitHub every 5 minutes while any ticket is in `pr_checks`.

**Parallel tickets** (D28). 1 in the initial version. Raise to 2, then 3, by editing configuration when every stage's first-attempt pass share has held above 90 percent over the last 10 tickets.

**Observer pass** (Later). Sample rate 100 percent at pilot scale. Cadence: on every ticket close for that ticket's runs, and every 5 tickets for a window pass. Cost cap per window pass: 10 percent of the window's ticket cost.

**Improvement window** (Later). The last 20 closed tickets or the last 30 days, whichever is smaller.

**Benchmark fixture set** (Later). 5 to 10 exported tickets per stage, chosen to span tiers.

**Initial-version tooling** (D24, D31; inputs section 6, where the reasons live). The manifest carries these by name; nothing below is a requirement.

| Concern | Selection | Decided by |
|---|---|---|
| Agent runtime | Cursor SDK primary; Claude Code CLI and Agent SDK secondary. One custom agent definition per agent stage, each naming its model; the grader model per stage is never the author model (C4). Before the first run: Privacy Mode enforced on the Cursor team account and a team spend limit set (R10c) | Owner |
| Code navigation | codegraph (colbymchenry), attached as its MCP server with the single default tool, the owner's exception to the first-party rule; full re-index of the ticket worktree by `scripts/reindex` before every S1 run, with `.codegraph/` inside the worktree and never committed, since the initial version never observes a merge (FM-17) | Owner |
| Evals and benchmarks | Inspect, Later. Fixtures are R-T-4 export directories through the sample files field; the `insufficient_information` grade is authored into each grader | Owner |
| Ticket source | A Jira key, read through the Atlassian MCP server | Owner |
| Question digest | The official Slack MCP server for posting; a CLI list view | Owner |
| MCP servers | First-party only: GitHub, Atlassian, AWS, Slack, plus codegraph by exception. No other third-party MCP server; other tools attach as scripts | Owner, enterprise rule |
| Run state, tracker, ledger | One SQLite database in WAL mode holding the section 2 tables; a Python runner | Recommended |
| PR opening | The `pr_open` script: push the ticket branch, open the pull request with the packet as description | Recommended |
| PR checks, Later | GitHub MCP server in read-only mode with the `actions` and `pull_requests` toolsets | Recommended |
| Language scripts | `dep_verify` diffs the resolved dependency list the build tool prints (`mvn dependency:list` or `gradle dependencies`, the command in `project.yaml`) at `base_sha` and at head and compares it with the plan's dependencies table; `contract_diff` extracts public declarations with tree-sitter, the Java grammar for the pilot and any language with a grammar later; japicmp or Revapi are a Later Java-only upgrade if the pilot shows misses (R-S5-5) | Owner (contract diff); recommended (dependency diff) |

**Tool attachment per stage** (C1, R-I-3). `tools.yaml`, initial values:

| Stage | Attached | Writes |
|---|---|---|
| S0 | Atlassian (read) | Ticket row only, by script |
| S1 | Atlassian (read), codegraph, repository read | Brief only |
| S2 | Repository read; the `ticket_source` and `brief` artefacts as inputs | Criteria, questions |
| S3 | codegraph, repository read | Plan |
| S4 | codegraph, repository read and write confined to the worktree, project build commands through the wrapper, no push URL | The ticket branch, locally |
| S5 | None; scripts and project build commands | Check results |
| S6 | None; `pr_open` script holds the GitHub credential | Push and pull request, on approval |
| Digest script | Slack (one post tool) | The digest |

The same allowlist applies to every tier in the initial version; the manifest keys it by stage and tier with a `default` entry (R-I-4).

**Configuration files.** `tiers.yaml`: tier matrix, final tier rule, size gate, split threshold, question ceiling, length limits. `budgets.yaml`: budgets per stage and tier. `limits.yaml`: agreement check N, risk-map window and ownership threshold, test mix, guardrail limit, index staleness, calibration sample, parallel tickets, stage retries. `digest.yaml`: cadence and channel. `ticket-types.yaml`: types and Jira fields. `service-tiers.yaml`, `service-callers.yaml`, `sensitive-paths.yaml`: as above. `project.yaml`: checkout path, base branch, build and dependency-listing commands with timeouts, tree-sitter grammars, JDK, generated paths, `scrutiny_draft`, impact methods. `tools.yaml`: attachment table. `runtime.yaml`: runtime settings recorded before the first run, including Cursor Privacy Mode and the spend limit.

**Day-one decisions.**

- **Runner invocation.** `factory advance <ticket>` runs stages until the next human touchpoint and exits, writing its process id on the open `stage_run`. `factory run <stage> <ticket>` runs one stage. `factory queue` and `factory act` are the list view; `act` records the decision and then runs `advance` on that ticket, so acting is resuming. `factory stop <ticket>` signals the running `advance`, whose handler writes `aborted_human` (R-I-8). `factory show <ticket>`, `factory report`, `factory export <ticket>`, `factory import <dir>`, `factory tag <ticket>`, and `factory abandon <ticket>` complete the R-I-1 operations. The digest is `factory digest` under the scheduler entry named with the cadence. There is no daemon in the initial version.
- **Project location and worktrees.** `project.yaml` names the pilot service's checkout path outside this repository, the base branch, the build commands for lint, type check (for Java, compile), unit tests, and the resolved-dependency listing, each with a timeout, the tree-sitter grammars per language, and the JDK. `base_sha` is set at eligibility from the base branch head of that checkout and never re-pinned. The runner creates `runs/tickets/<id>/worktree` on branch `factory/<id>` from `base_sha` at eligibility, with no push URL on its remote; S1, S3, and S4 read and S4 writes that worktree, never the engineer's checkout. The worktree is removed on `pr_opened`, `abandoned`, or `rejected`; the branch stays. `ticket.id` is the source issue key.
- **Runtime mapping.** An agent definition is the runtime's agent or rules file; a skill is the stage prompt; the rubric is attached as an input file; the allowlist is the runtime's MCP configuration plus its native tool permissions, denied where the stage has no write role (R-I-3). The adapter that does this mapping and fills the ledger is R-I-13.
- **Blocking questions and reruns.** A run that raises a blocking question ends `blocked` after writing everything that does not depend on the answer (2.3); when the question is answered the runner reruns the stage from the record with `attempt + 1`, keeping the independent sections. The same holds for escalations and for send-backs, whose note the rerun receives.
- **Manifest hash.** The hash of `manifest.yaml` as committed, which in turn carries the hash of every referenced file. An uncommitted edit fails validation (R-F-1).

## 9. Traceability

Generated by `tools/prd_check.py --trace` from the requirement rows; do not edit by hand. Every catalogue entry is caught by at least one requirement. Where every requirement is Later, the entry is uncaught in the initial version and the pilot should expect to observe it.

| Failure mode | Requirements | Initial |
|---|---|---|
| FM-01 Abstraction | R-S3-2, R-S3-3 | Yes |
| FM-02 Load-bearing hack | R-S0-5, R-S1-4, R-S3-4, R-S3-11, R-S6-6 | Yes |
| FM-03 Style and pattern | R-S3-6, R-S5-8, R-S5-10, R-F-7 | Yes; Later: R-S5-8 |
| FM-04 Tech debt mixing | R-S3-5, R-S5-4 | Yes |
| FM-05 Scope creep | R-I-3, R-I-11, R-S0-2, R-S0-7, R-S1-8, R-S2-10, R-S3-12, R-S3-18, R-S3-19, R-S4-1, R-S5-1, R-S5-2, R-S5-4, R-S6-6, R-S6-8 | Yes; Later: R-S6-8 |
| FM-06 Jumps to implementation | R-S0-1, R-S2-1, R-S2-2, R-S2-3 | Yes |
| FM-07 Question noise | R-S2-5, R-S2-6, R-S2-7, R-S2-8, R-S2-9, R-S2-12, R-S2-14, R-H-1, R-H-3, R-H-4, R-O-5 | Yes |
| FM-08 Missing scenarios | R-S2-2, R-S2-4, R-S3-7 | Yes |
| FM-09 Parallel fatigue | R-I-8, R-I-10, R-S0-7, R-S1-10, R-S2-9, R-S2-12, R-S4-6, R-S7-5, R-H-1, R-H-3, R-H-4, R-O-4, R-O-5, R-O-6, R-O-8 | Yes; Later: R-S1-10, R-S7-5, R-O-8 |
| FM-10 Unreviewable diff | R-T-2, R-S0-6, R-S1-2, R-S3-11, R-S3-14, R-S6-1, R-S6-2, R-S6-3, R-S6-8, R-S7-1, R-S7-2, R-S7-6, R-H-8, R-H-10, R-O-1, R-O-5, R-O-6 | Yes; Later: R-S6-8, R-S7-1, R-S7-2, R-S7-6, R-H-10 |
| FM-11 Filler tests | R-S3-9, R-S3-19, R-S4-7, R-S5-1, R-S5-8, R-S6-2, R-O-5 | Yes; Later: R-S4-7, R-S5-8 |
| FM-12 Filler comments | R-S4-7, R-S5-8 | No, all Later |
| FM-13 Missing comments | R-S4-7, R-S5-8 | No, all Later |
| FM-14 Unknown impact | R-S0-5, R-S1-3, R-S1-6, R-S1-10 | Yes; Later: R-S1-10 |
| FM-15 Contract drift | R-S2-8, R-S3-7, R-S3-18, R-S4-2, R-S5-1, R-S5-5 | Yes |
| FM-16 False rigor | R-I-12, R-S0-1, R-S1-2, R-S2-1, R-S2-3, R-S2-11, R-S3-10, R-S3-18, R-S3-19, R-O-10, R-O-11, R-F-2, R-F-3, R-F-5, R-F-8, R-F-12 | Yes; Later: R-O-10, R-O-11, R-F-3, R-F-8, R-F-12 |
| FM-17 Memory rot | R-T-3, R-T-4, R-T-6, R-I-4, R-I-9, R-S1-7, R-O-10, R-F-1, R-F-2, R-F-4, R-F-5, R-F-6, R-F-7, R-F-9, R-F-10 | Yes; Later: R-I-9, R-O-10, R-F-9, R-F-10 |
| FM-18 Agent-only review | R-T-5, R-I-11, R-S3-15, R-S5-8, R-S6-1, R-S6-7, R-S7-3, R-S7-4, R-S7-6, R-O-11, R-F-3, R-F-8, R-F-11 | Yes; Later: R-S5-8, R-S7-3, R-S7-4, R-S7-6, R-O-11, R-F-3, R-F-8 |
| FM-19 Slow failure | R-I-1, R-I-2, R-I-4, R-I-6, R-I-8, R-I-13, R-S4-5, R-S4-6, R-O-1 | Yes |
| FM-20 Hallucinated dependency | R-S5-1, R-S5-2 | Yes |
| FM-21 State loss | R-T-1, R-T-2, R-T-3, R-T-5, R-I-1, R-I-2, R-I-6, R-I-13, R-S4-1, R-S4-2, R-S4-5, R-S5-11, R-O-1 | Yes; Later: R-S5-11 |
| FM-22 Loop drift | R-T-1, R-O-5, R-O-12, R-F-10, R-F-11, R-F-12 | Yes; Later: R-F-10, R-F-12 |
|---|---|---|
| FM-01 Abstraction | R-S3-2, R-S3-3 | Yes |
| FM-02 Load-bearing hack | R-S0-5, R-S1-4, R-S3-4, R-S3-11, R-S6-6 | Yes |
| FM-03 Style and pattern | R-S3-6, R-S5-8, R-S5-10, R-F-7 | Yes; Later: R-S5-8 |
| FM-04 Tech debt mixing | R-S3-5, R-S5-4 | Yes |
| FM-05 Scope creep | R-I-3, R-I-11, R-S0-2, R-S0-7, R-S1-8, R-S2-10, R-S3-12, R-S3-18, R-S4-1, R-S5-1, R-S5-2, R-S5-4, R-S6-6, R-S6-8 | Yes; Later: R-S6-8 |
| FM-06 Jumps to implementation | R-S0-1, R-S2-1, R-S2-2, R-S2-3 | Yes |
| FM-07 Question noise | R-S2-5, R-S2-6, R-S2-7, R-S2-8, R-S2-9, R-S2-12, R-H-1, R-H-3, R-H-4, R-O-5 | Yes |
| FM-08 Missing scenarios | R-S2-2, R-S2-4, R-S3-7 | Yes |
| FM-09 Parallel fatigue | R-I-8, R-I-10, R-S0-7, R-S1-10, R-S2-9, R-S2-12, R-S4-6, R-S7-5, R-H-1, R-H-3, R-H-4, R-O-4, R-O-5, R-O-6, R-O-8 | Yes; Later: R-S1-10, R-S7-5, R-O-8 |
| FM-10 Unreviewable diff | R-T-2, R-S0-6, R-S1-2, R-S3-11, R-S3-14, R-S6-1, R-S6-2, R-S6-3, R-S6-8, R-S7-1, R-S7-2, R-S7-6, R-H-8, R-H-10, R-O-1, R-O-5, R-O-6 | Yes; Later: R-S6-8, R-S7-1, R-S7-2, R-S7-6, R-H-10 |
| FM-11 Filler tests | R-S3-9, R-S4-7, R-S5-1, R-S5-8, R-S6-2, R-O-5 | Yes; Later: R-S4-7, R-S5-8 |
| FM-12 Filler comments | R-S4-7, R-S5-8 | No, all Later |
| FM-13 Missing comments | R-S4-7, R-S5-8 | No, all Later |
| FM-14 Unknown impact | R-S0-5, R-S1-3, R-S1-6, R-S1-10 | Yes; Later: R-S1-10 |
| FM-15 Contract drift | R-S2-8, R-S3-7, R-S3-18, R-S4-2, R-S5-1, R-S5-5 | Yes |
| FM-16 False rigor | R-I-12, R-S0-1, R-S1-2, R-S2-1, R-S2-3, R-S2-11, R-S3-10, R-S3-18, R-O-10, R-O-11, R-F-2, R-F-3, R-F-5, R-F-8, R-F-12 | Yes; Later: R-O-10, R-O-11, R-F-3, R-F-8, R-F-12 |
| FM-17 Memory rot | R-T-3, R-T-4, R-T-6, R-I-4, R-I-9, R-S1-7, R-O-10, R-F-1, R-F-2, R-F-4, R-F-5, R-F-6, R-F-7, R-F-9, R-F-10 | Yes; Later: R-I-9, R-O-10, R-F-9, R-F-10 |
| FM-18 Agent-only review | R-T-5, R-I-11, R-S3-15, R-S5-8, R-S6-1, R-S6-7, R-S7-3, R-S7-4, R-S7-6, R-O-11, R-F-3, R-F-8, R-F-11 | Yes; Later: R-S5-8, R-S7-3, R-S7-4, R-S7-6, R-O-11, R-F-3, R-F-8 |
| FM-19 Slow failure | R-I-1, R-I-2, R-I-4, R-I-6, R-I-8, R-I-13, R-S4-5, R-S4-6, R-O-1 | Yes |
| FM-20 Hallucinated dependency | R-S5-1, R-S5-2 | Yes |
| FM-21 State loss | R-T-1, R-T-2, R-T-3, R-T-5, R-I-1, R-I-2, R-I-6, R-I-13, R-S4-1, R-S4-2, R-S4-5, R-O-1 | Yes |
| FM-22 Loop drift | R-T-1, R-O-5, R-O-12, R-F-10, R-F-11, R-F-12 | Yes; Later: R-F-10, R-F-12 |

Coverage notes the generator cannot derive: FM-01 and FM-03 rely on graders that are advisory until calibrated; FM-11 has planned purpose at S3 and S6 in the initial version and filter enforcement Later; FM-12 and FM-13 are carried in the handoff and enforced Later; FM-14 has the outbound import scan and the optional callers list initially, with inbound coverage a declared blind spot where the list is absent, and build-graph methods Later; FM-15 is caught by source-level declaration extraction where a grammar is configured and is a declared blind spot otherwise, with inherited members and binary compatibility outside its reach; FM-22 has the objective rule and the fence initially and the agent-drafted loop they bound Later.

Principles: P1 is cited by every queue, question, gate, and measure requirement. P2 by the factory-as-code rows and the rubric rows. P3 by S2. P4 by the record, S1, S2, S3, S4. P5 by S1, S3, S5. P6 by S0, S2, S3, S4, S5. P7 by S0, S1, S4, S5, S7, observability. P8 by the tagging requirement and the improvement pass. P9 by the summary, the plan, the packet, and the ledger. P10 by every gate, budget, allowlist, and fence requirement. P11 by the stance in section 1, the factory API, the stop operation, the human signals, the observer pass, and the objective rule.

## 10. Later items, collected

Everything marked Later above, in one list, so the initial version's edges are visible. Rows: R-I-9, R-S1-10, R-S4-7, R-S5-8, R-S5-11, R-S6-8, R-S7-1, R-S7-2, R-S7-3, R-S7-4, R-S7-5, R-S7-6, R-H-10, R-O-8, R-O-10, R-O-11, R-F-3, R-F-8, R-F-9, R-F-10, R-F-12. In words: S7 in full, meaning check-run tracking, failure summaries, merge detection, post-approval invalidation, the close survey, and review comments as human signals; enforcement of the comment rules and the test filter through the S5 advisory tier; S1 fan-out; build-graph, catalogue, and trace-derived impact methods (R-S1-3); a formal solver check at S2 (R-S2-3); a compiled-API contract comparison such as japicmp (R-S5-5); stacked pull requests; enforcement of a second approver and of required reviewers (R-S0-5, R-S3-15, R-S6-6); Confluence sync; dashboards; the "not touched" measure; the read-only factory MCP server; the observer pass and calibration; the eval harness and eval-gated adoption, branch protection on `factory/`, the improvement pass, and benchmarks; the bloat signal; and, from `docs/prd/inputs.md`, durable workflow engines, containers per stage, and a persistent code graph beyond codegraph. LaunchDarkly, Grafana, and OpenSearch stay out of the factory (D25). Added in v0.7: the sliced advisory pass, R-S5-11.

## 11. Decisions this document makes beyond the charter

Each is a judgment call the charter does not settle. Veto here, not in the requirements. Calls 1 to 19 were accepted by the owner on 2026-09-04; 9, 10, and 15 were rewritten for the amended D20 and stood. Calls 20 to 28 were accepted on 2026-09-04 after the v0.5 review. Calls 29 to 35 record the owner's answers to that review's questions, decided on 2026-09-04.

1. **Artefacts are files with database pointers**, not blobs in SQLite, so humans and agents read the same thing and versions diff.
2. **S0 is scripts except the scrutiny draft**, which configuration can switch off, and ticket type comes from the Jira issue-type mapping with human confirmation, so no agent judgment is spent before eligibility.
3. **The tier matrix and the final-tier rule** are the values in section 8. They are guesses until pilot data replaces them.
4. **The Heavy size gate is tighter than Standard**, 200 against 300, because reviewer attention per line matters more on Heavy tickets.
5. **The initial formalisation check is an agreement check** over N independent restatements, not a solver. It catches ambiguity by disagreement, which is the Kiro mechanism without the SMT step.
6. **"Consequential" is defined** as touching a contract, a migration, a permission boundary, a public interface, the rollout strategy, or a sensitive path. Everything else gets a default.
7. **The S2 split threshold is 60 percent of the size gate**, so a split is proposed before the plan is written rather than after the diff exists.
8. **Contract diff is done by language tooling where it exists** and is otherwise a declared blind spot, rather than an LLM judgment.
9. **S4 is automated from the first version** through the primary runtime under the D14 bounds, because its SDK makes a bounded, recorded implementation cheap and the human still gates at plan approval and at review. The hand-off and hand-back stay a protocol so an external implementer remains possible, and a missing deviation list is a blind spot, not a block.
10. **The review comes before the pull request.** The engineer reviews the packet with the diff appended inside the factory; only on approval does a script push the branch and open the pull request with the packet as its description. Nothing unreviewed reaches GitHub, and the initial version ends there.
11. **Tags are human-written**, except `stale_index` and `escalation`, which the factory writes. Checks name a likely catalogue id for the human to confirm; they do not tag.
12. **Any commit pushed after `pr_open` invalidates the approval** and reruns S5 (R-S7-4, Later). No exceptions per ticket.
13. **A baseline of 10 recent tickets** is computed before the first factory ticket, from PR history and one retrospective, for the measures history can yield.
14. **The reporting-rule requirement cites the measures it protects** rather than a failure mode of its own. Gaming of measures is not a catalogue entry, and this document proposes none.
15. **S7 is Later.** In the initial version no agent runs on a ticket after S4; the observer pass, when it arrives, runs over the record, not on the ticket. S7 failure summaries use an agent at Light budget, read-only.
16. **Every run is scored at pilot scale**, once the observer pass runs. Sampling is for fleets. At one to three tickets in parallel the cost is small and every score is calibration data.
17. **Stop is the only mid-run intervention.** Steering is left out on purpose: it breaks reproducibility from the record and requires a watching human.
18. **`factory/` lives in this repository, the factory repository,** alongside `docs/`, so proposals can be pull requests and the adoption gate can be a check when they arrive (R-F-9). Until then the engineer commits directly with the reason in the message (R-F-4).
19. **The first benchmark per stage decides D5 for that stage**, after that stage's graders are calibrated. Until then the manifest carries the runtime the engineer starts with, recorded on every run.
20. **Close means `pr_opened` in the initial version.** Entering `pr_opened` sets `closed_at`; windows, exports, and cadences key off it. Merge is observed only when S7 arrives. This is what makes every context measure computable before S7.
21. **The self-improvement scaffold ships as structure only.** The `score`, `proposal`, and `benchmark` tables, the `evals/` and `benchmarks/` directories, the grader-model manifest field, and the eval directory per skill exist from day one (C6). The observer pass, calibration, the eval harness, eval-gated adoption, branch protection, benchmarks, and the improvement pass are Later, switching on after the first exported ticket. Grader-verified rubric lines are advisory until calibrated. D20's criterion, rubrics that have survived real tickets, is what turns them on.
22. **A second approver is named, not enforced.** The pilot has one engineer. Owners from sensitive and discretion paths appear on the plan, the packet, and the queue item; GitHub enforcement is Later.
23. **Rejection at S0 carries no tag.** It is mechanical and the missing item is its reason. Tags cover the human decisions against the factory's output: override, send back, request changes, abandon, plus the two the factory writes.
24. **Escalations are their own queue-item kind**, not questions, because they carry a failure history rather than options and a default.
25. **Rubric lines are requirement rows.** Rubric files are generated from the rows named in each stage's rubric list, and `score.dimension` is a requirement id. When the file and the row diverge, the file is regenerated.
26. **Retired ids are never reused** (section 13). References in research packets and earlier revisions keep resolving.
27. **The reliability unit at S4 is the plan task.** One `stage_run` per task, `attempt` per (stage, plan item), refusals excluded. That is what D28's first-attempt share counts.
28. **The engineer sends back; the engineer does not patch.** A red check or a request for changes returns the ticket to S4 with a note. No change to the branch happens outside a stage run, so the record stays complete (C5).
29. **The plan carries fixed tables.** Scope, dependencies, contracts, tasks, test strategy, and size are tables with named columns (R-S3-18, section 8), inside the plan file rather than a sidecar, so the human reads one document and the scripts read no prose.
30. **A task passes by its own commands.** Every plan task names the commands that prove it and their expected results; the runner executes them and sets `pass`; the agent's opinion sets nothing (R-S4-5). This keeps the initial success measure outside the self-grading anti-goal.
31. **Contract diff is source-level and generic.** Public declarations are extracted with tree-sitter at `base_sha` and at head and compared with the plan's contracts table; it is a factory script, works for any language with a grammar, and needs no build. A compiled-API comparison such as japicmp is a Later upgrade, not a prerequisite (R-S5-5).
32. **The human can send a ticket back to any earlier stage** from any open item, with a note the rerun receives (2.3, R-H-4). Stop and abandon are no longer the only between-gate interventions; P11 is met by the send-back, not by steering a running agent.
33. **Callers of the pilot service come from an optional hand-written list.** `service-callers.yaml` supplies inbound impact where the engineer has written it; otherwise the brief says "callers unknown" as a blind spot and never implies coverage (R-S1-3).
34. **The factory lives in this repository.** `factory/` and `runs/` are here; the pilot service is a separate checkout, and worktrees are created under `runs/`, never inside the service repository (sections 7 and 8).
35. **Restatements are child runs.** The S2 agreement check's fresh-context invocations are `stage_run` rows with `parent_run_id`, counted in the S2 budget and excluded from the first-attempt measure, so C5 holds and the reliability measure is not distorted (R-S2-3).
36. **Questions are written for a reader who has opened nothing.** No factory-internal identifiers in a question or its options, and every option carries its consequence (R-S2-14). From the v0.6 review round: the one question the owner sent back was well-formed and badly worded.
37. **Plan rows cite criteria.** Tasks and tests carry `AC-n` ids and a script proves every criterion is served by a task and a test (R-S3-19), the way section 9 proves every failure mode is served by a requirement.
38. **The advisory pass stays single until it truncates.** Slicing by concern with script consolidation is R-S5-11, Later.
39. **The factory's own build runs through the process.** Each build ticket gets a hand-written brief and plan tables under `docs/build/`, checked by the factory's scripts as each lands, so the first pilot ticket is not the first run of the process. Java-specific checks wait for the pilot service (D10, D32).

## 12. Open questions

- **QP-5, open.** Merge detection by polling, at the runner cadence in section 8. A webhook waits for a reachable endpoint. Later, with S7.

Closed on 2026-09-04, each into its home: QP-1 into the Java scripts row of section 8; QP-2 into the ticket-types entry of section 8 (the field mapping is filled by hand before the first run, not learned from it); QP-3 into the sensitive-paths entry; QP-4 into D20 and call 9; QP-6 into call 10; QP-7 into R-F-3 (a model other than the author's; a different family where the runtimes offer one); QP-8 into call 18. R10, R10b, and R10c are done; findings in `docs/prd/inputs.md` section 5, selections in section 8 here and inputs section 6.

## 13. Retired requirement ids

Retired in v0.5. Each id names the row that now carries its obligation. Ids are never reused.

| Retired | Now in | Retired | Now in |
|---|---|---|---|
| R-T-7 | R-S2-12 | R-S3-17 | R-S3-11 |
| R-T-8 | R-T-1 | R-S4-3 | `deviation` entity, R-S4-2 |
| R-I-5 | R-I-4 | R-S4-4 | R-I-11 |
| R-I-7 | R-I-1 | R-S4-8 | R-S4-7 |
| R-S0-3 | R-S0-2 | R-S5-3 | R-S3-12 |
| R-S0-4 | R-S0-2 | R-S5-6 | R-I-11, S5 preamble |
| R-S1-1 | R-I-12 | R-S5-7 | R-S5-1 |
| R-S1-5 | R-S1-6 | R-S5-9 | R-F-8 |
| R-S1-9 | R-I-11 | R-S6-4 | R-S6-1, R-S3-11 |
| R-S2-13 | R-S2-12 | R-S6-5 | R-T-5, R-S6-7 |
| R-S3-1 | R-I-12 | R-S6-9 | R-H-1 |
| R-S3-8 | R-I-12, D16 | R-H-2 | R-H-3 |
| R-S3-13 | R-T-6, S3 touchpoint | R-H-5 | R-H-4 |
| R-S3-16 | R-T-5, R-S3-15 | R-H-6 | R-H-1 |
| R-H-7 | R-H-1 | R-H-9 | R-S2-11 |
| R-O-2 | R-T-5 | R-O-3 | R-O-1 |
| R-O-7 | R-O-5, measure table | R-O-9 | R-T-4, R-F-3 |

## Revision history

- **v0.7, 2026-09-04.** Three additions from the v0.6 dry run of the process on this document (calls 36 to 39): question wording for a reader who has opened nothing (R-S2-14, `options` carry consequences), criterion ids on restated criteria (R-S2-1) with a two-way traceability check between criteria, tasks, and tests (R-S3-19, R-I-12, section 8 plan tables), and the sliced advisory pass as Later (R-S5-11). Section 9 regenerated. Cites charter v0.9 and inputs v0.8.
- **v0.6, 2026-09-04.** Review of v0.5 against charter v0.9 for the initial scope, five slices and 75 findings, verified and answered by the owner. Plan gained fixed tables and R-S3-18; S4 tasks pass only by their validation commands, run by the runner (R-S4-5); contract diff is source-level tree-sitter extraction with japicmp Later (R-S5-5); dependency diff uses the build tool's resolved list; send-back to any earlier stage from any open item, with `escalated` able to return to `planning` (2.3, R-H-4, R-T-6); impacted services split into the outbound scan and an optional callers list (R-S1-3, `service-callers.yaml`); `factory/` and `runs/` fixed to this repository with the pilot service as a separate checkout; S2 restatements recorded as child runs (`parent_run_id`, R-S2-3); the runtime adapter is R-I-13; `failure_history` and `baseline_measure` defined; `ticket_source` artefact; `fail`, `blocked`, and failed `pr_open` paths in 2.3; first-attempt measure excludes `blocked` and child runs; wait, question, cost, and touchpoint computations corrected; list view gains scrutiny edit, rubric-inspection close, stop, send-back, and ticket-addressed incident and abandon; runner gains stop, show, report, export, import; digest scheduler, index seed, configuration file map, and `base_sha` timing named. R-T-3 scoped to the append-only set. Calls 29 to 35 added. 102 rows, 82 Initial. Cites charter v0.9 and inputs v0.8.
- **v0.5, 2026-09-04.** Review pass with four audits (conflicts, redundancy, initial scope, citations). Added the one-page initial version. Every Version cell is now Initial or Later; the self-improvement scaffold moved to Later as behaviour and stayed as structure (call 21). Record gained `queue_item`, branch and worktree fields, `required_approvers`, `baseline`, `plan_item`, `cost_provenance`, `blocking`, `source`, the `refused` outcome, and `pr_opened` as a close reason (call 20). State table gained exits from `escalated` and `checks` and closes at `pr_opened`. 34 duplicate rows retired into their homes (section 13), two rows added (R-I-11 forbidden tools, R-I-12 structural completeness): 132 rows became 100. Rubric lists now name requirement ids. Section 9 is generated. Section 8 gained the tool attachment table and day-one decisions. Calls 20 to 28 added. Cites charter v0.9 and inputs v0.7.
- **v0.4, 2026-09-04.** Scope of the initial version amended with charter D20: S4 automated (R-S4-5, R-S4-6, R-I-6 Initial), review before the pull request (R-S6-3, new `pr_opened` state, `pr_open` script), S7 Later. Codegraph attached as its MCP server with one tool by the owner's exception. Section 11 items 9, 10, 15 rewritten. Cites charter v0.8 and inputs v0.6.
- **v0.3, 2026-09-04.** Owner named. The nineteen calls in section 11 accepted. Section 12 closed except QP-5. Section 8 gained pilot eligibility (D32) and the initial-version tooling table after research packets R10 and R10b. Cites charter v0.7 and inputs v0.5.
- **v0.2, 2026-09-04.** Absorbed the Warp closed-loop article against charter v0.6. Added the stance under P11. Ticket record gained `manifest_hash`, `aborted_human`, and the `score`, `human_signal`, `proposal`, and `benchmark` entities (R-T-8). Stage interface became the factory API with stop, a later read-only MCP server, and the parallel ticket limit (R-I-8 to R-I-10); the manifest now names runtime, model, and grader model (R-I-4, D31). S7 records PR review comments as human signals (R-S7-6). Observability gained the observer pass, the calibration sample, the objective rule, and the reliability and context measures (R-O-10 to R-O-12, R-O-5 rewritten). Factory as code gained the git and PR path, the improvement pass, the fence, and benchmarks (R-F-9 to R-F-12, R-F-8 amended). Configuration gained the parallel limit, observer, window, fixture, and grader-model values. FM-22 added to traceability.
- **v0.1, 2026-09-04.** First draft from charter v0.5, PRD inputs v0.2, and both research syntheses. Opens with the ticket record. Rubric lines for S0 to S6. Configuration defaults answering Q10 to Q12. Traceability over FM-01 to FM-21.
