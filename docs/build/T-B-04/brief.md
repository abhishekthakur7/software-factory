# T-B-04 brief

The runner enforces a parallel-ticket limit: how many tickets may sit past
`intake` at once. The initial version's limit is one. A ticket that would
push the count above the limit stays in `intake` rather than starting
work, and the wait is visible from the same state and configuration every
other read derives from, not from a separate tracked flag.

The limit can only rise above one through a recorded graduation decision:
a `factory_owner` approval that binds the exact bytes of the configuration
file carrying the number and a graduation report that passed under the
manifest currently in force. Editing the number in the file by hand, with
no such approval on record, changes nothing observable -- the effective
limit stays one, with a reason attached so the difference between "never
asked" and "asked, but the binding has gone stale" is visible to whoever
reads it. The same is true once the file drifts from what the approval
bound, or the bound report's manifest no longer matches the one in force:
the raise lapses back to one until a fresh approval is recorded.

Three surfaces read the same computation: starting a ticket's first
stage or admitting it out of `intake` refuses at the limit instead of
proceeding, and the two status views that list open work state the wait
in the same words, so a human reading either one sees the same reason a
ticket is not moving.

Requirements: R-I-10.
