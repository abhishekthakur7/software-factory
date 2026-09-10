## Archaeology and characterization tests

| path | classification | characterization_task | alters_captured_behaviour |
|---|---|---|---|
| src/legacy/Parser.java | unexplained | T-2 | yes |

## Tasks

| id | title | depends_on | criteria | files | validation_recipe | validation_args | expected_result | no_behaviour_change |
|---|---|---|---|---|---|---|---|---|
| T-2 | characterize Parser.parse |  | AC-1 | src/legacy/Parser.java | fixture_unit | target=out | pins current behaviour | no |

## Unknowns

Whether src/legacy/Parser.java's undocumented branch at line 80 is load-bearing or accidental is unresolved; the change may alter it.
