# Implementation review findings: Milestones A, AB and B

| | |
|---|---|
| Status | Draft v0.4 |
| Date | 2026-09-10 |
| Owner | Abhishek Thakur |
| Reviewed against | `docs/prd/prd.md` v0.18 and its parts; `docs/design/hld/README.md` v0.3 and the L1/L2 files; `docs/design/milestones.md` v0.7 section 3 and Appendix A; `docs/design/tickets/A.md`, `AB.md`, `B.md` |
| Reviewed code | `runner/`, `factory/`, `tools/`, `runner/tests/` at commit 332b84c (tree clean) |
| Out of scope | T-B-06 (live connections, `factory doctor`, runbooks) and T-B-07 (the dry run on the pilot host), not yet built; every PRD row marked Later |
| Test baseline | `uv run pytest runner/tests -q`: 1857 passed, 4 skipped, 14m44s at v0.1; 1882 passed, 4 skipped, 15m08s after v0.4. The four skips are the loud real-host skips (Cursor key, two Atlassian Keychain reads, the live closing run) |

## 1. How this review was done

Nine reviewers, each holding one slice of the design, read the slice's PRD rows, HLD components and crossings, milestone block shapes and ticket acceptance criteria, then read the code and tests that claim to satisfy them. Every finding cites the spec sentence and the code line. The orchestrator re-read every blocking and major finding against the source before it entered this document; the verification notes say what was re-checked. The nine slices: record and factory tree; control plane; trust, binding and approvals; execution boundary; stages S0 to S3; stages S4 to S6 with checks; external systems and the outcome record; observability, baseline and graduation; HLD structural conformance (component and crossing maps).

**Kinds.** `gap`: required, not built. `deviation`: built differently from the spec in a way that changes a contract. `untested`: built, but the criterion has no test that could fail. `simplification`: a shortcut the docs do not admit; `(known)` when the owner already accepted it. `doc drift`: the code is right and a document is stale.

**Severities.** `blocking`: a milestone exit test or the definition of done cannot honestly pass, or a trust, guard, append-only or credential rule is violated. `major`: a row's verification clause is not met. `minor`: contract detail, naming, hygiene.

## 2. Summary

| Severity | Count | Ids |
|---|---|---|
| Blocking | 4 | G-01, G-02, G-03, G-04 |
| Major | 17 | G-05 to G-21 |
| Minor | 15 | G-22 to G-36 |
| Known simplifications confirmed | 6 | section 6 |

The four blocking findings are all in the runner's control and boundary code, not in the record or the factory tree. Two break the ticket's own path on a real ticket: a passing fix round never returns the ticket to `checks` (G-01), and the only route out of a verification-exhaustion escalation is a transition that does not exist (G-02). Two break a boundary rule: S4 task-validation recipes run with no OS sandbox (G-03), and the guard sees five crossings while the design and R-T-9 seat it on eight, leaving every agent-written artefact unguarded at persistence (G-04). None of the four is caught by the suite, and in three cases a test's own docstring records that it was written around the gap.

The record (schema, append-only triggers, export and import, manifest, eval walk, adoption gate), the S0 to S3 drivers, the S5 order, the outbox, the outcome record and the graduation clauses were found to match the specification closely; section 8 lists what was verified.

## 2a. Decisions of 2026-09-10 and the disposition of every finding

The owner's rule: the factory cannot yet open a real pull request, so security hardening beyond what is already built waits until the factory is stable on real tickets. The built sandbox, proxy, escape suite and guard stay. Milestones and tickets are not rewritten; the PRD is (v0.19, decision 55), and each deferred item carries a to-do note at its seam in the code. Dispositions: **fix** (do now), **deferred** (moved to a Later PRD row or sentence, to-do in code), **closed by decision** (the spec changed to match the code, or the clause was dropped), **wait** (needs the pilot repository or the live connections), **doc** (a document fix only).

