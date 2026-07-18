-- 0016_views.sql — Read-only views supporting dashboards only (§232).
CREATE OR REPLACE VIEW repository.vw_repository_summary AS
    SELECT (SELECT count(*) FROM repository.documents)       AS documents,
           (SELECT count(*) FROM repository.knowledge_units) AS knowledge_units,
           (SELECT count(*) FROM repository.evidence)        AS evidence,
           (SELECT count(*) FROM repository.retrieval_chunks) AS chunks,
           (SELECT count(*) FROM repository.embeddings)      AS embeddings;

CREATE OR REPLACE VIEW repository.vw_document_statistics AS
    SELECT status, count(*) AS document_count
    FROM repository.documents GROUP BY status;

CREATE OR REPLACE VIEW repository.vw_knowledge_statistics AS
    SELECT category, count(*) AS knowledge_count
    FROM repository.knowledge_units GROUP BY category;

CREATE OR REPLACE VIEW repository.vw_embedding_statistics AS
    SELECT provider, model, count(*) AS embedding_count
    FROM repository.embeddings GROUP BY provider, model;

CREATE OR REPLACE VIEW repository.vw_repository_health AS
    SELECT DISTINCT ON (component) component, state, checked_at
    FROM monitoring.health_checks
    ORDER BY component, checked_at DESC;
