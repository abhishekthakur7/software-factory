# L2 — External systems (domain 6)

| | |
|---|---|
| Status | Draft v0.4 |
| Date | 2026-09-10 |
| Owner | Abhishek Thakur |
| Derived from | `docs/prd/prd.md` v0.18; `docs/design/milestones.md` v0.6; `docs/charter.md` v0.14 |
| Layer | 2 |
| Domain | 6, External systems |
| Domain rule | A component sits in the domain where its code runs or its file lives, and under whose trust it acts. Domain 6, External systems, is everything outside the engineer's machine, plus the two host facilities the runner trusts: the credential store and the scheduler. Trust (README §2): content untrusted; the credential store and scheduler are trusted host facilities. |

**Legend.** S0 intake; S1 context gathering; S5 cleanup pass; S6 human review; S7 PR checks and merge (Later); X3 dispatch; X5 outside access; X6 model reach; X8 person sees outside; X9 factory change; X11 sandbox wall; C1 `factory` command (stage interface); C3 run orchestration; C5 guard; C6 stage drivers; C7 external access; F1 tree and change control; F3 agent definitions and skills; F8 fixtures and evals; G2 the wall (launcher, recipe runner, OS policy, loopback proxy); G3 sandbox interior; E1 Atlassian server (Jira and Confluence); E2 GitHub; E3 Slack; E4 hosted model endpoint; E5 host credential store and scheduler; E6 package registries and vulnerability feeds; H1 person and roles.

## How to read

The first diagram is the domain picture: the Atlassian server (E1) through to the package registries and vulnerability feeds (E6), split into their several faces where one system plays more than one role (GitHub's three repositories; the credential store's five roles), each labelled with what it is used for and from which step. The crossings that reach domain 6 are drawn from border stub nodes — the `factory` command (C1), external access (C7), the loopback proxy (G2), the sandbox interior (G3), the person (H1), tree and change control (F1) — carrying the same ids they hold in the control-plane, execution-boundary, human-surface and factory-as-code files; nothing about those components is redrawn here beyond the one label needed to anchor the edge. The second diagram follows each credential role on its own: where the host credential store hands it out, which trust-profile route authorises it, the step it first works at, and what it may never do. Unmarked labels hold from Milestone A; a step written after a label (`AB`, `B`, `Later`) marks when that fact starts being true, and a dotted edge (`-.->`) carries every crossing that only holds from AB, B or Later — nearly every edge into a real outside system, since Milestone A runs on local fixtures and stub deliverers. A thick edge marks the main ticket path only; nothing in this domain sits on that path, so no edge here is thick. Every crossing edge in these diagrams passes the guard (C5) and leaves one `guard_decision` row; the guard's seats are drawn once, in `L2-control-plane.md`, and are not redrawn here.

Every domain-6 node except the host credential store and scheduler (E5) is shaded red, the untrusted-content class, because everything else this domain returns is content the guard must classify before it is trusted. The credential store and scheduler is shaded a distinct, unmarked colour instead: the domain rule above states the exception by name, so it is drawn as a trusted host facility, not as untrusted content.

The runtime key's path is one route across both diagrams: the runner fetches it, with every other credential, by role from the host credential store (E5) over outside access (X5), landing on external access (C7) — never on the sandbox or the launcher directly, since no crossing in the register runs domain 6 to domain 3. From there the key travels inside the control plane and the execution boundary, not across a domain-6 border: the stage drivers (C6) and run orchestration (C3) hand it to the launcher inside the dispatch envelope (X3 dispatch), and the launcher supplies it to the agent sandbox alone across the sandbox wall (X11). Neither dispatch nor the sandbox wall touches this domain, so that hand-off is stated here as a note, not drawn as an edge; no other credential ever reaches a sandbox by any route. What domain 6 does draw is the key's use once it is inside: the sandbox interior (G3) reaching the hosted model endpoint (E4) directly at Milestone A, and, from AB, the loopback proxy (G2) in front of it — both on model reach (X6), which does cross into this domain.

