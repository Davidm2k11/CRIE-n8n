-- 0022_processing_history.sql — monitoring.processing_history (§239.1, §424, §591).
-- Append-only per-document lifecycle log; backs checkpoints (§372, R-18).
CREATE TABLE IF NOT EXISTS monitoring.processing_history (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id    UUID NOT NULL,
    stage          TEXT NOT NULL,
    status         TEXT NOT NULL,
    correlation_id TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_processing_history_documents
        FOREIGN KEY (document_id) REFERENCES repository.documents (id) ON DELETE CASCADE,
    CONSTRAINT chk_processing_history_stage CHECK (stage IN (
        'Upload','OCR','KnowledgeExtraction','ChunkGeneration',
        'Embeddings','Certification','Archive')),
    CONSTRAINT chk_processing_history_status CHECK (status IN ('PENDING','COMPLETED','FAILED'))
);
CREATE INDEX IF NOT EXISTS idx_processing_history_document_stage
    ON monitoring.processing_history (document_id, stage);

-- Append-only enforcement (§239.1): block UPDATE/DELETE.
CREATE OR REPLACE FUNCTION monitoring.deny_mutation()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'append-only table: % not permitted', TG_OP;
END $$;
DROP TRIGGER IF EXISTS trg_processing_history_append_only ON monitoring.processing_history;
CREATE TRIGGER trg_processing_history_append_only
    BEFORE UPDATE OR DELETE ON monitoring.processing_history
    FOR EACH ROW EXECUTE FUNCTION monitoring.deny_mutation();
