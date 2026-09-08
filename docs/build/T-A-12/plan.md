# T-A-12 plan

## Steps

| # | Step | Files touched | Proves |
|---|---|---|---|
| 1 | `ACTIONS` mapping, `open_item`, `latency_seconds`, `ActionRefused`. | `runner/queue.py` | `test_queue.py`'s kind/display and `open_item` tests (criteria 1, 2); `test_act.py`'s latency tests (criterion 10) |
| 2 | `runner/tags.py`'s `tag`, validating target shape and required fields before insert. | `runner/tags.py` | `test_act.py`'s tag tests (criteria 12, 15) |
| 3 | `act`'s dispatch: actor/kind-action validation, the per-action helpers (`_answer`, `_override`, `_approve`, `_redirect`, `_request_changes`, `_send_back`, `_resume`, `_record_control_event`), and the shared once-group `_resolve`. | `runner/queue.py` | `test_act.py`'s mapping matrix and per-action tests (criteria 7, 8, 9, 12, 13) |
| 4 | `abandon`, shared by `act`'s own `abandon` action and `factory abandon`. | `runner/queue.py` | `test_act.py`'s abandon tests (criteria 12, 14) |
| 5 | `list_queue` and its eligibility/approval-context helpers. | `runner/queue.py` | `test_queue.py`'s display tests (criterion 3); `test_attention_bucket.py`'s multi-reviewer test (criterion 4) |
| 6 | Four CLI subparsers (`queue`, `act`, `abandon`, `tag`) and their dispatch branches; every other line of `cli.py` unchanged. | `runner/cli.py` | `test_act.py`'s CLI thin-wrapper tests (criteria 7, 14, 15) |
| 7 | Seeded queue-item fixtures across every Initial kind. | `runner/tests/fixtures/queue/items.yaml` | `test_queue.py` (criteria 1, 3) |
| 8 | Forbidden-telemetry token scan and the AST derivation check. | `runner/tests/test_attention_bucket.py` | criteria 5, 6 |
| 9 | This ticket's own brief and plan. | `docs/build/T-A-12/brief.md`, `docs/build/T-A-12/plan.md` | reviewed by the human, not a test |

## Test strategy

`test_queue.py` loads its fixture family once per test through a small
loader (`load_scenario`, matching `test_state_table.py`'s convention but
also substituting a `$name` reference embedded inside a larger string, for
the escalation item's polymorphic `stage_run:<id>` ref) and asserts against
`list_queue`'s text output: every kind's block appears (criterion 1), the
common fields appear on a plain item (criterion 3), the eligibility item's
extra context appears in full (criterion 3), and a resolved `pr_outcome`
item's latency line reads "queue latency" with the word "attention" nowhere
in its own block (criterion 2), plus a direct check that `open_item` never
sets `blocked_on` for that kind.

`test_act.py` seeds each ticket directly in the state its item's action
needs (`record.insert(..., state=...)`, not `tickets.open_ticket`, which
always opens in `intake`) and drives `queue.act` and the CLI verbs
in-process. A parametrized test walks every `(kind, action)` pair the
mapping lists and asserts acceptance (criterion 8's positive half); a
second parametrized test walks pairs outside the mapping, `pr_outcome`
included, and asserts `ActionRefused` (criterion 8's negative half). Separate
tests pin the once-only resolution and its refusal on a second call
(criterion 9), latency's exact subtraction (criterion 10), that
`send_back`/`abandon`/`override` each write exactly one tag naming the
transition (criterion 12), that `control_event` records an
`incident_observation` row and its tag while leaving the item open
(criterion 13), and the CLI's four thin wrappers end to end (criteria 7, 14,
15), including that `granted` alone does not move the ticket while
`send_back` does.

`test_attention_bucket.py` covers the four criteria the ticket assigns it
directly: a multi-reviewer plan decision showing two actors' own buckets,
`unknown` among them, each on its own line, separate from the queue-latency
and outcome lines (criterion 4); a token scan over `factory/manifest.yaml`,
every file under `factory/config/`, and every non-test `.py` under
`runner/` for the eight forbidden tokens (criterion 5); an `ast`-based check
that every `active_attention_bucket` assignment or keyword argument in
`runner/` is a plain name or the literal `"unknown"` (criterion 6); and that
`approve` without `--bucket` is refused while a non-approval action accepts
one optionally, with or without a value (criterion 11).

## Verification

`uv run pytest -q` -- 507 tests pass (456 before this ticket, plus 5 in
`test_queue.py`, 41 in `test_act.py`, and 5 in `test_attention_bucket.py`).

## Note on the forbidden-telemetry scan and this ticket's own prose

The first run of the token scan failed against `runner/queue.py`'s own
module docstring, which used the word "keystroke" to explain what the
column is *not* derived from. The criterion scans literal file content, not
production code paths, so the docstring was reworded to describe the same
invariant without naming any of the eight tokens -- the rule the scan
enforces is stricter than "no code reads a keyboard," it is "no governed
file or runner module names one of these sources at all," prose included.
