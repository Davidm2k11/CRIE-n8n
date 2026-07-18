-- 0009_embeddings.sql — repository.embeddings (§226).
-- Vector column fixed at vector(1536) for v1 (R-09). Provider is config-driven
-- among 1536-dimension models; a different dimension requires a migration + re-embed.
CREATE TABLE IF NOT EXISTS repository.embeddings (
    id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    chunk_id   UUID NOT NULL,
    embedding  vector(1536) NOT NULL,
    provider   TEXT,                 -- config-driven (§226)
    model      TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_embeddings_retrieval_chunks
        FOREIGN KEY (chunk_id) REFERENCES repository.retrieval_chunks (id) ON DELETE CASCADE
);
-- Vector index is created in 0013 (type/params config-driven per §227).