| Finding | Disposition | Decision or note |
|---|---|---|
| G-01 fix round return | fixed 2026-09-10 | A passing fix round applies `s4_pass` in the transaction that closes its `validation_only` run; the next `advance` runs a fresh S5 |
| G-02 send-back from `escalated` | fixed 2026-09-10 | The three `escalated` exits are `send_back_to_{planning,clarifying,context}`, the vocabulary every other open item uses; `checks` and `implementing` stay refused |
| G-03 S4 validation unsandboxed | fixed 2026-09-10 | `_validate_task` passes the sandbox run directory, so validation goes through the enforced build launch like S5. The bare-subprocess branch of `recipes.run` remains for the recipe unit tests; no production caller reaches it, and a to-do at the branch says why it stays and what replaces it |
| G-04 guard seats | closed by decision, rest deferred; code aligned 2026-09-10 | Guard covers outside content, the baseline import, display, outbox and export in Initial (R-T-9 narrowed); stage output, mounts, logs and dispatch are R-T-13 (Later). `CROSSINGS` now declares exactly those five, S0's intake is decided under `ingress`, and an undeclared crossing denies with `crossing_not_declared`. To-do at each deferred seat: `runner/guard.py` (the tuple), `runner/artefact_registry.py`, `runner/launcher.py`, `runner/adapters/cursor_sdk.py` and `runner/sandbox/proxy.py` (dispatch) |
| G-05 registry policy | deferred | R-S5-15 (Later); R-S5-2 and R-I-14 narrowed. To-do in `runner/stages/S5.py` and `runner/recipes.py` |
| G-06 pilot repository entry | wait | Environment work under the live-connection ticket; the single-entry loader changes then |
| G-07 retry evidence feed | fixed 2026-09-10 | `_validate_task` registers the validation recipe's output as a `task_validation_evidence` artefact on the `task_validation` check result; attempt N+1 of the same task under the same plan-item version stages the last verification failure's evidence through `_red_evidence_artefact_ids`, skipping over intervening infrastructure failures. Evidence never crosses tasks or plan versions |
| G-08 removal return, bad hand-back | fixed 2026-09-10 | S5 preflight applies `checks_removal_return` on the accidental case, recording the offending paths as an `exclusion` failure with evidence and a `removal_route` marker; S4 reads the marker the way it reads `fix_round_route` and runs a removal round through the fix-round machinery, confined by rerunning the exclusion decision over the round's diff instead of the plan's scope table, then `validation_only` and `s4_pass`. A removal round is stored as `run_kind = fix_round` and draws on the fix-round cap, since `limits.yaml` has no separate entry; a failed or capped round opens one `red_check`. A ticket at `checks` with no recorded branch, head or worktree applies `checks_bad_handback` before the freshness check and resumes the ordinary per-task loop under its own bound |
| G-09 pre-dispatch mismatch routes | fixed 2026-09-10 | The outbox's pre-dispatch recheck records the mismatched component in `external_write.last_error` under a `predispatch_mismatch:` prefix, widest first: target base or trust profile moved routes to `context`; a newer plan tuple or an invalid plan waiver routes to `planning`; a review-subject, head or destination mismatch routes to `checks`, which `review_gate` also uses as the fail-safe when no component was recorded |
| G-10 baseline freeze | fix | Freeze regardless of count; the gate reports a short baseline as unavailable |
| G-11 disposition values | fix | The entity table's set wins; fix the config, the loader and the pinning test |
| G-12 question flags mutable | fixed 2026-09-10 | The three flags are immutable; `correct_flag` appends a row copying every content field with the corrected flag, `supersedes` naming the tip, the tip's state carried forward and the tip moved to the new `superseded` state; the `flag_correction` tag lands on the new row. The queue, checklist, S3 plan inputs and report views read only lineage tips. Observed while fixing: `answer.question_version_hash` is declared but never written anywhere, so an answer binds to the question id alone; left as is |
| G-13 blocking override | fixed 2026-09-10 | `correct_flag` accepts `blocking`; `factory act` takes `--blocking yes|no` through `queue.act`; a blocking question corrected to non-blocking on a ticket parked in `clarifying` lets the next `advance` leave the state |
| G-14 `size: none` | fixed 2026-09-10 | `none` is a test-strategy size; the rubric fails a `none` row with an empty `proves` or an action other than `add`; the test-mix report counts automated sizes only; the packet's test summary matches rows to diff files by name and needs no change. The S3 rubric fixture was not given a `none` row because its hash is pinned in the manifest, which cannot change uncommitted |
| G-15 S0 rubric stub | fix | |
| G-16 S2 pre-fill unreachable | closed by decision | Clause dropped from R-S2-4; remove the dead code |
| G-17 `tools.yaml` | closed by decision | The manifest's per-stage list is the table; PRD sections 7 and 8 amended. Make the list carry the real per-stage entries |
| G-18 agent shell and tool list | closed by decision, rest deferred | Free command execution inside the agent sandbox is deliberate (R-I-3 amended); confinement and runtime enforcement are R-I-18 (Later). To-do in `runner/sandbox/os_policy.py` and `runner/adapters/cursor_sdk_worker.py` |
| G-19 non-waivable backstop | deferred | Section 10 sentence; to-do in `runner/waivers.py` |
| G-20 digest cadence | fix | |
| G-21 closing-run tests | fix the testable half, wait for the rest | Report and pre-dispatch assertions on the fixture walk, and the digest criterion, now; the live legs with the live connections |
| G-22 `gate = manifest` | doc | Admit the value in the entity row |
| G-23 `imported_from` unread | deferred | Follows R-T-13's scope; note only |
| G-24 export table set | fix | R-T-4 now names every table with a human decision or agent claim |
| G-25 proxy writes rows | doc | Note in the L2 file when it is next touched |
| G-26 mount-time guard | deferred | Part of R-T-13 |
| G-27 gate on pull requests | closed by decision | Later, under R-F-9 |
| G-28 incident manifest hash | fix | |
| G-29 roles as constants | fix | Read from `owners.yaml` |
| G-30 owners test | fix | Compare identity values |
| G-31 queue latency union | fix | |
| G-32 verbatim fixture copy | wait | Matters when a real export is the input |
| G-33 `dependents_invalidated` unused | fix | Surface in the queue item or drop the function |
| G-34 provisional marking | fix | |
| G-35 stop note on every run | fix | |
| G-36 dead relabelling | fix | Wire or remove |

The HLD followed the PRD to v0.4 the same day: `L2-control-plane.md` draws the Initial guard seats solid and the deferred ones dotted with the runner's own writes and the mounts direct, `L2-factory-as-code.md` drops `config/tools.yaml` and adds the confined-execution row, `L2-execution-boundary.md` marks the registry leg Later, and the README's trust rule and X2 row say which seats are Initial. Still describing the old scope, by the owner's choice not to rewrite built tickets: T-A-07 criteria 8 and 9 name all eight crossings; T-AB-08 names the registry policy.

## 3. Blocking

### G-01. A passing fix round never returns the ticket to `checks`, so S5 does not rerun

- Kind: gap. Slice: stages S4 to S6.
- Spec: R-S4-9, `docs/prd/04-S4-implementation.md:11`: "After hand-back the runner executes every task's validation recipes once as a `validation_only` run, then S5 reruns in full." `docs/design/hld/L1-ticket-walk.md` diagram 2 loop 2a draws the S5 rerun directly after the validation pass. `docs/prd/prd.md:71`.
- Ticket criterion: T-A-29 criterion 23 presupposes the rerun; T-A-29's Out list assigns "the live S5 rerun after a fix round's validation pass" to T-A-30, whose criteria never mention it. No ticket owns the return leg.
- Code: `runner/stages/S4.py:1020-1044` `_run_fix_round` returns `"pass"` without applying `PASS_EVENT` (`s4_pass`), unlike the ordinary task path at `runner/stages/S4.py:1090-1096`. The state table has only `("implementing", "s4_pass") -> "checks"` as the way back (`runner/state_table.py:122`). On the next `factory advance`, `_due_stage` (`runner/operations.py:34-60`) finds S4 always due in `implementing`, and `run_next` (`runner/stages/S4.py:1070`) re-enters `_fix_round_routed`, which reads the same latest S5 run's `fix_round_route` result (`runner/stages/S4.py:838-846`) and is still true. A second fix round starts against a ticket that already passed; the two-round cap in `factory/config/limits.yaml` is exhausted on phantom rounds and the ticket lands on a human `red_check` with reason `cap_reached`.
- Tests: `runner/tests/test_s4_fix_round.py` asserts state after a budget abort (`escalated`) and after a cap refusal (`implementing`) but never after a successful round; no test drives `advance` from a fix-round pass into a fresh S5 run. `runner/tests/test_s5_ab_fix_routing.py` covers routing into the round only.
- Verified by the orchestrator: read `_run_fix_round`, `run_next`, `_fix_round_routed`, `_due_stage`.
- Why it matters at B: a red lint or unit result on the pilot ticket takes exactly this path. The definition of done requires the bounded fix round to complete before anyone is asked; as built it cannot.

