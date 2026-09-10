# Study brief: what soft-factory can port from Mastra

## The two repositories

- **Ours**: `/Users/abhishekthakur/Developer/soft-factory`. A Python software factory that takes a Jira ticket through stages
  intake -> context gathering -> requirements clarification -> spec and plan -> implementation -> cleanup/checks -> human review -> PR checks and merge,
  inside a closed loop (the factory records everything, measures itself, and improves its own factory-as-code tree).
  Key reading, in this order:
  1. `docs/prd/prd.md` (how to read, the initial-version page, the part map) — read fully.
  2. `docs/charter.md` — skim sections on principles (P-n), failure modes (FM-n), constraints (C-n), decisions (D-n); grep for what you need.
  3. The PRD part files under `docs/prd/` that your packet touches (listed in your packet). `docs/prd/02-2-entities.md` is the record's data model; `docs/prd/08-configuration.md` holds the tooling selections and day-one decisions.
  4. `docs/design/milestones.md` — milestones A, AB, B, Later; rows say what is built and what waits. Grep by topic rather than reading all 500 lines.
  5. `docs/design/hld/README.md` and `docs/design/hld/L1-bird-view.md` — the component inventory (34 components, six domains, seams X1..X11). Then the L2 file for your domain.
  6. `runner/` — the Python implementation. `runner/schema.py` is the SQLite record; `runner/queue.py` the human queue; `runner/stages/` the stages; `runner/adapters/` the agent runtimes; `runner/checks/`, `runner/evals.py`, `runner/graduation.py`, `runner/outbox.py`, `runner/digest.py`, `runner/waivers.py`, `runner/trust_profile.py`, `runner/reviewer_sets.py`. `factory/` is the factory-as-code tree (agents, rubrics, recipes, config, evals, skills). `docs/build/findings.md` is the latest review of what is built.
- **Theirs**: `/Users/abhishekthakur/Developer/mastra`. The Mastra TypeScript monorepo (last commit 2026-09-10). It contains a general agent/workflow framework in `packages/core/src` and, importantly, a "Mastra Software Factory" product under `mastracode/` (`factory` backend with boards, phases, transition policies, rules, integrations, sandboxes, agent-controller; `factory-ui`; `web` host; `sdk` coding-agent runtime; `tui`). `explorations/` holds design notes (durable agents, ralph-wiggum loop, agent network, orchestrator report). Docs are under `docs/src/content/en/docs/`.

## Owner's constraints you must respect when rating ideas

- Prototype first. The initial version is being made ready for a dry run against one real pilot ticket. Nothing that only matters at scale, for security hardening, or for many-tenant hosting is a must-have now.
- Enterprise rules: no niche third-party tools, no third-party MCP servers. Chosen runtimes: Cursor SDK primary, Claude Code secondary. codegraph, Inspect, official Slack and Atlassian MCP are the allowed external pieces. The runner is Python on macOS with SQLite; the factory tree is YAML/Markdown under `factory/`.
- Prefer rules to hard-coded numbers; numbers live in config; flag over refuse where the record can carry the flag.
- The factory is a collaborator, not a black box: every automation adds a human-readable artefact and a record of the reasoning.
- We are NOT adopting Mastra as a dependency. We port ideas, data shapes, contracts, mechanisms and, where it is small and clean, logic translated to Python.

## Naming rule for your report

Your report is a document, so it MAY cite our ids (R-x-n, S0..S7, D-n, FM-n, P-n, X-n, T-x-n, G-n). Be precise: cite the row or component you mean.

## Do NOT

- Do not modify any file in either repository. Do not run git commands that change state (no stash, reset, checkout, restore, clean, commit, add). `git log` / `git show` / `git grep` are fine.
- Do not read `examples/` in Mastra beyond a glance; source and docs are the truth.
- Do not build or install anything.

## Report format (write it to the path given in your packet; Markdown; aim for 250-450 lines; concrete file paths on the Mastra side for every mechanism)

1. **What Mastra does here** — the mechanisms, data model, contracts and lifecycle in this packet, each with its defining files. Say what problem each mechanism solves. Include the shapes (types, table columns, state enums, config keys) that a port would copy.
2. **What we already have** — the PRD rows, HLD components and runner modules that cover the same ground, and how our version differs (simpler, stricter, missing, different split).
3. **Portable ideas** — a numbered list. For each:
   - Name and one-line what it is.
   - Why it matters for a closed-loop software factory (cite the failure mode or principle it serves, or say "new" if none fits).
   - Rating: `must-have for dry run` / `next milestone` / `later` / `do not port` (with reason, e.g. hosting-only, duplicates ours, violates constraint).
   - Where it lands: PRD section and part file; the existing row it extends or "new row"; the HLD component it extends or "new component" with its domain and the seam it crosses.
   - Draft acceptance criteria: 2-5 clauses in the PRD's style, including at least one `must-reject:` clause, and the verification (script test / manifest test / grader / inspection).
   - Size: S (< 1 day), M (1-3 days), L (> 3 days).
   - What to copy literally (a shape, an enum, a state machine, a prompt) vs what to re-derive.
4. **Questions for the owner** — only questions whose answer changes what gets written into the PRD. Plain words, no ids in the question text, state a default for each.
5. **Do-not-port list** — things in the packet that look attractive but should not come over, with the reason.
