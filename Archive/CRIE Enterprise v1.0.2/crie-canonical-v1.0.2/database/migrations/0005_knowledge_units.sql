-- 0005_knowledge_units.sql — repository.knowledge_units core table (§222).
-- Ontology/classification/lifecycle columns are ADDED additively in 0018 (R-15);
-- core structure here is unchanged.
CREATE TABLE IF NOT EXISTS repository.knowledge_units (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id  UUID NOT NULL,
    content      TEXT NOT NULL,
    category     TEXT,                -- constrained to §438 enum in 0018 (R-05)
    authority    TEXT,
    status       TEXT NOT NULL DEFAULT 'Draft',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_knowledge_units_documents
        FOREIGN KEY (document_id) REFERENCES repository.documents (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_knowledge_units_authority   ON repository.knowledge_units (authority);
CREATE INDEX IF NOT EXISTS idx_knowledge_units_category    ON repository.knowledge_units (category);
CREATE INDEX IF NOT EXISTS idx_knowledge_units_status      ON repository.knowledge_units (status);
CREATE INDEX IF NOT EXISTS idx_knowledge_units_document_id ON repository.knowledge_units (document_id);
