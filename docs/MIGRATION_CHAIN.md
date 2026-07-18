# CRIE v1.0 — Definitive Migration Chain

Reproduces the CRIE database from an empty PostgreSQL 16 (Supabase) instance.
Apply **in numeric order, 0001 → 0028**, then the two post-migration data steps.
All migrations are additive and idempotent (`CREATE ... IF NOT EXISTS`, guarded
`INSERT`s), so a partial replay is safe to re-run.

## Order

| # | File | Establishes |
|---|------|-------------|
| 0001 | extensions | `uuid-ossp`, `vector` (pgvector) |
| 0002 | schemas | `repository`, `configuration`, `monitoring`, `audit`, `admin` |
| 0003 | documents | `repository.documents` (+ `uq_documents_sha256`) |
| 0004 | metadata | `repository.metadata` |
| 0005 | knowledge_units | `repository.knowledge_units` |
| 0006 | evidence | `repository.evidence` |
| 0007 | citations | `repository.citations` |
| 0008 | retrieval_chunks | `repository.retrieval_chunks` |
| 0009 | embeddings | `repository.embeddings` (`vector(1536)`, R-09) |
| 0010 | configuration | `configuration.*` base (providers, prompts base) |
| 0011 | prompt_registry | `configuration.prompt_versions` (PR-001..PR-008) |
| 0012 | monitoring | `monitoring.*` base |
| 0013 | indexes | performance indexes |
| 0014 | rls | Row-Level Security + `p_service_all` / `p_read_repository` |
| 0015 | functions | stored functions |
| 0016 | views | base views |
| 0017 | seed_data | reference seeds |
| 0018 | knowledge_classification | **`chk_knowledge_units_category`** (§438, 16 values, R-05) + `configuration.knowledge_categories` |
| 0019 | knowledge_relationships | KU relationship model |
| 0020 | semantic_tags | semantic tagging |
| 0021 | dictionaries | controlled dictionaries |
| 0022 | processing_history | `monitoring.processing_history` (+ append-only trigger) |
| 0023 | audit_columns | audit columns + `audit.*` append-only triggers |
| 0024 | admin_dashboard_views | `admin.*` dashboards |
| 0025 | admin_registry_audit_views | registry/audit dashboards (§570, R-17) |
| 0026 | health_alert_center | health/alert views |
| 0027 | benchmark_persistence | benchmark tables |
| 0028 | benchmark_views | benchmark views |

## Post-migration data steps (order matters)

These load the operational prompt rows the ingestion pipeline reads. They live
outside the numbered DDL chain because they are **data**, not schema, and are
versioned independently in `configuration.prompt_versions`.

1. **Seed the prompt catalogue** (PR-001..PR-008 base rows), if not already seeded
   by your environment's provisioning.
2. **Apply `prompts/PR-001_v1.2_language_preservation.sql`** — the current
   production PR-001 (v1.2). It inserts v1.2 additively; v1.0/v1.1 are retained
   for audit. SW-008 loads `ORDER BY version DESC LIMIT 1` → v1.2.

## Verification after replay

```sql
-- 28 tables/objects across the four schemas exist; spot-check the critical ones:
SELECT to_regclass('repository.knowledge_units')  IS NOT NULL AS ku,
       to_regclass('repository.embeddings')       IS NOT NULL AS emb,
       to_regclass('configuration.prompt_versions') IS NOT NULL AS prompts,
       to_regclass('configuration.knowledge_categories') IS NOT NULL AS cats;

-- category enum is the §438 16 and matches the CHECK (run the taxonomy preflight):
--   docs/taxonomy_preflight.sql  -> taxonomyOk = true

-- embeddings dimension is 1536 (R-09):
SELECT atttypmod FROM pg_attribute
WHERE attrelid='repository.embeddings'::regclass AND attname='embedding';

-- PR-001 that SW-008 will load is v1.2, has the placeholder and the language rule:
--   prompts/PR-001_v1.2_language_preservation.sql  (verification SELECT at its end)
```

## Notes on defect-corrections folded into this chain

- **Category taxonomy** is enforced by 0018's `chk_knowledge_units_category` (§438).
  The prompt/enum drift that surfaced during bring-up was corrected in the PROMPT
  (PR-001 v1.1+) and the workflow enum — **not** by relaxing this constraint. The
  constraint is canonical; do not widen it without a new reconciliation decision.
- **RLS** (0014): the n8n Postgres credential must connect as `service_role` (or the
  table owner). The `p_service_all` policy grants `ALL` to `service_role`; the
  existing pipeline's UPDATEs prove the privilege is present.
- **No forward references**: every view/function references only objects created in
  an earlier-numbered migration. A CI ephemeral-Postgres replay (see release
  checklist) guards this property.
