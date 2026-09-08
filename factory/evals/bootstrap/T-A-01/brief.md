# T-A-01 brief: factory tree, manifest, hash script, fence, write barrier

## What this delivers

The foundation the rest of Milestone A builds files into: the `factory/`
directory tree fixed by PRD section 7, its `manifest.yaml`, the
`scripts/tools/manifest_hash` script that recomputes the manifest hash from
the committed tree, and the two runner-code modules -- `state_table.py` and
`anti_goals.py` -- that stay outside `factory/` so no proposal path can ever
reach them (R-F-11). It also fixes, for every later ticket, the code
locations named in the ticket file: `runner/` as the trusted control plane,
`runner/tests/` as the pytest suite, `factory/evals/<kind>/<name>/` as the
eval-directory shape, and `python3 -m runner.gate` as the adoption-gate
entry point.

Rows covered: R-F-1 (the layout and the manifest hash), R-F-5 (nothing at
runtime writes to `factory/`), R-F-11 (the fence).

## Owner decisions this ticket follows

- The write barrier is a funnel plus a static scan: `runner/fs.py` is the
  only module allowed to open a path under `factory/` for writing, and
  `test_write_barrier.py` proves every other `runner/` module contains no
  raw write primitive (`open` with a write mode, `.write_text`/`.write_bytes`,
  or a copy/move/rename call).
- The four synthetic write-attempt fixtures (`tag`, `stale_index_entry`,
  `grader_failure`, `engineer_reading`) are data, not enforcement: each is a
  tiny module that performs one raw write, run through the same scanner.
- The gate is a pytest wrapper: `runner/gate.py` runs the suite under
  `runner/tests/` and returns its exit code. Nothing more.
- `manifest_hash` does not walk and verify every referenced file's content
  hash -- that belongs to T-A-35's completeness walk (R-F-2). This ticket's
  manifest still carries correct hashes (computed with `shasum -a 256`)
  because T-A-35 will check them.

## Explicitly out

- The manifest's completeness walk over every referenced file (R-F-2,
  T-A-35).
- The reviewed-change adoption path, review records, and the smoke gate
  (R-F-4, T-A-35).
- The manifest's full field set, model and budget resolution (R-I-4,
  T-A-19).
- Transition enforcement and stub stage drivers reading `state_table.py`
  (R-T-5, T-A-04) -- this ticket only adds the data.
