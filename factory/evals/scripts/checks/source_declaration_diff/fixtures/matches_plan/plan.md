## Contracts

| unit | kind | source_declaration | input | output | errors | side_effects | invariants | authorization | ordering_concurrency | transaction_persistence | compatibility |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Widget.compute | function | unchanged: Widget.java:4 | int x | int | none | none | deterministic | none | single-threaded | none | unchanged |
| Widget.computeTwice | function | changed: new doubling method, Widget.java:9 | int x | int | none | none | deterministic | none | single-threaded | none | unchanged |
