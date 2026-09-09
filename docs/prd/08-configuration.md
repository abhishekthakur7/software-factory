# 8. Configuration values and day-one decisions

Part of the [Software Factory PRD](prd.md). The index holds the version, the reading rules, and the map from section numbers to files.

Not requirements. D42's accepted pilot defaults, owned by the engineer, live in `factory/config/`. The day-one decisions at the end settle the mechanics a builder meets first; they are architecture in the small and stay out of the requirements.

**Service tiers** (D42). Hand-maintained `service-tiers.yaml`: service to T1 (customer-facing, critical), T2 (important), T3 (internal or tooling). Filled for the pilot service first.

**Pilot eligibility** (D32). One T2 service, written in Java. Eligible ticket type at S0: `small_feature`. Any other type is rejected at S0 with "outside pilot scope" until the owner widens the list. The provisional tier for every pilot ticket is therefore Standard, unless R-S0-5 raises it.

**Ticket types and Jira fields.** `bug`, `small_feature`, `feature`, `refactor`, `config_or_docs`. Mapping from Jira: Bug to `bug`; Story to `feature`, or `small_feature` when the estimate is at or under the configured point value; Task to `config_or_docs` or `refactor` by label; Epic rejected at S0 with "needs child tickets". Human confirms at eligibility. `ticket-types.yaml` also names the Jira fields for acceptance criteria, owner, parent, and service (a component or label), filled by hand from one pilot ticket viewed in Jira before the first run (QP-2).

**Provisional tier matrix** (D11).

| Service tier | bug | small_feature | feature | refactor | config_or_docs |
|---|---|---|---|---|---|
| T1 | Heavy | Heavy | Heavy | Heavy | Standard |
| T2 | Standard | Standard | Heavy | Standard | Light |
| T3 | Light | Light | Standard | Standard | Light |

**Final tier rule** (S1). Raise one level when services touched is two or more, or files touched exceeds 10, or unknowns are three or more. Sensitive paths raise to Heavy per R-S0-5. Never lower automatically.

**Size gate** (D42). Light 300, Standard 300, Heavy 200 changed lines (definition in R-S3-12). Heavy is tighter because reviewer attention matters more there, not less. Generated paths and lockfiles to exclude are listed in `project.yaml`.

**Split threshold at S2.** 60 percent of the tier's size gate as estimated lines, or more than 10 files.

**Budgets per stage run** (D14, D42), in `tiers.yaml`. Placeholders until three pilot tickets have run, then set from their records. Light: 400k tokens, 20 minutes. Standard: 800k tokens, 40 minutes. Heavy: 1.5M tokens, 60 minutes. S4, per ticket across all its task invocations, on the same placeholder basis: Light 1M tokens, 45 minutes; Standard 2M tokens, 90 minutes; Heavy 4M tokens, 150 minutes. S5 wall clock counts against no budget; the build commands carry their own timeout.

**Agreement check N** (R-S2-3). 3.

**Question ceiling as a signal, not a cap.** Light 2, Standard 6, Heavy none. Exceeding it queues a `rubric_inspection` item; it never suppresses a question.

**Length limits.** Brief summary 300 words. Plan prose: Light 800, Standard 1500, Heavy 2500 words, excluding tables; plan tables: Light 40, Standard 80, Heavy 150 rows in total; first page is the first 60 lines. Reasoning summary 200 words. Instruction files 300 lines.

**Plan tables** (R-S3-18). Fixed columns, validated by R-I-12. Readiness (R-S3-21): `condition` from the fixed keys `restatement_agreed`, `questions_closed`, `impact_evidence`, `risk_map`, `linked_sources`, `size_gate`, `reviewer_set`, a missing key being a missing required row; `status` (`pass`, `blind_spot`, `pending`); `source_artefact`, the criteria, brief, question set, assumption log, risk-map artefact, or the plan table the row rests on; `hash`, that artefact's hash or, for a plan table, the canonical digest of that table alone, never the plan hash; `waiver_id` for a `blind_spot` row; `note`. The readiness table is derived and does not count against the plan table ceiling. Scope: `path`, `action` (`touch`, `not_touched`, `discretion`), `reason`. Dependencies: `package`, `from_version`, `to_version`, `kind` (`add`, `change`, `remove`), `reason`; an empty table is written explicitly. Contracts: `unit`, `kind` (function, module, endpoint, event, serialized shape), `source_declaration`, `input`, `output`, `errors`, `side_effects`, `invariants`, `authorization`, `ordering_concurrency`, `transaction_persistence`, `compatibility`, with each contract field carrying `unchanged`, `changed`, or `unknown` plus evidence. Tasks: `id`, `title`, `depends_on`, `criteria`, `files`, `validation_recipe`, `validation_args`, `expected_result`, `no_behaviour_change`; at least one validation row per task. Test strategy: `test`, `action` (`add`, `change`, `remove`), `size` (small, medium, large, or `none` with the reason in `proves`), `criteria`, `proves`; a `change` or `remove` row names a base test, and its `criteria` cell holds the `AC-n` ids or the `no_behaviour_change` task id it serves. The two `criteria` columns list `AC-n` ids and R-S3-19 checks them in both directions. Size: `estimated_lines`, `estimated_files`, `basis`, `justification` (empty unless over the gate).

