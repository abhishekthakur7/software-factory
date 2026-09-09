# T-AB-11 plan

1. Register sandbox copy-disposal and three record-history eval directories
   beside escape; validate every fixture, ownership, redaction and failure-mode id.
2. Seed incident events, control events, and coverage check/tag histories.
   Replay through the real record write path and test persistence, foreign-key
   validation and append-only rejection rather than echoing memberwise values.
3. Run each configured recipe at the current base in separate APFS base/head
   copies through the common sandbox recipe executor. Retain one combined result
   per recipe, dispose both copies on success/failure, and recheck immutable inputs.
4. Make the gate include required mechanical suites even with a custom --tests
   selection. Pass the selected factory root to those suites. Reject covered
   mechanism changes that do not update matching fixtures and failure-mode metadata.
5. Add positive and mandatory negative tests, including a subprocess gate failure
   for each required fixture directory. Refresh the manifest after integration.

Verification: runner/tests/test_gate_ab.py, runner/tests/test_adoption_fixtures.py,
runner/tests/test_escape_suite.py, existing gate and eval completeness tests,
then the full adoption gate. Live pilot execution is pending configuration.

The closing command is `python3 -m runner.gate --close`. It writes a local
adoption receipt only after the test suite and every required mechanical fixture
pass. The receipt records mechanics, not a live pilot launch or completed live
connection checks. The history check examines each commit since the required
fixtures were introduced, so an unrelated follow-up commit cannot hide a missing
regression fixture. The sandbox dry run records expected unavailable security
feeds as `blind_spot`; successful replay does not convert that result to `pass`.
