-- 0013_indexes.sql — Vector index + supporting indexes (§227, §13 indexes).
-- The vector index TYPE and parameters are config-driven (§227: "Configuration
-- determines implementation"). This migration creates the HNSW default; the seed
-- step (0017) reads embedding.vectorIndex from providers.yaml and, if a different
-- type/params are configured, recreates the index accordingly WITHOUT source edits.
--
-- Default: HNSW with cosine ops (§227). Fallback: IVFFlat (created by seed step
-- when embedding.vectorIndex.type = ivfflat).
CREATE INDEX IF NOT EXISTS idx_embeddings_hnsw_cosine
    ON repository.embeddings
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Trigram index to support keyword retrieval (§458) on chunk content.
CREATE INDEX IF NOT EXISTS idx_retrieval_chunks_content_trgm
    ON repository.retrieval_chunks
    USING gin (content gin_trgm_ops);
