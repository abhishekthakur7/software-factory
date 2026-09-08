This fixture has no `seed.yaml`: the report's exit-test walk needs a real
state-machine transition through the stub stages, which a flat list of
table rows cannot express. `runner/tests/test_report.py` builds it directly
with `runner.stages.run_stage` and `runner.transitions.apply`, the same way
`runner/tests/test_stub_stages.py` walks a ticket, then layers on the
supplementary rows (tags, a question and its answer, a generated test,
stale index use, a tool call, an incident) that populate every measure.
