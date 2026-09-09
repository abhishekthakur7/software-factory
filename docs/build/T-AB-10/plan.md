# T-AB-10 plan

| # | Change | Files | Proof |
| --- | --- | --- | --- |
| 1 | Add a governed selection artefact record and frozen cohort write checks. | `runner/schema.py`, `runner/record.py` | `test_baseline_import.py` frozen-write cases |
| 2 | Extend Atlassian reading for baseline ticket and Confluence history, with route/role validation; add the GitHub read client with the equivalent boundary. | `runner/readers/atlassian.py`, `runner/readers/github.py` | reader and importer transport assertions |
| 3 | Implement normalized selection, measurement, supplemental eligibility, artefact registration, and freeze in one import module exposed by the command script. | `runner/baseline.py`, `factory/scripts/tools/baseline_import` | `test_baseline_import.py` |
| 4 | Seed retrospective, supplemental, unavailable, prohibited-field, and frozen-cohort fixtures and register the eval subject. | `runner/tests/fixtures/baseline_import/`, `factory/evals/scripts/tools/baseline_import/` | importer tests and eval walk |
| 5 | Add the build brief and plan and their byte-identical bootstrap copies. | `docs/build/T-AB-10/`, `factory/evals/bootstrap/T-AB-10/`, `factory/evals/bootstrap/eval.yaml` | `test_bootstrap_fixtures.py` |

## Test strategy

The importer creates one cohort. An incomplete cohort is supplemented through
the guarded `add_ticket` and `add_measure` APIs; it is not replayed from source
history.

Tests execute the importer over fake Atlassian and GitHub transports, rather
than a test-only alternate implementation. They prove selection order and
exclusions, route denial before a call, allowed-field projection, baseline row
shape, observed/approximate/unavailable measure outcomes, separate supplemental
cutoff and shared definitions, baseline-view visibility, freeze persistence,
and refusal after freezing. A closing-run test is loud when the committed
project remains fixture-only or the required Keychain roles are unavailable.