### G-02. Send-back from `escalated` has no transition, so a verification-exhaustion escalation cannot be resolved through `factory act`

- Kind: gap. Slice: control plane.
- Spec: `docs/prd/02-3-ticket-states.md:23` (`escalated` row): "Verification exhaustion may only move to `planning` or earlier for a superseding plan-item version and new approval, or abandon." `docs/prd/02-3-ticket-states.md:25`: send-back is allowed "from any open queue item (plan approval, red check, packet approval, escalation, or manual pause)".
- Ticket criteria: T-A-12 criterion 8 (`escalation` accepts `send_back`), T-A-17 criterion 10, T-A-04 criterion 33.
- Code: `runner/state_table.py:154-156` names the `escalated` exits `escalation_verification_resolved_to_{planning,clarifying,context}`; every other state uses `send_back_to_{to}`. `runner/queue.py:572-576` `_send_back` always applies `send_back_to_{to}` regardless of kind or state. Every production site that opens an `escalation` item moves the ticket to `escalated` first (`runner/control.py:128-133`, `runner/budgets.py:138-141`, `runner/refresh_base.py:83-84`, `runner/stages/S4.py:729-741`). So `factory act <escalation> send_back --to planning` on a real ticket raises `TransitionRefused`. Nothing in `runner/` outside tests ever applies an `escalation_verification_resolved_to_*` event. `runner/queue.py:658-663` `_resume` refuses a verification-exhaustion escalation and tells the operator to use `send_back --to planning`, the route that is broken.
- Tests: `runner/tests/test_act.py:237-250` says in its docstring that `escalated` has no `send_back_to_*` row "so the escalation/send_back combination is exercised against a ticket seeded in `checks` instead"; `runner/tests/test_stage_interface.py`'s `_SEND_BACK_STATES` maps `escalation` to `checks` for the same reason. `runner/tests/test_state_table.py:521-534` applies the literal event string only.
- Verified by the orchestrator: grep of `send_back_to_` and `escalation_verification_resolved` across `runner/` outside tests.
- Why it matters at B: three failed S4 attempts on the pilot ticket leave it in a state no `act` action can move to `planning`; abandon is the only exit.

### G-03. S4 task-validation recipes run outside the OS sandbox

- Kind: gap. Slice: execution boundary.
- Spec: R-I-14, `docs/prd/03-stage-interface.md:24`: "Every agent invocation and repository/build recipe runs inside an OS-enforced sandbox identified by immutable policy or image digest." Milestone AB Sandbox shape (`docs/design/milestones.md:161`) names no stage carve-out. `docs/design/hld/L2-execution-boundary.md` diagram 2, S4 row.
- Ticket criterion: T-AB-01 covers R-I-14 for every recipe; no ticket exempts S4 validation.
- Code: `runner/recipes.py:run` has two branches. With `sandbox_run_dir` it goes through `launcher.launch(role="build", policy="enforced", ...)` and refuses a run without an applied OS policy (`runner/recipes.py:394-425`). Without it, it falls through to a bare `subprocess.run` (`runner/recipes.py:427` onward). `runner/stages/S4.py:694-697` `_validate_task` is the only caller in the codebase that omits `sandbox_run_dir`; `runner/stages/S5.py:283`, `runner/stages/S5.py:415` and `runner/adoption.py:52` all pass it.
- Tests: `runner/tests/test_capability_boundary.py` calls `_validate_task` only to assert the `recipe_binding` refusal of a shell string. Nothing asserts that a validation recipe ran under the build profile.
- Verified by the orchestrator: read both branches of `recipes.run` and the S4 call.
- Why it matters at B: the validation recipe is the one process that runs against the agent-writable worktree after every task attempt. Charter C10 and the AB exit test require the OS policy on it.

### G-04. The guard is seated on five crossings, not the eight R-T-9 and the HLD name; agent-written artefacts are persisted unguarded

