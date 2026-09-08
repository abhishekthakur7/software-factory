# Forced categories

Run this checklist against the criteria as a whole, not against any one
criterion in isolation. Resolve every category below; a category is left
silent only if it is missing from the table entirely, which is itself a
defect. A category an intake-stage exclusion record already closed
arrives pre-filled -- leave it as written, it is not yours to evaluate.

For each category, write exactly one of:

- `covered by criterion AC-n` -- an existing criterion already requires
  the behaviour this category asks about; name the criterion.
- `not applicable because <reason>` -- state why this ticket has nothing
  for this category to apply to; a reason that only restates the category
  name ("not applicable because there is no concurrency") is not enough --
  say what about this specific change makes it so.
- `open` -- the category applies but no criterion covers it yet; this
  becomes a question for a human to resolve before the plan is written.

## The eight categories

1. **error paths** -- what happens when the operation cannot complete:
   invalid input, a dependency failure, a timeout.
2. **concurrency** -- what happens when two callers act on the same data
   at the same time; is there a race, and does it matter.
3. **migration** -- whether existing data or a running system needs to
   move from an old shape to a new one, and how.
4. **backward compatibility** -- whether an existing caller, format, or
   integration keeps working unchanged.
5. **permissions** -- who is allowed to trigger this behaviour, and what
   happens when someone who is not allowed to tries.
6. **observability** -- what a person watching the system afterward can
   see: a log line, a metric, a trace that shows this happened.
7. **rollback** -- what it takes to undo this change if it turns out to
   be wrong, and whether that undo is itself safe.
8. **data retention** -- how long any new or changed data is kept, and
   what removes it.