**Ordinary stage retries.** One fresh rerun after `fail` or `infrastructure_failure`, then escalation. S4 verification failures instead use D14's three-attempt bound; infrastructure retries never consume it.

**Fix rounds** (R-S4-9). 2 per ticket, in `limits.yaml`; each round runs inside the per-ticket S4 budget.

**Tool-result inline limit** (R-I-17). 200 lines or 8 KB, whichever is reached first, in `limits.yaml`; the excerpt is the first 40 and the last 20 lines, truncated to 4 KB at each end; a non-text result is represented by size, media type, and digest only.

**Maintenance source** (R-S0-9, Later). `maintenance.yaml`: enrolled skills, paths, schedule, off-peak window, and the open-ticket cap, default 3.

**Risk map.** Churn window 12 months. Ownership concentration is the top author's share of commits in the window; under 40 percent means no clear owner. Named entries are the top decile of churn times file size, plus every file with no clear owner.

**Test mix target.** 80 small, 15 medium, 5 large, by count, over `add` rows; the large share applies only where the repository registers an end-to-end recipe.

**Guardrail metrics in the rollout section.** At most 12.

**Digest cadence** (D42). Twice per working day, Monday to Friday, 10:00 and 15:00 local, from a launchd entry (cron on Linux) installed by setup that runs `factory digest`; times, weekdays, and channel under the `digest` key of `project.yaml`, channel chosen by the engineer.

**Index staleness default.** 90 days since `last_verified`, or any commit on the base branch touching the entry's `paths`.

**Index seed.** Two entries written by hand before the first run, each with `last_verified` set at seeding: the pilot service's conventions, and its sensitive paths with their owners; a third, `caller`-kind entry joins them where the pilot service's callers are known.

**Grader calibration minimum sample.** 20 items graded by the engineer before a grader may block.

**Sensitive paths.** `sensitive-paths.yaml`: glob to owner. Seeded with the pilot service's authentication, authorisation, payments, secrets, migration, and infrastructure directories. Where the repository has CODEOWNERS, it wins; the file adds owners only for paths CODEOWNERS does not cover (QP-3).

**Impact methods.** `project.yaml` lists the outbound methods enabled per service; the pilot service has `import_scan` (Maven or Gradle dependency tree). Inbound callers come from context index entries of kind `caller`, hand-written and optional, with `last_verified` set at seeding; absent means "callers unknown" in the brief (R-S1-3).

**Baseline set.** The ten most recent completed, agent-assisted tickets matching the pilot service and admitted ticket type before R-O-6's retrospective cutoff, with no discretionary omissions. When they cannot provide ten comparable observed revision values, prospectively observed non-factory current-process tickets complete a separately delimited supplemental cohort. Both cohorts freeze before Milestone B; no factory result can influence their membership.

**Runner cadence.** Later, with S7: poll GitHub every 5 minutes while any ticket is in `pr_checks`.

**Parallel tickets** (D28). 1 in the initial version. R-O-13 is the only path to 2 and then 3; editing configuration without a recorded passing graduation decision is refused.

**Observer pass** (Later). Sample rate 100 percent at pilot scale. Cadence: on every ticket close for that ticket's runs, and every 5 tickets for a window pass. Cost cap per window pass: 10 percent of the window's ticket cost.

**Improvement window** (Later). The last 20 closed tickets or the last 30 days, whichever is smaller.

**Benchmark fixture set** (Later). 5 to 10 exported tickets per stage, chosen to span tiers.

