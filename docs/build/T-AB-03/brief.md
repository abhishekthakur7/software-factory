# T-AB-03 brief: tool results through the proxy into the results subpath

## What this delivers

R-I-17 already governs a direct tool call the Cursor SDK adapter records
after an invocation finishes; this ticket extends the same governance to a
call an agent routes live, through the sandbox's loopback proxy, to an
MCP-style endpoint. `runner/sandbox/proxy.py`'s `POST /routes/<route_id>`
handler -- reserved but unimplemented since T-AB-01 -- now looks the route
up in the stage's resolved endpoint allowlist, relays it to the endpoint
through an injectable `relay` callable, shapes the raw result against
`limits.yaml`'s `tool_result_inline` rule, writes the full untruncated
bytes to `<run_dir>/results/tool_results/<seq>.<ext>` as a governed
`tool_result` artefact, and records one `tool_call` row -- all from the
trusted runner's own background thread, since the sandboxed child has no
write access to `results/` at all.

The inline-or-excerpt decision itself moves out of the adapter into
`runner/tool_results.py` (`shape`), so the adapter's direct calls and the
proxy's routed calls share one rule instead of two copies that could
silently drift apart on where "small" ends for the same bytes. The
adapter's own `_record_tool_calls` is refactored to call it; its existing
behaviour and tests are unchanged.

`runner/launcher.py` gets a `routes: RouteService | None = None` keyword
that passes straight through to `proxy.start`, and
`runner/tests/support.py`'s `launch_probe` gets the same keyword, so a
probe under the real, committed Seatbelt profile can dispatch a call
through the proxy and prove the boundary for real rather than through a
fixture sandbox with no `os_profiles`.

Row covered: R-I-17 (the proxy half; the adapter's direct-call half was
already proven at T-A-18 and is not restated here).

## Owner decisions this ticket follows

- **`tool_results.shape` takes raw bytes and a media type, not a parsed
  value.** The four cases the design names -- small inline, large text
  excerpted, one-line oversized with no excerpt, non-text with no excerpt
  -- all fall out of one function: a non-text media type never decodes and
  so is never inline and never excerpted; a text result within the line
  and byte bounds is inline, with the excerpt equal to its own whole text;
  a larger text result excerpts head-and-tail only when it has more than
  one line to split, otherwise it is stored with no excerpt at all.
- **The adapter keeps its own artefact layout.** `_record_tool_calls`
  still writes `results/tool_calls/<seq>.txt` plus a sidecar
  `<seq>.excerpt.txt`, calling `tool_results.shape` with
  `media_type="text/plain"` always -- every value it shapes already
  reached the agent as text (a string or this module's own canonical JSON
  serialization), so the non-text case belongs to the proxy's raw-bytes
  calls alone.
- **The stored artefact's extension is a small fixed table, not
  `mimetypes.guess_extension`.** That stdlib function's answer for a given
  media type depends on the host's registered-type table; a fixed
  `{"text/plain": ".txt", "application/json": ".json"}` (default `.bin`)
  keeps the artefact path deterministic across hosts.
- **A route's credential role is fetched at the moment of the call, from
  an injectable `credential_fetch` on `RouteService`** (defaulting to
  `credentials.fetch`), the same "fetched at the moment of use, handed to
  one call" contract every other credential path in this codebase already
  follows. No test here exercises a route with a non-empty
  `credential_roles`, so no test ever reaches the real Keychain.
- **`self.path` on a `POST` may be an absolute-URI, not only an
  origin-form path.** The sandbox's own `HTTP_PROXY`/`HTTPS_PROXY`
  environment variables point at this same loopback proxy, so a plain
  `urllib.request` call to it from inside the sandbox is itself proxied,
  and a proxied request line is legitimately `POST http://host/routes/x
  HTTP/1.1`. The handler normalizes through `urllib.parse.urlsplit(...).path`
  before matching `/routes/`.
- **A `POST` body is always drained before any early return, refusal
  included.** Responding to a route refusal without first reading the
  client's request body left it sitting unread in the kernel socket
  buffer; on this host, closing the connection with unread bytes still
  pending sent a TCP `RST` instead of a clean close, which surfaced to the
  test client as an intermittent `ConnectionResetError` on exactly the
  403/404 paths. Reading `Content-Length` bytes unconditionally, before
  any response is sent, removed the race outright.
- **`RouteService.stage` is carried but not read by the proxy's own
  dispatch logic.** The stage's endpoint allowlist is already resolved
  once, by `runner.launcher.launch`, into the `allowlist` argument
  `proxy.start` receives; `stage` on `RouteService` is the field the
  design names for whatever builds the service to keep alongside its own
  other state, not a second filter this module re-applies.

## Explicitly out

The OS Seatbelt policy, copy-on-write copies, and the escape suite
(T-AB-01's scope). The manifest and sandbox-capability tests (T-AB-02).
`runner/adapters/cursor_sdk.py` gains no call that builds a `RouteService`
and passes `routes=` into `launcher.launch` -- this ticket's ownership
list restricts that file to moving the shaping helper, and no acceptance
criterion here needs an adapter-driven route call (criterion 1 dispatches
directly through `launch_probe`, bypassing the adapter entirely). Wiring a
real `RouteService` into `cursor_sdk.invoke` is left open for whichever
ticket wires the pilot's live MCP routes end to end. `runner/sandbox/proxy.py`'s
`live_relay` is written to the design's own shape (one `urllib.request`
POST, credential as a bearer token) but exercised by no test in this
suite, since no fixture upstream server exists here; every test injects
its own fake `relay`.
