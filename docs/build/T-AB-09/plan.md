# S5 execution plan

1. Declare security controls, their pinned inputs, suppressions, severity policies, and feed route in configuration.
2. Add a security-check executable that produces bounded results from declared evidence.
3. Extend S5's sequence to provision copies, execute build recipes, record trusted checks, and route failures through existing policy.
4. Cover order, blind spots, and routing with focused tests and an eval fixture.

## Verification

Run S5 tests, security-check tests, recipe catalogue tests, and the eval-directory walk.
