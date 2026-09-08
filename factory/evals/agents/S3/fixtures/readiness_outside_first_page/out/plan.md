## Intent and scrutiny

Widget.compute currently ignores negative input; this plan adds validation so it rejects negative input with a typed error instead of returning a wrong answer. Scrutiny: standard tier, one file touched, no sensitive path.

filler note line 0.

filler note line 1.

filler note line 2.

filler note line 3.

filler note line 4.

filler note line 5.

filler note line 6.

filler note line 7.

filler note line 8.

filler note line 9.

filler note line 10.

filler note line 11.

filler note line 12.

filler note line 13.

filler note line 14.

filler note line 15.

filler note line 16.

filler note line 17.

filler note line 18.

filler note line 19.

filler note line 20.

filler note line 21.

filler note line 22.

filler note line 23.

filler note line 24.

filler note line 25.

filler note line 26.

filler note line 27.

filler note line 28.

filler note line 29.

filler note line 30.

filler note line 31.

filler note line 32.

filler note line 33.

filler note line 34.

filler note line 35.

filler note line 36.

filler note line 37.

filler note line 38.

filler note line 39.

filler note line 40.

filler note line 41.

filler note line 42.

filler note line 43.

filler note line 44.

filler note line 45.

filler note line 46.

filler note line 47.

filler note line 48.

filler note line 49.

filler note line 50.

filler note line 51.

filler note line 52.

filler note line 53.

filler note line 54.

filler note line 55.

filler note line 56.

filler note line 57.

filler note line 58.

filler note line 59.

filler note line 60.

filler note line 61.

filler note line 62.

filler note line 63.

filler note line 64.

filler note line 65.

filler note line 66.

filler note line 67.

filler note line 68.

filler note line 69.

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
| T-1 | implement widget compute |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile | compiles clean | no |

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
