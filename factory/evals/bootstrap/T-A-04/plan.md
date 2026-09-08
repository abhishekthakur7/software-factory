# T-A-04 plan

## Steps

| # | Step | Files touched | Proves |
|---|---|---|---|
| 1 | Encode the event table: `STATES` (unchanged), `STAGE_STATE`, `TERMINAL_STATES`, `TABLE` (`(from_state, event) -> to_state`), `CLOSE_REASON`. The earlier entered-from sets are removed. | `runner/state_table.py` | `test_fence.py`, now checking every row's endpoints are real states |
| 2 | `apply(conn, ticket_id, event)`: table lookup, `TransitionRefused` on no row, `ticket.state` update, `closed_at`/`close_reason` stamped on entry to a terminal state. | `runner/transitions.py` | `test_state_table.py` (all 37 transition criteria) |
| 3 | The four gate functions (`intake_gate`, `plan_review_gate`, `checks_gate`, `review_gate`), each reading already-recorded rows and returning an event or `None`. | `runner/gates.py` | `test_state_table.py`'s gate-fixture tests (criteria 11, 12, 15, 19, 20, 24, 25, 26, 27) |
| 4 | `open_ticket`: the one function that inserts a ticket row in `intake`. | `runner/tickets.py` | `test_state_table.py` criterion 1 |
| 5 | `run_stage`: refusal before any stage_run exists (missing ticket, unknown stage), refusal recorded as that ticket's own stage_run (wrong state), otherwise insert/run/record, then apply the driver's `PASS_EVENT` unless `validation_only`. | `runner/stages/__init__.py` | `test_cli_skeleton.py` (criteria 39, 40, 41); `test_state_table.py` criterion 38 |
| 6 | Seven stub drivers sharing one write/register helper; `PASS_EVENT` set for S1-S4, `None` for S0/S5/S6 (their exits are gates). | `runner/stages/_common.py`, `runner/stages/S0.py`..`S6.py` | `test_stub_stages.py` (criteria 2, 5, 8, 9, 14, 24) |
| 7 | `factory advance\|run\|show`, each a thin wrapper; `advance` runs the stage due in the ticket's state, else evaluates its gate, else reports the wait; the run tree is the database's directory. | `runner/cli.py`, `pyproject.toml` (`[project.scripts]`) | `test_cli_skeleton.py`, including the intake-to-clarifying walk through `advance` |
| 8 | The front-matter loader for stub agent/skill/rubric files. | `runner/definitions.py` | `test_stub_stages.py`'s eval-directory walk |
| 9 | Stub files: `factory/agents/S1-S4.md`, `factory/skills/S1-S4.md`, `factory/rubrics/S0-S6.md`, 15 eval directories (one `ok` fixture copying the stub, one `missing_front_matter` reject fixture), and the manifest's `stages:` map plus every new file's path/hash. | `factory/agents/**`, `factory/skills/**`, `factory/rubrics/**`, `factory/evals/{agents,skills,rubrics}/**`, `factory/manifest.yaml` | `test_stub_stages.py`'s eval-directory walk; `factory/scripts/tools/manifest_hash` run by hand against a throwaway git commit (see Verification below) |
| 10 | Five fixture families under `runner/tests/fixtures/state_table/`, one per family named in the ticket, each holding one or more named scenarios a small loader (`load_scenario` in `test_state_table.py`) inserts through `record.insert`. | `runner/tests/fixtures/state_table/*.yaml` | `test_state_table.py`'s gate-fixture tests |
| 11 | This ticket's own brief and plan. | `docs/build/T-A-04/brief.md`, `docs/build/T-A-04/plan.md` | reviewed by the human, not a test |

## The entered-from comparison the design asked for

Before writing `TABLE`, the brief asked to compare, for every `to_state`,
its from-state set against the old hand-written entered-from sets, and to
cite the PRD sentence deciding each difference.

| to_state | old entered-from | new entered-from | difference | PRD sentence |
|---|---|---|---|---|
| `context` | (10 states, no self) | + `context` | `migrate_manifest` can fire while already in `context` | R-I-4: "a human-approved manifest migration ... returns to `context`" from any non-terminal state, `context` included |
| `context`, `implementing`, `merged`, `abandoned` | included `pr_checks` | `pr_checks` removed | `pr_checks` is the Later S7-polling state; nothing in this Initial version reaches or leaves it | 2.3's own row: `pr_checks` is "Entered from `pr_opened` (Later)"; this ticket builds only the Initial paths |
| `clarifying` | included `planning` | `planning` removed | no PRD sentence routes `planning` itself to `clarifying`; the old set conflated "any later state" with every state, but `planning` exposes no queue item a send-back could fire from | 2.3 send-back paragraph: the human acts "from any open queue item (plan approval, red check, packet approval, escalation, or manual pause)" -- `planning` (S3 running) is none of these |
| `planning` | -- | + `implementing`, `pr_opened` | a send-back from `implementing` and a `pr_opened` revision can both target `planning` | criterion 16 ("For each of `planning` and `clarifying` ... `implementing` ... moves to that state"); criterion 32 (`pr_opened` revision "through the selected earlier stage") |
| `implementing` | -- | + `pr_opened` | a `pr_opened` revision can target `implementing` | criterion 32 |
| `checks` | -- | + `escalated` | criterion 35's infrastructure/stop resume can return to `checks` | criterion 35 |
| `review` | -- | + `escalated` | criterion 35's infrastructure/stop resume can return to `review` | criterion 35 |

Every other `to_state` (`rejected`, `plan_review`, `pr_opened`, `escalated`,
`abandoned` apart from the `pr_checks` removal above) is unchanged between
the old and new tables.

## Test strategy

`test_state_table.py` seeds a ticket directly in the state under test
(`_ticket_in`, bypassing `tickets.open_ticket`'s fixed `intake` entry) and
asserts on the resulting state or the raised exception, never on `TABLE`'s
own content, so a wrong row in the table fails its test rather than
passing by construction. The five gate-fixture families seed the rows a
real quorum/freshness/reviewer-set/outbox computation would leave behind
and assert what the *gate* returns before applying it, so a gate that
returns the wrong event (or fires when it should withhold) is caught
independently of the table. `test_cli_skeleton.py` drives refusals through
`runner.cli.main` in-process. `test_stub_stages.py` runs the real stub
drivers end to end for the criteria the ticket assigns to it, and
separately walks every stub's eval directory, loading its `ok` and
`missing_front_matter` fixtures through `runner.definitions.load_definition`
so a stub with no usable front matter, or a reject fixture that
`load_definition` does not actually reject, fails the walk. Every test
opens its own `tmp_path` database; the stage tests additionally
monkeypatch `artefact_registry.REPO_ROOT` to `tmp_path` (via pytest's
`monkeypatch`, which reverts automatically) so a stub's registered
artefact path resolves under `tmp_path` instead of the real repository,
matching `artefact_registry.register`'s assumption that a registered
file lives under `REPO_ROOT` without needing to touch that module.
