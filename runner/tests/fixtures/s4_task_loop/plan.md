## Scope and discretion

| path | action | reason |
|---|---|---|
| src/main/java/com/fixture/Widget.java | touch | implements widget compute |
| src/main/java/com/fixture/WidgetHelper.java | create | helper extracted from Widget |

## Contracts

| unit | kind | source_declaration | input | output | errors | side_effects | invariants | authorization | ordering_concurrency | transaction_persistence | compatibility |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Widget.compute | function | unchanged: Widget.java:1 | int x | int | none | none | deterministic | none | single-threaded | none | unchanged |

## Tasks

| id | title | depends_on | criteria | files | validation_recipe | validation_args | expected_result | no_behaviour_change |
|---|---|---|---|---|---|---|---|---|
| T-1 | implement widget compute |  | AC-1 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile | compiles clean | no |
| T-2 | add widget helper | T-1 | AC-1 | src/main/java/com/fixture/WidgetHelper.java | fixture_compile | target=out/compile | compiles clean | no |
