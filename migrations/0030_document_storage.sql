-- =====================================================================
-- CRIE — Migration 0030_document_storage.sql
-- Object-storage reference for the original uploaded file.
-- Spec refs: §242 (sha256 immutable fingerprint), §310/§320 (storage config).
-- Docs: CRIE_Document_Lifecycle_Object_Storage_Standard.md §4;
--       configuration/storage.yaml (canonical storage configuration, R-08).
--
-- All Rights Reserved, Copyright (c) 2026 Dawod Manasra. Unauthorized copying,
-- modification, distribution, or commercial use is prohibited without written
-- permission.
--
-- ADDITIVE ONLY. Adds five NULLABLE columns and one index to
-- repository.documents. Edits NO historical migration, relaxes NO constraint,
-- writes NO data, and drops nothing. Safe on a populated database: every
-- existing row keeps NULL storage columns until it is backfilled.
--
-- WHY THIS EXISTS: the original file is to be stored exactly once in object
-- storage, after which workflows carry only the reference tuple
-- { documentId, sha256, storageKey, correlationId } and never the binary.
-- These columns are where that reference is persisted. sha256 (0003) remains
-- the content fingerprint; storage_key is the LOCATION. Both are carried in
-- the tuple.
--
-- RECORDED DESIGN DECISIONS (final; do not re-derive):
--   D1  This is migration 0030. 0029 is the orphan sweep.
--   D3  repository.document_blobs (integrity/verified_at table) is DEFERRED.
--       It is intentionally NOT created here — nothing reads it until the
--       storage-integrity job exists.
--   D4  documentId is generated BEFORE storage_key is computed, because the
--       key embeds it. Registration therefore accepts an explicit id rather
--       than relying on the DEFAULT uuid_generate_v4(); the ON CONFLICT
--       (sha256) upsert behaviour is unchanged.
--   D5  Erasure (GDPR / retention deletion) is OUT OF SCOPE for this
--       workstream. A documents row cannot currently be deleted at all: the
--       ON DELETE CASCADE from monitoring.processing_history (0022) fires that
--       table's append-only trigger, which raises. Object-side deletion only.
--
-- RLS: repository.documents already has row-level security enabled (0014) and
-- the p_service_all / p_read_repository policies apply to the whole row, so
-- new columns are covered without policy changes. No policy is added here.
--
-- Rollback: additive and unread until the ingestion cutover, so reverting the
-- commit is sufficient; the columns may also be left in place harmlessly.
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------------
-- Storage reference columns. ALL NULLABLE — the migration must be safe on
-- existing rows, and storage_key is populated at ingestion going forward.
-- ---------------------------------------------------------------------
ALTER TABLE repository.documents
    ADD COLUMN IF NOT EXISTS storage_key    TEXT,
    ADD COLUMN IF NOT EXISTS storage_bucket TEXT,
    ADD COLUMN IF NOT EXISTS byte_size      BIGINT,
    ADD COLUMN IF NOT EXISTS content_type   TEXT,
    ADD COLUMN IF NOT EXISTS stored_at      TIMESTAMPTZ;

-- Lookup by object path (reconciliation, integrity checks, operator queries).
CREATE INDEX IF NOT EXISTS idx_documents_storage_key
    ON repository.documents (storage_key);

-- ---------------------------------------------------------------------
-- Column documentation. These comments carry the rules a future author needs
-- at the point of use; the full rationale lives in storage.yaml and the
-- Object Storage standard.
-- ---------------------------------------------------------------------
COMMENT ON COLUMN repository.documents.storage_key IS
    'Full object path within the storage bucket; the single source of truth for '
    'locating the original file. Template: '
    'originals/{yyyy}/{mm}/{dd}/{documentId}/{sha256}.{ext} (see '
    'configuration/storage.yaml keyTemplate). The date partition MUST be derived '
    'from documents.uploaded_at, NOT from wall-clock time at upload: deriving it '
    'from the clock gives a re-ingested document a second key, leaving the first '
    'object orphaned. The bucket name is environment config and is deliberately '
    'NOT part of the key, so the same key resolves in every environment. '
    'Never encode secrets or PII in the key.';

COMMENT ON COLUMN repository.documents.storage_bucket IS
    'Environment-resolved bucket holding the object, e.g. crie-documents-prod. '
    'Recorded per row so an object remains locatable after the configured '
    'bucketPattern changes. Private bucket; access is via short-lived signed URL '
    'or service-role key.';

COMMENT ON COLUMN repository.documents.byte_size IS
    'Size in bytes of the stored original. Used for integrity checks and for '
    'enforcing the OCR provider size limit before the expensive OCR step.';

COMMENT ON COLUMN repository.documents.content_type IS
    'Validated MIME type of the STORED BYTES, and the source of {ext} in '
    'storage_key. It MUST be derived from the downloaded bytes, not from the '
    'Google Drive mimeType carried through the pipeline: WF-001 downloads with '
    'googleFileConversion, so a Google-native document arrives as application/pdf '
    'while Drive still reports application/vnd.google-apps.document. Trusting '
    'the Drive value would key those objects with the wrong extension.';

COMMENT ON COLUMN repository.documents.stored_at IS
    'When the original was successfully persisted to object storage. NULL means '
    'no stored original: either a pre-storage document awaiting backfill, or an '
    'ingestion that did not reach the storage step.';

COMMIT;
