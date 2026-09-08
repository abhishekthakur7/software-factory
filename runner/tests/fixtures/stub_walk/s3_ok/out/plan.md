## Intent and scrutiny

Widget.compute currently ignores negative input; this plan adds validation so it rejects negative input with a typed error instead of returning a wrong answer. Scrutiny: standard tier, one file touched, no sensitive path.

## Readiness

| condition | status | source_artefact | hash | waiver_id | note |
|---|---|---|---|---|---|
| restatement_agreed | pass | criteria | cccccccc |  | both criteria agreed |
| questions_closed | pass | question_set | qqqqqqqq |  | no open blocking questions |
| impact_evidence | pass | brief | bbbbbbbb |  | every row covered |
| risk_map | pass | risk_map | rrrrrrrr |  | attached and named |
| linked_sources | pass | brief | bbbbbbbb |  | every source dated |
| size_gate | pass | plan:Size | ssssssss |  | within threshold |
| reviewer_set | pass | reviewer_set | vvvvvvvv |  | s3_reviewer: abhishek |

## Risk map

| place | why |
|---|---|
| src/main/java/com/fixture/Widget.java | sole touched file; a fresh guard clause changes its error path, worth a reviewer's eyes even though ownership is clear |

## Goals and non-goals

Goal: reject negative input. Non-goal: changing the return type for valid input.

## Approach

Add a guard clause at the top of Widget.compute that raises a typed error for negative input.

## Alternatives

| alternative | rejected_because |
|---|---|
| validate at the caller instead | leaves the library unsafe for every other caller that skips validation |

## Scope and discretion

| path | action | reason |
|---|---|---|
| src/main/java/com/fixture/Widget.java | touch | implements the widget |

## Dependencies

| package | from_version | to_version | kind | reason |
|---|---|---|---|---|

## Archaeology and characterization tests

| path | classification | characterization_task | alters_captured_behaviour |
|---|---|---|---|
| src/main/java/com/fixture/Widget.java | explained |  | no |

## Abstraction and separate debt

| kind | unit | existing | reason |
|---|---|---|---|

## Contracts

| unit | kind | source_declaration | input | output | errors | side_effects | invariants | authorization | ordering_concurrency | transaction_persistence | compatibility |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Widget.compute | function | unchanged: com.fixture.WidgetUnitTest#testComputeRejectsNegative | changed: com.fixture.WidgetUnitTest#testComputeRejectsNegative | unchanged: com.fixture.WidgetUnitTest#testComputeRejectsNegative | changed: com.fixture.WidgetUnitTest#testComputeRejectsNegative | unchanged: com.fixture.WidgetUnitTest#testComputeRejectsNegative | unchanged: com.fixture.WidgetUnitTest#testComputeRejectsNegative | unchanged: com.fixture.WidgetUnitTest#testComputeRejectsNegative | unchanged: com.fixture.WidgetUnitTest#testComputeRejectsNegative | unchanged: com.fixture.WidgetUnitTest#testComputeRejectsNegative | unchanged: com.fixture.WidgetUnitTest#testComputeRejectsNegative |

## Semantic-contract checklist

Widget.compute: input validation is the only changed field, output and side effects unchanged.

## Tasks

| id | title | depends_on | criteria | files | validation_recipe | validation_args | expected_result | no_behaviour_change |
|---|---|---|---|---|---|---|---|---|
| T-1 | implement widget compute |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile | compiles clean | no |

## Test strategy

| test | action | size | criteria | proves |
|---|---|---|---|---|
| WidgetUnitTest | add | small | AC-1,AC-2 | widget compute behaves per AC-1 and AC-2 |

## Rollout

### Flags

| flag | expected_life | owner | removal_condition | cleanup_task |
|---|---|---|---|---|

### Ramp

| step | description |
|---|---|

### Guardrails

| metric | query | critical_threshold |
|---|---|---|

### Kill trigger

| trigger | default_response |
|---|---|
| Widget.compute rejects previously-accepted negative input in production | rollback the deploy and restore the previous compute implementation |

### Log verification

| query | pass_pattern | fail_pattern |
|---|---|---|

## Size

| estimated_lines | estimated_files | basis | justification |
|---|---|---|---|
| 10 | 1 | task table sum |  |

## Impact evidence and blind spots

No downstream service depends on negative input being accepted; no blind spot.

## Assumptions

assumption 1: callers never rely on negative input being silently accepted.

## Unknowns

none

## Required approvers

s3_reviewer