Left out on purpose: how each outside system authenticates internally (Jira/Confluence's own auth is "outside this design by owner decision," Appendix B, model reach (X6)); the git-tree mechanics of the pinned checkout itself (clone, worktree, `base_sha`), which belong to the record and control-plane files; and the trust profile's own class-and-route policy content, which belongs to the factory-as-code file. Grafana, OpenSearch, AWS and LaunchDarkly are not drawn at all — the charter places them out of scope for the factory, not merely Later (see Not drawn).

The first diagram shows the six external systems, their several faces, and every crossing that reaches them.

```mermaid
flowchart TB
  C1["factory command (C1)<br/>stage interface"]
  C7["external access (C7)<br/>control plane"]
  G2["loopback proxy (G2)<br/>execution boundary wall"]
  G3["sandbox interior (G3)<br/>execution boundary"]
  H1["person and roles (H1)<br/>human surface"]
  F1["tree and change control (F1)<br/>factory as code"]

  subgraph D6["Domain 6 — External systems"]
    E1["Atlassian server (E1)<br/>Jira and Confluence<br/>(Later: Confluence sync)"]

    subgraph E2["GitHub (E2)"]
      E2_pilot["pilot service remote"]
      E2_scratch["scratch repo<br/>(outbox test)"]
      E2_factory["factory repository<br/>(where the X9 factory<br/>change PR lands)"]
    end

    E3["Slack (E3)<br/>digest post, one tool"]

    E4["hosted model<br/>endpoint (E4)"]

    subgraph E5["host credential store<br/>and scheduler (E5)"]
      E5_runtime["runtime key role"]
      E5_atlassian["Jira/Confluence role"]
      E5_github["GitHub role"]
      E5_slack["Slack role"]
      E5_sched["scheduler entry<br/>launchd or cron"]
    end

    subgraph E6["package registries<br/>and vulnerability feeds (E6)"]
      E6_reg["recipe-declared<br/>registries"]
      E6_vuln["vulnerability-<br/>database feed"]
    end
  end

  C7 -.->|"Jira/Confluence: intake (S0) read,<br/>feedback, baseline — AB<br/>(X5 outside access)"| E1
  C7 -.->|"GitHub: fetch, CODEOWNERS,<br/>push+PR after quorum — AB<br/>(X5 outside access)"| E2_pilot
  C7 -.->|"GitHub: outbox test — AB<br/>(X5 outside access)"| E2_scratch
  C7 -.->|"Slack: digest, five fields — AB<br/>(X5 outside access)"| E3
  E5 -->|"credentials by role:<br/>runtime key A; other roles AB<br/>(X5 outside access)"| C7
  E5_sched -.->|"invokes factory digest (AB),<br/>never a stage<br/>(X5 outside access)"| C1

  G3 -->|"A: direct over<br/>the runtime key<br/>(X6 model reach)"| E4
  G2 -.->|"proxied — AB<br/>(X6 model reach)"| E4
  G2 -.->|"no runner credential;<br/>auth outside design — AB<br/>(X6 model reach)"| E1
  G2 -.->|"no credential — AB<br/>(X6 model reach)"| E6_reg
  G2 -.->|"no credential — AB<br/>(X6 model reach)"| E6_vuln

  H1 -->|"via a GitHub pull request — A<br/>(X9 factory change)"| F1
  E2_pilot -.->|"draft PR — AB<br/>(X8 person sees outside)"| H1
  E3 -.->|"digest read — AB<br/>(X8 person sees outside)"| H1

  classDef untrusted fill:#fde8e8,stroke:#b91c1c
  classDef hostFacility fill:#fff7ed,stroke:#9a3412
  class E1,E2,E2_pilot,E2_scratch,E2_factory,E3,E4,E6,E6_reg,E6_vuln untrusted
  class E5,E5_runtime,E5_atlassian,E5_github,E5_slack,E5_sched hostFacility
```

The second diagram follows each credential role from the host credential store to its authorising trust-profile route, its first step, and what it can never do. It draws the credential fetch (X5 outside access) into external access (C7) and the runtime key's eventual use (X6 model reach) out of the sandbox interior (G3) and the loopback proxy (G2) as two separate edges, with nothing joining them: the hand-off between the two, through the dispatch and the wall, is a control-plane and execution-boundary fact, stated below as a note rather than drawn.

```mermaid
flowchart TB
  E5_runtime["runtime key role (E5)"]
  E5_atlassian["Jira/Confluence role (E5)"]
  E5_github["GitHub role (E5)"]
  E5_slack["Slack role (E5)"]
  E5_sched["scheduler entry (E5)"]

  C7["external access (C7)<br/>the runner, control plane"]
  C1["factory command (C1)<br/>stage interface"]
  G3["sandbox interior (G3)<br/>execution boundary"]
  G2["loopback proxy (G2)<br/>execution boundary wall"]

  E4["hosted model endpoint (E4)"]
  E1["Atlassian server (E1)"]
  E2_pilot["GitHub (E2)<br/>pilot + scratch"]
  E3["Slack (E3)"]
  E6["registries and<br/>vulnerability feed (E6)"]

  E5_runtime -->|"runtime key, A<br/>(X5 outside access)"| C7
  E5_atlassian -.->|"AB (X5 outside access)"| C7
  E5_github -.->|"AB (X5 outside access)"| C7
  E5_slack -.->|"AB (X5 outside access)"| C7

  C7 -.->|"Atlassian: intake (S0) read,<br/>feedback, baseline — AB<br/>(X5 outside access)"| E1
  C7 -.->|"never"| N2["Never: write beyond one<br/>idempotent Jira feedback;<br/>enter a sandbox"]

  C7 -.->|"GitHub role: human review (S6)<br/>after quorum, plus intake (S0) and<br/>cleanup pass (S5) reads — AB<br/>(X5 outside access)"| E2_pilot
  C7 -.->|"never"| N3["Never: push before quorum;<br/>any ref but ticket branch;<br/>merge, approve, rerun<br/>Actions; enter a sandbox"]

  C7 -.->|"Slack role: digest command — AB<br/>(X5 outside access)"| E3
  C7 -.->|"never"| N4["Never: post anything but<br/>the digest; enter a sandbox"]

  E5_sched -.->|"invokes factory digest (AB),<br/>never a stage<br/>(X5 outside access)"| C1
  C1 -.->|"never"| N6["Never: start a stage or<br/>an agent invocation"]

  G3 -->|"A: direct over<br/>the runtime key<br/>(X6 model reach)"| E4
  G2 -.->|"proxied — AB<br/>(X6 model reach)"| E4
  G3 -.->|"never"| N1["Never: outside the proxy<br/>route; a fallback model;<br/>a build sandbox"]

  G2 -.->|"context gathering (S1),<br/>no runner credential — AB<br/>(X6 model reach)"| E1

  G2 -.->|"registry + vuln feed,<br/>credential none — AB<br/>(X6 model reach)"| E6
  G2 -.->|"never"| N5["Never: an endpoint outside<br/>the recipe-declared allowlist"]

  classDef untrusted fill:#fde8e8,stroke:#b91c1c
  class E4,E1,E2_pilot,E3,E6 untrusted
```

The runtime key's onward path, once external access (C7) has fetched it: the control plane hands it to the launcher inside the dispatch envelope over dispatch (X3), and the launcher alone supplies it to an agent sandbox over the sandbox wall (X11) — neither crossing touches domain 6, so neither is drawn above. No credential but the runtime key ever reaches a sandbox by any route; the Atlassian, GitHub and Slack roles stop at external access.

## Derivation table

| Component or part | `milestones.md` block | Requirement rows | First step |
|---|---|---|---|
| E1 — Atlassian server (Jira, Confluence) | External access | R-S0-1, R-S1-4, R-H-10, R-O-6 | AB (Later: R-H-10 Confluence sync) |
| E2 — GitHub | External access | R-T-11, R-S6-3, R-S7-1, R-S7-2, R-S7-6 | AB (Later: R-S7-1, R-S7-2, R-S7-6) |
| E2_pilot — pilot service remote | External access | R-S6-3, R-S6-6, R-O-6 | AB (R-S6-6's reviewer-set read itself is A, against the fixture repo) |
| E2_scratch — scratch repository (outbox test) | External access | R-T-11, R-S6-3 | AB |
| E2_factory — factory repository | External access (secondary: factory tree and change control) | R-F-4, R-F-9 | A (R-F-4 adoption path; R-F-9 branch protection Later; R-F-14's fixture gate is drawn in `L2-factory-as-code.md`, block Fixtures and evals) |
| E3 — Slack | External access | R-H-3 | AB |
| E4 — Hosted model endpoint | Invocation and runtime adapter | R-I-13, R-I-4 | A |
| E5 — Host credential store and scheduler | External access (secondary: Sandbox, R-I-14, via E5_runtime) | R-H-3 | A for the runtime key; AB for the rest |
| E5_runtime — runtime key role | Sandbox | R-I-14 | A (row completes AB; the key itself is in the Sandbox block's A shape) |
| E5_atlassian — Jira/Confluence role | External access | R-S0-1, R-S1-4 | AB |
| E5_github — GitHub role | External access | R-S6-3 | AB |
| E5_slack — Slack role | External access | R-H-3 | AB |
| E5_sched — scheduler entry (launchd/cron) | External access | R-H-3 | AB |
| E6 — Registries and vulnerability feed | Check (secondary: Sandbox) | R-S5-1, R-S5-2 (Check rows, secondary sandbox, that need the registry and vulnerability-feed routes) | AB (fixture project vendors dependencies at A, no registry route) |
| E6_reg — recipe-declared registries | Recipe (secondary: Check, R-S5-2) | R-I-16 (Recipe row for the declared allowlist); R-S5-2 (Check row, secondary sandbox, that needs this route) | AB |
| E6_vuln — vulnerability-database feed | Recipe (secondary: Check, R-S5-1) | R-S5-1 (Check row, secondary sandbox, that needs this route) | AB |

Note on R-I-14: it is the requirement row that fixes the runtime key's route end to end — fetched from the host credential store (E5) over outside access (X5), dispatched over dispatch (X3), supplied to the sandbox over the sandbox wall (X11), used on model reach (X6) — so it recurs against the runtime key role, the sandbox interior (G3) and the loopback proxy (G2) rather than sitting once.

## Not drawn

- **Grafana, OpenSearch, AWS, LaunchDarkly** — named in the charter's own section 7 environment table (charter.md:177–181) but excluded from the brief's component register entirely. The charter marks Grafana "not an agent tool," OpenSearch and LaunchDarkly "out of scope," and AWS "None for pilot" (D9, D25); the crossings table's unlabelled row states directly: "Rollout/flag-ramp/production-verification: nothing crosses into the factory... out of scope (not Later)." None of the six external systems' Initial rows need them, so nothing is missing by their absence.
- **Confluence sync, GitHub's PR checks and merge (S7) reads** (`R-H-10`, `R-S7-1`, `R-S7-2`, `R-S7-6`, all Later) — their block, External access, is homed at external access (C7), domain 2; owned by `L2-control-plane.md`, not restated here.
- **The maintenance scan's own external read** (`R-S0-9`, Later) — its block, Skill, is homed at agent definitions and skills (F3), domain 5; owned by `L2-factory-as-code.md`, not restated here.
- **The observer pass's grader-model call** (`R-O-10`, Later) — its block, Fixtures and evals, is homed at fixtures and evals (F8), domain 5; owned by `L2-factory-as-code.md`, not restated here.
- **Codegraph** — third-party software, but it runs inside the sandbox interior (G3) on the local worktree; it is not an external system, so it is correctly absent from this file.
- **A push before quorum, an agent holding a GitHub or Slack credential, the scheduler starting a stage, an approval carried past a change** — charter anti-goals and R-I-11's forbidden-capability set; none of the six charter anti-goal exclusions on autonomous merge or deploy appear on either diagram.
- **The permanent route to the hosted model on model reach (X6) is charter-admitted** since charter v0.14: the charter's OS-isolation constraint (C10) admits, for an agent sandbox only, the approved hosted-inference endpoint reached through the loopback proxy with the scoped, spend-capped runtime key, and a build sandbox holds no key of any kind. Both diagrams draw that route; `findings.md` section 1, item 3 records the amendment.
