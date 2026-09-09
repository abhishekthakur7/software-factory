# T-B-05 brief

The runner exposes one API and every client uses it. `runner/stage_interface.py`
re-exports each Initial operation by name, thinly bound to the function its
own module already defines, so `runner/cli.py` -- and any later client --
reaches the record and every stage driver only through this one surface,
never `runner.record` directly, never a stage driver module directly,
never the graduation gate's write path outside its one approving verb.
The record-writing outcome actions (revision, outcome, exposure, coverage,
incident/control event, disposition) name no export of their own: each
reaches the surface only as an `action` argument to the queue's own `act`.

Three import-graph boundaries are checked by AST scan rather than by
convention alone: the command line imports nothing from the runner
package but the stage interface and the paths module; a stage driver
package is reached only through its registry, never a client naming an
individual stage module by hand except the one already-existing site a
real circular-import constraint forces; and a script the factory runs
outside the runner's own process reaches the record only through the
runner functions built for that purpose, never a raw SQL write of its
own.

A governed ticket export becomes the first redacted real fixture through
a standalone script that copies the export directory and writes a
redaction review naming who looked at it, when, what was redacted, and
the export's own content hash -- the same four-field shape now required,
in the same completeness walk, of every real-ticket-export case anywhere
in the eval tree.

The closing run drives the pilot ticket through this one surface from its
Jira key to a draft pull request, records its outcome by hand, evaluates
the real graduation gate as not yet passed with the failing clauses
named, and turns its own governed export into that first redacted
fixture -- the milestone's own definition of done, restated as a run
over the actual record rather than as prose.

Requirements: R-I-1.
