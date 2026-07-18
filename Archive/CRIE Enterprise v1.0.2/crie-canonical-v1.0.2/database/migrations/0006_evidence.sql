-- 0006_evidence.sql — repository.evidence (§223).
CREATE TABLE IF NOT EXISTS repository.evidence (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    knowledge_unit_id UUID NOT NULL,
    excerpt           TEXT,
    authority         TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_evidence_knowledge_units
        FOREIGN KEY (knowledge_unit_id) REFERENCES repository.knowledge_units (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_evidence_knowledge_unit_id ON repository.evidence (knowledge_unit_id);
CREATE INDEX IF NOT EXISTS idx_evidence_authority         ON repository.evidence (authority);
