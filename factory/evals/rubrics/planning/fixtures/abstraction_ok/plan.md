## Abstraction and separate debt

| kind | unit | existing | reason |
|---|---|---|---|
| new_shared_abstraction | RetryPolicy | HttpRetry, GrpcRetry, DbRetry |  |
| widened_shared_function | formatMoney |  | inlining would duplicate rounding logic across five unrelated callers |
| new_utility | SlugGenerator | codegraph: no slug helper found; catalogue: no match | existing helpers only handle ASCII, this needs unicode normalisation |