- Kind: gap. Slices: trust and binding; HLD conformance (their findings merged).
- Spec: R-T-9, `docs/prd/02-1-ticket-record.md:19`: "one runner-owned guard outside stages and adapters is the sole path for content-bearing ingress, persistence, display, sandbox mounting, logs, model/MCP/tool dispatch, outbox payloads, and exports. Each content decision writes one `guard_decision`." `docs/design/hld/README.md:17`: "Every content-bearing crossing passes the guard (C5) and leaves one `guard_decision` row." `docs/design/hld/L2-control-plane.md` seats C5 on X2 persistence ("every write from C2, C3, C6, C8 and C9 fans in to C5_seat"), X3 dispatch and X7 mounts. Milestone A Guard shape: "Route enforcement on every content-bearing crossing ... a secret hit denies and is never stored."
- Ticket criteria: T-A-07 criteria 8 and 9 name all eight crossings; criterion 8 admits bare-module fixtures only for sandbox mounting, outbox payloads and exports.
- Code: `runner/guard.py:27-29` declares eight crossings. Production call sites of `guard.decide`: `runner/stages/S0.py:255` (Jira intake, crossing name `s0_intake`, outside the declared tuple), `runner/baseline.py:61` (`persistence`, baseline import only), `runner/operations.py:258` (`display`, `show_artefact` only), `runner/outbox.py:336` (`outbox`), `runner/export.py:136` (`export`). No call site uses `sandbox_mount`, `logs` or `dispatch`. `runner/launcher.py:stage_inputs` (the X7 mount path) and `runner/adapters/cursor_sdk.py:_record_tool_calls` never import the guard. `runner/artefact_registry.register` takes `guard_decision_id` defaulting to `None`, and every registration in `runner/stages/S1.py` to `S6.py`, `runner/adapters/cursor_sdk.py`, `runner/sandbox/proxy.py` and `runner/outcome.py` passes none: briefs, criteria, plans, handoffs, check evidence, tool results, packets and PR bodies enter the record with no classification, no secret scan and no decision row. Only the S0 ticket source, the export manifest and the outbox receipt carry one.
- Tests: `runner/tests/test_guard.py` exercises all eight names against the bare module with hand-built operations. `runner/tests/test_stub_walk.py:702` counts decision rows over the stub walk but only for the crossings that exist. No test asserts that a stage-registered artefact or a tool result obtained a decision.
- Verified by the orchestrator: grep of `guard.decide(` and `crossing=` across `runner/` outside tests.
- Reading: the spot checks of the trust rule held (recipe id checked against the plan's approved list, model from the manifest, credential role a literal), so no case was found where untrusted content selected a tool, recipe, mount, model or credential. The gap is the persistence and dispatch seats themselves: an agent output containing a secret is stored, and a downgrade through those paths is invisible to any audit of `guard_decision`. If the owner decides R-T-9's "persistence" was meant narrowly (external content only), then the HLD text and T-A-07 criteria 8 and 9 must be narrowed to match; otherwise the missing seats must be added. Either way the document and the code disagree today.

## 4. Major

### G-05. The registry policy of R-S5-2 does not exist: no S5 proxy route, no registry endpoint, and `dep_verify` gets an empty allowlist

- Kind: gap. Slices: execution boundary; stages S4 to S6 (merged).
- Spec: R-S5-2, `docs/prd/04-S5-cleanup-pass.md`: dependency verification runs "with the same declared registry/cache policy" and "a required network source outside the recipe allowlist" blocks. T-AB-08 criteria 1 and 9 (`sandbox.yaml`'s S5 `proxy_allowlist` admits only the recipe-declared registry endpoints under route id `registry`). Milestone AB "Absent at A" names "any registry route" as something AB adds.
- Code: `factory/config/sandbox.yaml`'s `proxy_allowlist` names S1 to S4 only, and `endpoints` holds `hosted_model` and `atlassian_read` only. Every recipe in `factory/config/command-recipes.yaml` declares `network: none`. `runner/stages/S5.py:695` passes `"--allowed-registry", ""` as a literal. No file under `factory/config/` carries a registry allowlist.
- Tests: `runner/tests/test_dep_verify.py` calls the script directly with `--allowed-registry registry.example`; the S5 call path with the empty string is untested. `runner/tests/test_recipes.py:226` refuses a `network: registry` recipe, which passes only because S5 has no route at all.
- Verified by the orchestrator: grep of `sandbox.yaml`, `command-recipes.yaml`, the S5 call.
- Note: the pilot repository's own recipes wait on the pilot repository (G-06), but the route, the endpoint shape and the configuration source for the allowlist are AB mechanism and can be built on the fixture project.

### G-06. No pilot repository entry exists, and the loader refuses a second project

- Kind: gap (environment part known). Slices: stages S0 to S3; observability (merged).
- Spec: Milestone AB Git trees shape (`docs/design/milestones.md`): "The pilot repository as a pinned source checkout outside this repository, named in `project.yaml` beside the fixture project, a ticket pinning one of the two." T-AB-04 criteria 13 to 16 (pilot rows in `service-tiers.yaml`, the pilot entry in `project.yaml`, the pilot's context index entries).
- Code: `factory/config/project.yaml:7-24` has one entry, `fixture-project`. `runner/project.py:32-43` `pilot()` raises unless `projects` has exactly one entry, so the design's "beside the fixture project" cannot be expressed. `service-tiers.yaml`, `sensitive-paths.yaml` and `factory/index/*.md` describe the fixture project only.
- Tests: `runner/tests/test_pilot_config.py` reads the committed file, so "the pilot" it checks is the fixture project. `runner/tests/test_s1_archaeology.py:424` skips with "no real pilot repository exists yet".
- Owner context: `docs/build/T-AB-04/brief.md:19-23` records that no real pilot repository, Jira key or Keychain item existed when AB was built. The environment half belongs with T-B-06. The code half does not: the single-entry loader and the fixture-only configuration files are AB scope and block T-AB-04's own criteria.

### G-07. Ordinary S4 retries do not feed the failed attempt's evidence into the next invocation

- Kind: gap. Slice: stages S4 to S6.
- Spec: `docs/prd/prd.md:70`: "A failed attempt closes with its evidence and feeds the next fresh attempt; three failed attempts escalate."
- Code: `runner/stages/S4.py:446-452` builds the invocation inputs as handoff, plan and criteria only. The fix-round path at `runner/stages/S4.py:973-978` adds the failing recipe outputs through `_red_evidence_artefact_ids`; the retry path has no equivalent. `_failure_history_payload` (`runner/stages/S4.py:745-784`) is assembled only at the third failure.
- Tests: `runner/tests/test_s4_task_loop.py:248` asserts a fresh handoff version and distinct run ids, not the inputs of attempt two.
- Why it matters at B: a second attempt has no governed record of why the first failed, which is what the sentence exists to guarantee; the report's first-attempt versus later-attempt reliability figure rests on it.

### G-08. `checks_removal_return` and `checks_bad_handback` exist only as state-table rows

- Kind: gap. Slice: control plane (confirmed against the S5 driver).
- Spec: `docs/prd/02-3-ticket-states.md:19` (`checks` row): "an accidental Initial-sensitive path may return to S4 for removal, while a path required by the plan closes `pilot_excluded`." T-A-04 criterion 18; T-A-20 criterion 19.
- Code: `runner/state_table.py:128-129` declares both events. `runner/checks/exclusion.py:107-136` `decide_at_checks` returns `checks_removal_return` for the accidental case, but `_STAGE_EVENTS` (`runner/checks/exclusion.py:32-36`) has no mapping for it and `runner/stages/S5.py:160-179` acts only on `checks_sensitive_path_required`; the accidental case falls through to a generic structural failure. `checks_bad_handback` is applied nowhere outside its own test.
- Tests: `runner/tests/test_s5_order.py:248-256` documents the gap in its docstring. `runner/tests/test_exclusion.py:193-197` and `runner/tests/test_state_table.py:363-369` apply the literal event only.
- Why it matters at B: the spec's automatic return to S4 for removal is replaced by a `red_check` whose send-back targets never include `implementing`.

### G-09. A pre-dispatch mismatch routes only to `checks`, never to `planning` or `context`

- Kind: gap. Slice: external systems.
- Spec: R-S6-3, `docs/prd/04-S6-human-review.md:9`: "a pre-dispatch binding mismatch supersedes the intent and follows the affected check/plan/context route". T-AB-06 criterion 9.
- Code: `runner/gates.py:187-213` `review_gate` returns `review_predispatch_mismatch_to_checks` for every superseded intent; its docstring says the planning and context routes "are applied only by a caller that decides them", and no caller exists.
- Tests: `runner/tests/test_state_table.py:456-460` applies the two other events directly; no outbox test selects between the three.

### G-10. The baseline cohort freezes only when ten observed values exist

- Kind: deviation. Slice: observability.
- Spec: R-O-6, `docs/prd/06-observability.md:17`: "The combined declared cohort is frozen before Milestone B and never backfilled." The ten-value threshold decides whether a supplemental cohort is added, not whether the freeze happens. T-AB-10 criteria 17 and 20. T-B-03 criterion 30 expects a short baseline to reach the gate as `unavailable_baseline`.
- Code: `runner/baseline.py:238-245` freezes only when `observed >= 10`, otherwise finishes the utility run `blocked` and leaves `frozen_at` null.
- Tests: `runner/tests/test_baseline_import.py:87-113` asserts `frozen_at is None` after a two-ticket import and then freezes by hand to test the frozen-cohort refusal.
- Verified by the orchestrator: read the freeze branch.
- Why it matters at B: a pilot service whose history cannot supply ten comparable values never gets a frozen baseline, so the AB exit sentence about the frozen cohort is unsatisfiable and the graduation clause designed for that case is unreachable.

### G-11. `incident-policy.yaml`'s disposition set differs from the entity table's, and the two halves of the code disagree

- Kind: deviation. Slice: external systems.
- Spec: `docs/prd/02-2-entities.md:149`: disposition is `open`, `remediated`, `reviewed_no_change`.
- Code: `factory/config/incident-policy.yaml:42` has `[open, remediated, accepted, not_applicable]`, enforced by `runner/incident_policy.py:57-60` and `runner/outcome.py:328-330`. `runner/tests/test_graduation_clauses.py:54` seeds `reviewed_no_change` through a helper that bypasses that validation, so the writer would refuse the value the graduation reader is tested with.
- Tests: `runner/tests/test_outcome_incident.py:90` pins the yaml's set.

### G-12. `question.consequential`, `hard_to_reverse` and `blocking` are mutable in place beyond R-T-3's exception

- Kind: deviation. Slice: record.
- Spec: R-T-3, `docs/prd/02-1-ticket-record.md`: the `question` table's only mutable field is `state`; content fields are never edited in place.
- Code: `runner/schema.py:506-510` marks the three flags `mutable=True`, so the append-only trigger excludes them. A correction overwrites the agent's original value; only the `flag_correction` tag keeps the reason (`runner/questions.py:242-262`), not the prior value.
- Tests: `runner/tests/test_mutable_exceptions.py:46` pins the mutable set; T-A-03 criterion 14's test edits `reasoning` and `options` only.
- Decision needed: either add the three flags to R-T-3's exception list (and record the prior value somewhere) or make a correction append a superseding row.

### G-13. No human override exists for `question.blocking`

- Kind: gap. Slice: stages S0 to S3.
- Spec: `docs/prd/02-2-entities.md:95` and R-S2-12: `blocking` is "set by the agent and overridable by the human".
- Code: `runner/questions.py:242-262` `correct_flag` accepts `consequential` and `hard_to_reverse` only; `runner/queue.py:315-345` forwards the same two. No write to `question.blocking` exists after the insert.
- Tests: none for a blocking override. T-A-23 criterion 10 omits it, so the gap came from the ticket text.
- Why it matters at B: an over-classified blocking question parks the ticket in `clarifying` until it is answered.

### G-14. A plan cannot record "no automated test" for a criterion

- Kind: gap. Slice: stages S0 to S3.
- Spec: `docs/prd/08-configuration.md:35` test-strategy row: size is small, medium, large "or none with the reason in proves"; R-S3-19: "A criterion with no automated test is a test-strategy row with test `none` and the reason in `proves`."
- Code: `runner/artefacts.py:167` `TEST_SIZES = ("small", "medium", "large")`; `runner/checks/plan_rubric.py:185-186` fails any other size. No branch requires a `proves` reason for `none`.
- Tests: no fixture or test uses `none`.

### G-15. `factory/rubrics/S0.md` is still the T-A-01 stub

- Kind: gap. Slice: stages S0 to S3.
- Spec: `docs/prd/04-S0-intake.md:17` declares rubric lines for R-S0-1, R-S0-2, R-S0-5 and R-S0-6; Milestone A Rubric shape: "Files generated from the rows, script lines only."
- Code: `factory/rubrics/S0.md` is seven lines reading "Stub rubric for the intake stage's mechanical gate; real checklist lands in a later ticket." S1 to S3 carry real content. No ticket after T-A-01 lists the file.
- Tests: `factory/evals/rubrics/S0/` checks front matter only.
- Note: the four rows are enforced directly in `runner/checks/intake_fields.py`, `runner/checks/exclusion.py` and `runner/stages/S0.py`, so behaviour is unaffected; the manifest pins a rubric hash with nothing behind it.

### G-16. The S2 forced-category pre-fill from an S0 exclusion can never fire

- Kind: gap. Slice: stages S0 to S3.
- Spec: R-S2-4, `docs/prd/04-S2-requirements-clarification.md:12`; T-A-24 criterion 13.
- Code: `runner/stages/S2.py:158-174` reads an S0 `check_result` named `exclusion`; S0 never writes one (`runner/stages/S0.py` around line 487 applies the transition only). The comment at `runner/stages/S2.py:62-66` says so. Under R-S0-8 a migration or permissions match excludes the ticket at `intake`, so no ticket reaching S2 can carry such a record.
- Tests: `runner/tests/test_s2_criteria.py` inserts the row by hand.
- Decision needed: either S0 records a passing exclusion check with the closed categories, or the row's clause is retired as unreachable under R-S0-8.

### G-17. `config/tools.yaml` does not exist; the tool-attachment table is a generic list inside the manifest

- Kind: gap. Slice: record and tree.
- Spec: `docs/prd/07-factory-as-code.md:15` names `config/tools.yaml` in the fixed layout; `docs/prd/08-configuration.md` "tools.yaml: attachment table" and the per-stage table (Atlassian read at S1, codegraph and repository read, none at S5 and S6); `docs/design/hld/L2-factory-as-code.md` derivation row F6 `config/tools.yaml`.
- Code: no such file; `factory/manifest.yaml:1220` onward carries `tool_allowlist: [read_file, write_file, run_command]` per agent stage, which does not encode the section 8 table. `runner/tests/test_tree_layout.py` checks directories only.
- Related: G-18.

### G-18. The agent Seatbelt profile allows any `process-exec`, and the tool allowlist is recorded but never passed to the runtime

- Kind: deviation. Slice: execution boundary.
- Spec: R-I-3, `docs/prd/03-stage-interface.md:23`: "Agents request typed command recipes rather than shell strings." T-AB-01 criterion 26 (a subprocess other than a declared recipe executable is refused).
- Code: `factory/config/sandbox/agent-profile.sb` grants `(allow process-exec)` and `(allow process-fork)` unconditionally; `factory/config/sandbox/build-profile.sb`'s closing comment records the asymmetry as deliberate. `runner/adapters/cursor_sdk_worker.py` never passes `tool_allowlist` or any tool restriction to the SDK; `runner/adapters/cursor_sdk.py:341` only records it on the run row.
- Tests: the escape suite's subprocess probe runs under the build role only.
- Caveat: the SDK's default tool surface could not be confirmed from source in this environment; if it exposes a shell tool, the typed-recipe rule is enforced only for the plan's `validation_recipe` field.

### G-19. The non-waivable list lives only in `waiver-policy.yaml`

- Kind: deviation. Slice: trust and binding.
- Spec: R-S5-13 and charter section 6 state the non-waivable set as an absolute list.
- Code: `runner/waivers.py:263-264` refuses a condition only if `policy.never_waivable` (loaded from the yaml, `runner/waivers.py:91-111`) names it; no code constant backs the list.
- Tests: `runner/tests/test_s5_waivers.py:505` proves the yaml-to-code wiring, not an invariant that survives an edited file.
- Mitigation: the file is manifest-hashed and changes only by reviewed pull request.

### G-20. The digest scheduler cannot express D42's cadence

- Kind: deviation. Slice: external systems.
- Spec: `docs/prd/08-configuration.md:51`: twice per working day, Monday to Friday, 10:00 and 15:00, "times, weekdays, and channel under the `digest` key of `project.yaml`". T-AB-07 criterion 8.
- Code: `runner/setup.py:31-48` supports `hourly`, `daily` (09:00 every calendar day) and `weekly` (Monday 09:00) as one `StartCalendarInterval`; `factory/config/project.yaml:40-47` has no `times` or `weekdays` key; `runner/digest.py:17-27` mirrors the three-value cadence for the idempotency slot.
- Tests: `runner/tests/test_digest.py:186-203` pin the single-slot behaviour.

### G-21. The closing run of T-B-05 is only partly proven on the fixture project

- Kind: untested. Slices: observability; external systems; stages S0 to S3 (merged).
- Spec: `docs/prd/prd.md:78` definition of done; T-B-05 criteria 17, 19, 20, 21; T-AB-07 criterion 11; T-AB-04 criteria 8, 11, 12; T-AB-05 criteria 7, 8.
- Findings, each with the file searched:
  - Criterion 20 ("`factory report` distinguishes first-attempt reliability, queue latency, active attention and unavailable evidence") has no test in `runner/tests/test_pilot_walk.py`; the file never calls `stage_interface.report`.
  - Criterion 19 (the pre-dispatch recheck confirms S5's review subject and the worker's plan subject are the same fresh subjects) is not asserted anywhere in that file beyond the walk succeeding.
  - Criterion 17 (the escape suite's `credentials` category re-run against the pilot ticket's own sandbox) is exercised only by the skipped live test; `runner/tests/test_escape_suite.py` runs the category against a generic sandbox.
  - Criterion 21 (`factory/evals/tickets/<pilot ticket id>/` exists and is listed in the manifest) has not landed: `factory/evals/tickets/` does not exist; the tests write the fixture to a temporary root only.
  - T-AB-07 criterion 11 (one Slack post on the closing run) has neither a test nor a loud skip in `runner/tests/test_digest.py`.
  - T-AB-04 and T-AB-05's real-server criteria skip loudly in `runner/tests/test_s0.py:527-556` and `runner/tests/test_s1_archaeology.py:418-424`.
- Note: criteria 17 and 21 and the real-server legs are the known placeholder for the live run and wait on T-B-06 and T-B-07. Criteria 19 and 20 and the digest criterion can be tested on the fixture project today and are the actionable part.

## 5. Minor

### G-22. `approval_record.gate` has a fifth value, `manifest`
- Deviation, record. `runner/schema.py:129` adds `manifest` for `factory migrate-manifest` re-approval; `docs/prd/02-2-entities.md` closes the set at four. Either the entity row admits it or the migration approval uses `trust_profile`.

### G-23. `imported_from` is written but never read
- Gap, record. R-T-4 "marks imported prose as untrusted input". `runner/export.py:368-370` sets the field; nothing in `runner/` reads it, so imported prose is not treated differently from native text. T-A-16 criterion 12's test asserts the field only (`runner/tests/test_export_import.py:444`).

### G-24. The governed export omits `question`, `answer`, `assumption`, `human_verdict`, `deviation`, `generated_test`, `index_use` and `baseline_measure`
- Untested, record. `runner/export.py:44-48` `EXPORT_TABLES`. R-T-4's literal list does not name these tables, but T-B-05 criterion 16 says the export "shows every ... human decision", and S3 bootstrap-checklist verdicts and answers are human decisions. `runner/tests/test_pilot_walk.py`'s completeness test checks five tables. Decision needed on the intended table set; the fixture from export inherits whatever is chosen.

### G-25. The loopback proxy writes ledger and artefact rows from inside the execution-boundary domain
- Deviation, HLD conformance. `runner/sandbox/proxy.py:161-206` `_relay_and_record` opens its own connection and writes `tool_call` and artefact rows; `docs/design/hld/L2-execution-boundary.md` "Not drawn" says C6 and C3 write those rows. Harmless (the proxy is a thread of the trusted process); the L2 text or a module comment should say so.

### G-26. No guard decision at mount time (X7)
- Gap, HLD conformance; part of G-04 called out because `docs/design/hld/L2-control-plane.md` draws the mount seat by name. `runner/launcher.py:stage_inputs` and `runner/envelope.py` carry the artefact's original `guard_decision_id` forward but take no fresh decision for the target sandbox.

### G-27. The adoption gate is not wired as a pull-request check in this repository
- Gap, HLD conformance. `docs/design/milestones.md` Appendix B X9 names the gate as the pull request's check; `runner/gate.py` exists but no `.github/` workflow or root `CODEOWNERS` invokes it. R-F-9 (branch protection) is Later; decision 5 of milestones section 3 says "required" at AB means required by R-F-4's reviewed-change path, so this may be intended. Confirm.

### G-28. `incident_observation.factory_manifest_hash` is never populated
- Deviation, external systems. `runner/schema.py:849` declares the column; `runner/outcome.py` (six writers) and `runner/stages/S4.py:724-728` omit it. R-O-4's per-manifest filter cannot slice incidents or control defects.

### G-29. `outcome_actor_role` and the incident reviewer role are constants, not read from `owners.yaml`
- Simplification, external systems. `runner/outcome.py:48-49`; T-B-01 criterion 12 says "read from `owners.yaml`". The module docstring records the shortcut.

### G-30. `owners.yaml` gives the sensitive-path owner and the ticket engineer the same identity, and the test cannot tell
- Untested, trust. `factory/config/owners.yaml:14-19`; `runner/tests/test_owners.py:63-69` compares two dict objects, not identity values. T-A-06 criterion 8. Harmless while sensitive work is excluded from Initial.

### G-31. Queue latency averages per-item intervals, not the union of a batch
- Deviation, observability. `docs/prd/06-observability.md` measure table: "the union of open intervals ... a batch counts once". `runner/schema.py:993-1007` averages each item's own span. Overstates latency when a round opens several items.

### G-32. `fixture_from_export` copies the export verbatim; the redaction review is metadata only
- Simplification, observability. `factory/scripts/tools/fixture_from_export:44-71` `copytree` with no stripping or verification of `redacted_fields`; `runner/evals.py:_redaction_review_missing_fields` checks the four fields are present. Real risk once a real export is the input.

### G-33. `dependents_invalidated` is computed but never consulted
- Gap, stages S0 to S3. `runner/questions.py:297-337` has no caller; the plan-tuple hash already blocks stale plan approvals, but no report or queue item tells the human which artefacts went stale (R-S2-11).

### G-34. Provisional marking covers only driver-derived questions
- Gap, stages S0 to S3. R-S2-12: criteria depending on an open non-blocking question are `provisional`. `runner/stages/S2.py:429-452` marks them only for the agreement-check and contradiction cases, not an agent-raised non-blocking question naming a criterion.

### G-35. `control.stop` stamps the same note on every open run
- Minor, control plane. `runner/control.py:113-121` writes the stop note as the reasoning summary of every open run lacking one; wrong once parent and child runs are open together. Untested either way.

### G-36. The packet's blind-spot relabelling for impact and declaration entries is unreachable from the real S6 driver
- Untested, stages S4 to S6. `factory/scripts/tools/packet_render.py:38-42,116-130` keys on an entry `kind` that `runner/stages/S6.py:222-235` never sets; only the standalone eval fixture exercises it. The underlying checks already self-report `blind_spot`, so the branch is dead rather than wrong.

## 6. Known simplifications, confirmed present

Listed so the owner can confirm each stays accepted.

| Simplification | Where | Matters at B |
|---|---|---|
| Fix-round "recipes cleared" inferred from the next `validation_only` run by id adjacency | `runner/stages/S6.py:246-263` | Cosmetic in the evidence table |
| Intent and scrutiny split on a literal `Scrutiny:` marker | `runner/stages/S6.py:129-137` | A plan without the marker leaves scrutiny empty in the packet |
| The adapter test fixture `sandbox.yaml` carries no `os_profiles`, so routine stage and walk tests never pay for `sandbox-exec` | `runner/tests/fixtures/adapter/sandbox.yaml` | The escape suite and `test_sandbox.py` cover the real profiles; combined with G-03 it means no test ever runs S4 validation under the OS policy |
| `queue.act` keeps the older per-flag kwargs beside `fields` | `runner/queue.py` | None |
| Waiver flags reuse `--verdict` and `--evidence` | `runner/queue.py:_issue_waiver` | None |
| The live closing-run leg of `test_pilot_walk.py` is a loud skip | `runner/tests/test_pilot_walk.py:252-277` | Waits on T-B-06 and T-B-07; see G-21 for what is testable now |

Also confirmed loud, not silent: the two Atlassian Keychain skips and the Cursor key skip; `test_escape_suite.py` fails outright when `sandbox-exec` cannot run the profile; `test_dep_verify.py` and `test_recipe_wrappers.py` skip by name when `javac` or `jar` is absent.

## 7. Doc drift

- T-A-25 criterion 23 says the readiness table's `hash` column binds the plan version; `docs/prd/08-configuration.md:35` says each row's hash is that condition's own source, never the plan hash. The code follows the configuration file (`runner/tests/test_s3_structure.py::test_registered_plan_hash_binds_the_readiness_rows_source_hashes`). Fix the ticket text.
- `docs/design/hld/L2-execution-boundary.md` "Not drawn" says only C6 and C3 write tool-result rows; the proxy does (G-25).
- `docs/design/hld/L2-control-plane.md` seats the guard on X2 persistence, X3 dispatch and X7 mounts; the code seats it on five narrower crossings (G-04). One of the two must change.
- `docs/design/hld/L2-control-plane.md` diagram 3 draws the final reviewer-set check inside the S5 ordered list; the code runs it first thing in the S6 driver (`runner/stages/S6.py:92-134`), before assembly, which satisfies R-S6-6 in substance.

## 8. Verified as implemented

What the reviewers checked and found to match, by slice. The per-slice reports carry the row-by-row lists; this is the summary.

- **Record and tree.** Every Initial table of `docs/prd/02-2-entities.md` with its fields; the five Later tables absent; WAL, foreign keys, single connection opener (`runner/db.py`); append-only triggers with the R-T-3 exceptions (except G-12); the fence (`runner/state_table.py`, `runner/anti_goals.py` outside `factory/`); the write barrier (`runner/fs.py` sole writer, AST-scanned); the manifest's full field set, fail-closed resolution, model checks and quorum-gated migration; the whole-tree hash from committed bytes; the eval walk refusing empty or unowned directories; the adoption gate reading local git only; the AB mechanism fixtures with `check_fixture_changes`; export, import and purge across all fourteen T-A-16 criteria; `runs/` ignored; git trees with a disabled push URL and independent base and head checkouts.
- **Control plane.** Every transition of `docs/prd/02-3-ticket-states.md` present (except G-02, G-08) and none extra; close reasons; pause at the next boundary, stop to `aborted_human`, status; all eight crash-recovery criteria including the per-stage kill and rerun; budgets over settled usage with the abort to `escalated`; freshness at the three boundaries and `refresh-base` (all eight criteria); the parallel limit bound to a graduation approval with `unsigned_edit` and `stale_report` refusals; every queue item kind with its minimum context; `cli.py` importing only `stage_interface` and `paths`; the twelve API-exclusivity and import-graph tests of T-B-05.
- **Trust, binding and approvals.** Owners file and authority-policy hash with the identity snapshot; the trust profile schema, class join, dominance, default deny, sanitiser pairs; the governance console's metadata-only writes and mandatory expiry; the guard's fail-closed decision order and `pass_through` re-read; reviewer sets from CODEOWNERS with last-match-wins and separation rules; one immutable approval record per actor and slot, quorum over distinct actors, forked-head refusal; canonical hashing and the plan and review tuple fields; waiver issuance and validity reasons; tags with their target and actor shapes; the verbatim final-review attestation; `packet_defect` bound to the exact record; credential roles fetched by name and never logged.
- **Execution boundary.** Model check before and after the invocation with `infrastructure_failure` on mismatch; envelope reconstruction and the sandbox digest over profile, allowlist, `sandbox.yaml` and environment; the inline limit and excerpt rule; proxy-routed tool results into `results/` with `result_bytes` and `inline`; all eleven escape categories run for real under Seatbelt; copy-on-write copies with disposal in `finally` and recheck; recipe schema validation with digest re-check at dispatch; the six hidden-capability surfaces of R-I-11.
- **Stages S0 to S3.** The field gate; classify-and-redact before the ticket source is written; all fifteen provisional-tier cells; sensitive-path handling; the scrutiny template with no agent at S0; the four fail-closed governance reasons on eligibility; the eight exclusion surfaces; the brief rubric, impact evidence and final-tier rules; two-step archaeology; index use and staleness; EARS restatement with id continuity; the agreement check as child runs; the eight forced categories; the question gate in full; the split rule; the append-only assumption log; the seven plan tables' columns; the size gate in plan and diff modes; typed-recipe-only tasks; traceability (except G-14); the readiness table after the invocation and before the checklist; the risk map from git before the invocation; the bootstrap checklist with `human_verdict` rows hashed into the plan tuple; the planned reviewer set from the Scope table.
- **Stages S4 to S6.** The S5 order matches R-S5-1 and the one-page version step by step through the final approval-binding check (the reviewer-set race guard runs at the top of S6); checks continue after red unless sandbox integrity or tuple construction fails; one `red_check` item; the fix-round eligibility rule, cap from configuration, test-only diff refusal, scope diff and single `validation_only` pass; fix rounds fed the failing recipe outputs; pre-task revalidation; the three-attempt cap and atomic escalation; the control-defect route for an invalid recipe binding; security and dependency recipes inside the copies at AB; trusted-side scripts never inside the sandbox; the packet and PR body opening with the evidence table and the PR body carrying no literal diff; no agent after S4.
- **External systems and outcome.** The `external_write` row shape; one idempotency-key rule over four operation kinds; reconciliation at the start of every state-advancing command; crash injection at all three points; the stub deliverer's unexpected head, existing object and duplicate key; the real GitHub deliverer pushing only the ticket branch to the scratch repository as a draft; `pr_create` and `pr_update` committed in the quorum-completing transaction; the already-closed remote raising `pr_outcome`; the digest as the only Slack write, one intent per channel and slot; the `pr_outcome` item once per ticket; every outcome, revision, exposure, coverage, incident and disposition action of T-B-01 with its refusals; the no-polling AST scan; S7 all Later.
- **Observability and graduation.** All eighteen measure views in the table's order with the reliability view's exclusion set; the forbidden-view list; the report as the only view reader beside the gate; unavailable evidence shown as such; the baseline's selection, guard-checked reads, statuses and post-freeze refusal (except G-10); all nine graduation clauses matching charter section 8; thresholds and configuration hash bound into the owner approval; the view allowlist of T-B-03 criterion 37; benchmarks, observer and proposal absent.
- **HLD conformance.** All 34 components have a code or content home; X1, X4, X5, X9, X10 and X11 hold as drawn; the three ticket-walk loops are wired; the trust-rule spot checks (recipe id, model, credential role) hold.

## 9. Not checked

- The S4 first-attempt reliability unit `(stage, plan_item)` grouping in `stage_reliability_view`.
- `test_graduation*.py` line by line against T-B-03's forty criteria (structure only).
- `factory/config/*.yaml` key by key against every clause of `docs/prd/08-configuration.md` beyond `limits.yaml` and `project.yaml`.
- The `human_verdict` fixtures under `factory/evals/rubrics/` for wording fidelity.
- The Cursor SDK's default tool surface (G-18's severity assumes a shell tool exists).
- Post-graduation distinct-owner enforcement for sensitive slots (unreachable in Initial).
- `runner/readers/github.py` is imported only by tests; whether T-AB-10 was meant to wire it was not chased.

## 10. Suggested order of work

1. G-01, G-02, G-03: three small, well-located fixes to the S4 driver, the state table or `_send_back`, and the S4 validation call; each needs the test its ticket criterion already names, driven end to end rather than on a seeded state.
2. The core-path and record fixes marked **fix** in section 2a: G-07 to G-15, G-20, G-24, G-28 to G-31, G-33 to G-36, and G-21's testable half (report and pre-dispatch assertions on the fixture walk, the digest criterion).
3. The **closed by decision** items need only the dead code removed (G-16) and the manifest's tool list made real per stage (G-17).
4. Nothing on the **deferred** list until the factory is stable; the to-do notes mark the seams.
5. The **wait** items with the live-connection work.

## Revision history

- **v0.4, 2026-09-10.** Six major findings closed in code by parallel fixers: G-07, G-08, G-09, G-12, G-13 and G-14, each with end-to-end tests driven through the real drivers. Section 2a rows updated with what was built and the two simplifications taken (a removal round shares the fix round's `run_kind` and cap; `answer.question_version_hash` stays unwritten). Finding text unchanged.
- **v0.3, 2026-09-10.** The four blocking findings closed in code: G-01, G-02 and G-03 fixed with the end-to-end tests section 10 asked for; G-04's declared crossing set and the S0 intake name aligned to the narrowed R-T-9, with an undeclared crossing now denied. Section 2a rows updated; finding text unchanged.
- **v0.2, 2026-09-10.** Section 2a added with the owner's decisions and the disposition of every finding; PRD v0.19 applied (three Later rows, four rows narrowed, decision 55) and to-do notes placed at the seven code seams the deferred items would occupy. Finding text unchanged.
- **v0.1, 2026-09-10.** First review of the implemented A, AB and B tickets by nine slice reviewers with orchestrator re-verification of every blocking and major finding. 36 findings: 4 blocking, 17 major, 15 minor; 6 known simplifications confirmed; 4 doc-drift items.
