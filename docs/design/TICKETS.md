# Soft-factory build tickets

| | |
|---|---|
| Status | Draft v0.1 |
| Date | 2026-09-08 |
| Owner | Abhishek Thakur |
| Cites | `docs/design/milestones.md` v0.7; `docs/prd/prd.md` v0.18; `docs/charter.md` v0.14; `docs/design/hld/README.md` v0.3 |

The build order inside each milestone of `docs/design/milestones.md` section 3, as tickets. One file per milestone, tickets in build order; a ticket depends only on tickets above it in its file or in an earlier milestone's file. Every Initial requirement row of the PRD sits in exactly one ticket of the milestone Appendix A gives it; Later rows have no ticket. B's two closing tickets cover no row of their own: their `Rows exercised` cell names the rows of earlier tickets whose live, pilot-host clauses they run. `python3 tools/tickets_check.py` checks the files against the PRD and Appendix A and prints the ticket list with `--list`.

| Milestone | File | Tickets | Rows | Status |
|---|---|---|---|---|
| A, walking skeleton | [tickets/A.md](tickets/A.md) | 35 | 89 | Draft v0.1 |
| AB, boundary and connection | [tickets/AB.md](tickets/AB.md) | 11 | 13 | Draft v0.1 |
| B, pilot | [tickets/B.md](tickets/B.md) | 7 | 5 | Draft v0.2 |

## Ticket format

Each ticket has: id (`T-<milestone>-NN`, numbered in file order), title, milestone, blocks by number and name from `milestones.md` section 1, HLD component ids from `docs/design/hld/README.md` section 4, depends on, rows covered, description, scope in and out, optionally rows exercised, numbered acceptance criteria each ending with the row id it satisfies, and verification (the test files and fixtures the ticket adds under `runner/tests/` or `factory/evals/`).
