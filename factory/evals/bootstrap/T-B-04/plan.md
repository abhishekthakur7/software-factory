# T-B-04 plan

| # | Step | Files touched | Proving test |
|---|---|---|---|
| 1 | Write the capacity module: the configured limit, the counted states, the graduation-approval lookup that can raise it, and the wait line derived from state and the limit | `runner/capacity.py` | `runner/tests/test_capacity.py` |
| 2 | Check the limit at both `intake` boundaries -- before a ticket's first stage starts and before the intake gate's admitting event is applied -- so a ticket at capacity starts no run, opens no queue item, and stays in `intake` | `runner/operations.py` | `runner/tests/test_capacity.py` |
| 3 | Show the same wait line from the ticket-status view | `runner/operations.py` | `runner/tests/test_capacity.py` |
| 4 | Show one wait line per ticket held at `intake` from the open-work listing, since a held ticket carries no queue item of its own | `runner/queue.py` | `runner/tests/test_capacity.py` |
| 5 | Seed fixtures for the configured read, the missing-approval case, the exact counted-state set, the unsigned edit, the approved raise, the stale configuration hash, the stale manifest hash, and the expired record | `runner/tests/fixtures/capacity/` | `runner/tests/test_capacity.py` |
| 6 | Refresh the manifest and write this ticket's own brief and plan | `factory/manifest.yaml`, `docs/build/T-B-04/brief.md`, `docs/build/T-B-04/plan.md` | reviewed by the human, not a test |

## Test strategy

Every case seeds real rows through the record's own write paths --
`record.insert` for tickets in a given state, `artefact_registry.register`
for a report file actually written to disk, `approvals.record_approval`
for the binding approval -- and asserts on `effective_parallel_limit`'s
returned limit and reason, on `factory advance`'s refusal to start a run
or write a queue item at capacity, and on the wait line's text from both
`factory queue` and `factory show`, rather than re-reading back a value a
test just wrote. The unsigned-edit, stale-hash, stale-manifest and
expired-record cases each change exactly one bound value away from a
seeded passing case, so each proves that one check and not another.
