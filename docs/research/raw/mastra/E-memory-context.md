# Packet E — Memory, observational memory, RAG/context retrieval, workspace file access, code-mode, request context

Scope: `packages/core/src/memory/`, `packages/memory/` (Observational Memory), `packages/core/src/workspace/`,
`packages/rag/`, `packages/core/src/vector/`, `code-mode/`, `packages/core/src/request-context/`,
`packages/core/src/cache/`, `packages/core/src/features/`, `packages/core/src/predicate/`, and the
context-window/compaction/token-limit processors under `packages/core/src/processors/processors/`.

## 1. What Mastra does here

### 1.1 Threads, messages, working memory (`packages/core/src/memory/`)

Mastra's baseline memory model is a conversational one: a `StorageThreadType` (`packages/core/src/memory/types.ts`)
— `id`, `resourceId`, `title`, `createdAt`/`updatedAt`, `metadata` — holds an ordered list of
`MastraMessageV1`/`MastraDBMessage` rows, each with `role` (`system`/`user`/`assistant`/`tool`/`signal`),
`content`, `threadId`, `resourceId`. `resourceId` is typically a user; `threadId` a conversation. Everything else
(working memory, semantic recall, Observational Memory) is a *processor* layered on top of this raw message list —
`packages/core/src/processors/memory/message-history.ts`, `working-memory.ts`, `semantic-recall.ts`.

