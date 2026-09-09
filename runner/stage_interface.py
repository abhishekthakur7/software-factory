"""The one operation surface: every Initial-catalogue operation, bound to the function its own module already defines.

`runner/cli.py`, and any later client, reach the record and every stage
driver only through this module -- never `runner.record` directly, never
a `runner.stages.S<n>` module directly, never `runner.graduation`'s own
write path outside `graduate_approve`. `__all__` is the export list and
the one place it is written; a test reads it back rather than a second
hand-maintained catalogue drifting from it. The record-writing outcome
actions (`revision`, `outcome`, `exposure`, `coverage`, `incident_event`,
`control_event`, `disposition`) name no export of their own here: each
reaches this surface only as an `action` argument to `act`, exactly like
every other queued human decision.

`run_stage` binds to `operations.run`, not the raw `runner.stages.run_stage`
driver dispatcher: `operations.run` is the thin wrapper that already
refuses a ticket with a live run and reconciles its pending external
writes before ever reaching the driver, exactly what the command line ran
before this module existed, so binding the export straight to the
undecorated dispatcher would drop that refusal silently.

Two attributes below serve `runner/cli.py`'s own composition and are
never part of `__all__`: `connect`, so the command line opens the database
through this module instead of importing `runner.db`, and `target_branch`,
the freshness read `refresh_base`'s own required argument depends on and
`cli.py` otherwise has no route to.
"""
from runner import export as _export
from runner import graduation as _graduation
from runner import manifest as _manifest
from runner import operations as _operations
from runner import queue as _queue
from runner import refresh_base as _refresh_base
from runner import tags as _tags
from runner.db import connect
from runner.freshness import target_branch

__all__ = [
    "advance",
    "run_stage",
    "pause",
    "resume",
    "stop",
    "show",
    "queue",
    "act",
    "migrate_manifest",
    "refresh_base",
    "tag",
    "abandon",
    "report",
    "export",
    "import_record",
    "purge",
    "digest",
    "graduate_evaluate",
    "graduate_approve",
]

advance = _operations.advance
run_stage = _operations.run
pause = _operations.pause
resume = _operations.resume
stop = _operations.stop
show = _operations.show
queue = _queue.list_queue
act = _queue.act
migrate_manifest = _manifest.migrate
refresh_base = _refresh_base.refresh_base
tag = _tags.tag
abandon = _queue.abandon
report = _operations.report
export = _export.export_ticket
import_record = _export.import_export
purge = _export.purge_export
digest = _operations.digest_open_items
graduate_evaluate = _graduation.evaluate
graduate_approve = _graduation.approve
