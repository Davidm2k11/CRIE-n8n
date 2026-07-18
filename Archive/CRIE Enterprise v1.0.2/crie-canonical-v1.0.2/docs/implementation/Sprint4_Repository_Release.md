# CRIE v0.5.0 — Sprint 4: Repository

**Tag:** `v0.5.0` · **Depends on:** `v0.4.0` (Sprint 3 — Knowledge Ingestion)

## Added
- **Repository Writer hardening** (§148, §234) — single-transaction writer with
  §524/§525/§427 integrity + governance gates; rollback on any failure; partial
  writes prohibited.
- **Certification framework** — per-Knowledge-Unit certification (§512) and
  per-Document certification (§428/§527), emitting the §527 certification object.
- **Knowledge Quality Score** (§511) — deterministic 0.00–1.00, configurable
  weights.
- **Versioning + lineage** (§519/§522) — `previous_version`, `created_by`,
  `change_reason`, lifecycle states (§518); superseded units deprecated, never
  deleted.
- **Repository API** (§365/§56) — CreateDocument, UpdateDocument, ArchiveDocument,
  GetKnowledgeUnit (certified-only), SearchMetadata, SearchKnowledge
  (certified-only), RebuildEmbeddings (reserved triggers, §523), Statistics,
  Health. Canonical `{status,data|error}` contracts.
- **Repository Health score** (§528) — weighted 0–100 with Healthy/Degraded/
  Critical bands.
- **Repository Statistics** (§529) — all required fields, auto-recomputed.
- **Ownership enforcement** (R-13/§425) — chunks/embeddings owned by Repository;
  Compliance Result / Context Package / prompts refused.
- Acceptance + unit test suite (21 tests, all passing), example input/output,
  module documentation.

## Honors
R-05 (16-value category enum), R-06 (citation keys on evidence_id + document_id),
R-09 (vector(1536) enforced on rebuild), R-13 (chunk/embedding ownership);
Principle 1 (repository authoritative), Principle 7 (no hardcoded config),
§608 (Repository never bypassed).

## Exit gate
Production repository operational; certification passes; APIs, health, and
statistics available; Repository never bypassed. **Met.**

## Notes
- Live Supabase application deferred to the infrastructure integration stage
  (accepted no-live-datastore-in-build risk); logic is exercised end-to-end
  against in-memory doubles.
- No Sprint 5+ functionality and no placeholder implementations included
  (strict sprint isolation).
