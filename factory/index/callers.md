---
kind: caller
source: hand-recorded; no live service registry exists at this scale
owner: abhishek
last_verified: 2026-09-08
staleness_rule: default
paths:
  - src/main/java/com/fixture/Greeter.java
---

## checkout-web (tier T1)

`checkout-web` calls `com.fixture.Greeter#greet` through the vendored
`fixture-project` artifact to render the checkout confirmation's greeting
line. It is the fixture project's one known inbound consumer, and the only
caller currently registered against it in the index.