**Initial-version tooling** (D24, D31; inputs section 6, where the reasons live). The manifest carries these by name; nothing below is a requirement.

| Concern | Selection | Decided by |
|---|---|---|
| Agent runtime | Cursor SDK in its local runtime on the pilot host, primary (call 48); Claude Code CLI and Agent SDK secondary. One custom agent definition per agent stage, each naming its model; the grader model per stage is never the author model (C4). Before the first run, the exact trust-profile route and its security plus legal/data-governance approvals pass R-T-9; Privacy Mode and a spend limit do not substitute | Owner plus security and legal/data-governance approvers |
| Execution boundary | An ephemeral container or equivalently restricted OS identity satisfying R-I-14, identified by immutable image or policy digest and tested on the pilot host before Milestone B | Owner plus security approver |
| Code navigation | codegraph (colbymchenry), attached as its MCP server with the single default tool, the owner's exception to the first-party rule; full re-index of the ticket worktree by `scripts/tools/reindex` before every S1 run, with `.codegraph/` inside the worktree and never committed, since the initial version never observes a merge (FM-17) | Owner |
| Evals and benchmarks | Initial smoke/conformance suite under R-F-14; Later calibrated quality harness and benchmarks under R-F-3 and R-F-12. Real-ticket fixtures enter only after governed export and redaction review | Owner |
| Ticket source | A Jira key, read through the Atlassian MCP server; Later, tickets created by an enrolled maintenance skill (R-S0-9) | Owner |
| Question digest | The official Slack MCP server for posting; a CLI list view | Owner |
| MCP servers | First-party only: GitHub, Atlassian, Slack, plus codegraph by exception. AWS has no pilot access. No other third-party MCP server; other tools attach as scripts | Owner, enterprise rule |
| Run state, tracker, ledger | One SQLite database in WAL mode holding the section 2 tables; a Python runner | Recommended |
| PR publication | The `pr_create`/`pr_update` outbox worker: revalidate the canonical review subject and quorum, compare the expected remote head, and create or update one draft pull request with `pr_body` as its description | Recommended |
| PR checks, Later | GitHub MCP server in read-only mode with the `actions` and `pull_requests` toolsets | Recommended |
| Language and security scripts | `dep_verify` runs a typed resolved-dependency recipe at base and head and compares it with the plan; `source_declaration_diff` extracts public/protected declarations with tree-sitter and never claims behavioural or binary compatibility; `behavior_contract_evidence` checks evidence links only; `security-checks.yaml` pins the pilot repository's secret, static-analysis, dependency-vulnerability and licence-policy recipes, rule/database versions, thresholds, suppressions and unavailable-feed policy. japicmp or Revapi is a Later Java compatibility upgrade (R-S5-5) | Owner plus security approver |

**Tool attachment per stage** (C1, R-I-3). Carried by the manifest as each stage's `tool_allowlist`, with no separate `tools.yaml` (owner decision of 2026-09-10); initial values:

| Stage | Attached | Writes |
|---|---|---|
| S0 | Atlassian (read) | Ticket row only, by script |
| S1 | Atlassian (read), codegraph, repository read | Brief only |
| S2 | Repository read; the `ticket_source` and `brief` artefacts as inputs | Criteria, questions |
| S3 | codegraph, repository read | Plan |
| S4 | codegraph, repository read and write confined to the sandboxed ticket worktree, named typed recipes, no credential beyond the scoped runtime key of R-I-14 and no usable push authority | The ticket branch, locally |
| S5 | None; the project's and the security recipes inside a clean sandbox with disposable build-output/cache layers; the factory's own check scripts run on the trusted side over the captured evidence and the immutable checkouts | Check evidence only; never the ticket source or branch |
| S6 | None; after S6, the trusted `pr_create`/`pr_update` outbox worker alone obtains the scoped GitHub credential | Same draft pull request, only after full approval quorum |
| Digest script | Slack (one post tool) | The digest |

The same allowlist applies to every tier in the initial version; the manifest keys it by stage and tier with a `default` entry (R-I-4).

