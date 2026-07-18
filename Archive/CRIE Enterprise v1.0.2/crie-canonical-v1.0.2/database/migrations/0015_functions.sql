-- 0015_functions.sql — Lightweight repository functions (§231).
-- Business logic stays in n8n; DB functions remain lightweight (§231).

CREATE OR REPLACE FUNCTION repository.repository_statistics()
RETURNS TABLE (documents BIGINT, knowledge_units BIGINT, evidence BIGINT,
               chunks BIGINT, embeddings BIGINT)
LANGUAGE sql STABLE AS $$
    SELECT (SELECT count(*) FROM repository.documents),
           (SELECT count(*) FROM repository.knowledge_units),
           (SELECT count(*) FROM repository.evidence),
           (SELECT count(*) FROM repository.retrieval_chunks),
           (SELECT count(*) FROM repository.embeddings);
$$;

CREATE OR REPLACE FUNCTION repository.repository_version()
RETURNS INTEGER LANGUAGE sql STABLE AS $$
    SELECT (value#>>'{}')::INTEGER
    FROM configuration.configuration
    WHERE domain = 'repository' AND key = 'repository.repositoryVersion'
    LIMIT 1;
$$;

CREATE OR REPLACE FUNCTION repository.repository_health()
RETURNS TABLE (component TEXT, state TEXT, checked_at TIMESTAMPTZ)
LANGUAGE sql STABLE AS $$
    SELECT DISTINCT ON (component) component, state, checked_at
    FROM monitoring.health_checks
    ORDER BY component, checked_at DESC;
$$;

CREATE OR REPLACE FUNCTION repository.search_metadata(p_key TEXT, p_value TEXT)
RETURNS SETOF repository.metadata LANGUAGE sql STABLE AS $$
    SELECT * FROM repository.metadata
    WHERE key = p_key AND (p_value IS NULL OR value = p_value);
$$;

CREATE OR REPLACE FUNCTION repository.archive_document(p_document_id UUID)
RETURNS VOID LANGUAGE sql AS $$
    UPDATE repository.documents SET status = 'Archived' WHERE id = p_document_id;
$$;

-- create_document() and rebuild_embeddings() are declared here as lightweight
-- helpers; the orchestration that uses them lives in n8n (§231, Sprints 3-4).
CREATE OR REPLACE FUNCTION repository.create_document(p_sha256 TEXT, p_filename TEXT, p_authority TEXT)
RETURNS UUID LANGUAGE sql AS $$
    INSERT INTO repository.documents (sha256, filename, authority)
    VALUES (p_sha256, p_filename, p_authority)
    RETURNING id;
$$;

CREATE OR REPLACE FUNCTION repository.rebuild_embeddings(p_document_id UUID)
RETURNS VOID LANGUAGE sql AS $$
    -- Marks embeddings for the document as stale by deleting them; regeneration is
    -- performed by the Ingestion pipeline in n8n (§523, R-13). Lightweight only.
    DELETE FROM repository.embeddings e
    USING repository.retrieval_chunks c, repository.knowledge_units k
    WHERE e.chunk_id = c.id AND c.knowledge_unit_id = k.id AND k.document_id = p_document_id;
$$;
