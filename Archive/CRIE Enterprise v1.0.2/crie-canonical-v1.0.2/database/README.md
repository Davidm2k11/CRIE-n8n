# Database

Supabase (PostgreSQL + pgvector) schema for CRIE, implemented as ordered
migrations `0001`–`0023` (§217, §239.1). Naming per §237.

## Layout

| Folder | Contents |
|--------|----------|
| `migrations/` | Forward migrations `0001`–`0023` (execute in order; stop on first failure, §217). |
| `rollback/` | One `<name>_rollback.sql` per migration (§239). |
| `seeds/` | Authored seed data (categories, dictionaries) loaded by the seed step (R-08). |
| `functions/` | (Reserved) additional SQL functions; core functions are in `0015`. |
| `views/` | (Reserved) additional views; core views are in `0016`. |
| `policies/` | (Reserved) additional RLS policies; core RLS is in `0014`. |
| `indexes/` | (Reserved) additional indexes; core + vector indexes are in `0013`. |
| `diagrams/` | `er_diagram.md` (§233). |

## Key facts

- Additive migrations `0018`–`0023` are purely additive (R-15); `0018` only ADDs
  columns to `knowledge_units`.
- `embeddings.embedding` is `vector(1536)` (R-09); vector index is config-driven (§227).
- `citations` key on `evidence_id` + `document_id` (R-06).
- `category` CHECK-constrained to the §438 16-value enum (R-05).
- Configuration enters the DB only via `scripts/setup/seed_configuration.py`
  from the authored YAML (R-08); nothing is authored directly in the tables.

See `docs/architecture/Database_Schema.md` and
`docs/deployment/Migration_Execution_Guide.md`.
