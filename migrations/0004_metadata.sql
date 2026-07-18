-- 0004_metadata.sql — repository.metadata (§221).
CREATE TABLE IF NOT EXISTS repository.metadata (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id  UUID NOT NULL,
    key          TEXT NOT NULL,
    value        TEXT,
    CONSTRAINT fk_metadata_documents
        FOREIGN KEY (document_id) REFERENCES repository.documents (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_metadata_document_id ON repository.metadata (document_id);
CREATE INDEX IF NOT EXISTS idx_metadata_key         ON repository.metadata (key);
CREATE INDEX IF NOT EXISTS idx_metadata_value       ON repository.metadata (value);
