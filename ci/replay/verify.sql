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
    -- Resolve by INPUT signature via to_regprocedure (robust): it uses PostgreSQL's
    -- own function-resolution over the input argument types and is immune to the exact
    -- text rendering of pg_get_function_identity_arguments (which varies for functions
    -- carrying OUT/TABLE columns). OUT/TABLE columns are not part of a function's
    -- identity signature, so only the two integer inputs are named here.
    IF to_regprocedure('monitoring.sweep_orphaned_documents(integer, integer)') IS NULL THEN
        RAISE EXCEPTION 'missing monitoring.sweep_orphaned_documents(integer, integer) (migration 0029)';
    END IF;
    RAISE NOTICE 'OK: migration 0029 orphan-sweep objects present';
END $$;

-- 6. Migration 0030 (document storage): five NULLABLE columns + lookup index,
--    and no data written. document_blobs is DEFERRED (decision D3) and is
--    therefore deliberately NOT asserted here.
DO $$
DECLARE
    v_missing TEXT;
    v_notnull TEXT;
    v_rows    BIGINT;
BEGIN
    SELECT string_agg(c.col, ', ')
      INTO v_missing
      FROM (VALUES ('storage_key'), ('storage_bucket'), ('byte_size'),
                   ('content_type'), ('stored_at')) AS c(col)
     WHERE NOT EXISTS (
             SELECT 1 FROM information_schema.columns
              WHERE table_schema = 'repository'
                AND table_name   = 'documents'
                AND column_name  = c.col);
    IF v_missing IS NOT NULL THEN
        RAISE EXCEPTION 'missing repository.documents storage columns (migration 0030): %', v_missing;
    END IF;

    -- All five MUST be nullable: the migration has to be safe on existing rows.
    SELECT string_agg(column_name, ', ')
      INTO v_notnull
      FROM information_schema.columns
     WHERE table_schema = 'repository'
       AND table_name   = 'documents'
       AND column_name IN ('storage_key', 'storage_bucket', 'byte_size',
                           'content_type', 'stored_at')
       AND is_nullable <> 'YES';
    IF v_notnull IS NOT NULL THEN
        RAISE EXCEPTION 'migration 0030 storage columns must be NULLABLE: %', v_notnull;
    END IF;

    IF to_regclass('repository.idx_documents_storage_key') IS NULL THEN
        RAISE EXCEPTION 'missing idx_documents_storage_key (migration 0030)';
    END IF;

    -- The migration is schema-only; it must not populate anything.
    SELECT count(*) INTO v_rows
      FROM repository.documents WHERE storage_key IS NOT NULL;
    IF v_rows <> 0 THEN
        RAISE EXCEPTION 'migration 0030 must write no data, found % row(s) with storage_key', v_rows;
    END IF;

    RAISE NOTICE 'OK: migration 0030 storage columns present, nullable, indexed, no data written';
END $$;

\echo '=================================================='
\echo 'verify.sql: ALL POST-REPLAY ASSERTIONS PASSED'
\echo '=================================================='
