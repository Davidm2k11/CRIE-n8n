-- ci/replay/bootstrap.sql — replay prerequisite (NOT a migration).
--
-- The migration chain assumes the Supabase-provided roles exist: migration 0014
-- creates RLS policies `TO service_role` and `TO authenticated`, which fail on a
-- bare PostgreSQL where those roles are absent. Supabase ships them; a throwaway
-- CI / local replay database does not — so we create them here, ONCE, BEFORE the
-- chain is applied.
--
-- This file is applied only to the disposable replay database. It is never part of
-- migrations/ and never applied to a real environment (Supabase already has these
-- roles). Idempotent: safe to re-run.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
        CREATE ROLE service_role NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        CREATE ROLE authenticated NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        CREATE ROLE anon NOLOGIN;
    END IF;
END $$;
