# Migration Execution Guide

Ordered PostgreSQL migrations for the CRIE Supabase database (§217, §239).
Migrations execute **in order** and stop immediately on first failure (§217).

## Prerequisites

- Supabase project (PostgreSQL 15+) with the `vector` (pgvector) extension
  available.
- `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` set (see `.env.example`).
- `psql` or the Supabase SQL editor / CLI.

## Forward migration

Run every file in `database/migrations/` in ascending numeric order:

```bash
for f in database/migrations/0*.sql; do
  echo "applying $f"
  psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f "$f" || { echo "STOP: $f failed"; break; }
done
```

`-v ON_ERROR_STOP=1` enforces the §217 "stop on first failure" rule.

Order (§217): `0001_extensions` → `0002_schemas` → `0003_documents` →
`0004_metadata` → `0005_knowledge_units` → `0006_evidence` → `0007_citations` →
`0008_retrieval_chunks` → `0009_embeddings` → `0010_configuration` →
`0011_prompt_registry` → `0012_monitoring` → `0013_indexes` → `0014_rls` →
`0015_functions` → `0016_views` → `0017_seed_data` → `0018_knowledge_classification`
→ `0019_knowledge_relationships` → `0020_semantic_tags` → `0021_dictionaries` →
`0022_processing_history` → `0023_audit_columns`.

## Seed / sync configuration (R-08)

After `0017` (and after `0010`, `0021` exist), populate the runtime cache from the
authored YAML — this is the **only** way configuration enters the database; values
are never authored directly in the tables (§627):

```bash
# Emit SQL and review:
python3 scripts/setup/seed_configuration.py > /tmp/seed.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f /tmp/seed.sql
# …or apply directly when a driver is installed:
python3 scripts/setup/seed_configuration.py --apply   # uses $DATABASE_URL
```

Re-running the seed re-syncs configuration after any YAML edit — no source code or
SQL changes are needed to adjust behavior.

## Vector index (config-driven, §227)

The vector index type/params come from `embedding.vectorIndex` in
`configuration/providers.yaml` ("Configuration determines implementation", §227).
`0013` creates the HNSW default; to switch to IVFFlat or change params, edit the
YAML and apply the generated DDL:

```bash
python3 scripts/setup/apply_vector_index.py            # review DDL
python3 scripts/setup/apply_vector_index.py --apply    # apply
```

## Rollback

Each migration has a matching rollback in `database/rollback/`
(`<name>_rollback.sql`). To undo, run rollbacks in **reverse** order:

```bash
for f in $(ls -r database/rollback/0*_rollback.sql); do
  psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f "$f"
done
```

Notes:
- `0001_extensions_rollback.sql` leaves extensions installed by default (other
  databases may depend on them); uncomment lines to remove in an isolated DB.
- Audit tables (`0023`) and `monitoring.processing_history` (`0022`) are
  append-only in normal operation; rollback drops the tables entirely.

## Verify

```bash
python3 tests/integration/test_database.py        # static acceptance (§238)
bash   tests/integration/test_sprint2_database.sh # full Sprint 2 acceptance
```

Live post-migration verification (§238) against Supabase: confirm all tables
exist, foreign keys enforced, the vector index is operational, RLS enabled,
functions executable, views operational, and seed data loaded.
