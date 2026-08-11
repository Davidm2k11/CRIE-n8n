# CRIE — Implementation Notes

The implementation-specific knowledge and operational gotchas needed to run,
deploy, and modify CRIE without re-discovering hard-won fixes. These are the
"how it actually works" details deliberately kept **out of**
[`PROJECT_CONTEXT.md`](../PROJECT_CONTEXT.md) and
[`docs/ARCHITECTURE_DECISIONS.md`](ARCHITECTURE_DECISIONS.md).

Procedures live elsewhere and are not duplicated here:
[`DEPLOYMENT_GUIDE.md`](DEPLOYMENT_GUIDE.md) (bring-up),
[`MIGRATION_CHAIN.md`](MIGRATION_CHAIN.md) (DB replay),
[`WORKFLOW_INVENTORY.md`](WORKFLOW_INVENTORY.md) (active vs archive + binding fix).

## Known-good runtime facts — do NOT "fix" these

These look like bugs but are deliberate. Changing them breaks the pipeline.

- **n8n interpolates `{{ }}` in a Postgres node's query field.** Never run SQL
  containing `{{` through an n8n node. The `{{ocr}}` placeholder in prompt SQL is
  built with `chr(123)||chr(123)||'ocr'||chr(125)||chr(125)` for exactly this
  reason — a literal `{{ocr}}` would be interpolated to the string `undefined`.
- **PostgreSQL rejects adjacent string literals on one line.** All prompt/repair
  SQL uses dollar-quoting (`$$…$$`). Preserve it.
- **The Code node has no `crypto`.** Binary must be read via
  `getBinaryDataBuffer`. Postgres/HTTP/Set nodes replace the item and drop binary,
  so binary handling order matters. These constraints are already encoded in the
  workflows — preserve them.

## Execution semantics — multi-parent nodes

**A node with multiple incoming parents executes once per incoming branch, not once
with the branches merged.** `$input.all()` returns only the items of the branch the
current run belongs to.

**Verified empirically on n8n 2.29.9** with an isolated probe (four Set branches —
one of them two nodes deep — fanning into a single Code node under
`executionOrder: "v1"`). The Code node executed **4 times**, `runIndex` 0–3, each run
reporting `itemCount: 1` and exactly one source. Every upstream node executed once. No
wave-grouping occurred: the deeper branch still produced its own separate run.

**The invariant that follows:** *a node with multiple parents may depend only on the
current branch's item.* Cross-branch aggregation requires an explicit aggregation
mechanism (a Merge node); it cannot be achieved by fanning several branches into one
Code node.

**The correct authoring pattern** is already the shipped one. WF-001's `Emit FAILED`
has six parents and reads **`$json` only** — each failure path normalizes its own
payload upstream (`failStage`, `error`) and the shared terminal node merely emits it.
Follow that shape: branch-local semantics in the shared node, normalization upstream.

**Why this matters beyond wrong answers.** A rule that infers something from the
*absence* of another branch's data is unsound by construction — it will fire on every
run that is not that branch's run. This produced WF-005's false "Orphan sweep did not
complete" alert on three of every four runs. Where the converging node performs a
**write** rather than an evaluation, the same semantics cause duplicate writes instead:
`WF-004`'s `SW-025 Google Sheets Writer` and `Assemble Proposal Package` are both fed by
two parallel parents today and will need this treatment before WF-004 is built.

Every other multi-parent node in the repository is safe, and for a second reason worth
knowing: they are **alternative-path convergences**, not parallel fan-ins — mutually
exclusive IF branches (`Emit FAILED`, `SW-020`), loop-backs (`poll() — wait`,
`more batches?`, `Regenerate (retry)`), or exclusive triggers (`SW-016 Initialize`).
Only one parent ever delivers, so no repeated run occurs regardless of input access.

`ci/validate_workflows.py` reports a **warning** when a multi-parent node's code calls
`$input.all()` — a warning rather than an error because loop-back and exclusive
convergences make legitimate use of it.

## Workflow binding (the #1 deployment failure)

