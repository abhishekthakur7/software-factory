This fixture has no `seed.yaml`: an export needs an active trust profile
(a satisfied governance quorum over `governed_export_display`) and a
ticket with rows across the exported tables, neither of which a flat list
of table rows can express on its own. `runner/tests/test_export_import.py`
builds it directly the same way `test_outbox.py` and `test_guard.py`
activate a trust profile before exercising the guard, then seeds a ticket
with a permitted `data_class` and rows across every exported table before
calling `runner.export.export_ticket`.
