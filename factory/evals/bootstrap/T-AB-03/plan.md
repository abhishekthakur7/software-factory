# T-AB-03 plan

| # | Step | Files touched | Proving test |
|---|---|---|---|
| 1 | `Shaped`, `is_text`, `shape`: the shared inline/excerpt rule, taking raw bytes and a media type. | `runner/tool_results.py` | `runner/tests/test_proxy_results.py`; exercised indirectly through the adapter's own suite |
| 2 | `_record_tool_calls` calls `tool_results.shape` instead of its own inline copy of `_excerpt`; behaviour and stored artefact layout unchanged. | `runner/adapters/cursor_sdk.py` | `runner/tests/test_adapter.py` (unchanged assertions, still green) |
| 3 | `RouteService`, `live_relay`, `POST /routes/<route_id>` dispatch: route lookup against the stage's resolved allowlist, relay, shape, write the artefact, register it, write the `tool_call` row; `start` takes an optional `routes` argument. | `runner/sandbox/proxy.py` | `runner/tests/test_proxy_results.py` |
| 4 | `launch` gains a `routes: RouteService \| None = None` keyword, passed straight through to `proxy.start`. | `runner/launcher.py` | `runner/tests/test_proxy_results.py` (the two real-sandbox cases) |
| 5 | `launch_probe` gains the same `routes=` keyword, passed straight through to `launcher.launch`. | `runner/tests/support.py` | `runner/tests/test_proxy_results.py`; `runner/tests/test_escape_suite.py` unaffected (keyword defaults to `None`) |
| 6 | Four result-content fixtures: small, large (500 fixed-width lines), one-line oversized, non-text binary. | `runner/tests/fixtures/proxy_results/small.txt`, `large.txt`, `one_line_oversized.txt`, `binary.bin` | `runner/tests/test_proxy_results.py` |
| 7 | Two real-sandbox probes: one POSTs a route call and rereads a further slice of the returned artefact path; one attempts a write into `results/`. | `runner/tests/fixtures/proxy_results/route_call_probe.py`, `write_results_probe.py` | `runner/tests/test_proxy_results.py` |
| 8 | The proving test file itself. | `runner/tests/test_proxy_results.py` | itself |
| 9 | This ticket's own brief and plan. | `docs/build/T-AB-03/brief.md`, `docs/build/T-AB-03/plan.md` | reviewed by the human, not a test |

No file under `factory/` changes, so the manifest is untouched and
`tools/refresh_manifest.py` has nothing to regenerate for this ticket.

## Test strategy

`runner/tests/test_proxy_results.py` splits into two groups.

The first drives `runner.sandbox.proxy` directly: `proxy.start(allowlist,
routes)` with a hand-built `RouteService` whose `relay` is a fixed closure
returning one of the four fixtures' bytes, then a plain `http.client.
HTTPConnection` POST to `/routes/<id>`, asserting on the JSON response,
the artefact file on disk, and the `tool_call` row read back from the same
sqlite file. This covers the size cases (small inline; large text
excerpted head-and-tail with the artefact never truncated; one-line
oversized with no excerpt; non-text with no excerpt, media type and
digest only), the `tool_call` row's `result_bytes`/`inline` fields, an
unlisted route id refusing `403`, a `routes=None` proxy refusing every
`POST` with `404`, and the sequence counter continuing from the run's
existing `MAX(seq)` when a prior direct call already used seq 5. None of
these cases touches the OS sandbox, so they run in a few seconds each.

The second group runs through `runner.tests.support.launch_probe` under
the real, committed `factory/config/sandbox.yaml`, the way
`test_escape_suite.py` does: one probe (`route_call_probe.py`) POSTs a
route call for the real `hosted_model` route id (already on `S1`'s
committed `proxy_allowlist`) from inside the agent Seatbelt profile, then
rereads a byte range of the returned artefact path with an ordinary file
open, asserting the slice lands outside the excerpt's own head/tail bound
(a deterministic offset into the 500-fixed-width-line fixture, chosen so
the read content -- `"line 200"` -- provably was not part of what the
proxy's own excerpt already returned). A second probe
(`write_results_probe.py`) attempts to write into the run's own
`results/` subpath (derived from `FACTORY_RUN_OUT`'s sibling, since no
`results/`-specific environment variable exists) and asserts the write is
refused. Both probes need `RouteService.run_dir` to name exactly the
`tmp_path / "run"` directory `launch_probe` itself launches under --
undocumented anywhere but `launch_probe`'s own source before this ticket,
so its docstring now says so directly.

A flake surfaced during development on the refusal-path tests (`403`/
`404` over `http.client`): responding without first draining the
client's request body raced the connection close against the client's own
read of the response, producing an intermittent `ConnectionResetError` at
the caller roughly one run in three. Reading the full `Content-Length`
body unconditionally before any response -- refusal included -- removed
it; ten consecutive full-file runs afterward all passed.