Imports mint **new** workflow IDs, so a `mode:"list"` / cached-name binding can
silently resolve to a **stale** sub-workflow — the parent then receives its own
input instead of the child's output (manifesting as a false HUMAN_REVIEW).

- After importing, **re-bind every `executeWorkflow` node in WF-001** to the
  freshly-imported children.
- **Pin `SW-008 LLM Knowledge` by ID** (`workflowId.mode:"id"`, literal `value`).
- **Delete stale imported copies** and rename survivors with their version so the
  picker resolves exactly one record per name.
- Step-by-step in [`WORKFLOW_INVENTORY.md`](WORKFLOW_INVENTORY.md).

### Sub-workflows must be ACTIVE to be callable

On n8n 2.29.9 an `executeWorkflow` call against an **inactive** child fails outright:

```
Workflow is not active and cannot be executed.
```

Verified A/B with an isolated probe pair (same parent, same child, nothing else changed):
inactive → the above error; `n8n update:workflow --id=<id> --active=true` → succeeds.
Every CRIE sub-workflow was inactive on the live instance, which alone would have stopped
WF-001 end to end. Activation is therefore part of **deployment**, not an optional step,
and it applies to SW-005/007/008/013/014/029/030.

### Deploy by ID, never through the UI

`n8n import:workflow --input=<file>` **preserves the `id` in the file** and updates that
row in place, so redeploying is idempotent. An artifact with no `id` is rejected outright
(`SQLITE_CONSTRAINT: NOT NULL constraint failed: workflow_entity.id`), leaving UI import
as the only route — and UI import **mints a new id every time**. That is how the instance
accumulated 8 copies of WF-001. CI guards both conditions.

## Sub-workflow execution records under `saveDataSuccessExecution: none`

**Correction to the PR-3 commit message.** It claimed "zero execution records created
for the child". That is **not accurate** and should not be relied on. What is true — and
what the security requirement actually needs — is narrower:

> No signed URL and no node run-data are ever persisted. An execution **record** for the
> child may exist, transiently.

Measured on n8n 2.29.9 with an isolated twin pair (no Azure, no CRIE dependencies):

- n8n creates the child's `execution_entity` row when the sub-workflow starts.
- With `saveDataSuccessExecution: none` the run is **discarded rather than finalized**:
  `deletedAt` is stamped immediately (a soft delete) and `status` is therefore left at
  its last value — **`running`** — with `finished = 0` and `stoppedAt = NULL`.
- The row survives an n8n restart in that state. It is **not** a stuck or crashed
  execution and must not be "fixed" by force-failing or manually deleting it.
- The periodic hard-delete sweep removes it (`pruneData: true`,
  `pruneDataIntervals.hardDelete: 15` minutes). Observed: rows created at 23:50 and
  00:02 were both gone by 00:16.
