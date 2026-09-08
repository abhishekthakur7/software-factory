---
kind: convention
source: factory/evals/fixture-project
owner: abhishek
last_verified: 2026-09-08
staleness_rule: default
paths:
  - src/main/java/**
---

## Package layout

Every class lives under `com.fixture`, one package for the whole project;
`src/main/java/com/fixture/**` is the production source root.

## Test class style

A test is a plain class with a `main` method, no test framework on the
classpath. `main` calls each test method through a small `run(name,
Runnable)` helper that prints `ran: <FullyQualifiedClass>#<method>` before
running it, and records a failure on a thrown exception rather than exiting
immediately, so one failing method does not hide the rest.

## Test source roots

`src/test/java/**/*UnitTest.java` (unit), `src/it/java/**/*IntegrationTest.java`
(integration), and `src/e2e/java/**/*EndToEndTest.java` (end-to-end) are
separate source roots, each compiled and run by its own recipe in
`factory/config/command-recipes.yaml`.

## Dependencies

Declared in `pom.xml` under `<dependencies>`, resolved against the vendored
layout under `vendor/<group>/<artifact>/<version>/<artifact>-<version>.pom`,
never a live repository.
