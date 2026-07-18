-- 0003_documents.sql — repository.documents (§220). No foreign keys.
CREATE TABLE IF NOT EXISTS repository.documents (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sha256       TEXT NOT NULL,
    filename     TEXT,
    status       TEXT NOT NULL DEFAULT 'Uploaded',
    authority    TEXT,
    uploaded_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_documents_sha256 UNIQUE (sha256)   -- immutable fingerprint (§242)
);
CREATE INDEX IF NOT EXISTS idx_documents_status      ON repository.documents (status);
CREATE INDEX IF NOT EXISTS idx_documents_authority   ON repository.documents (authority);
CREATE INDEX IF NOT EXISTS idx_documents_uploaded_at ON repository.documents (uploaded_at);