- `runData` is **empty**, so nothing the child computed is stored. The row carries only
  the child's *input*. For SW-030 that is `{ storageKey, azureEndpoint, azureModel,
  signedUrlTtlSeconds, correlationId }` — no URL, no token, no storage host.

So an operator inspecting the database mid-window will see a `running` SW-030 execution
that never completes. That is expected. Verified on a real production run: the parent's
persisted payload contained zero occurrences of `token=`, `object/sign`, `supabase.co`,
`urlSource`, `signedURL`, `service_role` or `Bearer ey`.

## Sub-workflow I/O contract

- `executeWorkflowTrigger` must use **`inputSource:"passthrough"`** (lowercase
  't') to receive the caller payload including binary. The camelCase variant is
  silently ignored on import. Applied on SW-007, SW-008, SW-013, SW-014.
- WF-001's `SW-008 LLM Knowledge` node has **`options.waitForSubWorkflow: true`**
  set explicitly. This is serialized in the workflow JSON and travels with the
  import — it is part of the frozen contract, not a manual step. With it off,
  WF-001 continues before SW-008 returns and `knowledge.knowledgeUnits` is never
  received → false HUMAN_REVIEW. If a re-export shows `options: {}` on this node,
  re-apply it before freezing.

## Knowledge extraction (SW-008 v3.5.0)

- Extraction runs in **token-budgeted batches inside SW-008**; WF-001 calls it
  once and receives one merged `{ knowledgeUnits: [] }`.
- **Dual budget:** a batch closes on prompt-token OR expected-completion-token
  limit, so dense documents cannot overflow the output ceiling
  (`finish_reason:length`).
- The **planner** is pure/deterministic and stores batches as index **ranges**,
  not paragraph copies, to bound loop memory.
- **`extractionDensity` = 0.30** (calibrated from live batch data).
- **`build-request()`** materializes the batch into the prompt and **fails fast**
  if OCR content did not materialize (refuses to call the LLM).
- A **`Return to WF-001`** terminal node makes the loop-topology return
  deterministic.

## Repository writer (SW-014 v1.1.0)

- `uid()` emits a bare `DEFAULT` token for an absent PK (firing
  `uuid_generate_v4()`) — **never** `NULL` (a PK rejects it) and never `''`.
- `fk()` throws on an absent required foreign key.
- `q()` is unchanged for TEXT columns; the earlier `null → ''` coercion caused
  `invalid input syntax for type uuid: ""`.

## Document registration (SW-004 / WF-001)

- Registration uses `INSERT ... ON CONFLICT (sha256) DO UPDATE ... RETURNING id`,
  which always returns a row. The previous conditional-INSERT guard could emit
  `documentId = null` under three-valued logic (a scalar subquery over an empty
  set yields NULL, not false) while reporting success.
- A **documentId guard** node fails fast if a null ever appears.
- Duplicate suppression remains solely in SW-003.

## Memory / worker configuration

- n8n retains every loop iteration's run data for the whole execution, so SW-008's
  in-execution batch loop grows heap with document size.
- **Validated working config:** `NODE_OPTIONS=--max-old-space-size=6144`,
  `QUEUE_WORKER_CONCURRENCY=1` (concurrency 1 avoids per-worker heap contention
  during large-doc ingestion).
- The **per-batch sub-workflow refactor** (PLAN → Loop → EXTRACT-ONE → MERGE, OCR
  persisted to Postgres) is designed and deferred to post-v1.0; it removes the
  need for the raised heap.

### Object storage does not reduce peak memory — measure RSS, not cgroup usage

Do not cite object storage as a memory optimisation, and do not benchmark it with
`docker stats`.

**A first attempt at this measurement was wrong and its numbers (1591 vs 2192 MiB)
must not be reused.** It sampled `docker stats` MemUsage, which is the cgroup's usage
**including page cache** — and n8n runs `binaryMode: "separate"`, so it writes the
document to disk and the two arms dirty different amounts of cache. It also ran once per
arm with no container restart between them, so the V8 high-water mark carried across.

Corrected method: anonymous RSS summed across every container PID (Code nodes execute in
the **task runner**, a separate process, so the main n8n process alone is not the
figure), page cache recorded separately, container restarted before every run, arms
alternated, byte-identical fixtures, three runs per arm. All six runs produced identical
work: PROCESSED, 96 knowledge units, 96 chunks.

| arm | runs (MiB) | median | min | max | range |
|---|---|---|---|---|---|
| PR-4, storage-backed | 2263, 2296, 2305 | 2296 | 2263 | 2305 | 42 |
| pre-PR-4, binary path | 2363, 1844, 1938 | 1938 | 1844 | 2363 | **519** |

The arms **overlap**: the binary path's highest run (2363) exceeds every storage-backed
run. Its spread (519 MiB) is larger than the median gap (358 MiB), so no meaningful
regression is established either way. Page cache peaked at only 72–111 MiB.

Why no improvement is possible here: `binaryMode: "separate"` already keeps the original
**off the heap**, and n8n *streams* it — `HttpRequestV3` calls
`helpers.getBinaryStream(binaryData.id)` whenever the binary has an id, which is the case
in filesystem mode, for both the Supabase upload and the legacy Azure submit. The only
whole-file materialisations are `getBinaryDataBuffer` (needed for magic bytes and the
digest) and, previously, the hash's padded copy — about 24 MiB total, ~1% of a 2.3 GiB
peak and far inside run-to-run variance. Peak is dominated by OCR normalisation and
SW-008's batch loop, which are identical either side of the cutover.

The original acceptance criterion assumed removing `item.binary` from the main path would
reduce heap. That premise is incompatible with `binaryMode: "separate"`. The criterion was
amended by Architecture Owner ruling — see
[`PR4_ACCEPTANCE_RECORD.md`](PR4_ACCEPTANCE_RECORD.md). Object storage's justification
stands on durability, resumability, reference-passing and integrity, not heap use.

## Prompt registry

- `SW-008` loads the current PR-001 with `ORDER BY version DESC LIMIT 1` → v1.2.
- New prompt versions are inserted **additively**; older versions are retained for
  audit.
- **PR-001 v1.2** adds a mandatory LANGUAGE block: each KU statement stays in its
  source paragraph's language; `authoritySource` is exempt.

## Operational safeguards

- **Orphan-document sweep (built, post-v1.0):** a scheduled check that detects any
  document whose latest `processing_history` row is stuck `PENDING` beyond a
  configurable threshold with no terminal successor, and remediates it against
  worker crashes (OOM/restart) that skip WF-001's in-workflow failure paths.
  Delivered as migration `0029_orphan_sweep.sql` (detector view
  `monitoring.vw_orphaned_documents` + function
  `monitoring.sweep_orphaned_documents(stale_minutes, limit)`) and the standalone
  workflow `SW-016 Orphan Sweep`.
  - **Remediation is append-only** (the `processing_history` table forbids
    UPDATE/DELETE, so the row is *not* flipped). Per document it: sets
    `repository.documents.status='HUMAN_REVIEW'`, **appends a new** terminal
    `FAILED` `processing_history` row for the stuck stage, and inserts the
    `monitoring.alerts` row — exactly the pattern WF-001 uses on a handled
    failure. Idempotent: a remediated document leaves the detector immediately.
  - **Config-driven** ($vars, no hardcoded values): `CRIE_ORPHAN_SWEEP_CRON`,
    `CRIE_ORPHAN_SWEEP_STALE_MINUTES` (default 30), `CRIE_ORPHAN_SWEEP_BATCH_LIMIT`
    (default 100). The workflow carries a passthrough `executeWorkflowTrigger` so
    it can later be folded into WF-005 as a sub-workflow with no graph change.
  - **Single scheduler — do NOT run both.** SW-016's own Schedule Trigger is an
    *interim* cadence for while WF-005 is still a skeleton. The intended production
    architecture has **exactly one scheduler**: once WF-005 invokes SW-016 (via its
    `When Called by WF-005` passthrough trigger), **disable SW-016's Schedule
    Trigger** so WF-005 is the sole cadence. Running both is *safe but wrong* — the
    DB function is idempotent and guarded, so nothing is remediated twice, but you
    get redundant executions, duplicated heartbeat noise, and two competing
    definitions of cadence. Never leave both schedules active.
  - **`monitoring.sweep_orphaned_documents()` is a supported manual/operator entry
    point** (by design), not only the workflow's callee. A DBA can run it directly —
    `SELECT * FROM monitoring.sweep_orphaned_documents();` (defaults 30 min / limit
    100) or with overrides, e.g. `monitoring.sweep_orphaned_documents(5, 10)`. The
    function is the unit of work; SW-016 is one caller (scheduler now, WF-005
    sub-workflow later) and `psql` is a first-class other caller. A manual run is
    idempotent, guarded against concurrent double-remediation, returns the
    remediated set, and produces the identical audit trail as the scheduled path.
- **BI layer:** point Metabase/Power BI/Grafana at the `admin.*` views.

## CI guards

- **Shipped** — `validate_workflows.py` over the active workflow set (node-ref,
  trigger passthrough, prompt-ref, IF-schema, executeWorkflow binding, Set-node
  parameter/typeVersion). See [`ci/README.md`](../ci/README.md).
- **Shipped** — ephemeral-Postgres **migration replay**; catches forward-reference
  defects invisible to text tests.
- **Deferred** — `pgcheck.py` over all prompt/repair SQL (adjacent-literal + `{{` guard).