`WorkingMemory` (`packages/core/src/memory/types.ts`) is a small structured blob (either a free-text `template`, a
Zod `schema`, or `none`), scoped `'thread'` or `'resource'` (default `'resource'`), optionally delivered as a
"state signal" instead of folded into the system prompt (`useStateSignals`) to keep the prompt prefix
cache-stable. It is explicitly framed as "small, structured data," distinct from the event-log role Observational
Memory plays (see the doc's "Comparing OM with other memory features" table).

Semantic Recall (`packages/core/src/processors/memory/semantic-recall.ts`) is classic RAG over past messages: a
`MastraVector` + `MastraEmbeddingModel`, `topK` (default `4`), `messageRange` (default `1` message of context
before/after each hit), `scope` (`'thread'`/`'resource'`, default `'resource'`), `threshold`, and an
`embeddingCache` (`embedding-cache.ts`) to avoid re-embedding identical queries.

### 1.2 Observational Memory (OM) — `packages/memory/src/processors/observational-memory/`

OM (added `@mastra/memory@1.1.0`, doc: `docs/src/content/en/docs/memory/observational-memory.mdx`) is a background
compression system for long-running chat threads, built from two LLM roles plus a large amount of scheduling logic:

**The three-tier model.** (1) Recent raw messages — exact history for the current task. (2) *Observations* — a
dense append-style log the **Observer** writes: terse, dated, priority-tagged bullets (`🔴`/`🟡`/`🟢` urgency,
`✅` completion) with 1–5 observations per exchange, "5x to 40x" compression. (3) *Reflections* — when the
observation log itself grows past a threshold, the **Reflector** rewrites the *entire* log into a smaller one
(not an additional layer); the next reflection re-processes everything again, so the log stays bounded forever.
Both roles share one system-prompt builder (`buildObserverOutputFormat` in `observer-agent.ts`, reused by
`reflector-agent.ts`), and the Observer's own guideline text (`OBSERVER_GUIDELINES`, `observer-agent.ts:362`) is
explicit about *what* to write ("Be specific enough for the assistant to act on… Group repeated similar actions…
Capture the user's words closely"). The Reflector's job is different in kind, not degree: `buildReflectorSystemPrompt`
(`reflector-agent.ts:41`) says it "re-organizes and streamlines," "draws connections and conclusions," and
"identif[ies] if the agent got off track" — a synthesis pass, not a second observation pass. Its compression is
driven by a five-level escalating-instruction retry loop, `COMPRESSION_GUIDANCE[0..4]` (`reflector-agent.ts:145-236`,
`MAX_COMPRESSION_LEVEL = 4`): level 0 is a first free attempt; levels 1–4 progressively demand "Aim for a X/10
detail level" (8/10 → 2/10), and `validateCompression` (`reflector-agent.ts:410`) re-runs the Reflector at the next
level whenever its output isn't smaller than the input, so the loop terminates on a shrinking sequence rather than
trusting the model's first attempt.

**Triggers (`thresholds.ts`, `constants.ts`).** Defaults: `observation.messageTokens = 30_000` (Observer fires when
unobserved message tokens exceed this), `reflection.observationTokens = 40_000` (Reflector fires when the
observation log exceeds this). Both can be a plain number or a `ThresholdRange {min, max}` for a `shareTokenBudget`
mode where the message budget can borrow unused observation space (`calculateDynamicThreshold`,
`thresholds.ts:18-46`). Async buffering (on by default) pre-computes observation "chunks" every
`bufferTokens` interval (default `0.2` = 20% of `messageTokens`, i.e. ~6k tokens) so activation at the threshold is
instant; `bufferActivation` (default `0.8`) sets how much raw history to drop on activation (retain ~20%);
`blockAfter` (default `1.2`×threshold) is a safety valve that lets activation overshoot rather than starve;
`activateAfterIdle` (`'auto'` or a duration) force-activates buffered chunks once a provider's prompt-cache TTL has
likely expired — `activation-ttl.ts` hard-codes per-provider TTLs (OpenAI 5m/1h depending on model and
`promptCacheRetention`, Gemini 24h, DeepSeek/Groq 1–2h, everyone else 5m default).

**The observation record's shape.** Observations are plain Markdown text with two citation mechanisms layered on
top, both string conventions rather than schema:
- *Ephemeral anchor ids* (`anchor-ids.ts`): every non-heading, non-XML line gets a `[O<n>]` or nested `[O<n>-N<m>]`
  prefix injected right before it's shown to a model turn, then stripped again (`stripEphemeralAnchorIds`) before
  persisting — they exist only to let a model *reference* a specific observation line in the same turn, are
  regenerated every time, and carry no identity across turns.
- *Observation groups* (`observation-groups.ts`), used only when "retrieval mode" is on: `<observation-group
  id="…" range="startId:endId" kind="…">…</observation-group>` wraps a block of observations with the *raw message
  id range* it was derived from. `combineObservationGroupRanges` merges group ranges when the Reflector folds
  several groups into one. This is the actual provenance mechanism — not a hash, a half-open id range into the
  thread's own message table.

**Retrieval mode** (`retrieval: true` or `retrieval: { vector: true }` in config) registers a `recall` tool the
agent can call with a `cursor` (a message id from a group's `range`) to page through the *original* raw messages a
compressed observation came from — "no vector store needed" for plain browsing; `vector: true` additionally indexes
each new observation group for semantic search over the raw corpus. This is OM's answer to "the original wording is
gone": it is opt-in, and off by default.

**TTL / staleness is about prompt-cache economics, not truth.** `activation-ttl.ts`'s only job is: how long can we
leave buffered-but-inactive observations un-activated before the provider's cache would have expired anyway. There
is no notion anywhere in OM of a *fact* going stale — once written, an observation is durable and is only ever
rewritten by a later Reflector pass (condensed, not fact-checked). The system prompt Mastra injects alongside
observations (`OBSERVATION_CONTEXT_INSTRUCTIONS`, `constants.ts`) tells the model to prefer the *newest* stated fact
when two observations conflict ("Observations include dates - if you see conflicting information, the newer
observation supersedes") — a convention enforced by prompt instruction, not by any staleness computation.

**Failure handling** (`retry.ts`, `error.ts`): transient transport errors (timeouts, ECONNRESET, 408/425/429/5xx,
AI-SDK `isRetryable`) are retried with exponential backoff + jitter, 8 retries / ~4 minutes total
(`RETRY_CONFIG`, `retry.ts:19-27`), walking the `.cause`/`.error` chain so wrapped errors aren't missed. Any
non-transient error (auth, schema validation, a malformed model response) is rethrown immediately — OM does not
silently fall back to keeping raw history forever; a hard Observer/Reflector failure surfaces as a
`data-om-observation-failed` marker (`markers.ts`) and (per the docs) blocks that cycle rather than corrupting the
log.

**Extractors** (`extractor.ts`, doc §"Extractors") let an app declare named, optionally Zod-schema'd values (e.g.
"current task," "user profile," "mood") the Observer/Reflector should also emit; schema-less ones are inline string
fields in the same response, schema'd ones trigger a follow-up structured-output call. Built-in extractors are
*current task*, *suggested response*, and (opt-in) *thread title*.

**Subconscious** (`packages/memory/src/processors/observational-memory/subconscious/`) is a separate, smaller
mechanism layered next to OM: `pinned.ts`/`pinned-state-processor.ts` keep a small set of always-injected pinned
facts (state-signal delivered, like working memory); `remind*.ts` implement a "remind" protocol — a background pass
that can proactively re-surface a pinned fact or ask a clarifying question mid-conversation; `knowledge-tools.ts`/
`knowledge-write-tools.ts` expose tools for the agent to read/write a small curated knowledge store;
`semantic-index.ts` indexes that store. It is conceptually "a curated, agent-writable, always-visible fact store"
sitting beside OM's "background-compressed event log," not a mode of OM itself.

### 1.3 Workspace abstraction (`packages/core/src/workspace/`)

`Workspace` (`workspace.ts`, overview in `README.md`) composes four independently swappable subsystems behind one
object handed to an `Agent`:

- **Filesystem** (`filesystem/`): a `WorkspaceFilesystem` interface with `LocalFilesystem`, a remote/sandboxed
  `MastraFilesystem`, and a `CompositeFilesystem` that mounts several filesystems at different paths
  (`filesystem/mount.ts`). Two correctness aids sit here, neither present in a plain mounted directory: a
  `FileReadTracker` (`file-read-tracker.ts`) records `(path, readAt, modifiedAtRead)` per file and exposes
  `needsReRead(path, currentModifiedAt)` — a tool wrapper can *refuse a write* until the agent has read the file's
  current content, and re-refuse if the file changed on disk after that read (classic "read-before-write" /
  optimistic-lock guard against blind overwrites). A `FileWriteLock` (`file-write-lock.ts`) is a per-path promise
  queue (`withLock`, 30s default timeout) serializing concurrent writers to the same file — a race-condition guard
  for multi-agent or multi-tool-call concurrency, not needed by a single sequential writer.
- **Sandbox** (`sandbox/`): a `WorkspaceSandbox` interface with a `LocalSandbox` (raw `execa`) and a
  `MastraSandbox` (remote). `native-sandbox/seatbelt.ts` generates a macOS `sandbox-exec` SBPL profile
  programmatically: deny-by-default, then `(allow file-read*)` for all reads (macOS cannot subpath-restrict reads,
  so they allow all reads and instead restrict *writes* to workspace + temp directories via `(allow file-write*
  (subpath …))`), network denied unless `allowNetwork`, and a fixed Mach-service allowlist
  (`MACH_SERVICES`, `seatbelt.ts:26-36`) needed for basic process operation (distributed notifications, logd,
  opendirectoryd, securityd, trustd). The comment block documents two real macOS gotchas worth copying literally:
  `-p` (inline profile) must be used instead of `-f` (file) because `-f` "doesn't work reliably with path filters on
  modern macOS," and `(allow file-read* (subpath …))` only works *given* a preceding blanket `(allow file-read*)`.
  The file explicitly credits Anthropic's own `sandbox-runtime` as the approach's origin. `native-sandbox/bubblewrap.ts`
  is the Linux equivalent. `sandbox/mount-manager.ts` and `mounts/` handle read-only vs read-write mount
  declarations; `process-manager/` tracks long-running background processes started inside the sandbox
  (`execute-command` with `background: true`, then `get-process-output`/`kill-process` tools).
- **Search** (`search/`): `bm25.ts` is a from-scratch BM25 lexical index; `search-engine.ts` unifies BM25, vector
  (`'vector'`), and `'hybrid'` search behind one `SearchEngine`, with a batch-capable embedder interface. No vector
  store is required for BM25 mode. `workspace.index(path, content)` feeds it.
- **Skills** (`skills/`): discovers `SKILL.md` files (explicitly "following the Agent Skills specification," the
  same spec our `factory/` skills already use — `skills/types.ts:1-6` links `github.com/anthropics/skills`),
  distinguishes `external`/`local`/`managed` content sources, and layers a `CompositeVersionedSkillSource` over
  several sources with precedence. This is the same shape as our own `agent_ref`/`skill_ref`/`shared_skill_hashes`
  mechanism, just discovered at runtime from a directory list instead of resolved by the manifest at dispatch.
- **LSP** (`lsp/`): a managed language-server client giving the agent go-to-definition/references/diagnostics tools
  (`lsp-inspect.ts`) — a generic alternative to a project-specific code index.
- **Tools** (`tools/`): the full file-op/exec surface a workspace-equipped agent gets: `read-file`, `write-file`,
  `edit-file`, `delete-file`, `list-files`, `mkdir`, `file-stat`, `grep`, `search`, `index-content`, `ast-edit`
  (structural code edits), `lsp-inspect`, `execute-command`(+background variant), `get-process-output`,
  `kill-process`, `media.ts`, plus a GUI-automation family (`computer-click`, `computer-screenshot`, `computer-type`,
  etc.) irrelevant here. Safety knobs are configured per tool name (`requireApproval`, `requireReadBeforeWrite`,
  `mediaTypes` allowlist) in `tools/types.ts`.

### 1.4 RAG (`packages/rag/`) and the vector interface (`packages/core/src/vector/`)

Chunking (`document/transformers/`) offers character/token/sentence splitters and a header-aware
`SemanticMarkdownTransformer` (`semantic-markdown.ts`) that splits Markdown by header depth then joins small
adjacent sections up to a `joinThreshold` (default `500` tokens, tiktoken-counted) so chunks are neither too small
nor blind to document structure. Metadata **extractors** (`document/extractors/`) attach LLM-derived fields to a
chunk: `TitleExtractor`, `SummaryExtractor` (self/prev/next summaries), `QuestionsAnsweredExtractor` (default `5`
questions the chunk could answer), `KeywordExtractor` — all built on a shared `BaseExtractor` + `PromptTemplate`
pattern, independent of any vector store. **Reranking** (`rerank/relevance/`) has a `mastra-agent` implementation
(`rerank/relevance/mastra-agent/index.ts`) that scores relevance by asking an `Agent` to return a bare `0–1` number
per (query, passage) pair — no cross-encoder model, no vector store, just an LLM call; alongside Cohere and
ZeroEntropy provider implementations. `MastraVector` (`vector/vector.ts`) is a thin abstract interface
(`query`/`upsert`/`createIndex`/`describeIndex`/`deleteIndex`) with a `VectorFilter` DSL — notable mainly as a
"what a generic retriever interface looks like," not as something to instantiate.

### 1.5 code-mode (`code-mode/`)

`createCodeMode(config, transport)` (`packages/core/src/tools/code-mode/code-mode.ts`) wraps a *set* of declared
tools into a single `execute_typescript` tool plus generated TypeScript stub instructions, so the model writes one
program that calls `getPrice(...)`, `search(...)` etc. directly instead of emitting N separate tool-call turns —
the classic "code mode" pattern (fewer round trips, tool composition expressed as real code). The program runs
inside an isolate, not the host process: `IsolatedVmCodeModeTransport` (`code-mode/isolated-vm/src/transport.ts`)
uses V8's `isolated-vm` — "the guest has no filesystem, network, process, or module access — the only capabilities
are the injected `external_*` functions, which call back into the host dispatcher (allow-list enforced host-side)."
Every call crosses the isolate boundary as a JSON string in both directions (no host object references leak in);
TypeScript is stripped with esbuild on the host first, since isolates only run plain JS. `code-mode/quickjs/` is the
lighter, more portable alternative backend (no native addon, works where `isolated-vm` can't be installed) with the
same transport contract. Neither backend needs a `WorkspaceSandbox` — the isolate itself is a memory-limited
(`memoryLimitMb`, default 128) execution boundary (`requiresSandbox: false`).

### 1.6 Misc core pieces

- **Request context** (`request-context/index.ts`): a small typed key-value bag threaded through a run — closer to
  a call-scoped dependency-injection context than to our envelope.
- **Cache** (`cache/base.ts`): an abstract `MastraServerCache` (get/set/listPush/listFromTo/increment, plus an
  atomic `listPushIndexed` for sequential event indices) — generic server-side KV/list caching, not memory-specific.
- **Features** (`features/index.ts`): a flat `Set<string>` of feature-flag names dependent packages test with
  `.has()` for cross-version compatibility — a versioning convention, not runtime logic.
- **Predicate** (`predicate/index.ts`): a small, JSON-safe declarative condition grammar — `eq`/`ne`/`lt`/`lte`/
  `gt`/`gte`, `in`/`notIn`, `exists`/`notExists`, `truthy`/`falsy`, `and`/`or`/`not` — over dotted paths, evaluated
  by a domain-supplied path resolver that fails quiet on a missing path (`false`, except `notIn`/`notExists` fail
  to `true`). `predicateSchema` is a Zod schema so a stored predicate validates at load time; `collectInvalidPredicatePaths`
  statically checks path roots against a domain's declared set; `derivePredicateLabel` renders it back to a short
  human string. Framework-generic, but directly relevant to how *rules* (not facts) get stored and versioned.

### 1.7 Context-window / compaction / token-limit processors

`processors/processors/token-limiter.ts`: an input processor (truncate history to fit) and output processor
(truncate/abort a generating response) over a token `limit`, using `tokenx` fast estimation rather than a real
tokenizer; `strategy: 'truncate' | 'abort'`; `countMode: 'cumulative' | 'part'`. Media is estimated with fixed
heuristics rather than tokenized (`TOKENS_PER_IMAGE = 765`, `TOKENS_PER_MEDIA_FALLBACK = 258`,
`BYTES_PER_TOKEN = 4` for non-image files) since stringifying a base64 image would wildly overcount.
`token-cost-control.ts` is a *cost*, not token-count, gate: `CostScope` = `'run' | 'resource' | 'thread' | 'user' |
'organization' | 'session'`, cumulative over named `CostWindow`s (`'1h'|'6h'|'24h'|'7d'|'30d'|'365d'`), aborting
(TripWire) once `maxCost` is exceeded for the scope+window; `'user'`/`'organization'`/`'session'` scopes fail open
(skip the check) when the RequestContext lacks the corresponding id, rather than blocking. `message-selection.ts`
is an 18-line helper (`selectMessagesToCheck`) letting a guardrail-style processor run only against the latest
message instead of the whole history when `lastMessageOnly` is set.

## 2. What we already have

Our equivalent surface is spread across the PRD, the HLD's domain 3 (Execution boundary) and domain 4 (Record), and
several runner modules. The comparison, mechanism by mechanism:

- **Threads/messages/conversational memory** — we have none, deliberately. `R-I-2` (`docs/prd/03-stage-interface.md`):
  "Each agent attempt is a fresh invocation… nothing from an earlier invocation's transcript." There is no thread,
  no resource, no message list to compress; the closed loop's memory channel is exclusively the governed,
  content-addressed `artefact` table (`docs/prd/02-2-entities.md`). This is the single biggest structural
  difference from everything OM/semantic-recall/working-memory assume.

- **Observational Memory's job, done differently.** The nearest analogue to an "observation log across attempts"
  is `failure_history` (`docs/prd/02-2-entities.md`, R-S4-6): "written so the human can act from the escalation
  item alone," carrying the approved plan-item version, per-execution attempt/outcome/diagnosis/head-SHA/tokens,
  consumed verification quota, and dependent-task state. It is compiled by the *trusted runner* from typed
  `stage_run`/`check_result` rows, not paraphrased by a second LLM pass — the S1 driver's own doc-comment states
  the general rule explicitly: "the classification is never trusted from the agent" (`runner/stages/context_gathering.py`),
  and the same "runner computes, agent doesn't get to summarize its own state" pattern governs `Final tier`
  and `index_reads`. `tool_call` (one row per call, with `result_bytes`/`inline`) and the governed `tool_result`
  artefact (R-I-17) are our analogue of OM's retrieval-mode "keep the raw source linked to the summary" — except
  every "observation" we keep is either full-fidelity (the governed file) or a deterministic bounded excerpt, never
  an LLM's lossy paraphrase of a prior LLM's output.

- **Freshness/staleness — a different concept entirely.** `runner/freshness.py` (`BEFORE_IMPLEMENTATION`,
  `CHECKS_PREFLIGHT`, `BEFORE_DISPATCH` boundaries) and `runner/context_index.py` (`stale_reason`, `FM-17`
  "memory rot") both check whether a *fact* is still true — has the target branch moved, has a base-branch commit
  touched a context-index entry's `paths` since its `last_verified`, does the worktree HEAD still match what was
  approved. OM has no equivalent: `activation-ttl.ts` decides when to *compress*, never whether an already-written
  observation is still correct. Our freshness model is strictly the more developed of the two; there is nothing
  useful to port from OM here (see finding under §4).

- **Sandbox / execution boundary** (`docs/design/hld/L2-execution-boundary.md`, domain 3: G1 runtime adapter/
  envelope, G2 the wall — launcher/recipe runner/OS policy/loopback proxy, G3 sandbox interior; R-I-14) already
  implements the same shape Mastra's `WorkspaceSandbox` + `native-sandbox/seatbelt.ts` implements: read-only mounts
  by default, write access scoped to one path (our worktree, S4 only, vs their configured writable subpaths),
  network denied except a fixed allowlist (our loopback proxy vs their `allowNetwork` flag), and a macOS Seatbelt
  profile is explicitly named in our R-I-14 rows as the AB-milestone deliverable. We do not yet have the actual
  SBPL text; Mastra's `seatbelt.ts` is a literal, tested reference implementation of exactly that artifact.

- **Workspace filesystem tools vs our `staged inputs/` (per-run `out/`/`results/`) and worktree mount** — our stage
  gets: a read-only (or S4 read-write) worktree mount, the governed artefacts named in its envelope, and an
  `out/`-writable / `results/`-read-only per-run directory (R-I-14, R-I-17; `docs/design/hld/L2-record.md`
  diagram 1's `G3_rundir`). What we do *not* have that Workspace gives an agent: (a) a read-before-write guard
  (nothing stops an S4 agent from overwriting a file it never read this attempt — we rely on the plan's declared
  `Scope and discretion` table plus post-hoc `deviation` rows, not a live tool-level guard); (b) full-text/BM25
  search over prose that codegraph (a *code* graph) doesn't index — our context index (`factory/index/*.md`) is a
  handful of hand-curated entries (`callers.md`, `conventions.md`, `sensitive-paths.md`), not a searchable corpus,
  by design (C3: "a finding from run state enters the versioned files only through a change the engineer reviews").

- **Skills** (`agent definitions and skills`, domain 5, `F3`) already use the identical Agent Skills / `SKILL.md`
  spec Mastra's `skills/` subsystem discovers — this is convergent design, not a gap.

- **RAG/vector** — we deliberately have none (D8, the Owner's constraint list: "codegraph, Inspect, official Slack
  and Atlassian MCP are the allowed external pieces"; no vector store is chosen). `runner/readers/atlassian.py`
  (Jira issue read, baseline history, Confluence history) and `factory/scripts/tools/archaeology`
  (`git blame` → issue keys → Atlassian read, classified `explained`/`unexplained`/`contradictory`) are our
  context-gathering retrieval mechanism — evidence-graph, not similarity-search.

- **code-mode** — flatly excluded by our own contract: R-I-16 ("No shell interpolation, command substitution,
  redirection, or untyped free text is accepted… Plans cite recipe ids and typed values"), R-I-18 (process
  execution confined to "the runtime itself and the recipe programs the catalogue declares"), and R-I-3/R-I-11
  ("Native write and shell tools are denied unless the stage role permits them… no arbitrary shell at any stage").
  Every deterministic check we run goes through `command-recipes.yaml`, executed by the trusted `G2_reciperunner`
  (`docs/design/hld/L2-execution-boundary.md`), never by model-written code.

- **Cost/budget** (`R-I-6`, `docs/prd/03-stage-interface.md`) is per-stage-tier and cumulative-per-ticket-S4 only;
  we have nothing like Mastra's named multi-scope multi-window cost aggregation (`token-cost-control.ts`'s
  `run`/`resource`/`thread`/`user`/`organization`/`session` × `1h..365d`) — not needed yet at one ticket in flight,
  relevant once `R-I-10`'s parallel-ticket limit is raised past 1.

- **Rules as config, not as code** — `tiers.yaml`'s `final_tier_rule`, `split_threshold`, forced-category
  resolution, and `runner/checks/brief.py`'s `final_tier_rule`/`impact_derived_tier` functions are hand-written
  Python reading plain YAML dicts, matched by hand-written tests. There is no shared declarative condition grammar
  the way Mastra's `predicate/index.ts` gives every domain (workflows, scoring, …) one evaluator.

## 3. Portable ideas

1. **macOS Seatbelt profile gotchas and Mach-service allowlist (literal reference).**
   The specific SBPL authoring knowledge in `packages/core/src/workspace/sandbox/native-sandbox/seatbelt.ts`
   (`-p` inline profile instead of `-f`; `(allow file-read* (subpath …))` needs a preceding blanket
   `(allow file-read*)`; the fixed `MACH_SERVICES` list needed for a sandboxed process to do anything at all) is a
   tested, working macOS sandbox-exec profile generator, credited to Anthropic's own `sandbox-runtime`.
   *Why it matters*: R-I-14's OS policy is exactly this artifact, due at Milestone AB; getting the Mach-service
   allowlist or the `-p`-vs-`-f` behavior wrong is the kind of thing that surfaces as a mysterious sandboxed-process
   hang, not a clean refusal — serves FM-05 (Later: not yet catalogued, but structurally a "silent capability gap")
   and directly implements R-I-14/D9.
   *Rating*: **next milestone** (AB — when the OS policy is actually built; nothing to do before then).
   *Lands*: `docs/prd/03-stage-interface.md` R-I-14 (no new row — implementation detail); HLD component G2 (the
   wall), domain 3, seam X11 (sandbox wall); config file `sandbox.yaml`'s `os_profiles`.
   *Draft acceptance*: given the AB Seatbelt profile, (a) a sandboxed process can still resolve DNS-independent
   Mach lookups needed for basic libc/Foundation calls; (b) `sandbox-exec -p <profile>` is invoked, never `-f`;
   (c) `must-reject:` a probe that reads outside the declared `readOnlyPaths`/worktree subpath is denied; (d)
   `must-reject:` a probe that writes outside the worktree subpath (or, at S1–S3, any write at all) is denied.
   *Verified by*: the escape suite named in R-I-14's own "Verified by" cell (paths, symlinks, subprocesses,
   environment, sockets, network, mounts already listed there) plus a new case for the Mach-lookup allowlist.
   *Size*: **S** (reference material, not new code — verify our profile author knows the two gotchas).
   *Copy literally*: the `-p`-not-`-f` invocation shape and the Mach-service name list. Re-derive: our own
   `readOnlyPaths`/write-subpath contract already differs (per-stage worktree RO/RW, not a static config), so the
   profile *generation* logic (per-stage, from `sandbox.yaml`) should stay ours.

2. **Read-before-write guard on the S4 worktree, with a modification-time check.**
   Mastra's `FileReadTracker` (`filesystem/file-read-tracker.ts`) refuses a write until the same tool session has
   read the current file content, and re-flags if the file changed on disk since that read.
   *Why it matters*: serves P5 ("Not touching is the default… presumed correct until shown otherwise") and FM-21
   (state loss: "contradicts its own earlier decision") by catching a blind overwrite at tool-call time instead of
   only after the fact via a `deviation` row. New mechanism for us — we currently rely on the plan's `Scope and
   discretion` table and post-hoc deviation classification, not a live guard.
   *Rating*: **next milestone** (a real but non-blocking safety net for S4; the pilot's single-ticket-at-a-time
   scope means the risk it catches is lower-frequency than in a long multi-turn chat agent).
   *Lands*: `docs/prd/03-stage-interface.md`, extends R-I-3/R-I-11 (tool confinement) — new row, not an existing
   one; HLD component G3 (`G3_agent`, `G3_s4write`), domain 3, no new seam (the guard lives inside the interior's
   write-file tool wrapper).
   *Draft acceptance*: (a) a write to a worktree file the current S4 attempt has not read is refused with a
   named reason; (b) a write to a file read earlier in the same attempt but modified on disk since (e.g. by a
   recipe) is refused until re-read; (c) `must-reject:` a write to an unread file never reaches the worktree.
   *Verified by*: script test on the S4 write tool wrapper (three fixture files: never-read, read-then-unchanged,
   read-then-externally-modified).
   *Size*: **S**.
   *Copy literally*: the `(path, readAt, modifiedAtRead)` record shape and the `needsReRead` comparison rule.
   Re-derive: our tracker is per-attempt (cleared each fresh S4 invocation, matching R-I-2), not per-session.

3. **BM25 lexical search over the factory tree / long prose documents.**
   `packages/core/src/workspace/search/bm25.ts` + `search-engine.ts` give an agent keyword search over indexed text
   with no vector store — relevant because codegraph indexes *code*, not the PRD, ADRs, or long Confluence pages an
   archaeology or context-gathering pass might need to search.
   *Why it matters*: no failure mode currently names this gap explicitly; flagged as **new**. Low current value
   because our context index is deliberately small and hand-curated (C3), not a corpus to search.
   *Rating*: **later** (revisit once the context index or archaeology's Confluence reads grow past what a human can
   curate by hand).
   *Lands*: `docs/prd/04-S1-context-gathering.md`, extends R-S1-4 (archaeology) or R-S1-7 (index reads) — new row;
   HLD component G3 (`G3_codegraph` sibling — a new "prose index" part), domain 3, seam X6 (model reach) unchanged.
   *Draft acceptance*: (a) a search over indexed Markdown returns ranked hits with the matching line range; (b) an
   empty index returns no results, never an error; (c) `must-reject:` a search over unindexed content raises rather
   than silently returning nothing so the caller can distinguish "no index" from "no match."
   *Size*: **M** (BM25 itself is ~a day; wiring it into context gathering and deciding what gets indexed is the
   rest).
   *Copy literally*: the BM25 scoring algorithm (well-understood, small). Re-derive: what gets indexed and when —
   our C3 curation rule means this can't just be "index everything under `factory/`."

4. **Escalating-compression retry for a size-capped agent output.**
   The Reflector's `COMPRESSION_GUIDANCE[0..4]` + `validateCompression` retry loop (`reflector-agent.ts`) re-asks
   the model with progressively firmer instructions when its own output doesn't fit the target, instead of hard
   -rejecting on the first miss.
   *Why it matters*: serves P10 (only automate what's cheap to check) by turning a size-limit miss into a bounded
   auto-retry instead of a wasted whole-stage rerun; relevant to R-S1-2 (brief summary word limit) and the
   `reasoning_summary` size cap (R-I-13), both of which today fail the *whole attempt* on overrun rather than
   giving the model one more chance with explicit compression guidance.
   *Rating*: **later** (a quality-of-life improvement to reduce wasted reruns; not needed for a first pilot ticket
   where reruns are cheap and the a human is watching every question anyway).
   *Lands*: `docs/prd/04-S1-context-gathering.md` R-S1-2 — extends existing row (adds a bounded retry before the
   fail path); HLD component G1 (envelope/adapter) or the S1 stage driver, no new component.
   *Draft acceptance*: (a) an over-length summary triggers at most N (config) compression retries with
   escalating guidance before failing structural; (b) each retry is a separate `stage_run` child, budgeted and
   recorded like the S2 restatement children (R-S2-3); (c) `must-reject:` a summary that is still over-length after
   the retry ceiling fails the attempt exactly as it does today.
   *Size*: **S**.
   *Copy literally*: nothing verbatim (the prompt text is theirs); re-derive the "try again with X/10 detail"
   framing for our own word/line limits, and reuse our existing child-`stage_run` pattern (R-S2-3) rather than
   inventing a new one.

5. **LLM-based relevance ranking without a vector store, for archaeology/touched-area candidates.**
   `packages/rag/src/rerank/relevance/mastra-agent/index.ts` scores (query, passage) relevance with a plain "return
   a number 0–1" agent call — no embeddings needed.
   *Why it matters*: **new** — when archaeology (R-S1-4) or touched-area discovery turns up many candidates, a
   cheap relevance pass could help order them for the brief without adopting a vector store, which the Owner's
   constraints already rule out.
   *Rating*: **later** (our current volumes — one ticket, a handful of candidate files — don't need ranking beyond
   what the agent already does inline).
   *Lands*: `docs/prd/04-S1-context-gathering.md`, extends R-S1-4 — new row; no new HLD component (runs as an extra
   model call inside the existing S1 sandbox interior).
   *Draft acceptance*: (a) candidates are returned with a relevance score in `[0,1]`; (b) a malformed or
   out-of-range score is rejected and the candidate keeps its original order; (c) `must-reject:` a scorer call that
   times out or errors never silently drops a candidate from the brief.
   *Size*: **S**.
   *Copy literally*: the "return only the number" prompt discipline and its parse/validate function
   (`parseRelevanceScore`). Re-derive: everything about what gets scored and why (ours is evidence classification,
   theirs is text similarity).

6. **A declarative predicate grammar for our own rule config (tiering, split, forced categories).**
   `packages/core/src/predicate/index.ts`'s JSON-safe `eq/ne/lt/lte/gt/gte/in/notIn/exists/notExists/truthy/falsy/
   and/or/not` DSL over dotted paths, schema-validated at load time, with static path-root checking and a
   human-readable renderer.
   *Why it matters*: directly serves the charter's stated preference ("prefer rules to hard-coded numbers; numbers
   live in config") more uniformly than today's per-rule Python functions (`checks_brief.final_tier_rule`,
   `clarification._split_required`) each hand-rolling their own comparison logic against `tiers.yaml`. A shared
   grammar makes every threshold rule auditable and versionable the same way (one parser, one renderer for the
   human-readable summary shown at review), rather than one bespoke function per rule.
   *Rating*: **next milestone** (a clean generalization that reduces near-duplicate rule code as more tier/split/
   category rules accumulate; not blocking the first pilot ticket, which only exercises the rules that already
   work).
   *Lands*: `docs/prd/08-configuration.md` (`tiers.yaml`'s `final_tier_rule`/`split_threshold` shape) — extends
   existing config, no new PRD row; no new HLD component (a library used by the existing S1/S2 stage drivers).
   *Draft acceptance*: (a) a stored predicate evaluates identically to today's hand-written `final_tier_rule` for
   every existing fixture case; (b) a predicate referencing an unknown path root fails validation at manifest/config
   load time, not at rule-evaluation time; (c) `must-reject:` a predicate with a malformed shape (e.g. `in` with an
   empty `set`) is refused by the schema before it ever reaches a ticket.
   *Size*: **M** (the grammar itself is small; migrating `final_tier_rule` and `_split_required` onto it and
   re-verifying every existing fixture is the real cost).
   *Copy literally*: the grammar shape (op names, `{path}`/`{literal}` value refs, fail-quiet-to-false semantics for
   missing paths) and the static path-root validator pattern. Re-derive: our own evaluation context (ticket/brief/
   criteria fields, not a chat request context).

7. **Factory-wide, multi-window cost aggregation, once parallel tickets scale.**
   `token-cost-control.ts`'s named `CostScope` (`run`/`resource`/`thread`/`user`/`organization`/`session`) crossed
   with named `CostWindow`s (`1h..365d`) is a ready-made shape for "how much have we spent across all tickets this
   week," which our current per-ticket/per-stage budget (R-I-6) doesn't answer.
   *Why it matters*: **new** — relevant once R-I-10's parallel-ticket limit is raised past 1 and per-ticket budgets
   no longer bound total spend. *Rating*: **later** (irrelevant at one ticket in flight).
   *Lands*: `docs/prd/03-stage-interface.md`, extends R-I-10 — new row; HLD domain 4 (Record), extends R5.
   *Draft acceptance*: (a) a factory-wide window (e.g. `24h`) aggregates cost across every `stage_run`/
   `utility_run` in that window; (b) a scope whose identifying field is absent from a run is excluded, never
   coerced to zero; (c) `must-reject:` an aggregate exceeding a configured cap blocks new admission at `intake`,
   not mid-stage. *Verified by*: script test over a seeded run set. *Size*: **M**.
   *Copy literally*: the scope × window cross-product shape. Re-derive: our source is `stage_run`/`utility_run`
   rows with settled `cost_basis` provenance, stricter than Mastra's usage-metric traces.

8. **Header-aware Markdown chunking for bounded excerpts of long source documents.**
   `packages/rag/src/document/transformers/semantic-markdown.ts` splits by header depth and joins small sections up
   to a token `joinThreshold` (default 500) — a smarter unit than a raw head/tail cut for a long Confluence page or
   design doc that must fit inside R-I-17's bounded excerpt.
   *Why it matters*: **new** — today a long tool/document result gets a fixed head-and-tail excerpt (R-I-17);
   header-aware chunking could pick the section that actually matched instead of literal first/last N lines.
   *Rating*: **later** (the current head/tail rule is simple and auditable, which matters more at pilot scale).
   *Lands*: `docs/prd/03-stage-interface.md`, extends R-I-17 — new row (an alternative excerpt strategy); HLD
   component G1 (`tool_result` artefact governance), domain 3.
   *Draft acceptance*: (a) a long document's stored excerpt covers a coherent header-delimited section, not an
   arbitrary line cut; (b) the excerpt still respects the section 8 byte/line bound; (c) `must-reject:` an excerpt
   that spans a header boundary mid-section when a clean boundary was available. *Verified by*: fixture test over
   a long multi-header document. *Size*: **S**.
   *Copy literally*: the join-threshold joining logic. Re-derive: token counting (our own estimate, not tiktoken,
   to avoid a new dependency).

## 4. Questions for the owner

- **Should a read-before-write guard apply only to the S4 implementation stage, or to any future stage that gets
  write access?** Default: S4 only, since it's the only stage with any write role today (R-I-3/R-I-11); revisit if
  a later stage gains scoped writes.
- **Should the compression-retry idea (item 4) apply to every size-capped agent output, or just the brief summary
  it was scoped against here?** Default: brief summary only for now (R-S1-2), since that's the one place we've
  already observed a hard word limit with a known failure path; extend to `reasoning_summary` only if reruns caused
  by that specific limit turn out to be common in the pilot.
- **Is a shared rule grammar (item 6) worth the migration cost before the pilot, or should it wait until a second
  or third similar rule shows up and the duplication becomes visible in practice?** Default: wait — migrate
  `final_tier_rule` and the split rule onto it only once a third rule of the same shape is about to be written by
  hand.

## 5. Do-not-port list

- **Observational Memory as a subsystem** (the Observer/Reflector background compression loop, buffering,
  activation, retrieval mode). It solves "a long-lived conversational thread's raw history grows without bound,"
  a problem we do not have: R-I-2 makes every agent invocation fresh by design, and the only cross-invocation
  memory channel is the governed `artefact` table plus `failure_history`/`deviation` rows the *trusted runner*
  compiles from typed data, never an LLM's paraphrase of another LLM's output. Porting OM would mean reintroducing,
  via a second model call, exactly the kind of "agent self-report the human can't fully trust" our record model
  (C4 judge separation, P6 "nothing that fakes confidence") is built to avoid. If a compact cross-attempt summary
  is ever needed beyond what `failure_history` gives today, the answer is a *deterministic* compaction pass over
  that table (see item 4's smaller, related idea), not an LLM observer.
- **Semantic Recall / vector-store-backed retrieval.** Directly excluded by the Owner's tooling constraint (no
  vector store chosen; codegraph + the Atlassian/GitHub readers are the sanctioned retrieval path) and duplicates
  what our evidence-graph archaeology (R-S1-4) already does with a stronger provenance chain (named issue, blame
  commit) than a similarity score gives.
- **Token-tiered model selection (`ModelByInputTokens`).** Directly violates R-I-4/D5/D31: "no adapter silently
  substitutes a runtime, model, tool, or image… a mismatch is recorded as `infrastructure_failure`." Our model
  identity is manifest-pinned and checked before *and* after every invocation; letting input size pick the model
  at runtime is the exact failure mode that check exists to prevent.
- **code-mode (isolated-vm / QuickJS "run model-written code as a tool").** Violates R-I-16 (typed recipes only, no
  free-form code) and R-I-18 (process execution confined to the runtime and declared recipe programs). Even as
  a sandboxing *pattern* it's solving a problem we don't have — we never let a model author executable code that
  the runner then runs; every deterministic action is a pre-declared, digest-pinned recipe the trusted runner
  itself invokes.
- **LSP client integration.** Duplicates codegraph, the one sanctioned external code-index tool (Owner's
  constraint list), and would add a second niche tool where the enterprise rule asks for none.
- **File-write-lock (per-path concurrency queue).** Solves multi-writer races that don't exist in our design — S4
  is the sole writer to the worktree, sequentially, one attempt at a time (R-I-3, R-I-11).
- **Continuation hints / "please continue naturally" prompt scaffolding.** Exists to paper over the seam where raw
  history was just deleted mid-conversation — a problem specific to compressing a *live* multi-turn thread, which
  we never have (every stage invocation is already a clean, fresh start per R-I-2).
- **Temporal gap markers, resource-scope cross-thread observation, thread titles.** All presuppose a persistent
  chat-style thread/resource model with no analogue in a ticket's stage sequence.
