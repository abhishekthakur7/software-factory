## Readiness

placeholder, overwritten by handoff_ready

## Risk map

| place | why |
|---|---|
| src/main/java/com/fixture/Widget.java | sole touched file; a fresh guard clause changes its error path |

## Size

| estimated_lines | estimated_files | basis | justification |
|---|---|---|---|
| 80 | 1 | task table sum |  |

## Assumptions

assumption A-1: callers never rely on negative input being silently accepted.
