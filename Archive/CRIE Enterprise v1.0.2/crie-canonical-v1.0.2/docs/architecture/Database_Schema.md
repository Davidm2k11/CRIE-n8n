# Database Schema

CRIE runs on Supabase PostgreSQL + pgvector. The schema is created by ordered
migrations `0001`–`0023` (§217, §239.1). Naming follows §237: tables/columns
`snake_case`, PK `id`, FK `entity_id`, indexes `idx_table_column`, constraints
`fk_table_reference`.

## Schemas (§219)

| Schema | Purpose |
|--------|---------|
| `repository` | Governed knowledge (authoritative store) |
| `configuration` | Runtime cache of config + reference data (R-08) |
| `monitoring` | Logs, telemetry, health, benchmarks, processing history |
| `audit` | Append-only, immutable audit trail |
| `retrieval` | Reserved for retrieval-side objects |

`public` stays minimal; business tables never live in `public` (§219).

## `repository` tables

- **documents** (`0003`) — PK `id`; unique `sha256` (immutable fingerprint);
  indexes on status, authority, uploaded_at. No FKs.
- **metadata** (`0004`) — FK → documents; indexes on document_id, key, value.
- **knowledge_units** (`0005` + additive `0018`) — FK → documents. Core columns
  plus additive classification/lifecycle/lineage columns (`domain`, `capability`,
  `module`, `feature`, `authority_source`, `authority_score`, `quality_score`,
  `lifecycle_state` default `Draft`, `previous_version` self-FK, `created_by`,
  `change_reason`). `category` is CHECK-constrained to the §438 16-value enum
  (R-05); `lifecycle_state` to the §518 states.
- **evidence** (`0006`) — FK → knowledge_units; indexes on knowledge_unit_id,
  authority.
- **citations** (`0007`) — FK → **both** evidence and documents (R-06); indexes
  on document_id, page, section.
- **retrieval_chunks** (`0008`) — FK → knowledge_units; owned by Repository
  (R-13); indexes on knowledge_unit_id, chunk_order; trigram index on content
  (`0013`) for keyword retrieval.
- **embeddings** (`0009`) — FK → retrieval_chunks; `embedding vector(1536)` fixed
  for v1 (R-09); vector index config-driven (`0013`, §227).
- **knowledge_relationships** (`0019`) — directional KU→KU relationships
  (§441 types); no self-reference; index (source_ku_id, relationship_type).
- **knowledge_tags** (`0020`) — per-KU semantic tags (§443); index on tag.

## `configuration` tables (runtime cache, R-08)

- **configuration** — flattened dotted-key/value (JSONB) of every domain YAML.
- **providers** — per-kind provider settings (ocr/llm/embedding/storage).
- **prompt_registry** / **prompt_versions** (`0010`/`0011`) — PR-001…PR-008
  manifest and versioned bodies (bodies cached at seed time when present).
- **workflow_registry** — WF/SW/UT inventory with status and owning sprint.
- **authority_sources** (`0010`) — 9-source model, scores config-driven (R-16).
- **knowledge_categories** (`0010`) — the 16 frozen categories (R-05).
- **synonyms** / **acronyms** (`0021`) — dictionaries seeded from config (§444–445).

All values are populated from the authored YAML by `seed_configuration.py`; never
authored directly in the tables (§627).

## `monitoring` tables (§229)

`workflow_logs`, `ai_requests`, `execution_statistics`, `health_checks`,
`benchmark_results`, and append-only `processing_history` (`0022`, backs
checkpoints per R-18). Monitoring data is never mixed with repository data (§229).

## `audit` tables (§230, §344 columns via `0023`)

`repository_changes`, `workflow_changes`, `configuration_changes`,
`prompt_changes` — columns `event_id`, `event_type`, `user`, `timestamp`,
`object_type`, `object_id`, `changes` (JSONB). Append-only/immutable: UPDATE/DELETE
blocked by trigger and revoked grants; records are never deleted (§230).

## Referential integrity (§233)

`documents → knowledge_units → evidence → citations`;
`knowledge_units → retrieval_chunks → embeddings`. Orphan records prohibited
(FK `ON DELETE CASCADE`).

## Functions (§231) and views (§232)

Lightweight functions: `create_document`, `archive_document`, `rebuild_embeddings`,
`repository_statistics`, `repository_health`, `search_metadata`,
`repository_version` — business logic stays in n8n. Read-only dashboard views:
`vw_repository_summary`, `vw_document_statistics`, `vw_knowledge_statistics`,
`vw_embedding_statistics`, `vw_repository_health`.

## Security (§235)

RLS enabled on all `repository` tables; workflow execution uses the Service Role;
`authenticated` gets read policies as a baseline for future user access.
