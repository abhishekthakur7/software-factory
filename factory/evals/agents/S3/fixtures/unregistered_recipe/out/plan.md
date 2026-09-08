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

Widget.java is the only touched file; the last twelve months show two authors with the primary author holding a clear majority of commits, so no reviewer beyond the size gate's ordinary check is named.

## Goals and non-goals

Goal: reject negative input. Non-goal: changing the return type for valid input.

## Approach

Add a guard clause at the top of Widget.compute that raises a typed error for negative input.

## Alternatives

Considered and rejected: validating at the caller instead, which would leave the library unsafe for other callers.

## Scope and discretion

| path | action | reason |
|---|---|---|
| src/main/java/com/fixture/Widget.java | touch | implements the widget |

## Dependencies

| package | from_version | to_version | kind | reason |
|---|---|---|---|---|

## Archaeology and characterization tests

Widget.compute is explained: its one prior commit's message and the existing unit test both document intended behaviour for valid input.

## Abstraction and separate debt

No new abstraction introduced; the guard clause is local to Widget.compute.

## Contracts

| unit | kind | source_declaration | input | output | errors | side_effects | invariants | authorization | ordering_concurrency | transaction_persistence | compatibility |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Widget.compute | function | Widget.java:42 | int x | int | none | none | deterministic | none | single-threaded | none | unchanged |

## Semantic-contract checklist

Widget.compute: input validation is the only changed field, output and side effects unchanged.

## Tasks

| id | title | depends_on | criteria | files | validation_recipe | validation_args | expected_result | no_behaviour_change |
|---|---|---|---|---|---|---|---|---|
| T-1 | implement widget compute |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | not_a_real_recipe | target=out/compile | compiles clean | no |

## Test strategy

| test | action | size | criteria | proves |
|---|---|---|---|---|
| WidgetTest | add | small | AC-1,AC-2 | widget compute behaves per AC-1 and AC-2 |

## Rollout

No flag; this is a small_feature ticket with no ramp. No guardrail metrics beyond the existing test suite.

## Size

| estimated_lines | estimated_files | basis | justification |
|---|---|---|---|
| 80 | 1 | task table sum |  |

## Impact evidence and blind spots

No downstream service depends on negative input being accepted; no blind spot.

## Assumptions

assumption 1: callers never rely on negative input being silently accepted.

## Unknowns

none

## Required approvers

s3_reviewer
