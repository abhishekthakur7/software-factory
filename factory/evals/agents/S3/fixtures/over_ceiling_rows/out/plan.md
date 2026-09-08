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
| T-0 | task 0 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile0 | compiles clean | no |
| T-1 | task 1 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile1 | compiles clean | no |
| T-2 | task 2 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile2 | compiles clean | no |
| T-3 | task 3 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile3 | compiles clean | no |
| T-4 | task 4 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile4 | compiles clean | no |
| T-5 | task 5 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile5 | compiles clean | no |
| T-6 | task 6 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile6 | compiles clean | no |
| T-7 | task 7 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile7 | compiles clean | no |
| T-8 | task 8 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile8 | compiles clean | no |
| T-9 | task 9 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile9 | compiles clean | no |
| T-10 | task 10 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile10 | compiles clean | no |
| T-11 | task 11 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile11 | compiles clean | no |
| T-12 | task 12 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile12 | compiles clean | no |
| T-13 | task 13 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile13 | compiles clean | no |
| T-14 | task 14 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile14 | compiles clean | no |
| T-15 | task 15 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile15 | compiles clean | no |
| T-16 | task 16 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile16 | compiles clean | no |
| T-17 | task 17 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile17 | compiles clean | no |
| T-18 | task 18 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile18 | compiles clean | no |
| T-19 | task 19 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile19 | compiles clean | no |
| T-20 | task 20 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile20 | compiles clean | no |
| T-21 | task 21 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile21 | compiles clean | no |
| T-22 | task 22 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile22 | compiles clean | no |
| T-23 | task 23 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile23 | compiles clean | no |
| T-24 | task 24 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile24 | compiles clean | no |
| T-25 | task 25 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile25 | compiles clean | no |
| T-26 | task 26 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile26 | compiles clean | no |
| T-27 | task 27 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile27 | compiles clean | no |
| T-28 | task 28 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile28 | compiles clean | no |
| T-29 | task 29 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile29 | compiles clean | no |
| T-30 | task 30 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile30 | compiles clean | no |
| T-31 | task 31 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile31 | compiles clean | no |
| T-32 | task 32 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile32 | compiles clean | no |
| T-33 | task 33 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile33 | compiles clean | no |
| T-34 | task 34 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile34 | compiles clean | no |
| T-35 | task 35 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile35 | compiles clean | no |
| T-36 | task 36 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile36 | compiles clean | no |
| T-37 | task 37 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile37 | compiles clean | no |
| T-38 | task 38 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile38 | compiles clean | no |
| T-39 | task 39 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile39 | compiles clean | no |
| T-40 | task 40 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile40 | compiles clean | no |
| T-41 | task 41 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile41 | compiles clean | no |
| T-42 | task 42 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile42 | compiles clean | no |
| T-43 | task 43 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile43 | compiles clean | no |
| T-44 | task 44 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile44 | compiles clean | no |
| T-45 | task 45 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile45 | compiles clean | no |
| T-46 | task 46 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile46 | compiles clean | no |
| T-47 | task 47 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile47 | compiles clean | no |
| T-48 | task 48 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile48 | compiles clean | no |
| T-49 | task 49 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile49 | compiles clean | no |
| T-50 | task 50 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile50 | compiles clean | no |
| T-51 | task 51 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile51 | compiles clean | no |
| T-52 | task 52 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile52 | compiles clean | no |
| T-53 | task 53 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile53 | compiles clean | no |
| T-54 | task 54 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile54 | compiles clean | no |
| T-55 | task 55 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile55 | compiles clean | no |
| T-56 | task 56 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile56 | compiles clean | no |
| T-57 | task 57 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile57 | compiles clean | no |
| T-58 | task 58 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile58 | compiles clean | no |
| T-59 | task 59 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile59 | compiles clean | no |
| T-60 | task 60 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile60 | compiles clean | no |
| T-61 | task 61 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile61 | compiles clean | no |
| T-62 | task 62 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile62 | compiles clean | no |
| T-63 | task 63 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile63 | compiles clean | no |
| T-64 | task 64 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile64 | compiles clean | no |
| T-65 | task 65 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile65 | compiles clean | no |
| T-66 | task 66 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile66 | compiles clean | no |
| T-67 | task 67 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile67 | compiles clean | no |
| T-68 | task 68 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile68 | compiles clean | no |
| T-69 | task 69 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile69 | compiles clean | no |
| T-70 | task 70 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile70 | compiles clean | no |
| T-71 | task 71 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile71 | compiles clean | no |
| T-72 | task 72 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile72 | compiles clean | no |
| T-73 | task 73 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile73 | compiles clean | no |
| T-74 | task 74 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile74 | compiles clean | no |
| T-75 | task 75 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile75 | compiles clean | no |
| T-76 | task 76 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile76 | compiles clean | no |
| T-77 | task 77 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile77 | compiles clean | no |
| T-78 | task 78 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile78 | compiles clean | no |
| T-79 | task 79 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile79 | compiles clean | no |
| T-80 | task 80 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile80 | compiles clean | no |
| T-81 | task 81 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile81 | compiles clean | no |
| T-82 | task 82 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile82 | compiles clean | no |
| T-83 | task 83 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile83 | compiles clean | no |
| T-84 | task 84 |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile84 | compiles clean | no |

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
