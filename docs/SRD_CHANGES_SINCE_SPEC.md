# CRIE v1.0 — Changes Since the Original Specification (SRD Delta)

Records every architectural decision and defect-correction made during bring-up,
relative to CRIE Enterprise Specification v1.1.1. **Nothing here redesigns the
architecture** — these are the changes required to make the frozen design run
correctly in production. Each is scoped and reversible in principle.

## A. Knowledge extraction — batching (SW-008)

The v1.1.1 single-call extraction truncated large documents (the prompt was
capped and silently dropped ~⅔ of a big SRS). v1.0 extracts in **token-budgeted
batches inside SW-008**; WF-001 still calls SW-008 once and receives one merged
`{ knowledgeUnits: [] }`. Downstream contract unchanged.

- **Dual budget**: a batch closes on prompt-token OR expected-completion-token
  limit, so dense documents cannot overflow the model's output ceiling
  (`finish_reason:length`).
- **Planner** is pure/deterministic and stores batches as index **ranges**, not
  paragraph copies, to bound loop memory.
- **`extractionDensity` = 0.30** (calibrated from live batch data; was 0.12).
- **`build-request()` materialization + fail-fast**: renders the batch into the
  prompt robustly and refuses to call the LLM if OCR content did not materialize.
- **`Return to WF-001`** explicit terminal node (loop-topology return determinism).

## B. Memory posture (operational, not architectural)

n8n retains every loop iteration's run data for the whole execution, so SW-008's
in-execution batch loop grows heap with document size. v1.0 ships with
`--max-old-space-size=6144` and `QUEUE_WORKER_CONCURRENCY=1` as the validated
working configuration. The **per-batch sub-workflow refactor** (PLAN → Loop →
EXTRACT-ONE → MERGE, with OCR persisted to Postgres) is fully designed and
**deferred to post-v1.0**.

## C. Document registration (SW-004 / WF-001)

The conditional-INSERT guard could emit `documentId = null` under three-valued
logic (a scalar subquery over an empty set yields NULL, not false), while the
node reported success. Replaced with `INSERT ... ON CONFLICT (sha256) DO UPDATE
... RETURNING id`, which always returns a row. Duplicate suppression remains
solely in SW-003. A **documentId guard** node fails fast if a null ever appears.

## D. Category taxonomy (PR-001 / SW-011)

PR-001 and the in-workflow `CATEGORY_ENUM` carried the **superseded §415/§504**
taxonomy (Capability, BusinessRule, DataModel, …) instead of the canonical **§438
16-value enum (R-05)** the DB CHECK enforces. Corrected the **prompt and the enum**
— the CHECK constraint was left canonical and untouched. Added a **taxonomy
pre-flight** (first node in WF-001) that compares CHECK ↔ seed table ↔ PR-001 body
and aborts before OCR on any drift.

## E. Prompt registry integrity (PR-001)

Two production hazards were found and made permanent policy:
- n8n interpolates `{{ }}` in a Postgres node's query field, so running the
  prompt INSERT through n8n destroyed `{{ocr}}` → the literal `undefined`. All
  prompt SQL now builds the placeholder with `chr(123)||chr(123)||'ocr'||...`.
- PostgreSQL rejects **adjacent string literals** on one line; all prompt SQL uses
  **dollar-quoting**.

## F. Repository writer (SW-014)

The SQL generator's `q()` coerced `null → ''` and quoted it, producing `id=''`
for absent UUIDs → `invalid input syntax for type uuid: ""`. Added `uid()`
(absent PK → bare `DEFAULT` token, firing `uuid_generate_v4()`; **not** `NULL`,
which a PK rejects) and `fk()` (throws on an absent required foreign key). `q()`
unchanged for TEXT columns.

## G. Sub-workflow I/O contract (multiple SWs)

`executeWorkflowTrigger` must use `inputSource:"passthrough"` (lowercase 't') to
receive the caller payload including binary; the camelCase variant is silently
ignored on import. Fixed on SW-007, SW-008, SW-013, SW-014. The parent
`executeWorkflow` binding must be **pinned by ID** — an unpinned `list` binding
drifts to stale re-imported records.

## H. Language preservation (PR-001 v1.2)

The model translated Arabic Knowledge Units to English because the prompt never
pinned output language. **PR-001 v1.2** adds a mandatory LANGUAGE block: each
statement stays in the source paragraph's language; never translate/normalise;
`authoritySource` (product/section names) is exempt. Taxonomy, schema, and output
shape unchanged.

## Unchanged / reaffirmed invariants

- **§438 16-value category enum** (R-05) — canonical, frozen.
- **`vector(1536)` embeddings** (R-09).
- **Single Compliance Result contract**; **8-prompt catalogue** frozen.
- **Additive-only migrations** (0001–0028 frozen; corrections as new migrations).
- **YAML-authored config as source of truth** (R-08).
- **9-source authority model** (R-16); platform-computed confidence; deterministic
  compliance-level derivation.

## Deferred to post-v1.0 (explicitly out of the freeze)

- Per-batch sub-workflow memory refactor (design complete).
- Orphan-document sweep (recommended to ship early in operations).
- Adaptive extraction density.
- CI ephemeral-Postgres migration replay test.
- §406 operational sign-offs (UAT, backup/restore drills, live monitoring,
  queue/circuit-breaker exercise).
- WF-002 Retrieval (next feature workstream).
