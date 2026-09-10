## Readiness

| condition | status | source_artefact | hash | waiver_id | note |
|---|---|---|---|---|---|
| restatement_agreed | pass | criteria | cccccccc |  | both criteria agreed |
| questions_closed | pass | question_set | qqqqqqqq |  | no open blocking questions |
| impact_evidence | blind_spot | brief | bbbbbbbb | W-1 | one row's coverage is unknown |
| risk_map | pass | risk_map | rrrrrrrr |  | attached and named |
| linked_sources | pass | brief | bbbbbbbb |  | every source dated |
| size_gate | pass | plan:Size | ssssssss |  | within threshold |
| reviewer_set | pass | reviewer_set | vvvvvvvv |  | plan_reviewer: abhishek |

## Scope and discretion

| path | action | reason |
|---|---|---|
| src/main/java/com/fixture/Widget.java | touch | implements the widget |
| src/main/java/com/fixture/WidgetHelper.java | create | new helper extracted from Widget |

## Contracts

| unit | kind | source_declaration | input | output | errors | side_effects | invariants | authorization | ordering_concurrency | transaction_persistence | compatibility |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Widget.compute | function | Widget.java:42 | int x | int | none | none | deterministic | none | single-threaded | none | unknown: not yet decided |

## Tasks

| id | title | depends_on | criteria | files | validation_recipe | validation_args | expected_result | no_behaviour_change |
|---|---|---|---|---|---|---|---|---|
| T-1 | implement widget compute |  | AC-1,AC-2 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile retries=2 | compiles clean | no |
| T-2 | extract helper | T-1 | AC-1 | src/main/java/com/fixture/WidgetHelper.java | fixture_unit | strict=true | tests pass | no |
