## Tasks

| id | title | depends_on | criteria | files | validation_recipe | validation_args | expected_result | no_behaviour_change |
|---|---|---|---|---|---|---|---|---|
| T-3 | rename internal variable |  |  | src/main/Widget.java | fixture_lint | target=out | lints clean | yes |

## Test strategy

| test | action | size | criteria | proves |
|---|---|---|---|---|
| WidgetRenameTest | add | small | T-3 | behaviour is unchanged after the rename |
