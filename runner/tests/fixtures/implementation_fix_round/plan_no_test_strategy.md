## Scope and discretion

| path | action | reason |
|---|---|---|
| src/main/java/com/fixture/Widget.java | touch | implements widget compute |
| src/test/java/com/fixture/WidgetUnitTest.java | touch | exercises the guard clause |

## Tasks

| id | title | depends_on | criteria | files | validation_recipe | validation_args | expected_result | no_behaviour_change |
|---|---|---|---|---|---|---|---|---|
| T-1 | implement widget compute |  | AC-1 | src/main/java/com/fixture/Widget.java | fixture_compile | target=out/compile | compiles clean | no |

## Test strategy

| test | action | size | criteria | proves |
|---|---|---|---|---|
