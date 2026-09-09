# Dependency verification plan

1. Add a pinned dependency-resolution recipe and declared registry/cache policy to the typed catalogue.
2. Implement a JSON check executable that compares base and head dependency records with the plan's Dependencies table and policy.
3. Add the S5 registry route, eval fixtures for each rejection path, and unit coverage for both views and the bounded evidence shape.

## Verification

Run the dedicated dependency-verification tests, recipe catalogue tests, and the eval-directory walk.
