# Failure-mode catalogue

Mirrors the failure-mode table in `docs/charter.md` at its current version,
keyed by a descriptive name in place of the charter's numbering (the PRD's
key table maps one to the other).
Cost and frequency are computed from tag rows rather
than stored here, so this table carries only what a tag's `fm_id` needs to
resolve: the id, the stage the failure belongs to, the failure itself, and
its consequence. A change to the mirrored table, or to the event-kind list
below, is a catalogue decision recorded in `decisions.md` before it lands.

## Failure modes

| id | stage | failure | consequence |
|---|---|---|---|
| unjustified_abstraction | Planning | Abstraction introduced without justification, or a needed one skipped | Harder maintenance or duplication; rework in review |
| load_bearing_hack | Planning | Load-bearing hack modified or removed because it looked wrong | Edge-case regression; production risk |
| pattern_ignored | Planning | Existing style, utilities, and patterns ignored; new patterns introduced alongside old | Inconsistency; review churn |
| tech_debt_mixing | Planning | Tech debt silently fixed inside a feature change, or never surfaced at all | Mixed-concern diffs that are hard to review, or debt accumulates |
| scope_creep | Planning | Scope creep; the agent extends the change beyond the ticket | Larger diff, longer review, larger blast radius |
| jumps_to_implementation | Requirements | Agent jumps from a large product requirement straight to implementation without checking completeness | Multiple revision cycles; the wrong thing built correctly |
| question_noise | Requirements | Meaningful questions mixed with useless ones | Humans stop reading questions; the ones that would have simplified the spec go unanswered |
| missing_scenarios | Requirements | Product scenarios not surfaced: error paths, migration, backward compatibility, concurrency | Late discovery; rework |
| parallel_fatigue | Cross-cutting | A human cannot hold parallel tickets because every switch back demands re-immersion; switches imposed from outside, into cognitively distant work, are the expensive kind | Resumption cost on every switch; the second ticket gets half-hearted answers |
| unreviewable_diff | Review | Diff arrives without narrative; the reviewer reconstructs intent line by line | Review is slow and shallow; humans avoid it |
| filler_tests | Implementation | Filler tests that pass but do not exercise behaviour | False sense of safety |
| filler_comments | Implementation | Filler comments that restate the code | Noise; masks the absence of needed comments |
| missing_comments | Implementation | Missing comments where the code is not self-explanatory | The next reader, human or agent, misreads intent |
| unknown_impact | Context gathering | Impacted services unknown at the start of the change | Change lands with an unknown blast radius; downstream breakage |
| contract_drift | Implementation | Contract drift: an input, output, or error contract of touched code changes without being declared | Later agents and humans build on the wrong assumption; the next change to the same code fails |
| false_rigor | Requirements, Planning | False rigor: a spec, plan, or question set that is structurally complete but semantically vague passes on appearance | The wrong thing built correctly, with a paper trail that says otherwise |
| memory_rot | Cross-cutting | Memory rot: a rubric line, instruction, or context index entry stops being true with no signal; or the owning engineer's understanding of a changed subsystem decays while tests stay green | Agent behaviour degrades and the model is blamed; the subsystem becomes illegible to its owner |
| agent_only_review | Review | Agent-only review: an agent pass is treated as satisfying human review, or the human gate is implemented as a configurable default and switched off | Merge quality drops measurably; nobody holds the judgment |
| slow_failure | Implementation | Slow failure: an ungrounded or blocked agent keeps working, expanding context and cost, instead of failing early and escalating | Wasted budget; a late escalation with a long history to read |
| hallucinated_dependency | Implementation | Hallucinated dependency: the agent uses a package, API, function, or version that does not exist or does not behave as assumed | Build or runtime failure at best; a subtly wrong behaviour that passes review at worst |
| state_loss | Cross-cutting | State loss: over a long task the agent forgets what it has done, repeats or skips steps, or contradicts its own earlier decision | Wasted budget; inconsistent change; deviations the self-report does not mention |
| loop_drift | Cross-cutting | Loop drift: the improvement loop, pointed at a cost, throughput, or touchpoint number, proposes locally reasonable changes that remove context, questions, or gates; each is merged on its own merits and the factory drifts back to a pipeline | jumps_to_implementation, question_noise, unknown_impact, and agent_only_review return with a paper trail that says every step was justified |
| unsafe_execution | Implementation, Checks | Untrusted execution escapes its intended boundary: an agent or repository build reads host data, reaches an undeclared network service, uses ambient credentials, changes another checkout, or pushes without approval | Source or credential disclosure; host or repository damage; an unaudited external action |
| data_boundary_breach | Cross-cutting | Data crosses an unapproved trust boundary, or is retained, exposed, or reused beyond the recorded policy | Confidentiality or compliance breach; the factory cannot show what a provider or operator was allowed to see |
| stale_approval | Planning, Review | An approval remains in force after its base source, factory configuration, approved artefact, branch diff, required reviewer set, or check evidence changes | The human appears to have approved a state they never reviewed; stale judgment reaches a pull request or merge |

## Tag schema

The `tag` table: `id`, `ticket_id`, `event_kind`, `fm_id` (one catalogue id
above, required on every row), `ref` (the exact stage run, question or
question version, artefact, queue item, approval record, or waiver the tag
names), `severity`, `note`, `tagged_by`, `tagged_at`, `resolves_tag_id`,
`resolution_evidence_ref` (a prior defect tag and immutable evidence that
resolves it, optional and either both present or both absent).

Every event kind and who writes it:

| event_kind | tagged_by | severity required |
|---|---|---|
| override | human | no |
| send_back | human | no |
| revision_after_approval | human | no |
| abandoned | human | no |
| packet_defect | human | no |
| flag_correction | human | no |
| incident | human | yes |
| policy_exception | human | yes |
| stale_index | mechanical | no |
| escalation | mechanical | no |
| control_defect | mechanical | yes |

A human `tagged_by` is the identity who made the decision; a mechanical
one is always the runner's own actor identity, never a person's.
