-- =============================================================================
-- CRIE Supabase / PostgreSQL bootstrap  (Sprint 10, S10-4 · §630 supabase/)
-- -----------------------------------------------------------------------------
-- Runs once on first container start (docker-entrypoint-initdb.d). Creates the
-- separate n8n metadata database so n8n's own tables never mingle with the CRIE
-- schema. The CRIE schema itself is applied afterwards by the ordered migrations
-- (deployment/scripts/apply_migrations.sh), NOT here — migrations remain the
-- single source of schema truth (§217/§239).
--
-- Idempotent: safe to re-run (guards with IF NOT EXISTS semantics via DO block).
-- =============================================================================

-- pgvector is provided by the pgvector/pgvector image, but the CRIE migration
-- 0001_extensions.sql is what actually enables it inside the crie database.
-- Nothing schema-related happens here.

DO
$$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_database WHERE datname = 'n8n') THEN
      -- CREATE DATABASE cannot run inside a transaction/DO block directly;
      -- use dblink-free approach: this file is split so the CREATE runs at top
      -- level below. The guard here only emits a notice.
      RAISE NOTICE 'n8n database will be created';
   END IF;
END
$$;

-- Top-level, outside any transaction block:
SELECT 'CREATE DATABASE n8n'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'n8n')\gexec
