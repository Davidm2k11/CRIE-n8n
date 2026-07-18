# CRIE v1.0 — Deployment Guide (clean environment)

End-to-end bring-up of CRIE v1.0 on a fresh host. Assumes a Hostinger-class VPS
(≥ 8 GB RAM), Docker, a Supabase/PostgreSQL 16 instance with `pgvector`, and
OpenAI + Azure Document Intelligence credentials.

## 0. Prerequisites

- PostgreSQL 16 with extensions `uuid-ossp` and `vector` installable.
- A Postgres role for n8n that is **`service_role` or the table owner** (required
  for the RLS policy in migration 0014 and for the repository UPDATE paths).
- n8n **2.29.9**, Queue Mode, filesystem binary storage.
- OpenAI API key (GPT-4o); Azure Document Intelligence endpoint + key.

## 1. Database

Apply the migration chain in order (see `docs/MIGRATION_CHAIN.md`):

```bash
for f in migrations/00*.sql; do
  echo "applying $f"
  psql "$SUPABASE_CONN" -v ON_ERROR_STOP=1 -f "$f"
done
```

Then the prompt data:

```bash
# 1. seed PR-001..PR-008 base rows (your provisioning), then:
psql "$SUPABASE_CONN" -v ON_ERROR_STOP=1 -f prompts/PR-001_v1.2_language_preservation.sql
```

Verify (from `MIGRATION_CHAIN.md`): the four critical objects exist, the category
enum is the §438 16, embeddings are `vector(1536)`, and PR-001 loads at v1.2.

## 2. n8n environment

```yaml
# docker-compose.yml (worker service) — PRODUCTION values
environment:
  - EXECUTIONS_MODE=queue
  - QUEUE_BULL_REDIS_HOST=redis
  - N8N_DEFAULT_BINARY_DATA_MODE=filesystem
  # Heap: SW-008 runs the batch loop in one execution. Until the per-batch
  # sub-workflow refactor lands (post-v1.0), keep a working headroom:
  - NODE_OPTIONS=--max-old-space-size=6144
  # Concurrency 1 avoids per-worker heap contention during large-doc ingestion:
  - QUEUE_WORKER_CONCURRENCY=1
```

> The 6144/concurrency-1 settings are the validated working configuration for
> large documents in v1.0. The per-batch memory refactor (design already written)
> is deferred to post-v1.0 and will remove the need for the raised heap.

## 3. Credentials (in n8n)

- **Postgres**: connect as `service_role`/owner (see prerequisites).
- **OpenAI**: API key credential; used by SW-008 and SW-013.
- **Azure Document Intelligence**: header-auth credential; bound on SW-005.

## 4. Import workflows

Import every JSON in `workflows/`. Then follow `docs/WORKFLOW_INVENTORY.md`:

1. **Re-bind every Execute Workflow node** in WF-001 to the freshly-imported
   sub-workflows (imports mint new IDs). Pin `SW-008 LLM Knowledge` by **ID**.
2. **Re-bind the Azure credential** on SW-005.
3. **Delete stale imported copies** so bindings cannot drift.

## 5. Smoke test

1. Ingest a small English PDF. Expect: document `PROCESSED`, knowledge units
   written, `LLM ok?` passing (no false HUMAN_REVIEW).
2. Ingest a small Arabic PDF. Expect: KU **statements remain Arabic** (PR-001
   v1.2 language preservation).
3. Confirm the repository transaction commits (SW-014) with no
   `invalid input syntax for type uuid` error.

## 6. Operational safeguards to enable

- **Orphan-document sweep** (deferred build): a scheduled check that flips any
  `processing_history` row stuck `PENDING` beyond N minutes with no `COMPLETED`
  successor to `HUMAN_REVIEW`. Protects against worker crashes (OOM, restart)
  that skip the in-workflow failure paths. Ship early in operations.
- **BI layer**: point Metabase/Power BI/Grafana at the `admin.*` views.

## 7. Known-good runtime facts (do not "fix" these)

- n8n Postgres nodes interpolate `{{ }}` in the query field. **Never** run SQL
  containing `{{` through an n8n node — the `chr()` construction in the prompt
  SQL exists for this reason.
- The Code node has no `crypto`; binary must be read via
  `getBinaryDataBuffer`; Postgres/HTTP/Set nodes replace the item and drop binary.
  These are encoded in the current workflows; preserve them.
