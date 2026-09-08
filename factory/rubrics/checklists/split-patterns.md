# Split patterns

When the criteria describe more than one vertical slice, or the size
estimate exceeds the tier's threshold, propose a split. A split proposal
must name one of the six patterns below -- pick the one that actually cuts
the criteria into vertical slices with observable value on their own, not
just a smaller diff.

1. **workflow steps** -- split a multi-step process into one slice per
   step, each independently observable (submit, then confirm, then
   notify).
2. **business-rule variations** -- split by which rule applies (the
   standard case first, an exception or special case as a later slice).
3. **data variations** -- split by the shape or source of the data
   involved (one record type first, a second type later).
4. **interface variations** -- split by which caller or channel is
   served first (the primary API first, a secondary one later).
5. **defer performance** -- ship the correct behaviour first; a
   performance or scale requirement becomes its own later slice.
6. **simple then complex** -- ship the common, simple case first; a rarer
   or more complex variant becomes its own later slice.
