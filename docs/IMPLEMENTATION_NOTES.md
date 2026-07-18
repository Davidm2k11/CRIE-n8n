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

## Recommended CI guards (deferred)

- Ephemeral-Postgres **migration replay** — catches forward-reference defects
  invisible to text tests.
- `pgcheck.py` over all prompt/repair SQL (adjacent-literal + `{{` guard).
- `validate_workflows.py` over workflow JSON (node-ref, trigger passthrough,
  prompt-ref, IF-schema, 3VL-INSERT, taxonomy-enum checks).
