# CRIE — Architecture Decisions

Records the **standing architectural decisions** behind CRIE and the reasoning
for them. This is the "why" companion to the stable
[`PROJECT_CONTEXT.md`](../PROJECT_CONTEXT.md). It does **not** re-list the
per-defect corrections made during bring-up — those are in
[`SRD_CHANGES_SINCE_SPEC.md`](SRD_CHANGES_SINCE_SPEC.md); it captures the durable
choices those corrections reaffirmed.

## AD-1 — Orchestration in n8n over a governed PostgreSQL system of record

Business logic lives in n8n workflows; correctness-critical invariants live in the
database. **Why:** the platform must produce defensible, auditable output, so the
guarantees (taxonomy, uniqueness, audit trail, access control) are enforced by
constraints/RLS/triggers that no workflow can bypass — not by convention in the
orchestration layer.

## AD-2 — §438 16-value category taxonomy is canonical (R-05)

The knowledge-category enum is fixed at the §438 16 values, enforced by
`chk_knowledge_units_category` and mirrored in `configuration.knowledge_categories`.
**Why:** compliance classification must be stable and comparable over time. When a
prompt or workflow enum drifts from the CHECK, the drift is corrected in the
prompt/enum — **the constraint is never widened to accommodate bad data.** A
taxonomy pre-flight (first node in WF-001) compares CHECK ↔ seed ↔ prompt and
aborts before OCR on any mismatch.

## AD-3 — Embeddings are `vector(1536)` (R-09)

Fixed embedding dimensionality in `repository.embeddings`. **Why:** retrieval and
storage assume one dimension; a change is a data-migration event, not a config
toggle.

## AD-4 — Additive-only, reproducible migration chain

The DDL chain `0001–0028` is append-only, idempotent, and free of forward
references (every view/function references only earlier-numbered objects).
**Why:** a tagged release must reproduce from an empty database deterministically,
and partial replays must be safe. Corrections ship as new migrations.

## AD-5 — Row-Level Security with a `service_role` writer (0014)

RLS is enabled on repository tables; the n8n Postgres credential connects as
`service_role`/owner. **Why:** enforce access control at the data layer while still
allowing the pipeline's INSERT/UPDATE paths. The `p_service_all` policy grants the
pipeline what it needs; `p_read_repository` covers read access.

## AD-6 — Append-only audit and processing history

`audit.*` triggers and `monitoring.processing_history` (with an append-only
trigger) record change history immutably. **Why:** compliance output must be
traceable; history cannot be silently rewritten.

## AD-7 — Single-responsibility sub-workflows with an explicit I/O contract

WF-001 orchestrates single-purpose sub-workflows called via `executeWorkflow`.
The parent waits for completion and receives a defined payload. **Why:** isolates
concerns (OCR, metadata, extraction, embeddings, persistence) and makes each unit
independently testable and replaceable. The contract details (passthrough trigger,
bind-by-ID, wait-for-completion) are operational and live in
[`IMPLEMENTATION_NOTES.md`](IMPLEMENTATION_NOTES.md).

## AD-8 — Batched knowledge extraction inside SW-008, unchanged downstream contract

Extraction runs in token-budgeted batches inside SW-008; WF-001 still calls it
once and receives one merged `{ knowledgeUnits: [] }`. **Why:** a single LLM call
truncated large documents. Batching preserves completeness without changing the
pipeline's shape. The batch loop's memory cost is a known trade-off mitigated by
runtime config, with a per-batch refactor deferred (see
[`PROJECT_STATUS.md`](../PROJECT_STATUS.md)).

## AD-9 — Single-transaction repository writer (SW-014)

All repository writes for a document commit in one transaction, with UUID handling
that emits `DEFAULT` for absent PKs (never `NULL` or `''`). **Why:** partial
persistence would leave the repository inconsistent; the transaction is
all-or-nothing.

## AD-10 — Deterministic compliance derivation and platform-computed confidence (R-16)

Confidence and compliance level are computed by the platform from a 9-source
authority model, not produced free-form by the model. **Why:** compliance results
must be reproducible and defensible rather than dependent on model phrasing.

## AD-11 — Output language is preserved (PR-001 v1.2)

Knowledge Unit statements remain in the source paragraph's language; only
`authoritySource` (product/section names) is exempt. **Why:** translating source
statements alters meaning and breaks traceability to evidence.

## AD-12 — Configuration is YAML-authored source of truth (R-08)

Platform configuration is authored in YAML and treated as canonical. **Why:** a
single reviewable source of truth for configuration, versionable alongside code.

---

### Related documents
- [`SRD_CHANGES_SINCE_SPEC.md`](SRD_CHANGES_SINCE_SPEC.md) — the concrete
  corrections that reaffirmed these decisions during bring-up.
- [`IMPLEMENTATION_NOTES.md`](IMPLEMENTATION_NOTES.md) — how these decisions show
  up as implementation details and gotchas.
