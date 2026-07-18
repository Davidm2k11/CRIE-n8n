-- 0007_citations.sql — repository.citations (§224).
-- Keys on BOTH evidence_id and document_id (R-06); serialized citations also
-- carry evidenceId (contract-level, not a schema change).
CREATE TABLE IF NOT EXISTS repository.citations (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    evidence_id  UUID NOT NULL,
    document_id  UUID NOT NULL,
    page         INTEGER,
    section      TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_citations_evidence
        FOREIGN KEY (evidence_id) REFERENCES repository.evidence (id) ON DELETE CASCADE,
    CONSTRAINT fk_citations_documents
        FOREIGN KEY (document_id) REFERENCES repository.documents (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_citations_document_id ON repository.citations (document_id);
CREATE INDEX IF NOT EXISTS idx_citations_page        ON repository.citations (page);
CREATE INDEX IF NOT EXISTS idx_citations_section     ON repository.citations (section);
