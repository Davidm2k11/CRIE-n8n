-- Rollback 0013.
DROP INDEX IF EXISTS repository.idx_embeddings_hnsw_cosine;
DROP INDEX IF EXISTS repository.idx_retrieval_chunks_content_trgm;
