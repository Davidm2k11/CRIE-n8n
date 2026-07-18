-- ci/replay/verify.sql — post-replay invariant assertions.
--
-- Run with `psql -v ON_ERROR_STOP=1` against the throwaway replay database AFTER
-- the full migration chain has been applied. Every check RAISEs on failure, which
-- (under ON_ERROR_STOP) aborts psql with a non-zero exit and fails the CI job.
-- Read-only: inspects catalogs only, writes no data. Mirrors the "Verification
-- after replay" section of docs/MIGRATION_CHAIN.md.
\set ON_ERROR_STOP on

-- 1. The four critical objects exist.
DO $$
BEGIN
    IF to_regclass('repository.knowledge_units')        IS NULL THEN RAISE EXCEPTION 'missing repository.knowledge_units'; END IF;
    IF to_regclass('repository.embeddings')             IS NULL THEN RAISE EXCEPTION 'missing repository.embeddings'; END IF;
    IF to_regclass('configuration.prompt_versions')     IS NULL THEN RAISE EXCEPTION 'missing configuration.prompt_versions'; END IF;
    IF to_regclass('configuration.knowledge_categories') IS NULL THEN RAISE EXCEPTION 'missing configuration.knowledge_categories'; END IF;
    RAISE NOTICE 'OK: four critical objects present';
END $$;

-- 2. Embeddings are vector(1536) (R-09). pgvector stores the dimension in atttypmod.
DO $$
DECLARE dim integer;
BEGIN
    SELECT atttypmod INTO dim
      FROM pg_attribute
     WHERE attrelid = 'repository.embeddings'::regclass
       AND attname  = 'embedding';
    IF dim IS DISTINCT FROM 1536 THEN
        RAISE EXCEPTION 'repository.embeddings.embedding is not vector(1536) (atttypmod=%)', dim;
    END IF;
    RAISE NOTICE 'OK: embeddings.embedding is vector(1536)';
END $$;

-- 3. The §438 taxonomy CHECK holds exactly 16 values. Counted from the constraint
--    definition itself (migration-guaranteed, independent of any seed data): the
--    16 single-quoted category literals contribute 32 quote characters.
DO $$
DECLARE def text; nvals integer;
BEGIN
    SELECT pg_get_constraintdef(oid) INTO def
      FROM pg_constraint
     WHERE conname = 'chk_knowledge_units_category';
    IF def IS NULL THEN
        RAISE EXCEPTION 'missing constraint chk_knowledge_units_category';
    END IF;
    nvals := (length(def) - length(replace(def, '''', ''))) / 2;
    IF nvals <> 16 THEN
        RAISE EXCEPTION 'chk_knowledge_units_category holds % values, expected the §438 16', nvals;
    END IF;
    RAISE NOTICE 'OK: §438 taxonomy CHECK holds 16 values';
END $$;

-- 4. processing_history append-only trigger present (migration 0022).
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
         WHERE tgname = 'trg_processing_history_append_only'
           AND NOT tgisinternal
    ) THEN
        RAISE EXCEPTION 'missing append-only trigger on monitoring.processing_history';
    END IF;
    RAISE NOTICE 'OK: processing_history append-only trigger present';
END $$;

-- 5. Migration 0029 (orphan sweep) objects: detector view + sweep function signature.
DO $$
BEGIN
    IF to_regclass('monitoring.vw_orphaned_documents') IS NULL THEN
        RAISE EXCEPTION 'missing monitoring.vw_orphaned_documents (migration 0029)';
    END IF;
    IF NOT EXISTS (
        SELECT 1
          FROM pg_proc p
          JOIN pg_namespace n ON n.oid = p.pronamespace
         WHERE n.nspname = 'monitoring'
           AND p.proname = 'sweep_orphaned_documents'
           AND pg_get_function_identity_arguments(p.oid) = 'integer, integer'
    ) THEN
        RAISE EXCEPTION 'missing monitoring.sweep_orphaned_documents(integer, integer) (migration 0029)';
    END IF;
    RAISE NOTICE 'OK: migration 0029 orphan-sweep objects present';
END $$;

\echo '=================================================='
\echo 'verify.sql: ALL POST-REPLAY ASSERTIONS PASSED'
\echo '=================================================='