**Configuration files.** `tiers.yaml`: tier matrix, final tier rule, size gate, split threshold, question ceiling, length limits, budgets per stage and tier. `limits.yaml`: agreement check N, risk-map window and ownership threshold, test mix, guardrail limit, index staleness, calibration sample, parallel tickets, stage retries, fix rounds, tool-result inline limit. `ticket-types.yaml`: types and Jira fields. `service-tiers.yaml`, `artifact-to-service.yaml`, and `sensitive-paths.yaml`: impact and ownership evidence. `owners.yaml`: the R-F-13 roles and authority policy. `trust-profile.yaml`: source scopes, data classes and join rules, routes, route-authorised sanitizer implementation/rule hashes and source/target classes, providers/MCP endpoints, processing/storage/residency/readers, retention/export, guard policy, approval slots and immutable evidence. `waiver-policy.yaml`: the content-addressed conditions, authority, scope, expiry and evidence rules for semantic and cross-check blind spots; check-specific policy may be named from here. `incident-policy.yaml`: severity, attribution, disposition and remediation rules. `pricing.yaml`: dated provider/model token prices and currency, used only under the cost-provenance rule. `sandbox.yaml`: OS policy digest, runtime sandbox configuration and proxy allowlist hashes, worktree, disposable copy and per-run directory locations, environment-name allowlist, and the loopback-only egress rule. `command-recipes.yaml`: R-I-16 recipes, each test recipe carrying its `level` (unit, integration, end-to-end) and added by the engineer by hand outside any ticket, an end-to-end entry only where the repository already has such a suite, and the test-file globs `base_test_diff` reads, covering test sources, fixtures, snapshots, and helpers. `security-checks.yaml`: required local security recipes, rule/database digests, thresholds, suppressions, unavailable-feed behavior and check-specific waiver-policy references. `project.yaml`: source checkout, target branch, recipe ids, tree-sitter grammars, JDK/toolchain digest, generated paths, the `digest` cadence/channel key, and impact methods. `tools.yaml`: attachment table. `runtime.yaml`: approved runtime and exact adapter/model identities, and the runtime key's role name, scope and spend cap, never its value; route authority comes from the trust profile, not this file. `maintenance.yaml` (Later): enrolled maintenance skills, paths, schedule, window, and cap.

**Day-one decisions.**

- **Runner invocation.** `factory advance <ticket>` runs stages until the next human touchpoint and exits, holding a renewable lease on the open `stage_run`. `factory run <stage> <ticket>` runs one stage. `factory queue` and `factory act` are the list view; `act` records the decision and resumes only when that action permits it. `factory pause`, `factory resume`, and `factory stop` implement R-H-13 and R-I-8. `factory refresh-base`, `factory migrate-manifest`, `factory show`, `factory report`, `factory export`, `factory import`, `factory purge`, `factory tag`, and `factory abandon` complete R-I-1. The manual PR outcome of R-H-11 is `factory act` on the `pr_outcome` item; there is no separate outcome command. The digest is `factory digest` under the scheduler entry named with the cadence. There is no daemon in Initial; outbox reconciliation runs before each command that may advance state.
- **Project location and ticket checkout.** `project.yaml` names a read-only source checkout outside this repository, the target branch, recipe ids, tree-sitter grammars, and the pinned JDK/toolchain. At eligibility the trusted runner fetches the target, records `base_sha`, and creates an isolated ticket clone and worktree under `runs/tickets/<id>/`; it is not a linked worktree sharing remote configuration with the engineer's checkout. The sandbox has neither a credential nor a usable push URL. S1, S2 and S3 read that checkout, S2 read-only as the attachment table says; S4 alone writes its worktree; S5 reads disposable copy-on-write copies of the immutable base and head checkouts, each with its own build/cache directories (R-I-14). `refresh-base` is the explicit invalidating human transition in R-S5-12. The checkout is removed only after `merged`, `abandoned`, or `rejected` and the retention/export policy permits it; the branch remains until governed cleanup. `ticket.id` is the source issue key.
- **Runtime mapping.** An agent definition is the runtime's agent or rules file; a skill is the stage prompt; the rubric is attached as an input file; the allowlist is the runtime's MCP configuration plus its native tool permissions, passed inline per invocation with no user- or project-level setting source loaded, denied where the stage has no write role (R-I-3). The adapter that does this mapping and fills the ledger is R-I-13.
- **Blocking questions and reruns.** A run that raises a blocking question ends `blocked` after writing everything that does not depend on the answer (2.3); when the question is answered the runner reruns the stage from the record with `attempt + 1`, keeping the independent sections. The same holds for escalations and for send-backs, whose note the rerun receives.
- **Manifest hash.** The hash of `manifest.yaml` as committed, which in turn carries the hash of every referenced file. An uncommitted edit fails validation (R-F-1).
