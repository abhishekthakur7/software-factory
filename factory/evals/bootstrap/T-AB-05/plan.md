# T-AB-05 plan

| # | Step | Files touched | Proving test |
|---|---|---|---|
| 1 | `archaeology`: candidate loop, `git blame --line-porcelain`, issue-key regex, the proxy route call, the field-based classification rule, one JSON line on stdout. | `factory/scripts/tools/archaeology` | `runner/tests/test_s1_archaeology.py` |
| 2 | `endpoints.atlassian_read` (host/port), `atlassian_read` added to `proxy_allowlist.S1` only. | `factory/config/sandbox.yaml` | `runner/tests/test_s1_archaeology.py`; `runner/tests/test_sandbox.py`'s pre-existing `proxy_allowlist["S1"]` assertion updated to match |
| 3 | The archaeology wall-clock ceiling, a number, added to config rather than hard-coded. | `factory/config/limits.yaml` | `runner/tests/test_s1_archaeology.py` |
| 4 | `_archaeology_candidates`, `_history_row`, `_run_archaeology`, the `History` runner-section, the `archaeology` check_result, `archaeology_proxy_url`/`archaeology_sandbox_path` test-only overrides on `S1.run`. | `runner/stages/S1.py` | `runner/tests/test_s1_archaeology.py`; `runner/tests/test_s1.py` (unaffected: still green with the new step running under the fixture sandbox and no issue-naming commit in its own fixture repo) |
| 5 | R-S1-4's grader-only line, hand-written. | `factory/rubrics/S1.md` | `runner/tests/test_s1_archaeology.py` |
| 6 | The R-S1-4 human-verdict scenario fixture, following R-S1-2/3/6/11's existing shape. | `factory/evals/rubrics/S1/fixtures/human_verdict/R-S1-4.yaml` | `runner/tests/test_s1_archaeology.py` |
| 7 | The archaeology eval directory: `eval.yaml` plus fixtures for a resolved-issue case and an unlisted-route case. | `factory/evals/scripts/tools/archaeology/` | `runner/tests/test_manifest_eval_walk.py` ("the real tree passes"), exercised directly in `runner/tests/test_s1_archaeology.py` |
| 8 | The new R-S1-4:grader/brief instance every ticket using the real S1 rubric now carries, added with a `pass` verdict alongside the existing four S1 lines. | `factory/evals/rubrics/S3/fixtures/checklist/expected.json`, `verdicts.yaml` | `runner/tests/test_s3_checklist.py` (pre-existing assertions) |
| 9 | The seeded dry-run brief (History already carrying a classification) criterion 11 derives the bootstrap checklist over. | `factory/evals/rubrics/S3/fixtures/dry_run_brief/` | `runner/tests/test_s3_checklist.py` (new test) |
| 10 | Blame/commit-message/classification fixtures the script- and driver-level tests build their own git repository from, plus canned issue payloads. | `runner/tests/fixtures/s1_archaeology/` | `runner/tests/test_s1_archaeology.py` |
| 11 | Criteria 1-10: the script over a real repository and a fake proxy; the sandbox/credential-absence assertions; the three-classification and no-issue fixtures; the dry-run walk to `clarifying` and `factory abandon`; the rubric line. | `runner/tests/test_s1_archaeology.py` | itself |
| 12 | Criterion 11: the checklist instance and its `human_verdict`. | `runner/tests/test_s3_checklist.py` | itself |
| 13 | This ticket's own brief and plan. | `docs/build/T-AB-05/brief.md`, `docs/build/T-AB-05/plan.md` | reviewed by the human, not a test |
| 14 | Manifest hashes recomputed for every new or changed file under `factory/`. | `factory/manifest.yaml` | `runner/tests/test_manifest_hash.py` |

## Test strategy

`test_s1_archaeology.py` splits into a script layer and a driver layer.
The script layer builds a small git repository directly (mirroring
`test_s1.py`'s own `_source_repo` pattern) with commits whose messages
name issue keys, starts a local `http.server` implementing the proxy's
exact route contract from canned issue payloads under
`runner/tests/fixtures/s1_archaeology/issues/`, and runs the script as a
real subprocess: one fixture per classification (`explained`,
`unexplained` with a named-but-unresolved issue, `contradictory`, and
`unexplained` with no issue at all), plus the self-evident-skip case. The
sandbox layer runs the same script through `runner.tests.support.
launch_probe`-style real `launcher.launch` under the committed
`factory/config/sandbox.yaml`'s agent profile, pointing `--proxy` at the
same local fake server (loopback traffic reaches it regardless of the
launcher's own assigned proxy port), and asserts `os_policy_applied` is
true and that the fake credential value the test's own stand-in "proxy"
would have fetched never appears in the sandboxed child's reported
environment, its stdout, or the registered `history` artefact.

The driver layer builds a ticket with `test_s1.py`'s own `_ready_ticket`/
`_run_s1_fixture` helpers (imported, not duplicated) over a worktree
carrying an issue-naming commit, runs `S1.run` directly with
`archaeology_proxy_url` pointed at the test's fake server, and asserts:
the checked brief's `History` table carries the resolved classification
(never the agent's own, by using a fixture brief whose `History` section
the agent left with different content), a `history` artefact is
registered, and -- calling `transitions.apply(conn, ticket_id, "s1_pass")`
itself since `S1.run` is called directly rather than through `run_stage`
so the proxy override can be passed -- the ticket moves `context` to
`clarifying`. A second test then calls `queue.abandon` on that ticket and
asserts the `abandoned` tag, the `not_deployed` `incident_observation`
row, and that no `stage_run` for S2 or later exists, reusing `queue.
abandon` rather than reimplementing its effects. A third test skips
loudly when `credentials.available("atlassian_read")` is false or
`runner.project.pilot()` names the fixture project only -- true on every
host today, so it always skips, the same way `test_s0.py`'s own dry-run
test does.

`test_s3_checklist.py` gains one test: `checklist.expected_instances`
over the seeded `dry_run_brief` fixture (its `History` section already
carrying a classification) includes the `("R-S1-4:grader", "brief")`
instance, and `checklist.record_verdict` binds a `human_verdict` row to
it. The pre-existing tests in that file, which use the real committed
`factory/rubrics/S1.md`, are kept green by adding the same instance (with
a `pass` verdict) to the shared `expected.json`/`verdicts.yaml` fixture
the whole file reads.
