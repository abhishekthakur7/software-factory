# Dependency verification brief

## Outcome

Verify the configured project's declared dependency resolution independently at the immutable base and head views. The check compares normalized package changes to the approved dependency plan and refuses resolution sources outside the build sandbox's registry routes.

## Boundaries

The configured fixture project remains the only project profile. The implementation does not add a project-specific package manager, remote source, or implicit dependency discovery contract.

## Evidence

The check emits only package, from-version, to-version, and change-kind values. The build runner owns sandbox execution and route refusal; the verifier consumes its recorded resolution output.
