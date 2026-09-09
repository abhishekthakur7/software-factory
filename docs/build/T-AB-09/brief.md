# S5 execution brief

## Outcome

Run the configured project's validation sequence in isolated base and head copies, then run the trusted evidence checks against immutable views. Security controls are declared as pinned local recipes and their unavailable external feed is recorded as a waivable blind spot.

## Boundaries

Only the configured fixture project is supported. Recipe execution remains behind the build sandbox boundary; trusted scripts receive produced evidence and immutable checkouts.

## Failure routing

Lint, compilation, unit, and integration failures can enter the existing fix-round route. End-to-end and all other failures form the existing red-check route. A dependency the sandbox cannot provide is a blind spot, not a fabricated pass or failure.
