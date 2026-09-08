This fixture has no `seed.yaml`: the reject case is a database file that
exists but was never given the schema, so none of the required views are
present. `runner/tests/test_report.py` builds it as a bare SQLite file with
no `CREATE VIEW` statements run against it at all.
